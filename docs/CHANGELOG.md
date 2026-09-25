# Changelog

All notable changes to **Semantic Harness** follow [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.4] — 2026-09-25

### Added
- **Hardware Auto-Detection & Accelerator Engine (`core.hardware`)**:
  - Automatically identifies host hardware: Apple Silicon Metal (macOS arm64 unified memory via `sysctl`), NVIDIA CUDA GPUs (PyTorch / `nvidia-smi`), and host CPU core/RAM topologies.
  - Automatically selects and configures the optimal local quantized engine when `model` is omitted in `AgentConfig`.
- **Tokenomics & Cost Amortization Engine (`core.tokenomics`)**:
  - Real-time token tracking (prompt, completion, cached, and retry tokens) and exact dollar calculations across local models ($0) and commercial frontier models (GPT-4o, Claude 3.5 Sonnet, DeepSeek-V3).
  - Mathematical break-even threshold analysis ($r^*$) evaluating the economic ROI of procedural memory compilation.
  - Dynamic 3-tier routing: Tier 1 (Procedural Cache) $\rightarrow$ Tier 2 (Hardware-detected Local SLM) $\rightarrow$ Tier 3 (Cloud Frontier fallback upon excessive retries or high complexity).
- **Relational Knowledge Graph Memory (`memory.graph`)**:
  - Embedded SQLite property graph storing entities and directed relations as `(Subject, Predicate, Object)` triplets with timestamps and confidence scores.
  - Multi-hop breadth-first search (BFS) traversal expanding relational graph neighborhoods into structured markdown prompt context for SLMs.
  - Automated regex triplet extraction from model prose.
- **Monochrome Knowledge Graph Visualizer & TurboQuant Export (`visualization.kg_visualizer`)**:
  - High-contrast minimalist black & white (`#000000` / `#ffffff`) force-directed physics graph.
  - Interactive node detail inspector displaying entity properties, degrees, and connected relations upon click.
  - Direct 1-bit PolarQuant vector bitstream export and JSON graph export.
- **NOOA Bounded Variable Previews (`execution.repl`)**:
  - `PythonREPL.get_bounded_previews()` creates structural summaries for DataFrames, NumPy arrays, dicts, and lists, preventing prompt context blowout while retaining variable state in memory.
- **Developer Ergonomics**:
  - Added `.record(...)` alias and `.total_tokens` property to `TokenomicsTracker`.
  - Added clean `.locals` inspection to `REPLResult` and `PythonREPL`.
  - Added explicit `-> None` return annotations across `turbo_quant.py`.

## [0.2.3] — 2026-09-25

### Added
- Initial scaffolding for dual-stack TypeScript Knowledge Graph and Tokenomics engine.

### Added
- **Node.js 22 LTS & Provenance**: Modernized CI runtime and added signed build provenance to npm packages.
- **PyPI Release Environment**: Aligned OIDC trusted publishing environment claims.
- **Clean CI Environment Isolation**: Decoupled test execution from optional LLM client installations with native adapter fallback.

## [0.2.1] — 2026-08-22

### Added
- **PyPI Trusted Publishing (OIDC)**: Automated zero-token passwordless release via GitHub Actions.
- **Continuous Integration Matrix**: Multi-Python (3.10–3.13) & TypeScript build workflow.

## [0.2.0] — 2026-08-22

### Added
- **Real LLM Provider Adapters**: Direct `OpenAIProvider`, `AnthropicProvider`, zero-dependency `OllamaProvider`, `HuggingFaceProvider` (Inference API & TGI endpoints), and `MLXProvider` (Apple Silicon Metal hardware-accelerated on-device SLM execution).
- **Provider Factory**: `get_provider()` with automatic provider routing from model name strings (`gpt-*`, `claude-*`, `ollama/*`, `hf/*`, `mlx/*`, `metal/*`).
- **TurboQuant & PolarQuant Vector Engine**: Extreme 1-bit Hadamard compression with QJL residual error correction.
- **Fuzzy Procedural Memory**: Exact $O(1)$ SHA-256 hash match + sub-microsecond PolarQuant approximate nearest neighbor vector search.
- **TypeScript Parity**: Full TypeScript SDK exports including `Agent` base class, `ShortTermMemory`, `LongTermMemory`, `ProceduralMemory`, and `TurboQuantVectorIndex`.
- **Reproducible Benchmark Suite**: Standalone `benchmarks/run_benchmark.py` testing C2C self-correction, cache latency, and REPL sandbox security.
- **SQLite Migrations**: `MigrationManager` applying incremental versioned schema migrations.
- **Sandboxed REPL Hardening**: AST-level import filtering and blocked builtins in `PythonREPL`.
- **GitHub Actions CI/CD**: Automated matrix testing (`ci.yml`) and PyPI/npm publish workflow (`publish.yml`).

### Changed
- Migrated Python packaging to `hatchling` build backend.
- Refined research paper speedup and empirical ablation benchmarks.

## [0.1.0] — 2026-07-01

### Added
- Initial release: Chaos2Clarity (C2C) Validator, ACT-R Long-Term Memory SQLite, Short-Term Memory, and CodeAct REPL.
- Drop-in `@step` decorator middleware and object-oriented `Agent` class.
- 70 unit and integration tests.
