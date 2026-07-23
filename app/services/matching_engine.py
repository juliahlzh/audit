from __future__ import annotations

import json
import re
from collections import Counter
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
    medium_max = RULE_CONFIG["risk_level"]["medium_max"]
    if score > medium_max:
        return "UNMATCHED"
    if score > 0:
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

    holidays = set(RULE_CONFIG.get("holidays", {}))
    days = 0
    cursor = start_date + timedelta(days=1)
    while cursor <= end_date:
        if cursor.weekday() < 5 and cursor.isoformat() not in holidays:
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
    if late_days >= conf.get("critical_after_days", 11):
        score = conf.get("critical_score", 8)
        severity = "warning merah"
    elif late_days >= conf["high_after_days"]:
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


def _normalize_fingerprint_text(value: str | None) -> str:
    return " ".join((value or "").strip().casefold().split())


def _duplicate_fingerprint(branch: BranchInput) -> tuple | None:
    proof_reference = _normalize_fingerprint_text(branch.proof_reference)
    if not proof_reference:
        return None
    return (
        branch.transaction_date,
        branch.source_created_at,
        branch.payment_received_at,
        branch.bank_date,
        branch.deposit_date,
        _normalize_fingerprint_text(branch.transaction_time),
        _normalize_fingerprint_text(branch.location_code or branch.branch_name),
        _normalize_fingerprint_text(branch.customer_name),
        round(float(branch.amount_should_pay or 0), 2),
        round(float(branch.amount_input_branch or 0), 2),
        _payment_method_key(branch.payment_method),
        _normalize_fingerprint_text(branch.destination_account),
        proof_reference,
    )


def run_matching(db: Session, branch_ids: list[int] | None = None) -> list[MatchingResult]:
    query = db.query(BranchInput).filter(BranchInput.archived_at.is_(None))
    if branch_ids is None:
        branch_inputs = query.order_by(BranchInput.transaction_date.asc(), BranchInput.id.asc()).all()
    else:
        unique_ids = list(dict.fromkeys(int(item) for item in branch_ids if item is not None))
        branch_inputs = []
        for offset in range(0, len(unique_ids), 900):
            branch_inputs.extend(query.filter(BranchInput.id.in_(unique_ids[offset : offset + 900])).all())
        branch_inputs.sort(key=lambda item: (item.transaction_date, item.id or 0))

    active_ids = [item.id for item in branch_inputs if item.id is not None]
    existing_results: dict[int, tuple[str, str | None]] = {}
    for offset in range(0, len(active_ids), 900):
        id_chunk = active_ids[offset : offset + 900]
        for result in db.query(MatchingResult).filter(MatchingResult.branch_input_id.in_(id_chunk)).all():
            if result.branch_input_id is not None:
                existing_results[result.branch_input_id] = (result.follow_up_status, result.follow_up_notes)
        db.query(MatchingResult).filter(MatchingResult.branch_input_id.in_(id_chunk)).delete(synchronize_session=False)
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
    duplicate_counts = Counter(
        fingerprint
        for fingerprint in (
            _duplicate_fingerprint(row)
            for row in db.query(BranchInput).filter(BranchInput.archived_at.is_(None)).all()
        )
        if fingerprint is not None
    )
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

        reference_date = item.bank_date or item.deposit_date
        if item.source_created_at and reference_date:
            late_days = _business_day_gap(reference_date, item.source_created_at)
            if late_days > late_input_max_days:
                rule_code, rule_score, severity = _late_input_rule(item.payment_method, late_days)
                score += rule_score
                input_at_label = _datetime_label(item.source_created_at)
                triggered.append(
                    _trigger(
                        rule_code,
                        f"Tanggal bank {_date_label(reference_date)}, tanggal input {input_at_label}, terlambat {late_days} hari kerja",
                        f"Maksimal H+{late_input_max_days} hari kerja; klasifikasi {severity}",
                    f"Input data setor metode {item.payment_method} terlambat {late_days} hari kerja dari tanggal bank {_date_label(reference_date)} ke tanggal input {input_at_label}, melewati batas H+{late_input_max_days} hari kerja.",
                        score=rule_score,
                        source_field="bank_date/source_created_at/payment_method",
                    )
                )

        date_parts = {
            "input": item.source_created_at.date() if item.source_created_at else None,
            "setoran": item.deposit_date,
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
                    "Tanggal input dan tanggal setor harus konsisten",
                    f"Tanggal input dan tanggal setor tidak konsisten: {observed}.",
                    source_field="source_created_at/deposit_date",
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

        duplicate_fingerprint = _duplicate_fingerprint(item)
        if duplicate_fingerprint and duplicate_counts[duplicate_fingerprint] > 1:
            rule_score = RULE_CONFIG["score"]["double_input"]
            score += rule_score
            triggered.append(
                _trigger(
                    "double_input",
                    f"Referensi bukti {item.proof_reference}; ditemukan {duplicate_counts[duplicate_fingerprint]} data aktif identik",
                    "Fingerprint transaksi dan referensi bukti transfer harus unik",
                    f"Data transaksi dengan bukti transfer {item.proof_reference} ditemukan {duplicate_counts[duplicate_fingerprint]} kali pada data aktif.",
                    source_field="transaction_date/source_created_at/payment_received_at/bank_date/deposit_date/location/customer/amount/payment_method/destination_account/proof_reference",
                )
            )

        status = _status_from_score(score)
        mismatch = [str(r["reason"]) for r in triggered]

        previous_follow_up = existing_results.get(item.id)
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
            follow_up_status=previous_follow_up[0] if previous_follow_up else ("OPEN" if score > 0 else "RESOLVED"),
            follow_up_notes=previous_follow_up[1] if previous_follow_up else None,
        )
        db.add(result)
        results.append(result)

    db.commit()
    return results
