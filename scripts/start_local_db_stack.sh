#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/.runtime"
PG_DATA_DIR="$RUNTIME_DIR/postgres"
PG_SOCKET_DIR="$RUNTIME_DIR/pgsocket"
LOG_DIR="$RUNTIME_DIR/logs"
PG_PORT="${PG_PORT:-55432}"
PG_DB="${PG_DB:-aimonitor}"
CLICKHOUSE_PATH="$RUNTIME_DIR/clickhouse"
CLICKHOUSE_HTTP_PORT="${CLICKHOUSE_HTTP_PORT:-58123}"
CLICKHOUSE_TCP_PORT="${CLICKHOUSE_TCP_PORT:-59000}"
CLICKHOUSE_PID_FILE="$CLICKHOUSE_PATH/clickhouse.pid"

mkdir -p "$PG_SOCKET_DIR" "$CLICKHOUSE_PATH" "$LOG_DIR"

if ! command -v postgres >/dev/null 2>&1; then
  echo "postgres not found. Install postgresql@18 or update PATH." >&2
  exit 1
fi

if ! command -v clickhouse >/dev/null 2>&1; then
  echo "clickhouse not found. Install ClickHouse or update PATH." >&2
  exit 1
fi

if [ ! -f "$PG_DATA_DIR/PG_VERSION" ]; then
  initdb -D "$PG_DATA_DIR" >/dev/null
fi

if ! pg_ctl -D "$PG_DATA_DIR" status >/dev/null 2>&1; then
  pg_ctl -D "$PG_DATA_DIR" -l "$LOG_DIR/postgres.log" -o "-p $PG_PORT -k $PG_SOCKET_DIR" start >/dev/null
fi

for _ in $(seq 1 30); do
  if psql "postgresql://$(whoami)@127.0.0.1:$PG_PORT/postgres" -Atqc "select 1" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

psql "postgresql://$(whoami)@127.0.0.1:$PG_PORT/postgres" -Atqc "select 1" >/dev/null

if ! psql -h "$PG_SOCKET_DIR" -p "$PG_PORT" -lqt | cut -d '|' -f 1 | tr -d ' ' | grep -qx "$PG_DB"; then
  createdb -h "$PG_SOCKET_DIR" -p "$PG_PORT" "$PG_DB"
fi

if ! TMPDIR=/tmp clickhouse client --host 127.0.0.1 --port "$CLICKHOUSE_TCP_PORT" --query "select 1" >/dev/null 2>&1; then
  nohup env TMPDIR=/tmp clickhouse server -- \
    --path="$CLICKHOUSE_PATH" \
    --http_port="$CLICKHOUSE_HTTP_PORT" \
    --tcp_port="$CLICKHOUSE_TCP_PORT" \
    --logger.log="$LOG_DIR/clickhouse.log" \
    --logger.errorlog="$LOG_DIR/clickhouse.err.log" \
    >"$LOG_DIR/clickhouse.stdout.log" 2>&1 &
  echo $! > "$CLICKHOUSE_PID_FILE"
fi

for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:$CLICKHOUSE_HTTP_PORT/?query=SELECT%201" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

curl -fsS "http://127.0.0.1:$CLICKHOUSE_HTTP_PORT/?query=SELECT%201" >/dev/null

echo "Postgres: postgres://$(whoami)@127.0.0.1:$PG_PORT/$PG_DB"
echo "ClickHouse TCP: 127.0.0.1:$CLICKHOUSE_TCP_PORT"
echo "ClickHouse HTTP: 127.0.0.1:$CLICKHOUSE_HTTP_PORT"
