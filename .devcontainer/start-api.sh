#!/usr/bin/env bash
# Runs on every codespace start: launches the API on port 8000 in the background.
# Log: /tmp/api.log
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -z "${APP_PASSWORD:-}" ]; then
  echo "APP_PASSWORD is not set (add it as a Codespaces secret). Not starting a public API without it." >&2
  exit 0
fi

pkill -f "uvicorn investigator.api.app:app" 2>/dev/null || true
# setsid + nohup: the server must outlive this start hook.
setsid nohup python -m uvicorn investigator.api.app:app --host 0.0.0.0 --port 8000 \
  > /tmp/api.log 2>&1 < /dev/null &
echo "API starting on :8000 (log: /tmp/api.log)"

# The hosted frontend calls this port from the internet, so it must be public (the API itself
# still requires APP_PASSWORD). Retried because port forwarding comes up a little after the server.
setsid nohup bash -c 'for _ in $(seq 1 60); do sleep 5;
  gh codespace ports visibility 8000:public -c "$CODESPACE_NAME" && break; done' \
  > /tmp/port.log 2>&1 < /dev/null &
