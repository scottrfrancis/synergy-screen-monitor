# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based MQTT monitoring system for Synergy (keyboard/mouse sharing software). It monitors Synergy logs and publishes desktop switching events to an MQTT broker, with a subscriber that triggers alerts when specific desktops become active.

## Development Commands

### Running the System
```bash
# Start the complete monitoring system
./start.sh
```

### Running Components Individually
```bash
# Run the log monitor (requires Synergy logs piped to stdin)
tail -f ~/Library/Logs/Synergy/synergy.log | python waldo.py

# Run the alert subscriber
python found-him.py --broker localhost --topic synergy --key desktop --value workstation
```

### Testing
```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=. --cov-report=html

# Run only unit tests
pytest -m unit

# Run integration tests (requires MQTT broker)
pytest -m integration
```

### Dependencies
```bash
# Install all dependencies (including development dependencies)
pip install -r requirements.txt

# Install only runtime dependencies
pip install paho-mqtt==2.1.0
```

## Architecture

The system consists of three components:

1. **waldo.py** - Log monitor that reads Synergy logs from stdin and publishes desktop switching events to MQTT
   - Extracts system names from log entries
   - Publishes JSON messages to MQTT topic "synergy"
   - Default broker: localhost:1883

2. **found-him.py** - MQTT subscriber that triggers alerts when specific desktop is active
   - Cross-platform bell/beep functionality
   - Configurable via command-line arguments

3. **start.sh** - Orchestration script that launches both components
   - Currently hardcoded to monitor for "workstation" desktop
   - Log path hardcoded to: /Users/scottfrancis/Library/Logs/Synergy/synergy.log

## Key Considerations

- The system uses MQTT broker at `localhost:1883` by default
- Log paths are currently hardcoded in start.sh and should be made configurable
- Comprehensive testing infrastructure with pytest (run tests with `pytest`)
- Cross-platform alert functionality is implemented for macOS, Linux, and Windows
- All JSON messages include a timestamp field
- Enhanced error handling and logging throughout the codebase
- Retry logic with exponential backoff for robust operation
- Full API documentation with docstrings for all classes and methods
- Log rotation is handled correctly using `tail -F` (not `tail -f`) which follows the file by name
- The log-based approach is the standard method for integrating with Synergy without modifications

## Design Decisions

### Why Log-Based Monitoring?

After investigating multiple approaches for real-time desktop focus feedback, the log-based solution was chosen for these reasons:

1. **Version Independence**: Works with any Synergy version without modification. Changes to Synergy's internal protocol, encryption, or port numbers don't affect log monitoring.

2. **Cross-System Support**: MQTT enables monitoring and alerting across multiple systems on the network, not limited to a single machine.

3. **No Synergy Modifications**: Synergy updates can be applied without any changes to the monitoring system.

4. **Synergy Limitations**: Synergy does not provide native hooks, APIs, or configuration options for executing scripts on screen enter/leave events. The configuration file only supports keyboard shortcuts and screen layout.

### Alternatives Considered and Rejected

- **Direct TCP Monitoring (Port 24800)**: Would break with encryption changes or protocol updates
- **System Event Monitoring**: Limited to single-system scope, doesn't track focus across multiple computers
- **Synergy Config Hooks**: Not supported - Synergy lacks native event hook functionality
- **Forking Synergy**: Creates maintenance burden and prevents easy updates

## Technical Implementation Details

### Log Parsing
- Uses regex pattern `r'to "([^-]+)'` to extract desktop names from Synergy log entries
- Monitors log lines containing "switched to" events

### Log Rotation Handling
- `start.sh` uses `tail -F` (uppercase F) which follows the file by name
- Automatically handles when Synergy rotates logs (e.g., synergy.log → synergy.log.1)
- Continues monitoring the new log file without interruption

### MQTT Architecture
- Enables distributed monitoring across the network
- Publishers and subscribers can run on different systems
- Provides reliable message delivery with QoS levels

### Dependency Injection Framework
- **Abstract Interfaces**: `MQTTPublisherInterface` and `MQTTSubscriberInterface` define standard operations
- **Factory Pattern**: `MQTTClientFactory` provides centralized client creation
- **Runtime Selection**: Client type can be specified via CLI argument `--client-type`
- **Extensible Design**: New MQTT client implementations can be added without changing existing code

#### Current Implementation Structure:
```
mqtt_clients/
├── __init__.py          # Package exports
├── interface.py         # Abstract base classes
├── paho_client.py       # Paho MQTT implementation
└── factory.py           # Client factory
```

