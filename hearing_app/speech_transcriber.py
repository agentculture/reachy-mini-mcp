#!/usr/bin/env python3
"""
Speech Transcriber using Faster-Whisper

Transcribes speech segments detected by SpeechDetector.
Based on the baby-tau implementation pattern.
"""

import numpy as np
import wave
import io
import logging
from faster_whisper import WhisperModel
from typing import Optional, Dict


class SpeechTranscriber:
    """Transcribes speech using Faster-Whisper"""
    
    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "auto",
        initial_prompt: Optional[str] = None,
        language: Optional[str] = None
    ):
        """
        Initialize speech transcriber
        
        Args:
            model_size: Whisper model size (tiny, base, small, medium, large-v3)
            device: Device to run on ('cpu', 'cuda', or 'auto')
            compute_type: Compute type ('int8', 'float16', 'float32', or 'auto')
            initial_prompt: Optional initial prompt to guide transcription
            language: Language code (None for auto-detect)
        """
        # Configure logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        self.sample_rate = 16000  # Whisper requires 16kHz
        self.initial_prompt = initial_prompt
        self.language = language
        
        # Auto-detect device and compute type
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except:
                device = "cpu"
        
        if compute_type == "auto":
            compute_type = "float16" if device == "cuda" else "int8"
        
        self.logger.info(f"Loading Whisper model ({model_size}) on {device} with {compute_type}...")
        
        try:
            self.whisper_model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type
            )
            self.logger.info("✓ Whisper model loaded successfully")
        except Exception as e:
            self.logger.error(f"Failed to load Whisper model: {e}")
            raise
        
        # Statistics
        self.total_transcriptions = 0
        self.languages_detected = {}
    
    def transcribe(self, audio_data: np.ndarray) -> Optional[Dict]:
        """
        Transcribe audio segment
        
        Args:
            audio_data: Audio data as numpy array (int16)
            
        Returns:
            Dictionary with transcription results or None
        """
        if audio_data is None or len(audio_data) == 0:
            return None
        
        try:
            # Create WAV buffer from audio data
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_data.tobytes())
            
            wav_buffer.seek(0)
            
            # Transcribe with Whisper
            segments, info = self.whisper_model.transcribe(
                wav_buffer,
                beam_size=5,
                initial_prompt=self.initial_prompt,
                language=self.language,
                condition_on_previous_text=True,
                vad_filter=False  # We already did VAD
            )
            
            # Collect transcription text
            transcription_parts = []
            for segment in segments:
                text = segment.text.strip()
                if text:
                    transcription_parts.append(text)
            
            if not transcription_parts:
                return None
            
            transcription = " ".join(transcription_parts)
            
            # Get language info
            detected_language = info.language if self.language is None else self.language
            language_probability = info.language_probability if self.language is None else 1.0
            
            # Update statistics
            self.total_transcriptions += 1
            self.languages_detected[detected_language] = \
                self.languages_detected.get(detected_language, 0) + 1
            
            result = {
                "text": transcription,
                "language": detected_language,
                "language_probability": float(language_probability),
                "duration": len(audio_data) / self.sample_rate
            }
            
            self.logger.info(f"✓ Transcribed: '{transcription}' [{detected_language}] ({language_probability:.2f})")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Transcription error: {e}")
            return None
    
    def get_stats(self) -> Dict:
        """Get transcription statistics"""
        return {
            "total_transcriptions": self.total_transcriptions,
            "languages_detected": self.languages_detected.copy()
        }


if __name__ == "__main__":
    print("[TEST] Speech Transcriber Test")
    transcriber = SpeechTranscriber(model_size="tiny", device="cpu")
    print(f"[TEST] Stats: {transcriber.get_stats()}")
