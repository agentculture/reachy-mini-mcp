#!/bin/bash
# Quick start script for Reachy Mini MCP Server

set -e

echo "🤖 Starting Reachy Mini MCP Server"
echo "===================================="
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "   Please run ./setup.sh first"
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Check if daemon is running
# Comment out
# Check if Reachy Mini daemon is running
#if curl -s http://localhost:8000/api/state/power > /dev/null 2>&1; then
#    echo "✓ Daemon is running"
#else
#    echo ""
#    echo "⚠️  Warning: Reachy Mini daemon is not running!"
#    echo ""
#    echo "Please start the daemon first:"
#    echo "  For simulation: reachy-mini-daemon --sim"
#    echo "  For real robot: reachy-mini-daemon"
#    echo ""
#    read -p "Start MCP server anyway? (y/n) " -n 1 -r
#    echo
#    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
#        exit 1
#    fi
#fi

echo ""
echo "Starting MCP server..."
echo ""
python -m reachy_mini_mcp serve


