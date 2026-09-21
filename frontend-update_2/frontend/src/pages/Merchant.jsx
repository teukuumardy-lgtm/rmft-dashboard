import { useEffect, useState } from "react";
import { api } from "../api/client";
import { formatDate, formatShort } from "../utils/format";

const CHANNELS = [
  { key: "EDC", label: "EDC" },
  { key: "QRIS", label: "QRIS" },
];

const STATUS_LABEL = {
  PRODUKTIF: "Produktif",
  BELUM_PRODUKTIF: "Belum Produktif",
  TIDAK_ADA_TRANSAKSI: "Belum Ada Transaksi",
};

const STATUS_PILL = {
  PRODUKTIF: "pos",
  BELUM_PRODUKTIF: "warn",
  TIDAK_ADA_TRANSAKSI: "neg",
};

export default function Merchant() {
  const [channel, setChannel] = useState("EDC");
  const [summary, setSummary] = useState(null);
  const [rows, setRows] = useState([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [unassignedOnly, setUnassignedOnly] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function load() {
    setLoading(true);
    setError("");
    Promise.all([
      api.merchantSummary(channel),
      api.merchantList({ channel, status: statusFilter || undefined, unassigned_only: unassignedOnly || undefined }),
    ])
      .then(([s, l]) => {
        setSummary(s.find((x) => x.channel === channel) || null);
        setRows(l);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(load, [channel, statusFilter, unassignedOnly]);

  return (
    <div>
      <div className="section-title">Produktivitas EDC / QRIS</div>
      <p style={{ marginTop: -6, fontSize: 13, color: "var(--text-muted)" }}>
        Terminal EDC/QRIS yang belum produktif atau belum pernah bertransaksi sama sekali, berdasarkan
        threshold aktif ({channel === "EDC" ? "≥ Rp15jt/EDC" : "≥ Rp50rb/QRIS"} secara default — dapat diubah admin).
        Kepemilikan PN dicocokkan otomatis lewat nomor rekening merchant, bukan nama RM di file.
      </p>

      <div className="tabs">
        {CHANNELS.map((c) => (
          <button
            key={c.key}
            className={`tab-btn ${channel === c.key ? "active" : ""}`}
            onClick={() => setChannel(c.key)}
          >
            {c.label}
          </button>
        ))}
      </div>

      {error && <div className="error-text">{error}</div>}

      {summary ? (
        <>
          <div className="meta" style={{ marginBottom: 8 }}>Data per {formatDate(summary.snapshot_date)}</div>
          <div className="kpi-grid">
            <div className="kpi-card"><div className="label">Total Terminal</div><div className="value">{summary.total_terminal}</div></div>
            <div className="kpi-card"><div className="label">Produktif</div><div className="value" style={{ color: "var(--green)" }}>{summary.produktif}</div></div>
            <div className="kpi-card"><div className="label">Belum Produktif</div><div className="value" style={{ color: "var(--orange, #c77700)" }}>{summary.belum_produktif}</div></div>
            <div className="kpi-card"><div className="label">Belum Ada Transaksi</div><div className="value" style={{ color: "var(--red)" }}>{summary.tidak_ada_transaksi}</div></div>
            <div className="kpi-card"><div className="label">Total Pending</div><div className="value">{summary.pending}</div></div>
            <div className="kpi-card"><div className="label">Belum Teridentifikasi PN</div><div className="value">{summary.unassigned}</div></div>
            <div className="kpi-card"><div className="label">Total Volume</div><div className="value">{formatShort(summary.total_volume)}</div></div>
          </div>
        </>
      ) : (
        !loading && <div className="empty-state card">Belum ada data {channel} yang diupload.</div>
      )}

      <div className="section-title" style={{ marginTop: 24, display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
        <span>Daftar Terminal</span>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">Semua Status</option>
            <option value="PRODUKTIF">Produktif</option>
            <option value="BELUM_PRODUKTIF">Belum Produktif</option>
            <option value="TIDAK_ADA_TRANSAKSI">Belum Ada Transaksi</option>
          </select>
          <label style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 13 }}>
            <input type="checkbox" checked={unassignedOnly} onChange={(e) => setUnassignedOnly(e.target.checked)} />
            Belum teridentifikasi PN saja
          </label>
        </div>
      </div>

      <div className="list-card table-scroll">
        <table>
          <thead>
            <tr>
              <th>Terminal</th><th>Merchant</th><th>Uker</th><th>No. Rekening</th>
              <th>Volume</th><th>RMFT</th><th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={`${r.channel}-${r.terminal_id}`}>
                <td>{r.terminal_id}</td>
                <td>{r.merchant_name || "-"}</td>
                <td>{r.uker_name || "-"}</td>
                <td>{r.account_number || "-"}</td>
                <td>{formatShort(r.sales_volume)}</td>
                <td>{r.ownership_matched ? `${r.rmft_name} (${r.pn})` : <span className="pill warn">Belum teridentifikasi</span>}</td>
                <td><span className={`pill ${STATUS_PILL[r.productivity_status]}`}>{STATUS_LABEL[r.productivity_status]}</span></td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={7} className="meta">Tidak ada data untuk filter ini.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
