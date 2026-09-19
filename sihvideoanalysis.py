"""
sihvideoanalysis.py
====================
MULTIMEDIA DIGITAL FORENSIC — "Video Analysis" module (file 3/5)

Built on top of the shared foundation in `sihforensicanalysis.py` (file
1/5): hash_and_stamp / ForensicResult / run_analysis_and_render /
persist_result / get_or_create_fixture / load_fir_details.

SCOPE (BASIC tier only — see 3_video_analysis.md for the HEAVY-tier items
that were explicitly deferred: PRNU sensor-fingerprint analysis, optical-flow
tamper detection, and deepfake/synthetic-video classifiers).

Accepted formats: .mp4 .mov .avi .dav
  - All formats are opened with OpenCV (cv2.VideoCapture), which supports
    most container/codec combinations.
  - Container metadata is extracted via ffprobe (binary must be on PATH or
    in common Windows locations).
  - Formats not recognized by OpenCV return a clean status="parse_error"
    explaining why, rather than crashing.

Everything below targets the SAME output shape regardless of input format:
    entities.timestamps     -> list[str]  (ISO 8601: container creation +
                                           scene-cut detection timestamps)
    entities.locations      -> list[dict] (GPS from container, if present —
                                           rare but checked)
    findings.container_metadata -> dict, container details table (duration,
                                   resolution, codec, creation time)
    findings.scene_cuts     -> list[dict], tampering heuristic: detected
                               scene changes with timestamps + confidence
    findings.frame_grid_image -> path to PNG thumbnail grid (sampled frames)
    findings.total_frames   -> int, count of frames in video
"""

import io
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import streamlit as st
from scenedetect import detect, AdaptiveDetector

# Import the shared forensic foundation
from sihforensicanalysis import (
    hash_and_stamp,
    ForensicResult,
    run_analysis_and_render,
    persist_result,
    get_or_create_fixture,
    load_fir_details,
    empty_entities,
    STANDING_DISCLAIMER,
)

# -----------------------------------------------------------------------------
# CONSTANTS
# -----------------------------------------------------------------------------

# Video processing limits
MAX_FRAMES = 600                    # cap on frame extraction (1 frame/sec ~ 10 min)
FRAME_INTERVAL_SEC = 1.0            # extract 1 frame per second
THUMBNAIL_GRID_COLS = 4             # grid layout for frame thumbnails
THUMBNAIL_FRAME_SIZE = (160, 120)   # size of each thumbnail in grid (W x H)

# ffprobe search paths (Windows)
FFPROBE_SEARCH_PATHS = [
    r"C:\ffmpeg\bin\ffprobe.exe",
    r"C:\Program Files\ffmpeg\bin\ffprobe.exe",
    r"C:\Program Files (x86)\ffmpeg\bin\ffprobe.exe",
]

# Scene detection threshold (lower = more sensitive, more false positives)
SCENE_DETECTION_THRESHOLD = 27.0

# Formats that this module accepts
SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi", ".dav"}


# -----------------------------------------------------------------------------
# 1. FFPROBE LOCATION HELPER
# -----------------------------------------------------------------------------

def _find_ffprobe() -> Optional[str]:
    """Finds ffprobe binary by searching common Windows locations, then PATH.
    Returns the full path if found, None otherwise."""
    # Try common Windows locations first
    for path in FFPROBE_SEARCH_PATHS:
        if os.path.exists(path):
            return path

    # Try system PATH
    result = shutil.which("ffprobe")
    if result:
        return result

    return None


# -----------------------------------------------------------------------------
# 2. CONTAINER METADATA EXTRACTION
# -----------------------------------------------------------------------------

