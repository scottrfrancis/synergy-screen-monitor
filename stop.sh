#!/bin/zsh

# Synergy Screen Monitor - Service Shutdown Script
# Cleanly stops all running waldo.py and found-him.py processes

set -e  # Exit on any error

echo "=== Synergy Screen Monitor - Stopping Services ==="

# Find and stop all waldo.py processes
WALDO_PIDS=$(pgrep -f "python3 ./waldo.py" || true)
if [ -n "$WALDO_PIDS" ]; then
    echo "Stopping waldo.py processes: $WALDO_PIDS"
    echo "$WALDO_PIDS" | xargs kill 2>/dev/null || true
    sleep 1

    # Force kill if still running
    WALDO_PIDS=$(pgrep -f "python3 ./waldo.py" || true)
    if [ -n "$WALDO_PIDS" ]; then
        echo "Force stopping remaining waldo.py processes: $WALDO_PIDS"
        echo "$WALDO_PIDS" | xargs kill -9 2>/dev/null || true
    fi
else
    echo "No waldo.py processes found"
fi

# Find and stop all found-him.py processes
FOUND_HIM_PIDS=$(pgrep -f "python3 ./found-him.py" || true)
if [ -n "$FOUND_HIM_PIDS" ]; then
    echo "Stopping found-him.py processes: $FOUND_HIM_PIDS"
    echo "$FOUND_HIM_PIDS" | xargs kill 2>/dev/null || true
    sleep 1

    # Force kill if still running
    FOUND_HIM_PIDS=$(pgrep -f "python3 ./found-him.py" || true)
    if [ -n "$FOUND_HIM_PIDS" ]; then
        echo "Force stopping remaining found-him.py processes: $FOUND_HIM_PIDS"
        echo "$FOUND_HIM_PIDS" | xargs kill -9 2>/dev/null || true
    fi
else
    echo "No found-him.py processes found"
fi

echo "All services stopped"
