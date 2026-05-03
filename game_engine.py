"""
game_engine.py — Quest logic, state management, and scoring.

Five quests walk the player through the entire Indian election cycle:
  Q1 Voter Registration  →  Q2 Know Your Constituency
  →  Q3 Election Timeline  →  Q4 Polling Day  →  Q5 Results & Democracy
"""

__all__ = ["GameEngine", "PlayerState", "LanguageCode", "QuestID"]

import time
import logging
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from gemini_client import GeminiClient

logger = logging.getLogger(__name__)

# Constants
SESSION_TTL_SECONDS: int = 86400  # 24 hours
MAX_CHAT_HISTORY: int = 6
XP_PER_PROGRESS: int = 25
CLEANUP_INTERVAL: int = 100

class LanguageCode(str, Enum):
    """Enumeration of supported language codes."""
    ENGLISH = "en"
    HINDI = "hi"
    GUJARATI = "gu"
    TAMIL = "ta"
    TELUGU = "te"
    MARATHI = "mr"
    BENGALI = "bn"
    KANNADA = "kn"
    MALAYALAM = "ml"
    PUNJABI = "pa"

class QuestID(str, Enum):
    """Enumeration of the 5 main quests."""
    VOTER_REGISTRATION = "voter_registration"
    KNOW_YOUR_CONSTITUENCY = "know_your_constituency"
    ELECTION_TIMELINE = "election_timeline"
    POLLING_DAY = "polling_day"
    RESULTS_DEMOCRACY = "results_democracy"


# ── Quest definitions ─────────────────────────────────────────────────────────

