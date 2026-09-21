import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatDate, formatShort } from "../../utils/format";

/** Section 50: Pipeline vs Realisasi bar chart — daily conversion trend within a month. */
export default function PipelineVsRealisasiChart({ data = [] }) {
  if (data.length === 0) {
    return (
      <div className="card" style={{ textAlign: "center", color: "var(--text-muted)", fontSize: 13, padding: 24 }}>
        Belum ada aktivitas pipeline pada bulan ini.
      </div>
    );
  }

  return (
    <div className="card" style={{ height: 280 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" tickFormatter={(d) => formatDate(d)} tick={{ fontSize: 11 }} />
          <YAxis tickFormatter={(v) => formatShort(v)} tick={{ fontSize: 11 }} width={70} />
          <Tooltip labelFormatter={(d) => formatDate(d)} formatter={(value) => formatShort(value)} />
          <Legend />
          <Bar dataKey="pipeline_nominal" name="Pipeline" fill="#2f6fed" radius={[4, 4, 0, 0]} />
          <Bar dataKey="realisasi_nominal" name="Realisasi" fill="#1c9a6c" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
