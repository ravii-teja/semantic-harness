# Semantic Harness: System Context & Architecture Overview

> **Document Version:** 1.0.0  
> **Target Path:** `docs/context.md`  
> **Source Base:** `semantic-harness` monorepo (`python/`, `npm/`, `.github/workflows/`, `website/`)  
> **Author & Research:** Bankupalli Ravi Teja | Zenodo DOI: [10.5281/zenodo.19414309](https://zenodo.org/records/19414309)

---

## 1. Executive Overview

**Semantic Harness** is an enterprise-grade runtime middleware and agent execution harness engineered to bridge the performance, reliability, and token-efficiency gap between Small Language Models (SLMs: <0.5B to 3B parameters) and large frontier models.

### Key Value Propositions
1. **Compilation of Reasoning to Procedural Routines:** Multi-turn model reasoning is treated as an initial "compilation" phase. Once verified, execution paths are cached as parameterized procedures that execute in sub-microsecond time with zero LLM tokens.
2. **Deterministic Semantic Guardrails:** Intercepts malformed structured text (JSON, code, schemas) and provides diagnostic feedback prompts directly to the model for self-healing, eliminating pipeline crashes.
3. **Cognitively Grounded Memory:** Leverages an ACT-R activation-decay model for SQLite long-term storage, combined with PolarQuant vector compression (TurboQuant) for compact representations.
4. **Sandboxed CodeAct Execution:** Empowers models to emit executable Python scripts evaluated in an isolated REPL rather than hallucinating mathematical calculations, state transformations, or tool calls.

---

## 2. GitHub Actions Automation & CI/CD Pipelines

The repository maintains automated testing, packaging, and deployments under `.github/workflows/`:

| Workflow File | Triggers | Jobs & Responsibilities |
|---|---|---|
| **[`ci.yml`](file:///.github/workflows/ci.yml)** | Push / PR on `main`, `develop` | - **`python-build-and-test`**: Matrix validation across Python 3.10, 3.11, 3.12, 3.13; runs `pytest -v --cov=semantic_harness` and uploads coverage to Codecov.<br>- **`npm-build-and-test`**: Node.js 22 runtime check, TypeScript compilation (`tsc --noEmit`), build, and unit tests for `@ravii-teja/semantic-harness`.<br>- **`benchmark-local`**: Runs procedural cache and REPL benchmarks (`benchmarks/run_benchmark.py`). |
| **[`publish.yml`](file:///.github/workflows/publish.yml)** | Tag pushes (`v*.*.*`) or manual `workflow_dispatch` | - **`deploy-python-pypi`**: Pre-flight test verification, wheel/sdist packaging with `hatch build`, and OIDC trusted publishing to PyPI.<br>- **`deploy-npm-registry`**: Build verification and npm registry publishing with provenance. |
| **[`pages.yml`](file:///.github/workflows/pages.yml)** | Push to `main` impacting `website/**` | Packages static documentation and interactive demos from `website/` and deploys to GitHub Pages. |

---

## 3. Monorepo Component Breakdown

```
harness/
├── .github/workflows/        # CI/CD, PyPI/npm automated release pipelines, Pages
├── docs/                     # Research papers, assessments, experimental plans
│   ├── context.md            # This system context and architectural reference
│   ├── semantics-assesment.md# Publication readiness and gap analysis
│   └── SEMANTIC_HARNESS_PAPER.md
├── website/                  # Live interactive playground and documentation site
├── experiments/              # Benchmark suites and Jupyter notebooks
└── semantic-harness/         # Core dual-stack SDKs
    ├── python/               # Python Implementation (Hatch / pip package)
    │   ├── pyproject.toml
    │   └── semantic_harness/
    │       ├── core/         # Agent loop, Events, Context Assembler, Budgeting
    │       ├── execution/    # Sandboxed Python REPL & CodeAct AST execution
    │       ├── guard/        # Cycle detection, repetition guards, budget limits
    │       ├── memory/       # STM, LTM (ACT-R SQLite), Procedural Memory, TurboQuant
    │       ├── providers/    # Adapters (OpenAI, Anthropic, Ollama, HuggingFace, MLX)
    │       ├── semantics/    # C2C validator, JSON fence extraction, Schema diffs
    │       └── middleware.py # Drop-in @step decorator
    └── npm/                  # TypeScript Implementation (Node 22 / Zod equivalents)
        ├── package.json
        └── src/              # Parity implementations of Core, Memory, REPL, and C2C
```

### Core Python Modules
* **`middleware.py` (`@step`)**: Minimal-overhead function decorator providing schema enforcement, retry mechanics, and zero-token procedural caching.
* **`semantics/c2c.py` (`C2CValidator`)**: Chaos-to-Clarity validation logic. Extracts JSON from markdown fences, validates with Pydantic, and creates actionable diagnostic diffs on failure.
* **`core/tokenomics.py` (`TokenomicsTracker`, `AmortizationEngine`, `DynamicCostRouter`)**: Telemetry tracking for prompt, completion, cached, and retry tokens, mathematical break-even threshold analysis ($r^*$), and adaptive 3-tier routing (Cache $\rightarrow$ Local SLM $\rightarrow$ Frontier Fallback).
* **`memory/graph.py` (`GraphMemory`)**: Relational knowledge graph storing `(Subject, Predicate, Object)` triplets with multi-hop subgraph BFS traversal and context injection.
* **`memory/procedural.py` (`ProceduralMemory`)**: Key-value and fuzzy semantic store mapping normalized intent signatures to compiled execution routines.
* **`memory/turbo_quant.py` (`TurboQuant`)**: PolarQuant compression with Fast Walsh-Hadamard Transform (FWHT), QJL dimension reduction, and bit-packing.
* **`execution/repl.py` & `execution/codeact.py`**: In-process sandboxed REPL executing arbitrary Python AST blocks with configurable timeouts, state retention, and NOOA bounded previews for large collections and DataFrames.

---

## 4. Semantic Harness Architecture

```
                            ┌────────────────────────┐
                            │  User / Orchestrator   │
                            └───────────┬────────────┘
                                        │ User Intent / Query
                                        ▼
                         ┌──────────────────────────────┐
                         │   Procedural Memory Cache    │ ──[Hit (0 tokens, <1µs)]──┐
                         └──────────────┬───────────────┘                           │
                                        │ Cache Miss                                │
                                        ▼                                           │
                         ┌──────────────────────────────┐                           │
                         │    Knowledge Graph Memory    │ ──(Multi-hop Traversal)   │
                         │   (Entity-Relation Subgraph) │                           │
                         └──────────────┬───────────────┘                           │
                                        ▼                                           │
                         ┌──────────────────────────────┐                           │
                         │   Context Assembler &        │                           │
                         │   ACT-R Memory Injector      │ ──(PolarQuant Compressed) │
                         └──────────────┬───────────────┘                           │
                                        │ Token-Budgeted Prompt                     │
                                        ▼                                           │
                         ┌──────────────────────────────┐                           │
                         │   Tokenomics Cost Router     │ ──(Local SLM vs Cloud)    │
                         └──────────────┬───────────────┘                           │
                                        ▼                                           │
                         ┌──────────────────────────────┐                           │
                         │   Execution Strategy         │                           │
                         │   (CodeAct / Direct Predict) │                           │
                         └──────────────┬───────────────┘                           │
                                        │                                           │
                                        ▼                                           │
                         ┌──────────────────────────────┐                           │
                         │   Small / Local LLM (SLM)    │                           │
                         │   (Qwen-2.5, Ollama, MLX)    │                           │
                         └──────────────┬───────────────┘                           │
                                        │ Raw generation (Prose + JSON / Code)      │
                                        ▼                                           │
                         ┌──────────────────────────────┐                           │
                         │    C2C Semantic Validator    │                           │
                         │    (Pydantic / Type Schema)  │                           │
                         └──────┬───────────────┬───────┘                           │
       [Validation Error]       │               │ [Pass]                            │
   Generates targeted feedback  │               ▼                                   │
   and triggers repair loop ────┘        ┌──────────────┐                           │
                                         │ KG Triplet   │                           │
                                         │ Extraction   │                           │
                                         └──────┬───────┘                           │
                                                ▼                                   │
                                         ┌──────────────┐                           │
                                         │ Memory Write │                           │
                                         │ & Procedure  │                           │
                                         │ Compilation  │                           │
                                         └──────┬───────┘                           │
                                                ▼                                   ▼
                                      Verified Output + Cost Telemetry ◄────────────┘
```

---

## 5. How Small Language Models (SLMs) Achieve Complex Semantic Tasks

Small models (0.5B to 3B parameters) are computationally agile and cost-effective, but possess known vulnerabilities: narrow context windows, susceptibility to hallucination during complex multi-step reasoning, and poor output format discipline. 

The harness turns these small models into reliable production workers through six foundational mechanisms:

### 1. Concept-to-Concept (C2C) Self-Correction
* **Problem:** Small models frequently insert conversational prefixes (`"Sure, here is your JSON:"`), produce syntax errors, or violate field constraints.
* **Harness Solution:** 
  1. `extract_json()` isolates the payload using regex-based code fence and brace matching.
  2. If Pydantic validation fails, the validator avoids standard stack traces and synthesizes a concise, structured error prompt:
     ```text
     Your output failed semantic validation. Please fix these errors:
       ✗ Field 'confidence': Input should be a valid number (type: float_parsing)
     Expected schema (SentimentResult):
       - sentiment (str): required
       - confidence (float): required
     Please regenerate your output matching the schema exactly.
     ```
  3. Small models readily parse this clean diff, allowing them to self-correct on the immediate next turn without requiring high-parameter reasoning capabilities.

### 2. CodeAct Execution (Computation Offloading)
* **Problem:** Multi-digit arithmetic, array sorting, string filtering, and multi-turn state tracking induce severe hallucination in models below 7B parameters.
* **Harness Solution:** The model is guided to generate deterministic Python snippets via `CodeActStrategy`. The harness executes these snippets in a secure, sandboxed REPL (`SandboxedREPL`), passing standard output and variable states back into the model context. Logic and math are delegated to the Python interpreter.

### 3. Dynamic Context Budgeting & ACT-R Long-Term Memory
* **Problem:** SLMs suffer severe context degradation and "needle-in-a-haystack" retrieval failure as token counts increase.
* **Harness Solution:**
  - The context assembler enforces strict token budgets, prioritizing system rules and immediate task constraints.
  - Historical context is persisted into an SQLite database scored using the **ACT-R activation decay model**:
    $$A_i = \ln \sum_{k=1}^n t_k^{-d} + \beta$$
    Facts that are frequently or recently referenced are automatically brought into the model's context window, suppressing irrelevant historical bloat.

### 4. Procedural Memory Compilation (Zero-Token Execution)
* **Problem:** Repeated invocations of multi-step reasoning on SLMs introduce non-zero error probabilities across time.
* **Harness Solution:** Successful multi-turn agent runs are compiled into parameter-variant procedural routines in `ProceduralMemory`. When identical or semantically equivalent user requests recur, the harness retrieves the procedure and executes it immediately in microsecond latency with zero token consumption and zero variance.

### 5. Knowledge Graph (KG) Memory Integration
* **Problem:** Standard vector RAG retrieves disconnected text chunks based on surface similarity, causing SLMs to hallucinate connections across relational facts.
* **Harness Solution:** Integrates a structured graph layer mapping `(Subject, Predicate, Object)` triplets. When queries mention specific entities, the harness retrieves the 1-hop or 2-hop connected subgraph, presenting pre-resolved relational facts directly in the prompt context.

### 6. Tokenomics Cost Router & Amortization
* **Problem:** Running agent loops blindly without budget thresholds causes cost overruns and latency spikes.
* **Harness Solution:** Tracks input tokens, output tokens, cache hit rates, and computes the amortization break-even factor $r^*$. Routes straightforward requests to local SLMs and only escalates to cloud frontier models if C2C validation retries exhaust the local model's budget.

---

## 6. Current Implementation Status: TurboQuant & NOOA

| Component | Status | Implemented | Gaps & Next Steps |
|---|:---:|---|---|
| **TurboQuant & PolarQuant** | **80%** | FWHT ($O(d \log d)$), deterministic sign randomization, PolarQuant 1-bit / 2-bit quantization, QJL dimension reduction, Python + TS vector indices. | Pure Python/NumPy without SIMD bitwise popcount or Metal/C kernels; needs empirical evaluation against large-scale ANN baselines. |
| **NVIDIA NOOA Patterns** | **65%** | Class-as-agent reflection, static/dynamic context split for KV-cache reuse, ACT-R activation ranking, CodeAct REPL execution loop. | Pass-by-reference with bounded previews for big dataframes/tensors; verification benchmarks measuring actual KV-cache prefix hits on vLLM/Ollama. |

