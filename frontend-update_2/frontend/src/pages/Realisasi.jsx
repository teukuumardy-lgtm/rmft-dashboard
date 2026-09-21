import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { formatShort } from "../utils/format";

const STATUS_ICON = { "Realisasi": "✅", "Carry Over": "🔄", "Pending": "⏳", "Batal": "❌" };

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

function RealizationRow({ pipeline, onSaved }) {
  const [amount, setAmount] = useState(String(pipeline.nominal || ""));
  const [status, setStatus] = useState("Realisasi");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    setBusy(true);
    setError("");
    try {
      await api.createRealization({
        pipeline_id: pipeline.pipeline_id,
        date: todayStr(),
        realization_amount: Number(amount) || 0,
        status,
        notes,
      });
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="list-row" style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <div>
          <div className="name">{pipeline.customer}</div>
          <div className="meta">{pipeline.product} · Pipeline {formatShort(pipeline.nominal)} · {pipeline.rmft}</div>
        </div>
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <input type="text" style={{ maxWidth: 160 }} value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="Realisasi (Rp)" />
        <select style={{ maxWidth: 160 }} value={status} onChange={(e) => setStatus(e.target.value)}>
          {Object.keys(STATUS_ICON).map((s) => <option key={s} value={s}>{STATUS_ICON[s]} {s}</option>)}
        </select>
        <input type="text" style={{ flex: 1, minWidth: 140 }} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Keterangan" />
        <button className="btn btn-primary" onClick={submit} disabled={busy}>{busy ? "…" : "Simpan"}</button>
      </div>
      {error && <div className="error-text" style={{ margin: 0 }}>{error}</div>}
    </div>
  );
}

export default function Realisasi() {
  const { isAdmin } = useAuth();
  const [rows, setRows] = useState([]);
  const [done, setDone] = useState([]);
  const [error, setError] = useState("");

  async function load() {
    try {
      const all = await api.listPipeline({ date: todayStr() });
      setRows(all.filter((p) => !["Realisasi", "Batal"].includes(p.status)));
      setDone(all.filter((p) => ["Realisasi", "Batal"].includes(p.status)));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <div>
      <div className="section-title">Realisasi Sore — Hari Ini</div>
      <p style={{ marginTop: -6, fontSize: 13, color: "var(--text-muted)" }}>
        Isi realisasi untuk pipeline hari ini. Status realisasi akan otomatis memperbarui status pipeline terkait.
      </p>
      {error && <div className="error-text">{error}</div>}

      <div className="list-card">
        {rows.length === 0 && <div className="list-row"><span className="meta">Semua pipeline hari ini sudah diisi realisasinya.</span></div>}
        {rows.map((p) => <RealizationRow key={p.pipeline_id} pipeline={p} onSaved={load} />)}
      </div>

      {done.length > 0 && (
        <>
          <div className="section-title">Sudah Diisi</div>
          <div className="list-card">
            {done.map((p) => (
              <div className="list-row" key={p.pipeline_id}>
                <div>
                  <div className="name">{p.customer}</div>
                  <div className="meta">{p.product} · {p.rmft}</div>
                </div>
                <div className={`pill ${p.status === "Realisasi" ? "pos" : "neg"}`}>
                  {STATUS_ICON[p.status] || ""} {p.status}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
