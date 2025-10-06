#!/bin/zsh

# Synergy Screen Monitor - Watchdog Service
# Monitors service health and automatically restarts on failure

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment variables from .env file if it exists
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# Watchdog configuration
CHECK_INTERVAL=${WATCHDOG_CHECK_INTERVAL:-30}  # Check every 30 seconds
MAX_RESTART_ATTEMPTS=${WATCHDOG_MAX_RESTARTS:-3}  # Max restarts within window
RESTART_WINDOW=${WATCHDOG_RESTART_WINDOW:-300}  # 5 minute window
BROKER_CHECK_TIMEOUT=${WATCHDOG_BROKER_TIMEOUT:-5}  # Broker connectivity timeout

# Set defaults
ROLE=${ROLE:-"secondary"}
MQTT_BROKER=${MQTT_BROKER:-"localhost"}
MQTT_PORT=${MQTT_PORT:-"1883"}
LOG_DIR=${LOG_DIR:-"./logs"}

# Watchdog state
WATCHDOG_LOG="${LOG_DIR}/watchdog.log"
RESTART_HISTORY_FILE="${LOG_DIR}/watchdog_restarts.log"
PID_FILE="${LOG_DIR}/watchdog.pid"

# Ensure logs directory exists
mkdir -p "$LOG_DIR"

# Logging functions
log_info() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $1" | tee -a "$WATCHDOG_LOG"
}

log_warn() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARN] $1" | tee -a "$WATCHDOG_LOG"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $1" | tee -a "$WATCHDOG_LOG"
}

# Check if another watchdog instance is running
check_watchdog_instance() {
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        if ps -p "$OLD_PID" > /dev/null 2>&1; then
            log_error "Watchdog already running with PID $OLD_PID"
            exit 1
        else
            log_warn "Stale PID file found, removing"
            rm -f "$PID_FILE"
        fi
    fi

    # Write our PID
    echo $$ > "$PID_FILE"
}

# Cleanup on exit
cleanup() {
    log_info "Watchdog shutting down"
    rm -f "$PID_FILE"
}

trap cleanup EXIT INT TERM

