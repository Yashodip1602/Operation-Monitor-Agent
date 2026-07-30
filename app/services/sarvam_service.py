import base64
import hashlib
import time
import uuid
from typing import Any, Dict, AsyncGenerator, Optional
import httpx

from app.config.settings import settings
from app.utils.logger import logger


class SarvamService:
    """Singleton service for Sarvam AI Text-to-Speech (TTS) and Speech-to-Text (STT) integration."""

    _instance: Optional["SarvamService"] = None

    def __new__(cls) -> "SarvamService":
        if cls._instance is None:
            cls._instance = super(SarvamService, cls).__new__(cls)
        return cls._instance

    def _get_api_key(self) -> str:
        """Retrieves and validates Sarvam API key."""
        api_key = (settings.SARVAM_API_KEY or "").strip()
        if not api_key or api_key == "your_sarvam_api_key_here":
            logger.error("Sarvam API Key is missing or set to placeholder in .env file.")
            raise ValueError(
                "Sarvam API Key is not configured. Please set SARVAM_API_KEY in .env file."
            )
        return api_key

    def check_api_key_on_startup(self) -> bool:
        """Checks if SARVAM_API_KEY is configured on startup and logs a warning if missing."""
        api_key = (settings.SARVAM_API_KEY or "").strip()
        if not api_key or api_key == "your_sarvam_api_key_here":
            logger.warning(
                "WARNING: SARVAM_API_KEY is not configured or is set to placeholder in .env file. "
                "TTS and STT requests will fail until a valid key is provided."
            )
            return False
        logger.info("Sarvam API Key configuration verified successfully.")
        return True

    def _get_headers(self) -> Dict[str, str]:
        """Returns HTTP headers required for Sarvam API requests."""
        return {
            "api-subscription-key": self._get_api_key(),
            "Content-Type": "application/json",
        }

    def _get_cache_filename(
        self,
        text: str,
        target_language_code: str,
        speaker: str,
        model: str,
        pace: float,
        pitch: float,
    ) -> str:
        """Generates a deterministic filename for caching based on request parameters."""
        raw_key = f"{text}:{target_language_code}:{speaker}:{model}:{pace}:{pitch}".encode("utf-8")
        hash_hex = hashlib.sha256(raw_key).hexdigest()[:16]
        return f"sarvam_cache_{hash_hex}.wav"

    async def generate_speech(
        self,
        text: str,
        target_language_code: Optional[str] = None,
        speaker: Optional[str] = None,
        pitch: Optional[float] = 0.0,
        pace: Optional[float] = 1.0,
        loudness: Optional[float] = 1.5,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Converts input text to speech using Sarvam AI TTS API.
        Saves decoded audio file and returns metadata.
        """
        start_time = time.time()
        target_language_code = target_language_code or settings.DEFAULT_SARVAM_LANGUAGE
        speaker = speaker or settings.DEFAULT_SARVAM_SPEAKER
        model = model or settings.DEFAULT_SARVAM_MODEL
        pitch = pitch if pitch is not None else 0.0
        pace = pace if pace is not None else 1.0

        # Check hash cache if enabled
        if settings.CACHE_ENABLED:
            cache_file = self._get_cache_filename(
                text, target_language_code, speaker, model, pace, pitch
            )
            cache_path = settings.AUDIO_OUTPUT_DIR / cache_file
            if cache_path.exists():
                elapsed_ms = round((time.time() - start_time) * 1000, 2)
                logger.info(f"Sarvam Cache hit for text: '{text[:30]}...' -> {cache_file} ({elapsed_ms}ms)")
                return {
                    "audio_file": cache_file,
                    "audio_url": f"/audio/{cache_file}",
                    "cached": True,
                    "response_time_ms": elapsed_ms,
                    "language_code": target_language_code,
                    "speaker": speaker,
                }

        api_key = self._get_api_key()

        payload = {
            "inputs": [text],
            "target_language_code": target_language_code,
            "speaker": speaker,
            "pitch": pitch,
            "pace": pace,
            "loudness": loudness,
            "enable_preprocessing": True,
            "model": model,
        }

        headers = {
            "api-subscription-key": api_key,
            "Content-Type": "application/json",
        }

        logger.info(
            f"Generating speech with Sarvam AI (lang: {target_language_code}, speaker: {speaker}, model: {model})"
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    settings.SARVAM_TTS_URL,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()

            audios = data.get("audios", [])
            if not audios or not audios[0]:
                raise RuntimeError("Sarvam AI returned empty audio response.")

            audio_bytes = base64.b64decode(audios[0])

            # Determine output filename
            if settings.CACHE_ENABLED:
                filename = self._get_cache_filename(
                    text, target_language_code, speaker, model, pace, pitch
                )
            else:
                unique_id = uuid.uuid4().hex[:12]
                filename = f"sarvam_tts_{unique_id}.wav"

            file_path = settings.AUDIO_OUTPUT_DIR / filename
            with open(file_path, "wb") as f:
                f.write(audio_bytes)

            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            logger.info(f"Sarvam TTS generation successful: '{filename}' ({elapsed_ms}ms)")

            return {
                "audio_file": filename,
                "audio_url": f"/audio/{filename}",
                "cached": False,
                "response_time_ms": elapsed_ms,
                "language_code": target_language_code,
                "speaker": speaker,
            }

        except httpx.HTTPStatusError as hse:
            error_detail = hse.response.text
            logger.error(f"Sarvam TTS HTTP error {hse.response.status_code}: {error_detail}")
            raise RuntimeError(f"Sarvam API error: {error_detail}")
        except Exception as e:
            logger.error(f"Sarvam TTS failed: {e}", exc_info=True)
            raise RuntimeError(f"Sarvam TTS failed: {str(e)}")

    async def stream_speech(
        self,
        text: str,
        target_language_code: Optional[str] = None,
        speaker: Optional[str] = None,
        pitch: Optional[float] = 0.0,
        pace: Optional[float] = 1.0,
        loudness: Optional[float] = 1.5,
        model: Optional[str] = None,
    ) -> AsyncGenerator[bytes, None]:
        """Streams Sarvam TTS decoded audio byte chunks."""
        result = await self.generate_speech(
            text=text,
            target_language_code=target_language_code,
            speaker=speaker,
            pitch=pitch,
            pace=pace,
            loudness=loudness,
            model=model,
        )

        filename = result["audio_file"]
        file_path = settings.AUDIO_OUTPUT_DIR / filename

        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                yield chunk

    async def transcribe_audio(
        self,
        file_bytes: bytes,
        filename: str,
        language_code: Optional[str] = None,
        model: Optional[str] = None,
        with_timestamps: bool = False,
    ) -> Dict[str, Any]:
        """
        Transcribes input audio file using Sarvam AI Speech-to-Text (STT) API.
        """
        start_time = time.time()
        api_key = self._get_api_key()
        model = model or settings.DEFAULT_STT_MODEL
        language_code = language_code or settings.DEFAULT_SARVAM_LANGUAGE

        headers = {
            "api-subscription-key": api_key,
        }

        data = {
            "model": model,
            "language_code": language_code,
            "with_timestamps": str(with_timestamps).lower(),
        }

        files = {
            "file": (filename, file_bytes, "audio/wav"),
        }

        logger.info(f"Transcribing audio with Sarvam AI STT (model: {model}, language: {language_code})")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    settings.SARVAM_STT_URL,
                    data=data,
                    files=files,
                    headers=headers,
                )
                response.raise_for_status()
                res_data = response.json()

            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            transcript = res_data.get("transcript", "")
            detected_lang = res_data.get("language_code", language_code)

            logger.info(f"Sarvam STT completed in {elapsed_ms}ms. Transcript length: {len(transcript)}")

            return {
                "transcript": transcript,
                "language_code": detected_lang,
                "timestamps": res_data.get("timestamps"),
                "diarization": res_data.get("diarization"),
                "response_time_ms": elapsed_ms,
            }

        except httpx.HTTPStatusError as hse:
            error_detail = hse.response.text
            logger.error(f"Sarvam STT HTTP error {hse.response.status_code}: {error_detail}")
            raise RuntimeError(f"Sarvam STT error: {error_detail}")
        except Exception as e:
            logger.error(f"Sarvam STT failed: {e}", exc_info=True)
            raise RuntimeError(f"Sarvam STT transcription failed: {str(e)}")


sarvam_service = SarvamService()
