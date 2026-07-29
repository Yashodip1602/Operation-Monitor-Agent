import hashlib
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Generator, Optional

from app.config.settings import settings
from app.utils.logger import logger

try:
    from elevenlabs.client import ElevenLabs
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ElevenLabs = None  # type: ignore
    ELEVENLABS_AVAILABLE = False


class ElevenLabsService:
    """Singleton service for ElevenLabs Text-to-Speech integration."""

    _instance: Optional["ElevenLabsService"] = None
    _client: Optional[Any] = None

    def __new__(cls) -> "ElevenLabsService":
        if cls._instance is None:
            cls._instance = super(ElevenLabsService, cls).__new__(cls)
            cls._instance._initialize_client()
        return cls._instance

    def _initialize_client(self) -> None:
        """Initializes the ElevenLabs SDK client once (singleton)."""
        api_key = settings.ELEVENLABS_API_KEY
        if api_key and api_key != "your_api_key_here" and ELEVENLABS_AVAILABLE:
            try:
                self._client = ElevenLabs(api_key=api_key)
                logger.info("ElevenLabs SDK client successfully initialized.")
            except Exception as e:
                logger.error(f"Failed to initialize ElevenLabs client: {e}")
                self._client = None
        else:
            if not ELEVENLABS_AVAILABLE:
                logger.warning("elevenlabs SDK package is not installed.")
            else:
                logger.warning("ELEVENLABS_API_KEY is not configured or using placeholder value.")
            self._client = None

    def get_client(self) -> Any:
        """Returns initialized client or attempts lazy initialization if config updated."""
        if self._client is None and ELEVENLABS_AVAILABLE:
            api_key = settings.ELEVENLABS_API_KEY
            if api_key and api_key != "your_api_key_here":
                try:
                    self._client = ElevenLabs(api_key=api_key)
                    logger.info("ElevenLabs client initialized on-demand.")
                except Exception as e:
                    logger.error(f"Failed lazy initialization of ElevenLabs client: {e}")
        return self._client

    def _get_cache_filename(self, text: str, voice_id: str, model_id: str) -> str:
        """Generates a deterministic filename for caching based on text and voice parameters."""
        raw_key = f"{text}:{voice_id}:{model_id}".encode("utf-8")
        hash_hex = hashlib.sha256(raw_key).hexdigest()[:16]
        return f"cache_{hash_hex}.mp3"

    def generate_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Converts text to speech using ElevenLabs API and saves the MP3 file.

        Returns:
            Dict containing audio_file, audio_url, cached status, and response_time_ms.
        """
        start_time = time.time()
        voice_id = voice_id or settings.DEFAULT_VOICE_ID
        model_id = model_id or settings.DEFAULT_MODEL_ID

        # Audio file caching check
        if settings.CACHE_ENABLED:
            cache_file = self._get_cache_filename(text, voice_id, model_id)
            cache_path = settings.AUDIO_OUTPUT_DIR / cache_file
            if cache_path.exists():
                elapsed_ms = round((time.time() - start_time) * 1000, 2)
                logger.info(f"Cache hit for text: '{text[:30]}...' -> {cache_file} ({elapsed_ms}ms)")
                return {
                    "audio_file": cache_file,
                    "audio_url": f"/audio/{cache_file}",
                    "cached": True,
                    "response_time_ms": elapsed_ms,
                }

        client = self.get_client()
        if client is None:
            raise ValueError(
                "ElevenLabs API Key is not configured. Please set a valid ELEVENLABS_API_KEY in .env file."
            )

        logger.info(f"Generating speech with ElevenLabs (voice_id: {voice_id}, model_id: {model_id})")

        try:
            # Call ElevenLabs API
            audio_generator = client.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id=model_id,
                output_format="mp3_44100_128",
            )

            # Generate filename
            if settings.CACHE_ENABLED:
                filename = self._get_cache_filename(text, voice_id, model_id)
            else:
                unique_id = uuid.uuid4().hex[:12]
                filename = f"tts_{unique_id}.mp3"

            file_path = settings.AUDIO_OUTPUT_DIR / filename

            # Write audio content to MP3 file
            with open(file_path, "wb") as f:
                if isinstance(audio_generator, bytes):
                    f.write(audio_generator)
                else:
                    for chunk in audio_generator:
                        if chunk:
                            f.write(chunk)

            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            logger.info(f"Successfully generated audio file '{filename}' in {elapsed_ms}ms")

            return {
                "audio_file": filename,
                "audio_url": f"/audio/{filename}",
                "cached": False,
                "response_time_ms": elapsed_ms,
            }

        except Exception as e:
            logger.error(f"ElevenLabs TTS generation failed: {e}", exc_info=True)
            raise RuntimeError(f"ElevenLabs TTS generation failed: {str(e)}")

    def stream_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> Generator[bytes, None, None]:
        """Streams audio byte chunks directly from ElevenLabs API."""
        voice_id = voice_id or settings.DEFAULT_VOICE_ID
        model_id = model_id or settings.DEFAULT_MODEL_ID

        client = self.get_client()
        if client is None:
            raise ValueError(
                "ElevenLabs API Key is not configured. Please set a valid ELEVENLABS_API_KEY in .env file."
            )

        logger.info(f"Streaming speech with ElevenLabs (voice_id: {voice_id}, model_id: {model_id})")

        try:
            audio_stream = client.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id=model_id,
                output_format="mp3_44100_128",
            )
            if isinstance(audio_stream, bytes):
                yield audio_stream
            else:
                for chunk in audio_stream:
                    if chunk:
                        yield chunk
        except Exception as e:
            logger.error(f"ElevenLabs audio streaming failed: {e}", exc_info=True)
            raise RuntimeError(f"ElevenLabs audio streaming failed: {str(e)}")


elevenlabs_service = ElevenLabsService()
