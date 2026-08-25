/* ==========================================================================
   SEMANTIC HARNESS - INTERACTIVE SHOWCASE APPLICATION
   ========================================================================== */

// SIMULATION DATASETS
const SIMULATION_SCENARIOS = {
  param_na: {
    badge: "Turn 1: Cold Start",
    b1: { tokens: 260, latency: "9,120 ms", cost: "$0.0039", status: "Success (Slow)" },
    b4: { tokens: 260, latency: "9,120 ms", accuracy: "Cold Cache Miss (100%)" },
    s0: { tokens: 260, latency: "9,120 ms", accuracy: "100% (AST Compiled & Cached)" },
    expected: "$44,410,000 (North America Revenue)",
    vectorVal: "$44,410,000 (Initial Cold Write)",
    harnessVal: "$44,410,000 (Compiled to AST: crm_revenue)",
    trace: `# Turn 1: Cold Start Reasoning
query = "Calculate total closed won revenue for North America region"

# Step 1: Procedural Cache Check -> MISS (Cold)
# Step 2: Full Neural LLM Invocation (Qwen-2.5-Coder-3B via Ollama)
raw_sql = """SELECT SUM(amount) AS revenue FROM salesforce_opportunities 
             WHERE region = 'North America' AND stage = 'Closed Won';"""

# Step 3: Chaos2Clarity (C2C) Semantic Verification
# >> Pydantic Contract: Validated against 'RevenueReport' schema

# Step 4: Procedural AST Compilation & Promotion (Beta-Bernoulli Prior)
proc_ast = compile_to_ast(raw_sql, params=['region', 'stage'])
procedural_memory.promote('crm_revenue_by_region', proc_ast)

# Step 5: Initial Execution Result: $44,410,000
# >> Billed Tokens: 260 | Latency: 9,120 ms`
  },

  param_eu: {
    badge: "Turn 2: Parameter Variant (The Signature Experiment)",
    b1: { tokens: 258, latency: "9,081 ms", cost: "$0.0038", status: "Full Re-inference" },
    b4: { tokens: 0, latency: "915 ms", accuracy: "❌ STALE DATA ERROR (62.5%)" },
    s0: { tokens: 0, latency: "1.12 ms (80.3 µs)", accuracy: "✅ 100.0% Correct (Live AST)" },
    expected: "$300,000 (Europe Revenue)",
    vectorVal: "$44,410,000 (❌ Stale North America Data)",
    harnessVal: "$300,000 (✅ Live AST REPL Execution)",
    trace: `# Turn 2: Parameter Variant Query
query = "Calculate total closed won revenue for Europe region"

# Step 1: TurboQuant PolarQuant Intent Lookup
proc = procedural_memory.lookup(query, similarity_threshold=0.80)
# >> HIT on Procedure 'crm_revenue_by_region' (Sim: 0.94, Confidence: 0.92 >= 0.85)

# Step 2: AST Parameter Extraction & Type Binding (0 Model Tokens)
# >> Bound Parameters: {'region': 'Europe', 'stage': 'Closed Won'}

# Step 3: Deterministic Sandboxed Python CodeAct REPL Re-Execution
result = execute_ast_in_sandbox(proc.ast_bytecode, params={'region': 'Europe'})
# >> Result: {"revenue": 300000.0, "region": "Europe", "records_aggregated": 14}
# >> Model Tokens: 0 ($0.00) | Latency: 1.12 ms | False Reuse Rate: 0.00%`
  },

  param_apac: {
    badge: "Turn 3: Parameter Variant (Territory Re-query)",
    b1: { tokens: 264, latency: "8,950 ms", cost: "$0.0039", status: "Full Re-inference" },
    b4: { tokens: 0, latency: "890 ms", accuracy: "❌ STALE DATA ERROR (62.5%)" },
    s0: { tokens: 0, latency: "1.08 ms (79.1 µs)", accuracy: "✅ 100.0% Correct (Live AST)" },
    expected: "$1,850,000 (APAC Revenue)",
    vectorVal: "$44,410,000 (❌ Stale North America Data)",
    harnessVal: "$1,850,000 (✅ Live AST REPL Execution)",
    trace: `# Turn 3: Parameter Variant Query (APAC)
query = "What is total closed won revenue in APAC territory?"

# Step 1: TurboQuant PolarQuant Intent Lookup
proc = procedural_memory.lookup(query, similarity_threshold=0.80)
# >> HIT on Procedure 'crm_revenue_by_region' (Sim: 0.91, Confidence: 0.95)

# Step 2: Ingest Extracted Entity -> AST Parameter
bound_args = {'region': 'APAC', 'stage': 'Closed Won'}

# Step 3: Sandboxed Python REPL Query
result = execute_ast_in_sandbox(proc.ast_bytecode, params=bound_args)
# >> Result: {"revenue": 1850000.0, "region": "APAC"}
# >> Model Tokens: 0 | Latency: 1.08 ms | 0 Stale Data Errors`
  },

  c2c_heal: {
    badge: "Turn 4: Small Model (SLM) Auto-Remediation",
    b1: { tokens: 340, latency: "14,200 ms", cost: "$0.0051", status: "Crashes Downstream API" },
    b4: { tokens: 340, latency: "14,200 ms", accuracy: "Unusable String Error" },
    s0: { tokens: 380, latency: "2,150 ms", accuracy: "✅ 100% Healed on 1st Retry Turn" },
    expected: '{"user_id": 101, "email": "alice@corp.com"}',
    vectorVal: 'user_id="101A" (❌ Unhandled String Syntax Error)',
    harnessVal: '{"user_id": 101, "email": "alice@corp.com"} (✅ C2C Healed)',
    trace: `# Turn 4: Compact Model (<0.5GB) Schema Violation
prompt = "Generate user profile for ID 101 Alice"

# Model Turn 1 Output:
# >> {"user_id": "101A", "name": "Alice"} (Missing email, stringified integer)

# Step 1: Chaos2Clarity (C2C) Validator Intercepts Violation:
# >> Error 1: Field 'user_id': Input should be valid integer, got '101A'
# >> Error 2: Field 'email': Required field missing

# Step 2: C2C Synthesizes Differential Feedback Prompt (No stack traces!)
# >> Retry Prompt: "Please fix: user_id must be int, email is required."

# Step 3: Model Converges on 1st Retry:
# >> Output: {"user_id": 101, "name": "Alice", "email": "alice@corp.com"}
# >> Schema Pass Rate lifted from 41.2% -> 96.8%`
  },

  exact_repeat: {
    badge: "Turn 5: Exact Hash Repeat",
    b1: { tokens: 260, latency: "9,081 ms", cost: "$0.0039", status: "Full Re-inference" },
    b4: { tokens: 0, latency: "800 ms", accuracy: "Exact Hit (String)" },
    s0: { tokens: 0, latency: "0.08 ms (80.3 µs)", accuracy: "✅ Exact SHA-256 Hit (0 Tokens)" },
    expected: "$44,410,000 (North America Revenue)",
    vectorVal: "$44,410,000 (Exact String Hit)",
    harnessVal: "$44,410,000 (O(1) SHA-256 Microsecond Hit)",
    trace: `# Turn 5: Exact Repeat Prompt
query = "Calculate total closed won revenue for North America region"

# Step 1: TurboQuant Exact SHA-256 Hash Lookup -> O(1) HIT
# >> Key: sha256("Calculate total closed won revenue for North America region")
# >> Sub-Millisecond Direct Memory Access
# >> Result: {"revenue": 44410000.0, "region": "North America"}
# >> Model Tokens: 0 | Latency: 0.08 ms (80.3 µs) | Cost: $0.00`
  }
};

