export interface LongTermMemoryItem {
  id: string;
  content: string;
  importance: number;
  embedding?: number[];
  lastAccessed?: number;
  accessCount?: number;
}

export class LongTermMemory {
  private df: LongTermMemoryItem[] = [];

  constructor() {
    this.df = [];
  }

  remember(memoryId: string, content: string, importance: number = 1.0, embedding?: number[]): void {
    const vector = embedding || new Array(128).fill(0.0);
    this.df.push({
      id: memoryId,
      content,
      importance,
      embedding: vector,
      lastAccessed: Date.now(),
      accessCount: 1,
    });
  }

  recall(k: number = 5): LongTermMemoryItem[] {
    return this.recallTopK(k);
  }

  recallTopK(k: number = 5): LongTermMemoryItem[] {
    if (this.df.length === 0) return [];
    // Sort descending by importance
    return [...this.df].sort((a, b) => b.importance - a.importance).slice(0, k);
  }
}
