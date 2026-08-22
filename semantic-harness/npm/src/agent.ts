import { ShortTermMemory } from "./memory/short_term.js";
import { LongTermMemory } from "./memory/long_term.js";
import { ProceduralMemory } from "./memory/procedural.js";

export interface AgentConfig {
  model: string;
  maxTurns?: number;
  maxTokens?: number;
  temperature?: number;
  stmWindowSize?: number;
}

export interface AgentMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface AgentResponse {
  content: string;
  turnCount: number;
  tokenCost: { input: number; output: number };
  fromCache: boolean;
}

/**
 * Base Agent class with integrated memory hierarchy (STM, ACT-R LTM, Procedural Memory).
 * Subclasses implement `_execute()` to connect their LLM provider.
 */
export abstract class Agent {
  readonly config: AgentConfig;
  readonly shortTerm: ShortTermMemory;
  readonly longTerm: LongTermMemory;
  readonly procedural: ProceduralMemory;

  private turnCount = 0;

  constructor(config: AgentConfig) {
    this.config = {
      maxTurns: 10,
      maxTokens: 1024,
      temperature: 0.0,
      stmWindowSize: 20,
      ...config,
    };
    this.shortTerm = new ShortTermMemory(this.config.stmWindowSize!);
    this.longTerm = new LongTermMemory();
    this.procedural = new ProceduralMemory();
  }

  /**
   * Run the agent with a user message.
   */
  async run(userMessage: string): Promise<AgentResponse> {
    // Check procedural cache
    const cached = this.procedural.lookup(userMessage);
    if (cached) {
      return {
        content: typeof cached.procedure === "string" ? cached.procedure : JSON.stringify(cached.procedure),
        turnCount: this.turnCount,
        tokenCost: { input: 0, output: 0 },
        fromCache: true,
      };
    }

    // Build context
    this.shortTerm.add({ role: "user", content: userMessage });
    const messages = this._buildMessages(userMessage);

    // Execute via subclass LLM provider adapter
    const response = await this._execute(messages);

    // Update memory
    this.shortTerm.add({ role: "assistant", content: response.content });
    this.procedural.cache(userMessage, response.content);
    this.turnCount++;

    return {
      ...response,
      turnCount: this.turnCount,
      fromCache: false,
    };
  }

  protected _buildMessages(_userMessage: string): AgentMessage[] {
    const system = this._getSystemPrompt();
    const memories = this.longTerm.recall(3);
    const memoryContext = memories.length > 0
      ? `\n\nRelevant context from memory:\n${memories.map(m => `- ${m.content}`).join("\n")}`
      : "";

    const messages: AgentMessage[] = [
      { role: "system", content: system + memoryContext },
      ...this.shortTerm.getWindow().map(t => ({ role: t.role as "user" | "assistant", content: t.content })),
    ];
    return messages;
  }

  protected _getSystemPrompt(): string {
    return `You are ${this.constructor.name}. Be helpful, precise, and structured.`;
  }

  /**
   * Override this method to wire your LLM provider.
   */
  protected abstract _execute(
    messages: AgentMessage[]
  ): Promise<{ content: string; tokenCost: { input: number; output: number } }>;
}
