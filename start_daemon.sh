#!/bin/bash
# Startup wrapper for Reachy Mini Daemon with signal handling

# Function to handle shutdown signals
shutdown_handler() {
    echo ""
    echo "🛑 Received shutdown signal (Ctrl+C)..."
    /app/shutdown_daemon.sh
    exit 0
}

# Trap SIGTERM and SIGINT signals
trap shutdown_handler SIGTERM SIGINT

# Install dependencies
echo "📦 Installing dependencies..."
apt-get update -qq
apt-get install -y -qq portaudio*-dev libgl1
pip install --no-cache-dir -q -r /app/requirements.txt

# Start the daemon
echo "🤖 Starting Reachy Mini Daemon..."
echo "💡 Press Ctrl+C to shutdown gracefully"
reachy-mini-daemon &

# Store the daemon PID
DAEMON_PID=$!

# Wait for the daemon process
wait $DAEMON_PID
