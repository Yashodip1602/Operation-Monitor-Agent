from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.jenkins_browser import JenkinsBrowserError
from app.services.jenkins_client import JenkinsClientError

client = TestClient(app)


@patch("app.routes.mic.sarvam_service.generate_speech")
def test_mic_activate_endpoint(mock_tts):
    mock_tts.return_value = {
        "audio_file": "sarvam_cache_welcome.wav",
        "audio_url": "/audio/sarvam_cache_welcome.wav",
        "cached": True,
    }

    response = client.post("/mic/activate", json={"provider": "sarvam"})
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Welcome to Operation Monitor Agent"
    assert data["audio_file"] == "sarvam_cache_welcome.wav"
    assert data["audio_url"] == "/audio/sarvam_cache_welcome.wav"
    assert data["status"] == "ready_for_stt"


@patch("app.routes.voice_agent.sarvam_service.generate_speech")
@patch("app.routes.voice_agent.trigger_build_via_ui")
@patch("app.routes.voice_agent.jenkins_client.get_all_jobs")
def test_voice_command_trigger_build_browser(mock_get_jobs, mock_trigger_ui, mock_tts):
    mock_get_jobs.return_value = [{"name": "my-project", "status": "SUCCESS"}]
    mock_trigger_ui.return_value = {
        "job_name": "my-project",
        "triggered": True,
        "status": "QUEUED",
        "message": "my-project build has been triggered in the browser.",
    }
    mock_tts.return_value = {"audio_file": "speech_res.wav", "audio_url": "/audio/speech_res.wav"}

    response = client.post(
        "/voice-agent/command-text",
        json={"text": "Trigger build for my-project", "provider": "sarvam"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "TRIGGER_BUILD"
    assert data["job_name"] == "my-project"
    assert data["execution_status"] == "SUCCESS"
    assert "triggered in the browser" in data["response_text"]
    assert data["audio_url"] == "/audio/speech_res.wav"


@patch("app.routes.voice_agent.sarvam_service.generate_speech")
@patch("app.routes.voice_agent.check_build_status")
@patch("app.routes.voice_agent.jenkins_client.get_all_jobs")
def test_voice_command_get_status_browser(mock_get_jobs, mock_status_ui, mock_tts):
    mock_get_jobs.return_value = [{"name": "backend-api", "status": "SUCCESS"}]
    mock_status_ui.return_value = {
        "job_name": "backend-api",
        "status": "SUCCESS",
        "build_number": 42,
        "message": "Job 'backend-api' build number 42 status is SUCCESS.",
    }
    mock_tts.return_value = {"audio_file": "speech_status.wav", "audio_url": "/audio/speech_status.wav"}

    response = client.post(
        "/voice-agent/command-text",
        json={"text": "Check status for backend-api"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "GET_STATUS"
    assert data["job_name"] == "backend-api"
    assert "status is SUCCESS" in data["response_text"]


@patch("app.routes.voice_agent.sarvam_service.generate_speech")
@patch("app.routes.voice_agent.stop_build_via_ui")
@patch("app.routes.voice_agent.jenkins_client.get_all_jobs")
def test_voice_command_stop_build_browser(mock_get_jobs, mock_stop_ui, mock_tts):
    mock_get_jobs.return_value = [{"name": "deploy-job", "status": "IN_PROGRESS"}]
    mock_stop_ui.return_value = {
        "job_name": "deploy-job",
        "stopped": True,
        "message": "Build for job 'deploy-job' has been aborted in the browser.",
    }
    mock_tts.return_value = {"audio_file": "speech_stop.wav", "audio_url": "/audio/speech_stop.wav"}

    response = client.post(
        "/voice-agent/command-text",
        json={"text": "Stop build for deploy-job"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "STOP_BUILD"
    assert data["job_name"] == "deploy-job"
    assert "aborted in the browser" in data["response_text"]


@patch("app.routes.voice_agent.sarvam_service.generate_speech")
@patch("app.routes.voice_agent.trigger_build_via_ui")
@patch("app.routes.voice_agent.jenkins_client.get_all_jobs")
def test_voice_command_jenkins_browser_error_handling(mock_get_jobs, mock_trigger_ui, mock_tts):
    mock_get_jobs.return_value = []
    mock_trigger_ui.side_effect = JenkinsBrowserError("Could not find 'Build Now' button for job 'invalid-job'.")
    mock_tts.return_value = {"audio_file": "err_speech.wav", "audio_url": "/audio/err_speech.wav"}

    response = client.post(
        "/voice-agent/command-text",
        json={"text": "Trigger build for invalid-job"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["execution_status"] == "ERROR"
    assert "Jenkins browser operation failed" in data["response_text"]
    assert "invalid-job" in data["response_text"]
    assert data["audio_url"] == "/audio/err_speech.wav"


@patch("app.routes.voice_agent.sarvam_service.transcribe_audio")
@patch("app.routes.voice_agent.sarvam_service.generate_speech")
@patch("app.routes.voice_agent.check_build_status")
@patch("app.routes.voice_agent.jenkins_client.get_all_jobs")
def test_voice_command_audio_upload(mock_get_jobs, mock_status_ui, mock_tts, mock_stt):
    mock_stt.return_value = {"transcript": "Check status for my-project"}
    mock_get_jobs.return_value = [{"name": "my-project", "status": "SUCCESS"}]
    mock_status_ui.return_value = {
        "job_name": "my-project",
        "status": "SUCCESS",
        "message": "Job 'my-project' status is SUCCESS.",
    }
    mock_tts.return_value = {"audio_file": "audio_resp.wav", "audio_url": "/audio/audio_resp.wav"}

    files = {"file": ("test.wav", b"dummy_audio_bytes", "audio/wav")}
    response = client.post("/voice-agent/command-audio", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["transcript"] == "Check status for my-project"
    assert data["intent"] == "GET_STATUS"
    assert data["execution_status"] == "SUCCESS"
