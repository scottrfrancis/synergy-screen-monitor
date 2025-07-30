import sys
import os
import re
import json
import argparse
import time
import logging
from datetime import datetime
from mqtt_clients.factory import MQTTClientFactory

# Configure logging - only show errors by default
# Create logs directory if it doesn't exist
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
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
    parser.add_argument('--broker', type=str, default='vault.local', help='MQTT broker address')
    parser.add_argument('--port', type=int, default=1883, help='MQTT broker port')
    parser.add_argument('--topic', type=str, default='synergy', help='MQTT topic')
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
    
    process_logs(args.broker, args.port, args.topic, args.client_type)