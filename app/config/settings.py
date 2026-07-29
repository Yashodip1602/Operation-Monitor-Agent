import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings:
    """Application settings and configuration."""
    
    PROJECT_NAME: str = "OpsMonit Backend"
    VERSION: str = "1.0.0"

    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "your_api_key_here")
    DEFAULT_VOICE_ID: str = os.getenv("DEFAULT_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
    DEFAULT_MODEL_ID: str = os.getenv("DEFAULT_MODEL_ID", "eleven_multilingual_v2")

    AUDIO_OUTPUT_DIR: Path = BASE_DIR / os.getenv("AUDIO_OUTPUT_DIR", "app/static/audio")
    CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "True").lower() in ("true", "1", "t")

    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    def __init__(self) -> None:
        """Ensure static audio output directory exists."""
        self.AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
