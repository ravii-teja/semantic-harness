export interface TurnItem {
  role: string;
  content: string;
  timestamp?: number;
  metadata?: Record<string, any>;
}

export class ShortTermMemory {
  private workingMemory: TurnItem[] = [];
  private maxItems: number;

  constructor(maxItems: number = 10) {
    this.maxItems = maxItems;
  }

  add(item: TurnItem): void {
    if (this.workingMemory.length >= this.maxItems) {
      this.workingMemory.shift();
    }
    this.workingMemory.push(item);
  }

  getContext(): TurnItem[] {
    return [...this.workingMemory];
  }

  getWindow(): TurnItem[] {
    return [...this.workingMemory];
  }

  clear(): void {
    this.workingMemory = [];
  }
}
