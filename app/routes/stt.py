from typing import Any, List, Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.services.sarvam_service import sarvam_service
from app.utils.logger import logger

router = APIRouter(tags=["Speech-to-Text"])


class STTResponse(BaseModel):
    transcript: str = Field(
        ...,
        description="Transcribed text from input audio.",
        json_schema_extra={"example": "Server utilization is optimal."},
    )
    language_code: Optional[str] = Field(
        default="hi-IN",
        description="Language code detected or specified for transcription.",
        json_schema_extra={"example": "hi-IN"},
    )
    timestamps: Optional[List[Any]] = Field(
        default=None,
        description="Optional word-level or segment timestamps if requested.",
    )
    diarization: Optional[Any] = Field(
        default=None,
        description="Optional speaker diarization labels.",
    )
    response_time_ms: Optional[float] = Field(
        default=None,
        description="Processing duration in milliseconds.",
    )


@router.post(
    "/speech-to-text",
    response_model=STTResponse,
    status_code=status.HTTP_200_OK,
    summary="Transcribe audio file to text",
    description=(
        "Transcribes uploaded audio files (WAV, MP3, M4A, FLAC, OGG) into text "
        "using Sarvam AI Speech-to-Text (Saaras) API."
    ),
)
async def speech_to_text(
    file: UploadFile = File(..., description="Audio file to transcribe."),
    language_code: Optional[str] = Form(
        default=None,
        description="Target language code (e.g. hi-IN, en-IN, ta-IN).",
    ),
    model: Optional[str] = Form(
        default=None,
        description="Sarvam STT model ID (e.g. saaras:v1, saaras:v3).",
    ),
    with_timestamps: bool = Form(
        default=False,
        description="Whether to include timestamp alignment in response.",
    ),
) -> STTResponse:
    """Handles Speech-to-Text transcription request for uploaded audio file."""
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

    try:
        result = await sarvam_service.transcribe_audio(
            file_bytes=file_bytes,
            filename=file.filename,
            language_code=language_code,
            model=model,
            with_timestamps=with_timestamps,
        )
        return STTResponse(**result)

    except ValueError as ve:
        logger.error(f"STT Configuration Error: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except Exception as e:
        logger.error(f"STT Transcription Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to transcribe audio: {str(e)}",
        )
