export const API_BASE_URL =
  globalThis.__AI_MONITORING_GATEWAY_API_URL__ ||
  import.meta.env?.VITE_GATEWAY_API_URL ||
  "http://localhost:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `Request failed with status ${response.status}`);
  }
  return response.json();
}

export async function login(email, password) {
  return request("/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function fetchSummary(token) {
  return request("/v1/dashboard/summary", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function fetchLogs(token, query = "") {
  const suffix = query ? `?${query}` : "";
  return request(`/v1/logs${suffix}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function fetchLogDetail(token, requestId) {
  return request(`/v1/logs/${requestId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function compareLogs(token, leftRequestId, rightRequestId) {
  return request("/v1/logs/compare", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      left_request_id: leftRequestId,
      right_request_id: rightRequestId,
    }),
  });
}
