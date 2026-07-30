import pytest
from app.utils.sanitizer import GENERIC_ERROR_TTS, sanitize_for_tts


def test_sanitize_normal_text():
    text = "  my-project build has been triggered in the browser.\n  "
    sanitized = sanitize_for_tts(text)
    assert sanitized == "my-project build has been triggered in the browser."


def test_sanitize_stack_trace_replacement():
    raw_stack_trace = """
    Failed to retrieve console logs:
    Traceback (most recent call last):
      File "app/services/jenkins_client.py", line 42, in get_console_output
        raise Exception("403 Forbidden")
    """
    sanitized = sanitize_for_tts(raw_stack_trace)
    assert sanitized == GENERIC_ERROR_TTS


def test_sanitize_long_error_message():
    long_error = (
        "Jenkins browser operation failed: Could not find 'Build Now' button for job 'my-project'. "
        "Detailed reason: HTTP 500 Server Error connecting to http://13.202.2.200:8080/job/my-project/build "
        "due to connection timeout after 30 seconds."
    )
    sanitized = sanitize_for_tts(long_error)
    assert sanitized == GENERIC_ERROR_TTS


def test_sanitize_truncation():
    very_long_normal_text = "This is a very long clean text description " * 15
    sanitized = sanitize_for_tts(very_long_normal_text, max_length=100)
    assert len(sanitized) <= 100
    assert sanitized.endswith("...")


def test_sanitize_empty_input():
    assert sanitize_for_tts("") == ""
    assert sanitize_for_tts(None) == ""
