"""
Example 02: C2C Validation & Self-Correction Feedback Loop

Demonstrates how C2CValidator catches malformed structured outputs from 
small models and builds actionable retry prompts for self-correction.
"""

from pydantic import BaseModel, Field
from semantic_harness import C2CValidator

class UserProfile(BaseModel):
    user_id: int
    username: str
    email: str
    tags: list[str] = Field(default_factory=list)

if __name__ == "__main__":
    validator = C2CValidator()

    # Simulated malformed output from a small model (<0.5GB)
    malformed_output = {
        "user_id": "not_an_integer",
        "username": "alice",
        # 'email' field is missing
    }

    print("--- Validating Raw Output ---")
    result = validator.validate(malformed_output, UserProfile)
    
    if not result.valid:
        print(f"Validation failed with {len(result.errors)} errors:")
        for err in result.errors:
            print(f"  - {err}")
        
        print("\n--- Actionable Retry Prompt Generated for LLM ---")
        print(result.retry_prompt)
