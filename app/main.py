from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from io import BytesIO
import json
import logging
import os
import re
from time import perf_counter
from pathlib import Path
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, text
from sqlalchemy import inspect
from sqlalchemy.orm import Session, joinedload
from starlette.middleware.sessions import SessionMiddleware

from .auth import verify_password
from .config import SESSION_SECRET
from .database import Base, SessionLocal, engine, get_db, raw_database_url
from .dependencies import get_current_user, require_roles
from .models import AuditLog, BankMutation, BranchInput, MatchingResult, User
from .seed import seed_data
from .services.branch_inputs import archive_all_branch_inputs_with_results, archive_branch_input_with_results
from .services.analytics import build_global_region_ranking, build_monitoring_context, filter_options, filtered_results
from .services.matching_engine import run_matching
from .services.organization import ORGANIZATION_ROWS
from .services.rule_config import RULE_CONFIG
from .services.reports import build_excel_report, build_pdf_report, build_ranked_excel_report, summarize_by_location
from .services.system_status import get_database_warning, get_system_status

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="FEWS Approval Monitoring")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
storage_dir = BASE_DIR.parent / "storage"
if storage_dir.exists():
    app.mount("/storage", StaticFiles(directory=str(storage_dir)), name="storage")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
logger = logging.getLogger("fews.performance")


@app.middleware("http")
async def add_server_timing(request: Request, call_next):
    started_at = perf_counter()
    response = await call_next(request)
    duration_ms = (perf_counter() - started_at) * 1000
    response.headers["Server-Timing"] = f"app;dur={duration_ms:.1f}"
    response.headers["X-FEWS-Response-Time-Ms"] = f"{duration_ms:.1f}"
    if duration_ms >= 1000:
        logger.warning("Slow request %s %s took %.1f ms", request.method, request.url.path, duration_ms)
    return response

DAY_NAMES_ID = {
    0: "Senin",
    1: "Selasa",
    2: "Rabu",
    3: "Kamis",
    4: "Jumat",
    5: "Sabtu",
    6: "Minggu",
}


def _format_date_id(value) -> str:
    if not value:
        return "-"
    parsed = _to_date(value) if isinstance(value, str) else value
    if isinstance(parsed, datetime):
        parsed = parsed.date()
    if not isinstance(parsed, date):
        return str(value)
    return f"{DAY_NAMES_ID[parsed.weekday()]}, {parsed:%d/%m/%Y}"


def _format_datetime_id(value) -> str:
    if not value:
        return "-"
    parsed = _to_datetime(value) if isinstance(value, str) else value
    if isinstance(parsed, date) and not isinstance(parsed, datetime):
        return _format_date_id(parsed)
    if not isinstance(parsed, datetime):
        return str(value)
    return f"{DAY_NAMES_ID[parsed.weekday()]}, {parsed:%d/%m/%Y %H:%M}"


templates.env.filters["date_id"] = _format_date_id
templates.env.filters["datetime_id"] = _format_datetime_id


HEADER_ALIASES = {
    "transaction_date": ["tanggal transaksi", "tanggal", "tgl transaksi", "tgl", "tgl bukubesar", "tgl_bukubesar", "tanggal pembayaran"],
    "branch_name": ["nama cabang", "cabang", "nama lokasi", "lokasi", "location", "kodelokasi", "kode lokasi"],
    "customer_name": ["nama customer", "customer", "nama pelanggan", "pelanggan", "nama siswa", "siswa", "keterangan_dr_lokasi", "keterangan dr lokasi"],
    "amount_should_pay": ["nominal yang harus dibayar", "nominal harus bayar", "nominal harus dibayar", "amount should pay", "jumlah_biaya", "jumlah biaya", "nominal transaksi"],
    "amount_input_branch": ["nominal yang diinput cabang", "nominal input cabang", "nominal input", "amount input", "nominal dibayar", "jumlah_setor", "jumlah setor", "nominal setor"],
    "payment_method": ["metode pembayaran", "metode", "payment method", "cara bayar", "bank", "pilihan_bank", "pilihan bank", "tipe bayar"],
    "invoice_code": ["kode unik/invoice", "kode unik", "invoice", "kode invoice", "nomor invoice", "no invoice", "idunix", "id unix", "id unix/idunix"],
    "notes": ["keterangan", "catatan", "notes", "remark", "catatan", "nokwt_awal", "nokwt_akhir"],
    "transaction_time": ["jam transaksi", "waktu transaksi", "jam", "jam input"],
    "source_created_at": ["created_at", "waktu_input", "tgl input", "tanggal input", "input_at", "input at", "tanggal input data", "waktu input"],
    "payment_received_at": ["tanggal pembayaran", "waktu pembayaran", "payment_received_at", "pembayaran diterima", "tanggal transfer"],
    "deposit_date": ["tanggal setoran", "tanggal setor", "tgl setor", "tgl setoran", "deposit_date", "tanggal data setor"],
    "approved_at": ["tgl_approve", "tanggal approve", "approved_at", "approval_at", "approve_at"],
    "bank_date": ["tgl_bank", "tanggal bank", "bank_date", "tanggal dana masuk", "tanggal bank masuk"],
    "bank_time": ["waktu_bank", "waktu bank", "jam bank", "jam setoran", "waktu setoran"],
    "officer_id": ["pegawai", "petugas", "petugas_id", "user_input", "user id", "nopeg penginput transaksi", "nopeg input transaksi"],
    "deposit_officer_id": ["nopeg penginput setoran", "nopeg input setoran", "petugas setoran", "user setor", "user_setor"],
    "approver_id": ["approve_by", "approved_by", "approver", "approver_id", "user_approve"],
    "bank_target": ["bank tujuan", "bank yang dipilih", "bank input", "pilihan bank", "pilihan_bank"],
    "proof_bank": ["bank bukti", "bank pada bukti", "bukti bank", "bank_bukti"],
    "destination_account": ["rekening tujuan", "rekening penerimaan", "rekening penerima", "norek tujuan", "norek penerimaan"],
    "proof_reference": ["bukti transaksi", "nomor bukti", "no bukti", "referensi bukti", "proof_reference"],
    "student_list": ["daftar siswa", "list siswa", "siswa kolektif", "daftar siswa setoran kolektif"],
    "incoming_date": ["tanggal dana masuk", "tgl dana masuk", "incoming_date", "incoming date", "tanggal", "tgl", "tgl_bank", "tanggal mutasi"],
    "sender_name": ["nama pengirim", "pengirim", "sender", "sender_name", "nama pengirim transfer", "dari", "keterangan_dr_lokasi"],
    "amount_in": ["nominal masuk", "jumlah masuk", "amount in", "jumlah_setor", "nominal", "kredit"],
    "company_account": ["rekening perusahaan", "rekening", "no rekening", "account", "norek", "rekening tujuan"],
    "mutation_description": ["deskripsi mutasi", "deskripsi", "keterangan mutasi", "mutation_description", "pilihan_bank", "bukti_bank di relasikan ke gd mutasi bank"],
    "mutation_notes": ["keterangan", "catatan", "notes", "remark", "catatan mutasi"],
}


