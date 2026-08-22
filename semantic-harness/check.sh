#!/bin/bash
set -e

echo "==================================="
echo " System Checks: Semantic-Harness"
echo "==================================="

echo ">>> 1. Running Python Core Unit Tests..."
cd python
pytest -v

echo ">>> 2. Verifying Runnable Examples..."
PYTHONPATH=. python3 examples/01_middleware_quickstart.py
PYTHONPATH=. python3 examples/02_c2c_self_correction.py
PYTHONPATH=. python3 examples/03_procedural_cache_bench.py
PYTHONPATH=. python3 examples/04_agent_memory_tiers.py
PYTHONPATH=. python3 examples/05_turboquant_fuzzy_procedural_cache.py

echo "==================================="
echo " ✅ All 78 Tests & 5 Examples Passed!"
echo "==================================="
