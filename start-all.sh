#!/bin/zsh

# Synergy Screen Monitor - Complete Setup & Start with Live Monitoring
# One command to install watchdog, start services, and watch output

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

# Stop any existing instances first
echo "Cleaning up existing instances..."
./stop.sh 2>/dev/null || true
sleep 1

# Start services in background
echo "Starting services..."
echo ""

# Load config
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

SYNERGY_LOG_PATH=${SYNERGY_LOG_PATH:-"$HOME/Library/Logs/Synergy/synergy.log"}
MQTT_BROKER=${MQTT_BROKER:-"localhost"}
MQTT_PORT=${MQTT_PORT:-"1883"}
MQTT_TOPIC=${MQTT_TOPIC:-"synergy"}
MQTT_CLIENT_TYPE=${MQTT_CLIENT_TYPE:-"nanomq"}
TARGET_DESKTOP=${TARGET_DESKTOP:-""}

# Start waldo (log monitor) in background
tail -F "$SYNERGY_LOG_PATH" | python3 ./waldo.py --broker "$MQTT_BROKER" --port "$MQTT_PORT" --topic "$MQTT_TOPIC" --client-type "$MQTT_CLIENT_TYPE" 2>/dev/null &
WALDO_PID=$!

# Start found-him (alert) in background if TARGET_DESKTOP is set
if [ -n "$TARGET_DESKTOP" ]; then
    python3 ./found-him.py "$TARGET_DESKTOP" --broker "$MQTT_BROKER" --port "$MQTT_PORT" --topic "$MQTT_TOPIC" --client-type "$MQTT_CLIENT_TYPE" 2>/dev/null &
    FOUND_HIM_PID=$!
fi

sleep 2

echo "✓ Services started (watchdog monitoring enabled)"
echo ""

# Monitor Synergy log and show desktop switches in real-time
# Extract just the base name (everything before the first dash)
tail -F "$SYNERGY_LOG_PATH" | grep --line-buffered "switch from" | sed -u -E 's/.*to "([^-]+).*/\1/' | while read desktop; do
    echo "$desktop"
done