def init_db():
    Base.metadata.create_all(bind=engine)
    _run_schema_migrations()
    db = SessionLocal()
    try:
        seed_data(db)
    finally:
        db.close()


def _table_columns(table_name: str) -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns(table_name)}


def _add_column_if_missing(table_name: str, column_name: str, sqlite_sql: str, postgres_sql: str | None = None) -> None:
    existing = _table_columns(table_name)
    if column_name in existing:
        return
    column_sql = postgres_sql if engine.dialect.name.startswith("postgres") and postgres_sql else sqlite_sql
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"))


def _run_schema_migrations() -> None:
    # Lightweight migration untuk kompatibilitas DB lama.
    _add_column_if_missing("branch_inputs", "transaction_time", "VARCHAR(20)")
    _add_column_if_missing("branch_inputs", "source_created_at", "DATETIME", "TIMESTAMP")
    _add_column_if_missing("branch_inputs", "approved_at", "DATETIME", "TIMESTAMP")
    _add_column_if_missing("branch_inputs", "bank_date", "DATE")
    _add_column_if_missing("branch_inputs", "officer_id", "VARCHAR(60)")
    _add_column_if_missing("branch_inputs", "deposit_officer_id", "VARCHAR(60)")
    _add_column_if_missing("branch_inputs", "approver_id", "VARCHAR(60)")
    _add_column_if_missing("branch_inputs", "payment_received_at", "DATETIME", "TIMESTAMP")
    _add_column_if_missing("branch_inputs", "deposit_date", "DATE")
    _add_column_if_missing("branch_inputs", "bank_target", "VARCHAR(80)")
    _add_column_if_missing("branch_inputs", "proof_bank", "VARCHAR(80)")
    _add_column_if_missing("branch_inputs", "destination_account", "VARCHAR(100)")
    _add_column_if_missing("branch_inputs", "proof_reference", "VARCHAR(150)")
    _add_column_if_missing("branch_inputs", "student_list", "TEXT")
    _add_column_if_missing("branch_inputs", "source_file_name", "VARCHAR(255)")
    _add_column_if_missing("branch_inputs", "source_row_number", "INTEGER")
    _add_column_if_missing("branch_inputs", "archived_at", "DATETIME", "TIMESTAMP")
    _add_column_if_missing("branch_inputs", "correction_reason", "TEXT")
    _add_column_if_missing("branch_inputs", "correction_notes", "TEXT")
    _add_column_if_missing("branch_inputs", "region", "VARCHAR(80) DEFAULT 'Belum Dipetakan'")
    _add_column_if_missing("branch_inputs", "area", "VARCHAR(100) DEFAULT 'Belum Dipetakan'")
    _add_column_if_missing("branch_inputs", "data_type", "VARCHAR(20) DEFAULT 'OPERASIONAL'")
    _add_column_if_missing("users", "region", "VARCHAR(80)")
    _add_column_if_missing("matching_results", "triggered_rules", "TEXT")
    _add_column_if_missing("matching_results", "follow_up_status", "VARCHAR(30) DEFAULT 'OPEN'")
    _add_column_if_missing("matching_results", "follow_up_notes", "TEXT")
    with engine.begin() as conn:
        for region, area, location in ORGANIZATION_ROWS:
            conn.execute(
                text(
                    "UPDATE branch_inputs SET region = :region, area = :area "
                    "WHERE LOWER(TRIM(branch_name)) = LOWER(:location)"
                ),
                {"region": region, "area": area, "location": location.strip()},
            )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_branch_inputs_area ON branch_inputs (area)"))
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_branch_inputs_active_transaction "
                "ON branch_inputs (archived_at, transaction_date, id)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_branch_inputs_source_created_at "
                "ON branch_inputs (source_created_at)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_matching_results_risk_updated "
                "ON matching_results (risk_score, updated_at)"
            )
        )


@app.on_event("startup")
def startup_event():
    if (os.getenv("VERCEL") or os.getenv("VERCEL_ENV")) and not raw_database_url:
        return
    init_db()


def add_log(db: Session, action: str, notes: str, user_id: int | None = None, status: str = "INFO"):
    db.add(AuditLog(user_id=user_id, action=action, notes=notes, status=status))
    db.commit()


