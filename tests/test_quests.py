"""
tests/test_quests.py — Unit tests for GameEngine and quest logic.

Covers: quest definitions, game lifecycle, player state, leaderboard,
integration testing, session cleanup, and edge cases.
Run with: pytest tests/ -v
"""

import time

import pytest
from unittest.mock import MagicMock

from game_engine import GameEngine, QUESTS, PlayerState, LanguageCode, QuestID


# ── Quest definitions ─────────────────────────────────────────────────────────

def test_quest_count():
    """There should be exactly 5 quests."""
    assert len(QUESTS) == 5


def test_quest_fields():
    """Every quest should have all required fields."""
    required = {"id", "title", "subtitle", "badge", "badge_emoji", "xp", "topic",
                "scene_prompt", "questions", "knowledge"}
    for q in QUESTS:
        assert required.issubset(q.keys()), f"Quest '{q['id']}' missing fields"


def test_quest_enums():
    """Quest and language enums should have expected values."""
    assert QuestID.VOTER_REGISTRATION.value == "voter_registration"
    assert LanguageCode.ENGLISH.value == "en"


def test_quest_xp_increases():
    """Quest XP rewards should increase with each quest."""
    xp_values = [q["xp"] for q in QUESTS]
    assert xp_values == sorted(xp_values), "Quest XP should increase each quest"


def test_quest_questions_not_empty():
    """Each quest should have at least 3 suggested questions."""
    for q in QUESTS:
        assert len(q["questions"]) >= 3, f"Quest {q['id']} needs at least 3 questions"


def test_quest_ids_unique():
    """All quest IDs should be unique."""
    ids = [q["id"] for q in QUESTS]
    assert len(ids) == len(set(ids)), "Quest IDs must be unique"


def test_quest_badges_unique():
    """All quest badges should be unique."""
    badges = [q["badge"] for q in QUESTS]
    assert len(badges) == len(set(badges)), "Quest badges must be unique"


# ── GameEngine: new_game ──────────────────────────────────────────────────────

def test_new_game_creates_session(engine):
    """new_game should create a valid session with correct initial state."""
    state = engine.new_game("sess-abc", "Priya", "Maharashtra", "hi")
    assert state["player_name"] == "Priya"
    assert state["state_name"]  == "Maharashtra"
    assert state["total_xp"]    == 0
    assert state["quest_index"] == 0
    assert state["badges"]      == []


def test_new_game_invalid_language_fallback(engine):
    """Invalid language code should fall back to English."""
    state = engine.new_game("sess-xyz", "Test", "State", "invalid_lang")
    assert state["language"] == "en"


def test_new_game_returns_first_quest_title(engine):
    """new_game should return the title of the first quest."""
    state = engine.new_game("sess-q1", "Dev", "Kerala", "en")
    assert state["current_quest_title"] == QUESTS[0]["title"]


# ── GameEngine: get_current_scene ────────────────────────────────────────────

def test_get_scene_calls_gemini(engine, active_session):
    """get_current_scene should call Gemini's generate method."""
    sid, _ = active_session
    scene = engine.get_current_scene(sid)
    engine.gemini.generate.assert_called_once()
    assert scene["type"] == "scene"
    assert scene["quest_number"] == 1
    assert scene["total_quests"] == 5


def test_get_scene_has_suggested_questions(engine, active_session):
    """get_current_scene should include suggested questions."""
    sid, _ = active_session
    scene = engine.get_current_scene(sid)
    assert len(scene["suggested_questions"]) >= 3


# ── GameEngine: process_input ────────────────────────────────────────────────

def test_process_input_returns_response(engine, active_session):
    """process_input should return a valid response with type 'response'."""
    sid, _ = active_session
    result = engine.process_input(sid, "What is a voter ID?")
    assert result["type"]     == "response"
    assert len(result["response"]) > 0


def test_process_input_grants_xp_on_progress(engine, active_session):
    """process_input should grant XP when quest progresses."""
    sid, _ = active_session
    result = engine.process_input(sid, "What is an EPIC card?")
    assert result["quest_progressed"] is True
    assert result["xp_gained"]        == 25


def test_process_input_strips_progress_signal(engine, active_session):
    """[QUEST_PROGRESS] signal should be stripped from the response."""
    sid, _ = active_session
    result = engine.process_input(sid, "How do I register?")
    assert "[QUEST_PROGRESS]" not in result["response"]


def test_process_input_invalid_session(engine):
    """process_input with invalid session should raise ValueError."""
    with pytest.raises(ValueError):
        engine.process_input("bad-session-id", "hello")


# ── GameEngine: advance_quest ────────────────────────────────────────────────

def test_advance_quest_awards_badge(engine, active_session):
    """advance_quest should award the correct badge."""
    sid, _ = active_session
    result = engine.advance_quest(sid)
    assert result["type"]       == "quest_complete"
    assert result["earned_badge"] == QUESTS[0]["badge"]
    assert result["xp_earned"]  == QUESTS[0]["xp"]


def test_advance_quest_moves_index(engine, active_session):
    """advance_quest should increment the quest_index."""
    sid, _ = active_session
    engine.advance_quest(sid)
    state = engine._get_state(sid)
    assert state.quest_index == 1


