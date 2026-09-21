"""Covers section 50 chart data: dpk_trend() (Funding Trend line chart) and
flow_totals() (Inflow vs Outflow chart) — both added for Task 25.

flow_totals() reuses the same _all_movers() candidate-building logic as
top_movers() (refactored out so the two stay consistent), so this suite
focuses on what's new: full-population sums (not just top 10) and the
per-date trend aggregation across TABUNGAN/GIRO/DEPOSITO snapshots that
don't necessarily share upload dates.
"""
from datetime import date, timedelta

from app.models import FundingSnapshot, ReportType, UploadBatch
from app.services import funding_calc


def _batch(db_session, report_type, snapshot_date):
    b = UploadBatch(filename="x.xlsx", report_type=report_type, product=report_type.value, snapshot_date=snapshot_date)
    db_session.add(b)
    db_session.flush()
    return b.batch_id


def _snap(db_session, report_type, snapshot_date, account_number, balance, pn="00380727", rmft="Adist Ayudistira"):
    batch_id = _batch(db_session, report_type, snapshot_date)
    db_session.add(FundingSnapshot(
        snapshot_date=snapshot_date, report_type=report_type, account_number=account_number,
        customer_name="PT Test", product=report_type.value, balance_idr=balance,
        resolved_pn=pn, resolved_rmft=rmft, upload_batch_id=batch_id,
    ))


def test_flow_totals_sums_full_population_not_just_top10(db_session):
    today = date.today()
    yesterday = today - timedelta(days=1)

    # 3 accounts moved: two inflows, one outflow -- flow_totals must sum ALL of
    # them, unlike top_movers(limit=1) which would only report one side.
    _snap(db_session, ReportType.TABUNGAN, yesterday, "A1", 1_000_000)
    _snap(db_session, ReportType.TABUNGAN, today, "A1", 1_500_000)  # +500k inflow

    _snap(db_session, ReportType.TABUNGAN, yesterday, "A2", 2_000_000)
    _snap(db_session, ReportType.TABUNGAN, today, "A2", 2_300_000)  # +300k inflow

    _snap(db_session, ReportType.TABUNGAN, yesterday, "A3", 900_000)
    _snap(db_session, ReportType.TABUNGAN, today, "A3", 400_000)  # -500k outflow
    db_session.commit()

    totals = funding_calc.flow_totals(db_session, mode="DTD")
    assert totals["inflow"] == 800_000
    assert totals["outflow"] == 500_000
    assert totals["net"] == 300_000


def test_flow_totals_scoped_by_pn(db_session):
    today = date.today()
    yesterday = today - timedelta(days=1)
    _snap(db_session, ReportType.TABUNGAN, yesterday, "B1", 1_000_000, pn="00380727")
    _snap(db_session, ReportType.TABUNGAN, today, "B1", 2_000_000, pn="00380727")
    _snap(db_session, ReportType.TABUNGAN, yesterday, "B2", 1_000_000, pn="00382271")
    _snap(db_session, ReportType.TABUNGAN, today, "B2", 3_000_000, pn="00382271")
    db_session.commit()

    totals = funding_calc.flow_totals(db_session, mode="DTD", pn="00380727")
    assert totals["inflow"] == 1_000_000


def test_dpk_trend_pins_each_product_to_its_own_latest_on_or_before_date(db_session):
    d1 = date(2026, 8, 10)
    d2 = date(2026, 8, 15)  # GIRO uploaded only here, not on d1 or a later date

    _snap(db_session, ReportType.TABUNGAN, d1, "T1", 1_000_000)
    _snap(db_session, ReportType.GIRO, d2, "G1", 500_000)
    db_session.commit()

    trend = funding_calc.dpk_trend(db_session, days=30)
    by_date = {t["date"]: t for t in trend}

    # On d1, GIRO has no data yet at all -> giro contributes 0.
    assert by_date[d1]["tabungan"] == 1_000_000
    assert by_date[d1]["giro"] == 0

    # On d2, TABUNGAN carries forward its last known value (d1) even though
    # TABUNGAN itself wasn't re-uploaded on d2.
    assert by_date[d2]["tabungan"] == 1_000_000
    assert by_date[d2]["giro"] == 500_000
    assert by_date[d2]["dpk"] == 1_500_000


def test_dpk_trend_respects_days_window(db_session):
    old_date = date.today() - timedelta(days=200)
    _snap(db_session, ReportType.TABUNGAN, old_date, "OLD1", 1_000_000)
    db_session.commit()

    trend = funding_calc.dpk_trend(db_session, days=30)
    assert all(t["date"] >= date.today() - timedelta(days=29) for t in trend)
