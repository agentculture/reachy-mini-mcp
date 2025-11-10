# Reachy Hearing Event Emitter

This service runs inside a Docker container and emits hearing events via Unix Domain Sockets, allowing external applications to subscribe and receive real-time notifications.

## Overview

The **Hearing Event Emitter** is a Python server that:
- **Captures audio** from ReSpeaker USB microphone array
- **Detects voice activity** using SileroVAD
- **Transcribes speech** using Faster-Whisper
- **Detects language** and filters for English (configurable)
- Creates a Unix Domain Socket at `/tmp/reachy_sockets/hearing.sock`
- Accepts multiple simultaneous client connections
- Broadcasts hearing events to all connected clients in real-time
- Handles client disconnections gracefully with auto-cleanup
- Runs continuously inside the Docker container

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│   Docker Container (reachy-hearing-service)                 │
│                                                              │
│   ┌──────────────────────────────────────────────────┐     │
│   │ Audio Processing Pipeline                        │     │
│   │                                                   │     │
│   │  ReSpeaker USB ──> PyAudio ──> Audio Chunks     │     │
│   │                         │                         │     │
│   │                         ▼                         │     │
│   │                  SileroVAD                        │     │
│   │                  (Voice Activity Detection)       │     │
│   │                         │                         │     │
│   │                         ▼                         │     │
│   │              Complete Speech Segments            │     │
│   │                         │                         │     │
│   │                         ▼                         │     │
│   │                  Faster-Whisper                   │     │
│   │              (Speech Recognition + Lang Detect)   │     │
│   │                         │                         │     │
│   │                         ▼                         │     │
│   │              hearing_event_emitter.py             │     │
│   │              (Event Broadcasting)                 │     │
│   └─────────────────────┬────────────────────────────┘     │
│                         │                                    │
└─────────────────────────┼────────────────────────────────────┘
                          │
                          ▼
          /tmp/reachy_sockets/hearing.sock
                          │
          ┌───────────────┴───────────────┐
          │                               │
          ▼                               ▼
    [External Client 1]           [External Client 2]
    (Python app)                  (Node.js app)
```

## How It Works

### 1. Audio Capture (ReSpeaker)
- Captures audio from ReSpeaker USB microphone array at 16kHz, mono
- Uses PyAudio with streaming callback for low-latency processing
- Automatically detects ReSpeaker device or falls back to default input
- Provides queue-based interface for audio chunks

### 2. Voice Activity Detection (SileroVAD)
- Processes audio chunks in real-time using SileroVAD model
- Detects speech vs. silence with configurable threshold (default: 0.5)
- Buffers complete speech segments with padding
- Prevents false triggers with minimum speech duration (250ms)
- Limits maximum speech duration (30s) to prevent memory issues
- Emits periodic `voice_activity` events

### 3. Speech Transcription (Faster-Whisper)
- Transcribes complete speech segments using Faster-Whisper
- Automatically detects spoken language
- Filters for target language (default: English)
- Provides confidence scores and language probability
- Optimized for speed with configurable model size (tiny/base/small/medium/large-v3)

### 4. Socket Creation
- The emitter creates a Unix Domain Socket on startup
- Socket path: `/tmp/reachy_sockets/hearing.sock`
- Permissions set to `0666` (readable/writable by all users)
- Directory is shared between Docker container and host via volume mount

### 5. Connection Handling
- Runs a background thread to accept new client connections
- Multiple clients can connect simultaneously
- Each client connection is tracked and managed independently
- Disconnected clients are automatically removed from the list

### 6. Event Broadcasting
- Events are generated from audio processing pipeline
- Each event is JSON-formatted and newline-delimited
- Thread-safe broadcasting ensures no race conditions
- Failed sends automatically disconnect dead clients

## Event Types

The emitter generates the following types of events:

### `speech_detected`
Emitted when speech is transcribed from the microphone.
```json
{
  "timestamp": "2025-11-10T12:34:56.789",
  "type": "speech_detected",
  "data": {
    "text": "Hello, how are you?",
    "confidence": 0.95,
    "language": "en",
    "language_probability": 0.98,
    "is_target_language": true,
    "duration": 1.2,
    "sequence": 0
  }
}
```

**Fields:**
- `text`: Transcribed text
- `confidence`: Transcription confidence (0-1)
- `language`: Detected language code (e.g., "en", "fr", "es")
- `language_probability`: Language detection confidence (0-1)
- `is_target_language`: Whether detected language matches target language
- `duration`: Duration of speech segment in seconds
- `sequence`: Sequential event number

### `voice_activity`
Emitted periodically to report voice activity detection status.
```json
{
  "timestamp": "2025-11-10T12:35:08.789",
  "type": "voice_activity",
  "data": {
    "active": true,
    "duration": 2.3,
    "sequence": 1
  }
}
```

**Fields:**
- `active`: Whether voice is currently detected
- `duration`: Duration of current voice activity in seconds
- `sequence`: Sequential event number

### Legacy Event Types (Demo Mode Only)

The following events are only emitted in demo mode (when audio processing is disabled):

### `sound_detected`
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

## Running the Emitter

### Prerequisites

#### Hardware
- **ReSpeaker USB Microphone Array** connected via USB
  - Any ReSpeaker model (4-mic, 6-mic, etc.)
  - Device name should contain "ReSpeaker" (configurable)

#### Software
- Docker and docker-compose installed
- USB audio device accessible in Docker container
- Sufficient disk space for Whisper model (varies by size):
  - tiny: ~75MB
  - base: ~150MB (default)
  - small: ~500MB
  - medium: ~1.5GB
  - large-v3: ~3GB

### Inside Docker (Recommended)

The emitter runs inside the Docker container automatically:

```bash
# Start the service
docker-compose -f ../docker-compose-vllm.yml up -d reachy-hearing

