import unittest
import json
from io import BytesIO
from datetime import date
import pandas as pd

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.database import Base, get_db
from app.main import app
from app.models import BranchInput, MatchingResult, User


class LogoutPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.db.add(User(username="admin", full_name="Admin Test", password_hash=hash_password("admin123"), role="admin"))
        self.db.commit()

        row = BranchInput(
            transaction_date=date(2026, 6, 5),
            branch_name="Cabang Persist",
            customer_name="Customer Persist",
            amount_should_pay=1_000_000,
            amount_input_branch=1_000_000,
            payment_method="transfer",
            invoice_code="INV-PERSIST",
        )
        self.db.add(row)
        self.db.commit()
        self.db.add(
            MatchingResult(
                branch_input_id=row.id,
                status="NEED REVIEW",
                risk_score=5,
                risk_level="Medium",
                match_reason="Data harus tetap ada setelah logout.",
                triggered_rules=json.dumps([
                    {"code": "off_hour", "name": "Input di luar jam operasional", "score": 3}
                ]),
                follow_up_status="HOLD",
                follow_up_notes="Catatan persistensi",
            )
        )
        self.db.commit()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_logout_does_not_delete_input_detection_or_follow_up(self):
        login_response = self.client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=False)
        self.assertEqual(login_response.status_code, 303)

        logout_response = self.client.get("/logout", follow_redirects=False)
        self.assertEqual(logout_response.status_code, 303)

        second_login = self.client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=False)
        self.assertEqual(second_login.status_code, 303)

        approval_page = self.client.get("/branch-inputs")
        alert_page = self.client.get("/alerts")

        self.assertIn("INV-PERSIST", approval_page.text)
        self.assertIn("Customer Persist", alert_page.text)
        self.assertIn("HOLD", alert_page.text)
        self.assertIn("Catatan persistensi", self.db.query(MatchingResult).first().follow_up_notes)

    def test_report_is_grouped_by_location_without_customer_name(self):
        self.client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=False)

        report_page = self.client.get("/reports?period=bulanan")

        self.assertEqual(report_page.status_code, 200)
        self.assertIn("Cabang Persist", report_page.text)
        self.assertIn("Input di luar jam operasional", report_page.text)
        self.assertNotIn("Customer Persist", report_page.text)
        self.assertNotIn("<th>Customer</th>", report_page.text)

    def test_upload_maps_created_at_as_input_and_tgl_bank_waktu_bank_as_setoran(self):
        self.client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=False)
        workbook = BytesIO()
        df = pd.DataFrame(
            [
                {
                    "tanggal transaksi": "05/06/2026",
                    "nama cabang": "Cabang Mapping",
                    "nama customer": "Customer Mapping",
                    "jumlah_biaya": 1000000,
                    "jumlah_setor": 1000000,
                    "tipe bayar": "transfer",
                    "idunix": "INV-MAP",
                    "created_at": "05/06/2026 00:30:00",
                    "tgl_bank": "05/06/2026",
                    "waktu_bank": "06:15:00",
                    "pegawai": "P001",
                    "keterangan": "Pembayaran Customer Mapping Cabang Mapping",
                }
            ]
        )
        with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        workbook.seek(0)

        response = self.client.post(
            "/branch-inputs/upload",
            files={"excel_file": ("mapping.xlsx", workbook.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        row = self.db.query(BranchInput).filter(BranchInput.invoice_code == "INV-MAP").one()
        self.assertIsNone(row.transaction_time)
        self.assertEqual(row.transaction_date.isoformat(), "2026-06-05")
        self.assertEqual(row.source_created_at.strftime("%Y-%m-%d %H:%M"), "2026-06-05 00:30")
        self.assertEqual(row.bank_date.isoformat(), "2026-06-05")
        self.assertEqual(row.deposit_date.isoformat(), "2026-06-05")
        self.assertEqual(row.payment_received_at.strftime("%Y-%m-%d %H:%M"), "2026-06-05 06:15")
        result = self.db.query(MatchingResult).filter(MatchingResult.branch_input_id == row.id).one()
        self.assertIn("00:01-05:00", result.triggered_rules)
        page = self.client.get("/branch-inputs")
        self.assertIn("Jumat, 05/06/2026", page.text)
        self.assertNotIn(">2026-06-05<", page.text)


if __name__ == "__main__":
    unittest.main()
