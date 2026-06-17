import unittest
from datetime import date, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import BranchInput
from app.services.matching_engine import run_matching


class MatchingEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _insert_branch(self, **kwargs):
        now = datetime.utcnow()
        payload = {
            "transaction_date": date.today(),
            "branch_name": "Cabang A",
            "customer_name": "Customer X",
            "amount_should_pay": 1_000_000,
            "amount_input_branch": 1_000_000,
            "payment_method": "transfer",
            "invoice_code": "INV-1",
            "transaction_time": "12:00",
            "source_created_at": now,
            "approved_at": now + timedelta(hours=1),
            "notes": "ok",
            "officer_id": "U1",
            "approver_id": "A1",
            "bank_date": date.today(),
        }
        payload.update(kwargs)
        return BranchInput(**payload)

    def test_off_hour_flag(self):
        db = self.Session()
        db.add(self._insert_branch(transaction_time="04:30", source_created_at=datetime.utcnow().replace(hour=4, minute=30), invoice_code="INV-OFF"))
        db.commit()

        results = run_matching(db)
        self.assertEqual(len(results), 1)
        self.assertIn("rentang waktu perhatian", results[0].match_reason)
        self.assertEqual(results[0].risk_score, 1)

    def test_amount_mismatch_flag(self):
        db = self.Session()
        db.add(self._insert_branch(amount_should_pay=1_500_000, amount_input_branch=1_000_000, invoice_code="INV-AMT"))
        db.commit()

        results = run_matching(db)
        self.assertIn("Jumlah biaya tidak sama", results[0].match_reason)
        self.assertGreaterEqual(results[0].risk_score, 4)

    def test_date_mismatch_flag(self):
        db = self.Session()
        db.add(self._insert_branch(bank_date=date.today() - timedelta(days=1), invoice_code="INV-DATE"))
        db.commit()

        results = run_matching(db)
        self.assertIn("tanggal bank", results[0].match_reason.lower())

    def test_late_input_flag(self):
        db = self.Session()
        transaction_date = date(2026, 6, 1)
        input_at = datetime(2026, 6, 5, 14, 30)
        db.add(
            self._insert_branch(
                transaction_date=transaction_date,
                deposit_date=transaction_date,
                bank_date=transaction_date,
                source_created_at=input_at,
                invoice_code="INV-LATE",
            )
        )
        db.commit()

        results = run_matching(db)
        self.assertIn("melewati batas", results[0].match_reason)
        self.assertIn("tanggal transaksi Senin, 01/06/2026", results[0].match_reason)
        self.assertIn("tanggal input Jumat, 05/06/2026 14:30", results[0].match_reason)

    def test_inputter_mismatch_no_longer_flags(self):
        db = self.Session()
        db.add(self._insert_branch(officer_id="U1", deposit_officer_id="U2", invoice_code="INV-NOPEG"))
        db.commit()

        results = run_matching(db)
        self.assertNotIn("NOPEG", results[0].match_reason)
        self.assertEqual(results[0].risk_score, 0)


if __name__ == "__main__":
    unittest.main()
