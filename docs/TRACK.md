# Price Tracking — `doxxx-track`

A competitor price tracker built into the doxxx OSINT suite. Track specific
product URLs over time, record every price change (drops **and** increases),
and alert when a price moves.

## Installation

`doxxx-track` ships with `doxxx`. After installing:

```bash
pip install doxxx
```

The `doxxx-track` console entry point is registered automatically.

## Quick Start

Add a product you want to watch:

```bash
doxxx-track add "https://example.com/products/acme-widget" \
  -n "Acme Widget" -c USD
```

Check its current price (baseline — nothing to compare yet):

```bash
doxxx-track check
```

Add a competitor's listing too:

```bash
doxxx-track add "https://competitor.example.com/acme-widget-alt" \
  -n "Competitor Alt" -c USD
```

Run `check` again and see the change since last time:

```
✅ example.com/products/acme-widget
  Name: Acme Widget
  Site: example.com
  Current: $24.99 (USD)
  In stock: ✅
  Change: → 0.00 (0.00%) from $24.99   ← only on second check

✅ competitor.example.com/acme-widget-alt
  Name: Competitor Alt
  Site: competitor.example.com
  Current: $19.99 (USD)
  In stock: ✅
  Change: ↓ -5.00 (-20.00%) from $24.99   ← drop alert
```

Every check records the result in your store, so each subsequent run shows
the delta against the previous observation.

## Usage

### `doxxx-track add <url>`

Register a product URL for tracking.

| Flag | Description |
|------|-------------|
| `-n, --name` | Human-readable name |
| `-s, --selector` | CSS selector to locate price on the page |
| `--selector-kind` | `css` (default) or `regex` |
| `-c, --currency` | Currency code, e.g. `USD` |

If name/currency aren't provided, the tool fetches the page once to
auto-discover them from schema.org JSON-LD or OpenGraph metadata.

### `doxxx-track check [ID...]`

Run a one-shot check. Omit the IDs to check **all** tracked products.
Output shows current price, stock status, and the change vs the previous
record (`↓` for a drop, `↑` for a rise).

### `doxxx-track list`

List all tracked products.

### `doxxx-track remove <id>`

Remove a tracked product by its ID (shown by `list`).

### `doxxx-track history <id> [-l N]`

Show the full price history for a product, or the last `N` entries with `-l`.

## Global flags

| Flag | Description |
|------|-------------|
| `--store PATH` | Path to JSON or SQLite store (default: `~/.doxxx/tracker.json`). Use a `.db` / `.sqlite` / `.sqlite3` suffix for SQLite. |
| `-t, --timeout` | HTTP request timeout in seconds |
| `--proxy PROXY` | Proxy URL for HTTP requests |

## How price extraction works

Prices are extracted in this order:

1. An explicit `--selector` (CSS or regex) you supply with `add`.
2. schema.org **JSON-LD** `Product`/`Offer` structured data (`offers.price`).
3. **OpenGraph / microdata `<meta>`** tags (`og:price:amount`).

Availability is read from `offers.availability` (`InStock` / `OutOfStock`).

Bot-walled sites are handled automatically: the tool first tries `httpx`,
and falls back to a browser-impersonating `curl_cffi` session (chrome TLS
fingerprint) on 403/406/429/503 responses.

## Storage

By default history lives in `~/.doxxx/tracker.json` (created automatically).
It contains the product registry plus every `checked_at` price observation.
Use `--store path/to/db.sqlite` for SQLite instead.

## Example workflow

```bash
# Baseline check
doxxx-track add "https://store-a.example.com/item/123" -n "Store A Item" -c USD
doxxx-track check

# Add competitors
doxxx-track add "https://store-b.example.com/p/123" -n "Store B Item" -c USD
doxxx-track add "https://store-c.example.com/item/123" -n "Store C Item" -c USD

# Re-check later (shows changes since baseline)
doxxx-track check

# View history for Store A only
doxxx-track history store-a.example.com/item/123
```

## Library mode

Use the engine from Python:

```python
import asyncio
from doxxx.track.tracker import PriceTracker, TrackConfig

tracker = PriceTracker()
product = tracker.add("https://example.com/item/1", name="Item 1")
results = tracker.check(product_ids=[product.id])

for result in results:
    if result.change_direction:
        print(f"Price {result.change_direction}: {result.price}")
```

## Requirements

- `doxxx` core deps (`httpx`, `curl_cffi`, `colorama`, `rich`)
- Python ≥ 3.10

## Caveats

- Price extraction is best-effort and depends on the retailer exposing price
  data in structured data or meta tags. If a site doesn't expose it, register
  the product anyway — you'll get an error record instead of a false price.
- Bot-walled sites (Amazon, etc.) may not return usable HTML; extraction
  works best on retailers that serve server-side-rendered product pages.