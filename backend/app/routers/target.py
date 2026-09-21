from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.audit import log_action
from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import RmftTarget, User, UserRole
from app.schemas import TargetUpsert
from app.services import target_calc

router = APIRouter(prefix="/target", tags=["target"])


@router.get("")
def list_targets(month: str, pn: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    scoped_pn = user.pn if user.role == UserRole.RMFT else pn
    q = db.query(RmftTarget).filter(RmftTarget.month == month)
    if scoped_pn:
        q = q.filter(RmftTarget.pn == scoped_pn)
    return q.all()


@router.post("")
def upsert_target(payload: TargetUpsert, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    """Section 43: Admin sets/updates a target — one row per (month, pn, product)."""
    row = db.query(RmftTarget).filter(
        RmftTarget.month == payload.month, RmftTarget.pn == payload.pn, RmftTarget.product == payload.product,
    ).first()
    before = row.target if row else None
    if row:
        row.target = payload.target
    else:
        row = RmftTarget(month=payload.month, pn=payload.pn, product=payload.product, target=payload.target)
        db.add(row)
    db.commit()
    log_action(db, user.username, "UPDATE" if before is not None else "CREATE", "rmft_target",
               record=f"{payload.month}:{payload.pn}:{payload.product}", before=before, after=payload.target)
    return row


@router.get("/achievement")
def achievement(month: str, pn: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Section 43: Achievement = Realisasi / Target * 100%, Gap = Target - Realisasi."""
    scoped_pn = user.pn if user.role == UserRole.RMFT else pn
    return target_calc.compute_achievement(db, month, pn=scoped_pn)