// RUN SIMULATION
function runSimulation() {
  const select = document.getElementById("query-preset");
  const key = select.value;
  const data = SIMULATION_SCENARIOS[key];
  if (!data) return;

  // Update Badges & Counters
  document.getElementById("sim-scenario-badge").textContent = data.badge;

  // Stateless LLM (B1)
  document.getElementById("b1-tokens").textContent = data.b1.tokens;
  document.getElementById("b1-lat").textContent = data.b1.latency;
  document.getElementById("b1-cost").textContent = data.b1.cost;

  // Vector Cache (B4)
  document.getElementById("b4-tokens").textContent = data.b4.tokens;
  document.getElementById("b4-lat").textContent = data.b4.latency;
  document.getElementById("b4-acc").textContent = data.b4.accuracy;
  document.getElementById("b4-acc").className = data.b4.accuracy.includes("ERROR") ? "text-error" : "text-green";

  // Semantic Harness (S0)
  document.getElementById("s0-tokens").textContent = data.s0.tokens;
  document.getElementById("s0-lat").textContent = data.s0.latency;
  document.getElementById("s0-acc").textContent = data.s0.accuracy;

  // Diff lines
  document.getElementById("diff-expected").textContent = data.expected;
  document.getElementById("diff-vector").textContent = data.vectorVal;
  document.getElementById("diff-vector").className = data.vectorVal.includes("❌") ? "diff-val text-error" : "diff-val text-green";
  document.getElementById("diff-harness").textContent = data.harnessVal;

  // Trace code
  document.getElementById("trace-output").textContent = data.trace;
}

