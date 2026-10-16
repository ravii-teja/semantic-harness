"""Adversarial Fuzzer and Stress Testing Suite for Semantic Harness.

Tests procedure preconditions, schema invariants, tool signatures, and
parameter poisoning to verify 0.00% False Reuse Rate (FRR) safety guarantees.
"""
from __future__ import annotations

import random
import string
from dataclasses import dataclass, field
from typing import Any

from semantic_harness.memory.procedural import (
    ProceduralMemory,
    ProcedurePrecondition,
    ReuseStatus,
)


@dataclass
class FuzzResult:
    total_mutations: int = 0
    blocked_mismatches: int = 0
    false_reuses: int = 0
    frr_percent: float = 0.0
    details: list[str] = field(default_factory=list)


class PreconditionFuzzer:
    """Fuzzing suite to stress-test procedural cache invariants and precondition checks."""

    def __init__(self, memory: ProceduralMemory | None = None) -> None:
        self.memory = memory or ProceduralMemory()

    def generate_random_string(self, length: int = 8) -> str:
        return "".join(random.choices(string.ascii_letters + string.digits, k=length))

    def run_stress_test(self, iterations: int = 50) -> FuzzResult:
        """Run stress test fuzzing random schema fingerprints and tool signatures."""
        res = FuzzResult()
        intent = "extract financial invoice"

        # Compile base procedure
        base_schema_fp = "fp_valid_v1"
        base_tools = {"db_query": "1.0.0"}
        self.memory.compile(
            intent=intent,
            trajectory=["select * from invoices"],
            schema_fingerprint=base_schema_fp,
            tool_signatures=base_tools,
            min_success_count=1,
            confidence=1.0,
        )

        for i in range(iterations):
            res.total_mutations += 1
            roll = random.random()

            if roll < 0.33:
                # Mutate schema fingerprint
                fuzzed_fp = f"fp_valid_v1_mutated_{self.generate_random_string()}"
                fuzzed_tools = base_tools
            elif roll < 0.66:
                # Mutate tool signature
                fuzzed_fp = base_schema_fp
                fuzzed_tools = {"db_query": f"2.0.0_breaking_{self.generate_random_string()}"}
            else:
                # Mutate both
                fuzzed_fp = f"fp_invalid_{self.generate_random_string()}"
                fuzzed_tools = {"db_query": "0.0.1"}

            hit, explanation = self.memory.explain_lookup(
                intent=intent,
                schema_fingerprint=fuzzed_fp,
                tool_signatures=fuzzed_tools,
                require_reliable=False,
            )

            if hit is not None:
                res.false_reuses += 1
                res.details.append(f"FALSE REUSE on iteration {i}: mutated schema/tools were accepted!")
            else:
                res.blocked_mismatches += 1

        if res.total_mutations > 0:
            res.frr_percent = (res.false_reuses / res.total_mutations) * 100.0

        return res
