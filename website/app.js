/* ==========================================================================
   SEMANTIC HARNESS - HIGHLY INTERACTIVE SIMULATION ENGINE
   Google Design Standard compliant
   ========================================================================== */

// INTENT KNOWLEDGE BASE & REGIONAL DATA
const WORKLOAD_DATABASE = {
  revenue: {
    title: "Enterprise Sales Revenue",
    paramName: "Region",
    options: ["North America", "Europe", "APAC", "LATAM"],
    goldValues: {
      "North America": { amount: "$44,410,000", records: 412, rawSql: "SELECT SUM(amount) FROM salesforce_opportunities WHERE region='North America' AND stage='Closed Won';" },
      "Europe": { amount: "$300,000", records: 14, rawSql: "SELECT SUM(amount) FROM salesforce_opportunities WHERE region='Europe' AND stage='Closed Won';" },
      "APAC": { amount: "$1,850,000", records: 58, rawSql: "SELECT SUM(amount) FROM salesforce_opportunities WHERE region='APAC' AND stage='Closed Won';" },
      "LATAM": { amount: "$620,000", records: 22, rawSql: "SELECT SUM(amount) FROM salesforce_opportunities WHERE region='LATAM' AND stage='Closed Won';" }
    },
    vectorStale: "$44,410,000", // The classic vector cache staleness trap
    astName: "crm_closed_won_revenue(region: str)"
  },
  churn: {
    title: "Customer Churn & LTV",
    paramName: "Segment",
    options: ["Enterprise", "Mid-Market", "SMB", "Startups"],
    goldValues: {
      "Enterprise": { amount: "1.2% Churn ($84,000 LTV)", records: 120, rawSql: "SELECT AVG(churn), AVG(ltv) FROM accounts WHERE segment='Enterprise';" },
      "Mid-Market": { amount: "3.8% Churn ($32,000 LTV)", records: 450, rawSql: "SELECT AVG(churn), AVG(ltv) FROM accounts WHERE segment='Mid-Market';" },
      "SMB": { amount: "7.4% Churn ($8,500 LTV)", records: 1200, rawSql: "SELECT AVG(churn), AVG(ltv) FROM accounts WHERE segment='SMB';" },
      "Startups": { amount: "9.1% Churn ($4,200 LTV)", records: 800, rawSql: "SELECT AVG(churn), AVG(ltv) FROM accounts WHERE segment='Startups';" }
    },
    vectorStale: "1.2% Churn ($84,000 LTV)",
    astName: "compute_churn_ltv_by_segment(segment: str)"
  },
  logistics: {
    title: "Carrier Delay & Returns",
    paramName: "Carrier",
    options: ["FedEx", "DHL", "UPS", "USPS"],
    goldValues: {
      "FedEx": { amount: "4.2 hrs delay (1.8% Returns)", records: 980, rawSql: "SELECT AVG(delay_hrs), AVG(return_rate) FROM logistics WHERE carrier='FedEx';" },
      "DHL": { amount: "1.9 hrs delay (0.9% Returns)", records: 640, rawSql: "SELECT AVG(delay_hrs), AVG(return_rate) FROM logistics WHERE carrier='DHL';" },
      "UPS": { amount: "3.1 hrs delay (1.4% Returns)", records: 1100, rawSql: "SELECT AVG(delay_hrs), AVG(return_rate) FROM logistics WHERE carrier='UPS';" },
      "USPS": { amount: "8.5 hrs delay (4.2% Returns)", records: 420, rawSql: "SELECT AVG(delay_hrs), AVG(return_rate) FROM logistics WHERE carrier='USPS';" }
    },
    vectorStale: "4.2 hrs delay (1.8% Returns)",
    astName: "carrier_delay_vs_returns(carrier: str)"
  }
};

// QUICK SCENARIOS SELECTOR
function selectQuickScenario(scenarioKey) {
  const chips = document.querySelectorAll(".scenario-chip");
  chips.forEach(c => c.classList.remove("active"));
  if (event && event.currentTarget) {
    event.currentTarget.classList.add("active");
  }

  const presetSelect = document.getElementById("intent-preset");
  const paramSelect = document.getElementById("param-region");

  if (scenarioKey === "cold") {
    presetSelect.value = "revenue";
    onPresetChange();
    paramSelect.value = "North America";
  } else if (scenarioKey === "param_eu") {
    presetSelect.value = "revenue";
    onPresetChange();
    paramSelect.value = "Europe";
  } else if (scenarioKey === "param_apac") {
    presetSelect.value = "revenue";
    onPresetChange();
    paramSelect.value = "APAC";
  } else if (scenarioKey === "churn_mid") {
    presetSelect.value = "churn";
    onPresetChange();
    paramSelect.value = "Mid-Market";
  }

  triggerSimRun();
}

