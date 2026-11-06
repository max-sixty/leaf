/* lf-chart: a chart drawn by Observable Plot, written in Plot's own API. The body is a
 * JavaScript expression for the options object an author would hand `Plot.plot`, with
 * `Plot` and the drawing's `width` in scope, so every mark, transform, scale, format and
 * function in it is Plot's. Leaf keeps no chart vocabulary of its own for an author to
 * learn or for Plot to outgrow.
 *
 * The body is source in the markup rather than a page module, because a chart has to
 * stand wherever markup does: in a reply an agent sends into a thread, which carries no
 * module, and in any version of the page. It is compiled with `Function`, which each
 * policy a page is delivered under admits, and it runs with the page's own authority:
 * the body is the author's code, as a page module is.
 *
 * What the host adds is what a drawing needs from the page it sits in. It is drawn for the
 * room it has and drawn again when that room changes, since a drawing scaled into a new
 * box takes its labels below legibility with it: the width is the host's, and the body
 * reads it to fit its ticks to the room. The height is the box's too: on a Leaf page it
 * is stated (x-height, or the occurrence's data-height), and the theme holds the box at
 * it before the drawing arrives, so the drawing and any legend Plot sets beside it are
 * drawn to fill it and move nothing below it. Its type and ink are the theme's, and so
 * are its series colours, because Plot takes `var(--series-N)` wherever it takes a colour. A user
 * who cannot see it hears Plot's `ariaLabel` in its place. It is one comment target,
 * through `x-visual: whole`. And a chart that cannot draw says why over its own source.
 *
 * A chart says the value under the reader's aim (chart-points.js says which marks and
 * how): a pointer resting near a point, a finger held on one, or, with the chart
 * focused, the arrow keys stepping along a series and across to the next, Home and End
 * to its ends. The point the reader is on wears a ring, with a rule to the axis it
 * stands at, and its words stand beside it in the page's preview (`lfPreview`), which
 * the chart reads again as the aim moves to another point (`previewChanged`). The ring
 * is the chart's own, so it goes when the aim leaves: the pointer and finger by
 * leaving the drawing, the keyboard by leaving the chart. A finger slides across the
 * drawing to read along it, and scrolls the page up and down it.
 *
 * The vendored bundle loads once, on the first draw rather than with this module: a chart
 * in a shut panel has no box, so measure holds its draw, and the 384KB bundle waits with
 * it instead of loading in front of a user who never opens that panel.
 *
 * It imports only the helpers that load in any document, so a plain HTML page that maps
 * `/runtime/` and `/vendor/` draws it too, into the box that page gives it. A
 * Leaf page hears its drawing and its refusals from outside it: the drawing under way
 * as a `pending-task` event, which holds the page's presentation until it is in, and a
 * refusal as the `error` event `failSoft` dispatches, which the page reports to the
 * author. */
import {
  PendingTaskEvent,
  announce,
  bodyText,
  commandsChanged,
  html,
  keeps,
  whileConnected,
  failSoft,
  inBaseLayer,
  measure,
  once,
  previewChanged,
  sizeObserver,
} from "/runtime/portable-api.js";
import { cross, nearest, readPoints, sayPoint, step } from "./chart-points.js";

const SVG = "http://www.w3.org/2000/svg";

/** @typedef {import("./chart-points.js").Point} Point
 * @typedef {import("./chart-points.js").Reading & {svg: SVGSVGElement, ring: SVGGElement}} Reading
 * @typedef {"pointer" | "focus" | "key"} By */

let plotReady;
const loadPlot = () => (plotReady ??= import("/vendor/plot.esm.js"));

/* The body as a function of Plot and the width, which returns the chart's options. The
 * newline before the closing parenthesis ends a trailing line comment. */
/** @param {string} source */
const compile = (source) =>
  new Function("Plot", "width", `"use strict";\nreturn (\n${source}\n);`);

/* The options one drawing is made from, made afresh for each so that no mark Plot has
 * already rendered is handed to it a second time. */
/** @param {Function} body @param {typeof import("@observablehq/plot")} Plot
 * @param {number} width @param {number} height */
function drawOptions(body, Plot, width, height) {
  /** @type {import("@observablehq/plot").PlotOptions} */
  const spec = body(Plot, width);
  // Plot's own examples end in Plot.plot(...), which returns the drawing rather than
  // its options, at a width the body chose.
  if (spec instanceof Node)
    throw new Error(
      "give the options rather than Plot.plot(...): lf-chart calls Plot.plot itself, at the width it has",
    );
  if (!spec.ariaLabel)
    throw new Error(
      "give Plot an ariaLabel: it is what a user who cannot see the chart hears",
    );
  if ("height" in spec)
    throw new Error(
      "state the chart's height as data-height on the element rather than in the options: the page holds that box before the chart draws",
    );
  offsetsAreNumbers(spec.marks);
  return { ...spec, width, height };
}

