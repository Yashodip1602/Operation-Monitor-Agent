from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_tts_empty_text_returns_400():
    """Test POST /text-to-speech with empty text returns 422 or 400 error."""
    response = client.post("/text-to-speech", json={"text": ""})
    assert response.status_code in (400, 422)


def test_sarvam_tts_missing_api_key_handling():
    """Test POST /text-to-speech without valid API key returns proper error."""
    response = client.post("/text-to-speech", json={"text": "Hello OpsMonit"})
    assert response.status_code == 400
    assert "Sarvam API Key" in response.json()["detail"]


def test_sarvam_tts_cached_response(tmp_path):
    """Test cached Sarvam TTS response when cache file already exists."""
    from app.config import settings

    # Setup dummy cache file
    cache_file = "sarvam_cache_test12345.wav"
    cache_filepath = settings.AUDIO_OUTPUT_DIR / cache_file
    cache_filepath.write_bytes(b"mock_wav_data")

    mock_service_return = {
        "audio_file": cache_file,
        "audio_url": f"/audio/{cache_file}",
        "cached": True,
        "response_time_ms": 1.5,
        "language_code": "hi-IN",
        "speaker": "meera",
    }

    with patch(
        "app.routes.tts.sarvam_service.generate_speech",
        new_callable=AsyncMock,
        return_value=mock_service_return,
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