WORKFLOW_TRANSITIONS = {
    "OPEN": {"CLARIFICATION", "HOLD", "RETURN", "INVESTIGATION", "RESOLVED"},
    "CLARIFICATION": {"HOLD", "RETURN", "INVESTIGATION", "RESOLVED"},
    "HOLD": {"CLARIFICATION", "RETURN", "INVESTIGATION", "RESOLVED"},
    "RETURN": {"CLARIFICATION", "INVESTIGATION", "RESOLVED"},
    "INVESTIGATION": {"HOLD", "RETURN", "RESOLVED"},
    "RESOLVED": set(),
}


def _normalize_header(value: str) -> str:
    return "".join(ch for ch in str(value).strip().lower() if ch.isalnum() or ch.isspace()).strip()


def _alias_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for field_name, aliases in HEADER_ALIASES.items():
        lookup[_normalize_header(field_name)] = field_name
        for alias in aliases:
            lookup[_normalize_header(alias)] = field_name
    return lookup


def _header_score(values) -> int:
    lookup = _alias_lookup()
    fields = set()
    for value in values:
        normalized = _normalize_header(value)
        if normalized in lookup:
            fields.add(lookup[normalized])
    required_fields = {"transaction_date", "branch_name", "customer_name", "amount_input_branch", "invoice_code"}
    required_hits = len(fields & required_fields)
    return (required_hits * 3) + len(fields)


def _normalize_upload_dataframe(df):
    if df.empty:
        return df

    current_score = _header_score(df.columns)
    if current_score >= 12:
        df.attrs["source_row_offset"] = 2
        return df

    best_idx = None
    best_score = current_score
    search_limit = min(len(df), 10)
    for idx in range(search_limit):
        score = _header_score(df.iloc[idx].tolist())
        if score > best_score:
            best_idx = idx
            best_score = score

    if best_idx is None or best_score < 12:
        df.attrs["source_row_offset"] = 2
        return df

    promoted = df.iloc[best_idx + 1 :].copy()
    promoted.columns = [str(value).strip() for value in df.iloc[best_idx].tolist()]
    promoted = promoted.dropna(how="all").reset_index(drop=True)
    # With pandas' default header row, dataframe row 0 maps to Excel row 2.
    promoted.attrs["source_row_offset"] = best_idx + 3
    return promoted


def _to_float(value) -> float | None:
    import pandas as pd

    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip().replace("Rp", "").replace("rp", "").replace(" ", "")
    raw = raw.replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _is_blank_cell(value) -> bool:
    import pandas as pd

    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return str(value).strip() in {"", "\\N", "nan", "NaN", "None"}


def _to_datetime(value) -> datetime | None:
    import pandas as pd

    raw = str(value).strip() if value is not None else ""
    year_first = bool(re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}", raw))
    ts = pd.to_datetime(value, errors="coerce", dayfirst=not year_first)
    if pd.isna(ts):
        return None
    return ts.to_pydatetime()


def _to_date(value):
    import pandas as pd

    raw = str(value).strip() if value is not None else ""
    year_first = bool(re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}", raw))
    ts = pd.to_datetime(value, errors="coerce", dayfirst=not year_first)
    if pd.isna(ts):
        return None
    return ts.date()


def _to_time(value) -> time | None:
    import pandas as pd

    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, time):
        return value.replace(tzinfo=None)
    if isinstance(value, datetime):
        return value.time().replace(tzinfo=None)
    ts = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if not pd.isna(ts):
        return ts.to_pydatetime().time().replace(tzinfo=None)
    raw = str(value).strip()
    match = re.search(r"(\d{1,2})[:.](\d{2})(?::(\d{2}))?", raw)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    second = int(match.group(3) or 0)
    if 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59:
        return time(hour, minute, second)
    return None


def _combine_date_time(date_value, time_value) -> datetime | None:
    parsed_date = _to_date(date_value)
    parsed_time = _to_time(time_value)
    if not parsed_date or not parsed_time:
        return None
    return datetime.combine(parsed_date, parsed_time)


def _read_upload_dataframe(upload_file: UploadFile):
    import pandas as pd

    data = upload_file.file.read()
    filename = (upload_file.filename or "").lower()
    if filename.endswith(".csv"):
        return _normalize_upload_dataframe(pd.read_csv(BytesIO(data)))
    return _normalize_upload_dataframe(pd.read_excel(BytesIO(data)))


def _extract_column(df, field_name: str, required: bool = True) -> str | None:
    normalized_map = {_normalize_header(col): col for col in df.columns}
    for alias in HEADER_ALIASES[field_name]:
        found = normalized_map.get(_normalize_header(alias))
        if found:
            return found
    if required:
        raise ValueError(f"Header untuk '{field_name}' tidak ditemukan.")
    return None


