"""
Command Line Interface (CLI) for Semantic Harness.

Provides operators with diagnostic, cache inspection, hardware detection,
and metrics exposition commands.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Sequence

from semantic_harness.__version__ import __version__
from semantic_harness.core.hardware import HardwareDetector
from semantic_harness.memory.procedural import ProceduralMemory
from semantic_harness.telemetry.metrics import get_metrics_collector


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for the semantic-harness CLI."""
    parser = argparse.ArgumentParser(
        prog="semantic-harness",
        description="Cognitive middleware and procedural acceleration runtime for autonomous AI agents.",
    )
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"semantic-harness {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Sub-command to execute")

    # Subcommand: hardware
    subparsers.add_parser(
        "hardware",
        help="Inspect host hardware accelerators, memory, and recommended local model",
    )

    # Subcommand: cache
    cache_parser = subparsers.add_parser("cache", help="Inspect and manage procedural cache files")
    cache_subparsers = cache_parser.add_subparsers(dest="cache_command")

    # cache inspect
    inspect_parser = cache_subparsers.add_parser(
        "inspect", help="Inspect procedural memory cache file"
    )
    inspect_parser.add_argument("path", help="Path to procedural cache JSON file")

    # cache export
    export_parser = cache_subparsers.add_parser(
        "export", help="Export procedural memory cache to human-readable JSON"
    )
    export_parser.add_argument("path", help="Path to procedural cache JSON file")
    export_parser.add_argument(
        "--output", "-o", default=None, help="Target file path (defaults to stdout)"
    )

    # Subcommand: metrics
    subparsers.add_parser("metrics", help="Export Prometheus metrics in text format")

    # Subcommand: dashboard
    dash_parser = subparsers.add_parser("dashboard", help="Launch live enterprise observability web dashboard")
    dash_parser.add_argument("--port", type=int, default=8080, help="Port to bind dashboard server (default: 8080)")
    dash_parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    dash_parser.add_argument("--open", action="store_true", help="Automatically open dashboard in web browser")

    # Subcommand: roi
    roi_parser = subparsers.add_parser("roi", help="Calculate token cost savings and procedural compilation ROI")
    roi_parser.add_argument("--spend", type=float, default=25000.0, help="Current monthly LLM spend in USD (default: 25000)")
    roi_parser.add_argument("--model", type=str, default="gpt-4o", choices=["gpt-4o", "claude-3-5-sonnet", "llama-3-3-70b", "deepseek-v3"], help="Primary model tier")
    roi_parser.add_argument("--repetition", type=float, default=0.45, help="Estimated workflow repetition / overlap rate (0.0 to 1.0, default: 0.45)")
    roi_parser.add_argument("--turns", type=int, default=5, help="Average agent turns per task (default: 5)")

    return parser


def cmd_hardware() -> int:
    """Execute hardware detection command."""
    profile = HardwareDetector.detect()
    print("=== Semantic Harness Hardware Profile ===")
    print(f"Accelerator:           {profile.accelerator.value.upper()}")
    print(f"Device Name:           {profile.device_name}")
    print(f"CPU Cores:             {profile.cpu_cores}")
    print(f"Total Memory (GB):     {profile.total_memory_gb:.1f}")
    print(f"Available Memory (GB): {profile.available_memory_gb:.1f}")
    print(f"Recommended Model:     {profile.recommended_model}")
    print(f"Recommended Provider:  {profile.recommended_provider}")

    tf_meta = profile.metadata.get("tensor_frameworks", {})
    torch_info = tf_meta.get("torch", {})
    tf_info = tf_meta.get("tensorflow", {})
    if torch_info.get("available"):
        accels = []
        if torch_info.get("cuda"):
            accels.append(f"CUDA (x{torch_info.get('cuda_count')})")
        if torch_info.get("mps"):
            accels.append("Apple MPS")
        if torch_info.get("rocm"):
            accels.append("AMD ROCm")
        accel_str = ", ".join(accels) if accels else "CPU"
        print(f"PyTorch:               {torch_info.get('version')} [{accel_str}]")
    else:
        print("PyTorch:               Not Installed")

    if tf_info.get("available"):
        gpu_str = f"GPU (x{tf_info.get('gpu_count')})" if tf_info.get("gpu") else "CPU"
        print(f"TensorFlow:            {tf_info.get('version')} [{gpu_str}]")
    else:
        print("TensorFlow:            Not Installed")
    return 0


def cmd_cache_inspect(path: str) -> int:
    """Inspect procedural memory file."""
    if not os.path.exists(path):
        print(f"Error: Cache file not found: {path}", file=sys.stderr)
        return 1

    memory = ProceduralMemory(persist_path=path)
    entries = memory.get_all()

    print(f"=== Procedural Memory Cache: {path} ===")
    print(f"Total compiled procedures: {len(entries)}")
    for idx, proc in enumerate(entries, 1):
        fp = proc.preconditions.schema_fingerprint or "None"
        print(f"[{idx}] Intent: {proc.intent_text}")
        print(f"    Hits: {proc.hit_count} | Successes: {proc.success_count} | Failures: {proc.failure_count}")
        print(f"    Schema FP:  {fp}")
        if proc.preconditions.tool_signatures:
            print(f"    Tools:      {list(proc.preconditions.tool_signatures.keys())}")
    return 0


