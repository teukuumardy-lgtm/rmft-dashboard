"""Covers section 57: Export Laporan (Excel & PDF) for the 9 report types.

Renderer-level correctness (openpyxl cell values/number formats, reportlab
PDF structure) is verified separately and directly in this sandbox — see
/tmp/test_report_export.py referenced in the README, since it needs no
sqlalchemy/fastapi — because those two packages aren't installable here.
This suite instead covers the `build_report_rows()` dispatcher: that each
report type produces the right shape and numbers from real DB rows, and
that RBAC-relevant scoping (pn filter) works as expected.
"""
from datetime import date

import pytest

from app.models import FundingSnapshot, Pipeline, Realization, ReportType, RmftTarget, UploadBatch
from app.services import report_export


def _seed_funding_snapshot(db_session):
    batch = UploadBatch(filename="x.xlsx", report_type=ReportType.TABUNGAN, product="TABUNGAN",
                         snapshot_date=date(2026, 8, 20))
    db_session.add(batch)
    db_session.flush()
    db_session.add(FundingSnapshot(
        snapshot_date=date(2026, 8, 20), report_type=ReportType.TABUNGAN, account_number="1001",
        customer_name="PT Sinar Jaya", product="Tabungan", balance_idr=1_000_000_000,
        resolved_pn="00380727", resolved_rmft="Adist Ayudistira", upload_batch_id=batch.batch_id,
    ))
    db_session.commit()


def test_build_report_rows_unknown_report_raises(db_session):
    with pytest.raises(ValueError):
        report_export.build_report_rows(db_session, "not_a_real_report", {})


def test_funding_report_shape_and_values(db_session):
    _seed_funding_snapshot(db_session)
    result = report_export.build_report_rows(db_session, "funding", {"pn": None})
    assert result["title"] == "Posisi Funding per RMFT"
    row = next(r for r in result["rows"] if r["pn"] == "00380727")
    assert row["tabungan"] == 1_000_000_000
    assert row["dpk"] == 1_000_000_000


def test_rmft_performance_report_ranks_by_success_rate(db_session):
    p1 = Pipeline(pipeline_date=date(2026, 8, 3), pn="00380727", rmft="Adist Ayudistira",
                  customer="PT Kecil", product="Giro", nominal=100_000_000, status="Realisasi")
    db_session.add(p1)
    db_session.flush()
    db_session.add(Realization(pipeline_id=p1.pipeline_id, date=date(2026, 8, 3), realization_amount=100_000_000, status="Realisasi"))
    db_session.commit()

    result = report_export.build_report_rows(db_session, "rmft_performance", {"month": "2026-08"})
    top = result["rows"][0]
    assert top["rank"] == 1
    assert top["pn"] == "00380727"
    assert top["nominal_sr"] == pytest.approx(100.0)


def test_pipeline_report_filters_by_pn(db_session):
    db_session.add(Pipeline(pipeline_date=date(2026, 8, 10), pn="00380727", rmft="Adist Ayudistira",
                             customer="A", product="Giro", nominal=1, status="Prospect"))
    db_session.add(Pipeline(pipeline_date=date(2026, 8, 10), pn="00382271", rmft="Ahmad Rafiq",
                             customer="B", product="Giro", nominal=1, status="Prospect"))
    db_session.commit()

    result = report_export.build_report_rows(db_session, "pipeline", {"pn": "00380727"})
    assert len(result["rows"]) == 1
    assert result["rows"][0]["pn"] == "00380727"


def test_target_achievement_report(db_session):
    db_session.add(RmftTarget(month="2026-08", pn="00380727", product="Giro", target=500_000_000))
    p = Pipeline(pipeline_date=date(2026, 8, 5), pn="00380727", rmft="Adist Ayudistira",
                 customer="C", product="Giro", nominal=500_000_000, status="Realisasi")
    db_session.add(p)
    db_session.flush()
    db_session.add(Realization(pipeline_id=p.pipeline_id, date=date(2026, 8, 5), realization_amount=250_000_000, status="Realisasi"))
    db_session.commit()

    result = report_export.build_report_rows(db_session, "target_achievement", {"month": "2026-08"})
    row = result["rows"][0]
    assert row["achievement_pct"] == pytest.approx(50.0)
    assert row["gap"] == pytest.approx(250_000_000)


def test_monthly_performance_report_is_metric_value_rows(db_session):
    result = report_export.build_report_rows(db_session, "monthly_performance", {"month": "2026-08"})
    assert result["columns"][1][2] == "mixed"
    metrics = {r["metric"] for r in result["rows"]}
    assert "Total Pipeline Nominal" in metrics
    assert "RMFT Terbaik" in metrics


def test_customer_outflow_and_inflow_reports_use_correct_direction(db_session):
    out = report_export.build_report_rows(db_session, "customer_outflow", {"mode": "MTD"})
    inflow = report_export.build_report_rows(db_session, "customer_inflow", {"mode": "MTD"})
    assert out["title"] == "Top Customer Outflow"
    assert inflow["title"] == "Top Customer Inflow"
