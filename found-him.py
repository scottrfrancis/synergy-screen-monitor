import json
import sys
import argparse
import os
import platform
import subprocess
import time
import logging
from datetime import datetime
from mqtt_clients.factory import MQTTClientFactory

# Configure logging - only show errors by default
# Create logs directory if it doesn't exist
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

# Set up file handler
log_file = os.path.join(log_dir, 'found-him.log')
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)  # File gets all log levels
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# Set up console handler (only for errors)
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.ERROR)
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to capture all levels
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger('found-him')

def main():
    """
    Main entry point for the MQTT subscriber.
    
    Parses command-line arguments and starts the subscriber to monitor
    for specific desktop activation events.
    """
    # Set up CLI argument parsing
    parser = argparse.ArgumentParser(description='MQTT JSON message listener with auto-reconnect')
    parser.add_argument('-b', '--broker', help='MQTT broker address', default='vault.local')
    parser.add_argument('-t', '--topic', help='MQTT topic to subscribe', default='synergy')
    parser.add_argument('-k', '--key', help='JSON key to check', default='current_desktop')
    parser.add_argument('value', help='Value to match for the key')
    parser.add_argument('-p', '--port', type=int, default=1883, help='MQTT broker port (default: 1883)')
    parser.add_argument('--client-type', type=str, default='paho',
                        choices=MQTTClientFactory.get_supported_clients(),
                        help='MQTT client type to use')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    if args.debug:
        # Enable debug logging to console as well
        for handler in logging.root.handlers:
            if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stderr:
                handler.setLevel(logging.DEBUG)
        logger.info("Debug logging enabled")
        print(f"Listening for messages on topic '{args.topic}'")
        print(f"Will ring bell when '{args.key}' matches '{args.value}'")
    
    # Create subscriber using factory
    subscriber = MQTTClientFactory.create_subscriber(
        client_type=args.client_type,
        broker=args.broker,
        port=args.port,
        topic=args.topic,
        key=args.key,
        value=args.value,
        bell_func=None
    )
    
    # Set bell function
    subscriber.bell_func = subscriber.get_bell_function()
    
    # Run
    subscriber.run()

if __name__ == "__main__":
    main()