"""
Section 13-15: PN ownership engine.

A single data row can carry several PN columns (RM Dana, Pengelola SinglePN,
Referral, Relationship Officer, and other PN-ish columns). This module:

  1. Extracts every 8-digit PN found in the row's PN-tagged columns.
  2. Keeps only PNs that exist in rmft_master (the only PNs we can assign
     balances to).
  3. Deduplicates by PN, keeping the highest-priority (lowest tier number)
     source label each PN was found under.
  4. Picks the Priority-1 (lowest tier) PN as Primary Owner.
  5. If a second, DIFFERENT valid PN is found in a lower-priority column,
     flags a conflict and records it as Secondary.

Never double counts: this returns exactly ONE primary owner per row.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

PN_PATTERN = re.compile(r"\d{8}")


@dataclass
class OwnershipResult:
    primary_pn: Optional[str]
    primary_source: str        # OwnershipSource label
    secondary_pn: Optional[str]
    conflict_flag: bool


def extract_pns(cell_value) -> list[str]:
    """Pull every 8-digit sequence out of a cell (handles '00380727 - Adist ...')."""
    if cell_value is None:
        return []
    return PN_PATTERN.findall(str(cell_value))


def resolve_ownership(
    pn_column_values: list[tuple[int, str, object]],
    valid_pns: set[str],
) -> OwnershipResult:
    """
    pn_column_values: list of (tier, source_label, raw_cell_value) for every
    PN-tagged column present in this row (tier 1 = highest priority).
    valid_pns: set of 8-digit PNs present in rmft_master.
    """
    # Track the best (lowest) tier + label at which each valid PN was seen.
    best_for_pn: dict[str, tuple[int, str]] = {}
    for tier, label, raw_value in pn_column_values:
        for pn in extract_pns(raw_value):
            if pn not in valid_pns:
                continue
            if pn not in best_for_pn or tier < best_for_pn[pn][0]:
                best_for_pn[pn] = (tier, label)

    if not best_for_pn:
        return OwnershipResult(primary_pn=None, primary_source="UNASSIGNED", secondary_pn=None, conflict_flag=False)

    ranked = sorted(best_for_pn.items(), key=lambda item: item[1][0])  # by tier asc
    primary_pn, (primary_tier, primary_label) = ranked[0]

    if len(ranked) > 1:
        secondary_pn = ranked[1][0]
        conflict_flag = True
    else:
        secondary_pn = None
        conflict_flag = False

    return OwnershipResult(
        primary_pn=primary_pn,
        primary_source=primary_label,
        secondary_pn=secondary_pn,
        conflict_flag=conflict_flag,
    )
