import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { formatShort } from "../utils/format";

export default function Customer() {
  const [searchParams] = useSearchParams();
  const [q, setQ] = useState(searchParams.get("q") || "");
  const [results, setResults] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  async function runSearch(term) {
    if (term.trim().length < 2) return;
    setBusy(true);
    setError("");
    try {
      const rows = await api.searchCustomers(term.trim());
      setResults(rows);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    const initial = searchParams.get("q");
    if (initial) runSearch(initial);
    // eslint-disable-next-line
  }, []);

  function handleSearch(e) {
    e.preventDefault();
    runSearch(q);
  }

  function openCustomer(row) {
    const params = row.cif ? `cif=${encodeURIComponent(row.cif)}` : `account_number=${encodeURIComponent(row.account_number)}`;
    navigate(`/customer/360?${params}`);
  }

  return (
    <div>
      <div className="section-title">Customer 360</div>
      <form onSubmit={handleSearch} style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <input
          type="text"
          placeholder="Cari Nasabah / CIF / Rekening"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          autoFocus
        />
        <button className="btn btn-primary" disabled={busy}>{busy ? "…" : "Cari"}</button>
      </form>

      {error && <div className="error-text">{error}</div>}

      {results && (
        <div className="list-card">
          {results.length === 0 && <div className="list-row"><span className="meta">Tidak ada hasil untuk "{q}".</span></div>}
          {results.map((r) => (
            <div className="list-row" key={r.cif || r.account_number} onClick={() => openCustomer(r)} style={{ cursor: "pointer" }}>
              <div>
                <div className="name">{r.customer || r.account_number}</div>
                <div className="meta">
                  {r.cif ? `CIF ${r.cif}` : `Rek. ${r.account_number}`} · {r.resolved_rmft || "Belum termapping"}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {!results && (
        <div className="empty-state card">
          <div className="big">🔍</div>
          <p>Ketik nama nasabah, CIF, atau nomor rekening untuk melihat posisi Customer 360 — berguna saat sedang meeting dengan nasabah.</p>
        </div>
      )}
    </div>
  );
}
