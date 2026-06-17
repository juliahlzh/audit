import unittest

from app.services.system_status import build_database_status


class SystemStatusTests(unittest.TestCase):
    def test_vercel_without_database_url_warns_about_non_persistent_database(self):
        status = build_database_status(
            database_url="sqlite+pysqlite:///:memory:",
            runtime_label="in-memory (fallback)",
            raw_database_url="",
            is_vercel=True,
        )

        self.assertFalse(status["ok"])
        self.assertIn("Database production belum aktif", status["message"])
        self.assertIn("data dapat hilang", status["message"].lower())

    def test_postgres_database_url_is_marked_persistent(self):
        status = build_database_status(
            database_url="postgresql+psycopg2://user:pass@host/db",
            runtime_label="external DATABASE_URL",
            raw_database_url="postgresql://user:pass@host/db",
            is_vercel=True,
        )

        self.assertTrue(status["ok"])
        self.assertIn("Postgres/Supabase", status["name"])
        self.assertIn("permanen", status["message"].lower())


if __name__ == "__main__":
    unittest.main()
