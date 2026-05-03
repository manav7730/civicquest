"""
gemini_client.py — Thin wrapper around Google Gemini API (google-generativeai SDK).

Includes retry logic with exponential backoff for free-tier 429 rate limits,
a small inter-call delay, and knowledge-based fallback answers.
"""

__all__ = ["GeminiClient"]

import os
import time
import logging
import pathlib
from typing import Callable, Any, List, Dict, Optional

from dotenv import dotenv_values
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

# Retry / throttle settings
MAX_RETRIES: int    = 3      # max retry attempts on 429
RETRY_BASE_SEC: int = 5      # initial back-off wait (doubles each retry)
CALL_DELAY_SEC: int = 1      # minimum gap between any two API calls

# Generation settings
MAX_OUTPUT_TOKENS: int = 512
TEMPERATURE: float     = 0.7

# Pre-load .env values as a fallback in case load_dotenv wasn't called yet
_env_path: pathlib.Path = pathlib.Path(__file__).resolve().parent / ".env"
_env_vals: Dict[str, Optional[str]] = dotenv_values(_env_path)


class GeminiClient:
    """Wrapper for the Gemini API handling retries, rate limits, and fallback knowledge."""
    
    def __init__(self) -> None:
        """Initialize the Gemini client and API key."""
        # Try os.environ first, fall back to reading .env directly
        api_key: Optional[str] = os.environ.get("GEMINI_API_KEY") or _env_vals.get("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY not set — responses will be mocked.")
        self._client = genai.Client(api_key=api_key or "MISSING")
        self._last_call_ts: float = 0.0   # timestamp of last API call

    # ── internal helpers ─────────────────────────────────────────────────────

    def _throttle(self) -> None:
        """Enforce a minimum delay between consecutive API calls."""
        elapsed = time.time() - self._last_call_ts
        if elapsed < CALL_DELAY_SEC:
            time.sleep(CALL_DELAY_SEC - elapsed)

    @staticmethod
    def _is_rate_limit(exc: Exception) -> bool:
        """Return True if the exception is a 429 / resource-exhausted error.
        
        Args:
            exc: The exception thrown by the API call.
            
        Returns:
            bool: True if rate limit, False otherwise.
        """
        msg = str(exc).lower()
        return "429" in msg or ("resource" in msg and "exhausted" in msg)

    def _build_fallback_generate(self, knowledge: str) -> str:
        """Return a scene-like narrative built from quest knowledge.
        
        Args:
            knowledge: Educational context for the fallback response.
            
        Returns:
            str: Fallback string.
        """
        if knowledge:
            return (
                f"⚔ Desh steps forward and shares some wisdom:\n\n"
                f"{knowledge}\n\n"
                f"(The AI narrator is resting — this answer comes from the quest "
                f"knowledge base.)"
            )
        return "The adventure begins... (AI narrator temporarily unavailable)"

    def _build_fallback_chat(self, knowledge: str, user_message: str) -> str:
        """Return a helpful answer derived from quest knowledge.
        
        Args:
            knowledge: Educational context for the fallback response.
            user_message: The user's input.
            
        Returns:
            str: Fallback string.
        """
        if knowledge:
            return (
                f"Great question, brave citizen! Here's what Desh knows:\n\n"
                f"{knowledge}\n\n"
                f"(Desh answered from the quest knowledge base because the AI guide "
                f"is resting. Ask more questions to keep exploring!) [QUEST_PROGRESS]"
            )
        return (
            "Great question, brave citizen! The AI guide is temporarily resting — "
            "please try again in a moment. [QUEST_PROGRESS]"
        )

    def _with_retry(self, operation: str, api_call: Callable[[], Any], fallback: Callable[[], str]) -> str:
        """Execute an API call with exponential backoff on 429 errors.
        
        Args:
            operation: Name of the operation (for logging).
            api_call: Lambda or function executing the actual API call.
            fallback: Function returning a fallback string if all retries fail.
            
        Returns:
            str: API response text or fallback string.
        """
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                self._throttle()
                response = api_call()
                self._last_call_ts = time.time()
                logger.info("Gemini %s succeeded (attempt %d/%d)", operation, attempt, MAX_RETRIES)
                return str(response.text).strip()
            except Exception as e:
                self._last_call_ts = time.time()
                if self._is_rate_limit(e) and attempt < MAX_RETRIES:
                    wait = RETRY_BASE_SEC * (2 ** (attempt - 1))
                    logger.warning(
                        "Gemini 429 on %s (attempt %d/%d) — retrying in %ds",
                        operation, attempt, MAX_RETRIES, wait,
                    )
                    time.sleep(wait)
                    continue
                logger.error("Gemini %s error (attempt %d/%d): %s",
                             operation, attempt, MAX_RETRIES, e)
                return fallback()

        return fallback()

    # ── public API ───────────────────────────────────────────────────────────

    def generate(self, prompt: str, knowledge: str = "") -> str:
        """Single-turn generation (scene narration) with retry and fallback.
        
        Args:
            prompt: Instruction for generation.
            knowledge: Knowledge base to fall back on.
            
        Returns:
            str: Generated text.
        """
        def make_call() -> Any:
            return self._client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                    temperature=TEMPERATURE,
                ),
            )
        
        def make_fallback() -> str:
            return self._build_fallback_generate(knowledge)
            
        return self._with_retry("generate", make_call, make_fallback)

    def chat(self, system_prompt: str, history: List[Dict[str, str]],
             user_message: str, knowledge: str = "") -> str:
        """Multi-turn chat with retry, backoff, and knowledge fallback.
        
        Args:
            system_prompt: System instruction.
            history: List of role/content dictionaries.
            user_message: The user's input.
            knowledge: Knowledge base to fall back on.
            
        Returns:
            str: Chat response.
        """
        def make_call() -> Any:
            gemini_history: List[types.Content] = []
            for turn in history:
                role = "model" if turn["role"] == "assistant" else "user"
                gemini_history.append(
                    types.Content(role=role, parts=[types.Part(text=turn["content"])])
                )

            return self._client.models.generate_content(
                model=GEMINI_MODEL,
                contents=gemini_history + [
                    types.Content(role="user", parts=[types.Part(text=user_message)])
                ],
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                    temperature=TEMPERATURE,
                ),
            )
            
        def make_fallback() -> str:
            return self._build_fallback_chat(knowledge, user_message)

        return self._with_retry("chat", make_call, make_fallback)
