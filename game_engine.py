"""
game_engine.py — Quest logic, state management, and scoring.

Five quests walk the player through the entire Indian election cycle:
  Q1 Voter Registration  →  Q2 Know Your Constituency
  →  Q3 Election Timeline  →  Q4 Polling Day  →  Q5 Results & Democracy
"""

import time
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional
from gemini_client import GeminiClient

logger = logging.getLogger(__name__)

# ── Quest definitions ─────────────────────────────────────────────────────────

QUESTS = [
    {
        "id": "voter_registration",
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
        "id": "know_your_constituency",
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
        "id": "election_timeline",
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
        "id": "polling_day",
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
        "id": "results_democracy",
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
_leaderboard: list[dict] = []


# ── Game state ────────────────────────────────────────────────────────────────

@dataclass
class PlayerState:
    session_id: str
    player_name: str
    state_name: str
    language: str
    quest_index: int = 0
    total_xp: int = 0
    badges: list = field(default_factory=list)
    chat_history: list = field(default_factory=list)
    quest_completed: bool = False
    created_at: float = field(default_factory=time.time)

    def current_quest(self) -> Optional[dict]:
        if self.quest_index < len(QUESTS):
            return QUESTS[self.quest_index]
        return None

    def is_finished(self) -> bool:
        return self.quest_index >= len(QUESTS)


# ── Engine ────────────────────────────────────────────────────────────────────

class GameEngine:
    def __init__(self, gemini: GeminiClient):
        self.gemini = gemini
        self._sessions: dict[str, PlayerState] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def new_game(self, session_id: str, player_name: str,
                 state_name: str, language: str) -> dict:
        state = PlayerState(
            session_id=session_id,
            player_name=player_name,
            state_name=state_name,
            language=language,
        )
        self._sessions[session_id] = state
        logger.info("New game: %s (%s)", player_name, session_id[:8])
        return self._state_summary(state)

    def get_current_scene(self, session_id: str) -> dict:
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

    def process_input(self, session_id: str, user_input: str) -> dict:
        state = self._get_state(session_id)
        quest = state.current_quest()
        if not quest:
            return {"type": "error", "message": "Game already completed."}

        # Build the AI prompt with full knowledge context
        system_prompt = (
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

        # Maintain chat history per quest (last 6 turns)
        history = state.chat_history[-6:] if state.chat_history else []
        response_text = self.gemini.chat(system_prompt, history, user_input,
                                            knowledge=quest["knowledge"])

        # Detect progress signal
        quest_progressed = "[QUEST_PROGRESS]" in response_text
        clean_response   = response_text.replace("[QUEST_PROGRESS]", "").strip()

        # Update chat history
        state.chat_history.append({"role": "user",    "content": user_input})
        state.chat_history.append({"role": "assistant", "content": clean_response})

        # Award XP on progress (once per question, capped)
        xp_gained = 0
        if quest_progressed and not state.quest_completed:
            xp_gained = 25
            state.total_xp += xp_gained

        return {
            "type": "response",
            "response": clean_response,
            "xp_gained": xp_gained,
            "quest_progressed": quest_progressed,
            "game_state": self._state_summary(state),
        }

    def advance_quest(self, session_id: str) -> dict:
        state = self._get_state(session_id)
        quest = state.current_quest()
        if not quest:
            return {"type": "error", "message": "No active quest."}

        # Award quest XP and badge
        state.total_xp += quest["xp"]
        state.badges.append({
            "name": quest["badge"],
            "emoji": quest["badge_emoji"],
            "quest": quest["title"],
        })
        state.chat_history = []          # fresh history for next quest
        state.quest_completed = False
        state.quest_index += 1

        # Check game over
        if state.is_finished():
            self._record_score(state)
            return {
                "type": "game_over",
                "message": self._victory_message(state),
                "badges": state.badges,
                "total_xp": state.total_xp,
            }

        return {
            "type": "quest_complete",
            "earned_badge": quest["badge"],
            "earned_badge_emoji": quest["badge_emoji"],
            "xp_earned": quest["xp"],
            "game_state": self._state_summary(state),
        }

    def get_top_scores(self, limit: int = 10) -> list[dict]:
        return sorted(_leaderboard, key=lambda x: x["xp"], reverse=True)[:limit]

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_state(self, session_id: str) -> PlayerState:
        state = self._sessions.get(session_id)
        if not state:
            raise ValueError(f"Session not found: {session_id}")
        return state

    def _state_summary(self, state: PlayerState) -> dict:
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
        return (
            f"Congratulations, {state.player_name}! You have completed all 5 quests "
            f"and earned {state.total_xp} XP. You are now a true Democracy Champion! "
            f"You earned {len(state.badges)} badges: "
            + ", ".join(f"{b['emoji']} {b['name']}" for b in state.badges)
        )

    def _record_score(self, state: PlayerState):
        _leaderboard.append({
            "name": state.player_name,
            "state": state.state_name,
            "xp": state.total_xp,
            "badges": len(state.badges),
        })

    @staticmethod
    def _language_label(code: str) -> str:
        mapping = {
            "en": "English", "hi": "Hindi", "gu": "Gujarati",
            "ta": "Tamil",   "te": "Telugu", "mr": "Marathi",
            "bn": "Bengali", "kn": "Kannada", "ml": "Malayalam",
            "pa": "Punjabi",
        }
        return mapping.get(code, "English")
