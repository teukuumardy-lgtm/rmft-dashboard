"""
Section 58: Indonesian number formatting, shared by the WA generator so the
text pasted into WhatsApp matches the numbers shown on screen. Mirrors
frontend/src/utils/format.js's formatShort/formatFull — keep both in sync.
"""
from __future__ import annotations


def format_full(n) -> str:
    value = float(n or 0)
    sign = "-" if value < 0 else ""
    grouped = f"{abs(round(value)):,}".replace(",", ".")
    return f"{sign}Rp {grouped}"


def format_short(n) -> str:
    value = float(n or 0)
    sign = "-" if value < 0 else ""
    abs_value = abs(value)
    if abs_value >= 1_000_000_000:
        num = abs_value / 1_000_000_000
        text = f"{num:.2f}".rstrip("0").rstrip(".").replace(".", ",")
        return f"{sign}Rp{text} M"
    if abs_value >= 1_000_000:
        return f"{sign}Rp{round(abs_value / 1_000_000)} jt"
    if abs_value >= 1_000:
        return f"{sign}Rp{round(abs_value / 1_000)} rb"
    return format_full(value)


def format_percent(n, decimals: int = 1) -> str:
    try:
        value = float(n)
    except (TypeError, ValueError):
        return "-"
    return f"{value:.{decimals}f}".replace(".", ",") + "%"


def format_date_id(d) -> str:
    if d is None:
        return "-"
    months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    return f"{d.day} {months[d.month - 1]} {d.year}"
