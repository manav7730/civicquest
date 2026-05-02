from dotenv import load_dotenv
import os
import pathlib

# Load .env with explicit path and override=True so it always takes effect
_env_path = pathlib.Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

import uuid
import logging
from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
from game_engine import GameEngine
from gemini_client import GeminiClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "civicquest-dev-key-change-in-prod")
CORS(app)

gemini = GeminiClient()
engine = GameEngine(gemini)

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html",
                           maps_api_key=os.environ.get("GOOGLE_MAPS_API_KEY", ""))

@app.route("/api/start", methods=["POST"])
def start_game():
    """Start a new game session for a player."""
    data = request.get_json() or {}
    player_name = data.get("name", "Citizen").strip()[:50]
    state_name  = data.get("state", "Gujarat").strip()
    language    = data.get("language", "en")

    session_id  = str(uuid.uuid4())
    game_state  = engine.new_game(session_id, player_name, state_name, language)

    return jsonify({"session_id": session_id, "game_state": game_state})

@app.route("/api/scene", methods=["POST"])
def get_scene():
    """Return the current quest scene narration from Gemini."""
    data       = request.get_json() or {}
    session_id = data.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    scene = engine.get_current_scene(session_id)
    return jsonify(scene)

@app.route("/api/answer", methods=["POST"])
def submit_answer():
    """Player submits an answer or chat message within a quest."""
    data       = request.get_json() or {}
    session_id = data.get("session_id")
    user_input = data.get("input", "").strip()

    if not session_id or not user_input:
        return jsonify({"error": "session_id and input are required"}), 400

    result = engine.process_input(session_id, user_input)
    return jsonify(result)

@app.route("/api/next_quest", methods=["POST"])
def next_quest():
    """Advance to the next quest after current is completed."""
    data       = request.get_json() or {}
    session_id = data.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    result = engine.advance_quest(session_id)
    return jsonify(result)

@app.route("/api/translate", methods=["POST"])
def translate_text():
    """Translate text using Google Translate API."""
    data       = request.get_json() or {}
    text       = data.get("text", "")
    target     = data.get("target_language", "en")

    from google.cloud import translate_v2 as translate
    client     = translate.Client()
    translated = client.translate(text, target_language=target)
    return jsonify({"translated_text": translated["translatedText"]})

@app.route("/api/booth_finder", methods=["POST"])
def booth_finder():
    """Return a Maps-ready address for a polling booth search."""
    data       = request.get_json() or {}
    address    = data.get("address", "")
    state      = data.get("state", "")
    search_query = f"polling booth election office {address} {state} India"
    return jsonify({"search_query": search_query,
                    "maps_url": f"https://maps.google.com/?q={search_query.replace(' ', '+')}"})

@app.route("/api/leaderboard", methods=["GET"])
def leaderboard():
    """Return top scores (stored in-memory for demo; swap for Firestore)."""
    scores = engine.get_top_scores(limit=10)
    return jsonify({"leaderboard": scores})

@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "CivicQuest"})

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
