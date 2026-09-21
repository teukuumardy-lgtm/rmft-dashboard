from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.audit import log_action
from app.database import get_db
from app.deps import get_current_user
from app.models import Pipeline, Realization, User, UserRole
from app.schemas import RealizationCreate

router = APIRouter(prefix="/realization", tags=["realization"])

VALID_STATUSES = {"Realisasi", "Carry Over", "Pending", "Batal"}


@router.get("")
def list_realization(
    date_: date | None = Query(None, alias="date"),
    pn: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Section 34: Realisasi Harian (sore)."""
    q = db.query(Realization).join(Pipeline, Realization.pipeline_id == Pipeline.pipeline_id)
    if user.role == UserRole.RMFT:
        q = q.filter(Pipeline.pn == user.pn)
    elif pn:
        q = q.filter(Pipeline.pn == pn)
    if date_:
        q = q.filter(Realization.date == date_)
    return q.order_by(Realization.date.desc()).all()


@router.post("")
def create_realization(payload: RealizationCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Status harus salah satu dari {sorted(VALID_STATUSES)}")

    pipeline_row = db.query(Pipeline).filter(Pipeline.pipeline_id == payload.pipeline_id).first()
    if not pipeline_row:
        raise HTTPException(status_code=404, detail="Pipeline tidak ditemukan")
    if user.role == UserRole.RMFT and pipeline_row.pn != user.pn:
        raise HTTPException(status_code=403, detail="Tidak dapat mengisi realisasi untuk pipeline RMFT lain")

    row = Realization(
        pipeline_id=payload.pipeline_id, date=payload.date, realization_amount=payload.realization_amount,
        status=payload.status, confirmation_source="MANUAL", notes=payload.notes,
    )
    db.add(row)

    # Section 34: realization status drives the pipeline's own status forward.
    pipeline_row.status = payload.status
    db.commit()

    log_action(
        db, user.username, "CREATE", "realization", record=row.realization_id,
        after=f"pipeline={payload.pipeline_id} amount={payload.realization_amount} status={payload.status}",
    )
    return row
