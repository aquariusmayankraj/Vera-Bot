"""SQLite state, serialized transactions, scoped keys, and explicit data teardown."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .utils import canonical

TABLES = ("contexts", "conversations", "recipients", "suppressions", "reply_cache")


class Store:
    def __init__(self, path: str, ttl_hours: int = 24):
        if path != ":memory:":
            Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False, timeout=10, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA secure_delete=ON")
        self.conn.execute("PRAGMA busy_timeout=10000")
        self.lock = threading.RLock()
        self.ttl = ttl_hours * 3600
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS contexts (
                scope TEXT NOT NULL, id TEXT NOT NULL, version INTEGER NOT NULL,
                payload TEXT NOT NULL, stored_at TEXT NOT NULL, ack_id TEXT NOT NULL,
                delivered_at TEXT NOT NULL, PRIMARY KEY(scope, id));
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS recipients (
                id TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS suppressions (
                target TEXT NOT NULL, key TEXT NOT NULL, PRIMARY KEY(target,key));
            CREATE TABLE IF NOT EXISTS reply_cache (
                conversation_id TEXT NOT NULL, turn_number INTEGER NOT NULL,
                request_hash TEXT NOT NULL, response TEXT NOT NULL,
                PRIMARY KEY(conversation_id,turn_number));
            CREATE TABLE IF NOT EXISTS housekeeping (id INTEGER PRIMARY KEY CHECK(id=1), last_activity REAL NOT NULL);
        """)
        self.conn.execute("INSERT OR IGNORE INTO housekeeping VALUES(1, ?)", (time.time(),))

    @contextmanager
    def transaction(self, activity: bool = True) -> Iterator[sqlite3.Connection]:
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                last = self.conn.execute("SELECT last_activity FROM housekeeping WHERE id=1").fetchone()[0]
                now = time.time()
                if now - last > self.ttl:
                    self._wipe(self.conn)
                if activity:
                    self.conn.execute("UPDATE housekeeping SET last_activity=? WHERE id=1", (now,))
                yield self.conn
                self.conn.execute("COMMIT")
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise

    @staticmethod
    def _wipe(db: sqlite3.Connection) -> None:
        for table in TABLES:  # Constant allowlist; no untrusted identifiers in SQL.
            db.execute(f"DELETE FROM {table}")
        db.execute("UPDATE housekeeping SET last_activity=? WHERE id=1", (time.time(),))

    def teardown(self) -> None:
        with self.lock:
            with self.transaction(activity=False) as db:
                self._wipe(db)
            # Clear SQLite's journal and free-page remnants, not only live records.
            self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self.conn.execute("VACUUM")
            self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def close(self) -> None:
        with self.lock:
            self.conn.close()

    @staticmethod
    def context(db: sqlite3.Connection, scope: str, key: str | None) -> dict | None:
        row = db.execute("SELECT payload FROM contexts WHERE scope=? AND id=?", (scope, key)).fetchone()
        return json.loads(row[0]) if row else None

    @staticmethod
    def get(db: sqlite3.Connection, table: str, key: str) -> dict | None:
        if table not in {"conversations", "recipients"}:
            raise ValueError("Invalid state table")
        row = db.execute(f"SELECT data FROM {table} WHERE id=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    @staticmethod
    def put(db: sqlite3.Connection, table: str, key: str, data: dict) -> None:
        if table not in {"conversations", "recipients"}:
            raise ValueError("Invalid state table")
        db.execute(f"INSERT INTO {table}(id,data) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data", (key, canonical(data)))
