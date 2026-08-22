# ⚡ Semantic Harness

[![CI](https://github.com/ravii-teja/semantic-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/ravii-teja/semantic-harness/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/semantic-harness.svg?color=blue)](https://pypi.org/project/semantic-harness/0.2.0/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/semantic-harness.svg)](https://pypi.org/project/semantic-harness/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)]()
[![Tests](https://img.shields.io/badge/tests-87%20passed-brightgreen.svg)]()
[![TypeScript](https://img.shields.io/badge/typescript-5.0+-3178C6.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Semantic middleware and runtime harness for autonomous AI agents.**  
> Validate outputs, eliminate redundant LLM reasoning with procedural caching, manage 3-tier memory hierarchies, and execute CodeAct REPL loops across small (<0.5GB to 3B) and frontier models.

---

## 📑 Table of Contents

- [Overview](#-overview)
- [📦 Installation & Verification](#-installation--quick-verification)
- [Enterprise Workflow & Adoption Guide (WORKFLOW.md)](./WORKFLOW.md)
- [Why Semantic Harness?](#-why-semantic-harness)
- [Architecture](#-architecture)
- [Monorepo Structure](#-monorepo-structure)
- [Python SDK: How to Use](#-python-sdk)
  - [1. Drop-in `@step` Decorator Middleware](#1-drop-in-step-decorator)
  - [2. Object-Oriented Agent with Memory Tiers](#2-object-oriented-agent-harness)
  - [3. Auto-Routing Provider Factory](#3-provider-factory-openai-anthropic-ollama-hf-metal-mlx)
  - [4. Chaos2Clarity (C2C) Self-Correction](#4-chaos2clarity-c2c-self-correction)
  - [5. TurboQuant Procedural Memory Caching](#5-turboquant-procedural-memory-caching)
  - [6. CodeAct Sandboxed REPL](#6-codeact-sandboxed-repl-execution)
- [TypeScript / Node SDK](#-typescript--node-sdk)
- [Verification & Benchmarks](#-verification--benchmarks)
- [Research Foundations](#-research-foundations)
- [License](#-license)

---

## 📦 Installation & Quick Verification

### 1. Install via pip

Install the package directly from [**PyPI**](https://pypi.org/project/semantic-harness/0.2.0/):

```bash
pip install semantic-harness
```

Or install with specific LLM provider extras:
```bash
# OpenAI / Azure
pip install "semantic-harness[openai]"

# Anthropic Claude
pip install "semantic-harness[anthropic]"

# Hugging Face Inference API / TGI
pip install "semantic-harness[huggingface]"

# Apple Silicon Metal hardware acceleration (Mac M1/M2/M3/M4)
pip install "semantic-harness[mlx]"

# All providers
pip install "semantic-harness[all]"
```

### 2. Verify Post-Installation

Run this one-liner in your terminal to verify installation:

```bash
python -c "import semantic_harness; print(f'⚡ Semantic Harness v{semantic_harness.__version__} is ready!')"
```

---

## 💡 Quickstart: How to Use Post-Installation

### Minimal 3-Line Middleware Example

```python
from pydantic import BaseModel
from semantic_harness import step

class SentimentResult(BaseModel):
    sentiment: str  # "positive" | "negative" | "neutral"
    confidence: float

# Wrap ANY existing function with @step for schema validation & zero-token caching
@step(validates=SentimentResult, cache=True)
def analyze_review(text: str) -> dict:
    # Your LLM call (OpenAI, Anthropic, Ollama, HuggingFace, MLX, etc.)
    return {"sentiment": "positive", "confidence": 0.98}

# Turn 1: Validated against SentimentResult schema
res1 = analyze_review("Fast delivery and amazing customer support!")

# Turn 2: Exact same intent? Procedural cache serves result in 0.60 µs with 0 tokens!
res2 = analyze_review("Fast delivery and amazing customer support!")
```

---

## 🚀 Why Semantic Harness?

| Problem | Without Semantic Harness | With Semantic Harness |
|---|---|---|
| **Small Model Failures** | Malformed JSON crashes the agent pipeline. | C2C validator feeds targeted schema diffs back to LLM for instant self-healing. |
| **Redundant API Costs** | Identical tasks re-query expensive LLMs every time. | Procedural cache serves verified workflows in ~1 µs with 0 tokens. |
| **Context Window Exhaustion** | Long agent conversations overflow model context. | Token budget engine trims context dynamically while preserving vital history. |
| **Volatile Agent Knowledge** | Agent forgets facts across session boundaries. | ACT-R ranked SQLite long-term memory surfaces relevant facts spontaneously. |

---

## 🏛️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             Your Agent Loop                                 │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                        ┌──────────────▼──────────────┐
                        │   Procedural Memory Cache   │ ──(Cache Hit: Skip LLM!)──┐
                        └──────────────┬──────────────┘                           │
                                       │ (Miss)                                   │
                        ┌──────────────▼──────────────┐                           │
                        │     Context Token Budget    │                           │
                        └──────────────┬──────────────┘                           │
                                       │                                          │
                        ┌──────────────▼──────────────┐                           │
                        │     LLM Execution Step      │                           │
                        └──────────────┬──────────────┘                           │
                                       │                                          │
                        ┌──────────────▼──────────────┐                           │
                        │   C2C Semantic Validator    │ ──(Invalid: Self-Correct) │
                        └──────────────┬──────────────┘                           │
                                       │ (Valid)                                  │
                        ┌──────────────▼──────────────┐                           │
                        │      Long-Term Memory       │                           │
                        │    (ACT-R Ranked SQLite)    │                           │
                        └──────────────┬──────────────┘                           │
                                       │                                          │
                                       ▼                                          ▼
                                 Verified Output ◄────────────────────────────────┘
```

---

## 📂 Monorepo Structure

```
semantic-harness/
├── check.sh                  # One-command system check (Python + Examples)
├── install.sh                # Environment installer
├── python/                   # Python Core Implementation
│   ├── pyproject.toml        # Poetry / Flit / Pip configuration
│   ├── README.md             # Python-specific documentation
│   ├── semantic_harness/     # Core package
│   │   ├── core/             # Agent, Events, Context Assembler
│   │   ├── execution/        # CodeAct, Python REPL, Tools registry
│   │   ├── guard/            # Loop guards (budget, repeat detection)
│   │   ├── memory/           # STM, LTM (ACT-R SQLite), Procedural Memory
│   │   ├── providers/        # LLM provider adapters
│   │   ├── semantics/        # C2C validator, JSON extraction
│   │   └── middleware.py     # @step decorator
│   ├── examples/             # 4 runnable quickstart scripts
│   └── tests/                # 70 unit and integration tests
└── npm/                      # TypeScript / Node.js Implementation
    ├── package.json          # NPM package config
    ├── tsconfig.json         # TypeScript configuration
    └── src/                  # TypeScript implementation
        ├── core/             # Agent, Events, Context
        ├── executor/         # REPL Executor
        ├── memory/           # Memory tiers
        ├── semantics/        # Zod C2C validation
        └── strategies/       # CodeAct & Predict strategies
```

---

## 🐍 Python SDK

### Installation

```bash
cd semantic-harness/python
pip install -e .
```

Or with all optional dependencies:
```bash
pip install -e ".[all]"
```

### 1. Drop-in `@step` Decorator

Wrap any function with `@step` to add schema validation and procedural caching without rewriting your logic:

```python
from pydantic import BaseModel
from semantic_harness import step

class CodeReview(BaseModel):
    summary: str
    issues_found: int
    approved: bool

@step(validates=CodeReview, cache=True)
def review_code(diff: str) -> dict:
    # Your LLM call (OpenAI, Anthropic, Ollama, etc.)
    return llm_client.generate_json(diff)

# 1. Automatically validates against CodeReview schema
# 2. Automatically learns and caches successful workflow
# 3. Repeated diffs bypass LLM completely!
result = review_code(diff="git diff...")
```

### 2. Object-Oriented Agent Harness

```python
from semantic_harness import Agent, AgentConfig
from pydantic import BaseModel

class ResearchAgent(Agent):
    """You are a research analyst summarizing corporate disclosures."""

    def extract_financials(self, company: str) -> dict:
        """Extract revenue and net income."""
        ...

agent = ResearchAgent(config=AgentConfig(model="gpt-4o-mini"))

# Store memory with ACT-R importance ranking
agent.long_term.remember("nvidia_q4", "NVIDIA Q4 revenue reached $39.3B", importance=0.95)

# Spontaneous recall injects memories during execution
response = agent.run("Summarize NVIDIA's latest quarterly performance.")
print(response)
```

### 3. Chaos2Clarity (C2C) Self-Correction

```python
from semantic_harness.semantics import C2CValidator
from pydantic import BaseModel

class UserProfile(BaseModel):
    user_id: int
    username: str
    email: str

validator = C2CValidator(schema=UserProfile)

# When an LLM produces malformed data:
raw_output = {"user_id": "not_an_int", "username": "alice"}
result = validator.validate(raw_output)

if not result.is_valid:
    # Generates precise, actionable correction prompt for LLM retry
    print(validator.build_retry_prompt(result))
```

### 4. Procedural Workflow Caching

```python
from semantic_harness.memory import ProceduralMemory

proc_mem = ProceduralMemory()

# Cache verified workflow result
proc_mem.cache(
    intent="invoice_extraction",
    input_text="Invoice #99 total: $1,250",
    result={"invoice_no": "INV-2026-99", "total": 1250.0, "currency": "USD"},
    confidence=1.0
)

# Subsequent exact or semantic match:
hit = proc_mem.lookup("invoice_extraction", "Invoice #99 total: $1,250")
if hit:
    print("Served from cache in 1.25 µs (100% token savings):", hit.result)
```

### 5. CodeAct Python REPL Execution

```python
from semantic_harness.execution import PythonREPL

repl = PythonREPL(timeout=5.0)

# Stateful multi-turn code execution
res1 = repl.execute("data = [10, 20, 30, 40]")
res2 = repl.execute("sum(data) / len(data)")

print(res2.output)  # 25.0
```

---

## 🔷 TypeScript / Node SDK

### TypeScript Installation

```bash
cd semantic-harness/npm
npm install
```

### TypeScript Quickstart

```typescript
import { z } from "zod";
import { C2CSemantics } from "./src/semantics/c2c_semantics";
import { ShortTermMemory } from "./src/memory/short_term";
import { LongTermMemory } from "./src/memory/long_term";

// 1. Zod-powered C2C Validation
const UserSchema = z.object({
  userId: z.number(),
  username: z.string(),
  email: z.string().email(),
});

const semantics = new C2CSemantics(UserSchema);
const validation = semantics.validate({
  userId: 101,
  username: "octocat",
  email: "octocat@github.com",
});
console.log("Is Valid:", validation.isValid);

// 2. Memory Tier Usage
const stm = new ShortTermMemory(10);
stm.add({ role: "user", content: "Initialize deployment." });

const ltm = new LongTermMemory();
ltm.remember("cluster_config", "Production cluster is us-west-2", 0.9);
```

---

## 📊 Feature Comparison

| Capability | Raw LLM Loop | LangGraph / CrewAI | Mem0 | **Semantic Harness** |
|---|:---:|:---:|:---:|:---:|
| **Drop-in `@step` Decorator** | ❌ | ❌ | ❌ | ✅ **Yes** |
| **C2C Step Validation** | ❌ | Manual | ❌ | ✅ **Automated + Feedback** |
| **Procedural Workflow Caching** | ❌ | ❌ | ❌ | ✅ **Yes (Skip LLMs)** |
| **3-Tier Memory (Short/Long/Proc)** | ❌ | Partial | LTM only | ✅ **Unified Hierarchy** |
| **Context Token Budget Engine** | ❌ | Manual | ❌ | ✅ **Dynamic Trimming** |
| **CodeAct REPL Sandbox** | ❌ | External | ❌ | ✅ **Built-in Stateful** |
| **Small Model (<3B) Optimized** | ❌ | ❌ | ❌ | ✅ **Yes** |
| **Deterministic JSONL Logs** | ❌ | ❌ | ❌ | ✅ **Event Bus Auditing** |

---

## 🧪 Verification & Tests

Run the full system verification suite (70 unit tests + 4 runnable end-to-end examples):

```bash
cd semantic-harness
bash check.sh
```

Run pytest directly:
```bash
cd semantic-harness/python
pytest -v
```

Typecheck TypeScript codebase:
```bash
cd semantic-harness/npm
npx tsc --noEmit
```

---

## 📚 Research Paper & Foundations

Read the full technical paper: [**Semantic Harness: Cognitive Middleware and Procedural Acceleration for Agentic Systems**](./SEMANTIC_HARNESS_PAPER.md)

Semantic Harness synthesizes three pioneering systems into a production-grade agent harness:

1. **DeepSeek Harness (DSH)** — Capability-seam architecture, waterfall event lifecycle, session logs as ground truth, and proactive guard plugins.
2. **NVIDIA Object-Oriented Agents (NOOA)** — Class-as-agent patterns, CodeAct REPL execution, static/dynamic context splitting for KV-cache reuse, and ACT-R activation-ranked memory.
3. **Google TurboQuant / PolarQuant** — Information-theoretic quantization and extreme KV compression paradigms informing our quantized procedural indexing roadmap.

---

## 📄 License

MIT License. Copyright (c) 2026 Ravi Teja.
