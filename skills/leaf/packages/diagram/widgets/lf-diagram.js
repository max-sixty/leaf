/* lf-diagram: renders a Mermaid-source body with Agentic Mermaid. The body is data,
 * not prose — the theme shows it as source until the SVG replaces it, so a page
 * degrades readably if rendering fails. The optional renderer loads lazily, once, and
 * only on pages that use this package. */
import {
  dataBody,
  once,
  failSoft,
  registerVisualParts,
  widgetController,
} from "/runtime/widget-api.js";

let rendererReady;
const loadRenderer = () => (rendererReady ??= import("/vendor/agentic-mermaid.esm.js"));

/* The renderer takes the sans face as its `font` option, which reaches the SVG as a
 * var() expression, but writes class members and ER attributes in a fixed mono stack;
 * that one is rewritten to the page's apparatus face before it reaches the DOM. The
 * palette stays as var() expressions in the SVG, which makes light/dark scheme changes
 * live rather than another render. */
const prepareSvg = (svg) =>
  svg.replaceAll(
    "'JetBrains Mono', 'SF Mono', 'Fira Code', ui-monospace, monospace",
    "var(--mono)",
  );

/* The boxes an author can name as parts: the group the renderer writes for each node,
 * participant, class and entity, and for each group of them — a subgraph, composite
 * state, namespace or sequence box — carries its source id in data-id and its kind in
 * data-role, the attributes the renderer documents as its contract. The shapes inside a
 * box repeat the role under ids of their own. */
const BOXES = ["node", "group", "actor", "class-box", "entity"]
  .map((role) => `g[data-role="${role}"]`)
  .join();
/* The registry's grammar for a part's source id. An id outside it, such as a quoted ER
 * name with a space in it, can never be named, and a part id must be one token. */
const NAMEABLE = /^[A-Za-z_][A-Za-z0-9_-]*$/;

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
      // Registered with the controller so the runtime holds view restore and the first
      // anchor pass until the SVG is in and the page's geometry is final.
      widgetController(this).present(this.render());
    }

    async render() {
      const source = dataBody(this).trim();
      const renderId = `lf-diagram-${++seq}`;
      try {
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
          // A chart's values take a hover tooltip, and a line series draws a dot per
          // value; without it the line alone carries them.
          interactive: true,
          font: "var(--sans)",
          // The renderer's arrowhead and gradient ids are fixed, and a repeated id
          // resolves a later diagram's references into an earlier SVG.
          idPrefix: `${renderId}-`,
          // Otherwise a `click` or `link` target is drawn as a focusable link that
          // nothing on the page navigates; strict draws that box as a plain one.
          security: "strict",
        });
        this.innerHTML = prepareSvg(svg);
        const drawn = this.querySelector("svg");

        // Keep the renderer's natural size. A drawing wider than its room scrolls in
        // the widget instead of scaling its labels below legibility.
        const natural = drawn.viewBox.baseVal.width;
        if (natural) {
          drawn.setAttribute("width", natural);
          drawn.style.maxWidth = "";
        }

        // A class can share its name with the namespace holding it, so a group gives way
        // to a box under the same id; two of one kind under one id name neither.
        const boxes = new Map();
        for (const element of drawn.querySelectorAll(BOXES)) {
          const id = element.getAttribute("data-id");
          const rank = element.getAttribute("data-role") === "group" ? 0 : 1;
          const held = boxes.get(id);
          if (!held || rank > held.rank) boxes.set(id, { element, rank });
          else if (rank === held.rank) held.element = null;
        }
        this.visualParts.clear();
        for (const [id, { element }] of boxes) {
          if (!element || !NAMEABLE.test(id)) continue;
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
