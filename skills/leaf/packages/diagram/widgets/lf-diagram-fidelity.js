/* lf-diagram's render check: does the drawing hold what the source says?
 *
 * Beautiful Mermaid's parsers are total. A statement they cannot read still gets a
 * reading — the leading word becomes a node, the rest of the line is dropped — so a source
 * the renderer only partly understands draws a plausible, wrong diagram and reports
 * nothing. Official Mermaid's grammars are strict, and both libraries describe what they
 * found: Mermaid in its diagram database, Beautiful Mermaid in the `data-*` attributes of
 * the SVG it drew. This module reads both into one shape and lists where they differ.
 *
 * No Mermaid grammar lives here, and none should be added: a divergence this misses is
 * answered by reading more of what either library already reports. What does live here is
 * the mapping between the two vocabularies — pseudo-state ids, ER ids, label markup,
 * shape names. Both libraries are pinned in scripts/vendor.py and neither reading is a
 * documented API, so moving a pin is what can break the mapping, and the diagram cases in
 * tests/test_render_gate.py are what says so.
 *
 * Only the render gate runs this (runtime/render-check.js), which is why it may import
 * 2.9MB of Mermaid. */

/* Leaf's palette reaches a diagram as `var(--token)` inside classDef, style and
 * linkStyle, and Mermaid's flowchart grammar has no CSS functions in a style value. Mermaid
 * only reads here, so a colour literal stands in for the token. */
const TOKEN = /var\(--[\w-]+\)/g;

const words = (value) =>
  String(value ?? "")
    .replace(TOKEN, "#000")
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/\\n/g, " ")
    // Beautiful Mermaid turns **x** into <b>x</b>; Mermaid keeps the asterisks.
    .replace(/<\/?[a-z][^>]*>/gi, "")
    .replace(/\*\*/g, "")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ")
    .trim();

const PSEUDO_STATE = "[*]";

/* One spelling per node and per edge, shared by both readings: it is what they are
 * compared on and what the author is shown. */
const nodeItem = (id, label, shape) =>
  `${id} "${words(label)}"` + (shape ? ` (${shape})` : "");
const edgeItem = (from, to, label) =>
  `${from} -> ${to}` + (words(label) ? ` "${words(label)}"` : "");

/* Mermaid's shape names against the ones Beautiful Mermaid writes in `data-shape`. A shape
 * with no entry is one Beautiful Mermaid has no drawing for, so it keeps Mermaid's name
 * and the comparison reports it. */
const DRAWN_SHAPE = {
  squareRect: "rectangle",
  rect: "rounded",
  roundedRect: "rounded",
  stadium: "stadium",
  subroutine: "subroutine",
  cylinder: "cylinder",
  circle: "circle",
  doublecircle: "doublecircle",
  odd: "asymmetric",
  diamond: "diamond",
  hexagon: "hexagon",
  trapezoid: "trapezoid",
  inv_trapezoid: "trapezoid-alt",
};

const sourceReading = ({ db, type }) => {
  const reading = { nodes: [], groups: [], edges: [], counts: {} };
  // Mermaid reads an accessible title and description; this renderer draws neither.
  if (db.getAccTitle?.() || db.getAccDescription?.())
    reading.counts["accessible titles"] = 1;

  if (typeof db.getData === "function") {
    // Flowchart, state, class and ER diagrams share Mermaid's unified layout data.
    const data = db.getData();
    const shaped = type !== "er" && !/class/i.test(type);
    const names = new Map();
    for (const node of data.nodes) {
      const pseudo = /^state(Start|End)$/.test(node.shape ?? "");
      const id = pseudo ? PSEUDO_STATE : type === "er" ? words(node.label) : node.id;
      names.set(node.id, id);
      if (pseudo) continue;
      // A group's id is never drawn, and Mermaid invents one for `subgraph My Group`.
      if (node.isGroup) reading.groups.push(words(node.label));
      else
        reading.nodes.push(
          nodeItem(id, node.label, shaped && (DRAWN_SHAPE[node.shape] ?? node.shape)),
        );
    }
    for (const edge of data.edges)
      reading.edges.push(
        edgeItem(
          names.get(edge.start) ?? edge.start,
          names.get(edge.end) ?? edge.end,
          edge.label,
        ),
      );
    if (/class/i.test(type))
      reading.counts.members = [...db.getClasses().values()].reduce(
        (sum, entry) => sum + entry.members.length + entry.methods.length,
        0,
      );
    if (type === "er")
      reading.counts.attributes = [...db.getEntities().values()].reduce(
        (sum, entity) => sum + entity.attributes.length,
        0,
      );
    return reading;
  }

  if (type === "sequence") {
    const kind = db.LINETYPE;
    const known = (kinds) => new Set(kinds.filter((value) => value !== undefined));
    const arrows = known([
      kind.SOLID,
      kind.DOTTED,
      kind.SOLID_CROSS,
      kind.DOTTED_CROSS,
      kind.SOLID_OPEN,
      kind.DOTTED_OPEN,
      kind.SOLID_POINT,
      kind.DOTTED_POINT,
      kind.BIDIRECTIONAL_SOLID,
      kind.BIDIRECTIONAL_DOTTED,
    ]);
    const blocks = known([
      kind.LOOP_START,
      kind.ALT_START,
      kind.OPT_START,
      kind.PAR_START,
      kind.CRITICAL_START,
      kind.BREAK_START,
      kind.RECT_START,
    ]);
    for (const [id, actor] of db.getActors())
      reading.nodes.push(nodeItem(id, actor.description));
    Object.assign(reading.counts, {
      notes: 0,
      blocks: 0,
      "numbered messages": 0,
      boxes: db.getBoxes().length,
    });
    for (const message of db.getMessages())
      if (arrows.has(message.type))
        reading.edges.push(edgeItem(message.from, message.to, message.message));
      else if (message.type === kind.NOTE) reading.counts.notes++;
      else if (blocks.has(message.type)) reading.counts.blocks++;
      else if (message.type === kind.AUTONUMBER)
        reading.counts["numbered messages"] = 1;
    return reading;
  }

  if (type === "xychart") {
    reading.counts.values = db
      .getXYChartData()
      .plots.reduce((sum, plot) => sum + plot.data.length, 0);
    return reading;
  }

  throw new Error(`Leaf diagrams do not draw Mermaid's ${type} diagrams`);
};

