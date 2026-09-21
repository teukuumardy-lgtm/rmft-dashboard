from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.audit import log_action
from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import MonthlyBaseline, User, UserRole
from app.services import funding_calc

router = APIRouter(prefix="/funding", tags=["funding"])


@router.get("/home")
def home_kpis(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Section 4-5: executive home KPIs. RMFT-role users are scoped to their own PN only
    (section 2: RMFT hanya dapat melihat data miliknya sendiri)."""
    data = funding_calc.compute_home_kpis(db)

    if user.role == UserRole.RMFT:
        own_card = next((c for c in data["rmft_cards"] if c["pn"] == user.pn), None)
        data["rmft_cards"] = [own_card] if own_card else []
        if own_card:
            data["unit_current"] = own_card["current"]
            data["unit_mtd"] = own_card["mtd"]
            data["unit_dtd"] = own_card["dtd"]
            data["unit_mtd_growth_pct"] = (
                (own_card["mtd"]["dpk"] / (own_card["current"]["dpk"] - own_card["mtd"]["dpk"]) * 100)
                if (own_card["current"]["dpk"] - own_card["mtd"]["dpk"]) else 0
            )

    return data


@router.get("/top-movers")
def top_movers(
    mode: str = Query("MTD", pattern="^(MTD|DTD)$"),
    direction: str = Query("outflow", pattern="^(outflow|inflow)$"),
    pn: str | None = None,
    limit: int = 10,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Section 26-28: Top 10 outflow/inflow, MTD & DTD."""
    scoped_pn = user.pn if user.role == UserRole.RMFT else pn
    return funding_calc.top_movers(db, mode=mode, direction=direction, pn=scoped_pn, limit=limit)


@router.get("/flow-totals")
def flow_totals(
    mode: str = Query("MTD", pattern="^(MTD|DTD)$"),
    pn: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Section 50: full-population Inflow vs Outflow chart totals."""
    scoped_pn = user.pn if user.role == UserRole.RMFT else pn
    return funding_calc.flow_totals(db, mode=mode, pn=scoped_pn)


@router.get("/trend")
def funding_trend(
    days: int = Query(30, ge=7, le=180),
    pn: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Section 50: Funding Trend line chart — DPK/CASA composition over time."""
    scoped_pn = user.pn if user.role == UserRole.RMFT else pn
    return funding_calc.dpk_trend(db, days=days, pn=scoped_pn)


@router.get("/baseline")
def get_baseline(month: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.query(MonthlyBaseline).filter(MonthlyBaseline.baseline_month == month).first()
    if not row:
        return {"baseline_month": month, "baseline_date": None}
    return {"baseline_month": row.baseline_month, "baseline_date": row.baseline_date}


@router.post("/baseline")
def set_baseline(
    month: str,
    baseline_date: date,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Section 17/71: Admin sets/confirms the monthly baseline used for MTD calculations."""
    row = db.query(MonthlyBaseline).filter(MonthlyBaseline.baseline_month == month).first()
    before = row.baseline_date if row else None
    if row:
        row.baseline_date = baseline_date
        row.set_by = user.id
    else:
        row = MonthlyBaseline(baseline_month=month, baseline_date=baseline_date, set_by=user.id)
        db.add(row)
    db.commit()
    log_action(db, user.username, "UPDATE", "monthly_baseline", record=month, before=before, after=baseline_date)
    return {"baseline_month": month, "baseline_date": baseline_date}
