"""
Section 30-31, 65-66: customer aggregation by CIF (Tabungan/Giro carry CIF;
Deposito has no CIF per the CI324 mapping in section 10, so deposito stays
account-level "sampai tersedia mapping" as the spec explicitly allows),
universal search, and the Customer 360 detail view.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models import FundingSnapshot, Pipeline, Realization, ReportType
from app.services import funding_calc

D = lambda v: float(v) if v is not None else 0.0


def search_customers(db: Session, query: str, scoped_pn: Optional[str] = None, limit: int = 20) -> list[dict]:
    """Section 65-66: search by Nama Nasabah / CIF / Nomor Rekening."""
    needle = f"%{query.strip().upper()}%"
    seen: dict[str, dict] = {}

    for rtype in [ReportType.TABUNGAN, ReportType.GIRO, ReportType.DEPOSITO]:
        snap_date = funding_calc.get_latest_snapshot_date(db, rtype)
        if not snap_date:
            continue
        q = db.query(FundingSnapshot).filter(
            FundingSnapshot.report_type == rtype,
            FundingSnapshot.snapshot_date == snap_date,
            or_(
                func.upper(func.coalesce(FundingSnapshot.customer_name, "")).like(needle),
                func.upper(func.coalesce(FundingSnapshot.cif, "")).like(needle),
                func.upper(FundingSnapshot.account_number).like(needle),
            ),
        )
        if scoped_pn:
            q = q.filter(FundingSnapshot.resolved_pn == scoped_pn)

        for row in q.limit(limit * 3).all():
            key = f"CIF:{row.cif}" if row.cif else f"ACC:{row.account_number}"
            if key not in seen:
                seen[key] = {
                    "cif": row.cif,
                    "account_number": row.account_number if not row.cif else None,
                    "customer": row.customer_name,
                    "resolved_pn": row.resolved_pn,
                    "resolved_rmft": row.resolved_rmft,
                }
            if len(seen) >= limit:
                break
    return list(seen.values())[:limit]


def _customer_snapshot_dates(db: Session) -> dict:
    return {
        ReportType.TABUNGAN: funding_calc.get_latest_snapshot_date(db, ReportType.TABUNGAN),
        ReportType.GIRO: funding_calc.get_latest_snapshot_date(db, ReportType.GIRO),
        ReportType.DEPOSITO: funding_calc.get_latest_snapshot_date(db, ReportType.DEPOSITO),
    }


def _aggregate_for_customer(db: Session, snapshot_dates: dict, cif: Optional[str], account_number: Optional[str]) -> dict:
    totals = {"tabungan": 0.0, "giro": 0.0, "deposito": 0.0}
    mapping = {ReportType.TABUNGAN: "tabungan", ReportType.GIRO: "giro", ReportType.DEPOSITO: "deposito"}
    for rtype, snap_date in snapshot_dates.items():
        if snap_date is None:
            continue
        q = db.query(func.coalesce(func.sum(FundingSnapshot.balance_idr), 0)).filter(
            FundingSnapshot.report_type == rtype, FundingSnapshot.snapshot_date == snap_date,
        )
        if cif:
            q = q.filter(FundingSnapshot.cif == cif)
        elif account_number:
            q = q.filter(FundingSnapshot.account_number == account_number)
        else:
            continue
        totals[mapping[rtype]] = D(q.scalar())
    totals["casa"] = totals["tabungan"] + totals["giro"]
    totals["dpk"] = totals["casa"] + totals["deposito"]
    return totals


def get_customer_360(db: Session, cif: Optional[str] = None, account_number: Optional[str] = None,
                      scoped_pn: Optional[str] = None) -> Optional[dict]:
    if not cif and not account_number:
        return None

    as_of_dates = _customer_snapshot_dates(db)
    fresh = funding_calc.data_freshness(db)

    # Resolve identity + ownership from the latest snapshot rows available.
    identity_row = None
    for rtype, snap_date in as_of_dates.items():
        if not snap_date:
            continue
        q = db.query(FundingSnapshot).filter(FundingSnapshot.report_type == rtype, FundingSnapshot.snapshot_date == snap_date)
        q = q.filter(FundingSnapshot.cif == cif) if cif else q.filter(FundingSnapshot.account_number == account_number)
        row = q.first()
        if row:
            identity_row = row
            if cif is None:
                cif = row.cif
            break

    if scoped_pn and identity_row and identity_row.resolved_pn != scoped_pn:
        return None  # RMFT tried to view a customer outside their own book

    current = _aggregate_for_customer(db, as_of_dates, cif, account_number if not cif else None)

    baseline = {"tabungan": 0.0, "giro": 0.0, "deposito": 0.0, "casa": 0.0, "dpk": 0.0}
    if fresh["as_of"]:
        baseline_date = funding_calc.get_baseline_date(db, fresh["as_of"].strftime("%Y-%m"))
        if baseline_date:
            baseline = _aggregate_for_customer(db, {r: baseline_date for r in as_of_dates}, cif, account_number if not cif else None)

    dtd_ref_dates = {
        r: (funding_calc.get_previous_snapshot_date(db, r, d) if d else None) for r, d in as_of_dates.items()
    }
    previous = _aggregate_for_customer(db, dtd_ref_dates, cif, account_number if not cif else None)

    mtd = {k: current[k] - baseline[k] for k in current}
    dtd = {k: current[k] - previous[k] for k in current}

    # Pipeline summary (section 31) — populated once Phase 5 pipeline data exists.
    pipeline_q = db.query(Pipeline)
    pipeline_q = pipeline_q.filter(Pipeline.cif == cif) if cif else pipeline_q.filter(Pipeline.account_number == account_number)
    pipelines = pipeline_q.all()
    pipeline_nominal = sum(D(p.nominal) for p in pipelines)
    active_count = sum(1 for p in pipelines if p.status not in ("Realisasi", "Batal"))
    realized_ids = {p.pipeline_id for p in pipelines if p.status == "Realisasi"}
    realisasi_nominal = 0.0
    if pipelines:
        pipeline_ids = [p.pipeline_id for p in pipelines]
        realisasi_nominal = D(
            db.query(func.coalesce(func.sum(Realization.realization_amount), 0))
            .filter(Realization.pipeline_id.in_(pipeline_ids), Realization.status == "Realisasi")
            .scalar()
        )
    outstanding = max(pipeline_nominal - realisasi_nominal, 0.0)
    success_rate = (realisasi_nominal / pipeline_nominal * 100) if pipeline_nominal else 0.0

    return {
        "cif": cif,
        "account_number": account_number if not cif else None,
        "customer_name": identity_row.customer_name if identity_row else None,
        "funding": {"current": current, "mtd": mtd, "dtd": dtd},
        "movement": {
            "baseline": baseline, "previous": previous, "today": current,
            "mtd": mtd, "dtd": dtd, "as_of": fresh["as_of"],
        },
        "rmft": {
            "primary_pn": identity_row.resolved_pn if identity_row else None,
            "rmft_name": identity_row.resolved_rmft if identity_row else None,
            "ownership_source": identity_row.ownership_source.value if identity_row and identity_row.ownership_source else None,
        },
        "pipeline": {
            "active_count": active_count,
            "pipeline_nominal": pipeline_nominal,
            "realisasi_nominal": realisasi_nominal,
            "outstanding": outstanding,
            "success_rate": success_rate,
        },
    }
