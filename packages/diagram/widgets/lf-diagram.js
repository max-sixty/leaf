/* Pele owns Mermaid parsing, semantic models, layout and SVG generation. Leaf
 * loads it only when a diagram draws, supplies local font metrics and live palette
 * roles, and registers Comment coordinates from Pele's drawn named boxes.
 * Drawn boxes have one authored identity across a diagram, including containers;
 * ambiguous identities cannot supply a stable node:<id> Comment coordinate.
 * Rendering is inert: source callbacks never execute, links and images are disabled,
 * and Pele escapes labels and filters styles. A refused source remains visible with
 * its diagnostic; Leaf never salvages a diagram by dropping statements.
 *
 * It imports only the helpers that load in any document, so a plain HTML page that maps
 * `/runtime/` and `/vendor/` draws it too, in the fonts that page's `--sans` and `--mono`
 * name, else the browser's sans-serif. What Leaf adds it reads from outside: the drawing
 * under way as a `pending-task` event and the named boxes as the visual parts this
 * module registers, which only Leaf's Comment reads. */
import {
  PendingTaskEvent,
  bodyText,
  once,
  failSoft,
  registerVisualParts,
} from "/runtime/portable-api.js";

// Room for a 15px overlay track plus the drawing's stroke. CSS lets a native
// classic track consume this same padding, retaining 1px around the marks.
const drawingPadding = 16;

let rendererReady;
const loadRenderer = () => (rendererReady ??= import("/vendor/pele.esm.js"));

/** Pele owns the drawn inventory and its order; synthetic endpoints and mirrors are not parts.
 * @param {ReturnType<typeof import("pele").parse>} model @param {HTMLElement} drawn */
function namedParts(model, drawn) {
  /** @type {Partial<Record<typeof model.type, string>>} */
  const selectors = {
    flowchart: ".pele-node,.pele-cluster",
    class: ".pele-class,.pele-namespace",
    er: ".pele-entity,.pele-cluster",
    sequence: ".pele-actor:not(.pele-actor-footer)",
    state:
      ".pele-node:not(.pele-state-start):not(.pele-state-end):not(.pele-state-divider),.pele-cluster",
  };
  const selector = selectors[model.type];
  if (!selector) return [];
  return [...drawn.querySelectorAll("g")]
    .filter((element) => element.matches("[data-id]:is(" + selector + ")"))
    .map((element) => {
      const id = element.getAttribute("data-id");
      if (!id) throw new Error("Pele drew a named box without an identity");
      return {
        id,
        label: ["class", "er"].includes(model.type) ? id : undefined,
        selector: ":is(" + selector + ")",
      };
    });
}

let seq = 0;
customElements.define(
  "lf-diagram",
  class extends HTMLElement {
    /** @type {Map<string, {element: Element, label: string}>} */
    visualParts = new Map();
    visualPartRegistration = registerVisualParts(this, () =>
      [...this.visualParts].map(([id, part]) => ({ id, ...part })),
    );

    connectedCallback() {
      if (!once(this)) return;
      this.dispatchEvent(new PendingTaskEvent(this.render()));
    }

    async render() {
      const source = bodyText(this);
      const renderId = `lf-diagram-${++seq}`;
      try {
        const [{ parse, render }] = await Promise.all([
          loadRenderer(),
          document.fonts.ready,
        ]);
        const style = getComputedStyle(this);
        const model = parse(source);
        const { svg, height } = render(model, {
          idPrefix: renderId,
          fontFamily: style.getPropertyValue("--sans").trim(),
          fontFamilyMono: style.getPropertyValue("--mono").trim(),
          fontSize: 14,
          padding: drawingPadding,
          responsive: false,
          links: false,
          images: false,
        });
        this.innerHTML = svg;
        this.style.setProperty("--lf-diagram-height", `${height}px`);
        this.style.setProperty("--lf-diagram-padding", `${drawingPadding}px`);
        const drawn = this;
        const parts = [...namedParts(model, drawn)];
        const visualParts = new Map();
        for (const part of parts) {
          const elements = drawn.querySelectorAll(
            `g${part.selector}[data-id="${CSS.escape(part.id)}"]`,
          );
          const [element, duplicate] = elements;
          if (!element || duplicate)
            throw new Error(`Pele did not draw one named box for ${part.id}`);
          const label =
            part.label || element.textContent.replace(/\s+/g, " ").trim() || part.id;
          visualParts.set(`node:${encodeURIComponent(part.id)}`, {
            element,
            label,
          });
        }
        this.visualParts = visualParts;
        this.classList.add("lf-rendered", "scroll");
        this.visualPartRegistration.update();
      } catch (err) {
        failSoft(this, err, source);
      }
    }
  },
);
