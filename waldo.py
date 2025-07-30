import sys
import os
import re
import json
import argparse
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
log_file = os.path.join(log_dir, 'waldo.log')
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
logger = logging.getLogger('waldo')

def process_logs(broker_address, port, topic, client_type='paho'):
    """
    Process Synergy log entries from stdin and publish desktop switching events.
    
    Reads log lines from stdin, extracts desktop names from switch events,
    and publishes them as JSON messages to the MQTT broker.
    
    Args:
        broker_address: MQTT broker hostname or IP address
        port: MQTT broker port number
        topic: MQTT topic to publish messages to
        client_type: MQTT client type to use (default: 'paho')
    """
    publisher = MQTTClientFactory.create_publisher(client_type, broker_address, port, topic)
    
    # Initial connection
    publisher.connect_with_retry()
    
    try:
        for line in sys.stdin:
            match = re.search(r'to "([^-]+)', line)
            if match:
                system_name = match.group(1)
                timestamp = datetime.now().isoformat()
                message = json.dumps({
                    'current_desktop': system_name,
                    'timestamp': timestamp
                })
                
                # Retry publishing with exponential backoff
                retry_count = 0
                max_retries = 3
                published = False
                
                while retry_count < max_retries and not published:
                    if publisher.publish(message):
                        print(f"{system_name}")
                        published = True
                    else:
                        retry_count += 1
                        if retry_count < max_retries:
                            wait_time = 2 ** retry_count
                            logger.debug(f"Publish retry {retry_count}/{max_retries}, waiting {wait_time}s")
                            time.sleep(wait_time)
                    
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down")
    except Exception as e:
        logger.error(f"Unexpected error in process_logs: {e}")
    finally:
        logger.info("Closing MQTT connection")
        publisher.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process logs and publish to MQTT.')
    parser.add_argument('--broker', type=str, default=Config.MQTT_BROKER, 
                        help=f'MQTT broker address (default: {Config.MQTT_BROKER})')
    parser.add_argument('--port', type=int, default=Config.MQTT_PORT, 
                        help=f'MQTT broker port (default: {Config.MQTT_PORT})')
    parser.add_argument('--topic', type=str, default=Config.MQTT_TOPIC, 
                        help=f'MQTT topic (default: {Config.MQTT_TOPIC})')
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
        debug_mode=args.debug
    )
    
    if args.debug:
        # Enable debug logging to console as well
        for handler in logging.root.handlers:
            if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stderr:
                handler.setLevel(logging.DEBUG)
        logger.info("Debug logging enabled")
        Config.print_config_summary()
    
    # Validate configuration
    config_errors = Config.validate_config()
    if config_errors:
        logger.error("Configuration errors:")
        for error in config_errors:
            logger.error(f"  - {error}")
        sys.exit(1)
    
    process_logs(args.broker, args.port, args.topic, args.client_type)