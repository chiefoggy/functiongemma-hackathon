"""
Privacy scrubber: redact sensitive keywords (names, IDs, etc.) from text before sending to cloud.
"""
import re
from typing import List, Optional

# Default sensitive patterns (extend via config later)
DEFAULT_SENSITIVE_KEYWORDS: List[str] = []


def scrub(text: str, keywords: Optional[List[str]] = None) -> str:
    """
    Redact keywords from text. Replaces whole-word matches with [REDACTED].
    """
    if not text:
        return text
    kw = keywords if keywords is not None else DEFAULT_SENSITIVE_KEYWORDS
    out = text
    for k in kw:
        if not k.strip():
            continue
        # Whole-word replacement
        pattern = re.compile(re.escape(k), re.IGNORECASE)
        out = pattern.sub("[REDACTED]", out)
    return out


def set_sensitive_keywords(keywords: List[str]) -> None:
    """Update the default keyword list (e.g. from API or config)."""
    global DEFAULT_SENSITIVE_KEYWORDS
    DEFAULT_SENSITIVE_KEYWORDS = list(keywords)
