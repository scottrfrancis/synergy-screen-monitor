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
from config import Config, get_mqtt_config, override_config

# Configure logging - only show errors by default
# Create logs directory if it doesn't exist
log_dir = Config.LOG_DIR
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
    parser.add_argument('-b', '--broker', help='MQTT broker address', default=Config.MQTT_BROKER)
    parser.add_argument('-t', '--topic', help='MQTT topic to subscribe', default=Config.MQTT_TOPIC)
    parser.add_argument('-k', '--key', help='JSON key to check', default='current_desktop')
    parser.add_argument('value', help='Value to match for the key (target desktop name)')
    parser.add_argument('-p', '--port', type=int, default=Config.MQTT_PORT, 
                        help=f'MQTT broker port (default: {Config.MQTT_PORT})')
    parser.add_argument('--client-type', type=str, default=Config.MQTT_CLIENT_TYPE,
                        choices=MQTTClientFactory.get_supported_clients(),
                        help=f'MQTT client type to use (default: {Config.MQTT_CLIENT_TYPE})')
    parser.add_argument('--debug', action='store_true', default=Config.DEBUG_MODE,
                        help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Override config with CLI arguments (CLI takes precedence)
    override_config(
        mqtt_broker=args.broker,
        mqtt_port=args.port,
        mqtt_topic=args.topic,
        mqtt_client_type=args.client_type,
        debug_mode=args.debug,
        target_desktop=args.value  # Target desktop from CLI argument
    )
    
    if args.debug:
        # Enable debug logging to console as well
        for handler in logging.root.handlers:
            if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stderr:
                handler.setLevel(logging.DEBUG)
        logger.info("Debug logging enabled")
        Config.print_config_summary()
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