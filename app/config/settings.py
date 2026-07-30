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

    # Sarvam AI Settings
    SARVAM_API_KEY: str = os.getenv("SARVAM_API_KEY", "your_sarvam_api_key_here")
    SARVAM_TTS_URL: str = os.getenv("SARVAM_TTS_URL", "https://api.sarvam.ai/text-to-speech")
    SARVAM_STT_URL: str = os.getenv("SARVAM_STT_URL", "https://api.sarvam.ai/speech-to-text")
    DEFAULT_SARVAM_MODEL: str = os.getenv("DEFAULT_SARVAM_MODEL", "bulbul:v2")
    DEFAULT_SARVAM_SPEAKER: str = os.getenv("DEFAULT_SARVAM_SPEAKER", "anushka")
    DEFAULT_SARVAM_LANGUAGE: str = os.getenv("DEFAULT_SARVAM_LANGUAGE", "hi-IN")
    DEFAULT_STT_MODEL: str = os.getenv("DEFAULT_STT_MODEL", "saaras:v1")

    # Audio & Server Configuration
    AUDIO_OUTPUT_DIR: Path = BASE_DIR / os.getenv("AUDIO_OUTPUT_DIR", "app/static/audio")
    CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "True").lower() in ("true", "1", "t")

    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Jenkins Settings
    JENKINS_URL: str = os.getenv("JENKINS_URL", "http://localhost:8080")
    JENKINS_USERNAME: str = os.getenv("JENKINS_USERNAME", "")
    JENKINS_PASSWORD: str = os.getenv("JENKINS_PASSWORD", "")
    KEEP_BROWSER_OPEN: bool = os.getenv("KEEP_BROWSER_OPEN", "True").lower() in ("true", "1", "t")
    HEADLESS_BROWSER: bool = os.getenv("HEADLESS_BROWSER", "True").lower() in ("true", "1", "t")
    CHROME_BINARY_PATH: str = os.getenv("CHROME_BINARY_PATH", "/usr/bin/chromium-browser")
    SCREENSHOT_DIR: Path = BASE_DIR / "app/static/screenshots"

    # External API Settings
    EXTERNAL_API_BASE_URL: str = os.getenv("EXTERNAL_API_BASE_URL", "http://13.202.2.200:8000")
    EXTERNAL_API_TOKEN: str = os.getenv("EXTERNAL_API_TOKEN", "")


    def __init__(self) -> None:
        """Ensure static output directories exist."""
        self.AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
