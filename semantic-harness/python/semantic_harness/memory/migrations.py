"""
Schema versioning for LTM SQLite store.
Add new migrations as tuples: (version_int, sql_string)
Apply with: MigrationManager(db_path).migrate()
"""
from __future__ import annotations
import sqlite3

MIGRATIONS: list[tuple[int, str]] = [
    (1, """
        CREATE TABLE IF NOT EXISTS memories (
            key TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            importance REAL DEFAULT 0.5,
            access_count INTEGER DEFAULT 0,
            last_accessed REAL DEFAULT 0,
            created_at REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS schema_version (version INTEGER);
        INSERT INTO schema_version VALUES (1);
    """),
    (2, """
        ALTER TABLE memories ADD COLUMN tags TEXT DEFAULT '';
        UPDATE schema_version SET version = 2;
    """),
]


class MigrationManager:
    """Manages SQLite schema versioning and incremental migrations for agent memory stores."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def current_version(self, conn: sqlite3.Connection) -> int:
        try:
            cur = conn.execute("SELECT version FROM schema_version")
            row = cur.fetchone()
            return row[0] if row else 0
        except sqlite3.OperationalError:
            return 0

    def migrate(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            current = self.current_version(conn)
            for version, sql in MIGRATIONS:
                if version > current:
                    conn.executescript(sql)
                    conn.commit()
        finally:
            conn.close()
