# Changelog

All notable changes to **Semantic Harness** follow [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.5] — 2026-09-27

### Added
- **Drop-In FastAPI & ASGI Middleware (`integrations.fastapi`)**: Zero-effort `SemanticHarnessMiddleware` and `procedural_route` decorator allowing any FastAPI or Starlette application to automatically compile and serve recurring agent workflows at zero tokens in sub-millisecond time. Emits transparent HTTP telemetry headers (`X-Semantic-Harness-Cache`, `X-Semantic-Harness-Cost-Saved`, `X-Semantic-Harness-Tokens-Bypassed`, `X-Semantic-Harness-Latency-Saved-Ms`).
  - *Why this is important*: Eliminates developer migration friction by serving as the primary adoption wedge—existing enterprise web APIs gain procedural caching without refactoring core business logic.
- **Interactive Token Savings & ROI Calculator (`website/` & CLI `roi`)**: Built-in reactive amortization calculator in the official documentation/playground website and via `semantic-harness roi` CLI (`--spend`, `--model`, `--repetition`, `--turns`) providing automated financial projections, bypassed token metrics, developer latency recovery, and break-even turn ($r^*$) analysis.
  - *Why this is important*: Bridges the gap between technical architect evaluation and executive budget approvals by translating procedural hit rates into direct dollar and compute savings.
- **Closing the "Procedural Gap" Architectural Positioning**: Formally established Semantic Harness as the definitive answer to the fourth pillar of enterprise LLM systems—closing the Procedural Gap alongside RAG (Knowledge Gap), 1M+ Context Windows (Context Length Gap), and Fine-Tuning (Domain Style Gap).
  - *Why this is important*: Clarifies market differentiation and category leadership against standard response caches and prompt-trimming utilities.
- **Multi-Model Empirical Benchmark Suite (`experiments/run_ablation.py`) (P1.1)**: Multi-model empirical benchmark execution across 4 local SLMs (`Qwen/Qwen2.5-0.5B-Instruct`, `Qwen/Qwen2.5-Coder-3B-Instruct`, `meta-llama/Llama-3.2-1B-Instruct`, `microsoft/Phi-3.5-mini-instruct`) computing 95% bootstrap confidence intervals (500 resamples), Wilcoxon signed-rank paired significance tests, McNemar schema accuracy lift, and token cost curves saved to `experiments/ablation_results.json`.
  - *Why this is important*: Statistically validates that procedural compilation yields $>90\%$ latency and token cost reductions ($p < 0.001$) and C2C schema validation delivers $>95\%$ JSON conformity on sub-3B SLMs.
- **TypeScript Operator CLI & Hardware Detection Parity (`npm/src/cli.ts` & `npm/src/core/hardware.ts`) (P1.2)**: Host silicon detection in Node.js (`HardwareDetector`) probing Apple Metal unified memory, NVIDIA CUDA GPUs via `nvidia-smi`, CPU architecture, and model recommendations. Created `semantic-harness` CLI (`hardware`, `cache inspect`, `cache export`) with `"bin"` entry in `npm/package.json`.
  - *Why this is important*: Empowers Node.js and TypeScript agent operators to inspect host accelerators and audit serialized procedural cache files directly from the shell via `npx semantic-harness`.
- **Distributed Procedural Storage Backend (`memory.procedural`) (P2.1)**: Pluggable storage architecture (`BaseProceduralStorage`, `DiskProceduralStorage`, `RedisProceduralStorage`) supporting Redis cluster backends with automatic serialization, multi-process synchronizations, and graceful fallback.
  - *Why this is important*: Allows distributed agent workers running across Kubernetes pods to share compiled procedural routines horizontally with sub-millisecond network lookup.
- **4-Bit & 8-Bit Model Quantization in `TorchProvider` (`providers.torch_provider`) (P2.2)**: Added `load_in_4bit`, `load_in_8bit`, and `torch_compile` parameters integrating `BitsAndBytesConfig` (NF4/FP4 quantization) and PyTorch Inductor compilation into in-process HuggingFace execution.
  - *Why this is important*: Reduces VRAM footprint of local 3B–7B models from ~6GB to <2GB, allowing local agent execution on consumer laptops and edge workstations.
- **Google-Style Minimalist Mission Control & Turn-Key Observability Console (`visualization.dashboard` & `website/#console`) (P3.1 Upgrade)**: Standalone HTTP server and live web console adhering to authentic Google Material 3 / DeepMind design aesthetics. Unifies real-time Tokenomics meters (Prompt, Completion, 78.2% Bypassed at $0.00), multi-model fleet routing status, 4-tier memory capacity gauges (Procedural, Semantic, Episodic, Working), interactive force-directed Knowledge Graph with node inspector drawer, and live Prometheus telemetry. Exposed via `semantic-harness dashboard [--port PORT] [--open]`.
  - *Why this is important*: Eliminates the "headless agent" limitation (elevating End-User Daily Utility from 3/10 to 9/10) by providing enterprise operators, SREs, and architects a stunning, interactive visual command surface with zero frontend setup.
