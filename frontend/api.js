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

  return response.json();
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
  vehicleDevices: (id) => apiRequest(`/vehicles/${id}/devices`),
  createDevice: (vehicleId, device) => apiRequest(`/vehicles/${vehicleId}/devices`, {
    method: 'POST',
    body: JSON.stringify(device),
  }),
  device: (id) => apiRequest(`/devices/${id}`),
  alerts: () => apiRequest('/alerts'),
  analytics: () => apiRequest('/analytics/summary'),
};

