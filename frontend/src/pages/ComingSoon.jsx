export default function ComingSoon({ title, phase, description }) {
  return (
    <div className="coming-soon card">
      <div className="badge">{phase}</div>
      <h2 style={{ margin: "0 0 8px" }}>{title}</h2>
      <p style={{ color: "var(--text-muted)", maxWidth: 420, margin: "0 auto" }}>
        {description || "Modul ini termasuk dalam roadmap pengembangan berikutnya dan akan terintegrasi penuh dengan data funding & pipeline yang sudah berjalan."}
      </p>
    </div>
  );
}