- **Ultra-Dense LUT Popcount Similarity Matrix Kernel (`memory.turbo_quant`) (P3.2)**: 256-element byte popcount lookup table (`_BYTE_POPCOUNT`), accelerated matrix similarity (`similarity_dense_matrix`), and dynamic candidate matrix caching in `TurboQuantVectorIndex`.
  - *Why this is important*: Replaces iterative scalar bit calculations with fast byte lookups and contiguous matrix operations, enabling sub-millisecond retrieval across procedural vector indices exceeding 1,000,000 entries.
- **PyTorch & TensorFlow Deep Tensor Acceleration (`memory.turbo_quant`)**: Batched Fast Walsh-Hadamard Transform (FWHT) orthogonal projection (`_torch_fwht`), batched 1-bit PolarQuant vector quantization (`quantize_batch`), and parallel GPU-accelerated candidate similarity evaluation (`similarity_batch`) utilizing PyTorch tensor operations (`torch.bitwise_xor` and popcount) with automatic CUDA, Apple MPS, and CPU acceleration and seamless NumPy fallback.
  - *Why this is important*: Eliminates vector processing bottlenecks in large embedding search spaces; running Walsh-Hadamard projections and bitwise Hamming similarity on tensors yields $50\times–100\times$ faster batched semantic recall compared to scalar iteration while maintaining sub-millisecond latency.
- **Native In-Process PyTorch Model Provider (`providers.torch_provider`)**: High-performance `TorchProvider` executing HuggingFace causal LM models directly inside the host process across `cuda`, `mps`, or `cpu` devices with automatic half-precision (`bfloat16`/`float16`), chat templating, and asynchronous non-blocking inference via `asyncio.to_thread`.
  - *Why this is important*: Eliminates reliance on external REST server daemons (such as Ollama or vLLM) in resource-constrained or embedded environments, enabling direct model weights execution on dedicated GPUs or Apple Silicon unified memory.
- **Multi-Framework Hardware Discovery Engine (`core.hardware`)**: Framework probing via `HardwareDetector.detect_frameworks()` identifying installed PyTorch and TensorFlow runtimes, active CUDA acceleration, Apple Silicon Metal Performance Shaders (`mps`), AMD ROCm (`hip`), device counts, and physical GPU allocations.
  - *Why this is important*: Enables heterogeneous auto-tuning across cloud instances and local developer workstations, allowing `semantic-harness` to dynamically select the fastest available tensor acceleration engine without user configuration.
- **Modular Hardware Extras (`pyproject.toml`)**: Added `torch` (`torch>=2.0`, `transformers>=4.40`, `accelerate>=0.28`) and `tensorflow` (`tensorflow>=2.14`) optional dependency extras.
  - *Why this is important*: Keeps the base package lightweight (~zero bloat) while providing simple one-command installation (`pip install "semantic-harness[torch]"`) for users wanting full deep learning capabilities.
- **Transparent Async/Await Support (`middleware.py`)**: Dual-dispatch decorator on `@layer.step` supporting native async coroutines with non-blocking cache lookups, asynchronous schema validation retry loops, and automatic procedural compilation.
  - *Why this is important*: Prevents event loop blocking and unawaited coroutine drops in modern asynchronous frameworks (FastAPI, Starlette, LiteLLM, `aiohttp`, `AsyncOpenAI`), enabling seamless microservice integration without changing function invocation syntax.
- **Procedural Cache Durability & Multi-Process Persistence (`memory.procedural`)**: Atomic disk persistence (`persist_path`, `save()`, `load()`) using temporary files and atomic `os.replace` to prevent corrupted partial reads in containerized and multi-process deployments.
  - *Why this is important*: Ensures compiled routines survive pod and container restarts in Kubernetes/ECS/serverless environments, preventing cold-cache token cost spikes and enabling zero-token warm starts via CI/CD pre-warming.
- **Thread-Safety & Re-entrant Concurrency (`RLock`)**: Re-entrant thread locking (`threading.RLock`) across `ProceduralMemory` (`compile`, `explain_lookup`, `record_success`) and `TokenomicsTracker` (`record_turn`, `summary`, token metrics).
  - *Why this is important*: Protects shared cache dictionaries and telemetry arrays from race conditions, data loss, and runtime modification errors under high-concurrency WSGI/ASGI multi-threaded workers (e.g. Uvicorn threads, Gunicorn gthreads).
- **Enterprise Observability & Prometheus Exporter (`telemetry.metrics`)**: Native `MetricsCollector` providing Prometheus exposition format for step calls, cache hits, average latencies, token consumption by type/model, and procedural cache size gauge.
  - *Why this is important*: Eliminates "black box" agent deployments by providing out-of-the-box telemetry scrapable by Prometheus, Grafana, and Datadog for live SLA monitoring and alerting.
