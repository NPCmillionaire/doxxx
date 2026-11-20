"""Text scanner for redaction markers and hidden PII.

The scanner is the pure-analysis half of unredact: it takes a document body
and reports every redaction span and every PII shape that survived redaction.
It makes no network requests and is safe to call during pivot extraction.
"""

from typing import List

from doxxx.unredact.models import RedactionReport, RedactionSpan, record_slug
from doxxx.unredact.tools import (
    HIDDEN_INFO_PATTERNS,
    REDACTION_PATTERNS,
    analyze_redaction_patterns,
    find_redacted_spans,
)


def scan_text(
    text: str,
    target: str,
    *,
    min_span_length: int = 3,
    include_pii_scan: bool = True,
) -> RedactionReport:
    """Scan ``text`` for redaction markers and hidden PII.

    Args:
        text: The document body to analyze.
        target: The file path or URL the text came from (used for reporting).
        min_span_length: Drop redaction spans shorter than this.
        include_pii_scan: When false, only count redaction markers.

    Returns:
        A :class:`RedactionReport` describing every span found.
    """
    raw_spans = find_redacted_spans(text)
    spans: List[RedactionSpan] = []
    for start, end, matched in raw_spans:
        if len(matched) < min_span_length:
            continue
        spans.append(
            RedactionSpan(
                start=start,
                end=end,
                text=matched,
                pattern=_matching_pattern(matched),
            )
        )

    report = analyze_redaction_patterns(text)
    redaction_counts = {
        key: count for key, count in report.items() if not _is_pii_key(key)
    }
    pii_counts = {key: count for key, count in report.items() if _is_pii_key(key)}

    if not include_pii_scan:
        pii_counts = {}

    return RedactionReport(
        target_id=record_slug(target),
        target_path=target,
        spans=spans,
        redaction_counts=redaction_counts,
        pii_counts=pii_counts,
    )


def _matching_pattern(matched: str) -> str:
    """Return the regex pattern string that produced *matched*."""
    for pattern in REDACTION_PATTERNS:
        if pattern.fullmatch(matched):
            return pattern.pattern
    return "unknown"


def _is_pii_key(key: str) -> bool:
    """True when *key* names a PII pattern rather than a redaction marker."""
    return any(key == pattern.pattern for pattern in HIDDEN_INFO_PATTERNS)