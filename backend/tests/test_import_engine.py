"""
Covers spec section 78 acceptance tests 1-9 for the import engine:
detection of DI319/DI321/CI324, PN grouping, anti-double-count, and
MTD/DTD-ready snapshot storage.

Run with:  cd backend && pytest -v
(requires the full requirements.txt installed — see README for setup,
since this sandbox could not reach PyPI to install fastapi/sqlalchemy
to execute this suite itself).
"""
from datetime import date

from app.models import FundingSnapshot, ReportType
from app.services import import_engine
from tests.helpers import build_ci324, build_di319, build_di321


def test_di319_detected_as_tabungan(tmp_path, db_session):
    path = tmp_path / "di319.xlsx"
    build_di319(str(path))
    result = import_engine.import_report(db_session, str(path), "di319.xlsx", uploaded_by=None)
    assert result["error"] is None
    assert result["report_type"] == "TABUNGAN"
    assert result["periode"] == date(2026, 8, 20)


def test_di321_detected_as_giro(tmp_path, db_session):
    path = tmp_path / "di321.xlsx"
    build_di321(str(path))
    result = import_engine.import_report(db_session, str(path), "di321.xlsx", uploaded_by=None)
    assert result["report_type"] == "GIRO"


def test_ci324_detected_as_deposito(tmp_path, db_session):
    path = tmp_path / "ci324.xlsx"
    build_ci324(str(path))
    result = import_engine.import_report(db_session, str(path), "ci324.xlsx", uploaded_by=None)
    assert result["report_type"] == "DEPOSITO"


def test_pn_grouped_to_correct_rmft_with_conflict(tmp_path, db_session):
    path = tmp_path / "di319.xlsx"
    build_di319(str(path))
    import_engine.import_report(db_session, str(path), "di319.xlsx", uploaded_by=None)

    row = db_session.query(FundingSnapshot).filter(FundingSnapshot.account_number == "1234567890").first()
    assert row.resolved_pn == "00382271"          # RM Dana wins (Ahmad Rafiq)
    assert row.conflict_flag is True               # Referral PN (Dia Silopa) present too

    row2 = db_session.query(FundingSnapshot).filter(FundingSnapshot.account_number == "1234567891").first()
    assert row2.resolved_pn == "00380727"           # Adist, no conflict
    assert row2.conflict_flag is False


def test_no_double_count_on_reupload(tmp_path, db_session):
    path = tmp_path / "di319.xlsx"
    build_di319(str(path))
    import_engine.import_report(db_session, str(path), "di319.xlsx", uploaded_by=None)
    import_engine.import_report(db_session, str(path), "di319_reupload.xlsx", uploaded_by=None)

    rows = db_session.query(FundingSnapshot).filter(
        FundingSnapshot.report_type == ReportType.TABUNGAN,
        FundingSnapshot.snapshot_date == date(2026, 8, 20),
        FundingSnapshot.account_number == "1234567890",
    ).all()
    assert len(rows) == 1, "re-uploading the same snapshot must replace, not duplicate"
    assert float(rows[0].balance_idr) == 1_000_000.0


def test_duplicate_account_within_same_file_is_deduped(tmp_path, db_session):
    path = tmp_path / "di319_dup.xlsx"
    dup_row = ["20/08/2026", "1234567890", "CIF001", "PT ABC (corrected)", "SAV", "IDR",
               1_500_000, 1_500_000, "00382271 Ahmad Rafiq", None, None]
    build_di319(str(path), extra_rows=[dup_row])
    result = import_engine.import_report(db_session, str(path), "di319_dup.xlsx", uploaded_by=None)
    assert result["duplicates_removed"] == 1

    row = db_session.query(FundingSnapshot).filter(FundingSnapshot.account_number == "1234567890").first()
    assert float(row.balance_idr) == 1_500_000.0, "last occurrence in file should win"


