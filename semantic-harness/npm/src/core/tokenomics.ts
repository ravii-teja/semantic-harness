/**
 * Tokenomics & Cost Amortization Engine in TypeScript.
 */

export enum ModelTier {
  CACHE = "cache",
  LOCAL_SLM = "local_slm",
  CLOUD_FRONTIER = "cloud_frontier",
}

export interface ModelPricing {
  promptPerMillion: number;
  completionPerMillion: number;
}

export const DEFAULT_PRICING: Record<string, ModelPricing> = {
  local_slm: { promptPerMillion: 0, completionPerMillion: 0 },
  ollama: { promptPerMillion: 0, completionPerMillion: 0 },
  "qwen2.5-coder:3b": { promptPerMillion: 0, completionPerMillion: 0 },
  "gpt-4o": { promptPerMillion: 2.5, completionPerMillion: 10.0 },
  "gpt-4o-mini": { promptPerMillion: 0.15, completionPerMillion: 0.6 },
  "claude-3-5-sonnet": { promptPerMillion: 3.0, completionPerMillion: 15.0 },
};

export interface TokenUsageRecord {
  turnId: string;
  modelName: string;
  promptTokens: number;
  completionTokens: number;
  cachedTokens: number;
  retryTokens: number;
  isCacheHit: boolean;
  costUsd: number;
  latencyMs: number;
  metadata?: Record<string, unknown> | undefined;
}

export class TokenomicsTracker {
  private readonly pricing: Map<string, ModelPricing>;
  public readonly records: TokenUsageRecord[] = [];

  constructor(customPricing?: Record<string, ModelPricing>) {
    this.pricing = new Map(Object.entries(DEFAULT_PRICING));
    if (customPricing) {
      for (const [k, v] of Object.entries(customPricing)) {
        this.pricing.set(k, v);
      }
    }
  }

  public setPricing(modelName: string, promptPerMillion: number, completionPerMillion: number): void {
    this.pricing.set(modelName, { promptPerMillion, completionPerMillion });
  }

  public recordTurn(params: {
    turnId: string;
    modelName: string;
    promptTokens?: number;
    completionTokens?: number;
    cachedTokens?: number;
    retryTokens?: number;
    isCacheHit?: boolean;
    latencyMs?: number;
    metadata?: Record<string, unknown>;
  }): TokenUsageRecord {
    const promptTokens = params.promptTokens ?? 0;
    const completionTokens = params.completionTokens ?? 0;
    const cachedTokens = params.cachedTokens ?? 0;
    const retryTokens = params.retryTokens ?? 0;
    const isCacheHit = params.isCacheHit ?? false;
    const latencyMs = params.latencyMs ?? 0;

    const price = this.pricing.get(params.modelName) ?? { promptPerMillion: 0, completionPerMillion: 0 };
    let costUsd = 0;
    if (!isCacheHit) {
      costUsd =
        ((promptTokens + retryTokens) / 1_000_000) * price.promptPerMillion +
        (completionTokens / 1_000_000) * price.completionPerMillion;
    }

    const rec: TokenUsageRecord = {
      turnId: params.turnId,
      modelName: params.modelName,
      promptTokens,
      completionTokens,
      cachedTokens,
      retryTokens,
      isCacheHit,
      costUsd,
      latencyMs,
      metadata: params.metadata,
    };
    this.records.push(rec);
    return rec;
  }

  public get totalPromptTokens(): number {
    return this.records.reduce((acc, r) => acc + r.promptTokens, 0);
  }

  public get totalCompletionTokens(): number {
    return this.records.reduce((acc, r) => acc + r.completionTokens, 0);
  }

  public get totalCachedTokens(): number {
    return this.records.reduce((acc, r) => acc + r.cachedTokens, 0);
  }

  public get totalCostUsd(): number {
    return this.records.reduce((acc, r) => acc + r.costUsd, 0);
  }

  public get cacheHitRate(): number {
    if (this.records.length === 0) return 0;
    const hits = this.records.filter((r) => r.isCacheHit).length;
    return hits / this.records.length;
  }

  public summary() {
    return {
      totalTurns: this.records.length,
      totalPromptTokens: this.totalPromptTokens,
      totalCompletionTokens: this.totalCompletionTokens,
      totalCachedTokens: this.totalCachedTokens,
      totalCostUsd: Number(this.totalCostUsd.toFixed(6)),
      cacheHitRate: Number(this.cacheHitRate.toFixed(4)),
    };
  }
}

export class AmortizationEngine {
  public static breakEvenThreshold(
    compilationCostUsd: number,
    frontierTurnCostUsd: number,
    proceduralTurnCostUsd = 0.0
  ): number {
    const netSavings = frontierTurnCostUsd - proceduralTurnCostUsd;
    if (netSavings <= 0) return Infinity;
    return compilationCostUsd / netSavings;
  }

  public static calculateRoi(
    compilationCostUsd: number,
    invocations: number,
    frontierTurnCostUsd: number,
    proceduralTurnCostUsd = 0.0
  ) {
    const uncompiledBaseline = invocations * frontierTurnCostUsd;
    const actualAmortized = compilationCostUsd + invocations * proceduralTurnCostUsd;
    const netSavings = uncompiledBaseline - actualAmortized;
    const roiPct = compilationCostUsd > 0 ? (netSavings / compilationCostUsd) * 100 : 0;

    return {
      invocations,
      uncompiledBaselineCostUsd: Number(uncompiledBaseline.toFixed(6)),
      actualAmortizedCostUsd: Number(actualAmortized.toFixed(6)),
      netSavingsUsd: Number(netSavings.toFixed(6)),
      roiPct: Number(roiPct.toFixed(2)),
    };
  }
}

export class DynamicCostRouter {
  constructor(
    public readonly tracker: TokenomicsTracker,
    public readonly localModel = "qwen2.5-coder:3b",
    public readonly frontierModel = "gpt-4o-mini",
    public readonly maxLocalRetries = 2
  ) {}

  public decideTier(
    hasProceduralCache: boolean,
    currentRetries = 0,
    estimatedComplexity = 0.5
  ): { tier: ModelTier; model: string } {
    if (hasProceduralCache) {
      return { tier: ModelTier.CACHE, model: "procedural_cache" };
    }
    if (currentRetries >= this.maxLocalRetries || estimatedComplexity > 0.9) {
      return { tier: ModelTier.CLOUD_FRONTIER, model: this.frontierModel };
    }
    return { tier: ModelTier.LOCAL_SLM, model: this.localModel };
  }
}