QUESTS: List[Dict[str, Any]] = [
    {
        "id": QuestID.VOTER_REGISTRATION.value,
        "title": "Quest 1: The Voter's Journey Begins",
        "subtitle": "Get your Voter ID",
        "badge": "Registered Citizen",
        "badge_emoji": "📋",
        "xp": 100,
        "topic": "voter registration in India",
        "scene_prompt": (
            "You are a friendly guide named 'Desh', helping {player} from {state} "
            "understand how to register as a voter in India. Write a short engaging "
            "scene (3-4 sentences) where Desh greets the player at a government office "
            "and explains that their adventure to become a true democratic citizen begins here. "
            "Mention EPIC card and voter list. Keep it exciting and simple. Language: {language}."
        ),
        "questions": [
            "What is the minimum age to vote in India?",
            "What is an EPIC card?",
            "How can I check if my name is on the voter list?",
            "What documents do I need to register as a voter?",
        ],
        "knowledge": (
            "In India, citizens must be 18+ to vote. The EPIC (Electors Photo Identity Card) "
            "is the official Voter ID card. Citizens can register on the National Voter's Service "
            "Portal (NVSP) or the Voter Helpline App. Form 6 is used for new voter registration. "
            "The Electoral Roll (voter list) is managed by the Election Commission of India (ECI). "
            "You can check your name on voterportal.eci.gov.in or call helpline 1950."
        ),
    },
    {
        "id": QuestID.KNOW_YOUR_CONSTITUENCY.value,
        "title": "Quest 2: Know Your Battlefield",
        "subtitle": "Understand constituencies",
        "badge": "Constituency Scholar",
        "badge_emoji": "🗺️",
        "xp": 150,
        "topic": "Indian election constituencies and types of elections",
        "scene_prompt": (
            "Continue the story for {player} from {state}. Guide Desh now takes the player "
            "to a giant map of India. Write a scene (3-4 sentences) explaining Lok Sabha vs "
            "Vidhan Sabha, what a constituency is, and why knowing your constituency matters. "
            "Make it feel like an adventure map in a game. Language: {language}."
        ),
        "questions": [
            "What is the difference between Lok Sabha and Vidhan Sabha?",
            "How many Lok Sabha seats are there in total?",
            "What is a constituency?",
            "Who is an MLA and who is an MP?",
        ],
        "knowledge": (
            "India has two main election types: Lok Sabha (Parliament, 543 seats, national govt) "
            "and Vidhan Sabha (State Assembly, seats vary by state). A constituency is a geographic "
            "area represented by one elected member. Lok Sabha members are called MPs "
            "(Members of Parliament). State assembly members are called MLAs (Members of Legislative "
            "Assembly). Rajya Sabha members are indirectly elected. Gujarat has 26 Lok Sabha and "
            "182 Vidhan Sabha seats. Delimitation Commission decides constituency boundaries."
        ),
    },
    {
        "id": QuestID.ELECTION_TIMELINE.value,
        "title": "Quest 3: The Election Calendar",
        "subtitle": "From announcement to results",
        "badge": "Election Analyst",
        "badge_emoji": "📅",
        "xp": 200,
        "topic": "Indian election process, phases, Model Code of Conduct, nomination",
        "scene_prompt": (
            "Continue the adventure for {player} from {state}. Desh now shows a magical timeline "
            "scroll. Write a scene (3-4 sentences) describing the election announcement, Model Code "
            "of Conduct (MCC), nomination filing, campaigning phase, and the silence period. "
            "Use dramatic quest-like language. Language: {language}."
        ),
        "questions": [
            "What is the Model Code of Conduct?",
            "How many phases did the 2024 Lok Sabha election have?",
            "What is the election silence period?",
            "How are candidates nominated?",
        ],
        "knowledge": (
            "Indian elections have multiple phases (2024 Lok Sabha had 7 phases across 44 days). "
            "The Model Code of Conduct (MCC) kicks in when ECI announces election dates — "
            "political parties must follow rules of fair conduct. Candidates file nomination papers "
            "and pay a security deposit (₹25,000 for Lok Sabha). Campaigns must stop 48 hours "
            "before polling (silence period). The ECI uses Systematic Voters' Education and "
            "Electoral Participation (SVEEP) to encourage voting."
        ),
    },
    {
        "id": QuestID.POLLING_DAY.value,
        "title": "Quest 4: The Big Day",
        "subtitle": "Inside the polling booth",
        "badge": "Polling Expert",
        "badge_emoji": "🗳️",
        "xp": 250,
        "topic": "Indian election day process, EVM, VVPAT, voting procedure",
        "scene_prompt": (
            "The most important day for {player} from {state}! Desh walks the player through the "
            "gates of a polling booth on election day. Write an exciting scene (3-4 sentences) "
            "explaining: showing voter ID at the gate, getting ink on the finger, using the EVM "
            "(Electronic Voting Machine), and the VVPAT slip. Make the player feel like a hero. "
            "Language: {language}."
        ),
        "questions": [
            "What is an EVM?",
            "What is VVPAT and why is it important?",
            "Why is ink applied on the finger after voting?",
            "What documents can I use at the polling booth instead of EPIC?",
        ],
        "knowledge": (
            "EVM (Electronic Voting Machine) replaced paper ballots in India. It has two units: "
            "Control Unit (with Presiding Officer) and Balloting Unit (with voter). "
            "VVPAT (Voter Verified Paper Audit Trail) shows the voter a paper slip with their vote "
            "for 7 seconds before it drops into a sealed box — this ensures transparency. "
            "Indelible ink on the left index finger prevents duplicate voting. "
            "12 alternative IDs are accepted at polling booths including Aadhaar, passport, "
            "driving licence, PAN card, and MNREGS job card."
        ),
    },
    {
        "id": QuestID.RESULTS_DEMOCRACY.value,
        "title": "Quest 5: Democracy Wins!",
        "subtitle": "Counting day and beyond",
        "badge": "Democracy Champion",
        "badge_emoji": "🏆",
        "xp": 300,
        "topic": "Indian election results, counting, government formation",
        "scene_prompt": (
            "Final quest for {player} from {state}! Desh leads the player to the counting centre "
            "on results day. Write a triumphant scene (3-4 sentences) explaining how votes are "
            "counted, what a majority is (272 for Lok Sabha), how the President invites the leader "
            "to form government, and how {player} as a voter made this all possible. "
            "Make it feel like the end of an epic quest — very emotional and proud. Language: {language}."
        ),
        "questions": [
            "How are EVM votes counted on results day?",
            "How many seats are needed for a majority in Lok Sabha?",
            "Who invites the winning party to form the government?",
            "What happens if no party gets a majority?",
        ],
        "knowledge": (
            "Vote counting happens at Returning Officer centres on counting day. EVMs are unsealed "
            "and votes counted round by round. 272 seats (out of 543) is the majority mark for "
            "Lok Sabha. The President of India invites the leader of the majority party/coalition "
            "to form the government. If no single party gets majority, a hung parliament is formed "
            "and coalition talks begin. The winning party's leader becomes Prime Minister. "
            "State election results follow similar rules with the Governor's role instead of President."
        ),
    },
]

