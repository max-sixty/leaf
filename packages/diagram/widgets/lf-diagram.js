/* Pele owns Mermaid parsing, semantic models, layout and SVG generation. Leaf
 * loads it only when a diagram draws, supplies local font metrics and live palette
 * roles, and registers each box its author named as a Comment coordinate (`namedParts`).
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
 * `/runtime/` and `/vendor/` draws it too, in the fonts that page's `--lf-sans` and `--lf-mono`
 * name, else the browser's sans-serif. What Leaf adds it reads from outside: the drawing
 * under way as a `pending-task` event and the named boxes as the visual parts this
 * module registers, which only Leaf's Comment reads. */
import { frameFor, whileConnected } from "/runtime/portable-api.js";
import { PendingTaskEvent } from "/runtime/lib/pending-task.js";
import { bodyText } from "/runtime/lib/data-body.js";
import { failSoft } from "/runtime/lib/failure.js";
import { once } from "/runtime/lib/once.js";
import { sizeObserver } from "/runtime/lib/frame-pass.js";

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

// Pele draws each box its author named, in every kind of diagram, as a node or a
// cluster carrying the name as `data-id`: the Mermaid id, or the box's words where the
// language gives it none, as a journey's task or a timeline's period has. So each takes
// a comment of its own, keyed by its kind and its name: a sequence diagram's `box A`
// is a group and its `participant A` a node. A start or end point and a state's
// divider are Pele's own, and a sequence diagram's foot row draws the participants its
// head row draws again, so none of those is a part. Nor is a box its author left
// unnamed, as an untitled block group or a subgraph titled only in quotes: Pele numbers
// those in order (`id-1`, `subGraph0`), so a comment on one would move to another box
// once the author adds one above it.
//
// A box Pele draws inside another named box is named within it, as a journey's task is
// within its section and a kanban card within its column: a section's task names are
// its own, so `Ship/Review` stays that task whatever other sections hold. A name drawn
// twice within one place, as one label on two periods of a timeline without sections,
// points at no one box, so each copy takes the whole diagram's comment rather than one
// of them taking it by its place in the drawing.
const NAMED =
  'g[data-id]:not([data-id=""]):is(.pele-node,.pele-cluster)' +
  ":not(.pele-state-start,.pele-state-end,.pele-state-divider,.pele-actor-footer)";
const NUMBERED = /^(?:id-|subGraph)\d+$/;
/** @param {Element} drawn @returns {[key: string, box: Element][]} */
function namedParts(drawn) {
  /** @param {Element} box @returns {string} */
  const path = (box) => {
    const name = encodeURIComponent(box.getAttribute("data-id") ?? "");
    const holder = box.parentElement?.closest(NAMED);
    return holder ? `${path(holder)}/${name}` : name;
  };
  const boxes = [...drawn.querySelectorAll(NAMED)].filter(
    (box) => !NUMBERED.test(box.getAttribute("data-id") ?? ""),
  );
  /** @type {[key: string, box: Element][]} */
  const parts = boxes.map((box) => [
    `${box.matches(".pele-cluster") ? "group" : "node"}:${path(box)}`,
    box,
  ]);
  const twice = repeated(parts.map(([key]) => key));
  return parts.filter(([key]) => !twice(key));
}
/** @param {string[]} keys */
function repeated(keys) {
  /** @type {Map<string, number>} */
  const seen = new Map();
  for (const key of keys) seen.set(key, (seen.get(key) ?? 0) + 1);
  return (/** @type {string} */ key) => (seen.get(key) ?? 0) > 1;
}

// The words a drawn box says, with a space where a line wraps. Pele sets each line of a
// wrapped label in a `tspan` at a `y` of its own, and the runs a line's styles split it
// into share their line's, so the box's `textContent` ran "Start" and "request"
// together as "Startrequest", which named its Respond control and its Comment target.
// A `title` is a tooltip, not the box's words, and nor are the words of a named box
// Pele draws inside it, as a journey's section holds its tasks.
/** @param {Element} box */
function wordsOf(box) {
  let words = "";
  for (const text of box.querySelectorAll("text")) {
    if (text.closest(NAMED) !== box) continue;
    let line = text.getAttribute("y");
    words += " ";
    for (const run of text.childNodes) {
      const y = run instanceof Element ? run.getAttribute("y") : null;
      if (y !== null && y !== line) words += " ";
      line = y ?? line;
      words += run.textContent;
    }
  }
  return words.replace(/\s+/g, " ").trim();
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
  drawing.setAttribute("aria-label", title.textContent);
  drawing.removeAttribute("aria-labelledby");
  title.remove();
}

let seq = 0;
customElements.define(
  "lf-diagram",
  class extends HTMLElement {
    /** @type {Map<string, {element: Element, label: string, surface: Element | null}>} */
    visualParts = new Map();
    lfParts = {
      read: () => [...this.visualParts].map(([id, part]) => ({ id, ...part })),
    };
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
          fontFamily: style.getPropertyValue("--lf-sans").trim(),
          fontFamilyMono: style.getPropertyValue("--lf-mono").trim(),
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
      // A class or an entity says its members too, so its name is its label, and a box
      // whose words another part also says is told apart by the box holding it. A box
      // Pele draws other named boxes inside, as a kanban column holds its cards, is
      // marked on its own frame, the shape it draws first, and the boxes keep theirs.
      const named = ["class", "er"].includes(model.type);
      /** @param {Element} box */
      const words = (box) =>
        (!named && wordsOf(box)) || box.getAttribute("data-id") || "";
      const parts = namedParts(this);
      const said = repeated(parts.map(([, element]) => words(element)));
      const visualParts = new Map();
      for (const [key, element] of parts) {
        const holder = element.parentElement?.closest(NAMED);
        const own = words(element);
        const label = said(own) && holder ? `${words(holder)} · ${own}` : own;
        const surface = element.querySelector(NAMED)
          ? element.querySelector(":scope > :is(rect, path, polygon, circle, ellipse)")
          : null;
        visualParts.set(key, { element, label, surface });
      }
      this.visualParts = visualParts;
      this.classList.toggle("lf-rendered", true);
      this.toggleAttribute("data-lf-scroll", true);
      this.dispatchEvent(
        new CustomEvent("lf-layout", { bubbles: true, composed: true }),
      );
    }
  },
);
