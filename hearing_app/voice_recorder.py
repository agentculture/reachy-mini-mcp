#!/usr/bin/env python3
"""
Voice Recorder - Integrates audio capture, speech detection, and transcription

Based on the baby-tau implementation pattern for better performance.
Uses Producer-Consumer pattern to avoid race conditions.
"""

import time
import logging
import threading
import queue
from typing import Optional, Callable
from respeaker_capture import ReSpeakerCapture
from speech_detector import SpeechDetector
from speech_transcriber import SpeechTranscriber


class VoiceRecorder:
    """Integrated voice recorder with VAD and transcription"""
    
    def __init__(
        self,
        device_name: str = "ReSpeaker",
        model_size: str = "base",
        device: str = "cuda",
        initial_prompt: Optional[str] = None,
        language: Optional[str] = None,
        on_transcription: Optional[Callable] = None
    ):
        """
        Initialize voice recorder
        
        Args:
            device_name: Audio device name to search for
            model_size: Whisper model size
            device: Device to run models on ('cpu', 'cuda', 'auto')
            initial_prompt: Optional initial prompt for Whisper
            language: Language code (None for auto-detect)
            on_transcription: Callback function(result_dict) when transcription completes
        """
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        self.on_transcription = on_transcription
        
        # Initialize components
        self.logger.info("Initializing voice recorder components...")
        
        # Audio capture
        self.capture = ReSpeakerCapture(device_name=device_name)
        
        # Speech detector with callback
        self.detector = SpeechDetector(
            sample_rate=self.capture.SAMPLE_RATE,
            threshold=0.5,
            max_silence_duration=1.0,
            device=device,
            callback=self._on_speech_segment
        )
        
        # Transcriber (load after detector to allow audio to start)
        self.transcriber = None
        self.model_size = model_size
        self.model_device = device
        self.initial_prompt = initial_prompt
        self.language = language
        
        # Threading control
        self.running = False
        self.transcribing = False  # Flag to track active transcription
        self.transcription_queue = queue.Queue(maxsize=2)  # Limit queue size to prevent memory issues
        self.worker_thread = None
        self.dropped_segments = 0  # Counter for dropped segments
        
    def _on_speech_segment(self, audio_data):
        """
        Callback when speech segment is detected - MUST be extremely fast
        
        This is called from the VAD (speech detector). Its only job is to:
        1. Check if we're already transcribing
        2. If busy, drop the segment
        3. If free, add to queue (non-blocking)
        
        NO threading spawns here. NO blocking operations.
        """
        # Check if already transcribing - if so, drop this segment
        if self.transcribing:
            self.dropped_segments += 1
            self.logger.debug(
                f"Already transcribing, dropping speech segment "
                f"(total dropped: {self.dropped_segments})"
            )
            return
        
        # Try to add to queue without blocking
        try:
            self.transcription_queue.put_nowait(audio_data)
            self.logger.debug("Speech segment added to transcription queue")
        except queue.Full:
            self.dropped_segments += 1
            self.logger.warning(
                f"Transcription queue full, dropping segment "
                f"(total dropped: {self.dropped_segments})"
            )
    
    def _transcription_worker(self):
        """
        Worker thread that processes transcription queue
        
        This runs in a single dedicated thread. It:
        1. Blocks waiting for audio segments
        2. Sets transcribing flag
        3. Does the slow transcription
        4. Clears transcribing flag
        5. Repeats
        
        This serializes all transcriptions, preventing race conditions.
        """
        self.logger.info("Transcription worker thread started")
        
        while self.running:
            try:
                # Block waiting for audio data (with timeout to check self.running)
                try:
                    audio_data = self.transcription_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                
                if self.transcriber is None:
                    self.logger.warning("Transcriber not ready, skipping segment")
                    continue
                
                # Mark as transcribing BEFORE starting the slow operation
                self.transcribing = True
                
                try:
                    self.logger.info("Transcribing speech segment...")
                    
                    # This is the slow, blocking operation
                    result = self.transcriber.transcribe(audio_data)
                    
                    if result and self.on_transcription:
                        # Call user callback with result
                        self.on_transcription(result)
                        
                except Exception as e:
                    self.logger.error(f"Error transcribing audio: {e}")
                    import traceback
                    traceback.print_exc()
                finally:
                    # Always clear the flag, even if transcription failed
                    self.transcribing = False
                    self.logger.debug("Transcription complete, ready for next segment")
                    
            except Exception as e:
                self.logger.error(f"Error in transcription worker: {e}")
                import traceback
                traceback.print_exc()
        
        self.logger.info("Transcription worker thread stopped")
    
    def start(self):
        """Start voice recording"""
        if self.running:
            self.logger.warning("Voice recorder already running")
            return
        
        try:
            # Load transcriber FIRST, before starting audio capture
            # This prevents hardware buffer overflow during slow model loading
            self.logger.info(f"Loading Whisper model ({self.model_size})...")
            self.transcriber = SpeechTranscriber(
                model_size=self.model_size,
                device=self.model_device,
                compute_type="auto",
                initial_prompt=self.initial_prompt,
                language=self.language
            )
            self.logger.info("✓ Whisper model loaded")
            
            # NOW start audio capture (after heavy model is loaded)
            self.logger.info("Starting audio capture...")
            if not self.capture.start():
                self.logger.error("Failed to start audio capture")
                return False
            
            self.running = True
            
            # Start the single worker thread for transcription
            self.worker_thread = threading.Thread(
                target=self._transcription_worker,
                daemon=True,
                name="TranscriptionWorker"
            )
            self.worker_thread.start()
            
            self.logger.info("✓ Voice recorder started successfully")
            
            # Main processing loop - Producer thread
            # Its ONLY job is to drain the audio hardware buffer as fast as possible
            # and feed the lightweight VAD
            self.logger.info("Listening for speech...")
            chunk_count = 0
            while self.running:
                # Get audio chunk with short timeout to keep draining the queue
                audio_chunk = self.capture.get_audio_chunk(timeout=0.1)
                
                if audio_chunk is None:
                    continue
                
                chunk_count += 1
                
                # Process with speech detector (lightweight, non-blocking)
                # The detector will call _on_speech_segment when speech is detected
                try:
                    self.detector.process_audio(audio_chunk)
                except Exception as e:
                    self.logger.error(f"Error in speech detector: {e}")
                
                # Periodically check buffer status
                if chunk_count % 100 == 0:
                    status = self.capture.get_buffer_status()
                    if status['buffer_percent'] > 50:
                        self.logger.warning(
                            f"Audio queue filling up: {status['queue_size']}/{status['queue_max']} "
                            f"({status['buffer_percent']:.1f}%), dropped: {status['dropped_frames']}"
                        )
                    
                    # Also log transcription stats
                    if self.dropped_segments > 0:
                        self.logger.info(
                            f"Transcription status - "
                            f"Queue: {self.transcription_queue.qsize()}, "
                            f"Dropped segments: {self.dropped_segments}, "
                            f"Currently transcribing: {self.transcribing}"
                        )
                
        except KeyboardInterrupt:
            self.logger.info("Voice recorder interrupted by user")
        except Exception as e:
            self.logger.error(f"Error in voice recorder: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.stop()
    
    def stop(self):
        """Stop voice recording"""
        self.logger.info("Stopping voice recorder...")
        self.running = False
        
        # Wait for worker thread to finish
        if self.worker_thread and self.worker_thread.is_alive():
            self.logger.info("Waiting for transcription worker to finish...")
            self.worker_thread.join(timeout=5.0)
            if self.worker_thread.is_alive():
                self.logger.warning("Transcription worker did not stop gracefully")
        
        if self.capture:
            self.capture.stop()
        
        self.logger.info("Voice recorder stopped")
    
    def get_stats(self) -> dict:
        """Get recording statistics"""
        stats = {
            "detector": self.detector.get_state() if self.detector else {},
            "transcriber": self.transcriber.get_stats() if self.transcriber else {},
            "queue_size": self.transcription_queue.qsize(),
            "dropped_segments": self.dropped_segments,
            "transcribing": self.transcribing
        }
        
        if self.capture:
            stats["capture"] = self.capture.get_buffer_status()
        
        return stats


def main():
    """Example usage"""
    def handle_transcription(result):
        print(f"\n{'='*60}")
        print(f"TRANSCRIPTION:")
        print(f"  Text: {result['text']}")
        print(f"  Language: {result['language']} ({result['language_probability']:.2f})")
        print(f"  Duration: {result['duration']:.2f}s")
        print(f"{'='*60}\n")
    
    recorder = VoiceRecorder(
        device_name="ReSpeaker",
        model_size="base",
        device="cuda",
        initial_prompt="The following is a clear and accurate transcription:",
        language=None,  # Auto-detect
        on_transcription=handle_transcription
    )
    
    try:
        recorder.start()
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        recorder.stop()


if __name__ == "__main__":
    main()
