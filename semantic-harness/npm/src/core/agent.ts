import { ContextManager } from "./context.js";
import { EventManager } from "./events.js";

export class SemanticAgent {
  public context: ContextManager;
  public events: EventManager;
  public llm: any;
  public memory: any = null;

  constructor(llm: any = null) {
    this.llm = llm;
    this.context = new ContextManager();
    this.events = new EventManager();
    
    this.context.setStatic("system_prompt", "You are an intelligent semantic agent.");
  }

  doc(): string {
    // Returns available methods
    const methods = Object.getOwnPropertyNames(Object.getPrototypeOf(this))
      .filter(name => name !== 'constructor' && typeof (this as any)[name] === 'function' && !name.startsWith('_'));
    
    return methods.map(m => `- ${m}: Available method`).join("\n");
  }
}
