#!/bin/zsh

# Synergy Screen Monitor - Watchdog Uninstallation Script
# Removes the watchdog launchd agent and its off-volume runtime copy.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

LABEL="com.synergy.watchdog"

echo "=== Synergy Watchdog Uninstallation ==="
echo ""

resolve_real_home
INSTALL_DIR="$REALHOME/.local/share/synergy-monitor"
PLIST_DEST="$REALHOME/Library/LaunchAgents/$LABEL.plist"

if launchctl list | grep -q "$LABEL"; then
    echo "Stopping watchdog service..."
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    sleep 1
else
    echo "Watchdog service is not running"
fi

if [ -f "$PLIST_DEST" ]; then
    echo "Removing service configuration..."
    rm "$PLIST_DEST"
fi

if [ -d "$INSTALL_DIR" ]; then
    echo "Removing runtime copy $INSTALL_DIR ..."
    rm -rf "$INSTALL_DIR"
fi

echo "✓ Watchdog service uninstalled"
echo ""
echo "Note: Services managed by the watchdog (waldo.py, found-him.py) are still running."
echo "To stop them, run: ./stop.sh"
