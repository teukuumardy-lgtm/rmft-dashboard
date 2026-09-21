import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
      navigate("/");
    } catch (err) {
      setError(err.message || "Login gagal");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={handleSubmit}>
        <h1>RMFT Performance & Pipeline Dashboard</h1>
        <p className="sub">Command Center Harian RMFT</p>

        {error && <div className="error-text">{error}</div>}

        <div className="field">
          <label>Username</label>
          <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus required />
        </div>
        <div className="field">
          <label>Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        <button className="btn btn-primary btn-block" disabled={loading}>
          {loading ? "Memproses..." : "Masuk"}
        </button>

        <div className="demo-hint">
          Demo login (seed data): <b>admin / admin123</b> (Admin/SBOH) atau <b>adist / adist123</b>,{" "}
          <b>ahmad / ahmad123</b>, <b>dia / dia123</b> (RMFT).
        </div>
      </form>
    </div>
  );
}
