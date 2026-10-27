#!/bin/zsh

# Synergy Screen Monitor - live view of desktop switches straight from the
# Synergy log. No MQTT involved; useful to confirm the log path and format.
# Parsing is waldo.py's own (--dry-run), so this shows exactly what gets published.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
source ./common.sh

load_env
resolve_python
resolve_synergy_log_path

echo "=== Synergy Desktop Monitor ==="
echo "Watching $SYNERGY_LOG_PATH (Ctrl-C to stop)"
echo ""

exec "$PYTHON" ./waldo.py --dry-run < <(tail -F "$SYNERGY_LOG_PATH")
