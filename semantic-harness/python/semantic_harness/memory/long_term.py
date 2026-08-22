"""Long-term memory — persistent fact storage with semantic retrieval."""
from __future__ import annotations

import json
import math
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Memory:
    """A single memory entry."""
    id: str
    content: str
    importance: float = 1.0
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None

    def activation_score(self, recency_weight: float = 0.3, frequency_weight: float = 0.3) -> float:
        """
        ACT-R inspired activation scoring (from NOOA).
        Combines recency, frequency, and importance.
        """
        time_decay = 1.0 / (1.0 + math.log1p(time.time() - self.last_accessed))
        frequency_bonus = math.log1p(self.access_count)
        return (
            recency_weight * time_decay
            + frequency_weight * frequency_bonus
            + (1.0 - recency_weight - frequency_weight) * self.importance
        )


class LongTermMemory:
    """
    Persistent fact memory backed by SQLite.

    Combines NOOA's ACT-R activation ranking with a zero-config
    SQLite backend. No server needed — just a file.

    Usage:
        memory = LongTermMemory("agent_memory.db")
        memory.remember("user_pref_1", "User prefers dark mode", importance=0.8)
        facts = memory.recall(k=5)
    """

    def __init__(self, db_path: str = ":memory:"):
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._init_schema()

    def _init_schema(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                importance REAL DEFAULT 1.0,
                created_at REAL NOT NULL,
                last_accessed REAL NOT NULL,
                access_count INTEGER DEFAULT 0,
                metadata TEXT DEFAULT '{}',
                embedding TEXT DEFAULT NULL
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_importance
            ON memories(importance DESC)
        """)
        self._conn.commit()

    def remember(
        self,
        memory_id: str,
        content: str,
        importance: float = 1.0,
        metadata: dict[str, Any] | None = None,
        embedding: list[float] | None = None,
    ):
        """Store a new memory or update an existing one."""
        now = time.time()
        meta_json = json.dumps(metadata or {})
        emb_json = json.dumps(embedding) if embedding else None

        self._conn.execute(
            """
            INSERT INTO memories (id, content, importance, created_at, last_accessed, access_count, metadata, embedding)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                content = excluded.content,
                importance = excluded.importance,
                last_accessed = excluded.last_accessed,
                access_count = access_count + 1,
                metadata = excluded.metadata,
                embedding = COALESCE(excluded.embedding, embedding)
            """,
            (memory_id, content, importance, now, now, meta_json, emb_json),
        )
        self._conn.commit()

    def recall(self, k: int = 5) -> list[Memory]:
        """Recall top-k memories by ACT-R activation score."""
        rows = self._conn.execute(
            "SELECT id, content, importance, created_at, last_accessed, access_count, metadata, embedding FROM memories"
        ).fetchall()

        memories = []
        for row in rows:
            emb = json.loads(row[7]) if row[7] else None
            mem = Memory(
                id=row[0],
                content=row[1],
                importance=row[2],
                created_at=row[3],
                last_accessed=row[4],
                access_count=row[5],
                metadata=json.loads(row[6]),
                embedding=emb,
            )
            memories.append(mem)

        # Sort by activation score (ACT-R)
        memories.sort(key=lambda m: m.activation_score(), reverse=True)

        # Update access times for recalled memories
        top_k = memories[:k]
        now = time.time()
        for mem in top_k:
            self._conn.execute(
                "UPDATE memories SET last_accessed = ?, access_count = access_count + 1 WHERE id = ?",
                (now, mem.id),
            )
        self._conn.commit()

        return top_k

    def search(self, query: str, k: int = 5) -> list[Memory]:
        """Simple text search across memory content."""
        rows = self._conn.execute(
            "SELECT id, content, importance, created_at, last_accessed, access_count, metadata, embedding FROM memories WHERE content LIKE ?",
            (f"%{query}%",),
        ).fetchall()

        memories = []
        for row in rows:
            emb = json.loads(row[7]) if row[7] else None
            memories.append(Memory(
                id=row[0], content=row[1], importance=row[2],
                created_at=row[3], last_accessed=row[4], access_count=row[5],
                metadata=json.loads(row[6]), embedding=emb,
            ))
        return memories[:k]

    def forget(self, memory_id: str):
        """Remove a memory."""
        self._conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        self._conn.commit()

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]

    def close(self):
        self._conn.close()
