"""SQLite persistence. Trajectory events are an append-only log; laws and experiments are JSON documents.
The schema and documents are identical to the earlier TypeScript server, so existing databases open unchanged."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path

from .paths import DEFAULT_DB

_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
CREATE TABLE IF NOT EXISTS laws (id TEXT PRIMARY KEY, doc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS experiments (id TEXT PRIMARY KEY, started_at INTEGER NOT NULL, doc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events (
  experiment_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  doc TEXT NOT NULL,
  PRIMARY KEY (experiment_id, seq)
);
-- the log is append-only: refuse updates of individual events
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
  BEGIN SELECT RAISE(ABORT, 'trajectory events are append-only'); END;
"""


def _dump(doc: dict) -> str:
    # compact separators, like JSON.stringify, so documents stay byte-compatible with the earlier server
    return json.dumps(doc, separators=(",", ":"), ensure_ascii=False)


class Store:
    def __init__(self, path: str | Path | None = None):
        p = str(path or os.environ.get("SWARMCONTROL_DB") or DEFAULT_DB)
        if p != ":memory:":
            Path(p).parent.mkdir(parents=True, exist_ok=True)
        self.path = p
        self.db = sqlite3.connect(p, check_same_thread=False, isolation_level=None)
        self.lock = threading.RLock()
        self.db.executescript(_SCHEMA)

    # laws
    def put_law(self, law: dict) -> None:
        with self.lock:
            self.db.execute("INSERT INTO laws (id, doc) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET doc = excluded.doc", (law["id"], _dump(law)))

    def get_law(self, law_id: str) -> dict | None:
        with self.lock:
            r = self.db.execute("SELECT doc FROM laws WHERE id = ?", (law_id,)).fetchone()
        return json.loads(r[0]) if r else None

    def laws(self) -> list[dict]:
        with self.lock:
            rows = self.db.execute("SELECT doc FROM laws").fetchall()
        return sorted((json.loads(r[0]) for r in rows), key=lambda l: l.get("createdAt", 0))

    def delete_law(self, law_id: str) -> None:
        with self.lock:
            self.db.execute("DELETE FROM laws WHERE id = ?", (law_id,))

    # experiments
    def put_experiment(self, e: dict) -> None:
        with self.lock:
            self.db.execute("INSERT INTO experiments (id, started_at, doc) VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET doc = excluded.doc",
                            (e["id"], e["startedAt"], _dump(e)))

    def get_experiment(self, exp_id: str) -> dict | None:
        with self.lock:
            r = self.db.execute("SELECT doc FROM experiments WHERE id = ?", (exp_id,)).fetchone()
        return json.loads(r[0]) if r else None

    def experiments(self) -> list[dict]:
        with self.lock:
            rows = self.db.execute("SELECT doc FROM experiments ORDER BY started_at DESC").fetchall()
        return [json.loads(r[0]) for r in rows]

    # events
    def append_events(self, events: list[dict]) -> None:
        if not events:
            return
        with self.lock:
            self.db.execute("BEGIN")
            try:
                self.db.executemany("INSERT INTO events (experiment_id, seq, doc) VALUES (?, ?, ?)",
                                    [(e["experimentId"], e["id"], _dump(e)) for e in events])
                self.db.execute("COMMIT")
            except Exception:
                self.db.execute("ROLLBACK")
                raise

    def events(self, exp_id: str, after: int = 0) -> list[dict]:
        with self.lock:
            rows = self.db.execute("SELECT doc FROM events WHERE experiment_id = ? AND seq > ? ORDER BY seq", (exp_id, after)).fetchall()
        return [json.loads(r[0]) for r in rows]


_store: Store | None = None


def store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store


def use_store(s: Store) -> Store:
    """Point the app (and tests) at a specific database."""
    global _store
    _store = s
    return s
