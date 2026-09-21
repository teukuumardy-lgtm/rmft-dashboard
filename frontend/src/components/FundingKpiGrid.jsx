import { formatShort, formatPercent, deltaArrow } from "../utils/format";

const ROWS = [
  { key: "tabungan", label: "Tabungan" },
  { key: "giro", label: "Giro" },
  { key: "deposito", label: "Deposito" },
  { key: "dpk", label: "Total DPK" },
  { key: "casa", label: "CASA" },
];

function DeltaPill({ value, mode }) {
  const cls = value > 0 ? "pos" : value < 0 ? "neg" : "neutral";
  return (
    <span className={`pill ${cls}`}>
      {deltaArrow(value)} {mode} {formatShort(Math.abs(value))}
    </span>
  );
}

export default function FundingKpiGrid({ current, mtd, dtd }) {
  if (!current) return null;
  return (
    <div className="kpi-grid">
      {ROWS.map((row) => (
        <div className="kpi-card" key={row.key}>
          <div className="label">{row.label}</div>
          <div className="value">{formatShort(current[row.key])}</div>
          <div className="delta-row">
            <DeltaPill value={mtd?.[row.key] ?? 0} mode="MTD" />
            <DeltaPill value={dtd?.[row.key] ?? 0} mode="DTD" />
          </div>
        </div>
      ))}
    </div>
  );
}
