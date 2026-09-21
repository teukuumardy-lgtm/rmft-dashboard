import { createContext, useContext, useState, useCallback } from "react";
import { api, clearSession, getProfile, setSession } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [profile, setProfile] = useState(() => getProfile());

  const login = useCallback(async (username, password) => {
    const data = await api.login(username, password);
    const nextProfile = { full_name: data.full_name, role: data.role, pn: data.pn };
    setSession(data.access_token, nextProfile);
    setProfile(nextProfile);
    return nextProfile;
  }, []);

  const logout = useCallback(() => {
    clearSession();
    setProfile(null);
  }, []);

  return (
    <AuthContext.Provider value={{ profile, isAdmin: profile?.role === "ADMIN", login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
