#!/usr/bin/env python3
"""
Voice Activity Detection (VAD) Processor using SileroVAD

Detects speech segments in audio stream and buffers complete utterances.
"""

import torch
import numpy as np
from collections import deque
from typing import Optional, List
import time


class VADProcessor:
    """Voice Activity Detection using SileroVAD"""
    
    def __init__(
        self,
        sample_rate: int = 16000,
        threshold: float = 0.5,
        min_speech_duration_ms: int = 250,
        max_speech_duration_s: float = 30.0,
        min_silence_duration_ms: int = 500,
        speech_pad_ms: int = 300,
        #vad_frame_size_ms: int = 96  # Process VAD every N ms to reduce CPU load
        vad_frame_size_ms: int = 192  # Process VAD every N ms to reduce CPU load
    ):
        """
        Initialize VAD processor
        
        Args:
            sample_rate: Audio sample rate (Hz)
            threshold: Speech probability threshold (0-1)
            min_speech_duration_ms: Minimum speech duration to trigger detection (ms)
            max_speech_duration_s: Maximum speech duration before forcing split (s)
            min_silence_duration_ms: Minimum silence to end speech segment (ms)
            speech_pad_ms: Padding to add before/after speech (ms)
        """
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.min_speech_duration_ms = min_speech_duration_ms
        self.max_speech_duration_s = max_speech_duration_s
        self.min_silence_duration_ms = min_silence_duration_ms
        self.speech_pad_ms = speech_pad_ms
        self.vad_frame_size_ms = vad_frame_size_ms
        
        # Load Silero VAD model
        print("[INFO] Loading SileroVAD model...")
        try:
            self.model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=False
            )
            self.get_speech_timestamps = utils[0]
            print("[INFO] SileroVAD model loaded successfully")
        except Exception as e:
            print(f"[ERROR] Failed to load SileroVAD model: {e}")
            raise
        
        # State tracking
        self.is_speaking = False
        self.speech_buffer = []
        self.silence_buffer = []
        self.speech_start_time = None
        self.last_speech_time = None
        
        # Audio buffer for context
        self.audio_buffer = deque(maxlen=int(sample_rate * 2))  # 2 second rolling buffer
        
        # Convert time parameters to samples
        self.min_speech_samples = int(min_speech_duration_ms * sample_rate / 1000)
        self.min_silence_samples = int(min_silence_duration_ms * sample_rate / 1000)
        self.speech_pad_samples = int(speech_pad_ms * sample_rate / 1000)
        self.max_speech_samples = int(max_speech_duration_s * sample_rate)
        self.vad_frame_size = int(vad_frame_size_ms * sample_rate / 1000)
        
        # VAD accumulation buffer to reduce processing frequency
        self.vad_accumulator = []
        self.frames_since_last_vad = 0
        self.vad_check_count = 0
        print(f"[VAD] Initialized with: threshold={threshold}, "
              f"min_speech={min_speech_duration_ms}ms, min_silence={min_silence_duration_ms}ms")
    
    def process_chunk(self, audio_chunk: np.ndarray) -> Optional[np.ndarray]:
        """
        Process audio chunk and return complete speech segment if available
        
        Args:
            audio_chunk: Audio data as numpy array (int16)
            
        Returns:
            Complete speech segment as numpy array, or None if no complete segment
        """
        # Add to rolling buffer
        self.audio_buffer.extend(audio_chunk)
        
        # Accumulate audio for VAD processing to reduce CPU usage
        self.vad_accumulator.extend(audio_chunk)
        self.frames_since_last_vad += len(audio_chunk)
        
        # Only run VAD when we have enough accumulated frames
        if self.frames_since_last_vad < self.vad_frame_size:
            # Not enough data yet, but still collect speech if already speaking
            if self.is_speaking:
                self.speech_buffer.extend(audio_chunk)
                # Check if speech is too long
                if len(self.speech_buffer) > self.max_speech_samples:
                    print(f"[VAD] Max speech duration reached, forcing segment end")
                    return self._finalize_speech_segment()
            return None
        
        # Convert accumulated audio to float32 for VAD model
        accumulated_array = np.array(self.vad_accumulator, dtype=np.int16)
        audio_float = accumulated_array.astype(np.float32) / 32768.0
        audio_tensor = torch.from_numpy(audio_float)
        
        # Get speech probability
        try:
            speech_prob = self.model(audio_tensor, self.sample_rate).item()
            self.vad_check_count += 1
        except Exception as e:
            print(f"[ERROR] VAD processing error: {e}")
            # Reset accumulator and continue
            self.vad_accumulator = []
            self.frames_since_last_vad = 0
            return None
        
        # Reset accumulator
        self.vad_accumulator = []
        self.frames_since_last_vad = 0
        
        is_speech = speech_prob > self.threshold
        current_time = time.time()
        
        # State machine for speech detection
        if is_speech:
            self.last_speech_time = current_time
            
            if not self.is_speaking:
                # Speech started
                self.is_speaking = True
                self.speech_start_time = current_time
                
                # Add padding from buffer if available
                pad_start = max(0, len(self.audio_buffer) - len(audio_chunk) - self.speech_pad_samples)
                self.speech_buffer = list(self.audio_buffer)[pad_start:]
                
                print(f"[VAD] ✓ SPEECH STARTED (prob: {speech_prob:.3f}, buffer: {len(self.speech_buffer)} samples)")
            else:
                # Continue collecting speech
                self.speech_buffer.extend(audio_chunk)
                buffer_duration = len(self.speech_buffer) / self.sample_rate
                
                # Check if speech is too long
                if len(self.speech_buffer) > self.max_speech_samples:
                    print(f"[VAD] ✗ Max speech duration reached ({buffer_duration:.2f}s), forcing segment end")
                    return self._finalize_speech_segment()
                
                # Log progress every 1 second
                if buffer_duration > 0 and buffer_duration % 1.0 < (len(audio_chunk) / self.sample_rate):
                    print(f"[VAD] → Speech in progress: {buffer_duration:.2f}s (prob: {speech_prob:.3f})")
        else:
            if self.is_speaking:
                # Potential end of speech, buffer silence
                self.silence_buffer.extend(audio_chunk)
                
                # Check if silence is long enough to end speech
                silence_duration = len(self.silence_buffer)
                time_since_speech = current_time - self.last_speech_time if self.last_speech_time else 0
                speech_duration = len(self.speech_buffer) / self.sample_rate if self.speech_buffer else 0
                
                if (silence_duration >= self.min_silence_samples and 
                    len(self.speech_buffer) >= self.min_speech_samples):
                    # Speech ended
                    print(f"[VAD] ✓ SPEECH ENDED")
                    print(f"      Duration: {speech_duration:.2f}s")
                    print(f"      Silence before end: {silence_duration / self.sample_rate:.2f}s")
                    print(f"      Total buffer: {len(self.speech_buffer)} samples")
                    
                    # Add some silence padding
                    pad_samples = min(len(self.silence_buffer), self.speech_pad_samples)
                    self.speech_buffer.extend(list(self.silence_buffer)[:pad_samples])
                    
                    return self._finalize_speech_segment()
                elif time_since_speech > 2.0:  # Force end after 2 seconds of silence
                    print(f"[VAD] ✗ SPEECH TIMEOUT (2s+ silence)")
                    print(f"      Speech duration: {speech_duration:.2f}s")
                    print(f"      Silence duration: {silence_duration / self.sample_rate:.2f}s")
                    return self._finalize_speech_segment()
        
        return None
    
    def _finalize_speech_segment(self) -> np.ndarray:
        """Finalize and return speech segment, reset state"""
        if not self.speech_buffer:
            print("[VAD] ⚠ Speech buffer empty, nothing to finalize")
            self.reset()
            return None
            
        # Convert buffer to numpy array
        speech_array = np.array(self.speech_buffer, dtype=np.int16)
        duration = len(speech_array) / self.sample_rate
        
        print(f"[VAD] ✓ SEGMENT FINALIZED: {len(speech_array)} samples ({duration:.2f}s)")
        
        # Reset state
        self.reset()
        
        return speech_array
    
    def reset(self):
        """Reset VAD state"""
        self.is_speaking = False
        self.speech_buffer = []
        self.silence_buffer = []
        self.speech_start_time = None
        self.last_speech_time = None
        self.vad_accumulator = []
        self.frames_since_last_vad = 0
    
    def get_state(self) -> dict:
        """Get current VAD state"""
        return {
            "is_speaking": self.is_speaking,
            "buffer_size": len(self.speech_buffer),
            "buffer_duration_s": len(self.speech_buffer) / self.sample_rate if self.speech_buffer else 0,
            "speech_start_time": self.speech_start_time,
            "last_speech_time": self.last_speech_time,
            "vad_checks_performed": self.vad_check_count
        }


def test_vad():
    """Test function for VAD processor"""
    print("[TEST] Starting VAD processor test...")
    
    # Create test audio with speech-like patterns
    sample_rate = 16000
    vad = VADProcessor(sample_rate=sample_rate)
    
    print("[TEST] Simulating audio stream with speech patterns...")
    
    # Simulate 5 seconds of audio
    for i in range(50):  # 50 chunks of 0.1s each
        # Generate random audio (simulating speech/silence)
        if i < 10 or i > 40:
            # Silence
            audio = np.random.randint(-1000, 1000, int(sample_rate * 0.1), dtype=np.int16)
        else:
            # "Speech" (higher amplitude)
            audio = np.random.randint(-10000, 10000, int(sample_rate * 0.1), dtype=np.int16)
        
        result = vad.process_chunk(audio)
        if result is not None:
            print(f"[TEST] Speech segment detected: {len(result)} samples ({len(result)/sample_rate:.2f}s)")
        
        time.sleep(0.05)  # Simulate real-time processing
    
    print("[TEST] VAD test complete")
    print(f"[TEST] Final state: {vad.get_state()}")


if __name__ == "__main__":
    test_vad()
