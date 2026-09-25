/**
 * Knowledge Graph Memory & Subgraph Traversal Layer in TypeScript.
 */

export interface GraphEntity {
  id: string;
  name: string;
  entityType: string;
  properties: Record<string, unknown>;
  createdAt: number;
}

export interface GraphTriplet {
  sourceName: string;
  predicate: string;
  targetName: string;
  confidence: number;
  properties: Record<string, unknown>;
  timestamp: number;
}

export class GraphMemory {
  private readonly entities = new Map<string, GraphEntity>();
  private readonly triplets: GraphTriplet[] = [];

  public addEntity(name: string, entityType = "entity", properties: Record<string, unknown> = {}): GraphEntity {
    const cleanName = name.trim();
    const id = cleanName.toLowerCase().replace(/\s+/g, "_");
    const entity: GraphEntity = {
      id,
      name: cleanName,
      entityType,
      properties,
      createdAt: Date.now(),
    };
    this.entities.set(cleanName.toLowerCase(), entity);
    return entity;
  }

  public addTriplet(
    source: string,
    predicate: string,
    target: string,
    confidence = 1.0,
    properties: Record<string, unknown> = {}
  ): GraphTriplet {
    const s = source.trim();
    const p = predicate.trim().toLowerCase().replace(/\s+/g, "_");
    const t = target.trim();

    this.addEntity(s);
    this.addEntity(t);

    const triplet: GraphTriplet = {
      sourceName: s,
      predicate: p,
      targetName: t,
      confidence,
      properties,
      timestamp: Date.now(),
    };

    // Update existing or append
    const idx = this.triplets.findIndex(
      (item) => item.sourceName === s && item.predicate === p && item.targetName === t
    );
    if (idx >= 0) {
      this.triplets[idx] = triplet;
    } else {
      this.triplets.push(triplet);
    }
    return triplet;
  }

  public getRelationsFor(entityName: string): GraphTriplet[] {
    const name = entityName.trim().toLowerCase();
    return this.triplets.filter(
      (t) => t.sourceName.toLowerCase() === name || t.targetName.toLowerCase() === name
    );
  }

  public traverseSubgraph(rootEntities: string[], maxHops = 2, maxNodes = 30): GraphTriplet[] {
    const visited = new Set<string>();
    let frontier = new Set<string>(rootEntities.map((e) => e.trim().toLowerCase()).filter(Boolean));
    const result: GraphTriplet[] = [];
    const seenTriplets = new Set<string>();

    for (let hop = 0; hop < maxHops; hop++) {
      if (frontier.size === 0 || visited.size >= maxNodes) break;
      const nextFrontier = new Set<string>();

      for (const entity of frontier) {
        if (visited.has(entity)) continue;
        visited.add(entity);

        const rels = this.getRelationsFor(entity);
        for (const r of rels) {
          const key = `${r.sourceName}::${r.predicate}::${r.targetName}`;
          if (!seenTriplets.has(key)) {
            seenTriplets.add(key);
            result.push(r);
          }
          const sLower = r.sourceName.toLowerCase();
          const tLower = r.targetName.toLowerCase();
          if (!visited.has(sLower)) nextFrontier.add(sLower);
          if (!visited.has(tLower)) nextFrontier.add(tLower);
        }
      }
      frontier = nextFrontier;
    }

    return result;
  }

  public renderSubgraphContext(rootEntities: string[], maxHops = 2): string {
    const triplets = this.traverseSubgraph(rootEntities, maxHops);
    if (triplets.length === 0) return "";

    const lines = ["### Relational Knowledge Graph Context:"];
    for (const t of triplets) {
      lines.push(`- (${t.sourceName}) --[${t.predicate}]--> (${t.targetName}) [conf: ${t.confidence.toFixed(2)}]`);
    }
    return lines.join("\n");
  }

  public extractTripletsFromText(text: string): GraphTriplet[] {
    const extracted: GraphTriplet[] = [];
    const regex = /\(([^,\)]+)\)\s*(?:--\[([^\]]+)\]-->|,)\s*\(([^,\)]+)\)/g;
    let match: RegExpExecArray | null;
    while ((match = regex.exec(text)) !== null) {
      const s = match[1]?.trim();
      const p = match[2]?.trim();
      const o = match[3]?.trim();
      if (s && p && o) {
        extracted.push(this.addTriplet(s, p, o));
      }
    }
    return extracted;
  }

  public getAllEntities(): GraphEntity[] {
    return Array.from(this.entities.values());
  }

  public getAllTriplets(): GraphTriplet[] {
    return [...this.triplets];
  }

  public renderInteractiveHtml(title = "Relational Knowledge Graph"): string {
    const rawNodes = this.getAllEntities().map((e) => ({
      id: e.name,
      label: e.name,
      title: `Entity: ${e.name} (${e.entityType})`,
      shape: "dot",
      size: 18,
      color: { background: "#ffffff", border: "#000000", highlight: { background: "#000000", border: "#000000" } },
      font: { color: "#000000", face: "system-ui, sans-serif", size: 14, bold: true },
      entityType: e.entityType,
      properties: e.properties,
    }));

    const rawEdges = this.getAllTriplets().map((t, i) => ({
      id: `e_${i}`,
      from: t.sourceName,
      to: t.targetName,
      label: t.predicate,
      confidence: t.confidence,
      arrows: "to",
      color: { color: "#000000", highlight: "#000000" },
      font: { color: "#444444", size: 11, align: "middle", background: "#ffffff" },
      width: 1.5,
    }));

    const nodesJson = JSON.stringify(rawNodes);
    const edgesJson = JSON.stringify(rawEdges);

    return `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>${title}</title>
  <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <style>
    body { font-family: system-ui, sans-serif; margin: 0; padding: 20px; background: #fff; color: #000; }
    .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 20px; }
    #container { height: 650px; border: 2px solid #000; }
  </style>
</head>
<body>
  <div class="header">
    <h2>${title}</h2>
  </div>
  <div id="container"></div>
  <script>
    const data = { nodes: new vis.DataSet(${nodesJson}), edges: new vis.DataSet(${edgesJson}) };
    const options = { physics: { barnesHut: { gravitationalConstant: -3500, springLength: 130 } } };
    new vis.Network(document.getElementById('container'), data, options);
  </script>
</body>
</html>`;
  }
}
