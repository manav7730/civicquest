import pytest
import sys
import os
import json
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    # Disable rate limiting for testing
    app.config["RATELIMIT_ENABLED"] = False
    with app.test_client() as client:
        yield client

def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "ok"
    assert "Cache-Control" in response.headers

def test_index_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"CivicQuest" in response.data

def test_api_start_game(client):
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

def test_invalid_session_id(client):
    response = client.post("/api/scene", json={"session_id": "invalid-uuid"})
    assert response.status_code == 400

def test_security_headers(client):
    response = client.get("/")
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"

def test_missing_input_answer(client):
    response = client.post("/api/answer", json={
        "session_id": "123e4567-e89b-12d3-a456-426614174000",
        "input": ""
    })
    assert response.status_code == 400

@patch("app.get_translate_client")
def test_translate_text(mock_get_client, client):
    mock_client = mock_get_client.return_value
    mock_client.translate.return_value = {"translatedText": "नमस्ते"}
    
    response = client.post("/api/translate", json={"text": "hello", "target_language": "hi"})
    assert response.status_code == 200
    assert json.loads(response.data)["translated_text"] == "नमस्ते"

def test_booth_finder(client):
    response = client.post("/api/booth_finder", json={"address": "MG Road", "state": "Gujarat"})
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "search_query" in data
    assert "maps_url" in data
