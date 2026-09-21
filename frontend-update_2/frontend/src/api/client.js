const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

function getToken() {
  return localStorage.getItem("rmft_token");
}

export function setSession(token, profile) {
  localStorage.setItem("rmft_token", token);
  localStorage.setItem("rmft_profile", JSON.stringify(profile));
}

export function clearSession() {
  localStorage.removeItem("rmft_token");
  localStorage.removeItem("rmft_profile");
}

export function getProfile() {
  const raw = localStorage.getItem("rmft_profile");
  return raw ? JSON.parse(raw) : null;
}

async function request(path, { method = "GET", body, isForm = false } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (body && !isForm) headers["Content-Type"] = "application/json";

  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: isForm ? body : body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    clearSession();
    window.location.href = "/login";
    throw new Error("Sesi berakhir, silakan login kembali.");
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || JSON.stringify(data);
    } catch (_) {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

export async function downloadReport(report, format, params = {}) {
  const token = getToken();
  const qs = new URLSearchParams({ report, format, ...params });
  const res = await fetch(`${BASE_URL}/reports/export?${qs.toString()}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (_) { /* ignore */ }
    throw new Error(detail);
  }
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : `${report}.${format === "xlsx" ? "xlsx" : "pdf"}`;

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export const api = {
  login: async (username, password) => {
    const form = new URLSearchParams();
    form.append("username", username);
    form.append("password", password);
    const res = await fetch(`${BASE_URL}/auth/login`, { method: "POST", body: form });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || "Login gagal");
    }
    return res.json();
  },
  me: () => request("/auth/me"),
  listRmft: () => request("/rmft"),
  home: () => request("/funding/home"),
  topMovers: (mode, direction, pn, limit = 10) => {
    const params = new URLSearchParams({ mode, direction, limit: String(limit) });
    if (pn) params.append("pn", pn);
    return request(`/funding/top-movers?${params.toString()}`);
  },
  getBaseline: (month) => request(`/funding/baseline?month=${month}`),
  flowTotals: (mode = "MTD", pn) => request(`/funding/flow-totals?mode=${mode}${pn ? `&pn=${pn}` : ""}`),
  fundingTrend: (days = 30, pn) => request(`/funding/trend?days=${days}${pn ? `&pn=${pn}` : ""}`),
  setBaseline: (month, baseline_date) =>
    request(`/funding/baseline?month=${month}&baseline_date=${baseline_date}`, { method: "POST" }),
  previewUpload: (formData) => request("/upload/preview", { method: "POST", body: formData, isForm: true }),
  importUpload: (formData) => request("/upload/import", { method: "POST", body: formData, isForm: true }),

  // --- Customer 360 / search (Phase 4) ---
  searchCustomers: (q) => request(`/customers/search?q=${encodeURIComponent(q)}`),
  customer360: ({ cif, account_number }) => {
    const params = new URLSearchParams();
    if (cif) params.append("cif", cif);
    if (account_number) params.append("account_number", account_number);
    return request(`/customers/360?${params.toString()}`);
  },
  outflowAlerts: (mode = "DTD", limit = 20) => request(`/customers/outflow-alerts?mode=${mode}&limit=${limit}`),
  listFollowup: () => request("/customers/followup"),
  createFollowup: (payload) => request("/customers/followup", { method: "POST", body: payload }),
  updateFollowup: (id, payload) => request(`/customers/followup/${id}`, { method: "PUT", body: payload }),

  // --- Pipeline / Realisasi (Phase 5) ---
  listPipeline: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""));
    return request(`/pipeline?${qs.toString()}`);
  },
  createPipeline: (payload) => request("/pipeline", { method: "POST", body: payload }),
  updatePipeline: (id, payload) => request(`/pipeline/${id}`, { method: "PUT", body: payload }),
  copyPipelineKemarin: (target_date, pn) => {
    const params = new URLSearchParams({ target_date });
    if (pn) params.append("pn", pn);
    return request(`/pipeline/copy-yesterday?${params.toString()}`, { method: "POST" });
  },
  listRealization: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""));
    return request(`/realization?${qs.toString()}`);
  },
  createRealization: (payload) => request("/realization", { method: "POST", body: payload }),

  // --- Pipeline vs Actual Funding matching (Phase 7) ---
  potentialMatches: (pn) => request(`/pipeline/matches${pn ? `?pn=${pn}` : ""}`),
  confirmMatch: (pipeline_id, amount) =>
    request(`/pipeline/matches/confirm?pipeline_id=${encodeURIComponent(pipeline_id)}&amount=${amount}`, { method: "POST" }),
  dismissMatch: (pipeline_id, actual_account_number) =>
    request(`/pipeline/matches/dismiss?pipeline_id=${encodeURIComponent(pipeline_id)}&actual_account_number=${encodeURIComponent(actual_account_number)}`, { method: "POST" }),

  // --- Performance (Phase 6) ---
  successRate: (scope = "mtd", pn) => {
    const params = new URLSearchParams({ scope });
    if (pn) params.append("pn", pn);
    return request(`/performance/success-rate?${params.toString()}`);
  },
  leaderboard: (scope = "mtd") => request(`/performance/leaderboard?scope=${scope}`),
  dailyAction: (pn) => request(`/performance/daily-action${pn ? `?pn=${pn}` : ""}`),
  monthlySummary: (month, pn) => request(`/performance/monthly-summary?month=${month}${pn ? `&pn=${pn}` : ""}`),
  conversionTrend: (month, pn) => request(`/performance/conversion-trend?month=${month}${pn ? `&pn=${pn}` : ""}`),

  // --- WA Report (Phase 8) ---
  waPagi: (target_date, pn) => {
    const params = new URLSearchParams({ target_date });
    if (pn) params.append("pn", pn);
    return request(`/wa/pagi?${params.toString()}`);
  },
  waSore: (target_date, pn) => {
    const params = new URLSearchParams({ target_date });
    if (pn) params.append("pn", pn);
    return request(`/wa/sore?${params.toString()}`);
  },

  // --- Target (Phase 9) ---
  listTargets: (month, pn) => {
    const params = new URLSearchParams({ month });
    if (pn) params.append("pn", pn);
    return request(`/target?${params.toString()}`);
  },
  upsertTarget: (payload) => request("/target", { method: "POST", body: payload }),
  achievement: (month, pn) => {
    const params = new URLSearchParams({ month });
    if (pn) params.append("pn", pn);
    return request(`/target/achievement?${params.toString()}`);
  },

  // --- Admin (Phase 10) ---
  adminListUsers: () => request("/admin/users"),
  adminCreateUser: (payload) => request("/admin/users", { method: "POST", body: payload }),
  adminUpdateUser: (id, payload) => request(`/admin/users/${id}`, { method: "PUT", body: payload }),
  adminOwnershipConflicts: (snapshot_date) =>
    request(`/admin/ownership-conflicts${snapshot_date ? `?snapshot_date=${snapshot_date}` : ""}`),
  adminOverrideOwnership: (payload) =>
    request("/admin/ownership-conflicts/override", { method: "POST", body: payload }),
  adminUploadHistory: () => request("/admin/upload-history"),
  adminRollbackUpload: (batch_id) =>
    request(`/admin/upload-history/${batch_id}/rollback`, { method: "POST" }),
  adminAuditLog: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""));
    return request(`/admin/audit-log?${qs.toString()}`);
  },

  // --- RMFT master CRUD (edit nama RMFT / tambah / nonaktifkan) ---
  adminListRmftMaster: () => request("/admin/rmft"),
  adminCreateRmft: (payload) => request("/admin/rmft", { method: "POST", body: payload }),
  adminUpdateRmft: (pn, payload) => request(`/admin/rmft/${pn}`, { method: "PUT", body: payload }),

  // --- EDC/QRIS productivity thresholds (admin-editable policy) ---
  adminGetMerchantThresholds: () => request("/admin/merchant-thresholds"),
  adminUpdateMerchantThreshold: (payload) =>
    request("/admin/merchant-thresholds", { method: "PUT", body: payload }),

  // --- EDC/QRIS productivity data ---
  merchantSummary: (channel, pn) => {
    const params = new URLSearchParams();
    if (channel) params.append("channel", channel);
    if (pn) params.append("pn", pn);
    return request(`/merchant/summary?${params.toString()}`);
  },
  merchantList: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""));
    return request(`/merchant/list?${qs.toString()}`);
  },

  // --- Report per RMFT (inline preview before export) ---
  previewReport: (report, params = {}) => {
    const qs = new URLSearchParams(Object.entries({ report, ...params }).filter(([, v]) => v !== undefined && v !== null && v !== ""));
    return request(`/reports/preview?${qs.toString()}`);
  },
};
