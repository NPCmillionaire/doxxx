"""Storage backends for persisted price history and tracked products.

Two implementations are provided:

* ``JsonStore`` — a single JSON file; default for simplicity.
* ``SqliteStore`` — a lightweight SQLite database; selected by file suffix
  (``.db`` / ``.sqlite`` / ``.sqlite3``) or via the factory below.

Both satisfy the same public interface so the ``PriceTracker`` can be
configuration-swapped at runtime.
"""

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from doxxx.track.models import PriceRecord, TrackedProduct

SQLITE_SUFFIXES = frozenset({".db", ".sqlite", ".sqlite3"})
DEFAULT_STORE_PATH = Path("~/.doxxx/tracker.json").expanduser()


def resolve_store_path(store_arg: str | None) -> Path:
    """Resolve the store path from a CLI argument (defaults to ``~/.doxxx/tracker.json``)."""
    if not store_arg:
        return DEFAULT_STORE_PATH
    return Path(store_arg).expanduser().resolve()


def get_store(store_arg: str | None):
    """Factory: pick a JSON or SQLite store from a CLI-style store argument."""
    path = resolve_store_path(store_arg)
    if path.suffix.lower() in SQLITE_SUFFIXES:
        return SqliteStore(str(path))
    return JsonStore(str(path))


