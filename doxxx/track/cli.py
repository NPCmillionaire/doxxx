"""Command-line interface for the competitor price tracker."""

import argparse

from doxxx.track.models import CheckResult
from doxxx.track.tracker import PriceTracker, product_slug


def _print_check_result(result: CheckResult) -> None:
    """Pretty-print a single CheckResult."""
    status = "✅" if not result.is_error else "❌"
    price = f"${result.price:.2f}" if result.price is not None else "Not Found"
    prev = f"${result.previous_price:.2f}" if result.previous_price is not None else "None"
    change = f"{result.change:.2f}" if result.change is not None else "N/A"
    pct = f"{result.change_pct:.1f}%" if result.change_pct is not None else "N/A"

    print(f"{status} {product_slug(result.product.url)}")
    print(f"  Name: {result.product.name or 'N/A'}")
    print(f"  Site: {result.product.site or 'N/A'}")
    print(f"  Current: {price} ({result.currency or 'N/A'})")
    print(f"  In stock: {'✅' if result.in_stock else '❌' if result.in_stock is False else 'N/A'}")
    if result.previous_price is not None:
        if result.change is not None and result.change < 0:
            direction = "↓"
        elif result.change is not None and result.change > 0:
            direction = "↑"
        else:
            direction = "→"
        print(f"  Change: {direction} {change} ({pct}) from {prev}")


def _add(args: argparse.Namespace) -> None:
    tracker = PriceTracker(store_arg=args.store)
    product = tracker.add(
        args.url,
        name=args.name,
        selector=args.selector,
        selector_kind=args.selector_kind or "css",
        currency=args.currency,
    )
    print(f"[+] Added product: {product.url} (ID: {product.id})")


def _remove(args: argparse.Namespace) -> None:
    tracker = PriceTracker(store_arg=args.store)
    removed = tracker.remove(args.id)
    if removed:
        print(f"[✓] Removed product with ID: {args.id}")
    else:
        print(f"[✗] Product with ID: {args.id} not found")


def _list(args: argparse.Namespace) -> None:
    tracker = PriceTracker(store_arg=args.store)
    products = tracker.list_products()
    if not products:
        print("[i] No products are being tracked.")
        return
    for product in products:
        print(f"ID: {product.id}")
        print(f"  URL: {product.url}")
        print(f"  Name: {product.name or 'N/A'}")
        print(f"  Site: {product.site or 'N/A'}")
        print(f"  Currency: {product.currency or 'N/A'}")
        if product.selector:
            print(f"  Selector: {product.selector} ({product.selector_kind})")
        print("-" * 40)


def _check(args: argparse.Namespace) -> None:
    tracker = PriceTracker(store_arg=args.store)
    results = tracker.check(product_ids=args.targets)
    if not results:
        print("[i] No matching products found.")
        return
    for result in results:
        _print_check_result(result)


def _history(args: argparse.Namespace) -> None:
    tracker = PriceTracker(store_arg=args.store)
    records = tracker.history(args.target, limit=args.limit)
    if not records:
        print(f"[i] No history found for {args.target}.")
        return
    print(f"[i] Price history for {args.target} (last {len(records)} checks):")
    for rec in records:
        print(
            f"  {rec.checked_at} | {rec.price if rec.price is not None else 'N/A'} "
            f"({rec.currency or 'N/A'}) | In Stock: {rec.in_stock if rec.in_stock is not None else 'N/A'}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="doxxx-track",
        description="Track competitor prices for specific products.",
    )
    parser.add_argument(
        "--store",
        type=str,
        default=None,
        help="Path to JSON or SQLite store (default: ~/.doxxx/tracker.json).",
    )
    parser.add_argument(
        "-t", "--timeout", type=float, default=15.0, help="HTTP request timeout in seconds."
    )
    parser.add_argument(
        "--proxy", type=str, default=None, help="Proxy URL for HTTP requests."
    )
    parser.add_argument(
        "--allow-loud",
        action="store_true",
        help="Allow scanning sites that may send notifications or emails.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # add
    add_parser = subparsers.add_parser("add", help="Add a product to track.")
    add_parser.add_argument("url", help="Full URL of the product to track.")
    add_parser.add_argument("-n", "--name", help="Human-readable name.")
    add_parser.add_argument(
        "-s", "--selector", help="CSS selector to locate price on the page."
    )
    add_parser.add_argument(
        "--selector-kind",
        choices=["css", "regex"],
        default="css",
        help="How to interpret the selector (default: css).",
    )
    add_parser.add_argument("-c", "--currency", help="Currency code (e.g., USD).")
    add_parser.set_defaults(func=_add)

    # remove
    rm_parser = subparsers.add_parser("remove", help="Remove a tracked product.")
    rm_parser.add_argument("id", help="Product ID (slug) or URL substring.")
    rm_parser.set_defaults(func=_remove)

    # list
    list_parser = subparsers.add_parser("list", help="List all tracked products.")
    list_parser.set_defaults(func=_list)

    # check
    check_parser = subparsers.add_parser("check", help="Check current prices.")
    check_parser.add_argument(
        "targets",
        nargs="*",
        help="Product IDs or URLs to check. Omit to check all tracked products.",
    )
    check_parser.set_defaults(func=_check)

    # history
    hist_parser = subparsers.add_parser("history", help="Show price history.")
    hist_parser.add_argument("target", help="Product ID or URL.")
    hist_parser.add_argument("-l", "--limit", type=int, help="Show only the last N entries.")
    hist_parser.set_defaults(func=_history)

    args = parser.parse_args()
    if args.command == "add":
        _add(args)
    elif args.command == "remove":
        _remove(args)
    elif args.command == "list":
        _list(args)
    elif args.command == "check":
        _check(args)
    elif args.command == "history":
        _history(args)


if __name__ == "__main__":
    main()