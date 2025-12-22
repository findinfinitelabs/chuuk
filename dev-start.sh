#!/bin/bash

# Chuuk Dictionary - Start Development Servers
# This script starts both Flask backend and React frontend

echo "🏝️  Starting Chuuk Dictionary Development Environment..."
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Check if in correct directory
if [ ! -f "app.py" ]; then
    echo "❌ Error: Must run from project root directory"
    exit 1
fi

# Check if .venv exists
if [ ! -d ".venv" ]; then
    echo "${YELLOW}⚠️  Virtual environment not found. Creating .venv...${NC}"
    python3 -m venv .venv
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create virtual environment"
        exit 1
    fi
fi

echo "${BLUE}📦 Checking dependencies...${NC}"

# Install Python dependencies
echo "${YELLOW}⚠️  Installing/updating Python dependencies...${NC}"
./.venv/bin/python -m pip install -r requirements.txt > /dev/null 2>&1

# Check Node modules
if [ ! -d "frontend/node_modules" ]; then
    echo "${YELLOW}⚠️  Installing Node dependencies...${NC}"
    cd frontend && npm install && cd ..
fi

echo "${GREEN}✅ Dependencies ready${NC}"
echo ""

# Create logs directory if it doesn't exist
mkdir -p logs

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down servers..."
    kill $FLASK_PID 2>/dev/null
    kill $VITE_PID 2>/dev/null
    exit 0
}

trap cleanup INT TERM

# Start Flask backend using .venv
echo "${BLUE}🐍 Starting Flask backend on http://localhost:5002${NC}"
./.venv/bin/python app.py > logs/flask.log 2>&1 &
FLASK_PID=$!
sleep 2

# Check if Flask started successfully
if ! ps -p $FLASK_PID > /dev/null; then
    echo "❌ Failed to start Flask backend"
    echo "Check logs/flask.log for errors"
    cat logs/flask.log
    exit 1
fi

echo "${GREEN}✅ Flask backend running (PID: $FLASK_PID)${NC}"
echo ""

# Start Vite frontend
echo "${BLUE}⚛️  Starting React frontend on http://localhost:5173${NC}"
cd frontend
npm run dev > ../logs/vite.log 2>&1 &
VITE_PID=$!
cd ..
sleep 2

# Check if Vite started successfully
if ! ps -p $VITE_PID > /dev/null; then
    echo "❌ Failed to start React frontend"
    echo "Check logs/vite.log for errors"
    kill $FLASK_PID
    exit 1
fi

echo "${GREEN}✅ React frontend running (PID: $VITE_PID)${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "${GREEN}🎉 Development servers are running!${NC}"
echo ""
echo "📱 Frontend:  ${BLUE}http://localhost:5173${NC}"
echo "🔧 Backend:   ${BLUE}http://localhost:5002${NC}"
echo "📝 Flask logs: logs/flask.log"
echo "📝 Vite logs:  logs/vite.log"
echo ""
echo "Press Ctrl+C to stop both servers"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Wait for processes
wait
