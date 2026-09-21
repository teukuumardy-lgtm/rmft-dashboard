"""
Section 12, 19-28: data freshness, MTD/DTD, and top mover calculations.

Key rules implemented here:
  - Snapshot date always comes from PERIODE, never Date Printed (section 12).
  - MTD = Current Balance - Baseline Balance (section 22).
  - DTD = Current Snapshot - Latest Available Previous Snapshot, which is
    NOT necessarily calendar day-1 (section 23).
  - An account present in the reference period but absent from the current
    one is flagged ACCOUNT MISSING FROM CURRENT REPORT / potential full
    outflow rather than silently treated as balance = 0 (section 25).
  - An account present now but absent from the reference period is NEW
    ACCOUNT / NEW MONEY, contributing its full current balance (section 24).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import FundingSnapshot, MonthlyBaseline, ReportType, RmftMaster

D = lambda v: float(v) if v is not None else 0.0


def get_latest_snapshot_date(db: Session, report_type: ReportType) -> Optional[date]:
    return db.query(func.max(FundingSnapshot.snapshot_date)).filter(
        FundingSnapshot.report_type == report_type
    ).scalar()


def get_previous_snapshot_date(db: Session, report_type: ReportType, before: date) -> Optional[date]:
    return db.query(func.max(FundingSnapshot.snapshot_date)).filter(
        FundingSnapshot.report_type == report_type,
        FundingSnapshot.snapshot_date < before,
    ).scalar()


def get_snapshot_date_on_or_before(db: Session, report_type: ReportType, as_of: date) -> Optional[date]:
    """Latest snapshot date for this product that is <= as_of — used to build a
    historical DPK trend where TABUNGAN/GIRO/DEPOSITO may not share upload dates."""
    return db.query(func.max(FundingSnapshot.snapshot_date)).filter(
        FundingSnapshot.report_type == report_type,
        FundingSnapshot.snapshot_date <= as_of,
    ).scalar()


def data_freshness(db: Session) -> dict:
    items = []
    dates = {}
    for rtype in [ReportType.TABUNGAN, ReportType.GIRO, ReportType.DEPOSITO]:
        d = get_latest_snapshot_date(db, rtype)
        dates[rtype] = d
        items.append({"product": rtype.value, "snapshot_date": d, "is_latest": True})

    present = [d for d in dates.values() if d is not None]
    if not present:
        status = "NO_DATA"
        as_of = None
    elif len(present) < 3:
        status = "PARTIAL"
        as_of = max(present)
    elif len(set(present)) == 1:
        status = "COMPLETE"
        as_of = present[0]
    else:
        status = "DATE_MISMATCH"
        as_of = max(present)

    return {"items": items, "status": status, "as_of": as_of}


def get_baseline_date(db: Session, month: str) -> Optional[date]:
    row = db.query(MonthlyBaseline).filter(MonthlyBaseline.baseline_month == month).first()
    return row.baseline_date if row else None


def aggregate_figures(db: Session, snapshot_dates: dict[ReportType, Optional[date]], pn: Optional[str] = None) -> dict:
    """Sum balance_idr per product for the given snapshot date of EACH product
    (each product can be pinned to its own date — used for DTD where products
    may have different 'latest available' dates)."""
    totals = {"tabungan": 0.0, "giro": 0.0, "deposito": 0.0}
    mapping = {ReportType.TABUNGAN: "tabungan", ReportType.GIRO: "giro", ReportType.DEPOSITO: "deposito"}

    for rtype, snap_date in snapshot_dates.items():
        if snap_date is None:
            continue
        q = db.query(func.coalesce(func.sum(FundingSnapshot.balance_idr), 0)).filter(
            FundingSnapshot.report_type == rtype,
            FundingSnapshot.snapshot_date == snap_date,
        )
        if pn:
            q = q.filter(FundingSnapshot.resolved_pn == pn)
        totals[mapping[rtype]] = D(q.scalar())

    totals["casa"] = totals["tabungan"] + totals["giro"]
    totals["dpk"] = totals["casa"] + totals["deposito"]
    return totals


def _subtract(a: dict, b: dict) -> dict:
    return {k: a.get(k, 0.0) - b.get(k, 0.0) for k in ["tabungan", "giro", "deposito", "casa", "dpk"]}


def compute_home_kpis(db: Session) -> dict:
    fresh = data_freshness(db)
    as_of_dates = {
        ReportType.TABUNGAN: get_latest_snapshot_date(db, ReportType.TABUNGAN),
        ReportType.GIRO: get_latest_snapshot_date(db, ReportType.GIRO),
        ReportType.DEPOSITO: get_latest_snapshot_date(db, ReportType.DEPOSITO),
    }
    current = aggregate_figures(db, as_of_dates)

    # DTD reference: each product's own latest-available-previous snapshot
    dtd_ref_dates = {}
    for rtype, d in as_of_dates.items():
        dtd_ref_dates[rtype] = get_previous_snapshot_date(db, rtype, d) if d else None
    dtd_reference = aggregate_figures(db, dtd_ref_dates)
    dtd = _subtract(current, dtd_reference)

    # MTD reference: baseline for the month of the latest overall snapshot
    baseline = {"tabungan": 0.0, "giro": 0.0, "deposito": 0.0, "casa": 0.0, "dpk": 0.0}
    mtd_growth_pct = 0.0
    if fresh["as_of"]:
        month_key = fresh["as_of"].strftime("%Y-%m")
        baseline_date = get_baseline_date(db, month_key)
        if baseline_date:
            baseline_dates = {rtype: baseline_date for rtype in as_of_dates}
            baseline = aggregate_figures(db, baseline_dates)
    mtd = _subtract(current, baseline)
    if baseline["dpk"]:
        mtd_growth_pct = (mtd["dpk"] / baseline["dpk"]) * 100

    rmft_cards = []
    for m in db.query(RmftMaster).filter(RmftMaster.active.is_(True)).order_by(RmftMaster.rmft_name).all():
        rmft_current = aggregate_figures(db, as_of_dates, pn=m.pn)
        rmft_dtd_ref = aggregate_figures(db, dtd_ref_dates, pn=m.pn)
        rmft_dtd = _subtract(rmft_current, rmft_dtd_ref)
        rmft_baseline = {"tabungan": 0.0, "giro": 0.0, "deposito": 0.0, "casa": 0.0, "dpk": 0.0}
        if fresh["as_of"]:
            month_key = fresh["as_of"].strftime("%Y-%m")
            baseline_date = get_baseline_date(db, month_key)
            if baseline_date:
                rmft_baseline = aggregate_figures(db, {rtype: baseline_date for rtype in as_of_dates}, pn=m.pn)
        rmft_mtd = _subtract(rmft_current, rmft_baseline)

        acct_count = db.query(func.count(FundingSnapshot.id)).filter(
            FundingSnapshot.resolved_pn == m.pn,
            FundingSnapshot.snapshot_date.in_([d for d in as_of_dates.values() if d]),
        ).scalar() or 0

        rmft_cards.append({
            "pn": m.pn,
            "rmft_name": m.rmft_name,
            "current": rmft_current,
            "mtd": rmft_mtd,
            "dtd": rmft_dtd,
            "account_count": acct_count,
        })

    return {
        "freshness": fresh,
        "unit_current": current,
        "unit_mtd": mtd,
        "unit_dtd": dtd,
        "unit_mtd_growth_pct": mtd_growth_pct,
        "rmft_cards": rmft_cards,
    }


def _accounts_at(db: Session, snapshot_dates: dict[ReportType, Optional[date]], pn: Optional[str] = None) -> dict:
    """key=(report_type,account_number,fdr_serial) -> row dict, across the given per-product dates."""
    out = {}
    for rtype, snap_date in snapshot_dates.items():
        if snap_date is None:
            continue
        q = db.query(FundingSnapshot).filter(
            FundingSnapshot.report_type == rtype,
            FundingSnapshot.snapshot_date == snap_date,
        )
        if pn:
            q = q.filter(FundingSnapshot.resolved_pn == pn)
        for row in q.all():
            key = (rtype, row.account_number, row.fdr_serial)
            out[key] = row
    return out


def _all_movers(db: Session, mode: str, pn: Optional[str] = None) -> list[dict]:
    """Shared candidate-building logic behind top_movers() and flow_totals() —
    every account's delta for the given mode, unfiltered and unsorted."""
    as_of_dates = {
        ReportType.TABUNGAN: get_latest_snapshot_date(db, ReportType.TABUNGAN),
        ReportType.GIRO: get_latest_snapshot_date(db, ReportType.GIRO),
        ReportType.DEPOSITO: get_latest_snapshot_date(db, ReportType.DEPOSITO),
    }
    if not any(as_of_dates.values()):
        return []

    if mode == "MTD":
        latest_overall = max(d for d in as_of_dates.values() if d)
        month_key = latest_overall.strftime("%Y-%m")
        baseline_date = get_baseline_date(db, month_key)
        ref_dates = {rtype: baseline_date for rtype in as_of_dates} if baseline_date else {rtype: None for rtype in as_of_dates}
    else:  # DTD
        ref_dates = {rtype: (get_previous_snapshot_date(db, rtype, d) if d else None) for rtype, d in as_of_dates.items()}

    current_map = _accounts_at(db, as_of_dates, pn)
    ref_map = _accounts_at(db, ref_dates, pn)

    candidates = []
    seen_keys = set(current_map.keys()) | set(ref_map.keys())
    for key in seen_keys:
        cur = current_map.get(key)
        ref = ref_map.get(key)
        current_balance = D(cur.balance_idr) if cur else 0.0
        reference_balance = D(ref.balance_idr) if ref else 0.0
        delta = current_balance - reference_balance

        status = None
        if cur and not ref:
            status = "NEW_ACCOUNT"
        elif ref and not cur:
            status = "ACCOUNT_MISSING"

        source = cur or ref
        delta_pct = (delta / reference_balance * 100) if reference_balance else None

        candidates.append({
            "pn": source.resolved_pn if cur else (ref.resolved_pn if ref else None),
            "rmft_name": source.resolved_rmft if cur else (ref.resolved_rmft if ref else None),
            "cif": source.cif,
            "customer": source.customer_name,
            "account_number": source.account_number,
            "product": source.product,
            "baseline_or_previous": reference_balance,
            "current_balance": current_balance,
            "delta": delta,
            "delta_pct": delta_pct,
            "status": status,
        })
    return candidates


