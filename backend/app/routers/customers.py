from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.audit import log_action
from app.database import get_db
from app.deps import get_current_user
from app.models import CustomerFollowup, User, UserRole
from app.schemas import FollowupCreate, FollowupUpdate
from app.services import customer_360, funding_calc

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/search")
def search(q: str = Query(..., min_length=2), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Section 65-66: universal search — Nama Nasabah / CIF / Nomor Rekening."""
    scoped_pn = user.pn if user.role == UserRole.RMFT else None
    return customer_360.search_customers(db, q, scoped_pn=scoped_pn)


@router.get("/360")
def customer_360_view(
    cif: str | None = None,
    account_number: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Section 31: Customer 360."""
    if not cif and not account_number:
        raise HTTPException(status_code=400, detail="Sertakan cif atau account_number")
    scoped_pn = user.pn if user.role == UserRole.RMFT else None
    result = customer_360.get_customer_360(db, cif=cif, account_number=account_number, scoped_pn=scoped_pn)
    if result is None:
        raise HTTPException(status_code=404, detail="Nasabah tidak ditemukan")
    return result


@router.get("/outflow-alerts")
def outflow_alerts(
    mode: str = Query("DTD", pattern="^(MTD|DTD)$"),
    limit: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Section 29: Potential Fund Outflow, classified HIGH/MEDIUM/LOW, joined with any existing follow-up."""
    from app.config import settings

    scoped_pn = user.pn if user.role == UserRole.RMFT else None
    movers = funding_calc.top_movers(db, mode=mode, direction="outflow", pn=scoped_pn, limit=limit)

    followups = {
        (f.cif, f.account_number): f
        for f in db.query(CustomerFollowup).all()
    }

    alerts = []
    for m in movers:
        level = funding_calc.outflow_alert_level(abs(m["delta"]), settings.OUTFLOW_HIGH_THRESHOLD, settings.OUTFLOW_MEDIUM_THRESHOLD)
        fu = followups.get((m["cif"], m["account_number"]))
        alerts.append({
            **m, "level": level,
            "followup_status": fu.status if fu else "Belum Dihubungi",
            "followup_id": fu.followup_id if fu else None,
        })
    return alerts


@router.get("/followup")
def list_followup(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(CustomerFollowup).order_by(CustomerFollowup.date.desc())
    if user.role == UserRole.RMFT:
        q = q.filter(CustomerFollowup.pn == user.pn)
    return q.all()


@router.post("/followup")
def create_followup(payload: FollowupCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Section 29: log/update a follow-up action against an outflow alert."""
    pn = payload.pn or (user.pn if user.role == UserRole.RMFT else None)
    row = CustomerFollowup(
        cif=payload.cif, account_number=payload.account_number, pn=pn, date=payload.date,
        outflow_amount=payload.outflow_amount, status=payload.status,
        next_action=payload.next_action, notes=payload.notes,
    )
    db.add(row)
    db.commit()
    log_action(db, user.username, "CREATE", "customer_followup", record=row.followup_id, after=payload.status)
    return row


@router.put("/followup/{followup_id}")
def update_followup(followup_id: str, payload: FollowupUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.query(CustomerFollowup).filter(CustomerFollowup.followup_id == followup_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Follow-up tidak ditemukan")
    if user.role == UserRole.RMFT and row.pn != user.pn:
        raise HTTPException(status_code=403, detail="Tidak dapat mengubah follow-up RMFT lain")

    before = row.status
    if payload.status is not None:
        row.status = payload.status
    if payload.next_action is not None:
        row.next_action = payload.next_action
    if payload.notes is not None:
        row.notes = payload.notes
    db.commit()
    log_action(db, user.username, "UPDATE", "customer_followup", record=followup_id, before=before, after=row.status)
    return row
