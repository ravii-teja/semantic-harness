"""Interactive Knowledge Graph & TurboQuant Visualizer.

Provides monochrome (black and white minimalist) force-directed graph rendering
with clickable nodes and inspector panels, along with TurboQuant bit-level inspection.
"""
from __future__ import annotations

import html
import json
from typing import Any, Sequence


class KnowledgeGraphVisualizer:
    """Renders Knowledge Graph topologies into interactive black & white force-directed web visualizations."""

    @staticmethod
    def to_interactive_html(
        entities: Sequence[Any],
        triplets: Sequence[Any],
        title: str = "Relational Knowledge Graph",
        height: str = "700px",
        turbo_quant_details: list[dict[str, Any]] | None = None,
    ) -> str:
        """Render a minimalist monochrome (white background, black text/edges/nodes) interactive graph.

        Clicking on any node opens a floating detail card explaining the node's properties,
        connected edges, and associated TurboQuant representations.
        """
        nodes_data = []
        edges_data = []

        # Build nodes
        for e in entities:
            e_id = getattr(e, "name", str(e))
            e_type = getattr(e, "entity_type", "entity")
            props = getattr(e, "properties", {})

            nodes_data.append({
                "id": e_id,
                "label": e_id,
                "title": f"Click to view details for {e_id}",
                "shape": "dot",
                "size": 18,
                "color": {
                    "background": "#ffffff",
                    "border": "#000000",
                    "highlight": {"background": "#000000", "border": "#000000"},
                    "hover": {"background": "#e5e5e5", "border": "#000000"}
                },
                "font": {"color": "#000000", "face": "system-ui, -apple-system, sans-serif", "size": 14, "bold": True},
                "entityType": e_type,
                "properties": props,
            })

        # Build edges
        for idx, t in enumerate(triplets):
            edges_data.append({
                "id": f"e_{idx}",
                "from": t.source_name,
                "to": t.target_name,
                "label": t.predicate,
                "confidence": getattr(t, "confidence", 1.0),
                "properties": getattr(t, "properties", {}),
                "arrows": "to",
                "color": {"color": "#000000", "highlight": "#000000", "hover": "#555555"},
                "font": {"color": "#444444", "size": 11, "strokeWidth": 0, "align": "middle", "background": "#ffffff"},
                "width": 1.5,
            })

        nodes_json = json.dumps(nodes_data)
        edges_json = json.dumps(edges_data)
        tq_json = json.dumps(turbo_quant_details or [])

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{html.escape(title)}</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 24px;
            background: #ffffff;
            color: #000000;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #000000;
            padding-bottom: 12px;
            margin-bottom: 20px;
        }}
        h1 {{
            margin: 0;
            font-size: 22px;
            font-weight: 700;
            letter-spacing: -0.5px;
        }}
        .btn-group {{
            display: flex;
            gap: 8px;
        }}
        button {{
            background: #ffffff;
            color: #000000;
            border: 1.5px solid #000000;
            padding: 6px 14px;
            font-size: 13px;
            font-weight: 600;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.15s ease;
        }}
        button:hover {{
            background: #000000;
            color: #ffffff;
        }}
        .workspace {{
            display: flex;
            gap: 20px;
            position: relative;
        }}
        #graph-container {{
            flex: 1;
            height: {height};
            border: 2px solid #000000;
            background: #ffffff;
            border-radius: 4px;
        }}
        #inspector {{
            width: 360px;
            border: 2px solid #000000;
            background: #ffffff;
            border-radius: 4px;
            padding: 16px;
            display: flex;
            flex-direction: column;
            overflow-y: auto;
            max-height: {height};
        }}
        .inspector-title {{
            font-size: 16px;
            font-weight: 700;
            border-bottom: 1px solid #000000;
            padding-bottom: 8px;
            margin-bottom: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .property-row {{
            margin-bottom: 10px;
            font-size: 13px;
        }}
        .prop-label {{
            font-weight: 600;
            text-transform: uppercase;
            font-size: 11px;
            color: #666666;
            margin-bottom: 2px;
        }}
        .prop-value {{
            font-family: ui-monospace, Menlo, Monaco, monospace;
            background: #f5f5f5;
            padding: 4px 6px;
            border-radius: 3px;
            word-break: break-all;
        }}
        .tq-box {{
            margin-top: 16px;
            border-top: 1px dashed #000000;
            padding-top: 12px;
        }}
        .bits-preview {{
            font-family: monospace;
            font-size: 11px;
            background: #f5f5f5;
            padding: 8px;
            letter-spacing: 1px;
            word-break: break-all;
            max-height: 120px;
            overflow-y: auto;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>{html.escape(title)}</h1>
            <div style="font-size: 12px; color: #555555; margin-top: 4px;">Minimalist Black & White Knowledge Graph with TurboQuant Inspection</div>
        </div>
        <div class="btn-group">
            <button onclick="exportData('json')">Export JSON</button>
            <button onclick="network.fit()">Reset View</button>
        </div>
    </div>

    <div class="workspace">
        <div id="graph-container"></div>
        <div id="inspector">
            <div class="inspector-title">
                <span id="inspect-name">Select a Node</span>
                <span id="inspect-type" style="font-size: 11px; font-weight: normal; color: #666;"></span>
            </div>
            <div id="inspect-body">
                <p style="color: #666666; font-size: 13px;">Click on any node or edge to inspect its relational attributes and quantized vector features.</p>
            </div>
        </div>
    </div>

    <script type="text/javascript">
        const rawNodes = {nodes_json};
        const rawEdges = {edges_json};
        const turboQuantData = {tq_json};

        const nodes = new vis.DataSet(rawNodes);
        const edges = new vis.DataSet(rawEdges);
        const container = document.getElementById('graph-container');

        const data = {{ nodes: nodes, edges: edges }};
        const options = {{
            nodes: {{
                borderWidth: 2,
                shadow: false
            }},
            edges: {{
                arrows: {{ to: {{ enabled: true, scaleFactor: 0.8 }} }},
                smooth: {{ type: 'continuous' }}
            }},
            physics: {{
                barnesHut: {{
                    gravitationalConstant: -4000,
                    centralGravity: 0.3,
                    springLength: 140,
                    springConstant: 0.04
                }},
                stabilization: {{ iterations: 200 }}
            }},
            interaction: {{
                hover: true,
                tooltipDelay: 100
            }}
        }};

        const network = new vis.Network(container, data, options);

        network.on("click", function (params) {{
            if (params.nodes.length > 0) {{
                const nodeId = params.nodes[0];
                const node = nodes.get(nodeId);
                showNodeInspector(node);
            }} else if (params.edges.length > 0) {{
                const edgeId = params.edges[0];
                const edge = edges.get(edgeId);
                showEdgeInspector(edge);
            }}
        }});

        function showNodeInspector(node) {{
            document.getElementById('inspect-name').innerText = node.label;
            document.getElementById('inspect-type').innerText = '[' + (node.entityType || 'entity') + ']';

            // Find connected edges
            const connectedEdges = edges.get({{
                filter: function (item) {{
                    return item.from === node.id || item.to === node.id;
                }}
            }});

            let htmlContent = '<div class="property-row"><div class="prop-label">Entity ID</div><div class="prop-value">' + node.id + '</div></div>';
            
            if (node.properties && Object.keys(node.properties).length > 0) {{
                htmlContent += '<div class="property-row"><div class="prop-label">Properties</div><div class="prop-value">' + JSON.stringify(node.properties, null, 2) + '</div></div>';
            }}

            htmlContent += '<div class="property-row"><div class="prop-label">Connected Relations (' + connectedEdges.length + ')</div><ul style="padding-left: 18px; margin: 6px 0; font-size: 13px;">';
            connectedEdges.forEach(function(e) {{
                const direction = e.from === node.id ? '--> ' + e.to : '<-- ' + e.from;
                htmlContent += '<li><strong>' + e.label + '</strong> ' + direction + '</li>';
            }});
            htmlContent += '</ul></div>';

            // TurboQuant details if available
            const tq = turboQuantData.find(item => item.id === node.id);
            if (tq) {{
                htmlContent += '<div class="tq-box">';
                htmlContent += '<div class="prop-label">TurboQuant Vector Representation</div>';
                htmlContent += '<div class="property-row"><div class="prop-label">Dimension / Padded</div><div class="prop-value">' + tq.dim + ' / ' + tq.padded_dim + '</div></div>';
                htmlContent += '<div class="property-row"><div class="prop-label">Compression Ratio</div><div class="prop-value">' + tq.compression_ratio + 'x (Memory: ' + tq.byte_size + ' bytes)</div></div>';
                if (tq.binary_string) {{
                    htmlContent += '<div class="prop-label">1-Bit Polar Quantized Bitstream</div><div class="bits-preview">' + tq.binary_string + '</div>';
                }}
                htmlContent += '</div>';
            }}

            document.getElementById('inspect-body').innerHTML = htmlContent;
        }}

        function showEdgeInspector(edge) {{
            document.getElementById('inspect-name').innerText = edge.label;
            document.getElementById('inspect-type').innerText = '[relation]';

            let htmlContent = '<div class="property-row"><div class="prop-label">Source Node</div><div class="prop-value">' + edge.from + '</div></div>';
            htmlContent += '<div class="property-row"><div class="prop-label">Predicate</div><div class="prop-value">' + edge.label + '</div></div>';
            htmlContent += '<div class="property-row"><div class="prop-label">Target Node</div><div class="prop-value">' + edge.to + '</div></div>';
            htmlContent += '<div class="property-row"><div class="prop-label">Confidence Score</div><div class="prop-value">' + (edge.confidence || 1.0) + '</div></div>';

            document.getElementById('inspect-body').innerHTML = htmlContent;
        }}

        function exportData(format) {{
            const exportObj = {{
                nodes: rawNodes,
                edges: rawEdges,
                turboQuant: turboQuantData
            }};
            const blob = new Blob([JSON.stringify(exportObj, null, 2)], {{ type: 'application/json' }});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'knowledge_graph_export.json';
            a.click();
            URL.revokeObjectURL(url);
        }}
    </script>
</body>
</html>"""
