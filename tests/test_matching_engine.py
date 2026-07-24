import json
import unittest
from datetime import date, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import BranchInput
from app.services.matching_engine import automatic_follow_up, run_matching


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
        self.assertEqual(results[0].status, "NEED REVIEW")
        self.assertEqual(results[0].follow_up_status, "OPEN")
        self.assertEqual(results[0].follow_up_source, "AUTO")
        self.assertTrue(results[0].follow_up_notes.startswith("Otomatis FEWS:"))

    def test_automatic_follow_up_uses_risk_score_tiers(self):
        self.assertEqual(automatic_follow_up(0)[0], "RESOLVED")
        self.assertEqual(automatic_follow_up(1)[0], "OPEN")
        self.assertEqual(automatic_follow_up(4)[0], "CLARIFICATION")
        self.assertEqual(automatic_follow_up(8)[0], "INVESTIGATION")

    def test_amount_mismatch_flag(self):
        db = self.Session()
        db.add(self._insert_branch(amount_should_pay=1_500_000, amount_input_branch=1_000_000, invoice_code="INV-AMT"))
        db.commit()

        results = run_matching(db)
        self.assertIn("Jumlah biaya tidak sama", results[0].match_reason)
        self.assertGreaterEqual(results[0].risk_score, 4)

    def test_date_mismatch_flag(self):
        db = self.Session()
        db.add(
            self._insert_branch(
                deposit_date=date(2026, 6, 1),
                source_created_at=datetime(2026, 6, 5, 14, 30),
                invoice_code="INV-DATE",
            )
        )
        db.commit()

        results = run_matching(db)
        self.assertIn("tanggal input dan tanggal setor", results[0].match_reason.lower())
        self.assertNotIn("tanggal transaksi", results[0].match_reason.lower())
        self.assertNotIn("tanggal bank", results[0].match_reason.lower())

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
        self.assertIn("tanggal bank Senin, 01/06/2026", results[0].match_reason)
        self.assertIn("tanggal input Jumat, 05/06/2026 14:30", results[0].match_reason)
        self.assertNotIn("tanggal transaksi", results[0].match_reason.lower())

    def test_inputter_mismatch_no_longer_flags(self):
        db = self.Session()
        db.add(self._insert_branch(officer_id="U1", deposit_officer_id="U2", invoice_code="INV-NOPEG"))
        db.commit()

        results = run_matching(db)
        self.assertNotIn("NOPEG", results[0].match_reason)
        self.assertEqual(results[0].risk_score, 0)
        self.assertEqual(results[0].status, "MATCHED")
        self.assertEqual(results[0].follow_up_status, "RESOLVED")

    def test_double_input_detects_same_transaction_and_transfer_proof(self):
        db = self.Session()
        input_at = datetime(2026, 7, 23, 10, 15)
        payment_at = datetime(2026, 7, 23, 9, 45)
        first = self._insert_branch(
            invoice_code="INV-DUP-1",
            proof_reference="TRX-BANK-001",
            source_created_at=input_at,
            payment_received_at=payment_at,
            transaction_time="10:15",
        )
        second = self._insert_branch(
            invoice_code="INV-DUP-2",
            proof_reference=" trx-bank-001 ",
            customer_name="Customer berbeda tidak memengaruhi fingerprint",
            officer_id="U99",
            destination_account="REKENING-BERBEDA",
            source_created_at=input_at + timedelta(minutes=7),
            payment_received_at=payment_at + timedelta(minutes=3),
            transaction_time="10:22",
        )
        db.add_all([first, second])
        db.commit()

        results = run_matching(db)

        self.assertEqual(len(results), 2)
        for result in results:
            rules = json.loads(result.triggered_rules)
            self.assertIn("double_input", {rule["code"] for rule in rules})
            self.assertGreaterEqual(result.risk_score, 5)
            self.assertIn("ditemukan 2 kali", result.match_reason)

    def test_double_input_requires_all_five_business_keys_to_match(self):
        db = self.Session()
        common = {
            "proof_reference": "BUKTI-EXACT-01",
            "amount_input_branch": 1_000_000,
            "transaction_date": date(2026, 7, 23),
            "payment_method": "transfer",
            "branch_name": "Cabang A",
        }
        first = self._insert_branch(invoice_code="INV-KEY-1", **common)
        different_location = self._insert_branch(
            invoice_code="INV-KEY-2",
            **{**common, "branch_name": "Cabang B"},
        )
        db.add_all([first, different_location])
        db.commit()

        results = run_matching(db)

        self.assertEqual(len(results), 2)
        for result in results:
            rules = json.loads(result.triggered_rules)
            self.assertNotIn("double_input", {rule["code"] for rule in rules})


if __name__ == "__main__":
    unittest.main()
