"""Tests for the competitor price tracker."""

from doxxx.track.models import CheckResult, PriceRecord, TrackedProduct, compute_change, product_slug
from doxxx.track.pricing import detect_currency, find_meta, page_title, parse_price, scrape_price
from doxxx.track.store import JsonStore, SqliteStore, resolve_store_path, get_store
from doxxx.track.tracker import PriceTracker, TrackConfig


def test_product_slug():
    assert product_slug("https://www.amazon.com/dp/B07FPH5XN4") == "amazon.com/dp/b07fph5xn4"
    assert product_slug("https://www.google.com") == "google.com"


def test_parse_price_variants():
    result = parse_price("$1,299.00")
    assert result is not None
    assert result[0] == 1299.0
    assert result[1] == "USD"

    result = parse_price("1.299,00 EUR")
    assert result is not None
    assert result[0] == 1299.0
    assert result[1] == "EUR"

    result = parse_price("£12.99")
    assert result is not None
    assert result[0] == 12.99

    assert parse_price("N/A") is None


def test_detect_currency():
    assert detect_currency("$19.99") == "USD"
    assert detect_currency("€15.00") == "EUR"
    assert detect_currency("12.99") is None


def test_scrape_price_from_jsonld():
    html = """
    <html><head>
    <script type="application/ld+json">
    {"@type": "Product", "name": "Test", "offers": {"price": "29.99", "priceCurrency": "USD", "availability": "InStock"}}
    </script>
    </head><body></body></html>
    """
    candidate = scrape_price(html)
    assert candidate is not None
    assert candidate.price == 29.99
    assert candidate.currency == "USD"
    assert candidate.source == "jsonld"
    assert candidate.in_stock is True


def test_scrape_price_fallback_to_selector():
    html = '<html><body><span class="price">$9.99</span></body></html>'
    candidate = scrape_price(html, selector=".price")
    assert candidate is not None
    assert candidate.price == 9.99
    assert candidate.source == "selector"


def test_find_meta():
    html = """
    <html><head>
    <meta property="og:price:amount" content="49.99" />
    <meta property="og:price:currency" content="USD" />
    </head></html>
    """
    candidates = find_meta(html)
    assert len(candidates) == 1
    assert candidates[0].price == 49.99
    assert candidates[0].source == "meta"


def test_page_title():
    html = "<html><head><title>  Fancy Gadgets  </title></head></html>"
    assert page_title(html) == "Fancy Gadgets"


def test_compute_change():
    change, pct = compute_change(19.99, 29.99)
    assert change == -10.0
    assert pct == -33.34  # approx

    change, pct = compute_change(39.99, 29.99)
    assert change == 10.0
    assert pct == 33.34


def test_check_result_direction():
    product = TrackedProduct(id="test.com/prod/1", url="https://test.com/prod/1", name="Prod 1")
    result = CheckResult(
        product=product,
        price=10.0,
        previous_price=12.0,
        change=-2.0,
        change_pct=-16.67,
    )
    assert result.change_direction == "drop"
    assert result.is_error is False


def test_json_store_roundtrip(tmp_path):
    store = JsonStore(str(tmp_path / "tracker.json"))
    product = TrackedProduct(
        id="test.com/prod/1",
        url="https://test.com/prod/1",
        name="Prod 1",
        currency="USD",
    )
    store.add_product(product)

    assert len(store.list_products()) == 1
    assert store.get_product("test.com/prod/1") is not None
    assert store.remove_product("test.com/prod/1") is True
    assert store.list_products() == []


def test_json_store_history(tmp_path):
    store = JsonStore(str(tmp_path / "tracker.json"))
    store.add_product(TrackedProduct(id="test.com/prod/1", url="https://test.com/prod/1", name="Prod 1"))
    store.add_record(PriceRecord(product_id="test.com/prod/1", price=10.0, currency="USD", source="jsonld"))
    store.add_record(PriceRecord(product_id="test.com/prod/1", price=8.0, currency="USD", source="jsonld"))
    history = store.history("test.com/prod/1")
    assert len(history) == 2
    assert history[0].price == 10.0
    assert history[1].price == 8.0


def test_sqlite_store_roundtrip(tmp_path):
    store = SqliteStore(str(tmp_path / "tracker.db"))
    store.add_product(TrackedProduct(id="test.com/prod/1", url="https://test.com/prod/1", name="Prod 1"))
    assert store.get_product("test.com/prod/1") is not None
    store.add_record(PriceRecord(product_id="test.com/prod/1", price=15.0, currency="USD", source="jsonld"))
    assert store.last_record("test.com/prod/1").price == 15.0
    history = store.history("test.com/prod/1")
    assert len(history) == 1
    store.close()


def test_resolve_store_path_default():
    assert resolve_store_path(None).name == "tracker.json"


def test_get_store_sqlite_path():
    store = get_store("/tmp/test-tracker.db")
    assert isinstance(store, SqliteStore)
    store.close()


def test_tracker_check_with_mock_fetcher():
    JsonStore("/tmp/test-price-tracker.json")
    tracker = PriceTracker(store_arg=None, config=TrackConfig(fetcher=lambda url: "<html></html>"))
    results = tracker.check(product_ids=["/"])
    # Should handle gracefully without crashing
    for result in results:
        assert isinstance(result, CheckResult)


def test_price_tracker_add_and_list():
    tracker = PriceTracker(store_arg=None, config=TrackConfig())
    product = tracker.add("https://example.com/prod", name="Prod", currency="USD")
    assert product.url == "https://example.com/prod"
    products = tracker.list_products()
    assert len(products) >= 1
    tracker.remove(product.id)