#### Current Client Implementations:
- **Paho Client**: Standard Python MQTT client (default)
- **NanoMQ Client**: High-performance C++ client with Python bindings via pybind11

#### Adding New Client Types:
1. Implement `MQTTPublisherInterface` and `MQTTSubscriberInterface`
2. Add new client type to `MQTTClientFactory.SUPPORTED_CLIENTS`
3. Update factory methods to handle new client type
4. CLI arguments automatically support new client types

## NanoMQ Integration

### Architecture Overview
The NanoMQ integration consists of three layers:
1. **NanoSDK C Library**: High-performance MQTT implementation
2. **Python Bindings**: C++ extension using pybind11
3. **Python Client Classes**: Interface-compliant wrappers

### Build System
```
CMakeLists.txt           # NanoSDK build configuration
setup.py                 # Python extension build
build.sh                 # Automated build script
external/nanosdk/        # Git submodule
```

### Key Components

#### C++ Extension (`mqtt_clients/nanomq_bindings.cpp`)
- Uses pybind11 for Python-C++ integration
- Wraps NanoSDK MQTT client functionality
- Provides thread-safe message handling
- Implements connection management with retry logic

#### Python Client Classes (`mqtt_clients/nanomq_client.py`)
- `NanoMQTTPublisher`: High-performance message publishing
- `NanoMQTTSubscriber`: Efficient message subscription with callbacks
- Full interface compliance with existing Paho implementation
- Graceful fallback when bindings are unavailable

#### Factory Integration
- Runtime client selection via `--client-type nanomq`
- Automatic availability detection
- Seamless switching between Paho and NanoMQ clients

### Build Process
1. **Git Submodule**: NanoSDK integrated as external dependency
2. **CMake Build**: Compiles NanoSDK with optimized settings
3. **Python Extension**: pybind11 creates Python-accessible bindings
4. **Automated Testing**: Validates build and functionality

### Performance Benefits
- **10x Performance**: Faster than Paho on multi-core systems
- **QUIC Support**: Ultra-low latency transport protocol
- **Async I/O**: Fully asynchronous with multi-threading
- **0-RTT Reconnection**: Fast connection recovery

## Configuration Management

### Environment-Based Configuration System
The system uses a flexible configuration approach that eliminates hardcoded values while supporting multiple deployment patterns.

#### Configuration Loading Priority:
1. **Command Line Arguments** (highest priority)  
2. **Environment Variables** (.env file)
3. **Application Defaults** (lowest priority)

#### Configuration Files Structure:
```
config.py                 # Configuration management module
.env.primary.example      # Primary machine template
.env.secondary.example    # Secondary machine template
.env                      # User's actual config (gitignored)
```

### Multi-Machine Deployment Architecture

#### Primary Machine (Synergy Server):
- **Role**: `ROLE=primary`
- **Services**: Runs `waldo.py` (log monitor) + optional `found-him.py`  
- **Requirements**: Access to Synergy logs (`SYNERGY_LOG_PATH`)
- **Function**: Publishes all desktop switching events to MQTT

#### Secondary Machines (Synergy Clients):
- **Role**: `ROLE=secondary`
- **Services**: Runs `found-him.py` only
- **Requirements**: `TARGET_DESKTOP` configuration
- **Function**: Subscribes to MQTT for specific desktop alerts

### Configuration Parameters

#### Core Settings:
- `ROLE`: Deployment role (`primary` or `secondary`)
- `MQTT_BROKER`: Broker hostname/IP address
- `MQTT_PORT`: Broker port (default: 1883)
- `MQTT_TOPIC`: Topic for desktop events (default: synergy)
- `MQTT_CLIENT_TYPE`: Client implementation (default: paho)

#### Primary-Specific Settings:
- `SYNERGY_LOG_PATH`: Path to Synergy log file (platform-aware defaults)
- `TARGET_DESKTOP`: Optional local desktop to monitor

#### Secondary-Specific Settings:
- `TARGET_DESKTOP`: Required desktop name to monitor for alerts

#### Logging Settings:
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `DEBUG_MODE`: Enable debug mode (true/false)
- `LOG_DIR`: Directory for application logs (default: ./logs)

### Enhanced start.sh Script

The startup script now provides:
- **Role-based service startup** (primary vs secondary mode)
- **Configuration validation** with helpful error messages
- **Environment variable loading** from .env files
- **Service health monitoring** and error handling
- **Automatic service orchestration** based on configuration