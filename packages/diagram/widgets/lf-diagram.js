/* Pele owns Mermaid parsing, semantic models, layout and SVG generation. Leaf
 * loads it only when a diagram draws, supplies local font metrics and live palette
 * roles, and registers Comment coordinates from Pele's drawn named boxes.
 * Drawn boxes have one authored identity across a diagram, including containers;
 * ambiguous identities cannot supply a stable node:<id> Comment coordinate.
 * Rendering is inert: source callbacks never execute, links and images are disabled,
 * and Pele escapes labels and filters styles. A refused source remains visible with
 * its diagnostic; Leaf never salvages a diagram by dropping statements.
 *
 * A diagram is laid out for the width of the box the page gives it, on a phone as on a
 * desktop, so its author sizes nothing by hand. Pele takes that width as `maxWidth`:
 * where the authored layout fits, it returns that layout unchanged; where it doesn't,
 * it narrows what it can, and turns a left-to-right flowchart, class or entity diagram
 * top-down, at any width rather than only below Pele's 640px default, since a chain
 * cut at a desktop column's edge reads as ending there (defaults.css). A flowchart
 * still too wide is drawn again more compactly (`COMPACT`). What can't narrow that
 * far, such as a long row of boxes side by side, keeps its size and scrolls in its
 * box; a drawing is never scaled. The width is observed, and the diagram drawn again
 * in Leaf's next pass when it changes, so a window resized back to a width shows what
 * it showed there. Pele's own `mount()` observes and redraws too,
 * but on a frame of its own, outside the rendering loop whose settled reading pages and
 * checks wait on, and with an error box of its own in place of `failSoft`; so this
 * module observes through `sizeObserver` and calls `render`. A box whose width follows
 * its drawing, as a shrink-to-fit one does, would resize after every redraw, so the
 * widget skips the redraw when the box is exactly as wide as the drawing, as Pele's
 * `mount()` does.
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
  frameFor,
  registerVisualParts,
  sizeObserver,
  whileConnected,
} from "/runtime/portable-api.js";

// Room for a 15px overlay track plus the drawing's stroke. CSS lets a native
// classic track consume this same padding, retaining 1px around the marks.
const drawingPadding = 16;

let rendererReady;
const loadRenderer = () => (rendererReady ??= import("/vendor/pele.esm.js"));

// For `maxWidth`, Pele turns a left-to-right flowchart and tightens its spacing, but
// keeps Mermaid's 120px wrapping width for its labels, so a top-down flowchart with a
// few boxes side by side stays wider than a phone's column. A flowchart that still runs
// past its box is drawn again with its labels wrapped at 84px and its boxes 8px apart,
// as an author fitting one to a phone sets them, and kept where that is narrower. A
// flowchart config the author writes in the source's frontmatter replaces this one.
// Pele's own `maxWidth` would be its home, and this goes once Pele wraps labels for it.
const COMPACT = { flowchart: { wrappingWidth: 84, nodeSpacing: 8 } };

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

// `accTitle` names the drawing for a reader who can't see it. Pele writes it as the
// drawing's `<title>`, which the browser also shows as a tooltip over every part of the
// drawing that has none of its own, saying a name the caption or heading beside it
// usually says already. The same words as `aria-label` name it with no tooltip.
/** @param {SVGSVGElement | null} drawing */
function nameWithoutTooltip(drawing) {
  const id = drawing?.getAttribute("aria-labelledby");
  const title = id ? drawing?.querySelector(`:scope > title#${CSS.escape(id)}`) : null;
  if (!drawing || !title) return;
  drawing.setAttribute("aria-label", title.textContent ?? "");
  drawing.removeAttribute("aria-labelledby");
  title.remove();
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
    // The content width the box last laid out at, 0 where it shows no box, and none
    // before the first observation; the width the drawing showing was drawn for, its
    // own width, and its markup; and the draw, once the renderer has read the source.
    /** @type {number | undefined} */
    #width;
    /** @type {{for: number, width: number, svg: string} | null} */
    #drawn = null;
    /** @type {(() => void) | null} */
    #draw = null;

    connectedCallback() {
      if (!once(this)) return;
      this.dispatchEvent(new PendingTaskEvent(this.render()));
    }

    // Settles with the first drawing, or with its failure shown in its place.
    async render() {
      const source = bodyText(this);
      const renderId = `lf-diagram-${++seq}`;
      let stop = () => {};
      /** @param {unknown} err */
      const failed = (err) => {
        stop();
        this.#draw = null;
        failSoft(this, err, source);
      };
      const paint = frameFor(this, () => this.#draw?.());
      // The width arrives off the observer's entries rather than a read of the box, so
      // a page of diagrams is laid out once rather than once for each after another's
      // drawing. A box can't be resized inside the delivery that measured it, so the
      // drawing waits for the next pass. Each connection observes afresh, so a diagram
      // taken out before its drawing landed draws when it is put back.
      stop = whileConnected(this, () => {
        const watching = sizeObserver((entries) => {
          const width = Math.floor(entries.at(-1)?.contentRect.width ?? 0);
          this.#width = width;
          const drawn = this.#drawn;
          if (
            this.#draw &&
            width !== drawn?.for &&
            width !== Math.floor(drawn?.width ?? -1)
          )
            paint();
        });
        watching.observe(this);
        return () => watching.disconnect();
      });
      try {
        const [{ parse, render }] = await Promise.all([
          loadRenderer(),
          document.fonts.ready,
        ]);
        const style = getComputedStyle(this);
        const model = parse(source);
        const options = {
          idPrefix: renderId,
          fontFamily: style.getPropertyValue("--sans").trim(),
          fontFamilyMono: style.getPropertyValue("--mono").trim(),
          fontSize: 14,
          padding: drawingPadding,
          responsive: false,
          links: false,
          images: false,
          directionBreakpoint: Infinity,
        };
        /** @type {ReturnType<typeof parse> | undefined} */
        let compact;
        await new Promise((settled) => {
          this.#draw = () => {
            try {
              const width = this.#width ?? 0;
              const maxWidth = width || undefined;
              let drawing = render(model, { ...options, maxWidth });
              if (width && drawing.width > width) {
                compact ??= parse(source, { config: COMPACT });
                const narrower = render(compact, { ...options, maxWidth });
                if (narrower.width < drawing.width) drawing = narrower;
              }
              this.#show(model, width, drawing);
            } catch (err) {
              failed(err);
            }
            settled(undefined);
          };
          // A box the observer has measured draws now, and so does one with no box to
          // measure, such as one in a shut disclosure, which no observation reaches
          // until it opens: it draws at its natural size, so its parts stand as Comment
          // targets, and again at its width once shown. A box laid out but not yet
          // measured draws at the observation on its way.
          if (
            this.#width !== undefined ||
            !this.checkVisibility({ contentVisibilityAuto: true })
          )
            paint();
        });
      } catch (err) {
        failed(err);
      }
    }

    /** @param {ReturnType<typeof import("pele").parse>} model @param {number} width
     * @param {ReturnType<typeof import("pele").render>} drawing */
    #show(model, width, { svg, width: drawnWidth, height }) {
      const same = this.#drawn?.svg === svg;
      this.#drawn = { for: width, width: drawnWidth, svg };
      if (same) return;
      this.innerHTML = svg;
      nameWithoutTooltip(this.querySelector(":scope > svg"));
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
      this.classList.toggle("lf-rendered", true);
      this.toggleAttribute("data-lf-scroll", true);
      this.visualPartRegistration.update();
    }
  },
);
