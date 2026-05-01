import test from "node:test";
import assert from "node:assert/strict";

import { compareLogs, fetchLogDetail, fetchLogs, fetchSummary, login } from "../src/api.js";

test("login posts credentials to gateway auth endpoint", async () => {
  const calls = [];
  global.fetch = async (url, options) => {
    calls.push({ url, options });
    return {
      ok: true,
      json: async () => ({ access_token: "token" }),
    };
  };

  const response = await login("admin@example.com", "changeme");

  assert.equal(response.access_token, "token");
  assert.equal(calls[0].url, "http://localhost:8000/v1/auth/login");
  assert.equal(calls[0].options.method, "POST");
  assert.equal(calls[0].options.headers["Content-Type"], "application/json");
  assert.deepEqual(JSON.parse(calls[0].options.body), {
    email: "admin@example.com",
    password: "changeme",
  });
});

test("dashboard, logs, detail, and compare calls carry bearer auth", async () => {
  const calls = [];
  global.fetch = async (url, options) => {
    calls.push({ url, options });
    return {
      ok: true,
      json: async () => ({ items: [], total: 0 }),
    };
  };

  await fetchSummary("token-1");
  await fetchLogs("token-2", "search=req-1");
  await fetchLogDetail("token-3", "req-3");
  await compareLogs("token-4", "req-left", "req-right");

  assert.equal(calls[0].url, "http://localhost:8000/v1/dashboard/summary");
  assert.equal(calls[0].options.headers.Authorization, "Bearer token-1");

  assert.equal(calls[1].url, "http://localhost:8000/v1/logs?search=req-1");
  assert.equal(calls[1].options.headers.Authorization, "Bearer token-2");

  assert.equal(calls[2].url, "http://localhost:8000/v1/logs/req-3");
  assert.equal(calls[2].options.headers.Authorization, "Bearer token-3");

  assert.equal(calls[3].url, "http://localhost:8000/v1/logs/compare");
  assert.equal(calls[3].options.method, "POST");
  assert.equal(calls[3].options.headers.Authorization, "Bearer token-4");
  assert.deepEqual(JSON.parse(calls[3].options.body), {
    left_request_id: "req-left",
    right_request_id: "req-right",
  });
});
