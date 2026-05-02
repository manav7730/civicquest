"""
tests/test_quests.py — Unit tests for GameEngine and quest logic.
Run with: pytest tests/
"""

import pytest
from unittest.mock import MagicMock, patch
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from game_engine import GameEngine, QUESTS, PlayerState


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_gemini():
    gemini = MagicMock()
    gemini.generate.return_value = "Welcome, brave citizen! Your quest begins."
    gemini.chat.return_value     = "Great question! [QUEST_PROGRESS] You are learning well."
    return gemini

@pytest.fixture
def engine(mock_gemini):
    return GameEngine(mock_gemini)

@pytest.fixture
def active_session(engine):
    state = engine.new_game("test-session-001", "Rahul", "Gujarat", "en")
    return "test-session-001", state


# ── Quest definitions ─────────────────────────────────────────────────────────

def test_quest_count():
    assert len(QUESTS) == 5

def test_quest_fields():
    required = {"id", "title", "subtitle", "badge", "badge_emoji", "xp", "topic",
                "scene_prompt", "questions", "knowledge"}
    for q in QUESTS:
        assert required.issubset(q.keys()), f"Quest '{q['id']}' missing fields"

def test_quest_xp_increases():
    xp_values = [q["xp"] for q in QUESTS]
    assert xp_values == sorted(xp_values), "Quest XP should increase each quest"

def test_quest_questions_not_empty():
    for q in QUESTS:
        assert len(q["questions"]) >= 3, f"Quest {q['id']} needs at least 3 questions"


# ── GameEngine: new_game ──────────────────────────────────────────────────────

def test_new_game_creates_session(engine):
    state = engine.new_game("sess-abc", "Priya", "Maharashtra", "hi")
    assert state["player_name"] == "Priya"
    assert state["state_name"]  == "Maharashtra"
    assert state["total_xp"]    == 0
    assert state["quest_index"] == 0
    assert state["badges"]      == []

def test_new_game_returns_first_quest_title(engine):
    state = engine.new_game("sess-q1", "Dev", "Kerala", "en")
    assert state["current_quest_title"] == QUESTS[0]["title"]


# ── GameEngine: get_current_scene ────────────────────────────────────────────

def test_get_scene_calls_gemini(engine, active_session):
    sid, _ = active_session
    scene = engine.get_current_scene(sid)
    engine.gemini.generate.assert_called_once()
    assert scene["type"] == "scene"
    assert scene["quest_number"] == 1
    assert scene["total_quests"] == 5

def test_get_scene_has_suggested_questions(engine, active_session):
    sid, _ = active_session
    scene = engine.get_current_scene(sid)
    assert len(scene["suggested_questions"]) >= 3


# ── GameEngine: process_input ────────────────────────────────────────────────

def test_process_input_returns_response(engine, active_session):
    sid, _ = active_session
    result = engine.process_input(sid, "What is a voter ID?")
    assert result["type"]     == "response"
    assert len(result["response"]) > 0

def test_process_input_grants_xp_on_progress(engine, active_session):
    sid, _ = active_session
    result = engine.process_input(sid, "What is an EPIC card?")
    assert result["quest_progressed"] == True
    assert result["xp_gained"]        == 25

def test_process_input_strips_progress_signal(engine, active_session):
    sid, _ = active_session
    result = engine.process_input(sid, "How do I register?")
    assert "[QUEST_PROGRESS]" not in result["response"]

def test_process_input_invalid_session(engine):
    with pytest.raises(ValueError):
        engine.process_input("bad-session-id", "hello")


# ── GameEngine: advance_quest ────────────────────────────────────────────────

def test_advance_quest_awards_badge(engine, active_session):
    sid, _ = active_session
    result = engine.advance_quest(sid)
    assert result["type"]       == "quest_complete"
    assert result["earned_badge"] == QUESTS[0]["badge"]
    assert result["xp_earned"]  == QUESTS[0]["xp"]

def test_advance_quest_moves_index(engine, active_session):
    sid, _ = active_session
    engine.advance_quest(sid)
    state = engine._get_state(sid)
    assert state.quest_index == 1

def test_complete_all_quests_triggers_game_over(engine):
    sid = "full-game-sess"
    engine.new_game(sid, "Hero", "Delhi", "en")
    for _ in range(5):
        engine.advance_quest(sid)
    result = engine.advance_quest(sid)
    # After 5 advances the game is over
    assert result["type"] == "game_over" or engine._get_state(sid).is_finished()


# ── PlayerState ───────────────────────────────────────────────────────────────

def test_player_state_current_quest():
    s = PlayerState("s1", "Test", "Delhi", "en")
    assert s.current_quest() == QUESTS[0]

def test_player_state_is_finished_when_all_done():
    s = PlayerState("s2", "Test", "Delhi", "en", quest_index=5)
    assert s.is_finished() == True

def test_player_state_not_finished_at_start():
    s = PlayerState("s3", "Test", "Delhi", "en")
    assert s.is_finished() == False


# ── Leaderboard ───────────────────────────────────────────────────────────────

def test_leaderboard_records_on_completion(engine):
    sid = "lb-test-sess"
    engine.new_game(sid, "Topscorer", "Rajasthan", "en")
    state = engine._get_state(sid)
    state.quest_index = 4       # last quest
    engine.advance_quest(sid)   # triggers _record_score
    scores = engine.get_top_scores()
    assert any(s["name"] == "Topscorer" for s in scores)
