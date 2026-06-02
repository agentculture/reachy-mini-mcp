#!/bin/bash
# Setup script for Reachy Mini MCP Server

set -e

echo "🤖 Reachy Mini MCP Server Setup"
echo "================================"
echo ""

# Check Python version
echo "Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
elif command -v python &> /dev/null; then
    PYTHON_CMD=python
else
    echo "❌ Error: Python is not installed"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
echo "✓ Found Python $PYTHON_VERSION"

# Check if git-lfs is installed (required for reachy-mini)
echo ""
echo "Checking for git-lfs..."
if ! command -v git-lfs &> /dev/null; then
    echo "⚠️  Warning: git-lfs is not installed"
    echo "   Reachy Mini requires git-lfs for downloading models"
    echo ""
    echo "   Install it with:"
    echo "   - macOS: brew install git-lfs"
    echo "   - Linux: sudo apt install git-lfs"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✓ git-lfs is installed"
fi

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ -d ".venv" ]; then
    echo "⚠️  .venv already exists"
    read -p "Recreate it? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf .venv
        $PYTHON_CMD -m venv .venv
        echo "✓ Virtual environment recreated"
    fi
else
    $PYTHON_CMD -m venv .venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install the package (editable) with the server + TTS extras
echo ""
echo "Installing reachy-mini-mcp (editable, with [server,tts] extras)..."
pip install -e ".[server,tts]"

# Optional: Install simulation dependencies
echo ""
read -p "Install MuJoCo simulation dependencies? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Installing MuJoCo dependencies..."
    pip install reachy-mini[mujoco]
    echo "✓ MuJoCo dependencies installed"
fi

# Optional: Install development dependencies
echo ""
read -p "Install development dependencies? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Installing development dependencies..."
    pip install reachy-mini[dev]
    echo "✓ Development dependencies installed"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Activate the virtual environment:"
echo "   source .venv/bin/activate"
echo ""
echo "2. Start the Reachy Mini daemon:"
echo "   For simulation: reachy-mini-daemon --sim"
echo "   For real robot: reachy-mini-daemon"
echo ""
echo "3. In a new terminal, start the MCP server:"
echo "   reachy-mini-mcp serve        # or: python -m reachy_mini_mcp serve"
echo ""
echo "4. Register it with your MCP client:"
echo "   reachy-mini-mcp show         # print the mcp.json snippet"
echo "   reachy-mini-mcp install --client claude-desktop   # or claude-code / cursor"
echo "   reachy-mini-mcp doctor       # verify the setup"
echo ""


