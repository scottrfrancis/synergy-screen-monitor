# Synergy Desktop Alert System

A lightweight monitoring system that alerts you when you switch to specific computers in your Synergy setup. Perfect for multi-computer workflows where you need audio notifications when switching between machines.

## What is this?

If you use [Synergy](https://symless.com/synergy) to share a keyboard and mouse between multiple computers, this tool monitors your desktop switches and plays an alert sound when you switch to a specific computer. 

For example, if you have a "studio" computer for audio work, this can beep when you switch to it, reminding you that your audio interface is now active.

## How it Works

```
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
   cd synergy-alert
   ```

2. Install the required Python package:
   ```bash
   pip install paho-mqtt==2.1.0
   ```

3. Ensure you have an MQTT broker running (default expects `vault.local:1883`)

## Usage

### Quick Start

Run the complete system with default settings (alerts when switching to "studio"):
```bash
./start.sh
```

**Note**: You'll need to modify the log path in `start.sh` to match your Synergy installation.

### Manual Usage

Run components separately for testing or custom configurations:

#### Monitor Synergy logs:
```bash
tail -f ~/Library/Logs/Synergy/synergy.log | python waldo.py
```

#### Listen for specific desktop:
```bash
python found-him.py studio
```

#### Custom configuration:
```bash
# Monitor with custom MQTT settings
tail -f /path/to/synergy.log | python waldo.py --broker 192.168.1.100 --topic my-synergy --client-type paho

# Alert for different desktop with custom settings
python found-him.py --broker 192.168.1.100 --topic my-synergy --client-type paho workstation
```

## Configuration Options

### waldo.py (Log Monitor)
- `--broker`: MQTT broker address (default: `vault.local`)
- `--port`: MQTT broker port (default: `1883`)
- `--topic`: MQTT topic to publish to (default: `synergy`)
- `--client-type`: MQTT client type to use (default: `paho`, choices: `paho`)

### found-him.py (Alert Subscriber)
- `--broker, -b`: MQTT broker address (default: `vault.local`)
- `--port, -p`: MQTT broker port (default: `1883`)
- `--topic, -t`: MQTT topic to subscribe to (default: `synergy`)
- `--key, -k`: JSON key to monitor (default: `current_desktop`)
- `--client-type`: MQTT client type to use (default: `paho`, choices: `paho`)
- `value`: Desktop name to alert on (required, e.g., "studio")

## Message Format

The system publishes JSON messages to MQTT:
```json
{
  "current_desktop": "studio"
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

Future client support can be added without changing existing code.

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

### Version Compatibility
- This system works with all Synergy versions that write desktop switch events to logs
- Log format changes are handled by the regex pattern matching
- No modifications to Synergy itself are required

## Examples

### Monitor multiple desktops
Run multiple instances of `found-him.py`:
```bash
python found-him.py studio &
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