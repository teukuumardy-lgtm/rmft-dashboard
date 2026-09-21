from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User, UserRole
from app.services import monthly_report, pipeline_calc

router = APIRouter(prefix="/performance", tags=["performance"])


def _period_range(scope: str) -> tuple[date, date]:
    today = date.today()
    if scope == "daily":
        return today, today
    if scope == "ytd":
        return date(today.year, 1, 1), today
    # default: mtd
    return date(today.year, today.month, 1), today


@router.get("/success-rate")
def success_rate(
    scope: str = Query("mtd", pattern="^(daily|mtd|ytd)$"),
    pn: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Section 37: Daily / MTD / YTD success rate, with 🟢🟡🔴 indicator."""
    scoped_pn = user.pn if user.role == UserRole.RMFT else pn
    date_from, date_to = _period_range(scope)
    stats = pipeline_calc.get_period_stats(db, pn=scoped_pn, date_from=date_from, date_to=date_to)
    stats["nominal_indicator"] = pipeline_calc.sr_indicator(stats["nominal_sr"])
    stats["activity_indicator"] = pipeline_calc.sr_indicator(stats["activity_sr"])
    stats["scope"] = scope
    return stats


@router.get("/leaderboard")
def rmft_leaderboard(
    scope: str = Query("mtd", pattern="^(daily|mtd|ytd)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Section 38: RMFT LEADERBOARD, ranked by conversion — not by raw pipeline size."""
    date_from, date_to = _period_range(scope)
    rows = pipeline_calc.leaderboard(db, date_from=date_from, date_to=date_to)
    for row in rows:
        row["nominal_indicator"] = pipeline_calc.sr_indicator(row["nominal_sr"])
        row["activity_indicator"] = pipeline_calc.sr_indicator(row["activity_sr"])
    return rows


@router.get("/daily-action")
def daily_action(
    pn: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Section 42: TODAY'S ACTION — Daily Action Management System."""
    scoped_pn = user.pn if user.role == UserRole.RMFT else pn
    return pipeline_calc.daily_action(db, pn=scoped_pn)


@router.get("/monthly-summary")
def monthly_summary(
    month: str,
    pn: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Section 39: MONTHLY PIPELINE HISTORY."""
    scoped_pn = user.pn if user.role == UserRole.RMFT else pn
    return monthly_report.monthly_summary(db, month, pn=scoped_pn)


@router.get("/conversion-trend")
def conversion_trend(
    month: str,
    pn: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Pipeline Conversion trend within a month — feeds the Success Rate chart."""
    scoped_pn = user.pn if user.role == UserRole.RMFT else pn
    return monthly_report.daily_conversion_trend(db, month, pn=scoped_pn)
