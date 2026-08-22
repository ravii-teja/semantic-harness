export class Event {
  constructor(public tag: string, public type: string, public content: any) {}
  
  toString(): string {
    return `${this.type}(${JSON.stringify(this.content)})`;
  }
}

export class EventManager {
  private events: Event[] = [];
  private counter = 0;

  append(eventType: string, content: any): void {
    this.counter++;
    this.events.push(new Event(this.counter.toString(), eventType, content));
  }

  query(eventType?: string, limit?: number): Event[] {
    let results = this.events;
    if (eventType) {
      results = results.filter(e => e.type === eventType);
    }
    if (limit) {
      results = results.slice(-limit);
    }
    return results;
  }

  render(): string {
    if (this.events.length === 0) return "";
    return ["## Event History", ...this.events.map(e => `<sys tag="${e.tag}">\n${e.toString()}\n</sys>`)].join("\n");
  }
}
