"""
Example 04: 3-Tier Memory in Action

Demonstrates Short-Term (Context), Long-Term (ACT-R SQLite), and Procedural Memory.
"""

from semantic_harness import Agent, AgentConfig

class Assistant(Agent):
    """Helpful assistant demonstrating 3-tier memory."""

if __name__ == "__main__":
    agent = Assistant(config=AgentConfig(model="gpt-4o-mini"))

    print("--- 1. Working with Long-Term Memory ---")
    agent.long_term.remember("kb_project", "Project Apollo is scheduled for Q4 launch", importance=0.9)
    agent.long_term.remember("kb_lead", "Sarah Connor is the technical lead for Apollo", importance=0.8)

    recalled = agent.long_term.search("Apollo")
    print(f"Recalled {len(recalled)} memories:")
    for r in recalled:
        print(f"  [{r.importance:.1f}] {r.content}")

    print("\n--- 2. Working with Short-Term Memory ---")
    agent.short_term.add("What is Project Apollo?", role="user")
    agent.short_term.add("It is scheduled for Q4 launch.", role="assistant")
    print("Working context:")
    print(agent.short_term.get_context_string())

    print("\n--- 3. Working with Procedural Memory ---")
    agent.procedural.cache("apollo_status", {"status": "GREEN", "quarter": "Q4"})
    hit = agent.procedural.lookup("apollo_status")
    print("Cached procedure:", hit.procedure)
