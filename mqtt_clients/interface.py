"""
Abstract interfaces for MQTT client implementations.

This module defines the abstract base classes that all MQTT client implementations
must inherit from. This ensures a consistent API across different MQTT client libraries.
"""

from abc import ABC, abstractmethod


class MQTTPublisherInterface(ABC):
    """
    Abstract interface for MQTT publishers.
    
    This interface defines the standard operations that all MQTT publisher
    implementations must support for publishing desktop switching events.
    """
    
    @abstractmethod
    def __init__(self, broker_address: str, port: int, topic: str):
        """
        Initialize the MQTT publisher.
        
        Args:
            broker_address: MQTT broker hostname or IP address
            port: MQTT broker port number
            topic: MQTT topic to publish messages to
        """
        pass
    
    @abstractmethod
    def connect_with_retry(self) -> bool:
        """
        Attempt to connect to MQTT broker with exponential backoff.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    def publish(self, message: str) -> bool:
        """
        Publish a message to the configured MQTT topic.
        
        Args:
            message: Message string to publish
            
        Returns:
            bool: True if publish succeeded, False otherwise
        """
        pass
    
    @abstractmethod
    def close(self):
        """
        Cleanly shut down the MQTT connection.
        """
        pass


class MQTTSubscriberInterface(ABC):
    """
    Abstract interface for MQTT subscribers.
    
    This interface defines the standard operations that all MQTT subscriber
    implementations must support for monitoring desktop switching events.
    """
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    def connect_with_retry(self) -> bool:
        """
        Attempt to connect to the MQTT broker with exponential backoff retry.
        
        Returns:
            bool: True when successfully connected
        """
        pass
    
    @abstractmethod
    def run(self):
        """
        Start the subscriber and maintain the connection.
        
        This method blocks until interrupted and handles reconnections as needed.
        """
        pass