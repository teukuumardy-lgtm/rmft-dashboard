import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import FundingKpiGrid from "../components/FundingKpiGrid";
import { formatDate, formatPercent, formatShort } from "../utils/format";

export default function Customer360() {
  const [params] = useSearchParams();
  const cif = params.get("cif");
  const account_number = params.get("account_number");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setData(null);
    setError("");
    api.customer360({ cif, account_number }).then(setData).catch((err) => setError(err.message));
  }, [cif, account_number]);

  if (error) return <div className="error-text">{error}</div>;
  if (!data) return <div className="spinner-inline">Memuat…</div>;

  return (
    <div>
      <div className="section-title">Customer 360</div>
      <h2 style={{ margin: "0 0 4px" }}>{data.customer_name || "-"}</h2>
      <p style={{ marginTop: 0, color: "var(--text-muted)", fontSize: 13 }}>
        {data.cif ? `CIF ${data.cif}` : `Rekening ${data.account_number}`}
      </p>

      <div className="section-title">Funding</div>
      <FundingKpiGrid current={data.funding.current} mtd={data.funding.mtd} dtd={data.funding.dtd} />

      <div className="section-title">Movement</div>
      <div className="card" style={{ fontSize: 13 }}>
        <table>
          <tbody>
            <tr><td>Baseline</td><td>{formatShort(data.movement.baseline.dpk)}</td></tr>
            <tr><td>Previous Snapshot</td><td>{formatShort(data.movement.previous.dpk)}</td></tr>
            <tr><td>Today ({formatDate(data.movement.as_of)})</td><td>{formatShort(data.movement.today.dpk)}</td></tr>
            <tr><td>MTD</td><td>{formatShort(data.movement.mtd.dpk)}</td></tr>
            <tr><td>DTD</td><td>{formatShort(data.movement.dtd.dpk)}</td></tr>
          </tbody>
        </table>
      </div>

      <div className="section-title">RMFT</div>
      <div className="card" style={{ fontSize: 13 }}>
        <div><b>Primary RMFT:</b> {data.rmft.rmft_name || "Belum termapping"}</div>
        <div><b>PN:</b> {data.rmft.primary_pn || "-"}</div>
        <div><b>Ownership Source:</b> {data.rmft.ownership_source || "-"}</div>
      </div>

      <div className="section-title">Pipeline</div>
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="label">Pipeline Aktif</div>
          <div className="value">{data.pipeline.active_count}</div>
        </div>
        <div className="kpi-card">
          <div className="label">Pipeline Nominal</div>
          <div className="value">{formatShort(data.pipeline.pipeline_nominal)}</div>
        </div>
        <div className="kpi-card">
          <div className="label">Realisasi</div>
          <div className="value">{formatShort(data.pipeline.realisasi_nominal)}</div>
        </div>
        <div className="kpi-card">
          <div className="label">Outstanding</div>
          <div className="value">{formatShort(data.pipeline.outstanding)}</div>
        </div>
        <div className="kpi-card">
          <div className="label">Success Rate</div>
          <div className="value">{formatPercent(data.pipeline.success_rate)}</div>
        </div>
      </div>
    </div>
  );
}