// PRESET CHANGE HANDLER
function onPresetChange() {
  const presetKey = document.getElementById("intent-preset").value;
  const customRow = document.getElementById("custom-row");
  const paramGroup = document.getElementById("param-group");
  const paramSelect = document.getElementById("param-region");
  const paramLabel = document.getElementById("param-name-label");

  if (presetKey === "custom") {
    customRow.style.display = "flex";
    paramGroup.style.display = "none";
  } else {
    customRow.style.display = "none";
    paramGroup.style.display = "flex";

    const config = WORKLOAD_DATABASE[presetKey];
    paramLabel.textContent = config.paramName;
    paramSelect.innerHTML = "";
    
    config.options.forEach((opt, idx) => {
      const optionEl = document.createElement("option");
      optionEl.value = opt;
      optionEl.textContent = `${opt} ${idx === 0 ? "(Turn 1: Initial Comp.)" : `(Turn ${idx + 1}: Param Variant)`}`;
      if (idx === 1) optionEl.selected = true; // default to Europe / variant
      paramSelect.appendChild(optionEl);
    });
  }

  triggerSimRun();
}

// SIMULATION RUNNER WITH ANIMATED PIPELINE
function triggerSimRun() {
  const runBtn = document.getElementById("run-btn");
  runBtn.disabled = true;
  runBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Executing...';

  // Reset pipeline steps animation
  const steps = [
    document.getElementById("step-1"),
    document.getElementById("step-2"),
    document.getElementById("step-3"),
    document.getElementById("step-4"),
    document.getElementById("step-5")
  ];
  steps.forEach(s => s.classList.remove("active-step"));

  const presetKey = document.getElementById("intent-preset").value;
  let chosenParam = "Europe";
  let targetConfig = WORKLOAD_DATABASE.revenue;

  if (presetKey === "custom") {
    const customPrompt = document.getElementById("custom-input").value;
    chosenParam = customPrompt.includes("EMEA") || customPrompt.includes("Europe") ? "Europe" : "North America";
  } else {
    targetConfig = WORKLOAD_DATABASE[presetKey] || WORKLOAD_DATABASE.revenue;
    chosenParam = document.getElementById("param-region").value;
  }

  const isColdStart = (chosenParam === targetConfig.options[0]);
  const gold = targetConfig.goldValues[chosenParam] || { amount: "$300,000", records: 14, rawSql: "SELECT 300000;" };

  // Animate Step-by-Step
  let currentStep = 0;
  const interval = setInterval(() => {
    if (currentStep < steps.length) {
      steps[currentStep].classList.add("active-step");
      currentStep++;
    } else {
      clearInterval(interval);
      finalizeSimulation(presetKey, chosenParam, targetConfig, gold, isColdStart);
      runBtn.disabled = false;
      runBtn.innerHTML = '<i class="fa-solid fa-play"></i> Run Query';
    }
  }, 120);
}

// UPDATE TELEMETRY & RESULTS
function finalizeSimulation(presetKey, chosenParam, targetConfig, gold, isColdStart) {
  // Column 1: Stateless LLM
  document.getElementById("llm-tokens").textContent = "258 tokens";
  document.getElementById("llm-latency").textContent = "9,081 ms";
  document.getElementById("llm-cost").textContent = "$0.0038";
  document.getElementById("llm-val").textContent = gold.amount;

  // Column 2: Vector Cache
  const cacheTokens = document.getElementById("cache-tokens");
  const cacheLatency = document.getElementById("cache-latency");
  const cacheAcc = document.getElementById("cache-acc");
  const cacheVal = document.getElementById("cache-val");
  const cacheStatus = document.getElementById("cache-status");
  const colCache = document.getElementById("col-cache");

  if (isColdStart) {
    cacheTokens.textContent = "258 tokens";
    cacheLatency.textContent = "9,120 ms";
    cacheAcc.textContent = "Cold Miss (100%)";
    cacheAcc.className = "tel-val text-green";
    cacheVal.textContent = gold.amount;
    cacheVal.className = "card-val text-green";
    cacheStatus.textContent = "✅ Initial Cache Store";
    cacheStatus.className = "card-status status-ok";
  } else {
    cacheTokens.textContent = "0 tokens";
    cacheLatency.textContent = "915 ms";
    cacheAcc.textContent = "62.5% (STALE)";
    cacheAcc.className = "tel-val text-error";
    cacheVal.textContent = targetConfig.vectorStale;
    cacheVal.className = "card-val text-error";
    cacheStatus.textContent = "❌ STALE DATA ERROR (Hit Wrong Arg)";
    cacheStatus.className = "card-status status-error";
  }

  // Column 3: Semantic Harness
  const harnessTokens = document.getElementById("harness-tokens");
  const harnessLatency = document.getElementById("harness-latency");
  const harnessAcc = document.getElementById("harness-acc");
  const harnessVal = document.getElementById("harness-val");

  if (isColdStart) {
    harnessTokens.textContent = "258 tokens (Turn 1)";
    harnessLatency.textContent = "9,120 ms";
    harnessAcc.textContent = "100.0% (Compiled AST)";
    harnessVal.textContent = gold.amount;
  } else {
    harnessTokens.textContent = "0 tokens ($0.00)";
    harnessLatency.textContent = "1.12 ms (80.3 µs)";
    harnessAcc.textContent = "100.0% Verified (Live)";
    harnessVal.textContent = gold.amount;
  }

  // Update Code Trace
  const traceEl = document.getElementById("code-trace");
  if (isColdStart) {
    traceEl.textContent = `# Turn 1 (Cold Start): Intent JIT Program Synthesis
query = "Calculate ${targetConfig.title} for ${chosenParam}"
# >> 1. Cache Miss -> Invoke LLM (Qwen-2.5-Coder-3B)
# >> 2. C2C Validation -> Pydantic Schema Verified ✅
# >> 3. AST Compilation -> Compiled to '${targetConfig.astName}'
# >> 4. Promoted to Procedural Memory (Prior: Beta(2, 1), Conf: 0.88)
# >> Latency: 9,120 ms | Billed Tokens: 258`;
  } else {
    traceEl.textContent = `# Turn (Warm): Parameter Variant Query
query = "Calculate ${targetConfig.title} for ${chosenParam}"
# >> 1. TurboQuant PolarQuant Intent Hit -> '${targetConfig.astName}' (Sim: 0.94, Conf: 0.95 >= 0.85)
# >> 2. AST Parameter Binder -> bound_args = {'${targetConfig.paramName.toLowerCase()}': '${chosenParam}'}
# >> 3. Sandboxed Python REPL -> execute_ast(proc, params=bound_args)
# >> 4. Live DB Execution -> ${gold.amount} (${gold.records} rows aggregated in DuckDB)
# >> Latency: 1.12 ms (80.3 µs) | Model Tokens: 0 | False Reuse Rate: 0.00% ✅`;
  }
}

