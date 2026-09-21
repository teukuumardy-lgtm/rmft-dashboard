import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatShort } from "../../utils/format";

/** Section 50: Inflow vs Outflow bar chart (full-population totals, not just Top 10). */
export default function InflowOutflowChart({ inflow = 0, outflow = 0, mode = "MTD" }) {
  const data = [
    { name: "Inflow", value: inflow, fill: "#1c9a6c" },
    { name: "Outflow", value: outflow, fill: "#d64545" },
  ];

  if (inflow === 0 && outflow === 0) {
    return (
      <div className="card" style={{ textAlign: "center", color: "var(--text-muted)", fontSize: 13, padding: 24 }}>
        Belum ada pergerakan saldo ({mode}) untuk ditampilkan.
      </div>
    );
  }

  return (
    <div className="card" style={{ height: 220 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="name" tick={{ fontSize: 12 }} />
          <YAxis tickFormatter={(v) => formatShort(v)} tick={{ fontSize: 11 }} width={70} />
          <Tooltip formatter={(value) => formatShort(value)} />
          <Bar dataKey="value" radius={[6, 6, 0, 0]}>
            {data.map((d) => <Cell key={d.name} fill={d.fill} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
