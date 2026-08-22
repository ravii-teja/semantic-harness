"""
semantic-harness: Semantic middleware for AI agents.
Validate, remember, accelerate — any framework, any model.
"""

from semantic_harness.core.agent import Agent, AgentConfig
from semantic_harness.core.context import ContextAssembler
from semantic_harness.core.events import Event, EventBus, EventType
from semantic_harness.core.loop import AgentLoop
from semantic_harness.core.persistence import JSONLSessionLog
from semantic_harness.execution.codeact import CodeActStrategy, extract_code
from semantic_harness.execution.repl import ExecutionResult, PythonREPL
from semantic_harness.memory.long_term import LongTermMemory
from semantic_harness.memory.procedural import ProceduralMemory
from semantic_harness.memory.short_term import ShortTermMemory
from semantic_harness.middleware import SemanticLayer, step
from semantic_harness.semantics.budget import ContextBudget
from semantic_harness.semantics.c2c import C2CValidator, ValidationResult, extract_json
from semantic_harness.tools import ToolRegistry, function_to_schema, tool

__version__ = "0.2.0"

__all__ = [
    "Agent",
    "AgentConfig",
    "EventBus",
    "Event",
    "EventType",
    "ContextAssembler",
    "AgentLoop",
    "ShortTermMemory",
    "LongTermMemory",
    "ProceduralMemory",
    "C2CValidator",
    "ValidationResult",
    "extract_json",
    "ContextBudget",
    "ToolRegistry",
    "function_to_schema",
    "tool",
    "PythonREPL",
    "ExecutionResult",
    "CodeActStrategy",
    "extract_code",
    "JSONLSessionLog",
    "SemanticLayer",
    "step",
]
