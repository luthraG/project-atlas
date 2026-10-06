#!/usr/bin/env bash
# Generates a fresh openai-to-mcp log in ./logs/openai-to-mcp.log: builds the server in ../upstream,
# starts the Helpdesk API stand-in on 127.0.0.1 and drives the server with agent tool calls.
# Nothing leaves this machine. Any previous log moves to ./logs/archive/.
#
#   ./run.sh              # about 4 minutes of traffic
#   MINUTES=1 ./run.sh    # shorter
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
(cd ../upstream && npm ci --no-audit --no-fund && npm run build)
node generate-logs.mjs --minutes "${MINUTES:-4}"
