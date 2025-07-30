"""
Paho MQTT client implementation.

This module contains MQTT client implementations using the Eclipse Paho MQTT library.
These classes implement the abstract interfaces defined in interface.py.
"""

import sys
import os
import time
import logging
import platform
import subprocess
import paho.mqtt.client as mqtt
from .interface import MQTTPublisherInterface, MQTTSubscriberInterface

logger = logging.getLogger('paho_client')


class PahoMQTTPublisher(MQTTPublisherInterface):
    """
    MQTT publisher for Synergy desktop switching events using Paho MQTT client.
    
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
    
    def __init__(self, broker_address: str, port: int, topic: str):
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
    
    def connect_with_retry(self) -> bool:
        """
        Attempt to connect to MQTT broker with exponential backoff.
        
        This method will retry indefinitely until a successful connection is made.
        It only returns True on success and does not return on failure.
        
        Returns:
            bool: True when successfully connected (never returns False)
        """
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
    
    def publish(self, message: str) -> bool:
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


class PahoMQTTSubscriber(MQTTSubscriberInterface):
    """
    MQTT subscriber that monitors messages and alerts on specific desktop activation using Paho MQTT client.
    
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
    
    def __init__(self, broker: str, port: int, topic: str, key: str, value: str, bell_func):
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
    
    def connect_with_retry(self) -> bool:
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