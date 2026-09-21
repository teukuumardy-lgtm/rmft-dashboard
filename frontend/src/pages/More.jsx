import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { NAV_ITEMS } from "../nav";

export default function More() {
  const { isAdmin, logout } = useAuth();
  const items = NAV_ITEMS.filter((item) => !item.adminOnly || isAdmin);

  return (
    <div>
      <div className="section-title">Menu Lainnya</div>
      <div className="list-card">
        {items.map((item) => (
          <Link className="list-row" to={item.path} key={item.path}>
            <div>
              <div className="name">{item.icon} {item.label}</div>
              {!item.ready && <div className="meta">{item.phase}</div>}
            </div>
          </Link>
        ))}
      </div>
      <button className="btn btn-secondary btn-block" style={{ marginTop: 16 }} onClick={logout}>
        Keluar
      </button>
    </div>
  );
}