def test_complete_all_quests_triggers_game_over(engine):
    """Completing all 5 quests should trigger game_over."""
    sid = "full-game-sess"
    engine.new_game(sid, "Hero", "Delhi", "en")
    for _ in range(5):
        engine.advance_quest(sid)
    result = engine.advance_quest(sid)
    assert result["type"] == "error"
    assert result["message"] == "Game already completed."


# ── Full Game Integration Test ───────────────────────────────────────────────

def test_full_game_integration(engine):
    """Full game flow: start → 5 scenes → 5 inputs → 5 advances → game over."""
    sid = "integration-test-001"
    game_state = engine.new_game(sid, "IntegrationPlayer", "Gujarat", "en")
    assert game_state["quest_index"] == 0
    assert game_state["total_xp"] == 0

    total_expected_xp = 0
    for i in range(5):
        # Get scene
        scene = engine.get_current_scene(sid)
        assert scene["type"] == "scene"
        assert scene["quest_number"] == i + 1

        # Process input (earns 25 XP from QUEST_PROGRESS)
        result = engine.process_input(sid, f"Test question for quest {i+1}")
        assert result["type"] == "response"
        total_expected_xp += result["xp_gained"]

        # Advance quest (earns quest XP)
        advance = engine.advance_quest(sid)
        total_expected_xp += QUESTS[i]["xp"]

        if i < 4:
            assert advance["type"] == "quest_complete"
            assert advance["earned_badge"] == QUESTS[i]["badge"]
        else:
            assert advance["type"] == "game_over"
            assert len(advance["badges"]) == 5

    # Verify final state
    state = engine._get_state(sid)
    assert state.is_finished() is True
    assert state.total_xp == total_expected_xp
    assert len(state.badges) == 5


# ── PlayerState ───────────────────────────────────────────────────────────────

def test_player_state_current_quest():
    """PlayerState should return the correct current quest."""
    s = PlayerState("s1", "Test", "Delhi", "en")
    assert s.current_quest() == QUESTS[0]


def test_player_state_is_finished_when_all_done():
    """PlayerState with quest_index=5 should be finished."""
    s = PlayerState("s2", "Test", "Delhi", "en", quest_index=5)
    assert s.is_finished() is True


def test_player_state_not_finished_at_start():
    """New PlayerState should not be finished."""
    s = PlayerState("s3", "Test", "Delhi", "en")
    assert s.is_finished() is False


def test_player_state_no_quest_when_finished():
    """Finished PlayerState should return None for current_quest."""
    s = PlayerState("s4", "Test", "Delhi", "en", quest_index=5)
    assert s.current_quest() is None


# ── Leaderboard ───────────────────────────────────────────────────────────────

def test_leaderboard_records_on_completion(engine):
    """Leaderboard should record the player's score on game completion."""
    sid = "lb-test-sess"
    engine.new_game(sid, "Topscorer", "Rajasthan", "en")
    state = engine._get_state(sid)
    state.quest_index = 4       # last quest
    engine.advance_quest(sid)   # triggers _record_score
    scores = engine.get_top_scores()
    assert any(s["name"] == "Topscorer" for s in scores)


# ── Session Cleanup ──────────────────────────────────────────────────────────

def test_session_cleanup_removes_expired(engine):
    """_maybe_cleanup should remove sessions older than TTL."""
    # Create a session and make it expired
    engine.new_game("cleanup-test", "OldPlayer", "Delhi", "en")
    state = engine._get_state("cleanup-test")
    state.last_active = time.time() - 90000  # 25 hours ago (> 24h TTL)

    # Force cleanup by setting counter to threshold
    engine._cleanup_counter = 99
    engine._maybe_cleanup()

    # Session should be removed
    with pytest.raises(ValueError):
        engine._get_state("cleanup-test")


# ── Language Label Mapping ───────────────────────────────────────────────────

def test_language_label_mapping():
    """All 10 supported languages should map to labels."""
    for lang_code in LanguageCode:
        label = GameEngine._language_label(lang_code.value)
        assert label != "", f"Missing label for {lang_code.value}"
        assert isinstance(label, str)


def test_language_label_unknown_code():
    """Unknown language code should default to English."""
    label = GameEngine._language_label("xx")
    assert label == "English"


# ── Edge Cases ───────────────────────────────────────────────────────────────

def test_new_game_empty_name(engine):
    """Engine should handle empty player name without error."""
    state = engine.new_game("sess-empty", "", "Delhi", "en")
    assert state["player_name"] == ""


def test_advance_quest_out_of_bounds(engine):
    """Advancing past all quests should return an error."""
    sid = "out-of-bounds"
    engine.new_game(sid, "Test", "Delhi", "en")
    for _ in range(5):
        engine.advance_quest(sid)
    # 6th advance should return error
    result = engine.advance_quest(sid)
    assert result["type"] == "error"
    assert result["message"] == "Game already completed."


def test_process_input_on_completed_game(engine):
    """process_input on a completed game should return error."""
    sid = "completed-game"
    engine.new_game(sid, "Done", "Delhi", "en")
    state = engine._get_state(sid)
    state.quest_index = 5  # mark as finished
    result = engine.process_input(sid, "hello")
    assert result["type"] == "error"
