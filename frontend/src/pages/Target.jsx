import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import ExportButtons from "../components/ExportButtons";
import { formatPercent, formatShort } from "../utils/format";

const PRODUCTS = ["Tabungan", "Giro", "Deposito", "DPK", "Payroll", "EDC", "QRIS", "Premi", "FBI"];

function currentMonth() {
  return new Date().toISOString().slice(0, 7);
}

function ProgressBar({ pct }) {
  const clamped = Math.max(0, Math.min(100, pct));
  const color = pct >= 100 ? "var(--green)" : pct >= 60 ? "var(--accent)" : "var(--red)";
  return (
    <div style={{ background: "var(--bg)", borderRadius: 999, height: 8, overflow: "hidden" }}>
      <div style={{ width: `${clamped}%`, background: color, height: "100%" }} />
    </div>
  );
}

export default function Target() {
  const { isAdmin, profile } = useAuth();
  const [month, setMonth] = useState(currentMonth());
  const [rmftOptions, setRmftOptions] = useState([]);
  const [selectedPn, setSelectedPn] = useState(profile?.pn || "");
  const [targetValues, setTargetValues] = useState({});
  const [achievementRows, setAchievementRows] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

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

  async function loadTargets() {
    if (!activePn) return;
    try {
      const rows = await api.listTargets(month, activePn);
      const map = {};
      rows.forEach((r) => { map[r.product] = r.target; });
      setTargetValues(map);
    } catch (err) {
      setError(err.message);
    }
  }

  async function loadAchievement() {
    try {
      const rows = await api.achievement(month, isAdmin ? undefined : activePn);
      setAchievementRows(rows);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => { loadTargets(); loadAchievement(); /* eslint-disable-next-line */ }, [month, activePn]);

  async function handleSave() {
    setBusy(true);
    setError("");
    try {
      for (const product of PRODUCTS) {
        const value = Number(targetValues[product]);
        if (value > 0) {
          await api.upsertTarget({ month, pn: activePn, product, target: value });
        }
      }
      await loadAchievement();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="section-title">Target RMFT</div>
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
        <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} style={{ maxWidth: 160 }} />
        {isAdmin && rmftOptions.length > 0 && (
          <select value={selectedPn} onChange={(e) => setSelectedPn(e.target.value)} style={{ maxWidth: 220 }}>
            {rmftOptions.map((r) => <option key={r.pn} value={r.pn}>{r.rmft_name}</option>)}
          </select>
        )}
      </div>

      {error && <div className="error-text">{error}</div>}

      {isAdmin && (
        <>
          <div className="section-title">Set Target — {month}</div>
          <div className="card">
            {PRODUCTS.map((product) => (
              <div key={product} className="field" style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
                <label style={{ minWidth: 100, marginBottom: 0 }}>{product}</label>
                <input
                  type="text"
                  placeholder="0"
                  value={targetValues[product] ?? ""}
                  onChange={(e) => setTargetValues({ ...targetValues, [product]: e.target.value })}
                />
              </div>
            ))}
            <button className="btn btn-primary" onClick={handleSave} disabled={busy || !activePn}>
              {busy ? "Menyimpan…" : "Simpan Target"}
            </button>
          </div>
        </>
      )}

      <div className="section-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span>Achievement — {month}</span>
        <ExportButtons report="target_achievement" params={{ month, pn: isAdmin ? undefined : activePn }} />
      </div>
      <div className="list-card">
        {achievementRows.length === 0 && (
          <div className="list-row"><span className="meta">Belum ada target ditetapkan untuk periode ini.</span></div>
        )}
        {achievementRows.map((r) => (
          <div className="list-row" key={r.id} style={{ flexDirection: "column", alignItems: "stretch", gap: 6 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <div>
                <div className="name">{r.product}{isAdmin && !selectedPn ? ` — ${r.rmft_name}` : ""}</div>
                <div className="meta">Target {formatShort(r.target)} · Realisasi {formatShort(r.realisasi)}</div>
              </div>
              <div className={`pill ${r.achievement_pct >= 100 ? "pos" : r.achievement_pct >= 60 ? "neutral" : "neg"}`}>
                {formatPercent(r.achievement_pct)}
              </div>
            </div>
            <ProgressBar pct={r.achievement_pct} />
            <div className="meta">Gap: {formatShort(r.gap)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
