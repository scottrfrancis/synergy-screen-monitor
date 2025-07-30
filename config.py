"""
Configuration management for Synergy Screen Monitor.

This module handles loading configuration from environment variables (.env files)
with fallback to sensible defaults. It supports both primary (log monitoring) 
and secondary (alert only) deployment patterns.

Environment variable loading priority:
1. Command Line Arguments (highest priority)
2. Environment Variables (.env file)
3. Application Defaults (lowest priority)
"""

import os
import socket
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    # Load .env file if it exists
    load_dotenv()
except ImportError:
    # python-dotenv not installed, environment variables will still work
    pass


class Config:
    """
    Configuration class that loads settings from environment variables.
    
    Supports both primary and secondary deployment modes:
    - Primary: Runs waldo.py (log monitor) + optional found-him.py  
    - Secondary: Runs found-him.py only for specific target desktop
    """
    
    # === Deployment Configuration ===
    ROLE = os.getenv('ROLE', 'secondary')  # primary or secondary
    
    # === MQTT Broker Configuration ===
    MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
    MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
    MQTT_TOPIC = os.getenv('MQTT_TOPIC', 'synergy')
    MQTT_CLIENT_TYPE = os.getenv('MQTT_CLIENT_TYPE', 'paho')
    
    # === Synergy Configuration ===
    # Default Synergy log path (platform-specific)
    @staticmethod
    def _get_default_synergy_log_path() -> str:
        """Get default Synergy log path based on platform."""
        home = Path.home()
        
        # macOS
        if os.name == 'posix' and os.uname().sysname == 'Darwin':
            return str(home / 'Library' / 'Logs' / 'Synergy' / 'synergy.log')
        
        # Windows
        elif os.name == 'nt':
            return str(home / 'AppData' / 'Local' / 'Synergy' / 'synergy.log')
        
        # Linux and other Unix-like systems
        else:
            return str(home / '.local' / 'share' / 'synergy' / 'synergy.log')
    
    SYNERGY_LOG_PATH = os.getenv('SYNERGY_LOG_PATH', _get_default_synergy_log_path())
    
    # === Target Desktop Configuration ===
    # Default to hostname for convenience, can be overridden
    TARGET_DESKTOP = os.getenv('TARGET_DESKTOP', socket.gethostname().lower())
    
    # === Logging Configuration ===
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'ERROR').upper()
    DEBUG_MODE = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
    LOG_DIR = os.getenv('LOG_DIR', './logs')
    
    @classmethod
    def is_primary(cls) -> bool:
        """Check if this is configured as a primary machine."""
        return cls.ROLE.lower() == 'primary'
    
    @classmethod
    def is_secondary(cls) -> bool:
        """Check if this is configured as a secondary machine."""
        return cls.ROLE.lower() == 'secondary'
    
    @classmethod
    def validate_primary_config(cls) -> list:
        """
        Validate configuration for primary deployment.
        
        Returns:
            list: List of configuration errors, empty if valid
        """
        errors = []
        
        # Check if log path exists for primary
        if cls.is_primary():
            log_path = Path(cls.SYNERGY_LOG_PATH)
            if not log_path.exists():
                errors.append(f"Synergy log file not found: {cls.SYNERGY_LOG_PATH}")
            elif not log_path.is_file():
                errors.append(f"Synergy log path is not a file: {cls.SYNERGY_LOG_PATH}")
        
        return errors
    
    @classmethod
    def validate_secondary_config(cls) -> list:
        """
        Validate configuration for secondary deployment.
        
        Returns:
            list: List of configuration errors, empty if valid
        """
        errors = []
        
        # Check if target desktop is specified for secondary
        if cls.is_secondary():
            if not cls.TARGET_DESKTOP or cls.TARGET_DESKTOP.strip() == '':
                errors.append("TARGET_DESKTOP must be specified for secondary machines")
        
        return errors
    
    @classmethod
    def validate_config(cls) -> list:
        """
        Validate configuration based on deployment role.
        
        Returns:
            list: List of configuration errors, empty if valid
        """
        errors = []
        
        # Common validation
        if cls.ROLE.lower() not in ['primary', 'secondary']:
            errors.append(f"Invalid ROLE: {cls.ROLE}. Must be 'primary' or 'secondary'")
        
        if not cls.MQTT_BROKER or cls.MQTT_BROKER.strip() == '':
            errors.append("MQTT_BROKER must be specified")
        
        if cls.MQTT_PORT < 1 or cls.MQTT_PORT > 65535:
            errors.append(f"Invalid MQTT_PORT: {cls.MQTT_PORT}. Must be between 1-65535")
        
        # Role-specific validation
        if cls.is_primary():
            errors.extend(cls.validate_primary_config())
        elif cls.is_secondary():
            errors.extend(cls.validate_secondary_config())
        
        return errors
    
    @classmethod
    def print_config_summary(cls):
        """Print a summary of current configuration."""
        print(f"Configuration Summary:")
        print(f"  Role: {cls.ROLE}")
        print(f"  MQTT Broker: {cls.MQTT_BROKER}:{cls.MQTT_PORT}")
        print(f"  MQTT Topic: {cls.MQTT_TOPIC}")
        print(f"  Client Type: {cls.MQTT_CLIENT_TYPE}")
        
        if cls.is_primary():
            print(f"  Synergy Log: {cls.SYNERGY_LOG_PATH}")
            if cls.TARGET_DESKTOP:
                print(f"  Local Target: {cls.TARGET_DESKTOP}")
        
        if cls.is_secondary():
            print(f"  Target Desktop: {cls.TARGET_DESKTOP}")
        
        print(f"  Log Level: {cls.LOG_LEVEL}")
        print(f"  Debug Mode: {cls.DEBUG_MODE}")


def get_mqtt_config() -> dict:
    """
    Get MQTT configuration as a dictionary.
    
    Returns:
        dict: MQTT configuration parameters
    """
    return {
        'broker': Config.MQTT_BROKER,
        'port': Config.MQTT_PORT,
        'topic': Config.MQTT_TOPIC,
        'client_type': Config.MQTT_CLIENT_TYPE
    }


def override_config(**kwargs):
    """
    Override configuration values (useful for CLI arguments).
    
    Args:
        **kwargs: Configuration key-value pairs to override
    """
    for key, value in kwargs.items():
        if hasattr(Config, key.upper()) and value is not None:
            setattr(Config, key.upper(), value)