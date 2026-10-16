"""Multi-Agent Orchestrator and Team Coordinator for Semantic Harness.

Coordinates specialized autonomous agents (e.g. Research, Database Query, Code Review, Auditor)
sharing a unified distributed Procedural Memory cache, Knowledge Graph, and event lifecycle.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable

from semantic_harness.core.agent import Agent
from semantic_harness.memory.graph import GraphMemory
from semantic_harness.memory.procedural import ProceduralMemory


class AgentOrchestrator:
    """Enterprise multi-agent team coordinator sharing cognitive procedural memory."""

    def __init__(
        self,
        shared_memory: ProceduralMemory | None = None,
        shared_graph: GraphMemory | None = None,
    ) -> None:
        self.shared_memory = shared_memory or ProceduralMemory()
        self.shared_graph = shared_graph or GraphMemory()
        self.agents: dict[str, Agent] = {}

    def register_agent(self, role: str, agent: Agent) -> None:
        """Register a specialist agent role in the orchestrator."""
        self.agents[role] = agent
        # Share procedural memory with agent
        agent.procedural = self.shared_memory

    async def delegate(self, role: str, task: str) -> Any:
        """Route task to a specialist agent, caching verified outputs in shared procedural memory."""
        if role not in self.agents:
            raise ValueError(f"Agent role '{role}' not registered. Available: {list(self.agents.keys())}")

        intent = f"{role}:{task}"
        cached = self.shared_memory.lookup(intent, require_reliable=True)
        if cached:
            return cached.procedure

        agent = self.agents[role]
        result = await agent.arun(task)

        # Compile successful trajectory into shared multi-agent procedural memory
        self.shared_memory.compile(
            intent=intent,
            trajectory=result,
            confidence=1.0,
            min_success_count=1,
        )
        self.shared_memory.record_success(intent)
        return result

    async def broadcast_pipeline(self, pipeline_steps: list[tuple[str, str]]) -> list[Any]:
        """Execute sequential pipeline of (role, task) delegating across specialist agents."""
        results: list[Any] = []
        for role, task in pipeline_steps:
            res = await self.delegate(role, task)
            results.append(res)
        return results
