import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.database import Base, get_db
from app.main import app
from app.models import BranchInput, MatchingResult, User
from app.services.branch_inputs import count_orphan_matching_results, purge_monitoring_data


CSV_ROW = (
    "tgl_bukubesar,kodelokasi,keterangan_dr_lokasi,jumlah_biaya,jumlah_setor,idunix,bank\n"
    "2026-08-04,278,Data lifecycle,1000,1000,LIFE-1,transfer\n"
).encode("utf-8")


class ArchiveLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.db.add(User(username="admin", full_name="Admin", password_hash=hash_password("admin123"), role="admin"))
        self.db.commit()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=False)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_upload_archive_restore_archive_and_permanent_delete(self):
        upload = self.client.post(
            "/branch-inputs/upload",
            files={"excel_file": ("lifecycle.csv", CSV_ROW, "text/csv")},
            follow_redirects=False,
        )
        self.assertEqual(upload.status_code, 303)
        row = self.db.query(BranchInput).filter_by(invoice_code="LIFE-1").one()
        self.assertIsNone(row.archived_at)
        self.assertEqual(self.db.query(MatchingResult).filter_by(branch_input_id=row.id).count(), 1)

        archived = self.client.post(f"/branch-inputs/{row.id}/archive", follow_redirects=False)
        self.assertEqual(archived.headers["location"], "/archives")
        archives_page = self.client.get("/archives")
        self.assertIn("LIFE-1", archives_page.text)
        self.assertIn("Hapus Permanen", archives_page.text)

        restored = self.client.post(f"/archives/{row.id}/restore", follow_redirects=False)
        self.assertEqual(restored.status_code, 303)
        self.db.refresh(row)
        self.assertIsNone(row.archived_at)

        self.client.post(f"/branch-inputs/{row.id}/archive", follow_redirects=False)
        deleted = self.client.post(f"/archives/{row.id}/delete", follow_redirects=False)
        self.assertEqual(deleted.status_code, 303)
        self.assertEqual(self.db.query(BranchInput).count(), 0)
        self.assertEqual(self.db.query(MatchingResult).count(), 0)
        self.assertEqual(count_orphan_matching_results(self.db), 0)

    def test_required_routes_are_not_not_found(self):
        for path in ("/", "/login", "/dashboard", "/alerts", "/reports", "/branch-inputs", "/archives", "/health"):
            response = self.client.get(path, follow_redirects=False)
            self.assertNotEqual(response.status_code, 404, path)
        self.assertEqual(self.client.get("/health").json()["status"], "ok")

    def test_monitoring_purge_preserves_users(self):
        self.client.post(
            "/branch-inputs/upload",
            files={"excel_file": ("purge.csv", CSV_ROW, "text/csv")},
            follow_redirects=False,
        )
        users_before = self.db.query(User).count()

        deleted = purge_monitoring_data(self.db)

        self.assertEqual(deleted["branch_inputs"], 1)
        self.assertEqual(deleted["matching_results"], 1)
        self.assertEqual(self.db.query(User).count(), users_before)
        self.assertEqual(count_orphan_matching_results(self.db), 0)


if __name__ == "__main__":
    unittest.main()
