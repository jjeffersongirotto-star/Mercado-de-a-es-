#!/bin/bash
# Roda localmente em http://localhost:8000
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
.venv/bin/uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}
