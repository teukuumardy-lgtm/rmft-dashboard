"""
Section 7-12: report format detection.

The dashboard must read the ORIGINAL report files exactly as exported by the
core banking system — no renaming, no template copy/paste, no deleting title
rows. This module:

  1. Loads a workbook (first sheet, or a sheet whose name/content matches)
     as a raw grid of cells (no assumptions about which row is the header).
  2. Scans the first N rows for a header row, scoring each candidate row
     against three known report signatures (DI319/Tabungan, DI321/Giro,
     CI324/Deposito).
  3. Also looks for the report title strings anywhere in the scanned rows
     as a confidence bonus.
  4. Returns the winning report type, the header row index, a header->column
     map, and the parsed data rows as list[dict] keyed by canonical field
     names (with the original PN-like columns preserved separately for the
     ownership engine).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

import openpyxl

MAX_HEADER_SCAN_ROWS = 40


def _normalize(text: Any) -> str:
    """Uppercase, strip accents/punctuation/whitespace -> a matchable token."""
    if text is None:
        return ""
    s = str(text)
    s = unicodedata.normalize("NFKD", s)
    s = s.upper()
    s = re.sub(r"[^A-Z0-9]", "", s)
    return s


# --- Title signatures (section 8/9/10) --------------------------------------
TITLE_SIGNATURES = {
    "TABUNGAN": "SAVINGSACCOUNTMONTHLYTRIALBALANCE",
    "GIRO": "CURRENTACCOUNTMONTHLYTRIALBALANCE",
    "DEPOSITO": "FDSMONTHLYTRIALBALANCE",
}

# --- Header synonym maps -----------------------------------------------------
# canonical_field -> list of normalized header variants that count as a match
HEADER_SYNONYMS = {
    "TABUNGAN": {
        "snapshot_date": ["PERIODE"],
        "account_number": ["ACCOUNTNUMBER", "ACCTNO", "ACCOUNTNO"],
        "cif": ["CIFFNO", "CIFNO", "CIF"],
        "customer": ["SHORTNAME"],
        "product_code": ["PRODCODE", "PRODUCTCODE"],
        "currency": ["CURRCODE", "CURR"],
        "balance_original": ["BALANCE"],
        "balance_idr": ["BALANCEDALAMIDR", "BALANCEINIDR"],
    },
    "GIRO": {
        "snapshot_date": ["PERIODE"],
        "account_number": ["ACCOUNTNUMBER", "ACCTNO"],
        "cif": ["CIFNO", "CIF"],
        "customer": ["SHORTNAME"],
        "product_code": ["PRODUCTCODE"],
        "status": ["STATUS"],
        "balance_original": ["BALANCE"],
        "avail_balance": ["AVAILBALANCE"],
        "avg_balance": ["AVRGBALANCE", "AVERAGEBALANCE"],
        "currency": ["CURR", "CURRCODE"],
    },
    "DEPOSITO": {
        "snapshot_date": ["PERIODE"],
        "account_number": ["ACCTNO", "ACCOUNTNO"],
        "fdr_serial": ["FDRSRLNO", "FDRSERIALNO"],
        "customer": ["SHORTNAME"],
        "type": ["TYPE"],
        "principal": ["PRINCIPALAMOUNT"],
        "issue_date": ["ISSUEDT", "ISSUEDATE"],
        "maturity_date": ["MATDT", "MATURITYDATE"],
        "rate": ["INTRATE", "INTERESTRATE"],
        "tenor": ["INTTENORDISP", "TENOR"],
        "renewal": ["RENEW"],
        "balance_idr": ["CBALBASE"],
    },
    "EDC": {
        # NOTE: in the real export, PERIODE is a month string ("2026-08"), not
        # a parseable date — POSISI carries the actual snapshot date (e.g. a
        # datetime for 31/08/2026). snapshot_date must come from POSISI.
        "snapshot_date": ["POSISI"],
        "periode_month": ["PERIODE"],
        "uker_name": ["NAMAUKER"],
        "terminal_id": ["TID"],
        "merchant_ref": ["MID"],
        "merchant_name": ["NAMAMERCHANT"],
        "pemrakarsa": ["NAMAUSERPEMRAKARSA"],
        "sales_volume": ["SALESVOLUME"],
        "account_number": ["NOREK"],
    },
    "QRIS": {
        # Same PERIODE/POSISI split as EDC — see note above.
        "snapshot_date": ["POSISI"],
        "periode_month": ["PERIODE"],
        "uker_name": ["BRDESC"],
        "terminal_id": ["STOREID"],
        "merchant_ref": ["MERCHANTPAN"],
        "merchant_name": ["NAMAMERCHANT"],
        "pemrakarsa": ["PNPEMRAKASA", "PNPEMRAKARSA"],
        "status": ["STATUS"],
        "sales_volume": ["POSISISVTOTAL"],
        "account_number": ["NOREK"],
    },
}

# Fields that MUST be present in a header row for it to be considered a
# plausible header for that report type at all (used to gate false positives).
REQUIRED_FIELDS = {
    "TABUNGAN": ["snapshot_date", "account_number", "balance_original", "customer"],
    "GIRO": ["snapshot_date", "account_number", "balance_original", "customer"],
    "DEPOSITO": ["snapshot_date", "account_number", "principal", "customer"],
    "EDC": ["snapshot_date", "terminal_id", "sales_volume", "account_number"],
    "QRIS": ["snapshot_date", "terminal_id", "sales_volume", "account_number"],
}


def _is_pn_header(normalized: str) -> bool:
    return normalized.startswith("PN")


def _pn_priority_tier(normalized: str, original: str) -> tuple[int, str]:
    """Section 14: map a 'PN ...' header to its ownership priority tier."""
    if "PNRMDANA" in normalized or "PNRMMANTRI" in normalized:
        return 1, "PN RM Dana/Mantri"
    if "PNPENGELOLASINGLEPN" in normalized:
        return 2, "PN PENGELOLA SINGLEPN"
    if "PNRMREFERRAL" in normalized:
        return 3, "PN RM Referral"
    if "PNRELATIONSHIPOFFICER" in normalized or "PNRMKREDITMENENGAH" in normalized:
        return 4, "PN Relationship Officer/RM Kredit Menengah"
    return 5, "Kolom PN Lainnya"


@dataclass
class DetectedSheet:
    report_type: Optional[str]
    header_row_index: Optional[int]
    field_columns: dict[str, int] = field(default_factory=dict)   # canonical -> col idx
    pn_columns: list[tuple[int, int, str]] = field(default_factory=list)  # (col idx, tier, label)
    all_headers: dict[int, str] = field(default_factory=dict)     # col idx -> raw header text
    grid: list[list[Any]] = field(default_factory=list)
    error: Optional[str] = None


def load_grid(file_path: str) -> list[list[Any]]:
    wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
    ws = wb.worksheets[0]
    grid = []
    for row in ws.iter_rows(values_only=True):
        grid.append(list(row))
    return grid


def detect_report(file_path: str) -> DetectedSheet:
    try:
        grid = load_grid(file_path)
    except Exception as exc:  # noqa: BLE001
        return DetectedSheet(report_type=None, header_row_index=None, error=f"Tidak bisa membuka file: {exc}")

    if not grid:
        return DetectedSheet(report_type=None, header_row_index=None, error="File kosong")

    scan_limit = min(MAX_HEADER_SCAN_ROWS, len(grid))

    # Title bonus: does any of the first N rows contain a report title string?
    title_hit: Optional[str] = None
    for r in range(scan_limit):
        row_text = _normalize(" ".join(str(c) for c in grid[r] if c is not None))
        for rtype, sig in TITLE_SIGNATURES.items():
            if sig in row_text:
                title_hit = rtype
                break
        if title_hit:
            break

    best: Optional[DetectedSheet] = None
    best_score = 0.0

    for r in range(scan_limit):
        row = grid[r]
        normalized_cells = {c: _normalize(v) for c, v in enumerate(row) if v is not None and str(v).strip() != ""}
        if not normalized_cells:
            continue

        for rtype, synonyms in HEADER_SYNONYMS.items():
            field_columns: dict[str, int] = {}
            for canonical, variants in synonyms.items():
                for col, norm in normalized_cells.items():
                    if norm in variants:
                        field_columns[canonical] = col
                        break

            required = REQUIRED_FIELDS[rtype]
            matched_required = sum(1 for f in required if f in field_columns)
            if matched_required < len(required):
                continue  # not a plausible header row for this report type

            score = matched_required + 0.25 * (len(field_columns) - matched_required)
            if title_hit == rtype:
                score += 2.0

            if score > best_score:
                pn_columns = []
                all_headers = {}
                for col, val in enumerate(row):
                    if val is None or str(val).strip() == "":
                        continue
                    norm = _normalize(val)
                    all_headers[col] = str(val).strip()
                    if _is_pn_header(norm):
                        tier, label = _pn_priority_tier(norm, str(val))
                        pn_columns.append((col, tier, label))

                best = DetectedSheet(
                    report_type=rtype,
                    header_row_index=r,
                    field_columns=field_columns,
                    pn_columns=pn_columns,
                    all_headers=all_headers,
                    grid=grid,
                )
                best_score = score

    if best is None:
        return DetectedSheet(
            report_type=None,
            header_row_index=None,
            grid=grid,
            error="Header report tidak dikenali (bukan format DI319/DI321/CI324 yang valid)",
        )
    return best


# --- value coercion helpers ---------------------------------------------------

def to_decimal(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if s == "" or s.upper() in {"NA", "N/A", "-"}:
        return None
    s = s.replace(".", "").replace(",", ".") if s.count(",") == 1 and s.count(".") > 1 else s
    s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def to_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def to_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if isinstance(value, float) and value.is_integer():
        s = str(int(value))
    return s or None