# View logs
docker logs -f reachy-hearing-service

# Stop the service
docker-compose -f ../docker-compose-vllm.yml stop reachy-hearing

# Restart the service
docker-compose -f ../docker-compose-vllm.yml restart reachy-hearing
```

### Configuration Options

The service supports command-line arguments via docker-compose:

```yaml
command: python3 hearing_event_emitter.py [OPTIONS]

Options:
  --socket-path PATH    Unix socket path (default: /tmp/reachy_sockets/hearing.sock)
  --demo               Run in demo mode without audio processing
  --device NAME        Audio device name to search for (default: ReSpeaker)
  --model SIZE         Whisper model size: tiny/base/small/medium/large-v3 (default: base)
  --language CODE      Target language to detect (default: en)
```

**Example configurations:**

```yaml
# Use tiny model for faster processing (less accurate)
command: python3 hearing_event_emitter.py --model tiny

# Use large model for better accuracy (slower)
command: python3 hearing_event_emitter.py --model large-v3

# Detect French speech
command: python3 hearing_event_emitter.py --language fr

# Use different USB mic
command: python3 hearing_event_emitter.py --device "USB Audio"

# Demo mode without audio hardware
command: python3 hearing_event_emitter.py --demo
```

### Standalone (For Testing)

You can also run it directly on the host for testing:

```bash
# Install dependencies
cd hearing_app
pip install -r requirements.txt

# Ensure the socket directory exists
mkdir -p /tmp/reachy_sockets

# Run with default settings
python3 hearing_event_emitter.py

# Run in demo mode
python3 hearing_event_emitter.py --demo

