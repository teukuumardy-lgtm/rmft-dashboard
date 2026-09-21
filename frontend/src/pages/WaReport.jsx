import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

export default function WaReport() {
  const { isAdmin, profile } = useAuth();
  const [tab, setTab] = useState("pagi");
  const [date, setDate] = useState(todayStr());
  const [rmftOptions, setRmftOptions] = useState([]);
  const [selectedPn, setSelectedPn] = useState("");
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (isAdmin) {
      api.listRmft().then(setRmftOptions).catch(() => {});
    }
  }, [isAdmin]);

  async function load() {
    setBusy(true);
    setError("");
    setCopied(false);
    try {
      const pn = isAdmin ? (selectedPn || undefined) : profile.pn;
      const result = tab === "pagi" ? await api.waPagi(date, pn) : await api.waSore(date, pn);
      setText(result.text);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [tab, date, selectedPn]);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("Gagal menyalin — salin manual dari kotak teks di bawah.");
    }
  }

  return (
    <div>
      <div className="section-title">WA Report Generator</div>

      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
        <button className={`btn ${tab === "pagi" ? "btn-primary" : "btn-secondary"}`} onClick={() => setTab("pagi")}>
          ☀️ WA Pagi
        </button>
        <button className={`btn ${tab === "sore" ? "btn-primary" : "btn-secondary"}`} onClick={() => setTab("sore")}>
          🌆 WA Sore
        </button>
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} style={{ maxWidth: 180 }} />
        {isAdmin && (
          <select value={selectedPn} onChange={(e) => setSelectedPn(e.target.value)} style={{ maxWidth: 220 }}>
            <option value="">Seluruh Unit</option>
            {rmftOptions.map((r) => <option key={r.pn} value={r.pn}>{r.rmft_name}</option>)}
          </select>
        )}
      </div>

      {error && <div className="error-text">{error}</div>}

      <div className="card">
        <textarea
          readOnly
          value={busy ? "Memuat…" : text}
          style={{
            width: "100%", minHeight: 420, border: "none", resize: "vertical",
            fontFamily: "ui-monospace, Menlo, Consolas, monospace", fontSize: 13, lineHeight: 1.6,
            background: "transparent", color: "var(--text)",
          }}
        />
      </div>

      <div style={{ display: "flex", gap: 12, marginTop: 16 }}>
        <button className="btn btn-primary" onClick={handleCopy} disabled={busy || !text}>
          {copied ? "✅ Tersalin!" : `📋 Copy WA ${tab === "pagi" ? "Pagi" : "Sore"}`}
        </button>
        <button className="btn btn-secondary" onClick={load} disabled={busy}>🔄 Refresh</button>
      </div>
    </div>
  );
}
