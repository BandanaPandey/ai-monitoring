import test from "node:test";
import assert from "node:assert/strict";

import {
  buildComparisonTexts,
  buildDetailView,
  buildLogRows,
  buildMetricCards,
} from "../src/presenters.js";

test("metric presenter formats gateway summary payload for rendering", () => {
  const cards = buildMetricCards({
    total_requests: 8,
    average_latency_ms: 321.4,
    p95_latency_ms: 912.2,
    error_rate: 0.125,
    total_cost: 1.23456,
  });

  assert.deepEqual(cards, [
    { label: "Total Requests", value: 8 },
    { label: "Avg Latency", value: "321 ms" },
    { label: "P95 Latency", value: "912 ms" },
    { label: "Error Rate", value: "12.5%" },
    { label: "Total Cost", value: "$1.2346" },
  ]);
});

test("log, detail, and compare presenters shape data for the dashboard panels", () => {
  const rows = buildLogRows([
    { request_id: "req-1", model: "gpt-4o-mini", status: "success", preview: "preview text" },
  ]);
  const detail = buildDetailView({
    feature: "status-summary",
    latency_ms: 321,
    total_cost: 0.003,
    system_prompt: "You are a helpful assistant.",
    input_messages: [{ role: "user", content: "Summarize the outage" }],
    output_messages: [{ role: "assistant", content: "The outage impacted auth for 12 minutes." }],
  });
  const comparison = buildComparisonTexts({
    left_text: "left output",
    right_text: "right output",
  });

  assert.deepEqual(rows, [
    {
      requestId: "req-1",
      model: "gpt-4o-mini",
      status: "success",
      preview: "preview text",
    },
  ]);
  assert.equal(detail.feature, "status-summary");
  assert.equal(detail.latency, "321 ms");
  assert.equal(detail.cost, "$0.0030");
  assert.match(detail.inputMessages, /Summarize the outage/);
  assert.match(detail.outputMessages, /The outage impacted auth for 12 minutes/);
  assert.deepEqual(comparison, ["left output", "right output"]);
});
