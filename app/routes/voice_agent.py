from typing import Any, Dict, Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.config.settings import settings
from app.services.intent_parser import IntentParser, IntentType, intent_parser
from app.services.jenkins_client import JenkinsClient, JenkinsClientError, jenkins_client
from app.services.jenkins_browser import JenkinsBrowserError, check_build_status, stop_build_via_ui, trigger_build_via_ui
from app.services.sarvam_service import sarvam_service
from app.utils.logger import logger

router = APIRouter(prefix="/voice-agent", tags=["Voice Agent & Jenkins Automation"])


class TextCommandRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        description="Text command to parse and execute against Jenkins.",
        json_schema_extra={"example": "Trigger build for my-project"},
    )
    target_language_code: Optional[str] = Field(
        default=None,
        description="Target language code for TTS response.",
    )


class VoiceAgentResponse(BaseModel):
    transcript: str = Field(..., description="Transcribed or input command text.")
    intent: str = Field(..., description="Detected intent type (e.g. TRIGGER_BUILD, GET_STATUS).")
    job_name: Optional[str] = Field(default=None, description="Extracted target job name.")
    execution_status: str = Field(..., description="Execution outcome ('SUCCESS', 'ERROR', 'UNHANDLED').")
    response_text: str = Field(..., description="Generated text message spoken back to user.")
    audio_file: Optional[str] = Field(default=None, description="Filename of spoken TTS response.")
    audio_url: Optional[str] = Field(default=None, description="URL path to spoken TTS response audio.")
    jenkins_result: Optional[Dict[str, Any]] = Field(default=None, description="Raw details from Jenkins operation.")


async def _generate_spoken_response(text: str, target_language_code: Optional[str] = None) -> Dict[str, Any]:
    """Helper to convert response text string into spoken TTS audio."""
    try:
        return await sarvam_service.generate_speech(text=text, target_language_code=target_language_code)
    except Exception as e:
        logger.error(f"Failed to generate TTS audio for voice response: {e}")
        return {"audio_file": None, "audio_url": None}


async def _execute_voice_pipeline(
    transcript: str,
    target_language_code: Optional[str] = None,
) -> VoiceAgentResponse:
    """Core pipeline: Transcript -> Intent Parser -> Jenkins Action -> Spoken TTS Response."""
    logger.info(f"Processing voice command transcript: '{transcript}'")

    # Fetch known jobs if Jenkins is accessible via API
    known_job_names = []
    try:
        jobs = jenkins_client.get_all_jobs()
        known_job_names = [j["name"] for j in jobs if "name" in j]
    except Exception:
        pass  # Connection error handled during browser or API execution

    parsed = intent_parser.parse(transcript, known_jobs=known_job_names)
    intent = parsed.intent
    job_name = parsed.job_name

    execution_status = "SUCCESS"
    response_text = ""
    jenkins_data: Optional[Dict[str, Any]] = None

    try:
        if intent == IntentType.TRIGGER_BUILD:
            if not job_name:
                response_text = "Please specify a valid job name to trigger a build."
                execution_status = "ERROR"
            else:
                jenkins_data = trigger_build_via_ui(job_name)
                response_text = f"{job_name} build has been triggered in the browser."

        elif intent == IntentType.GET_STATUS:
            if not job_name:
                response_text = "Please specify a job name to check status."
                execution_status = "ERROR"
            else:
                jenkins_data = check_build_status(job_name)
                response_text = jenkins_data.get("message", f"Job '{job_name}' status retrieved.")

        elif intent == IntentType.STOP_BUILD:
            if not job_name:
                response_text = "Please specify a job name to stop build."
                execution_status = "ERROR"
            else:
                jenkins_data = stop_build_via_ui(job_name)
                response_text = jenkins_data.get("message", f"Build for job '{job_name}' stopped.")

        elif intent == IntentType.LIST_JOBS:
            jobs = jenkins_client.get_all_jobs()
            job_names = [j["name"] for j in jobs]
            jenkins_data = {"jobs": jobs, "count": len(jobs)}
            if job_names:
                names_str = ", ".join(job_names[:5])
                response_text = f"Found {len(job_names)} Jenkins jobs: {names_str}."
            else:
                response_text = "No Jenkins jobs found on server."

        elif intent == IntentType.GET_LOGS:
            if not job_name:
                response_text = "Please specify a job name to fetch console logs."
                execution_status = "ERROR"
            else:
                jenkins_data = jenkins_client.get_console_output(job_name)
                num = jenkins_data.get("build_number")
                response_text = f"Retrieved console logs for job '{job_name}' build number {num}."

        else:
            response_text = "Sorry, I could not understand the requested command."
            execution_status = "UNHANDLED"

    except JenkinsBrowserError as jbe:
        logger.error(f"Jenkins browser automation error during voice command processing: {jbe}")
        response_text = f"Jenkins browser operation failed: {str(jbe)}"
        execution_status = "ERROR"

    except JenkinsClientError as jce:
        logger.error(f"Jenkins action error during voice command processing: {jce}")
        response_text = f"Jenkins operation failed: {str(jce)}"
        execution_status = "ERROR"

    except Exception as e:
        logger.error(f"Unexpected error executing voice command: {e}", exc_info=True)
        response_text = f"An unexpected error occurred: {str(e)}"
        execution_status = "ERROR"

    # Log Jenkins action
    logger.info(
        f"Voice command executed | Transcript: '{transcript}' | Intent: {intent} | "
        f"Job: {job_name} | Status: {execution_status} | Spoken response: '{response_text}'"
    )

    # Convert generated response text to speech audio
    tts_result = await _generate_spoken_response(
        text=response_text,
        target_language_code=target_language_code,
    )

    return VoiceAgentResponse(
        transcript=transcript,
        intent=intent,
        job_name=job_name,
        execution_status=execution_status,
        response_text=response_text,
        audio_file=tts_result.get("audio_file"),
        audio_url=tts_result.get("audio_url"),
        jenkins_result=jenkins_data,
    )


