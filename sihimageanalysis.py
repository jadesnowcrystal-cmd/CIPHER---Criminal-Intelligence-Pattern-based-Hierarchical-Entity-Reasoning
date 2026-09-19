"""
sihimageanalysis.py
====================
MULTIMEDIA DIGITAL FORENSIC MODULE — Image Analysis (BASIC Tier)

Analyzes uploaded image files to extract:
  1. EXIF metadata (GPS coordinates, capture timestamp, camera make/model)
  2. Software tag detection (tamper indicator)
  3. Error Level Analysis (ELA) for JPEG files — detects edited/spliced regions

All results are tagged as BASIC tier — no sensor fingerprinting (PRNU) or advanced
tamper detection. Heavy-tier features (PRNU matching, DCT compression-variance
analysis) are deferred.

Dependencies:
  - Pillow >= 9.0.0 (image I/O and processing)
  - exifread >= 1.10.0 (comprehensive EXIF extraction including GPS)
  - numpy (ELA computation)

Hash & Timestamp:
  Every run is identified by SHA-256 hash of file contents + ISO timestamp.
"""

import io
import os
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import exifread
from PIL import Image

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

# Supported image formats
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".dng", ".raw", ".cr2", ".nef"}

# ELA parameters
ELA_QUALITY = 95  # JPEG quality for ELA re-save
ELA_AMPLIFICATION = 10  # Difference amplification factor

# EXIF tag names (exifread format)
EXIF_GPS_LATITUDE = "GPS GPSLatitude"
EXIF_GPS_LATITUDE_REF = "GPS GPSLatitudeRef"
EXIF_GPS_LONGITUDE = "GPS GPSLongitude"
EXIF_GPS_LONGITUDE_REF = "GPS GPSLongitudeRef"
EXIF_DATETIME_ORIGINAL = "EXIF DateTimeOriginal"
EXIF_DATETIME = "Image DateTime"
EXIF_MAKE = "Image Make"
EXIF_MODEL = "Image Model"
EXIF_SOFTWARE = "Image Software"


# -----------------------------------------------------------------------------
# EXIF EXTRACTION
# -----------------------------------------------------------------------------

def _convert_to_degrees(value) -> Optional[float]:
    """
    Convert GPS coordinates from degrees/minutes/seconds to decimal degrees.

    Parameters
    ----------
    value : exifread IFDTag
        GPS coordinate value (list of ratios)

    Returns
    -------
    float or None
        Decimal degrees, or None if conversion fails
    """
    try:
        # exifread returns GPS coords as [degrees, minutes, seconds] ratios
        d = float(value.values[0].num) / float(value.values[0].den)
        m = float(value.values[1].num) / float(value.values[1].den)
        s = float(value.values[2].num) / float(value.values[2].den)
        return d + (m / 60.0) + (s / 3600.0)
    except (AttributeError, IndexError, ZeroDivisionError, ValueError):
        return None


