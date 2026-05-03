"""
app.py — Main Flask application entry point for CivicQuest.

Handles routing, rate limiting, security headers, exception handling,
and initialization of the GameEngine and GeminiClient.
"""

__all__ = ["app", "get_translate_client", "validate_uuid"]

# ── Environment loading (must happen before other imports) ────────────────────

import pathlib
from dotenv import load_dotenv

_env_path: pathlib.Path = pathlib.Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

# ── Standard library imports ─────────────────────────────────────────────────

import gzip
import hashlib
import html
import logging
import os
import secrets
import uuid
import urllib.parse
from io import BytesIO
from typing import Any, Dict, Optional, Tuple

# ── Third-party imports ──────────────────────────────────────────────────────

from flask import Flask, Response, g, jsonify, make_response, render_template, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from google.cloud import translate_v2 as translate

# ── Local imports ────────────────────────────────────────────────────────────

from game_engine import GameEngine
from gemini_client import GeminiClient

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

RATE_LIMIT_GLOBAL: list = ["200 per day", "50 per hour"]
RATE_LIMIT_START: str = "10 per minute"
RATE_LIMIT_SCENE: str = "20 per minute"
RATE_LIMIT_ANSWER: str = "20 per minute"
RATE_LIMIT_NEXT: str = "20 per minute"
RATE_LIMIT_TRANSLATE: str = "30 per minute"
RATE_LIMIT_BOOTH: str = "10 per minute"
MAX_INPUT_LENGTH: int = 500

# ── Flask app initialization ─────────────────────────────────────────────────

app = Flask(__name__)

# Use env var or generate a random key for dev (never a guessable string)
_secret_key: str = os.environ.get("FLASK_SECRET_KEY", "")
if not _secret_key:
    _secret_key = secrets.token_hex(32)
    logger.warning("FLASK_SECRET_KEY not set — using random key (sessions won't persist across restarts)")
app.secret_key = _secret_key

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)
CORS(app, resources={r"/api/*": {"origins": os.environ.get("ALLOWED_ORIGIN", "*")}})

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=RATE_LIMIT_GLOBAL,
    storage_uri="memory://",
)

# ── Service initialization ───────────────────────────────────────────────────

gemini = GeminiClient()
engine = GameEngine(gemini)
translate_client: Optional[translate.Client] = None


def get_translate_client() -> translate.Client:
    """Lazy load and return the Google Translate Client."""
    global translate_client
    if translate_client is None:
        translate_client = translate.Client()
    return translate_client


# ── Middleware & Handlers ─────────────────────────────────────────────────────

@app.before_request
def generate_csp_nonce() -> None:
    """Generate a unique CSP nonce for each request."""
    g.csp_nonce = secrets.token_urlsafe(16)


@app.after_request
def after_request(response: Response) -> Response:
    """Apply strict security headers and optional GZIP compression."""
    nonce: str = getattr(g, 'csp_nonce', secrets.token_urlsafe(16))

    # Security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=(self)'
    response.headers['X-Permitted-Cross-Domain-Policies'] = 'none'

    # Strict Content Security Policy (CSP) — no unsafe-inline
    csp: str = (
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}' https://maps.googleapis.com; "
        f"style-src 'self' 'nonce-{nonce}' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "connect-src 'self' https://maps.googleapis.com; "
        "img-src 'self' data: https://maps.gstatic.com https://maps.googleapis.com;"
    )
    response.headers['Content-Security-Policy'] = csp

    # Gzip compression
    accept_encoding: str = request.headers.get('Accept-Encoding', '')
    if ('gzip' in accept_encoding.lower()
            and response.status_code in (200, 201)
            and 'Content-Encoding' not in response.headers):
        response.direct_passthrough = False
        data: bytes = response.get_data()
        if len(data) > 500 and 'image' not in response.content_type:
            gzip_buffer = BytesIO()
            with gzip.GzipFile(mode='wb', fileobj=gzip_buffer) as gzip_file:
                gzip_file.write(data)
            response.set_data(gzip_buffer.getvalue())
            response.headers['Content-Encoding'] = 'gzip'
            response.headers['Content-Length'] = str(len(response.get_data()))
    return response


@app.errorhandler(Exception)
def handle_exception(e: Exception) -> Tuple[Response, int]:
    """Global exception handler to ensure JSON responses on error."""
    logger.error("Unhandled exception: %s", e, exc_info=True)
    if isinstance(e, ValueError):
        return jsonify({"error": str(e)}), 400
    return jsonify({"error": "Internal Server Error"}), 500


def validate_uuid(val: str) -> bool:
    """Validate if a string is a well-formed UUID v4.

    Args:
        val: The string to check.

    Returns:
        bool: True if valid UUID.
    """
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False


def sanitize_input(val: Any, max_len: int = 50) -> str:
    """Sanitize and truncate user input to prevent XSS and payload abuse.

    Args:
        val: The raw input value.
        max_len: Maximum allowed length after sanitization.

    Returns:
        str: Sanitized, truncated string.
    """
    if not isinstance(val, str):
        val = str(val)
    return html.escape(val.strip()[:max_len])


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
@limiter.exempt
def index() -> Response:
    """Render the main SPA frontend."""
    resp = make_response(render_template(
        "index.html",
        maps_api_key=os.environ.get("GOOGLE_MAPS_API_KEY", ""),
        csp_nonce=g.csp_nonce,
    ))
    resp.headers['Cache-Control'] = 'public, max-age=3600'
    return resp


