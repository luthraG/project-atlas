#!/usr/bin/env bash
# Generates a fresh parking-lot log in ./logs/parking-lot.log: installs the backend's
# requirements into ./.venv (Python 3.12) and replays one business day against the app,
# in-process on a throwaway SQLite database. Nothing leaves this machine. Any previous
# log moves to ./logs/archive/.
#
#   ./run.sh                     # the default day and seed
#   ./run.sh --day 2026-10-05 --seed 7
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
PYTHON="${PYTHON:-python3.12}"
[[ -x .venv/bin/python ]] || "$PYTHON" -m venv .venv
.venv/bin/pip install -q -r ../upstream/requirements.txt
.venv/bin/python generate_logs.py "$@"
