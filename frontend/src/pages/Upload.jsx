import { useState } from "react";
import { api } from "../api/client";
import { formatDate } from "../utils/format";

const SLOTS = [
  { key: "tabungan", label: "Tabungan (DI319)" },
  { key: "giro", label: "Giro (DI321)" },
  { key: "deposito", label: "Deposito (CI324)" },
];

function PreviewLine({ preview }) {
  if (!preview) return null;
  if (preview.error) return <div className="preview-line" style={{ color: "var(--red)" }}>⚠️ {preview.error}</div>;
  if (!preview.detected) return null;
  return (
    <div className="preview-line">
      <div>{preview.report_type} detected ✅</div>
      <div style={{ color: "var(--text-muted)" }}>Periode: {formatDate(preview.periode)}</div>
      <div style={{ color: "var(--text-muted)" }}>Rows: {preview.rows}</div>
    </div>
  );
}

export default function Upload() {
  const [files, setFiles] = useState({ tabungan: null, giro: null, deposito: null });
  const [preview, setPreview] = useState(null);
  const [importResult, setImportResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function pick(key, file) {
    setFiles((f) => ({ ...f, [key]: file }));
    setPreview(null);
    setImportResult(null);
  }

  function buildForm() {
    const form = new FormData();
    Object.entries(files).forEach(([key, file]) => {
      if (file) form.append(key, file);
    });
    return form;
  }

  async function handlePreview() {
    setError("");
    setBusy(true);
    try {
      const result = await api.previewUpload(buildForm());
      setPreview(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleImport() {
    setError("");
    setBusy(true);
    try {
      const result = await api.importUpload(buildForm());
      setImportResult(result);
      setPreview(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const anyFile = Object.values(files).some(Boolean);

  return (
    <div>
      <div className="section-title">Upload Daily Position</div>
      <p style={{ marginTop: -6, fontSize: 13, color: "var(--text-muted)" }}>
        Upload file laporan asli (DI319 / DI321 / CI324) apa adanya — tidak perlu rename, hapus baris judul,
        atau ubah header. Sistem mendeteksi dan menormalisasi otomatis.
      </p>

      <div className="upload-grid">
        {SLOTS.map((slot) => (
          <div className="upload-slot" key={slot.key}>
            <h3>{slot.label}</h3>
            <input
              type="file"
              accept=".xlsx,.xls,.csv"
              onChange={(e) => pick(slot.key, e.target.files?.[0] || null)}
            />
            <PreviewLine preview={preview?.[slot.key]} />
            {importResult?.[slot.key] && (
              <div className="preview-line" style={{ marginTop: 8 }}>
                {importResult[slot.key].error ? (
                  <span style={{ color: "var(--red)" }}>⚠️ {importResult[slot.key].error}</span>
                ) : (
                  <>
                    <div className={`pill ${importResult[slot.key].status === "SUCCESS" ? "pos" : "warn"}`}>
                      {importResult[slot.key].status}
                    </div>
                    <div style={{ marginTop: 6, color: "var(--text-muted)" }}>
                      Total rows: {importResult[slot.key].total_rows} · Target RMFT: {importResult[slot.key].target_rmft_rows}
                      <br />
                      Unique accounts: {importResult[slot.key].unique_accounts} · Duplicates removed: {importResult[slot.key].duplicates_removed}
                      <br />
                      PN conflict: {importResult[slot.key].pn_conflict} · Unassigned: {importResult[slot.key].unassigned}
                      <br />
                      Invalid balance: {importResult[slot.key].invalid_balance}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {error && <div className="error-text" style={{ marginTop: 16 }}>{error}</div>}

      {preview && (
        <div className="card" style={{ marginTop: 16 }}>
          <b>Overall status: </b>
          <span className={`pill ${preview.overall_status === "COMPLETE" ? "pos" : "warn"}`}>
            {preview.overall_status}
          </span>
        </div>
      )}

      <div style={{ display: "flex", gap: 12, marginTop: 16 }}>
        <button className="btn btn-secondary" disabled={!anyFile || busy} onClick={handlePreview}>
          Preview
        </button>
        <button className="btn btn-primary" disabled={!anyFile || busy} onClick={handleImport}>
          {busy ? "Memproses…" : "IMPORT DAILY POSITION"}
        </button>
      </div>
    </div>
  );
}
