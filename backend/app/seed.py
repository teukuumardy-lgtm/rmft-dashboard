"""
Section 1: MASTER RMFT seed + demo login users (dev/test convenience — see
section 76: demo data is only for development and must be removable).

Run with: `python -m app.seed` (inside the backend container/venv).
"""
from decimal import Decimal

from app.database import Base, SessionLocal, engine
from app.models import MerchantChannel, MerchantThreshold, RmftMaster, User, UserRole
from app.security import hash_password

RMFT_SEED = [
    ("00380727", "Adist Ayudistira"),
    ("00382271", "Ahmad Rafiq"),
    ("00274689", "Dia Silopa"),
]

# Section: EDC/QRIS productivity thresholds — the real business rule the user
# supplied ("qris minimal trx 50 rb ... edc di angka minimal 15 juta rupiah").
# Stored as data (merchant_threshold) so admin can change it later without a
# code change; this just seeds the correct starting value on first run.
MERCHANT_THRESHOLD_SEED = [
    (MerchantChannel.EDC, Decimal("15000000")),   # Rp15.000.000
    (MerchantChannel.QRIS, Decimal("50000")),     # Rp50.000
]


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for pn, name in RMFT_SEED:
            existing = db.query(RmftMaster).filter(RmftMaster.pn == pn).first()
            if not existing:
                db.add(RmftMaster(pn=pn, rmft_name=name, active=True))
        db.commit()

        for channel, value in MERCHANT_THRESHOLD_SEED:
            if not db.query(MerchantThreshold).filter(MerchantThreshold.channel == channel).first():
                db.add(MerchantThreshold(channel=channel, min_productive_volume=value, updated_by=None))
        db.commit()

        if not db.query(User).filter(User.username == "admin").first():
            db.add(User(
                username="admin", full_name="SBOH Admin",
                password_hash=hash_password("admin123"),
                role=UserRole.ADMIN, pn=None,
            ))

        for pn, name in RMFT_SEED:
            username = name.lower().split()[0]
            if not db.query(User).filter(User.username == username).first():
                db.add(User(
                    username=username, full_name=name,
                    password_hash=hash_password(f"{username}123"),
                    role=UserRole.RMFT, pn=pn,
                ))
        db.commit()
        print("Seed complete. Demo logins:")
        print("  admin / admin123  (ADMIN/SBOH)")
        for pn, name in RMFT_SEED:
            username = name.lower().split()[0]
            print(f"  {username} / {username}123  (RMFT — {name})")
    finally:
        db.close()


if __name__ == "__main__":
    run()