def _dashboard_summary(db: Session, region: str = ""):
    branch_filters = [BranchInput.archived_at.is_(None)]
    result_filters = [BranchInput.archived_at.is_(None)]
    if region:
        branch_filters.append(BranchInput.region == region)
        result_filters.append(BranchInput.region == region)

    total_branch = db.query(func.count(BranchInput.id)).filter(*branch_filters).scalar() or 0
    status_counter = dict(
        db.query(MatchingResult.status, func.count(MatchingResult.id))
        .join(BranchInput, MatchingResult.branch_input_id == BranchInput.id)
        .filter(*result_filters)
        .group_by(MatchingResult.status)
        .all()
    )
    total_high_alert = (
        db.query(func.count(MatchingResult.id))
        .join(BranchInput, MatchingResult.branch_input_id == BranchInput.id)
        .filter(*result_filters, MatchingResult.risk_score > 7)
        .scalar()
        or 0
    )
    trend_rows = (
        db.query(BranchInput.transaction_date, func.count(BranchInput.id))
        .filter(*branch_filters)
        .group_by(BranchInput.transaction_date)
        .order_by(BranchInput.transaction_date.desc())
        .limit(10)
        .all()
    )
    trend_rows.reverse()
    sorted_labels = [row[0].isoformat() for row in trend_rows]
    branch_series = [row[1] for row in trend_rows]
    trend_max = max(branch_series) if branch_series else 1

    mismatch_counter = Counter()
    rule_payloads = (
        db.query(MatchingResult.triggered_rules)
        .join(BranchInput, MatchingResult.branch_input_id == BranchInput.id)
        .filter(*result_filters, MatchingResult.triggered_rules.is_not(None))
        .all()
    )
    for (triggered_rules,) in rule_payloads:
        try:
            rules = json.loads(triggered_rules or "[]")
        except json.JSONDecodeError:
            rules = []
        for rule in rules:
            label = rule.get("name") or rule.get("code") or "Indikator tidak dikenal"
            mismatch_counter[label] += 1
    indicator_rows = [
        {"label": label, "value": value}
        for label, value in mismatch_counter.most_common(8)
    ]
    suspicious_results = (
        db.query(MatchingResult)
        .options(joinedload(MatchingResult.branch_input))
        .join(BranchInput, MatchingResult.branch_input_id == BranchInput.id)
        .filter(*result_filters, MatchingResult.risk_score > 7)
        .order_by(MatchingResult.risk_score.desc(), MatchingResult.updated_at.desc())
        .limit(15)
        .all()
    )

    return {
        "total_branch": total_branch,
        "total_matched": status_counter.get("MATCHED", 0),
        "total_need_review": status_counter.get("NEED REVIEW", 0),
        "total_unmatched": status_counter.get("UNMATCHED", 0),
        "total_high_alert": total_high_alert,
        "trend_labels": sorted_labels,
        "trend_branch": branch_series,
        "trend_max": trend_max,
        "indicator_rows": indicator_rows,
        "mismatch_labels": [row["label"] for row in indicator_rows],
        "mismatch_values": [row["value"] for row in indicator_rows],
        "suspicious_results": suspicious_results,
        "rule_config": RULE_CONFIG,
    }


def _build_periodic_summary(db: Session, period: str = "harian") -> dict:
    now = datetime.utcnow()
    if period == "mingguan":
        cutoff = now - timedelta(days=7)
    elif period == "bulanan":
        cutoff = now - timedelta(days=30)
    else:
        cutoff = now - timedelta(days=1)
    scoped = (
        db.query(MatchingResult)
        .options(joinedload(MatchingResult.branch_input))
        .join(BranchInput, MatchingResult.branch_input_id == BranchInput.id)
        .filter(
            BranchInput.archived_at.is_(None),
            MatchingResult.created_at >= cutoff,
        )
        .order_by(MatchingResult.created_at.desc())
        .all()
    )
    location_rows = summarize_by_location(scoped)
    return {
        "total": len(scoped),
        "high": sum(1 for r in scoped if r.risk_score > 7),
        "medium": sum(1 for r in scoped if 4 <= r.risk_score <= 7),
        "low": sum(1 for r in scoped if r.risk_score <= 3),
        "period": period,
        "rows": scoped[:100],
        "location_rows": location_rows,
        "location_total": len(location_rows),
    }


