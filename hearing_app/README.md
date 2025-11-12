# Hearing App - Speech Detection Service

A lightweight Voice Activity Detection (VAD) service that detects speech and emits events via Unix Domain Socket.

## Features

- **Voice Activity Detection**: Uses WebRTC VAD for robust speech detection
- **Event Emission**: Sends speech start/stop events via Unix Domain Socket
- **Async Architecture**: Efficient asyncio-based implementation
- **Multiple Clients**: Supports multiple simultaneous client connections
- **Configurable**: Environment-based configuration
- **Docker Ready**: Designed to run in the reachy-hearing-service container

## Architecture

```
┌─────────────────────────────────────┐
│   Hearing Event Emitter Service    │
│                                     │
│  ┌──────────┐      ┌─────────────┐ │
│  │  Audio   │──────│   VAD       │ │
│  │  Input   │      │   Engine    │ │
│  └──────────┘      └─────────────┘ │
│                          │          │
│                          ▼          │
│                  ┌──────────────┐   │
│                  │  Event       │   │
│                  │  Emitter     │   │
│                  └──────────────┘   │
└──────────────────────┬──────────────┘
                       │
                       │ Unix Domain Socket
                       │ /tmp/reachy_sockets/hearing.sock
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
   Client 1       Client 2       Client N
```

## Installation

### Dependencies

```bash
pip install -r requirements.txt
```

### Requirements

- Python 3.8+
- PyAudio
- WebRTC VAD
- NumPy
- python-dotenv

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Audio Device Configuration
AUDIO_DEVICE_NAME=respeaker

# Socket Configuration
SOCKET_PATH=/tmp/reachy_sockets/hearing.sock

# VAD Configuration
VAD_AGGRESSIVENESS=3
SAMPLE_RATE=16000
CHUNK_DURATION_MS=30

# Speech Detection Configuration
MIN_SILENCE_DURATION=2.5
SPEECH_THRESHOLD_LOWER=1500
SPEECH_THRESHOLD_UPPER=2500
AUDIO_BUFFER_SIZE=100
```

### Configuration Options

- **AUDIO_DEVICE_NAME**: Name of the audio input device (e.g., "respeaker", "default")
- **VAD_AGGRESSIVENESS**: 0-3, higher = more aggressive filtering (3 recommended)
- **SAMPLE_RATE**: Audio sample rate in Hz (16000 recommended for VAD)
- **MIN_SILENCE_DURATION**: Seconds of silence before speech is considered ended
- **SAVE_AUDIO_FILES**: Set to "true" to save audio files for debugging

## Usage

### Command Line

```bash
# Basic usage
python3 hearing_event_emitter.py

# Specify device
python3 hearing_event_emitter.py --device ReSpeaker

# Specify language (for future use)
python3 hearing_event_emitter.py --device ReSpeaker --language en
```

### Docker Compose

The service is configured to run in the `reachy-hearing` container:

```yaml
reachy-hearing:
  image: reachy-hearing-thor:r38.2.arm64-sbsa-cu130-24.04
  container_name: reachy-hearing-service
  command: >
    sh -c "
    pip install --no-cache-dir -q -r /app/requirements.txt &&
    python3 hearing_event_emitter.py --device ReSpeaker --language en
    "
```

Start the service:

```bash
docker compose -f docker-compose-vllm.yml up reachy-hearing
```

## Event Format

Events are emitted as JSON objects, one per line:

### Speech Started Event

```json
{
  "type": "speech_started",
  "timestamp": "2025-11-11T10:30:45.123456",
  "data": {
    "event_number": 1,
    "timestamp": "2025-11-11 10:30:45"
  }
}
```

### Speech Stopped Event

```json
{
  "type": "speech_stopped",
  "timestamp": "2025-11-11T10:30:48.456789",
  "data": {
    "event_number": 1,
    "duration": 3.45,
    "timestamp": "2025-11-11 10:30:48"
  }
}
```

## Client Connection

Clients connect via Unix Domain Socket:

```python
import socket
import json

# Connect to socket
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect('/tmp/reachy_sockets/hearing.sock')

# Receive events
while True:
    data = sock.recv(4096).decode('utf-8')
    for line in data.split('\n'):
        if line.strip():
            event = json.loads(line)
            print(f"Event: {event['type']}")
```

See `../hearing_event_client.py` for a complete client implementation.

## Development

### Testing Locally

```bash
# Set environment variables
export AUDIO_DEVICE_NAME=default
export SOCKET_PATH=./test_hearing.sock

# Run the service
python3 hearing_event_emitter.py

# In another terminal, run the client
python3 ../hearing_event_client.py
```

### Debugging

Enable audio file saving:

```bash
export SAVE_AUDIO_FILES=true
```

This will save each detected speech segment as a WAV file for analysis.

### Logging

The service uses Python's logging module. Adjust the log level in the code:

```python
logging.basicConfig(level=logging.INFO)  # Change to DEBUG for verbose output
```

## Differences from microphone-listener.py

This implementation is a streamlined version of the original `microphone-listener.py`:

1. **Removed STT**: No Whisper transcription (focus on detection only)
2. **Server Mode**: Acts as a socket server instead of client
3. **Event System**: Emits structured JSON events
4. **Multiple Clients**: Supports multiple simultaneous connections
5. **No OpenAI Dependency**: Removed transcription service
6. **Simplified**: Focused on speech detection and event emission

## Troubleshooting

### No audio device found

Check available devices:

```python
import pyaudio
p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    print(p.get_device_info_by_index(i))
```

### Permission denied on socket

Ensure the socket directory is writable:

```bash
sudo mkdir -p /tmp/reachy_sockets
sudo chmod 777 /tmp/reachy_sockets
```

### VAD not detecting speech

- Try adjusting `VAD_AGGRESSIVENESS` (lower = less aggressive)
- Check `MIN_SILENCE_DURATION` (higher = longer wait before ending)
- Verify microphone is working and not muted

## License

See LICENSE file in the repository root.
