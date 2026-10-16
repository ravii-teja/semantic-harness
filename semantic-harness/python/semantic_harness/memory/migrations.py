"""
Schema versioning for LTM SQLite store.
Add new migrations as tuples: (version_int, sql_string)
Apply with: MigrationManager(db_path).migrate()
"""
from __future__ import annotations
import sqlite3
from typing import Any

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


PG_MIGRATIONS: list[tuple[int, str]] = [
    (1, """
        CREATE TABLE IF NOT EXISTS {prefix}entities (
            id VARCHAR(255) PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            entity_type VARCHAR(100) NOT NULL,
            properties JSONB NOT NULL,
            created_at DOUBLE PRECISION NOT NULL
        );
        CREATE TABLE IF NOT EXISTS {prefix}relations (
            id SERIAL PRIMARY KEY,
            source_name VARCHAR(255) NOT NULL,
            predicate VARCHAR(255) NOT NULL,
            target_name VARCHAR(255) NOT NULL,
            confidence DOUBLE PRECISION NOT NULL,
            properties JSONB NOT NULL,
            timestamp DOUBLE PRECISION NOT NULL,
            UNIQUE(source_name, predicate, target_name)
        );
        CREATE INDEX IF NOT EXISTS idx_{prefix}rel_src ON {prefix}relations(source_name);
        CREATE INDEX IF NOT EXISTS idx_{prefix}rel_tgt ON {prefix}relations(target_name);
        CREATE TABLE IF NOT EXISTS {prefix}schema_version (version INTEGER PRIMARY KEY);
        INSERT INTO {prefix}schema_version (version) VALUES (1) ON CONFLICT DO NOTHING;
    """),
    (2, """
        ALTER TABLE {prefix}relations ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{{}}'::jsonb;
        UPDATE {prefix}schema_version SET version = 2;
    """),
]


class PostgresMigrationManager:
    """Manages schema versioning and incremental migrations for PostgreSQL graph memory."""

    def __init__(self, conn: Any, table_prefix: str = "sh_"):
        self.conn = conn
        self.table_prefix = table_prefix

    def current_version(self) -> int:
        if not self.conn:
            return 0
        try:
            with self.conn.cursor() as cur:
                cur.execute(f"CREATE TABLE IF NOT EXISTS {self.table_prefix}schema_version (version INTEGER PRIMARY KEY);")
                cur.execute(f"SELECT version FROM {self.table_prefix}schema_version ORDER BY version DESC LIMIT 1;")
                row = cur.fetchone()
                if row:
                    return row[0] if isinstance(row, (tuple, list)) else row.get("version", 0)
                return 0
        except Exception:
            return 0

    def migrate(self) -> int:
        if not self.conn:
            return 0
        current = self.current_version()
        applied = 0
        with self.conn.cursor() as cur:
            for version, raw_sql in PG_MIGRATIONS:
                if version > current:
                    sql = raw_sql.replace("{prefix}", self.table_prefix)
                    cur.execute(sql)
                    cur.execute(
                        f"""
                        INSERT INTO {self.table_prefix}schema_version (version)
                        VALUES (%s)
                        ON CONFLICT (version) DO UPDATE SET version = EXCLUDED.version;
                        """,
                        (version,),
                    )
                    applied += 1
        return applied

