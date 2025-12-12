"""
Multimodal Integration Stress Tests for CATALYZE
=================================================
Comprehensive stress testing for voice transcription, image analysis,
and multimodal input processing.

Test Categories:
1. Unit Tests - Individual function validation
2. Edge Case Tests - Boundary conditions and error handling
3. Integration Tests - Full pipeline with mocked APIs
4. Stress Tests - High load and concurrent processing
5. Validation Tests - Input validation and security
"""

import pytest
import asyncio
import os
import sys
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from consensus_prompt_optimizer.multimodal_preprocessor import (
    transcribe_voice,
    analyze_image,
    combine_multimodal_inputs,
    preprocess_multimodal_input,
    check_multimodal_availability,
    validate_audio_file,
    validate_image_file,
    estimate_multimodal_cost,
    _detect_audio_suffix,
    _is_effectively_empty_audio,
    MultimodalError,
    VoiceTranscriptionError,
    ImageAnalysisError,
    MultimodalNotAvailableError,
)
from consensus_prompt_optimizer.config import (
    OPENAI_TRANSCRIBE,
    GEMINI_VISION,
    MULTIMODAL_PRICING,
    MULTIMODAL_CREDIT_COST,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_audio_bytes():
    """Generate sample audio bytes for testing."""
    # Minimal valid audio-like bytes (not real audio, just for testing)
    return b"\x00" * 1024  # 1KB of null bytes

@pytest.fixture
def sample_image_bytes():
    """Generate sample PNG-like bytes for testing."""
    # PNG magic bytes + minimal header
    png_header = b"\x89PNG\r\n\x1a\n"
    return png_header + b"\x00" * 1024

@pytest.fixture
def large_audio_bytes():
    """Generate audio bytes exceeding size limit."""
    return b"\x00" * (26 * 1024 * 1024)  # 26MB - over 25MB limit

@pytest.fixture
def large_image_bytes():
    """Generate image bytes exceeding size limit."""
    return b"\x00" * (21 * 1024 * 1024)  # 21MB - over 20MB limit


# =============================================================================
# 1. UNIT TESTS - Config Constants
# =============================================================================

class TestConfigConstants:
    """Verify multimodal configuration constants are correctly set."""
    
    def test_openai_transcribe_model(self):
        """Verify OpenAI transcription model is set."""
        assert OPENAI_TRANSCRIBE == "gpt-4o-mini-transcribe"
    
    def test_gemini_vision_model(self):
        """Verify Gemini vision model is set."""
        assert GEMINI_VISION == "gemini-2.0-flash"
    
    def test_multimodal_credit_cost(self):
        """Verify multimodal requests cost 2 credits."""
        assert MULTIMODAL_CREDIT_COST == 2
    
    def test_voice_pricing(self):
        """Verify voice transcription pricing is set."""
        assert "voice_transcription_per_minute" in MULTIMODAL_PRICING
        assert MULTIMODAL_PRICING["voice_transcription_per_minute"] == 0.003
    
    def test_image_pricing_is_free(self):
        """Verify image analysis is free (Gemini Flash)."""
        assert "image_analysis" in MULTIMODAL_PRICING
        assert MULTIMODAL_PRICING["image_analysis"] == 0.0


# =============================================================================
# 2. VALIDATION TESTS - Input Validation
# =============================================================================

class TestAudioValidation:
    """Test audio file validation."""
    
    @pytest.mark.parametrize("filename,expected", [
        ("test.mp3", True),
        ("test.wav", True),
        ("test.webm", True),
        ("test.m4a", True),
        ("test.ogg", True),
        ("test.flac", True),
        ("test.MP3", True),  # Case insensitive
        ("test.WAV", True),
    ])
    def test_valid_audio_formats(self, sample_audio_bytes, filename, expected):
        """Test supported audio formats are accepted."""
        is_valid, _ = validate_audio_file(sample_audio_bytes, filename)
        assert is_valid == expected
    
    @pytest.mark.parametrize("filename", [
        "test.txt",
        "test.pdf",
        "test.doc",
        "test.exe",
        "test.py",
        "test",  # No extension
        "test.mp4",  # Video, not audio
    ])
    def test_invalid_audio_formats(self, sample_audio_bytes, filename):
        """Test unsupported formats are rejected."""
        is_valid, message = validate_audio_file(sample_audio_bytes, filename)
        assert is_valid is False
        assert "Unsupported format" in message
    
    def test_audio_size_limit(self, large_audio_bytes):
        """Test audio exceeding 25MB limit is rejected."""
        is_valid, message = validate_audio_file(large_audio_bytes, "test.mp3")
        assert is_valid is False
        assert "too large" in message.lower()
    
    def test_empty_audio_bytes(self):
        """Test empty audio bytes are technically valid (size check only)."""
        is_valid, _ = validate_audio_file(b"", "test.mp3")
        assert is_valid is True  # Empty but valid format


class TestAudioSniffing:
    """Test audio container sniffing used for transcription."""

    def test_detects_wav(self):
        wav_bytes = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"\x00" * 64
        assert _detect_audio_suffix(wav_bytes) == ".wav"

    def test_detects_webm(self):
        webm_bytes = b"\x1A\x45\xDF\xA3" + b"\x00" * 64
        assert _detect_audio_suffix(webm_bytes) == ".webm"

    def test_empty_wav_header_is_effectively_empty(self):
        # Minimal RIFF/WAVE header with a data chunk of size 0
        header = (
            b"RIFF" + (36).to_bytes(4, "little") + b"WAVE" +
            b"fmt " + (16).to_bytes(4, "little") + (1).to_bytes(2, "little") + (1).to_bytes(2, "little") +
            (16000).to_bytes(4, "little") + (32000).to_bytes(4, "little") + (2).to_bytes(2, "little") + (16).to_bytes(2, "little") +
            b"data" + (0).to_bytes(4, "little")
        )
        assert _is_effectively_empty_audio(header) is True

    @pytest.mark.asyncio
    async def test_transcribe_voice_prefers_detected_suffix(self, monkeypatch):
        # WAV bytes but misleading filename should still be saved as .wav
        # Build a small-but-non-empty WAV (RIFF/WAVE + fmt + data chunk)
        data_payload = b"\x00" * 1024
        wav_bytes = (
            b"RIFF" + (36 + len(data_payload)).to_bytes(4, "little") + b"WAVE" +
            b"fmt " + (16).to_bytes(4, "little") + (1).to_bytes(2, "little") + (1).to_bytes(2, "little") +
            (16000).to_bytes(4, "little") + (16000 * 2).to_bytes(4, "little") + (2).to_bytes(2, "little") + (16).to_bytes(2, "little") +
            b"data" + (len(data_payload)).to_bytes(4, "little") + data_payload
        )

        recorded = {"suffix": None}

        import consensus_prompt_optimizer.multimodal_preprocessor as mp

        original_named_temp = mp.tempfile.NamedTemporaryFile

        def wrapped_named_temp(*args, **kwargs):
            recorded["suffix"] = kwargs.get("suffix")
            return original_named_temp(*args, **kwargs)

        monkeypatch.setattr(mp.tempfile, "NamedTemporaryFile", wrapped_named_temp)

        class DummyResponse:
            text = "hello"
            duration = 1.0

        class DummyOpenAI:
            def __init__(self, *args, **kwargs):
                self.audio = MagicMock()
                self.audio.transcriptions = MagicMock()
                self.audio.transcriptions.create = MagicMock(return_value=DummyResponse())

        monkeypatch.setattr("openai.OpenAI", DummyOpenAI)

        result = await transcribe_voice(wav_bytes, filename="audio.webm")
        assert result["success"] is True
        assert recorded["suffix"] == ".wav"


class TestImageValidation:
    """Test image file validation."""
    
    @pytest.mark.parametrize("filename,expected", [
        ("test.png", True),
        ("test.jpg", True),
        ("test.jpeg", True),
        ("test.webp", True),
        ("test.gif", True),
        ("test.PNG", True),  # Case insensitive
        ("test.JPEG", True),
    ])
    def test_valid_image_formats(self, sample_image_bytes, filename, expected):
        """Test supported image formats are accepted."""
        is_valid, _ = validate_image_file(sample_image_bytes, filename)
        assert is_valid == expected
    
    @pytest.mark.parametrize("filename", [
        "test.txt",
        "test.pdf",
        "test.bmp",  # BMP not supported
        "test.tiff",
        "test.svg",
        "test.ico",
    ])
    def test_invalid_image_formats(self, sample_image_bytes, filename):
        """Test unsupported formats are rejected."""
        is_valid, message = validate_image_file(sample_image_bytes, filename)
        assert is_valid is False
        assert "Unsupported format" in message
    
    def test_image_size_limit(self, large_image_bytes):
        """Test image exceeding 20MB limit is rejected."""
        is_valid, message = validate_image_file(large_image_bytes, "test.png")
        assert is_valid is False
        assert "too large" in message.lower()


# =============================================================================
# 3. COST ESTIMATION TESTS
# =============================================================================

class TestCostEstimation:
    """Test preprocessing cost estimation."""
    
    def test_voice_only_cost(self):
        """Test cost for voice-only input."""
        costs = estimate_multimodal_cost(has_voice=True, voice_duration_seconds=60)
        assert costs["voice_cost"] == pytest.approx(0.003, rel=1e-6)
        assert costs["image_cost"] == 0.0
        assert costs["total_cost"] == pytest.approx(0.003, rel=1e-6)
    
    def test_image_only_cost(self):
        """Test cost for image-only input (should be free)."""
        costs = estimate_multimodal_cost(has_image=True)
        assert costs["voice_cost"] == 0.0
        assert costs["image_cost"] == 0.0
        assert costs["total_cost"] == 0.0
    
    def test_combined_cost(self):
        """Test cost for voice + image."""
        costs = estimate_multimodal_cost(
            has_voice=True, 
            voice_duration_seconds=120,  # 2 minutes
            has_image=True
        )
        assert costs["voice_cost"] == pytest.approx(0.006, rel=1e-6)
        assert costs["image_cost"] == 0.0
        assert costs["total_cost"] == pytest.approx(0.006, rel=1e-6)
    
    def test_long_voice_cost(self):
        """Test cost for long voice recording (10 minutes)."""
        costs = estimate_multimodal_cost(has_voice=True, voice_duration_seconds=600)
        expected = (600 / 60) * 0.003  # 10 * 0.003 = 0.03
        assert costs["voice_cost"] == pytest.approx(expected, rel=1e-6)
    
    def test_no_inputs_cost(self):
        """Test cost when no multimodal inputs."""
        costs = estimate_multimodal_cost()
        assert costs["voice_cost"] == 0.0
        assert costs["image_cost"] == 0.0
        assert costs["total_cost"] == 0.0


# =============================================================================
# 4. AVAILABILITY CHECK TESTS
# =============================================================================

class TestAvailabilityCheck:
    """Test multimodal availability detection."""
    
    def test_availability_structure(self):
        """Test availability check returns correct structure."""
        result = check_multimodal_availability()
        
        assert "voice_available" in result
        assert "image_available" in result
        assert "voice_reason" in result
        assert "image_reason" in result
        assert "any_available" in result
        
        assert isinstance(result["voice_available"], bool)
        assert isinstance(result["image_available"], bool)
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "", "GEMINI_API_KEY": ""})
    def test_no_keys_configured(self):
        """Test when no API keys are configured."""
        result = check_multimodal_availability()
        
        assert result["voice_available"] is False
        assert result["image_available"] is False
        assert "not configured" in result["voice_reason"].lower() or "OPENAI_API_KEY" in result["voice_reason"]
        assert "not configured" in result["image_reason"].lower() or "GEMINI_API_KEY" in result["image_reason"]
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "GEMINI_API_KEY": ""})
    def test_only_openai_configured(self):
        """Test when only OpenAI key is configured."""
        result = check_multimodal_availability()
        
        # Voice may or may not be available depending on package installation
        assert result["image_available"] is False
        assert result["any_available"] == result["voice_available"]


