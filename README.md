# Synergy Desktop Alert System

A lightweight monitoring system that alerts you when you switch to specific computers in your Synergy setup. Perfect for multi-computer workflows where you need audio notifications when switching between machines.

## What is this?

If you use [Synergy](https://symless.com/synergy) to share a keyboard and mouse between multiple computers, this tool monitors your desktop switches and plays an alert sound when you switch to a specific computer.

For example, if you have a "workstation" computer for audio work, this can beep when you switch to it, reminding you that your audio interface is now active.

## How it Works

```ini
Synergy Logs → waldo.py → MQTT Broker → found-him.py → Alert Sound
```

1. **waldo.py** monitors Synergy's log file for desktop switching events
2. When you switch desktops, it publishes a message to an MQTT broker
3. **found-him.py** subscribes to these messages and plays a sound when your target desktop becomes active

## Design Philosophy

This system uses log monitoring as its integration method with Synergy. This approach was chosen after evaluating several alternatives because:

- **Version Independence**: Works with any Synergy version without modification
- **No Synergy Changes**: Synergy updates can be applied without affecting the monitoring system
- **Cross-System Support**: MQTT enables alerts across multiple computers on your network
- **Synergy Limitations**: Synergy does not provide native hooks or APIs for screen switch events

## Requirements

- Python 3.x
- MQTT broker (e.g., Mosquitto) running on your network
- Synergy installed and logging enabled
- `paho-mqtt` Python library

## Installation

1. Clone this repository:

```bash
git clone <repository-url>
cd synergy-screen-monitor
```

2. Install the required Python packages:

```bash
pip install -r requirements.txt
```

3. Set up configuration:

```bash
# For primary machine (runs log monitor)
cp .env.example .env
```

4. Edit the `.env` file to match your setup (see Configuration section below)

5. Ensure you have an MQTT broker running (configurable via .env file)

## Usage

### Quick Start

1. **Primary Machine Setup** (runs log monitor):

```bash
# Copy and edit primary configuration
cp .env.example .env
# Edit .env file - set SYNERGY_LOG_PATH and MQTT_BROKER

# Start services
./start.sh
```

2. **Secondary Machine Setup** (alert only):

```bash
# Copy and edit secondary configuration  
cp .env.example .env
# Edit .env file - set TARGET_DESKTOP and MQTT_BROKER

# Start alert service
./start.sh
```

The script automatically detects the role from your `.env` file and starts the appropriate services.

### Automatic Service Management with Watchdog

For production use, install the watchdog service to automatically recover from failures:

```bash
# Install watchdog as a launchd service (runs at login)
./install-watchdog.sh

# The watchdog will:
# - Start automatically at login
# - Monitor service health every 30 seconds
# - Automatically restart failed services
# - Wait for MQTT broker recovery before restarting
# - Prevent restart loops with throttling

# View watchdog logs
tail -f logs/watchdog.log

# Uninstall watchdog service
./uninstall-watchdog.sh
```

**Benefits:**
- Automatic recovery from broker crashes
- Automatic recovery from service crashes
- Prevents orphaned processes
- Logs all restart attempts
- Restart throttling (max 3 restarts per 5 minutes)

### Manual Service Control

```bash
# Stop all services
./stop.sh

# Start services manually (without watchdog)
./start.sh

# Restart everything
./stop.sh && ./start.sh
```

### Manual Usage

Run components separately for testing or custom configurations:

#### Monitor Synergy logs:

```bash
tail -f ~/Library/Logs/Synergy/synergy.log | python waldo.py
```

#### Listen for specific desktop:

```bash
python found-him.py workstation
```

#### Custom configuration:

```bash
# Monitor with custom MQTT settings
tail -f /path/to/synergy.log | python waldo.py --broker 192.168.1.100 --topic my-synergy --client-type paho

# Alert for different desktop with custom settings
python found-him.py --broker 192.168.1.100 --topic my-synergy --client-type paho workstation
```

## Configuration

The system uses a combination of `.env` files and command-line arguments for configuration. Command-line arguments take precedence over environment variables.

### Environment Configuration (.env files)

#### Configuration (.env.example)

```bash
ROLE=primary
SYNERGY_LOG_PATH=/Users/username/Library/Logs/Synergy/synergy.log
TARGET_DESKTOP=          # Optional: alert for this machine too
MQTT_BROKER=localhost
MQTT_PORT=1883
MQTT_TOPIC=synergy
MQTT_CLIENT_TYPE=nanomq
LOG_LEVEL=ERROR
DEBUG_MODE=false

# Watchdog Configuration (optional)
WATCHDOG_CHECK_INTERVAL=30        # Health check interval (seconds)
WATCHDOG_MAX_RESTARTS=3           # Max restarts within window
WATCHDOG_RESTART_WINDOW=300       # Restart window (seconds)
WATCHDOG_BROKER_TIMEOUT=5         # Broker check timeout (seconds)
```

#### Secondary Machine Configuration

For secondary machines (alert-only), copy `.env.example` to `.env` and modify:

```bash
ROLE=secondary
TARGET_DESKTOP=workstation    # Required: desktop name to monitor
MQTT_BROKER=primary-machine.local  # Point to primary machine
MQTT_CLIENT_TYPE=nanomq
# SYNERGY_LOG_PATH not needed for secondary machines
```

### Command Line Options

#### waldo.py (Log Monitor)

- `--broker`: MQTT broker address
- `--port`: MQTT broker port
- `--topic`: MQTT topic to publish to
- `--client-type`: MQTT client type (`paho`, `nanomq`)
- `--debug`: Enable debug logging

#### found-him.py (Alert Subscriber)

- `--broker, -b`: MQTT broker address
- `--port, -p`: MQTT broker port
- `--topic, -t`: MQTT topic to subscribe to
- `--key, -k`: JSON key to monitor (default: `current_desktop`)
- `--client-type`: MQTT client type (`paho`, `nanomq`)
- `--debug`: Enable debug logging
- `value`: Target desktop name (required positional argument)

### Multi-Machine Deployment

#### Deployment Topology

```ini
Primary Machine (Synergy Server)
├── Runs waldo.py (log monitor)
├── Publishes desktop switch events to MQTT
└── Optionally runs found-him.py for local alerts

Secondary Machines (Synergy Clients)  
├── Run found-him.py only
├── Subscribe to MQTT for their specific desktop
└── Trigger alerts when their desktop becomes active
```

#### Setup Process

1. __Primary Machine__: Set `ROLE=primary`, configure `SYNERGY_LOG_PATH`
2. __Secondary Machines__: Set `ROLE=secondary`, configure `TARGET_DESKTOP`
3. __All Machines__: Point `MQTT_BROKER` to the same broker (primary or dedicated)
4. **Run**: Execute `./start.sh` on each machine

## Message Format

The system publishes JSON messages to MQTT:

```json
{
  "current_desktop": "workstation"
}
```

## Platform Support

Alert sounds work across platforms:

- **macOS**: Uses `osascript` to play system beep
- **Linux**: Uses `paplay` or falls back to terminal bell
- **Windows**: Uses terminal bell character

## Technical Details

### Log Monitoring

- Uses `tail -F` (not `tail -f`) to properly handle log rotation
- When Synergy rotates logs, monitoring continues seamlessly with the new file
- Extracts desktop names using regex pattern `r'to "([^-]+)'` from log entries

### Architecture Decisions

**Alternatives Considered:**

- **Direct TCP Monitoring**: Rejected - would break with Synergy encryption or protocol changes
- **System Event Hooks**: Rejected - limited to single system, doesn't track cross-system focus
- **Synergy Config Hooks**: Rejected - Synergy doesn't support script execution on screen events
- **Modified Synergy Fork**: Rejected - creates maintenance burden, prevents easy updates

The log-based approach is the recommended integration method for Synergy monitoring.

### Dependency Injection Architecture

The system uses a dependency injection framework for MQTT client selection:

- **Extensible Design**: Easy to add new MQTT client implementations
- **Runtime Selection**: Choose client type via `--client-type` argument
- **Interface-Based**: All clients implement consistent abstract interfaces
- **Factory Pattern**: Centralized client creation through `MQTTClientFactory`

Current supported clients:

- `paho`: Eclipse Paho MQTT Python client (default)
- `nanomq`: NanoSDK high-performance MQTT client with QUIC support

Future client support can be added without changing existing code.

## NanoMQ High-Performance Client

The system includes support for NanoSDK, a high-performance MQTT client library with QUIC support, offering significantly better performance than the default Paho client.

### Building NanoMQ Support

#### Prerequisites

- CMake 3.16+
- C++17 compatible compiler (GCC 7+, Clang 6+, MSVC 2017+)
- Python 3.8+
- Git (for submodules)

#### Automated Build

```bash
# Build everything automatically
./build.sh

# Clean build
./build.sh --clean

# Skip tests
./build.sh --skip-tests
```

#### Manual Build

```bash
# Install build dependencies
pip install -r requirements.txt

# Initialize submodules (if not done automatically)
git submodule update --init --recursive

# Build NanoSDK and Python bindings
python setup.py build_ext --inplace

# Test the build
python -c "import nanomq_bindings; print('NanoMQ bindings work!')"
```

### Using NanoMQ Client

Once built, use NanoMQ client by specifying `--client-type nanomq`:

```bash
# Use NanoMQ for log monitoring
tail -f ~/Library/Logs/Synergy/synergy.log | python waldo.py --client-type nanomq

# Use NanoMQ for alerts
python found-him.py workstation --client-type nanomq

# Use in configuration files
MQTT_CLIENT_TYPE=nanomq
```

### Performance Benefits

NanoMQ provides significant performance improvements:

- **10x faster** than Paho on multi-core systems
- **Ultra-low latency** with MQTT over QUIC support
- **Better scalability** with async I/O design
- **Built-in reconnection** with 0-RTT fast handshake

### NanoMQ vs Paho Comparison

| Feature | Paho | NanoMQ |
|---------|------|--------|
| Performance | Standard | 10x faster |
| QUIC Support | No | Yes |
| Memory Usage | Higher | Lower |
| Reconnection | Basic | 0-RTT fast handshake |
| Threading | Single-threaded | Multi-core optimized |
| Deployment | Python only | Requires C++ build |

## Troubleshooting

### No alerts when switching desktops

1. Check MQTT broker is running: `mosquitto_sub -h vault.local -t synergy`
2. Verify Synergy is logging desktop switches
3. Ensure log file path is correct in `start.sh`
4. **Log rotation**: If alerts stop working after time, check if Synergy rotated logs - `start.sh` uses `tail -F` to handle this automatically

### Connection refused errors

- Verify MQTT broker address and port
- Check firewall settings
- Ensure MQTT broker allows connections from your host

### No sound on alerts

- macOS: Check system sound is not muted
- Linux: Ensure `paplay` is installed or terminal bell is enabled
- Windows: Enable system sounds

### NanoMQ Client Issues

- **Import Error**: Run `./build.sh` to build the NanoMQ bindings
- **Build Failures**: Ensure CMake 3.16+ and C++17 compiler are installed
- **Submodule Missing**: Run `git submodule update --init --recursive`
- **Permission Errors**: May need developer tools on macOS: `xcode-select --install`

### Watchdog Issues

**Watchdog not starting services:**
1. Check watchdog logs: `tail -f logs/watchdog.log`
2. Verify broker is reachable: `nc -zv your-broker-host 1883`
3. Check for restart throttling (too many restarts in 5 minutes)
4. Manual recovery: `./stop.sh && ./start.sh`

**Too many restarts:**
- Watchdog throttles after 3 restarts in 5 minutes
- This prevents restart loops from persistent problems
- Check logs to identify root cause: `tail -100 logs/watchdog.log`
- Fix the underlying issue (broker down, config error, etc.)

**Check watchdog status:**
```bash
# Is watchdog running?
launchctl list | grep synergy.watchdog

# View recent activity
tail -30 logs/watchdog.log

# Manually trigger restart
launchctl kickstart -k gui/$(id -u)/com.synergy.watchdog
```

**Multiple orphaned processes after macOS upgrade:**
- Run `./stop.sh` to clean up all processes
- Restart watchdog: `launchctl kickstart -k gui/$(id -u)/com.synergy.watchdog`

### Version Compatibility

- This system works with all Synergy versions that write desktop switch events to logs
- Log format changes are handled by the regex pattern matching
- No modifications to Synergy itself are required

## Examples

### Monitor multiple desktops

Run multiple instances of `found-him.py`:

```bash
python found-him.py workstation &
python found-him.py workstation &
python found-him.py laptop &
```

### Different alerts for different desktops

Modify `found-him.py` to play different sounds based on the desktop name.

### Integration with other systems

Since this uses MQTT, you can integrate with:

- Home automation systems
- Logging services
- Custom notification systems

## License

This project is provided as-is for personal use.