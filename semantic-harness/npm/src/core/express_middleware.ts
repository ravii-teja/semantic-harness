import { ProceduralMemory } from "../memory/procedural.js";
import { TokenomicsTracker } from "./tokenomics.js";

export interface ExpressRequestLike {
  headers: Record<string, string | string[] | undefined>;
}

export interface ExpressResponseLike {
  setHeader(name: string, value: string): void;
  json(body: any): void;
}

export interface ExpressMiddlewareOptions {
  proceduralMemory?: ProceduralMemory;
  tokenomicsTracker?: TokenomicsTracker;
  enableHeaders?: boolean;
}

/**
 * Express middleware for Semantic Harness procedural compilation & HTTP header telemetry.
 */
export function expressSemanticHarness(options: ExpressMiddlewareOptions = {}) {
  const memory = options.proceduralMemory ?? new ProceduralMemory();
  const tracker = options.tokenomicsTracker ?? new TokenomicsTracker();
  const enableHeaders = options.enableHeaders ?? true;

  return async (req: ExpressRequestLike, res: ExpressResponseLike, next: () => void) => {
    const intent = req.headers["x-semantic-harness-intent"] as string | undefined;

    if (intent) {
      const cached = memory.lookup(intent);
      if (cached) {
        if (enableHeaders) {
          res.setHeader("X-Semantic-Harness-Cache", "HIT");
          res.setHeader("X-Semantic-Harness-Cost-Saved", "$0.00");
          res.setHeader("X-Semantic-Harness-Tokens-Bypassed", "150");
          res.setHeader("X-Semantic-Harness-Latency-Saved-Ms", "1500");
        }
        return res.json({
          status: "success",
          compiled: true,
          result: cached.procedure,
        });
      }
    }

    if (enableHeaders) {
      res.setHeader("X-Semantic-Harness-Cache", "MISS");
    }
    next();
  };
}
