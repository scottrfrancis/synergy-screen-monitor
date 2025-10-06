#!/bin/zsh

# Synergy Screen Monitor - Watchdog Uninstallation Script
# Removes watchdog launchd service

set -e

PLIST_NAME="com.synergy.watchdog.plist"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"
PLIST_DEST="$LAUNCHD_DIR/$PLIST_NAME"

echo "=== Synergy Watchdog Uninstallation ==="
echo ""

# Check if service is loaded
if launchctl list | grep -q "com.synergy.watchdog"; then
    echo "Stopping watchdog service..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    sleep 1
else
    echo "Watchdog service is not running"
fi

# Remove plist file
if [ -f "$PLIST_DEST" ]; then
    echo "Removing service configuration..."
    rm "$PLIST_DEST"
    echo "✓ Watchdog service uninstalled"
else
    echo "Service configuration not found (already removed)"
fi

echo ""
echo "Note: Services managed by the watchdog (waldo.py, found-him.py) are still running."
echo "To stop them, run: ./stop.sh"