# Run with specific settings
python3 hearing_event_emitter.py --device ReSpeaker --model base --language en
```

## Configuration

### Audio Processing Pipeline

#### ReSpeaker Capture
- **Sample Rate**: 16kHz (required for Whisper)
- **Channels**: Mono (single channel)
- **Format**: 16-bit PCM
- **Chunk Size**: 512 samples (~32ms chunks)
- **Buffer**: 2-second rolling buffer for context

Edit `respeaker_capture.py` to customize:
```python
SAMPLE_RATE = 16000  # Hz
CHANNELS = 1         # Mono
CHUNK_SIZE = 512     # Samples
```

#### Voice Activity Detection (VAD)
- **Threshold**: 0.5 (speech probability threshold)
- **Min Speech Duration**: 250ms (prevents false triggers)
- **Max Speech Duration**: 30s (prevents memory overflow)
- **Min Silence Duration**: 500ms (time to end speech)
- **Speech Padding**: 300ms (added before/after speech)

Edit `vad_processor.py` or pass parameters:
```python
vad = VADProcessor(
    sample_rate=16000,
    threshold=0.5,              # Lower = more sensitive
    min_speech_duration_ms=250,
    max_speech_duration_s=30.0,
    min_silence_duration_ms=500,
    speech_pad_ms=300
)
```

#### Speech Transcription
- **Model**: Faster-Whisper (optimized Whisper implementation)
- **Model Size**: Configurable (tiny/base/small/medium/large-v3)
- **Device**: Auto-detected (CUDA if available, else CPU)
- **Compute Type**: Auto-selected (float16 for GPU, int8 for CPU)
- **Language Detection**: Enabled by default
- **Target Language**: Filterable (default: English)

Model size vs. accuracy vs. speed:
- **tiny**: Fastest, lowest accuracy (~75MB, ~2-5x realtime on CPU)
- **base**: Good balance (default) (~150MB, ~1-2x realtime on CPU)
- **small**: Better accuracy (~500MB, ~0.5-1x realtime on CPU)
- **medium**: High accuracy (~1.5GB, requires GPU recommended)
- **large-v3**: Best accuracy (~3GB, requires GPU)

### Customizing the Socket Path

Edit the `docker-compose-vllm.yml`:

```yaml
command: python3 hearing_event_emitter.py --socket-path /custom/path/hearing.sock
volumes:
  - /custom/path:/custom/path  # Update mount
```

### Docker Audio Device Access

The docker-compose configuration includes:

```yaml
privileged: true      # Required for audio device access
devices:
  - /dev/snd:/dev/snd  # Audio devices
volumes:
  - /dev/shm:/dev/shm  # Shared memory for audio buffers
```

**Note**: `privileged: true` is required for USB audio access. In production, consider using specific capabilities instead:

```yaml
cap_add:
  - SYS_ADMIN
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

The system is fully integrated with real audio processing. The pipeline consists of:

### Module Structure

```
hearing_app/
├── hearing_event_emitter.py  # Main service (socket server + pipeline coordinator)
├── respeaker_capture.py      # ReSpeaker USB microphone capture
├── vad_processor.py           # SileroVAD voice activity detection
├── transcription.py           # Faster-Whisper speech recognition
└── requirements.txt           # Python dependencies
```

### Pipeline Flow

1. **Audio Capture** (`respeaker_capture.py`)
   - Captures audio from ReSpeaker USB mic
   - Provides streaming interface via callbacks and queue
   - Handles device detection and fallback

2. **Voice Activity Detection** (`vad_processor.py`)
   - Processes audio chunks with SileroVAD
   - Buffers complete speech segments
   - Filters out silence and noise

3. **Speech Recognition** (`transcription.py`)
   - Transcribes speech segments with Faster-Whisper
   - Detects language automatically
   - Provides confidence scores

4. **Event Broadcasting** (`hearing_event_emitter.py`)
   - Coordinates the pipeline
   - Emits events via Unix Domain Socket
   - Manages client connections

### Adding Custom Event Types

To add new event types, edit `hearing_event_emitter.py`:

```python
# In process_audio_stream() method
if some_condition:
    self.emit_event("custom_event", {
        "field1": "value1",
        "field2": 123,
        "field3": True
    })
```

### Extending Audio Processing

To add additional audio analysis:

```python
# Create new module: hearing_app/sound_classifier.py
class SoundClassifier:
    def classify(self, audio_data):
        # Your classification logic
        return {"type": "clap", "confidence": 0.9}

# Integrate in hearing_event_emitter.py
from sound_classifier import SoundClassifier

class HearingEventEmitter:
    def process_audio_stream(self):
        # ... existing code ...
        classifier = SoundClassifier()
        
        while self.running:
            audio_chunk = self.audio_capture.get_audio_chunk()
            
            # Existing VAD processing
            speech_segment = self.vad_processor.process_chunk(audio_chunk)
            
            # Add new classification
            sound_class = classifier.classify(audio_chunk)
            if sound_class:
                self.emit_event("sound_detected", sound_class)
```

## Dependencies

### Core Dependencies

Required for full audio processing:

```
numpy>=1.24.0          # Numerical operations
pyaudio>=0.2.13        # Audio I/O
torch>=2.0.0           # PyTorch for SileroVAD
torchaudio>=2.0.0      # Audio processing for PyTorch
silero-vad>=5.1.2      # Voice activity detection
faster-whisper>=1.0.0  # Speech recognition
langdetect>=1.0.9      # Language detection
scipy>=1.10.0          # Signal processing
```

