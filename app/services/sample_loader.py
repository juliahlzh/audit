from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from ..models import BranchInput, MatchingResult
from .matching_engine import run_matching
from .organization import resolve_location


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "ya"}


def load_sample_file(db: Session, csv_path: Path) -> dict:
    existing_follow_up = {
        row.branch_input_id: (row.follow_up_status, row.follow_up_notes)
        for row in db.query(MatchingResult).filter(MatchingResult.branch_input_id.isnot(None)).all()
    }
    inserted = 0
    sample_verification: dict[str, bool] = {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            invoice_code = row["invoice_code"].strip()
            location_code, location_name, inferred_region, inferred_area = resolve_location(row["location"])
            sample_verification[invoice_code] = _as_bool(row.get("verified", "false"))
            if db.query(BranchInput.id).filter(BranchInput.invoice_code == invoice_code).first():
                continue
            db.add(
                BranchInput(
                    transaction_date=date.fromisoformat(row["transaction_date"]),
                    location_code=location_code or None,
                    region=row["region"].strip() or inferred_region,
                    area=row.get("area", "").strip() or inferred_area,
                    branch_name=location_name,
                    customer_name="DATA SINTETIS — BUKAN DATA PRODUKSI",
                    amount_should_pay=float(row["amount_should_pay"]),
                    amount_input_branch=float(row["amount_input_branch"]),
                    payment_method=row["payment_method"].strip(),
                    invoice_code=invoice_code,
                    bank_date=date.fromisoformat(row["bank_date"]),
                    deposit_date=date.fromisoformat(row["bank_date"]),
                    source_created_at=datetime.fromisoformat(row["source_created_at"]),
                    payment_received_at=datetime.fromisoformat(row["payment_received_at"]),
                    transaction_time=row["transaction_time"].strip(),
                    data_type=row["dataset"].strip(),
                    notes="Data sintetis untuk pengujian FEWS.",
                )
            )
            inserted += 1
    db.commit()

    if inserted:
        db.expunge_all()
        results = run_matching(db)
        for result in results:
            if result.branch_input_id in existing_follow_up:
                result.follow_up_status, result.follow_up_notes = existing_follow_up[result.branch_input_id]
            invoice = result.branch_input.invoice_code if result.branch_input else ""
            if invoice in sample_verification and sample_verification[invoice]:
                result.follow_up_status = "RESOLVED"
                result.follow_up_notes = "Status verifikasi bawaan dataset sintetis."
        db.commit()
    return {"inserted": inserted, "source": csv_path.name}
