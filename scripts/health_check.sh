#!/usr/bin/env bash
# Quick health probe against a running Aegis.
set -euo pipefail
HOST="${AEGIS_HOST:-127.0.0.1}"
PORT="${AEGIS_PORT:-8777}"
curl -fsS "http://$HOST:$PORT/api/health" && echo || { echo "Aegis not responding."; exit 1; }
