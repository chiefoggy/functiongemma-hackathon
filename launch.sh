#!/bin/bash

# Launch script for Deep-Focus webapp
# This script starts both the backend and frontend servers

set -e

echo "🚀 Launching Deep-Focus Webapp..."
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "backend/main.py" ] || [ ! -f "frontend/package.json" ]; then
    echo -e "${RED}❌ Error: Please run this script from the project root directory${NC}"
    exit 1
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Error: Python 3 is not installed${NC}"
    exit 1
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Error: Node.js is not installed${NC}"
    exit 1
fi

# Check if backend dependencies are installed
echo -e "${YELLOW}📦 Checking backend dependencies...${NC}"
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Backend dependencies not found. Installing...${NC}"
    pip3 install -r backend/requirements.txt
else
    echo -e "${GREEN}✅ Backend dependencies OK${NC}"
fi

# Check if frontend dependencies are installed
echo -e "${YELLOW}📦 Checking frontend dependencies...${NC}"
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}⚠️  Frontend dependencies not found. Installing...${NC}"
    cd frontend
    npm install
    cd ..
else
    echo -e "${GREEN}✅ Frontend dependencies OK${NC}"
fi

# Check for .env file
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
    if [ -f ".env.sample" ]; then
        echo -e "${YELLOW}   Copying .env.sample to .env...${NC}"
        cp .env.sample .env
        echo -e "${YELLOW}   Please edit .env and add your GEMINI_API_KEY${NC}"
    fi
fi

# Check for GEMINI_API_KEY
if ! grep -q "GEMINI_API_KEY" .env 2>/dev/null || grep -q "GEMINI_API_KEY=$" .env 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Warning: GEMINI_API_KEY not set in .env${NC}"
    echo -e "${YELLOW}   Cloud features may not work. You can set it later.${NC}"
fi

echo ""
echo -e "${GREEN}🎯 Starting servers...${NC}"
echo ""
echo -e "${YELLOW}Backend will run on: http://localhost:8000${NC}"
echo -e "${YELLOW}Frontend will run on: http://localhost:3000${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop both servers${NC}"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Shutting down servers...${NC}"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    exit
}

trap cleanup SIGINT SIGTERM

# Start backend
echo -e "${GREEN}▶️  Starting backend server...${NC}"
cd "$(dirname "$0")"
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait a bit for backend to start
sleep 2

# Start frontend
echo -e "${GREEN}▶️  Starting frontend server...${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!

# Wait for both processes
wait
