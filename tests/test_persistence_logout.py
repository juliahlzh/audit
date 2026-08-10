import unittest
import json
from io import BytesIO
from datetime import date

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

        report_page = self.client.get("/reports")

        self.assertIn("INV-PERSIST", report_page.text)
        self.assertNotIn("Customer Persist", report_page.text)
        self.assertIn("Belum Diverifikasi", report_page.text)
        self.assertIn("Catatan persistensi", self.db.query(MatchingResult).first().follow_up_notes)

    def test_login_page_does_not_expose_demo_credentials(self):
        response = self.client.get("/login")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Akun demo", response.text)
        self.assertNotIn("admin123", response.text)
        self.assertNotIn("auditor123", response.text)
        self.assertNotIn("viewer123", response.text)

    def test_report_is_grouped_by_location_without_customer_name(self):
        self.client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=False)

        report_page = self.client.get("/reports?period=bulanan")

        self.assertEqual(report_page.status_code, 200)
        self.assertIn("Cabang Persist", report_page.text)
        self.assertIn("Input di luar jam operasional", report_page.text)
        self.assertNotIn("Customer Persist", report_page.text)
        self.assertNotIn("<th>Customer</th>", report_page.text)

    def test_central_admin_upload_appends_history_and_maps_sil_location_code(self):
        self.client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=False)
        csv_data = (
            "tgl_bukubesar,kodelokasi,keterangan_dr_lokasi,jumlah_biaya,jumlah_setor,idunix,bank\n"
            "2026-07-01,278,Customer Upload,1000,900,278-260701,transfer\n"
        ).encode("utf-8")
        response = self.client.post(
            "/branch-inputs/upload",
            files={"excel_file": ("mapping.csv", csv_data, "text/csv")},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        self.assertIn("imported=1", response.headers["location"])
        active_rows = self.db.query(BranchInput).filter(BranchInput.archived_at.is_(None)).all()
        self.assertEqual(len(active_rows), 2)
        uploaded = self.db.query(BranchInput).filter(BranchInput.invoice_code == "278-260701").one()
        self.assertEqual(uploaded.location_code, "278")
        self.assertEqual(uploaded.branch_name, "Merduati")
        self.assertEqual(uploaded.area, "Area Aceh")
        self.assertEqual(uploaded.region, "Sumatera Bagian Utara")
        self.assertIsNone(
            self.db.query(BranchInput).filter(BranchInput.invoice_code == "INV-PERSIST").one().archived_at
        )
        original_result = (
            self.db.query(MatchingResult)
            .join(BranchInput, MatchingResult.branch_input_id == BranchInput.id)
            .filter(BranchInput.invoice_code == "INV-PERSIST")
            .one()
        )
        self.assertEqual(original_result.follow_up_status, "HOLD")
        self.assertEqual(original_result.follow_up_notes, "Catatan persistensi")

    def test_same_idunix_upload_archives_old_version_and_activates_replacement(self):
        self.client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=False)
        header = "tgl_bukubesar,kodelokasi,keterangan_dr_lokasi,jumlah_biaya,jumlah_setor,idunix,bank\n"
        first = (header + "2026-07-01,278,Versi 1,1000,1000,REVISI-1,transfer\n").encode("utf-8")
        second = (header + "2026-07-02,278,Versi 2,2000,2000,REVISI-1,transfer\n").encode("utf-8")

        self.client.post("/branch-inputs/upload", files={"excel_file": ("hari-1.csv", first, "text/csv")}, follow_redirects=False)
        response = self.client.post("/branch-inputs/upload", files={"excel_file": ("hari-2.csv", second, "text/csv")}, follow_redirects=False)

        self.assertIn("updated=1", response.headers["location"])
        versions = self.db.query(BranchInput).filter(BranchInput.invoice_code == "REVISI-1").order_by(BranchInput.id).all()
        self.assertEqual(len(versions), 2)
        self.assertIsNotNone(versions[0].archived_at)
        self.assertIsNone(versions[1].archived_at)
        self.assertEqual(versions[1].amount_input_branch, 2000)

    def test_raw_sil_rows_allow_shared_idunix_and_use_source_id_for_revision(self):
        self.client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=False)
        header = "id,tanggal,lb,nama,jumlah,idunix,type_bayar,created_at\n"
        first = (
            header
            + "442665,2026-08-06,206,Customer A,4715000,206-260806,TRANS,2026-08-06 22:33:32\n"
            + "442666,2026-08-06,206,Customer B,1200000,206-260806,KOMBI,2026-08-06 22:34:00\n"
        ).encode("utf-8")
        response = self.client.post(
            "/branch-inputs/upload",
            files={"excel_file": ("trx.csv", first, "text/csv")},
            follow_redirects=False,
        )

        self.assertIn("imported=2", response.headers["location"])
        rows = self.db.query(BranchInput).filter(BranchInput.invoice_code == "206-260806").order_by(BranchInput.source_record_id).all()
        self.assertEqual(len(rows), 2)
        self.assertEqual([row.source_record_id for row in rows], ["trx:442665", "trx:442666"])
        self.assertEqual(rows[0].branch_name, "Harapan Raya")
        self.assertEqual(rows[0].area, "Area Pekanbaru")
        self.assertEqual(rows[0].region, "Sumatera Bagian Utara")
        self.assertEqual(rows[1].payment_method, "kombi")

        revision = (
            header
            + "442665,2026-08-06,207,Customer A Revision,5000000,207-260806,TUNAI,2026-08-06 23:00:00\n"
        ).encode("utf-8")
        revised = self.client.post(
            "/branch-inputs/upload",
            files={"excel_file": ("trx-revision.csv", revision, "text/csv")},
            follow_redirects=False,
        )

        self.assertIn("updated=1", revised.headers["location"])
        sibling = self.db.query(BranchInput).filter_by(source_record_id="trx:442666").one()
        self.assertIsNone(sibling.archived_at)
        active_revision = self.db.query(BranchInput).filter_by(source_record_id="trx:442665", archived_at=None).one()
        self.assertEqual(active_revision.branch_name, "Hos Cokroaminoto")
        self.assertEqual(active_revision.area, "Area Joglosemar")
        self.assertEqual(active_revision.region, "Jatijaya")

        archived_original = (
            self.db.query(BranchInput)
            .filter(BranchInput.source_record_id == "trx:442665", BranchInput.archived_at.is_not(None))
            .one()
        )
        restored = self.client.post(f"/archives/{archived_original.id}/restore", follow_redirects=False)
        self.assertEqual(restored.status_code, 303)
        self.assertIsNone(self.db.query(BranchInput).filter_by(id=archived_original.id).one().archived_at)
        self.assertIsNotNone(self.db.query(BranchInput).filter_by(id=active_revision.id).one().archived_at)
        self.assertIsNone(self.db.query(BranchInput).filter_by(source_record_id="trx:442666").one().archived_at)

    def test_setoran_headers_allow_shared_idunix_when_source_ids_differ(self):
        self.client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=False)
        csv_data = (
            "id,kodelokasi,idunix,tgl_bukubesar,jumlah_biaya,bank,jumlah_setor,keterangan_dr_lokasi,created_at\n"
            "351327,242,242-260802,2026-08-02,5100000,TRANS,5100000,Customer Setoran A,2026-08-02 09:00:00\n"
            "351329,242,242-260802,2026-08-02,670000,KOMBI,670000,Customer Setoran B,2026-08-02 09:01:00\n"
        ).encode("utf-8")
        response = self.client.post(
            "/branch-inputs/upload",
            files={"excel_file": ("setoran.csv", csv_data, "text/csv")},
            follow_redirects=False,
        )

        self.assertIn("imported=2", response.headers["location"])
        rows = self.db.query(BranchInput).filter(BranchInput.invoice_code == "242-260802").all()
        self.assertEqual(len(rows), 2)
        self.assertEqual({row.source_record_id for row in rows}, {"setoran:351327", "setoran:351329"})
        self.assertEqual({row.payment_method for row in rows}, {"transfer", "kombi"})

    def test_manual_input_route_is_disabled(self):
        self.client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=False)
        response = self.client.post(
            "/branch-inputs/new",
            data={
                "transaction_date": "2026-06-05", "branch_name": "Cabang Baru",
                "customer_name": "Sampel", "amount_should_pay": "1000",
                "amount_input_branch": "1000", "payment_method": "transfer", "invoice_code": "BLOCKED",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 410)
        self.assertIsNone(self.db.query(BranchInput).filter(BranchInput.invoice_code == "BLOCKED").first())


if __name__ == "__main__":
    unittest.main()
