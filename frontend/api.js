// Backend client for the Smart Car Data Management API.
// Network failures are reported as ApiError with status 0 so the UI can fall back to mock data.

const API_BASE_URL = window.API_BASE_URL || 'http://localhost:8000/api/v1';
const TOKEN_KEY = 'smartcar.token';

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
  get unreachable() { return this.status === 0; }
}

// The token lives in localStorage when "Remember me" is ticked, otherwise in sessionStorage.
export const tokenStore = {
  get() {
    try { return sessionStorage.getItem(TOKEN_KEY) || localStorage.getItem(TOKEN_KEY); } catch { return null; }
  },
  set(token, remember = false) {
    try {
      this.clear();
      (remember ? localStorage : sessionStorage).setItem(TOKEN_KEY, token);
    } catch { /* storage unavailable: the session just won't persist */ }
  },
  clear() {
    try { sessionStorage.removeItem(TOKEN_KEY); localStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ }
  },
};

function queryString(params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, value);
  });
  const text = query.toString();
  return text ? `?${text}` : '';
}

function errorMessage(body) {
  if (typeof body.detail === 'string') return body.detail;
  if (Array.isArray(body.detail) && body.detail.length) return body.detail[0].msg || 'Invalid request';
  return 'API request failed';
}

async function apiRequest(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  const token = tokenStore.get();
  if (token) headers.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  } catch {
    throw new ApiError('Cannot reach the server', 0);
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(errorMessage(body), response.status);
  }
  return response.status === 204 ? null : response.json();
}

const post = (path, body) => apiRequest(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined });

export const api = {
  hasToken: () => Boolean(tokenStore.get()),

  // Authentication
  login: async (email, password, remember = false) => {
    const result = await post('/auth/login', { email, password });
    tokenStore.set(result.access_token, remember);
    return result;
  },
  register: (name, email, password) => post('/auth/register', { name, email, password }),
  logout: async () => {
    try { await post('/auth/logout'); } finally { tokenStore.clear(); }
  },
  me: () => apiRequest('/auth/me'),

  // Vehicles
  vehicles: () => apiRequest('/vehicles'),
  vehicle: (id) => apiRequest(`/vehicles/${encodeURIComponent(id)}`),
  updateControls: (id, controls) => apiRequest(`/vehicles/${encodeURIComponent(id)}/controls`, { method: 'PATCH', body: JSON.stringify(controls) }),
  devices: (params) => apiRequest(`/devices${queryString(params)}`),
  device: (id) => apiRequest(`/devices/${encodeURIComponent(id)}`),
  deviceHeartbeats: (id, params) => apiRequest(`/devices/${encodeURIComponent(id)}/heartbeats${queryString(params)}`),
  updateDeviceControls: (id, controls) => apiRequest(`/devices/${encodeURIComponent(id)}/status`, { method: 'PATCH', body: JSON.stringify(controls) }),
  deviceLogs: (id, params) => apiRequest(`/vehicles/${encodeURIComponent(id)}/logs${queryString(params)}`),

  // Audio
  audio: (params) => apiRequest(`/audio${queryString(params)}`),
  audioRecord: (id) => apiRequest(`/audio/${id}`),

  // Alerts
  alerts: (params) => apiRequest(`/alerts${queryString(params)}`),
  alert: (id) => apiRequest(`/alerts/${id}`),
  acknowledgeAlert: (id, notes) => post(`/alerts/${id}/acknowledge`, notes ? { notes } : undefined),
  resolveAlert: (id, notes) => post(`/alerts/${id}/resolve`, notes ? { notes } : undefined),

  // Analytics
  analytics: (params) => apiRequest(`/analytics/summary${queryString(params)}`),
  eventsOverTime: (params) => apiRequest(`/analytics/events-over-time${queryString(params)}`),
  eventsByType: (params) => apiRequest(`/analytics/events-by-type${queryString(params)}`),

  // Telemetry
  telemetry: (vehicleId, params) => apiRequest(`/telemetry/${encodeURIComponent(vehicleId)}${queryString(params)}`),
  latestTelemetry: (vehicleId) => apiRequest(`/telemetry/${encodeURIComponent(vehicleId)}/latest`),
};
