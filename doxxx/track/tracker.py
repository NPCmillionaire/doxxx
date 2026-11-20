"""PriceTracker: the high-level orchestration layer.

Coordinates fetching product pages, extracting prices, and persisting results.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from doxxx.track.models import (
    CheckResult,
    PriceRecord,
    TrackedProduct,
    compute_change,
    product_slug,
    utc_now_iso,
)
from doxxx.track.pricing import scrape_price
from doxxx.track.store import get_store

# --------------------------------------------------------------------------
# HTTP fetching with optional browser-impersonation fallback
# --------------------------------------------------------------------------

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
}

_TRIGGER_STATUSES = {403, 406, 429, 503}

_impersonation_sessions: dict[tuple[str, str | None], object] = {}
_impersonation_lock = asyncio.Lock()


async def _fetch_with_httpx(
    url: str,
    timeout: float,
    proxy: str | None,
) -> tuple[str, int]:
    async with httpx.AsyncClient(
        http2=True,
        timeout=timeout,
        follow_redirects=True,
        proxy=proxy,
        headers=_BROWSER_HEADERS,
    ) as client:
        response = await client.get(url)
        return response.text, response.status_code


async def _fetch_with_curl_cffi(
    url: str,
    timeout: float,
    proxy: str | None,
) -> tuple[str, int]:
    # Import lazily so the module loads even if curl_cffi is missing.
    from curl_cffi import requests as cffi  # type: ignore[import]

    async with _impersonation_lock:
        key = ("chrome", proxy)
        cached = _impersonation_sessions.get(key)
        if cached is not None and not isinstance(cached, cffi.Session):
            cached = None
        session: cffi.Session | None = cached  # type: ignore[type-misc]
        if session is None:
            session = cffi.Session(
                impersonate="chrome",
                proxies={"http": proxy, "https": proxy} if proxy else None,
            )
            _impersonation_sessions[key] = session
        response = await asyncio.to_thread(
            session.get,
            url,
            timeout=timeout,
            allow_redirects=True,
            headers=_BROWSER_HEADERS,
        )
        return response.text, response.status_code


async def fetch_html(
    url: str,
    timeout: float,
    proxy: str | None = None,
    allow_impersonation: bool = True,
) -> str:
    """Fetch HTML with httpx; on bot walls, fall back to curl_cffi impersonation."""
    try:
        html, status = await _fetch_with_httpx(url, timeout, proxy)
        if status not in _TRIGGER_STATUSES:
            return html
    except Exception:
        if not allow_impersonation:
            raise

    # Fall back to browser-impersonation.
    html, status = await _fetch_with_curl_cffi(url, timeout, proxy)
    # We return whatever we got even if it's an error page — the scraper
    # will return an empty candidate and the tracker records the error.
    return html


# --------------------------------------------------------------------------
# Tracker
# --------------------------------------------------------------------------


@dataclass
class TrackConfig:
    """Runtime configuration for a single price-tracking run."""

    timeout: float = 15.0
    proxy: str | None = None
    allow_impersonation: bool = True
    fetcher: Callable[[str], str] | None = None  # for tests


class PriceTracker:
    """Main entry point for checking and recording prices."""

    def __init__(
        self,
        store_arg: str | None = None,
        config: TrackConfig | None = None,
    ):
        self.config = config or TrackConfig()
        self.store = get_store(store_arg)

    def add(
        self,
        url: str,
        *,
        name: str | None = None,
        selector: str | None = None,
        selector_kind: str = "css",
        currency: str | None = None,
    ) -> TrackedProduct:
        """Register a new product URL for tracking.

        If *name* or *currency* are not supplied, the page is fetched once to
        auto-discover them.
        """
        product_id = product_slug(url)
        existing = self.store.get_product(product_id)
        if existing:
            return existing

        # Try to fetch the page to auto-fill name/currency if missing.
        auto_name: str | None = name
        auto_currency: str | None = currency
        auto_site: str | None = None
        if auto_name is None or auto_currency is None:
            try:
                html = self._fetch(url)
                if auto_name is None:
                    from doxxx.track.pricing import page_title
                    auto_name = page_title(html)
                if auto_currency is None:
                    from doxxx.track.pricing import find_jsonld, find_meta
                    # Try JSON-LD then meta for currency
                    for candidates in (find_jsonld(html), find_meta(html)):
                        for c in candidates:
                            if c.currency:
                                auto_currency = c.currency
                                break
                        if auto_currency:
                            break
                # Site from domain
                from urllib.parse import urlparse

                auto_site = urlparse(url).netloc.replace("www.", "").lower()
            except Exception:  # noqa: BLE001, S110 - best-effort; tracking still works
                pass

        product = TrackedProduct(
            id=product_id,
            url=url,
            name=auto_name,
            site=auto_site,
            currency=auto_currency,
            selector=selector,
            selector_kind=selector_kind,
        )
        self.store.add_product(product)
        return product

    def remove(self, product_id: str) -> bool:
        """Remove a tracked product by its ID."""
        return self.store.remove_product(product_id)

    def list_products(self) -> list[TrackedProduct]:
        """Return all tracked products."""
        return self.store.list_products()

    def find(self, query: str) -> list[TrackedProduct]:
        """Find products by ID or URL substring."""
        return self.store.find_products(query)

    def check(
        self,
        product_ids: list[str] | None = None,
        *,
        fetcher: Callable[[str], str] | None = None,
    ) -> list[CheckResult]:
        """Check prices for *product_ids* (or all tracked products if omitted)."""
        products = self.list_products()
        if product_ids:
            target: set[str] = set(product_ids)
            products = [p for p in products if p.id in target or p.url in target]
        if not products:
            return []

        results: list[CheckResult] = []
        for product in products:
            result = self._check_one(product, fetcher=fetcher)
            results.append(result)
        return results

    def history(
        self,
        product_id: str,
        limit: int | None = None,
    ) -> list[PriceRecord]:
        """Return the price history for a product."""
        return self.store.history(product_id, limit=limit)

    # ---- Internal helpers ----

    def _fetch(self, url: str) -> str:
        """Sync fetch wrapper used by auto-discovery during ``add()``."""
        # Prefer the same async path via the event loop if one is running,
        # but fall back to a synchronous request for simplicity in ``add()``.
        # The core check() path uses the async fetcher below.
        try:
            return asyncio.run(
                fetch_html(
                    url,
                    self.config.timeout,
                    self.config.proxy,
                    self.config.allow_impersonation,
                )
            )
        except Exception:  # noqa: BLE001 - if async fails (no loop), fall back to synchronous httpx.
            # If async fails (no loop), fall back to synchronous httpx.
            resp = httpx.get(
                url,
                headers=_BROWSER_HEADERS,
                timeout=self.config.timeout,
                follow_redirects=True,
                proxy=self.config.proxy,
            )
            return resp.text

    async def _async_fetch(self, url: str) -> str:
        """Async fetch used by the main check path."""
        if self.config.fetcher:
            return self.config.fetcher(url)
        return await fetch_html(
            url,
            self.config.timeout,
            self.config.proxy,
            self.config.allow_impersonation,
        )

    def _check_one(
        self,
        product: TrackedProduct,
        fetcher: Callable[[str], str] | None = None,
    ) -> CheckResult:
        """Check a single product synchronously."""
        previous = self.store.last_record(product.id)
        try:
            # Prefer the injected fetcher if given (tests), else use async.
            if fetcher:
                html = fetcher(product.url)
            else:
                html = asyncio.run(
                    fetch_html(
                        product.url,
                        self.config.timeout,
                        self.config.proxy,
                        self.config.allow_impersonation,
                    )
                )
        except Exception as exc:  # noqa: BLE001 - fetch errors are captured and recorded
            record = PriceRecord(
                product_id=product.id,
                price=None,
                currency=None,
                in_stock=None,
                checked_at=utc_now_iso(),
                source="error",
                error=str(exc),
            )
            self.store.add_record(record)
            return CheckResult(
                product=product,
                price=None,
                currency=None,
                in_stock=None,
                source="error",
                error=str(exc),
                previous_price=previous.price if previous else None,
                previous_checked_at=previous.checked_at if previous else None,
            )

        candidate = scrape_price(html, product.selector, product.selector_kind)
        if candidate is None:
            record = PriceRecord(
                product_id=product.id,
                price=None,
                currency=None,
                in_stock=None,
                checked_at=utc_now_iso(),
                source="none",
                error="No price found",
            )
            self.store.add_record(record)
            return CheckResult(
                product=product,
                price=None,
                currency=None,
                in_stock=None,
                source="none",
                error="No price found",
                previous_price=previous.price if previous else None,
                previous_checked_at=previous.checked_at if previous else None,
            )

        # Successful extraction
        price = candidate.price
        currency = candidate.currency or product.currency
        change, change_pct = compute_change(price, previous.price if previous else None)
        record = PriceRecord(
            product_id=product.id,
            price=price,
            currency=currency,
            in_stock=candidate.in_stock,
            checked_at=utc_now_iso(),
            source=candidate.source,
            error=None,
        )
        self.store.add_record(record)
        return CheckResult(
            product=product,
            price=price,
            currency=currency,
            in_stock=candidate.in_stock,
            source=candidate.source,
            error=None,
            previous_price=previous.price if previous else None,
            previous_checked_at=previous.checked_at if previous else None,
            change=change,
            change_pct=change_pct,
        )
