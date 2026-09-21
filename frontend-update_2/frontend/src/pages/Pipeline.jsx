import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import ExportButtons from "../components/ExportButtons";
import { formatDate, formatShort } from "../utils/format";

const STATUSES = ["Prospect", "Follow Up", "Negotiation", "Commit", "Realisasi", "Pending", "Carry Over", "Batal"];
const PRODUCTS = ["Tabungan", "Giro", "Deposito", "Payroll", "EDC", "QRIS", "BRILife", "Bancassurance", "FBI Lainnya"];

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

const emptyForm = {
  pipeline_date: todayStr(),
  customer: "",
  cif: "",
  product: "Tabungan",
  nominal: "",
  probability: 50,
  target_date: todayStr(),
  activity_today: "",
  next_action: "",
  notes: "",
};

export default function Pipeline() {
  const { profile, isAdmin } = useAuth();
  const [date, setDate] = useState(todayStr());
  const [rows, setRows] = useState([]);
  const [rmftOptions, setRmftOptions] = useState([]);
  const [selectedPn, setSelectedPn] = useState(profile?.pn || "");
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showForm, setShowForm] = useState(false);

  async function load() {
    try {
      const data = await api.listPipeline({ date });
      setRows(data);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [date]);

  useEffect(() => {
    if (isAdmin) {
      api.listRmft().then((list) => {
        setRmftOptions(list);
        if (!selectedPn && list.length) setSelectedPn(list[0].pn);
      }).catch(() => {});
    }
    // eslint-disable-next-line
  }, [isAdmin]);

  const activePn = isAdmin ? selectedPn : profile.pn;

  async function handleCreate(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.createPipeline({
        ...form,
        pn: activePn,
        nominal: Number(form.nominal) || 0,
        probability: Number(form.probability) || 0,
      });
      setForm(emptyForm);
      setShowForm(false);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleCopyYesterday() {
    setBusy(true);
    setError("");
    try {
      const result = await api.copyPipelineKemarin(date, isAdmin ? activePn : undefined);
      await load();
      if (result.copied === 0) alert("Tidak ada pipeline belum selesai dari hari sebelumnya untuk disalin.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="section-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span>Pipeline Harian</span>
        <ExportButtons report="pipeline" params={{ date_from: date, date_to: date, pn: isAdmin ? activePn : undefined }} />
      </div>
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} style={{ maxWidth: 180 }} />
        <button className="btn btn-secondary" onClick={handleCopyYesterday} disabled={busy}>Copy Pipeline Kemarin</button>
        <button className="btn btn-primary" onClick={() => setShowForm((s) => !s)}>+ Pipeline</button>
      </div>

      {error && <div className="error-text">{error}</div>}

      {isAdmin && rmftOptions.length > 0 && (
        <div className="field" style={{ maxWidth: 280 }}>
          <label>RMFT</label>
          <select value={selectedPn} onChange={(e) => setSelectedPn(e.target.value)}>
            {rmftOptions.map((r) => <option key={r.pn} value={r.pn}>{r.rmft_name}</option>)}
          </select>
        </div>
      )}

      {showForm && (
        <form className="card" onSubmit={handleCreate} style={{ marginBottom: 16 }}>
          <div className="field">
            <label>Customer</label>
            <input type="text" required value={form.customer} onChange={(e) => setForm({ ...form, customer: e.target.value })} />
          </div>
          <div className="field">
            <label>CIF (opsional)</label>
            <input type="text" value={form.cif} onChange={(e) => setForm({ ...form, cif: e.target.value })} />
          </div>
          <div className="field">
            <label>Produk</label>
            <select value={form.product} onChange={(e) => setForm({ ...form, product: e.target.value })}>
              {PRODUCTS.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Nominal (Rp)</label>
            <input type="text" required value={form.nominal} onChange={(e) => setForm({ ...form, nominal: e.target.value })} placeholder="500000000" />
          </div>
          <div className="field">
            <label>Probability (%)</label>
            <input type="text" value={form.probability} onChange={(e) => setForm({ ...form, probability: e.target.value })} />
          </div>
          <div className="field">
            <label>Target Closing</label>
            <input type="date" value={form.target_date} onChange={(e) => setForm({ ...form, target_date: e.target.value })} />
          </div>
          <div className="field">
            <label>Aktivitas Hari Ini</label>
            <input type="text" value={form.activity_today} onChange={(e) => setForm({ ...form, activity_today: e.target.value })} />
          </div>
          <div className="field">
            <label>Next Action</label>
            <input type="text" value={form.next_action} onChange={(e) => setForm({ ...form, next_action: e.target.value })} />
          </div>
          <button className="btn btn-primary btn-block" disabled={busy}>{busy ? "Menyimpan…" : "Simpan Pipeline"}</button>
        </form>
      )}

      <div className="list-card table-scroll">
        <table>
          <thead>
            <tr>
              <th>Customer</th><th>RMFT</th><th>Produk</th><th>Nominal</th><th>Prob.</th><th>Target</th><th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.pipeline_id}>
                <td>{r.customer}</td>
                <td>{r.rmft}</td>
                <td>{r.product}</td>
                <td>{formatShort(r.nominal)}</td>
                <td>{r.probability}%</td>
                <td>{formatDate(r.target_date)}</td>
                <td><span className="pill neutral">{r.status}</span></td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={7} style={{ color: "var(--text-muted)" }}>Belum ada pipeline pada tanggal ini.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <PotentialMatches pn={isAdmin ? undefined : profile.pn} onConfirmed={load} />
    </div>
  );
}

function PotentialMatches({ pn, onConfirmed }) {
  const [matches, setMatches] = useState([]);
  const [dismissed, setDismissed] = useState(new Set());
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState("");

  async function load() {
    try {
      const rows = await api.potentialMatches(pn);
      setMatches(rows);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [pn]);

  async function confirm(m) {
    setBusyId(m.pipeline_id);
    setError("");
    try {
      await api.confirmMatch(m.pipeline_id, m.actual_inflow);
      await load();
      onConfirmed?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  async function reject(m) {
    setDismissed((prev) => new Set(prev).add(m.pipeline_id));
    try {
      await api.dismissMatch(m.pipeline_id, m.actual_account_number);
    } catch (err) {
      setError(err.message);
    }
  }

  const visible = matches.filter((m) => !dismissed.has(m.pipeline_id));
  if (visible.length === 0) return null;

  return (
    <>
      <div className="section-title">🎯 Potential Pipeline Match</div>
      <p style={{ marginTop: -6, fontSize: 13, color: "var(--text-muted)" }}>
        Pipeline funding yang polanya cocok dengan penambahan saldo aktual hari ini. Tinjau sebelum dikonfirmasi —
        sistem tidak pernah otomatis mengubah pipeline menjadi realisasi.
      </p>
      {error && <div className="error-text">{error}</div>}
      <div className="list-card">
        {visible.map((m) => (
          <div className="list-row" key={m.pipeline_id} style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <div>
                <div className="name">{m.pipeline_customer}</div>
                <div className="meta">
                  {m.product} · {m.rmft} · Pipeline {formatShort(m.pipeline_nominal)} → Actual inflow {formatShort(m.actual_inflow)}
                </div>
              </div>
              <div className="pill pos">{Math.round(m.confidence)}%</div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn btn-primary" onClick={() => confirm(m)} disabled={busyId === m.pipeline_id}>
                {busyId === m.pipeline_id ? "…" : "Confirm as Realization"}
              </button>
              <button className="btn btn-secondary" onClick={() => reject(m)} disabled={busyId === m.pipeline_id}>Reject</button>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
