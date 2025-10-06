#!/bin/zsh

# Synergy Desktop Watcher
# Shows real-time desktop switches by subscribing to MQTT

echo "=== Synergy Desktop Watcher ==="
echo "Monitoring desktop switches via MQTT..."
echo ""

# Use found-him.py to subscribe and show all messages
python3 - << 'PYTHON_SCRIPT'
import sys
import json
from mqtt_clients.factory import MQTTClientFactory
from config import Config

def show_message(topic, payload):
    """Print desktop switch messages."""
    try:
        data = json.loads(payload)
        desktop = data.get('current_desktop', 'unknown')
        timestamp = data.get('timestamp', '')
        print(f"→ {desktop} ({timestamp.split('T')[1].split('.')[0] if timestamp else 'now'})")
        sys.stdout.flush()
    except:
        pass

# Create subscriber
subscriber = MQTTClientFactory.create_subscriber(
    client_type=Config.MQTT_CLIENT_TYPE,
    broker=Config.MQTT_BROKER,
    port=Config.MQTT_PORT,
    topic=Config.MQTT_TOPIC,
    key='current_desktop',
    value='*',  # Match anything
    bell_func=None
)

# Override message callback to just display
subscriber._on_message = show_message
subscriber.bell_func = lambda: None  # No beep

print(f"Connected to {Config.MQTT_BROKER}:{Config.MQTT_PORT}")
print(f"Watching topic: {Config.MQTT_TOPIC}")
print("")

try:
    subscriber.run()
except KeyboardInterrupt:
    print("\nStopped watching")
PYTHON_SCRIPT
