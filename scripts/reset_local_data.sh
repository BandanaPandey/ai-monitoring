#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLICKHOUSE_HTTP_URL="${CLICKHOUSE_HTTP_URL:-http://127.0.0.1:58123}"
FILE_STORE_PATH="${FILE_STORE_PATH:-$ROOT_DIR/var/data/logs.jsonl}"
AGGREGATE_STORE_PATH="${AGGREGATE_STORE_PATH:-$ROOT_DIR/var/data/aggregates.json}"

if curl -fsS "$CLICKHOUSE_HTTP_URL/?query=SELECT%201" >/dev/null 2>&1; then
  curl -fsS "$CLICKHOUSE_HTTP_URL" --data-binary "TRUNCATE TABLE llm_logs" >/dev/null
  curl -fsS "$CLICKHOUSE_HTTP_URL" --data-binary "TRUNCATE TABLE llm_daily_metrics" >/dev/null
  curl -fsS "$CLICKHOUSE_HTTP_URL" --data-binary "TRUNCATE TABLE llm_error_groups" >/dev/null
  echo "Reset ClickHouse tables: llm_logs, llm_daily_metrics, llm_error_groups"
else
  echo "ClickHouse is not reachable at $CLICKHOUSE_HTTP_URL; skipping DB reset." >&2
fi

rm -f "$FILE_STORE_PATH" "$AGGREGATE_STORE_PATH"
echo "Removed file-backed stores if present."