// BENCHMARK FIGURE TAB SWITCHER
function showFigTab(index) {
  const tabs = document.querySelectorAll(".tab-btn");
  const panes = document.querySelectorAll(".fig-panel");

  tabs.forEach((t, i) => {
    t.classList.toggle("active", i === index);
  });

  panes.forEach((p, i) => {
    p.classList.toggle("active", i === index);
  });
}

// CODE RECIPES TAB SWITCHER
function showCodePane(index) {
  const tabs = document.querySelectorAll(".code-tab-btn");
  const boxes = document.querySelectorAll(".code-box");

  tabs.forEach((t, i) => {
    t.classList.toggle("active", i === index);
  });

  boxes.forEach((b, i) => {
    b.classList.toggle("active", i === index);
  });
}

// ACCORDION STACK ITEM TOGGLE
function toggleStackItem(row) {
  const allRows = document.querySelectorAll(".stack-row");
  allRows.forEach(r => {
    if (r !== row) r.classList.remove("active");
  });
  row.classList.toggle("active");
}

// COPY UTILITIES
function copyInstallCmd(btn) {
  const cmd = document.getElementById("install-cmd").innerText;
  navigator.clipboard.writeText(cmd).then(() => {
    const icon = btn.querySelector("i");
    icon.className = "fa-solid fa-check text-green";
    setTimeout(() => { icon.className = "fa-regular fa-copy"; }, 2000);
  });
}

function copySnippet(btn) {
  const pre = btn.closest(".code-box").querySelector("code");
  navigator.clipboard.writeText(pre.innerText).then(() => {
    btn.innerHTML = '<i class="fa-solid fa-check text-green"></i> Copied!';
    setTimeout(() => { btn.innerHTML = '<i class="fa-regular fa-copy"></i> Copy Code'; }, 2000);
  });
}

function copyBibtex(btn) {
  const bib = document.getElementById("bibtex-val").innerText;
  navigator.clipboard.writeText(bib).then(() => {
    btn.innerHTML = '<i class="fa-solid fa-check text-green"></i> Copied!';
    setTimeout(() => { btn.innerHTML = '<i class="fa-regular fa-copy"></i> Copy'; }, 2000);
  });
}

// THEME TOGGLE (LIGHT / DARK)
function toggleTheme() {
  const isDark = document.body.classList.toggle("dark-theme");
  const icon = document.querySelector("#theme-btn i");
  if (isDark) {
    icon.className = "fa-regular fa-sun";
    localStorage.setItem("sh_theme", "dark");
  } else {
    icon.className = "fa-regular fa-moon";
    localStorage.setItem("sh_theme", "light");
  }
}

// INIT ON LOAD
document.addEventListener("DOMContentLoaded", () => {
  if (localStorage.getItem("sh_theme") === "dark") {
    document.body.classList.add("dark-theme");
    const icon = document.querySelector("#theme-btn i");
    if (icon) icon.className = "fa-regular fa-sun";
  }
  triggerSimRun();
  updateSavingsCalculator();
});

// ==========================================================================
// TOKEN SAVINGS & ROI CALCULATOR ENGINE
// ==========================================================================
const MODEL_PRICING_TABLE = {
  "claude-3-5-sonnet": { name: "Claude 3.5 Sonnet", blendedPerMillion: 9.0, coldLatencySec: 7.2 },
  "gpt-4o": { name: "GPT-4o (Frontier)", blendedPerMillion: 6.25, coldLatencySec: 6.8 },
  "deepseek-v3": { name: "DeepSeek-V3", blendedPerMillion: 0.21, coldLatencySec: 4.5 },
  "llama-3-3-70b": { name: "Llama 3.3 70B (Groq/vLLM)", blendedPerMillion: 0.80, coldLatencySec: 2.1 },
  "qwen-2-5-72b": { name: "Qwen 2.5 72B Instruct", blendedPerMillion: 1.10, coldLatencySec: 3.8 }
};

function onCalcSpendChange(val) {
  document.getElementById("calc-spend-badge").textContent = "$" + parseInt(val, 10).toLocaleString();
  updateSavingsCalculator();
}

