import difflib
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
    TRIGGER_KEYWORDS = ["trigger", "start", "run", "build", "execute", "launch", "deploy"]
    STATUS_KEYWORDS = ["status", "state", "check", "how is", "info"]
    LOGS_KEYWORDS = ["log", "logs", "console", "output"]
    LIST_KEYWORDS = ["list", "show all", "all jobs", "available jobs"]

    PREPOSITIONS = ["for", "of", "the", "job", "project", "build", "called", "named", "on", "in", "to", "app"]

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

        # If job_name was matched via fuzzy/exact matching but intent was UNKNOWN, default to TRIGGER_BUILD or GET_STATUS if keywords match
        if intent == IntentType.UNKNOWN and job_name:
            intent = IntentType.TRIGGER_BUILD

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

        # Trigger / Build / Deploy keywords
        if self._has_keyword(text, self.TRIGGER_KEYWORDS):
            return IntentType.TRIGGER_BUILD

        return IntentType.UNKNOWN

    def _extract_job_name(
        self,
        text: str,
        known_jobs: Optional[List[str]] = None,
    ) -> Optional[str]:
        """Extracts job name from command text, leveraging known_jobs list and fuzzy matching."""
        # 1. Exact or normalized substring match against known_jobs
        if known_jobs:
            for job in known_jobs:
                job_clean = job.lower().replace("-", " ").replace("_", " ")
                if job.lower() in text:
                    return job
                if job_clean in text.replace("-", " ").replace("_", " "):
                    return job

        # 2. Position-independent pattern matching (job before OR after keyword)
        # e.g., "blog-app-dev deploy", "deploy app blog-app-dev", "trigger build for blog-app-dev"
        patterns = [
            r"([a-zA-Z0-9\-_]+)\s+(?:deploy|build|job|status|trigger|run|start|stop|abort)",
            r"(?:for|of|job|project|named|called)\s+([a-zA-Z0-9\-_]+)",
            r"(?:trigger|start|run|build|deploy|status|check|stop|abort|logs?)\s+(?:build|job|project|app)?\s*([a-zA-Z0-9\-_]+)",
        ]

        action_words = set(self.STOP_KEYWORDS + self.TRIGGER_KEYWORDS + self.STATUS_KEYWORDS + self.LOGS_KEYWORDS + self.PREPOSITIONS)

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                candidate = match.group(1).strip()
                if candidate and candidate not in action_words:
                    if known_jobs and candidate not in known_jobs:
                        matches = difflib.get_close_matches(candidate.lower(), [j.lower() for j in known_jobs], n=1, cutoff=0.5)
                        if matches:
                            matched_lower = matches[0]
                            for j in known_jobs:
                                if j.lower() == matched_lower:
                                    logger.info(f"Fuzzy matched extracted candidate '{candidate}' to known job '{j}'")
                                    return j
                    return candidate

        # 3. Fuzzy matching fallback using difflib against known_jobs
        if known_jobs:
            words = text.split()
            # Try single tokens and pairs of tokens
            candidates_to_test = words + [f"{words[i]}-{words[i+1]}" for i in range(len(words)-1)]
            for token in candidates_to_test:
                clean_token = token.strip().lower()
                if clean_token in action_words or len(clean_token) < 2:
                    continue
                matches = difflib.get_close_matches(clean_token, [j.lower() for j in known_jobs], n=1, cutoff=0.55)
                if matches:
                    matched_lower = matches[0]
                    for j in known_jobs:
                        if j.lower() == matched_lower:
                            logger.info(f"Fuzzy matched '{token}' to known job '{j}'")
                            return j

        # 4. Token filtering fallback: remove keywords and prepositions
        words = text.split()
        filtered = [
            w for w in words
            if w not in action_words
            and w not in ["what", "is", "the", "a", "an", "please", "can", "you", "my", "in", "jenkins"]
        ]

        if filtered:
            return "-".join(filtered) if len(filtered) > 1 and len(words) <= 5 else filtered[-1]

        return None


intent_parser = IntentParser()