def _attach_rule_details(rows: list[MatchingResult]) -> list[MatchingResult]:
    for row in rows:
        try:
            row.rule_details = json.loads(row.triggered_rules or "[]")
        except json.JSONDecodeError:
            row.rule_details = []
    return rows


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return RedirectResponse("/dashboard" if request.session.get("user_id") else "/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login", response_class=HTMLResponse)
def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Username atau password salah."}, status_code=400)
    request.session["user_id"] = user.id
    add_log(db, "Login", f"User {user.username} login ke sistem.", user_id=user.id)
    return RedirectResponse("/dashboard", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    region: str = "",
    area: str = "",
    location: str = "",
    month: str = "",
    indicator: str = "",
    verification: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    filters = {
        "region": region,
        "area": area,
        "location": location,
        "month": month,
        "indicator": indicator,
        "verification": verification,
    }
    data = build_monitoring_context(db, user, filters)
    data["global_region_rows"] = build_global_region_ranking(db, user, filters)
    context = {
        "request": request,
        "user": user,
        **data,
        "system_status": get_system_status(),
        "database_warning": get_database_warning(),
    }
    return templates.TemplateResponse("dashboard.html", context)


@app.get("/info", response_class=HTMLResponse)
def info_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    summary = _dashboard_summary(db, user.region or "")
    activity_query = db.query(AuditLog).filter(AuditLog.status.in_(["WARNING", "ALERT"]))
    if user.region:
        activity_query = activity_query.filter(AuditLog.user_id == user.id)
    return templates.TemplateResponse(
        "info.html",
        {
            "request": request,
            "user": user,
            **summary,
            "latest_alerts": activity_query.order_by(AuditLog.created_at.desc()).limit(12).all(),
            "database_warning": get_database_warning(),
            "scope_label": user.region or "Nasional",
        },
    )


@app.get("/branch-inputs", response_class=HTMLResponse)
def branch_inputs_page(
    request: Request,
    imported: int = 0,
    failed: int = 0,
    msg: str = "",
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return RedirectResponse("/reports", status_code=303)
    page = max(1, page)
    per_page = min(max(10, per_page), 100)
    query = db.query(BranchInput).filter(BranchInput.archived_at.is_(None))
    total_rows = query.count()
    total_pages = max(1, (total_rows + per_page - 1) // per_page)
    page = min(page, total_pages)
    rows = (
        query.order_by(BranchInput.transaction_date.desc(), BranchInput.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return templates.TemplateResponse(
        "branch_inputs.html",
        {
            "request": request,
            "user": user,
            "rows": rows,
            "imported": imported,
            "failed": failed,
            "msg": msg,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_rows": total_rows,
                "total_pages": total_pages,
                "has_prev": page > 1,
                "has_next": page < total_pages,
            },
        },
    )


@app.post("/branch-inputs/new")
def create_branch_input(
    transaction_date: str = Form(...),
    branch_name: str = Form(...),
    customer_name: str = Form(...),
    amount_should_pay: float = Form(...),
    amount_input_branch: float = Form(...),
    payment_method: str = Form(...),
    invoice_code: str = Form(...),
    transaction_time: str = Form(""),
    bank_date: str = Form(""),
    deposit_date: str = Form(""),
    payment_received_at: str = Form(""),
    officer_id: str = Form(""),
    deposit_officer_id: str = Form(""),
    approver_id: str = Form(""),
    approved_at: str = Form(""),
    bank_target: str = Form(""),
    proof_bank: str = Form(""),
    destination_account: str = Form(""),
    proof_reference: str = Form(""),
    student_list: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "auditor")),
):
    return Response(status_code=410, content="Manual input sudah dinonaktifkan. Gunakan integrasi data terkontrol.")
    row = BranchInput(
        transaction_date=datetime.strptime(transaction_date, "%Y-%m-%d").date(),
        branch_name=branch_name,
        customer_name=customer_name,
        amount_should_pay=amount_should_pay,
        amount_input_branch=amount_input_branch,
        payment_method=payment_method,
        invoice_code=invoice_code,
        transaction_time=transaction_time or None,
        bank_date=datetime.strptime(bank_date, "%Y-%m-%d").date() if bank_date else None,
        deposit_date=datetime.strptime(deposit_date, "%Y-%m-%d").date() if deposit_date else None,
        payment_received_at=_to_datetime(payment_received_at) if payment_received_at else None,
        officer_id=officer_id or None,
        deposit_officer_id=deposit_officer_id or None,
        approver_id=approver_id or None,
        approved_at=_to_datetime(approved_at) if approved_at else None,
        bank_target=bank_target or None,
        proof_bank=proof_bank or None,
        destination_account=destination_account or None,
        proof_reference=proof_reference or None,
        student_list=student_list or None,
        notes=notes or None,
    )
    db.add(row)
    db.commit()
    run_matching(db)
    add_log(db, "Input Cabang", f"Input cabang baru #{row.id} oleh {user.username}", user_id=user.id, status="INFO")
    return RedirectResponse("/branch-inputs", status_code=303)


@app.post("/branch-inputs/{branch_input_id}/delete")
def delete_branch_input(
    branch_input_id: int,
    correction_reason: str = Form("Koreksi data approval"),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "auditor")),
):
    deleted = archive_branch_input_with_results(db, branch_input_id, user_id=user.id, reason=correction_reason)
    if deleted:
        run_matching(db)
        add_log(db, "Koreksi/Arsip Data Approval", f"Data approval #{branch_input_id} diarsipkan oleh {user.username}. Alasan: {correction_reason}", user_id=user.id, status="INFO")
    else:
        add_log(db, "Koreksi/Arsip Data Approval Gagal", f"Data approval #{branch_input_id} tidak ditemukan.", user_id=user.id, status="WARNING")
    return RedirectResponse("/branch-inputs", status_code=303)


@app.post("/branch-inputs/delete-all")
def delete_all_branch_inputs(
    correction_reason: str = Form("Koreksi semua data approval"),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "auditor")),
):
    deleted_count = archive_all_branch_inputs_with_results(db, user_id=user.id, reason=correction_reason)
    add_log(db, "Koreksi/Arsip Semua Data Approval", f"{deleted_count} data approval diarsipkan oleh {user.username}. Alasan: {correction_reason}", user_id=user.id, status="WARNING")
    return RedirectResponse("/branch-inputs?imported=0&failed=0&msg=Data approval berhasil diarsipkan", status_code=303)


