"""
Unit tests for NanoMQ client implementation.

Tests the NanoMQ client functionality including connection, publishing,
subscribing, and integration with the factory pattern.
"""

import pytest
import json
import time
import threading
from unittest.mock import Mock, patch, MagicMock

# Test if NanoMQ is available
try:
    from mqtt_clients.nanomq_client import NanoMQTTPublisher, NanoMQTTSubscriber, NANOMQ_AVAILABLE
    from mqtt_clients.factory import MQTTClientFactory
    nanomq_available = NANOMQ_AVAILABLE
except ImportError:
    nanomq_available = False
    NanoMQTTPublisher = None
    NanoMQTTSubscriber = None


# Skip all tests if NanoMQ is not available
pytestmark = pytest.mark.skipif(
    not nanomq_available,
    reason="NanoMQ bindings not available - run 'python setup.py build_ext --inplace' to build"
)


@pytest.mark.unit
class TestNanoMQTTPublisher:
    """Test cases for NanoMQTTPublisher."""
    
    @patch('mqtt_clients.nanomq_client.nanomq_bindings')
    def test_init_success(self, mock_bindings):
        """Test successful initialization of publisher."""
        mock_client = Mock()
        mock_bindings.NanoMQTTClient.return_value = mock_client
        
        publisher = NanoMQTTPublisher("test.broker", 1883, "test/topic")
        
        assert publisher.broker_address == "test.broker"
        assert publisher.port == 1883
        assert publisher.topic == "test/topic"
        assert publisher.connected is False
        assert publisher.client == mock_client
        mock_bindings.NanoMQTTClient.assert_called_once_with("test.broker", 1883)
    
    @patch('mqtt_clients.nanomq_client.nanomq_bindings')
    def test_init_no_bindings(self, mock_bindings):
        """Test initialization failure when bindings are not available."""
        with patch('mqtt_clients.nanomq_client.NANOMQ_AVAILABLE', False):
            with pytest.raises(RuntimeError, match="NanoMQ bindings are not available"):
                NanoMQTTPublisher("test.broker", 1883, "test/topic")
    
    @patch('mqtt_clients.nanomq_client.nanomq_bindings')
    @patch('time.sleep')
    def test_connect_with_retry_success(self, mock_sleep, mock_bindings):
        """Test successful connection with retry logic."""
        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_bindings.NanoMQTTClient.return_value = mock_client
        
        publisher = NanoMQTTPublisher("test.broker", 1883, "test/topic")
        result = publisher.connect_with_retry()
        
        assert result is True
        assert publisher.connected is True
        mock_client.connect.assert_called_once()
    
    @patch('mqtt_clients.nanomq_client.nanomq_bindings')
    @patch('time.sleep')
    def test_connect_with_retry_multiple_attempts(self, mock_sleep, mock_bindings):
        """Test connection retry logic with multiple attempts."""
        mock_client = Mock()
        # Fail twice, then succeed
        mock_client.connect.side_effect = [False, False, True]
        mock_bindings.NanoMQTTClient.return_value = mock_client
        
        publisher = NanoMQTTPublisher("test.broker", 1883, "test/topic")
        result = publisher.connect_with_retry()
        
        assert result is True
        assert publisher.connected is True
        assert mock_client.connect.call_count == 3
        assert mock_sleep.call_count == 2  # Should sleep between retries
    
    @patch('mqtt_clients.nanomq_client.nanomq_bindings')
    def test_publish_success(self, mock_bindings):
        """Test successful message publishing."""
        mock_client = Mock()
        mock_client.publish.return_value = True
        mock_bindings.NanoMQTTClient.return_value = mock_client
        
        publisher = NanoMQTTPublisher("test.broker", 1883, "test/topic")
        publisher.connected = True  # Mock connected state
        
        result = publisher.publish('{"test": "message"}')
        
        assert result is True
        mock_client.publish.assert_called_once_with("test/topic", '{"test": "message"}', qos=1)
    
    @patch('mqtt_clients.nanomq_client.nanomq_bindings')
    def test_publish_failure(self, mock_bindings):
        """Test message publishing failure."""
        mock_client = Mock()
        mock_client.publish.return_value = False
        mock_bindings.NanoMQTTClient.return_value = mock_client
        
        publisher = NanoMQTTPublisher("test.broker", 1883, "test/topic")
        publisher.connected = True  # Mock connected state
        
        result = publisher.publish('{"test": "message"}')
        
        assert result is False
        assert publisher.connected is False  # Should mark as disconnected
    
    @patch('mqtt_clients.nanomq_client.nanomq_bindings')
    def test_publish_not_connected(self, mock_bindings):
        """Test publishing when not connected triggers reconnection."""
        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_client.publish.return_value = True
        mock_bindings.NanoMQTTClient.return_value = mock_client
        
        publisher = NanoMQTTPublisher("test.broker", 1883, "test/topic")
        # connected starts as False
        
        result = publisher.publish('{"test": "message"}')
        
        assert result is True
        assert publisher.connected is True
        mock_client.connect.assert_called_once()
        mock_client.publish.assert_called_once()
    
    @patch('mqtt_clients.nanomq_client.nanomq_bindings')
    def test_close(self, mock_bindings):
        """Test clean connection shutdown."""
        mock_client = Mock()
        mock_bindings.NanoMQTTClient.return_value = mock_client
        
        publisher = NanoMQTTPublisher("test.broker", 1883, "test/topic")
        publisher.connected = True
        
        publisher.close()
        
        assert publisher.connected is False
        mock_client.disconnect.assert_called_once()


