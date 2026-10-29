#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -x "$ROOT/.venv/bin/python" ]]; then PYTHON_BIN="$ROOT/.venv/bin/python"; elif [[ -x "$ROOT/venv/bin/python" ]]; then PYTHON_BIN="$ROOT/venv/bin/python"; else PYTHON_BIN="$(command -v python3 || command -v python)"; fi
echo "Starting AutoTops Operations Dashboard..."
echo "Open: http://127.0.0.1:8000"
exec "$PYTHON_BIN" dashboard/server.py
