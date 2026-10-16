"""Semantic Harness: Cognitive middleware and procedural runtime for autonomous AI agents."""

from semantic_harness.__version__ import __version__
from semantic_harness.middleware import step, SemanticLayer
from semantic_harness.core.agent import Agent, AgentConfig
from semantic_harness.core.events import Event, EventBus, EventType
from semantic_harness.core.persistence import JSONLSessionLog
from semantic_harness.tools import ToolRegistry, tool, function_to_schema
from semantic_harness.semantics.c2c import C2CValidator, C2CValidationResult, extract_json
from semantic_harness.memory.procedural import (
    ProceduralMemory,
    SemanticProceduralMemory,
    CachedProcedure,
    CompiledProcedure,
    ProcedurePrecondition,
    ReuseExplanation,
    ReuseStatus,
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
from semantic_harness.memory.graph_pg import PostgresGraphMemory
from semantic_harness.guard.fuzzer import PreconditionFuzzer, FuzzResult
from semantic_harness.providers import (
    BaseProvider,
    ProviderResponse,
    OpenAIProvider,
    AnthropicProvider,
    OllamaProvider,
    HuggingFaceProvider,
    MLXProvider,
    TorchProvider,
    get_provider,
)
from semantic_harness.telemetry import (
    MetricsCollector,
    get_metrics_collector,
    SemanticTracer,
    Span,
    get_tracer,
)
from semantic_harness.integrations.fastapi import (
    SemanticHarnessMiddleware,
    procedural_route,
)
from semantic_harness.tools_sql import (
    SQLDatabaseTool,
    SQLResult,
)
from semantic_harness.core.orchestrator import (
    AgentOrchestrator,
)
from semantic_harness.security import (
    SecurityContext,
    Role,
    Permission,
    expand_permissions,
    ANONYMOUS_CONTEXT,
    SYSTEM_CONTEXT,
    require_permission,
    PermissionDeniedError,
    AuthConfig,
    AuthResolver,
    get_resolver,
    resolve as resolve_token,
)
from semantic_harness.cloud import (
    CloudFactory,
    get_cloud,
)


__all__ = [
    "__version__",
    "step",
    "SemanticLayer",
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
    "CompiledProcedure",
    "ProcedurePrecondition",
    "ReuseExplanation",
    "ReuseStatus",
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
    "TorchProvider",
    "get_provider",
    "TokenomicsTracker",
    "AmortizationEngine",
    "DynamicCostRouter",
    "ModelTier",
    "ModelPricing",
    "TokenUsageRecord",
    "GraphMemory",
    "PostgresGraphMemory",
    "Entity",
    "Triplet",
    "PreconditionFuzzer",
    "FuzzResult",
    "MetricsCollector",
    "get_metrics_collector",
    "SemanticTracer",
    "Span",
    "get_tracer",
    "SemanticHarnessMiddleware",
    "procedural_route",
    "SQLDatabaseTool",
    "SQLResult",
    "AgentOrchestrator",
    # Security / RBAC
    "SecurityContext",
    "Role",
    "Permission",
    "expand_permissions",
    "ANONYMOUS_CONTEXT",
    "SYSTEM_CONTEXT",
    "require_permission",
    "PermissionDeniedError",
    "AuthConfig",
    "AuthResolver",
    "get_resolver",
    "resolve_token",
    # Multi-Cloud SDK
    "CloudFactory",
    "get_cloud",
]
