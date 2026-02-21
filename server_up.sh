#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BACKEND_PID=""
cleanup() {
  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "Stopping backend (PID $BACKEND_PID)..."
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  exit 0
}
trap cleanup EXIT INT TERM

# Activate cactus venv for backend (Python, cactus, google-genai)
if [ -f "cactus/venv/bin/activate" ]; then
  source cactus/venv/bin/activate
fi

# Ensure backend deps (uvicorn, fastapi, etc.) are installed
pip install -r backend/requirements.txt -q

echo "Starting backend on http://localhost:8000 ..."
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Give backend a moment to bind
sleep 2

echo "Starting frontend on http://localhost:3000 ..."
cd frontend && npm run dev
