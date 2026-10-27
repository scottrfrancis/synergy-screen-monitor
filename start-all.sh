#!/bin/zsh

# Synergy Screen Monitor - Complete Setup & Start with Live Monitoring
# One command to (re)install the watchdog, start services, and watch output
#
# All service startup logic lives in start.sh (single source of truth).
# waldo.py prints each destination desktop as it publishes, so running
# start.sh in the foreground is the live display.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Synergy Screen Monitor - Start & Watch ==="
echo ""

# Always run the installer: it is idempotent, and it refreshes the copy of the
# runtime that launchd runs from (~/.local/share/synergy-monitor), so the
# watchdog never restarts stale code after an edit here.
./install-watchdog.sh
echo ""

echo "Starting services in the foreground. Ctrl-C stops this view;"
echo "the watchdog restarts the services from its own copy within ~90s."
echo ""
exec ./start.sh