function onCalcRepetitionChange(val) {
  document.getElementById("calc-repetition-badge").textContent = val + "% Overlap";
  updateSavingsCalculator();
}

function onCalcTurnsChange(val) {
  document.getElementById("calc-turns-badge").textContent = val + " Turns";
  updateSavingsCalculator();
}

function updateSavingsCalculator() {
  const spendSlider = document.getElementById("calc-spend");
  const modelSelect = document.getElementById("calc-model");
  const repSlider = document.getElementById("calc-repetition");
  const turnsSlider = document.getElementById("calc-turns");

  if (!spendSlider || !modelSelect || !repSlider || !turnsSlider) return;

  const monthlySpend = parseFloat(spendSlider.value);
  const modelKey = modelSelect.value;
  const repetitionRate = parseFloat(repSlider.value) / 100.0;
  const turnsPerTask = parseFloat(turnsSlider.value);
  const modelInfo = MODEL_PRICING_TABLE[modelKey] || MODEL_PRICING_TABLE["gpt-4o"];

  // Compilation amortized savings:
  // Procedural cache bypasses LLM on repeated matched intents.
  // Net efficiency factor: 95.8% (accounts for C2C 1-turn compilation overhead on cold start)
  const netSavingsRatio = repetitionRate * 0.958;
  const monthlySavings = monthlySpend * netSavingsRatio;
  const annualSavings = monthlySavings * 12.0;

  // Compute tokens bypassed
  const totalTokensBilled = (monthlySpend / modelInfo.blendedPerMillion) * 1_000_000;
  const tokensSaved = totalTokensBilled * repetitionRate;

  // Latency hours saved:
  // (tokensSaved / (turnsPerTask * 280 tokens per turn)) * coldLatencySec / 3600
  const estimatedTurnsSaved = tokensSaved / (280.0 * Math.max(1, turnsPerTask * 0.5));
  const latencyHoursSaved = (estimatedTurnsSaved * modelInfo.coldLatencySec) / 3600.0;

  // Break-even turn threshold r*
  // r* = C_compilation / (C_frontier - C_procedural)
  // For semantic harness, compiled routines run in <0.1ms at $0.00, so r* is between 1 and 2 turns
  const breakEvenTurn = (1.0 + (1.0 / turnsPerTask)).toFixed(1);

  // Update UI Elements
  document.getElementById("calc-monthly-savings").textContent = "$" + Math.round(monthlySavings).toLocaleString();
  document.getElementById("calc-annual-savings").textContent = "$" + Math.round(annualSavings).toLocaleString();
  
  if (tokensSaved >= 1_000_000_000) {
    document.getElementById("calc-tokens-saved").textContent = (tokensSaved / 1_000_000_000).toFixed(2) + "B Tokens";
  } else {
    document.getElementById("calc-tokens-saved").textContent = (tokensSaved / 1_000_000).toFixed(1) + "M Tokens";
  }

  document.getElementById("calc-hours-saved").textContent = Math.round(latencyHoursSaved).toLocaleString() + " hrs";
  document.getElementById("calc-breakeven-turn").textContent = "Turn " + breakEvenTurn;
}

function copyCalcSummary(btn) {
  const spend = document.getElementById("calc-spend-badge").textContent;
  const monthly = document.getElementById("calc-monthly-savings").textContent;
  const annual = document.getElementById("calc-annual-savings").textContent;
  const tokens = document.getElementById("calc-tokens-saved").textContent;
  const hours = document.getElementById("calc-hours-saved").textContent;
  const model = document.getElementById("calc-model").selectedOptions[0].text;

  const text = `Semantic Harness Token ROI Analysis:\n` +
    `• Baseline Monthly LLM Spend: ${spend} (${model})\n` +
    `• Projected Monthly Net Savings: ${monthly} / month\n` +
    `• Projected Annual Savings: ${annual} / year\n` +
    `• Tokens Bypassed: ${tokens} / month\n` +
    `• Developer Latency Saved: ${hours} / month\n` +
    `• Break-Even Point: Turn 1.2 (Amortized to $0.00 warm-path)`;

  navigator.clipboard.writeText(text).then(() => {
    btn.innerHTML = '<i class="fa-solid fa-check text-green"></i> Copied ROI Summary!';
    setTimeout(() => {
      btn.innerHTML = '<i class="fa-regular fa-copy"></i> Copy ROI Summary';
    }, 2500);
  });
}

/* ==========================================================================
   MISSION CONTROL / OPERATOR CONSOLE INTERACTIVE ENGINE
   Google Cloud & DeepMind Minimalist Standard
   ========================================================================== */

let activeConsoleTab = 'overview';
let consoleGraphNodes = [];
let consoleGraphLinks = [];
let consoleGraphFilter = 'ALL';
let consoleGraphZoom = 1.0;
let consoleGraphPan = { x: 0, y: 0 };
let selectedGraphNode = null;
let graphCanvasInited = false;

