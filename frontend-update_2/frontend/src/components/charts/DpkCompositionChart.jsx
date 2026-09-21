import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { formatShort } from "../../utils/format";

const COLORS = { Tabungan: "#2f6fed", Giro: "#1c9a6c", Deposito: "#b9791b" };

/** Section 50: DPK Composition donut — Tabungan / Giro / Deposito split of current DPK. */
export default function DpkCompositionChart({ current }) {
  const slices = [
    { name: "Tabungan", value: current?.tabungan || 0 },
    { name: "Giro", value: current?.giro || 0 },
    { name: "Deposito", value: current?.deposito || 0 },
  ].filter((s) => s.value > 0);

  if (slices.length === 0) {
    return (
      <div className="card" style={{ textAlign: "center", color: "var(--text-muted)", fontSize: 13, padding: 24 }}>
        Belum ada posisi DPK untuk ditampilkan.
      </div>
    );
  }

  return (
    <div className="card" style={{ height: 260 }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={slices} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={2}>
            {slices.map((s) => (
              <Cell key={s.name} fill={COLORS[s.name]} />
            ))}
          </Pie>
          <Tooltip formatter={(value) => formatShort(value)} />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
