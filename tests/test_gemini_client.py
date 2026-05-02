import pytest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gemini_client import GeminiClient

@patch("gemini_client.genai.Client")
def test_generate_success(mock_client_cls):
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
    mock_client = mock_client_cls.return_value
    mock_client.models.generate_content.side_effect = Exception("General Error")

    client = GeminiClient()
    # Cache makes it skip call if we repeat, so use a new prompt
    result = client.generate("unique prompt", "Fallback knowledge")
    
    assert "Fallback knowledge" in result
    assert "Desh steps forward" in result
