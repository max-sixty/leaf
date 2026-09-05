/* lf-diagram: renders a Mermaid-source body with Beautiful Mermaid. The body is data,
 * not prose — the theme shows it as source until the SVG replaces it, so a page
 * degrades readably if rendering fails. The optional renderer loads lazily, once, and
 * only on pages that use this package. */
import {
  dataBody,
  once,
  failSoft,
  registerVisualParts,
  settle,
} from "/runtime/widget-api.js";

let rendererReady;
const loadRenderer = () =>
  (rendererReady ??= import("/vendor/beautiful-mermaid.esm.js"));

/* Beautiful Mermaid writes a Google Fonts import and its requested font name into
 * every SVG. A Leaf page is self-contained and its CSP rejects that import, so the
 * renderer receives a sentinel and the output is rewritten to the page's apparatus
 * face before it ever reaches the DOM. The palette stays as var() expressions in the
 * SVG, which makes light/dark scheme changes live rather than another render. */
const prepareSvg = (svg) =>
  svg
    .replace(/@import url\(['"]https:\/\/fonts\.googleapis\.com\/[^)]*\);\s*/g, "")
    .replaceAll("'LeafDiagram', system-ui, sans-serif", "var(--sans)")
    .replaceAll(
      "'JetBrains Mono', 'SF Mono', 'Fira Code', ui-monospace, monospace",
      "var(--mono)",
    );

/* Beautiful Mermaid's flowchart parser reads statements it does not implement as node
 * declarations. Reject the known unsupported Mermaid directives before they can draw
 * boxes labelled with their own keywords. The identifier after `click` distinguishes
 * the directive from an ordinary flowchart node an author happened to name `click`. */
const UNSUPPORTED_DIRECTIVE =
  /^\s*(?:click\s+[A-Za-z_]|accTitle\s*:|accDescr\s*(?::|\{))/m;

/* The same parser reads a label as the text up to the first closing delimiter without
 * noticing the quotes Mermaid uses to hold one. `A["list[str]"]` is therefore cut at the
 * inner bracket, and the remainder of the line — the node an edge points at included —
 * is dropped, so the reader sees a box short of a diagram rather than an error. Refuse
 * that source. The reading is the parser's own: a quoted label is cut only by the
 * delimiter run that actually follows it, so a doubled closer (`A[["list[str]"]]`) and a
 * pipe-delimited edge label (`A -->|"list[str]"| B`) both pass through whole. */
const QUOTED_LABEL = /"([^"\n]*)"([\])}|>/\\]*)/g;

/* A subgraph title is the exception: the parser reads the whole line with its own greedy,
 * end-anchored regex (`/^([\w-]+)\s*\[(.+)\]$/`) rather than through the node patterns,
 * so it carries the closer whole and `subgraph S["Stage [1]"]` renders today. Scan by line
 * so the title's line can be skipped without exempting the nodes around it. */
const SUBGRAPH_TITLE = /^\s*subgraph\s/;

/* A comment is not read at all: the parser trims each line and drops the ones starting
 * with `%%` before any pattern sees them, so a commented-out label cannot be cut — and
 * refusing one leaves an author no way to set a refused line aside while they work. */
const COMMENT_LINE = /^\s*%%/;
const rejectCutLabel = (source) => {
  for (const line of source.split("\n")) {
    if (SUBGRAPH_TITLE.test(line) || COMMENT_LINE.test(line)) continue;
    for (const [, label, closer] of line.matchAll(QUOTED_LABEL))
      if (closer && label.includes(closer))
        throw new Error(
          `a label cannot hold ${closer}, the delimiter that closes its own shape — ` +
            `the renderer cuts the line there, quoted or not: "${label}"`,
        );
  }
};

const rejectUnsupportedSource = (source) => {
  if (UNSUPPORTED_DIRECTIVE.test(source))
    throw new Error(
      "click, accTitle and accDescr directives are not supported by Leaf diagrams",
    );
  rejectCutLabel(source);
};

/* The renderer uses fixed ids for arrowheads, gradients and masks. Repeated ids make
 * a later diagram's references resolve into an earlier SVG, so each rendering gets a
 * namespace at Leaf's boundary. Source coordinates live in data-id and do not move. */
const namespaceDefinitions = (svg, prefix) => {
  const ids = new Map();
  for (const element of [svg, ...svg.querySelectorAll("[id]")]) {
    if (!element.id) continue;
    const namespaced = `${prefix}-${element.id}`;
    ids.set(element.id, namespaced);
    element.id = namespaced;
  }
  const rewrite = (value) =>
    value
      .replace(/url\(#([^)]+)\)/g, (whole, id) =>
        ids.has(id) ? `url(#${ids.get(id)})` : whole,
      )
      .replace(/^#(.+)$/, (whole, id) => (ids.has(id) ? `#${ids.get(id)}` : whole));
  for (const element of [svg, ...svg.querySelectorAll("*")])
    for (const attribute of [...element.attributes]) {
      const value = rewrite(attribute.value);
      if (value !== attribute.value) element.setAttribute(attribute.name, value);
    }
  for (const style of svg.querySelectorAll("style"))
    style.textContent = rewrite(style.textContent);
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
      // Registered with settle() so the runtime holds view restore and the first
      // anchor pass until the SVG is in and the page's geometry is final.
      settle(this.render());
    }

    async render() {
      const source = dataBody(this).trim();
      const renderId = `lf-diagram-${++seq}`;
      try {
        rejectUnsupportedSource(source);
        const { renderMermaidSVG } = await loadRenderer();
        const svg = renderMermaidSVG(source, {
          bg: "var(--lf-diagram-paper)",
          fg: "var(--lf-diagram-ink)",
          line: "var(--lf-diagram-muted)",
          accent: "var(--lf-diagram-accent)",
          muted: "var(--lf-diagram-muted)",
          surface:
            "color-mix(in srgb, var(--lf-diagram-accent) 14%, var(--lf-diagram-paper))",
          border:
            "color-mix(in srgb, var(--lf-diagram-accent) 48%, var(--lf-diagram-paper))",
          transparent: true,
          font: "LeafDiagram",
        });
        this.innerHTML = prepareSvg(svg);
        const drawn = this.querySelector("svg");
        namespaceDefinitions(drawn, renderId);

        // Keep the renderer's natural size. A drawing wider than its room scrolls in
        // the widget instead of scaling its labels below legibility.
        const natural = drawn.viewBox.baseVal.width;
        if (natural) {
          drawn.setAttribute("width", natural);
          drawn.style.maxWidth = "";
        }

        const boxes = new Map();
        for (const element of drawn.querySelectorAll("[data-id]")) {
          const id = element.getAttribute("data-id");
          boxes.set(id, boxes.has(id) ? null : element);
        }
        this.visualParts.clear();
        for (const [id, element] of boxes) {
          if (!element) continue;
          const says = element.textContent.replace(/\s+/g, " ").trim();
          const label = element.getAttribute("data-label") || says || id;
          this.visualParts.set(`node:${id}`, { element, label });
        }
        this.classList.add("lf-rendered");
        this.visualPartRegistration.update();
      } catch (err) {
        failSoft(this, err, source);
      }
    }
  },
);