# Check if MQTT broker is reachable
check_broker_availability() {
    if nc -zv -w "$BROKER_CHECK_TIMEOUT" "$MQTT_BROKER" "$MQTT_PORT" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Check if waldo.py is running (primary mode only)
check_waldo_running() {
    if [ "$ROLE" = "primary" ]; then
        if pgrep -f "python3 ./waldo.py" > /dev/null 2>&1; then
            return 0
        else
            return 1
        fi
    fi
    return 0  # Not needed for secondary
}

# Check if found-him.py is running
check_found_him_running() {
    if [ -n "$TARGET_DESKTOP" ] && [ "$TARGET_DESKTOP" != "" ]; then
        if pgrep -f "python3 ./found-him.py" > /dev/null 2>&1; then
            return 0
        else
            return 1
        fi
    fi
    return 0  # Not needed if no target desktop
}

# Check service health by examining recent log activity
check_service_health() {
    local service_name="$1"
    local log_file="${LOG_DIR}/${service_name}.log"

    if [ ! -f "$log_file" ]; then
        log_warn "$service_name log file not found: $log_file"
        return 1
    fi

    # Check for recent activity (within last 2 minutes)
    local recent_entries=$(tail -100 "$log_file" | grep -c "$(date '+%Y-%m-%d %H:%M')\|$(date -v-1M '+%Y-%m-%d %H:%M')" || echo "0")

    if [ "$recent_entries" -gt 0 ]; then
        return 0
    else
        log_warn "$service_name appears stalled (no recent log activity)"
        return 1
    fi
}

# Get restart count within the restart window
get_restart_count() {
    if [ ! -f "$RESTART_HISTORY_FILE" ]; then
        echo 0
        return
    fi

    local window_start=$(($(date +%s) - RESTART_WINDOW))
    local count=$(awk -v start="$window_start" '$1 >= start { count++ } END { print count+0 }' "$RESTART_HISTORY_FILE")
    echo "$count"
}

# Record restart attempt
record_restart() {
    echo "$(date +%s) $(date '+%Y-%m-%d %H:%M:%S')" >> "$RESTART_HISTORY_FILE"

    # Clean old entries (older than restart window)
    local window_start=$(($(date +%s) - RESTART_WINDOW))
    local temp_file="${RESTART_HISTORY_FILE}.tmp"
    awk -v start="$window_start" '$1 >= start' "$RESTART_HISTORY_FILE" > "$temp_file" 2>/dev/null || true
    mv "$temp_file" "$RESTART_HISTORY_FILE" 2>/dev/null || true
}

# Restart services
restart_services() {
    local reason="$1"

    log_warn "Restarting services: $reason"

    # Check restart throttling
    local restart_count=$(get_restart_count)
    if [ "$restart_count" -ge "$MAX_RESTART_ATTEMPTS" ]; then
        log_error "Too many restarts ($restart_count) within ${RESTART_WINDOW}s window. Throttling enabled."
        log_error "Manual intervention required. Run: ./stop.sh && ./start.sh"
        # Wait longer before next check
        sleep $((CHECK_INTERVAL * 3))
        return 1
    fi

    record_restart

    # Stop existing services
    log_info "Stopping existing services..."
    ./stop.sh >> "$WATCHDOG_LOG" 2>&1 || true
    sleep 2

    # Wait for broker if it's down
    if ! check_broker_availability; then
        log_warn "MQTT broker not available, waiting for it to come back online..."
        local wait_count=0
        local max_wait=60  # Wait up to 5 minutes (60 * 5s = 300s)

        while [ $wait_count -lt $max_wait ]; do
            sleep 5
            if check_broker_availability; then
                log_info "MQTT broker is back online"
                break
            fi
            wait_count=$((wait_count + 1))
        done

        if [ $wait_count -ge $max_wait ]; then
            log_error "MQTT broker still unavailable after 5 minutes"
            return 1
        fi
    fi

    # Start services
    log_info "Starting services..."
    ./start.sh >> "$WATCHDOG_LOG" 2>&1 &

    # Give services time to start
    sleep 5

    log_info "Services restarted successfully"
    return 0
}

# Main monitoring loop
monitor_services() {
    log_info "=== Synergy Watchdog Started ==="
    log_info "Role: $ROLE"
    log_info "MQTT Broker: $MQTT_BROKER:$MQTT_PORT"
    log_info "Check Interval: ${CHECK_INTERVAL}s"
    log_info "Max Restarts: $MAX_RESTART_ATTEMPTS per ${RESTART_WINDOW}s"

    local consecutive_failures=0
    local max_consecutive_failures=3

    while true; do
        # Check broker availability
        if ! check_broker_availability; then
            log_warn "MQTT broker unavailable at $MQTT_BROKER:$MQTT_PORT"
            consecutive_failures=$((consecutive_failures + 1))

            if [ $consecutive_failures -ge $max_consecutive_failures ]; then
                restart_services "MQTT broker unavailable for $((consecutive_failures * CHECK_INTERVAL))s"
                consecutive_failures=0
            fi
        else
            # Broker is available, check services
            local services_ok=true

            # Check waldo.py (primary only)
            if [ "$ROLE" = "primary" ]; then
                if ! check_waldo_running; then
                    log_error "waldo.py is not running"
                    services_ok=false
                fi
            fi

            # Check found-him.py (if target desktop configured)
            if [ -n "$TARGET_DESKTOP" ] && [ "$TARGET_DESKTOP" != "" ]; then
                if ! check_found_him_running; then
                    log_error "found-him.py is not running"
                    services_ok=false
                fi
            fi

            if [ "$services_ok" = false ]; then
                consecutive_failures=$((consecutive_failures + 1))

                if [ $consecutive_failures -ge $max_consecutive_failures ]; then
                    restart_services "Service process(es) not running"
                    consecutive_failures=0
                fi
            else
                # All checks passed
                if [ $consecutive_failures -gt 0 ]; then
                    log_info "Services recovered, resetting failure counter"
                fi
                consecutive_failures=0
            fi
        fi

        sleep "$CHECK_INTERVAL"
    done
}

# Main entry point
main() {
    check_watchdog_instance
    monitor_services
}

main
