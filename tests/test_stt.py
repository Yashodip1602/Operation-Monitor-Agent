import io
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_stt_empty_file_returns_400():
    """Test POST /speech-to-text with empty audio file returns 400 error."""
    files = {"file": ("test.wav", io.BytesIO(b""), "audio/wav")}
    response = client.post("/speech-to-text", files=files)
    assert response.status_code == 400
    assert "cannot be empty" in response.json()["detail"]


def test_stt_success_response():
    """Test successful audio transcription using mocked Sarvam STT service."""
    mock_stt_result = {
        "transcript": "Hello OpsMonit system is operating normally.",
        "language_code": "en-IN",
        "timestamps": None,
        "diarization": None,
        "response_time_ms": 120.5,
    }

    dummy_audio_bytes = b"RIFF....WAVEfmt ....data...."

    with patch(
        "app.routes.stt.sarvam_service.transcribe_audio",
        new_callable=AsyncMock,
        return_value=mock_stt_result,
    ):
        files = {"file": ("sample.wav", io.BytesIO(dummy_audio_bytes), "audio/wav")}
        data = {"language_code": "en-IN", "model": "saaras:v1"}
        response = client.post("/speech-to-text", files=files, data=data)

        assert response.status_code == 200
        res = response.json()
        assert res["transcript"] == "Hello OpsMonit system is operating normally."
        assert res["language_code"] == "en-IN"
        assert res["response_time_ms"] == 120.5
