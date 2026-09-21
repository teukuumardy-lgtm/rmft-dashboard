import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { formatDate, formatShort } from "../utils/format";

export default function DailyAction() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.dailyAction().then(setData).catch((err) => setError(err.message));
  }, []);

  if (error) return <div className="error-text">{error}</div>;
  if (!data) return <div className="spinner-inline">Memuat…</div>;

  const sections = [
    {
      key: "priority_1_fund_outflow", title: "🚨 Priority 1 — Fund Outflow",
      empty: "Tidak ada outflow signifikan.",
      render: (m) => (
        <div className="list-row" key={m.account_number}>
          <div>
            <div className="name">{m.customer || m.account_number}</div>
            <div className="meta">{m.rmft_name || "-"} · {m.product}</div>
          </div>
          <div className="pill neg">{formatShort(m.delta)}</div>
        </div>
      ),
    },
    {
      key: "priority_2_closing_today", title: "🎯 Priority 2 — Closing Hari Ini",
      empty: "Tidak ada pipeline target closing hari ini.",
      render: (p) => (
        <div className="list-row" key={p.pipeline_id}>
          <div><div className="name">{p.customer}</div><div className="meta">{p.product} · {p.rmft}</div></div>
          <div className="pill neutral">{formatShort(p.nominal)}</div>
        </div>
      ),
    },
    {
      key: "priority_3_overdue", title: "⏰ Priority 3 — Overdue",
      empty: "Tidak ada pipeline yang lewat target closing.",
      render: (p) => (
        <div className="list-row" key={p.pipeline_id}>
          <div><div className="name">{p.customer}</div><div className="meta">{p.product} · {p.rmft} · Target {formatDate(p.target_date)}</div></div>
          <div className="pill warn">{formatShort(p.nominal)}</div>
        </div>
      ),
    },
    {
      key: "priority_4_high_probability", title: "⭐ Priority 4 — High Probability (≥80%)",
      empty: "Tidak ada pipeline probability tinggi.",
      render: (p) => (
        <div className="list-row" key={p.pipeline_id}>
          <div><div className="name">{p.customer}</div><div className="meta">{p.product} · {p.rmft}</div></div>
          <div className="pill pos">{p.probability}%</div>
        </div>
      ),
    },
    {
      key: "priority_5_follow_up", title: "📞 Priority 5 — Follow Up Outflow",
      empty: "Tidak ada follow up outflow yang menunggu.",
      render: (f) => (
        <div className="list-row" key={f.followup_id}>
          <div><div className="name">{f.cif || f.account_number}</div><div className="meta">{formatDate(f.date)}</div></div>
          <div className="pill warn">{formatShort(f.outflow_amount)}</div>
        </div>
      ),
    },
  ];

  return (
    <div>
      <div className="section-title">Today's Action</div>
      {sections.map((s) => (
        <div key={s.key}>
          <div className="section-title">{s.title}</div>
          <div className="list-card">
            {(data[s.key] || []).length === 0
              ? <div className="list-row"><span className="meta">{s.empty}</span></div>
              : data[s.key].map(s.render)}
          </div>
        </div>
      ))}
    </div>
  );
}
