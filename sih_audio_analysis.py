"""
sih_audio_analysis.py
====================
MULTIMEDIA DIGITAL FORENSIC MODULE — Audio Analysis (BASIC Tier)

Analyzes uploaded audio files (voice recordings, ambient audio, etc.) to extract:
  1. File metadata (duration, sample rate, channel count)
  2. Speech vs. silence segmentation (energy-threshold based)
  3. Spectrogram visualization (PNG, embedded as base64)
  4. MFCC feature summary (mean/variance per coefficient)

All results are tagged as BASIC tier — no speaker identity claims are made here.
Heavy-tier identity verification (speaker diarization, ENF matching) deferred.

Dependencies:
  - librosa >= 0.10.0 (audio analysis, MFCC, silence detection)
  - pydub (multi-format audio support via ffmpeg)
  - numpy (numerical operations)
  - matplotlib (spectrogram rendering)
  - soundfile (fallback audio I/O)

Hash & Timestamp:
  Every run is identified by SHA-256 hash of file contents + ISO timestamp.
"""

import os
import io
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional

import numpy as np
import librosa
import librosa.display
import matplotlib
matplotlib.use("Agg")  # Non-GUI backend for server/headless environments
import matplotlib.pyplot as plt
from pydub import AudioSegment


# =============================================================================
# HASH & TIMESTAMP (shared pattern from file 1/5 foundation)
# =============================================================================

def hash_and_stamp(file_bytes: bytes) -> Dict[str, str]:
    """
    Compute SHA-256 hash and ISO-8601 timestamp for uploaded file.

    Parameters
    ----------
    file_bytes : bytes
        Raw file content

    Returns
    -------
    dict
        {"sha256": "abc123...", "timestamp": "2026-09-17T09:30:00Z"}
    """
    sha256_hash = hashlib.sha256(file_bytes).hexdigest()
    iso_timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "sha256": sha256_hash,
        "timestamp": iso_timestamp,
    }


# =============================================================================
# AUDIO METADATA EXTRACTION
# =============================================================================

def _extract_metadata(audio_data: np.ndarray, sr: int) -> Dict[str, Any]:
    """
    Extract basic metadata from audio signal.

    Parameters
    ----------
    audio_data : np.ndarray
        Audio time series (mono or stereo)
    sr : int
        Sample rate in Hz

    Returns
    -------
    dict
        {
          "duration_seconds": float,
          "sample_rate": int,
          "channels": int,
          "samples": int
        }
    """
    # Handle mono vs stereo
    if audio_data.ndim == 1:
        channels = 1
    else:
        channels = audio_data.shape[0]

    duration = librosa.get_duration(y=audio_data, sr=sr)
    num_samples = audio_data.shape[1] if audio_data.ndim > 1 else len(audio_data)

    return {
        "duration_seconds": round(duration, 2),
        "sample_rate": sr,
        "channels": channels,
        "samples": int(num_samples),
    }


# =============================================================================
# SPEECH vs. SILENCE SEGMENTATION (Energy-threshold based)
# =============================================================================

def _detect_speech_segments(
    audio_data: np.ndarray, sr: int, threshold_db: float = -40.0
) -> List[Tuple[float, float]]:
    """
    Detect speech vs. silence segments using energy thresholds.

    librosa.effects.split() finds contiguous segments above an energy threshold,
    which is a reasonable heuristic for speech/sound activity detection.

    Parameters
    ----------
    audio_data : np.ndarray
        Audio time series (will be converted to mono if stereo)
    sr : int
        Sample rate in Hz
    threshold_db : float
        Energy threshold in dB (default -40 dB is reasonable for speech)

    Returns
    -------
    list of tuples
        [(start_seconds, end_seconds), ...] for each detected segment
    """
    # Convert stereo to mono if needed
    if audio_data.ndim > 1:
        audio_mono = librosa.to_mono(audio_data)
    else:
        audio_mono = audio_data

    # Use librosa.effects.split to find segments above threshold
    # S is the spectrogram power; top_db is the threshold in dB
    segments_frames = librosa.effects.split(
        audio_mono,
        top_db=-threshold_db,  # librosa uses top_db as a positive value
        frame_length=2048,
        hop_length=512,
    )

    # Convert frame indices to time (seconds)
    segments_seconds = librosa.frames_to_time(segments_frames, sr=sr)

    return [tuple(row) for row in segments_seconds]


# =============================================================================
# SPECTROGRAM GENERATION (PNG, embedded as base64)
# =============================================================================

