// Section 3: MENU UTAMA. All items are fully implemented (`ready: true`).
// `adminOnly` items are hidden from the RMFT-role menu entirely; RMFT users
// who deep-link to one anyway hit the "Akses Terbatas" guard in App.jsx.
export const NAV_ITEMS = [
  { path: "/", label: "Home", icon: "🏠", ready: true, bottom: true },
  { path: "/daily-action", label: "Daily Action", icon: "⚡", ready: true },
  { path: "/pipeline", label: "Pipeline", icon: "📈", ready: true, bottom: true },
  { path: "/realisasi", label: "Realisasi", icon: "✅", ready: true, bottom: true },
  { path: "/funding", label: "Funding", icon: "💰", ready: true, bottom: true },
  { path: "/customer", label: "Customer", icon: "🧑‍💼", ready: true },
  { path: "/rmft-performance", label: "RMFT Performance", icon: "🏆", ready: true },
  { path: "/monthly-report", label: "Monthly Report", icon: "📅", ready: true },
  { path: "/wa-report", label: "WA Report", icon: "📲", ready: true },
  { path: "/upload", label: "Upload Data", icon: "📤", ready: true, adminOnly: true },
  { path: "/target", label: "Target", icon: "🎯", ready: true },
  { path: "/admin", label: "Admin", icon: "🛠️", ready: true, adminOnly: true },
];
