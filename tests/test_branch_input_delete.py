import unittest
from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import BranchInput, MatchingResult
from app.services.branch_inputs import delete_branch_input_with_results


class BranchInputDeleteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_permanent_delete_requires_archive_and_removes_matching_results(self):
        db = self.Session()
        row = BranchInput(
            transaction_date=date(2026, 6, 5),
            branch_name="Cabang A",
            customer_name="Customer X",
            amount_should_pay=1_000_000,
            amount_input_branch=1_000_000,
            payment_method="transfer",
            invoice_code="INV-DEL",
        )
        db.add(row)
        db.commit()
        db.add(MatchingResult(branch_input_id=row.id, status="NEED REVIEW", risk_score=5))
        db.commit()

        self.assertFalse(delete_branch_input_with_results(db, row.id))
        row.archived_at = datetime.utcnow()
        db.commit()
        deleted = delete_branch_input_with_results(db, row.id)

        self.assertTrue(deleted)
        self.assertEqual(db.query(BranchInput).count(), 0)
        self.assertEqual(db.query(MatchingResult).count(), 0)


if __name__ == "__main__":
    unittest.main()
