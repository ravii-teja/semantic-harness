# ⚡ Semantic Harness

[![Tests](https://img.shields.io/badge/tests-70%20passed-brightgreen.svg)]()
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)]()
[![TypeScript](https://img.shields.io/badge/typescript-5.0+-3178C6.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Semantic middleware and runtime harness for autonomous AI agents.**  
> Validate outputs, eliminate redundant LLM reasoning with procedural caching, manage 3-tier memory hierarchies, and execute CodeAct REPL loops across small (<0.5GB to 3B) and frontier models.

---

## 🚀 Quick Commands

- **Run all tests & runnable examples:** `bash check.sh`
- **Install Python & NPM packages:** `bash install.sh`
- **Python package:** [`python/`](./python/)
- **TypeScript package:** [`npm/`](./npm/)

---

## 📦 Packages

### 1. Python Implementation (`python/`)
Includes full Python core:
- `@step` middleware decorator
- `Agent` class-as-agent execution harness
- `C2CValidator` schema validation with self-correcting feedback
- `ProceduralMemory`, `LongTermMemory` (ACT-R SQLite), `ShortTermMemory`
- `PythonREPL` stateful execution sandbox & `ToolRegistry`
- 70 unit tests in `python/tests/`
- 4 runnable examples in `python/examples/`

See [python/README.md](./python/README.md) for deep-dive Python documentation.

### 2. TypeScript / Node.js Implementation (`npm/`)
Includes full TypeScript core:
- `Agent` and event bus orchestration
- `C2CSemantics` powered by Zod
- 3-tier memory engine (`ShortTermMemory`, `LongTermMemory`, `ProceduralMemory`)
- `CodeActStrategy` and `REPL` executor
- Strongly typed events and lifecycle hooks

See [npm/README.md](./npm/README.md) for TypeScript documentation.

---

## 🧪 Testing

```bash
# Complete system verification:
bash check.sh

# Python unit tests:
cd python && pytest -v

# TypeScript typecheck:
cd npm && npx tsc --noEmit
```

## 📚 Research Paper
Read the complete technical paper: [`docs/SEMANTIC_HARNESS_PAPER.md`](./docs/SEMANTIC_HARNESS_PAPER.md)

---

## 📄 License

MIT License. Designed & developed by Ravi Teja.