# =============================================================================
# 5. INPUT COMBINER TESTS
# =============================================================================

class TestInputCombiner:
    """Test multimodal input combination logic."""
    
    @pytest.mark.asyncio
    async def test_text_only_input(self):
        """Test combining text-only input."""
        result = await combine_multimodal_inputs(text_input="Test prompt idea")
        
        assert result["combined_prompt"] != ""
        assert "text" in result["sources"]
        assert result["is_multimodal"] is False
        assert result["credit_cost"] == 1  # Text-only = 1 credit
    
    @pytest.mark.asyncio
    async def test_text_with_voice(self):
        """Test combining text + voice input."""
        voice_result = {
            "text": "Transcribed voice content",
            "success": True,
            "cost": 0.003
        }
        
        result = await combine_multimodal_inputs(
            text_input="Written text",
            voice_result=voice_result
        )
        
        assert "text" in result["sources"]
        assert "voice" in result["sources"]
        assert result["is_multimodal"] is True
        assert result["credit_cost"] == MULTIMODAL_CREDIT_COST  # 2 credits
        assert result["total_cost"] == 0.003
    
    @pytest.mark.asyncio
    async def test_text_with_image(self):
        """Test combining text + image input."""
        image_result = {
            "description": "Image shows a diagram",
            "success": True,
            "cost": 0.0
        }
        
        result = await combine_multimodal_inputs(
            text_input="Written text",
            image_result=image_result
        )
        
        assert "text" in result["sources"]
        assert "image" in result["sources"]
        assert result["is_multimodal"] is True
        assert result["credit_cost"] == MULTIMODAL_CREDIT_COST
    
    @pytest.mark.asyncio
    async def test_all_inputs_combined(self):
        """Test combining text + voice + image."""
        voice_result = {
            "text": "Voice content",
            "success": True,
            "cost": 0.003
        }
        image_result = {
            "description": "Image description",
            "success": True,
            "cost": 0.0
        }
        
        result = await combine_multimodal_inputs(
            text_input="Text content",
            voice_result=voice_result,
            image_result=image_result
        )
        
        assert len(result["sources"]) == 3
        assert result["is_multimodal"] is True
        assert result["credit_cost"] == MULTIMODAL_CREDIT_COST
    
    @pytest.mark.asyncio
    async def test_failed_voice_ignored(self):
        """Test that failed voice transcription is ignored."""
        voice_result = {
            "text": "",
            "success": False,
            "error": "Transcription failed",
            "cost": 0
        }
        
        result = await combine_multimodal_inputs(
            text_input="Text only",
            voice_result=voice_result
        )
        
        assert "voice" not in result["sources"]
        assert result["is_multimodal"] is False
    
    @pytest.mark.asyncio
    async def test_empty_inputs(self):
        """Test with no inputs."""
        result = await combine_multimodal_inputs()
        
        assert result["combined_prompt"] == ""
        assert result["sources"] == []
        assert result["is_multimodal"] is False
    
    @pytest.mark.asyncio
    async def test_whitespace_text_ignored(self):
        """Test that whitespace-only text is ignored."""
        result = await combine_multimodal_inputs(text_input="   \n\t  ")
        
        assert "text" not in result["sources"]


