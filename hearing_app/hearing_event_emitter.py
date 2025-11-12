#!/usr/bin/env python3
"""
Hearing Event Emitter - Service that detects speech using VAD and emits events

This service listens to audio input, detects speech using Voice Activity Detection,
and emits events via Unix Domain Socket to connected clients.

Usage:
    python3 hearing_event_emitter.py --device ReSpeaker --language en
"""

import pyaudio
import webrtcvad
import wave
import time
import numpy as np
import os
import socket
import sys
import logging
import json
import argparse
from datetime import datetime
from dotenv import load_dotenv
import asyncio
from collections import deque
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info("Hearing Event Emitter starting...")

# Load environment variables
load_dotenv()
logger.debug("Environment variables loaded")


class HearingEventEmitter:
    """Service that detects speech and emits events via Unix Domain Socket"""
    
    def __init__(self, device_name=None, language='en'):
        logger.info("Initializing HearingEventEmitter")
        
        # Configuration from environment or defaults
        self.device_name = (device_name or os.getenv('AUDIO_DEVICE_NAME', 'default')).lower()
        self.language = language
        self.socket_path = os.getenv('SOCKET_PATH', '/tmp/reachy_sockets/hearing.sock')
        
        # Audio configuration
        self.rate = int(os.getenv('SAMPLE_RATE', '16000'))
        self.chunk_duration_ms = int(os.getenv('CHUNK_DURATION_MS', '30'))
        self.chunk_size = int(self.rate * self.chunk_duration_ms / 1000)
        
        # VAD configuration
        vad_aggressiveness = int(os.getenv('VAD_AGGRESSIVENESS', '3'))
        self.vad = webrtcvad.Vad(vad_aggressiveness)
        
        # Speech detection configuration
        self.min_silence_duration = float(os.getenv('MIN_SILENCE_DURATION', '2.5'))
        self.lower_threshold = int(os.getenv('SPEECH_THRESHOLD_LOWER', '1500'))
        self.upper_threshold = int(os.getenv('SPEECH_THRESHOLD_UPPER', '2500'))
        self.min_audio_bytes = 4000
        
        # Buffers
        buffer_size = int(os.getenv('AUDIO_BUFFER_SIZE', '100'))
        self.audio_buffer = deque(maxlen=buffer_size)
        self.speech_buffer = []
        
        # State
        self.speech_detected = False
        self.silence_start_time = None
        self.start_time = None
        self.speech_events = 0
        self.processing_lock = asyncio.Lock()
        
        # Socket setup
        self.server_socket = None
        self.clients = []
        self.setup_socket_server()
        
        # Audio setup
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.input_device_index = None
        
        logger.info("HearingEventEmitter initialization complete")
    
    def setup_socket_server(self):
        """Set up Unix Domain Socket server"""
        logger.debug(f"Setting up Unix socket server at {self.socket_path}")
        
        # Create socket directory if it doesn't exist
        socket_dir = os.path.dirname(self.socket_path)
        os.makedirs(socket_dir, exist_ok=True)
        
        # Remove existing socket file if it exists
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
        
        # Create socket
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(self.socket_path)
        self.server_socket.listen(5)
        self.server_socket.setblocking(False)
        
        # Set permissions
        os.chmod(self.socket_path, 0o666)
        
        logger.info(f"Socket server listening on {self.socket_path}")
    
    def initialize_input_device(self):
        """Find and initialize audio input device"""
        wait_times = [1, 2, 4, 8, 16, 32]
        for wait_time in wait_times:
            self.input_device_index = self.find_input_device()
            if self.input_device_index is not None:
                break
            logger.warning(f"Input device not found, retrying in {wait_time} seconds...")
            time.sleep(wait_time)
        else:
            logger.error("Suitable input device not found after multiple attempts")
            raise RuntimeError("Suitable input device not found")
        
        logger.info(f"Using audio device index: {self.input_device_index}")
    
    def find_input_device(self):
        """Search for audio input device by name"""
        logger.info("Searching for input device")
        device_count = self.p.get_device_count()
        logger.info(f"Found {device_count} audio devices")
        
        for i in range(device_count):
            device_info = self.p.get_device_info_by_index(i)
            device_name = device_info['name'].lower()
            logger.debug(f"Checking device {i}: {device_name}")
            
            if self.device_name in device_name and device_info['maxInputChannels'] > 0:
                logger.info(f"Found matching device: {device_info['name']} (index {i})")
                return i
        
        logger.warning("Suitable input device not found")
        return None
    
    def setup_audio_stream(self):
        """Open audio stream"""
        try:
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                input_device_index=self.input_device_index
            )
            logger.info("Audio stream opened successfully")
        except IOError as e:
            logger.error(f"Error opening audio stream: {e}")
            raise
    
    async def accept_clients(self):
        """Accept new client connections"""
        while True:
            try:
                # Try to accept new connections (non-blocking)
                try:
                    client_socket, _ = self.server_socket.accept()
                    client_socket.setblocking(False)
                    self.clients.append(client_socket)
                    logger.info(f"New client connected. Total clients: {len(self.clients)}")
                except BlockingIOError:
                    pass
                
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error accepting clients: {e}")
                await asyncio.sleep(1)
    
    async def emit_event(self, event_type, data=None):
        """Emit event to all connected clients asynchronously"""
        event = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data or {}
        }
        
        message = json.dumps(event) + "\n"
        message_bytes = message.encode('utf-8')
        
        # Send to all clients
        disconnected_clients = []
        for client in self.clients:
            try:
                # Run the blocking sendall in a thread to avoid blocking the event loop
                await asyncio.to_thread(client.sendall, message_bytes)
            except (BrokenPipeError, ConnectionResetError) as e:
                logger.warning(f"Client disconnected: {e}")
                disconnected_clients.append(client)
            except Exception as e:
                logger.error(f"Error sending to client: {e}")
                disconnected_clients.append(client)
        
        # Remove disconnected clients
        for client in disconnected_clients:
            try:
                client.close()
            except:
                pass
            self.clients.remove(client)
        
        if disconnected_clients:
            logger.info(f"Removed {len(disconnected_clients)} disconnected clients. Active: {len(self.clients)}")
        
        logger.debug(f"Emitted event: {event_type}")
    
    def is_speech(self, data):
        """Check if audio data contains speech using VAD"""
        try:
            return self.vad.is_speech(data, self.rate)
        except Exception as e:
            logger.error(f"Error in VAD processing: {e}")
            return False
    
    async def log_speech_event(self, event_type, duration=None):
        """Log and emit speech detection events"""
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        
        if event_type == "start":
            self.speech_events += 1
            message = f"Speech started (Event #{self.speech_events})"
            logger.info(f"[{current_time}] {message}")
            
            await self.emit_event("speech_started", {
                "event_number": self.speech_events,
                "timestamp": current_time
            })
            
        elif event_type == "stop":
            message = f"Speech stopped (Event #{self.speech_events})"
            if duration:
                message += f" - Duration: {duration:.2f} seconds"
            
            logger.info(f"[{current_time}] {message}")
            
            await self.emit_event("speech_stopped", {
                "event_number": self.speech_events,
                "duration": duration,
                "timestamp": current_time
            })
    
    async def listen(self):
        """Continuously listen to audio and buffer it"""
        while True:
            try:
                data = await asyncio.to_thread(
                    self.stream.read,
                    self.chunk_size,
                    exception_on_overflow=False
                )
                np_data = np.frombuffer(data, dtype=np.int16)
                
                async with self.processing_lock:
                    self.audio_buffer.append(np_data)
                    
            except Exception as e:
                logger.error(f"Error during audio capture: {e}", exc_info=True)
                await asyncio.sleep(0.1)
    
    async def process(self):
        """Process buffered audio and detect speech"""
        while True:
            # Get data from buffer with minimal lock time
            data = None
            async with self.processing_lock:
                if len(self.audio_buffer) > 0:
                    data = self.audio_buffer.popleft()
            
            # Process data outside the lock
            if data is not None:
                # Run CPU-bound VAD check in a thread to avoid blocking the event loop
                is_speech = await asyncio.to_thread(self.is_speech, data.tobytes())
                
                # Handle state (no lock needed here)
                if is_speech:
                    await self.handle_speech(data)
                else:
                    await self.handle_silence()
            else:
                # No data, sleep briefly
                await asyncio.sleep(0.01)
    
    async def handle_speech(self, data):
        """Handle detected speech"""
        if not self.speech_detected:
            self.start_time = time.time()
            await self.log_speech_event("start")
            self.speech_detected = True
            self.speech_buffer = []
            logger.debug("Speech detected, starting new buffer")
        
        self.speech_buffer.append(data)
        self.silence_start_time = None  # Reset silence timer
    
    async def handle_silence(self):
        """Handle silence (potential end of speech)"""
        if self.speech_detected:
            if self.silence_start_time is None:
                self.silence_start_time = time.time()
                logger.debug("Silence detected, starting silence timer")
            elif time.time() - self.silence_start_time >= self.min_silence_duration:
                logger.info("Silence duration exceeded, ending speech event")
                await self.process_speech()
    
    async def process_speech(self):
        """Process completed speech segment"""
        duration = time.time() - self.start_time
        audio_size = len(self.speech_buffer) * self.chunk_size * 2  # 2 bytes per sample
        
        logger.info(f"Processing speech segment: {len(self.speech_buffer)} chunks, {audio_size} bytes")
        
        # Emit completion event
        await self.log_speech_event("stop", duration)
        
        # Optional: Save audio file for debugging
        if os.getenv('SAVE_AUDIO_FILES', 'false').lower() == 'true':
            await self.save_audio_file()
        
        # Reset state
        self.speech_detected = False
        self.silence_start_time = None
        self.speech_buffer = []
    
    async def save_audio_file(self):
        """Save recorded speech to file"""
        if not self.speech_buffer:
            return
        
        try:
            combined_audio = np.concatenate(self.speech_buffer)
            filename = f"speech_{self.speech_events}_{int(time.time())}.wav"
            
            await asyncio.to_thread(self._save_audio_sync, combined_audio, filename)
            logger.info(f"Saved audio to {filename}")
        except Exception as e:
            logger.error(f"Error saving audio file: {e}")
    
    def _save_audio_sync(self, audio_data, filename):
        """Synchronous audio file writing"""
        with wave.open(filename, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(self.p.get_sample_size(pyaudio.paInt16))
            wav_file.setframerate(self.rate)
            wav_file.writeframes(audio_data.tobytes())
    
    async def run(self):
        """Main run loop"""
        logger.info("Starting Hearing Event Emitter service")
        logger.info(f"Device: {self.device_name}")
        logger.info(f"Rate: {self.rate} Hz")
        logger.info(f"Socket: {self.socket_path}")
        
        # Initialize audio device
        self.initialize_input_device()
        self.setup_audio_stream()
        
        # Start tasks
        accept_task = asyncio.create_task(self.accept_clients())
        listen_task = asyncio.create_task(self.listen())
        process_task = asyncio.create_task(self.process())
        
        try:
            await asyncio.gather(accept_task, listen_task, process_task)
        except Exception as e:
            logger.error(f"Error during service operation: {e}", exc_info=True)
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        logger.info("Cleaning up resources")
        
        # Close audio stream
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass
        
        # Terminate PyAudio
        if self.p:
            try:
                self.p.terminate()
            except:
                pass
        
        # Close all client connections
        for client in self.clients:
            try:
                client.close()
            except:
                pass
        
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
        
        logger.info("Cleanup complete")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Hearing Event Emitter - VAD-based speech detection service'
    )
    parser.add_argument(
        '--device',
        type=str,
        default=None,
        help='Audio device name (e.g., ReSpeaker, default)'
    )
    parser.add_argument(
        '--language',
        type=str,
        default='en',
        help='Language code for future use (default: en)'
    )
    
    args = parser.parse_args()
    
    emitter = HearingEventEmitter(device_name=args.device, language=args.language)
    
    try:
        asyncio.run(emitter.run())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, terminating...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