### System Dependencies

For audio device access:
```bash
# Ubuntu/Debian
sudo apt-get install -y portaudio19-dev python3-pyaudio libasound2-dev

# The Docker image should include these
```

### Installation

#### In Docker (Automatic)
Dependencies are installed when building the Docker image or on first run.

#### On Host (Manual)
```bash
cd hearing_app
pip install -r requirements.txt
```

**Note**: Installing PyTorch can be large (~2-3GB). For CPU-only:
```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```

## Troubleshooting

### Audio Issues

#### ReSpeaker not detected
```bash
# List audio devices in container
docker exec reachy-hearing-service python3 -c "
import pyaudio
p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info['maxInputChannels'] > 0:
        print(f'{i}: {info[\"name\"]}')
"

# Check USB devices on host
lsusb | grep -i respeaker

# Check if device is accessible in container
docker exec reachy-hearing-service ls -la /dev/snd/
```

**Solutions**:
1. Ensure ReSpeaker is plugged in and recognized by host
2. Verify `/dev/snd` is mounted in container
3. Check container has `privileged: true` or appropriate capabilities
4. Try using `--device "USB Audio"` if device name doesn't match
5. Use demo mode to test without hardware: `--demo`

#### Audio quality issues
- Check sample rate matches (16kHz required)
- Ensure USB power is sufficient (use powered hub if needed)
- Update ReSpeaker firmware if available
- Check for USB interference or cable quality

#### No speech detected
```bash
# Check VAD threshold (lower = more sensitive)
# Edit docker-compose to pass custom threshold via environment variable
# Or modify vad_processor.py threshold parameter
```

**Solutions**:
1. Speak louder and closer to microphone
2. Reduce background noise
3. Lower VAD threshold (0.3-0.4 for noisier environments)
4. Check microphone is not muted

### Transcription Issues

#### Slow transcription
**Solutions**:
1. Use smaller model: `--model tiny` or `--model base`
2. Use GPU if available (CUDA)
3. Increase `max_speech_duration_s` if cutting off long speech
4. Reduce `min_speech_duration_ms` if missing short utterances

#### Poor transcription accuracy
**Solutions**:
1. Use larger model: `--model medium` or `--model large-v3`
2. Ensure good audio quality (reduce noise, speak clearly)
3. Check language is correctly detected
4. Use language-specific model if available

#### Wrong language detected
```bash
# Force specific language
command: python3 hearing_event_emitter.py --language fr
```

### Docker Issues

#### Container won't start
```bash
# Check logs
docker logs reachy-hearing-service

# Common issues:
# - Missing audio devices: Check device mapping
# - Port conflicts: Ensure socket path is unique
# - Permission errors: Ensure /tmp/reachy_sockets has correct permissions
```

#### Model download fails
```bash
# Pre-download models on host (they'll be cached)
docker exec reachy-hearing-service python3 -c "
from faster_whisper import WhisperModel
WhisperModel('base', device='cpu', compute_type='int8')
"

# Or download outside container
python3 -c "
from faster_whisper import WhisperModel
WhisperModel('base', device='cpu', compute_type='int8')
"
```

### Socket Issues

#### Socket permission denied
```bash
# Check socket permissions
ls -la /tmp/reachy_sockets/hearing.sock

# Should show: srw-rw-rw- (0666 permissions)
# If not, the emitter sets this on creation
```

#### Socket already in use
```bash
# The emitter automatically removes old socket on startup
# If it fails, manually remove:
rm /tmp/reachy_sockets/hearing.sock
```

#### Container can't create socket
```bash
# Ensure the volume mount exists in docker-compose-vllm.yml:
volumes:
  - /tmp/reachy_sockets:/tmp/reachy_sockets

# Create directory on host if needed:
mkdir -p /tmp/reachy_sockets
chmod 777 /tmp/reachy_sockets
```

#### No events being emitted
```bash
# Check container logs:
docker logs reachy-hearing-service

# Verify emitter is running:
docker exec reachy-hearing-service ps aux | grep python

# Test with netcat:
nc -U /tmp/reachy_sockets/hearing.sock
```

### Memory Issues

#### Out of memory errors
**Solutions**:
1. Use smaller Whisper model (`tiny` or `base`)
2. Reduce `max_speech_duration_s` in VAD
3. Increase Docker memory limit
4. Use CPU instead of GPU if GPU memory is limited