// KNOWLEDGE GRAPH DATASET (18 Connected Cognitive Nodes)
const GRAPH_NODES_DATA = [
  {
    id: "proc:crm_closed_won",
    label: "crm_closed_won",
    type: "PROCEDURE",
    color: "#1e8e3e",
    desc: "Compiled AST procedure. Calculates regional closed-won revenue in 80µs at $0.00 token cost.",
    relations: [
      { rel: "calls", target: "tool:sql_engine" },
      { rel: "validates", target: "inv:RegionEnum" },
      { rel: "derives_from", target: "ent:SalesforceOpp" }
    ],
    code: "def crm_closed_won_revenue(region: str) -> dict:\n    # Zero-Token Fast Path\n    query = f\"SELECT SUM(amount) FROM opps WHERE region='{region}' AND stage='Closed Won';\"\n    rows = sql_engine.execute(query)\n    return {\"region\": region, \"closed_won\": rows[0][0], \"verified\": True}"
  },
  {
    id: "proc:compute_churn_ltv",
    label: "compute_churn_ltv",
    type: "PROCEDURE",
    color: "#1e8e3e",
    desc: "Compiled AST procedure. Aggregates customer churn and lifetime value by account tier.",
    relations: [
      { rel: "calls", target: "tool:sql_engine" },
      { rel: "validates", target: "inv:SegmentRange" },
      { rel: "derives_from", target: "ent:Account" }
    ],
    code: "def compute_churn_ltv_by_segment(segment: str) -> dict:\n    query = f\"SELECT AVG(churn), AVG(ltv) FROM accounts WHERE segment='{segment}';\"\n    res = sql_engine.execute(query)\n    return {\"segment\": segment, \"churn\": res[0][0], \"ltv\": res[0][1]}"
  },
  {
    id: "proc:carrier_delay",
    label: "carrier_delay",
    type: "PROCEDURE",
    color: "#1e8e3e",
    desc: "Compiled AST procedure. Correlates logistics transit delay with customer return rates.",
    relations: [
      { rel: "calls", target: "tool:logistics_db" },
      { rel: "validates", target: "inv:CarrierValid" },
      { rel: "derives_from", target: "ent:Carrier" }
    ],
    code: "def carrier_delay_vs_returns(carrier: str) -> dict:\n    query = f\"SELECT AVG(delay_hrs), AVG(return_rate) FROM logistics WHERE carrier='{carrier}';\"\n    res = logistics_db.execute(query)\n    return {\"carrier\": carrier, \"delay_hrs\": res[0][0], \"return_rate\": res[0][1]}"
  },
  {
    id: "proc:inventory_reorder",
    label: "inventory_reorder",
    type: "PROCEDURE",
    color: "#1e8e3e",
    desc: "Compiled AST procedure. Evaluates safety stock thresholds and generates ERP replenishment triggers.",
    relations: [
      { rel: "calls", target: "tool:erp_api" },
      { rel: "validates", target: "inv:SKUFormat" },
      { rel: "derives_from", target: "ent:WarehouseSKU" }
    ],
    code: "def inventory_reorder_trigger(sku: str) -> dict:\n    item = erp_api.get_stock(sku)\n    reorder = item['qty'] < item['safety_stock']\n    return {\"sku\": sku, \"reorder_needed\": reorder, \"suggested_qty\": item['reorder_qty']}"
  },
  {
    id: "ent:SalesforceOpp",
    label: "SalesforceOpp",
    type: "ENTITY",
    color: "#1a73e8",
    desc: "Core CRM enterprise entity representing sales pipeline opportunities and stage transitions.",
    relations: [{ rel: "indexes", target: "ent:Region" }],
    code: "class SalesforceOpportunity(BaseModel):\n    id: str\n    region: str\n    amount: float\n    stage: str"
  },
  {
    id: "ent:Region",
    label: "Region",
    type: "ENTITY",
    color: "#1a73e8",
    desc: "Geographic sales territory division (North America, Europe, APAC, LATAM).",
    relations: [{ rel: "constrained_by", target: "inv:RegionEnum" }],
    code: "Region = Literal['North America', 'Europe', 'APAC', 'LATAM']"
  },
  {
    id: "ent:Account",
    label: "Account",
    type: "ENTITY",
    color: "#1a73e8",
    desc: "Customer account entity holding historical billing, retention, and LTV telemetry.",
    relations: [{ rel: "categorized_by", target: "ent:Segment" }],
    code: "class Account(BaseModel):\n    account_id: str\n    segment: str\n    ltv: float\n    churn_score: float"
  },
  {
    id: "ent:Segment",
    label: "Segment",
    type: "ENTITY",
    color: "#1a73e8",
    desc: "Enterprise market segment categorization (Enterprise, Mid-Market, SMB, Startups).",
    relations: [{ rel: "constrained_by", target: "inv:SegmentRange" }],
    code: "Segment = Literal['Enterprise', 'Mid-Market', 'SMB', 'Startups']"
  },
  {
    id: "ent:Carrier",
    label: "Carrier",
    type: "ENTITY",
    color: "#1a73e8",
    desc: "Shipping and freight carrier partner entity (FedEx, DHL, UPS, USPS).",
    relations: [{ rel: "constrained_by", target: "inv:CarrierValid" }],
    code: "Carrier = Literal['FedEx', 'DHL', 'UPS', 'USPS']"
  },
  {
    id: "ent:WarehouseSKU",
    label: "WarehouseSKU",
    type: "ENTITY",
    color: "#1a73e8",
    desc: "Stock keeping unit entity for supply chain tracking and replenishment.",
    relations: [{ rel: "constrained_by", target: "inv:SKUFormat" }],
    code: "class WarehouseSKU(BaseModel):\n    sku: str\n    qty: int\n    safety_stock: int"
  },
  {
    id: "tool:sql_engine",
    label: "sql_engine",
    type: "TOOL",
    color: "#f9ab00",
    desc: "Sandboxed analytical SQL execution engine with sub-millisecond query evaluation.",
    relations: [{ rel: "accesses", target: "ent:SalesforceOpp" }],
    code: "def execute(sql: str) -> list[tuple]:\n    # Safe parameterized analytical execution\n    return db_pool.query(sql)"
  },
  {
    id: "tool:salesforce_api",
    label: "salesforce_api",
    type: "TOOL",
    color: "#f9ab00",
    desc: "CRM REST client for syncing opportunities and customer account metadata.",
    relations: [{ rel: "manages", target: "ent:SalesforceOpp" }],
    code: "class SalesforceClient:\n    def get_opps(self, region: str) -> list: ... "
  },
  {
    id: "tool:logistics_db",
    label: "logistics_db",
    type: "TOOL",
    color: "#f9ab00",
    desc: "Real-time carrier tracking database storing transit telemetry and return logs.",
    relations: [{ rel: "accesses", target: "ent:Carrier" }],
    code: "class LogisticsDatabase:\n    def fetch_delays(self, carrier: str): ... "
  },
  {
    id: "tool:erp_api",
    label: "erp_api",
    type: "TOOL",
    color: "#f9ab00",
    desc: "Enterprise Resource Planning REST API for inventory count and supply reorder triggers.",
    relations: [{ rel: "accesses", target: "ent:WarehouseSKU" }],
    code: "class ERPClient:\n    def get_stock(self, sku: str) -> dict: ... "
  },
  {
    id: "inv:RegionEnum",
    label: "inv:RegionEnum",
    type: "INVARIANT",
    color: "#8b5cf6",
    desc: "Precondition invariant rule verifying region is within standard enterprise territories.",
    relations: [{ rel: "protects", target: "proc:crm_closed_won" }],
    code: "assert region in ['North America', 'Europe', 'APAC', 'LATAM'], f'Invalid region: {region}'"
  },
  {
    id: "inv:SegmentRange",
    label: "inv:SegmentRange",
    type: "INVARIANT",
    color: "#8b5cf6",
    desc: "Precondition invariant rule enforcing valid enterprise client tier boundaries.",
    relations: [{ rel: "protects", target: "proc:compute_churn_ltv" }],
    code: "assert segment in ['Enterprise', 'Mid-Market', 'SMB', 'Startups'], f'Unknown segment: {segment}'"
  },
  {
    id: "inv:CarrierValid",
    label: "inv:CarrierValid",
    type: "INVARIANT",
    color: "#8b5cf6",
    desc: "Precondition invariant verifying contracted freight carrier identifier.",
    relations: [{ rel: "protects", target: "proc:carrier_delay" }],
    code: "assert carrier in ['FedEx', 'DHL', 'UPS', 'USPS'], f'Unsupported carrier: {carrier}'"
  },
  {
    id: "inv:SKUFormat",
    label: "inv:SKUFormat",
    type: "INVARIANT",
    color: "#8b5cf6",
    desc: "Precondition invariant asserting 8-character alphanumeric SKU format.",
    relations: [{ rel: "protects", target: "proc:inventory_reorder" }],
    code: "assert len(sku) == 8 and sku.isalnum(), f'Malformed SKU: {sku}'"
  }
];

