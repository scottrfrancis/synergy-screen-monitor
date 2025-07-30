"""Integration tests for the Synergy MQTT monitoring system"""

import pytest
import json
import time
import threading
from unittest.mock import patch, Mock
import paho.mqtt.client as mqtt
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from waldo import MQTTPublisher
from found_him import MQTTSubscriber


@pytest.mark.integration
class TestSystemIntegration:
    """End-to-end integration tests"""
    
    @pytest.fixture
    def test_broker(self):
        """Return test broker configuration"""
        return {
            'host': 'localhost',
            'port': 1883,
            'topic': 'test/synergy'
        }
    
    def test_publish_subscribe_flow(self, test_broker):
        """Test complete publish-subscribe flow"""
        # Note: This test requires a running MQTT broker
        pytest.skip("Requires MQTT broker running on localhost:1883")
        
        received_messages = []
        bell_rang = False
        
        def mock_bell():
            nonlocal bell_rang
            bell_rang = True
        
        # Create subscriber
        subscriber = MQTTSubscriber(
            broker=test_broker['host'],
            port=test_broker['port'],
            topic=test_broker['topic'],
            key='current_desktop',
            value='target_system',
            bell_func=mock_bell
        )
        
        # Override on_message to capture messages
        original_on_message = subscriber.on_message
        def capture_on_message(client, userdata, msg):
            received_messages.append(json.loads(msg.payload.decode()))
            original_on_message(client, userdata, msg)
        
        subscriber.on_message = capture_on_message
        
        # Start subscriber in thread
        subscriber_thread = threading.Thread(target=subscriber.run)
        subscriber_thread.daemon = True
        subscriber_thread.start()
        
        # Wait for subscriber to connect
        time.sleep(2)
        
        # Create publisher
        publisher = MQTTPublisher(
            broker_address=test_broker['host'],
            port=test_broker['port'],
            topic=test_broker['topic']
        )
        
        # Connect publisher
        publisher.connect_with_retry()
        
        # Test cases
        test_messages = [
            {'current_desktop': 'other_system', 'timestamp': '2025-01-28T00:00:00'},
            {'current_desktop': 'target_system', 'timestamp': '2025-01-28T00:00:01'},
            {'current_desktop': 'another_system', 'timestamp': '2025-01-28T00:00:02'},
        ]
        
        # Publish messages
        for msg in test_messages:
            publisher.publish(json.dumps(msg))
            time.sleep(0.5)
        
        # Wait for messages to be received
        time.sleep(2)
        
        # Verify results
        assert len(received_messages) == 3
        assert bell_rang is True  # Bell should have rung for 'target_system'
        
        # Clean up
        publisher.close()
        subscriber.client.loop_stop()
        subscriber.client.disconnect()


@pytest.mark.integration
class TestLogProcessingIntegration:
    """Test log processing with mocked components"""
    
    @patch('waldo.MQTTPublisher')
    def test_log_processing_pipeline(self, mock_publisher_class):
        """Test complete log processing pipeline"""
        from waldo import process_logs
        
        # Mock publisher
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = True
        mock_publisher.connect_with_retry.return_value = True
        
        # Simulate log entries
        test_logs = [
            'INFO: some unrelated log\n',
            'INFO: switched to "desktop1-\n',
            'DEBUG: another log entry\n',
            'INFO: switched to "desktop2-\n',
            'ERROR: connection lost\n',
            'INFO: switched to "desktop3-\n',
        ]
        
        published_messages = []
        
        def capture_publish(message):
            published_messages.append(json.loads(message))
            return True
        
        mock_publisher.publish.side_effect = capture_publish
        
        # Process logs
        with patch('sys.stdin', test_logs):
            try:
                process_logs('test.broker', 1883, 'test/topic')
            except StopIteration:
                pass  # Expected when stdin exhausted
        
        # Verify
        assert len(published_messages) == 3
        assert published_messages[0]['current_desktop'] == 'desktop1'
        assert published_messages[1]['current_desktop'] == 'desktop2'
        assert published_messages[2]['current_desktop'] == 'desktop3'
        
        # All messages should have timestamps
        for msg in published_messages:
            assert 'timestamp' in msg
            assert msg['timestamp']  # Not empty


@pytest.mark.integration
class TestReconnectionScenarios:
    """Test various reconnection scenarios"""
    
    def test_publisher_reconnection(self):
        """Test publisher handles disconnection and reconnection"""
        publisher = MQTTPublisher('test.broker', 1883, 'test/topic')
        
        # Simulate connection then disconnection
        publisher.connected = True
        publisher.on_disconnect(None, None, None, 0, None)
        
        assert publisher.connected is False
        
        # Verify publish triggers reconnection
        with patch.object(publisher, 'connect_with_retry') as mock_connect:
            with patch.object(publisher, 'client', Mock()) as mock_client:
                mock_client.publish.return_value.rc = mqtt.MQTT_ERR_NO_CONN
                
                result = publisher.publish('test message')
                
                assert result is False
                mock_connect.assert_called_once()
    
    def test_subscriber_reconnection(self):
        """Test subscriber handles disconnection and reconnection"""
        subscriber = MQTTSubscriber(
            broker='test.broker',
            port=1883,
            topic='test/topic',
            key='key',
            value='value',
            bell_func=lambda: None
        )
        
        # Simulate disconnection
        subscriber.connected = True
        subscriber.on_disconnect(None, None, None, None)
        
        assert subscriber.connected is False
        
        # Test monitor_connection triggers reconnect
        with patch.object(subscriber, 'connect_with_retry') as mock_connect:
            with patch('time.sleep', side_effect=[None, KeyboardInterrupt()]):
                try:
                    subscriber.monitor_connection()
                except KeyboardInterrupt:
                    pass
            
            mock_connect.assert_called_once()


@pytest.mark.integration
@pytest.mark.slow
class TestStressScenarios:
    """Stress test scenarios"""
    
    @patch('waldo.MQTTPublisher')
    def test_high_volume_publishing(self, mock_publisher_class):
        """Test handling high volume of messages"""
        from waldo import process_logs
        
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher
        mock_publisher.publish.return_value = True
        mock_publisher.connect_with_retry.return_value = True
        
        # Generate many log entries
        test_logs = []
        for i in range(1000):
            test_logs.append(f'INFO: switched to "desktop{i}-\n')
        
        publish_count = 0
        
        def count_publish(message):
            nonlocal publish_count
            publish_count += 1
            return True
        
        mock_publisher.publish.side_effect = count_publish
        
        # Process logs
        with patch('sys.stdin', test_logs):
            try:
                process_logs('test.broker', 1883, 'test/topic')
            except StopIteration:
                pass
        
        assert publish_count == 1000