"""
Generate a synthetic test WAV file that simulates a forest soundscape.
This creates a 60-second WAV with bird-frequency chirps + ambient noise.
Then POSTs it to the backend for end-to-end pipeline testing.
"""
import numpy as np
import soundfile as sf
import os
import json
import sys

def generate_forest_audio(out_path: str, duration_sec=60, sr=44100):
    """Create a synthetic forest-like soundscape with bird-frequency chirps."""
    t = np.linspace(0, duration_sec, sr * duration_sec, endpoint=False)
    
    # Base ambient noise (low-level forest hum)
    ambient = np.random.normal(0, 0.02, len(t))
    
    # Add bird-like chirp bursts at various frequencies (2-8 kHz range)
    signal = ambient.copy()
    chirp_times = np.arange(5, duration_sec - 5, 3)  # chirp every ~3 seconds
    
    for ct in chirp_times:
        freq = np.random.uniform(2000, 8000)  # bird call frequency
        chirp_dur = np.random.uniform(0.3, 1.5)
        start_idx = int(ct * sr)
        end_idx = min(int((ct + chirp_dur) * sr), len(t))
        
        chirp_t = t[start_idx:end_idx] - ct
        # Frequency-modulated chirp with envelope
        envelope = np.sin(np.pi * chirp_t / chirp_dur) ** 2
        chirp = 0.15 * envelope * np.sin(2 * np.pi * freq * chirp_t + 
                                          50 * np.sin(2 * np.pi * 5 * chirp_t))
        signal[start_idx:end_idx] += chirp
    
    # Add some biophony harmonics (insect-like)
    signal += 0.01 * np.sin(2 * np.pi * 4500 * t)
    signal += 0.008 * np.sin(2 * np.pi * 6200 * t + np.random.uniform(0, 2*np.pi))
    
    # Normalize
    signal = signal / np.max(np.abs(signal)) * 0.8
    signal = np.clip(signal, -1.0, 1.0).astype(np.float32)
    
    sf.write(out_path, signal, sr)
    print(f"[OK] Generated {duration_sec}s test WAV: {out_path}")
    print(f"     Sample rate: {sr} Hz, samples: {len(signal)}")
    return out_path

if __name__ == "__main__":
    os.makedirs("test_audio", exist_ok=True)
    wav_path = "test_audio/synthetic_forest_60s.wav"
    generate_forest_audio(wav_path)
    
    # Also generate a short file (15s) to test quality gate rejection
    short_path = "test_audio/too_short_15s.wav"
    generate_forest_audio(short_path, duration_sec=15)
    
    print("\n[DONE] Test audio files ready. To test the backend:")
    print("  1. Start server:  uv run uvicorn backend.main:app --host 127.0.0.1 --port 8000")
    print("  2. Upload test:   uv run python test_audio/test_upload.py")