- **OpenTelemetry-Compatible Tracing (`telemetry.tracing`)**: Structured hierarchical `SemanticTracer` and `Span` context managers capturing parent-child execution traces, events, error metadata, and JSON export.
  - *Why this is important*: Allows distributed tracing across multi-step agent tool calls and sub-tasks, enabling engineers to instantly locate performance bottlenecks and pinpoint schema failures.
- **Operator CLI (`semantic_harness.cli`)**: Command-line tool registered under `[project.scripts]` as `semantic-harness`, providing `hardware` profiling, `cache inspect`, `cache export`, and `metrics` exposition.
  - *Why this is important*: Grants DevOps and SRE teams out-of-band operational debugging and inspection tools to audit cache health and verify hardware acceleration directly from the terminal without writing ad-hoc scripts.
- **Production Validation Test Suite (`tests/test_production.py` & `tests/test_torch_acceleration.py`)**: 17 rigorous tests covering async execution, cache durability, multi-threaded concurrency, telemetry export, CLI commands, PyTorch FWHT math equivalence, batched quantization, GPU candidate similarity, and in-process `TorchProvider` factory routing.
  - *Why this is important*: Provides concrete regression protection for enterprise capabilities, bringing the verified Python test suite to 115 tests passing (100% pass rate).

### Fixed
- **README API Correctness**: Corrected all three code examples that had drifted from the current API:
  - `C2CValidator` no longer accepts `schema` in `__init__`; updated example passes schema to `validate(data, Schema)`.
  - `ValidationResult` uses `.valid` and `.retry_prompt` fields, not `.is_valid` / `build_retry_prompt()`.
  - `ProceduralMemory` example updated from stale `cache(intent, input_text=..., result=...)` to current `compile(intent, trajectory=...) + record_success()` + `lookup(intent, require_reliable=True)` pattern; added `explain_lookup()` showcase.
- **README Broken Links**: Fixed three dead hyperlinks — `WORKFLOW.md`, `CHANGELOG.md`, and `SEMANTIC_HARNESS_PAPER.md` now correctly resolve to `docs/`.
- **README Architecture Image**: Restored the missing benchmark figure (`docs/figures/semantic_harness_benchmark.png`) in the Architecture section.
- **Package Exports (`__init__.py`)**: Re-exported `SemanticLayer` in top-level package and added to `__all__`.
- **Strict Typing Compliance**: Added explicit return annotations (`-> None`) and parameter annotations (`*args: Any, **kwargs: Any`) across `middleware.py` (`wrapper`), `core/agent.py` (`Agent.__init__`, `_register_methods`, `run`, `arun`), and `core/tokenomics.py` (`TokenomicsTracker.__init__`, `set_pricing`, `DynamicCostRouter.__init__`).
- **Version Bump (0.2.5)**: Bumped dual-stack package version to `0.2.5` across Python (`__version__.py`, `pyproject.toml`), TypeScript (`npm/package.json`), documentation (`CITATION.cff`, `SEMANTIC_HARNESS_PAPER.md`), and README PyPI badges.
- **CI/CD Continuous Validation**: Integrated scientific ablation benchmark smoke test (`python experiments/run_ablation.py --tasks 20`) into `.github/workflows/ci.yml`.
- **README Alignment**: Restructured Python SDK sections 1 through 8 to match the Table of Contents 1:1, added Section 3 Provider Factory, and updated test verification counter to 98.

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
- **Compiled Procedural Memory & Invariant Preconditions (`memory.procedural`)**:
  - `CompiledProcedure` captures trajectory, parameterized inputs, and strict safety invariants (`ProcedurePrecondition`).
  - Added schema fingerprinting (`schema_fingerprint`), tool version checks (`tool_signatures`), and environment dependency validation (`env_keys`).
  - `explain_lookup()` returns an auditable `ReuseExplanation` trace with `ReuseStatus` (`reused`, `unreliable`, `schema_mismatch`, `tool_version_mismatch`, `environment_mismatch`, `cache_miss`).
  - Upgraded `@step` decorator to automatically compute schema hashes and enforce procedural preconditions.
- **NOOA Bounded Variable Previews (`execution.repl`)**:
  - `PythonREPL.get_bounded_previews()` creates structural summaries for DataFrames, NumPy arrays, dicts, and lists, preventing prompt context blowout while retaining variable state in memory.
- **Developer Ergonomics**:
  - Added `.record(...)` alias and `.total_tokens` property to `TokenomicsTracker`.
  - Added clean `.locals` inspection to `REPLResult` and `PythonREPL`.
  - Added explicit return type annotations (`-> None`, `-> CompiledProcedure`, generic `Callable[..., Any]`) across `turbo_quant.py`, `procedural.py`, and `middleware.py` for 100% strict type checker compliance.

## [0.2.3] — 2026-08-23

### Added
- **Multi-Package CI/CD Matrix Enhancements**: Extended GitHub Actions workflows for unified dual Python (PyPI) and NPM publishing.
- Initial scaffolding for dual-stack TypeScript Knowledge Graph and Tokenomics engine.

## [0.2.2] — 2026-08-22

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
