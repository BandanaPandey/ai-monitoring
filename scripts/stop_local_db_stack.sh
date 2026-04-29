#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/.runtime"
PG_DATA_DIR="$RUNTIME_DIR/postgres"
CLICKHOUSE_PID_FILE="$RUNTIME_DIR/clickhouse/clickhouse.pid"

if [ -f "$CLICKHOUSE_PID_FILE" ]; then
  CLICKHOUSE_PID="$(cat "$CLICKHOUSE_PID_FILE")"
  if kill -0 "$CLICKHOUSE_PID" >/dev/null 2>&1; then
    kill "$CLICKHOUSE_PID" >/dev/null 2>&1 || true
  fi
  rm -f "$CLICKHOUSE_PID_FILE"
fi

if [ -f "$PG_DATA_DIR/PG_VERSION" ]; then
  pg_ctl -D "$PG_DATA_DIR" stop -m fast >/dev/null 2>&1 || true
fi

echo "Local Postgres and ClickHouse runtime stopped."
