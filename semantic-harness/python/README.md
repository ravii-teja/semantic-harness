# ⚡ Semantic Harness

[![CI](https://github.com/ravii-teja/semantic-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/ravii-teja/semantic-harness/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/semantic-harness.svg?color=blue)](https://pypi.org/project/semantic-harness/0.2.2/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19414309.svg)](https://zenodo.org/records/19414309)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-87%20passed-brightgreen.svg)]()
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)]()

> **Semantic middleware for AI agents.** Validate, remember, and accelerate across any framework, loop, or model.  
> **Author:** [Bankupalli Ravi Teja](https://www.linkedin.com/in/raviiteja/) | **Research Paper:** [Chaos to Clarity (Zenodo: 19414309)](https://zenodo.org/records/19414309)

Semantic Harness brings **Chaos2Clarity (C2C) validation** ([Zenodo: 19414309](https://zenodo.org/records/19414309)), **3-tier memory hierarchy**, **procedural workflow caching**, and **context token budget management** directly into your agent loops.

---

## 🚀 Why Semantic Harness?

Small language models (<0.5GB to 3B parameters) and even frontier models suffer from three core bottlenecks in autonomous agent loops:
1. **Schema Fragility:** Small models produce malformed outputs that crash downstream steps.
2. **Context Blowup:** Agent loops quickly exceed context limits or exhaust token budgets.
3. **Redundant Reasoning:** Repeating identical reasoning loops over and over wastes compute and latency.

Semantic Harness solves this with a zero-friction decorator middleware and object-oriented agent harness.

```
┌──────────────────────────────────────────────────────────────┐
│                      Your Agent Loop                         │
└──────────────────────────────┬───────────────────────────────┘
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
                └──────────────┬──────────────┘                           │
                               │                                          │
                               ▼                                          ▼
                         Final Verified Output ◄──────────────────────────┘
```

---

## 📦 Installation

```bash
pip install semantic-harness
```

Or install with specific providers:

```bash
# OpenAI / Azure
pip install "semantic-harness[openai]"

# Anthropic Claude
pip install "semantic-harness[anthropic]"

# Hugging Face Inference API / TGI
pip install "semantic-harness[huggingface]"

# Apple Silicon Metal acceleration (Mac M-series)
pip install "semantic-harness[mlx]"

# All providers
pip install "semantic-harness[all]"
```

---

## ⚡ Quickstart: Drop-in Middleware

Wrap any existing agent function with `@step`. No restructuring needed:

```python
from pydantic import BaseModel
from semantic_harness import step

class CodeReview(BaseModel):
    summary: str
    issues_found: int
    approved: bool

@step(validates=CodeReview, cache=True)
def analyze_code(diff: str) -> dict:
    # Your LLM call (OpenAI, Anthropic, Ollama, vLLM, etc.)
    return llm.generate_json(diff)

# 1. Output is validated against CodeReview (auto-retries if invalid)
# 2. Results are cached in procedural memory
# 3. Repeated diffs skip LLM execution entirely!
review = analyze_code(diff="git diff...")
```

---

## 🧠 Complete Agent Harness

Build robust, object-oriented agents with automated memory tiers:

```python
from semantic_harness import Agent, AgentConfig
from pydantic import BaseModel

class ResearchAgent(Agent):
    """You are a concise research analyst that extracts key facts."""

    def extract_metrics(self, company: str) -> dict:
        """Extract quarterly metrics for a target company."""
        ...

agent = ResearchAgent(config=AgentConfig(model="gpt-4o-mini"))

# 1. Long-term memory stores facts with ACT-R activation ranking
agent.long_term.remember("tesla_q2", "Tesla Q2 revenue reached $25.5B", importance=0.9)

# 2. Spontaneous recall injects relevant facts before turns
result = agent.run("What was Tesla's recent revenue?")
print(result)
```

---

## 📊 Feature Comparison

| Capability | Raw LLM Loop | LangGraph / CrewAI | Mem0 | **Semantic Harness** |
|---|:---:|:---:|:---:|:---:|
| **Drop-in `@step` Decorator** | ❌ | ❌ | ❌ | ✅ **Yes** |
| **C2C Step Validation** | ❌ | Manual | ❌ | ✅ **Automated + Feedback** |
| **Procedural Workflow Caching** | ❌ | ❌ | ❌ | ✅ **Yes (Skip LLMs)** |
| **3-Tier Memory (Short/Long/Proc)**| ❌ | Partial | LTM only | ✅ **Unified** |
| **Context Token Budget Engine** | ❌ | Manual | ❌ | ✅ **Yes** |
| **Small Model (<0.5GB) Optimized** | ❌ | ❌ | ❌ | ✅ **Yes** |
| **Zero-Config Persistence** | ❌ | Requires DB | Cloud/DB | ✅ **SQLite Built-in** |

---

## 🛠️ Architecture Highlights

### 1. Chaos2Clarity (C2C) Validation
When small models fail schema validation, `C2CValidator` (based on [Chaos2Clarity research](https://zenodo.org/records/19414309)) generates actionable, LLM-friendly diagnostic feedback that is fed back into the prompt for immediate self-correction.

### 2. Procedural Memory
Caches verified workflows based on semantic intent. Once a procedure proves reliable (>80% success across 3+ runs), subsequent identical intents bypass the LLM entirely, cutting costs to zero and latency to sub-millisecond.

### 3. ACT-R Long-Term Memory
Combines recency, frequency of recall, and base importance into a cognitive activation score:
$$\text{Activation} = w_r \cdot \text{Recency} + w_f \cdot \ln(1 + \text{Count}) + w_i \cdot \text{Importance}$$

### 4. Context Budget Management
Tracks token pressure across turns, trimming old turns dynamically before the context window overflows.

---

## 🧪 Running Tests

```bash
pytest -v
```

---

## 📚 Research Foundations

Semantic Harness synthesizes three independent research tracks into a unified middleware:

### 1. DeepSeek Harness (DSH) — Plugin Architecture & Event Taxonomy
The capability-seam pattern (Definition → Provider → Consumer), waterfall event lifecycle (`turn/start` → `step/start` → `agent/request` → `agent/response` → `step/end` → `turn/end`), session logs as source of truth, and guard plugins (repeat detection, budget enforcement) are directly adapted from DSH's runtime architecture.

### 2. NVIDIA Object-Oriented Agents (NOOA) — Execution Model & Memory
The class-as-agent pattern (docstrings are prompts, type annotations are contracts), CodeAct REPL execution, pass-by-reference with bounded previews, static/dynamic/event context splits for KV-cache reuse, and ACT-R activation-ranked SQLite memory are adapted from NVIDIA Labs' NOOA framework.

- **Paper:** *Object-Oriented Agents: A Class-Based Agent Framework* (NVIDIA Labs, 2025)

### 3. Google TurboQuant / PolarQuant — Extreme Compression Theory
TurboQuant (ICLR 2026) and PolarQuant (AISTATS 2026) demonstrate that KV cache memory can be compressed by **6×** with **zero accuracy loss** using a two-stage pipeline:

1. **PolarQuant** applies random rotation (Hadamard transforms) to convert Cartesian vectors into polar coordinates. This eliminates the expensive per-block normalization constants that traditional quantizers require, achieving high-quality compression without retraining.
2. **QJL (Quantized Johnson-Lindenstrauss)** applies 1-bit residual error correction to the PolarQuant output, eliminating bias in attention scores.

**Relevance to Semantic Harness:** TurboQuant's information-theoretic approach to lossless compression maps directly to our roadmap for compressing the **procedural memory cache** and **long-term memory embeddings**:
- **Quantized Procedural Index** — Apply PolarQuant-style polar transformations to semantic intent embeddings stored in procedural memory, enabling sub-millisecond approximate nearest-neighbor intent matching without full floating-point vectors.
- **KV-Cache-Aware Context Budget** — Integrate TurboQuant's 3-bit quantization insights into the `ContextBudget` module to predict real GPU memory pressure, not just token count estimates.

- **Papers:** [arXiv:2504.19874](https://arxiv.org/abs/2504.19874) (TurboQuant), [arXiv:2502.02617](https://arxiv.org/abs/2502.02617) (PolarQuant)

---

## 📖 Citation

If you use **Semantic Harness** in your research, please cite:

```bibtex
@software{semantic-harness,
  author       = {Bankupalli, Ravi Teja},
  title        = {{semantic-harness: Cognitive Middleware and Procedural Acceleration Runtime for Autonomous AI Agents}},
  month        = aug,
  year         = 2026,
  publisher    = {Zenodo},
  version      = {0.2.2},
  doi          = {10.5281/zenodo.19414309},
  url          = {https://zenodo.org/records/19414309}
}
```

---

## 📄 License

MIT License. Designed & developed by [Bankupalli Ravi Teja](https://www.linkedin.com/in/raviiteja/).
