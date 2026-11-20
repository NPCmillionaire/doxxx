"""Core data models for the competitor price tracker."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


def utc_now_iso() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def product_slug(url: str) -> str:
    """Build a stable, machine-friendly product id from a product URL."""
    from urllib.parse import urlparse

    cleaned = (url or "").strip().lower()
    if not cleaned:
        return ""
    parsed = urlparse(cleaned if "://" in cleaned else f"https://{cleaned}")
    host = (parsed.netloc or parsed.path or "").lower().removeprefix("www.")
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    slug = "/".join(parts)
    return f"{host}/{slug}" if slug else host


@dataclass
class TrackedProduct:
    """A product/competitor listing the user wants to watch."""

    id: str
    url: str = ""
    name: str | None = None
    site: str | None = None
    currency: str | None = None
    selector: str | None = None
    selector_kind: str = "css"
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "name": self.name,
            "site": self.site,
            "currency": self.currency,
            "selector": self.selector,
            "selector_kind": self.selector_kind,
            "created_at": self.created_at,
        }


@dataclass
class PriceRecord:
    """A single price observation for a tracked product."""

    product_id: str
    price: float | None = None
    currency: str | None = None
    in_stock: bool | None = None
    checked_at: str = field(default_factory=utc_now_iso)
    source: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "price": self.price,
            "currency": self.currency,
            "in_stock": self.in_stock,
            "checked_at": self.checked_at,
            "source": self.source,
            "error": self.error,
        }


@dataclass
class CheckResult:
    """Outcome of a single price check, including the change vs the last record."""

    product: TrackedProduct
    price: float | None = None
    currency: str | None = None
    in_stock: bool | None = None
    source: str | None = None
    error: str | None = None
    checked_at: str = field(default_factory=utc_now_iso)
    previous_price: float | None = None
    previous_checked_at: str | None = None
    change: float | None = None
    change_pct: float | None = None

    @property
    def is_error(self) -> bool:
        return self.error is not None

    @property
    def change_direction(self) -> str | None:
        """Return 'drop', 'rise', or None when no comparable previous price exists."""
        if self.price is None or self.previous_price is None or self.previous_price == 0:
            return None
        change = self.price - self.previous_price
        if abs(change) < 1e-9:
            return None
        return "drop" if change < 0 else "rise"

    def to_dict(self) -> dict:
        return {
            "id": self.product.id,
            "url": self.product.url,
            "name": self.product.name,
            "site": self.product.site,
            "price": self.price,
            "currency": self.currency,
            "in_stock": self.in_stock,
            "source": self.source,
            "error": self.error,
            "checked_at": self.checked_at,
            "previous_price": self.previous_price,
            "previous_checked_at": self.previous_checked_at,
            "change": self.change,
            "change_pct": self.change_pct,
            "status": "error" if self.is_error else "ok",
        }


def compute_change(current: float | None, previous: float | None) -> tuple[float | None, float | None]:
    """Return (absolute change, percent change) between two prices."""
    if current is None or previous is None or previous == 0:
        return None, None
    change = round(current - previous, 2)
    pct = round((change / previous) * 100, 2)
    return change, pct
