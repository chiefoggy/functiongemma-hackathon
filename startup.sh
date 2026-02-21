#!/bin/bash
set -e

echo "===================================================="
echo " Starting Deep-Focus (OS Level Executive Assistant) "
echo "===================================================="

# Activate the existing virtual environment containing Cactus and dependencies
if [ -f "cactus/venv/bin/activate" ]; then
    echo "Activting virtual environment..."
    source cactus/venv/bin/activate
else
    echo "Error: Virtual environment not found at cactus/venv/bin/activate"
    exit 1
fi

# Load environment variables if .env exists
if [ -f ".env" ]; then
    echo "Loading environment variables from .env..."
    export $(grep -v '^#' .env | xargs)
fi

# Ensure required API keys are present
if [ -z "$CACTUS_API_KEY" ]; then
    echo "Warning: CACTUS_API_KEY is not set. Local model execution may fail."
fi

if [ -z "$GEMINI_API_KEY" ]; then
    echo "Warning: GEMINI_API_KEY is not set. Cloud handoff will fail."
fi

echo "Starting FastAPI server on http://localhost:8000..."
python3 app.py
