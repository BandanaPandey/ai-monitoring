#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:8001}"
API_KEY="${API_KEY:-demo-ingest-key}"
REQUEST_ID="${REQUEST_ID:-req-runtime-$(date +%s)}"

curl -sS -X POST "$API_URL/v1/logs" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d "{
    \"request_id\": \"$REQUEST_ID\",
    \"provider\": \"openai\",
    \"model\": \"gpt-4o-mini\",
    \"system_prompt\": \"You are a helpful assistant.\",
    \"input_messages\": [{\"role\": \"user\", \"content\": \"Summarize the outage\"}],
    \"output_messages\": [{\"role\": \"assistant\", \"content\": \"The outage impacted auth for 12 minutes.\"}],
    \"latency_ms\": 321,
    \"tokens\": {\"input\": 12, \"output\": 18},
    \"cost_total\": 0.003,
    \"feature\": \"status-summary\",
    \"user_id\": \"demo-user\"
  }"
echo