def top_movers(db: Session, mode: str, direction: str, pn: Optional[str] = None, limit: int = 10) -> list[dict]:
    """mode: 'MTD' or 'DTD'. direction: 'outflow' (most negative delta) or 'inflow'."""
    candidates = _all_movers(db, mode, pn)

    if direction == "outflow":
        candidates = [c for c in candidates if c["delta"] < 0]
        candidates.sort(key=lambda c: c["delta"])
    else:
        candidates = [c for c in candidates if c["delta"] > 0]
        candidates.sort(key=lambda c: -c["delta"])

    for i, c in enumerate(candidates[:limit], start=1):
        c["rank"] = i
    return candidates[:limit]


def flow_totals(db: Session, mode: str, pn: Optional[str] = None) -> dict:
    """Section 50: aggregate Inflow vs Outflow chart data — full-population sums
    (not just the Top 10 shown in the mover lists)."""
    candidates = _all_movers(db, mode, pn)
    inflow = sum(c["delta"] for c in candidates if c["delta"] > 0)
    outflow = sum(-c["delta"] for c in candidates if c["delta"] < 0)
    return {"mode": mode, "inflow": inflow, "outflow": outflow, "net": inflow - outflow}


def dpk_trend(db: Session, days: int = 30, pn: Optional[str] = None) -> list[dict]:
    """Section 50: Funding Trend line chart — DPK/CASA composition as of each
    distinct snapshot date within the window, each product pinned to its own
    latest-available-on-or-before that date (since TABUNGAN/GIRO/DEPOSITO
    uploads don't necessarily land on the same calendar day)."""
    from datetime import timedelta

    end = date.today()
    start = end - timedelta(days=days - 1)

    all_dates: set[date] = set()
    for rtype in (ReportType.TABUNGAN, ReportType.GIRO, ReportType.DEPOSITO):
        rows = db.query(FundingSnapshot.snapshot_date).filter(
            FundingSnapshot.report_type == rtype,
            FundingSnapshot.snapshot_date >= start, FundingSnapshot.snapshot_date <= end,
        ).distinct().all()
        all_dates.update(r[0] for r in rows)

    trend = []
    for d in sorted(all_dates):
        as_of_dates = {
            rtype: get_snapshot_date_on_or_before(db, rtype, d)
            for rtype in (ReportType.TABUNGAN, ReportType.GIRO, ReportType.DEPOSITO)
        }
        figures = aggregate_figures(db, as_of_dates, pn=pn)
        trend.append({"date": d, **figures})
    return trend


def outflow_alert_level(amount_abs: float, high_threshold: float, medium_threshold: float) -> str:
    if amount_abs > high_threshold:
        return "HIGH"
    if amount_abs >= medium_threshold:
        return "MEDIUM"
    return "LOW"
