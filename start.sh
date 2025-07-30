#!/bin/zsh

# Synergy Screen Monitor - Role-based startup script
# Supports both primary (log monitor) and secondary (alert only) deployment modes

set -e  # Exit on any error

# Load environment variables from .env file if it exists
if [ -f ".env" ]; then
    echo "Loading configuration from .env file..."
    export $(grep -v '^#' .env | xargs)
else
    echo "Warning: .env file not found. Using defaults or environment variables."
fi

# Set defaults if not provided
ROLE=${ROLE:-"secondary"}
MQTT_BROKER=${MQTT_BROKER:-"localhost"}
MQTT_PORT=${MQTT_PORT:-"1883"}
MQTT_TOPIC=${MQTT_TOPIC:-"synergy"}
MQTT_CLIENT_TYPE=${MQTT_CLIENT_TYPE:-"paho"}
LOG_DIR=${LOG_DIR:-"./logs"}
DEBUG_MODE=${DEBUG_MODE:-"false"}

# Ensure logs directory exists
mkdir -p "$LOG_DIR"

echo "=== Synergy Screen Monitor ==="
echo "Role: $ROLE"
echo "MQTT Broker: $MQTT_BROKER:$MQTT_PORT"
echo "MQTT Topic: $MQTT_TOPIC"

# Function to start services with proper error handling
start_service() {
    local service_name="$1"
    local command="$2"
    local background="$3"
    
    echo "Starting $service_name..."
    
    if [ "$background" = "true" ]; then
        if ! eval "$command > /dev/null 2>&1 &"; then
            echo "ERROR: Failed to start $service_name"
            exit 1
        fi
        echo "$service_name started in background (PID: $!)"
    else
        echo "Starting $service_name in foreground..."
        if ! eval "$command"; then
            echo "ERROR: $service_name failed"
            exit 1
        fi
    fi
}

# Role-based service startup
if [ "$ROLE" = "primary" ]; then
    echo "=== PRIMARY MODE: Running log monitor + optional local alerts ==="
    
    # Validate primary configuration
    if [ -z "$SYNERGY_LOG_PATH" ]; then
        echo "ERROR: SYNERGY_LOG_PATH must be set for primary machines"
        echo "Please check your .env file or set the environment variable"
        exit 1
    fi
    
    if [ ! -f "$SYNERGY_LOG_PATH" ]; then
        echo "ERROR: Synergy log file not found: $SYNERGY_LOG_PATH"
        echo "Please check your SYNERGY_LOG_PATH setting"
        exit 1
    fi
    
    echo "Monitoring Synergy log: $SYNERGY_LOG_PATH"
    
    # Start local alert service if target desktop is specified
    if [ -n "$TARGET_DESKTOP" ] && [ "$TARGET_DESKTOP" != "" ]; then
        echo "Starting local alert service for desktop: $TARGET_DESKTOP"
        local_alert_cmd="python3 ./found-him.py '$TARGET_DESKTOP' --broker '$MQTT_BROKER' --port '$MQTT_PORT' --topic '$MQTT_TOPIC' --client-type '$MQTT_CLIENT_TYPE'"
        if [ "$DEBUG_MODE" = "true" ]; then
            local_alert_cmd="$local_alert_cmd --debug"
        fi
        start_service "Local Alert Service" "$local_alert_cmd" "true"
    fi
    
    # Start log monitor (foreground)
    waldo_cmd="tail -F '$SYNERGY_LOG_PATH' | python3 ./waldo.py --broker '$MQTT_BROKER' --port '$MQTT_PORT' --topic '$MQTT_TOPIC' --client-type '$MQTT_CLIENT_TYPE'"
    if [ "$DEBUG_MODE" = "true" ]; then
        waldo_cmd="tail -F '$SYNERGY_LOG_PATH' | python3 ./waldo.py --broker '$MQTT_BROKER' --port '$MQTT_PORT' --topic '$MQTT_TOPIC' --client-type '$MQTT_CLIENT_TYPE' --debug"
    fi
    start_service "Log Monitor Service (Waldo)" "$waldo_cmd" "false"
    
elif [ "$ROLE" = "secondary" ]; then
    echo "=== SECONDARY MODE: Running alert service only ==="
    
    # Validate secondary configuration
    if [ -z "$TARGET_DESKTOP" ] || [ "$TARGET_DESKTOP" = "" ]; then
        echo "ERROR: TARGET_DESKTOP must be set for secondary machines"
        echo "Please set TARGET_DESKTOP in your .env file or environment"
        echo "Example: TARGET_DESKTOP=studio"
        exit 1
    fi
    
    echo "Monitoring for desktop: $TARGET_DESKTOP"
    
    # Start alert service (foreground)
    found_him_cmd="python3 ./found-him.py '$TARGET_DESKTOP' --broker '$MQTT_BROKER' --port '$MQTT_PORT' --topic '$MQTT_TOPIC' --client-type '$MQTT_CLIENT_TYPE'"
    if [ "$DEBUG_MODE" = "true" ]; then
        found_him_cmd="$found_him_cmd --debug"
    fi
    start_service "Alert Service (Found-Him)" "$found_him_cmd" "false"
    
else
    echo "ERROR: Invalid ROLE: $ROLE"
    echo "ROLE must be either 'primary' or 'secondary'"
    echo "Please check your .env file or environment variables"
    exit 1
fi