// TOGGLE ARCHITECTURE LAYERS
function toggleLayer(layerNum) {
  const details = document.getElementById(`layer-details-${layerNum}`);
  const parent = details.closest('.layer-item');
  
  if (details.classList.contains('open')) {
    details.classList.remove('open');
    parent.classList.remove('active');
  } else {
    details.classList.add('open');
    parent.classList.add('active');
  }
}

// SWITCH BENCHMARK GALLERY TABS
function switchTab(tabId) {
  // Update Buttons
  const tabs = document.querySelectorAll('.gallery-tab');
  tabs.forEach(tab => tab.classList.remove('active'));
  
  event.currentTarget.classList.add('active');

  // Update Panes
  const panes = document.querySelectorAll('.tab-pane');
  panes.forEach(pane => pane.classList.remove('active'));

  const targetPane = document.getElementById(`tab-${tabId}`);
  if (targetPane) {
    targetPane.classList.add('active');
  }
}

// SWITCH CODE RECIPES TABS
function switchCodeTab(paneId) {
  const tabs = document.querySelectorAll('.code-tab');
  tabs.forEach(tab => tab.classList.remove('active'));

  event.currentTarget.classList.add('active');

  const panes = document.querySelectorAll('.code-pane');
  panes.forEach(pane => pane.classList.remove('active'));

  const target = document.getElementById(`pane-${paneId}`);
  if (target) {
    target.classList.add('active');
  }
}

// COPY UTILITIES
function copyText(text, btn) {
  navigator.clipboard.writeText(text).then(() => {
    const icon = btn.querySelector('i');
    if (icon) {
      icon.className = "fa-solid fa-check text-green";
      setTimeout(() => {
        icon.className = "fa-regular fa-copy";
      }, 2000);
    }
  });
}

function copyCode(btn) {
  const pane = btn.closest('.code-pane');
  const code = pane.querySelector('code').innerText;
  copyText(code, btn);
}

function copyBibtex(btn) {
  const code = document.getElementById('bibtex-text').innerText;
  copyText(code, btn);
}

// THEME TOGGLE
const themeToggleBtn = document.getElementById('theme-toggle');
if (themeToggleBtn) {
  themeToggleBtn.addEventListener('click', () => {
    const isDark = document.body.classList.toggle('dark-theme');
    const icon = themeToggleBtn.querySelector('i');
    if (isDark) {
      icon.className = 'fa-solid fa-sun';
      localStorage.setItem('theme', 'dark');
    } else {
      icon.className = 'fa-solid fa-moon';
      localStorage.setItem('theme', 'light');
    }
  });

  // Restore saved theme
  if (localStorage.getItem('theme') === 'dark') {
    document.body.classList.add('dark-theme');
    themeToggleBtn.querySelector('i').className = 'fa-solid fa-sun';
  }
}

// INITIALIZE ON LOAD
document.addEventListener('DOMContentLoaded', () => {
  runSimulation();
});
