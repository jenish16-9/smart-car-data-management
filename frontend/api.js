const API_BASE_URL = 'http://localhost:8000/api/v1';
let accessToken = null;

export function setAccessToken(token) {
  accessToken = token;
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const detail = Array.isArray(error.detail)
      ? error.detail.map((item) => item.msg).join(', ')
      : error.detail;
    throw new Error(detail || 'API request failed');
  }

  return response.status === 204 ? null : response.json();
}

export const api = {
  login: (email, password) => apiRequest('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  }),
  logout: () => apiRequest('/auth/logout', { method: 'POST' }),
  vehicles: () => apiRequest('/vehicles'),
  createVehicle: (vehicle) => apiRequest('/vehicles', {
    method: 'POST',
    body: JSON.stringify(vehicle),
  }),
  vehicle: (id) => apiRequest(`/vehicles/${id}`),
  updateVehicle: (id, vehicle) => apiRequest(`/vehicles/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(vehicle),
  }),
  removeVehicle: (id) => apiRequest(`/vehicles/${id}`, { method: 'DELETE' }),
  vehicleDevices: (id) => apiRequest(`/vehicles/${id}/devices`),
  createDevice: (vehicleId, device) => apiRequest(`/vehicles/${vehicleId}/devices`, {
    method: 'POST',
    body: JSON.stringify(device),
  }),
  device: (id) => apiRequest(`/devices/${id}`),
  updateDevice: (id, device) => apiRequest(`/devices/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(device),
  }),
  updateDeviceConfiguration: (id, configuration) => apiRequest(`/devices/${id}/configuration`, {
    method: 'PUT',
    body: JSON.stringify({ configuration }),
  }),
  heartbeat: (id, heartbeat) => apiRequest(`/devices/${id}/heartbeat`, {
    method: 'POST',
    body: JSON.stringify(heartbeat),
  }),
  deviceHeartbeats: (id) => apiRequest(`/devices/${id}/heartbeats`),
  removeDevice: (id) => apiRequest(`/devices/${id}`, { method: 'DELETE' }),
  alerts: () => apiRequest('/alerts'),
  analytics: () => apiRequest('/analytics/summary'),
};

