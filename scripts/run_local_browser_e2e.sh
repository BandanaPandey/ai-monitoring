#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REQUEST_ID_ONE="${E2E_REQUEST_ID_ONE:-browser-e2e-1}"
REQUEST_ID_TWO="${E2E_REQUEST_ID_TWO:-browser-e2e-2}"
CHROME_EXECUTABLE_PATH="${CHROME_EXECUTABLE_PATH:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"

started_gateway=0
started_ingest=0
started_web=0
gateway_pid=""
ingest_pid=""
web_pid=""

cleanup() {
  if [ "$started_web" -eq 1 ] && [ -n "$web_pid" ]; then
    kill "$web_pid" >/dev/null 2>&1 || true
  fi
  if [ "$started_ingest" -eq 1 ] && [ -n "$ingest_pid" ]; then
    kill "$ingest_pid" >/dev/null 2>&1 || true
  fi
  if [ "$started_gateway" -eq 1 ] && [ -n "$gateway_pid" ]; then
    kill "$gateway_pid" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

wait_for_url() {
  local url="$1"
  local name="$2"
  for _ in $(seq 1 30); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "$name is ready."
      return 0
    fi
    sleep 1
  done

  echo "Timed out waiting for $name at $url" >&2
  return 1
}

ensure_service() {
  local check_url="$1"
  local name="$2"
  local command="$3"
  local pid_var="$4"
  local started_var="$5"

  if curl -fsS "$check_url" >/dev/null 2>&1; then
    echo "$name already running."
    return 0
  fi

  echo "Starting $name..."
  bash -lc "$command" >/tmp/"$name".log 2>&1 &
  local pid=$!
  printf -v "$pid_var" '%s' "$pid"
  printf -v "$started_var" '1'
  wait_for_url "$check_url" "$name"
}

"$ROOT_DIR/scripts/start_local_db_stack.sh"
ensure_service "http://127.0.0.1:8000/healthz" "gateway-api" "cd '$ROOT_DIR' && ./scripts/run_local_gateway.sh" gateway_pid started_gateway
ensure_service "http://127.0.0.1:8001/healthz" "ingest-api" "cd '$ROOT_DIR' && ./scripts/run_local_ingest_api.sh" ingest_pid started_ingest
ensure_service "http://127.0.0.1:5173" "web" "cd '$ROOT_DIR' && ./scripts/run_local_web.sh" web_pid started_web

"$ROOT_DIR/scripts/reset_local_data.sh"
REQUEST_ID="$REQUEST_ID_ONE" "$ROOT_DIR/scripts/send_sample_log.sh" >/dev/null
REQUEST_ID="$REQUEST_ID_TWO" "$ROOT_DIR/scripts/send_sample_log.sh" >/dev/null
"$ROOT_DIR/scripts/run_local_processor_once.sh" >/dev/null

(
  cd "$ROOT_DIR"
  CHROME_EXECUTABLE_PATH="$CHROME_EXECUTABLE_PATH" \
  E2E_REQUEST_ID_ONE="$REQUEST_ID_ONE" \
  E2E_REQUEST_ID_TWO="$REQUEST_ID_TWO" \
  npm --workspace services/web run test:e2e
)