@router.post(
    "/command-text",
    response_model=VoiceAgentResponse,
    status_code=status.HTTP_200_OK,
    summary="Process text command against Jenkins with TTS response",
    description="Parses text input, executes Jenkins action, and speaks response via TTS.",
)
async def process_text_command(request: TextCommandRequest) -> VoiceAgentResponse:
    """Handles text command input."""
    return await _execute_voice_pipeline(
        transcript=request.text.strip(),
        target_language_code=request.target_language_code,
    )


@router.post(
    "/command-audio",
    response_model=VoiceAgentResponse,
    status_code=status.HTTP_200_OK,
    summary="Process audio voice command against Jenkins with STT and TTS response",
    description="Transcribes uploaded audio via STT, parses intent, executes Jenkins action, and speaks response via TTS.",
)
async def process_audio_command(
    file: UploadFile = File(..., description="Audio file containing voice command."),
    language_code: Optional[str] = Form(default=None, description="STT / TTS language code."),
    stt_model: Optional[str] = Form(default=None, description="Sarvam STT model ID."),
) -> VoiceAgentResponse:
    """Handles audio file input: STT -> Intent -> Jenkins API -> TTS."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a valid filename.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded audio file cannot be empty.",
        )

    # 1. Transcribe speech audio using STT service
    try:
        stt_result = await sarvam_service.transcribe_audio(
            file_bytes=file_bytes,
            filename=file.filename,
            language_code=language_code,
            model=stt_model,
        )
        transcript = stt_result.get("transcript", "").strip()
        logger.info(f"Audio STT transcription completed: '{transcript}'")
    except Exception as e:
        logger.error(f"STT transcription failed for voice command: {e}", exc_info=True)
        error_msg = f"Failed to transcribe audio command: {str(e)}"
        tts_err = await _generate_spoken_response(text="Failed to recognize audio command.")
        return VoiceAgentResponse(
            transcript="",
            intent=IntentType.UNKNOWN,
            job_name=None,
            execution_status="ERROR",
            response_text=error_msg,
            audio_file=tts_err.get("audio_file"),
            audio_url=tts_err.get("audio_url"),
        )

    if not transcript:
        error_msg = "No speech detected in uploaded audio file."
        tts_err = await _generate_spoken_response(text=error_msg)
        return VoiceAgentResponse(
            transcript="",
            intent=IntentType.UNKNOWN,
            job_name=None,
            execution_status="ERROR",
            response_text=error_msg,
            audio_file=tts_err.get("audio_file"),
            audio_url=tts_err.get("audio_url"),
        )

    # 2. Run Voice Agent pipeline with transcribed text
    return await _execute_voice_pipeline(
        transcript=transcript,
        target_language_code=language_code,
    )
