import { useEffect, useState } from "react";
import { api } from "../api/client";
import { formatDate, formatFull } from "../utils/format";

const TABS = [
  { key: "users", label: "User" },
  { key: "conflicts", label: "Ownership Conflict" },
  { key: "uploads", label: "Upload History" },
  { key: "audit", label: "Audit Trail" },
];

function UsersTab() {
  const [users, setUsers] = useState([]);
  const [rmftOptions, setRmftOptions] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ username: "", full_name: "", password: "", role: "RMFT", pn: "" });

  function load() {
    api.adminListUsers().then(setUsers).catch((err) => setError(err.message));
    api.listRmft().then(setRmftOptions).catch(() => {});
  }
  useEffect(load, []);

  async function handleCreate(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.adminCreateUser({ ...form, pn: form.role === "RMFT" ? form.pn : null });
      setForm({ username: "", full_name: "", password: "", role: "RMFT", pn: "" });
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(u) {
    try {
      await api.adminUpdateUser(u.id, { active: !u.active });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div>
      {error && <div className="error-text">{error}</div>}

      <div className="section-title">Tambah User</div>
      <form className="card" onSubmit={handleCreate}>
        <div className="field">
          <label>Username</label>
          <input type="text" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
        </div>
        <div className="field">
          <label>Nama Lengkap</label>
          <input type="text" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
        </div>
        <div className="field">
          <label>Password</label>
          <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
        </div>
        <div className="field">
          <label>Role</label>
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
            <option value="RMFT">RMFT</option>
            <option value="ADMIN">ADMIN / SBOH</option>
          </select>
        </div>
        {form.role === "RMFT" && (
          <div className="field">
            <label>PN RMFT</label>
            <select value={form.pn} onChange={(e) => setForm({ ...form, pn: e.target.value })} required>
              <option value="">Pilih PN…</option>
              {rmftOptions.map((r) => <option key={r.pn} value={r.pn}>{r.pn} — {r.rmft_name}</option>)}
            </select>
          </div>
        )}
        <button className="btn btn-primary" type="submit" disabled={busy}>{busy ? "Menyimpan…" : "Buat User"}</button>
      </form>

      <div className="section-title">Daftar User ({users.length})</div>
      <div className="list-card">
        {users.length === 0 && <div className="list-row"><span className="meta">Belum ada user.</span></div>}
        {users.map((u) => (
          <div className="list-row" key={u.id}>
            <div>
              <div className="name">{u.full_name} <span className="meta">({u.username})</span></div>
              <div className="meta">{u.role}{u.pn ? ` · PN ${u.pn}` : ""}</div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span className={`pill ${u.active ? "pos" : "neg"}`}>{u.active ? "Aktif" : "Nonaktif"}</span>
              <button className="btn btn-secondary" onClick={() => toggleActive(u)}>
                {u.active ? "Nonaktifkan" : "Aktifkan"}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ConflictsTab() {
  const [rows, setRows] = useState([]);
  const [rmftOptions, setRmftOptions] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  function load() {
    api.adminOwnershipConflicts().then(setRows).catch((err) => setError(err.message));
    api.listRmft().then(setRmftOptions).catch(() => {});
  }
  useEffect(load, []);

  async function handleOverride(row, pn) {
    if (!pn) return;
    setBusy(row.account_number);
    setError("");
    try {
      await api.adminOverrideOwnership({ snapshot_date: row.snapshot_date, account_number: row.account_number, override_pn: pn });
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  return (
    <div>
      {error && <div className="error-text">{error}</div>}
      <div className="section-title">Konflik Kepemilikan PN — Snapshot Terbaru ({rows.length})</div>
      <div className="list-card">
        {rows.length === 0 && <div className="list-row"><span className="meta">Tidak ada konflik kepemilikan pada snapshot terbaru.</span></div>}
        {rows.map((r) => (
          <div className="list-row" key={r.account_number} style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
              <div>
                <div className="name">{r.customer_name || "-"} <span className="meta">({r.account_number})</span></div>
                <div className="meta">{r.product} · {formatFull(r.balance_idr)} · {formatDate(r.snapshot_date)}</div>
                <div className="meta">Primary saat ini: {r.primary_rmft || "-"} ({r.primary_pn || "-"}) — {r.ownership_source}</div>
                {r.override_pn && <div className="meta">Sudah di-override ke: {r.override_rmft} ({r.override_pn})</div>}
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <select
                  defaultValue=""
                  onChange={(e) => handleOverride(r, e.target.value)}
                  disabled={busy === r.account_number}
                  style={{ maxWidth: 220 }}
                >
                  <option value="">Override ke PN…</option>
                  {rmftOptions.map((o) => <option key={o.pn} value={o.pn}>{o.pn} — {o.rmft_name}</option>)}
                </select>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function UploadsTab() {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  function load() {
    api.adminUploadHistory().then(setRows).catch((err) => setError(err.message));
  }
  useEffect(load, []);

  async function handleRollback(batch) {
    if (!window.confirm(`Rollback upload ${batch.filename} (${batch.snapshot_date})? Data snapshot ini akan dihapus.`)) return;
    setBusy(batch.batch_id);
    setError("");
    try {
      await api.adminRollbackUpload(batch.batch_id);
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  return (
    <div>
      {error && <div className="error-text">{error}</div>}
      <div className="section-title">Riwayat Upload ({rows.length})</div>
      <div className="list-card">
        {rows.length === 0 && <div className="list-row"><span className="meta">Belum ada riwayat upload.</span></div>}
        {rows.map((b) => (
          <div className="list-row" key={b.batch_id}>
            <div>
              <div className="name">{b.filename}</div>
              <div className="meta">
                {b.report_type} · Periode {formatDate(b.snapshot_date)} · {b.valid_count}/{b.row_count} baris valid
                {b.pn_conflict_count > 0 && ` · ${b.pn_conflict_count} konflik PN`}
              </div>
              <div className="meta">Diupload {formatDate(b.uploaded_at)}</div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span className={`pill ${b.status === "SUCCESS" ? "pos" : b.status === "ROLLED_BACK" ? "neg" : "warn"}`}>{b.status}</span>
              {b.status !== "ROLLED_BACK" && (
                <button className="btn btn-secondary" disabled={busy === b.batch_id} onClick={() => handleRollback(b)}>
                  {busy === b.batch_id ? "Memproses…" : "Rollback"}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function AuditTab() {
  const [rows, setRows] = useState([]);
  const [module, setModule] = useState("");
  const [error, setError] = useState("");

  function load() {
    api.adminAuditLog({ module: module || undefined }).then(setRows).catch((err) => setError(err.message));
  }
  useEffect(load, [module]);

  return (
    <div>
      {error && <div className="error-text">{error}</div>}
      <div className="field" style={{ maxWidth: 260 }}>
        <label>Filter Modul</label>
        <select value={module} onChange={(e) => setModule(e.target.value)}>
          <option value="">Semua Modul</option>
          <option value="user">User</option>
          <option value="account_rmft_assignment">Ownership Conflict</option>
          <option value="upload_batch">Upload Batch</option>
        </select>
      </div>
      <div className="section-title">Audit Trail ({rows.length})</div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr><th>Waktu</th><th>User</th><th>Aksi</th><th>Modul</th><th>Record</th><th>Sebelum</th><th>Sesudah</th></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{formatDate(r.timestamp)}</td>
                <td>{r.user}</td>
                <td>{r.action}</td>
                <td>{r.module}</td>
                <td>{r.record || "-"}</td>
                <td>{r.before_value || "-"}</td>
                <td>{r.after_value || "-"}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={7} className="meta">Belum ada aktivitas.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function Admin() {
  const [tab, setTab] = useState("users");

  return (
    <div>
      <div className="section-title">Admin Panel</div>
      <div className="tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`tab-btn ${tab === t.key ? "active" : ""}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === "users" && <UsersTab />}
      {tab === "conflicts" && <ConflictsTab />}
      {tab === "uploads" && <UploadsTab />}
      {tab === "audit" && <AuditTab />}
    </div>
  );
}