const drawnReading = (svg) => {
  const all = (selector) => [...svg.querySelectorAll(selector)];
  const at = (element, name) => element.getAttribute(name) ?? "";
  const pseudo = (element) => /^state-(start|end)$/.test(at(element, "data-shape"));
  const pseudoIds = new Set(
    all("g.node")
      .filter(pseudo)
      .map((element) => at(element, "data-id")),
  );
  const end = (id) => (pseudoIds.has(id) ? PSEUDO_STATE : id);
  const reading = { nodes: [], groups: [], edges: [], counts: {} };

  for (const element of all("g.node, g.class-node, g.entity, g.actor"))
    if (!pseudo(element))
      reading.nodes.push(
        nodeItem(
          at(element, "data-id"),
          at(element, "data-label"),
          element.matches("g.node") && at(element, "data-shape"),
        ),
      );
  for (const element of all("g.subgraph"))
    reading.groups.push(words(at(element, "data-label")));
  for (const element of all(".edge, .class-relationship, g.message"))
    reading.edges.push(
      edgeItem(
        end(at(element, "data-from")),
        end(at(element, "data-to")),
        at(element, "data-label"),
      ),
    );
  for (const element of all(".er-relationship"))
    reading.edges.push(
      edgeItem(
        at(element, "data-entity1"),
        at(element, "data-entity2"),
        at(element, "data-label"),
      ),
    );

  if (all("g.class-node").length)
    reading.counts.members = all("g.class-node text.mono").length;
  if (all("g.entity").length)
    reading.counts.attributes = all("g.entity text.mono").length / 2;
  if (all("g.actor").length)
    Object.assign(reading.counts, {
      notes: all("g.note").length,
      blocks: all("g.block").length,
    });
  const values = all("[data-value]").length;
  if (values) reading.counts.values = values;
  return reading;
};

const tally = (items) =>
  items.reduce(
    (counts, item) => counts.set(item, (counts.get(item) ?? 0) + 1),
    new Map(),
  );

const unmatched = (kind, source, drawn) => {
  const wanted = tally(source);
  const got = tally(drawn);
  return [
    ...[...wanted]
      .filter(([item, count]) => (got.get(item) ?? 0) < count)
      .map(([item]) => `${kind} in the source but not drawn: ${item}`),
    ...[...got]
      .filter(([item, count]) => (wanted.get(item) ?? 0) < count)
      .map(([item]) => `${kind} drawn but not in the source: ${item}`),
  ];
};

/** What is wrong with the drawing under `svg` as a drawing of `source`, in words for the
 * page's author, or null when the two readings agree. */
export async function drawingFault(source, svg) {
  const { readMermaid } = await import("/vendor/mermaid-reader.esm.js");
  let diagram;
  try {
    diagram = await readMermaid(source.replace(TOKEN, "#000"));
  } catch (error) {
    return `Mermaid does not read this source — ${error?.message || error}`;
  }
  const wanted = sourceReading(diagram);
  const got = drawnReading(svg);
  const differences = [
    ...unmatched("node", wanted.nodes, got.nodes),
    ...unmatched("group", wanted.groups, got.groups),
    ...unmatched("edge", wanted.edges, got.edges),
    ...Object.entries(wanted.counts)
      .filter(([name, count]) => count !== (got.counts[name] ?? 0))
      .map(
        ([name, count]) =>
          `${name}: ${count} in the source, ${got.counts[name] ?? 0} drawn`,
      ),
  ];
  return differences.length
    ? "the drawing does not match its source as Mermaid reads it — " +
        differences.join("; ")
    : null;
}