@pytest.mark.unit
class TestNanoMQTTSubscriber:
    """Test cases for NanoMQTTSubscriber."""
    
    @patch('mqtt_clients.nanomq_client.nanomq_bindings')
    def test_init_success(self, mock_bindings):
        """Test successful initialization of subscriber."""
        mock_client = Mock()
        mock_bindings.NanoMQTTClient.return_value = mock_client
        bell_func = Mock()
        
        subscriber = NanoMQTTSubscriber("test.broker", 1883, "test/topic", "key", "value", bell_func)
        
        assert subscriber.broker == "test.broker"
        assert subscriber.port == 1883
        assert subscriber.topic == "test/topic"
        assert subscriber.key == "key"
        assert subscriber.value == "value"
        assert subscriber.bell_func == bell_func
        assert subscriber.connected is False
        assert subscriber.client == mock_client
        mock_client.set_message_callback.assert_called_once()
    
    @patch('mqtt_clients.nanomq_client.nanomq_bindings')
    def test_init_no_bindings(self, mock_bindings):
        """Test initialization failure when bindings are not available."""
        with patch('mqtt_clients.nanomq_client.NANOMQ_AVAILABLE', False):
            with pytest.raises(RuntimeError, match="NanoMQ bindings are not available"):
                NanoMQTTSubscriber("test.broker", 1883, "test/topic", "key", "value", None)
    
    @patch('mqtt_clients.nanomq_client.nanomq_bindings')
    def test_on_message_match(self, mock_bindings):
        """Test message processing with matching content."""
        mock_client = Mock()
        mock_bindings.NanoMQTTClient.return_value = mock_client
        bell_func = Mock()
        
        subscriber = NanoMQTTSubscriber("test.broker", 1883, "test/topic", "desktop", "workstation", bell_func)
        
        # Simulate receiving a matching message
        test_payload = '{"desktop": "workstation", "timestamp": "2025-01-01T12:00:00"}'
        subscriber._on_message("test/topic", test_payload)
        
        bell_func.assert_called_once()
    
    @patch('mqtt_clients.nanomq_client.nanomq_bindings')
    def test_on_message_no_match(self, mock_bindings):
        """Test message processing with non-matching content."""
        mock_client = Mock()
        mock_bindings.NanoMQTTClient.return_value = mock_client
        bell_func = Mock()
        
        subscriber = NanoMQTTSubscriber("test.broker", 1883, "test/topic", "desktop", "workstation", bell_func)
        
        # Simulate receiving a non-matching message
        test_payload = '{"desktop": "laptop", "timestamp": "2025-01-01T12:00:00"}'
        subscriber._on_message("test/topic", test_payload)
        
        bell_func.assert_not_called()
    
    @patch('mqtt_clients.nanomq_client.nanomq_bindings')
    def test_on_message_invalid_json(self, mock_bindings):
        """Test message processing with invalid JSON."""
        mock_client = Mock()
        mock_bindings.NanoMQTTClient.return_value = mock_client
        bell_func = Mock()
        
        subscriber = NanoMQTTSubscriber("test.broker", 1883, "test/topic", "desktop", "workstation", bell_func)
        
        # Simulate receiving invalid JSON
        subscriber._on_message("test/topic", "invalid json")
        
        bell_func.assert_not_called()
    
    @patch('mqtt_clients.nanomq_client.nanomq_bindings')
    @patch('time.sleep')
    def test_connect_with_retry_success(self, mock_sleep, mock_bindings):
        """Test successful connection and subscription."""
        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_client.subscribe.return_value = True
        mock_bindings.NanoMQTTClient.return_value = mock_client
        
        subscriber = NanoMQTTSubscriber("test.broker", 1883, "test/topic", "key", "value", None)
        result = subscriber.connect_with_retry()
        
        assert result is True
        assert subscriber.connected is True
        mock_client.connect.assert_called_once()
        mock_client.subscribe.assert_called_once_with("test/topic", qos=1)
    
    @patch('mqtt_clients.nanomq_client.nanomq_bindings')
    def test_get_bell_function_macos(self, mock_bindings):
        """Test bell function selection for macOS."""
        mock_client = Mock()
        mock_bindings.NanoMQTTClient.return_value = mock_client
        
        with patch('platform.system', return_value='Darwin'):
            subscriber = NanoMQTTSubscriber("test.broker", 1883, "test/topic", "key", "value", None)
            bell_func = subscriber.get_bell_function()
            
            # Bell function should be callable
            assert callable(bell_func)
    
    @patch('mqtt_clients.nanomq_client.nanomq_bindings')
    def test_get_bell_function_linux(self, mock_bindings):
        """Test bell function selection for Linux."""
        mock_client = Mock()
        mock_bindings.NanoMQTTClient.return_value = mock_client
        
        with patch('platform.system', return_value='Linux'):
            subscriber = NanoMQTTSubscriber("test.broker", 1883, "test/topic", "key", "value", None)
            bell_func = subscriber.get_bell_function()
            
            # Bell function should be callable
            assert callable(bell_func)


