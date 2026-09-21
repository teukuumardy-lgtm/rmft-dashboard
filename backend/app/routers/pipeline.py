from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.audit import log_action
from app.database import get_db
from app.deps import get_current_user
from app.models import DismissedMatch, Pipeline, Realization, RmftMaster, User, UserRole
from app.schemas import PipelineCreate, PipelineUpdate
from app.services import pipeline_match

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

ACTIVE_STATUSES = {"Prospect", "Follow Up", "Negotiation", "Commit", "Pending", "Carry Over"}


def _scope_query(q, user: User):
    if user.role == UserRole.RMFT:
        q = q.filter(Pipeline.pn == user.pn)
    return q


@router.get("")
def list_pipeline(
    date_: date | None = Query(None, alias="date"),
    date_from: date | None = None,
    date_to: date | None = None,
    pn: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Section 32-33: Pipeline Bulanan (no date filter) / Pipeline Harian (date filter)."""
    q = db.query(Pipeline)
    if user.role == UserRole.RMFT:
        q = q.filter(Pipeline.pn == user.pn)
    elif pn:
        q = q.filter(Pipeline.pn == pn)
    if date_:
        q = q.filter(Pipeline.pipeline_date == date_)
    if date_from:
        q = q.filter(Pipeline.pipeline_date >= date_from)
    if date_to:
        q = q.filter(Pipeline.pipeline_date <= date_to)
    if status:
        q = q.filter(Pipeline.status == status)
    return q.order_by(Pipeline.pipeline_date.desc(), Pipeline.created_at.desc()).all()


@router.post("")
def create_pipeline(payload: PipelineCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role == UserRole.RMFT and payload.pn != user.pn:
        raise HTTPException(status_code=403, detail="RMFT hanya dapat input pipeline miliknya sendiri")
    master = db.query(RmftMaster).filter(RmftMaster.pn == payload.pn, RmftMaster.active.is_(True)).first()
    if not master:
        raise HTTPException(status_code=400, detail="PN RMFT tidak ditemukan di master")

    row = Pipeline(
        pipeline_date=payload.pipeline_date, pn=payload.pn, rmft=master.rmft_name,
        cif=payload.cif, customer=payload.customer, account_number=payload.account_number,
        category=payload.category, product=payload.product, nominal=payload.nominal, fbi=payload.fbi,
        probability=payload.probability, target_date=payload.target_date, status=payload.status,
        activity_today=payload.activity_today, next_action=payload.next_action, notes=payload.notes,
    )
    db.add(row)
    db.commit()
    log_action(db, user.username, "CREATE", "pipeline", record=row.pipeline_id, after=f"{payload.customer} {payload.product} {payload.nominal}")
    return row


@router.put("/{pipeline_id}")
def update_pipeline(pipeline_id: str, payload: PipelineUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.query(Pipeline).filter(Pipeline.pipeline_id == pipeline_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Pipeline tidak ditemukan")
    if user.role == UserRole.RMFT and row.pn != user.pn:
        raise HTTPException(status_code=403, detail="Tidak dapat mengubah pipeline RMFT lain")

    before = f"nominal={row.nominal} status={row.status}"
    for field in ["category", "nominal", "probability", "target_date", "status", "activity_today", "next_action", "notes"]:
        value = getattr(payload, field)
        if value is not None:
            setattr(row, field, value)
    db.commit()
    log_action(db, user.username, "UPDATE", "pipeline", record=pipeline_id, before=before, after=f"nominal={row.nominal} status={row.status}")
    return row


@router.post("/copy-yesterday")
def copy_pipeline_kemarin(
    target_date: date,
    pn: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Section 33: 'Copy Pipeline Kemarin' — carries forward pipeline entries that are
    still unfinished (not yet Realisasi/Batal) from the most recent prior date with data."""
    scoped_pn = user.pn if user.role == UserRole.RMFT else pn
    if not scoped_pn:
        raise HTTPException(status_code=400, detail="Sertakan pn (Admin) — RMFT otomatis menggunakan PN sendiri")

    prior_date = (
        db.query(Pipeline.pipeline_date)
        .filter(Pipeline.pn == scoped_pn, Pipeline.pipeline_date < target_date)
        .order_by(Pipeline.pipeline_date.desc())
        .limit(1)
        .scalar()
    )
    if not prior_date:
        return {"copied": 0, "source_date": None}

    unfinished = db.query(Pipeline).filter(
        Pipeline.pn == scoped_pn, Pipeline.pipeline_date == prior_date,
        Pipeline.status.in_(list(ACTIVE_STATUSES)),
    ).all()

    already_copied = {
        p.carried_from_id for p in db.query(Pipeline).filter(
            Pipeline.pn == scoped_pn, Pipeline.pipeline_date == target_date, Pipeline.carried_from_id.isnot(None),
        ).all()
    }

    copied = 0
    for src in unfinished:
        if src.pipeline_id in already_copied:
            continue
        db.add(Pipeline(
            pipeline_date=target_date, pn=src.pn, rmft=src.rmft, cif=src.cif, customer=src.customer,
            account_number=src.account_number, category=src.category, product=src.product,
            nominal=src.nominal, fbi=src.fbi, probability=src.probability, target_date=src.target_date,
            status="Carry Over", activity_today=None, next_action=src.next_action, notes=src.notes,
            carried_from_id=src.pipeline_id,
        ))
        copied += 1
    db.commit()
    if copied:
        log_action(db, user.username, "CREATE", "pipeline", record=f"copy-yesterday:{scoped_pn}", after=f"{copied} rows from {prior_date}")
    return {"copied": copied, "source_date": prior_date}


@router.get("/matches")
def potential_matches(
    pn: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Section 40-41: POTENTIAL PIPELINE MATCH — suggestion only, never auto-realized."""
    scoped_pn = user.pn if user.role == UserRole.RMFT else pn
    return pipeline_match.find_potential_matches(db, pn=scoped_pn)


@router.post("/matches/dismiss")
def dismiss_match(
    pipeline_id: str,
    actual_account_number: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Section 41: 'Reject' on a Potential Pipeline Match — persisted server-side so the
    same pairing doesn't resurface, unlike a purely client-side dismissal."""
    row = db.query(Pipeline).filter(Pipeline.pipeline_id == pipeline_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Pipeline tidak ditemukan")
    if user.role == UserRole.RMFT and row.pn != user.pn:
        raise HTTPException(status_code=403, detail="Tidak dapat menolak match untuk pipeline RMFT lain")

    existing = db.query(DismissedMatch).filter(
        DismissedMatch.pipeline_id == pipeline_id, DismissedMatch.actual_account_number == actual_account_number,
    ).first()
    if not existing:
        db.add(DismissedMatch(pipeline_id=pipeline_id, actual_account_number=actual_account_number, dismissed_by=user.id))
        db.commit()
        log_action(db, user.username, "UPDATE", "dismissed_match", record=pipeline_id, after=actual_account_number)
    return {"pipeline_id": pipeline_id, "actual_account_number": actual_account_number, "dismissed": True}


@router.post("/matches/confirm")
def confirm_match(
    pipeline_id: str,
    amount: float,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Section 40: 'Confirm as Realization' — the only way a suggested match becomes real."""
    row = db.query(Pipeline).filter(Pipeline.pipeline_id == pipeline_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Pipeline tidak ditemukan")
    if user.role == UserRole.RMFT and row.pn != user.pn:
        raise HTTPException(status_code=403, detail="Tidak dapat mengonfirmasi match untuk pipeline RMFT lain")

    realization = Realization(
        pipeline_id=pipeline_id, date=date.today(), realization_amount=amount,
        status="Realisasi", confirmation_source="AUTO_MATCH",
        notes="Dikonfirmasi dari Potential Pipeline Match",
    )
    db.add(realization)
    row.status = "Realisasi"
    db.commit()
    log_action(db, user.username, "CREATE", "realization", record=realization.realization_id,
               after=f"AUTO_MATCH confirm pipeline={pipeline_id} amount={amount}")
    return realization
