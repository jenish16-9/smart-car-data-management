const API_BASE_URL = 'http://localhost:8000/api/v1';

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'API request failed');
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
  vehicle: (id) => apiRequest(`/vehicles/${id}`),
  alerts: () => apiRequest('/alerts'),
  analytics: () => apiRequest('/analytics/summary'),
};

