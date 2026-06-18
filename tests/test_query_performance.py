import json
import subprocess
import sys
import unittest
from datetime import date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.database import Base, get_db
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
        self.assertLessEqual(select_count, 4)

    def test_report_avoids_query_per_transaction(self):
        status_code, select_count = self._select_count_for("/reports?period=harian")

        self.assertEqual(status_code, 200)
        self.assertLessEqual(select_count, 3)

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


if __name__ == "__main__":
    unittest.main()
