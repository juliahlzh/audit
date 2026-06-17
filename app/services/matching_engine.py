from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from ..models import BranchInput, MatchingResult
from .rule_config import RULE_CONFIG

DAY_NAMES_ID = {
    0: "Senin",
    1: "Selasa",
    2: "Rabu",
    3: "Kamis",
    4: "Jumat",
    5: "Sabtu",
    6: "Minggu",
}


def _risk_level(score: int) -> str:
    low_max = RULE_CONFIG["risk_level"]["low_max"]
    medium_max = RULE_CONFIG["risk_level"]["medium_max"]
    if score > medium_max:
        return "High Alert"
    if score > low_max:
        return "Medium"
    return "Low"


def _status_from_score(score: int) -> str:
    low_max = RULE_CONFIG["risk_level"]["low_max"]
    medium_max = RULE_CONFIG["risk_level"]["medium_max"]
    if score > medium_max:
        return "UNMATCHED"
    if score > low_max:
        return "NEED REVIEW"
    return "MATCHED"


def _indicator_level(score: int) -> str:
    if score >= 5:
        return "Tinggi"
    if score >= 3:
        return "Sedang"
    return "Rendah"


def _date_label(value: date | datetime | None) -> str:
    if not value:
        return "-"
    parsed = value.date() if isinstance(value, datetime) else value
    return f"{DAY_NAMES_ID[parsed.weekday()]}, {parsed:%d/%m/%Y}"


def _datetime_label(value: datetime | None) -> str:
    if not value:
        return "-"
    return f"{DAY_NAMES_ID[value.weekday()]}, {value:%d/%m/%Y %H:%M}"


def _extract_time_label(branch: BranchInput) -> tuple[int, int, str] | tuple[None, None, None]:
    if branch.transaction_time:
        match = re.search(r"(\d{1,2})[:.](\d{2})", branch.transaction_time)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return hour, minute, f"{hour:02d}:{minute:02d}"
    if branch.source_created_at:
        return branch.source_created_at.hour, branch.source_created_at.minute, branch.source_created_at.strftime("%H:%M")
    if branch.created_at:
        return branch.created_at.hour, branch.created_at.minute, branch.created_at.strftime("%H:%M")
    return None, None, None


def _as_datetime(value: date | datetime | None, fallback_time: time = time.min) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, fallback_time)


def _date_gap_days(start: date | datetime, end: date | datetime) -> int:
    return abs((_as_datetime(end).date() - _as_datetime(start).date()).days)


def _business_day_gap(start: date | datetime, end: date | datetime) -> int:
    start_date = _as_datetime(start).date()
    end_date = _as_datetime(end).date()
    if end_date <= start_date:
        return 0

    days = 0
    cursor = start_date + timedelta(days=1)
    while cursor <= end_date:
        if cursor.weekday() < 5:
            days += 1
        cursor += timedelta(days=1)
    return days


