"""Semantic Harness: Cognitive middleware and procedural runtime for autonomous AI agents."""

from semantic_harness.__version__ import __version__
from semantic_harness.middleware import step
from semantic_harness.core.agent import Agent, AgentConfig
from semantic_harness.core.events import Event, EventBus, EventType
from semantic_harness.core.persistence import JSONLSessionLog
from semantic_harness.tools import ToolRegistry, tool, function_to_schema
from semantic_harness.semantics.c2c import C2CValidator, C2CValidationResult, extract_json
from semantic_harness.memory.procedural import (
    ProceduralMemory,
    SemanticProceduralMemory,
    CachedProcedure,
)
from semantic_harness.memory.long_term import LongTermMemory, MemoryItem
from semantic_harness.memory.short_term import ShortTermMemory
from semantic_harness.memory.turbo_quant import (
    PolarQuantizer,
    QuantizedVector,
    SemanticFeatureEmbedder,
    TurboQuantVectorIndex,
)
from semantic_harness.execution.repl import PythonREPL, REPLResult, ExecutionResult
from semantic_harness.execution.codeact import extract_code, CodeActStrategy
from semantic_harness.visualization import (
    ProceduralGraphVisualizer,
    render_procedural_graph,
    KnowledgeGraphVisualizer,
)
from semantic_harness.core.hardware import (
    HardwareDetector,
    HardwareProfile,
    AcceleratorType,
    get_default_local_model,
)
from semantic_harness.core.tokenomics import (
    TokenomicsTracker,
    AmortizationEngine,
    DynamicCostRouter,
    ModelTier,
    ModelPricing,
    TokenUsageRecord,
)
from semantic_harness.memory.graph import (
    GraphMemory,
    Entity,
    Triplet,
)
from semantic_harness.providers import (
    BaseProvider,
    ProviderResponse,
    OpenAIProvider,
    AnthropicProvider,
    OllamaProvider,
    HuggingFaceProvider,
    MLXProvider,
    get_provider,
)

__all__ = [
    "__version__",
    "step",
    "Agent",
    "AgentConfig",
    "HardwareDetector",
    "HardwareProfile",
    "AcceleratorType",
    "get_default_local_model",
    "Event",
    "EventBus",
    "EventType",
    "JSONLSessionLog",
    "ToolRegistry",
    "tool",
    "function_to_schema",
    "C2CValidator",
    "C2CValidationResult",
    "extract_json",
    "ProceduralMemory",
    "SemanticProceduralMemory",
    "CachedProcedure",
    "LongTermMemory",
    "MemoryItem",
    "ShortTermMemory",
    "PolarQuantizer",
    "QuantizedVector",
    "SemanticFeatureEmbedder",
    "TurboQuantVectorIndex",
    "PythonREPL",
    "REPLResult",
    "ExecutionResult",
    "extract_code",
    "CodeActStrategy",
    "ProceduralGraphVisualizer",
    "render_procedural_graph",
    "KnowledgeGraphVisualizer",
    "BaseProvider",
    "ProviderResponse",
    "OpenAIProvider",
    "AnthropicProvider",
    "OllamaProvider",
    "HuggingFaceProvider",
    "MLXProvider",
    "get_provider",
    "TokenomicsTracker",
    "AmortizationEngine",
    "DynamicCostRouter",
    "ModelTier",
    "ModelPricing",
    "TokenUsageRecord",
    "GraphMemory",
    "Entity",
    "Triplet",
]
