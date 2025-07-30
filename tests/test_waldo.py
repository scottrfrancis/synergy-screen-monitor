"""Unit tests for waldo.py MQTT publisher"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock, call
import paho.mqtt.client as mqtt
from mqtt_clients.paho_client import PahoMQTTPublisher as MQTTPublisher


class TestMQTTPublisher:
    """Test cases for MQTTPublisher class"""
    
    @pytest.fixture
    def publisher(self):
        """Create a test publisher instance"""
        return MQTTPublisher('test.broker', 1883, 'test/topic')
    
    def test_initialization(self, publisher):
        """Test publisher initialization"""
        assert publisher.broker_address == 'test.broker'
        assert publisher.port == 1883
        assert publisher.topic == 'test/topic'
        assert publisher.connected is False
        assert publisher.reconnect_delay == 1
        assert publisher.max_reconnect_delay == 60
    
    def test_on_connect_success(self, publisher):
        """Test successful connection callback"""
        mock_client = Mock()
        publisher.on_connect(mock_client, None, None, 0, None)
        assert publisher.connected is True
        assert publisher.reconnect_delay == 1
    
    def test_on_connect_failure(self, publisher):
        """Test failed connection callback"""
        mock_client = Mock()
        publisher.on_connect(mock_client, None, None, 1, None)
        assert publisher.connected is False
    
    def test_on_disconnect(self, publisher):
        """Test disconnect callback"""
        mock_client = Mock()
        publisher.connected = True
        publisher.on_disconnect(mock_client, None, None, 0, None)
        assert publisher.connected is False
    
    @patch('waldo.mqtt.Client')
    @patch('time.sleep')
    def test_connect_with_retry_success(self, mock_sleep, mock_mqtt_client, publisher):
        """Test successful connection with retry"""
        mock_client = MagicMock()
        mock_mqtt_client.return_value = mock_client
        
        # Simulate successful connection on first try
        def simulate_connect(*args, **kwargs):
            # Call the on_connect callback
            publisher.on_connect(mock_client, None, None, 0, None)
        
        mock_client.connect.side_effect = simulate_connect
        
        result = publisher.connect_with_retry()
        
        assert result is True
        assert publisher.connected is True
        mock_client.connect.assert_called_once_with('test.broker', 1883, keepalive=60)
        mock_client.loop_start.assert_called_once()
    
    @patch('waldo.mqtt.Client')
    @patch('time.sleep')
    def test_connect_with_retry_timeout(self, mock_sleep, mock_mqtt_client, publisher):
        """Test connection retry with timeout"""
        mock_client = MagicMock()
        mock_mqtt_client.return_value = mock_client
        
        # Simulate connection timeout (connected stays False)
        publisher.connected = False
        
        # This will loop, so we need to break it after first iteration
        with patch('time.time', side_effect=[0, 0.1, 10.1]):  # Simulate timeout
            publisher.connect_with_retry()
        
        # Should have attempted connection
        mock_client.connect.assert_called()
        mock_sleep.assert_called()  # Should sleep before retry
        assert publisher.reconnect_delay == 2  # Should increase delay
    
    @patch('waldo.mqtt.Client')
    def test_publish_success(self, mock_mqtt_client, publisher):
        """Test successful message publishing"""
        mock_client = MagicMock()
        mock_mqtt_client.return_value = mock_client
        publisher.client = mock_client
        publisher.connected = True
        
        # Mock successful publish
        mock_result = Mock()
        mock_result.rc = mqtt.MQTT_ERR_SUCCESS
        mock_client.publish.return_value = mock_result
        
        result = publisher.publish('test message')
        
        assert result is True
        mock_client.publish.assert_called_once_with('test/topic', 'test message', qos=1)
    
    @patch('waldo.mqtt.Client')
    def test_publish_failure(self, mock_mqtt_client, publisher):
        """Test failed message publishing"""
        mock_client = MagicMock()
        mock_mqtt_client.return_value = mock_client
        publisher.client = mock_client
        publisher.connected = True
        
        # Mock failed publish
        mock_result = Mock()
        mock_result.rc = mqtt.MQTT_ERR_NO_CONN
        mock_client.publish.return_value = mock_result
        
        result = publisher.publish('test message')
        
        assert result is False
        assert publisher.connected is False
    
    @patch('waldo.mqtt.Client')
    def test_publish_reconnect(self, mock_mqtt_client, publisher):
        """Test publish triggers reconnect when disconnected"""
        mock_client = MagicMock()
        mock_mqtt_client.return_value = mock_client
        publisher.connected = False
        
        # Mock connect_with_retry
        with patch.object(publisher, 'connect_with_retry') as mock_connect:
            publisher.publish('test message')
            mock_connect.assert_called_once()
    
    def test_close(self, publisher):
        """Test clean shutdown"""
        mock_client = Mock()
        publisher.client = mock_client
        
        publisher.close()
        
        mock_client.loop_stop.assert_called_once()
        mock_client.disconnect.assert_called_once()


@pytest.mark.unit
class TestLogProcessing:
    """Test log processing functionality"""
    
    @patch('sys.stdin', ['log line without match\n', 'switched to "desktop1-\n'])
    @patch('waldo.MQTTPublisher')
    def test_process_logs_pattern_matching(self, mock_publisher_class):
        """Test that log patterns are correctly matched"""
        from waldo import process_logs
        
        mock_publisher = MagicMock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = True
        
        # Run with mocked stdin
        with patch('sys.stdin', ['log line without match\n', 'switched to "desktop1-\n']):
            try:
                process_logs('test.broker', 1883, 'test/topic')
            except StopIteration:
                pass  # Expected when stdin is exhausted
        
        # Should have published once for the matching line
        assert mock_publisher.publish.call_count == 1
        published_message = mock_publisher.publish.call_args[0][0]
        assert '"current_desktop": "desktop1"' in published_message
    
    @patch('waldo.MQTTPublisher')
    def test_process_logs_retry_logic(self, mock_publisher_class):
        """Test retry logic for failed publishes"""
        from waldo import process_logs
        
        mock_publisher = MagicMock()
        mock_publisher_class.return_value = mock_publisher
        
        # Simulate publish failing twice then succeeding
        mock_publisher.publish.side_effect = [False, False, True]
        
        with patch('sys.stdin', ['switched to "desktop1-\n']):
            with patch('time.sleep') as mock_sleep:
                try:
                    process_logs('test.broker', 1883, 'test/topic')
                except StopIteration:
                    pass
        
        # Should have tried 3 times
        assert mock_publisher.publish.call_count == 3
        # Should have slept between retries
        assert mock_sleep.call_count == 2
        mock_sleep.assert_has_calls([call(2), call(4)])  # Exponential backoff