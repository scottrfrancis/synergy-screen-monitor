#!/bin/zsh

# Synergy Screen Monitor - Watchdog Installation Script
# Installs watchdog as a launchd service for automatic startup

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.synergy.watchdog.plist"
PLIST_SOURCE="$SCRIPT_DIR/$PLIST_NAME"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"
PLIST_DEST="$LAUNCHD_DIR/$PLIST_NAME"

echo "=== Synergy Watchdog Installation ==="
echo ""

# Check if running as root
if [ "$(id -u)" = "0" ]; then
    echo "ERROR: Do not run this script as root/sudo"
    echo "The watchdog should run as your user account"
    exit 1
fi

# Create LaunchAgents directory if it doesn't exist
if [ ! -d "$LAUNCHD_DIR" ]; then
    echo "Creating LaunchAgents directory..."
    mkdir -p "$LAUNCHD_DIR"
fi

# Check if plist exists
if [ ! -f "$PLIST_SOURCE" ]; then
    echo "ERROR: Plist file not found: $PLIST_SOURCE"
    exit 1
fi

# Update plist paths if needed (template uses absolute paths)
echo "Preparing plist configuration..."
TEMP_PLIST="$PLIST_SOURCE.tmp"
sed "s|/Volumes/workspace/Synergy|$SCRIPT_DIR|g" "$PLIST_SOURCE" > "$TEMP_PLIST"

# Unload existing service if running
if launchctl list | grep -q "com.synergy.watchdog"; then
    echo "Stopping existing watchdog service..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    sleep 1
fi

# Copy plist to LaunchAgents
echo "Installing watchdog service..."
cp "$TEMP_PLIST" "$PLIST_DEST"
rm "$TEMP_PLIST"

# Load the service
echo "Starting watchdog service..."
launchctl load "$PLIST_DEST"

# Verify installation
sleep 2
if launchctl list | grep -q "com.synergy.watchdog"; then
    echo ""
    echo "✓ Watchdog service installed and started successfully!"
    echo ""
    echo "Service will now:"
    echo "  - Start automatically at login"
    echo "  - Monitor service health every 30 seconds"
    echo "  - Automatically restart failed services"
    echo "  - Wait for broker recovery before restarting"
    echo ""
    echo "Useful commands:"
    echo "  Check status:    launchctl list | grep synergy.watchdog"
    echo "  View logs:       tail -f $SCRIPT_DIR/logs/watchdog.log"
    echo "  Stop service:    ./uninstall-watchdog.sh"
    echo "  Manual restart:  launchctl kickstart -k gui/\$(id -u)/com.synergy.watchdog"
else
    echo ""
    echo "✗ Installation failed - service not running"
    echo "Check logs: cat $SCRIPT_DIR/logs/watchdog_stderr.log"
    exit 1
fi
