from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_tts_empty_text_returns_400():
    """Test POST /text-to-speech with empty text returns 422 or 400 error."""
    response = client.post("/text-to-speech", json={"text": ""})
    assert response.status_code in (400, 422)


def test_tts_missing_api_key_handling():
    """Test POST /text-to-speech without valid API key returns proper error message."""
    response = client.post("/text-to-speech", json={"text": "Hello OpsMonit"})
    # Without valid API key, should return 400 with descriptive error detail
    assert response.status_code == 400
    assert "ElevenLabs API Key" in response.json()["detail"]


def test_tts_cached_response(tmp_path, monkeypatch):
    """Test cached TTS response when cache file already exists."""
    from app.config import settings

    # Setup dummy cache file
    cache_file = "cache_8e2f810aa7be6632.mp3"
    cache_filepath = settings.AUDIO_OUTPUT_DIR / cache_file
    cache_filepath.write_bytes(b"mock_mp3_data")

    # Mock the cache filename calculation to return our dummy file
    with patch(
        "app.services.elevenlabs_service.elevenlabs_service._get_cache_filename",
        return_value=cache_file,
    ):
        response = client.post(
            "/text-to-speech",
            json={"text": "Cached text demo"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["audio_file"] == cache_file
        assert data["cached"] is True

    # Clean up test file
    if cache_filepath.exists():
        cache_filepath.unlink()
