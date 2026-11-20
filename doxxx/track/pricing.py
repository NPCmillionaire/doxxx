"""Price extraction from retailer HTML.

Extraction order (most reliable first):

1. An explicit user CSS selector / regex (per-product override).
2. JSON-LD ``Product``/``Offer`` structured data (schema.org).
3. OpenGraph / microdata ``<meta>`` price tags.

The parser is dependency-free: a tiny HTML tree builder plus a small CSS
subset matcher cover the selectors price elements actually use.
"""

import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

_CURRENCY_SYMBOLS = {
    "R$": "BRL",
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "₹": "INR",
    "₩": "KRW",
    "₽": "RUB",
    "₺": "TRY",
    "₴": "UAH",
    "₦": "NGN",
    "₱": "PHP",
    "₪": "ILS",
    "฿": "THB",
    "₫": "VND",
    "zł": "PLN",
    "Kč": "CZK",
    "kr": "SEK",
}

_CURRENCY_CODES = ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "CNY", "RMB", "INR", "BRL", "RUB", "KRW", "MXN", "SEK", "NOK", "DKK", "PLN", "CZK", "HUF", "TRY", "ZAR", "SGD", "HKD", "NZD", "AED", "SAR", "ILS", "THB", "VND", "PHP", "IDR", "MYR"]

_CODE_RE = re.compile(rf"\b({'|'.join(_CURRENCY_CODES)})\b", re.IGNORECASE)
_NUMBER_RE = re.compile(r"\d[\d.,'\u00a0 ]*\d|\d")
_META_TAG_RE = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
_JSONLD_RE = re.compile(
    r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)


@dataclass
class PriceCandidate:
    """A single extracted price plus where it came from."""

    price: float
    currency: str | None = None
    in_stock: bool | None = None
    source: str = "unknown"


def detect_currency(text: str) -> str | None:
    """Guess the ISO currency code from a price snippet."""
    if not text:
        return None
    # Longest symbols first so "R$" wins over "$".
    for symbol in sorted(_CURRENCY_SYMBOLS, key=len, reverse=True):
        if symbol in text:
            return _CURRENCY_SYMBOLS[symbol]
    match = _CODE_RE.search(text)
    if match:
        return match.group(1).upper()
    return None


def _to_float(number: str) -> float | None:
    """Convert a locale-formatted numeric string to a float."""
    cleaned = number.replace("\u00a0", "").replace(" ", "").replace("'", "")
    if not cleaned:
        return None
    has_dot = "." in cleaned
    has_comma = "," in cleaned
    try:
        if has_dot and has_comma:
            # The rightmost separator is the decimal one.
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif has_comma:
            tail = cleaned.rsplit(",", 1)[1]
            if len(tail) in (1, 2):
                cleaned = cleaned.replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif has_dot:
            tail = cleaned.rsplit(".", 1)[1]
            if len(tail) == 3 and cleaned.count(".") >= 1:
                # "1.299" is ambiguous: three trailing digits read as thousands.
                cleaned = cleaned.replace(".", "")
        return float(cleaned)
    except ValueError:
        return None


def parse_price(raw: str) -> tuple[float, str | None] | None:
    """Parse the first price-like number out of a string.

    Supports ``$1,299.00``, ``1.299,00 €``, ``12,99£`` and similar formats.
    Returns ``(price, currency)`` or ``None`` when no number is present.
    """
    if not raw:
        return None
    match = _NUMBER_RE.search(raw)
    if not match:
        return None
    value = _to_float(match.group(0))
    if value is None:
        return None
    return value, detect_currency(raw)


# --------------------------------------------------------------------------
# Minimal HTML tree + CSS subset matcher
# --------------------------------------------------------------------------

_VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


