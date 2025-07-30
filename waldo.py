import sys
import os
import re
import json
import argparse
import time
import logging
from datetime import datetime
import paho.mqtt.client as mqtt

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

class MQTTPublisher:
    """
    MQTT publisher for Synergy desktop switching events.
    
    This class handles publishing desktop switching events to an MQTT broker
    with automatic reconnection and retry logic.
    
    Attributes:
        broker_address: MQTT broker hostname or IP address
        port: MQTT broker port number
        topic: MQTT topic to publish messages to
        client: Paho MQTT client instance
        connected: Current connection status
        reconnect_delay: Current reconnection delay in seconds
        max_reconnect_delay: Maximum reconnection delay in seconds
    """
    
    def __init__(self, broker_address, port, topic):
        """
        Initialize the MQTT publisher.
        
        Args:
            broker_address: MQTT broker hostname or IP address
            port: MQTT broker port number
            topic: MQTT topic to publish messages to
        """
        self.broker_address = broker_address
        self.port = port
        self.topic = topic
        self.client = None
        self.connected = False
        self.reconnect_delay = 1
        self.max_reconnect_delay = 60
        
    def on_connect(self, client, userdata, flags, reason_code, properties):
        """
        Callback for when the client receives a CONNACK response from the server.
        
        Args:
            client: The client instance for this callback
            userdata: The private user data
            flags: Response flags sent by the broker
            reason_code: Connection result code (0 = success)
            properties: MQTT v5.0 properties (unused for v3.x)
        """
        if reason_code == 0:
            self.connected = True
            self.reconnect_delay = 1  # Reset delay on successful connection
        else:
            self.connected = False
    
    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        """
        Callback for when the client disconnects from the server.
        
        Args:
            client: The client instance for this callback
            userdata: The private user data
            disconnect_flags: Disconnect flags from the broker
            reason_code: Disconnection reason code
            properties: MQTT v5.0 properties (unused for v3.x)
        """
        self.connected = False
    
    def connect_with_retry(self):
        """Attempt to connect to MQTT broker with exponential backoff."""
        while not self.connected:
            try:
                self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
                self.client.on_connect = self.on_connect
                self.client.on_disconnect = self.on_disconnect
                
                # Enable automatic reconnection
                self.client.reconnect_delay_set(min_delay=1, max_delay=120)
                
                logger.info(f"Attempting to connect to {self.broker_address}:{self.port}")
                self.client.connect(self.broker_address, self.port, keepalive=60)
                self.client.loop_start()
                
                # Wait for connection
                timeout = 10
                start_time = time.time()
                while not self.connected and (time.time() - start_time) < timeout:
                    time.sleep(0.1)
                
                if self.connected:
                    logger.info("Successfully connected to MQTT broker")
                    return True
                else:
                    raise Exception("Connection timeout")
                    
            except Exception as e:
                logger.warning(f"Connection failed: {e}. Retrying in {self.reconnect_delay} seconds")
                time.sleep(self.reconnect_delay)
                
                # Exponential backoff
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
                
                if self.client:
                    try:
                        self.client.loop_stop()
                        self.client.disconnect()
                    except Exception as cleanup_error:
                        logger.debug(f"Error during cleanup: {cleanup_error}")
    
    def publish(self, message):
        """
        Publish a message to the configured MQTT topic.
        
        Automatically attempts to reconnect if not connected.
        
        Args:
            message: Message string to publish
            
        Returns:
            bool: True if publish succeeded, False otherwise
        """
        if not self.connected:
            logger.debug("Not connected, attempting to reconnect")
            self.connect_with_retry()
        
        try:
            result = self.client.publish(self.topic, message, qos=1)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.error(f"Failed to publish message: MQTT error code {result.rc}")
                self.connected = False
                return False
            logger.debug(f"Successfully published message to {self.topic}")
            return True
        except Exception as e:
            logger.error(f"Exception during publish: {e}")
            self.connected = False
            return False
    
    def close(self):
        """
        Cleanly shut down the MQTT connection.
        
        Stops the network loop and disconnects from the broker.
        """
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()

def process_logs(broker_address, port, topic):
    """
    Process Synergy log entries from stdin and publish desktop switching events.
    
    Reads log lines from stdin, extracts desktop names from switch events,
    and publishes them as JSON messages to the MQTT broker.
    
    Args:
        broker_address: MQTT broker hostname or IP address
        port: MQTT broker port number
        topic: MQTT topic to publish messages to
    """
    publisher = MQTTPublisher(broker_address, port, topic)
    
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
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    if args.debug:
        # Enable debug logging to console as well
        for handler in logging.root.handlers:
            if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stderr:
                handler.setLevel(logging.DEBUG)
        logger.info("Debug logging enabled")
    
    process_logs(args.broker, args.port, args.topic)