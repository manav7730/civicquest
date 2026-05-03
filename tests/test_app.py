"""
tests/test_app.py — Flask route and middleware tests.

Tests cover: health endpoint, index page, game start, session validation,
security headers, input validation, translation, and booth finder.
"""

import json

import pytest
from unittest.mock import patch

from app import app, validate_uuid


@pytest.fixture
def client():
    """Create a Flask test client with rate limiting disabled."""
    app.config["TESTING"] = True
    app.config["RATELIMIT_ENABLED"] = False
    with app.test_client() as test_client:
        yield test_client


# ── Health & Index ────────────────────────────────────────────────────────────

def test_health_endpoint(client):
    """Health endpoint should return status ok with cache headers."""
    response = client.get("/health")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "ok"
    assert "Cache-Control" in response.headers


def test_index_page(client):
    """Index page should render with CivicQuest content."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"CivicQuest" in response.data


# ── Game Start ────────────────────────────────────────────────────────────────

def test_api_start_game(client):
    """Starting a game should return session_id and game_state."""
    response = client.post("/api/start", json={
        "name": "Test User",
        "state": "Delhi",
        "language": "en"
    })
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "session_id" in data
    assert "game_state" in data
    assert data["game_state"]["player_name"] == "Test User"


def test_api_start_game_default_values(client):
    """Starting a game with no data should use default values."""
    response = client.post("/api/start", json={})
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["game_state"]["player_name"] == "Citizen"


# ── Session Validation ───────────────────────────────────────────────────────

def test_invalid_session_id(client):
    """Invalid session_id should return 400."""
    response = client.post("/api/scene", json={"session_id": "invalid-uuid"})
    assert response.status_code == 400


def test_missing_session_id(client):
    """Missing session_id should return 400."""
    response = client.post("/api/scene", json={})
    assert response.status_code == 400


# ── Security Headers ─────────────────────────────────────────────────────────

def test_security_headers(client):
    """Response should contain all required security headers."""
    response = client.get("/")
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Permissions-Policy" in response.headers
    assert "X-Permitted-Cross-Domain-Policies" in response.headers


def test_csp_header_no_unsafe_inline(client):
    """CSP header should use nonces, not unsafe-inline."""
    response = client.get("/")
    csp = response.headers.get("Content-Security-Policy", "")
    assert "unsafe-inline" not in csp
    assert "nonce-" in csp


def test_hsts_header(client):
    """HSTS header should be present with includeSubDomains."""
    response = client.get("/")
    hsts = response.headers.get("Strict-Transport-Security", "")
    assert "max-age=" in hsts
    assert "includeSubDomains" in hsts


# ── Input Validation ─────────────────────────────────────────────────────────

def test_missing_input_answer(client):
    """Empty input on /api/answer should return 400."""
    response = client.post("/api/answer", json={
        "session_id": "123e4567-e89b-12d3-a456-426614174000",
        "input": ""
    })
    assert response.status_code == 400


# ── Translate ─────────────────────────────────────────────────────────────────

@patch("app.get_translate_client")
def test_translate_text(mock_get_client, client):
    """Translate endpoint should return translated text."""
    mock_client = mock_get_client.return_value
    mock_client.translate.return_value = {"translatedText": "नमस्ते"}
    
    response = client.post("/api/translate", json={"text": "hello", "target_language": "hi"})
    assert response.status_code == 200
    assert json.loads(response.data)["translated_text"] == "नमस्ते"


@patch("app.get_translate_client")
def test_translate_empty_text(mock_get_client, client):
    """Empty text should return empty translated_text."""
    response = client.post("/api/translate", json={"text": "", "target_language": "hi"})
    assert response.status_code == 200
    assert json.loads(response.data)["translated_text"] == ""


# ── Booth Finder ──────────────────────────────────────────────────────────────

def test_booth_finder(client):
    """Booth finder should return search_query and maps_url."""
    response = client.post("/api/booth_finder", json={"address": "MG Road", "state": "Gujarat"})
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "search_query" in data
    assert "maps_url" in data
    assert "maps.google.com" in data["maps_url"]


def test_booth_finder_url_encoding(client):
    """Booth finder should properly URL-encode the maps_url."""
    response = client.post("/api/booth_finder", json={"address": "M G Road & Station", "state": "Gujarat"})
    assert response.status_code == 200
    data = json.loads(response.data)
    # URL-encoded query should not contain raw spaces
    assert " " not in data["maps_url"].split("?q=")[1]


# ── Leaderboard ───────────────────────────────────────────────────────────────

def test_leaderboard(client):
    """Leaderboard should return a list with ETag header."""
    response = client.get("/api/leaderboard")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "leaderboard" in data
    assert "ETag" in response.headers


# ── UUID Validation ───────────────────────────────────────────────────────────

def test_validate_uuid_valid():
    """Valid UUID should return True."""
    assert validate_uuid("123e4567-e89b-12d3-a456-426614174000") is True


def test_validate_uuid_invalid():
    """Invalid UUID should return False."""
    assert validate_uuid("not-a-uuid") is False


def test_validate_uuid_empty():
    """Empty string should return False."""
    assert validate_uuid("") is False
