export class ShortTermMemory {
  private workingMemory: any[] = [];
  private maxItems: number;

  constructor(maxItems: number = 10) {
    this.maxItems = maxItems;
  }

  add(item: any): void {
    if (this.workingMemory.length >= this.maxItems) {
      this.workingMemory.shift();
    }
    this.workingMemory.push(item);
  }

  getContext(): any[] {
    return [...this.workingMemory];
  }

  clear(): void {
    this.workingMemory = [];
  }
}
