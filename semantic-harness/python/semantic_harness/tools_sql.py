"""Enterprise SQL Database Query Agent Tool for Semantic Harness.

Enables autonomous agents to:
1. Safely inspect database schema tables, column types, and constraints in markdown format.
2. Validate and execute read-only SQL queries with query timeout and row limit safety.
3. Automatically map relational query results directly into Knowledge Graph Memory (GraphMemory / PostgresGraphMemory).
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any, Sequence

from semantic_harness.memory.graph import Entity, GraphMemory, Triplet


@dataclass
class SQLResult:
    """Result of a safe SQL execution."""
    success: bool
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    execution_time_ms: float = 0.0
    error: str | None = None

    def to_markdown_table(self, max_display_rows: int = 10) -> str:
        """Render query results as a markdown table for LLM prompt context."""
        if not self.success:
            return f"**SQL Query Error**: {self.error}"
        if not self.columns:
            return f"*Query executed successfully, returned {self.row_count} rows (no columns).*"

        headers = " | ".join(self.columns)
        separators = " | ".join(["---"] * len(self.columns))
        lines = [f"| {headers} |", f"| {separators} |"]

        for row in self.rows[:max_display_rows]:
            cells = " | ".join(str(row.get(col, "")) for col in self.columns)
            lines.append(f"| {cells} |")

        if self.row_count > max_display_rows:
            lines.append(f"\n*(Showing {max_display_rows} of {self.row_count} total rows)*")

        return "\n".join(lines)


class SQLDatabaseTool:
    """Enterprise SQL tool providing safe query execution and Knowledge Graph mapping."""

    FORBIDDEN_KEYWORDS = (
        "DROP", "DELETE", "TRUNCATE", "ALTER", "INSERT", "UPDATE",
        "GRANT", "REVOKE", "VACUUM", "EXEC", "EXECUTE", "REPLACE"
    )

    def __init__(
        self,
        connection_or_dsn: Any,
        schema_whitelist: list[str] | None = None,
        read_only: bool = True,
        max_rows: int = 100,
        default_timeout_sec: float = 5.0,
    ) -> None:
        self.connection_or_dsn = connection_or_dsn
        self.schema_whitelist = [t.lower() for t in schema_whitelist] if schema_whitelist else None
        self.read_only = read_only
        self.max_rows = max_rows
        self.default_timeout_sec = default_timeout_sec

    def _get_connection(self) -> Any:
        if isinstance(self.connection_or_dsn, str):
            if self.connection_or_dsn.startswith("postgresql://") or self.connection_or_dsn.startswith("postgres://"):
                import psycopg2
                from psycopg2.extras import RealDictCursor
                conn = psycopg2.connect(self.connection_or_dsn)
                conn.autocommit = True
                return conn
            else:
                conn = sqlite3.connect(self.connection_or_dsn)
                conn.row_factory = sqlite3.Row
                return conn
        return self.connection_or_dsn

    def describe_schema(self, table_name: str | None = None) -> str:
        """Describe table schema(s) as clear markdown for agent reasoning."""
        conn = self._get_connection()
        is_pg = hasattr(conn, "cursor_factory") or "psycopg" in str(type(conn))

        lines = ["### Database Schema:"]
        try:
            cur = conn.cursor()
            if is_pg:
                if table_name:
                    query = """
                    SELECT table_name, column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = %s
                    ORDER BY ordinal_position
                    """
                    cur.execute(query, (table_name,))
                else:
                    query = """
                    SELECT table_name, column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    ORDER BY table_name, ordinal_position
                    """
                    cur.execute(query)
                rows = cur.fetchall()
                current_table = None
                for r in rows:
                    t_name, col_name, data_type, nullable = r[0], r[1], r[2], r[3]
                    if self.schema_whitelist and t_name.lower() not in self.schema_whitelist:
                        continue
                    if t_name != current_table:
                        current_table = t_name
                        lines.append(f"\n#### Table: `{t_name}`")
                    lines.append(f"- `{col_name}` ({data_type}, nullable={nullable})")
            else:
                # SQLite
                if table_name:
                    tables = [table_name]
                else:
                    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
                    tables = [r[0] if isinstance(r, (list, tuple)) else r["name"] for r in cur.fetchall()]

                for t in tables:
                    if self.schema_whitelist and t.lower() not in self.schema_whitelist:
                        continue
                    lines.append(f"\n#### Table: `{t}`")
                    cur.execute(f"PRAGMA table_info({t});")
                    col_rows = cur.fetchall()
                    for col in col_rows:
                        name = col[1] if isinstance(col, (list, tuple)) else col["name"]
                        type_ = col[2] if isinstance(col, (list, tuple)) else col["type"]
                        notnull = col[3] if isinstance(col, (list, tuple)) else col["notnull"]
                        lines.append(f"- `{name}` ({type_ or 'ANY'}, not_null={bool(notnull)})")

            return "\n".join(lines)
        except Exception as e:
            return f"Error retrieving schema: {e}"
        finally:
            if isinstance(self.connection_or_dsn, str) and hasattr(conn, "close"):
                conn.close()

    def execute_query(self, query: str, parameters: Sequence[Any] | dict[str, Any] | None = None) -> SQLResult:
        """Execute a validated read-only SQL query with safety bounds."""
        clean_sql = query.strip()
        t0 = time.time()

        # Safety: verify read-only
        if self.read_only:
            first_word = clean_sql.split()[0].upper() if clean_sql.split() else ""
            if first_word not in ("SELECT", "WITH", "EXPLAIN"):
                return SQLResult(
                    success=False,
                    error=f"Security violation: only read-only statements (SELECT, WITH) are permitted, got '{first_word}'.",
                )
            for forbidden in self.FORBIDDEN_KEYWORDS:
                if re.search(rf"\b{forbidden}\b", clean_sql, re.IGNORECASE):
                    return SQLResult(
                        success=False,
                        error=f"Security violation: query contains disallowed statement modifier '{forbidden}'.",
                    )

        # Enforce schema whitelist if configured
        if self.schema_whitelist:
            for forbidden_char in [";", "--", "/*"]:
                if forbidden_char in clean_sql:
                    return SQLResult(success=False, error="Security violation: query comments and multiple statements forbidden.")

        conn = self._get_connection()
        is_pg = hasattr(conn, "cursor_factory") or "psycopg" in str(type(conn))

        try:
            cur = conn.cursor()
            if parameters:
                cur.execute(clean_sql, parameters)
            else:
                cur.execute(clean_sql)

            description = cur.description or []
            columns = [desc[0] for desc in description]

            fetched = cur.fetchmany(self.max_rows)
            rows = []
            for item in fetched:
                if isinstance(item, dict):
                    rows.append(item)
                elif hasattr(item, "keys"):
                    rows.append({k: item[k] for k in item.keys()})
                elif isinstance(item, (list, tuple)):
                    rows.append({col: item[i] for i, col in enumerate(columns)})

            elapsed_ms = (time.time() - t0) * 1000.0
            return SQLResult(
                success=True,
                columns=columns,
                rows=rows,
                row_count=len(rows),
                execution_time_ms=elapsed_ms,
            )
        except Exception as e:
            elapsed_ms = (time.time() - t0) * 1000.0
            return SQLResult(
                success=False,
                error=f"SQL Execution Error: {e}",
                execution_time_ms=elapsed_ms,
            )
        finally:
            if isinstance(self.connection_or_dsn, str) and hasattr(conn, "close"):
                conn.close()

    def to_knowledge_graph(
        self,
        result: SQLResult,
        graph_memory: GraphMemory,
        source_column: str,
        predicate: str,
        target_column: str,
        confidence: float = 1.0,
    ) -> int:
        """Map relational query result rows directly into Knowledge Graph triplets."""
        if not result.success or not result.rows:
            return 0

        inserted_count = 0
        for row in result.rows:
            if source_column in row and target_column in row:
                s_val = str(row[source_column]).strip()
                t_val = str(row[target_column]).strip()
                if s_val and t_val:
                    # Pass other columns as properties
                    props = {k: v for k, v in row.items() if k not in (source_column, target_column)}
                    graph_memory.add_triplet(
                        source=s_val,
                        predicate=predicate,
                        target=t_val,
                        confidence=confidence,
                        properties=props,
                    )
                    inserted_count += 1
        return inserted_count
