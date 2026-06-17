from sqlalchemy.orm import Session

from .auth import hash_password
from .models import User


def seed_data(db: Session) -> None:
    if db.query(User).count() == 0:
        db.add_all(
            [
                User(username="admin", full_name="Admin Keuangan", password_hash=hash_password("admin123"), role="admin"),
                User(username="auditor", full_name="Internal Auditor", password_hash=hash_password("auditor123"), role="auditor"),
                User(username="viewer", full_name="Finance Viewer", password_hash=hash_password("viewer123"), role="viewer"),
            ]
        )
        db.commit()

    # Data transaksi sengaja tidak di-seed agar aplikasi mulai dari kondisi kosong.
