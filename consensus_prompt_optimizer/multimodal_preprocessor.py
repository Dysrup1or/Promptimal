"""
Multimodal Preprocessor Module for CATALYZE
============================================
Handles voice transcription and image analysis preprocessing
before the main 5-stage optimization pipeline.
"""

import os
import base64
import tempfile
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

from loguru import logger

from .config import (
    OPENAI_TRANSCRIBE,
    GEMINI_VISION,
    MULTIMODAL_PRICING,
    MULTIMODAL_CREDIT_COST,
)


def _detect_audio_suffix(audio_bytes: bytes) -> str:
    """Best-effort container sniffing for common audio formats."""
    if not audio_bytes:
        return ""

    # WAV: RIFF....WAVE
    if len(audio_bytes) >= 12 and audio_bytes[0:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
        return ".wav"

    # MP3: ID3 tag or frame sync
    if audio_bytes.startswith(b"ID3"):
        return ".mp3"
    if len(audio_bytes) >= 2 and audio_bytes[0] == 0xFF and (audio_bytes[1] & 0xE0) == 0xE0:
        return ".mp3"

    # OGG
    if audio_bytes.startswith(b"OggS"):
        return ".ogg"

    # FLAC
    if audio_bytes.startswith(b"fLaC"):
        return ".flac"

    # WEBM (EBML)
    if audio_bytes.startswith(b"\x1A\x45\xDF\xA3"):
        return ".webm"

    # MP4/M4A family (ftyp box)
    if len(audio_bytes) >= 12 and audio_bytes[4:8] == b"ftyp":
        # Most voice recordings in browsers are m4a/mp4 or similar
        return ".m4a"

    return ""


def _wav_data_chunk_size(audio_bytes: bytes) -> Optional[int]:
    """Return WAV 'data' chunk size if parseable, else None."""
    if len(audio_bytes) < 12:
        return None
    if not (audio_bytes[0:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE"):
        return None

    # Walk chunks: 12-byte RIFF header then repeated [4-byte id][4-byte size][data]
    offset = 12
    while offset + 8 <= len(audio_bytes):
        chunk_id = audio_bytes[offset : offset + 4]
        chunk_size = int.from_bytes(audio_bytes[offset + 4 : offset + 8], "little", signed=False)
        offset += 8

        if chunk_id == b"data":
            return chunk_size

        # Chunks are word-aligned
        offset += chunk_size
        if chunk_size % 2 == 1:
            offset += 1

    return None


def _is_effectively_empty_audio(audio_bytes: bytes) -> bool:
    """Heuristics: treat tiny recordings / WAV with 0 data as empty."""
    if not audio_bytes:
        return True
    if len(audio_bytes) < 512:
        return True

    data_size = _wav_data_chunk_size(audio_bytes)
    if data_size is not None and data_size == 0:
        return True

    return False


# =============================================================================
# VOICE TRANSCRIPTION (Task 2.1)
# =============================================================================

async def transcribe_voice(audio_bytes: bytes, filename: str = "audio.webm") -> Dict[str, Any]:
    """
    Transcribe voice input using OpenAI's gpt-4o-mini-transcribe model.
    
    Args:
        audio_bytes: Raw audio file bytes (supports webm, mp3, wav, m4a)
        filename: Original filename with extension for format detection
    
    Returns:
        Dict with keys:
            - text: Transcribed text
            - duration_seconds: Audio duration for billing
            - cost: Estimated cost in USD
            - success: Boolean indicating success
            - error: Error message if failed
    """
    try:
        from openai import OpenAI

        if _is_effectively_empty_audio(audio_bytes):
            return {
                "text": "",
                "duration_seconds": 0,
                "cost": 0,
                "success": False,
                "error": "No audio captured. Please re-record and try again.",
            }
        
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Create temp file for the audio.
        # Important: OpenAI may rely on filename extension/MIME. Streamlit recordings
        # can be WAV even when the UI doesn't provide a filename.
        requested_suffix = Path(filename).suffix.lower() if filename else ""
        detected_suffix = _detect_audio_suffix(audio_bytes)

        # Validate against supported formats using the most reliable suffix.
        effective_suffix = detected_suffix or requested_suffix
        effective_name = f"audio{effective_suffix or '.webm'}"
        is_valid, validation_msg = validate_audio_file(audio_bytes, effective_name)
        if not is_valid:
            return {
                "text": "",
                "duration_seconds": 0,
                "cost": 0,
                "success": False,
                "error": validation_msg,
            }

        suffix = effective_suffix or ".webm"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        
        try:
            # Call OpenAI transcription API
            with open(tmp_path, "rb") as audio_file:
                response = client.audio.transcriptions.create(
                    model=OPENAI_TRANSCRIBE,
                    file=audio_file,
                    response_format="verbose_json"  # Get duration info
                )
            
            # Extract results
            text = response.text
            duration = getattr(response, 'duration', 60.0)  # Default 1 min if not provided
            cost = (duration / 60.0) * MULTIMODAL_PRICING["voice_transcription_per_minute"]
            
            logger.info(f"Voice transcription complete: {len(text)} chars, {duration:.1f}s, ${cost:.4f}")
            
            return {
                "text": text,
                "duration_seconds": duration,
                "cost": cost,
                "success": True,
                "error": None
            }
            
        finally:
            # Clean up temp file
            os.unlink(tmp_path)
            
    except ImportError:
        logger.error("OpenAI package not installed")
        return {
            "text": "",
            "duration_seconds": 0,
            "cost": 0,
            "success": False,
            "error": "OpenAI package not installed. Run: pip install openai"
        }
    except Exception as e:
        detected = _detect_audio_suffix(audio_bytes)
        size = len(audio_bytes) if audio_bytes else 0
        logger.error(f"Voice transcription failed: {e} (bytes={size}, detected={detected}, filename={filename})")
        return {
            "text": "",
            "duration_seconds": 0,
            "cost": 0,
            "success": False,
            "error": str(e)
        }


# =============================================================================
# IMAGE ANALYSIS (Task 2.2)
# =============================================================================

async def analyze_image(image_bytes: bytes, filename: str = "image.png") -> Dict[str, Any]:
    """
    Analyze image content using Gemini 2.0 Flash vision model (FREE).
    Extracts text, UI elements, and contextual information.
    
    Args:
        image_bytes: Raw image file bytes (supports png, jpg, webp, gif)
        filename: Original filename for format detection
    
    Returns:
        Dict with keys:
            - description: Detailed description of image content
            - extracted_text: Any text visible in the image (OCR)
            - ui_elements: Identified UI components if applicable
            - context: Inferred context/purpose
            - cost: Always 0 (Gemini Flash is free)
            - success: Boolean indicating success
            - error: Error message if failed
    """
    try:
        from google import genai
        from google.genai import types  # type: ignore
        
        # Initialize Gemini client
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        # Determine MIME type
        suffix = Path(filename).suffix.lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif"
        }
        mime_type = mime_map.get(suffix, "image/png")
        
        # Create image part
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        
        # Comprehensive analysis prompt
        analysis_prompt = """Analyze this image thoroughly and provide:

1. **Description**: What does this image show? Be specific and detailed.
2. **Extracted Text**: Any visible text, labels, or written content (perform OCR).
3. **UI Elements**: If this is a screenshot/UI, identify buttons, forms, menus, etc.
4. **Context**: What is the likely purpose or context of this image?
5. **Prompt Optimization Hints**: What aspects should be emphasized when creating a prompt related to this image?

Format your response as structured text with clear sections."""

        # Call Gemini API
        response = client.models.generate_content(
            model=GEMINI_VISION,
            contents=[analysis_prompt, image_part]
        )
        
        analysis_text = response.text
        
        logger.info(f"Image analysis complete: {len(analysis_text)} chars")
        
        return {
            "description": analysis_text,
            "extracted_text": _extract_section(analysis_text, "Extracted Text"),
            "ui_elements": _extract_section(analysis_text, "UI Elements"),
            "context": _extract_section(analysis_text, "Context"),
            "cost": MULTIMODAL_PRICING["image_analysis"],  # FREE
            "success": True,
            "error": None
        }
        
    except ImportError:
        logger.error("Google GenAI package not installed")
        return {
            "description": "",
            "extracted_text": "",
            "ui_elements": "",
            "context": "",
            "cost": 0,
            "success": False,
            "error": "Google GenAI package not installed. Run: pip install google-genai"
        }
    except Exception as e:
        logger.error(f"Image analysis failed: {e}")
        return {
            "description": "",
            "extracted_text": "",
            "ui_elements": "",
            "context": "",
            "cost": 0,
            "success": False,
            "error": str(e)
        }


def _extract_section(text: str, section_name: str) -> str:
    """Extract a section from the analysis response."""
    try:
        lines = text.split('\n')
        in_section = False
        section_lines = []
        
        for line in lines:
            if section_name.lower() in line.lower() and ('**' in line or ':' in line):
                in_section = True
                # Get content after the header if on same line
                if ':' in line:
                    content = line.split(':', 1)[1].strip()
                    if content:
                        section_lines.append(content)
                continue
            
            if in_section:
                # Stop at next section
                if line.strip().startswith('**') or (line.strip() and line.strip()[0].isdigit() and '.' in line[:3]):
                    break
                if line.strip():
                    section_lines.append(line.strip())
        
        return ' '.join(section_lines)
    except Exception:
        return ""

async def combine_multimodal_inputs(
    text_input: str = "",
    voice_result: Optional[Dict[str, Any]] = None,
    image_result: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Combine text, voice transcription, and image analysis into a unified prompt.
    
    Args:
        text_input: Direct text input from user
        voice_result: Result from transcribe_voice()
        image_result: Result from analyze_image()
    
    Returns:
        Dict with keys:
            - combined_prompt: Unified prompt text ready for optimization
            - sources: List of input sources used
            - total_cost: Combined preprocessing cost
            - is_multimodal: Whether multimodal inputs were used
            - credit_cost: Credits to deduct (1 for text-only, 2 for multimodal)
    """
    combined_parts = []
    sources = []
    total_cost = 0.0
    is_multimodal = False
    
    # Add text input
    if text_input and text_input.strip():
        combined_parts.append(f"**User Request:**\n{text_input.strip()}")
        sources.append("text")
    
    # Add voice transcription
    if voice_result and voice_result.get("success") and voice_result.get("text"):
        voice_text = voice_result["text"].strip()
        if voice_text:
            combined_parts.append(f"**Voice Input (Transcribed):**\n{voice_text}")
            sources.append("voice")
            total_cost += voice_result.get("cost", 0)
            is_multimodal = True
    
    # Add image analysis
    if image_result and image_result.get("success") and image_result.get("description"):
        image_desc = image_result["description"].strip()
        if image_desc:
            combined_parts.append(f"**Image Context:**\n{image_desc}")
            sources.append("image")
            total_cost += image_result.get("cost", 0)
            is_multimodal = True
    
    # Combine all parts
    if combined_parts:
        combined_prompt = "\n\n---\n\n".join(combined_parts)
    else:
        combined_prompt = ""
    
    # Determine credit cost
    credit_cost = MULTIMODAL_CREDIT_COST if is_multimodal else 1
    
    logger.info(f"Combined inputs from {sources}, multimodal={is_multimodal}, credits={credit_cost}")
    
    return {
        "combined_prompt": combined_prompt,
        "sources": sources,
        "total_cost": total_cost,
        "is_multimodal": is_multimodal,
        "credit_cost": credit_cost
    }


# =============================================================================
# MAIN PREPROCESSOR FUNCTION (Task 2.4)
# =============================================================================

async def preprocess_multimodal_input(
    text_input: str = "",
    audio_bytes: Optional[bytes] = None,
    audio_filename: str = "audio.webm",
    image_bytes: Optional[bytes] = None,
    image_filename: str = "image.png"
) -> Dict[str, Any]:
    """
    Main entry point for multimodal preprocessing.
    Processes all inputs and returns unified prompt ready for optimization.
    
    Args:
        text_input: Direct text input
        audio_bytes: Optional voice recording bytes
        audio_filename: Voice file name with extension
        image_bytes: Optional image bytes
        image_filename: Image file name with extension
    
    Returns:
        Dict with:
            - combined_prompt: Ready for optimization pipeline
            - sources: Input sources used
            - is_multimodal: Whether voice/image was used
            - credit_cost: Credits to deduct
            - total_preprocessing_cost: USD cost of preprocessing
            - voice_result: Full voice transcription result (if used)
            - image_result: Full image analysis result (if used)
            - errors: List of any errors encountered
    """
    voice_result = None
    image_result = None
    errors = []
    
    # Process voice input if provided
    if audio_bytes:
        logger.info(f"Processing voice input: {len(audio_bytes)} bytes")
        voice_result = await transcribe_voice(audio_bytes, audio_filename)
        if not voice_result["success"]:
            errors.append(f"Voice: {voice_result['error']}")
    
    # Process image input if provided
    if image_bytes:
        logger.info(f"Processing image input: {len(image_bytes)} bytes")
        image_result = await analyze_image(image_bytes, image_filename)
        if not image_result["success"]:
            errors.append(f"Image: {image_result['error']}")
    
    # Combine all inputs
    combined = await combine_multimodal_inputs(
        text_input=text_input,
        voice_result=voice_result,
        image_result=image_result
    )
    
    return {
        "combined_prompt": combined["combined_prompt"],
        "sources": combined["sources"],
        "is_multimodal": combined["is_multimodal"],
        "credit_cost": combined["credit_cost"],
        "total_preprocessing_cost": combined["total_cost"],
        "voice_result": voice_result,
        "image_result": image_result,
        "errors": errors
    }


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def validate_audio_file(audio_bytes: bytes, filename: str) -> Tuple[bool, str]:
    """Validate audio file format and size."""
    SUPPORTED_FORMATS = [".webm", ".mp3", ".wav", ".m4a", ".ogg", ".flac"]
    MAX_SIZE_MB = 25
    
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        return False, f"Unsupported format: {suffix}. Supported: {SUPPORTED_FORMATS}"
    
    size_mb = len(audio_bytes) / (1024 * 1024)
    if size_mb > MAX_SIZE_MB:
        return False, f"File too large: {size_mb:.1f}MB. Max: {MAX_SIZE_MB}MB"
    
    return True, "Valid"


def validate_image_file(image_bytes: bytes, filename: str) -> Tuple[bool, str]:
    """Validate image file format and size."""
    SUPPORTED_FORMATS = [".png", ".jpg", ".jpeg", ".webp", ".gif"]
    MAX_SIZE_MB = 20
    
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        return False, f"Unsupported format: {suffix}. Supported: {SUPPORTED_FORMATS}"
    
    size_mb = len(image_bytes) / (1024 * 1024)
    if size_mb > MAX_SIZE_MB:
        return False, f"File too large: {size_mb:.1f}MB. Max: {MAX_SIZE_MB}MB"
    
    return True, "Valid"


def estimate_multimodal_cost(
    has_voice: bool = False,
    voice_duration_seconds: float = 60,
    has_image: bool = False
) -> Dict[str, float]:
    """
    Estimate preprocessing costs before processing.
    
    Returns:
        Dict with voice_cost, image_cost, total_cost (all in USD)
    """
    voice_cost = 0.0
    if has_voice:
        voice_cost = (voice_duration_seconds / 60.0) * MULTIMODAL_PRICING["voice_transcription_per_minute"]
    
    image_cost = MULTIMODAL_PRICING["image_analysis"] if has_image else 0.0
    
    return {
        "voice_cost": voice_cost,
        "image_cost": image_cost,
        "total_cost": voice_cost + image_cost
    }


# =============================================================================
# MULTIMODAL AVAILABILITY CHECK (Task 3.3)
# =============================================================================

def check_multimodal_availability() -> Dict[str, Any]:
    """
    Check if multimodal features are available based on API key configuration.
    
    Returns:
        Dict with:
            - voice_available: Whether voice transcription is available
            - image_available: Whether image analysis is available
            - voice_reason: Reason if voice unavailable
            - image_reason: Reason if image unavailable
    """
    voice_available = False
    image_available = False
    voice_reason = ""
    image_reason = ""
    
    # Check OpenAI API key for voice
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_key:
        try:
            from openai import OpenAI
            voice_available = True
        except ImportError:
            voice_reason = "OpenAI package not installed"
    else:
        voice_reason = "OPENAI_API_KEY not configured"
    
    # Check Gemini API key for image
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if gemini_key:
        try:
            from google import genai
            image_available = True
        except ImportError:
            image_reason = "google-genai package not installed"
    else:
        image_reason = "GEMINI_API_KEY not configured"
    
    # Compatibility: some callers read `voice`/`image` while others read
    # `voice_available`/`image_available`.
    return {
        "voice": voice_available,
        "image": image_available,
        "voice_available": voice_available,
        "image_available": image_available,
        "voice_reason": voice_reason,
        "image_reason": image_reason,
        "any_available": voice_available or image_available,
    }


class MultimodalError(Exception):
    """Base exception for multimodal processing errors."""
    pass


class VoiceTranscriptionError(MultimodalError):
    """Error during voice transcription."""
    pass


class ImageAnalysisError(MultimodalError):
    """Error during image analysis."""
    pass


class MultimodalNotAvailableError(MultimodalError):
    """Multimodal features not available due to missing configuration."""
    pass