@pytest.mark.unit
class TestMQTTClientFactoryNanoMQ:
    """Test factory integration with NanoMQ clients."""
    
    def test_nanomq_in_supported_clients(self):
        """Test that nanomq is listed in supported clients."""
        supported = MQTTClientFactory.get_supported_clients()
        assert 'nanomq' in supported
    
    @patch('mqtt_clients.nanomq_client.nanomq_bindings')
    def test_create_publisher(self, mock_bindings):
        """Test factory creation of NanoMQ publisher."""
        mock_client = Mock()
        mock_bindings.NanoMQTTClient.return_value = mock_client
        
        publisher = MQTTClientFactory.create_publisher('nanomq', 'test.broker', 1883, 'test/topic')
        
        assert isinstance(publisher, NanoMQTTPublisher)
        assert publisher.broker_address == 'test.broker'
        assert publisher.port == 1883
        assert publisher.topic == 'test/topic'
    
    @patch('mqtt_clients.nanomq_client.nanomq_bindings')
    def test_create_subscriber(self, mock_bindings):
        """Test factory creation of NanoMQ subscriber."""
        mock_client = Mock()
        mock_bindings.NanoMQTTClient.return_value = mock_client
        bell_func = Mock()
        
        subscriber = MQTTClientFactory.create_subscriber(
            'nanomq', 'test.broker', 1883, 'test/topic', 'key', 'value', bell_func
        )
        
        assert isinstance(subscriber, NanoMQTTSubscriber)
        assert subscriber.broker == 'test.broker'
        assert subscriber.port == 1883
        assert subscriber.topic == 'test/topic'
        assert subscriber.key == 'key'
        assert subscriber.value == 'value'
        assert subscriber.bell_func == bell_func


@pytest.mark.integration
@pytest.mark.skipif(
    not nanomq_available,
    reason="NanoMQ bindings required for integration tests"
)
class TestNanoMQIntegration:
    """Integration tests for NanoMQ client (require actual bindings)."""
    
    def test_publisher_subscriber_integration(self):
        """Test end-to-end publisher-subscriber communication."""
        # This would require a running MQTT broker for real integration testing
        # For now, we'll test that the classes can be instantiated
        try:
            publisher = NanoMQTTPublisher("localhost", 1883, "test/topic")
            subscriber = NanoMQTTSubscriber("localhost", 1883, "test/topic", "key", "value", None)
            
            # Basic instantiation test
            assert publisher is not None
            assert subscriber is not None
            
        except RuntimeError as e:
            if "NanoMQ bindings are not available" in str(e):
                pytest.skip("NanoMQ bindings not built")
            else:
                raise