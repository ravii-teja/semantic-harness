import { test, describe } from "node:test";
import assert from "node:assert/strict";
import {
  TokenomicsTracker,
  AmortizationEngine,
  DynamicCostRouter,
  ModelTier,
  GraphMemory,
} from "./index.js";

describe("Tokenomics Engine (TypeScript)", () => {
  test("computes token costs and cache hit rates accurately", () => {
    const tracker = new TokenomicsTracker();
    tracker.setPricing("cloud-model", 2.0, 8.0);

    tracker.recordTurn({
      turnId: "t1",
      modelName: "cloud-model",
      promptTokens: 1000,
      completionTokens: 500,
      isCacheHit: false,
    });

    tracker.recordTurn({
      turnId: "t2",
      modelName: "cloud-model",
      cachedTokens: 1500,
      isCacheHit: true,
    });

    const summary = tracker.summary();
    assert.equal(summary.totalTurns, 2);
    assert.equal(summary.totalPromptTokens, 1000);
    assert.equal(summary.totalCompletionTokens, 500);
    assert.equal(summary.totalCachedTokens, 1500);
    assert.equal(summary.cacheHitRate, 0.5);
    assert.equal(summary.totalCostUsd, 0.006);
  });

  test("calculates break-even threshold and ROI", () => {
    const rStar = AmortizationEngine.breakEvenThreshold(0.05, 0.01, 0.0001);
    assert.ok(rStar > 5.0 && rStar < 5.1);

    const roi = AmortizationEngine.calculateRoi(0.05, 20, 0.01, 0.0);
    assert.equal(roi.uncompiledBaselineCostUsd, 0.2);
    assert.equal(roi.actualAmortizedCostUsd, 0.05);
    assert.equal(roi.netSavingsUsd, 0.15);
    assert.equal(roi.roiPct, 300);
  });

  test("dynamically routes tiers based on cache and retries", () => {
    const tracker = new TokenomicsTracker();
    const router = new DynamicCostRouter(tracker, "qwen2.5-coder:3b", "gpt-4o", 2);

    assert.deepEqual(router.decideTier(true), {
      tier: ModelTier.CACHE,
      model: "procedural_cache",
    });

    assert.deepEqual(router.decideTier(false, 0), {
      tier: ModelTier.LOCAL_SLM,
      model: "qwen2.5-coder:3b",
    });

    assert.deepEqual(router.decideTier(false, 2), {
      tier: ModelTier.CLOUD_FRONTIER,
      model: "gpt-4o",
    });
  });
});

describe("Knowledge Graph Memory (TypeScript)", () => {
  test("stores and traverses relational subgraphs", () => {
    const kg = new GraphMemory();

    kg.addTriplet("Alice", "works_at", "AcmeCorp", 0.99);
    kg.addTriplet("AcmeCorp", "acquired", "BetaLabs", 0.95);

    const rels = kg.getRelationsFor("Alice");
    assert.equal(rels.length, 1);
    assert.equal(rels[0]?.predicate, "works_at");

    const subgraph = kg.traverseSubgraph(["Alice"], 2);
    assert.equal(subgraph.length, 2);

    const rendered = kg.renderSubgraphContext(["Alice"], 2);
    assert.ok(rendered.includes("Alice"));
    assert.ok(rendered.includes("AcmeCorp"));
    assert.ok(rendered.includes("BetaLabs"));
  });

  test("extracts triplets from structured text", () => {
    const kg = new GraphMemory();
    const extracted = kg.extractTripletsFromText("(Alice) --[manages]--> (Bob)");
    assert.equal(extracted.length, 1);
    assert.equal(extracted[0]?.sourceName, "Alice");
    assert.equal(extracted[0]?.predicate, "manages");
    assert.equal(extracted[0]?.targetName, "Bob");
  });
});
