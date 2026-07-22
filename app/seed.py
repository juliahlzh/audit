import os

from sqlalchemy.orm import Session

from .auth import hash_password
from .config import IS_PRODUCTION
from .models import User
from .services.organization import REGIONAL_ACCOUNTS


def _seed_password(variable: str, local_default: str) -> str:
    configured = os.getenv(variable, "").strip()
    if configured:
        if IS_PRODUCTION and len(configured) < 12:
            raise RuntimeError(f"{variable} minimal 12 karakter pada production")
        return configured
    if IS_PRODUCTION:
        raise RuntimeError(f"{variable} wajib diset sebelum membuat akun production")
    return local_default


def seed_data(db: Session) -> None:
    base_accounts = [
        ("admin", "Admin Pusat", "admin", "FEWS_ADMIN_PASSWORD", "admin123"),
        ("auditor", "Internal Auditor", "auditor", "FEWS_AUDITOR_PASSWORD", "auditor123"),
        ("viewer", "Finance Viewer", "viewer", "FEWS_VIEWER_PASSWORD", "viewer123"),
    ]
    changed = False
    for username, full_name, role, password_variable, local_default in base_accounts:
        if not db.query(User.id).filter(User.username == username).first():
            db.add(
                User(
                    username=username,
                    full_name=full_name,
                    password_hash=hash_password(_seed_password(password_variable, local_default)),
                    role=role,
                )
            )
            changed = True

    regional_password: str | None = None
    for username, region in REGIONAL_ACCOUNTS.items():
        full_name = f"Admin Wilayah {region}"
        user = db.query(User).filter(User.username == username).first()
        if not user:
            if regional_password is None:
                regional_password = _seed_password("FEWS_REGIONAL_PASSWORD", "wilayah123")
            db.add(User(username=username, full_name=full_name, password_hash=hash_password(regional_password), role="viewer", region=region))
            changed = True
        elif user.region != region or user.role != "viewer" or user.full_name != full_name:
            user.region = region
            user.role = "viewer"
            user.full_name = full_name
            changed = True
    if changed:
        db.commit()

    # Data transaksi sengaja tidak di-seed agar aplikasi mulai dari kondisi kosong.
