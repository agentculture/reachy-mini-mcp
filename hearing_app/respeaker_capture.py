#!/usr/bin/env python3
"""
ReSpeaker Audio Capture Module

Handles audio capture from ReSpeaker USB microphone array.
Provides a queue-based interface for real-time audio processing.
"""

import pyaudio
import numpy as np
import queue
import threading
import time
from typing import Optional, Callable


class ReSpeakerCapture:
    """Captures audio from ReSpeaker USB microphone"""
    
    # Audio configuration
    SAMPLE_RATE = 16000  # 16kHz for speech recognition
    CHANNELS = 1  # Mono audio
    CHUNK_SIZE = 512  # 32ms chunks (512 for 16000Hz - smaller to reduce latency)
    FORMAT = pyaudio.paInt16  # 16-bit PCM
    
    def __init__(self, device_name: str = "ReSpeaker", callback: Optional[Callable] = None):
        """
        Initialize ReSpeaker audio capture
        
        Args:
            device_name: Substring to match in device name (e.g., "ReSpeaker")
            callback: Optional callback function(audio_chunk) called for each audio chunk
        """
        self.device_name = device_name
        self.callback = callback
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.running = False
        self.audio_queue = queue.Queue(maxsize=500)  # Increased to 500 to handle model loading spikes
        self.device_index = None
        self.dropped_frames = 0
        self.processed_frames = 0
        self.paused = False  # Flag to pause audio collection during heavy processing
        self.overflow_count = 0  # Track overflow events
        
    def find_device(self) -> Optional[int]:
        """Find ReSpeaker device index by name"""
        print("[RESPEAKER] Searching for audio devices...")
        
        device_count = self.audio.get_device_count()
        print(f"[RESPEAKER] Total devices found: {device_count}")
        
        for i in range(device_count):
            try:
                info = self.audio.get_device_info_by_index(i)
                device_name = info.get('name', '')
                channels = info.get('maxInputChannels', 0)
                print(f"[RESPEAKER] Device {i}: {device_name} (input channels: {channels})")
                
                # Look for ReSpeaker or specified device name
                if (self.device_name.lower() in device_name.lower() and channels > 0):
                    print(f"[RESPEAKER] ✓ FOUND: {device_name} (index: {i})")
                    return i
            except Exception as e:
                print(f"[RESPEAKER] ⚠ Error checking device {i}: {e}")
                continue
        
        print(f"[RESPEAKER] ✗ Device '{self.device_name}' not found")
        print(f"[RESPEAKER] Available input devices:")
        for i in range(device_count):
            try:
                info = self.audio.get_device_info_by_index(i)
                if info.get('maxInputChannels', 0) > 0:
                    print(f"[RESPEAKER]   - Device {i}: {info.get('name', 'Unknown')}")
            except:
                pass
                
        return None
    
    def audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback for streaming audio"""
        if status:
            status_names = {
                1: "paInputUnderflow",
                2: "paInputOverflow",
                4: "paNeverDroppedInput"
            }
            status_name = status_names.get(status, f"Unknown({status})")
            
            # Track overflow events
            if status == 2:  # paInputOverflow
                self.overflow_count += 1
                if self.overflow_count % 5 == 1:  # Log first and every 5th
                    queue_size = self.audio_queue.qsize()
                    print(f"[RESPEAKER] ⚠️ INPUT OVERFLOW detected! "
                          f"(event #{self.overflow_count}, queue: {queue_size}/500, paused: {self.paused})")
            else:
                print(f"[RESPEAKER] Audio callback status: {status} ({status_name})")
            
        # If paused, silently drop this frame to allow backpressure
        if self.paused:
            self.dropped_frames += 1
            return (in_data, pyaudio.paContinue)
        
        # Convert bytes to numpy array
        audio_data = np.frombuffer(in_data, dtype=np.int16)
        
        # Calculate and log audio level
        rms = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))
        
        # Add to queue for processing
        try:
            self.audio_queue.put_nowait((audio_data, rms))
            self.processed_frames += 1
        except queue.Full:
            # Drop frame instead of blocking callback
            self.dropped_frames += 1
            if self.dropped_frames % 50 == 0:
                queue_size = self.audio_queue.qsize()
                drop_rate = (self.dropped_frames / (self.processed_frames + self.dropped_frames)) * 100
                print(f"[RESPEAKER] ⚠ Audio queue full: {self.dropped_frames} frames dropped "
                      f"({drop_rate:.1f}%), queue: {queue_size}/500")
            
        # Call user callback if provided
        if self.callback:
            try:
                self.callback(audio_data)
            except Exception as e:
                print(f"[RESPEAKER] Error in callback: {e}")
        
        return (in_data, pyaudio.paContinue)
    
    def start(self) -> bool:
        """
        Start audio capture
        
        Returns:
            True if started successfully, False otherwise
        """
        if self.running:
            print("[RESPEAKER] Warning: Audio capture already running")
            return True
            
        # Find device
        self.device_index = self.find_device()
        if self.device_index is None:
            print("[RESPEAKER] Warning: Could not find audio device by name")
            print("[RESPEAKER] Attempting to use default input device...")
            self.device_index = None  # Will use default
        
        try:
            print(f"[RESPEAKER] Opening audio stream with configuration:")
            print(f"  - Sample rate: {self.SAMPLE_RATE}Hz")
            print(f"  - Channels: {self.CHANNELS}")
            print(f"  - Chunk size: {self.CHUNK_SIZE} samples ({self.CHUNK_SIZE / self.SAMPLE_RATE * 1000:.1f}ms)")
            print(f"  - Device index: {self.device_index if self.device_index is not None else 'default'}")
            
            # Open audio stream
            self.stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.SAMPLE_RATE,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.CHUNK_SIZE,
                stream_callback=self.audio_callback,
                start=False
            )
            
            self.stream.start_stream()
            self.running = True
            print(f"[RESPEAKER] Audio capture started successfully")
            return True
            
        except Exception as e:
            print(f"[RESPEAKER] Error: Failed to start audio capture: {e}")
            return False
    
    def stop(self):
        """Stop audio capture"""
        if not self.running:
            return
            
        print("[INFO] Stopping audio capture...")
        self.running = False
        
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                print(f"[WARNING] Error stopping stream: {e}")
            self.stream = None
            
        # Clear queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except:
                break
        
        # Print statistics
        total_frames = self.processed_frames + self.dropped_frames
        if total_frames > 0:
            drop_rate = (self.dropped_frames / total_frames) * 100
            print(f"[INFO] Audio capture stats:")
            print(f"       Processed frames: {self.processed_frames:,}")
            print(f"       Dropped frames:   {self.dropped_frames:,}")
            print(f"       Drop rate:        {drop_rate:.2f}%")
            print(f"       Overflow events:  {self.overflow_count}")
            
            if self.overflow_count > 5:
                print(f"[WARNING] High number of overflow events detected!")
                print(f"[WARNING] Consider:")
                print(f"         - Reducing CHUNK_SIZE (currently {self.CHUNK_SIZE})")
                print(f"         - Pausing capture during heavy processing")
                print(f"         - Reducing audio processing workload")
        else:
            print("[INFO] Audio capture stats: No frames captured")
        print("[INFO] Audio capture stopped")
    
    def get_audio_chunk(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """
        Get next audio chunk from queue
        
        Args:
            timeout: Maximum time to wait for audio data (seconds)
            
        Returns:
            Audio data as numpy array, or None if timeout
        """
        try:
            audio_data, rms = self.audio_queue.get(timeout=timeout)
            # Log audio level every 10 chunks to avoid spam
            if np.random.random() < 0.1:
                print(f"[RESPEAKER] Audio level: RMS={rms:.2f}")
            return audio_data
        except queue.Empty:
            return None
    
    def pause_capture(self):
        """Pause audio capture (used during heavy processing like model loading)"""
        self.paused = True
        print("[RESPEAKER] Audio capture PAUSED (backpressure during heavy processing)")
    
    def resume_capture(self):
        """Resume audio capture after pause"""
        self.paused = False
        print("[RESPEAKER] Audio capture RESUMED")
    
    def get_buffer_status(self) -> dict:
        """Get current buffer and performance statistics"""
        total_frames = self.processed_frames + self.dropped_frames
        drop_rate = (self.dropped_frames / total_frames * 100) if total_frames > 0 else 0
        
        return {
            "queue_size": self.audio_queue.qsize(),
            "queue_max": self.audio_queue.maxsize,
            "buffer_percent": (self.audio_queue.qsize() / self.audio_queue.maxsize * 100),
            "processed_frames": self.processed_frames,
            "dropped_frames": self.dropped_frames,
            "total_frames": total_frames,
            "drop_rate_percent": drop_rate,
            "overflow_events": self.overflow_count,
            "paused": self.paused
        }
    
    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()
        self.audio.terminate()
    
    def __del__(self):
        """Cleanup on deletion"""
        self.stop()
        if hasattr(self, 'audio'):
            self.audio.terminate()


def test_capture():
    """Test function for ReSpeaker capture"""
    print("[TEST] Starting ReSpeaker capture test...")
    
    def audio_callback(data):
        # Calculate RMS amplitude
        rms = np.sqrt(np.mean(data.astype(np.float32) ** 2))
        print(f"[TEST] Audio level: {rms:.2f}")
    
    with ReSpeakerCapture(callback=audio_callback) as capture:
        print("[TEST] Recording for 10 seconds. Speak into the microphone...")
        time.sleep(10)
    
    print("[TEST] Test complete")


if __name__ == "__main__":
    test_capture()
