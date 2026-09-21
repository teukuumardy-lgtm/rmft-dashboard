"""
Covers section 40-41 (Pipeline vs Actual Funding match confidence) and
section 45-48 (WA Pagi / WA Sore generators).
"""
from datetime import date

from app.models import DismissedMatch, FundingSnapshot, MonthlyBaseline, Pipeline, Realization, ReportType, UploadBatch
from app.services import import_engine, pipeline_match, wa_generator
from tests.helpers import build_di319


def test_confidence_score_high_for_strong_match():
    """Section 41 worked example: pipeline Rp500jt vs actual inflow Rp505jt,
    matching CIF/account/name/product -> high confidence."""
    class FakePipeline:
        cif = "CIF001"
        account_number = "1234567890"
        customer = "PT ABC"
        product = "Giro"
        nominal = 500_000_000

    funding_row = {"cif": "CIF001", "account_number": "1234567890", "customer": "PT ABC",
                   "product": "GIRO", "delta": 505_000_000}
    score = pipeline_match.confidence_score(FakePipeline(), funding_row)
    assert score >= 90, f"expected a strong match, got {score}"


def test_confidence_score_low_for_unrelated_pair():
    class FakePipeline:
        cif = "CIF001"
        account_number = "1234567890"
        customer = "PT ABC"
        product = "Giro"
        nominal = 500_000_000

    funding_row = {"cif": "CIF999", "account_number": "999", "customer": "PT XYZ",
                   "product": "DEPOSITO", "delta": 10_000_000}
    score = pipeline_match.confidence_score(FakePipeline(), funding_row)
    assert score < 50, f"expected a weak/no match, got {score}"


def test_dismissed_match_is_persisted_and_excluded_from_future_suggestions(db_session):
    """Section 41: 'Reject' must be persisted server-side (not just a client-side
    filter) so the same pipeline+actual-account pairing doesn't resurface on reload."""
    today = date.today()
    yesterday = date(today.year, today.month, max(today.day - 1, 1))

    db_session.add(Pipeline(
        pipeline_date=today, pn="00380727", rmft="Adist Ayudistira", customer="PT ABC",
        cif="CIF001", account_number="1234567890", product="Giro", nominal=500_000_000,
        status="Follow Up",
    ))
    db_session.flush()

    batch = UploadBatch(filename="x.xlsx", report_type=ReportType.GIRO, product="GIRO", snapshot_date=today)
    db_session.add(batch)
    db_session.flush()
    db_session.add(FundingSnapshot(
        snapshot_date=yesterday, report_type=ReportType.GIRO, account_number="1234567890",
        cif="CIF001", customer_name="PT ABC", product="GIRO", balance_idr=0,
        resolved_pn="00380727", resolved_rmft="Adist Ayudistira", upload_batch_id=batch.batch_id,
    ))
    db_session.add(FundingSnapshot(
        snapshot_date=today, report_type=ReportType.GIRO, account_number="1234567890",
        cif="CIF001", customer_name="PT ABC", product="GIRO", balance_idr=505_000_000,
        resolved_pn="00380727", resolved_rmft="Adist Ayudistira", upload_batch_id=batch.batch_id,
    ))
    db_session.commit()

    before = pipeline_match.find_potential_matches(db_session, pn="00380727")
    assert len(before) == 1
    pipeline_id = before[0]["pipeline_id"]
    actual_account = before[0]["actual_account_number"]

    db_session.add(DismissedMatch(pipeline_id=pipeline_id, actual_account_number=actual_account))
    db_session.commit()

    after = pipeline_match.find_potential_matches(db_session, pn="00380727")
    assert after == []


def test_wa_pagi_contains_rmft_sections_and_unit_total(tmp_path, db_session):
    today = date(2026, 8, 20)
    db_session.add(Pipeline(
        pipeline_date=today, pn="00380727", rmft="Adist Ayudistira", customer="PT Sejahtera",
        product="Giro", nominal=500_000_000, probability=70, target_date=today,
        activity_today="Follow up telepon", status="Follow Up",
    ))
    db_session.commit()

    text = wa_generator.generate_wa_pagi(db_session, today)
    assert "ADIST AYUDISTIRA" in text
    assert "AHMAD RAFIQ" in text          # shown even with no pipeline today (transparency)
    assert "Belum ada pipeline hari ini." in text
    assert "PT Sejahtera" in text
    assert "TOTAL PIPELINE UNIT" in text
    assert "Rp500 jt" in text


def test_wa_sore_contains_success_rate_and_funding_position(tmp_path, db_session):
    today = date(2026, 8, 20)
    p = Pipeline(
        pipeline_date=today, pn="00380727", rmft="Adist Ayudistira", customer="PT Sejahtera",
        product="Giro", nominal=500_000_000, probability=70, target_date=today, status="Realisasi",
    )
    db_session.add(p)
    db_session.flush()
    db_session.add(Realization(pipeline_id=p.pipeline_id, date=today, realization_amount=500_000_000, status="Realisasi"))

    # Funding snapshot so the FUNDING POSITION section has real numbers.
    baseline_path = tmp_path / "baseline.xlsx"
    build_di319(str(baseline_path), periode="31/07/2026", date_printed="31/07/2026")
    import_engine.import_report(db_session, str(baseline_path), "baseline.xlsx", uploaded_by=None)
    current_path = tmp_path / "current.xlsx"
    build_di319(str(current_path), periode="20/08/2026")
    import_engine.import_report(db_session, str(current_path), "current.xlsx", uploaded_by=None)
    db_session.add(MonthlyBaseline(baseline_month="2026-08", baseline_date=date(2026, 7, 31)))
    db_session.commit()

    text = wa_generator.generate_wa_sore(db_session, today)
    assert "SUMMARY UNIT" in text
    assert "Nominal Success Rate" in text
    assert "🏆 RMFT Conversion terbaik" in text
    assert "FUNDING POSITION" in text
    assert "Tabungan:" in text
