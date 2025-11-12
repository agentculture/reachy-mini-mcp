#!/bin/bash
# Start script for OpenAI-compatible robot control server

echo "=========================================="
echo "Reachy Mini OpenAI-Compatible API Server"
echo "=========================================="
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  No .env file found"
    echo "   Creating from .env.openai.example..."
    cp .env.openai.example .env
    echo "   ✓ Created .env file"
    echo "   Please edit .env with your configuration"
    echo ""
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "⚠️  No virtual environment found"
    echo "   Creating virtual environment..."
    python3 -m venv .venv
    echo "   ✓ Virtual environment created"
    echo ""
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Install/upgrade dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements-openai.txt
echo "✓ Dependencies installed"
echo ""

# Check if Reachy daemon is running
echo "Checking Reachy Mini daemon..."
if curl -s http://localhost:8000/api/state/full > /dev/null 2>&1; then
    echo "✓ Reachy Mini daemon is running"
else
    echo "⚠️  Reachy Mini daemon not detected on localhost:8000"
    echo "   Please start it with: reachy-mini-daemon"
    echo ""
fi

# Start the server
echo ""
echo "=========================================="
echo "Starting OpenAI-compatible API server..."
echo "=========================================="
echo ""
echo "Server will be available at:"
echo "  http://localhost:8100"
echo ""
echo "Endpoints:"
echo "  GET  /              - API information"
echo "  GET  /tools         - List available tools"
echo "  POST /execute_tool  - Execute a tool"
echo "  POST /v1/chat/completions - Chat completions"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python server_openai.py
