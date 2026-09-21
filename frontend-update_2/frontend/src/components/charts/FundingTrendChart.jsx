import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatDate, formatShort } from "../../utils/format";

/** Section 50: Funding Trend line chart — DPK composition over the last N days. */
export default function FundingTrendChart({ data = [] }) {
  if (data.length < 2) {
    return (
      <div className="card" style={{ textAlign: "center", color: "var(--text-muted)", fontSize: 13, padding: 24 }}>
        Belum cukup riwayat snapshot untuk menampilkan tren (minimal 2 tanggal upload).
      </div>
    );
  }

  return (
    <div className="card" style={{ height: 280 }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tickFormatter={(d) => formatDate(d)} tick={{ fontSize: 11 }} />
          <YAxis tickFormatter={(v) => formatShort(v)} tick={{ fontSize: 11 }} width={70} />
          <Tooltip labelFormatter={(d) => formatDate(d)} formatter={(value) => formatShort(value)} />
          <Legend />
          <Line type="monotone" dataKey="dpk" name="Total DPK" stroke="#0b2545" strokeWidth={2.5} dot={false} />
          <Line type="monotone" dataKey="tabungan" name="Tabungan" stroke="#2f6fed" strokeWidth={1.5} dot={false} />
          <Line type="monotone" dataKey="giro" name="Giro" stroke="#1c9a6c" strokeWidth={1.5} dot={false} />
          <Line type="monotone" dataKey="deposito" name="Deposito" stroke="#b9791b" strokeWidth={1.5} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
