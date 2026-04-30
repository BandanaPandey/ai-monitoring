#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export INGEST_STORAGE_BACKEND="${INGEST_STORAGE_BACKEND:-clickhouse}"
export INGEST_POSTGRES_DSN="${INGEST_POSTGRES_DSN:-postgresql://$(whoami)@127.0.0.1:55432/aimonitor}"
export INGEST_CLICKHOUSE_DSN="${INGEST_CLICKHOUSE_DSN:-clickhouse://127.0.0.1:58123}"

exec "$ROOT_DIR/.venv/bin/uvicorn" ingest_api.app:app --host 127.0.0.1 --port 8001