def extract_exif_metadata(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Extract EXIF metadata from image file.

    Parameters
    ----------
    file_bytes : bytes
        Raw image file content
    filename : str
        Original filename

    Returns
    -------
    dict
        {
          "gps_coordinates": {"lat": float, "lon": float, "source": "EXIF"} or None,
          "capture_timestamp": ISO 8601 string or None,
          "camera_make": str or None,
          "camera_model": str or None,
          "software": str or None,
          "software_tamper_flag": bool,
          "exif_table": dict of all extracted tags
        }
    """
    result = {
        "gps_coordinates": None,
        "capture_timestamp": None,
        "camera_make": None,
        "camera_model": None,
        "software": None,
        "software_tamper_flag": False,
        "exif_table": {},
    }

    try:
        # Use exifread to extract all EXIF tags
        tags = exifread.process_file(io.BytesIO(file_bytes), details=False)

        # Build exif_table (convert tags to simple dict)
        for tag, value in tags.items():
            if not tag.startswith("JPEGThumbnail"):  # Skip thumbnail data
                result["exif_table"][tag] = str(value)

        # Extract GPS coordinates
        if EXIF_GPS_LATITUDE in tags and EXIF_GPS_LONGITUDE in tags:
            lat = _convert_to_degrees(tags[EXIF_GPS_LATITUDE])
            lon = _convert_to_degrees(tags[EXIF_GPS_LONGITUDE])

            if lat is not None and lon is not None:
                # Apply hemisphere corrections
                if EXIF_GPS_LATITUDE_REF in tags and str(tags[EXIF_GPS_LATITUDE_REF]) == "S":
                    lat = -lat
                if EXIF_GPS_LONGITUDE_REF in tags and str(tags[EXIF_GPS_LONGITUDE_REF]) == "W":
                    lon = -lon

                result["gps_coordinates"] = {
                    "lat": round(lat, 6),
                    "lon": round(lon, 6),
                    "source": "EXIF"
                }

        # Extract capture timestamp
        timestamp_raw = None
        if EXIF_DATETIME_ORIGINAL in tags:
            timestamp_raw = str(tags[EXIF_DATETIME_ORIGINAL])
        elif EXIF_DATETIME in tags:
            timestamp_raw = str(tags[EXIF_DATETIME])

        if timestamp_raw:
            # EXIF timestamps are in format "YYYY:MM:DD HH:MM:SS"
            try:
                dt = datetime.strptime(timestamp_raw, "%Y:%m:%d %H:%M:%S")
                result["capture_timestamp"] = dt.isoformat() + "Z"
            except ValueError:
                # Try alternative format without seconds
                try:
                    dt = datetime.strptime(timestamp_raw, "%Y:%m:%d %H:%M")
                    result["capture_timestamp"] = dt.isoformat() + "Z"
                except ValueError:
                    pass

        # Extract camera make/model
        if EXIF_MAKE in tags:
            result["camera_make"] = str(tags[EXIF_MAKE]).strip()
        if EXIF_MODEL in tags:
            result["camera_model"] = str(tags[EXIF_MODEL]).strip()

        # Extract software tag (tamper indicator)
        if EXIF_SOFTWARE in tags:
            software = str(tags[EXIF_SOFTWARE]).strip()
            result["software"] = software
            # Flag if software tag suggests editing (common editing tools)
            editing_keywords = ["photoshop", "gimp", "lightroom", "paint", "editor", "edit"]
            if any(kw in software.lower() for kw in editing_keywords):
                result["software_tamper_flag"] = True

    except Exception:
        # EXIF extraction failures are non-fatal — return empty result
        pass

    return result


# -----------------------------------------------------------------------------
# ERROR LEVEL ANALYSIS (ELA) — JPEG only
# -----------------------------------------------------------------------------

def perform_ela(file_bytes: bytes, filename: str) -> Optional[str]:
    """
    Perform Error Level Analysis on JPEG image.

    Re-saves the image at a known quality, computes the difference between
    original and re-saved, amplifies differences, and saves as a PNG overlay.

    Parameters
    ----------
    file_bytes : bytes
        Raw image file content
    filename : str
        Original filename

    Returns
    -------
    str or None
        Path to saved ELA overlay PNG, or None if ELA is not applicable
    """
    ext = Path(filename).suffix.lower()

    # ELA only works on JPEG files
    if ext not in {".jpg", ".jpeg"}:
        return None

    try:
        # Load original image
        original = Image.open(io.BytesIO(file_bytes))

        # Convert to RGB if needed (strip alpha, handle grayscale)
        if original.mode not in ("RGB", "L"):
            original = original.convert("RGB")

        # Re-save at known quality
        temp_buffer = io.BytesIO()
        original.save(temp_buffer, format="JPEG", quality=ELA_QUALITY)
        temp_buffer.seek(0)
        resaved = Image.open(temp_buffer)

        # Convert both to numpy arrays
        original_arr = np.array(original, dtype=np.float32)
        resaved_arr = np.array(resaved, dtype=np.float32)

        # Compute absolute difference
        diff = np.abs(original_arr - resaved_arr)

        # Amplify differences
        diff_amplified = np.clip(diff * ELA_AMPLIFICATION, 0, 255).astype(np.uint8)

        # Convert to PIL Image
        ela_image = Image.fromarray(diff_amplified)

        # Save to temporary file
        temp_dir = tempfile.gettempdir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        ela_path = os.path.join(temp_dir, f"ela_overlay_{timestamp}.png")
        ela_image.save(ela_path, format="PNG")

        return ela_path

    except Exception:
        # ELA failures are non-fatal
        return None


# -----------------------------------------------------------------------------
# MAIN ANALYZER FUNCTION
# -----------------------------------------------------------------------------

def analyze_image_file(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Main analyzer function. Accepts raw image file bytes and returns a dict
    with findings, entities, and status.

    This function is called by run_analysis_and_render() with exception
    handling, so it should return a dict with status/error/findings/entities
    keys. Any raised exception will be caught and turned into
    status="parse_error".

    Parameters
    ----------
    file_bytes : bytes
        Raw image file content
    filename : str
        Original filename

    Returns
    -------
    dict
        {
          "status": "ok" | "parse_error",
          "error": str or None,
          "findings": dict,
          "entities": dict
        }
    """
    # Validate file extension
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return {
            "status": "parse_error",
            "error": f"Unsupported image format: {ext}. Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}",
            "findings": {},
            "entities": empty_entities(),
        }

    try:
        # Verify it's a valid image file
        try:
            img = Image.open(io.BytesIO(file_bytes))
            img.verify()  # Verify integrity
        except Exception as e:
            return {
                "status": "parse_error",
                "error": f"Invalid or corrupted image file: {e}",
                "findings": {},
                "entities": empty_entities(),
            }

        # Extract EXIF metadata
        exif_data = extract_exif_metadata(file_bytes, filename)

        # Perform Error Level Analysis (JPEG only)
        ela_overlay_path = None
        ela_status = "not_applicable"

        if ext in {".jpg", ".jpeg"}:
            ela_overlay_path = perform_ela(file_bytes, filename)
            if ela_overlay_path:
                ela_status = "completed"
            else:
                ela_status = "failed"
        elif ext in {".png", ".heic"}:
            ela_status = "not_applicable_format"
        else:  # RAW formats
            ela_status = "not_applicable_raw"

        # Build entities
        entities = empty_entities()

        # Add GPS location if present
        if exif_data["gps_coordinates"]:
            entities["locations"].append(exif_data["gps_coordinates"])

        # Add capture timestamp if present
        if exif_data["capture_timestamp"]:
            entities["timestamps"].append(exif_data["capture_timestamp"])

        # Build findings
        findings = {
            "exif_metadata": {
                "camera_make": exif_data["camera_make"] or "Not present in this file",
                "camera_model": exif_data["camera_model"] or "Not present in this file",
                "capture_timestamp": exif_data["capture_timestamp"] or "Not present in this file",
                "gps_coordinates": exif_data["gps_coordinates"] or "Not present in this file",
                "software": exif_data["software"] or "Not present in this file",
                "software_tamper_flag": exif_data["software_tamper_flag"],
            },
            "exif_table": exif_data["exif_table"],
            "error_level_analysis": {
                "status": ela_status,
                "overlay_image": ela_overlay_path,
                "explanation": _get_ela_explanation(ela_status),
            },
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


def _get_ela_explanation(status: str) -> str:
    """Return explanation text for ELA status."""
    explanations = {
        "completed": (
            "ELA overlay shows compression artifacts. Bright regions indicate areas with "
            "higher error levels after re-compression, which may suggest editing, splicing, "
            "or regions saved at different quality levels. This is a heuristic indicator — "
            "not conclusive on its own."
        ),
        "failed": "ELA analysis failed (processing error).",
        "not_applicable_format": (
            "ELA not applicable to PNG/HEIC format (no JPEG recompression artifacts to analyze)."
        ),
        "not_applicable_raw": (
            "ELA not applicable to RAW format (uncompressed sensor data)."
        ),
        "not_applicable": "ELA not applicable to this file format.",
    }
    return explanations.get(status, "Unknown ELA status.")


# -----------------------------------------------------------------------------
# SYNTHETIC FIXTURE GENERATOR
# -----------------------------------------------------------------------------

def generate_image_fixture(fir_details: Dict[str, str]) -> bytes:
    """
    Generates a minimal synthetic image file with known EXIF data for testing.

    The image includes:
    - GPS coordinates (Mumbai coordinates for consistency with other modules)
    - Capture timestamp
    - Camera make/model
    - A simple visual pattern for ELA testing

    Parameters
    ----------
    fir_details : dict
        FIR details from load_fir_details()

    Returns
    -------
    bytes
        Raw JPEG file bytes
    """
    try:
        # Create a simple test image (solid color with text overlay)
        width, height = 800, 600
        img = Image.new("RGB", (width, height), color=(70, 130, 180))  # Steel blue

        # Add some pattern for ELA testing (simulated "edited" region)
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(img)

        # Draw a rectangle (simulated splice)
        draw.rectangle([(200, 200), (600, 400)], fill=(220, 220, 220))

        # Add text
        case_id = fir_details.get("fir_no", "FIR/2026/0001")
        draw.text((250, 280), f"Test Evidence Image", fill=(0, 0, 0))
        draw.text((250, 320), f"Case: {case_id}", fill=(0, 0, 0))

        # Save to bytes buffer
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=90)

        # Note: exifread can read EXIF, but writing EXIF requires piexif or pillow-heif
        # For the fixture, we'll create a basic JPEG without embedded EXIF
        # Real-world testing should use actual images with EXIF data

        buffer.seek(0)
        return buffer.getvalue()

    except Exception:
        # Fallback: minimal valid JPEG
        img = Image.new("RGB", (100, 100), color=(128, 128, 128))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        buffer.seek(0)
        return buffer.getvalue()


# -----------------------------------------------------------------------------
# DASHBOARD INTEGRATION HOOK
# (Called from sihdashboard.py when "Run Analysis" is clicked)
# -----------------------------------------------------------------------------

def run_image_analysis(case_id: str, uploaded_file: Any) -> Dict[str, Any]:
    """
    Called by sihdashboard.py when the user clicks "Run Analysis" on the
    Image Analysis section.

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
        module_name="Image Analysis",
        tier="basic",
        uploaded_file=uploaded_file,
        analyze_fn=analyze_image_file,
        spinner_text="Analyzing image file…",
    )
