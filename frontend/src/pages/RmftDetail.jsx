import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import ExportButtons from "../components/ExportButtons";
import FundingKpiGrid from "../components/FundingKpiGrid";
import { formatPercent, formatShort } from "../utils/format";

export default function RmftDetail() {
  const { pn } = useParams();
  const [data, setData] = useState(null);
  const [outflow, setOutflow] = useState([]);
  const [inflow, setInflow] = useState([]);
  const [srDaily, setSrDaily] = useState(null);
  const [srMtd, setSrMtd] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api.home(),
      api.topMovers("MTD", "outflow", pn, 10),
      api.topMovers("MTD", "inflow", pn, 10),
      api.successRate("daily", pn),
      api.successRate("mtd", pn),
    ])
      .then(([home, out, inf, sd, sm]) => {
        setData(home);
        setOutflow(out);
        setInflow(inf);
        setSrDaily(sd);
        setSrMtd(sm);
      })
      .catch((err) => setError(err.message));
  }, [pn]);

  if (error) return <div className="error-text">{error}</div>;
  if (!data) return <div className="spinner-inline">Memuat…</div>;

  const card = data.rmft_cards.find((c) => c.pn === pn);
  if (!card) return <div className="empty-state card">Data RMFT tidak ditemukan untuk PN ini pada snapshot terkini.</div>;

  return (
    <div>
      <div className="section-title">RMFT Profile</div>
      <h2 style={{ margin: "0 0 4px" }}>{card.rmft_name}</h2>
      <p style={{ marginTop: 0, color: "var(--text-muted)", fontSize: 13 }}>PN {card.pn} · {card.account_count} rekening</p>

      <FundingKpiGrid current={card.current} mtd={card.mtd} dtd={card.dtd} />

      <div className="section-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span>Top Penurunan Saldo (MTD)</span>
        <ExportButtons report="customer_outflow" params={{ mode: "MTD", pn, limit: 10 }} />
      </div>
      <MoverTable rows={outflow} negative />

      <div className="section-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span>Top Kenaikan Saldo (MTD)</span>
        <ExportButtons report="customer_inflow" params={{ mode: "MTD", pn, limit: 10 }} />
      </div>
      <MoverTable rows={inflow} />

      <div className="section-title">Pipeline — Hari Ini</div>
      <div className="kpi-grid">
        <div className="kpi-card"><div className="label">Pipeline</div><div className="value">{formatShort(srDaily?.pipeline_nominal)}</div></div>
        <div className="kpi-card"><div className="label">Realisasi</div><div className="value">{formatShort(srDaily?.realisasi_nominal)}</div></div>
        <div className="kpi-card"><div className="label">Nominal SR</div><div className="value">{srDaily?.nominal_indicator} {formatPercent(srDaily?.nominal_sr)}</div></div>
        <div className="kpi-card"><div className="label">Activity SR</div><div className="value">{srDaily?.activity_indicator} {formatPercent(srDaily?.activity_sr)}</div></div>
      </div>

      <div className="section-title">Pipeline — MTD</div>
      <div className="kpi-grid">
        <div className="kpi-card"><div className="label">Pipeline MTD</div><div className="value">{formatShort(srMtd?.pipeline_nominal)}</div></div>
        <div className="kpi-card"><div className="label">Realisasi MTD</div><div className="value">{formatShort(srMtd?.realisasi_nominal)}</div></div>
        <div className="kpi-card"><div className="label">Outstanding</div><div className="value">{formatShort(srMtd?.outstanding)}</div></div>
        <div className="kpi-card"><div className="label">Nominal SR</div><div className="value">{srMtd?.nominal_indicator} {formatPercent(srMtd?.nominal_sr)}</div></div>
      </div>

      <div className="section-title">Target</div>
      <div className="card">
        <p style={{ margin: 0, color: "var(--text-muted)", fontSize: 13 }}>
          Lihat detail Target vs Achievement RMFT ini di menu <Link to="/target">Target</Link>.
        </p>
      </div>
    </div>
  );
}

function MoverTable({ rows, negative }) {
  if (!rows || rows.length === 0) {
    return <div className="card"><p style={{ margin: 0, fontSize: 13, color: "var(--text-muted)" }}>Tidak ada data.</p></div>;
  }
  return (
    <div className="list-card table-scroll">
      <table>
        <thead>
          <tr>
            <th>#</th><th>Customer</th><th>Account</th><th>Product</th><th>Baseline</th><th>Current</th><th>Delta</th><th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.account_number}>
              <td>{r.rank}</td>
              <td>{r.customer || "-"}</td>
              <td>{r.account_number}</td>
              <td>{r.product}</td>
              <td>{formatShort(r.baseline_or_previous)}</td>
              <td>{formatShort(r.current_balance)}</td>
              <td className={negative ? "pill neg" : "pill pos"} style={{ display: "inline-block" }}>{formatShort(r.delta)}</td>
              <td>{r.status || "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