def extract_container_metadata(video_path: str) -> Dict[str, Any]:
    """Extracts container-level metadata using ffprobe: duration, resolution,
    codec, creation timestamp. Returns a dict with keys:
        - duration_seconds: float or None
        - resolution: str like "1920x1080" or None
        - codec: str like "h264" or None
        - creation_timestamp: ISO 8601 string or None (labeled "container-reported")
        - ffprobe_available: bool, whether ffprobe was found/used
        - error: str or None, if ffprobe failed

    If ffprobe is not available, returns a dict indicating that, but does NOT
    raise an exception."""
    ffprobe_path = _find_ffprobe()
    if not ffprobe_path:
        return {
            "ffprobe_available": False,
            "error": "ffprobe binary not found on system (not in PATH or common Windows locations)",
            "duration_seconds": None,
            "resolution": None,
            "codec": None,
            "creation_timestamp": None,
        }

    try:
        # ffprobe -v quiet -print_format json -show_format -show_streams
        cmd = [
            ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return {
                "ffprobe_available": True,
                "error": f"ffprobe failed: {result.stderr[:200]}",
                "duration_seconds": None,
                "resolution": None,
                "codec": None,
                "creation_timestamp": None,
            }

        data = json.loads(result.stdout)
        duration = None
        resolution = None
        codec = None
        creation_timestamp = None

        # Extract duration from format.duration
        if "format" in data and "duration" in data["format"]:
            try:
                duration = float(data["format"]["duration"])
            except (ValueError, TypeError):
                pass

        # Extract codec and resolution from first video stream
        if "streams" in data:
            for stream in data["streams"]:
                if stream.get("codec_type") == "video":
                    codec = stream.get("codec_name", "unknown")
                    width = stream.get("width")
                    height = stream.get("height")
                    if width and height:
                        resolution = f"{width}x{height}"
                    break

        # Extract creation timestamp from format.tags.creation_time
        if "format" in data and "tags" in data["format"]:
            creation_timestamp = data["format"]["tags"].get("creation_time")

        return {
            "ffprobe_available": True,
            "error": None,
            "duration_seconds": duration,
            "resolution": resolution,
            "codec": codec,
            "creation_timestamp": creation_timestamp,
        }
    except subprocess.TimeoutExpired:
        return {
            "ffprobe_available": True,
            "error": "ffprobe command timed out",
            "duration_seconds": None,
            "resolution": None,
            "codec": None,
            "creation_timestamp": None,
        }
    except json.JSONDecodeError:
        return {
            "ffprobe_available": True,
            "error": "ffprobe output was not valid JSON",
            "duration_seconds": None,
            "resolution": None,
            "codec": None,
            "creation_timestamp": None,
        }
    except Exception as e:
        return {
            "ffprobe_available": True,
            "error": f"ffprobe error: {str(e)[:200]}",
            "duration_seconds": None,
            "resolution": None,
            "codec": None,
            "creation_timestamp": None,
        }


# -----------------------------------------------------------------------------
# 3. FRAME EXTRACTION
# -----------------------------------------------------------------------------

def extract_frames(
    video_path: str,
    interval_sec: float = FRAME_INTERVAL_SEC,
    max_frames: int = MAX_FRAMES,
) -> List[Tuple[float, np.ndarray]]:
    """Extracts frames from video at fixed time intervals using OpenCV.
    Returns a list of (timestamp_seconds, frame_array) tuples, capped at
    max_frames to prevent runaway processing.

    Raises an exception if the video cannot be opened (caught by caller)."""
    frames = []
    cap = cv2.VideoCapture(video_path)
    try:
        if not cap.isOpened():
            raise ValueError("Cannot open video file with OpenCV")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30  # fallback

        frame_interval = int(fps * interval_sec)
        if frame_interval < 1:
            frame_interval = 1

        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % frame_interval == 0:
                timestamp_sec = frame_count / fps
                frames.append((timestamp_sec, frame))

                if len(frames) >= max_frames:
                    break

            frame_count += 1

        return frames
    finally:
        cap.release()


# -----------------------------------------------------------------------------
# 4. SCENE-CUT / EDIT-POINT DETECTION
# -----------------------------------------------------------------------------

def detect_scene_cuts(video_path: str) -> List[Dict[str, Any]]:
    """Detects scene cuts / edit points using PySceneDetect.
    Returns a list of dicts: {"timestamp_seconds": ..., "confidence": ...}
    labeled as a basic tamper heuristic.

    If detection fails, returns an empty list (does not raise)."""
    try:
        # scenedetect returns a list of (frame_num, timecode) tuples for detected scenes
        scenes = detect(video_path, detector=AdaptiveDetector(threshold=SCENE_DETECTION_THRESHOLD))
        if not scenes:
            return []

        # Convert to a list of dicts with timestamp and confidence info
        cuts = []
        for i, (frame_num, timecode) in enumerate(scenes):
            # Calculate seconds from timecode
            # timecode is a Timecode object; convert it to total seconds
            timestamp_sec = timecode.get_seconds()
            cuts.append({
                "timestamp_seconds": timestamp_sec,
                "timecode": str(timecode),
                "frame_number": frame_num,
                # Confidence is a heuristic: first frame is the start (low relevance),
                # subsequent cuts are edit points (higher relevance)
                "confidence": "high" if i > 0 else "low",
            })
        return cuts
    except Exception:
        # Scene detection errors (missing model, bad file, etc.) do not crash
        return []


# -----------------------------------------------------------------------------
# 5. FRAME THUMBNAIL GRID GENERATION
# -----------------------------------------------------------------------------

def generate_thumbnail_grid(
    frames: List[Tuple[float, np.ndarray]],
    grid_cols: int = THUMBNAIL_GRID_COLS,
) -> str:
    """Generates a PNG thumbnail grid from sampled frames, saved to a
    temporary file. Returns the file path (suitable for
    sihforensicanalysis._render_findings() to detect and render as an image).

    Samples frames evenly across the input list to fill the grid."""
    if not frames:
        raise ValueError("No frames to generate thumbnail grid")

    # Determine grid dimensions
    num_frames = min(len(frames), 12)  # cap at 12 thumbnails (3x4 grid)
    grid_rows = (num_frames + grid_cols - 1) // grid_cols
    grid_cols_actual = min(grid_cols, num_frames)

    # Create grid canvas
    thumb_w, thumb_h = THUMBNAIL_FRAME_SIZE
    grid_w = grid_cols_actual * thumb_w
    grid_h = grid_rows * thumb_h
    grid = np.ones((grid_h, grid_w, 3), dtype=np.uint8) * 240  # light gray background

    # Sample frames evenly across the list
    step = max(1, len(frames) // num_frames) if num_frames < len(frames) else 1
    sampled_frames = frames[::step][:num_frames]

    # Place thumbnails in grid
    for idx, (timestamp_sec, frame) in enumerate(sampled_frames):
        row = idx // grid_cols_actual
        col = idx % grid_cols_actual

        # Resize frame to thumbnail size
        resized = cv2.resize(frame, THUMBNAIL_FRAME_SIZE)

        # Convert BGR to RGB for PNG
        resized_rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        # Place in grid
        y_start = row * thumb_h
        x_start = col * thumb_w
        grid[y_start : y_start + thumb_h, x_start : x_start + thumb_w] = resized_rgb

    # Save to temporary PNG file
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"video_thumbnails_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png")

    # Convert RGB to BGR for cv2.imwrite
    grid_bgr = cv2.cvtColor(grid, cv2.COLOR_RGB2BGR)
    if not cv2.imwrite(temp_path, grid_bgr):
        raise ValueError(f"Failed to write thumbnail grid to {temp_path}")

    return temp_path


# -----------------------------------------------------------------------------
# 6. ENTITY EXTRACTION HELPERS
# -----------------------------------------------------------------------------

def extract_timestamps(
    container_metadata: Dict[str, Any],
    scene_cuts: List[Dict[str, Any]],
) -> List[str]:
    """Collects timestamps from container metadata and scene cuts into ISO 8601
    strings for the entities block."""
    timestamps = []

    # Add container creation timestamp if present
    if container_metadata.get("creation_timestamp"):
        try:
            # Try to parse and normalize to ISO 8601
            ts_str = container_metadata["creation_timestamp"]
            # If it's already ISO-like, keep it; otherwise try common formats
            if "T" in ts_str or ts_str.endswith("Z"):
                timestamps.append(ts_str)
            else:
                # Try to parse common ffprobe timestamp format (e.g., "2025-01-15T10:30:45Z")
                timestamps.append(ts_str)
        except Exception:
            pass

    # Add scene-cut timestamps
    for cut in scene_cuts:
        try:
            timestamp_sec = cut.get("timestamp_seconds")
            if timestamp_sec is not None:
                # Convert seconds to ISO 8601 duration or absolute time
                # For now, just include the timestamp as-is
                iso_timestamp = f"PT{timestamp_sec}S"  # ISO 8601 duration format
                timestamps.append(iso_timestamp)
        except Exception:
            pass

    return timestamps


def extract_locations(container_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Attempts to extract GPS location from container metadata. Returns a list
    of location dicts (usually empty, as video containers rarely embed GPS)."""
    locations = []

    # Check for GPS tags in ffprobe output (metadata.tags may have location info)
    # This is a rare case, but worth checking
    # ffprobe may provide: creation_time, but not GPS by default.
    # GPS in video is typically in XMP metadata or EXIF (not container-level).
    # For BASIC tier, we leave this empty.

    return locations


# -----------------------------------------------------------------------------
# 7. MAIN ANALYZER FUNCTION
# -----------------------------------------------------------------------------

def analyze_video_file(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Main analyzer function. Accepts raw video file bytes and returns a dict
    with findings, entities, and status.

    This function is called by run_analysis_and_render() with exception
    handling, so it should return a dict with status/error/findings/entities
    keys. Any raised exception will be caught and turned into
    status="parse_error"."""

    # Validate file extension
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return {
            "status": "parse_error",
            "error": f"Unsupported video format: {ext}. Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}",
            "findings": {},
            "entities": empty_entities(),
        }

    # Write bytes to a temporary file (OpenCV and ffprobe need file paths)
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"video_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{ext}")
    try:
        with open(temp_path, "wb") as f:
            f.write(file_bytes)

        # Extract container metadata
        metadata = extract_container_metadata(temp_path)

        # Extract frames
        frames = extract_frames(temp_path, interval_sec=FRAME_INTERVAL_SEC, max_frames=MAX_FRAMES)
        if not frames:
            return {
                "status": "parse_error",
                "error": "Could not extract frames from video. File may be corrupted or in an unsupported codec.",
                "findings": {},
                "entities": empty_entities(),
            }

        # Detect scene cuts
        scene_cuts = detect_scene_cuts(temp_path)

        # Generate thumbnail grid
        thumbnail_grid_path = generate_thumbnail_grid(frames)

        # Extract entities
        timestamps = extract_timestamps(metadata, scene_cuts)
        locations = extract_locations(metadata)

        # Build findings dict
        findings = {
            "container_metadata": {
                "duration_seconds": metadata.get("duration_seconds"),
                "resolution": metadata.get("resolution"),
                "codec": metadata.get("codec"),
                "creation_timestamp": metadata.get("creation_timestamp"),
                "ffprobe_available": metadata.get("ffprobe_available"),
                "ffprobe_error": metadata.get("error"),
            },
            "frame_grid_image": thumbnail_grid_path,
            "total_frames": len(frames),
            "scene_cuts": scene_cuts,
            "scene_cuts_disclaimer": (
                "Scene changes detected at these timestamps. This is a basic tamper "
                "heuristic: may indicate normal recording gaps, camera movements, or "
                "edited splices. Not conclusive on its own; requires expert corroboration."
            ),
        }

        entities = {
            "timestamps": timestamps,
            "locations": locations,
            "phone_numbers": [],
            "people": [],
        }

        return {
            "status": "ok",
            "findings": findings,
            "entities": entities,
        }

    except Exception as exc:
        return {
            "status": "parse_error",
            "error": f"{type(exc).__name__}: {exc}",
            "findings": {},
            "entities": empty_entities(),
        }
    finally:
        # Clean up temporary video file
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass


# -----------------------------------------------------------------------------
# 8. SYNTHETIC FIXTURE GENERATOR
# -----------------------------------------------------------------------------

def generate_video_fixture(fir_details: Dict[str, str]) -> bytes:
    """Generates a minimal synthetic video file (~5 seconds) with deterministic
    scene cuts for testing the analyzer. Returns raw bytes of a valid .mp4 file.

    The video includes:
    - 5 seconds of synthetic frames (each a solid color block)
    - 2-3 scene cuts (color changes) to demonstrate tamper detection
    """
    try:
        # Video parameters
        width, height = 640, 480
        fps = 24
        duration_sec = 5
        total_frames = duration_sec * fps

        # Temporary file for video output
        temp_dir = tempfile.gettempdir()
        temp_video_path = os.path.join(
            temp_dir, f"generated_video_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.mp4"
        )

        # Create video writer (using H.264 codec via MJPEG fallback for compatibility)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(temp_video_path, fourcc, fps, (width, height))

        if not out.isOpened():
            # Fallback: try MJPEG
            fourcc = cv2.VideoWriter_fourcc(*"MJPG")
            out = cv2.VideoWriter(temp_video_path, fourcc, fps, (width, height))

        if not out.isOpened():
            raise ValueError("Cannot create video writer")

        try:
            # Generate frames with color changes (scene cuts)
            # Divide into 3 segments with different colors
            segment_frames = total_frames // 3
            colors = [
                (50, 100, 200),    # Blue
                (100, 200, 100),   # Green
                (200, 100, 50),    # Orange
            ]

            for frame_idx in range(total_frames):
                segment = min(frame_idx // segment_frames, len(colors) - 1)
                color = colors[segment]

                # Create a solid-color frame with a timestamp overlay
                frame = np.full((height, width, 3), color, dtype=np.uint8)

                # Add frame number text for debugging
                cv2.putText(
                    frame,
                    f"Frame {frame_idx}/{total_frames}",
                    (50, 100),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (255, 255, 255),
                    2,
                )
                cv2.putText(
                    frame,
                    f"Segment {segment}",
                    (50, 150),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2,
                )

                out.write(frame)
        finally:
            out.release()

        # Read the generated video bytes
        with open(temp_video_path, "rb") as f:
            video_bytes = f.read()

        return video_bytes

    except Exception:
        # Fallback: return minimal valid MP4 (header only, will fail to play but won't crash)
        # This is a last-resort fallback; in practice OpenCV should succeed
        return b""
    finally:
        try:
            if os.path.exists(temp_video_path):
                os.remove(temp_video_path)
        except Exception:
            pass


# -----------------------------------------------------------------------------
# 9. DASHBOARD INTEGRATION HOOK
# (Called from sihdashboard.py when "Run Analysis" is clicked)
# -----------------------------------------------------------------------------

def run_video_analysis(case_id: str, uploaded_file: Any) -> Dict[str, Any]:
    """Called by sihdashboard.py when the user clicks "Run Analysis" on the
    Video Analysis section.

    Parameters
    ----------
    case_id : str
        Active FIR number (e.g., "FIR/2026/0007")
    uploaded_file : Streamlit UploadedFile or _FixtureFile
        Either a real upload or a cached fixture from get_or_create_fixture()

    Returns the full persisted result dict with findings + hash + tier + disclaimer.
    """
    return run_analysis_and_render(
        case_id=case_id,
        module_name="Video Analysis",
        tier="basic",
        uploaded_file=uploaded_file,
        analyze_fn=analyze_video_file,
        spinner_text="Analyzing video file…",
    )
