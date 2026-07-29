from typing import Optional
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.elevenlabs_service import elevenlabs_service
from app.utils.logger import logger

router = APIRouter(tags=["Text-to-Speech"])


class TTSRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Text content to convert to realistic speech.",
        json_schema_extra={"example": "Server is running successfully"},
    )
    voice_id: Optional[str] = Field(
        default=None,
        description="ElevenLabs Voice ID. Defaults to JBFqnCBsd6RMkjVDRZzb if omitted.",
        json_schema_extra={"example": "JBFqnCBsd6RMkjVDRZzb"},
    )
    model_id: Optional[str] = Field(
        default=None,
        description="ElevenLabs Model ID. Defaults to eleven_multilingual_v2 if omitted.",
        json_schema_extra={"example": "eleven_multilingual_v2"},
    )


class TTSResponse(BaseModel):
    audio_file: str = Field(
        ...,
        description="Generated MP3 audio filename.",
        json_schema_extra={"example": "tts_a1b2c3d4e5f6.mp3"},
    )
    audio_url: Optional[str] = Field(
        default=None,
        description="Relative URL to download/stream the generated audio file.",
        json_schema_extra={"example": "/audio/tts_a1b2c3d4e5f6.mp3"},
    )
    cached: Optional[bool] = Field(
        default=False,
        description="Indicates whether the response was retrieved from cache.",
    )
    response_time_ms: Optional[float] = Field(
        default=None,
        description="Processing time in milliseconds.",
    )


@router.post(
    "/text-to-speech",
    response_model=TTSResponse,
    status_code=status.HTTP_200_OK,
    summary="Convert text to speech MP3 file",
    description=(
        "Converts input text to realistic audio speech using ElevenLabs API "
        "and saves the generated audio file as an MP3."
    ),
)
async def text_to_speech(request: TTSRequest) -> TTSResponse:
    """Handles Text-to-Speech generation request."""
    if not request.text or not request.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text field cannot be empty.",
        )

    try:
        result = elevenlabs_service.generate_speech(
            text=request.text.strip(),
            voice_id=request.voice_id,
            model_id=request.model_id,
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
    description="Generates speech and streams audio chunks directly as audio/mpeg.",
)
async def text_to_speech_stream(request: TTSRequest) -> StreamingResponse:
    """Handles real-time streaming Text-to-Speech audio generation."""
    if not request.text or not request.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text field cannot be empty.",
        )

    try:
        audio_stream = elevenlabs_service.stream_speech(
            text=request.text.strip(),
            voice_id=request.voice_id,
            model_id=request.model_id,
        )
        return StreamingResponse(
            audio_stream,
            media_type="audio/mpeg",
            headers={"Content-Disposition": 'inline; filename="speech.mp3"'},
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
