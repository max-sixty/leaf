/* lf-diagram's render check: does the drawing hold what the source says?
 *
 * The renderer's parsers are more forgiving than Mermaid's: a statement they cannot read
 * can be dropped, or read as something else, while the rest draws, so a source the
 * renderer only partly understands draws a plausible, wrong diagram and reports nothing.
 * Official Mermaid's grammars are strict, and both libraries describe what they found:
 * Mermaid in its diagram database, Agentic Mermaid in the semantic attributes of the SVG
 * it drew — `data-id`, `data-role`, `data-from`, `data-to` and `data-label`, which its
 * package documents as the contract to read in place of its CSS classes. This module
 * reads both into one shape and lists where they differ.
 *
 * One thing Mermaid reads never reaches this module: its public API keeps a frontmatter
 * `title` back from the diagram it returns, so a title the renderer drops goes unseen
 * here unless the source states it in the body.
 *
 * Mermaid's reading is the authority in both directions. Where Mermaid itself reads less
 * than the author meant — a line opening with `click` is a click directive to it, never
 * a node — a drawing that shows more is refused for showing what Mermaid proper would not
 * draw: that source is a diagram only under the renderer.
 *
 * No Mermaid grammar lives here, and none should be added: a divergence this misses is
 * answered by reading more of what either library already reports. What does live here is
 * the mapping between the two vocabularies — pseudo-state ids, ER names and aliases,
 * notes, sequence numbering, label markup, shape names. Mermaid's database is not a
 * documented API and both libraries are pinned in scripts/vendor.py, so moving a pin is
 * what can break the mapping, and the diagram cases in tests/test_render_gate.py are what
 * says so.
 *
 * Only the render gate runs this (runtime/render-check.js), which is why it may import
 * 2.9MB of Mermaid. */

/* Leaf's palette reaches a diagram as `var(--token)` inside classDef, style and
 * linkStyle, and Mermaid's flowchart grammar has no CSS functions in a style value. Mermaid
 * only reads here, so a colour literal stands in for the token. */
const TOKEN = /var\(--[\w-]+\)/g;

/* The families Leaf documents, as Mermaid names them. The renderer draws more, but a
 * drawing this module cannot compare is not one Leaf promises. */
const FAMILIES = new Set([
  "flowchart-v2",
  "stateDiagram",
  "classDiagram",
  "er",
  "sequence",
  "xychart",
]);

const words = (value) =>
  String(value ?? "")
    .replace(TOKEN, "#000")
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/\\n/g, " ")
    // The renderer turns **x** into <b>x</b>; Mermaid keeps the asterisks.
    .replace(/<\/?[a-z][^>]*>/gi, "")
    .replace(/\*\*/g, "")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&")
    // Mermaid holds an entity code (`#36;`, `#quot;`) as a placeholder until it draws.
    .replace(/ﬂ°°(\d+)¶ß/g, (_, code) => String.fromCodePoint(Number(code)))
    .replace(
      /ﬂ°(\w+)¶ß/g,
      (_, name) =>
        new DOMParser().parseFromString(`&${name};`, "text/html").documentElement
          .textContent,
    )
    .replace(/\s+/g, " ")
    .trim();

const PSEUDO_STATE = "[*]";

/* One spelling per node and per edge, shared by both readings: it is what they are
 * compared on and what the author is shown. */
const nodeItem = (id, label, shape) =>
  `${id} "${words(label)}"` + (shape ? ` (${shape})` : "");
const edgeItem = (from, to, label) =>
  `${from} -> ${to}` + (words(label) ? ` "${words(label)}"` : "");

/* Mermaid's shape names against the ones the renderer writes in `data-shape`. A shape
 * with no entry is one the renderer has no drawing for, so it keeps Mermaid's name and
 * the comparison reports it. */
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
  lean_right: "lean-r",
  lean_left: "lean-l",
  choice: "state-choice",
  fork: "state-fork",
  join: "state-join",
};

/* Shapes neither library writes a label into. Mermaid reads the state's id as its label
 * and draws no text; the renderer writes an empty data-label. */
const UNLABELLED = new Set(["choice", "fork", "join"]);

const sequenceReading = (db, config, reading) => {
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
  // A box groups participants as a subgraph groups nodes.
  for (const box of db.getBoxes()) reading.groups.push(words(box.name));
  Object.assign(reading.counts, { notes: 0, blocks: 0 });
  // `autonumber` numbers every message from its start by its step, whether or not the
  // numbers are showing, and the renderer writes a shown number into the label.
  let number = 1;
  let step = 1;
  let numbered = Boolean(config.sequence?.showSequenceNumbers);
  for (const message of db.getMessages())
    if (arrows.has(message.type)) {
      const label = numbered ? `${number}. ${words(message.message)}` : message.message;
      reading.edges.push(edgeItem(message.from, message.to, label));
      number += step;
    } else if (message.type === kind.NOTE) reading.counts.notes++;
    else if (blocks.has(message.type)) reading.counts.blocks++;
    else if (message.type === kind.AUTONUMBER) {
      number = message.message.start || number;
      step = message.message.step || step;
      numbered = message.message.visible;
    }
  return reading;
};

