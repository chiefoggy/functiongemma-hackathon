#!/usr/bin/env bash
set -e

# Run from repo root (directory containing this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "===================================================="
echo " Starting Deep-Focus (OS Level Executive Assistant) "
echo "===================================================="

# Clone cactus repo if not present (submodule or direct clone)
if [ ! -d "cactus" ]; then
    echo "cactus not found. Cloning..."
    if [ -f ".gitmodules" ] && git submodule status cactus &>/dev/null; then
        git submodule update --init
    else
        git clone https://github.com/cactus-compute/cactus cactus
    fi
fi

# Create cactus venv and run setup if it doesn't exist (Step 3 + 4)
VENV_NEEDED=
if [ ! -f "cactus/venv/bin/activate" ]; then
    echo "Virtual environment not found. Running cactus setup (Step 3)..."
    (cd cactus && source ./setup && cd ..)
    VENV_NEEDED=1
fi

# Activate the virtual environment containing Cactus and dependencies
if [ -f "cactus/venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source cactus/venv/bin/activate
else
    echo "Error: Virtual environment not found at cactus/venv/bin/activate"
    exit 1
fi

# Step 4: build cactus Python bindings (after first-time setup)
if [ -n "$VENV_NEEDED" ]; then
    echo "Running cactus build --python (Step 4)..."
    cactus build --python
fi

# Step 5: download FunctionGemma model if not present
MODEL_DIR="cactus/weights/functiongemma-270m-it"
if [ ! -d "$MODEL_DIR" ] || [ -z "$(ls -A "$MODEL_DIR" 2>/dev/null)" ]; then
    echo "Model not found. Downloading (Step 5): google/functiongemma-270m-it..."
    cactus download google/functiongemma-270m-it --reconvert
else
    echo "Model already at $MODEL_DIR (Step 5 skipped)."
fi

# Step 8: ensure google-genai is installed (run every time, idempotent)
echo "Ensuring google-genai is installed (Step 8)..."
pip install google-genai -q

# Step 6/7 reminder: get cactus key from website and run cactus auth if needed
if ! cactus auth --check 2>/dev/null; then
    echo "Reminder: Get your key from https://cactuscompute.com/dashboard/api-keys then run: cactus auth"
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
