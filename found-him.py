import paho.mqtt.client as mqtt
import json
import sys
import argparse
import os
import platform
import subprocess
import time
import logging
from datetime import datetime

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

class MQTTSubscriber:
    """
    MQTT subscriber that monitors messages and alerts on specific desktop activation.
    
    This class subscribes to an MQTT topic and rings a system bell when a message
    contains a specific key-value pair, typically used to alert when a particular
    desktop becomes active in Synergy.
    
    Attributes:
        broker: MQTT broker hostname or IP address
        port: MQTT broker port number
        topic: MQTT topic to subscribe to
        key: JSON key to monitor in messages
        value: Value to match for the specified key
        bell_func: Function to call when a match is found
        client: Paho MQTT client instance
        connected: Current connection status
        reconnect_delay: Current reconnection delay in seconds
        max_reconnect_delay: Maximum reconnection delay in seconds
        last_message_time: Timestamp of last received message
    """
    
    def __init__(self, broker, port, topic, key, value, bell_func):
        """
        Initialize the MQTT subscriber.
        
        Args:
            broker: MQTT broker hostname or IP address
            port: MQTT broker port number
            topic: MQTT topic to subscribe to
            key: JSON key to monitor in messages
            value: Value to match for the specified key
            bell_func: Function to call when a match is found
        """
        self.broker = broker
        self.port = port
        self.topic = topic
        self.key = key
        self.value = value
        self.bell_func = bell_func
        self.client = None
        self.connected = False
        self.reconnect_delay = 1
        self.max_reconnect_delay = 60
        self.last_message_time = time.time()
        
    def get_bell_function(self):
        """
        Determine the appropriate bell/beep function based on the operating system.
        
        Returns:
            callable: A function that produces a system bell/beep sound
        """
        system = platform.system().lower()
        
        if system == 'darwin':  # macOS
            return lambda: subprocess.run(['osascript', '-e', 'beep'], check=False)
        elif system == 'linux':
            return lambda: os.system('paplay /usr/share/sounds/freedesktop/bell.oga 2>/dev/null || echo -e "\a"')
        elif system == 'windows':
            return lambda: os.system('echo \a')
        else:
            return lambda: print('\a')  # Fallback to print bell character
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        """
        Callback for when the client receives a CONNACK response from the server.
        
        Subscribes to the configured topic upon successful connection.
        
        Args:
            client: The client instance for this callback
            userdata: The private user data
            flags: Response flags sent by the broker
            rc: Connection result code (0 = success)
            properties: MQTT v5.0 properties (unused for v3.x)
        """
        if rc == 0:
            self.connected = True
            self.reconnect_delay = 1  # Reset delay on successful connection
            
            # Subscribe to topic
            result = client.subscribe(self.topic, qos=1)
        else:
            self.connected = False
    
    def on_disconnect(self, client, userdata, rc, properties=None):
        """
        Callback for when the client disconnects from the server.
        
        Args:
            client: The client instance for this callback
            userdata: The private user data
            rc: Disconnection reason code
            properties: MQTT v5.0 properties (unused for v3.x)
        """
        self.connected = False
    
    def on_message(self, client, userdata, msg):
        """
        Process incoming MQTT messages and trigger bell on matching content.
        
        Parses JSON messages and checks if the configured key matches the
        expected value. Rings the system bell when a match is found.
        
        Args:
            client: The client instance for this callback
            userdata: The private user data
            msg: An instance of MQTTMessage containing topic and payload
        """
        self.last_message_time = time.time()
        
        try:
            # Parse JSON message
            payload = json.loads(msg.payload.decode())
            
            # Check if specified key exists and matches value
            if self.key in payload and payload[self.key] == self.value:
                # Ring terminal bell
                if self.bell_func:
                    self.bell_func()
                
                print(f"Match found! {self.key} = {payload[self.key]}")
        
        except json.JSONDecodeError:
            logger.debug(f"Failed to parse JSON message: {msg.payload}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def on_subscribe(self, client, userdata, mid, granted_qos, properties=None):
        """
        Callback for when the broker responds to a subscribe request.
        
        Args:
            client: The client instance for this callback
            userdata: The private user data
            mid: Message ID of the subscribe request
            granted_qos: List of QoS levels granted by the broker
            properties: MQTT v5.0 properties (unused for v3.x)
        """
        pass
    
    def connect_with_retry(self):
        """
        Attempt to connect to the MQTT broker with exponential backoff retry.
        
        Continuously attempts to connect until successful, with increasing
        delays between attempts.
        
        Returns:
            bool: True when successfully connected
        """
        while not self.connected:
            try:
                # Create new client instance
                self.client = mqtt.Client(
                    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                    client_id=f"found-him-{os.getpid()}"
                )
                
                # Set callbacks
                self.client.on_connect = self.on_connect
                self.client.on_disconnect = self.on_disconnect
                self.client.on_message = self.on_message
                self.client.on_subscribe = self.on_subscribe
                
                # Enable automatic reconnection
                self.client.reconnect_delay_set(min_delay=1, max_delay=120)
                
                # Connect
                self.client.connect(self.broker, self.port, keepalive=60)
                
                # Start network loop in background
                self.client.loop_start()
                
                # Wait for connection
                timeout = 10
                start_time = time.time()
                while not self.connected and (time.time() - start_time) < timeout:
                    time.sleep(0.1)
                
                if self.connected:
                    logger.info(f"Successfully connected to {self.broker}:{self.port}")
                    return True
                else:
                    raise Exception("Connection timeout")
                    
            except Exception as e:
                logger.warning(f"Connection failed: {e}. Retrying in {self.reconnect_delay} seconds")
                # Clean up failed connection
                if self.client:
                    try:
                        self.client.loop_stop()
                        self.client.disconnect()
                    except Exception as cleanup_error:
                        logger.debug(f"Error during cleanup: {cleanup_error}")
                
                time.sleep(self.reconnect_delay)
                
                # Exponential backoff
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
    
    def monitor_connection(self):
        """
        Monitor the MQTT connection and reconnect if disconnected.
        
        Runs in a loop checking connection status every 10 seconds and
        initiating reconnection when needed.
        """
        while True:
            try:
                if not self.connected:
                    self.connect_with_retry()
                
                time.sleep(10)  # Check every 10 seconds
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error in monitor_connection: {e}")
                time.sleep(10)
    
    def run(self):
        """
        Start the subscriber and maintain the connection.
        
        Establishes initial connection and then monitors it, handling
        reconnections as needed. Blocks until interrupted.
        """
        # Initial connection
        self.connect_with_retry()
        
        try:
            # Keep the main thread alive and monitor connection
            self.monitor_connection()
        except KeyboardInterrupt:
            pass
        finally:
            if self.client:
                self.client.loop_stop()
                self.client.disconnect()

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
    
    # Create subscriber
    subscriber = MQTTSubscriber(
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