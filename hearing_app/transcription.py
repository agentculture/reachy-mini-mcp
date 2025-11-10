#!/usr/bin/env python3
"""
Speech Transcription Module using Faster-Whisper

Transcribes audio segments to text and detects language.
"""

import numpy as np
from faster_whisper import WhisperModel
from typing import Optional, Tuple, Dict
import time


class TranscriptionProcessor:
    """Transcribes speech using Faster-Whisper"""
    
    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "auto",
        language: Optional[str] = None,
        detect_language: bool = True,
        target_language: str = "en"
    ):
        """
        Initialize transcription processor
        
        Args:
            model_size: Whisper model size (tiny, base, small, medium, large-v3)
            device: Device to run on ("cpu", "cuda", or "auto")
            compute_type: Compute type ("int8", "float16", "float32", or "auto")
            language: Force specific language (None for auto-detect)
            detect_language: Whether to detect language
            target_language: Target language to filter (e.g., "en" for English)
        """
        self.model_size = model_size
        self.language = language
        self.detect_language = detect_language
        self.target_language = target_language
        
        # Auto-detect device and compute type if needed
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except:
                device = "cpu"
        
        if compute_type == "auto":
            compute_type = "float16" if device == "cuda" else "int8"
        
        print(f"[INFO] Loading Faster-Whisper model ({model_size}) on {device} with {compute_type}...")
        
        try:
            self.model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type,
                download_root=None
            )
            print(f"[INFO] Faster-Whisper model loaded successfully")
        except Exception as e:
            print(f"[ERROR] Failed to load Faster-Whisper model: {e}")
            raise
        
        self.stats = {
            "total_transcriptions": 0,
            "total_duration": 0.0,
            "languages_detected": {}
        }
    
    def transcribe(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000
    ) -> Optional[Dict]:
        """
        Transcribe audio segment
        
        Args:
            audio_data: Audio data as numpy array (int16)
            sample_rate: Sample rate of audio
            
        Returns:
            Dictionary with transcription results:
            {
                "text": str,
                "language": str,
                "language_probability": float,
                "confidence": float,
                "duration": float,
                "is_target_language": bool
            }
            Or None if transcription failed
        """
        if audio_data is None or len(audio_data) == 0:
            return None
        
        # Convert to float32 normalized to [-1, 1]
        audio_float = audio_data.astype(np.float32) / 32768.0
        
        # Ensure sample rate is 16kHz (Whisper requirement)
        if sample_rate != 16000:
            print(f"[WARNING] Audio sample rate is {sample_rate}Hz, Whisper expects 16kHz")
            # In production, you should resample here
        
        start_time = time.time()
        
        try:
            # Transcribe
            segments, info = self.model.transcribe(
                audio_float,
                language=self.language,
                beam_size=5,
                vad_filter=False,  # We already did VAD
                word_timestamps=False
            )
            
            # Collect all segments
            text_parts = []
            total_confidence = 0.0
            segment_count = 0
            
            for segment in segments:
                text_parts.append(segment.text.strip())
                # Use log probability as confidence proxy
                total_confidence += np.exp(segment.avg_logprob)
                segment_count += 1
            
            transcription_time = time.time() - start_time
            
            if not text_parts:
                print("[INFO] No speech detected in audio segment")
                return None
            
            # Combine text
            text = " ".join(text_parts).strip()
            
            if not text:
                return None
            
            # Calculate average confidence
            confidence = total_confidence / segment_count if segment_count > 0 else 0.0
            
            # Get language info
            detected_language = info.language if self.detect_language else (self.language or "unknown")
            language_probability = info.language_probability if self.detect_language else 1.0
            
            # Check if target language
            is_target_language = (detected_language.lower() == self.target_language.lower()) if self.target_language else True
            
            # Update stats
            self.stats["total_transcriptions"] += 1
            self.stats["total_duration"] += len(audio_data) / sample_rate
            self.stats["languages_detected"][detected_language] = \
                self.stats["languages_detected"].get(detected_language, 0) + 1
            
            result = {
                "text": text,
                "language": detected_language,
                "language_probability": float(language_probability),
                "confidence": float(confidence),
                "duration": len(audio_data) / sample_rate,
                "processing_time": transcription_time,
                "is_target_language": is_target_language
            }
            
            print(f"[TRANSCRIBE] Text: '{text}' | Lang: {detected_language} ({language_probability:.2f}) | "
                  f"Conf: {confidence:.2f} | Time: {transcription_time:.2f}s")
            
            return result
            
        except Exception as e:
            print(f"[ERROR] Transcription error: {e}")
            return None
    
    def get_stats(self) -> Dict:
        """Get transcription statistics"""
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset statistics"""
        self.stats = {
            "total_transcriptions": 0,
            "total_duration": 0.0,
            "languages_detected": {}
        }


def test_transcription():
    """Test function for transcription processor"""
    print("[TEST] Starting transcription processor test...")
    
    # Create processor
    processor = TranscriptionProcessor(
        model_size="tiny",  # Use tiny model for testing
        device="cpu",
        target_language="en"
    )
    
    print("[TEST] Transcription processor initialized")
    print("[TEST] In real usage, pass audio from VAD to transcribe()")
    
    # Note: We can't easily test without real audio
    # In production, audio comes from VAD processor
    
    print("[TEST] Stats:", processor.get_stats())
    print("[TEST] Test complete")


if __name__ == "__main__":
    test_transcription()
