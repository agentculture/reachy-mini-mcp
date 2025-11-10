# Reachy Hearing Event Emitter

This service runs inside a Docker container and emits hearing events via Unix Domain Sockets, allowing external applications to subscribe and receive real-time notifications.

## Overview

The **Hearing Event Emitter** is a Python server that:
- Creates a Unix Domain Socket at `/tmp/reachy_sockets/hearing.sock`
- Accepts multiple simultaneous client connections
- Broadcasts hearing events to all connected clients in real-time
- Handles client disconnections gracefully with auto-cleanup
- Runs continuously inside the Docker container

## Architecture

```
┌─────────────────────────────────────┐
│   Docker Container                  │
│   reachy-hearing-service            │
│                                     │
│   ┌───────────────────────────┐    │
│   │ hearing_event_emitter.py  │    │
│   │                           │    │
│   │ - Creates Unix socket     │    │
│   │ - Accepts connections     │    │
│   │ - Generates events        │    │
│   │ - Broadcasts to clients   │    │
│   └───────────┬───────────────┘    │
│               │                     │
└───────────────┼─────────────────────┘
                │
                ▼
    /tmp/reachy_sockets/hearing.sock
                │
                ▼
    ┌───────────┴───────────┐
    │                       │
    ▼                       ▼
[External Client 1]   [External Client 2]
(Python app)          (Node.js app)
```

## How It Works

### 1. Socket Creation
- The emitter creates a Unix Domain Socket on startup
- Socket path: `/tmp/reachy_sockets/hearing.sock`
- Permissions set to `0666` (readable/writable by all users)
- Directory is shared between Docker container and host via volume mount

### 2. Connection Handling
- Runs a background thread to accept new client connections
- Multiple clients can connect simultaneously
- Each client connection is tracked and managed independently
- Disconnected clients are automatically removed from the list

### 3. Event Broadcasting
- Events are generated and broadcast to all connected clients
- Each event is JSON-formatted and newline-delimited
- Thread-safe broadcasting ensures no race conditions
- Failed sends automatically disconnect dead clients

## Event Types

The emitter generates the following types of events:

### `speech_detected`
Emitted when speech is detected (or in demo mode, periodically).
```json
{
  "timestamp": "2025-11-10T12:34:56.789",
  "type": "speech_detected",
  "data": {
    "text": "Hello",
    "confidence": 0.95,
    "language": "en",
    "sequence": 0
  }
}
```

### `sound_detected`
Emitted when a specific sound is detected.
```json
{
  "timestamp": "2025-11-10T12:34:59.789",
  "type": "sound_detected",
  "data": {
    "type": "clap",
    "intensity": 0.8,
    "direction": "front",
    "sequence": 1
  }
}
```

### `keyword_spotted`
Emitted when a wake word or keyword is detected.
```json
{
  "timestamp": "2025-11-10T12:35:02.789",
  "type": "keyword_spotted",
  "data": {
    "keyword": "reachy",
    "confidence": 0.92,
    "sequence": 2
  }
}
```

### `noise_level`
Emitted to report ambient noise levels.
```json
{
  "timestamp": "2025-11-10T12:35:05.789",
  "type": "noise_level",
  "data": {
    "level": 65,
    "unit": "dB",
    "sequence": 3
  }
}
```

### `voice_activity`
Emitted to indicate voice activity detection status.
```json
{
  "timestamp": "2025-11-10T12:35:08.789",
  "type": "voice_activity",
  "data": {
    "active": true,
    "duration": 2.3,
    "sequence": 4
  }
}
```

## Running the Emitter

### Inside Docker (Recommended)

The emitter is designed to run inside the Docker container automatically:

```bash
# Start via docker-compose
docker-compose -f ../docker-compose-vllm.yml up -d reachy-hearing

# View logs
docker logs -f reachy-hearing-service
```

### Standalone (For Testing)

You can also run it directly on the host for testing:

```bash
# Ensure the socket directory exists
mkdir -p /tmp/reachy_sockets

# Run the emitter
python3 hearing_event_emitter.py
```

## Configuration

### Customizing the Socket Path

Edit the `HearingEventEmitter` initialization:

```python
emitter = HearingEventEmitter(socket_path="/custom/path/hearing.sock")
```

Don't forget to update the docker-compose volume mount accordingly.

### Customizing Event Generation

The `generate_sample_events()` method creates demo events. Replace this with your actual audio processing logic:

```python
def generate_sample_events(self):
    """Replace with real audio processing"""
    while self.running:
        # Your audio processing code here
        # Example: read from microphone, process audio, detect events
        
        audio_data = capture_audio()
        if detect_speech(audio_data):
            text = transcribe(audio_data)
            self.emit_event("speech_detected", {
                "text": text,
                "confidence": 0.95,
                "language": "en"
            })
        
        time.sleep(0.1)  # Adjust based on your needs
```

