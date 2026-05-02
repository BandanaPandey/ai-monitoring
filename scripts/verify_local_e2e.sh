#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POSTGRES_DSN="${POSTGRES_DSN:-postgresql://$(whoami)@127.0.0.1:55432/aimonitor}"
CLICKHOUSE_HTTP_URL="${CLICKHOUSE_HTTP_URL:-http://127.0.0.1:58123}"
GATEWAY_URL="${GATEWAY_URL:-http://127.0.0.1:8000}"
INGEST_URL="${INGEST_URL:-http://127.0.0.1:8001}"
REQUEST_ID="${REQUEST_ID:-verify-$(date +%s)}"
LOGIN_EMAIL="${LOGIN_EMAIL:-admin@example.com}"
LOGIN_PASSWORD="${LOGIN_PASSWORD:-changeme}"
API_KEY="${API_KEY:-demo-ingest-key}"
VERIFY_WAIT_SECONDS="${VERIFY_WAIT_SECONDS:-15}"

poll_until() {
  local description="$1"
  local command="$2"
  local attempts="${3:-$VERIFY_WAIT_SECONDS}"

  for _ in $(seq 1 "$attempts"); do
    if eval "$command" >/dev/null 2>&1; then
      echo "$description"
      return 0
    fi
    sleep 1
  done

  echo "Timed out waiting for: $description" >&2
  return 1
}

echo "Checking Postgres availability..."
psql "$POSTGRES_DSN" -Atqc 'select 1' >/dev/null

echo "Checking ClickHouse availability..."
curl -fsS "$CLICKHOUSE_HTTP_URL/?query=SELECT%201" >/dev/null

echo "Checking gateway health..."
curl -fsS "$GATEWAY_URL/healthz" >/dev/null

echo "Checking ingest health..."
curl -fsS "$INGEST_URL/healthz" >/dev/null

echo "Authenticating through gateway..."
LOGIN_RESPONSE="$(curl -fsS -X POST "$GATEWAY_URL/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$LOGIN_EMAIL\",\"password\":\"$LOGIN_PASSWORD\"}")"
TOKEN="$(
  LOGIN_RESPONSE="$LOGIN_RESPONSE" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["LOGIN_RESPONSE"])
print(payload["access_token"])
PY
)"

echo "Ingesting sample request $REQUEST_ID..."
INGEST_RESPONSE="$(curl -fsS -X POST "$INGEST_URL/v1/logs" \
  -H 'Content-Type: application/json' \
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
    \"user_id\": \"verify-user\"
  }")"

INGEST_RESPONSE="$INGEST_RESPONSE" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["INGEST_RESPONSE"])
assert payload["accepted"] is True
assert "request_id" in payload
PY

poll_until \
  "Raw ClickHouse log is visible." \
  "curl -fsS \"$CLICKHOUSE_HTTP_URL/?query=SELECT%20request_id%20FROM%20llm_logs%20WHERE%20request_id%20%3D%20%27$REQUEST_ID%27%20FORMAT%20TabSeparatedRaw\" | grep -qx \"$REQUEST_ID\""

echo "Running processor..."
"$ROOT_DIR/scripts/run_local_processor_once.sh" >/dev/null

poll_until \
  "Gateway logs search reflects the ingested request." \
  "curl -fsS \"$GATEWAY_URL/v1/logs?search=$REQUEST_ID\" -H \"Authorization: Bearer $TOKEN\" | python3 -c \"import json,sys; payload=json.load(sys.stdin); assert any(item['request_id']=='$REQUEST_ID' for item in payload['items'])\""

poll_until \
  "Gateway summary reflects processed data." \
  "curl -fsS \"$GATEWAY_URL/v1/dashboard/summary\" -H \"Authorization: Bearer $TOKEN\" | python3 -c \"import json,sys; payload=json.load(sys.stdin); assert payload['total_requests'] >= 1 and payload['total_cost'] >= 0.003\""

echo "Fetching summary and logs..."
SUMMARY_RESPONSE="$(curl -fsS "$GATEWAY_URL/v1/dashboard/summary" -H "Authorization: Bearer $TOKEN")"
LOGS_RESPONSE="$(curl -fsS "$GATEWAY_URL/v1/logs?search=$REQUEST_ID" -H "Authorization: Bearer $TOKEN")"

SUMMARY_RESPONSE="$SUMMARY_RESPONSE" LOGS_RESPONSE="$LOGS_RESPONSE" REQUEST_ID="$REQUEST_ID" python3 - <<'PY'
import json
import os

summary = json.loads(os.environ["SUMMARY_RESPONSE"])
logs = json.loads(os.environ["LOGS_RESPONSE"])
request_id = os.environ["REQUEST_ID"]

assert summary["total_requests"] >= 1
assert isinstance(summary["total_cost"], (int, float))
assert logs["total"] >= 1
assert any(item["request_id"] == request_id for item in logs["items"]), logs
PY

echo "E2E verification passed for request: $REQUEST_ID"