def _payment_method_key(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {"tunai", "cash", "setoran tunai", "setor tunai"}:
        return "tunai"
    return "transfer"


def _trigger(rule_code: str, observed: str, threshold: str, reason: str, score: int | None = None, source_field: str = "") -> dict[str, str | int | bool]:
    rule_meta = RULE_CONFIG["rules"][rule_code]
    rule_score = score if score is not None else RULE_CONFIG["score"][rule_code]
    return {
        "code": rule_code,
        "category": rule_meta["category"],
        "name": rule_meta["name"],
        "definition": rule_meta["definition"],
        "description": rule_meta["description"],
        "observed": observed,
        "threshold": threshold,
        "score": rule_score,
        "risk_impact": _indicator_level(rule_score),
        "reason": reason,
        "recommendation": rule_meta["recommendation"],
        "rekomendasi": rule_meta["recommendation"],
        "source_field": source_field,
        "clarification_required": rule_meta["clarification_required"],
        # Backward-compatible alias for templates/tests that still read old keys.
        "level": _indicator_level(rule_score),
    }


def _late_input_rule(method: str, late_days: int) -> tuple[str, int, str]:
    method_key = _payment_method_key(method)
    config_key = "tunai" if method_key == "tunai" else "transfer"
    conf = RULE_CONFIG["late_input_score"][config_key]
    if late_days >= conf["high_after_days"]:
        score = conf["high_score"]
        severity = "berat"
    elif late_days >= conf["medium_after_days"]:
        score = conf["medium_score"]
        severity = "sedang"
    else:
        score = conf["low_score"]
        severity = "rendah"
    rule_code = "late_input_cash" if config_key == "tunai" else "late_input_transfer"
    return rule_code, score, severity


def run_matching(db: Session) -> list[MatchingResult]:
    branch_inputs = (
        db.query(BranchInput)
        .filter(BranchInput.archived_at.is_(None))
        .order_by(BranchInput.transaction_date.asc(), BranchInput.id.asc())
        .all()
    )

    active_ids = [item.id for item in branch_inputs if item.id is not None]
    if active_ids:
        db.query(MatchingResult).filter(MatchingResult.branch_input_id.in_(active_ids)).delete(synchronize_session=False)
    db.flush()

    if not branch_inputs:
        db.commit()
        return []

    amount_tolerance = RULE_CONFIG["amount_tolerance"]
    attention_window = RULE_CONFIG["attention_window"]
    attention_start = attention_window.get("start_minute", attention_window["start_hour"] * 60)
    attention_end = attention_window.get("end_minute", attention_window["end_hour"] * 60)
    attention_label = attention_window.get("label", f"{attention_window['start_hour']:02d}:00-{attention_window['end_hour']:02d}:00")
    late_input_max_days = RULE_CONFIG["late_input_max_days"]
    split_window_hours = RULE_CONFIG["split_window_hours"]
    split_threshold = RULE_CONFIG["split_threshold"]

    avg_by_branch: dict[str, float] = {}
    grouped_amount: dict[str, list[float]] = defaultdict(list)
    for item in branch_inputs:
        grouped_amount[item.branch_name or "-"].append(item.amount_input_branch or 0.0)
    for key, values in grouped_amount.items():
        avg_by_branch[key] = (sum(values) / len(values)) if values else 0.0

    by_officer_time: dict[str, list[BranchInput]] = defaultdict(list)
    for item in branch_inputs:
        by_officer_time[item.officer_id or "-"].append(item)

    results: list[MatchingResult] = []
    for item in branch_inputs:
        triggered: list[dict[str, str | int | bool]] = []
        score = 0

        hour, minute, time_label = _extract_time_label(item)
        if hour is not None and minute is not None and attention_start <= ((hour * 60) + minute) <= attention_end:
            rule_score = RULE_CONFIG["score"]["off_hour"]
            score += rule_score
            triggered.append(
                _trigger(
                    "off_hour",
                    time_label or f"{hour:02d}:00",
                    attention_label,
                    f"Input transaksi pada pukul {time_label or f'{hour:02d}:00'} berada dalam rentang waktu perhatian SOP {attention_label}.",
                    source_field="transaction_time/source_created_at",
                )
            )

        if item.source_created_at and item.payment_received_at and item.source_created_at < item.payment_received_at:
            diff_minutes = (item.payment_received_at - item.source_created_at).total_seconds() / 60.0
            rule_score = RULE_CONFIG["score"]["pre_payment_input"]
            score += rule_score
            triggered.append(
                _trigger(
                    "pre_payment_input",
                    f"Input {_datetime_label(item.source_created_at)}, pembayaran {_datetime_label(item.payment_received_at)}",
                    "Input harus setelah pembayaran diterima",
                    f"Penginputan dilakukan {diff_minutes:.0f} menit sebelum pembayaran diterima.",
                    source_field="source_created_at/payment_received_at",
                )
            )

        reference_date = item.deposit_date or item.bank_date or (item.payment_received_at.date() if item.payment_received_at else item.transaction_date)
        if item.source_created_at and reference_date:
            late_days = _business_day_gap(reference_date, item.source_created_at)
            if late_days > late_input_max_days:
                rule_code, rule_score, severity = _late_input_rule(item.payment_method, late_days)
                score += rule_score
                input_at_label = _datetime_label(item.source_created_at)
                triggered.append(
                    _trigger(
                        rule_code,
                        f"Tanggal setor/pembayaran {_date_label(reference_date)}, tanggal input {input_at_label}, terlambat {late_days} hari kerja",
                        f"Maksimal H+{late_input_max_days} hari kerja; klasifikasi {severity}",
                    f"Input data setor metode {item.payment_method} terlambat {late_days} hari kerja dari tanggal transaksi {_date_label(item.transaction_date)} / tanggal setor {_date_label(reference_date)} ke tanggal input {input_at_label}, melewati batas H+{late_input_max_days} hari kerja.",
                        score=rule_score,
                        source_field="deposit_date/bank_date/payment_received_at/source_created_at/payment_method",
                    )
                )

        date_parts = {
            "transaksi": item.transaction_date,
            "input": item.source_created_at.date() if item.source_created_at else None,
            "setoran": item.deposit_date,
            "bank": item.bank_date,
        }
        present_dates = {key: value for key, value in date_parts.items() if value}
        if len(set(present_dates.values())) > 1:
            rule_score = RULE_CONFIG["score"]["date_mismatch"]
            score += rule_score
            observed = ", ".join(f"{key}: {_date_label(value)}" for key, value in present_dates.items())
            triggered.append(
                _trigger(
                    "date_mismatch",
                    observed,
                    "Tanggal transaksi, input, setoran, dan bank harus konsisten",
                    f"Tanggal tidak konsisten pada data setoran termasuk tanggal bank/input/setoran: {observed}.",
                    source_field="transaction_date/source_created_at/deposit_date/bank_date",
                )
            )

        if abs((item.amount_should_pay or 0.0) - (item.amount_input_branch or 0.0)) > amount_tolerance:
            rule_score = RULE_CONFIG["score"]["amount_mismatch"]
            score += rule_score
            triggered.append(
                _trigger(
                    "amount_mismatch",
                    f"Biaya {item.amount_should_pay:,.0f}, setor {item.amount_input_branch:,.0f}",
                    "Jumlah biaya harus sama dengan jumlah setor",
                    f"Jumlah biaya tidak sama dengan jumlah setor: biaya Rp {item.amount_should_pay:,.0f}, setor Rp {item.amount_input_branch:,.0f}. Kemungkinan salah input, double input, atau nominal setor tidak sesuai.",
                    source_field="amount_should_pay/amount_input_branch",
                )
            )

        branch_avg = avg_by_branch.get(item.branch_name or "-", 0.0)
        if branch_avg > 0 and (item.amount_input_branch or 0.0) >= (branch_avg * 2.0) and len(grouped_amount[item.branch_name or "-"]) >= 3:
            rule_score = RULE_CONFIG["score"]["split_txn"]
            score += rule_score
            triggered.append(
                _trigger(
                    "split_txn",
                    f"{item.amount_input_branch:,.0f} vs rata-rata lokasi {branch_avg:,.0f}",
                    "Kurang dari 2x rata-rata lokasi atau ada alasan sah",
                    f"Nominal Rp {item.amount_input_branch:,.0f} jauh di atas pola normal lokasi Rp {branch_avg:,.0f}.",
                    source_field="amount_input_branch/branch_name",
                )
            )

        if item.officer_id:
            if item.source_created_at:
                near_count = 0
                win_start = item.source_created_at - timedelta(hours=split_window_hours)
                win_end = item.source_created_at + timedelta(hours=split_window_hours)
                for other in by_officer_time[item.officer_id]:
                    if other.id == item.id or not other.source_created_at:
                        continue
                    if win_start <= other.source_created_at <= win_end and (other.amount_input_branch or 0.0) <= split_threshold:
                        near_count += 1
                if near_count >= 2:
                    rule_score = RULE_CONFIG["score"]["split_txn"]
                    score += rule_score
                    triggered.append(
                        _trigger(
                            "split_txn",
                            f"{near_count + 1} transaksi berdekatan",
                            f"< 3 transaksi dalam {split_window_hours} jam",
                            f"Ada {near_count + 1} transaksi kecil berdekatan dalam {split_window_hours} jam oleh petugas {item.officer_id}.",
                            source_field="officer_id/source_created_at/amount_input_branch",
                        )
                    )

        status = _status_from_score(score)
        mismatch = [str(r["reason"]) for r in triggered]

        result = MatchingResult(
            branch_input_id=item.id,
            bank_mutation_id=None,
            status=status,
            risk_score=score,
            risk_level=_risk_level(score),
            mismatch_type=", ".join(mismatch) if mismatch else "Tidak ada indikasi fraud",
            nominal_gap=abs((item.amount_should_pay or 0.0) - (item.amount_input_branch or 0.0)),
            name_similarity=None,
            date_gap_days=None,
            confidence=max(0.0, 100.0 - (score * 8.0)),
            match_reason="; ".join(mismatch) if mismatch else "Lolos seluruh pengujian FEWS.",
            triggered_rules=json.dumps(triggered, ensure_ascii=False),
            follow_up_status="OPEN" if score > RULE_CONFIG["risk_level"]["low_max"] else "RESOLVED",
            follow_up_notes=None,
        )
        db.add(result)
        results.append(result)

    db.commit()
    return results
