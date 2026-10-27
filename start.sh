#!/bin/zsh

# Synergy Screen Monitor - Role-based startup script
# Supports both primary (log monitor) and secondary (alert only) deployment modes

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
source ./common.sh

# Load environment variables from .env file if it exists
if [ -f ".env" ]; then
    echo "Loading configuration from .env file..."
else
    echo "Warning: .env file not found. Using defaults or environment variables."
fi
load_env

# Set defaults if not provided
ROLE=${ROLE:-"secondary"}
MQTT_BROKER=${MQTT_BROKER:-"localhost"}
MQTT_PORT=${MQTT_PORT:-"1883"}
MQTT_TOPIC=${MQTT_TOPIC:-"synergy"}
MQTT_CLIENT_TYPE=${MQTT_CLIENT_TYPE:-"nanomq"}
LOG_DIR=${LOG_DIR:-"./logs"}
DEBUG_MODE=${DEBUG_MODE:-"false"}

# Pick an interpreter that can actually import paho-mqtt. Fails loud rather
# than launching services that die on their first import.
resolve_python
echo "Python: $PYTHON"

# Validate NanoMQ availability if selected
if [ "$MQTT_CLIENT_TYPE" = "nanomq" ]; then
    if ! "$PYTHON" -c "import nanomq_bindings" 2>/dev/null; then
        echo "Warning: NanoMQ bindings not available. Falling back to Paho client."
        echo "To build NanoMQ support, run: ./build.sh"
        MQTT_CLIENT_TYPE="paho"
    fi
fi

# Ensure logs directory exists
mkdir -p "$LOG_DIR"

# Whatever ends this script, take its children with it: the tail feeding
# waldo and the background alert service. Without this a dead waldo left
# tail -F running and the pipeline looked alive from the outside.
trap 'pkill -P $$ 2>/dev/null || true' EXIT

# Stop any existing instances before starting new ones
echo "Checking for existing service instances..."
WALDO_PIDS=$(pgrep -f "$WALDO_PATTERN" || true)
FOUND_HIM_PIDS=$(pgrep -f "$FOUND_HIM_PATTERN" || true)

if [ -n "$WALDO_PIDS" ] || [ -n "$FOUND_HIM_PIDS" ]; then
    echo "Found running services. Stopping them first..."
    ./stop.sh
    sleep 2
fi

echo "=== Synergy Screen Monitor ==="
echo "Role: $ROLE"
echo "MQTT Broker: $MQTT_BROKER:$MQTT_PORT"
echo "MQTT Topic: $MQTT_TOPIC"
echo "MQTT Client: $MQTT_CLIENT_TYPE"

# Function to start services with proper error handling
start_service() {
    local service_name="$1"
    local background="$2"
    shift 2
    local command=("$@")
    
    echo "Starting $service_name..."
    
    if [ "$background" = "true" ]; then
        "${command[@]}" > /dev/null 2>&1 &
        local pid=$!
        echo "$service_name started in background (PID: $pid)"
    else
        echo "Starting $service_name in foreground..."
        if ! "${command[@]}"; then
            echo "ERROR: $service_name failed"
            exit 1
        fi
    fi
}

# Role-based service startup
if [ "$ROLE" = "primary" ]; then
    echo "=== PRIMARY MODE: Running log monitor + optional local alerts ==="
    
    # Validate primary configuration
    resolve_synergy_log_path
    
    if [ ! -f "$SYNERGY_LOG_PATH" ]; then
        echo "ERROR: Synergy log file not found: $SYNERGY_LOG_PATH"
        echo "Please check your SYNERGY_LOG_PATH setting."
        echo "Synergy 3.8.4 writes synergy.jsonl; builds before it wrote synergy.log."
        exit 1
    fi
    
    echo "Monitoring Synergy log: $SYNERGY_LOG_PATH"
    
    # Start local alert service if target desktop is specified
    if [ -n "$TARGET_DESKTOP" ] && [ "$TARGET_DESKTOP" != "" ]; then
        echo "Starting local alert service for desktop: $TARGET_DESKTOP"
        local_alert_args=("$PYTHON" ./found-him.py "$TARGET_DESKTOP" --broker "$MQTT_BROKER" --port "$MQTT_PORT" --topic "$MQTT_TOPIC" --client-type "$MQTT_CLIENT_TYPE")
        if [ "$DEBUG_MODE" = "true" ]; then
            local_alert_args+=(--debug)
        fi
        start_service "Local Alert Service" "true" "${local_alert_args[@]}"
    fi
    
    # Start log monitor (foreground)
    waldo_args=("$PYTHON" ./waldo.py --broker "$MQTT_BROKER" --port "$MQTT_PORT" --topic "$MQTT_TOPIC" --client-type "$MQTT_CLIENT_TYPE")
    if [ "$DEBUG_MODE" = "true" ]; then
        waldo_args+=(--debug)
    fi
    
    echo "Starting Log Monitor Service (Waldo) in foreground..."
    # waldo is the foreground command, so its exit ends this script (set -e)
    # and the EXIT trap reaps the tail. A plain pipeline would block on tail.
    "${waldo_args[@]}" < <(tail -F "$SYNERGY_LOG_PATH")
    
elif [ "$ROLE" = "secondary" ]; then
    echo "=== SECONDARY MODE: Running alert service only ==="
    
    # Validate secondary configuration
    if [ -z "$TARGET_DESKTOP" ] || [ "$TARGET_DESKTOP" = "" ]; then
        echo "ERROR: TARGET_DESKTOP must be set for secondary machines"
        echo "Please set TARGET_DESKTOP in your .env file or environment"
        echo "Example: TARGET_DESKTOP=workstation"
        exit 1
    fi
    
    echo "Monitoring for desktop: $TARGET_DESKTOP"
    
    # Start alert service (foreground)
    found_him_args=("$PYTHON" ./found-him.py "$TARGET_DESKTOP" --broker "$MQTT_BROKER" --port "$MQTT_PORT" --topic "$MQTT_TOPIC" --client-type "$MQTT_CLIENT_TYPE")
    if [ "$DEBUG_MODE" = "true" ]; then
        found_him_args+=(--debug)
    fi
    start_service "Alert Service (Found-Him)" "false" "${found_him_args[@]}"
    
else
    echo "ERROR: Invalid ROLE: $ROLE"
    echo "ROLE must be either 'primary' or 'secondary'"
    echo "Please check your .env file or environment variables"
    exit 1
fi