### Adjusting Event Frequency

Change the sleep interval in `generate_sample_events()`:

```python
time.sleep(3)  # Emit every 3 seconds (current)
time.sleep(0.5)  # Emit twice per second (faster)
```

## Client Connection

External applications connect to the socket to receive events:

### Python Example
```python
import socket
import json

sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect("/tmp/reachy_sockets/hearing.sock")

buffer = ""
while True:
    data = sock.recv(4096).decode('utf-8')
    buffer += data
    
    while '\n' in buffer:
        line, buffer = buffer.split('\n', 1)
        event = json.loads(line)
        print(f"Event: {event['type']} - {event['data']}")
```

### Shell Example
```bash
# Listen for events
nc -U /tmp/reachy_sockets/hearing.sock

# With formatted output
nc -U /tmp/reachy_sockets/hearing.sock | jq .
```

## Class Structure

### `HearingEventEmitter`

Main class that manages the event emitter service.

#### Constructor
```python
__init__(socket_path="/tmp/reachy_sockets/hearing.sock")
```

#### Methods

- **`setup_socket()`** - Creates and configures the Unix Domain Socket
- **`accept_connections()`** - Background thread that accepts new client connections
- **`emit_event(event_type, data)`** - Broadcasts an event to all connected clients
- **`generate_sample_events()`** - Demo method that generates sample events (replace with real logic)
- **`start()`** - Starts the service and begins emitting events
- **`stop()`** - Stops the service and cleans up resources

## Error Handling

The emitter includes robust error handling:

- **Connection errors**: Disconnected clients are automatically removed
- **Socket errors**: Socket is cleaned up on shutdown
- **Keyboard interrupt**: Graceful shutdown on Ctrl+C
- **Thread safety**: Lock-based synchronization for client list access

## Logging

The emitter provides informative console output:

```
[INFO] Starting Hearing Event Emitter...
[INFO] Listening on Unix socket: /tmp/reachy_sockets/hearing.sock
[INFO] Client connected. Total clients: 1
[EVENT] Emitted: speech_detected - {'text': 'Hello', 'confidence': 0.95, ...}
[INFO] Client connected. Total clients: 2
[INFO] Removed 1 disconnected client(s). Active: 1
[INFO] Shutting down...
[INFO] Service stopped
```

## Integration with Real Audio Processing

To integrate with real audio processing:

1. **Add audio capture**: Use `pyaudio` or similar to capture audio from microphone
2. **Add speech recognition**: Integrate Whisper, Vosk, or other ASR engine
3. **Add sound detection**: Use audio classification models
4. **Add VAD**: Implement Voice Activity Detection
5. **Replace `generate_sample_events()`**: Replace with real-time audio processing loop

Example audio processing libraries:
- `pyaudio` - Audio I/O
- `whisper` - Speech recognition
- `vosk` - Offline speech recognition
- `webrtcvad` - Voice activity detection
- `librosa` - Audio analysis
- `scipy` - Signal processing

## Dependencies

Current implementation uses only Python standard library:
- `socket` - Unix Domain Socket communication
- `json` - Event serialization
- `threading` - Concurrent client handling
- `datetime` - Event timestamps
- `os` / `pathlib` - File system operations

For audio processing, add to `requirements.txt`:
```
numpy>=1.24.0
pyaudio>=0.2.13
scipy>=1.10.0
librosa>=0.10.0
whisper>=1.0.0
```

## Troubleshooting

### Socket permission denied
```bash
# Check socket permissions
ls -la /tmp/reachy_sockets/hearing.sock

# Should show: srw-rw-rw- (0666 permissions)
# If not, the emitter sets this on creation
```

### Socket already in use
```bash
# The emitter automatically removes old socket on startup
# If it fails, manually remove:
rm /tmp/reachy_sockets/hearing.sock
```

### Container can't create socket
```bash
# Ensure the volume mount exists in docker-compose-vllm.yml:
volumes:
  - /tmp/reachy_sockets:/tmp/reachy_sockets

# Create directory on host if needed:
mkdir -p /tmp/reachy_sockets
```

### No events being emitted
```bash
# Check container logs:
docker logs reachy-hearing-service

# Verify emitter is running:
docker exec reachy-hearing-service ps aux | grep python
```

## Performance Considerations

- **Event rate**: Current demo emits every 3 seconds; adjust based on your needs
- **Buffer size**: Socket buffer is 4096 bytes; increase for high-frequency events
- **Client limit**: No hard limit, but consider limiting connections for performance
- **Thread pool**: Currently uses one thread for accepts; consider thread pool for high client counts

## Security Considerations

- **Socket permissions**: Currently `0666` (world-readable/writable) for ease of use
- **Authentication**: No authentication; add if needed for production
- **Rate limiting**: No rate limiting; add to prevent abuse
- **Input validation**: All events are generated internally; validate if accepting external input

## License

Same as the main project.
