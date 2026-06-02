# Setup script for Reachy Mini MCP Server (Windows PowerShell)

Write-Host "🤖 Reachy Mini MCP Server Setup" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Check Python version
Write-Host "Checking Python version..."
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Found $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Error: Python is not installed" -ForegroundColor Red
    exit 1
}

# Check if git-lfs is installed
Write-Host ""
Write-Host "Checking for git-lfs..."
try {
    $gitLfsVersion = git-lfs --version 2>&1
    Write-Host "✓ git-lfs is installed" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Warning: git-lfs is not installed" -ForegroundColor Yellow
    Write-Host "   Reachy Mini requires git-lfs for downloading models" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "   Download from: https://git-lfs.github.com/" -ForegroundColor Yellow
    Write-Host ""
    $continue = Read-Host "Continue anyway? (y/n)"
    if ($continue -ne "y" -and $continue -ne "Y") {
        exit 1
    }
}

# Create virtual environment
Write-Host ""
Write-Host "Creating virtual environment..."
if (Test-Path ".venv") {
    Write-Host "⚠️  .venv already exists" -ForegroundColor Yellow
    $recreate = Read-Host "Recreate it? (y/n)"
    if ($recreate -eq "y" -or $recreate -eq "Y") {
        Remove-Item -Recurse -Force .venv
        python -m venv .venv
        Write-Host "✓ Virtual environment recreated" -ForegroundColor Green
    }
} else {
    python -m venv .venv
    Write-Host "✓ Virtual environment created" -ForegroundColor Green
}

# Activate virtual environment
Write-Host ""
Write-Host "Activating virtual environment..."
& .\.venv\Scripts\Activate.ps1

# Upgrade pip
Write-Host ""
Write-Host "Upgrading pip..."
python -m pip install --upgrade pip

# Install the package (editable) with the server + TTS extras
Write-Host ""
Write-Host "Installing reachy-mini-mcp (editable, with [server,tts] extras)..."
pip install -e ".[server,tts]"

# Optional: Install simulation dependencies
Write-Host ""
$installMujoco = Read-Host "Install MuJoCo simulation dependencies? (y/n)"
if ($installMujoco -eq "y" -or $installMujoco -eq "Y") {
    Write-Host "Installing MuJoCo dependencies..."
    pip install reachy-mini[mujoco]
    Write-Host "✓ MuJoCo dependencies installed" -ForegroundColor Green
}

# Optional: Install development dependencies
Write-Host ""
$installDev = Read-Host "Install development dependencies? (y/n)"
if ($installDev -eq "y" -or $installDev -eq "Y") {
    Write-Host "Installing development dependencies..."
    pip install reachy-mini[dev]
    Write-Host "✓ Development dependencies installed" -ForegroundColor Green
}

Write-Host ""
Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Activate the virtual environment:"
Write-Host "   .\.venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "2. Start the Reachy Mini daemon:"
Write-Host "   For simulation: reachy-mini-daemon --sim"
Write-Host "   For real robot: reachy-mini-daemon"
Write-Host ""
Write-Host "3. In a new terminal, start the MCP server:"
Write-Host "   reachy-mini-mcp serve        # or: python -m reachy_mini_mcp serve"
Write-Host ""
Write-Host "4. Register it with your MCP client:"
Write-Host "   reachy-mini-mcp show         # print the mcp.json snippet"
Write-Host "   reachy-mini-mcp install --client claude-desktop   # or claude-code / cursor"
Write-Host "   reachy-mini-mcp doctor       # verify the setup"
Write-Host ""


