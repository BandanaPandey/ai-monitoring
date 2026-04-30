#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export PROCESSOR_MODE="${PROCESSOR_MODE:-clickhouse}"
export PROCESSOR_POSTGRES_DSN="${PROCESSOR_POSTGRES_DSN:-postgresql://$(whoami)@127.0.0.1:55432/aimonitor}"
export PROCESSOR_CLICKHOUSE_DSN="${PROCESSOR_CLICKHOUSE_DSN:-clickhouse://127.0.0.1:58123}"

exec "$ROOT_DIR/.venv/bin/python" -m processor.main run-once
