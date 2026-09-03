"""Publish an at-desk heartbeat derived from macOS HID idle time.

Companion to waldo.py. waldo publishes only when the Synergy screen *changes*,
which on a normal day means long silences: on 2026-09-03 there was a 2h01m gap
between publishes while Scott sat at the desk the whole time. Anything gating on
that signal has to guess.

This publishes what we actually want to know. `ioreg -c IOHIDSystem` exposes
HIDIdleTime, nanoseconds since the last keyboard or mouse event. The physical
keyboard and mouse hang off the Synergy server, so it registers input regardless
of which screen currently has focus.

The payload carries idle_seconds and a computed at_desk flag, so a consumer can
either trust the flag or apply its own threshold.

    python3 desk_presence.py --broker vault.local --topic desk/presence
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime

from mqtt_clients.factory import MQTTClientFactory
from config import Config, override_config

log_dir = Config.LOG_DIR
os.makedirs(log_dir, exist_ok=True)

file_handler = logging.FileHandler(os.path.join(log_dir, 'desk-presence.log'))
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(
    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)

console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.ERROR)
console_handler.setFormatter(
    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)

logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, console_handler])
logger = logging.getLogger('desk-presence')

IOREG_COMMAND = ["ioreg", "-c", "IOHIDSystem"]

# Seconds of no keyboard/mouse input before we call it "away". Reading a document
# at the desk is still being at the desk, so this is deliberately generous.
DEFAULT_IDLE_THRESHOLD = 900

# How often to publish. Well under the consumer's expire_after, so a couple of
# dropped messages don't read as the publisher having died.
DEFAULT_INTERVAL = 30

_HID_IDLE_RE = re.compile(r'"HIDIdleTime"\s*=\s*(\d+)')


def parse_hid_idle_ns(ioreg_output):
    """Extract HIDIdleTime (nanoseconds) from `ioreg -c IOHIDSystem` output.

    Returns None when the key is missing or malformed, which callers must treat
    as "unknown", never as "active".
    """
    if not ioreg_output:
        return None
    match = _HID_IDLE_RE.search(ioreg_output)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def idle_seconds(ns):
    """Convert nanoseconds to seconds. None passes through."""
    if ns is None:
        return None
    return ns / 1_000_000_000


def is_at_desk(idle_s, threshold=DEFAULT_IDLE_THRESHOLD):
    """True when input was seen more recently than `threshold` seconds ago.

    An unknown idle time is reported as away: a failed probe must never assert
    presence, or a broken publisher would pin the fan on.
    """
    if idle_s is None:
        return False
    return idle_s < threshold


def build_message(host, idle_s, threshold=DEFAULT_IDLE_THRESHOLD, now=None):
    """Build the JSON payload."""
    return json.dumps({
        'host': host,
        'idle_seconds': idle_s,
        'at_desk': is_at_desk(idle_s, threshold),
        'threshold_seconds': threshold,
        'timestamp': now if now is not None else datetime.now().isoformat(),
    })


def read_idle_seconds():
    """Probe the system for seconds since last input. None if the probe fails."""
    try:
        out = subprocess.run(
            IOREG_COMMAND, capture_output=True, text=True, timeout=10
        ).stdout
    except (OSError, subprocess.SubprocessError) as e:
        logger.error(f"ioreg probe failed: {e}")
        return None
    return idle_seconds(parse_hid_idle_ns(out))


def publish_loop(broker_address, port, topic, interval, threshold,
                 host, client_type='paho'):
    """Sample HID idle time and publish it on `interval`, forever."""
    publisher = MQTTClientFactory.create_publisher(
        client_type, broker_address, port, topic
    )
    publisher.connect_with_retry()
    logger.info(
        f"publishing {host} presence to {broker_address}:{port}/{topic} "
        f"every {interval}s (idle threshold {threshold}s)"
    )
    try:
        while True:
            idle_s = read_idle_seconds()
            message = build_message(host, idle_s, threshold)
            if not publisher.publish(message):
                logger.warning(f"publish failed: {message}")
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down")
    finally:
        logger.info("Closing MQTT connection")
        publisher.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Publish an at-desk heartbeat from macOS HID idle time.'
    )
    parser.add_argument('--broker', type=str, default=Config.MQTT_BROKER,
                        help=f'MQTT broker address (default: {Config.MQTT_BROKER})')
    parser.add_argument('--port', type=int, default=Config.MQTT_PORT,
                        help=f'MQTT broker port (default: {Config.MQTT_PORT})')
    parser.add_argument('--topic', type=str, default='desk/presence',
                        help='MQTT topic (default: desk/presence)')
    parser.add_argument('--interval', type=int, default=DEFAULT_INTERVAL,
                        help=f'Seconds between publishes (default: {DEFAULT_INTERVAL})')
    parser.add_argument('--idle-threshold', type=int, default=DEFAULT_IDLE_THRESHOLD,
                        help=f'Idle seconds before "away" (default: {DEFAULT_IDLE_THRESHOLD})')
    parser.add_argument('--host-name', type=str, default=os.uname().nodename.split('.')[0],
                        help='Name to report as (default: this host)')
    parser.add_argument('--client-type', type=str, default=Config.MQTT_CLIENT_TYPE,
                        choices=MQTTClientFactory.get_supported_clients(),
                        help=f'MQTT client type (default: {Config.MQTT_CLIENT_TYPE})')
    parser.add_argument('--once', action='store_true',
                        help='Print one reading and exit; does not publish')
    parser.add_argument('--debug', action='store_true', default=Config.DEBUG_MODE,
                        help='Enable debug logging')

    args = parser.parse_args()

    if args.once:
        idle = read_idle_seconds()
        print(build_message(args.host_name, idle, args.idle_threshold))
        sys.exit(0 if idle is not None else 1)

    override_config(
        mqtt_broker=args.broker,
        mqtt_port=args.port,
        mqtt_topic=args.topic,
        mqtt_client_type=args.client_type,
        debug_mode=args.debug,
    )

    if args.debug:
        for handler in logging.root.handlers:
            if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stderr:
                handler.setLevel(logging.DEBUG)
        logger.info("Debug logging enabled")

    config_errors = Config.validate_config()
    if config_errors:
        logger.error("Configuration errors:")
        for error in config_errors:
            logger.error(f"  - {error}")
        sys.exit(1)

    publish_loop(args.broker, args.port, args.topic, args.interval,
                 args.idle_threshold, args.host_name, args.client_type)