// TAB SWITCHING
function switchConsoleTab(tabKey, btn) {
  activeConsoleTab = tabKey;
  
  // Update tab buttons
  const buttons = document.querySelectorAll(".console-tab-btn");
  buttons.forEach(b => b.classList.remove("active"));
  if (btn) btn.classList.add("active");

  // Update panes
  const panes = document.querySelectorAll(".console-pane");
  panes.forEach(p => p.classList.remove("active"));
  const targetPane = document.getElementById("pane-" + tabKey);
  if (targetPane) targetPane.classList.add("active");

  // If graph tab is chosen, initialize canvas
  if (tabKey === 'graph') {
    setTimeout(initConsoleGraph, 50);
  }
}

// CONSOLE KNOWLEDGE GRAPH INITIALIZATION & RENDER
function initConsoleGraph() {
  const canvas = document.getElementById("consoleGraphCanvas");
  if (!canvas) return;

  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width;
  canvas.height = rect.height || 520;

  // Initialize nodes positions in a structured circular / relational layout
  if (!graphCanvasInited) {
    const cx = canvas.width / 2;
    const cy = canvas.height / 2;
    const count = GRAPH_NODES_DATA.length;

    GRAPH_NODES_DATA.forEach((node, idx) => {
      // Procedures in inner circle, entities and tools in outer circle
      let radius = 170;
      if (node.type === "PROCEDURE") radius = 80;
      else if (node.type === "INVARIANT") radius = 230;

      const angle = (idx / count) * Math.PI * 2;
      node.x = cx + Math.cos(angle) * radius;
      node.y = cy + Math.sin(angle) * radius;
      node.vx = 0;
      node.vy = 0;
    });

    // Populate links
    consoleGraphLinks = [];
    GRAPH_NODES_DATA.forEach(src => {
      src.relations.forEach(r => {
        consoleGraphLinks.push({
          source: src.id,
          target: r.target,
          rel: r.rel
        });
      });
    });

    // Setup mouse click & drag
    setupGraphInteractivity(canvas);
    graphCanvasInited = true;
  }

  drawConsoleGraph();
}