# ── Scoring ───────────────────────────────────────────────────────────────────

# In-memory leaderboard (replace with Firestore in production)
_leaderboard: List[Dict[str, Any]] = []
_leaderboard_lock: threading.Lock = threading.Lock()

# ── Game state ────────────────────────────────────────────────────────────────

@dataclass(slots=True)
class PlayerState:
    """Represents a player's progression and state during the game."""
    session_id: str
    player_name: str
    state_name: str
    language: str
    quest_index: int = 0
    total_xp: int = 0
    badges: List[Dict[str, str]] = field(default_factory=list)
    chat_history: List[Dict[str, str]] = field(default_factory=list)
    quest_completed: bool = False
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)

    def current_quest(self) -> Optional[Dict[str, Any]]:
        """Returns the dictionary for the player's current quest."""
        if self.quest_index < len(QUESTS):
            return QUESTS[self.quest_index]
        return None

    def is_finished(self) -> bool:
        """Returns True if the player has completed all quests."""
        return self.quest_index >= len(QUESTS)


# ── Engine ────────────────────────────────────────────────────────────────────

class GameEngine:
    """Core engine to manage user sessions and route LLM prompts."""

    def __init__(self, gemini: GeminiClient) -> None:
        self.gemini: GeminiClient = gemini
        self._sessions: Dict[str, PlayerState] = {}
        self._session_lock: threading.Lock = threading.Lock()
        self._cleanup_counter: int = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def new_game(self, session_id: str, player_name: str,
                 state_name: str, language: str) -> Dict[str, Any]:
        """Initialize a new game state for a player and store it in-memory.
        
        Args:
            session_id: The UUID representing the session.
            player_name: The user's name.
            state_name: The user's geographic state.
            language: The user's requested language.
            
        Returns:
            Dict[str, Any]: A summary of the newly created game state.
        """
        self._maybe_cleanup()
        
        # Enforce valid LanguageCode or default to English
        try:
            lang_code = LanguageCode(language).value
        except ValueError:
            lang_code = LanguageCode.ENGLISH.value

        state = PlayerState(
            session_id=session_id,
            player_name=player_name,
            state_name=state_name,
            language=lang_code,
        )
        
        # Lock acquired before modifying the shared _sessions dictionary
        with self._session_lock:
            self._sessions[session_id] = state
        logger.info("New game: %s (%s)", player_name, session_id[:8])
        return self._state_summary(state)

    def get_current_scene(self, session_id: str) -> Dict[str, Any]:
        """Retrieve the quest scene text from the Gemini model.
        
        Args:
            session_id: The active session UUID.
            
        Returns:
            Dict[str, Any]: Scene JSON including the narration and suggested questions.
        """
        state = self._get_state(session_id)
        quest = state.current_quest()
        if not quest:
            return {"type": "game_over", "message": self._victory_message(state)}

        prompt = quest["scene_prompt"].format(
            player=state.player_name,
            state=state.state_name,
            language=self._language_label(state.language),
        )
        narration = self.gemini.generate(prompt, knowledge=quest["knowledge"])

        # Add opening question suggestions
        questions = quest["questions"]

        return {
            "type": "scene",
            "quest_id": quest["id"],
            "quest_title": quest["title"],
            "quest_subtitle": quest["subtitle"],
            "narration": narration,
            "suggested_questions": questions,
            "xp_reward": quest["xp"],
            "badge": quest["badge"],
            "badge_emoji": quest["badge_emoji"],
            "quest_number": state.quest_index + 1,
            "total_quests": len(QUESTS),
            "game_state": self._state_summary(state),
        }

    def process_input(self, session_id: str, user_input: str) -> Dict[str, Any]:
        """Process a user's answer/question and pass it to Gemini.
        
        Args:
            session_id: The active session UUID.
            user_input: The user's submitted string.
            
        Returns:
            Dict[str, Any]: JSON including the AI response and XP gained.
        """
        state = self._get_state(session_id)
        quest = state.current_quest()
        if not quest:
            return {"type": "error", "message": "Game already completed."}

        system_prompt = self._build_system_prompt(state, quest)
        history = state.chat_history[-MAX_CHAT_HISTORY:] if state.chat_history else []
        
        response_text = self.gemini.chat(system_prompt, history, user_input, knowledge=quest["knowledge"])

        # Detect progress signal
        quest_progressed = "[QUEST_PROGRESS]" in response_text
        clean_response   = response_text.replace("[QUEST_PROGRESS]", "").strip()

        self._update_chat_history(state, user_input, clean_response)
        xp_gained = self._evaluate_progress(state, quest_progressed)

        return {
            "type": "response",
            "response": clean_response,
            "xp_gained": xp_gained,
            "quest_progressed": quest_progressed,
            "game_state": self._state_summary(state),
        }

    def advance_quest(self, session_id: str) -> Dict[str, Any]:
        """Move the player state to the next quest.
        
        Args:
            session_id: The active session UUID.
            
        Returns:
            Dict[str, Any]: JSON dict containing the earned badge or a game over notice.
        """
        state = self._get_state(session_id)
        if state.is_finished():
            return {"type": "error", "message": "Game already completed."}
            
        quest = state.current_quest()
        if not quest:
            return {"type": "error", "message": "No active quest."}

        self._award_quest_rewards(state, quest)
        
        game_over = self._check_game_over(state)
        if game_over:
            return game_over

        return {
            "type": "quest_complete",
            "earned_badge": quest["badge"],
            "earned_badge_emoji": quest["badge_emoji"],
            "xp_earned": quest["xp"],
            "game_state": self._state_summary(state),
        }

    def get_top_scores(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return the top scores from the in-memory leaderboard.
        
        Args:
            limit: Maximum number of scores to return.
            
        Returns:
            List[Dict[str, Any]]: The leaderboard list.
        """
        with _leaderboard_lock:
            return sorted(_leaderboard, key=lambda x: x["xp"], reverse=True)[:limit]

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_system_prompt(self, state: PlayerState, quest: Dict[str, Any]) -> str:
        """Helper to construct the prompt string for the Gemini Chat engine."""
        return (
            f"You are Desh, an enthusiastic election guide helping {state.player_name} from "
            f"{state.state_name} understand Indian elections through an RPG adventure. "
            f"Current quest topic: {quest['topic']}. "
            f"Knowledge base: {quest['knowledge']} "
            f"Rules: Answer only election-related questions. Keep answers to 3-5 sentences. "
            f"Be encouraging and use quest/adventure language. "
            f"If the answer is correct or the player asks a good question, end with: "
            f"'[QUEST_PROGRESS]' to signal progress. "
            f"Respond in: {self._language_label(state.language)}."
        )

    def _update_chat_history(self, state: PlayerState, user_input: str, clean_response: str) -> None:
        """Helper to append user and model replies to the state."""
        state.chat_history.append({"role": "user", "content": user_input})
        state.chat_history.append({"role": "assistant", "content": clean_response})

    def _evaluate_progress(self, state: PlayerState, quest_progressed: bool) -> int:
        """Helper to calculate and award XP for answering questions correctly."""
        xp_gained = 0
        if quest_progressed and not state.quest_completed:
            xp_gained = XP_PER_PROGRESS
            state.total_xp += xp_gained
        return xp_gained

    def _award_quest_rewards(self, state: PlayerState, quest: Dict[str, Any]) -> None:
        """Helper to give the player XP and badges upon quest completion."""
        state.total_xp += quest["xp"]
        state.badges.append({
            "name": quest["badge"],
            "emoji": quest["badge_emoji"],
            "quest": quest["title"],
        })
        state.chat_history = []          # fresh history for next quest
        state.quest_completed = False
        state.quest_index += 1

    def _check_game_over(self, state: PlayerState) -> Optional[Dict[str, Any]]:
        """Helper to record the score and return game over JSON if no more quests remain."""
        if state.is_finished():
            self._record_score(state)
            return {
                "type": "game_over",
                "message": self._victory_message(state),
                "badges": state.badges,
                "total_xp": state.total_xp,
            }
        return None

    def _get_state(self, session_id: str) -> PlayerState:
        """Fetch the PlayerState object by session UUID."""
        with self._session_lock:
            state = self._sessions.get(session_id)
        if not state:
            raise ValueError(f"Session not found: {session_id}")
        state.last_active = time.time()
        return state

    def _maybe_cleanup(self) -> None:
        """Periodically remove old sessions to free memory based on SESSION_TTL_SECONDS."""
        self._cleanup_counter += 1
        if self._cleanup_counter < CLEANUP_INTERVAL:
            return
        self._cleanup_counter = 0
        now = time.time()
        
        # Lock acquired before iterating and mutating the global session store
        with self._session_lock:
            to_remove = [sid for sid, state in self._sessions.items() 
                         if now - state.last_active > SESSION_TTL_SECONDS]
            for sid in to_remove:
                del self._sessions[sid]
        if to_remove:
            logger.info("Cleaned up %d inactive sessions", len(to_remove))

    def _state_summary(self, state: PlayerState) -> Dict[str, Any]:
        """Generate a summarized dict of the player state for JSON transmission."""
        quest = state.current_quest()
        return {
            "player_name": state.player_name,
            "state_name": state.state_name,
            "language": state.language,
            "quest_index": state.quest_index,
            "total_quests": len(QUESTS),
            "total_xp": state.total_xp,
            "badges": state.badges,
            "current_quest_title": quest["title"] if quest else "Complete!",
            "is_finished": state.is_finished(),
            "progress_pct": int((state.quest_index / len(QUESTS)) * 100),
        }

    def _victory_message(self, state: PlayerState) -> str:
        """Generate the final congratulatory message for the user."""
        return (
            f"Congratulations, {state.player_name}! You have completed all 5 quests "
            f"and earned {state.total_xp} XP. You are now a true Democracy Champion! "
            f"You earned {len(state.badges)} badges: "
            + ", ".join(f"{b['emoji']} {b['name']}" for b in state.badges)
        )

    def _record_score(self, state: PlayerState) -> None:
        """Append the final score to the shared in-memory leaderboard."""
        with _leaderboard_lock:
            _leaderboard.append({
                "name": state.player_name,
                "state": state.state_name,
                "xp": state.total_xp,
                "badges": len(state.badges),
            })

    @staticmethod
    def _language_label(code: str) -> str:
        """Map language string codes to their English display names."""
        mapping = {
            LanguageCode.ENGLISH.value: "English", 
            LanguageCode.HINDI.value: "Hindi", 
            LanguageCode.GUJARATI.value: "Gujarati",
            LanguageCode.TAMIL.value: "Tamil",   
            LanguageCode.TELUGU.value: "Telugu", 
            LanguageCode.MARATHI.value: "Marathi",
            LanguageCode.BENGALI.value: "Bengali", 
            LanguageCode.KANNADA.value: "Kannada", 
            LanguageCode.MALAYALAM.value: "Malayalam",
            LanguageCode.PUNJABI.value: "Punjabi",
        }
        return mapping.get(code, "English")
