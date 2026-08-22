# Contributing to Semantic Harness

Thank you for your interest in contributing to **Semantic Harness**!

## 🚀 Development Setup

```bash
# Clone the repository
git clone https://github.com/ravii-teja/semantic-harness.git
cd semantic-harness

# Setup Python development environment
cd semantic-harness/python
pip install -e ".[dev,all]"

# Setup TypeScript environment
cd ../npm
npm install
```

## 🧪 Running Tests & Benchmarks

```bash
# Run all Python unit tests (78 tests)
cd semantic-harness/python
pytest -v

# Run reproducible benchmarks
cd ../..
python3 semantic-harness/benchmarks/run_benchmark.py --benchmark cache --benchmark repl

# Typecheck and build TypeScript SDK
cd semantic-harness/npm
npm run typecheck
npm run build
```

## 📦 Adding a Provider Adapter

1. Create `python/semantic_harness/providers/your_provider.py`.
2. Extend `BaseProvider` from `semantic_harness.providers.base`.
3. Implement `complete()` (async) and `complete_sync()` (sync) returning `ProviderResponse`.
4. Register the model prefix in `factory.py` (`get_provider`).
5. Re-export in `providers/__init__.py`.

## 🏷️ Versioning & Release

We follow [Semantic Versioning](https://semver.org/). Version is single-sourced in:
- Python: `python/semantic_harness/__version__.py`
- TypeScript: `npm/package.json`
- Git Tag: `v0.2.0`
