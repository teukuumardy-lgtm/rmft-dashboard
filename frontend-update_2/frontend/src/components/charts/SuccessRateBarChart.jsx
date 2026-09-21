import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatPercent } from "../../utils/format";

function barColor(pct) {
  if (pct >= 80) return "#1c9a6c";
  if (pct >= 60) return "#b9791b";
  return "#d64545";
}

/** Section 50: Success Rate horizontal bar — RMFT leaderboard ranked by Nominal SR. */
export default function SuccessRateBarChart({ rows = [] }) {
  const data = rows
    .filter((r) => r.total_pipeline_count > 0)
    .map((r) => ({ name: r.rmft_name, nominal_sr: r.nominal_sr }))
    .sort((a, b) => b.nominal_sr - a.nominal_sr);

  if (data.length === 0) {
    return (
      <div className="card" style={{ textAlign: "center", color: "var(--text-muted)", fontSize: 13, padding: 24 }}>
        Belum ada data pipeline pada periode ini.
      </div>
    );
  }

  return (
    <div className="card" style={{ height: Math.max(180, data.length * 42) }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 8, right: 24, left: 8, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
          <YAxis type="category" dataKey="name" width={130} tick={{ fontSize: 12 }} />
          <Tooltip formatter={(value) => formatPercent(value)} />
          <Bar dataKey="nominal_sr" radius={[0, 6, 6, 0]}>
            {data.map((d) => <Cell key={d.name} fill={barColor(d.nominal_sr)} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
