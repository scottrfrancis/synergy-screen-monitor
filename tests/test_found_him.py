"""Unit tests for found-him.py MQTT subscriber"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock, call
import paho.mqtt.client as mqtt
import sys
import os

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mqtt_clients.paho_client import PahoMQTTSubscriber as MQTTSubscriber


class TestMQTTSubscriber:
    """Test cases for MQTTSubscriber class"""
    
    @pytest.fixture
    def mock_bell(self):
        """Mock bell function"""
        return Mock()
    
    @pytest.fixture
    def subscriber(self, mock_bell):
        """Create a test subscriber instance"""
        return MQTTSubscriber(
            broker='test.broker',
            port=1883,
            topic='test/topic',
            key='desktop',
            value='target',
            bell_func=mock_bell
        )
    
    def test_initialization(self, subscriber, mock_bell):
        """Test subscriber initialization"""
        assert subscriber.broker == 'test.broker'
        assert subscriber.port == 1883
        assert subscriber.topic == 'test/topic'
        assert subscriber.key == 'desktop'
        assert subscriber.value == 'target'
        assert subscriber.bell_func == mock_bell
        assert subscriber.connected is False
        assert subscriber.reconnect_delay == 1
        assert subscriber.max_reconnect_delay == 60
    
    @pytest.mark.parametrize('system,expected_call', [
        ('darwin', ['osascript', '-e', 'beep']),
        ('linux', 'paplay /usr/share/sounds/freedesktop/bell.oga 2>/dev/null || echo -e "\\a"'),
        ('windows', 'echo \\a'),
    ])
    def test_get_bell_function(self, subscriber, system, expected_call):
        """Test platform-specific bell functions"""
        with patch('platform.system', return_value=system):
            if system == 'darwin':
                with patch('subprocess.run') as mock_run:
                    bell_func = subscriber.get_bell_function()
                    bell_func()
                    mock_run.assert_called_once_with(expected_call, check=False)
            else:
                with patch('os.system') as mock_system:
                    bell_func = subscriber.get_bell_function()
                    bell_func()
                    mock_system.assert_called_once_with(expected_call)
    
    def test_on_connect_success(self, subscriber):
        """Test successful connection callback"""
        mock_client = Mock()
        subscriber.on_connect(mock_client, None, None, 0, None)
        
        assert subscriber.connected is True
        assert subscriber.reconnect_delay == 1
        mock_client.subscribe.assert_called_once_with('test/topic', qos=1)
    
    def test_on_connect_failure(self, subscriber):
        """Test failed connection callback"""
        mock_client = Mock()
        subscriber.on_connect(mock_client, None, None, 1, None)
        
        assert subscriber.connected is False
        mock_client.subscribe.assert_not_called()
    
    def test_on_disconnect(self, subscriber):
        """Test disconnect callback"""
        mock_client = Mock()
        subscriber.connected = True
        subscriber.on_disconnect(mock_client, None, None, None)
        
        assert subscriber.connected is False
    
    def test_on_message_match(self, subscriber, mock_bell):
        """Test message processing with matching value"""
        mock_client = Mock()
        mock_msg = Mock()
        mock_msg.payload = json.dumps({
            'desktop': 'target',
            'timestamp': '2025-01-28T00:00:00'
        }).encode()
        
        with patch('builtins.print') as mock_print:
            subscriber.on_message(mock_client, None, mock_msg)
        
        mock_bell.assert_called_once()
        mock_print.assert_called_once_with("Match found! desktop = target")
    
    def test_on_message_no_match(self, subscriber, mock_bell):
        """Test message processing without matching value"""
        mock_client = Mock()
        mock_msg = Mock()
        mock_msg.payload = json.dumps({
            'desktop': 'other',
            'timestamp': '2025-01-28T00:00:00'
        }).encode()
        
        with patch('builtins.print') as mock_print:
            subscriber.on_message(mock_client, None, mock_msg)
        
        mock_bell.assert_not_called()
        mock_print.assert_not_called()
    
    def test_on_message_missing_key(self, subscriber, mock_bell):
        """Test message processing with missing key"""
        mock_client = Mock()
        mock_msg = Mock()
        mock_msg.payload = json.dumps({
            'other_key': 'target',
            'timestamp': '2025-01-28T00:00:00'
        }).encode()
        
        with patch('builtins.print') as mock_print:
            subscriber.on_message(mock_client, None, mock_msg)
        
        mock_bell.assert_not_called()
        mock_print.assert_not_called()
    
    def test_on_message_invalid_json(self, subscriber, mock_bell):
        """Test message processing with invalid JSON"""
        mock_client = Mock()
        mock_msg = Mock()
        mock_msg.payload = b'invalid json'
        
        # Should not raise exception
        subscriber.on_message(mock_client, None, mock_msg)
        
        mock_bell.assert_not_called()
    
    @patch('found_him.mqtt.Client')
    @patch('time.sleep')
    def test_connect_with_retry_success(self, mock_sleep, mock_mqtt_client, subscriber):
        """Test successful connection with retry"""
        mock_client = MagicMock()
        mock_mqtt_client.return_value = mock_client
        
        # Simulate successful connection
        def simulate_connect(*args, **kwargs):
            subscriber.on_connect(mock_client, None, None, 0, None)
        
        mock_client.connect.side_effect = simulate_connect
        
        result = subscriber.connect_with_retry()
        
        assert result is True
        assert subscriber.connected is True
        mock_client.connect.assert_called_once_with('test.broker', 1883, keepalive=60)
        mock_client.loop_start.assert_called_once()
    
    @patch('found_him.mqtt.Client')
    @patch('time.sleep')
    @patch('time.time')
    def test_connect_with_retry_timeout(self, mock_time, mock_sleep, mock_mqtt_client, subscriber):
        """Test connection retry with timeout"""
        mock_client = MagicMock()
        mock_mqtt_client.return_value = mock_client
        
        # Simulate timeout
        mock_time.side_effect = [0, 0.1, 10.1, 0, 0.1, 10.1]  # Two timeout cycles
        
        # Run once and break the loop
        with patch.object(subscriber, 'connected', False):
            try:
                # Limit iterations to prevent infinite loop
                iteration_count = 0
                original_sleep = mock_sleep.side_effect
                
                def limited_sleep(seconds):
                    nonlocal iteration_count
                    iteration_count += 1
                    if iteration_count > 1:
                        raise KeyboardInterrupt("Breaking infinite loop")
                    if original_sleep:
                        return original_sleep(seconds)
                
                mock_sleep.side_effect = limited_sleep
                subscriber.connect_with_retry()
            except KeyboardInterrupt:
                pass
        
        # Should have attempted connection
        mock_client.connect.assert_called()
        assert subscriber.reconnect_delay > 1  # Should increase delay
    
    @patch('time.sleep')
    def test_monitor_connection_reconnect(self, mock_sleep, subscriber):
        """Test monitor_connection triggers reconnect when disconnected"""
        subscriber.connected = False
        
        # Mock connect_with_retry
        with patch.object(subscriber, 'connect_with_retry') as mock_connect:
            # Run one iteration then break
            mock_sleep.side_effect = [None, KeyboardInterrupt()]
            
            try:
                subscriber.monitor_connection()
            except KeyboardInterrupt:
                pass
            
            mock_connect.assert_called_once()
    
    @patch('found_him.mqtt.Client')
    def test_run_lifecycle(self, mock_mqtt_client, subscriber):
        """Test complete run lifecycle"""
        mock_client = MagicMock()
        mock_mqtt_client.return_value = mock_client
        
        with patch.object(subscriber, 'connect_with_retry'):
            with patch.object(subscriber, 'monitor_connection', side_effect=KeyboardInterrupt()):
                subscriber.run()
        
        # Should clean up on exit
        mock_client.loop_stop.assert_called_once()
        mock_client.disconnect.assert_called_once()


@pytest.mark.unit
class TestMainFunction:
    """Test the main entry point"""
    
    @patch('sys.argv', ['found-him.py', 'target_desktop'])
    @patch('found_him.MQTTSubscriber')
    def test_main_default_args(self, mock_subscriber_class):
        """Test main with default arguments"""
        from found_him import main
        
        mock_subscriber = MagicMock()
        mock_subscriber_class.return_value = mock_subscriber
        
        main()
        
        # Check subscriber was created with defaults
        mock_subscriber_class.assert_called_once_with(
            broker='vault.local',
            port=1883,
            topic='synergy',
            key='current_desktop',
            value='target_desktop',
            bell_func=None
        )
        
        # Check run was called
        mock_subscriber.run.assert_called_once()
    
    @patch('sys.argv', [
        'found-him.py',
        '-b', 'custom.broker',
        '-p', '1884',
        '-t', 'custom/topic',
        '-k', 'custom_key',
        '--debug',
        'custom_value'
    ])
    @patch('found_him.MQTTSubscriber')
    def test_main_custom_args(self, mock_subscriber_class):
        """Test main with custom arguments"""
        from found_him import main
        
        mock_subscriber = MagicMock()
        mock_subscriber_class.return_value = mock_subscriber
        
        with patch('builtins.print'):  # Suppress debug output
            main()
        
        # Check subscriber was created with custom args
        mock_subscriber_class.assert_called_once_with(
            broker='custom.broker',
            port=1884,
            topic='custom/topic',
            key='custom_key',
            value='custom_value',
            bell_func=None
        )