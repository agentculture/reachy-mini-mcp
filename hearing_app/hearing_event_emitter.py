#!/usr/bin/env python3
"""
Hearing Event Emitter - Emits events via Unix Domain Socket

This service creates a Unix Domain Socket server that emits hearing events
to connected clients. External applications can connect to the socket to
receive real-time event notifications.

Processes audio from ReSpeaker microphone using:
- SileroVAD for voice activity detection
- Faster-Whisper for speech transcription
- Language detection to filter English speech
"""

import socket
import os
import json
import time
import sys
import threading
from datetime import datetime
from pathlib import Path
import numpy as np

# Import audio processing modules
try:
    from voice_recorder import VoiceRecorder
    AUDIO_MODULES_AVAILABLE = True
except ImportError as e:
    print(f"[WARNING] Audio modules not available: {e}")
    print("[WARNING] Running in demo mode without audio processing")
    AUDIO_MODULES_AVAILABLE = False


class HearingEventEmitter:
    """Emits hearing events via Unix Domain Socket"""
    
    def __init__(
        self,
        socket_path="/tmp/reachy_sockets/hearing.sock",
        use_audio=True,
        device_name="ReSpeaker",
        whisper_model="base",
        target_language="en"
    ):
        """
        Initialize the hearing event emitter
        
        Args:
            socket_path: Path to Unix Domain Socket
            use_audio: Whether to use real audio processing (False for demo mode)
            device_name: Audio device name to search for
            whisper_model: Whisper model size (tiny, base, small, medium, large-v3)
            target_language: Target language to detect (e.g., "en" for English)
        """
        self.socket_path = socket_path
        self.clients = []
        self.server_socket = None
        self.running = False
        self.shutdown_event = threading.Event()  # For clean shutdown
        self.lock = threading.Lock()
        
        # Audio processing components
        self.use_audio = use_audio and AUDIO_MODULES_AVAILABLE
        self.voice_recorder = None
        self.device_name = device_name
        self.whisper_model = whisper_model
        self.target_language = target_language
        
        # Event sequence counter
        self.event_sequence = 0
        
    def setup_socket(self):
        """Create and configure the Unix Domain Socket"""
        # Ensure directory exists
        socket_dir = os.path.dirname(self.socket_path)
        Path(socket_dir).mkdir(parents=True, exist_ok=True)
        
        # Remove existing socket file if it exists
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
        
        # Create Unix Domain Socket
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(self.socket_path)
        
        # Set permissions to allow external connections
        os.chmod(self.socket_path, 0o666)
        
        self.server_socket.listen(5)
        print(f"[INFO] Listening on Unix socket: {self.socket_path}")
        
    def accept_connections(self):
        """Accept new client connections"""
        print("[INFO] Connection acceptor thread started")
        while self.running:
            try:
                if self.server_socket is None:
                    time.sleep(0.1)
                    continue
                    
                self.server_socket.settimeout(0.5)  # Short timeout for responsiveness
                try:
                    client_socket, _ = self.server_socket.accept()
                    with self.lock:
                        self.clients.append(client_socket)
                    print(f"[INFO] ✓ Client connected. Total clients: {len(self.clients)}")
                except socket.timeout:
                    continue
            except Exception as e:
                if self.running:
                    print(f"[ERROR] Error accepting connection: {e}")
                    time.sleep(0.1)
        print("[INFO] Connection acceptor thread stopped")
                    
    def emit_event(self, event_type, data):
        """Emit an event to all connected clients"""
        # Add sequence number
        data["sequence"] = self.event_sequence
        self.event_sequence += 1
        
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "data": data
        }
        
        message = json.dumps(event) + "\n"
        message_bytes = message.encode('utf-8')
        
        with self.lock:
            disconnected = []
            sent_count = 0
            for client in self.clients:
                try:
                    client.sendall(message_bytes)
                    sent_count += 1
                except (BrokenPipeError, ConnectionResetError, OSError):
                    disconnected.append(client)
                    
            # Remove disconnected clients
            for client in disconnected:
                try:
                    client.close()
                except:
                    pass
                self.clients.remove(client)
                
            if disconnected:
                print(f"[INFO] ⚠ Removed {len(disconnected)} disconnected client(s). Active: {len(self.clients)}")
            
            if sent_count > 0 and event_type == "voice_activity":
                print(f"[INFO] Event emitted to {sent_count} client(s): {event_type}")
    
    def _on_transcription_callback(self, result):
        """Callback for transcription results"""
        try:
            # Check if target language
            is_target = (result['language'].lower() == self.target_language.lower()) if self.target_language else True
            
            # Emit speech detected event
            self.emit_event("speech_detected", {
                "text": result["text"],
                "language": result["language"],
                "language_probability": result["language_probability"],
                "is_target_language": is_target,
                "duration": result["duration"]
            })
            
            print(f"[EVENT] ✓ Speech: '{result['text']}' "
                  f"[{result['language']}] "
                  f"({result['language_probability']:.2f})")
            
            if not is_target:
                print(f"[INFO] Detected non-{self.target_language} speech: {result['language']}")
                
        except Exception as e:
            print(f"[ERROR] Error in transcription callback: {e}")
    
    def process_audio_stream(self):
        """Process audio stream from ReSpeaker with VAD and transcription"""
        if not self.use_audio:
            print("[INFO] Audio processing disabled, using demo mode")
            self.generate_sample_events()
            return
        
        print("[INFO] Initializing voice recorder...")
        
        try:
            # Initialize voice recorder with callback
            self.voice_recorder = VoiceRecorder(
                device_name=self.device_name,
                model_size=self.whisper_model,
                device="cuda",
                initial_prompt="The following is a clear and accurate transcription:",
                language=None,  # Auto-detect
                on_transcription=self._on_transcription_callback
            )
            
            # Start voice recorder (this will block in its main loop)
            print("[INFO] Starting voice recorder...")
            self.voice_recorder.start()
                    
        except KeyboardInterrupt:
            print("\n[INFO] Audio processing interrupted")
        except Exception as e:
            print(f"[ERROR] Fatal error in audio processing: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Cleanup audio resources
            print("[INFO] Cleaning up audio resources...")
            if self.voice_recorder:
                self.voice_recorder.stop()
            print("[INFO] Audio processing stopped")
    
    def generate_sample_events(self):
        """Generate sample hearing events for demonstration (fallback mode)"""
        print("[INFO] Running in demo mode - generating sample events")
        
        event_types = [
            ("speech_detected", {
                "text": "Hello", 
                "confidence": 0.95, 
                "language": "en",
                "language_probability": 0.98,
                "is_target_language": True,
                "duration": 1.2
            }),
            ("sound_detected", {
                "type": "clap", 
                "intensity": 0.8, 
                "direction": "front"
            }),
            ("keyword_spotted", {
                "keyword": "reachy", 
                "confidence": 0.92
            }),
            ("noise_level", {
                "level": 65, 
                "unit": "dB"
            }),
            ("voice_activity", {
                "active": True, 
                "duration": 2.3
            }),
        ]
        
        counter = 0
        while self.running:
            time.sleep(3)  # Emit event every 3 seconds
            
            event_type, data = event_types[counter % len(event_types)]
            
            self.emit_event(event_type, data)
            print(f"[EVENT] Demo: {event_type} - {data}")
            
            counter += 1
            
    def start(self):
        """Start the event emitter service"""
        print("[INFO] Starting Hearing Event Emitter...")
        print(f"[INFO] Audio processing: {'ENABLED' if self.use_audio else 'DISABLED (demo mode)'}")
        if self.use_audio:
            print(f"[INFO] Device: {self.device_name}")
            print(f"[INFO] Whisper model: {self.whisper_model}")
            print(f"[INFO] Target language: {self.target_language}")
        
        self.running = True
        
        try:
            self.setup_socket()
            
            # Start connection acceptor thread
            accept_thread = threading.Thread(target=self.accept_connections, daemon=True)
            accept_thread.start()
            
            # Process audio stream (or generate sample events)
            self.process_audio_stream()
            
        except KeyboardInterrupt:
            print("\n[INFO] Shutting down...")
        except Exception as e:
            print(f"[ERROR] Fatal error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.stop()
            
    def stop(self):
        """Stop the service and cleanup"""
        print("[INFO] Stopping service...")
        self.running = False
        self.shutdown_event.set()  # Signal shutdown to all threads
        
        # Close all client connections
        with self.lock:
            for client in self.clients:
                try:
                    client.close()
                except:
                    pass
            self.clients.clear()
        
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        # Remove socket file
        if os.path.exists(self.socket_path):
            try:
                os.remove(self.socket_path)
            except:
                pass
                
        print("[INFO] Service stopped")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Reachy Hearing Event Emitter")
    parser.add_argument("--socket-path", default="/tmp/reachy_sockets/hearing.sock",
                        help="Unix socket path")
    parser.add_argument("--demo", action="store_true",
                        help="Run in demo mode without audio processing")
    parser.add_argument("--device", default="ReSpeaker",
                        help="Audio device name to search for")
    parser.add_argument("--model", default="base",
                        choices=["tiny", "base", "small", "medium", "large-v3"],
                        help="Whisper model size")
    parser.add_argument("--language", default="en",
                        help="Target language to detect (e.g., 'en' for English)")
    
    args = parser.parse_args()
    
    emitter = HearingEventEmitter(
        socket_path=args.socket_path,
        use_audio=not args.demo,
        device_name=args.device,
        whisper_model=args.model,
        target_language=args.language
    )
    emitter.start()
