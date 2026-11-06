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
 * how): the point nearest a resting pointer or a held finger, by Plot's pointer's rule,
 * or, with the chart focused, the arrow keys stepping along a series and across
 * to the next, Home and End to its ends. A redraw keeps the reader on their datum where
 * the new drawing still holds it. The point the reader is on wears a ring, with a rule
 * to the axis it stands at, and its words stand beside it in the page's preview
 * (`lfPreview`), which the chart reads again as the aim moves to another point, each a
 * new aim (`previewChanged` with `aim`), so a point the pointer or a key reaches after
 * Escape put the preview away shows its own. The ring goes when the aim leaves, the
 * pointer by leaving the drawing and the keyboard by leaving the chart, and when the
 * page puts the preview away (`PREVIEW_ENDED`), as Escape does and as the next touch
 * does after a held finger lifts. A finger slides across the drawing to read along it,
 * and scrolls the page up and down it.
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
  PREVIEW_ENDED,
  PendingTaskEvent,
  announce,
  beginWalk,
  bodyText,
  commandsChanged,
  keeps,
  layoutPx,
  listWalkPosition,
  whileConnected,
  failSoft,
  inBaseLayer,
  measure,
  nextRender,
  once,
  previewChanged,
  sizeObserver,
} from "/runtime/portable-api.js";
import {
  cross,
  nearest,
  readPoints,
  sameDatum,
  sayPoint,
  step,
} from "./chart-points.js";

const SVG = "http://www.w3.org/2000/svg";

