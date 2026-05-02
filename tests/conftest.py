import pytest
from unittest.mock import MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from game_engine import GameEngine

@pytest.fixture
def mock_gemini():
    gemini = MagicMock()
    gemini.generate.return_value = "Welcome, brave citizen! Your quest begins."
    gemini.chat.return_value = "Great question! [QUEST_PROGRESS] You are learning well."
    return gemini

@pytest.fixture
def engine(mock_gemini):
    return GameEngine(mock_gemini)

@pytest.fixture
def active_session(engine):
    state = engine.new_game("test-session-001", "Rahul", "Gujarat", "en")
    return "test-session-001", state
