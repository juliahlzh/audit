"""Non-destructive smoke test for long FEWS import values.

The row is flushed inside a transaction and always rolled back, so this script
can safely validate the production schema after a migration.
"""

from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, engine  # noqa: E402
from app.models import BranchInput  # noqa: E402


def main() -> None:
    db = SessionLocal()
    customer_name = "QA-LONG-CUSTOMER-" + ("A" * 300)
    proof_reference = "QA-LONG-REFERENCE-" + ("B" * 300)
    try:
        row = BranchInput(
            transaction_date=date(2026, 8, 4),
            location_code="278",
            branch_name="MERDUATI",
            region="Sumatera Bagian Utara",
            area="Area Aceh",
            data_type="OPERASIONAL",
            customer_name=customer_name,
            amount_should_pay=1000,
            amount_input_branch=1000,
            payment_method="transfer",
            invoice_code="__QA_LONG_IMPORT_SCHEMA__",
            proof_reference=proof_reference,
        )
        db.add(row)
        db.flush()
        print(
            "Long import schema OK "
            f"(dialect={engine.dialect.name}, customer={len(customer_name)}, "
            f"reference={len(proof_reference)})"
        )
    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
