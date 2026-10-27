#!/bin/zsh

# Synergy Screen Monitor - Service Shutdown Script
# Cleanly stops all running waldo.py and found-him.py processes

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

echo "=== Synergy Screen Monitor - Stopping Services ==="

# Stop every process matching a pgrep pattern: TERM first, KILL if it lingers.
stop_matching() {
    local name="$1" pattern="$2" pids
    pids=$(pgrep -f "$pattern" || true)
    if [ -z "$pids" ]; then
        echo "No $name processes found"
        return 0
    fi
    echo "Stopping $name processes: $pids"
    echo "$pids" | xargs kill 2>/dev/null || true
    sleep 1

    pids=$(pgrep -f "$pattern" || true)
    if [ -n "$pids" ]; then
        echo "Force stopping remaining $name processes: $pids"
        echo "$pids" | xargs kill -9 2>/dev/null || true
    fi
}

stop_matching "waldo.py" "$WALDO_PATTERN"
stop_matching "found-him.py" "$FOUND_HIM_PATTERN"

echo "All services stopped"
