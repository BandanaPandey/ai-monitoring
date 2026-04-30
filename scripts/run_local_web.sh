#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export VITE_GATEWAY_API_URL="${VITE_GATEWAY_API_URL:-http://127.0.0.1:8000}"

cd "$ROOT_DIR/services/web"
exec npm run dev -- --host 127.0.0.1 --port 5173
