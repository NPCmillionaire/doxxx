"""Competitor price tracking package for doxxx.

Provides the `doxxx-track` CLI and a Python library for programmatic use.
"""

from doxxx.track.models import (
    CheckResult,
    PriceRecord,
    TrackedProduct,
    compute_change,
    product_slug,
)
from doxxx.track.tracker import PriceTracker, TrackConfig

__all__ = [
    "CheckResult",
    "PriceRecord",
    "PriceTracker",
    "TrackConfig",
    "TrackedProduct",
    "compute_change",
    "product_slug",
]