import { useState } from "react";
import { downloadReport } from "../api/client";

/** Section 57: export any report as Excel or PDF. `params` is passed through
 * as query params (date / month / pn / mode etc, whatever the report needs). */
export default function ExportButtons({ report, params = {} }) {
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState("");

  async function handle(format) {
    setBusy(format);
    setError("");
    try {
      const cleanParams = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""));
      await downloadReport(report, format, cleanParams);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <span style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
      <button className="btn btn-secondary" onClick={() => handle("xlsx")} disabled={busy !== null}>
        {busy === "xlsx" ? "…" : "📊 Excel"}
      </button>
      <button className="btn btn-secondary" onClick={() => handle("pdf")} disabled={busy !== null}>
        {busy === "pdf" ? "…" : "📄 PDF"}
      </button>
      {error && <span className="error-text" style={{ margin: 0 }}>{error}</span>}
    </span>
  );
}
