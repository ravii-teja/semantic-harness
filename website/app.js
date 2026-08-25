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
});
