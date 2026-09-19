"""
Generate synthetic test audio file for audio analysis module testing.

Creates a 5-second WAV file with:
  - 1 sec silence
  - 2 sec 440Hz sine wave (speech-like tone)
  - 1 sec silence
  - 1 sec 880Hz sine wave

Sample rate: 16kHz, mono, 16-bit PCM
"""

import numpy as np
import soundfile as sf
from pathlib import Path

def generate_test_audio(output_path: str, sample_rate: int = 16000):
    """
    Generate synthetic test audio and save to WAV file.

    Parameters
    ----------
    output_path : str
        Path where WAV file will be saved
    sample_rate : int
        Sample rate in Hz (default 16000 Hz = 16kHz)
    """
    # Create output directory if needed
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Time parameters
    duration_silence_1 = 1.0  # seconds
    duration_tone_440 = 2.0
    duration_silence_2 = 1.0
    duration_tone_880 = 1.0

    # Generate silence (zeros)
    silence_1 = np.zeros(int(duration_silence_1 * sample_rate), dtype=np.float32)
    silence_2 = np.zeros(int(duration_silence_2 * sample_rate), dtype=np.float32)

    # Generate 440 Hz sine wave (A4 note)
    t_440 = np.linspace(0, duration_tone_440, int(duration_tone_440 * sample_rate), endpoint=False)
    frequency_440 = 440.0
    amplitude_440 = 0.3  # 30% amplitude to avoid clipping
    tone_440 = amplitude_440 * np.sin(2 * np.pi * frequency_440 * t_440).astype(np.float32)

    # Generate 880 Hz sine wave (A5 note)
    t_880 = np.linspace(0, duration_tone_880, int(duration_tone_880 * sample_rate), endpoint=False)
    frequency_880 = 880.0
    amplitude_880 = 0.3
    tone_880 = amplitude_880 * np.sin(2 * np.pi * frequency_880 * t_880).astype(np.float32)

    # Concatenate: silence -> tone440 -> silence -> tone880
    audio = np.concatenate([silence_1, tone_440, silence_2, tone_880])

    # Save to WAV file
    sf.write(output_path, audio, sample_rate, subtype='PCM_16')

    print("[OK] Generated test audio: {}".format(output_path))
    print("     Duration: {:.1f} seconds".format(len(audio) / sample_rate))
    print("     Sample rate: {} Hz".format(sample_rate))
    print("     Content: 1s silence, 2s 440Hz tone, 1s silence, 1s 880Hz tone")

if __name__ == "__main__":
    output_path = "sample_evidence/FIR/2026/0001/audio/test.wav"
    generate_test_audio(output_path)
