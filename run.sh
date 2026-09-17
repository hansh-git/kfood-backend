#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements-dev.txt
[ -f .env ] || { cp .env.example .env; echo ".env 생성됨 — 키 입력 후 다시 실행하세요"; exit 0; }
echo "http://localhost:8000/docs"
python -m uvicorn app.main:app --reload