def _generate_spectrogram(
    audio_data: np.ndarray, sr: int, width: int = 10, height: int = 4
) -> str:
    """
    Generate mel-scale spectrogram and return as base64 PNG data URI.

    Parameters
    ----------
    audio_data : np.ndarray
        Audio time series
    sr : int
        Sample rate in Hz
    width, height : int
        Figure size in inches (default 10x4)

    Returns
    -------
    str
        Base64-encoded PNG data URI: "data:image/png;base64,iVBO..."
    """
    # Convert stereo to mono if needed
    if audio_data.ndim > 1:
        audio_mono = librosa.to_mono(audio_data)
    else:
        audio_mono = audio_data

    # Compute mel-scale spectrogram
    S = librosa.feature.melspectrogram(y=audio_mono, sr=sr, n_mels=128)
    S_db = librosa.power_to_db(S, ref=np.max)

    # Create figure and render
    fig, ax = plt.subplots(figsize=(width, height))
    img = librosa.display.specshow(
        S_db,
        sr=sr,
        hop_length=512,
        x_axis="time",
        y_axis="mel",
        fmin=0,
        fmax=sr / 2,
        ax=ax,
        cmap="viridis",
    )
    ax.set_title("Mel-Scale Spectrogram")
    fig.colorbar(img, ax=ax, format="%+2.0f dB")

    # Save to bytes buffer as PNG
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=72, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)

    # Encode as base64 data URI
    import base64

    png_bytes = buf.getvalue()
    b64_str = base64.b64encode(png_bytes).decode("utf-8")
    return f"data:image/png;base64,{b64_str}"


# =============================================================================
# MFCC FEATURE EXTRACTION (mean/variance summary)
# =============================================================================

def _extract_mfcc_features(audio_data: np.ndarray, sr: int, n_mfcc: int = 13) -> Dict[str, Any]:
    """
    Extract MFCC features and compute mean/variance per coefficient.

    MFCCs (Mel-Frequency Cepstral Coefficients) are a compact representation of
    audio spectral content, useful as features for downstream analysis.
    We report only summary statistics (mean & variance per coefficient),
    not the full coefficient matrix.

    Parameters
    ----------
    audio_data : np.ndarray
        Audio time series
    sr : int
        Sample rate in Hz
    n_mfcc : int
        Number of MFCC coefficients (default 13)

    Returns
    -------
    dict
        {
          "n_coefficients": 13,
          "means": [c0_mean, c1_mean, ...],
          "variances": [c0_var, c1_var, ...],
          "note": "MFCC summary — not speaker identity claim"
        }
    """
    # Convert stereo to mono if needed
    if audio_data.ndim > 1:
        audio_mono = librosa.to_mono(audio_data)
    else:
        audio_mono = audio_data

    # Compute MFCCs
    mfccs = librosa.feature.mfcc(y=audio_mono, sr=sr, n_mfcc=n_mfcc)

    # Compute mean and variance per coefficient (across time)
    means = [float(np.mean(mfccs[i, :])) for i in range(n_mfcc)]
    variances = [float(np.var(mfccs[i, :])) for i in range(n_mfcc)]

    return {
        "n_coefficients": n_mfcc,
        "means": means,
        "variances": variances,
        "note": "Raw feature summary for investigative use — not speaker identity",
    }


# =============================================================================
# RESULT SCHEMA BUILDER
# =============================================================================

