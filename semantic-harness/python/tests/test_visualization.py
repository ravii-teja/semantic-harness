"""Unit tests for Semantic Harness visualization module."""
import pytest
from semantic_harness.memory.procedural import SemanticProceduralMemory
from semantic_harness.visualization import (
    ProceduralGraphVisualizer,
    render_procedural_graph,
)


def test_empty_procedural_graph_visualization():
    mem = SemanticProceduralMemory()
    mermaid_out = mem.to_mermaid()
    assert "```mermaid" in mermaid_out
    assert "graph LR" in mermaid_out
    assert "Empty" in mermaid_out

    html_out = mem.to_interactive_html()
    assert "<!DOCTYPE html>" in html_out
    assert "vis-network" in html_out
    assert "Total Procedures: <strong>0</strong>" in html_out


def test_populated_procedural_graph_visualization():
    mem = SemanticProceduralMemory(vector_dim=64, enable_fuzzy_search=True)
    mem.cache("calculate total sales for Q3", procedure={"sql": "SELECT SUM(amount) FROM sales WHERE quarter = 'Q3'"})
    mem.cache("classify incoming support ticket", procedure={"action": "triage_priority"})

    for _ in range(5):
        mem.record_success("calculate total sales for Q3")

    mem.record_success("classify incoming support ticket")
    mem.record_failure("classify incoming support ticket")

    # Test Mermaid
    mermaid_out = mem.to_mermaid()
    assert "```mermaid" in mermaid_out
    assert "calculate total sales for q3" in mermaid_out
    assert "classify incoming support ticket" in mermaid_out
    assert "reliable" in mermaid_out
    assert "κ = 1.00" in mermaid_out

    # Test Interactive HTML
    html_out = mem.to_interactive_html()
    assert "<!DOCTYPE html>" in html_out
    assert "vis.DataSet" in html_out
    assert "calculate total sales for q3" in html_out
    assert "Total Procedures: <strong>2</strong>" in html_out

    # Test top-level render_procedural_graph
    mermaid_fn = render_procedural_graph(mem, format="mermaid")
    assert "```mermaid" in mermaid_fn

    html_fn = render_procedural_graph(mem, format="html")
    assert "<!DOCTYPE html>" in html_fn
