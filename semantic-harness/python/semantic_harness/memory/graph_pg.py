"""PostgreSQL-backed Distributed Knowledge Graph Memory for Semantic Harness.

Extends entity-relation graph storage to PostgreSQL cluster deployments
allowing high-concurrency multi-agent relational deduction and graph RAG context traversal.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Iterable

from semantic_harness.memory.graph import Entity, Triplet


class PostgresGraphMemory:
    """PostgreSQL-backed Graph Memory for enterprise distributed cluster deployments."""

    def __init__(
        self,
        dsn: str = "postgresql://postgres:postgres@localhost:5432/semantic_harness",
        table_prefix: str = "sh_",
    ) -> None:
        self.dsn = dsn
        self.table_prefix = table_prefix
        self.entities_table = f"{table_prefix}entities"
        self.relations_table = f"{table_prefix}relations"
        self._pool: Any = None
        self._fallback_memory: dict[str, Any] = {"entities": {}, "relations": []}

        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            self._conn = psycopg2.connect(dsn)
            self._conn.autocommit = True
            self._cursor_factory = RealDictCursor
            self._init_db()
        except Exception:
            self._conn = None

    @property
    def is_connected(self) -> bool:
        return self._conn is not None or self._pool is not None

    async def init_async_pool(self, min_size: int = 2, max_size: int = 10) -> bool:
        """Initialize an asyncpg connection pool for high-concurrency non-blocking ASGI runtimes."""
        try:
            import asyncpg
            self._pool = await asyncpg.create_pool(
                dsn=self.dsn,
                min_size=min_size,
                max_size=max_size,
                command_timeout=30.0,
            )
            async with self._pool.acquire() as conn:
                await conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self.entities_table} (
                        id VARCHAR(255) PRIMARY KEY,
                        name VARCHAR(255) UNIQUE NOT NULL,
                        entity_type VARCHAR(100) NOT NULL,
                        properties JSONB NOT NULL,
                        created_at DOUBLE PRECISION NOT NULL
                    );
                    """
                )
                await conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self.relations_table} (
                        id SERIAL PRIMARY KEY,
                        source_name VARCHAR(255) NOT NULL,
                        predicate VARCHAR(255) NOT NULL,
                        target_name VARCHAR(255) NOT NULL,
                        confidence DOUBLE PRECISION NOT NULL,
                        properties JSONB NOT NULL,
                        timestamp DOUBLE PRECISION NOT NULL,
                        UNIQUE(source_name, predicate, target_name)
                    );
                    """
                )
                await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}rel_src ON {self.relations_table}(source_name);")
                await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}rel_tgt ON {self.relations_table}(target_name);")
            return True
        except Exception:
            self._pool = None
            return False

    async def close_async_pool(self) -> None:
        """Close the asyncpg connection pool if active."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def aadd_entity(self, name: str, entity_type: str = "entity", properties: dict[str, Any] | None = None) -> Entity:
        """Async non-blocking addition of entity."""
        clean_name = name.strip()
        props = properties or {}
        now = time.time()
        entity_id = clean_name.lower().replace(" ", "_")

        if self._pool is not None:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    f"""
                    INSERT INTO {self.entities_table} (id, name, entity_type, properties, created_at)
                    VALUES ($1, $2, $3, $4::jsonb, $5)
                    ON CONFLICT(name) DO UPDATE SET
                        entity_type=EXCLUDED.entity_type,
                        properties=EXCLUDED.properties
                    """,
                    entity_id, clean_name, entity_type, json.dumps(props), now,
                )
        else:
            return self.add_entity(name, entity_type, properties)

        return Entity(id=entity_id, name=clean_name, entity_type=entity_type, properties=props, created_at=now)

    async def aadd_triplet(
        self,
        source: str,
        predicate: str,
        target: str,
        confidence: float = 1.0,
        properties: dict[str, Any] | None = None,
    ) -> Triplet:
        """Async non-blocking addition of relational triplet."""
        s = source.strip()
        p = predicate.strip().lower().replace(" ", "_")
        t = target.strip()
        props = properties or {}
        now = time.time()

        await self.aadd_entity(s)
        await self.aadd_entity(t)

        if self._pool is not None:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    f"""
                    INSERT INTO {self.relations_table} (source_name, predicate, target_name, confidence, properties, timestamp)
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6)
                    ON CONFLICT(source_name, predicate, target_name) DO UPDATE SET
                        confidence=EXCLUDED.confidence,
                        properties=EXCLUDED.properties,
                        timestamp=EXCLUDED.timestamp
                    """,
                    s, p, t, confidence, json.dumps(props), now,
                )
        else:
            return self.add_triplet(source, predicate, target, confidence, properties)

        return Triplet(source_name=s, predicate=p, target_name=t, confidence=confidence, properties=props, timestamp=now)

    async def aget_relations_for(self, entity_name: str) -> list[Triplet]:
        """Async non-blocking retrieval of relations for an entity."""
        name = entity_name.strip()
        if self._pool is not None:
            triplets: list[Triplet] = []
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    f"""
                    SELECT source_name, predicate, target_name, confidence, properties, timestamp
                    FROM {self.relations_table}
                    WHERE source_name = $1 OR target_name = $2
                    ORDER BY confidence DESC
                    """,
                    name, name,
                )
                for row in rows:
                    raw_props = row["properties"]
                    props = json.loads(raw_props) if isinstance(raw_props, str) else dict(raw_props)
                    triplets.append(
                        Triplet(
                            source_name=row["source_name"],
                            predicate=row["predicate"],
                            target_name=row["target_name"],
                            confidence=row["confidence"],
                            properties=props,
                            timestamp=row["timestamp"],
                        )
                    )
            return triplets
        return self.get_relations_for(entity_name)

    def _init_db(self) -> None:
        if not self._conn:
            return
        from semantic_harness.memory.migrations import PostgresMigrationManager
        mgr = PostgresMigrationManager(self._conn, table_prefix=self.table_prefix)
        mgr.migrate()

    def add_entity(self, name: str, entity_type: str = "entity", properties: dict[str, Any] | None = None) -> Entity:
        clean_name = name.strip()
        props = properties or {}
        now = time.time()
        entity_id = clean_name.lower().replace(" ", "_")

        if self._conn:
            with self._conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {self.entities_table} (id, name, entity_type, properties, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT(name) DO UPDATE SET
                        entity_type=EXCLUDED.entity_type,
                        properties=EXCLUDED.properties
                    """,
                    (entity_id, clean_name, entity_type, json.dumps(props), now),
                )
        else:
            self._fallback_memory["entities"][clean_name] = {
                "id": entity_id, "name": clean_name, "entity_type": entity_type, "properties": props, "created_at": now
            }

        return Entity(id=entity_id, name=clean_name, entity_type=entity_type, properties=props, created_at=now)

    def add_triplet(
        self,
        source: str,
        predicate: str,
        target: str,
        confidence: float = 1.0,
        properties: dict[str, Any] | None = None,
    ) -> Triplet:
        s = source.strip()
        p = predicate.strip().lower().replace(" ", "_")
        t = target.strip()
        props = properties or {}
        now = time.time()

        self.add_entity(s)
        self.add_entity(t)

        if self._conn:
            with self._conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {self.relations_table} (source_name, predicate, target_name, confidence, properties, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT(source_name, predicate, target_name) DO UPDATE SET
                        confidence=EXCLUDED.confidence,
                        properties=EXCLUDED.properties,
                        timestamp=EXCLUDED.timestamp
                    """,
                    (s, p, t, confidence, json.dumps(props), now),
                )
        else:
            self._fallback_memory["relations"].append(
                {"source_name": s, "predicate": p, "target_name": t, "confidence": confidence, "properties": props, "timestamp": now}
            )

        return Triplet(source_name=s, predicate=p, target_name=t, confidence=confidence, properties=props, timestamp=now)

    def get_relations_for(self, entity_name: str) -> list[Triplet]:
        name = entity_name.strip()
        triplets: list[Triplet] = []

        if self._conn:
            with self._conn.cursor(cursor_factory=self._cursor_factory) as cur:
                cur.execute(
                    f"""
                    SELECT source_name, predicate, target_name, confidence, properties, timestamp
                    FROM {self.relations_table}
                    WHERE source_name = %s OR target_name = %s
                    ORDER BY confidence DESC
                    """,
                    (name, name),
                )
                rows = cur.fetchall()
                for row in rows:
                    props = row["properties"] if isinstance(row["properties"], dict) else json.loads(row["properties"])
                    triplets.append(
                        Triplet(
                            source_name=row["source_name"],
                            predicate=row["predicate"],
                            target_name=row["target_name"],
                            confidence=row["confidence"],
                            properties=props,
                            timestamp=row["timestamp"],
                        )
                    )
        else:
            for r in self._fallback_memory["relations"]:
                if r["source_name"] == name or r["target_name"] == name:
                    triplets.append(
                        Triplet(
                            source_name=r["source_name"],
                            predicate=r["predicate"],
                            target_name=r["target_name"],
                            confidence=r["confidence"],
                            properties=r["properties"],
                            timestamp=r["timestamp"],
                        )
                    )

        return triplets

    def get_all_entities(self) -> list[Entity]:
        """Fetch all entities registered in the graph."""
        entities: list[Entity] = []
        if self._conn:
            with self._conn.cursor(cursor_factory=self._cursor_factory) as cur:
                cur.execute(f"SELECT id, name, entity_type, properties, created_at FROM {self.entities_table}")
                rows = cur.fetchall()
                for row in rows:
                    props = row["properties"] if isinstance(row["properties"], dict) else json.loads(row["properties"])
                    entities.append(
                        Entity(
                            id=row["id"],
                            name=row["name"],
                            entity_type=row["entity_type"],
                            properties=props,
                            created_at=row["created_at"],
                        )
                    )
        else:
            for e in self._fallback_memory["entities"].values():
                entities.append(
                    Entity(
                        id=e["id"],
                        name=e["name"],
                        entity_type=e["entity_type"],
                        properties=e["properties"],
                        created_at=e["created_at"],
                    )
                )
        return entities

    def get_all_triplets(self) -> list[Triplet]:
        """Fetch all relations registered in the graph."""
        triplets: list[Triplet] = []
        if self._conn:
            with self._conn.cursor(cursor_factory=self._cursor_factory) as cur:
                cur.execute(
                    f"SELECT source_name, predicate, target_name, confidence, properties, timestamp FROM {self.relations_table}"
                )
                rows = cur.fetchall()
                for row in rows:
                    props = row["properties"] if isinstance(row["properties"], dict) else json.loads(row["properties"])
                    triplets.append(
                        Triplet(
                            source_name=row["source_name"],
                            predicate=row["predicate"],
                            target_name=row["target_name"],
                            confidence=row["confidence"],
                            properties=props,
                            timestamp=row["timestamp"],
                        )
                    )
        else:
            for r in self._fallback_memory["relations"]:
                triplets.append(
                    Triplet(
                        source_name=r["source_name"],
                        predicate=r["predicate"],
                        target_name=r["target_name"],
                        confidence=r["confidence"],
                        properties=r["properties"],
                        timestamp=r["timestamp"],
                    )
                )
        return triplets
