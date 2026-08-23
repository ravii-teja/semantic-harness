"""Semantic Harness visualization tools — Graph representations & learning curve renderers."""
from __future__ import annotations

import html
import json
from typing import Any, Sequence


class ProceduralGraphVisualizer:
    """
    Renders Semantic Procedural Memory topologies into Mermaid diagrams,
    interactive HTML graphs (vis-network), and learning curve dashboards.
    """

    @staticmethod
    def to_mermaid(
        procedures: Sequence[Any],
        title: str = "Semantic Procedural Memory Graph",
    ) -> str:
        """
        Render procedures into a Mermaid graph syntax string.

        Args:
            procedures: List of CachedProcedure items from SemanticProceduralMemory.
            title: Title for the diagram.

        Returns:
            Mermaid markdown string.
        """
        lines = [
            "```mermaid",
            "graph LR",
            f"    %% {title}",
            "    classDef intent fill:#2563eb,stroke:#1d4ed8,stroke-width:2px,color:#fff;",
            "    classDef reliable fill:#059669,stroke:#047857,stroke-width:2px,color:#fff;",
            "    classDef probationary fill:#d97706,stroke:#b45309,stroke-width:2px,color:#fff;",
            "    classDef unreliable fill:#dc2626,stroke:#b91c1c,stroke-width:2px,color:#fff;",
        ]

        if not procedures:
            lines.append('    Empty["[Semantic Procedural Memory Empty]"]')
            lines.append("```")
            return "\n".join(lines)

        for i, p in enumerate(procedures):
            intent_id = f"I_{p.intent_hash[:8]}"
            proc_id = f"P_{p.intent_hash[:8]}"

            # Safe sanitized labels
            intent_label = html.escape(p.intent_text).replace('"', "'")
            if len(intent_label) > 40:
                intent_label = intent_label[:37] + "..."

            conf_pct = int(p.confidence * 100)
            status_class = (
                "reliable" if p.is_reliable else ("probationary" if p.confidence >= 0.5 else "unreliable")
            )

            lines.append(f'    {intent_id}("{intent_label}"):::intent')
            lines.append(
                f'    {proc_id}["Procedure: {proc_id}<br/>Successes: {p.success_count} | κ: {conf_pct}%"]:::{status_class}'
            )
            lines.append(f"    {intent_id} ==>|κ = {p.confidence:.2f}| {proc_id}")

        lines.append("```")
        return "\n".join(lines)

    @staticmethod
    def to_interactive_html(
        procedures: Sequence[Any],
        title: str = "Semantic Procedural Memory Knowledge Graph",
        height: str = "600px",
    ) -> str:
        """
        Generate a self-contained interactive HTML page using vis-network.

        Args:
            procedures: List of CachedProcedure items from SemanticProceduralMemory.
            title: Dashboard title.
            height: Height of the graph canvas.

        Returns:
            HTML string.
        """
        nodes = []
        edges = []

        for p in procedures:
            intent_id = f"intent_{p.intent_hash}"
            proc_id = f"proc_{p.intent_hash}"

            # Intent Node
            nodes.append({
                "id": intent_id,
                "label": p.intent_text[:35] + ("..." if len(p.intent_text) > 35 else ""),
                "title": f"<b>Intent:</b> {html.escape(p.intent_text)}<br/><b>Hash:</b> {p.intent_hash}",
                "group": "intent",
                "color": {"background": "#2563eb", "border": "#1d4ed8"},
                "font": {"color": "#ffffff"},
                "shape": "box",
            })

            # Procedure Node
            status_color = "#059669" if p.is_reliable else ("#d97706" if p.confidence >= 0.5 else "#dc2626")
            nodes.append({
                "id": proc_id,
                "label": f"PROC ({int(p.confidence*100)}%)",
                "title": (
                    f"<b>Procedure Details:</b><br/>"
                    f"• Successes: {p.success_count}<br/>"
                    f"• Failures: {p.failure_count}<br/>"
                    f"• Confidence (κ): {p.confidence:.2%}<br/>"
                    f"• Reliable: {'Yes' if p.is_reliable else 'No'}"
                ),
                "group": "procedure",
                "color": {"background": status_color, "border": "#111827"},
                "font": {"color": "#ffffff"},
                "shape": "ellipse",
            })

            # Edge
            edges.append({
                "from": intent_id,
                "to": proc_id,
                "label": f"κ={p.confidence:.2f}",
                "arrows": "to",
                "width": max(1, int(p.confidence * 4)),
                "color": {"color": status_color},
            })

        nodes_json = json.dumps(nodes)
        edges_json = json.dumps(edges)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{html.escape(title)}</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: #0f172a;
            color: #f8fafc;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }}
        h1 {{ margin: 0; font-size: 20px; font-weight: 600; color: #38bdf8; }}
        .badge {{
            padding: 4px 10px;
            background: #1e293b;
            border-radius: 9999px;
            font-size: 13px;
            border: 1px solid #334155;
        }}
        #graph-container {{
            width: 100%;
            height: {height};
            border: 1px solid #334155;
            border-radius: 8px;
            background: #020617;
        }}
        .legend {{
            display: flex;
            gap: 16px;
            margin-top: 12px;
            font-size: 13px;
        }}
        .legend-item {{ display: flex; align-items: center; gap: 6px; }}
        .dot {{ width: 12px; height: 12px; border-radius: 50%; display: inline-block; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{html.escape(title)}</h1>
        <div class="badge">Total Procedures: <strong>{len(procedures)}</strong></div>
    </div>
    <div id="graph-container"></div>
    <div class="legend">
        <div class="legend-item"><span class="dot" style="background:#2563eb;"></span> Intent Node</div>
        <div class="legend-item"><span class="dot" style="background:#059669;"></span> Verified Reliable (κ ≥ 80%, N ≥ 3)</div>
        <div class="legend-item"><span class="dot" style="background:#d97706;"></span> Probationary (50% ≤ κ < 80%)</div>
        <div class="legend-item"><span class="dot" style="background:#dc2626;"></span> Low Confidence (κ < 50%)</div>
    </div>
    <script type="text/javascript">
        const nodes = new vis.DataSet({nodes_json});
        const edges = new vis.DataSet({edges_json});
        const container = document.getElementById('graph-container');
        const data = {{ nodes: nodes, edges: edges }};
        const options = {{
            nodes: {{ borderWidth: 2, font: {{ size: 14, face: 'monospace' }} }},
            edges: {{ font: {{ size: 12, align: 'middle', color: '#94a3b8' }}, smooth: {{ type: 'cubicBezier' }} }},
            physics: {{
                barnesHut: {{ gravitationalConstant: -3000, centralGravity: 0.3, springLength: 120 }},
                stabilization: {{ iterations: 150 }}
            }}
        }};
        const network = new vis.Network(container, data, options);
    </script>
</body>
</html>"""


def render_procedural_graph(memory: Any, format: str = "mermaid", **kwargs: Any) -> str:
    """
    Convenience function to render a SemanticProceduralMemory instance.

    Args:
        memory: SemanticProceduralMemory instance.
        format: 'mermaid' or 'html'.
        **kwargs: Extra arguments passed to visualizer.

    Returns:
        Rendered string output.
    """
    procedures = memory.get_all() if hasattr(memory, "get_all") else list(memory)
    if format.lower() == "html":
        return ProceduralGraphVisualizer.to_interactive_html(procedures, **kwargs)
    return ProceduralGraphVisualizer.to_mermaid(procedures, **kwargs)
