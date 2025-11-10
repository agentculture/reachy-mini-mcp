#!/usr/bin/env python3
"""
Audio Diagnostics Tool

Captures and analyzes audio from ReSpeaker microphone to diagnose:
- Audio overflow issues
- Recording quality
- Noise levels
- Whether speech is actually being captured
"""

import numpy as np
import wave
import time
from datetime import datetime
from respeaker_capture import ReSpeakerCapture


class AudioDiagnostics:
    """Diagnoses audio capture issues"""
    
    def __init__(self, device_name: str = "ReSpeaker", duration_seconds: int = 10):
        """
        Initialize audio diagnostics
        
        Args:
            device_name: Audio device name to search for
            duration_seconds: How long to record
        """
        self.device_name = device_name
        self.duration_seconds = duration_seconds
        self.audio_data = []
        self.rms_levels = []
        self.capture_times = []
        
    def record_audio(self):
        """Record audio and collect diagnostics"""
        print(f"\n{'='*60}")
        print(f"[DIAGNOSTICS] Starting {self.duration_seconds} second audio recording...")
        print(f"{'='*60}\n")
        
        def diagnostic_callback(data):
            """Callback to collect audio diagnostics"""
            rms = np.sqrt(np.mean(data.astype(np.float32) ** 2))
            self.audio_data.append(data.copy())
            self.rms_levels.append(rms)
            self.capture_times.append(time.time())
        
        try:
            # Create capture with diagnostic callback
            capture = ReSpeakerCapture(device_name=self.device_name, callback=diagnostic_callback)
            
            if not capture.start():
                print("[ERROR] Failed to start audio capture")
                return False
            
            print(f"[DIAGNOSTICS] Recording for {self.duration_seconds} seconds...")
            print(f"[DIAGNOSTICS] (Speak normally into the microphone)\n")
            
            # Record for specified duration
            start_time = time.time()
            last_report = start_time
            
            while time.time() - start_time < self.duration_seconds:
                elapsed = time.time() - start_time
                
                # Print status every 1 second
                if time.time() - last_report >= 1.0:
                    buffer_usage = capture.audio_queue.qsize()
                    max_buffer = capture.audio_queue.maxsize
                    buffer_percent = (buffer_usage / max_buffer * 100) if max_buffer else 0
                    
                    print(f"[{elapsed:5.1f}s] Buffer: {buffer_usage:3d}/{max_buffer} "
                          f"({buffer_percent:5.1f}%) | "
                          f"Processed: {capture.processed_frames:6d} | "
                          f"Dropped: {capture.dropped_frames:6d}")
                    last_report = time.time()
                
                time.sleep(0.1)
            
            capture.stop()
            print(f"\n[DIAGNOSTICS] Recording complete!")
            print(f"[DIAGNOSTICS] Captured {len(self.audio_data)} chunks")
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Recording failed: {e}")
            return False
    
    def analyze_audio(self):
        """Analyze captured audio and print diagnostics"""
        if not self.audio_data:
            print("[ERROR] No audio data to analyze")
            return
        
        # Concatenate all audio
        all_audio = np.concatenate(self.audio_data)
        
        print(f"\n{'='*60}")
        print("[DIAGNOSTICS] AUDIO ANALYSIS REPORT")
        print(f"{'='*60}\n")
        
        # Duration
        sample_rate = ReSpeakerCapture.SAMPLE_RATE
        total_samples = len(all_audio)
        total_duration = total_samples / sample_rate
        print(f"Total Samples:     {total_samples:,}")
        print(f"Total Duration:    {total_duration:.2f} seconds")
        print(f"Sample Rate:       {sample_rate} Hz")
        print(f"Chunks Captured:   {len(self.audio_data)}")
        
        # Amplitude statistics
        audio_float = all_audio.astype(np.float32)
        rms_overall = np.sqrt(np.mean(audio_float ** 2))
        peak = np.max(np.abs(audio_float))
        mean_level = np.mean(np.abs(audio_float))
        
        print(f"\n{'AMPLITUDE ANALYSIS':^60}")
        print(f"-" * 60)
        print(f"RMS Level:         {rms_overall:>10,.0f} (0-32768 scale)")
        print(f"Peak Level:        {peak:>10,.0f}")
        print(f"Mean Level:        {mean_level:>10,.0f}")
        print(f"Dynamic Range:     {20 * np.log10(peak / (rms_overall + 1e-10)) if rms_overall > 0 else 0:.2f} dB")
        
        # Noise floor estimation (lowest 10% of RMS values)
        sorted_rms = sorted(self.rms_levels)
        noise_floor = sorted_rms[int(len(sorted_rms) * 0.1)]
        signal_threshold = noise_floor * 2
        
        print(f"\nNoise Floor (est): {noise_floor:>10,.0f}")
        print(f"Signal Threshold:  {signal_threshold:>10,.0f}")
        
        # Count active frames (above threshold)
        active_frames = sum(1 for rms in self.rms_levels if rms > signal_threshold)
        silence_frames = len(self.rms_levels) - active_frames
        active_duration = active_frames * (ReSpeakerCapture.CHUNK_SIZE / sample_rate)
        silence_duration = silence_frames * (ReSpeakerCapture.CHUNK_SIZE / sample_rate)
        
        print(f"\n{'SPEECH DETECTION':^60}")
        print(f"-" * 60)
        print(f"Estimated Speech:  {active_duration:.2f}s ({active_frames} frames)")
        print(f"Estimated Silence: {silence_duration:.2f}s ({silence_frames} frames)")
        print(f"Speech Ratio:      {active_duration / total_duration * 100:.1f}%")
        
        # RMS level statistics
        print(f"\n{'RMS LEVEL STATISTICS':^60}")
        print(f"-" * 60)
        print(f"Min RMS:           {min(self.rms_levels):>10,.0f}")
        print(f"Max RMS:           {max(self.rms_levels):>10,.0f}")
        print(f"Mean RMS:          {np.mean(self.rms_levels):>10,.0f}")
        print(f"Median RMS:        {np.median(self.rms_levels):>10,.0f}")
        print(f"Stdev RMS:         {np.std(self.rms_levels):>10,.0f}")
        
        # Frame timing
        if len(self.capture_times) > 1:
            frame_intervals = np.diff(self.capture_times)
            print(f"\n{'TIMING ANALYSIS':^60}")
            print(f"-" * 60)
            print(f"Frames Captured:   {len(self.capture_times)}")
            print(f"Avg Frame Interval:{np.mean(frame_intervals)*1000:>9.2f} ms")
            print(f"Min Frame Interval:{np.min(frame_intervals)*1000:>9.2f} ms")
            print(f"Max Frame Interval:{np.max(frame_intervals)*1000:>9.2f} ms")
            
            # Check for large gaps (potential buffer issues)
            large_gaps = sum(1 for interval in frame_intervals if interval > 0.2)
            if large_gaps > 0:
                print(f"Large Gaps (>200ms):{large_gaps:>10} ⚠️")
        
        # Frequency analysis hint
        print(f"\n{'AUDIO CONTENT':^60}")
        print(f"-" * 60)
        
        # Simple check for periodic content (possible noise)
        if len(all_audio) > sample_rate:
            # Check for clipping (values at the edge of int16 range)
            clipped_samples = np.sum(np.abs(all_audio) > 32000)
            clipping_percent = (clipped_samples / len(all_audio)) * 100 if len(all_audio) > 0 else 0
            
            if clipping_percent > 0.1:
                print(f"Clipped Samples:   {clipping_percent:.2f}% ⚠️ (reduce mic gain!)")
            else:
                print(f"Clipped Samples:   {clipping_percent:.2f}%")
        
        # Estimate if speech might be present
        if active_duration > 1.0:
            print(f"Status:            ✓ Speech-like activity detected")
        elif active_duration > 0.5:
            print(f"Status:            ⚠️ Minimal activity (might be noise)")
        else:
            print(f"Status:            ✗ No significant activity (check mic!)")
        
        print(f"{'='*60}\n")
    
    def save_audio(self, filename: str = None):
        """Save captured audio as WAV file for further analysis"""
        if not self.audio_data:
            print("[ERROR] No audio data to save")
            return None
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"audio_capture_{timestamp}.wav"
        
        try:
            all_audio = np.concatenate(self.audio_data)
            sample_rate = ReSpeakerCapture.SAMPLE_RATE
            
            with wave.open(filename, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(all_audio.tobytes())
            
            print(f"[INFO] Audio saved to: {filename}")
            return filename
            
        except Exception as e:
            print(f"[ERROR] Failed to save audio: {e}")
            return None
    
    def run_diagnostics(self, save_file: bool = True):
        """Run full diagnostics sequence"""
        # Record audio
        if not self.record_audio():
            return False
        
        # Analyze
        self.analyze_audio()
        
        # Save
        if save_file:
            self.save_audio()
        
        return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Audio Diagnostics for ReSpeaker")
    parser.add_argument("--duration", type=int, default=10,
                        help="Recording duration in seconds (default: 10)")
    parser.add_argument("--device", default="ReSpeaker",
                        help="Audio device name to search for")
    parser.add_argument("--no-save", action="store_true",
                        help="Don't save audio to file")
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("REACHY HEARING APP - AUDIO DIAGNOSTICS")
    print("="*60)
    print(f"\nThis tool will record {args.duration} seconds of audio")
    print("and analyze it for potential issues.\n")
    print("Press Enter to start recording...")
    input()
    
    diagnostics = AudioDiagnostics(
        device_name=args.device,
        duration_seconds=args.duration
    )
    
    if diagnostics.run_diagnostics(save_file=not args.no_save):
        print("[INFO] Diagnostics complete!")
    else:
        print("[ERROR] Diagnostics failed")


if __name__ == "__main__":
    main()
