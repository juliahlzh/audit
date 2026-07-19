from sqlalchemy.orm import Session

from .auth import hash_password
from .models import User
from .services.organization import REGIONAL_ACCOUNTS


def seed_data(db: Session) -> None:
    if db.query(User).count() == 0:
        db.add_all(
            [
                User(username="admin", full_name="Admin Pusat", password_hash=hash_password("admin123"), role="admin"),
                User(username="auditor", full_name="Internal Auditor", password_hash=hash_password("auditor123"), role="auditor"),
                User(username="viewer", full_name="Finance Viewer", password_hash=hash_password("viewer123"), role="viewer"),
            ]
        )
        db.commit()

    changed = False
    for username, region in REGIONAL_ACCOUNTS.items():
        full_name = f"Admin Wilayah {region}"
        user = db.query(User).filter(User.username == username).first()
        if not user:
            db.add(User(username=username, full_name=full_name, password_hash=hash_password("wilayah123"), role="viewer", region=region))
            changed = True
        elif user.region != region or user.role != "viewer" or user.full_name != full_name:
            user.region = region
            user.role = "viewer"
            user.full_name = full_name
            changed = True
    if changed:
        db.commit()

    # Data transaksi sengaja tidak di-seed agar aplikasi mulai dari kondisi kosong.
