import json
import os
import subprocess
import sys
import unittest
from datetime import date, datetime
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.database import Base, get_db
import app.main as main_module
from app.main import app
from app.models import BranchInput, MatchingResult, User


class QueryPerformanceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.db.add(
            User(
                username="admin",
                full_name="Admin Test",
                password_hash=hash_password("admin123"),
                role="admin",
            )
        )
        for index in range(25):
            branch_input = BranchInput(
                transaction_date=date.today(),
                branch_name=f"Cabang {index % 3}",
                customer_name=f"Customer {index}",
                amount_should_pay=1_000_000,
                amount_input_branch=1_000_000,
                payment_method="transfer",
                invoice_code=f"INV-{index}",
                source_created_at=datetime.now(),
            )
            self.db.add(branch_input)
            self.db.flush()
            self.db.add(
                MatchingResult(
                    branch_input_id=branch_input.id,
                    status="NEED REVIEW",
                    risk_score=5,
                    risk_level="Medium",
                    triggered_rules=json.dumps(
                        [{"code": "late_input", "name": "Keterlambatan input", "score": 5}]
                    ),
                )
            )
        self.db.commit()
        self.db.expunge_all()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.client.post(
            "/login",
            data={"username": "admin", "password": "admin123"},
            follow_redirects=False,
        )

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _select_count_for(self, path: str) -> tuple[int, int]:
        select_count = 0

        def count_selects(_conn, _cursor, statement, _parameters, _context, _executemany):
            nonlocal select_count
            if statement.lstrip().upper().startswith("SELECT"):
                select_count += 1

        event.listen(self.engine, "before_cursor_execute", count_selects)
        try:
            response = self.client.get(path)
        finally:
            event.remove(self.engine, "before_cursor_execute", count_selects)
        return response.status_code, select_count

    def test_alert_center_avoids_query_per_card(self):
        status_code, select_count = self._select_count_for("/alerts")

        self.assertEqual(status_code, 200)
        self.assertLessEqual(select_count, 6)

    def test_report_avoids_query_per_transaction(self):
        status_code, select_count = self._select_count_for("/reports")

        self.assertEqual(status_code, 200)
        self.assertLessEqual(select_count, 5)

    def test_web_startup_does_not_eagerly_load_export_libraries(self):
        script = (
            "import json, sys; import app.main; "
            "print(json.dumps({'pandas': 'pandas' in sys.modules, "
            "'reportlab': any(name.startswith('reportlab') for name in sys.modules)}))"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=".",
            capture_output=True,
            text=True,
            check=True,
        )

        loaded = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertFalse(loaded["pandas"])
        self.assertFalse(loaded["reportlab"])

    def test_vercel_startup_does_not_run_schema_migrations(self):
        with patch.dict("os.environ", {"VERCEL": "1"}, clear=False), patch.object(
            main_module, "init_db"
        ) as init_db:
            main_module.startup_event()

        init_db.assert_not_called()

    def test_dashboard_summary_does_not_return_all_database_entities(self):
        self.db.expunge_all()

        summary = main_module._dashboard_summary(self.db)

        self.assertEqual(summary["total_branch"], 25)
        self.assertEqual(summary["total_need_review"], 25)
        self.assertNotIn("branch_inputs", summary)
        self.assertNotIn("results", summary)
        loaded_business_rows = [
            value
            for value in self.db.identity_map.values()
            if isinstance(value, (BranchInput, MatchingResult))
        ]
        self.assertLessEqual(len(loaded_business_rows), 15)

    def test_dashboard_explains_h_plus_two_bank_date_limit(self):
        response = self.client.get("/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertIn("H+2 hari kerja dari tanggal bank", response.text)

    def test_branch_inputs_page_is_paginated(self):
        response = self.client.get("/branch-inputs", follow_redirects=False)

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/reports")

    def test_responses_include_server_timing_header(self):
        response = self.client.get("/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertIn("app;dur=", response.headers.get("server-timing", ""))
        self.assertRegex(response.headers.get("x-fews-response-time-ms", ""), r"^\d+\.\d$")

    def test_performance_indexes_are_created_idempotently(self):
        original_engine = main_module.engine
        main_module.engine = self.engine
        try:
            main_module._run_schema_migrations()
            main_module._run_schema_migrations()
        finally:
            main_module.engine = original_engine

        branch_indexes = {item["name"] for item in inspect(self.engine).get_indexes("branch_inputs")}
        result_indexes = {item["name"] for item in inspect(self.engine).get_indexes("matching_results")}
        self.assertIn("ix_branch_inputs_active_transaction", branch_indexes)
        self.assertIn("ix_branch_inputs_source_created_at", branch_indexes)
        self.assertIn("ix_matching_results_risk_updated", result_indexes)

    def test_migration_script_runs_from_project_root(self):
        environment = os.environ.copy()
        environment["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

        result = subprocess.run(
            [sys.executable, "scripts/migrate_database.py"],
            cwd=".",
            env=environment,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Migration FEWS selesai", result.stdout)


if __name__ == "__main__":
    unittest.main()
