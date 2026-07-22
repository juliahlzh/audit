import unittest
import os
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.database import Base, get_db
from app.main import app
from app.models import BranchInput, User
from app.seed import _seed_password


class UploadSafetyTests(unittest.TestCase):
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

    @staticmethod
    def _message(response) -> str:
        return parse_qs(urlparse(response.headers["location"]).query).get("msg", [""])[0]

    def test_upload_rejects_unsupported_extension(self):
        response = self.client.post(
            "/branch-inputs/upload",
            files={"excel_file": ("approval.txt", b"not a workbook", "text/plain")},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        self.assertIn(".xlsx atau .csv", self._message(response))
        self.assertEqual(self.db.query(BranchInput).count(), 0)

    def test_upload_rejects_more_than_configured_row_limit_without_mutating_data(self):
        csv_data = (
            "tgl_bukubesar,kodelokasi,keterangan_dr_lokasi,jumlah_biaya,jumlah_setor,idunix,bank\n"
            "2026-07-01,278,Baris 1,1000,1000,LIMIT-1,transfer\n"
            "2026-07-01,287,Baris 2,1000,1000,LIMIT-2,transfer\n"
        ).encode("utf-8")
        with patch("app.main.MAX_UPLOAD_ROWS", 1):
            response = self.client.post(
                "/branch-inputs/upload",
                files={"excel_file": ("limit.csv", csv_data, "text/csv")},
                follow_redirects=False,
            )

        self.assertIn("Jumlah baris melebihi batas", self._message(response))
        self.assertEqual(self.db.query(BranchInput).count(), 0)

    def test_upload_rejects_duplicate_idunix_inside_same_file(self):
        csv_data = (
            "tgl_bukubesar,kodelokasi,keterangan_dr_lokasi,jumlah_biaya,jumlah_setor,idunix,bank\n"
            "2026-07-01,278,Baris 1,1000,1000,DUP-1,transfer\n"
            "2026-07-01,287,Baris 2,1000,1000,DUP-1,transfer\n"
        ).encode("utf-8")
        response = self.client.post(
            "/branch-inputs/upload",
            files={"excel_file": ("duplicate.csv", csv_data, "text/csv")},
            follow_redirects=False,
        )

        self.assertIn("imported=1", response.headers["location"])
        self.assertIn("failed=1", response.headers["location"])
        self.assertEqual(self.db.query(BranchInput).filter(BranchInput.archived_at.is_(None)).count(), 1)

    def test_security_headers_are_present(self):
        response = self.client.get("/dashboard")

        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(response.headers["referrer-policy"], "same-origin")
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_production_seed_requires_non_default_password(self):
        with patch("app.seed.IS_PRODUCTION", True), patch.dict(
            os.environ, {"FEWS_ADMIN_PASSWORD": ""}, clear=False
        ):
            with self.assertRaisesRegex(RuntimeError, "FEWS_ADMIN_PASSWORD wajib diset"):
                _seed_password("FEWS_ADMIN_PASSWORD", "admin123")


if __name__ == "__main__":
    unittest.main()
