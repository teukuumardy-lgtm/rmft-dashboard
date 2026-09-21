import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { formatDate, formatPercent, formatShort } from "../utils/format";
import ExportButtons from "../components/ExportButtons";
import FundingTrendChart from "../components/charts/FundingTrendChart";
import PipelineVsRealisasiChart from "../components/charts/PipelineVsRealisasiChart";

function currentMonth() {
  return new Date().toISOString().slice(0, 7);
}

export default function MonthlyReport() {
  const { isAdmin, profile } = useAuth();
  const [month, setMonth] = useState(currentMonth());
  const [rmftOptions, setRmftOptions] = useState([]);
  const [selectedPn, setSelectedPn] = useState("");
  const [summary, setSummary] = useState(null);
  const [trend, setTrend] = useState([]);
  const [fundingTrend, setFundingTrend] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (isAdmin) api.listRmft().then(setRmftOptions).catch(() => {});
  }, [isAdmin]);

  const scopedPn = isAdmin ? (selectedPn || undefined) : profile.pn;

  useEffect(() => {
    Promise.all([
      api.monthlySummary(month, scopedPn),
      api.conversionTrend(month, scopedPn),
      api.fundingTrend(30, scopedPn),
    ])
      .then(([s, t, ft]) => { setSummary(s); setTrend(t); setFundingTrend(ft); })
      .catch((err) => setError(err.message));
    // eslint-disable-next-line
  }, [month, scopedPn]);

  return (
    <div>
      <div className="section-title">Monthly Pipeline History</div>
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
        <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} style={{ maxWidth: 160 }} />
        {isAdmin && (
          <select value={selectedPn} onChange={(e) => setSelectedPn(e.target.value)} style={{ maxWidth: 220 }}>
            <option value="">Seluruh Unit</option>
            {rmftOptions.map((r) => <option key={r.pn} value={r.pn}>{r.rmft_name}</option>)}
          </select>
        )}
        <ExportButtons report="monthly_performance" params={{ month, pn: scopedPn }} />
      </div>

      {error && <div className="error-text">{error}</div>}

      {summary && (
        <>
          <div className="kpi-grid">
            <div className="kpi-card"><div className="label">Total Pipeline</div><div className="value">{formatShort(summary.pipeline_nominal)}</div></div>
            <div className="kpi-card"><div className="label">Realisasi</div><div className="value">{formatShort(summary.realisasi_nominal)}</div></div>
            <div className="kpi-card"><div className="label">Outstanding</div><div className="value">{formatShort(summary.outstanding)}</div></div>
            <div className="kpi-card"><div className="label">Batal</div><div className="value">{summary.batal_count}</div></div>
            <div className="kpi-card"><div className="label">Nominal SR</div><div className="value">{formatPercent(summary.nominal_sr)}</div></div>
            <div className="kpi-card"><div className="label">Activity SR</div><div className="value">{formatPercent(summary.activity_sr)}</div></div>
          </div>

          <div className="card" style={{ marginTop: 16 }}>
            <div style={{ marginBottom: 8 }}><b>🏆 RMFT Terbaik:</b> {summary.rmft_terbaik || "-"}</div>
            <div style={{ marginBottom: 8 }}>
              <b>Customer Terbesar:</b> {summary.customer_terbesar ? `${summary.customer_terbesar.customer} (${formatShort(summary.customer_terbesar.nominal)})` : "-"}
            </div>
            <div>
              <b>Produk Terbesar:</b> {summary.produk_terbesar ? `${summary.produk_terbesar.product} (${formatShort(summary.produk_terbesar.realisasi)})` : "-"}
            </div>
          </div>
        </>
      )}

      <div className="section-title">Funding Trend (30 Hari Terakhir)</div>
      <FundingTrendChart data={fundingTrend} />

      <div className="section-title">Pipeline vs Realisasi — Tren Harian</div>
      <PipelineVsRealisasiChart data={trend} />

      <div className="section-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span>Pipeline Conversion — Tren Harian</span>
        <ExportButtons report="pipeline_conversion" params={{ month, pn: scopedPn }} />
      </div>
      <div className="list-card table-scroll">
        <table>
          <thead>
            <tr><th>Tanggal</th><th>Pipeline</th><th>Realisasi</th><th>Nominal SR</th><th>Activity SR</th></tr>
          </thead>
          <tbody>
            {trend.map((t) => (
              <tr key={t.date}>
                <td>{formatDate(t.date)}</td>
                <td>{formatShort(t.pipeline_nominal)}</td>
                <td>{formatShort(t.realisasi_nominal)}</td>
                <td>{formatPercent(t.nominal_sr)}</td>
                <td>{formatPercent(t.activity_sr)}</td>
              </tr>
            ))}
            {trend.length === 0 && (
              <tr><td colSpan={5} style={{ color: "var(--text-muted)" }}>Belum ada aktivitas pipeline pada bulan ini.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
