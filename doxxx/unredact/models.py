"""Core data models for the unredact tool."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def utc_now_iso() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record_slug(target: str) -> str:
    """Build a stable, machine-friendly id from a file path or URL."""
    cleaned = (target or "").strip().lower()
    if not cleaned:
        return ""
    if "://" in cleaned:
        from urllib.parse import urlparse

        parsed = urlparse(cleaned)
        host = parsed.netloc.replace("www.", "").lower()
        url_path = "/".join(part for part in parsed.path.strip("/").split("/") if part)
        return f"{host}/{url_path}" if url_path else host
    # Local file path
    file_path = Path(cleaned)
    parts = [part for part in file_path.parts if part and part not in (".", "..")]
    return "/".join(parts[-3:]) if len(parts) > 3 else "/".join(parts)


@dataclass
class RedactionSpan:
    """A single redacted span found in a document."""

    start: int
    end: int
    text: str
    pattern: str

    def to_dict(self) -> dict:
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "pattern": self.pattern,
        }


@dataclass
class RedactionReport:
    """Result of analyzing a document for redactions."""

    target_id: str
    target_path: str
    spans: list[RedactionSpan]
    redaction_counts: dict[str, int]
    pii_counts: dict[str, int]
    analyzed_at: str = field(default_factory=utc_now_iso)

    @property
    def total_spans(self) -> int:
        return len(self.spans)

    @property
    def has_redactions(self) -> bool:
        return bool(self.redaction_counts)

    @property
    def has_pii_leaks(self) -> bool:
        return bool(self.pii_counts)

    def to_dict(self) -> dict:
        return {
            "target_id": self.target_id,
            "target_path": self.target_path,
            "spans": [s.to_dict() for s in self.spans],
            "redaction_counts": self.redaction_counts,
            "pii_counts": self.pii_counts,
            "analyzed_at": self.analyzed_at,
            "total_spans": self.total_spans,
            "has_redactions": self.has_redactions,
            "has_pii_leaks": self.has_pii_leaks,
        }


@dataclass
class UnredactRecord:
    """A persisted record of an unredaction analysis."""

    target_id: str
    target_path: str
    report: RedactionReport
    metadata: dict[str, str]
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict:
        return {
            "target_id": self.target_id,
            "target_path": self.target_path,
            "report": self.report.to_dict(),
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


@dataclass
class UnredactConfig:
    """Runtime configuration for an unredaction run."""

    store_path: Optional[str] = None
    min_span_length: int = 3
    include_pii_scan: bool = True