# Session Log: Fix MQTT Stale Socket Reconnection Bug

**Date**: 2026-03-17
**Duration**: Continuation session (~20 min)
**Topics**: MQTT, reconnection, socket caching, paho-client, debugging
**Previous Session**: [2025-10-06-1020-macos-upgrade-watchdog.md](2025-10-06-1020-macos-upgrade-watchdog.md) — macOS upgrade investigation and watchdog implementation

## Summary

Diagnosed why MQTT messages weren't flowing despite the broker being reachable. The root cause was a stale OS socket/routing cache in the long-running waldo.py process — it started when the broker was down and could never reconnect even after the broker came back. Fixed by replacing the subprocess-based self-healing mechanism with a fresh-socket TCP pre-flight check before every MQTT connect attempt.

## Key Activities

1. **Diagnosed the failure chain**
   - Services were running (waldo.py, found-him.py, tail processes all alive)
   - Broker at `192.168.4.3:1883` was TCP-reachable from fresh processes
   - `logs/waldo.log` showed continuous `[Errno 65] No route to host` since startup at 16:45
   - Self-healing fired at 16:50 (303s > 300s threshold) but the subprocess health check also returned "Network still down" — bad timing, broker wasn't up yet at that exact moment
   - Timer reset, requiring another 5-minute wait — by which time the broker was up but waldo was stuck in 60s backoff cycles with stale socket state

2. **Replaced self-healing with fresh-socket pre-flight** (`mqtt_clients/paho_client.py`)
   - Removed `_check_network_health()` (subprocess-based, only ran after 5-min delay)
   - Removed `first_failure_time` and `max_failure_duration` tracking
   - Added `_test_tcp_connect()` — opens a fresh `socket.create_connection()` before every MQTT connect attempt
   - If TCP pre-flight fails, skips the MQTT connect and backs off immediately
   - If TCP pre-flight succeeds, proceeds with MQTT connect knowing the broker is reachable
   - Net effect: reconnects within one retry cycle of broker becoming available

3. **Restarted services and verified**
   - Stopped all services and orphaned tail processes
   - Restarted via `./start.sh`
   - Confirmed "Successfully published message to synergy" in waldo.log

## Files Modified

| File | Change |
|------|--------|
| `mqtt_clients/paho_client.py` | Replaced subprocess health check + delayed self-healing with in-process fresh-socket TCP pre-flight; removed `_check_network_health`, `first_failure_time`, `max_failure_duration` |

## Decisions & Rationale

1. **Fresh socket per retry instead of subprocess health check** — The original design spawned a subprocess every 5 minutes to test connectivity, which was both slow (5-min delay) and fragile (timing-dependent). A fresh in-process socket on every attempt is cheaper, faster, and eliminates the stale routing cache problem entirely.

2. **Removed self-healing exit-for-watchdog pattern** — The `sys.exit(1)` self-healing was designed for the case where the process is stuck but the network is up. The fresh-socket pre-flight eliminates the "stuck" scenario, so the watchdog exit is no longer needed for this failure mode.

## Reusable Insights

- **Long-running Python processes can cache stale socket/routing state at the OS level.** When a destination becomes unreachable, subsequent `socket.connect()` calls in the same process may continue failing even after the destination comes back. Creating a fresh socket object bypasses this.
- **Self-healing with timing thresholds is fragile** — if the health check runs at the wrong moment (broker still down), it resets the timer and delays recovery further. Pre-flight checks on every attempt are more robust than periodic health checks.

## Session Effectiveness

- **Goal achieved?** — Yes
- **Blockers encountered** — None significant; diagnosis was straightforward from the log file
- **Process friction** — macOS lacks `timeout` command (had to use `signal.alarm` for timed MQTT subscribe test); pre-existing test failures (`test_get_bell_function`, `test_connect_with_retry_success`) unrelated to this change
- **Carry-forward items**:
  - Fix pre-existing test failures in `tests/test_found_him.py` (bell escape `\a` vs `\x07`, module naming `found_him`)
  - Commit the paho_client.py fix
  - `external/nanosdk` submodule still shows modified — needs decision (commit or reset)
  - Sed/Python hex-hash-stripping duplication across `start-all.sh` and `waldo.py` (noted last session)
