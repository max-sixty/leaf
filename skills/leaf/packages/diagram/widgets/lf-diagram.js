/* lf-diagram: renders a Mermaid-source body with Beautiful Mermaid. The body is data,
 * not prose — the theme shows it as source until the SVG replaces it, so a page
 * degrades readably if rendering fails. The optional renderer loads lazily, once, and
 * only on pages that use this package. */
import { dataBody, once, failSoft, settle } from "/runtime/widget-api.js";

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
    .replaceAll("'LeafDiagram', system-ui, sans-serif", "var(--sans)");

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
      // Registered with settle() so the runtime holds view restore and the first
      // anchor pass until the SVG is in and the page's geometry is final.
      settle(this.render());
    }

    async render() {
      const source = dataBody(this).trim();
      const renderId = `lf-diagram-${++seq}`;
      try {
        const { renderMermaidSVG } = await loadRenderer();
        const declared = new Set(
          (this.getAttribute("parts") ?? "").trim().split(/\s+/).filter(Boolean),
        );
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
        for (const part of declared) {
          const id = part.slice("node:".length);
          const element = boxes.get(id);
          if (!element) continue;
          const says = element.textContent.replace(/\s+/g, " ").trim();
          const label = element.getAttribute("data-label") || says || id;
          this.visualParts.set(part, { element, label });
        }
        const missing = [...declared].filter((part) => !this.visualParts.has(part));
        if (missing.length)
          throw new Error(`commentable diagram boxes not found: ${missing.join(", ")}`);
        this.classList.add("lf-rendered");
      } catch (err) {
        failSoft(this, err, source);
      }
    }

    lfVisualPart(part) {
      return this.visualParts.get(part) ?? null;
    }

    lfVisualPartAt(target) {
      for (const [part, record] of this.visualParts)
        if (record.element === target || record.element.contains(target)) return part;
      return null;
    }
  },
);
