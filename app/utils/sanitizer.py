import re
from app.utils.logger import logger

GENERIC_ERROR_TTS = "Sorry, the Jenkins operation failed due to a browser or connection issue. Please check the logs for details."

STACK_TRACE_PATTERNS = [
    r"traceback",
    r"file\s+\"",
    r"#\d+\s+0x",
    r"httpconnectionpool",
    r"maxretryerror",
    r"connectionrefusederror",
    r"attributeerror",
    r"keyerror",
    r"typeerror",
    r"valueerror",
    r"exception occurred",
    r"during handling of the above",
    r"line \d+",
    r"stack trace",
]


def sanitize_for_tts(text: str, max_length: int = 400) -> str:
    """
    Sanitizes and truncates text before sending to Sarvam TTS API.
    Guarantees clean, human-readable text under max_length and replaces
    raw exceptions/stack traces with a short generic spoken message.
    """
    if not text or not text.strip():
        return ""

    raw_lower = text.lower()

    # 1. Detect raw exception or stack trace patterns
    if any(re.search(pattern, raw_lower) for pattern in STACK_TRACE_PATTERNS):
        logger.info(f"Raw stack trace or exception pattern detected in TTS input. Substituting with generic TTS message.")
        return GENERIC_ERROR_TTS

    # 2. Clean newlines, tabs, and excess whitespace
    clean_text = re.sub(r"[\r\n\t]+", " ", text)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()

    # 3. If error message is longer than 200 characters and contains failure/error keywords
    if len(clean_text) > 200 and any(kw in raw_lower for kw in ["failed", "error", "exception", "refused", "timeout"]):
        logger.info(f"Long error message (>200 chars) detected for TTS. Substituting with generic error speech.")
        return GENERIC_ERROR_TTS

    # 4. Truncate if exceeds max_length
    if len(clean_text) > max_length:
        logger.info(f"TTS text length ({len(clean_text)}) exceeds max_length ({max_length}). Truncating.")
        clean_text = clean_text[: max_length - 3].rstrip() + "..."

    return clean_text
