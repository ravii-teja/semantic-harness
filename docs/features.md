# Semantic Harness: Feature Roadmap & Implementation Specifications

> **Target Path:** `docs/features.md`  
> **Status:** Active Roadmap for Next Implementations  
> **Related Architecture:** [`docs/context.md`](file:///Users/home/Development/harness/docs/context.md)

This document specifies the prioritized feature enhancements to elevate Semantic Harness into an industry-leading runtime engine for Small Language Models (SLMs) and autonomous agents.

---

## 🗺️ Feature Implementation Roadmap

```
                    ┌─────────────────────────────────────────┐
                    │        PHASE 1: ECONOMIC RUNTIME        │
                    │  Tokenomics, Cost Tracker & Model Router │
                    └────────────────────┬────────────────────┘
                                         │
                                         ▼
                    ┌─────────────────────────────────────────┐
                    │      PHASE 2: RELATIONAL GROUNDING      │
                    │   Knowledge Graph Memory & Triplet Store│
                    └────────────────────┬────────────────────┘
                                         │
                                         ▼
                    ┌─────────────────────────────────────────┐
                    │     PHASE 3: COMPUTE ACCELERATION       │
                    │  TurboQuant Native Kernel & SIMD Bitops │
                    └────────────────────┬────────────────────┘
                                         │
                                         ▼
                    ┌─────────────────────────────────────────┐
                    │      PHASE 4: NOOA DEPTH & BENCHMARKS   │
                    │ Bounded Data Previews & Empirical Eval  │
                    └─────────────────────────────────────────┘
```

---

## 1. Phase 1: Tokenomics & Cost Amortization Engine

### Objective
Provide real-time token tracking, dollar cost calculations, amortization curve analysis ($r^*$), and adaptive model routing (SLM vs. Cloud Frontier).

### Target Module
`semantic_harness.core.tokenomics` (Python) and `semantic-harness/npm/src/core/tokenomics.ts` (TypeScript).

### Key Components to Implement
1. **`TokenomicsTracker`**:
   - Collects per-turn statistics: Prompt Tokens, Completion Tokens, Cached/Bypassed Tokens, C2C Validation Retry Tokens.
   - Calculates real cost using configurable pricing profiles (Ollama local = $0.00/token, Claude 3.5 Sonnet, GPT-4o, DeepSeek-V3).
2. **`AmortizationEngine`**:
   - Measures the procedural compilation overhead vs. steady-state reuse.
   - Evaluates the break-even reuse threshold:
     $$r^* = \frac{C_{\text{compilation}}}{C_{\text{frontier\_turn}} - C_{\text{procedural\_turn}}}$$
   - Quantifies cumulative economic savings ($ and token count) across sessions.
3. **`DynamicCostRouter`**:
   - Tier 1: Zero-token Procedural Memory Cache (sub-microsecond execution).
   - Tier 2: Local SLM (e.g. Qwen 2.5 0.5B/3B, Llama 3.2 1B/3B via Ollama / MLX).
   - Tier 3: Cloud Frontier Fallback (only triggered when local C2C retries exhaust budget or task complexity exceeds SLM confidence threshold).

---

## 2. Phase 2: Knowledge Graph (KG) Memory Layer

### Objective
Enable relational, multi-hop reasoning for small language models by representing declarative memory as interconnected `(Subject, Predicate, Object)` triplets.

### Target Module
`semantic_harness.memory.graph`

### Key Components to Implement
1. **`GraphMemory` (SQLite / DuckDB Property Graph)**:
   - Stores entities (nodes) and relations (edges) with timestamp and activation attributes.
   - Tables: `entities(id, name, type, properties)` and `relations(source_id, predicate, target_id, confidence, timestamp)`.
2. **Automated Triplet Extractor**:
   - Extracts relational triples during successful C2C validations or CodeAct steps.
   - Normalizes entity synonyms using fuzzy matching / Levenshtein distance.
3. **Subgraph Traversal Context Injector**:
   - Given user query entities, retrieves the 1-hop and 2-hop connected neighborhood:
     $$(E_{\text{query}}) \xrightarrow{R_1} (E_{\text{intermediate}}) \xrightarrow{R_2} (E_{\text{target}})$$
   - Formats graph neighborhoods as compact markdown context for the SLM prompt, resolving complex relationships before the model generates its response.

---

## 3. Phase 3: TurboQuant SIMD Acceleration & Hardware Kernels

### Objective
Accelerate PolarQuant random orthogonal rotations and 1-bit / 2-bit inner product distance calculations to achieve true sub-millisecond vector retrieval.

### Target Module
`semantic_harness.memory.turbo_quant`

### Key Components to Implement
1. **SIMD Bitwise Popcount Kernel**:
   - Replace Python loop bit-unpacking with vectorized bitwise XOR + Popcount (`int.bit_count()` or C/Cython extension utilizing `__builtin_popcountll`).
   - Inner product over 1-bit quantized codes via:
     $$\langle \mathbf{u}, \mathbf{v} \rangle \approx \text{dim} - 2 \cdot \text{popcount}(\text{bits}_u \oplus \text{bits}_v)$$
2. **PolarQuant Wasm / Metal Backend**:
   - TypeScript: WebAssembly kernel for browser and edge environments.
   - Python: Optional MLX / PyTorch vector acceleration on Apple Silicon and CUDA.

---

## 4. Phase 4: Full NOOA Contracts & Empirical Benchmarks

### Objective
Complete NVIDIA Object-Oriented Agent patterns and validate the harness with live model executions.

### Key Components to Implement
1. **Pass-by-Reference with Bounded Previews**:
   - Enhance `SandboxedREPL` to inspect complex variables (Pandas DataFrames, PyTorch Tensors, NumPy arrays, long JSON payloads).
   - Generate bounded structural summaries in prompt context (e.g. `<DataFrame shape=(100000, 14), cols=[...], head(2)>`), avoiding context blowout while retaining variable references in the execution namespace.
2. **Live Foundation Model Benchmark Suite**:
   - Replace synthetic notebook formulas in `experiments/` with real multi-turn benchmark executions against local SLMs (`qwen2.5:0.5b`, `qwen2.5-coder:3b`, `llama3.2:1b`, `phi-3.5-mini`) via Ollama/MLX.
   - Report statistical rigor: 95% bootstrap confidence intervals, Wilcoxon signed-rank tests, token reduction percentages, and C2C recovery rates.
