#!/usr/bin/env bash
# One-time setup when the codespace is created: install the backend and build the sandbox images.
set -euo pipefail
cd "$(dirname "$0")/.."

pip install --no-cache-dir -e ./backend

# The docker-in-docker daemon starts with the container; wait until it answers.
for _ in $(seq 1 60); do docker info >/dev/null 2>&1 && break; sleep 2; done
python -m investigator.sandbox.images
