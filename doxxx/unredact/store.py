"""Storage layer for unredact analysis results.

Two implementations are provided:

* ``JsonStore`` — a single JSON file; default for simplicity.
* ``SqliteStore`` — a lightweight SQLite database; selected by file suffix
  (``.db`` / ``.sqlite`` / ``.sqlite3``) or via the factory below.

Both satisfy the same public interface so the :class:`Scanner` can be
configuration-swapped at runtime.
"""

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Optional

from doxxx.unredact.models import UnredactRecord


class JsonStore:
    """A single JSON file for unredact report history."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = {"version": 1, "reports": {}, "history": []}
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
                self._data = {"version": 1, "reports": {}, "history": []}

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

    def add_record(self, record: UnredactRecord) -> None:
        self._data["reports"][record.target_id] = record.report.to_dict()
        self._data["history"].append(
            {
                "target_id": record.target_id,
                "target_path": record.target_path,
                "report": record.report.to_dict(),
                "metadata": record.metadata,
                "created_at": record.created_at,
            }
        )
        self._persist()

    def last_record(self, target_id: str) -> Optional[dict]:
        history = self._data.get("history", [])
        matching = [r for r in history if r.get("target_id") == target_id]
        if not matching:
            return None
        return matching[-1]

    def history(self, target_id: str, limit: int | None = None) -> list[dict]:
        history = [
            r for r in self._data.get("history", []) if r.get("target_id") == target_id
        ]
        if limit is not None:
            history = history[-limit:]
        return history


class SqliteStore:
    """A SQLite-backed store for persistent report history."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    target_id   TEXT PRIMARY KEY,
                    target_path TEXT NOT NULL,
                    report_json TEXT NOT NULL,
                    metadata    TEXT,
                    created_at  TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_id   TEXT NOT NULL,
                    report_data TEXT NOT NULL,
                    created_at  TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_history_target ON history(target_id, created_at)"
            )
            conn.commit()
        finally:
            conn.close()

    def _connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
        return self._conn

    def add_record(self, record: UnredactRecord) -> None:
        conn = self._connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO reports
            (target_id, target_path, report_json, metadata, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                record.target_id,
                record.target_path,
                json.dumps(record.report.to_dict()),
                json.dumps(record.metadata),
                record.created_at,
            ),
        )
        conn.execute(
            """
            INSERT INTO history
            (target_id, report_data, created_at)
            VALUES (?, ?, ?)
            """,
            (
                record.target_id,
                json.dumps(record.report.to_dict()),
                record.created_at,
            ),
        )
        conn.commit()

    def last_record(self, target_id: str) -> Optional[dict]:
        conn = self._connection()
        row = conn.execute(
            """
            SELECT target_path, report_json, metadata, created_at
            FROM reports
            WHERE target_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (target_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "target_id": target_id,
            "target_path": row[1],
            "report": json.loads(row[2]),
            "metadata": json.loads(row[3]) if row[3] else {},
            "created_at": row[4],
        }

    def history(self, target_id: str, limit: int | None = None) -> list[dict]:
        conn = self._connection()
        rows = conn.execute(
            """
            SELECT target_path, report_data, created_at
            FROM history
            WHERE target_id = ?
            ORDER BY created_at ASC
            """,
            (target_id,),
        ).fetchall()
        records = [
            {
                "target_id": target_id,
                "target_path": row[0],
                "report": json.loads(row[1]),
                "metadata": {},
                "created_at": row[2],
            }
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


# Resolution helpers ---------------------------------------------------------


SQLITE_SUFFIXES = frozenset({".db", ".sqlite", ".sqlite3"})


def resolve_store_path(store_arg: str | None) -> Path:
    """Resolve the store path from a CLI argument (defaults to ``~/.doxxx/unredact.json``)."""
    if not store_arg:
        return Path("~/.doxxx/unredact.json").expanduser()
    return Path(store_arg).expanduser().resolve()


def get_store(store_arg: str | None):
    """Factory: pick a JSON or SQLite store from a CLI-style store argument."""
    path = resolve_store_path(store_arg)
    if path.suffix.lower() in SQLITE_SUFFIXES:
        return SqliteStore(str(path))
    return JsonStore(str(path))