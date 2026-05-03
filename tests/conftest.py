"""
tests/conftest.py — Shared fixtures for CivicQuest test suite.
"""

import pytest
from unittest.mock import MagicMock

from game_engine import GameEngine


@pytest.fixture
def mock_gemini():
    """Create a mocked GeminiClient for testing."""
    gemini = MagicMock()
    gemini.generate.return_value = "Welcome, brave citizen! Your quest begins."
    gemini.chat.return_value = "Great question! [QUEST_PROGRESS] You are learning well."
    return gemini


@pytest.fixture
def engine(mock_gemini):
    """Create a GameEngine instance with a mocked Gemini client."""
    return GameEngine(mock_gemini)


@pytest.fixture
def active_session(engine):
    """Create and return an active game session for testing."""
    state = engine.new_game("test-session-001", "Rahul", "Gujarat", "en")
    return "test-session-001", state
