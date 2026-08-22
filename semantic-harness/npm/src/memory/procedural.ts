import { TurboQuantVectorIndex, type SearchResult } from "./turbo_quant.js";

export interface CachedProcedure<T = any> {
  intentHash: string;
  intentText: string;
  procedure: T;
  successCount: number;
  failureCount: number;
  lastUsed: number;
  similarity: number;
}

export class ProceduralMemory<T = any> {
  private cacheMap: Map<string, CachedProcedure<T>> = new Map();
  private vectorIndex: TurboQuantVectorIndex<T>;
  public readonly enableFuzzySearch: boolean;

  constructor(vectorDim = 64, enableFuzzySearch = true) {
    this.enableFuzzySearch = enableFuzzySearch;
    this.vectorIndex = new TurboQuantVectorIndex<T>(vectorDim);
  }

  private hashIntent(intent: string): string {
    const normalized = intent.trim().toLowerCase();
    let hash = 0;
    for (let i = 0; i < normalized.length; i++) {
      hash = (Math.imul(31, hash) + normalized.charCodeAt(i)) | 0;
    }
    return Math.abs(hash).toString(16);
  }

  public cache(intent: string, procedure: T, vector?: number[], confidence = 1.0): void {
    const hash = this.hashIntent(intent);
    const normalized = intent.trim().toLowerCase();

    const existing = this.cacheMap.get(hash);
    if (existing) {
      existing.procedure = procedure;
      existing.lastUsed = Date.now();
    } else {
      this.cacheMap.set(hash, {
        intentHash: hash,
        intentText: normalized,
        procedure,
        successCount: 0,
        failureCount: 0,
        lastUsed: Date.now(),
        similarity: 1.0,
      });
    }

    if (this.enableFuzzySearch) {
      this.vectorIndex.add(hash, normalized, procedure, vector, confidence);
    }
  }

  public lookup(intent: string, vector?: number[], similarityThreshold = 0.85): CachedProcedure<T> | undefined {
    const hash = this.hashIntent(intent);
    const exact = this.cacheMap.get(hash);
    if (exact) {
      exact.lastUsed = Date.now();
      exact.similarity = 1.0;
      return exact;
    }

    if (this.enableFuzzySearch && this.vectorIndex.size > 0) {
      const matches = this.vectorIndex.search(vector || intent, 1, similarityThreshold);
      const top = matches[0];
      if (top) {
        const proc = this.cacheMap.get(top.key);
        if (proc) {
          proc.lastUsed = Date.now();
          proc.similarity = top.similarity;
          return proc;
        }
      }
    }

    return undefined;
  }

  public recordSuccess(intent: string): void {
    const hash = this.hashIntent(intent);
    const entry = this.cacheMap.get(hash);
    if (entry) entry.successCount += 1;
  }

  public recordFailure(intent: string): void {
    const hash = this.hashIntent(intent);
    const entry = this.cacheMap.get(hash);
    if (entry) {
      entry.failureCount += 1;
      const total = entry.successCount + entry.failureCount;
      if (entry.successCount / total < 0.5 && entry.failureCount >= 3) {
        this.cacheMap.delete(hash);
        if (this.enableFuzzySearch) this.vectorIndex.remove(hash);
      }
    }
  }

  public get size(): number {
    return this.cacheMap.size;
  }
}