function drawConsoleGraph() {
  const canvas = document.getElementById("consoleGraphCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.save();
  ctx.translate(consoleGraphPan.x, consoleGraphPan.y);
  ctx.scale(consoleGraphZoom, consoleGraphZoom);

  // Filter nodes
  const visibleNodes = GRAPH_NODES_DATA.filter(n => {
    if (consoleGraphFilter === 'ALL') return true;
    return n.type === consoleGraphFilter;
  });

  const visibleIds = new Set(visibleNodes.map(n => n.id));

  // Draw links
  consoleGraphLinks.forEach(link => {
    if (!visibleIds.has(link.source) || !visibleIds.has(link.target)) return;
    const s = GRAPH_NODES_DATA.find(n => n.id === link.source);
    const t = GRAPH_NODES_DATA.find(n => n.id === link.target);
    if (!s || !t) return;

    ctx.beginPath();
    ctx.moveTo(s.x, s.y);
    ctx.lineTo(t.x, t.y);
    ctx.strokeStyle = (selectedGraphNode && (selectedGraphNode.id === s.id || selectedGraphNode.id === t.id)) 
      ? "#1a73e8" 
      : "#dadce0";
    ctx.lineWidth = (selectedGraphNode && (selectedGraphNode.id === s.id || selectedGraphNode.id === t.id)) ? 2.5 : 1.2;
    ctx.stroke();
  });

  // Draw nodes
  visibleNodes.forEach(n => {
    const isSelected = selectedGraphNode && selectedGraphNode.id === n.id;
    
    // Outer highlight if selected
    if (isSelected) {
      ctx.beginPath();
      ctx.arc(n.x, n.y, 16, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(26, 115, 232, 0.25)";
      ctx.fill();
    }

    // Node body
    ctx.beginPath();
    ctx.arc(n.x, n.y, 10, 0, Math.PI * 2);
    ctx.fillStyle = n.color;
    ctx.fill();
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.stroke();

    // Node label
    ctx.fillStyle = "#1f1f1f";
    ctx.font = isSelected ? "bold 12px 'Google Sans', sans-serif" : "11px 'Google Sans', sans-serif";
    ctx.fillText(n.label, n.x + 14, n.y + 4);
  });

  ctx.restore();
}

function setupGraphInteractivity(canvas) {
  let isDragging = false;
  let dragNode = null;
  let lastX = 0, lastY = 0;

  canvas.addEventListener("mousedown", e => {
    const rect = canvas.getBoundingClientRect();
    const mx = (e.clientX - rect.left - consoleGraphPan.x) / consoleGraphZoom;
    const my = (e.clientY - rect.top - consoleGraphPan.y) / consoleGraphZoom;

    // Check if clicked a node
    const hit = GRAPH_NODES_DATA.find(n => {
      const dx = n.x - mx;
      const dy = n.y - my;
      return Math.sqrt(dx * dx + dy * dy) < 14;
    });

    if (hit) {
      dragNode = hit;
      selectedGraphNode = hit;
      inspectGraphNode(hit);
      drawConsoleGraph();
    } else {
      isDragging = true;
      lastX = e.clientX;
      lastY = e.clientY;
    }
  });

  window.addEventListener("mousemove", e => {
    if (dragNode) {
      const rect = canvas.getBoundingClientRect();
      dragNode.x = (e.clientX - rect.left - consoleGraphPan.x) / consoleGraphZoom;
      dragNode.y = (e.clientY - rect.top - consoleGraphPan.y) / consoleGraphZoom;
      drawConsoleGraph();
    } else if (isDragging) {
      const dx = e.clientX - lastX;
      const dy = e.clientY - lastY;
      consoleGraphPan.x += dx;
      consoleGraphPan.y += dy;
      lastX = e.clientX;
      lastY = e.clientY;
      drawConsoleGraph();
    }
  });

  window.addEventListener("mouseup", () => {
    dragNode = null;
    isDragging = false;
  });
}

function filterConsoleGraph(type, btn) {
  consoleGraphFilter = type;
  const chips = document.querySelectorAll(".graph-filter-chip");
  chips.forEach(c => c.classList.remove("active"));
  if (btn) btn.classList.add("active");
  drawConsoleGraph();
}

function zoomConsoleGraph(factor) {
  consoleGraphZoom *= factor;
  consoleGraphZoom = Math.max(0.5, Math.min(2.5, consoleGraphZoom));
  drawConsoleGraph();
}

function resetConsoleGraph() {
  consoleGraphZoom = 1.0;
  consoleGraphPan = { x: 0, y: 0 };
  drawConsoleGraph();
}

function inspectGraphNode(node) {
  const nameEl = document.getElementById("drawer-node-name");
  const typeEl = document.getElementById("drawer-node-type");
  const descEl = document.getElementById("drawer-node-desc");
  const listEl = document.getElementById("drawer-relations-list");
  const codeEl = document.getElementById("drawer-code-preview");

  if (!nameEl) return;

  nameEl.textContent = node.id;
  typeEl.textContent = node.type;
  typeEl.className = "pill " + (node.type === 'PROCEDURE' ? 'pill-green' : node.type === 'ENTITY' ? 'pill-blue' : 'pill-neutral');
  descEl.textContent = node.desc;

  listEl.innerHTML = "";
  node.relations.forEach(r => {
    const div = document.createElement("div");
    div.innerHTML = `&rarr; ${r.rel} <code>${r.target}</code>`;
    listEl.appendChild(div);
  });

  codeEl.textContent = node.code || "# No code associated";
}

function inspectProcedureAst(procKey) {
  const node = GRAPH_NODES_DATA.find(n => n.id.includes(procKey));
  if (node) {
    switchConsoleTab('graph', document.querySelectorAll(".console-tab-btn")[4]);
    selectedGraphNode = node;
    inspectGraphNode(node);
    drawConsoleGraph();
  }
}

// SIMULATE LIVE INCOMING AGENT TURN
let turnCounter = 9403;
function triggerConsoleSimTurn() {
  const tableBody = document.getElementById("console-stream-body");
  if (!tableBody) return;

  const scenarios = [
    { intent: "crm_closed_won_revenue(region='APAC')", path: "COMPILED_AST", billed: "0 tok ($0.00)", saved: "+$0.0081", lat: "76 µs", status: "✅ HIT (Verified)" },
    { intent: "compute_churn_ltv_by_segment(segment='SMB')", path: "COMPILED_AST", billed: "0 tok ($0.00)", saved: "+$0.0069", lat: "84 µs", status: "✅ HIT (Verified)" },
    { intent: "carrier_delay_vs_returns(carrier='FedEx')", path: "COMPILED_AST", billed: "0 tok ($0.00)", saved: "+$0.0075", lat: "81 µs", status: "✅ HIT (Verified)" },
    { intent: "inventory_reorder_trigger(sku='SKU-9021')", path: "COMPILED_AST", billed: "0 tok ($0.00)", saved: "+$0.0054", lat: "78 µs", status: "✅ HIT (Verified)" }
  ];

  const sc = scenarios[Math.floor(Math.random() * scenarios.length)];
  const tr = document.createElement("tr");
  tr.style.background = "rgba(30, 142, 62, 0.08)";
  tr.innerHTML = `
    <td class="mono-cell">#TRN-${turnCounter++}</td>
    <td><code>${sc.intent}</code></td>
    <td><span class="pill pill-green" style="font-size: 0.7rem; padding: 2px 6px;">${sc.path}</span></td>
    <td class="mono-cell">${sc.billed}</td>
    <td class="mono-cell text-green font-bold">${sc.saved}</td>
    <td class="mono-cell text-blue">${sc.lat}</td>
    <td><span style="color: #1e8e3e; font-weight: 600;">${sc.status}</span></td>
  `;

  tableBody.insertBefore(tr, tableBody.firstChild);

  // Update KPI counters
  const tokSavedEl = document.getElementById("kpi-tokens-saved");
  const costSavedEl = document.getElementById("kpi-cost-saved");
  if (tokSavedEl) {
    const curTok = parseInt(tokSavedEl.textContent.replace(/,/g, '')) + 1480;
    tokSavedEl.textContent = curTok.toLocaleString();
  }
  if (costSavedEl) {
    const curCost = parseFloat(costSavedEl.textContent.replace(/\$/g, '')) + 0.0074;
    costSavedEl.textContent = "$" + curCost.toFixed(2);
  }

  setTimeout(() => {
    tr.style.background = "transparent";
  }, 1000);
}

// ACT-R COGNITIVE COMPACTION
function triggerConsoleCompaction() {
  const btn = event.currentTarget;
  const originalHtml = btn.innerHTML;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin text-amber"></i> Compacting...';

  setTimeout(() => {
    btn.innerHTML = '<i class="fa-solid fa-check text-green"></i> 3.4× Compacted!';
    
    // Nudge memory tab badge
    const memBadge = document.getElementById("badge-memory");
    if (memBadge) memBadge.textContent = "5.14 MB (Compacted)";

    setTimeout(() => {
      btn.innerHTML = originalHtml;
    }, 2500);
  }, 600);
}

// EXPORT CONSOLE TELEMETRY AS JSON
function exportConsoleTelemetry() {
  const payload = {
    timestamp: new Date().toISOString(),
    engine: "semantic-harness",
    version: "0.2.5",
    tokenomics: {
      tokens_bypassed: 2418920,
      prompt_tokens: 412800,
      completion_tokens: 128450,
      cache_hit_rate_pct: 84.6,
      net_cost_saved_usd: 1428.40
    },
    models_configured: ["gemini-2.0-flash", "claude-3-7-sonnet", "gpt-4o", "deepseek-r1", "torch-llama-slm"],
    memory_tiers: {
      procedural_mb: 1.84,
      semantic_kb: 420,
      episodic_mb: 4.12,
      working_kb: 18.2
    },
    knowledge_graph_nodes: GRAPH_NODES_DATA.length,
    status: "HEALTHY"
  };

  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `semantic-harness-telemetry-${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(url);
}


