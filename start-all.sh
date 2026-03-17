#!/bin/zsh

# Synergy Screen Monitor - Complete Setup & Start with Live Monitoring
# One command to install watchdog, start services, and watch output
#
# This script adds watchdog installation and live display on top of start.sh.
# All service startup logic lives in start.sh (single source of truth).

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Synergy Screen Monitor - Start & Watch ==="
echo ""

# Check if watchdog is already installed
if ! launchctl list 2>/dev/null | grep -q "com.synergy.watchdog"; then
    echo "Installing watchdog service..."
    ./install-watchdog.sh
    echo ""
else
    echo "✓ Watchdog service already installed"
fi

# Delegate all service startup to start.sh (runs in background)
./start.sh &
START_PID=$!
sleep 2

echo "✓ Services started (watchdog monitoring enabled)"
echo ""

# Load config only for the display log path
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi
SYNERGY_LOG_PATH=${SYNERGY_LOG_PATH:-"$HOME/Library/Logs/Synergy/synergy.log"}

# Live display: show desktop switches from waldo's stdout
# waldo.py already parses and prints desktop names, but it runs in a pipe.
# So we grep the Synergy log for switch events and show the target desktop.
# The hex hash suffix (e.g., "studio-77773e4b") is stripped to show clean names.
tail -F "$SYNERGY_LOG_PATH" | grep --line-buffered "switch from" | sed -u -E 's/.*to "([^"]+)".*/\1/' | sed -u -E 's/-[0-9a-f]{8}$//' | while read desktop; do
    echo "$desktop"
done
