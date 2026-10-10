/* Mermaid owns parsing, semantic identities, layout and SVG generation. Leaf owns
 * the optional lazy load, theme integration and Comment coordinates. A source the
 * renderer refuses remains visible with its diagnostic; Leaf never salvages a
 * partial diagram by dropping statements. */
import {
  bodyText,
  once,
  failSoft,
  keeps,
  registerVisualParts,
  widgetController,
} from "/runtime/widget-api.js";

let rendererReady;
const loadRenderer = () => (rendererReady ??= import("/vendor/mermaid.esm.js"));
const NAMEABLE = /^\S+$/;

/* Mermaid's parser databases are shared between diagrams. Keep parsing, drawing
 * and reading the inventory in one serialized operation, so a neighboring widget
 * cannot replace the identities behind the SVG we have just received. */
let drawing = Promise.resolve();
const draw = (source, id) => {
  const next = drawing.then(async () => {
    const { default: mermaid } = await loadRenderer();
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      suppressErrorRendering: true,
      maxTextSize: Number.MAX_SAFE_INTEGER,
      htmlLabels: false,
      theme: "base",
      look: "classic",
      fontFamily: "var(--sans)",
      // Bind terminal palette roles: Mermaid's seed colors undergo color arithmetic
      // and cannot be CSS variables, while these roles pass straight to its SVG.
      themeVariables: {
        fontSize: "14px",
        useGradient: false,
        dropShadow: "none",
        actorTextColor: "var(--lf-diagram-ink)",
        actorBkg: "var(--lf-diagram-paper)",
        actorBorder: "var(--lf-diagram-accent)",
        actorLineColor: "var(--lf-diagram-muted)",
        labelBoxBkgColor: "var(--lf-diagram-paper)",
        labelBoxBorderColor: "var(--lf-diagram-muted)",
        noteTextColor: "var(--lf-diagram-ink)",
        noteBkgColor: "var(--lf-diagram-paper)",
        noteBorderColor: "var(--lf-diagram-muted)",
        activationBkgColor: "var(--lf-diagram-paper)",
        activationBorderColor: "var(--lf-diagram-muted)",
        stateLabelColor: "var(--lf-diagram-ink)",
        stateBkg: "var(--lf-diagram-paper)",
        compositeBackground: "var(--lf-diagram-paper)",
        compositeTitleBackground: "var(--lf-diagram-paper)",
        altBackground: "var(--lf-diagram-paper)",
        stateBorder: "var(--lf-diagram-muted)",
        specialStateColor: "var(--lf-diagram-ink)",
        innerEndBackground: "var(--lf-diagram-ink)",
        xyChart: {
          backgroundColor: "var(--lf-diagram-paper)",
          xAxisLineColor: "var(--lf-diagram-muted)",
          xAxisTickColor: "var(--lf-diagram-muted)",
          yAxisLineColor: "var(--lf-diagram-muted)",
          yAxisTickColor: "var(--lf-diagram-muted)",
          plotColorPalette: "var(--lf-diagram-accent)",
        },
      },
      // These stay as CSS values, so a scheme change repaints rather than replacing
      // nodes and losing their Comment coordinates. Authored class styles win.
      themeCSS: `
        text, tspan, .label, .nodeLabel, .edgeLabel, .messageText, .loopText,
        .noteText, .node text, .node tspan, .cluster text, .cluster tspan,
        .label text, .label tspan { fill: var(--lf-diagram-ink); color: var(--lf-diagram-ink); }
        .node rect, .node polygon, .node circle, .node ellipse, .node path,
        rect.actor, .actor-man line, .actor-man circle, .labelBox {
          fill: color-mix(in srgb, var(--lf-diagram-accent) 10%, var(--lf-diagram-paper));
          stroke: var(--lf-diagram-accent);
        }
        .cluster rect, .note { fill: var(--lf-diagram-paper); stroke: var(--lf-diagram-muted); }
        .edgePaths path, .flowchart-link, .messageLine0, .messageLine1, .actor-line {
          stroke: var(--lf-diagram-muted);
        }
        marker path { fill: var(--lf-diagram-muted); stroke: var(--lf-diagram-muted); }
        .edgeLabel .label rect, .labelBkg { fill: var(--lf-diagram-paper); }
        .edgeLabel, .labelBkg { background-color: var(--lf-diagram-paper); }
      `,
    });
    const diagram = await mermaid.mermaidAPI.getDiagramFromText(source);
    // Mermaid's graph layouts require each node and container to have one identity.
    // Refuse a collision before layout, which otherwise cannot finish its traversal.
    const identities = new Set();
    for (const node of diagram.db.getData?.().nodes ?? []) {
      if (identities.has(node.id))
        throw new Error(`Mermaid declares diagram identity ${node.id} more than once`);
      identities.add(node.id);
    }
    const { svg } = await mermaid.render(id, source);
    // Jison's parser keeps the database from its most recent parse in yy. Mermaid
    // can instantiate a new database when rendering (class IDs advance globally),
    // so read that actual render's inventory rather than the preflight instance.
    const db = diagram.getParser().parser?.yy ?? diagram.db;
    const parts = [];
    if (diagram.type === "sequence") {
      for (const key of db.getActors().keys()) parts.push({ id: key, dataId: key });
    } else if (diagram.type === "er") {
      for (const [key, entity] of db.getEntities())
        parts.push({ id: key, domId: `${id}-${entity.id}` });
    } else if (/^(flowchart|state|class)/.test(diagram.type)) {
      for (const node of db.getData().nodes) {
        if (["stateStart", "stateEnd", "divider", "note"].includes(node.shape))
          continue;
        // State layout writes its final prefixed domId back into its nodes; the
        // flowchart and class databases retain the pre-layout local identifier.
        const domId = diagram.type.startsWith("state")
          ? node.domId
          : `${id}-${node.domId || node.id}`;
        parts.push({ id: node.id, domId });
      }
    }
    return { svg, parts };
  });
  drawing = next.catch(() => {});
  return next;
};

let seq = 0;
customElements.define(
  "lf-diagram",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      this.visualParts = new Map();
      this.visualPartRegistration = registerVisualParts(this, () =>
        [...this.visualParts].map(([id, part]) => ({ id, ...part })),
      );
      widgetController(this).present(this.render());
    }

    async render() {
      const source = bodyText(this);
      const renderId = `lf-diagram-${++seq}`;
      try {
        const { svg, parts } = await draw(source, renderId);
        this.innerHTML = svg;
        const drawn = this.querySelector("svg");
        const natural = drawn.viewBox.baseVal.width;
        if (natural) {
          keeps(drawn, "width", natural);
          drawn.style.maxWidth = "";
        }
        this.visualParts.clear();
        for (const part of parts) {
          if (!NAMEABLE.test(part.id)) continue;
          const element = part.dataId
            ? drawn.querySelector(`g[data-id="${CSS.escape(part.dataId)}"]`)
            : drawn.querySelector(`[id="${CSS.escape(part.domId)}"]`);
          if (!element)
            throw new Error(`Mermaid did not draw the declared node ${part.id}`);
          const label = element.textContent.replace(/\s+/g, " ").trim() || part.id;
          this.visualParts.set(`node:${part.id}`, { element, label });
        }
        this.classList.add("lf-rendered");
        this.visualPartRegistration.update();
      } catch (err) {
        failSoft(this, err, source);
      }
    }
  },
);
