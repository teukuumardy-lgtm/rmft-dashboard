import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import DataPositionBanner from "../components/DataPositionBanner";
import FundingKpiGrid from "../components/FundingKpiGrid";
import DpkCompositionChart from "../components/charts/DpkCompositionChart";
import InflowOutflowChart from "../components/charts/InflowOutflowChart";
import { useAuth } from "../context/AuthContext";
import { formatPercent, formatShort } from "../utils/format";

export default function Home() {
  const { isAdmin, profile } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [outflow, setOutflow] = useState([]);
  const [sr, setSr] = useState(null);
  const [top, setTop] = useState(null);
  const [flows, setFlows] = useState(null);
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  function handleQuickSearch(e) {
    e.preventDefault();
    if (q.trim().length < 2) return;
    navigate(`/customer?q=${encodeURIComponent(q.trim())}`);
  }

  useEffect(() => {
    const scopedPn = profile?.role === "RMFT" ? profile.pn : undefined;
    Promise.all([
      api.home(),
      api.topMovers("DTD", "outflow", null, 5),
      api.successRate("daily", scopedPn),
      profile?.role === "ADMIN" ? api.leaderboard("daily") : Promise.resolve([]),
      api.flowTotals("MTD", scopedPn),
    ])
      .then(([home, movers, srData, leaderboard, flowData]) => {
        setData(home);
        setOutflow(movers);
        setSr(srData);
        setTop(leaderboard[0] || null);
        setFlows(flowData);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="spinner-inline">Memuat data posisi hari ini…</div>;
  if (error) return <div className="error-text">{error}</div>;

  const noData = data?.freshness?.status === "NO_DATA";

  return (
    <div>
      <form onSubmit={handleQuickSearch} style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input
          type="text"
          placeholder="🔍 Cari Nasabah / CIF / Rekening"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </form>

      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        <Link className="btn btn-secondary" to="/pipeline">+ Pipeline</Link>
        <Link className="btn btn-secondary" to="/realisasi">+ Realisasi</Link>
        {isAdmin && <Link className="btn btn-secondary" to="/upload">📤 Upload Data</Link>}
        <Link className="btn btn-secondary" to="/wa-report">📋 Copy WA Pagi</Link>
        <Link className="btn btn-secondary" to="/wa-report">📋 Copy WA Sore</Link>
      </div>

      <DataPositionBanner freshness={data.freshness} />

      {noData ? (
        <div className="empty-state card">
          <div className="big">📭</div>
          <p>
            Belum ada data posisi hari ini. {isAdmin ? (
              <>
                <Link to="/upload">Upload DI319, DI321 dan CI324</Link> untuk memulai.
              </>
            ) : (
              "Hubungi Admin/SBOH untuk upload data posisi harian."
            )}
          </p>
        </div>
      ) : (
        <>
          <div className="section-title">Posisi Funding — {data.rmft_cards.length > 1 ? "Unit" : "Anda"}</div>
          <FundingKpiGrid current={data.unit_current} mtd={data.unit_mtd} dtd={data.unit_dtd} />

          <div style={{ display: "grid", gap: 12, gridTemplateColumns: "1fr", marginTop: 12 }}>
            <div>
              <div className="section-title" style={{ margin: "0 0 8px" }}>Komposisi DPK</div>
              <DpkCompositionChart current={data.unit_current} />
            </div>
            <div>
              <div className="section-title" style={{ margin: "0 0 8px" }}>Inflow vs Outflow (MTD)</div>
              <InflowOutflowChart inflow={flows?.inflow} outflow={flows?.outflow} mode="MTD" />
            </div>
          </div>

          <div className="section-title">RMFT</div>
          <div className="list-card">
            {data.rmft_cards.length === 0 && (
              <div className="list-row"><span className="meta">Belum ada data kelolaan RMFT.</span></div>
            )}
            {data.rmft_cards.map((c) => (
              <Link className="list-row" to={`/funding/${c.pn}`} key={c.pn}>
                <div>
                  <div className="name">{c.rmft_name}</div>
                  <div className="meta">{c.account_count} rekening · DPK {formatShort(c.current.dpk)}</div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div className={`pill ${c.mtd.dpk >= 0 ? "pos" : "neg"}`}>
                    MTD {formatShort(Math.abs(c.mtd.dpk))}
                  </div>
                </div>
              </Link>
            ))}
          </div>

          {outflow.length > 0 && (
            <>
              <div className="section-title">🚨 Alert — Penurunan Saldo Terbesar (DTD)</div>
              <div className="list-card">
                {outflow.map((m) => (
                  <div className="list-row" key={m.account_number}>
                    <div>
                      <div className="name">{m.customer || m.account_number}</div>
                      <div className="meta">
                        {m.rmft_name || "Belum termapping"} · {m.status === "ACCOUNT_MISSING" ? "Rekening hilang dari laporan" : m.product}
                      </div>
                    </div>
                    <div className="pill neg">{formatShort(m.delta)}</div>
                  </div>
                ))}
              </div>
            </>
          )}

          <div className="section-title">Pipeline & Success Rate — Hari Ini</div>
          <div className="kpi-grid">
            <div className="kpi-card">
              <div className="label">Pipeline</div>
              <div className="value">{formatShort(sr?.pipeline_nominal)}</div>
            </div>
            <div className="kpi-card">
              <div className="label">Realisasi</div>
              <div className="value">{formatShort(sr?.realisasi_nominal)}</div>
            </div>
            <div className="kpi-card">
              <div className="label">Nominal SR</div>
              <div className="value">{sr?.nominal_indicator} {formatPercent(sr?.nominal_sr)}</div>
            </div>
            <div className="kpi-card">
              <div className="label">Activity SR</div>
              <div className="value">{sr?.activity_indicator} {formatPercent(sr?.activity_sr)}</div>
            </div>
            {top && (
              <div className="kpi-card">
                <div className="label">🏆 RMFT Terbaik</div>
                <div className="value" style={{ fontSize: 15 }}>{top.rmft_name}</div>
              </div>
            )}
          </div>
          <div style={{ display: "flex", gap: 12, marginTop: 12 }}>
            <Link className="btn btn-secondary" to="/daily-action">⚡ Lihat Daily Action</Link>
            <Link className="btn btn-secondary" to="/pipeline">+ Pipeline</Link>
          </div>
        </>
      )}
    </div>
  );
}
