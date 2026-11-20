"""Unredactor: the high-level orchestration layer for redaction analysis.

Coordinates reading a document body, scanning it for redaction markers and
hidden PII, and persisting results.
"""

from dataclasses import dataclass
from typing import Optional

from doxxx.unredact.models import RedactionReport, UnredactConfig, UnredactRecord, record_slug
from doxxx.unredact.scanner import scan_text
from doxxx.unredact.store import get_store


@dataclass
class ScanResult:
    """Outcome of a single unredaction scan."""

    target: str
    report: RedactionReport
    is_error: bool = False
    error: str | None = None

    @property
    def status(self) -> str:
        return "error" if self.is_error else "ok"


class Unredactor:
    """Main entry point for analyzing documents for redactions."""

    def __init__(self, store_arg: str | None = None, config: UnredactConfig | None = None):
        self.config = config or UnredactConfig(store_path=store_arg)
        self.store = get_store(self.config.store_path)

    def scan(self, target: str, *, content: str | None = None) -> ScanResult:
        """Analyze *target* for redaction markers and hidden PII.

        Args:
            target: File path or URL of the document to analyze.
            content: Inline text content to analyze (if supplied, *target* is
              only used as an identifier; otherwise the file at *target* is read).

        Returns:
            A :class:`ScanResult` containing the :class:`RedactionReport`.
        """
        target_id = record_slug(target)

        try:
            text = content if content is not None else self._read(target)
            report = scan_text(
                text,
                target,
                min_span_length=self.config.min_span_length,
                include_pii_scan=self.config.include_pii_scan,
            )

            record = UnredactRecord(
                target_id=target_id,
                target_path=target,
                report=report,
                metadata={"format": "text"},
            )
            self.store.add_record(record)

            return ScanResult(target=target, report=report)
        except FileNotFoundError as exc:
            return ScanResult(
                target=target,
                report=self._empty_report(target_id, target),
                is_error=True,
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001 - capture and record scan errors
            return ScanResult(
                target=target,
                report=self._empty_report(target_id, target),
                is_error=True,
                error=str(exc),
            )

    def history(self, target: str, limit: int | None = None):
        """Return previously stored analysis results for *target*."""
        target_id = record_slug(target)
        return self.store.history(target_id, limit=limit)

    def last_report(self, target: str) -> Optional[dict]:
        """Return the last stored analysis for *target*."""
        target_id = record_slug(target)
        return self.store.last_record(target_id)

    # ---- Internal helpers ----

    @staticmethod
    def _read(target: str) -> str:
        """Read the full text content of a local file."""
        from pathlib import Path

        path = Path(target).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {target}")
        return path.read_text(encoding="utf-8", errors="replace")

    @staticmethod
    def _empty_report(target_id: str, target: str) -> RedactionReport:
        return RedactionReport(
            target_id=target_id,
            target_path=target,
            spans=[],
            redaction_counts={},
            pii_counts={},
        )