@app.post("/branch-inputs/upload")
def upload_branch_input_excel(
    request: Request,
    excel_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "auditor")),
):
    return Response(status_code=410, content="Upload Excel melalui UI sudah dinonaktifkan.")
    try:
        df = _read_upload_dataframe(excel_file)
    except Exception:
        return RedirectResponse("/branch-inputs?imported=0&failed=0&msg=Format file tidak bisa dibaca", status_code=303)

    if df.empty:
        return RedirectResponse("/branch-inputs?imported=0&failed=0&msg=File kosong", status_code=303)

    try:
        col_date = _extract_column(df, "transaction_date", required=True)
        col_branch = _extract_column(df, "branch_name", required=True)
        col_customer = _extract_column(df, "customer_name", required=True)
        col_input = _extract_column(df, "amount_input_branch", required=True)
        col_invoice = _extract_column(df, "invoice_code", required=True)
        col_should = _extract_column(df, "amount_should_pay", required=False)
        col_payment = _extract_column(df, "payment_method", required=False)
        col_notes = _extract_column(df, "notes", required=False)
        col_trx_time = _extract_column(df, "transaction_time", required=False)
        col_source_created = _extract_column(df, "source_created_at", required=False)
        col_payment_received = _extract_column(df, "payment_received_at", required=False)
        col_deposit_date = _extract_column(df, "deposit_date", required=False)
        col_approved = _extract_column(df, "approved_at", required=False)
        col_bank_date = _extract_column(df, "bank_date", required=False)
        col_bank_time = _extract_column(df, "bank_time", required=False)
        col_officer = _extract_column(df, "officer_id", required=False)
        col_deposit_officer = _extract_column(df, "deposit_officer_id", required=False)
        col_approver = _extract_column(df, "approver_id", required=False)
        col_bank_target = _extract_column(df, "bank_target", required=False)
        col_proof_bank = _extract_column(df, "proof_bank", required=False)
        col_destination_account = _extract_column(df, "destination_account", required=False)
        col_proof_reference = _extract_column(df, "proof_reference", required=False)
        col_student_list = _extract_column(df, "student_list", required=False)
    except ValueError as exc:
        msg = quote(str(exc))
        return RedirectResponse(f"/branch-inputs?imported=0&failed=0&msg={msg}", status_code=303)

    inserted_rows: list[BranchInput] = []
    failed_rows: list[str] = []
    source_row_offset = int(df.attrs.get("source_row_offset", 2))

    for idx, item in df.iterrows():
        line_no = idx + source_row_offset
        required_values = [item.get(col_date), item.get(col_branch), item.get(col_customer), item.get(col_input), item.get(col_invoice)]
        if all(_is_blank_cell(value) for value in required_values):
            continue

        trx_date = _to_date(item.get(col_date))
        if not trx_date:
            failed_rows.append(f"Baris {line_no}: tanggal transaksi tidak valid.")
            continue

        amount_input = _to_float(item.get(col_input))
        if amount_input is None:
            failed_rows.append(f"Baris {line_no}: nominal input cabang tidak valid.")
            continue

        amount_should = _to_float(item.get(col_should)) if col_should else amount_input
        if amount_should is None:
            amount_should = amount_input

        invoice_code = str(item.get(col_invoice) or "").strip()
        branch_name = str(item.get(col_branch) or "").strip()
        customer_name = str(item.get(col_customer) or "").strip()
        if not invoice_code or not branch_name or not customer_name:
            failed_rows.append(f"Baris {line_no}: field wajib (cabang/customer/invoice) kosong.")
            continue

        payment_method = str(item.get(col_payment) or "transfer").strip().lower() if col_payment else "transfer"
        if payment_method not in {"transfer", "tunai"}:
            payment_method = "transfer"

        transaction_time = str(item.get(col_trx_time) or "").strip() if col_trx_time else ""
        notes = str(item.get(col_notes) or "").strip() if col_notes else ""
        source_created_at = _to_datetime(item.get(col_source_created)) if col_source_created else None
        payment_received_at = _to_datetime(item.get(col_payment_received)) if col_payment_received else None
        bank_date = _to_date(item.get(col_bank_date)) if col_bank_date else None
        bank_datetime = _combine_date_time(item.get(col_bank_date), item.get(col_bank_time)) if col_bank_date and col_bank_time else None
        if not payment_received_at and bank_datetime:
            payment_received_at = bank_datetime
        deposit_date = _to_date(item.get(col_deposit_date)) if col_deposit_date else bank_date
        approved_at = _to_datetime(item.get(col_approved)) if col_approved else None
        officer_id = str(item.get(col_officer) or "").strip() if col_officer else ""
        deposit_officer_id = str(item.get(col_deposit_officer) or "").strip() if col_deposit_officer else ""
        approver_id = str(item.get(col_approver) or "").strip() if col_approver else ""
        bank_target = str(item.get(col_bank_target) or "").strip() if col_bank_target else ""
        proof_bank = str(item.get(col_proof_bank) or "").strip() if col_proof_bank else ""
        destination_account = str(item.get(col_destination_account) or "").strip() if col_destination_account else ""
        proof_reference = str(item.get(col_proof_reference) or "").strip() if col_proof_reference else ""
        student_list = str(item.get(col_student_list) or "").strip() if col_student_list else ""
        inserted_rows.append(
            BranchInput(
                transaction_date=trx_date,
                branch_name=branch_name,
                customer_name=customer_name,
                amount_should_pay=amount_should,
                amount_input_branch=amount_input,
                payment_method=payment_method,
                invoice_code=invoice_code,
                transaction_time=transaction_time or None,
                bank_date=bank_date,
                deposit_date=deposit_date,
                officer_id=officer_id or None,
                deposit_officer_id=deposit_officer_id or None,
                approver_id=approver_id or None,
                source_created_at=source_created_at,
                payment_received_at=payment_received_at,
                approved_at=approved_at,
                bank_target=bank_target or None,
                proof_bank=proof_bank or None,
                destination_account=destination_account or None,
                proof_reference=proof_reference or None,
                student_list=student_list or None,
                source_file_name=excel_file.filename,
                source_row_number=line_no,
                notes=notes or None,
            )
        )

    if inserted_rows:
        archive_all_branch_inputs_with_results(db, user_id=user.id, reason=f"Diganti oleh upload baru: {excel_file.filename}")
        db.add_all(inserted_rows)
        db.commit()
        run_matching(db)

    log_status = "WARNING" if failed_rows else "INFO"
    add_log(
        db,
        "Upload Excel Input Cabang",
        f"{user.username} upload {len(inserted_rows)} baris valid, {len(failed_rows)} baris gagal.",
        user_id=user.id,
        status=log_status,
    )

    msg = "Upload selesai"
    if failed_rows:
        msg = "Upload selesai dengan sebagian baris gagal"
    return RedirectResponse(f"/branch-inputs?imported={len(inserted_rows)}&failed={len(failed_rows)}&msg={quote(msg)}", status_code=303)


@app.get("/bank-mutations", response_class=HTMLResponse)
def bank_mutations_page(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return RedirectResponse("/dashboard", status_code=303)


@app.post("/bank-mutations/new")
def create_bank_mutation(
    incoming_date: str = Form(...),
    sender_name: str = Form(...),
    amount_in: float = Form(...),
    company_account: str = Form(...),
    mutation_description: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "auditor")),
):
    add_log(db, "Legacy route blocked", "Input mutasi bank dinonaktifkan karena FEWS memakai single-source Excel approval.", user_id=user.id, status="INFO")
    return RedirectResponse("/dashboard", status_code=303)


