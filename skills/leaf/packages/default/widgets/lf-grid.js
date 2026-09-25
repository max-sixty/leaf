/* A grid's count needs no script: the theme reads `columns="3"` as a selector. A track
   template is the one value a stylesheet cannot read out of an attribute, so the module
   paints it as --lf-grid-template, and says when the grid stacks.

   A template stacks where its narrowest track would fall below --lf-grid-min, the least
   a column of a counted grid takes too: its tracks are minmax(0, …fr), so the narrowest
   is (width − gaps) × narrowest ÷ sum of the fr values, and the grid stacks below
   --lf-grid-min × (sum ÷ narrowest) plus its gaps. That width is a different number for
   every template, and a container query's condition is a constant, so the module reads
   the grid's width and marks `data-lf-grid-stacked` below it; the theme spans each cell
   across the row there. Stacking changes the grid's
   height and never its width, so the reading cannot feed back into itself.

   The mark is written in a rendering pass (`nextRender`), never in the size observer's
   delivery: that delivery comes after layout, and a grid changing height there resizes
   every box above it that another observer watches, which the browser reports as a
   ResizeObserver loop. A template painted at upgrade is judged in the pass before the
   frame paints it; a grid the window or a disclosure resizes is judged one frame after. */
import { nextRender, once, sizeObserver } from "/runtime/widget-api.js";

const COUNT = /^[1-6]$/;
const STACKED = "data-lf-grid-stacked";
// How many of its narrowest track each template is wide, and how many gaps it has.
const templates = new WeakMap();
const pending = new Set();
let queued = false;

function judge() {
  queued = false;
  // Every width is read before any mark is written, so the pass lays out once. A grid
  // with no width is not laid out (display: none) and keeps its mark; one in a closed
  // disclosure is laid out though not shown, so it is judged and opens already marked.
  const readings = [...pending]
    .filter((grid) => templates.has(grid))
    .map((grid) => [grid, grid.getBoundingClientRect().width])
    .filter(([, width]) => width > 0)
    .map(([grid, width]) => {
      const { scale, gaps } = templates.get(grid);
      const style = getComputedStyle(grid);
      const floor = parseFloat(style.getPropertyValue("--lf-grid-min"));
      const gap = parseFloat(style.columnGap);
      return [grid, width < floor * scale + gaps * gap];
    });
  pending.clear();
  for (const [grid, stacked] of readings)
    if (grid.hasAttribute(STACKED) !== stacked) grid.toggleAttribute(STACKED, stacked);
}

function reconsider(grid) {
  pending.add(grid);
  if (queued) return;
  queued = true;
  nextRender(judge);
}

const resized = sizeObserver((entries) => {
  for (const { target } of entries) reconsider(target);
});

customElements.define(
  "lf-grid",
  class extends HTMLElement {
    static observedAttributes = ["columns"];

    connectedCallback() {
      this.#paint();
      once(this);
    }

    disconnectedCallback() {
      resized.unobserve(this);
    }

    attributeChangedCallback() {
      if (this.isConnected) this.#paint();
    }

    #paint() {
      const columns = this.getAttribute("columns");
      if (columns && !COUNT.test(columns)) {
        const tracks = columns.split(" ");
        const fr = tracks.map(parseFloat);
        // Each track is at least nothing rather than its content's minimum, so what a
        // cell holds cannot move the split; a wide cell scrolls or wraps inside it.
        this.style.setProperty(
          "--lf-grid-template",
          tracks.map((track) => `minmax(0, ${track})`).join(" "),
        );
        templates.set(this, {
          scale: fr.reduce((a, b) => a + b, 0) / Math.min(...fr),
          gaps: tracks.length - 1,
        });
        resized.observe(this);
        reconsider(this);
      } else {
        this.style.removeProperty("--lf-grid-template");
        templates.delete(this);
        resized.unobserve(this);
        this.removeAttribute(STACKED);
      }
      if (!this.getAttribute("style")) this.removeAttribute("style");
    }
  },
);