class JsonStore:
    """A single JSON file for product registry + price history."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = {"version": 1, "products": {}, "history": []}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                with self.path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._data = data
            except (json.JSONDecodeError, OSError):
                # Start with a clean default if the file is corrupt.
                self._data = {"version": 1, "products": {}, "history": []}

    def _atomic_write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _persist(self) -> None:
        self._atomic_write(self._data)

    # ---- TrackedProduct interface ----

    def add_product(self, product: TrackedProduct) -> TrackedProduct:
        pid = product.id
        existing = self._data["products"].get(pid)
        if existing is None:
            self._data["products"][pid] = product.to_dict()
        self._persist()
        return product

    def remove_product(self, product_id: str) -> bool:
        removed = self._data["products"].pop(product_id, None) is not None
        if removed:
            self._data["history"] = [
                r for r in self._data.get("history", []) if r.get("product_id") != product_id
            ]
            self._persist()
        return removed

    def get_product(self, product_id: str) -> TrackedProduct | None:
        raw = self._data["products"].get(product_id)
        if not raw:
            return None
        return TrackedProduct(**raw)

    def list_products(self) -> list[TrackedProduct]:
        products: list[TrackedProduct] = []
        for raw in self._data.get("products", {}).values():
            if not isinstance(raw, dict):
                continue
            try:
                products.append(TrackedProduct(**raw))
            except Exception:  # noqa: BLE001, S112 - skip malformed entries
                continue
        return products

    def find_products(self, query: str) -> list[TrackedProduct]:
        """Return products whose id or url contains *query* (case-insensitive)."""
        needle = (query or "").lower()
        return [
            p
            for p in self.list_products()
            if needle in p.id.lower() or needle in p.url.lower()
        ]

    # ---- PriceRecord interface ----

    def last_record(self, product_id: str) -> PriceRecord | None:
        history = self._data.get("history", [])
        matching = [r for r in history if r.get("product_id") == product_id]
        if not matching:
            return None
        return PriceRecord(**matching[-1])

    def add_record(self, record: PriceRecord) -> None:
        self._data["history"].append(record.to_dict())
        self._persist()

    def history(self, product_id: str, limit: int | None = None) -> list[PriceRecord]:
        history = [r for r in self._data.get("history", []) if r.get("product_id") == product_id]
        records = [PriceRecord(**r) for r in history]
        if limit is not None:
            records = records[-limit:]
        return records


class SqliteStore:
    """A SQLite-backed store for persistent product + price history."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id           TEXT PRIMARY KEY,
                    url          TEXT NOT NULL,
                    name         TEXT,
                    site         TEXT,
                    currency     TEXT,
                    selector     TEXT,
                    selector_kind TEXT DEFAULT 'css',
                    created_at   TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS price_history (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                    price      REAL,
                    currency   TEXT,
                    in_stock   INTEGER,
                    checked_at TEXT NOT NULL,
                    source     TEXT,
                    error      TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_history_product ON price_history(product_id, checked_at)"
            )
            conn.commit()
        finally:
            conn.close()

    def _connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
        return self._conn

    # ---- TrackedProduct interface ----

    def add_product(self, product: TrackedProduct) -> TrackedProduct:
        conn = self._connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO products (id, url, name, site, currency, selector, selector_kind, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product.id,
                product.url,
                product.name,
                product.site,
                product.currency,
                product.selector,
                product.selector_kind,
                product.created_at,
            ),
        )
        conn.commit()
        return product

    def remove_product(self, product_id: str) -> bool:
        conn = self._connection()
        cursor = conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        return cursor.rowcount > 0

    def get_product(self, product_id: str) -> TrackedProduct | None:
        conn = self._connection()
        row = conn.execute(
            "SELECT id, url, name, site, currency, selector, selector_kind, created_at "
            "FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        if not row:
            return None
        return TrackedProduct(
            id=row[0],
            url=row[1] or "",
            name=row[2],
            site=row[3],
            currency=row[4],
            selector=row[5],
            selector_kind=row[6] or "css",
            created_at=row[7],
        )

    def list_products(self) -> list[TrackedProduct]:
        conn = self._connection()
        rows = conn.execute(
            "SELECT id, url, name, site, currency, selector, selector_kind, created_at FROM products"
        ).fetchall()
        return [
            TrackedProduct(
                id=r[0],
                url=r[1] or "",
                name=r[2],
                site=r[3],
                currency=r[4],
                selector=r[5],
                selector_kind=r[6] or "css",
                created_at=r[7],
            )
            for r in rows
        ]

    def find_products(self, query: str) -> list[TrackedProduct]:
        needle = (query or "").lower()
        results: list[TrackedProduct] = []
        for product in self.list_products():
            if needle in product.id.lower() or needle in product.url.lower():
                results.append(product)
        return results

    # ---- PriceRecord interface ----

    def last_record(self, product_id: str) -> PriceRecord | None:
        conn = self._connection()
        row = conn.execute(
            """
            SELECT price, currency, in_stock, checked_at, source, error
            FROM price_history
            WHERE product_id = ?
            ORDER BY checked_at DESC
            LIMIT 1
            """,
            (product_id,),
        ).fetchone()
        if not row:
            return None
        return PriceRecord(
            product_id=product_id,
            price=row[0],
            currency=row[1],
            in_stock=bool(row[2]) if row[2] is not None else None,
            checked_at=row[3],
            source=row[4],
            error=row[5],
        )

    def add_record(self, record: PriceRecord) -> None:
        conn = self._connection()
        in_stock_value = 1 if record.in_stock is True else (0 if record.in_stock is False else None)
        conn.execute(
            """
            INSERT INTO price_history (product_id, price, currency, in_stock, checked_at, source, error)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.product_id,
                record.price,
                record.currency,
                in_stock_value,
                record.checked_at,
                record.source,
                record.error,
            ),
        )
        conn.commit()

    def history(self, product_id: str, limit: int | None = None) -> list[PriceRecord]:
        conn = self._connection()
        rows = conn.execute(
            """
            SELECT price, currency, in_stock, checked_at, source, error
            FROM price_history
            WHERE product_id = ?
            ORDER BY checked_at ASC
            """,
            (product_id,),
        ).fetchall()
        records = [
            PriceRecord(
                product_id=product_id,
                price=row[0],
                currency=row[1],
                in_stock=bool(row[2]) if row[2] is not None else None,
                checked_at=row[3],
                source=row[4],
                error=row[5],
            )
            for row in rows
        ]
        if limit is not None:
            records = records[-limit:]
        return records

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __del__(self) -> None:  # pragma: no cover - best-effort cleanup
        try:
            self.close()
        except Exception:  # noqa: BLE001, S110
            pass
