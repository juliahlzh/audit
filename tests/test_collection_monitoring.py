import os
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.database import Base, get_db
from app.main import app
from app.models import CollectionActivity, CollectionReminder, CollectionTask, User
from app.services.organization import resolve_location


class CollectionMonitoringTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        _, _, self.region, _ = resolve_location("134")
        self.admin = User(
            username="collection-admin", full_name="Admin Pusat", password_hash=hash_password("secret"), role="admin"
        )
        self.regional = User(
            username="collection-region", full_name="Admin Wilayah", password_hash=hash_password("secret"), role="viewer", region=self.region
        )
        self.db.add_all([self.admin, self.regional])
        self.db.commit()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def payload(self, **changes):
        data = {
            "external_id": "VA-134-001",
            "student_id": "S-001",
            "student_name": "Siswa Collection",
            "location": "134",
            "staff_pic": "PIC Wilayah",
            "installment_number": "3",
            "amount_due": 1_500_000,
            "due_date": (date.today() - timedelta(days=15)).isoformat(),
            "outstanding": 1_000_000,
        }
        data.update(changes)
        return data

    def sync(self, payload, secret="va-test"):
        with patch.dict(os.environ, {"FEWS_VA_WEBHOOK_SECRET": secret}):
            return self.client.post(
                "/api/collection/va", json=payload, headers={"X-FEWS-VA-Secret": secret}
            )

    def login(self, username):
        response = self.client.post(
            "/login", data={"username": username, "password": "secret"}, follow_redirects=False
        )
        self.assertEqual(response.status_code, 303)

    def test_va_sync_is_authenticated_idempotent_and_visible(self):
        with patch.dict(os.environ, {"FEWS_VA_WEBHOOK_SECRET": "va-test"}):
            rejected = self.client.post("/api/collection/va", json=self.payload())
        self.assertEqual(rejected.status_code, 401)

        created = self.sync({"items": [self.payload()]})
        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json(), {"received": 1, "created": 1, "updated": 0})
        updated = self.sync(self.payload(outstanding=750_000))
        self.assertEqual(updated.json(), {"received": 1, "created": 0, "updated": 1})
        self.assertEqual(self.db.query(CollectionTask).count(), 1)
        self.assertEqual(self.db.query(CollectionTask).one().payment_status, "Overdue")

        self.login("collection-admin")
        page = self.client.get("/collections")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Central Collection Monitoring", page.text)
        self.assertIn("Siswa Collection", page.text)
        attention = self.client.get("/collections/attention")
        self.assertEqual(attention.status_code, 200)
        self.assertIn("Escalation", attention.text)

    def test_regional_scope_follow_up_and_va_paid_resolution(self):
        self.assertEqual(self.sync(self.payload()).status_code, 200)
        task = self.db.query(CollectionTask).one()
        self.login("collection-region")
        response = self.client.post(
            f"/collections/{task.id}/follow-up",
            data={"result": "Customer sudah bayar", "next_follow_up_date": "", "note": "Menunggu konfirmasi VA"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        self.db.refresh(task)
        self.assertEqual(task.collection_status, "Customer sudah bayar")
        self.assertEqual(task.payment_status, "Overdue")
        self.assertEqual(self.client.get("/collections/attention").status_code, 403)

        paid = self.sync(self.payload(outstanding=0, last_payment_at="2026-09-14T08:00:00Z"))
        self.assertEqual(paid.status_code, 200)
        self.db.refresh(task)
        self.assertEqual(task.payment_status, "Paid")
        self.assertEqual(task.collection_status, "Resolved")
        self.assertIsNotNone(task.resolved_at)
        self.assertTrue(
            self.db.query(CollectionActivity).filter_by(task_id=task.id, result="Resolved by VA").first()
        )

    def test_central_reminder_and_transactional_batch_validation(self):
        invalid_batch = [self.payload(), self.payload(external_id="VA-BAD", location="9999")]
        response = self.sync(invalid_batch)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.db.query(CollectionTask).count(), 0)

        self.assertEqual(self.sync(self.payload()).status_code, 200)
        task = self.db.query(CollectionTask).one()
        self.login("collection-admin")
        reminder = self.client.post(f"/collections/{task.id}/remind", follow_redirects=False)
        self.assertEqual(reminder.status_code, 303)
        self.assertEqual(self.db.query(CollectionReminder).filter_by(task_id=task.id).count(), 1)
        self.db.refresh(task)
        self.assertGreaterEqual(task.reminder_level, 1)

        location_reminder = self.client.post(
            f"/collections/location/{task.location_code}/remind", follow_redirects=False
        )
        self.assertEqual(location_reminder.status_code, 303)
        self.assertEqual(self.db.query(CollectionReminder).filter_by(task_id=task.id).count(), 2)

    def test_daily_runner_is_secret_protected_and_idempotent(self):
        self.assertEqual(self.sync(self.payload()).status_code, 200)
        with patch.dict(os.environ, {"CRON_SECRET": "cron-test"}):
            denied = self.client.get("/api/collection/reminders/run")
            first = self.client.get(
                "/api/collection/reminders/run", headers={"Authorization": "Bearer cron-test"}
            )
            second = self.client.get(
                "/api/collection/reminders/run", headers={"Authorization": "Bearer cron-test"}
            )
        self.assertEqual(denied.status_code, 401)
        self.assertEqual(first.json()["created"], 1)
        self.assertEqual(second.json()["created"], 0)
        self.assertEqual(self.db.query(CollectionReminder).count(), 1)

    def test_configured_first_threshold_does_not_remind_early(self):
        self.assertEqual(
            self.sync(self.payload(due_date=(date.today() - timedelta(days=1)).isoformat())).status_code,
            200,
        )
        with patch.dict(os.environ, {"CRON_SECRET": "cron-test", "FEWS_COLLECTION_REMINDER_DAYS": "3,7"}):
            result = self.client.get(
                "/api/collection/reminders/run", headers={"Authorization": "Bearer cron-test"}
            )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["created"], 0)

    def test_collection_list_is_paginated_for_larger_batches(self):
        items = [
            self.payload(external_id=f"VA-PAGE-{index:03d}", student_id=f"S-{index:03d}")
            for index in range(31)
        ]
        response = self.sync({"items": items})
        self.assertEqual(response.status_code, 200)
        self.login("collection-admin")
        first = self.client.get("/collections")
        second = self.client.get("/collections?page=2")
        self.assertIn("31 data, 25 per halaman", first.text)
        self.assertEqual(first.text.count('class="collection-card '), 25)
        self.assertEqual(second.text.count('class="collection-card '), 6)


if __name__ == "__main__":
    unittest.main()