/** @typedef {import("./chart-points.js").Point} Point
 * @typedef {import("./chart-points.js").PlotBundle} PlotBundle
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
/** @param {Function} body @param {PlotBundle["Plot"]} Plot
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
    // What each drawing is drawn from and where a failed one goes (`draw`), the height
    // every drawing takes, read at the first, and the height a legend beside it took
    // when last laid out, with the watch on the drawing that holds it (`paint`).
    /** @type {{bundle: PlotBundle, body: Function, failed: (err: unknown) => void} | null} */
    #source = null;
    /** @type {number | undefined} */
    #height;
    #legend = 0;
    /** @type {ResizeObserver | null} */
    #legendWatch = null;
    drawing = document.createElement("div");
    /** @type {number | undefined} */
    drawn;
    // The points the drawing showing says, the one the reader is on and what brought
    // them there, whether a pointer or finger is over the drawing, the point the keys
    // step on from once Escape has put the keyboard's reading away, and the one the
    // pointer rests on whose reading the page put away, quiet until the pointer reaches
    // another.
    /** @type {Reading | null} */
    #reading = null;
    /** @type {Point | null} */
    #at = null;
    /** @type {By} */
    #by = "pointer";
    #over = false;
    /** @type {Point | null} */
    #place = null;
    /** @type {Point | null} */
    #away = null;
    // What the chart last declared to the page's preview, which names the reading a
    // preview that ends had (`PREVIEW_ENDED`), and where a finger last touched the
    // drawing.
    /** @type {object | null} */
    #declared = null;
    /** @type {[number, number] | null} */
    #finger = null;

    // What the point the reader is on says, standing above its ring, on every route,
    // in a new object each time. Off a point the chart adds nothing, so what holds it
    // may say its own. A hold reads the point nearest where the finger is, whatever
    // the preview before it left: the press that starts a hold puts away the last
    // one's preview, and its point with it.
    /** @param {"pointer" | "focus" | "hold"} route */
    lfPreview = (route) => {
      if (route === "hold" && this.#finger) {
        const point = this.#pointAt(...this.#finger);
        this.#by = "pointer";
        if (point !== this.#at) this.#mark(point);
      }
      const ring = this.#reading?.ring.lastElementChild;
      this.#declared =
        this.#at && ring
          ? { ...sayPoint(this.#at), at: ring.getBoundingClientRect() }
          : null;
      return this.#declared;
    };

    connectedCallback() {
      if (!once(this)) return;
      whileConnected(this, (signal) => {
        // The pointer and a finger read the point nearest them on the drawing, by
        // Plot's pointer's rule, and nothing elsewhere, as over a legend: one reading
        // for each move, each point reached a new aim. A mouse carrying a press is
        // dragging. A pointer that picks nothing leaves the keyboard's point where it
        // was, and one still on the point whose reading the page put away reads nothing.
        const aim = (/** @type {PointerEvent} */ event) => {
          const reading = this.#reading;
          if (event.pointerType === "mouse" && event.buttons) return;
          if (!reading || !(event.target instanceof Node)) return this.#leave();
          if (!reading.svg.contains(event.target)) return this.#leave();
          if (!reading.svg.getScreenCTM()) return;
          this.#over = true;
          if (event.pointerType === "touch")
            this.#finger = [event.clientX, event.clientY];
          const point = this.#pointAt(event.clientX, event.clientY);
          if (point && point === this.#away) return;
          this.#away = null;
          if (point || this.#by === "pointer") this.#choose(point, "pointer", true);
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
        // Focus the browser shows lands the reader on a point, the one they are on or
        // the first, which the arrows then step from: the keyboard's from then on.
        this.addEventListener(
          "focus",
          () => {
            if (this.#reading && this.matches(":focus-visible"))
              this.#choose(this.#at ?? step(this.#reading, null, "first"), "focus");
          },
          { signal },
        );
        // Leaving the chart ends the keyboard's hold on its point.
        this.addEventListener(
          "blur",
          () => {
            this.#place = null;
            this.#choose(this.#over ? this.#at : null, "pointer");
          },
          { signal },
        );
        // The ring marks the point the page's preview says, so it comes off when the
        // page puts the preview away, whatever puts it away: the pointer leaving the
        // window from it, the next touch after a held finger lifts, Escape. A redraw
        // then has no point to read again, and the next aim reads from where it lands,
        // the keys stepping on from the point put away while the chart has focus, and a
        // pointer still over the drawing reading nothing until it reaches another point.
        // It comes off once the task that put the preview away is done, and only if the
        // reading that ended is still the chart's last and its point still the reader's:
        // a Tab that puts a resting pointer's preview away lands focus here in the same
        // task, whose preview reads the point again, and the keyboard takes it on.
        this.addEventListener(
          PREVIEW_ENDED,
          (event) => {
            const { declared } = /** @type {CustomEvent} */ (event).detail;
            const read = this.#at;
            nextRender(() => {
              if (!declared || declared !== this.#declared || this.#at !== read) return;
              this.#declared = null;
              if (this.matches(":focus")) this.#place = read;
              if (this.#over) this.#away = read;
              this.#choose(null, "pointer");
            });
          },
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
      let stop = () => {};
      // A failed drawing ends the watch: the failure replaced the drawing, and a chart
      // that returns to the page keeps showing it rather than drawing again.
      /** @param {unknown} err */
      const failed = (err) => {
        stop();
        this.#legendWatch?.disconnect();
        this.#read(null);
        failSoft(this, err, source);
      };
      try {
        source = bodyText(this);
        const body = compile(source);
        // The room it is drawn for, as the browser lays it out: the width the observer
        // last delivered, and the height it delivered before the first drawing, read
        // off its entries rather than off the box, so a page of charts resized together
        // is laid out once rather than once for each chart's read after another's
        // drawing. Only the width is watched, and only when it lands on a new whole
        // pixel; the height is the first drawing's and stays. A redraw is drawn during
        // the delivery, so labels fit the new width in the same paint, and a width
        // delivered while the first drawing was under way is drawn once it is in.
        /** @type {DOMRectReadOnly | undefined} */
        let room;
        /** @type {(value?: unknown) => void} */
        let arrived = () => {};
        const delivered = new Promise((resolve) => (arrived = resolve));
        let resized = () => {};
        stop = whileConnected(this, () => {
          const watching = sizeObserver((entries) => {
            const rect = entries.at(-1)?.contentRect;
            if (!rect?.width) return;
            room = rect;
            arrived();
            resized();
          });
          watching.observe(this);
          return () => watching.disconnect();
        });
        this.#source = { bundle: await loadPlot(), body, failed };
        await delivered;
        const { width, height } = /** @type {DOMRectReadOnly} */ (room);
        // The box each drawing goes in. A redraw replaces what is in it and nothing else,
        // because by then the runtime may have hung its own words on the widget — the
        // line saying a comment stands on this chart is a child of the element. It holds
        // the height the page held the chart at, so the chart's box keeps it whatever a
        // drawing measures, and only its width moves the observer.
        this.#height = height;
        this.drawing.className = "lf-chart-drawing";
        this.drawing.style.blockSize = layoutPx(height);
        this.replaceChildren(this.drawing);
        await this.paint(Math.round(width));
        this.classList.add("lf-rendered");
        resized = () => {
          const next = Math.round(room?.width ?? 0);
          if (next !== this.drawn) this.paint(next).catch(failed);
        };
        resized();
      } catch (err) {
        failed(err);
      }
    }

    // Drawn to the box's height as well as its width. The height is the first
    // delivery's, while the page still holds the box at it: once drawn the box is the
    // drawing's, and a box a grid or flex row stretches would hand a redraw the row's
    // height, a taller neighbour's. A legend Plot sets beside the drawing takes the
    // height its swatches wrap to in the fonts they are set in, which only laying it out
    // says. So a drawing with a legend is watched while it shows, and whenever the
    // legend's height changes, with a new width or a font that arrives late, the chart
    // draws again into the room the legend leaves, in the delivery that measured it, so
    // the frame that shows the new legend shows the drawing fitted to it; a chart with
    // none reads nothing. The drawing settles once its legend has the room it
    // measures, and a failed redraw fails as the drawing does. A hidden drawing measures
    // nothing.
    /** @param {number} width @returns {Promise<void>} */
    async paint(width) {
      const source = this.#source;
      if (!source) return;
      this.#legendWatch?.disconnect();
      this.#legendWatch = null;
      const room = (this.#height ?? 0) - this.#legend;
      const drawn = this.plot(source.bundle, source.body, width, room);
      this.drawing.replaceChildren(drawn.built);
      this.drawn = width;
      this.#read(drawn.reading);
      if (!drawn.legend) return;
      /** @type {Promise<void>} */
      const measured = new Promise((settled) => {
        const watch = (this.#legendWatch = sizeObserver(([entry]) => {
          const height = entry?.contentRect.height;
          const legend = height ? Math.max(0, Math.round(height - room)) : this.#legend;
          if (legend !== this.#legend) {
            this.#legend = legend;
            this.paint(width).catch(source.failed);
          }
          settled();
        }));
        watch.observe(drawn.built);
      });
      return measured;
    }

    // A new drawing's points. The reader stays on the point they were on, drawn again
    // where it now stands. A chart with none to read takes no Tab stop and no keys.
    /** @param {Reading | null} reading */
    #read(reading) {
      const at = this.#at;
      this.#reading = reading;
      this.#at = null;
      this.#place = reading && this.#place ? sameDatum(reading, this.#place) : null;
      this.#away = reading && this.#away ? sameDatum(reading, this.#away) : null;
      const points = reading?.points.length ?? 0;
      keeps(this, "tabindex", points ? "0" : null);
      this.lfCommands = reading && points ? this.#keys(reading) : null;
      commandsChanged(this);
      if (reading && at) this.#choose(sameDatum(reading, at), this.#by);
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
          run: () => this.#step(move(this.#at ?? this.#place)),
        })),
      };
    }

    // Puts the reader on `point`, or on none: its ring, a rule from it to the axis it
    // stands at, and the preview read again, as a new aim where the user's own move
    // reached the point (`aim`), which shows its preview though Escape put the last
    // one away.
    /** @param {Point | null} point @param {By} by @param {boolean} [aim] */
    #choose(point, by, aim = false) {
      this.#by = by;
      if (point === this.#at) return;
      this.#mark(point);
      previewChanged(this, { aim: aim && point !== null });
    }

    // The point nearest a place in the window, by Plot's pointer's rule, or none.
    /** @param {number} x @param {number} y */
    #pointAt(x, y) {
      const reading = this.#reading;
      const screen = reading?.svg.getScreenCTM();
      if (!reading || !screen) return null;
      const at = new DOMPoint(x, y).matrixTransform(screen.inverse());
      return nearest(reading, at.x, at.y);
    }

    // The reader on `point`, or on none, and the ring on it.
    /** @param {Point | null} point */
    #mark(point) {
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
    }

    // A key's step is a walk along the reading's series, a new aim wherever it lands; a
    // redraw that keeps the reader on their point is none. It says where it landed:
    // the point's words, then its place in its series.
    /** @param {Point | null} point */
    #step(point) {
      this.#place = null;
      this.#choose(point, "key", true);
      const reading = this.#reading;
      if (!point || !reading) return;
      const series = reading.series[point.series] ?? [];
      const position = beginWalk("chart", "Point", () =>
        listWalkPosition(series, this.#at),
      );
      const { name, detail } = sayPoint(point);
      announce([name, ...detail, position].filter(Boolean).join(", "));
    }

    // The pointer or finger left the drawing. A point the keyboard reached stays, and so
    // does a held finger's once it lifts, whose preview stands until the next touch
    // (`data-lf-held`, preview.js), until the page puts the preview away
    // (`PREVIEW_ENDED`); back on the drawing, it reads from where it comes. The
    // preview of a point takes no pointer (preview.js), so the pointer under it is
    // still on the drawing.
    #leave() {
      this.#over = false;
      this.#away = null;
      this.#finger = null;
      if (this.#by !== "pointer" || this.hasAttribute("data-lf-held")) return;
      this.#choose(null, "pointer");
    }

    /** @param {PlotBundle} bundle @param {Function} body @param {number} width
     * @param {number} height */
    plot(bundle, body, width, height) {
      const { Plot } = bundle;
      const options = drawOptions(body, Plot, width, Math.max(1, height));
      const points = readPoints(bundle, options.marks);
      /** @type {HTMLElement | SVGSVGElement} */
      let built = Plot.plot({ ...options, marks: [options.marks, points.marks] });
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
        // holding. Leaf gives Plot no tips, so only a pointer an author draws speaks, and
        // only its `input` is held back: any other event dispatched at the drawing, as
        // a script's long press over empty space, reaches the page. A figure turned into
        // a box above is detached, so only this one speaks.
        built.dispatchEvent = (event) =>
          event.type === "input" || Element.prototype.dispatchEvent.call(built, event);
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
        legend: built !== drawing,
        reading: {
          ...points.done(),
          svg: /** @type {SVGSVGElement} */ (drawing),
          ring,
        },
      };
    }
  },
);
