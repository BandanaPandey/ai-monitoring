#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export GATEWAY_STORAGE_BACKEND="${GATEWAY_STORAGE_BACKEND:-clickhouse}"
export GATEWAY_POSTGRES_DSN="${GATEWAY_POSTGRES_DSN:-postgresql://$(whoami)@127.0.0.1:55432/aimonitor}"
export GATEWAY_CLICKHOUSE_DSN="${GATEWAY_CLICKHOUSE_DSN:-clickhouse://127.0.0.1:58123}"

exec "$ROOT_DIR/.venv/bin/uvicorn" gateway_api.app:app --host 127.0.0.1 --port 8000