#### High CPU usage
**Solutions**:
1. Use smaller Whisper model
2. Increase VAD `min_silence_duration_ms` (processes less frequently)
3. Use GPU for transcription if available

## Performance Considerations

- **Event rate**: Depends on speech frequency; VAD status emitted every 2 seconds
- **Latency**: 
  - Audio capture: ~32ms chunks (real-time)
  - VAD: ~10-50ms (real-time)
  - Transcription: Varies by model size
    - tiny: 2-5x realtime on CPU
    - base: 1-2x realtime on CPU
    - small: 0.5-1x realtime on CPU
    - medium/large: Requires GPU for realtime
- **Buffer size**: Socket buffer is 4096 bytes; increase for high-frequency events
- **Client limit**: No hard limit, but consider limiting connections for performance
- **Thread pool**: Currently uses one thread for accepts; consider thread pool for high client counts
- **Memory usage**:
  - Base model: ~500MB RAM + model size
  - Larger models: Proportionally more
  - GPU: Significant GPU memory (2-8GB for large models)

### Optimization Tips

1. **For low latency**: Use `tiny` or `base` model
2. **For high accuracy**: Use `medium` or `large-v3` model with GPU
3. **For resource-constrained**: Use `tiny` model with CPU
4. **For production**: Use `base` or `small` model as good balance

## Testing

### Test Individual Modules

Each module can be tested independently:

#### Test ReSpeaker Capture
```bash
cd hearing_app
python3 respeaker_capture.py

# Expected output:
# [INFO] Searching for audio devices...
# [INFO] Found device: ReSpeaker 4 Mic Array (index: X)
# [INFO] Audio capture started (sample rate: 16000Hz, channels: 1)
# [TEST] Audio level: 1234.56
```

#### Test VAD Processor
```bash
python3 vad_processor.py

# Expected output:
# [INFO] Loading SileroVAD model...
# [INFO] SileroVAD model loaded successfully
# [TEST] Simulating audio stream...
```

#### Test Transcription
```bash
python3 transcription.py

# Expected output:
# [INFO] Loading Faster-Whisper model (base)...
# [INFO] Faster-Whisper model loaded successfully
```

### Test Full Pipeline

#### In Docker
```bash
# Start service
docker-compose -f ../docker-compose-vllm.yml up -d reachy-hearing

# Follow logs
docker logs -f reachy-hearing-service

# Expected output:
# [INFO] Starting Hearing Event Emitter...
# [INFO] Audio processing: ENABLED
# [INFO] Device: ReSpeaker
# [INFO] Listening on Unix socket: /tmp/reachy_sockets/hearing.sock
# [INFO] Initializing audio processing pipeline...
# [INFO] Found device: ReSpeaker...
# [INFO] Audio capture started...
# [INFO] Loading SileroVAD model...
# [INFO] SileroVAD model loaded successfully
# [INFO] Loading Faster-Whisper model (base)...
# [INFO] Faster-Whisper model loaded successfully
# [INFO] Audio processing pipeline initialized successfully
```

#### On Host (Standalone)
```bash
cd hearing_app
python3 hearing_event_emitter.py --model tiny

# Speak into microphone
# Expected output when you speak:
# [VAD] Speech started (prob: 0.876)
# [VAD] Speech ended (duration: 2.34s, prob: 0.123)
# [INFO] Processing speech segment: 37440 samples
# [TRANSCRIBE] Text: 'Hello, how are you?' | Lang: en (0.98) | Conf: 0.95 | Time: 1.23s
# [EVENT] Speech: 'Hello, how are you?' [en] (conf: 0.95)
```

### Test Client Connection

```bash
# Terminal 1: Run the service
python3 hearing_event_emitter.py

# Terminal 2: Connect with test client
python3 ../hearing_event_client.py

# Expected output in Terminal 2:
# Received: speech_detected - {'text': 'Hello', 'confidence': 0.95, ...}
```

## Security Considerations

- **Socket permissions**: Currently `0666` (world-readable/writable) for ease of use
- **Authentication**: No authentication; add if needed for production
- **Rate limiting**: No rate limiting; add to prevent abuse
- **Input validation**: All events are generated internally; validate if accepting external input

## License

Same as the main project.
