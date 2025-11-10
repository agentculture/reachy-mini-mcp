#!/usr/bin/env python3
"""
Speech Detector using Silero VAD

Lightweight speech detection that processes audio in callback.
Based on the baby-tau implementation pattern.
"""

import torch
import numpy as np
from typing import Optional, Callable


class SpeechDetector:
    """Lightweight speech detector using Silero VAD"""
    
    def __init__(
        self,
        sample_rate: int = 16000,
        threshold: float = 0.5,
        max_silence_duration: float = 1.0,
        device: str = 'cuda',
        callback: Optional[Callable] = None
    ):
        """
        Initialize speech detector
        
        Args:
            sample_rate: Audio sample rate (Hz)
            threshold: Speech probability threshold (0-1)
            max_silence_duration: Maximum silence before ending speech (seconds)
            device: Device to run VAD on ('cpu' or 'cuda')
            callback: Optional callback(audio_buffer) when speech segment completes
        """
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.max_silence_duration = max_silence_duration
        self.callback = callback
        
        # Load Silero VAD model
        print(f"[SPEECH_DETECTOR] Loading Silero VAD model on {device}...")
        self.device = torch.device(device)
        self.model, _ = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False
        )
        self.model = self.model.to(self.device)
        print("[SPEECH_DETECTOR] ✓ Silero VAD model loaded")
        
        # Speech detection state
        self.speaking = False
        self.silence_duration = 0
        self.audio_buffer = []
        
        # Statistics
        self.speech_segments_detected = 0
        
    def process_audio(self, audio_chunk: np.ndarray) -> Optional[np.ndarray]:
        """
        Process audio chunk and detect speech
        
        Args:
            audio_chunk: Audio data as numpy array (int16)
            
        Returns:
            Complete speech segment if detected, None otherwise
        """
        # Convert to tensor for VAD
        audio_tensor = torch.from_numpy(audio_chunk).float()
        audio_tensor = audio_tensor / 32768.0  # Normalize to [-1, 1]
        audio_tensor = audio_tensor.unsqueeze(0).to(self.device)
        
        # Get speech probability
        try:
            speech_prob = self.model(audio_tensor, self.sample_rate).item()
        except Exception as e:
            print(f"[SPEECH_DETECTOR] VAD error: {e}")
            return None
        
        # Speech detection state machine
        if speech_prob > self.threshold:
            # Speech detected
            if not self.speaking:
                print(f"[SPEECH_DETECTOR] 🎤 Speech started (prob: {speech_prob:.3f})")
                self.speaking = True
                self.audio_buffer = []
            
            self.audio_buffer.append(audio_chunk.tobytes())
            self.silence_duration = 0
            
        else:
            # No speech
            if self.speaking:
                # We were speaking, accumulate silence
                self.silence_duration += len(audio_chunk) / self.sample_rate
                self.audio_buffer.append(audio_chunk.tobytes())
                
                # Check if silence is long enough to end speech
                if self.silence_duration > self.max_silence_duration:
                    print(f"[SPEECH_DETECTOR] 🔇 Speech ended (silence: {self.silence_duration:.2f}s)")
                    
                    # Finalize speech segment
                    speech_segment = self._finalize_speech()
                    return speech_segment
        
        return None
    
    def _finalize_speech(self) -> Optional[np.ndarray]:
        """Finalize and return speech segment"""
        if not self.audio_buffer:
            self.speaking = False
            self.silence_duration = 0
            return None
        
        # Convert buffer to numpy array
        audio_bytes = b''.join(self.audio_buffer)
        speech_array = np.frombuffer(audio_bytes, dtype=np.int16)
        
        duration = len(speech_array) / self.sample_rate
        print(f"[SPEECH_DETECTOR] ✓ Segment finalized: {len(speech_array)} samples ({duration:.2f}s)")
        
        # Reset state
        self.speaking = False
        self.silence_duration = 0
        self.audio_buffer = []
        self.speech_segments_detected += 1
        
        # Call callback if provided
        if self.callback:
            try:
                self.callback(speech_array)
            except Exception as e:
                print(f"[SPEECH_DETECTOR] Callback error: {e}")
        
        return speech_array
    
    def get_state(self) -> dict:
        """Get current detector state"""
        buffer_samples = sum(len(chunk) for chunk in self.audio_buffer) // 2  # 2 bytes per sample
        return {
            "speaking": self.speaking,
            "silence_duration": self.silence_duration,
            "buffer_duration_s": buffer_samples / self.sample_rate if buffer_samples > 0 else 0,
            "segments_detected": self.speech_segments_detected
        }
    
    def reset(self):
        """Reset detector state"""
        self.speaking = False
        self.silence_duration = 0
        self.audio_buffer = []


if __name__ == "__main__":
    print("[TEST] Speech Detector Test")
    detector = SpeechDetector()
    print(f"[TEST] State: {detector.get_state()}")
