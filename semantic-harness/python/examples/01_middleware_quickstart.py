"""
Example 01: Drop-in Semantic Middleware Quickstart

Demonstrates using @step decorator for zero-overhead validation and caching.
"""

from pydantic import BaseModel, Field
from semantic_harness import step

class SentimentResult(BaseModel):
    sentiment: str = Field(description="positive, negative, or neutral")
    score: float = Field(ge=0.0, le=1.0)
    keywords: list[str]

@step(validates=SentimentResult, cache=True)
def classify_text(text: str) -> dict:
    print(f"  [LLM Called] Processing: '{text}'")
    # Simulated LLM generation:
    return {
        "sentiment": "positive",
        "score": 0.95,
        "keywords": ["fast", "reliable", "efficient"]
    }

if __name__ == "__main__":
    print("--- 1. Cold Execution (Establishing Reliability) ---")
    for i in range(3):
        res = classify_text("Semantic Harness is lightning fast and reliable!")
        print(f"  Turn {i+1} completed: {res.sentiment} (score={res.score})")

    print("\n--- 2. Warm Execution (Procedural Cache Hit - Skips LLM!) ---")
    cached_res = classify_text("Semantic Harness is lightning fast and reliable!")
    print("  Cached Result:", cached_res)
    print("  Notice that Turn 4 did NOT call the LLM because procedure is verified!")