def test_baseline_then_current_snapshot_mtd(tmp_path, db_session):
    """Sections 17 & 22: upload baseline (31 Jul), then current (20 Aug), compute MTD."""
    from app.models import MonthlyBaseline
    from app.services import funding_calc

    baseline_path = tmp_path / "di319_baseline.xlsx"
    build_di319(str(baseline_path), periode="31/07/2026", date_printed="31/07/2026")
    import_engine.import_report(db_session, str(baseline_path), "baseline.xlsx", uploaded_by=None)

    current_path = tmp_path / "di319_current.xlsx"
    build_di319(str(current_path), periode="20/08/2026")
    import_engine.import_report(db_session, str(current_path), "current.xlsx", uploaded_by=None)

    db_session.add(MonthlyBaseline(baseline_month="2026-08", baseline_date=date(2026, 7, 31)))
    db_session.commit()

    kpis = funding_calc.compute_home_kpis(db_session)
    # Same rows/balances at both dates in this fixture -> MTD delta should be 0
    assert kpis["unit_mtd"]["tabungan"] == 0.0
    assert kpis["freshness"]["as_of"] == date(2026, 8, 20)


def test_dtd_uses_latest_available_previous_snapshot_not_calendar_h1(tmp_path, db_session):
    """Section 23: if last data was the 18th and next is the 20th, DTD = 20 vs 18."""
    from app.services import funding_calc

    p18 = tmp_path / "di319_18.xlsx"
    build_di319(str(p18), periode="18/08/2026")
    import_engine.import_report(db_session, str(p18), "d18.xlsx", uploaded_by=None)

    p20 = tmp_path / "di319_20.xlsx"
    extra = ["20/08/2026", "1234567899", "CIF099", "PT NEWCO", "SAV", "IDR",
             500_000, 500_000, "00380727 Adist Ayudistira", None, None]
    build_di319(str(p20), periode="20/08/2026", extra_rows=[extra])
    import_engine.import_report(db_session, str(p20), "d20.xlsx", uploaded_by=None)

    ref_date = funding_calc.get_previous_snapshot_date(db_session, ReportType.TABUNGAN, date(2026, 8, 20))
    assert ref_date == date(2026, 8, 18)

    movers = funding_calc.top_movers(db_session, mode="DTD", direction="inflow", limit=10)
    new_account = next(m for m in movers if m["account_number"] == "1234567899")
    assert new_account["status"] == "NEW_ACCOUNT"
    assert new_account["delta"] == 500_000.0


def test_account_missing_flagged_not_zeroed(tmp_path, db_session):
    """Section 25: an account present yesterday but absent today is flagged
    ACCOUNT_MISSING / potential full outflow, never silently treated as balance 0."""
    import openpyxl
    from app.services import funding_calc

    p18 = tmp_path / "di319_18b.xlsx"
    build_di319(str(p18), periode="18/08/2026")
    import_engine.import_report(db_session, str(p18), "d18b.xlsx", uploaded_by=None)

    # Build the 20th snapshot with ONLY one of the two accounts -> the other vanished.
    p20 = tmp_path / "di319_20b.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["SAVINGS ACCOUNT MONTHLY TRIAL BALANCE"])
    ws.append([])
    ws.append([
        "periode", "account number", "ciff no", "short name", "prod code", "curr code",
        "balance", "Balance dalam IDR", "PN RM Dana/Mantri", "PN RM Referral", "PN Customer Service",
    ])
    ws.append(["20/08/2026", "1234567891", "CIF002", "PT DEF", "SAV", "IDR",
               2_000_000, 2_000_000, "00380727 - Adist Ayudistira Sembiring", None, None])
    wb.save(str(p20))
    import_engine.import_report(db_session, str(p20), "d20b.xlsx", uploaded_by=None)

    movers = funding_calc.top_movers(db_session, mode="DTD", direction="outflow", limit=10)
    missing = next(m for m in movers if m["account_number"] == "1234567890")
    assert missing["status"] == "ACCOUNT_MISSING"
    assert missing["current_balance"] == 0.0
    assert missing["baseline_or_previous"] == 1_000_000.0
    assert missing["delta"] == -1_000_000.0