@app.post("/bank-mutations/upload")
def upload_bank_mutation_excel(
    excel_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "auditor")),
):
    add_log(db, "Legacy route blocked", "Upload mutasi bank dinonaktifkan karena FEWS memakai single-source Excel approval.", user_id=user.id, status="INFO")
    return RedirectResponse("/dashboard", status_code=303)


@app.post("/matching/run")
def run_matching_manual(db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "auditor"))):
    results = run_matching(db)
    high_alert = sum(1 for item in results if item.risk_score > 7)
    log_status = "ALERT" if high_alert else "INFO"
    add_log(db, "Run FEWS Detection", f"Deteksi fraud selesai. Total {len(results)} hasil, high alert {high_alert}.", user_id=user.id, status=log_status)
    return RedirectResponse("/alerts", status_code=303)


@app.get("/alerts", response_class=HTMLResponse)
def alert_center(
    request: Request,
    status: str = "",
    follow_up_status: str = "",
    min_score: int = 0,
    region: str = "",
    area: str = "",
    branch: str = "",
    officer: str = "",
    indicator: str = "",
    date_from: str = "",
    date_to: str = "",
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    page = max(1, page)
    per_page = min(max(10, per_page), 100)
    query = (
        db.query(MatchingResult)
        .options(joinedload(MatchingResult.branch_input))
        .join(BranchInput, MatchingResult.branch_input_id == BranchInput.id)
        .filter(BranchInput.archived_at.is_(None))
    )
    if user.region:
        query = query.filter(BranchInput.region == user.region)
    elif region:
        query = query.filter(BranchInput.region == region)
    if area:
        query = query.filter(BranchInput.area == area)
    if status:
        query = query.filter(MatchingResult.status == status)
    if follow_up_status:
        query = query.filter(MatchingResult.follow_up_status == follow_up_status)
    if min_score > 0:
        query = query.filter(MatchingResult.risk_score >= min_score)
    if branch:
        query = query.filter(BranchInput.branch_name.ilike(f"%{branch}%"))
    if officer:
        query = query.filter(BranchInput.officer_id.ilike(f"%{officer}%"))
    if date_from:
        parsed = _to_date(date_from)
        if parsed:
            query = query.filter(BranchInput.source_created_at >= datetime.combine(parsed, time.min))
    if date_to:
        parsed = _to_date(date_to)
        if parsed:
            query = query.filter(BranchInput.source_created_at <= datetime.combine(parsed, time.max))
    if indicator:
        indicator_normalized = indicator.strip().lower()
        query = query.filter(MatchingResult.triggered_rules.ilike(f"%{indicator_normalized}%"))
    total_rows = query.count()
    total_pages = max(1, (total_rows + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages
    results = _attach_rule_details(
        query.order_by(MatchingResult.risk_score.desc(), MatchingResult.updated_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return templates.TemplateResponse(
        "alerts.html",
        {
            "request": request,
            "user": user,
            "rows": results,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_rows": total_rows,
                "total_pages": total_pages,
                "has_prev": page > 1,
                "has_next": page < total_pages,
            },
            "filter_options": filter_options(db, user, region, area),
            "filters": {
                "status": status,
                "region": region,
                "area": area,
                "follow_up_status": follow_up_status,
                "min_score": min_score,
                "branch": branch,
                "officer": officer,
                "indicator": indicator,
                "date_from": date_from,
                "date_to": date_to,
                "per_page": per_page,
            },
        },
    )


@app.post("/alerts/{result_id}/follow-up")
def update_alert_follow_up(
    result_id: int,
    follow_up_status: str = Form(...),
    follow_up_notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "auditor")),
):
    row = db.query(MatchingResult).filter(MatchingResult.id == result_id).first()
    if not row:
        return RedirectResponse("/alerts", status_code=303)

    current = row.follow_up_status or "OPEN"
    target = follow_up_status.strip().upper()
    if target not in WORKFLOW_TRANSITIONS:
        add_log(db, "Follow-up invalid", f"Status {target} tidak dikenal untuk hasil #{result_id}.", user_id=user.id, status="WARNING")
        return RedirectResponse("/alerts", status_code=303)

    if target not in WORKFLOW_TRANSITIONS.get(current, set()) and target != current:
        add_log(db, "Follow-up invalid", f"Transisi {current} -> {target} tidak diizinkan untuk hasil #{result_id}.", user_id=user.id, status="WARNING")
        return RedirectResponse("/alerts", status_code=303)

    if target in {"HOLD", "RETURN", "RESOLVED", "CLARIFICATION", "INVESTIGATION"} and not follow_up_notes.strip():
        add_log(db, "Follow-up invalid", f"Catatan wajib untuk status {target} pada hasil #{result_id}.", user_id=user.id, status="WARNING")
        return RedirectResponse("/alerts", status_code=303)

    row.follow_up_status = target
    row.follow_up_notes = follow_up_notes.strip() or row.follow_up_notes
    db.commit()
    add_log(db, "Follow-up update", f"Hasil #{result_id} diubah ke {target}. Catatan: {follow_up_notes.strip()}", user_id=user.id, status="INFO")
    return RedirectResponse("/alerts", status_code=303)


@app.get("/transactions")
def transactions_redirect():
    return RedirectResponse("/alerts", status_code=303)


@app.get("/transactions/new")
def transactions_new_redirect():
    return RedirectResponse("/branch-inputs", status_code=303)


@app.get("/logs", response_class=HTMLResponse)
def audit_logs(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return RedirectResponse("/reports", status_code=303)


@app.get("/reports", response_class=HTMLResponse)
def reports_page(
    request: Request,
    region: str = "",
    area: str = "",
    location: str = "",
    month: str = "",
    indicator: str = "",
    verification: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    filters = {
        "region": region,
        "area": area,
        "location": location,
        "month": month,
        "indicator": indicator,
        "verification": verification,
    }
    summary = build_monitoring_context(db, user, filters)
    return templates.TemplateResponse(
        "reports.html",
        {"request": request, "user": user, **summary},
    )


@app.post("/reports/{result_id}/verify")
def verify_report_result(
    result_id: int,
    notes: str = Form("Verifikasi selesai melalui laporan FEWS."),
    return_to: str = Form("/reports"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in {"admin", "auditor"}:
        return Response(status_code=403, content="Akun wilayah bersifat read-only.")
    query = (
        db.query(MatchingResult)
        .join(BranchInput, MatchingResult.branch_input_id == BranchInput.id)
        .filter(MatchingResult.id == result_id, BranchInput.archived_at.is_(None))
    )
    if user.region:
        query = query.filter(BranchInput.region == user.region)
    row = query.first()
    if not row:
        return Response(status_code=404, content="Temuan tidak ditemukan atau di luar wilayah akses.")
    row.follow_up_status = "RESOLVED"
    row.follow_up_notes = notes.strip() or "Verifikasi selesai melalui laporan FEWS."
    db.commit()
    add_log(db, "Verifikasi temuan", f"Hasil #{result_id} ditandai sudah diverifikasi.", user_id=user.id)
    safe_return = return_to if return_to.startswith("/reports") and not return_to.startswith("//") else "/reports"
    return RedirectResponse(safe_return, status_code=303)


@app.get("/templates/approval-import.xlsx")
def download_template(user: User = Depends(get_current_user)):
    return Response(status_code=410, content="Template upload UI sudah dinonaktifkan.")
    import pandas as pd

    columns = [
        "id",
        "kodelokasi",
        "idunix",
        "tgl_bukubesar",
        "nokwt_awal",
        "nokwt_akhir",
        "jumlah_biaya",
        "bank",
        "tgl_bank",
        "waktu_bank",
        "pilihan_bank",
        "bukti_bank di relasikan ke gd mutasi bank",
        "jumlah_setor",
        "pegawai",
        "tgl_approve",
        "approve_by",
        "keterangan_dr_lokasi",
        "catatan",
        "gambar",
        "link_file",
        "updated_at",
        "created_at",
        "deleted_at",
    ]
    group_row = [
        "id",
        "Cabang",
        "",
        "",
        "",
        "",
        "Nominal",
        "",
        "Tanggal Bank",
        "Waktu TF bank",
        "",
        "",
        "",
        "Petugas Input",
        "Tanggal Input",
        "",
        "Dibikin SOP",
        "",
        "",
        "",
        "",
        "Tanggal dan Jam Input",
        "",
    ]
    sample = [
        [328174, 106, "106-260402", "2026-04-02", "86101444-106", "86101444-106", 1800000, "TRANS", "2026-04-02", "11:15:00", "BCA - - EDC & Transfer BCA NFBP 6270207918", "BCA26kml3uH8", 1800000, "623022", "2026-04-06", "609061", "AISYAH NAIRA PUTRI", "", "", "106-260402/2026-04-02_925.jpg", "2026-04-06 10:55:39", "2026-04-02 19:49:21", ""],
        [329141, 106, "106-260401", "2026-04-01", "49133537-106", "21488049-106", 2260000, "TRANS", "2026-03-14", "23:16:00", "BCA - - EDC & Transfer BCA NFBP 6270207918", "BCA26dkJSJEF", 2260000, "614083", "2026-04-07", "609061", "NADINE RAZITA GHAISANI", "", "", "106-260401/2026-04-06_790.jpg", "2026-04-07 13:24:13", "2026-04-06 19:38:55", ""],
    ]
    df = pd.DataFrame([group_row, columns, *sample])
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, header=False, sheet_name="Template Upload")
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=template_fews_setoran_bank.xlsx"},
    )


@app.get("/reports/excel")
def export_excel(
    region: str = "",
    area: str = "",
    location: str = "",
    month: str = "",
    indicator: str = "",
    verification: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    effective_region = (user.region or region).strip()
    if not effective_region:
        raise HTTPException(status_code=400, detail="Pilih satu wilayah sebelum mengekspor laporan.")
    filters = {
        "region": effective_region,
        "area": area,
        "location": location,
        "month": month,
        "indicator": indicator,
        "verification": verification,
    }
    context = build_monitoring_context(db, user, filters)
    data = build_ranked_excel_report(context["location_rows"], filters)
    region_slug = re.sub(r"[^a-z0-9]+", "_", effective_region.casefold()).strip("_")
    return Response(content=data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename=fews_{region_slug}_ranking_lokasi.xlsx"})


@app.get("/reports/pdf")
def export_pdf(
    region: str = "",
    area: str = "",
    location: str = "",
    month: str = "",
    indicator: str = "",
    verification: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    effective_region = (user.region or region).strip()
    if not effective_region:
        raise HTTPException(status_code=400, detail="Pilih satu wilayah sebelum mengekspor laporan.")
    filters = {
        "region": effective_region,
        "area": area,
        "location": location,
        "month": month,
        "indicator": indicator,
        "verification": verification,
    }
    rows = filtered_results(db, user, **filters)
    data = build_pdf_report(rows, effective_region)
    region_slug = re.sub(r"[^a-z0-9]+", "_", effective_region.casefold()).strip("_")
    return Response(content=data, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=fews_{region_slug}_laporan.pdf"})
