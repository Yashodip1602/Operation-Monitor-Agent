from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.sarvam_service import sarvam_service
from app.utils.logger import logger

router = APIRouter(prefix="/mic", tags=["Mic Activation & Welcome"])

WELCOME_TEXT = "Welcome to Operation Monitor Agent"


class MicActivateRequest(BaseModel):
    target_language_code: Optional[str] = Field(
        default=None,
        description="Target language code for welcome message.",
    )
    speaker: Optional[str] = Field(
        default=None,
        description="Speaker voice for welcome message.",
    )


class MicActivateResponse(BaseModel):
    message: str = Field(
        default=WELCOME_TEXT,
        description="Welcome text message synthesized.",
    )
    audio_file: str = Field(
        ...,
        description="Filename of generated audio welcome message.",
    )
    audio_url: str = Field(
        ...,
        description="URL path to play/download generated welcome audio.",
    )
    cached: bool = Field(
        default=False,
        description="Indicates whether audio was served from cache.",
    )
    status: str = Field(
        default="ready_for_stt",
        description="Next state for client application workflow.",
    )


@router.post(
    "/activate",
    response_model=MicActivateResponse,
    status_code=status.HTTP_200_OK,
    summary="Mic activation welcome message trigger",
    description=(
        "Triggers fixed TTS welcome speech ('Welcome to Operation Monitor Agent') when mic is turned ON. "
        "Sequence: Mic ON -> Call /mic/activate -> Play welcome audio -> Start STT listening."
    ),
)
async def activate_mic(request: Optional[MicActivateRequest] = None) -> MicActivateResponse:
    """
    Handles mic activation by synthesizing the welcome message via TTS before STT listening starts.
    """
    req = request or MicActivateRequest()

    logger.info("Mic activated. Triggering welcome speech with Sarvam AI...")

    try:
        result = await sarvam_service.generate_speech(
            text=WELCOME_TEXT,
            target_language_code=req.target_language_code,
            speaker=req.speaker,
        )

        logger.info(f"Mic welcome audio generated successfully: {result.get('audio_file')}")
        return MicActivateResponse(
            message=WELCOME_TEXT,
            audio_file=result["audio_file"],
            audio_url=result["audio_url"],
            cached=result.get("cached", False),
            status="ready_for_stt",
        )
    except Exception as e:
        logger.error(f"Failed to generate mic welcome speech: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate mic welcome message: {str(e)}",
        )
