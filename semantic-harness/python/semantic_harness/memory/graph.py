"""Knowledge Graph Memory & Subgraph Traversal Layer for Semantic Harness.

Maintains an interconnected property graph of entities and relations,
allowing Small Language Models (SLMs) to execute multi-hop relational deduction
without relying on noisy semantic chunk retrieval.
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass
class Entity:
    id: str
    name: str
    entity_type: str = "entity"
    properties: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class Triplet:
    source_name: str
    predicate: str
    target_name: str
    confidence: float = 1.0
    properties: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class GraphMemory:
    """SQLite-backed lightweight Knowledge Graph with multi-hop subgraph extraction."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    entity_type TEXT NOT NULL,
                    properties TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS relations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_name TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    target_name TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    properties TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    UNIQUE(source_name, predicate, target_name)
                )
                """
            )
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_rel_src ON relations(source_name)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_rel_tgt ON relations(target_name)")

    def add_entity(self, name: str, entity_type: str = "entity", properties: dict[str, Any] | None = None) -> Entity:
        """Add or update an entity node."""
        clean_name = name.strip()
        props_json = json.dumps(properties or {})
        now = time.time()
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO entities (id, name, entity_type, properties, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    entity_type=excluded.entity_type,
                    properties=excluded.properties
                """,
                (clean_name.lower().replace(" ", "_"), clean_name, entity_type, props_json, now),
            )
        return Entity(
            id=clean_name.lower().replace(" ", "_"),
            name=clean_name,
            entity_type=entity_type,
            properties=properties or {},
            created_at=now,
        )

    def add_triplet(
        self,
        source: str,
        predicate: str,
        target: str,
        confidence: float = 1.0,
        properties: dict[str, Any] | None = None,
    ) -> Triplet:
        """Add a directed relational edge between two entities."""
        s = source.strip()
        p = predicate.strip().lower().replace(" ", "_")
        t = target.strip()

        # Ensure both entities exist
        self.add_entity(s)
        self.add_entity(t)

        props_json = json.dumps(properties or {})
        now = time.time()
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO relations (source_name, predicate, target_name, confidence, properties, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_name, predicate, target_name) DO UPDATE SET
                    confidence=excluded.confidence,
                    properties=excluded.properties,
                    timestamp=excluded.timestamp
                """,
                (s, p, t, confidence, props_json, now),
            )
        return Triplet(source_name=s, predicate=p, target_name=t, confidence=confidence, properties=properties or {}, timestamp=now)

    def get_relations_for(self, entity_name: str) -> list[Triplet]:
        """Get all 1-hop outgoing and incoming triplets for an entity."""
        name = entity_name.strip()
        cursor = self._conn.execute(
            """
            SELECT source_name, predicate, target_name, confidence, properties, timestamp
            FROM relations
            WHERE source_name = ? OR target_name = ?
            ORDER BY confidence DESC
            """,
            (name, name),
        )
        return [
            Triplet(
                source_name=row["source_name"],
                predicate=row["predicate"],
                target_name=row["target_name"],
                confidence=row["confidence"],
                properties=json.loads(row["properties"]),
                timestamp=row["timestamp"],
            )
            for row in cursor.fetchall()
        ]

    def traverse_subgraph(self, root_entities: list[str], max_hops: int = 2, max_nodes: int = 30) -> list[Triplet]:
        """Perform breadth-first traversal up to max_hops starting from root_entities."""
        visited_entities: set[str] = set()
        frontier: set[str] = {e.strip() for e in root_entities if e.strip()}
        subgraph: list[Triplet] = []
        seen_triplets: set[tuple[str, str, str]] = set()

        for _ in range(max_hops):
            if not frontier or len(visited_entities) >= max_nodes:
                break

            next_frontier: set[str] = set()
            for entity in list(frontier):
                if entity in visited_entities:
                    continue
                visited_entities.add(entity)

                rels = self.get_relations_for(entity)
                for r in rels:
                    key = (r.source_name, r.predicate, r.target_name)
                    if key not in seen_triplets:
                        seen_triplets.add(key)
                        subgraph.append(r)

                    if r.source_name not in visited_entities:
                        next_frontier.add(r.source_name)
                    if r.target_name not in visited_entities:
                        next_frontier.add(r.target_name)

            frontier = next_frontier

        return subgraph

    def render_subgraph_context(self, root_entities: list[str], max_hops: int = 2) -> str:
        """Render a compact Markdown/text representation of the relational subgraph for LLM prompts."""
        triplets = self.traverse_subgraph(root_entities, max_hops=max_hops)
        if not triplets:
            return ""

        lines = ["### Relational Knowledge Graph Context:"]
        for t in triplets:
            lines.append(f"- ({t.source_name}) --[{t.predicate}]--> ({t.target_name}) [conf: {t.confidence:.2f}]")
        return "\n".join(lines)

    def extract_triplets_from_text(self, text: str) -> list[Triplet]:
        """Extract explicit subject-predicate-object lines formatted as (S, P, O) or similar patterns."""
        import re
        extracted: list[Triplet] = []
        # Matches patterns like (A) --[rel]--> (B) or (A, rel, B)
        pattern = re.compile(r"\(([^,\)]+)\)\s*(?:--\[([^\]]+)\]-->|,)\s*\(([^,\)]+)\)")
        for match in pattern.finditer(text):
            s, p, o = match.group(1).strip(), match.group(2).strip(), match.group(3).strip()
            if s and p and o:
                extracted.append(self.add_triplet(s, p, o))
        return extracted

    def get_all_entities(self) -> list[Entity]:
        """Fetch all entities registered in the graph."""
        cursor = self._conn.execute("SELECT id, name, entity_type, properties, created_at FROM entities")
        return [
            Entity(
                id=row["id"],
                name=row["name"],
                entity_type=row["entity_type"],
                properties=json.loads(row["properties"]),
                created_at=row["created_at"],
            )
            for row in cursor.fetchall()
        ]

    def get_all_triplets(self) -> list[Triplet]:
        """Fetch all relations registered in the graph."""
        cursor = self._conn.execute("SELECT source_name, predicate, target_name, confidence, properties, timestamp FROM relations")
        return [
            Triplet(
                source_name=row["source_name"],
                predicate=row["predicate"],
                target_name=row["target_name"],
                confidence=row["confidence"],
                properties=json.loads(row["properties"]),
                timestamp=row["timestamp"],
            )
            for row in cursor.fetchall()
        ]

    def render_interactive_html(
        self,
        title: str = "Relational Knowledge Graph",
        height: str = "700px",
        include_turbo_quant: bool = True,
    ) -> str:
        """Render a black-and-white minimalist force-directed interactive visualization of this graph.

        Clicking on any node details its properties and displays its TurboQuant bitstream.
        """
        from semantic_harness.visualization.kg_visualizer import KnowledgeGraphVisualizer

        entities = self.get_all_entities()
        triplets = self.get_all_triplets()

        tq_details = []
        if include_turbo_quant:
            from semantic_harness.memory.turbo_quant import PolarQuantizer, SemanticFeatureEmbedder
            embedder = SemanticFeatureEmbedder(dim=64)
            quantizer = PolarQuantizer(dim=64)

            for e in entities:
                vec = embedder.embed(e.name)
                q = quantizer.quantize(vec)
                d = q.to_dict()
                d["id"] = e.name
                d["binary_string"] = q.to_binary_string()
                tq_details.append(d)

        return KnowledgeGraphVisualizer.to_interactive_html(
            entities=entities,
            triplets=triplets,
            title=title,
            height=height,
            turbo_quant_details=tq_details,
        )