const sourceReading = ({ diagram: { db, type }, config }) => {
  const reading = { nodes: [], groups: [], edges: [], counts: {} };
  if (db.getAccTitle?.() || db.getAccDescription?.())
    reading.counts["accessible titles"] = 1;
  if (db.getDiagramTitle?.()) reading.counts.titles = 1;
  if (type === "sequence") return sequenceReading(db, config, reading);
  if (type === "xychart") {
    reading.counts.values = db
      .getXYChartData()
      .plots.reduce((sum, plot) => sum + plot.data.length, 0);
    return reading;
  }

  // Flowchart, state, class and ER diagrams share Mermaid's unified layout data.
  const data = db.getData();
  const shaped = type === "flowchart-v2" || type === "stateDiagram";
  const entities = type === "er" ? db.getEntities() : null;
  const names = new Map();
  const notes = new Set();
  reading.counts.notes = 0;
  for (const node of data.nodes) {
    if (node.link) reading.counts.links = (reading.counts.links ?? 0) + 1;
    // A note is one drawn thing, and the dashed line to its subject is part of it.
    if (node.shape === "note") {
      notes.add(node.id);
      reading.counts.notes++;
      continue;
    }
    // Mermaid holds a state's note in a group of its own, which the source never names.
    if (node.shape === "noteGroup") continue;
    const pseudo = /^state(Start|End)$/.test(node.shape ?? "");
    // An ER entity is drawn under its name, and labelled with its alias when it has one.
    const id = pseudo ? PSEUDO_STATE : entities ? node.label : node.id;
    names.set(node.id, id);
    if (pseudo) continue;
    const label = UNLABELLED.has(node.shape)
      ? ""
      : entities
        ? entities.get(node.label)?.alias || node.label
        : node.label;
    // A group's id is never drawn, and Mermaid invents one for `subgraph My Group`.
    if (node.isGroup) reading.groups.push(words(label));
    else
      reading.nodes.push(
        nodeItem(id, label, shaped && (DRAWN_SHAPE[node.shape] ?? node.shape)),
      );
  }
  for (const edge of data.edges) {
    // `~~~` lays two nodes out together and draws nothing between them.
    if (notes.has(edge.start) || notes.has(edge.end) || edge.pattern === "invisible")
      continue;
    reading.edges.push(
      edgeItem(
        names.get(edge.start) ?? edge.start,
        names.get(edge.end) ?? edge.end,
        edge.label,
      ),
    );
  }
  if (type === "classDiagram")
    reading.counts.members = [...db.getClasses().values()].reduce(
      (sum, entry) => sum + entry.members.length + entry.methods.length,
      0,
    );
  if (entities)
    reading.counts.attributes = [...entities.values()].reduce(
      (sum, entity) => sum + entity.attributes.length,
      0,
    );
  return reading;
};

const drawnReading = (svg) => {
  const all = (selector) => [...svg.querySelectorAll(selector)];
  const at = (element, name) => element?.getAttribute(name) ?? "";
  // A drawn thing is the group carrying its role; the shapes inside repeat the role under
  // ids of their own.
  const marks = (...roles) => all(roles.map((role) => `g[data-role="${role}"]`).join());
  const pseudo = (element) => /^state-(start|end)$/.test(at(element, "data-shape"));
  const pseudoIds = new Set(
    marks("node")
      .filter(pseudo)
      .map((element) => at(element, "data-id")),
  );
  const end = (id) => (pseudoIds.has(id) ? PSEUDO_STATE : id);
  const reading = { nodes: [], groups: [], edges: [], counts: {} };

  for (const element of marks("node", "class-box", "entity", "actor"))
    if (!pseudo(element))
      reading.nodes.push(
        nodeItem(
          at(element, "data-id"),
          at(element, "data-label"),
          at(element, "data-role") === "node" && at(element, "data-shape"),
        ),
      );
  for (const element of marks("group"))
    reading.groups.push(words(at(element, "data-label")));
  // A relation carries its endpoints; the line tying a note to its subject has none.
  for (const element of all(
    '[data-role="edge"][data-from], [data-role="relationship"][data-from]',
  ))
    reading.edges.push(
      edgeItem(
        end(at(element, "data-from")),
        end(at(element, "data-to")),
        at(element, "data-label"),
      ),
    );
  // A message group holds its label; the line inside it holds the endpoints.
  for (const element of marks("message")) {
    const line = element.querySelector("[data-from]");
    reading.edges.push(
      edgeItem(at(line, "data-from"), at(line, "data-to"), at(element, "data-label")),
    );
  }

  Object.assign(reading.counts, {
    notes: marks("note").length,
    // A block's header is drawn again over the lifelines, hidden as decoration.
    blocks: all('g[data-role="block"]:not([aria-hidden="true"])').length,
    titles: all('[data-role="title"]').length,
    // The renderer marks a link target as `role="link"` and `data-href` on its node, with
    // nothing that follows it, so only an anchor counts as a link drawn.
    links: all("a[href]").length,
    "accessible titles": all(":scope > title, :scope > desc").length ? 1 : 0,
    members: all('g[data-role="class-box"] text.mono').length,
    attributes: all('g[data-role="entity"] text.mono').length / 2,
    values: all("[data-value]").length,
  });
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
  const { mermaidFamily, readMermaid } = await import("/vendor/mermaid-reader.esm.js");
  const read = source.replace(TOKEN, "#000");
  let reading;
  try {
    const family = mermaidFamily(read);
    if (!FAMILIES.has(family))
      return `Leaf diagrams do not draw Mermaid's ${family} diagrams`;
    reading = await readMermaid(read);
  } catch (error) {
    return `Mermaid does not read this source — ${error?.message || error}`;
  }
  const wanted = sourceReading(reading);
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
