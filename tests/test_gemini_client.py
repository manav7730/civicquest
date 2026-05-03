"""
tests/test_gemini_client.py — Tests for the Gemini API wrapper.

Covers: successful generation, retry on 429, fallback on errors,
chat method, throttle behavior, and rate limit detection.
"""

import time

import pytest
from unittest.mock import patch, MagicMock

from gemini_client import GeminiClient


# ── Generate ──────────────────────────────────────────────────────────────────

@patch("gemini_client.genai.Client")
def test_generate_success(mock_client_cls):
    """generate() should return text on successful API call."""
    mock_client = mock_client_cls.return_value
    mock_response = MagicMock()
    mock_response.text = "Generated scene"
    mock_client.models.generate_content.return_value = mock_response

    client = GeminiClient()
    result = client.generate("test prompt")
    
    assert result == "Generated scene"
    mock_client.models.generate_content.assert_called_once()


@patch("gemini_client.time.sleep")
@patch("gemini_client.genai.Client")
def test_generate_retry_on_429(mock_client_cls, mock_sleep):
    """generate() should retry on 429 errors with exponential backoff."""
    mock_client = mock_client_cls.return_value
    
    class RateLimitError(Exception):
        pass
        
    mock_response = MagicMock()
    mock_response.text = "Success after retry"
    
    # Fail first, succeed second
    mock_client.models.generate_content.side_effect = [
        RateLimitError("429 Resource has been exhausted"),
        mock_response
    ]

    client = GeminiClient()
    result = client.generate("test prompt", "knowledge fallback")
    
    assert result == "Success after retry"
    assert mock_client.models.generate_content.call_count == 2
    mock_sleep.assert_called()


@patch("gemini_client.genai.Client")
def test_generate_fallback_on_error(mock_client_cls):
    """generate() should return fallback text when API fails."""
    mock_client = mock_client_cls.return_value
    mock_client.models.generate_content.side_effect = Exception("General Error")

    client = GeminiClient()
    result = client.generate("unique prompt for fallback test", "Fallback knowledge")
    
    assert "Fallback knowledge" in result
    assert "Desh steps forward" in result


@patch("gemini_client.genai.Client")
def test_generate_fallback_no_knowledge(mock_client_cls):
    """generate() should return generic fallback when no knowledge is provided."""
    mock_client = mock_client_cls.return_value
    mock_client.models.generate_content.side_effect = Exception("Error")

    client = GeminiClient()
    result = client.generate("prompt without knowledge")
    
    assert "adventure begins" in result


# ── Chat ──────────────────────────────────────────────────────────────────────

@patch("gemini_client.genai.Client")
def test_chat_success(mock_client_cls):
    """chat() should return text on successful API call."""
    mock_client = mock_client_cls.return_value
    mock_response = MagicMock()
    mock_response.text = "Desh answers your question"
    mock_client.models.generate_content.return_value = mock_response

    client = GeminiClient()
    result = client.chat(
        "System prompt",
        [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
        "What is EPIC?",
        "knowledge"
    )
    
    assert result == "Desh answers your question"
    mock_client.models.generate_content.assert_called_once()


@patch("gemini_client.genai.Client")
def test_chat_fallback_on_error(mock_client_cls):
    """chat() should return knowledge-based fallback when API fails."""
    mock_client = mock_client_cls.return_value
    mock_client.models.generate_content.side_effect = Exception("API Error")

    client = GeminiClient()
    result = client.chat(
        "System prompt",
        [],
        "What is voting?",
        "Voting knowledge base"
    )
    
    assert "Voting knowledge base" in result
    assert "[QUEST_PROGRESS]" in result


@patch("gemini_client.genai.Client")
def test_chat_fallback_no_knowledge(mock_client_cls):
    """chat() fallback without knowledge should still return a response."""
    mock_client = mock_client_cls.return_value
    mock_client.models.generate_content.side_effect = Exception("Error")

    client = GeminiClient()
    result = client.chat("System", [], "question", "")
    
    assert "resting" in result


# ── Rate Limit Detection ─────────────────────────────────────────────────────

def test_is_rate_limit_429():
    """_is_rate_limit should detect 429 error codes."""
    assert GeminiClient._is_rate_limit(Exception("429 Too Many Requests")) is True


def test_is_rate_limit_resource_exhausted():
    """_is_rate_limit should detect 'resource exhausted' errors."""
    assert GeminiClient._is_rate_limit(Exception("Resource has been exhausted")) is True


def test_is_rate_limit_false():
    """_is_rate_limit should return False for non-rate-limit errors."""
    assert GeminiClient._is_rate_limit(Exception("Connection timeout")) is False


# ── Throttle ──────────────────────────────────────────────────────────────────

@patch("gemini_client.time.sleep")
@patch("gemini_client.genai.Client")
def test_throttle_enforces_delay(mock_client_cls, mock_sleep):
    """Throttle should enforce minimum delay between API calls."""
    mock_client = mock_client_cls.return_value
    mock_response = MagicMock()
    mock_response.text = "response"
    mock_client.models.generate_content.return_value = mock_response

    client = GeminiClient()
    # Set last call timestamp to just now
    client._last_call_ts = time.time()
    
    client.generate("throttle test prompt")
    # Sleep should have been called due to the throttle
    mock_sleep.assert_called()