class _Element:
    __slots__ = ("attrs", "parent", "tag", "text_parts")

    def __init__(self, tag: str, attrs: dict[str, str], parent: "_Element | None" = None):
        self.tag = tag
        self.attrs = attrs
        self.parent = parent
        self.text_parts: list[str] = []

    def text(self) -> str:
        return " ".join("".join(self.text_parts).split())


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Element("root", {})
        self.stack: list[_Element] = [self.root]
        self.elements: list[_Element] = []

    def _open(self, tag: str, attrs: list[tuple[str, str | None]]) -> _Element:
        element = _Element(tag, {k: (v or "") for k, v in attrs}, self.stack[-1])
        self.stack[-1].text_parts  # noqa: B018 - keep the parent alive
        self.elements.append(element)
        if tag not in _VOID_TAGS:
            self.stack.append(element)
        return element

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._open(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._open(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID_TAGS:
            return
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self.stack[-1].text_parts.append(data)


@dataclass
class _SimpleSelector:
    tag: str | None = None
    element_id: str | None = None
    classes: list[str] = field(default_factory=list)
    attrs: list[tuple[str, str | None, str | None]] = field(default_factory=list)


def _parse_simple_selector(selector: str) -> _SimpleSelector | None:
    result = _SimpleSelector(classes=[], attrs=[])
    index = 0
    length = len(selector)
    while index < length:
        char = selector[index]
        if char == "#":
            end = index + 1
            while end < length and (selector[end].isalnum() or selector[end] in "-_"):
                end += 1
            if end == index + 1:
                return None
            result.element_id = selector[index + 1:end]
            index = end
        elif char == ".":
            end = index + 1
            while end < length and (selector[end].isalnum() or selector[end] in "-_"):
                end += 1
            if end == index + 1:
                return None
            result.classes.append(selector[index + 1:end])
            index = end
        elif char == "[":
            end = selector.find("]", index)
            if end == -1:
                return None
            parsed = re.fullmatch(
                r"\[([\w:-]+)(?:([~|^$*]?=)\s*[\"']?([^\"'\]]*)[\"']?)?\]",
                selector[index:end + 1],
            )
            if not parsed:
                return None
            result.attrs.append((parsed.group(1), parsed.group(2), parsed.group(3)))
            index = end + 1
        elif char.isalpha():
            end = index
            while end < length and (selector[end].isalnum() or selector[end] == "-"):
                end += 1
            result.tag = selector[index:end]
            index = end
        else:
            return None
    return result


def _attr_matches(actual: str | None, op: str | None, expected: str | None) -> bool:
    if actual is None:
        return False
    if op is None:
        return True
    expected = expected or ""
    if op == "=":
        return actual == expected
    if op == "~=":
        return expected in actual.split()
    if op == "^=":
        return actual.startswith(expected)
    if op == "$=":
        return actual.endswith(expected)
    if op == "*=":
        return expected in actual
    if op == "|=":
        return actual == expected or actual.startswith(expected + "-")
    return False


def _simple_matches(element: _Element, simple: _SimpleSelector) -> bool:
    if simple.tag and element.tag != simple.tag:
        return False
    if simple.element_id and element.attrs.get("id") != simple.element_id:
        return False
    if simple.classes:
        present = set(element.attrs.get("class", "").split())
        if any(name not in present for name in simple.classes):
            return False
    for name, op, expected in simple.attrs or []:
        if not _attr_matches(element.attrs.get(name), op, expected):
            return False
    return True


def _selector_matches(element: _Element, chain: list[_SimpleSelector]) -> bool:
    """Match a descendant selector chain against an element, walking ancestors.

    ``chain[-1]`` describes the element itself; the preceding selectors are
    required ancestors (e.g. ``div .price`` -> div ancestor + .price element).
    A single-element chain means "the element itself must match".
    """
    if not chain or not _simple_matches(element, chain[-1]):
        return False
    remaining = chain[:-1]
    current = element.parent
    while remaining:
        while current is not None and not _simple_matches(current, remaining[-1]):
            current = current.parent
        if current is None:
            return False
        remaining = remaining[:-1]
        current = current.parent
    return True


def _parse_selector(selector: str) -> list[_SimpleSelector] | None:
    chain: list[_SimpleSelector] = []
    for part in selector.split():
        simple = _parse_simple_selector(part)
        if simple is None:
            return None
        chain.append(simple)
    return chain or None


def _build_tree(html: str) -> _TreeBuilder:
    builder = _TreeBuilder()
    try:
        builder.feed(html)
        builder.close()
    except Exception:  # noqa: BLE001, S110 - malformed markup is tolerated
        # Malformed markup: return whatever parsed before the failure.
        pass
    return builder


def find_by_selector(html: str, selector: str) -> list[PriceCandidate]:
    """Return price candidates for every element matching a CSS selector."""
    chain = _parse_selector(selector)
    if chain is None:
        return []
    builder = _build_tree(html)
    candidates = []
    for element in builder.elements:
        if not _selector_matches(element, chain):
            continue
        parsed = parse_price(element.text())
        if parsed is not None:
            candidates.append(PriceCandidate(price=parsed[0], currency=parsed[1], source="selector"))
    return candidates


def find_by_regex(html: str, pattern: str) -> list[PriceCandidate]:
    """Return price candidates for a user-supplied regex and optional currency group."""
    try:
        compiled = re.compile(pattern, re.DOTALL)
    except re.error:
        return []
    candidates = []
    for match in compiled.finditer(html):
        raw = match.group(1) if match.groups() else match.group(0)
        parsed = parse_price(raw)
        if parsed is not None:
            candidates.append(PriceCandidate(price=parsed[0], currency=parsed[1], source="selector"))
    return candidates


# --------------------------------------------------------------------------
# Structured-data extraction
# --------------------------------------------------------------------------


def _iter_jsonld_nodes(html: str) -> list[Any]:
    nodes: list[Any] = []

    def walk(node: Any) -> None:
        nodes.append(node)
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for match in _JSONLD_RE.finditer(html):
        payload = match.group(1).strip()
        if not payload:
            continue
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue
        walk(data)
    return nodes


def _offers_from_node(node: dict) -> list[dict]:
    offers = node.get("offers")
    if isinstance(offers, dict):
        return [offers]
    if isinstance(offers, list):
        return [offer for offer in offers if isinstance(offer, dict)]
    return []


def _offer_candidate(offer: dict, fallback_currency: str | None = None) -> PriceCandidate | None:
    raw_price = offer.get("price")
    if raw_price is None:
        raw_price = offer.get("lowPrice")
    if raw_price is None:
        raw_price = offer.get("highPrice")
    if raw_price is None:
        return None
    parsed = parse_price(str(raw_price))
    if parsed is None:
        return None
    currency = offer.get("priceCurrency") or fallback_currency
    availability = str(offer.get("availability") or "").lower()
    in_stock: bool | None = None
    if "instock" in availability or "in_stock" in availability:
        in_stock = True
    elif "outofstock" in availability or "soldout" in availability or "out_of_stock" in availability:
        in_stock = False
    return PriceCandidate(price=parsed[0], currency=currency, in_stock=in_stock, source="jsonld")


def find_jsonld(html: str) -> list[PriceCandidate]:
    """Return price candidates from schema.org JSON-LD blocks."""
    candidates: list[PriceCandidate] = []
    for node in _iter_jsonld_nodes(html):
        if not isinstance(node, dict):
            continue
        node_type = node.get("@type")
        types = node_type if isinstance(node_type, list) else [node_type]
        is_product = any(str(t).lower() in ("product", "offer", "aggregateoffer") for t in types)
        if not is_product and "price" not in node and "offers" not in node:
            continue
        fallback_currency = node.get("priceCurrency")
        offers = _offers_from_node(node)
        if offers:
            for offer in offers:
                candidate = _offer_candidate(offer, fallback_currency)
                if candidate is not None:
                    candidates.append(candidate)
        elif node.get("price") is not None:
            parsed = parse_price(str(node["price"]))
            if parsed is not None:
                candidates.append(
                    PriceCandidate(price=parsed[0], currency=fallback_currency, source="jsonld")
                )
    return candidates


def _meta_attr(tag: str, name: str) -> str | None:
    match = re.search(rf"""{name}\s*=\s*["']?([^"'\s>]+)""", tag, re.IGNORECASE)
    return match.group(1) if match else None


def find_meta(html: str) -> list[PriceCandidate]:
    """Return price candidates from OpenGraph/microdata ``<meta>`` tags."""
    price_value: str | None = None
    currency: str | None = None
    availability: str | None = None
    for tag in _META_TAG_RE.findall(html):
        key = (_meta_attr(tag, "property") or _meta_attr(tag, "name") or _meta_attr(tag, "itemprop"))
        if not key:
            continue
        key = key.lower()
        content = _meta_attr(tag, "content")
        if content is None:
            continue
        if key in ("product:price:amount", "og:price:amount", "twitter:price:amount"):
            price_value = content
        elif key in ("product:price:currency", "og:price:currency", "twitter:price:currency"):
            currency = content.upper()
        elif key in ("product:availability", "og:availability"):
            availability = content.lower()
    candidates: list[PriceCandidate] = []
    if price_value is not None:
        parsed = parse_price(price_value)
        if parsed is not None:
            in_stock: bool | None = None
            if availability:
                if "instock" in availability or "in stock" in availability:
                    in_stock = True
                elif "outofstock" in availability or "out of stock" in availability:
                    in_stock = False
            candidates.append(
                PriceCandidate(
                    price=parsed[0],
                    currency=currency or parsed[1],
                    in_stock=in_stock,
                    source="meta",
                )
            )
    return candidates


def scrape_price(
    html: str,
    selector: str | None = None,
    selector_kind: str = "css",
) -> PriceCandidate | None:
    """Extract the best price from an HTML page.

    Priority: explicit selector/regex → JSON-LD → meta tags.
    """
    if selector:
        if selector_kind == "regex":
            results = find_by_regex(html, selector)
        else:
            results = find_by_selector(html, selector)
        if results:
            return results[0]
    for candidates in (find_jsonld(html), find_meta(html)):
        if candidates:
            # Prefer an in-stock offer when the page is a multi-variant product.
            for candidate in candidates:
                if candidate.in_stock is True:
                    return candidate
            return candidates[0]
    return None


def page_title(html: str) -> str | None:
    """Return a cleaned <title> or og:title for auto-naming a tracked product."""
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match:
        title = " ".join(match.group(1).split())
        if title:
            return title
    for tag in _META_TAG_RE.findall(html):
        key = (_meta_attr(tag, "property") or _meta_attr(tag, "name") or "").lower()
        if key == "og:title":
            content = _meta_attr(tag, "content")
            if content:
                return content
    return None
