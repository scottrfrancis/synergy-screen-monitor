"""
NanoMQ client implementation using NanoSDK bindings.

This module provides MQTT client implementations using the NanoSDK library
through Python bindings. These classes implement the abstract interfaces
defined in interface.py.
"""

import json
import os
import time
import logging
import threading
from typing import Optional, Callable
from .interface import MQTTPublisherInterface, MQTTSubscriberInterface

logger = logging.getLogger('nanomq_client')

try:
    import nanomq_bindings
    NANOMQ_AVAILABLE = True
except ImportError as e:
    logger.warning(f"NanoMQ bindings not available: {e}")
    logger.warning("Install with: pip install -e .[build] && python setup.py build_ext --inplace")
    NANOMQ_AVAILABLE = False


class NanoMQTTPublisher(MQTTPublisherInterface):
    """
    MQTT publisher for Synergy desktop switching events using NanoMQ client.
    
    This class handles publishing desktop switching events to an MQTT broker
    with automatic reconnection and high-performance messaging.
    
    Attributes:
        broker_address: MQTT broker hostname or IP address
        port: MQTT broker port number
        topic: MQTT topic to publish messages to
        client: NanoMQ client instance
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
            
        Raises:
            RuntimeError: If NanoMQ bindings are not available
        """
        if not NANOMQ_AVAILABLE:
            raise RuntimeError("NanoMQ bindings are not available. "
                             "Please build the extension with: pip install -e .[build]")
        
        self.broker_address = broker_address
        self.port = port
        self.topic = topic
        self.connected = False
        self.reconnect_delay = 1
        self.max_reconnect_delay = 60
        
        # Create NanoMQ client
        self.client = nanomq_bindings.NanoMQTTClient(broker_address, port)
        
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
                logger.info(f"Attempting to connect to {self.broker_address}:{self.port}")
                
                if self.client.connect():
                    self.connected = True
                    self.reconnect_delay = 1  # Reset delay on successful connection
                    logger.info("Successfully connected to MQTT broker")
                    return True
                else:
                    raise Exception("Connection failed")
                    
            except Exception as e:
                logger.warning(f"Connection failed: {e}. Retrying in {self.reconnect_delay} seconds")
                time.sleep(self.reconnect_delay)
                
                # Exponential backoff
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
    
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
            # Publish with QoS 1 for reliability
            if self.client.publish(self.topic, message, qos=1):
                logger.debug(f"Successfully published message to {self.topic}")
                return True
            else:
                logger.error("Failed to publish message")
                self.connected = False
                return False
        except Exception as e:
            logger.error(f"Exception during publish: {e}")
            self.connected = False
            return False
    
    def close(self):
        """
        Cleanly shut down the MQTT connection.
        
        Disconnects from the broker and cleans up resources.
        """
        if self.connected:
            self.client.disconnect()
            self.connected = False
            logger.info("MQTT connection closed")


