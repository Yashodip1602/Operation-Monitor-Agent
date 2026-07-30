from typing import Optional
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.sarvam_service import sarvam_service
from app.utils.logger import logger

router = APIRouter(tags=["Text-to-Speech"])


class TTSRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Text content to convert to speech.",
        json_schema_extra={"example": "Server is running successfully"},
    )
    target_language_code: Optional[str] = Field(
        default=None,
        description="Sarvam target language code (e.g., hi-IN, en-IN, ta-IN).",
        json_schema_extra={"example": "hi-IN"},
    )
    speaker: Optional[str] = Field(
        default=None,
        description="Sarvam speaker name (e.g. meera, pavithra, arvind).",
        json_schema_extra={"example": "meera"},
    )
    pitch: Optional[float] = Field(
        default=0.0,
        description="Sarvam voice pitch modification (-1.0 to 1.0).",
    )
    pace: Optional[float] = Field(
        default=1.0,
        description="Sarvam voice pace speed multiplier (0.5 to 2.0).",
    )
    model_id: Optional[str] = Field(
        default=None,
        description="Model ID for Sarvam.",
        json_schema_extra={"example": "bulbul:v1"},
    )


class TTSResponse(BaseModel):
    audio_file: str = Field(
        ...,
        description="Generated audio filename.",
        json_schema_extra={"example": "sarvam_cache_a1b2c3d4e5f6.wav"},
    )
    audio_url: Optional[str] = Field(
        default=None,
        description="Relative URL to download/stream the generated audio file.",
        json_schema_extra={"example": "/audio/sarvam_cache_a1b2c3d4e5f6.wav"},
    )
    cached: Optional[bool] = Field(
        default=False,
        description="Indicates whether the response was retrieved from cache.",
    )
    response_time_ms: Optional[float] = Field(
        default=None,
        description="Processing time in milliseconds.",
    )
    language_code: Optional[str] = Field(
        default=None,
        description="Target language code used for synthesis.",
    )
    speaker: Optional[str] = Field(
        default=None,
        description="Speaker voice used for synthesis.",
    )


@router.post(
    "/text-to-speech",
    response_model=TTSResponse,
    status_code=status.HTTP_200_OK,
    summary="Convert text to speech audio file",
    description="Converts input text to audio speech using Sarvam AI and saves the generated audio file.",
)
async def text_to_speech(request: TTSRequest) -> TTSResponse:
    """Handles Text-to-Speech generation request."""
    if not request.text or not request.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text field cannot be empty.",
        )

    try:
        result = await sarvam_service.generate_speech(
            text=request.text.strip(),
            target_language_code=request.target_language_code,
            speaker=request.speaker,
            pitch=request.pitch,
            pace=request.pace,
            model=request.model_id,
        )

        return TTSResponse(**result)

    except ValueError as ve:
        logger.error(f"TTS Configuration Error: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except Exception as e:
        logger.error(f"TTS Generation Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate speech: {str(e)}",
        )


@router.post(
    "/text-to-speech/stream",
    status_code=status.HTTP_200_OK,
    summary="Stream text to speech audio chunks",
    description="Generates speech and streams audio chunks directly.",
)
async def text_to_speech_stream(request: TTSRequest) -> StreamingResponse:
    """Handles real-time streaming Text-to-Speech audio generation."""
    if not request.text or not request.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text field cannot be empty.",
        )

    try:
        audio_stream = sarvam_service.stream_speech(
            text=request.text.strip(),
            target_language_code=request.target_language_code,
            speaker=request.speaker,
            pitch=request.pitch,
            pace=request.pace,
            model=request.model_id,
        )
        media_type = "audio/wav"
        filename = "speech.wav"

        return StreamingResponse(
            audio_stream,
            media_type=media_type,
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Streaming failed: {str(e)}",
        )
