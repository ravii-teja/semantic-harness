// Core
export { Agent } from "./agent.js";
export type { AgentConfig, AgentMessage, AgentResponse } from "./agent.js";

// Memory
export { ShortTermMemory } from "./memory/short_term.js";
export type { TurnItem } from "./memory/short_term.js";
export { LongTermMemory } from "./memory/long_term.js";
export type { LongTermMemoryItem } from "./memory/long_term.js";
export { ProceduralMemory, SemanticProceduralMemory } from "./memory/procedural.js";
export type { CachedProcedure } from "./memory/procedural.js";
export {
  PolarQuantizer,
  SemanticFeatureEmbedder,
  TurboQuantVectorIndex,
} from "./memory/turbo_quant.js";
export type { QuantizedVector, SearchResult } from "./memory/turbo_quant.js";

// Semantics
export { C2CSemantics } from "./semantics/c2c_semantics.js";

// Strategies
export * from "./strategies/index.js";

// Version
export const VERSION = "0.2.0";
