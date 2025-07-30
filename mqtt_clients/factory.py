"""
MQTT Client Factory

This module provides a factory pattern for creating MQTT client instances.
It allows runtime selection of different MQTT client implementations through
dependency injection.
"""

from typing import Optional, Callable
from .interface import MQTTPublisherInterface, MQTTSubscriberInterface


class MQTTClientFactory:
    """
    Factory class for creating MQTT client instances.
    
    This factory supports dependency injection by allowing runtime selection
    of different MQTT client implementations while maintaining a consistent
    interface.
    
    Supported client types:
    - paho: Eclipse Paho MQTT client (default)
    """
    
    SUPPORTED_CLIENTS = ['paho']
    DEFAULT_CLIENT = 'paho'
    
    @staticmethod
    def create_publisher(client_type: str, broker_address: str, port: int, topic: str) -> MQTTPublisherInterface:
        """
        Create an MQTT publisher instance.
        
        Args:
            client_type: Type of MQTT client to create ('paho')
            broker_address: MQTT broker hostname or IP address
            port: MQTT broker port number
            topic: MQTT topic to publish messages to
            
        Returns:
            MQTTPublisherInterface: Publisher instance
            
        Raises:
            ValueError: If client_type is not supported
        """
        if client_type not in MQTTClientFactory.SUPPORTED_CLIENTS:
            raise ValueError(f"Unsupported client type: {client_type}. "
                           f"Supported types: {MQTTClientFactory.SUPPORTED_CLIENTS}")
        
        if client_type == 'paho':
            from .paho_client import PahoMQTTPublisher
            return PahoMQTTPublisher(broker_address, port, topic)
        
        # This should never be reached due to the check above, but just in case
        raise ValueError(f"Unknown client type: {client_type}")
    
    @staticmethod
    def create_subscriber(client_type: str, broker: str, port: int, topic: str, 
                         key: str, value: str, bell_func: Optional[Callable] = None) -> MQTTSubscriberInterface:
        """
        Create an MQTT subscriber instance.
        
        Args:
            client_type: Type of MQTT client to create ('paho')
            broker: MQTT broker hostname or IP address
            port: MQTT broker port number
            topic: MQTT topic to subscribe to
            key: JSON key to monitor in messages
            value: Value to match for the specified key
            bell_func: Function to call when a match is found (optional)
            
        Returns:
            MQTTSubscriberInterface: Subscriber instance
            
        Raises:
            ValueError: If client_type is not supported
        """
        if client_type not in MQTTClientFactory.SUPPORTED_CLIENTS:
            raise ValueError(f"Unsupported client type: {client_type}. "
                           f"Supported types: {MQTTClientFactory.SUPPORTED_CLIENTS}")
        
        if client_type == 'paho':
            from .paho_client import PahoMQTTSubscriber
            return PahoMQTTSubscriber(broker, port, topic, key, value, bell_func)
        
        # This should never be reached due to the check above, but just in case
        raise ValueError(f"Unknown client type: {client_type}")
    
    @staticmethod
    def get_supported_clients() -> list:
        """
        Get list of supported MQTT client types.
        
        Returns:
            list: List of supported client type strings
        """
        return MQTTClientFactory.SUPPORTED_CLIENTS.copy()
    
    @staticmethod
    def get_default_client() -> str:
        """
        Get the default MQTT client type.
        
        Returns:
            str: Default client type
        """
        return MQTTClientFactory.DEFAULT_CLIENT