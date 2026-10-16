import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { ProceduralMemory } from "../memory/procedural.js";
import { expressSemanticHarness, type ExpressRequestLike, type ExpressResponseLike } from "./express_middleware.js";

describe("Express Middleware (TypeScript)", () => {
  test("serves procedural cache HIT with headers when intent matches", async () => {
    const memory = new ProceduralMemory();
    memory.cache("fetch user profile", { userId: 42, name: "Alice" });

    const middleware = expressSemanticHarness({ proceduralMemory: memory });

    const headers: Record<string, string> = {};
    let responseBody: any = null;
    let nextCalled = false;

    const req: ExpressRequestLike = {
      headers: {
        "x-semantic-harness-intent": "fetch user profile",
      },
    };

    const res: ExpressResponseLike = {
      setHeader(name: string, value: string) {
        headers[name] = value;
      },
      json(body: any) {
        responseBody = body;
      },
    };

    await middleware(req, res, () => {
      nextCalled = true;
    });

    assert.equal(nextCalled, false);
    assert.equal(headers["X-Semantic-Harness-Cache"], "HIT");
    assert.equal(headers["X-Semantic-Harness-Tokens-Bypassed"], "150");
    assert.deepEqual(responseBody, {
      status: "success",
      compiled: true,
      result: { userId: 42, name: "Alice" },
    });
  });

  test("passes through on cache MISS and sets MISS header", async () => {
    const memory = new ProceduralMemory();
    const middleware = expressSemanticHarness({ proceduralMemory: memory });

    const headers: Record<string, string> = {};
    let nextCalled = false;

    const req: ExpressRequestLike = {
      headers: {
        "x-semantic-harness-intent": "unseen intent",
      },
    };

    const res: ExpressResponseLike = {
      setHeader(name: string, value: string) {
        headers[name] = value;
      },
      json() {},
    };

    await middleware(req, res, () => {
      nextCalled = true;
    });

    assert.equal(nextCalled, true);
    assert.equal(headers["X-Semantic-Harness-Cache"], "MISS");
  });
});
