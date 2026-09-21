import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { NAV_ITEMS } from "../nav";

export default function Layout() {
  const { profile, isAdmin, logout } = useAuth();
  const navigate = useNavigate();

  const visibleItems = NAV_ITEMS.filter((item) => !item.adminOnly || isAdmin);
  const bottomItems = visibleItems.filter((item) => item.bottom).slice(0, 4);

  const initials = (profile?.full_name || "?")
    .split(" ")
    .map((s) => s[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">RMFT DASHBOARD</div>
        {visibleItems.map((item) => (
          <NavLink key={item.path} to={item.path} className={({ isActive }) => (isActive ? "active" : "")}>
            <span>{item.icon}</span>
            <span>{item.label}{!item.ready && <span style={{ opacity: 0.5, fontSize: 10 }}> · {item.phase}</span>}</span>
          </NavLink>
        ))}
        <div style={{ marginTop: "auto", paddingTop: 16 }}>
          <button
            className="btn btn-secondary btn-block"
            style={{ background: "transparent", color: "#cdd8ee", borderColor: "rgba(255,255,255,0.2)" }}
            onClick={() => { logout(); navigate("/login"); }}
          >
            Keluar
          </button>
        </div>
      </aside>

      <div className="main-area">
        <div className="topbar">
          <div>
            <h1>RMFT Performance & Pipeline Dashboard</h1>
            <div className="subtitle">
              {profile?.role === "ADMIN" ? "ADMIN / SBOH" : `RMFT — ${profile?.full_name}`}
            </div>
          </div>
          <div className="avatar-chip" onClick={() => { logout(); navigate("/login"); }} title="Keluar">
            <span className="dot">{initials}</span>
            <span>{profile?.full_name}</span>
          </div>
        </div>

        <Outlet />
      </div>

      <nav className="bottom-nav">
        {bottomItems.map((item) => (
          <NavLink key={item.path} to={item.path} className={({ isActive }) => (isActive ? "active" : "")}>
            <span className="icon">{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
        <NavLink to="/more" className={({ isActive }) => (isActive ? "active" : "")}>
          <span className="icon">⋯</span>
          <span>More</span>
        </NavLink>
      </nav>
    </div>
  );
}