def _build_result_schema(
    case_id: str,
    filename: str,
    sha256_hash: str,
    timestamp: str,
    metadata: Dict[str, Any],
    segments: List[Tuple[float, float]],
    spectrogram_b64: str,
    mfcc_stats: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build the final analysis result in the shared forensic schema.

    Per file 4/5 requirements:
      - entities.timestamps: list of segment start times
      - findings: spectrogram image, segment details, MFCC summary
      - Tier badge: "basic"
      - Disclaimer: investigative use only, no identity claims

    Parameters
    ----------
    case_id : str
        FIR case identifier (e.g., "FIR/2026/0001")
    filename : str
        Original uploaded filename
    sha256_hash : str
        SHA-256 hash of file
    timestamp : str
        ISO timestamp of analysis
    metadata : dict
        Audio metadata (duration, sample rate, channels)
    segments : list of tuples
        [(start_sec, end_sec), ...] for detected speech segments
    spectrogram_b64 : str
        Base64-encoded PNG spectrogram data URI
    mfcc_stats : dict
        MFCC mean/variance summary

    Returns
    -------
    dict
        Complete analysis result ready for JSON persistence
    """
    # Extract segment start times for entities.timestamps
    segment_starts = [round(seg[0], 2) for seg in segments]
    segment_table = [
        {"start_seconds": round(seg[0], 2), "end_seconds": round(seg[1], 2)}
        for seg in segments
    ]

    result = {
        "Case_ID": case_id,
        "Analysis_Type": "Audio Analysis",
        "Tier": "basic",
        "Disclaimer": (
            "BASIC TIER — Investigative lead only. Speech segmentation is energy-threshold based; "
            "spectrogram is visual reference; MFCC features are acoustic summary statistics. "
            "This analysis makes NO speaker identity, voice match, or biometric claims. "
            "For speaker identification or forensic voice comparison, consult certified experts "
            "and refer to HEAVY-tier analysis (when approved)."
        ),
        "File": {
            "name": filename,
            "sha256_hash": sha256_hash,
            "analysis_timestamp_utc": timestamp,
        },
        "Metadata": metadata,
        "entities": {
            "timestamps": segment_starts,  # Start times of detected speech segments
        },
        "findings": {
            "speech_segments": {
                "count": len(segment_table),
                "total_speech_seconds": round(sum(seg["end_seconds"] - seg["start_seconds"] for seg in segment_table), 2),
                "segments": segment_table,
            },
            "spectrogram_image": spectrogram_b64,
            "mfcc_features": mfcc_stats,
        },
    }

    return result


# =============================================================================
# MAIN ANALYSIS FUNCTION (entry point from dashboard)
# =============================================================================

def analyze_audio_basic(uploaded_file: Any, case_id: str) -> Dict[str, Any]:
    """
    Main entry point for BASIC-tier audio analysis.

    Accepts .wav .mp3 .opus .m4a .aac .amr .flac (via pydub + ffmpeg).
    Returns complete analysis result in shared forensic schema.

    Parameters
    ----------
    uploaded_file : streamlit.UploadedFile or file-like object
        Must expose .name (str) and .getvalue() (bytes)
    case_id : str
        FIR case identifier

    Returns
    -------
    dict
        Analysis result with hash, metadata, segments, spectrogram, MFCC stats.
        On error, returns {"error": error_message}
    """
    try:
        # Read file bytes
        file_bytes = uploaded_file.getvalue()
        filename = uploaded_file.name

        # Compute hash and timestamp
        hash_info = hash_and_stamp(file_bytes)
        sha256_hash = hash_info["sha256"]
        timestamp = hash_info["timestamp"]

        # Load audio via pydub (handles multiple formats)
        # Convert to librosa-compatible format
        try:
            # Try to load as WAV first (native librosa support)
            if filename.lower().endswith(".wav"):
                import soundfile as sf
                y, sr = sf.read(io.BytesIO(file_bytes))
                if y.ndim == 2 and y.shape[1] == 1:
                    y = y[:, 0]
            else:
                # Use pydub for other formats, convert to WAV for librosa
                audio_segment = AudioSegment.from_file(io.BytesIO(file_bytes))
                # Export to WAV bytes, then load
                wav_buffer = io.BytesIO()
                audio_segment.export(wav_buffer, format="wav")
                wav_buffer.seek(0)

                import soundfile as sf
                y, sr = sf.read(wav_buffer)
                if y.ndim == 2 and y.shape[1] == 1:
                    y = y[:, 0]
        except Exception as e:
            return {"error": f"Audio file format error: {str(e)}"}

        # Extract metadata
        metadata = _extract_metadata(y, sr)

        # Detect speech segments
        segments = _detect_speech_segments(y, sr, threshold_db=-40.0)

        # Generate spectrogram
        spectrogram_b64 = _generate_spectrogram(y, sr)

        # Extract MFCC features
        mfcc_stats = _extract_mfcc_features(y, sr, n_mfcc=13)

        # Build result schema
        result = _build_result_schema(
            case_id=case_id,
            filename=filename,
            sha256_hash=sha256_hash,
            timestamp=timestamp,
            metadata=metadata,
            segments=segments,
            spectrogram_b64=spectrogram_b64,
            mfcc_stats=mfcc_stats,
        )

        return result

    except Exception as e:
        return {
            "error": f"Audio analysis failed: {str(e)}",
            "error_type": type(e).__name__,
        }


# =============================================================================
# UTILITY: Persist result to JSON file
# =============================================================================

def save_analysis_result(result: Dict[str, Any], case_id: str, output_dir: str = "case_analysis") -> str:
    """
    Save analysis result to JSON file in case_analysis/<Case_ID>/Audio_Analysis_results.json

    Parameters
    ----------
    result : dict
        Analysis result from analyze_audio_basic()
    case_id : str
        FIR case identifier
    output_dir : str
        Base output directory (default "case_analysis")

    Returns
    -------
    str
        Path to saved JSON file
    """
    case_dir = Path(output_dir) / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    output_path = case_dir / "Audio_Analysis_results.json"

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    return str(output_path)
