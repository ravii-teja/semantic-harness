"""Agent base class — inspired by NOOA's class-as-agent pattern."""
from __future__ import annotations

import inspect
from typing import Any

from pydantic import BaseModel

from semantic_harness.core.context import ContextAssembler
from semantic_harness.core.events import EventBus
from semantic_harness.core.hardware import HardwareDetector, HardwareProfile, get_default_local_model
from semantic_harness.memory.long_term import LongTermMemory
from semantic_harness.memory.procedural import ProceduralMemory
from semantic_harness.memory.short_term import ShortTermMemory
from semantic_harness.tools import ToolRegistry


class AgentConfig(BaseModel):
    """Typed agent configuration."""
    model: str | None = None  # None = auto-detect fastest local hardware accelerator
    max_tokens: int = 4096
    temperature: float = 0.7
    max_steps: int = 10
    context_budget: int = 8192
    procedural_cache: bool = True
    c2c_validation: bool = True
    ltm_db_path: str = "./semantic_agent.db"
    enable_tools: bool = True
    execution_strategy: str = "tools"  # "tools" | "codeact"
    repl_timeout: float = 10.0


class Agent:
    """
    Base agent class. Subclass this to create agents.

    Following NOOA: the class IS the agent, methods are capabilities,
    docstrings are prompts, type annotations are contracts.

    Following DSH: the agent uses an event bus for lifecycle hooks,
    capability seams for swappable providers.

    Usage:
        class MyAgent(Agent):
            \"""You are a helpful research assistant.\"""

            def research(self, topic: str) -> dict:
                \"""Research the given topic thoroughly.\"""
                ...  # LLM-driven via CodeAct
    """

    def __init__(
        self,
        config: AgentConfig | None = None,
        llm_model: str | None = None,
    ):
        self.config = config or AgentConfig()
        if llm_model:
            self.config.model = llm_model

        # Auto-detect local accelerator if no model is explicitly specified
        self.hardware_profile: HardwareProfile | None = None
        if not self.config.model:
            self.hardware_profile = HardwareDetector.detect()
            self.config.model = self.hardware_profile.recommended_model

        # Core subsystems
        self.events = EventBus()
        self.context = ContextAssembler()
        self.tools = ToolRegistry()

        # Memory tiers
        self.short_term = ShortTermMemory(max_items=self.config.context_budget)
        self.long_term = LongTermMemory(self.config.ltm_db_path)
        self.procedural = ProceduralMemory()

        # Set system prompt from class docstring
        system_prompt = self.__class__.__doc__ or "You are a helpful AI agent."
        self.context.set_static("system_prompt", system_prompt.strip())

        # Register available methods as tool descriptions
        self._register_methods()

    def _register_methods(self):
        """Auto-discover public methods and register them as callable tools."""
        # Register as real LLM-callable tools (schema from type hints + docstring)
        registered = self.tools.register_object(self)

        # Also expose them as a static context listing for the prompt
        methods = []
        for name in registered:
            attr = getattr(self, name)
            doc = inspect.getdoc(attr) or ""
            first_line = doc.split("\n\n")[0].strip()
            try:
                sig = inspect.signature(attr)
                params = ", ".join(
                    p for p in sig.parameters if p not in ("self", "cls")
                )
                methods.append(f"- {name}({params}): {first_line}")
            except (TypeError, ValueError):
                methods.append(f"- {name}: {first_line}")
        if methods:
            self.context.set_static("available_methods", "\n".join(methods))

    def run(self, task: str, **kwargs) -> Any:
        """Run the agent on a task. Dispatches to the configured execution strategy."""
        if self.config.execution_strategy == "codeact":
            from semantic_harness.execution.codeact import CodeActStrategy
            return CodeActStrategy(self).run(task, **kwargs)
        from semantic_harness.core.loop import AgentLoop
        loop = AgentLoop(self)
        return loop.run(task, **kwargs)

    async def arun(self, task: str, **kwargs) -> Any:
        """Async version of run."""
        if self.config.execution_strategy == "codeact":
            from semantic_harness.execution.codeact import CodeActStrategy
            return await CodeActStrategy(self).arun(task, **kwargs)
        from semantic_harness.core.loop import AgentLoop
        loop = AgentLoop(self)
        return await loop.arun(task, **kwargs)
