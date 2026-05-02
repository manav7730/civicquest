from dotenv import load_dotenv
import os
import pathlib

# Load .env with explicit path and override=True so it always takes effect
_env_path = pathlib.Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

import uuid
import logging
import hashlib
import gzip
from io import BytesIO
from flask import Flask, request, jsonify, render_template, session, make_response, Response
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from google.cloud import translate_v2 as translate
from game_engine import GameEngine
from gemini_client import GeminiClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "civicquest-dev-key-change-in-prod")
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)
CORS(app, resources={r"/api/*": {"origins": os.environ.get("ALLOWED_ORIGIN", "*")}})

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

gemini = GeminiClient()
engine = GameEngine(gemini)

translate_client = None
def get_translate_client():
    global translate_client
    if translate_client is None:
        translate_client = translate.Client()
    return translate_client

# ── Middleware & Handlers ─────────────────────────────────────────────────────

@app.after_request
def after_request(response: Response) -> Response:
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    # Gzip compression
    accept_encoding = request.headers.get('Accept-Encoding', '')
    if 'gzip' in accept_encoding.lower() and response.status_code in (200, 201) and 'Content-Encoding' not in response.headers:
        response.direct_passthrough = False
        data = response.get_data()
        if len(data) > 500 and 'image' not in response.content_type:
            gzip_buffer = BytesIO()
            with gzip.GzipFile(mode='wb', fileobj=gzip_buffer) as gzip_file:
                gzip_file.write(data)
            response.set_data(gzip_buffer.getvalue())
            response.headers['Content-Encoding'] = 'gzip'
            response.headers['Content-Length'] = len(response.get_data())
    return response

@app.errorhandler(Exception)
def handle_exception(e: Exception):
    logger.error("Unhandled exception: %s", e, exc_info=True)
    if isinstance(e, ValueError):
        return jsonify({"error": str(e)}), 400
    return jsonify({"error": "Internal Server Error"}), 500

def validate_uuid(val: str) -> bool:
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
@limiter.exempt
def index() -> Response:
    resp = make_response(render_template("index.html",
                           maps_api_key=os.environ.get("GOOGLE_MAPS_API_KEY", "")))
    resp.headers['Cache-Control'] = 'public, max-age=3600'
    return resp

@app.route("/api/start", methods=["POST"])
@limiter.limit("10 per minute")
def start_game() -> Response:
    """Start a new game session for a player."""
    data = request.get_json() or {}
    player_name = data.get("name", "Citizen").strip()[:50]
    state_name  = data.get("state", "Gujarat").strip()[:50]
    language    = data.get("language", "en")[:10]

    session_id  = str(uuid.uuid4())
    game_state  = engine.new_game(session_id, player_name, state_name, language)

    return jsonify({"session_id": session_id, "game_state": game_state})

@app.route("/api/scene", methods=["POST"])
def get_scene() -> Response:
    """Return the current quest scene narration from Gemini."""
    data       = request.get_json() or {}
    session_id = data.get("session_id")
    if not session_id or not validate_uuid(session_id):
        return jsonify({"error": "valid session_id required"}), 400

    scene = engine.get_current_scene(session_id)
    return jsonify(scene)

@app.route("/api/answer", methods=["POST"])
@limiter.limit("20 per minute")
def submit_answer() -> Response:
    """Player submits an answer or chat message within a quest."""
    data       = request.get_json() or {}
    session_id = data.get("session_id")
    user_input = data.get("input", "").strip()

    if not session_id or not validate_uuid(session_id):
        return jsonify({"error": "valid session_id required"}), 400
    if not user_input:
        return jsonify({"error": "input is required"}), 400

    result = engine.process_input(session_id, user_input)
    return jsonify(result)

@app.route("/api/next_quest", methods=["POST"])
def next_quest() -> Response:
    """Advance to the next quest after current is completed."""
    data       = request.get_json() or {}
    session_id = data.get("session_id")
    if not session_id or not validate_uuid(session_id):
        return jsonify({"error": "valid session_id required"}), 400

    result = engine.advance_quest(session_id)
    return jsonify(result)

@app.route("/api/translate", methods=["POST"])
@limiter.limit("30 per minute")
def translate_text() -> Response:
    """Translate text using Google Translate API."""
    data       = request.get_json() or {}
    text       = data.get("text", "")
    target     = data.get("target_language", "en")[:10]

    if not text:
        return jsonify({"translated_text": ""})

    client = get_translate_client()
    translated = client.translate(text, target_language=target)
    return jsonify({"translated_text": translated["translatedText"]})

@app.route("/api/booth_finder", methods=["POST"])
@limiter.limit("10 per minute")
def booth_finder() -> Response:
    """Return a Maps-ready address for a polling booth search."""
    data       = request.get_json() or {}
    address    = data.get("address", "")[:100]
    state      = data.get("state", "")[:50]
    search_query = f"polling booth election office {address} {state} India"
    return jsonify({"search_query": search_query,
                    "maps_url": f"https://maps.google.com/?q={search_query.replace(' ', '+')}"})

@app.route("/api/leaderboard", methods=["GET"])
def leaderboard() -> Response:
    """Return top scores (stored in-memory for demo; swap for Firestore)."""
    scores = engine.get_top_scores(limit=10)
    resp = jsonify({"leaderboard": scores})
    # Add ETag based on scores content
    content_hash = hashlib.md5(str(scores).encode('utf-8')).hexdigest()
    resp.set_etag(content_hash)
    return resp

@app.route("/health")
@limiter.exempt
def health() -> Response:
    """Health check endpoint for Cloud Run."""
    resp = jsonify({"status": "ok", "service": "CivicQuest"})
    resp.headers['Cache-Control'] = 'public, max-age=60'
    return resp

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