# =============================================================================
# 6. VOICE TRANSCRIPTION TESTS (Mocked)
# =============================================================================

class TestVoiceTranscription:
    """Test voice transcription with mocked OpenAI API."""
    
    @pytest.mark.asyncio
    async def test_successful_transcription(self, sample_audio_bytes):
        """Test successful voice transcription."""
        mock_response = Mock()
        mock_response.text = "This is the transcribed text"
        mock_response.duration = 30.0
        
        with patch("openai.OpenAI") as mock_openai:
            mock_client = Mock()
            mock_client.audio.transcriptions.create.return_value = mock_response
            mock_openai.return_value = mock_client
            
            result = await transcribe_voice(sample_audio_bytes, "test.mp3")
            
            assert result["success"] is True
            assert result["text"] == "This is the transcribed text"
            assert result["duration_seconds"] == 30.0
            assert result["cost"] == pytest.approx(0.0015, rel=1e-6)  # 30s = 0.5min * 0.003
    
    @pytest.mark.asyncio
    async def test_transcription_without_api_key(self, sample_audio_bytes):
        """Test transcription fails gracefully without API key."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
            with patch("openai.OpenAI") as mock_openai:
                mock_openai.side_effect = Exception("API key not configured")
                
                result = await transcribe_voice(sample_audio_bytes, "test.mp3")
                
                assert result["success"] is False
                assert result["error"] is not None
    
    @pytest.mark.asyncio
    async def test_transcription_api_error(self, sample_audio_bytes):
        """Test transcription handles API errors gracefully."""
        with patch("openai.OpenAI") as mock_openai:
            mock_client = Mock()
            mock_client.audio.transcriptions.create.side_effect = Exception("API rate limit exceeded")
            mock_openai.return_value = mock_client
            
            result = await transcribe_voice(sample_audio_bytes, "test.mp3")
            
            assert result["success"] is False
            assert "rate limit" in result["error"].lower()


# =============================================================================
# 7. IMAGE ANALYSIS TESTS (Mocked)
# =============================================================================

class TestImageAnalysis:
    """Test image analysis with mocked Gemini API."""
    
    @pytest.mark.asyncio
    async def test_successful_analysis(self, sample_image_bytes):
        """Test successful image analysis."""
        mock_response = Mock()
        mock_response.text = """
        **Description**: A screenshot of a web application
        **Extracted Text**: Login button, Username field
        **UI Elements**: Form, buttons, input fields
        **Context**: Login page for a web app
        """
        
        with patch("google.genai.Client") as mock_genai_client:
            mock_client = Mock()
            mock_client.models.generate_content.return_value = mock_response
            mock_genai_client.return_value = mock_client
            
            result = await analyze_image(sample_image_bytes, "test.png")
            
            assert result["success"] is True
            assert result["description"] != ""
            assert result["cost"] == 0.0  # Gemini Flash is free
    
    @pytest.mark.asyncio
    async def test_analysis_api_error(self, sample_image_bytes):
        """Test image analysis handles API errors gracefully."""
        with patch("google.genai.Client") as mock_genai_client:
            mock_client = Mock()
            mock_client.models.generate_content.side_effect = Exception("Quota exceeded")
            mock_genai_client.return_value = mock_client
            
            result = await analyze_image(sample_image_bytes, "test.png")
            
            assert result["success"] is False
            assert result["error"] is not None


# =============================================================================
# 8. FULL PREPROCESSOR TESTS (Mocked)
# =============================================================================

class TestFullPreprocessor:
    """Test the full preprocessing pipeline."""
    
    @pytest.mark.asyncio
    async def test_text_only_preprocessing(self):
        """Test preprocessing with text only."""
        result = await preprocess_multimodal_input(text_input="Create a landing page")
        
        assert result["combined_prompt"] != ""
        assert result["is_multimodal"] is False
        assert result["credit_cost"] == 1
        assert result["errors"] == []
    
    @pytest.mark.asyncio
    async def test_multimodal_preprocessing(self, sample_audio_bytes, sample_image_bytes):
        """Test full multimodal preprocessing with mocks."""
        mock_voice_response = Mock()
        mock_voice_response.text = "Voice input content"
        mock_voice_response.duration = 60.0
        
        mock_image_response = Mock()
        mock_image_response.text = "Image shows a diagram"
        
        with patch("openai.OpenAI") as mock_openai:
            with patch("google.genai.Client") as mock_genai_client:
                # Setup OpenAI mock
                mock_openai_client = Mock()
                mock_openai_client.audio.transcriptions.create.return_value = mock_voice_response
                mock_openai.return_value = mock_openai_client
                
                # Setup Gemini mock
                mock_gemini_client = Mock()
                mock_gemini_client.models.generate_content.return_value = mock_image_response
                mock_genai_client.return_value = mock_gemini_client
                
                result = await preprocess_multimodal_input(
                    text_input="Additional context",
                    audio_bytes=sample_audio_bytes,
                    audio_filename="test.mp3",
                    image_bytes=sample_image_bytes,
                    image_filename="test.png"
                )
                
                assert result["is_multimodal"] is True
                assert result["credit_cost"] == 2
                assert len(result["sources"]) >= 2
    
    @pytest.mark.asyncio
    async def test_graceful_degradation(self, sample_audio_bytes):
        """Test graceful degradation when voice fails but text works."""
        with patch("openai.OpenAI") as mock_openai:
            mock_openai.side_effect = Exception("Voice API unavailable")
            
            result = await preprocess_multimodal_input(
                text_input="Fallback text",
                audio_bytes=sample_audio_bytes,
                audio_filename="test.mp3"
            )
            
            # Should still work with text
            assert result["combined_prompt"] != ""
            assert "text" in result["sources"]
            assert len(result["errors"]) > 0  # Voice error recorded


# =============================================================================
# 9. STRESS TESTS - Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.mark.asyncio
    async def test_unicode_text_input(self):
        """Test handling of unicode characters."""
        unicode_text = "Create a prompt for 日本語 and émojis 🎉"
        result = await preprocess_multimodal_input(text_input=unicode_text)
        
        assert unicode_text in result["combined_prompt"]
    
    @pytest.mark.asyncio
    async def test_very_long_text_input(self):
        """Test handling of very long text input."""
        long_text = "A" * 50000  # 50K characters
        result = await preprocess_multimodal_input(text_input=long_text)
        
        assert len(result["combined_prompt"]) >= 50000
    
    @pytest.mark.asyncio
    async def test_special_characters_in_text(self):
        """Test handling of special characters."""
        special_text = "Test with <html>, \"quotes\", 'apostrophes', & ampersands"
        result = await preprocess_multimodal_input(text_input=special_text)
        
        assert result["combined_prompt"] != ""
    
    @pytest.mark.asyncio
    async def test_newlines_and_formatting(self):
        """Test preservation of newlines and formatting."""
        formatted_text = "Line 1\nLine 2\n\nParagraph 2\n\t- Bullet 1\n\t- Bullet 2"
        result = await preprocess_multimodal_input(text_input=formatted_text)
        
        assert "\n" in result["combined_prompt"]
    
    def test_zero_duration_voice_cost(self):
        """Test cost estimation with zero duration."""
        costs = estimate_multimodal_cost(has_voice=True, voice_duration_seconds=0)
        assert costs["voice_cost"] == 0.0
    
    def test_negative_duration_handling(self):
        """Test cost estimation handles negative duration gracefully."""
        costs = estimate_multimodal_cost(has_voice=True, voice_duration_seconds=-60)
        # Should either return 0 or negative (depending on implementation)
        assert isinstance(costs["voice_cost"], float)


# =============================================================================
# 10. EXCEPTION CLASS TESTS
# =============================================================================

class TestExceptionClasses:
    """Test custom exception classes."""
    
    def test_multimodal_error_inheritance(self):
        """Test MultimodalError is an Exception."""
        assert issubclass(MultimodalError, Exception)
    
    def test_voice_transcription_error(self):
        """Test VoiceTranscriptionError."""
        assert issubclass(VoiceTranscriptionError, MultimodalError)
        
        error = VoiceTranscriptionError("Transcription failed")
        assert str(error) == "Transcription failed"
    
    def test_image_analysis_error(self):
        """Test ImageAnalysisError."""
        assert issubclass(ImageAnalysisError, MultimodalError)
    
    def test_not_available_error(self):
        """Test MultimodalNotAvailableError."""
        assert issubclass(MultimodalNotAvailableError, MultimodalError)


# =============================================================================
# 11. CONCURRENT PROCESSING TESTS
# =============================================================================

class TestConcurrentProcessing:
    """Test concurrent/parallel processing scenarios."""
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_requests(self):
        """Test multiple concurrent preprocessing requests."""
        texts = [f"Request {i}" for i in range(10)]
        
        tasks = [
            preprocess_multimodal_input(text_input=text)
            for text in texts
        ]
        
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 10
        for i, result in enumerate(results):
            assert f"Request {i}" in result["combined_prompt"]
    
    @pytest.mark.asyncio
    async def test_concurrent_with_failures(self, sample_audio_bytes):
        """Test concurrent requests with some failures."""
        async def failing_request():
            with patch("openai.OpenAI") as mock:
                mock.side_effect = Exception("API Error")
                return await preprocess_multimodal_input(
                    text_input="Backup text",
                    audio_bytes=sample_audio_bytes,
                    audio_filename="test.mp3"
                )
        
        async def success_request():
            return await preprocess_multimodal_input(text_input="Success")
        
        tasks = [failing_request(), success_request(), failing_request(), success_request()]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 4
        # All should have combined_prompt (graceful degradation)
        for result in results:
            assert result["combined_prompt"] != ""


# =============================================================================
# 12. USAGE SERVICE INTEGRATION TESTS
# =============================================================================

class TestUsageServiceIntegration:
    """Test usage service integration for credit tracking."""
    
    def test_increment_by_method_exists(self):
        """Verify increment_usage_by method exists."""
        from auth.usage_service import UsageService
        
        service = UsageService()
        assert hasattr(service, 'increment_usage_by')
    
    def test_increment_by_signature(self):
        """Verify increment_usage_by has correct signature."""
        from auth.usage_service import UsageService
        import inspect
        
        sig = inspect.signature(UsageService.increment_usage_by)
        params = list(sig.parameters.keys())
        
        assert 'user_id' in params
        assert 'amount' in params


# =============================================================================
# 13. ORCHESTRATOR INTEGRATION TESTS
# =============================================================================

class TestOrchestratorIntegration:
    """Test orchestrator multimodal integration."""
    
    def test_run_multimodal_method_exists(self):
        """Verify run_multimodal method exists."""
        from consensus_prompt_optimizer.orchestrator import PromptimaV2
        
        orchestrator = PromptimaV2()
        assert hasattr(orchestrator, 'run_multimodal')
    
    def test_run_multimodal_is_async(self):
        """Verify run_multimodal is an async method."""
        from consensus_prompt_optimizer.orchestrator import PromptimaV2
        import inspect
        
        assert inspect.iscoroutinefunction(PromptimaV2.run_multimodal)


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
