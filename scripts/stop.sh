#!/usr/bin/env bash
# Stop a running Aegis instance (started via start.sh).
set -euo pipefail
PORT="${AEGIS_PORT:-8777}"
PID="$(lsof -ti tcp:"$PORT" 2>/dev/null || true)"
if [ -z "$PID" ]; then
  echo "Aegis is not running on port $PORT."
  exit 0
fi
echo "Stopping Aegis (pid $PID)…"
kill "$PID"
echo "Stopped."
