"""
Section 18-19, 53-54: orchestrates preview + import of the three daily
funding reports (DI319/Tabungan, DI321/Giro, CI324/Deposito).

Design choice for anti-double-count (section 16): rather than relying only
on the DB unique constraint, a (report_type, snapshot_date) import REPLACES
every funding_snapshot row previously stored for that exact key before
inserting the freshly parsed rows. Re-uploading the same file (or a
corrected version of it) can never accumulate/duplicate balances.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    AccountMaster, AccountRmftAssignment, CustomerMaster, FundingSnapshot,
    OwnershipSource, RawImport, ReportType, RmftMaster, UploadBatch, UploadStatus,
)
from app.services import excel_detect as det
from app.services import pn_engine


REPORT_TYPE_MAP = {
    "TABUNGAN": ReportType.TABUNGAN,
    "GIRO": ReportType.GIRO,
    "DEPOSITO": ReportType.DEPOSITO,
}

TOTAL_ROW_MARKERS = ("TOTAL", "GRANDTOTAL", "SUBTOTAL")


def _normalize(text) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(text).upper()) if text is not None else ""


def _find_label_value(grid: list[list], label_variants: list[str], before_row: int):
    """Scan rows above the header for a 'LABEL : value' style metadata line."""
    for r in range(min(before_row, len(grid))):
        row = grid[r]
        for c, cell in enumerate(row):
            if cell is None:
                continue
            if _normalize(cell) in label_variants:
                # try same row, following non-empty cells
                for c2 in range(c + 1, len(row)):
                    if row[c2] is not None and str(row[c2]).strip() != "":
                        return row[c2]
                # try next row, same column
                if r + 1 < len(grid) and c < len(grid[r + 1]) and grid[r + 1][c] is not None:
                    return grid[r + 1][c]
    return None


@dataclass
class ParsedRow:
    account_number: str
    fdr_serial: Optional[str]
    cif: Optional[str]
    customer_name: Optional[str]
    product: Optional[str]
    product_code: Optional[str]
    currency: Optional[str]
    balance_original: Optional[float]
    balance_idr: Optional[float]
    resolved_pn: Optional[str]
    resolved_rmft: Optional[str]
    ownership_source: str
    conflict_flag: bool
    raw: dict
    maturity_date: Optional[object] = None
    issue_date: Optional[object] = None
    interest_rate: Optional[float] = None
    tenor: Optional[str] = None
    balance_invalid: bool = False


def _label_for_source(source_text: str) -> OwnershipSource:
    for member in OwnershipSource:
        if member.value == source_text:
            return member
    return OwnershipSource.OTHER


def preview_file(file_path: str, filename: str) -> dict:
    detected = det.detect_report(file_path)
    if detected.report_type is None:
        return {
            "detected": False, "report_type": None, "periode": None,
            "date_printed": None, "rows": 0, "header_row_index": None,
            "filename": filename, "error": detected.error,
        }

    periode_raw = None
    date_printed_raw = None
    if "snapshot_date" in detected.field_columns:
        # per-row PERIODE column: sample first data row
        for r in range(detected.header_row_index + 1, len(detected.grid)):
            val = detected.grid[r][detected.field_columns["snapshot_date"]]
            if val is not None:
                periode_raw = val
                break
    if periode_raw is None:
        periode_raw = _find_label_value(detected.grid, ["PERIODE"], detected.header_row_index)
    date_printed_raw = _find_label_value(detected.grid, ["DATEPRINTED", "PRINTEDDATE"], detected.header_row_index)

    row_count = 0
    acct_col = detected.field_columns.get("account_number")
    for r in range(detected.header_row_index + 1, len(detected.grid)):
        row = detected.grid[r]
        if acct_col is None or acct_col >= len(row):
            continue
        val = row[acct_col]
        if val is None or str(val).strip() == "":
            continue
        if _normalize(val) in TOTAL_ROW_MARKERS:
            continue
        row_count += 1

    return {
        "detected": True,
        "report_type": detected.report_type,
        "periode": det.to_date(periode_raw),
        "date_printed": det.to_date(date_printed_raw),
        "rows": row_count,
        "header_row_index": detected.header_row_index,
        "filename": filename,
        "error": None,
    }


def parse_rows(detected: det.DetectedSheet, valid_pns: set[str], pn_to_name: dict[str, str]) -> tuple[list[ParsedRow], dict]:
    fc = detected.field_columns
    acct_col = fc.get("account_number")
    stats = {"total_rows": 0, "invalid_balance": 0}
    parsed: list[ParsedRow] = []

    for r in range(detected.header_row_index + 1, len(detected.grid)):
        row = detected.grid[r]
        if acct_col is None or acct_col >= len(row):
            continue
        account_raw = row[acct_col]
        if account_raw is None or str(account_raw).strip() == "":
            continue
        if _normalize(account_raw) in TOTAL_ROW_MARKERS:
            continue

        stats["total_rows"] += 1

        def get(field_name):
            col = fc.get(field_name)
            if col is None or col >= len(row):
                return None
            return row[col]

        if detected.report_type == "DEPOSITO":
            bal_idr = det.to_decimal(get("balance_idr"))
            if bal_idr is None:
                bal_idr = det.to_decimal(get("principal"))
            balance_original = det.to_decimal(get("principal"))
        elif detected.report_type == "TABUNGAN":
            bal_idr = det.to_decimal(get("balance_idr"))
            balance_original = det.to_decimal(get("balance_original"))
            if bal_idr is None:
                bal_idr = balance_original
        else:  # GIRO: use BALANCE, not AVAIL BALANCE (section 9)
            balance_original = det.to_decimal(get("balance_original"))
            bal_idr = balance_original

        balance_invalid = bal_idr is None
        if balance_invalid:
            stats["invalid_balance"] += 1

        pn_values = []
        for col, tier, label in detected.pn_columns:
            if col < len(row):
                pn_values.append((tier, label, row[col]))
        ownership = pn_engine.resolve_ownership(pn_values, valid_pns)

        raw_dict = {detected.all_headers.get(c, f"col_{c}"): (str(v) if v is not None else None)
                    for c, v in enumerate(row) if c in detected.all_headers}

        parsed.append(ParsedRow(
            account_number=det.to_str(account_raw) or "",
            fdr_serial=det.to_str(get("fdr_serial")) if detected.report_type == "DEPOSITO" else None,
            cif=det.to_str(get("cif")),
            customer_name=det.to_str(get("customer")),
            product=detected.report_type,
            product_code=det.to_str(get("product_code")),
            currency=det.to_str(get("currency")),
            balance_original=balance_original,
            balance_idr=bal_idr,
            resolved_pn=ownership.primary_pn,
            resolved_rmft=pn_to_name.get(ownership.primary_pn) if ownership.primary_pn else None,
            ownership_source=ownership.primary_source,
            conflict_flag=ownership.conflict_flag,
            raw=raw_dict,
            maturity_date=det.to_date(get("maturity_date")) if detected.report_type == "DEPOSITO" else None,
            issue_date=det.to_date(get("issue_date")) if detected.report_type == "DEPOSITO" else None,
            interest_rate=det.to_decimal(get("rate")) if detected.report_type == "DEPOSITO" else None,
            tenor=det.to_str(get("tenor")) if detected.report_type == "DEPOSITO" else None,
            balance_invalid=balance_invalid,
        ))

    return parsed, stats


def import_report(
    db: Session,
    file_path: str,
    filename: str,
    uploaded_by: Optional[str],
) -> dict:
    """Full parse + ownership resolution + upsert for one detected file."""
    detected = det.detect_report(file_path)
    if detected.report_type is None:
        return {"error": detected.error, "report_type": None}

    report_type_enum = REPORT_TYPE_MAP[detected.report_type]

    periode_raw = None
    if "snapshot_date" in detected.field_columns:
        for r in range(detected.header_row_index + 1, len(detected.grid)):
            val = detected.grid[r][detected.field_columns["snapshot_date"]]
            if val is not None:
                periode_raw = val
                break
    if periode_raw is None:
        periode_raw = _find_label_value(detected.grid, ["PERIODE"], detected.header_row_index)
    snapshot_date = det.to_date(periode_raw)
    if snapshot_date is None:
        return {"error": "Tidak dapat menentukan PERIODE (tanggal posisi) dari file ini.", "report_type": detected.report_type}

    date_printed_raw = _find_label_value(detected.grid, ["DATEPRINTED", "PRINTEDDATE"], detected.header_row_index)
    date_printed = det.to_date(date_printed_raw)

    master_rows = db.query(RmftMaster).filter(RmftMaster.active.is_(True)).all()
    valid_pns = {m.pn for m in master_rows}
    pn_to_name = {m.pn: m.rmft_name for m in master_rows}

    parsed_rows, stats = parse_rows(detected, valid_pns, pn_to_name)

    # Dedupe within this file by unique key (section 16)
    dedup: dict[tuple, ParsedRow] = {}
    duplicates_removed = 0
    for pr in parsed_rows:
        key = (pr.account_number, pr.fdr_serial)
        if key in dedup:
            duplicates_removed += 1
        dedup[key] = pr  # last occurrence wins

    final_rows = [pr for pr in dedup.values() if not pr.balance_invalid]

    batch = UploadBatch(
        filename=filename,
        report_type=report_type_enum,
        product=detected.report_type,
        snapshot_date=snapshot_date,
        date_printed=date_printed,
        uploaded_by=uploaded_by,
        row_count=stats["total_rows"],
        valid_count=len(final_rows),
        invalid_count=stats["invalid_balance"],
        duplicates_removed=duplicates_removed,
        pn_conflict_count=sum(1 for r in final_rows if r.conflict_flag),
        unassigned_count=sum(1 for r in final_rows if r.resolved_pn is None),
        status=UploadStatus.SUCCESS if stats["invalid_balance"] == 0 else UploadStatus.PARTIAL,
    )
    db.add(batch)
    db.flush()  # get batch_id

    # Raw storage — never discard source data (section 54)
    for idx, pr in enumerate(parsed_rows):
        db.add(RawImport(batch_id=batch.batch_id, row_index=idx, raw_json=json.dumps(pr.raw, default=str)))

    # REPLACE SNAPSHOT: delete any prior snapshot for this exact (report_type, snapshot_date)
    db.query(FundingSnapshot).filter(
        FundingSnapshot.report_type == report_type_enum,
        FundingSnapshot.snapshot_date == snapshot_date,
    ).delete(synchronize_session=False)

    # Master data upsert (section 55: customer_master / account_master) —
    # keeps CIF -> customer name and account -> CIF/product lookups current
    # for Customer 360 / search, independent of any single day's snapshot.
    cif_values = {pr.cif: pr.customer_name for pr in final_rows if pr.cif}
    if cif_values:
        existing_customers = {
            c.cif: c for c in db.query(CustomerMaster).filter(CustomerMaster.cif.in_(cif_values.keys())).all()
        }
        for cif, name in cif_values.items():
            if cif in existing_customers:
                if name:
                    existing_customers[cif].customer_name = name
            else:
                db.add(CustomerMaster(cif=cif, customer_name=name or cif))
        db.flush()  # ensure customer_master rows exist before account_master FK references them

    account_numbers = [pr.account_number for pr in final_rows]
    existing_accounts = {
        a.account_number: a for a in db.query(AccountMaster).filter(AccountMaster.account_number.in_(account_numbers)).all()
    }
    for pr in final_rows:
        acc = existing_accounts.get(pr.account_number)
        if acc:
            acc.cif = pr.cif or acc.cif
            acc.customer_name = pr.customer_name or acc.customer_name
            acc.product = detected.report_type
        else:
            new_acc = AccountMaster(
                account_number=pr.account_number, cif=pr.cif,
                customer_name=pr.customer_name, product=detected.report_type,
            )
            db.add(new_acc)
            existing_accounts[pr.account_number] = new_acc

    for pr in final_rows:
        db.add(FundingSnapshot(
            snapshot_date=snapshot_date,
            report_type=report_type_enum,
            account_number=pr.account_number,
            fdr_serial=pr.fdr_serial,
            cif=pr.cif,
            customer_name=pr.customer_name,
            product=detected.report_type,
            product_code=pr.product_code,
            currency=pr.currency,
            balance_original=pr.balance_original,
            balance_idr=pr.balance_idr,
            resolved_pn=pr.resolved_pn,
            resolved_rmft=pr.resolved_rmft,
            ownership_source=_label_for_source(pr.ownership_source),
            conflict_flag=pr.conflict_flag,
            upload_batch_id=batch.batch_id,
            maturity_date=pr.maturity_date,
            issue_date=pr.issue_date,
            interest_rate=pr.interest_rate,
            tenor=pr.tenor,
        ))

        # Upsert account_rmft_assignment (per account per snapshot date)
        existing = db.query(AccountRmftAssignment).filter(
            AccountRmftAssignment.snapshot_date == snapshot_date,
            AccountRmftAssignment.account_number == pr.account_number,
        ).first()
        if existing:
            existing.primary_pn = pr.resolved_pn
            existing.ownership_source = _label_for_source(pr.ownership_source)
            existing.conflict_flag = pr.conflict_flag
        else:
            db.add(AccountRmftAssignment(
                snapshot_date=snapshot_date,
                account_number=pr.account_number,
                primary_pn=pr.resolved_pn,
                ownership_source=_label_for_source(pr.ownership_source),
                conflict_flag=pr.conflict_flag,
            ))

    db.commit()

    return {
        "error": None,
        "report_type": detected.report_type,
        "periode": snapshot_date,
        "total_rows": stats["total_rows"],
        "target_rmft_rows": sum(1 for r in final_rows if r.resolved_pn is not None),
        "unique_accounts": len(dedup),
        "duplicates_removed": duplicates_removed,
        "pn_conflict": batch.pn_conflict_count,
        "unassigned": batch.unassigned_count,
        "invalid_balance": stats["invalid_balance"],
        "status": batch.status.value,
        "batch_id": batch.batch_id,
    }
