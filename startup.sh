#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:-}:/home/site/wwwroot/src"
python -m uvicorn regauto.dashboard.api:app --host 0.0.0.0 --port "${PORT:-8000}"
