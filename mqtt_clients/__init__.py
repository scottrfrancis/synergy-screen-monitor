"""
MQTT Clients Package

This package provides a dependency injection framework for MQTT client implementations.
It allows runtime selection of different MQTT client libraries while maintaining
a consistent interface.

Available clients:
- paho: Eclipse Paho MQTT client (default)

Usage:
    from mqtt_clients.factory import MQTTClientFactory
    
    publisher = MQTTClientFactory.create_publisher("paho", broker, port, topic)
    subscriber = MQTTClientFactory.create_subscriber("paho", broker, port, topic, key, value, bell_func)
"""

from .factory import MQTTClientFactory
from .interface import MQTTPublisherInterface, MQTTSubscriberInterface

__all__ = ['MQTTClientFactory', 'MQTTPublisherInterface', 'MQTTSubscriberInterface']