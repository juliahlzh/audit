import json
import unittest
from datetime import date, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import AuditLog, BranchInput, MatchingResult
from app.services.branch_inputs import archive_all_branch_inputs_with_results, archive_branch_input_with_results
from app.services.matching_engine import run_matching


class SopFewsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _insert_branch(self, **kwargs):
        payload = {
            "transaction_date": date(2026, 6, 5),
            "branch_name": "Lokasi A",
            "customer_name": "Siswa A",
            "amount_should_pay": 1_000_000,
            "amount_input_branch": 1_000_000,
            "payment_method": "transfer",
            "invoice_code": "IDU-1",
            "transaction_time": "10:00",
            "source_created_at": datetime(2026, 6, 5, 10, 0),
            "payment_received_at": datetime(2026, 6, 5, 9, 0),
            "deposit_date": date(2026, 6, 5),
            "bank_date": date(2026, 6, 5),
            "notes": "Pembayaran Siswa A Lokasi A",
            "officer_id": "P001",
            "deposit_officer_id": "P001",
            "approver_id": "A001",
            "approved_at": datetime(2026, 6, 5, 11, 0),
            "bank_target": "BCA",
            "proof_bank": "BCA",
            "destination_account": "COMPANY-001",
            "proof_reference": "BUKTI-1",
            "student_list": "Siswa A",
        }
        payload.update(kwargs)
        return BranchInput(**payload)

    def _rules(self, result):
        return {rule["code"]: rule for rule in json.loads(result.triggered_rules)}

    def test_sop_off_hour_uses_0001_to_0500_attention_window(self):
        db = self.Session()
        db.add(self._insert_branch(transaction_time="04:30", source_created_at=datetime(2026, 6, 5, 4, 30)))
        db.commit()

        result = run_matching(db)[0]
        rules = self._rules(result)

        self.assertIn("off_hour", rules)
        self.assertIn("00:01-05:00", rules["off_hour"]["threshold"])
        self.assertIn("matriks skor FEWS", rules["off_hour"]["definition"])
        self.assertIn("rekomendasi", rules["off_hour"])

    def test_sop_off_hour_boundary_minutes(self):
        cases = [
            ("00:00", False),
            ("00:01", True),
            ("05:00", True),
            ("05:01", False),
        ]
        for idx, (time_label, should_flag) in enumerate(cases):
            with self.subTest(time_label=time_label):
                db = self.Session()
                hour, minute = [int(part) for part in time_label.split(":")]
                db.add(
                    self._insert_branch(
                        transaction_time=time_label,
                        source_created_at=datetime(2026, 6, 5, hour, minute),
                        invoice_code=f"INV-OFF-{idx}",
                    )
                )
                db.commit()

                result = next(
                    item
                    for item in run_matching(db)
                    if item.branch_input and item.branch_input.invoice_code == f"INV-OFF-{idx}"
                )
                rules = self._rules(result)

                if should_flag:
                    self.assertIn("off_hour", rules)
                else:
                    self.assertNotIn("off_hour", rules)

    def test_input_before_payment_is_flagged(self):
        db = self.Session()
        db.add(
            self._insert_branch(
                source_created_at=datetime(2026, 6, 5, 8, 0),
                payment_received_at=datetime(2026, 6, 5, 9, 30),
            )
        )
        db.commit()

        rules = self._rules(run_matching(db)[0])

        self.assertIn("pre_payment_input", rules)
        self.assertIn("sebelum pembayaran", rules["pre_payment_input"]["reason"].lower())

    def test_late_input_uses_excel_score_tiers(self):
        db = self.Session()
        cases = [
            ("LATE-3", datetime(2026, 6, 4, 9, 0), 1),
            ("LATE-5", datetime(2026, 6, 6, 9, 0), 2),
            ("LATE-9", datetime(2026, 6, 12, 9, 0), 4),
        ]
        for invoice, input_at, _score in cases:
            db.add(
                self._insert_branch(
                    invoice_code=invoice,
                    payment_method="transfer",
                    deposit_date=date(2026, 6, 1),
                    bank_date=date(2026, 6, 1),
                    source_created_at=input_at,
                )
            )
        db.commit()

        results = {row.branch_input.invoice_code: self._rules(row) for row in run_matching(db)}

        for invoice, _input_at, expected_score in cases:
            self.assertIn("late_input_transfer", results[invoice])
            self.assertEqual(results[invoice]["late_input_transfer"]["score"], expected_score)

    def test_late_input_ignores_weekends_for_h_plus_one(self):
        db = self.Session()
        db.add(
            self._insert_branch(
                invoice_code="FRI-MON-OK",
                payment_method="transfer",
                deposit_date=date(2026, 6, 5),
                bank_date=date(2026, 6, 5),
                source_created_at=datetime(2026, 6, 8, 9, 0),
            )
        )
        db.add(
            self._insert_branch(
                invoice_code="FRI-TUE-LATE",
                payment_method="transfer",
                deposit_date=date(2026, 6, 5),
                bank_date=date(2026, 6, 5),
                source_created_at=datetime(2026, 6, 9, 9, 0),
            )
        )
        db.commit()

        results = {row.branch_input.invoice_code: self._rules(row) for row in run_matching(db)}

        self.assertNotIn("late_input_transfer", results["FRI-MON-OK"])
        self.assertIn("late_input_transfer", results["FRI-TUE-LATE"])
        self.assertIn("2 hari kerja", results["FRI-TUE-LATE"]["late_input_transfer"]["reason"])

    def test_late_input_ignores_indonesia_holidays_and_collective_leave(self):
        db = self.Session()
        db.add(
            self._insert_branch(
                invoice_code="NYEPI-CUTI-OK",
                payment_method="transfer",
                deposit_date=date(2026, 3, 17),
                source_created_at=datetime(2026, 3, 20, 9, 0),
            )
        )
        db.add(
            self._insert_branch(
                invoice_code="LEBARAN-CUTI-LATE",
                payment_method="transfer",
                deposit_date=date(2026, 3, 14),
                source_created_at=datetime(2026, 4, 6, 19, 38),
            )
        )
        db.commit()

        results = {row.branch_input.invoice_code: self._rules(row) for row in run_matching(db)}

        self.assertNotIn("late_input_transfer", results["NYEPI-CUTI-OK"])
        self.assertIn("late_input_transfer", results["LEBARAN-CUTI-LATE"])
        self.assertIn("10 hari kerja", results["LEBARAN-CUTI-LATE"]["late_input_transfer"]["reason"])
        self.assertNotIn("16 hari kerja", results["LEBARAN-CUTI-LATE"]["late_input_transfer"]["reason"])

    def test_late_input_more_than_10_business_days_is_red_warning(self):
        db = self.Session()
        db.add(
            self._insert_branch(
                invoice_code="LATE-10-NOT-RED",
                payment_method="transfer",
                deposit_date=date(2026, 3, 14),
                source_created_at=datetime(2026, 4, 6, 19, 38),
            )
        )
        db.add(
            self._insert_branch(
                invoice_code="LATE-11-RED",
                payment_method="transfer",
                deposit_date=date(2026, 3, 14),
                source_created_at=datetime(2026, 4, 7, 19, 38),
            )
        )
        db.commit()

        results = {row.branch_input.invoice_code: row for row in run_matching(db)}
        ten_day_rule = self._rules(results["LATE-10-NOT-RED"])["late_input_transfer"]
        eleven_day_rule = self._rules(results["LATE-11-RED"])["late_input_transfer"]

        self.assertEqual(ten_day_rule["score"], 4)
        self.assertEqual(results["LATE-10-NOT-RED"].status, "NEED REVIEW")
        self.assertEqual(eleven_day_rule["score"], 8)
        self.assertEqual(eleven_day_rule["risk_impact"], "Tinggi")
        self.assertEqual(results["LATE-11-RED"].status, "UNMATCHED")

    def test_late_input_uses_ddmmyyyy_business_day_gap_not_reversed_date(self):
        db = self.Session()
        db.add(
            self._insert_branch(
                invoice_code="APR-1-TO-4",
                payment_method="transfer",
                transaction_date=date(2026, 4, 1),
                deposit_date=date(2026, 4, 1),
                bank_date=date(2026, 4, 1),
                source_created_at=datetime(2026, 4, 6, 12, 49),
            )
        )
        db.commit()

        rules = self._rules(run_matching(db)[0])

        self.assertIn("late_input_transfer", rules)
        self.assertIn("2 hari kerja", rules["late_input_transfer"]["reason"])
        self.assertNotIn("90 hari", rules["late_input_transfer"]["reason"])

    def test_amount_mismatch_is_flagged_without_removed_indicators(self):
        db = self.Session()
        for idx in range(5):
            db.add(
                self._insert_branch(
                    invoice_code=f"IDU-{idx}",
                    amount_should_pay=1_000_000,
                    amount_input_branch=20_000_000 if idx == 0 else 100_000,
                    officer_id="P001",
                    deposit_officer_id="P002" if idx == 0 else "P001",
                    source_created_at=datetime(2026, 6, 5, 10, idx),
                    notes="" if idx == 0 else "Pembayaran Siswa A Lokasi A",
                )
            )
        db.commit()

        rules = self._rules(run_matching(db)[0])

        self.assertIn("amount_mismatch", rules)
        self.assertNotIn("split_txn", rules)
        self.assertNotIn("inputter_mismatch", rules)
        self.assertNotIn("user_dominance", rules)
        self.assertNotIn("missing_note", rules)

    def test_only_final_approved_indicators_can_trigger(self):
        allowed = {
            "off_hour",
            "pre_payment_input",
            "late_input_transfer",
            "late_input_cash",
            "date_mismatch",
            "amount_mismatch",
        }
        db = self.Session()
        db.add(
            self._insert_branch(
                transaction_time="04:30",
                source_created_at=datetime(2026, 6, 4, 4, 30),
                payment_received_at=datetime(2026, 6, 4, 5, 30),
                deposit_date=date(2026, 6, 1),
                bank_date=date(2026, 6, 2),
                amount_should_pay=1_500_000,
                amount_input_branch=1_000_000,
                officer_id="P001",
                deposit_officer_id="P002",
                notes="",
            )
        )
        db.commit()

        rules = self._rules(run_matching(db)[0])

        self.assertTrue(set(rules).issubset(allowed))
        self.assertNotIn("fast_approval", rules)
        self.assertNotIn("wrong_bank", rules)
        self.assertNotIn("employee_account", rules)
        self.assertNotIn("role_violation", rules)
        self.assertNotIn("inputter_mismatch", rules)
        self.assertNotIn("user_dominance", rules)
        self.assertNotIn("missing_note", rules)

    def test_archiving_preserves_rows_results_and_audit_log(self):
        db = self.Session()
        row = self._insert_branch(invoice_code="ARCHIVE-1")
        db.add(row)
        db.commit()
        db.add(MatchingResult(branch_input_id=row.id, status="NEED REVIEW", risk_score=5))
        db.commit()

        archived = archive_branch_input_with_results(db, row.id, user_id=99, reason="Koreksi data")

        self.assertTrue(archived)
        self.assertEqual(db.query(BranchInput).count(), 1)
        self.assertIsNotNone(db.query(BranchInput).first().archived_at)
        self.assertEqual(db.query(MatchingResult).count(), 1)
        self.assertEqual(db.query(AuditLog).filter(AuditLog.action == "Arsip/Koreksi Data Approval").count(), 1)

    def test_archive_all_preserves_rows_and_marks_all_archived(self):
        db = self.Session()
        db.add(self._insert_branch(invoice_code="A1"))
        db.add(self._insert_branch(invoice_code="A2"))
        db.commit()

        count = archive_all_branch_inputs_with_results(db, user_id=99, reason="Mulai ulang monitoring")

        self.assertEqual(count, 2)
        self.assertEqual(db.query(BranchInput).count(), 2)
        self.assertEqual(db.query(BranchInput).filter(BranchInput.archived_at.isnot(None)).count(), 2)


if __name__ == "__main__":
    unittest.main()
