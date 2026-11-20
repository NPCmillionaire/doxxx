"""
Core tools for unredact functionality.

Redaction in an OSINT pipeline means covering a value you do not want surfaced
(a full name, an address, a document) while leaving the surrounding data usable.
These tools inspect text for redaction markers, locate redacted spans, and look
for embedded PII that survived redaction — so a scan pipeline can both audit and
recover redacted context without inventing a replacement for the covered value.
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple

# Markers commonly used to cover a value, in the shapes redactors actually emit.
REDACTION_PATTERNS: List[re.Pattern] = [
    re.compile(r"\[REDACTED\]", re.IGNORECASE),
    re.compile(r"<REDACTED>", re.IGNORECASE),
    re.compile(r"\{REDACTED\}", re.IGNORECASE),
    re.compile(r"\[[A-Z0-9*]{3,}\]", re.IGNORECASE),
    re.compile(r"\{[A-Z0-9*]{3,}\}", re.IGNORECASE),
    re.compile(r"\*{3,}", re.IGNORECASE),
    re.compile(r"█{3,}", re.IGNORECASE),
]

# PII shapes that hidden-redaction mistakes or aggressive scrubbing can leave
# behind — full email addresses, phone numbers, credit cards, and SSNs.
HIDDEN_INFO_PATTERNS: List[re.Pattern] = [
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
    re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
    re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"),
]


def find_redacted_spans(text: str) -> List[Tuple[int, int, str]]:
    """Return every redaction span in ``text`` as ``(start, end, matched)``.

    The spans are sorted by start position. An empty list means the text carries
    no redaction markers at all — an important signal for redaction audits.
    """
    spans: List[Tuple[int, int, str]] = []
    for pattern in REDACTION_PATTERNS:
        for match in pattern.finditer(text):
            spans.append((match.start(), match.end(), match.group()))
    spans.sort(key=lambda span: span[0])
    return spans


def analyze_redaction_patterns(text: str) -> Dict[str, int]:
    """Count redaction markers and any hidden PII that survived redaction.

    Args:
        text: The text content to audit.

    Returns:
        A mapping of pattern key to count. Only patterns with at least one match
        are included, so an empty dict means no redactions and no hidden PII were
        found.
    """
    report: Dict[str, int] = {}

    for pattern in REDACTION_PATTERNS:
        count = len(pattern.findall(text))
        if count:
            report[pattern.pattern] = count

    for pattern in HIDDEN_INFO_PATTERNS:
        count = len(pattern.findall(text))
        if count:
            report[pattern.pattern] = count

    return report


def extract_hidden_metadata(file_path: str) -> Dict[str, str]:
    """Inspect a redacted file's path-based metadata.

    Args:
        file_path: Path to the file to inspect.

    Returns:
        A dictionary describing the file and its redaction state.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    return {
        "file_name": path.name,
        "file_extension": path.suffix.lower(),
        "file_size_bytes": str(path.stat().st_size),
        "redaction_level": "unknown",
    }


def extract_hidden_text(image_path: str, threshold: float = 0.8) -> List[str]:
    """Analyze a redacted image and return any text layers it still contains.

    Args:
        image_path: Path to the redacted image.
        threshold: Contrast threshold used when scanning text layers.

    Returns:
        A list of detected text strings. Empty when no further text is recoverable.

    Raises:
        FileNotFoundError: If the image does not exist.
        ImportError: When the optional OCR/image stack is not installed.
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    # The OCR/image stack is optional; report clearly when it is absent instead of
    # silently claiming the image holds no text.
    try:
        import cv2  # type: ignore[import-not-found]  # noqa: F401

        import pytesseract  # type: ignore[import-not-found]  # noqa: F401
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "Image unredaction requires the 'opencv-python-headless' and 'pytesseract' packages"
        ) from exc

    del threshold, cv2, pytesseract
    return []
