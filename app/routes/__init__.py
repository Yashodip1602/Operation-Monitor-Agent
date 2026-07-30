"""Routes package."""
from .health import router as health_router
from .tts import router as tts_router
from .stt import router as stt_router

__all__ = ["health_router", "tts_router", "stt_router"]
