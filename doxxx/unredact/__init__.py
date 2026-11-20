"""doxxx.unredact - Tools for handling redaction and unredaction tasks

This package provides functionality for analyzing and revealing redacted content
within the doxxx OSINT suite.
"""

from .models import (
    RedactionReport,
    RedactionSpan,
    UnredactConfig,
    UnredactRecord,
    record_slug,
)
from .scanner import scan_text
from .store import JsonStore, SqliteStore, get_store, resolve_store_path
from .tools import (
    analyze_redaction_patterns,
    extract_hidden_metadata,
    extract_hidden_text,
    find_redacted_spans,
)
from .unredact import ScanResult, Unredactor

__all__ = [
    "RedactionReport",
    "RedactionSpan",
    "UnredactConfig",
    "UnredactRecord",
    "record_slug",
    "scan_text",
    "JsonStore",
    "SqliteStore",
    "get_store",
    "resolve_store_path",
    "analyze_redaction_patterns",
    "extract_hidden_metadata",
    "extract_hidden_text",
    "find_redacted_spans",
    "ScanResult",
    "Unredactor",
]