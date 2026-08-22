# Changelog

All notable changes to **Semantic Harness** follow [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
