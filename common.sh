#!/bin/zsh

# Synergy Screen Monitor - shared shell helpers.
# Source this file; do not run it. Every script that starts, stops, watches or
# installs the services uses these so there is one definition of each.

# pgrep -f patterns for the two services. They match whichever interpreter
# resolve_python picked (python3, a versioned python3.x, or /usr/bin/python3, which
# re-execs as the framework binary ".../MacOS/Python", capital P, as ps shows it).
WALDO_PATTERN='[Pp]ython[^ ]* \./waldo\.py'
FOUND_HIM_PATTERN='[Pp]ython[^ ]* \./found-him\.py'

# Set PYTHON to an interpreter that can import paho-mqtt.
#
# Honours an explicit PYTHON if it works. Otherwise tries python3 on PATH, then
# the Apple-shipped /usr/bin/python3. A Homebrew python3 upgrade moves the symlink
# to a fresh interpreter with no site-packages, which is how the services came to
# die at import time while "python3" still looked fine.
resolve_python() {
    local candidate
    if [ -n "$PYTHON" ]; then
        if "$PYTHON" -c "import paho.mqtt.client" 2>/dev/null; then
            return 0
        fi
        echo "ERROR: PYTHON=$PYTHON cannot import paho.mqtt.client" >&2
        echo "Install paho-mqtt there, or unset PYTHON to auto-detect." >&2
        return 1
    fi
    for candidate in python3 /usr/bin/python3; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "import paho.mqtt.client" 2>/dev/null; then
            PYTHON="$(command -v "$candidate")"
            export PYTHON
            return 0
        fi
    done
    echo "ERROR: no python3 on this machine can import paho.mqtt.client" >&2
    echo "Run: /usr/bin/python3 -m pip install paho-mqtt   (or set PYTHON)" >&2
    return 1
}

# Set REALHOME to the account's real home directory, never $HOME.
#
# Under a profile-scoped tool (Claude Code with ~/.claude-profiles/<p>) $HOME
# points at the profile dir. A LaunchAgent written there is never scanned at
# login: it installs "successfully" and does not survive a reboot.
resolve_real_home() {
    REALHOME="$(dscl . -read "/Users/$(id -un)" NFSHomeDirectory 2>/dev/null | awk '{print $2}')"
    [ -d "$REALHOME" ] || REALHOME="/Users/$(id -un)"
    [ -d "$REALHOME" ] || { echo "ERROR: cannot resolve a real home directory" >&2; return 1; }
    case "$REALHOME" in
        *.claude-profiles*) echo "ERROR: resolved a profile dir ($REALHOME), refusing" >&2; return 1 ;;
    esac
    export REALHOME
}

# Export the settings in ./.env, if there is one, into the environment.
load_env() {
    if [ -f ".env" ]; then
        set -a
        source .env
        set +a
    fi
}

# Set SYNERGY_LOG_PATH, keeping an explicit value and otherwise asking config.py
# for the platform default so the path is defined in exactly one place.
resolve_synergy_log_path() {
    if [ -z "$SYNERGY_LOG_PATH" ]; then
        [ -n "$PYTHON" ] || resolve_python || return 1
        SYNERGY_LOG_PATH="$("$PYTHON" -c 'from config import Config; print(Config.SYNERGY_LOG_PATH)')" || return 1
    fi
    export SYNERGY_LOG_PATH
}

# (Re)load a launchd user agent: bootout any existing job, wait until launchd
# has really dropped it, then bootstrap with retries. Usage: reload_launch_agent LABEL PLIST
#
# bootout returns before the job is gone, and a bootstrap issued in that window
# fails. bootstrap can also report EIO from a non-GUI session even when it
# registers, so the caller still checks launchctl list afterwards.
reload_launch_agent() {
    local label="$1" plist="$2" domain="gui/$(id -u)" i err
    launchctl bootout "$domain/$label" 2>/dev/null || true
    for i in 1 2 3 4 5 6 7 8 9 10; do
        launchctl print "$domain/$label" >/dev/null 2>&1 || break
        sleep 1
    done
    for i in 1 2 3 4 5; do
        if err="$(launchctl bootstrap "$domain" "$plist" 2>&1)"; then
            break
        fi
        if launchctl print "$domain/$label" >/dev/null 2>&1; then
            break   # registered despite the error (EIO from a non-GUI session)
        fi
        echo "bootstrap attempt $i failed: $err" >&2
        sleep 2
    done
    launchctl enable "$domain/$label" 2>/dev/null || true
    launchctl kickstart -k "$domain/$label" 2>/dev/null || true
}
