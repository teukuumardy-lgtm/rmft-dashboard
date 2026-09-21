import { formatDate } from "../utils/format";

const STATUS_CONFIG = {
  COMPLETE: { icon: "🟢", label: "COMPLETE" },
  PARTIAL: { icon: "🟡", label: "PARTIAL — SEBAGIAN DATA BELUM ADA" },
  DATE_MISMATCH: { icon: "🟡", label: "PARTIAL / DATE MISMATCH" },
  NO_DATA: { icon: "🔵", label: "BELUM ADA DATA" },
};

const PRODUCT_LABEL = { TABUNGAN: "Tabungan", GIRO: "Giro", DEPOSITO: "Deposito" };

export default function DataPositionBanner({ freshness }) {
  if (!freshness) return null;
  const cfg = STATUS_CONFIG[freshness.status] || STATUS_CONFIG.NO_DATA;
  const latestOverall = freshness.items.reduce((max, item) => {
    if (!item.snapshot_date) return max;
    return !max || item.snapshot_date > max ? item.snapshot_date : max;
  }, null);

  return (
    <div className={`freshness-banner ${freshness.status.toLowerCase()}`}>
      <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.06em" }}>
        DATA POSITION
      </div>
      <div className="freshness-items">
        {freshness.items.map((item) => {
          const isMismatch = freshness.status === "DATE_MISMATCH" && item.snapshot_date !== latestOverall;
          return (
            <div className="item" key={item.product}>
              <span className="prod">{PRODUCT_LABEL[item.product]}</span>
              <span className="val">
                {item.snapshot_date ? formatDate(item.snapshot_date) : "Belum ada data"}{" "}
                {item.snapshot_date ? (isMismatch ? "⚠️" : "✅") : "⛔"}
              </span>
            </div>
          );
        })}
      </div>
      <div className="status-line">
        {cfg.icon} {cfg.label}
        {freshness.as_of ? ` — ${formatDate(freshness.as_of)}` : ""}
      </div>
    </div>
  );
}
