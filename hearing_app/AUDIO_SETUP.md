# Audio Processing Setup Guide

Quick guide to set up the Reachy hearing service with ReSpeaker, SileroVAD, and Faster-Whisper.

## Quick Start

### 1. Connect ReSpeaker Microphone
- Plug ReSpeaker USB microphone into your system
- Verify it's detected: `lsusb | grep -i respeaker`

### 2. Build/Update Docker Image (if needed)

If your Docker image doesn't have audio dependencies:

```bash
# Option A: Install in running container (temporary)
docker exec -it reachy-hearing-service pip install -r /app/requirements.txt

# Option B: Rebuild image with dependencies (permanent)
# Add to your Dockerfile:
# RUN pip install -r /app/requirements.txt
```

### 3. Start the Service

```bash
# Start with docker-compose
docker-compose -f docker-compose-vllm.yml up -d reachy-hearing

# Watch the logs
docker logs -f reachy-hearing-service
```

### 4. Test It

```bash
# Terminal 1: Watch events
nc -U /tmp/reachy_sockets/hearing.sock | jq .

# Terminal 2: Speak into microphone
# You should see speech_detected events appear in Terminal 1
```

## Configuration Quick Reference

### Change Whisper Model Size

Edit `docker-compose-vllm.yml`:

```yaml
# For faster processing (less accurate)
command: python3 hearing_event_emitter.py --model tiny

# For better accuracy (slower)
command: python3 hearing_event_emitter.py --model large-v3

# Default (good balance)
command: python3 hearing_event_emitter.py --model base
```

### Change Target Language

```yaml
# Detect French
command: python3 hearing_event_emitter.py --language fr

# Detect Spanish
command: python3 hearing_event_emitter.py --language es

# Default (English)
command: python3 hearing_event_emitter.py --language en
```

### Adjust VAD Sensitivity

Edit `hearing_app/vad_processor.py`:

```python
VADProcessor(
    threshold=0.5,  # Lower = more sensitive (0.3-0.4 for noisy environments)
    min_speech_duration_ms=250,  # Shorter = detects brief speech
    min_silence_duration_ms=500,  # Shorter = splits speech faster
)
```

## Typical Event Flow

1. **Startup**: Service loads models (30-60 seconds for first run)
2. **Idle**: Emits `voice_activity` events every 2 seconds with `active: false`
3. **Speech Start**: VAD detects speech, `voice_activity` shows `active: true`
4. **Speech End**: After 500ms silence, speech segment is transcribed
5. **Transcription**: `speech_detected` event emitted with text and language

## Expected Output

### Successful Startup
```
[INFO] Starting Hearing Event Emitter...
[INFO] Audio processing: ENABLED
[INFO] Device: ReSpeaker
[INFO] Whisper model: base
[INFO] Target language: en
[INFO] Listening on Unix socket: /tmp/reachy_sockets/hearing.sock
[INFO] Searching for audio devices...
[INFO] Found device: ReSpeaker 4 Mic Array (index: 2)
[INFO] Audio capture started (sample rate: 16000Hz, channels: 1)
[INFO] Loading SileroVAD model...
[INFO] SileroVAD model loaded successfully
[INFO] Loading Faster-Whisper model (base) on cpu with int8...
[INFO] Faster-Whisper model loaded successfully
[INFO] Audio processing pipeline initialized successfully
```

### When You Speak
```
[VAD] Speech started (prob: 0.876)
[VAD] Speech ended (duration: 2.34s, prob: 0.123)
[INFO] Processing speech segment: 37440 samples
[TRANSCRIBE] Text: 'Hello, how are you?' | Lang: en (0.98) | Conf: 0.95 | Time: 1.23s
[EVENT] Speech: 'Hello, how are you?' [en] (conf: 0.95)
```

## Troubleshooting Quick Fixes

### Problem: "Device 'ReSpeaker' not found"
```bash
# Check what devices are available
docker exec reachy-hearing-service python3 -c "
import pyaudio
p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info['maxInputChannels'] > 0:
        print(f\"{i}: {info['name']}\")
"

# Use the correct device name
# Edit docker-compose-vllm.yml:
command: python3 hearing_event_emitter.py --device "USB Audio"
```

### Problem: No speech detected
- **Check**: Speak louder and closer to microphone
- **Check**: Verify microphone is not muted
- **Fix**: Lower VAD threshold in `vad_processor.py` to 0.3-0.4

### Problem: Transcription too slow
- **Fix**: Use smaller model: `--model tiny`
- **Fix**: Use GPU if available (requires CUDA-enabled Docker image)

### Problem: Poor transcription accuracy
- **Fix**: Use larger model: `--model medium` or `--model large-v3`
- **Fix**: Speak more clearly with less background noise
- **Fix**: Ensure correct language is targeted

### Problem: Wrong language detected
- **Fix**: Force language: `--language en` (or fr, es, etc.)

## Demo Mode (No Hardware)

Test without ReSpeaker hardware:

```bash
# Start in demo mode
docker exec reachy-hearing-service python3 hearing_event_emitter.py --demo

# Or edit docker-compose-vllm.yml:
command: python3 hearing_event_emitter.py --demo
```

Demo mode generates sample events without real audio processing.

## Model Download Times (First Run)

| Model | Size | Download Time | CPU Inference Speed |
|-------|------|---------------|---------------------|
| tiny  | ~75MB | 10-30s | 2-5x realtime |
| base  | ~150MB | 20-60s | 1-2x realtime |
| small | ~500MB | 1-3min | 0.5-1x realtime |
| medium | ~1.5GB | 3-8min | Requires GPU |
| large-v3 | ~3GB | 5-15min | Requires GPU |

Models are cached after first download.

## System Requirements

### Minimum (tiny/base model, CPU)
- 2 CPU cores
- 2GB RAM
- 500MB disk space
- USB audio support

### Recommended (base/small model, CPU)
- 4 CPU cores
- 4GB RAM
- 1GB disk space
- USB audio support

### High Performance (medium/large model, GPU)
- 4+ CPU cores
- 8GB RAM
- 4-8GB VRAM (GPU)
- 5GB disk space
- CUDA-enabled GPU

## Next Steps

- See [README.md](README.md) for complete documentation
- Test with [hearing_event_client.py](../hearing_event_client.py)
- Integrate with your application using Unix Domain Socket
- Customize VAD and transcription parameters for your use case
