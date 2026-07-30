import re
from typing import Any, Dict, List, Optional, Tuple
from app.utils.logger import logger


class IntentType:
    TRIGGER_BUILD = "TRIGGER_BUILD"
    GET_STATUS = "GET_STATUS"
    STOP_BUILD = "STOP_BUILD"
    LIST_JOBS = "LIST_JOBS"
    GET_LOGS = "GET_LOGS"
    UNKNOWN = "UNKNOWN"


class IntentParseResult:
    """Encapsulates the parsed intent and extracted parameters."""

    def __init__(
        self,
        intent: str,
        job_name: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        raw_text: str = "",
        confidence: float = 1.0,
    ) -> None:
        self.intent = intent
        self.job_name = job_name
        self.parameters = parameters or {}
        self.raw_text = raw_text
        self.confidence = confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "job_name": self.job_name,
            "parameters": self.parameters,
            "raw_text": self.raw_text,
            "confidence": self.confidence,
        }


class IntentParser:
    """Parses user spoken text commands to determine Jenkins action and target job."""

    STOP_KEYWORDS = ["stop", "abort", "cancel", "kill", "halt", "terminate"]
    TRIGGER_KEYWORDS = ["trigger", "start", "run", "build", "execute", "launch"]
    STATUS_KEYWORDS = ["status", "state", "check", "how is", "info"]
    LOGS_KEYWORDS = ["log", "logs", "console", "output"]
    LIST_KEYWORDS = ["list", "show all", "all jobs", "available jobs"]

    PREPOSITIONS = ["for", "of", "the", "job", "project", "build", "called", "named", "on", "in", "to"]

    def parse(
        self,
        text: str,
        known_jobs: Optional[List[str]] = None,
    ) -> IntentParseResult:
        """
        Parses raw text input and resolves intent and job name.

        Args:
            text: Transcribed user command text.
            known_jobs: Optional list of known Jenkins job names for fuzzy/exact matching.

        Returns:
            IntentParseResult object.
        """
        if not text or not text.strip():
            return IntentParseResult(intent=IntentType.UNKNOWN, raw_text=text)

        cleaned_text = text.strip().lower()
        logger.info(f"Parsing intent for command text: '{text}'")

        # 1. Determine Intent Type
        intent = self._detect_intent(cleaned_text)

        # 2. Extract Job Name
        job_name = None
        if intent != IntentType.LIST_JOBS and intent != IntentType.UNKNOWN:
            job_name = self._extract_job_name(cleaned_text, known_jobs=known_jobs)

        # Special case: if user said "list jobs" or similar, job_name is None
        if intent == IntentType.UNKNOWN and any(kw in cleaned_text for kw in ["job", "jobs"]):
            intent = IntentType.LIST_JOBS

        logger.info(f"Intent parsed: intent='{intent}', job_name='{job_name}'")
        return IntentParseResult(
            intent=intent,
            job_name=job_name,
            raw_text=text,
            confidence=0.9 if intent != IntentType.UNKNOWN else 0.0,
        )

    def _has_keyword(self, text: str, keywords: List[str]) -> bool:
        """Checks if any keyword matches as a distinct word or phrase in text."""
        for kw in keywords:
            if " " in kw:
                if kw in text:
                    return True
            else:
                if re.search(rf"\b{re.escape(kw)}\b", text):
                    return True
        return False

    def _detect_intent(self, text: str) -> str:
        """Detects primary intent type from text keywords using word boundaries."""
        # Stop / Abort takes priority if stop keywords exist
        if self._has_keyword(text, self.STOP_KEYWORDS):
            return IntentType.STOP_BUILD

        # Check logs / console
        if self._has_keyword(text, self.LOGS_KEYWORDS):
            return IntentType.GET_LOGS

        # Check list all jobs
        if self._has_keyword(text, self.LIST_KEYWORDS) or ("jobs" in text and "all" in text):
            return IntentType.LIST_JOBS

        # Status keywords (check status before trigger if status is present)
        if self._has_keyword(text, self.STATUS_KEYWORDS):
            return IntentType.GET_STATUS

        # Trigger / Build keywords
        if self._has_keyword(text, self.TRIGGER_KEYWORDS):
            return IntentType.TRIGGER_BUILD

        return IntentType.UNKNOWN

    def _extract_job_name(
        self,
        text: str,
        known_jobs: Optional[List[str]] = None,
    ) -> Optional[str]:
        """Extracts job name from command text, leveraging known_jobs list if available."""
        # If known_jobs provided, check for direct or normalized match
        if known_jobs:
            for job in known_jobs:
                job_clean = job.lower().replace("-", " ").replace("_", " ")
                # Check if exact job name is substring
                if job.lower() in text:
                    return job
                # Check normalized job name
                if job_clean in text.replace("-", " ").replace("_", " "):
                    return job

        # Fallback to pattern matching / preposition extraction
        # e.g., "trigger build for my-project" -> extract "my-project"
        patterns = [
            r"(?:for|of|job|project|named|called)\s+([a-zA-Z0-9\-_]+)",
            r"(?:trigger|start|run|build|status|check|stop|abort|logs?)\s+(?:build|job)?\s*([a-zA-Z0-9\-_]+)",
            r"([a-zA-Z0-9\-_]+)\s+(?:build|status|job)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                candidate = match.group(1).strip()
                # Filter out generic action keywords
                if candidate not in self.STOP_KEYWORDS + self.TRIGGER_KEYWORDS + self.STATUS_KEYWORDS + self.LOGS_KEYWORDS + self.PREPOSITIONS:
                    return candidate

        # Token filtering fallback: remove keywords and prepositions
        words = text.split()
        filtered = [
            w for w in words
            if w not in self.STOP_KEYWORDS
            and w not in self.TRIGGER_KEYWORDS
            and w not in self.STATUS_KEYWORDS
            and w not in self.LOGS_KEYWORDS
            and w not in self.LIST_KEYWORDS
            and w not in self.PREPOSITIONS
            and w not in ["what", "is", "the", "a", "an", "please", "can", "you", "my"]
        ]

        if filtered:
            return "-".join(filtered) if len(filtered) > 1 and len(words) <= 5 else filtered[-1]

        return None


intent_parser = IntentParser()
