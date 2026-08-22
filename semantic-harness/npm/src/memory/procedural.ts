export class ProceduralMemory {
  private procedures: Map<string, any> = new Map();

  saveProcedure(intent: string, procedure: any): void {
    this.procedures.set(intent, procedure);
  }

  retrieveProcedure(intent: string): any | undefined {
    return this.procedures.get(intent);
  }
}