class NanoMQTTSubscriber(MQTTSubscriberInterface):
    """
    MQTT subscriber that monitors messages and alerts on specific desktop activation.
    
    This class subscribes to an MQTT topic using NanoMQ and triggers alerts when a message
    contains a specific key-value pair, typically used to alert when a particular
    desktop becomes active in Synergy.
    
    Attributes:
        broker: MQTT broker hostname or IP address
        port: MQTT broker port number
        topic: MQTT topic to subscribe to
        key: JSON key to monitor in messages
        value: Value to match for the specified key
        bell_func: Function to call when a match is found
        client: NanoMQ client instance
        connected: Current connection status
        running: Whether the message loop is running
        reconnect_delay: Current reconnection delay in seconds
        max_reconnect_delay: Maximum reconnection delay in seconds
        last_message_time: Timestamp of last received message
        message_thread: Thread for message processing
    """
    
    def __init__(self, broker: str, port: int, topic: str, key: str, value: str, bell_func: Optional[Callable]):
        """
        Initialize the MQTT subscriber.
        
        Args:
            broker: MQTT broker hostname or IP address
            port: MQTT broker port number
            topic: MQTT topic to subscribe to
            key: JSON key to monitor in messages
            value: Value to match for the specified key
            bell_func: Function to call when a match is found
            
        Raises:
            RuntimeError: If NanoMQ bindings are not available
        """
        if not NANOMQ_AVAILABLE:
            raise RuntimeError("NanoMQ bindings are not available. "
                             "Please build the extension with: pip install -e .[build]")
        
        self.broker = broker
        self.port = port
        self.topic = topic
        self.key = key
        self.value = value
        self.bell_func = bell_func
        self.connected = False
        self.running = False
        self.reconnect_delay = 1
        self.max_reconnect_delay = 60
        self.last_message_time = time.time()
        self.message_thread = None
        
        # Create NanoMQ client
        self.client = nanomq_bindings.NanoMQTTClient(broker, port)
        
        # Set message callback
        self.client.set_message_callback(self._on_message)
    
    def get_bell_function(self):
        """
        Determine the appropriate bell/beep function based on the operating system.
        
        Returns:
            callable: A function that produces a system bell/beep sound
        """
        import platform
        import subprocess
        
        system = platform.system().lower()
        
        if system == 'darwin':  # macOS
            return lambda: subprocess.run(['osascript', '-e', 'beep'], check=False)
        elif system == 'linux':
            return lambda: os.system('paplay /usr/share/sounds/freedesktop/bell.oga 2>/dev/null || echo -e "\\a"')
        elif system == 'windows':
            return lambda: os.system('echo \\a')
        else:
            return lambda: print('\\a')  # Fallback to print bell character
    
    def _on_message(self, topic: str, payload: str):
        """
        Process incoming MQTT messages and trigger bell on matching content.
        
        Args:
            topic: The topic the message was received on
            payload: The message payload as a string
        """
        self.last_message_time = time.time()
        
        try:
            # Parse JSON message
            data = json.loads(payload)
            
            # Check if specified key exists and matches value
            if self.key in data and data[self.key] == self.value:
                # Ring terminal bell
                if self.bell_func:
                    self.bell_func()
                
                print(f"Match found! {self.key} = {data[self.key]}")
        
        except json.JSONDecodeError:
            logger.debug(f"Failed to parse JSON message: {payload}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
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
                # Generate unique client ID
                client_id = f"synergy-found-him-{os.getpid()}-{int(time.time())}"
                
                logger.info(f"Attempting to connect to {self.broker}:{self.port}")
                
                if self.client.connect(client_id):
                    self.connected = True
                    self.reconnect_delay = 1  # Reset delay on successful connection
                    
                    # Subscribe to topic
                    if self.client.subscribe(self.topic, qos=1):
                        logger.info(f"Successfully connected and subscribed to {self.topic}")
                        return True
                    else:
                        raise Exception("Failed to subscribe to topic")
                else:
                    raise Exception("Connection failed")
                    
            except Exception as e:
                logger.warning(f"Connection failed: {e}. Retrying in {self.reconnect_delay} seconds")
                
                # Clean up failed connection
                try:
                    self.client.disconnect()
                except:
                    pass
                
                time.sleep(self.reconnect_delay)
                
                # Exponential backoff
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
    
    def run(self):
        """
        Start the subscriber and maintain the connection.
        
        Establishes initial connection and then monitors it, handling
        reconnections as needed. Blocks until interrupted.
        """
        # Set bell function if not provided
        if self.bell_func is None:
            self.bell_func = self.get_bell_function()
        
        # Initial connection
        self.connect_with_retry()
        
        # Start message loop
        self.running = True
        self.client.start_message_loop()
        
        try:
            # Keep the main thread alive and monitor connection
            while self.running and self.connected:
                # Check if we're still receiving messages (heartbeat check)
                if time.time() - self.last_message_time > 120:  # 2 minute timeout
                    logger.warning("No messages received recently, checking connection")
                    if not self.client.is_connected():
                        logger.warning("Connection lost, attempting to reconnect")
                        self.connected = False
                        self.connect_with_retry()
                
                time.sleep(10)  # Check every 10 seconds
                
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down")
        except Exception as e:
            logger.error(f"Error in message loop: {e}")
        finally:
            self.running = False
            self.client.stop_message_loop()
            if self.connected:
                self.client.disconnect()
                self.connected = False