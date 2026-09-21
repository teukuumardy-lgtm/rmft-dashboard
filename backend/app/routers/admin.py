from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit import log_action
from app.database import get_db
from app.deps import require_admin
from app.models import (
    AccountRmftAssignment, AuditLog, FundingSnapshot, MerchantChannel, RawImport,
    ReportType, RmftMaster, UploadBatch, UploadStatus, User, UserRole,
)
from app.schemas import MerchantThresholdUpdate, OwnershipOverride, RmftCreate, RmftUpdate, UserCreate, UserUpdate
from app.security import hash_password
from app.services import funding_calc, merchant_calc

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Section 1: RMFT master (edit RMFT name / activate-deactivate / add new PN)
# ---------------------------------------------------------------------------
@router.get("/rmft")
def list_rmft_master(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Unlike GET /rmft (active-only, any logged-in user), this includes
    inactive PNs too, since admin needs to see and reactivate them."""
    return db.query(RmftMaster).order_by(RmftMaster.rmft_name).all()


@router.post("/rmft")
def create_rmft_master(payload: RmftCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if not payload.pn.isdigit() or len(payload.pn) != 8:
        raise HTTPException(status_code=400, detail="PN harus 8 digit angka")
    if db.query(RmftMaster).filter(RmftMaster.pn == payload.pn).first():
        raise HTTPException(status_code=400, detail="PN sudah terdaftar di master RMFT")
    row = RmftMaster(pn=payload.pn, rmft_name=payload.rmft_name, active=payload.active)
    db.add(row)
    db.commit()
    log_action(db, admin.username, "CREATE", "rmft_master", record=payload.pn, after=payload.rmft_name)
    return row


@router.put("/rmft/{pn}")
def update_rmft_master(pn: str, payload: RmftUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Edit nama RMFT dan/atau status aktif. Nama yang diubah di sini langsung
    dipakai di seluruh dashboard (funding_snapshot.resolved_rmft, leaderboard,
    laporan, dst) sejak upload/perhitungan berikutnya — data historis yang
    sudah tersimpan (snapshot lama) tetap memakai nama pada saat itu diproses,
    supaya laporan periode lalu tidak berubah retroaktif tanpa sepengetahuan admin."""
    row = db.query(RmftMaster).filter(RmftMaster.pn == pn).first()
    if not row:
        raise HTTPException(status_code=404, detail="PN tidak ditemukan di master RMFT")
    before = f"{row.rmft_name} (active={row.active})"
    if payload.rmft_name is not None:
        row.rmft_name = payload.rmft_name
    if payload.active is not None:
        row.active = payload.active
    db.commit()
    log_action(db, admin.username, "UPDATE", "rmft_master", record=pn, before=before,
               after=f"{row.rmft_name} (active={row.active})")
    return row


# ---------------------------------------------------------------------------
# EDC / QRIS: productivity thresholds (admin-editable policy, not hardcoded)
# ---------------------------------------------------------------------------
@router.get("/merchant-thresholds")
def get_merchant_thresholds(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return [
        {"channel": ch.value, "min_productive_volume": float(merchant_calc.get_threshold(db, ch))}
        for ch in (MerchantChannel.EDC, MerchantChannel.QRIS)
    ]


@router.put("/merchant-thresholds")
def update_merchant_threshold(payload: MerchantThresholdUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    try:
        channel = MerchantChannel(payload.channel)
    except ValueError:
        raise HTTPException(status_code=400, detail="Channel harus EDC atau QRIS")
    if payload.min_productive_volume < 0:
        raise HTTPException(status_code=400, detail="Nilai minimum tidak boleh negatif")
    before = float(merchant_calc.get_threshold(db, channel))
    merchant_calc.set_threshold(db, channel, payload.min_productive_volume, admin.id)
    log_action(db, admin.username, "UPDATE", "merchant_threshold", record=channel.value,
               before=str(before), after=str(payload.min_productive_volume))
    return {"channel": channel.value, "min_productive_volume": payload.min_productive_volume}


# ---------------------------------------------------------------------------
# Section 2 / 60: user management
# ---------------------------------------------------------------------------
@router.get("/users")
def list_users(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return db.query(User).order_by(User.username).all()


@router.post("/users")
def create_user(payload: UserCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username sudah digunakan")
    if payload.role not in (UserRole.ADMIN.value, UserRole.RMFT.value):
        raise HTTPException(status_code=400, detail="Role harus ADMIN atau RMFT")
    if payload.role == UserRole.RMFT.value and not payload.pn:
        raise HTTPException(status_code=400, detail="User RMFT harus memiliki PN")

    row = User(
        username=payload.username, full_name=payload.full_name,
        password_hash=hash_password(payload.password), role=UserRole(payload.role), pn=payload.pn,
    )
    db.add(row)
    db.commit()
    log_action(db, admin.username, "CREATE", "user", record=row.id, after=f"{payload.username} ({payload.role})")
    return row


@router.put("/users/{user_id}")
def update_user(user_id: str, payload: UserUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    row = db.query(User).filter(User.id == user_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")

    before = f"role={row.role.value} pn={row.pn} active={row.active}"
    if payload.full_name is not None:
        row.full_name = payload.full_name
    if payload.role is not None:
        row.role = UserRole(payload.role)
    if payload.pn is not None:
        row.pn = payload.pn
    if payload.active is not None:
        row.active = payload.active
    if payload.password:
        row.password_hash = hash_password(payload.password)
    db.commit()
    log_action(db, admin.username, "UPDATE", "user", record=user_id, before=before,
               after=f"role={row.role.value} pn={row.pn} active={row.active}")
    return row


# ---------------------------------------------------------------------------
# Section 15: OWNERSHIP CONFLICT
# ---------------------------------------------------------------------------
@router.get("/ownership-conflicts")
def ownership_conflicts(snapshot_date: date | None = None, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    target_date = snapshot_date
    if target_date is None:
        candidates = [
            funding_calc.get_latest_snapshot_date(db, rt)
            for rt in (ReportType.TABUNGAN, ReportType.GIRO, ReportType.DEPOSITO)
        ]
        candidates = [c for c in candidates if c]
        target_date = max(candidates) if candidates else None

    if target_date is None:
        return []

    rows = db.query(FundingSnapshot).filter(
        FundingSnapshot.snapshot_date == target_date, FundingSnapshot.conflict_flag.is_(True),
    ).all()

    pn_to_name = {m.pn: m.rmft_name for m in db.query(RmftMaster).all()}
    out = []
    for r in rows:
        assignment = db.query(AccountRmftAssignment).filter(
            AccountRmftAssignment.snapshot_date == target_date, AccountRmftAssignment.account_number == r.account_number,
        ).first()
        out.append({
            "snapshot_date": target_date,
            "account_number": r.account_number,
            "customer_name": r.customer_name,
            "product": r.product,
            "balance_idr": float(r.balance_idr or 0),
            "primary_pn": r.resolved_pn,
            "primary_rmft": r.resolved_rmft,
            "ownership_source": r.ownership_source.value if r.ownership_source else None,
            "override_pn": assignment.conflict_override_pn if assignment else None,
            "override_rmft": pn_to_name.get(assignment.conflict_override_pn) if assignment and assignment.conflict_override_pn else None,
        })
    return out


@router.post("/ownership-conflicts/override")
def override_ownership(payload: OwnershipOverride, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    master = db.query(RmftMaster).filter(RmftMaster.pn == payload.override_pn, RmftMaster.active.is_(True)).first()
    if not master:
        raise HTTPException(status_code=400, detail="PN RMFT tujuan tidak ditemukan di master")

    snapshot_rows = db.query(FundingSnapshot).filter(
        FundingSnapshot.snapshot_date == payload.snapshot_date, FundingSnapshot.account_number == payload.account_number,
    ).all()
    if not snapshot_rows:
        raise HTTPException(status_code=404, detail="Rekening tidak ditemukan pada snapshot tersebut")

    before = snapshot_rows[0].resolved_pn
    for row in snapshot_rows:
        row.resolved_pn = payload.override_pn
        row.resolved_rmft = master.rmft_name

    assignment = db.query(AccountRmftAssignment).filter(
        AccountRmftAssignment.snapshot_date == payload.snapshot_date,
        AccountRmftAssignment.account_number == payload.account_number,
    ).first()
    if assignment:
        assignment.conflict_override_pn = payload.override_pn
        assignment.overridden_by = admin.id
        assignment.primary_pn = payload.override_pn

    db.commit()
    log_action(db, admin.username, "OVERRIDE", "account_rmft_assignment",
               record=f"{payload.snapshot_date}:{payload.account_number}", before=before, after=payload.override_pn)
    return {"account_number": payload.account_number, "override_pn": payload.override_pn, "override_rmft": master.rmft_name}


# ---------------------------------------------------------------------------
# Section 61: UPLOAD HISTORY + Rollback Import
# ---------------------------------------------------------------------------
@router.get("/upload-history")
def upload_history(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return db.query(UploadBatch).order_by(UploadBatch.uploaded_at.desc()).limit(200).all()


@router.post("/upload-history/{batch_id}/rollback")
def rollback_upload(batch_id: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    batch = db.query(UploadBatch).filter(UploadBatch.batch_id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Upload batch tidak ditemukan")
    if batch.status == UploadStatus.ROLLED_BACK:
        raise HTTPException(status_code=400, detail="Batch ini sudah pernah di-rollback")

    deleted = db.query(FundingSnapshot).filter(FundingSnapshot.upload_batch_id == batch_id).delete(synchronize_session=False)
    db.query(RawImport).filter(RawImport.batch_id == batch_id).delete(synchronize_session=False)
    batch.status = UploadStatus.ROLLED_BACK
    db.commit()

    log_action(db, admin.username, "ROLLBACK", "upload_batch", record=batch_id,
               before=f"{batch.report_type.value} {batch.snapshot_date}", after=f"{deleted} snapshot rows removed")
    return {"batch_id": batch_id, "rows_removed": deleted, "status": "ROLLED_BACK"}


# ---------------------------------------------------------------------------
# Section 56: AUDIT TRAIL
# ---------------------------------------------------------------------------
@router.get("/audit-log")
def audit_log(
    module: str | None = None,
    user: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    q = db.query(AuditLog)
    if module:
        q = q.filter(AuditLog.module == module)
    if user:
        q = q.filter(AuditLog.user == user)
    return q.order_by(AuditLog.timestamp.desc()).limit(min(limit, 1000)).all()
