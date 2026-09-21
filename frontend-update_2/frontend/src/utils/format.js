// Section 58: Indonesian number/currency formatting. Never USD.

export function formatFull(n) {
  const value = Number(n) || 0;
  const sign = value < 0 ? "-" : "";
  const abs = Math.round(Math.abs(value));
  return `${sign}Rp ${abs.toLocaleString("id-ID")}`;
}

export function formatShort(n) {
  const value = Number(n) || 0;
  const sign = value < 0 ? "-" : "";
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) {
    return `${sign}Rp${(abs / 1_000_000_000).toFixed(2).replace(".", ",").replace(/,00$/, "")} M`;
  }
  if (abs >= 1_000_000) {
    return `${sign}Rp${Math.round(abs / 1_000_000)} jt`;
  }
  if (abs >= 1_000) {
    return `${sign}Rp${Math.round(abs / 1_000)} rb`;
  }
  return formatFull(value);
}

export function formatPercent(n, decimals = 1) {
  const value = Number(n);
  if (!isFinite(value)) return "-";
  return `${value.toFixed(decimals).replace(".", ",")}%`;
}

export function formatDate(d) {
  if (!d) return "-";
  const date = typeof d === "string" ? new Date(d) : d;
  if (isNaN(date.getTime())) return "-";
  const months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
  return `${date.getDate()} ${months[date.getMonth()]} ${date.getFullYear()}`;
}

export function deltaArrow(n) {
  const value = Number(n) || 0;
  if (value > 0) return "▲";
  if (value < 0) return "▼";
  return "—";
}
