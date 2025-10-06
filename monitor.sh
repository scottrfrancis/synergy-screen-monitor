#!/bin/zsh

# Synergy Screen Monitor - Live Desktop Monitor
# Shows desktop switches in real-time

echo "=== Live Desktop Switching Monitor ==="
echo "Watching for desktop changes..."
echo ""

# Follow Synergy log and extract desktop names
tail -F /Users/scottfrancis/Library/Logs/Synergy/synergy.log | \
  grep --line-buffered "switch from" | \
  sed -u -E 's/.*to "([^"]+)".*/→ \1/' | \
  while read line; do
    echo "[$(date '+%H:%M:%S')] $line"
  done
