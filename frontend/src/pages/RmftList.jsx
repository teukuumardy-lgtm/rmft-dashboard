import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import DataPositionBanner from "../components/DataPositionBanner";
import ExportButtons from "../components/ExportButtons";
import { formatShort } from "../utils/format";

export default function RmftList() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.home().then(setData).catch((err) => setError(err.message));
  }, []);

  if (error) return <div className="error-text">{error}</div>;
  if (!data) return <div className="spinner-inline">Memuat…</div>;

  return (
    <div>
      <DataPositionBanner freshness={data.freshness} />
      <div className="section-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span>Funding per RMFT</span>
        <ExportButtons report="funding" params={{}} />
      </div>
      <div className="list-card">
        {data.rmft_cards.length === 0 && (
          <div className="list-row"><span className="meta">Belum ada data.</span></div>
        )}
        {data.rmft_cards.map((c) => (
          <Link className="list-row" to={`/funding/${c.pn}`} key={c.pn}>
            <div>
              <div className="name">{c.rmft_name}</div>
              <div className="meta">PN {c.pn} · {c.account_count} rekening</div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontWeight: 800 }}>{formatShort(c.current.dpk)}</div>
              <div className={`pill ${c.mtd.dpk >= 0 ? "pos" : "neg"}`}>MTD {formatShort(c.mtd.dpk)}</div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