def cmd_cache_export(path: str, output: str | None) -> int:
    """Export procedural cache entries."""
    if not os.path.exists(path):
        print(f"Error: Cache file not found: {path}", file=sys.stderr)
        return 1

    memory = ProceduralMemory(persist_path=path)
    entries = memory.get_all()
    serializable = [
        {
            "intent_hash": p.intent_hash,
            "intent_text": p.intent_text,
            "procedure": (
                p.procedure
                if isinstance(p.procedure, (dict, list, str, int, float, bool))
                else str(p.procedure)
            ),
            "parameters": p.parameters,
            "preconditions": {
                "schema_fingerprint": p.preconditions.schema_fingerprint,
                "tool_signatures": p.preconditions.tool_signatures,
                "env_keys": p.preconditions.env_keys,
                "min_confidence": p.preconditions.min_confidence,
                "min_success_count": p.preconditions.min_success_count,
            },
            "success_count": p.success_count,
            "failure_count": p.failure_count,
            "hit_count": p.hit_count,
            "created_at": p.created_at,
            "last_used": p.last_used,
        }
        for p in entries
    ]

    dumped = json.dumps(serializable, indent=2)
    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(dumped)
        print(f"Exported {len(serializable)} entries to {output}")
    else:
        print(dumped)
    return 0


def cmd_metrics() -> int:
    """Export Prometheus metrics to stdout."""
    collector = get_metrics_collector()
    print(collector.export_prometheus(), end="")
    return 0


def cmd_dashboard(port: int = 8080, host: str = "127.0.0.1", open_browser: bool = False) -> int:
    """Launch live enterprise observability web dashboard."""
    import time
    from semantic_harness.visualization.dashboard import serve_dashboard
    server = serve_dashboard(port=port, host=host, open_browser=open_browser)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping dashboard server...")
        server.stop()
    return 0


def cmd_roi(spend: float, model: str, repetition: float, turns: int) -> int:
    """Calculate and display projected procedural ROI and token savings."""
    rates = {
        "gpt-4o": {"blended": 6.25, "latency": 6.8},
        "claude-3-5-sonnet": {"blended": 9.00, "latency": 7.2},
        "llama-3-3-70b": {"blended": 0.80, "latency": 2.1},
        "deepseek-v3": {"blended": 0.21, "latency": 4.5},
    }
    info = rates.get(model, rates["gpt-4o"])
    net_savings_ratio = repetition * 0.958
    monthly_savings = spend * net_savings_ratio
    annual_savings = monthly_savings * 12.0
    tokens_billed = (spend / info["blended"]) * 1_000_000
    tokens_saved = tokens_billed * repetition
    turns_saved = tokens_saved / (280.0 * max(1, turns * 0.5))
    hours_saved = (turns_saved * info["latency"]) / 3600.0
    break_even = 1.0 + (1.0 / turns)

    print("================================================================")
    print("  SEMANTIC HARNESS — PROCEDURAL COMPILATION TOKEN ROI REPORT    ")
    print("================================================================")
    print(f"  Monthly LLM Spend:        ${spend:,.2f} ({model})")
    print(f"  Task Overlap Rate:        {repetition * 100:.1f}%")
    print(f"  Avg Turns Per Task:       {turns} turns")
    print("----------------------------------------------------------------")
    print(f"  PROJECTED MONTHLY SAVINGS: ${monthly_savings:,.2f} / month")
    print(f"  PROJECTED ANNUAL SAVINGS:  ${annual_savings:,.2f} / year")
    print(f"  Tokens Bypassed / Month:  {tokens_saved:,.0f} tokens")
    print(f"  Latency Saved / Month:    {hours_saved:,.1f} developer hours")
    print(f"  Break-Even Threshold (r*): Turn {break_even:.1f} (Zero-token warm paths)")
    print("================================================================")
    return 0


def main(args: Sequence[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    parsed = parser.parse_args(args)

    if not parsed.command:
        parser.print_help()
        return 0

    if parsed.command == "hardware":
        return cmd_hardware()
    elif parsed.command == "cache":
        if parsed.cache_command == "inspect":
            return cmd_cache_inspect(parsed.path)
        elif parsed.cache_command == "export":
            return cmd_cache_export(parsed.path, parsed.output)
        else:
            print("Error: Specify a cache subcommand ('inspect' or 'export')", file=sys.stderr)
            return 1
    elif parsed.command == "metrics":
        return cmd_metrics()
    elif parsed.command == "dashboard":
        return cmd_dashboard(port=parsed.port, host=parsed.host, open_browser=parsed.open)
    elif parsed.command == "roi":
        return cmd_roi(
            spend=parsed.spend,
            model=parsed.model,
            repetition=parsed.repetition,
            turns=parsed.turns,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
