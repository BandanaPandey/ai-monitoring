import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";

test("web app references only gateway api routes", () => {
  const apiSource = fs.readFileSync(new URL("../src/api.js", import.meta.url), "utf8");
  assert.match(apiSource, /\/v1\/auth\/login/);
  assert.match(apiSource, /\/v1\/dashboard\/summary/);
  assert.match(apiSource, /\/v1\/logs/);
  assert.doesNotMatch(apiSource, /clickhouse/i);
  assert.doesNotMatch(apiSource, /postgres/i);
  assert.doesNotMatch(apiSource, /ingest-api/i);
});