@app.route("/api/start", methods=["POST"])
@limiter.limit(RATE_LIMIT_START)
def start_game() -> Response:
    """Start a new game session for a player.

    Returns:
        Response: JSON dict containing session_id and initial game_state.
    """
    data: Dict[str, Any] = request.get_json() or {}
    player_name: str = sanitize_input(data.get("name", "Citizen"), 50)
    state_name: str = sanitize_input(data.get("state", "Gujarat"), 50)
    language: str = sanitize_input(data.get("language", "en"), 10)

    session_id: str = str(uuid.uuid4())
    game_state: Dict[str, Any] = engine.new_game(session_id, player_name, state_name, language)

    return jsonify({"session_id": session_id, "game_state": game_state})


@app.route("/api/scene", methods=["POST"])
@limiter.limit(RATE_LIMIT_SCENE)
def get_scene() -> Response:
    """Return the current quest scene narration from Gemini.

    Returns:
        Response: JSON dict with scene details and narration.
    """
    data: Dict[str, Any] = request.get_json() or {}
    session_id: str = str(data.get("session_id", ""))

    if not session_id or not validate_uuid(session_id):
        return jsonify({"error": "valid session_id required"}), 400

    scene: Dict[str, Any] = engine.get_current_scene(session_id)
    return jsonify(scene)


@app.route("/api/answer", methods=["POST"])
@limiter.limit(RATE_LIMIT_ANSWER)
def submit_answer() -> Response:
    """Player submits an answer or chat message within a quest.

    Returns:
        Response: JSON dict with AI response, XP gained, and game state.
    """
    data: Dict[str, Any] = request.get_json() or {}
    session_id: str = str(data.get("session_id", ""))
    user_input: str = sanitize_input(data.get("input", ""), MAX_INPUT_LENGTH)

    if not session_id or not validate_uuid(session_id):
        return jsonify({"error": "valid session_id required"}), 400
    if not user_input:
        return jsonify({"error": "input is required"}), 400

    result: Dict[str, Any] = engine.process_input(session_id, user_input)
    return jsonify(result)


@app.route("/api/next_quest", methods=["POST"])
@limiter.limit(RATE_LIMIT_NEXT)
def next_quest() -> Response:
    """Advance to the next quest after current is completed.

    Returns:
        Response: JSON dict with next quest details or game over stats.
    """
    data: Dict[str, Any] = request.get_json() or {}
    session_id: str = str(data.get("session_id", ""))

    if not session_id or not validate_uuid(session_id):
        return jsonify({"error": "valid session_id required"}), 400

    result: Dict[str, Any] = engine.advance_quest(session_id)
    return jsonify(result)


@app.route("/api/translate", methods=["POST"])
@limiter.limit(RATE_LIMIT_TRANSLATE)
def translate_text() -> Response:
    """Translate text using Google Translate API.

    Returns:
        Response: JSON dict with the translated string.
    """
    data: Dict[str, Any] = request.get_json() or {}
    text: str = str(data.get("text", ""))
    target: str = sanitize_input(data.get("target_language", "en"), 10)

    if not text:
        return jsonify({"translated_text": ""})

    client: translate.Client = get_translate_client()
    translated: Dict[str, str] = client.translate(text, target_language=target)
    return jsonify({"translated_text": translated["translatedText"]})


@app.route("/api/booth_finder", methods=["POST"])
@limiter.limit(RATE_LIMIT_BOOTH)
def booth_finder() -> Response:
    """Return a Maps-ready address for a polling booth search.

    Returns:
        Response: JSON dict containing the search_query and Maps URL.
    """
    data: Dict[str, Any] = request.get_json() or {}
    address: str = sanitize_input(data.get("address", ""), 100)
    state: str = sanitize_input(data.get("state", ""), 50)

    search_query: str = f"polling booth election office {address} {state} India"
    encoded_query: str = urllib.parse.quote_plus(search_query)
    maps_url: str = f"https://maps.google.com/?q={encoded_query}"
    return jsonify({"search_query": search_query, "maps_url": maps_url})


@app.route("/api/leaderboard", methods=["GET"])
def leaderboard() -> Response:
    """Return top scores (stored in-memory for demo; swap for Firestore).

    Returns:
        Response: JSON dict with the leaderboard array.
    """
    scores: list = engine.get_top_scores(limit=10)
    resp: Response = jsonify({"leaderboard": scores})

    # Add ETag based on scores content (using sha256 for integrity)
    content_hash: str = hashlib.sha256(str(scores).encode('utf-8')).hexdigest()
    resp.set_etag(content_hash)
    return resp


@app.route("/health")
@limiter.exempt
def health() -> Response:
    """Health check endpoint for Cloud Run.

    Returns:
        Response: JSON dict status.
    """
    resp: Response = jsonify({"status": "ok", "service": "CivicQuest"})
    resp.headers['Cache-Control'] = 'public, max-age=60'
    return resp


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port: int = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