/* Plot reads a mark's offsets and margins as one number for the whole mark (`+dy`), so a
 * function there, such as a dy chosen per datum to keep end labels apart, becomes NaN,
 * and all the page hears is the browser's "Trailing garbage" about a transform, logged
 * from Plot's bundle. The chart names the mark and the option instead. */
/** @type {("dx" | "dy" | "marginTop" | "marginRight" | "marginBottom" | "marginLeft")[]} */
const OFFSETS = ["dx", "dy", "marginTop", "marginRight", "marginBottom", "marginLeft"];
/** @param {import("@observablehq/plot").Markish} marks @param {string} [place] */
function offsetsAreNumbers(marks, place = "marks") {
  if (!Array.isArray(marks)) return;
  marks.forEach((mark, index) => {
    const at = `${place}[${index}]`;
    if (Array.isArray(mark)) return offsetsAreNumbers(mark, at);
    if (!mark || typeof mark !== "object") return;
    const name = OFFSETS.find((option) => Number.isNaN(mark[option]));
    if (name)
      throw new Error(
        `${at} (${mark.ariaLabel ?? "a mark"}) has a ${name} that is not a number: Plot takes one ${name} for the whole mark, so draw each group that needs its own ${name} as a mark of its own`,
      );
  });
}

customElements.define(
  "lf-chart",
  class extends HTMLElement {
    // The height every drawing takes, read at the first (`paint`).
    /** @type {number | undefined} */
    #height;
    drawing = document.createElement("div");
    /** @type {number | undefined} */
    drawn;
    // The points the drawing showing says, the one the reader is on and what brought
    // them there, and whether a pointer or finger is over the drawing.
    /** @type {Reading | null} */
    #reading = null;
    /** @type {Point | null} */
    #at = null;
    /** @type {By} */
    #by = "pointer";
    #over = false;

    // What the point the reader is on says, beside its ring.
    lfPreview = () => {
      const at = this.#at;
      const ring = this.#reading?.ring.lastElementChild;
      if (!at || !ring) return null;
      const { name, detail } = sayPoint(at);
      return {
        words: html`<span class="lf-preview-word">${name}</span>${detail.map(
            (line) => html`<span class="lf-preview-more">${line}</span>`,
          )}`,
        at: ring.getBoundingClientRect(),
      };
    };

    connectedCallback() {
      if (!once(this)) return;
      whileConnected(this, (signal) => {
        // The pointer and a finger read the point nearest them on the drawing, and
        // nothing elsewhere, as over a legend. A mouse carrying a press is dragging.
        const aim = (/** @type {PointerEvent} */ event) => {
          const svg = this.#reading?.svg;
          if (event.pointerType === "mouse" && event.buttons) return;
          if (!svg || !(event.target instanceof Node) || !svg.contains(event.target))
            return this.#leave();
          const screen = svg.getScreenCTM();
          if (!screen || !this.#reading) return;
          this.#over = true;
          const at = new DOMPoint(event.clientX, event.clientY).matrixTransform(
            screen.inverse(),
          );
          this.#choose(nearest(this.#reading, at.x, at.y), "pointer");
        };
        // A mouse reads where it moves to, so a drawing that arrives under a still one
        // says nothing; a finger, which lands before it moves, reads where it lands.
        this.addEventListener("pointermove", aim, { signal, passive: true });
        this.addEventListener(
          "pointerover",
          (event) => {
            if (event.pointerType !== "mouse") aim(event);
          },
          { signal, passive: true },
        );
        this.addEventListener("pointerleave", () => this.#leave(), { signal });
        // Focus the browser shows lands the reader on a point, where they last were or at
        // the first, which the arrows then step from.
        this.addEventListener(
          "focus",
          () => {
            if (this.#reading && !this.#at && this.matches(":focus-visible"))
              this.#choose(step(this.#reading, null, "first"), "focus");
          },
          { signal },
        );
        // Leaving the chart ends the keyboard's hold on its point.
        this.addEventListener(
          "blur",
          () => this.#choose(this.#over ? this.#at : null, "pointer"),
          { signal },
        );
      });
      // A chart is drawn to the room it has, so the first draw waits for a box. On the
      // page that box is there already and this settles inside the upgrade, holding the
      // view restore and the first anchor pass until the drawing is in and the page's
      // geometry is final. In a shut panel there is no box at all and measure holds the
      // draw instead of the page.
      measure(this, () => this.dispatchEvent(new PendingTaskEvent(this.draw())));
    }

    async draw() {
      // Inside the try with everything else: bodyText reaches for a <pre> both markup
      // doors require, and an authored document hand-edited past them threw out of here
      // instead of failing soft, leaving the user the body's raw text and no error at all.
      let source = "";
      try {
        source = bodyText(this);
        const body = compile(source);
        const Plot = await loadPlot();
        // The box each drawing goes in. A redraw replaces what is in it and nothing else,
        // because by then the runtime may have hung its own words on the widget — the
        // line saying a comment stands on this chart is a child of the element.
        this.drawing.className = "lf-chart-drawing";
        this.replaceChildren(this.drawing);
        this.paint(Plot, body);
        this.classList.add("lf-rendered");
        // Only the width is watched, and only when it lands on a new whole pixel; the
        // height is the first drawing's and stays. Draw during resize delivery so
        // labels fit the new width in the same paint. The fixed drawing height
        // keeps this redraw from resizing the host it watches.
        // A failed redraw ends the watch: the failure replaced the drawing, and a
        // chart that returns to the page keeps showing it rather than drawing again.
        /** @type {() => void} */
        let stop;
        const paint = () => {
          if (!this.clientWidth || Math.round(this.clientWidth) === this.drawn) return;
          try {
            this.paint(Plot, body);
          } catch (err) {
            stop();
            this.#read(null);
            failSoft(this, err, source);
          }
        };
        stop = whileConnected(this, () => {
          const watching = sizeObserver(paint);
          watching.observe(this);
          return () => watching.disconnect();
        });
      } catch (err) {
        this.#read(null);
        failSoft(this, err, source);
      }
    }

    // Drawn to the box's height as well as its width. The height is read once, at the
    // first drawing, while the page still holds the box at it: once drawn the box is
    // the drawing's, and a box a grid or flex row stretches would hand a redraw the
    // row's height, a taller neighbour's.
    /** @param {typeof import("@observablehq/plot")} Plot @param {Function} body */
    paint(Plot, body) {
      const width = Math.round(this.clientWidth);
      const box = (this.#height ??= this.clientHeight);
      let drawn = this.plot(Plot, body, width, box);
      this.drawing.replaceChildren(drawn.built);
      // A legend Plot sets beside the drawing takes its own height, which only laying it
      // out says, so a chart with one is drawn again into the room the legend leaves.
      const legend = this.drawing.offsetHeight - box;
      if (legend > 0) {
        drawn = this.plot(Plot, body, width, box - legend);
        this.drawing.replaceChildren(drawn.built);
      }
      this.drawn = width;
      this.#read(drawn.reading);
    }

    // A new drawing's points. The reader stays on the point they were on, drawn again
    // where it now stands. A chart with none to read takes no Tab stop and no keys.
    /** @param {Reading | null} reading */
    #read(reading) {
      const at = this.#at;
      this.#reading = reading;
      this.#at = null;
      const points = reading?.points.length ?? 0;
      keeps(this, "tabindex", points ? "0" : null);
      this.lfCommands = reading && points ? this.#keys(reading) : null;
      commandsChanged(this);
      if (reading && at)
        this.#choose(reading.series[at.series]?.[at.n] ?? null, this.#by);
      else if (at) previewChanged(this);
    }

    // The arrows step along the series the points stand in, along the axis they stand
    // at, and across to the next series; Home and End reach a series' ends.
    /** @param {Reading} reading */
    #keys(reading) {
      const across = reading.axis === "y";
      const [back, ahead] = across
        ? ["ArrowUp", "ArrowDown"]
        : ["ArrowLeft", "ArrowRight"];
      const [before, after] = across
        ? ["ArrowLeft", "ArrowRight"]
        : ["ArrowUp", "ArrowDown"];
      /** @type {[string, string, string, (from: Point | null) => Point | null][]} */
      const moves = [
        ["previous", "Previous point", back, (from) => step(reading, from, -1)],
        ["next", "Next point", ahead, (from) => step(reading, from, 1)],
        ["first", "First point", "Home", (from) => step(reading, from, "first")],
        ["last", "Last point", "End", (from) => step(reading, from, "last")],
      ];
      if (reading.series.length > 1)
        moves.push(
          [
            "previous-series",
            "Previous series",
            before,
            (from) => cross(reading, from, -1),
          ],
          ["next-series", "Next series", after, (from) => cross(reading, from, 1)],
        );
      return {
        title: "On a chart",
        rows: moves.map(([id, title, key, move]) => ({
          id: `chart.${id}`,
          title,
          keys: [key],
          repeat: key.startsWith("Arrow"),
          run: () => this.#choose(move(this.#at), "key"),
        })),
      };
    }

    // Puts the reader on `point`, or on none: its ring, a rule from it to the axis it
    // stands at, and the preview read again. A key's step says where it landed.
    /** @param {Point | null} point @param {By} by */
    #choose(point, by) {
      this.#by = by;
      if (point === this.#at) return;
      this.#at = point;
      const reading = this.#reading;
      if (reading) {
        const { ring } = reading;
        keeps(ring, "display", point ? null : "none");
        if (point) {
          keeps(ring, "transform", `translate(${point.x} ${point.y})`);
          const rule = /** @type {SVGLineElement} */ (ring.firstElementChild);
          const across = reading.axis === "y";
          keeps(rule, "x2", String(across ? point.drawn.left - point.x : 0));
          keeps(rule, "y2", String(across ? 0 : point.drawn.bottom - point.y));
        }
      }
      previewChanged(this);
      if (by === "key" && point) {
        const { name, detail } = sayPoint(point);
        announce([name, ...detail].join(", "));
      }
    }

    // The pointer or finger left the drawing. A point the keyboard reached stays.
    #leave() {
      this.#over = false;
      if (this.#by === "pointer") this.#choose(null, "pointer");
    }

    /** @param {typeof import("@observablehq/plot")} Plot @param {Function} body
     * @param {number} width @param {number} height */
    plot(Plot, body, width, height) {
      const options = drawOptions(body, Plot, width, Math.max(1, height));
      const points = readPoints(Plot, options.marks);
      /** @type {HTMLElement | SVGSVGElement} */
      let built = Plot.plot(options);
      // With a legend, Plot returns a <figure> holding it and the drawing. The page gives
      // its own figures margins and reads them as blocks a comment can stand on, and this
      // one is neither: the chart is the comment target and its box is the widget's. So
      // it becomes a plain box, keeping the class Plot styles it by.
      if (built.matches("figure")) {
        const box = document.createElement("div");
        box.className = built.classList.value;
        box.append(...built.childNodes);
        built = box;
      } else {
        // Plot's pointer reports what it points at by dispatching `input` on its figure,
        // for a notebook's viewof. On a page that is an input the user never gave, and the
        // runtime reads every `input` as the user's own, dropping a delayed move it was
        // holding. A figure turned into a box above is detached, so only this one speaks.
        built.dispatchEvent = () => true;
      }
      // The drawing is the <svg> carrying the author's ariaLabel: a legend Plot puts beside
      // it is an <svg> too, a colour ramp one of its own.
      const drawing = [built, ...built.children].find((node) =>
        node.matches("svg[aria-label]"),
      );
      // The drawing is one picture and takes a whole-widget comment, so nothing inside
      // it needs to be reachable on its own. `role="img"` closes the tree under it, and
      // Plot names every group inside — `aria-label="bar"`, `"x-axis tick label"` — on
      // `<g>` elements carrying no role, which axe reports as a serious WCAG failure.
      // Kept as data, because what Plot calls each group is the only thing that names
      // one: it is how a test asks for the x axis's words.
      for (const named of built.querySelectorAll("g")) {
        const label = named.getAttribute("aria-label");
        if (label === null) continue;
        named.dataset.lfPart = label;
        named.removeAttribute("aria-label");
      }
      if (!drawing) throw new Error("Plot did not draw its labelled SVG");
      drawing.setAttribute("role", "img");
      // Dependency defaults join the same tier as widget defaults. Leaf's chart
      // face and paper remain stylesheet-owned; authored Plot style options keep
      // their inline priority, including legend styles.
      for (const style of built.querySelectorAll("style"))
        style.textContent = inBaseLayer(style.textContent);
      // Plot writes a mark's `title` channel as each shape's <title>, the platform's
      // tooltip, which would stand beside the preview that says it.
      for (const title of drawing.querySelectorAll("title")) title.remove();
      const ring = document.createElementNS(SVG, "g");
      ring.setAttribute("class", "lf-chart-at");
      ring.setAttribute("display", "none");
      const dot = document.createElementNS(SVG, "circle");
      dot.setAttribute("r", "4");
      ring.append(document.createElementNS(SVG, "line"), dot);
      drawing.append(ring);
      return {
        built,
        reading: {
          ...points.done(),
          svg: /** @type {SVGSVGElement} */ (drawing),
          ring,
        },
      };
    }
  },
);
