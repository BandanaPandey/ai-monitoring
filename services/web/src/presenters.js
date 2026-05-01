export function buildMetricCards(summary) {
  if (!summary) {
    return [];
  }

  return [
    { label: "Total Requests", value: summary.total_requests },
    { label: "Avg Latency", value: `${Math.round(summary.average_latency_ms)} ms` },
    { label: "P95 Latency", value: `${Math.round(summary.p95_latency_ms)} ms` },
    { label: "Error Rate", value: `${(summary.error_rate * 100).toFixed(1)}%` },
    { label: "Total Cost", value: `$${summary.total_cost.toFixed(4)}` },
  ];
}

export function buildLogRows(logs) {
  return logs.map((log) => ({
    requestId: log.request_id,
    model: log.model,
    status: log.status,
    preview: log.preview,
  }));
}

export function buildDetailView(selectedLog) {
  if (!selectedLog) {
    return null;
  }

  return {
    feature: selectedLog.feature || "n/a",
    latency: `${selectedLog.latency_ms} ms`,
    cost: `$${selectedLog.total_cost.toFixed(4)}`,
    systemPrompt: selectedLog.system_prompt || "n/a",
    inputMessages: JSON.stringify(selectedLog.input_messages, null, 2),
    outputMessages: JSON.stringify(selectedLog.output_messages, null, 2),
  };
}

export function buildComparisonTexts(comparison) {
  if (!comparison) {
    return [];
  }
  return [comparison.left_text, comparison.right_text];
}
