import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import ExportButtons from "../components/ExportButtons";
import SuccessRateBarChart from "../components/charts/SuccessRateBarChart";
import { formatPercent, formatShort } from "../utils/format";

const SCOPES = [
  { key: "daily", label: "Daily" },
  { key: "mtd", label: "MTD" },
  { key: "ytd", label: "YTD" },
];

function scopeDateRange(scope) {
  const today = new Date();
  const iso = (d) => d.toISOString().slice(0, 10);
  if (scope === "daily") return { date_from: iso(today), date_to: iso(today) };
  if (scope === "ytd") return { date_from: `${today.getFullYear()}-01-01`, date_to: iso(today) };
  return { date_from: iso(new Date(today.getFullYear(), today.getMonth(), 1)), date_to: iso(today) };
}

export default function RmftPerformance() {
  const [scope, setScope] = useState("mtd");
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api.leaderboard(scope).then(setRows).catch((err) => setError(err.message));
  }, [scope]);

  return (
    <div>
      <div className="section-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span>RMFT Leaderboard</span>
        <ExportButtons report="rmft_performance" params={scopeDateRange(scope)} />
      </div>
      <p style={{ marginTop: -6, fontSize: 13, color: "var(--text-muted)" }}>
        Diranking berdasarkan Success Rate (conversion), bukan sekadar besar pipeline.
      </p>

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        {SCOPES.map((s) => (
          <button
            key={s.key}
            className={`btn ${scope === s.key ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setScope(s.key)}
          >
            {s.label}
          </button>
        ))}
      </div>

      {error && <div className="error-text">{error}</div>}

      <div className="section-title">Success Rate Nominal per RMFT</div>
      <SuccessRateBarChart rows={rows} />

      <div className="section-title">Detail</div>
      <div className="list-card table-scroll">
        <table>
          <thead>
            <tr>
              <th></th><th>RMFT</th><th>Pipeline</th><th>Realisasi</th><th>Outstanding</th><th>Nominal SR</th><th>Activity SR</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.pn}>
                <td style={{ fontSize: 16 }}>{r.medal || r.rank}</td>
                <td><Link to={`/funding/${r.pn}`}>{r.rmft_name}</Link></td>
                <td>{formatShort(r.pipeline_nominal)}</td>
                <td>{formatShort(r.realisasi_nominal)}</td>
                <td>{formatShort(r.outstanding)}</td>
                <td>{r.nominal_indicator} {formatPercent(r.nominal_sr)}</td>
                <td>{r.activity_indicator} {formatPercent(r.activity_sr)}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={7} style={{ color: "var(--text-muted)" }}>Belum ada data pipeline pada periode ini.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
