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
 * What the host adds is what a drawing needs from the page it sits in. It is drawn for
 * the room it has and drawn again when that room changes, since a drawing scaled into a
 * new box takes its labels below legibility with it: the width is the host's, and the
 * body reads it to fit its ticks to the room. The height is the box's too: on a Leaf
 * page it is stated (`height`, or the occurrence's data-height), and the theme
 * holds the box at it before the drawing arrives, so the drawing and any legend Plot
 * sets beside it are drawn to fill it and move nothing below it. Its type and ink are
 * the theme's, and so are its series colours, because Plot takes `var(--lf-series-N)`
 * wherever it takes a colour. A user who cannot see it hears Plot's `ariaLabel` in its
 * place. A comment takes the whole chart, or the point the reader is on (below) as a
 * part of it named by its datum. And a chart that cannot draw says why over its own
 * source.
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
 * page puts the preview away (`PREVIEW_ENDED`), as Escape and a press do and as the
 * next touch does after a held finger lifts. A finger slides across the drawing to read
 * along it, and scrolls the page up and down it.
 *
 * Crossing the drawing where no point is within reach keeps the reading and its ring,
 * and the next point within reach takes its place. Plot's own tip clears in empty
 * space; this one stays because it can be read: the preview takes no pointer and
 * stands over the drawing (preview.js), so a pointer moving toward it to read it
 * crosses the drawing's empty space, and clearing there would take the reading away
 * from under the reader's eye.
 *
 * A comment on a point is about the point the reader is on. Leaf's aim and a pointed
 * comment take the point the pointer is on wherever it stands in the drawing: the one
 * its ring is on, or the one it rests on whose reading Escape or a press put away. ⌥
 * alone leaves the reading standing (preview.js). Focus on the chart takes the point
 * the ring is on, so the keys reach one too, and the whole chart once Escape has put
 * the ring away, as does ⌥ where no point is within reach or over a legend. The comment
 * names its point by its datum (chart-points.js, `datumOf`). Leaf marks the point on
 * the bar, bin or cell Plot drew for it, as it marks any drawing's shape, and on a ring
 * the chart draws round a dot or a line's vertex, and travels to it. The chart is where
 * Leaf puts the reader for a point, its reading moved to that point (`focus`), as
 * travel to a comment on it and the hand back from one do. So Leaf learns of only
 * those points (`registerVisualParts`, with `find` and `at`), and the cost grows with
 * the comments rather than the data: a drawing holds no element for each dot, a line
 * none at all, and a list of every point would cost Leaf's picker a hint for each and
 * offer the reader nothing they could aim at, so the chart lists none. A comment whose
 * datum the drawing lacks stands on the whole chart, named by its datum's values, since
 * a chart in a shut tab has drawn nothing yet and one whose body reads its width may
 * draw a datum at one width and not another.
 *
 * The vendored bundle loads once, on the first draw rather than with this module: a chart
 * in a shut panel has no box, so its draw waits for one, and the 384KB bundle waits with
 * it instead of loading in front of a user who never opens that panel.
 *
 * It imports only the helpers that load in any document, so a plain HTML page that maps
 * `/runtime/` and `/vendor/` draws it too, into the box that page gives it. A
 * Leaf page hears its drawing and its refusals from outside it: each drawing under way
 * is a `pending-task` event, whose rejection is that drawing's refusal, which the page
 * shows in the chart's place and reports to the author.
 *
 * What it does with the page it writes in the browser's own terms: its own
 * ResizeObserver and frames, its own live region for a key's step, and its room before
 * it draws held by its own stylesheet (chart.css). */
import {
  PREVIEW_ENDED,
  PendingTaskEvent,
  beginWalk,
  commandsChanged,
  frameFor,
  previewChanged,
  registerVisualParts,
} from "/runtime/portable-api.js";
import {
  cross,
  datumOf,
  datumPoint,
  datumWords,
  nearest,
  readPoints,
  sayPoint,
  shapeOf,
  step,
} from "./chart-points.js";

const SVG = "http://www.w3.org/2000/svg";
// The prefix of a point's id as a comment target, which the registry declares.
const POINT = "point:";

/** @typedef {import("./chart-points.js").Point} Point
 * @typedef {import("./chart-points.js").PlotBundle} PlotBundle
 * @typedef {import("./chart-points.js").Reading & {svg: SVGSVGElement, ring: SVGGElement, marks: SVGGElement, aim: SVGCircleElement}} Reading
 * @typedef {{id: string, element: Element, label: string}} Part
 * @typedef {"pointer" | "focus" | "key"} By */

// A ring round a dot or a line's vertex, wider than the chart's own ring, where Leaf
// marks the point for its aim and a comment on it.
/** @param {SVGCircleElement} mark @param {Point} point */
function ringRound(mark, point) {
  mark.setAttribute("cx", String(point.x));
  mark.setAttribute("cy", String(point.y));
}

// What a point says, on one line, as a comment on it is named.
/** @param {Point} point */
const pointWords = (point) => {
  const { name, detail } = sayPoint(point);
  return [name, ...detail].filter(Boolean).join(", ");
};

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
    // What each drawing is drawn from (`draw`), the height every drawing takes, read at
    // the first, and the height a legend beside it took when last laid out, with the
    // watch on the drawing that holds it (`paint`).
    /** @type {{bundle: PlotBundle, body: Function} | null} */
    #source = null;
    /** @type {number | undefined} */
    #height;
    #legend = 0;
    /** @type {ResizeObserver | null} */
    #legendWatch = null;
    // The room the chart has, as the browser last laid it out, and what a delivery of
    // it does: the first one with a width starts the first drawing, which a chart in a
    // shut panel waits for with its bundle, and later ones draw again (`draw`). The
    // watch runs while the chart stands in the page, and a failed chart watches nothing.
    /** @type {DOMRectReadOnly | undefined} */
    #room;
    #heard = () => {
      // Paper prints a shut panel open, and a box laid out for a sheet is not the room
      // the user will see, so the first drawing waits for the screen's.
      if (matchMedia("print").matches) return;
      this.dispatchEvent(new PendingTaskEvent(this.draw()));
    };
    #watch = new ResizeObserver((entries) => {
      const rect = entries.at(-1)?.contentRect;
      if (!rect?.width) return;
      this.#room = rect;
      this.#heard();
    });
    #failed = false;
    drawing = document.createElement("div");
    // Where a key's step says its point to a listener: the chart's own live region.
    #says = document.createElement("div");
    /** @type {number | undefined} */
    drawn;
    // The points the drawing showing says, the one the reader is on and what brought
    // them there, whether a pointer or finger is over the drawing, the point the keys
    // step on from once Escape has put the keyboard's reading away or focus has left
    // the chart, and the one the
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
    // What the page's preview last read of the chart, while it stands, which names the
    // reading a preview that ends had (`PREVIEW_ENDED`), and how many times a finger
    // has pressed on the chart.
    /** @type {object | null} */
    #declared = null;
    #presses = 0;
    // The points Leaf has named by id in the drawing showing, each with its point and
    // the mark drawn at it (`#find`), or null for one the drawing lacks; whether Leaf
    // has asked for any, in this drawing or before it; the registration Leaf names them
    // through; and whether the next rendering pass tells Leaf they changed.
    /** @type {Map<string, {point: Point, part: Part} | null>} */
    #marks = new Map();
    #asked = false;
    /** @type {{update: () => void} | null} */
    #parts = null;
    #telling = false;

    // What the point the reader is on says, standing above its ring, on every route,
    // in a new object each time. Off a point the chart adds nothing, so what holds it
    // may say its own. Only the page's preview, which names its route, reads a reading
    // that stands.
    /** @param {"pointer" | "focus" | "hold"} [route] */
    lfPreview = (route) => {
      const ring = this.#reading?.ring.lastElementChild;
      const declared =
        this.#at && ring
          ? { ...sayPoint(this.#at), at: ring.getBoundingClientRect() }
          : null;
      if (route) this.#declared = declared;
      return declared;
    };

    // The chart hears its own events for as long as it lives, so the listeners go with it.
    constructor() {
      super();
      // The pointer and a finger read the point nearest them on the drawing, by
      // Plot's pointer's rule, and nothing elsewhere, as over a legend: one reading
      // for each move, each point reached a new aim. A mouse carrying a press is
      // dragging. A pointer that picks nothing keeps the reading it had, and one
      // still on the point whose reading the page put away reads nothing.
      const aim = (/** @type {PointerEvent} */ event) => {
        const reading = this.#reading;
        if (event.pointerType === "mouse" && event.buttons) return;
        if (!reading || !(event.target instanceof Node)) return this.#leave();
        if (!reading.svg.contains(event.target)) return this.#leave();
        if (!reading.svg.getScreenCTM()) return;
        this.#over = true;
        const point = this.#pointAt(event.clientX, event.clientY);
        if (!point || point === this.#away) return;
        this.#away = null;
        this.#choose(point, "pointer", true);
      };
      // A mouse reads where it moves to, so a drawing that arrives under a still one
      // says nothing; a finger, which lands before it moves, reads where it lands. A
      // finger's press is a new aim even on the point it held last, heard after the
      // page has put the last hold's preview away (preview.js listens first).
      this.addEventListener("pointermove", aim, { passive: true });
      this.addEventListener(
        "pointerover",
        (event) => {
          if (event.pointerType !== "mouse") aim(event);
        },
        { passive: true },
      );
      this.addEventListener(
        "pointerdown",
        (event) => {
          if (event.pointerType === "touch") this.#presses += 1;
        },
        { passive: true },
      );
      this.addEventListener("pointerleave", () => this.#leave());
      // Focus the browser shows lands the reader on a point, the one they are on, the
      // one the keys left them on, or the first, which the arrows then step from: the
      // keyboard's from then on. Focus Leaf puts on a point has put them on it already
      // (`#focusOn`).
      this.addEventListener("focus", () => {
        if (this.#reading && this.matches(":focus-visible"))
          this.#choose(
            this.#at ?? this.#place ?? step(this.#reading, null, "first"),
            "focus",
          );
      });
      // Leaving the chart takes the ring off a point the keys hold, which stays the
      // point they step on from.
      this.addEventListener("blur", () => {
        if (this.#at && this.#by !== "pointer") this.#place = this.#at;
        this.#choose(this.#over ? this.#at : null, "pointer");
      });
      // The ring marks the point the page's preview says, so it comes off when the
      // page puts the preview away, whatever puts it away: the pointer leaving the
      // window from it, the next touch after a held finger lifts, Escape. A redraw
      // then has no point to read again, and the next aim reads from where it lands,
      // the keys stepping on from the point put away while the chart has focus, and a
      // pointer still over the drawing reading nothing until it reaches another point.
      // The reading that ended no longer stands, at once. Its ring comes off in the
      // next frame, once the task that put the preview away is done, and only if no
      // reading stands again by then, its point is still the reader's and no finger has
      // pressed since: a Tab that puts a resting pointer's preview away lands focus here
      // in the same task, whose preview reads the point again, and the keyboard takes it
      // on; the press that starts a second hold on a point puts the first hold's preview
      // away as the finger presses that point again. A press is an aim, not a reading:
      // a tap that ends without a hold leaves the ring to go with the finger (`#leave`).
      this.addEventListener(PREVIEW_ENDED, (event) => {
        const { declared } = /** @type {CustomEvent} */ (event).detail;
        if (!declared || declared !== this.#declared) return;
        this.#declared = null;
        const [read, presses] = [this.#at, this.#presses];
        requestAnimationFrame(() => {
          if (this.#declared || this.#at !== read || this.#presses !== presses) return;
          if (this.matches(":focus")) this.#place = read;
          if (this.#over) this.#away = read;
          this.#choose(null, "pointer");
          this.#placeAim();
        });
      });
    }

    // A chart is drawn to the room it has, so it watches its box while it stands in the
    // page, and the first box with a width starts the first drawing (`#heard`). In a
    // shut panel there is no box, and the drawing waits for one.
    connectedCallback() {
      // The chart lists no point for a reader to pick from a list: its own aim and keys
      // reach each point, and Leaf finds a comment's point by its id.
      this.#parts ??= registerVisualParts(this, () => [], {
        find: (id) => this.#find(id),
        at: (node) => this.#partAt(node),
        focus: (id) => this.#focusOn(id),
        label: (id) =>
          id.startsWith(POINT) ? datumWords(id.slice(POINT.length)) : null,
      });
      if (!this.#failed) this.#watch.observe(this);
    }

    disconnectedCallback() {
      this.#watch.disconnect();
    }

    // A move within the page is no departure, so the watch stays.
    connectedMoveCallback() {}

    async draw() {
      try {
        // The body is the <pre> the content model requires, less the blank lines and
        // trailing space that are the <pre>'s own layout.
        const pre = this.querySelector(":scope > pre");
        if (!pre) throw new Error("<lf-chart> has no <pre> holding its options");
        const body = compile(pre.textContent.replace(/^\n+/, "").trimEnd());
        // The room it is drawn for, as the browser lays it out: the width the observer
        // last delivered, and the height it delivered before the first drawing, read
        // off its entries rather than off the box, so a page of charts resized together
        // is laid out once rather than once for each chart's read after another's
        // drawing. Only the width is watched, and only when it lands on a new whole
        // pixel; the height is the first drawing's and stays. A redraw is drawn during
        // the delivery, so labels fit the new width in the same paint: it writes only
        // inside the drawing, whose height is fixed, so it moves no box the browser
        // watches. The first drawing lets go of the box the stylesheet held
        // (chart.css), which a row may stretch, and a box that moves above one the
        // browser just delivered is a ResizeObserver loop error, so the first drawing
        // waits for the frame after the delivery that started it, or for Plot if that
        // comes later. A width delivered while it was under way is drawn once it is in.
        const framed = new Promise((resolve) => {
          this.#heard = frameFor(this, () => resolve(undefined));
        });
        this.#heard();
        this.#source = { bundle: await loadPlot(), body };
        await framed;
        const { width, height } = /** @type {DOMRectReadOnly} */ (this.#room);
        // The box each drawing goes in. A redraw replaces what is in it and nothing else,
        // because by then the runtime may have hung its own words on the widget — the
        // line saying a comment stands on this chart is a child of the element. It holds
        // the height the page held the chart at, so the chart's box keeps it whatever a
        // drawing measures, and only its width moves the observer.
        this.#height = height;
        this.drawing.className = "lf-chart-drawing";
        this.drawing.style.blockSize = `${height}px`;
        this.#says.setAttribute("role", "status");
        this.replaceChildren(this.drawing, this.#says);
        await this.paint(Math.round(width));
        this.classList.add("lf-rendered");
        this.#heard = () => {
          const next = Math.round(this.#room?.width ?? 0);
          if (next !== this.drawn) this.#redraw(next);
        };
        this.#heard();
      } catch (err) {
        // The first drawing's failure is its pending task's: the page that heard the
        // task hears why it ended.
        this.#fail();
        throw err;
      }
    }

    // A failed drawing ends the watches, and the chart stays failed: one that leaves
    // the page and returns does not watch its room or draw again.
    #fail() {
      this.#failed = true;
      this.#watch.disconnect();
      this.#legendWatch?.disconnect();
      this.#read(null);
    }

    // A drawing after the first, for a new width or a legend's new height, made inside
    // the size delivery that asked for it. It is a pending task as the first is, so the
    // page that hears it hears why one that fails ended.
    /** @param {number} width */
    #redraw(width) {
      const painted = this.paint(width, true).catch((err) => {
        this.#fail();
        throw err;
      });
      this.dispatchEvent(new PendingTaskEvent(painted));
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
    // none reads nothing. The drawing settles in the frame after its legend has the
    // room it measures. A failed redraw fails as the drawing does. A hidden drawing
    // measures nothing. A drawing made inside a size delivery (`later`) is watched from
    // the next frame: the browser delivers no observation begun at the depth it is
    // delivering, and reports the one left over as a ResizeObserver loop.
    /** @param {number} width @param {boolean} [later] @returns {Promise<void>} */
    async paint(width, later = false) {
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
        const watch = (this.#legendWatch = new ResizeObserver(([entry]) => {
          const height = entry?.contentRect.height;
          const legend = height ? Math.max(0, Math.round(height - room)) : this.#legend;
          if (legend !== this.#legend) {
            this.#legend = legend;
            this.#redraw(width);
          }
          requestAnimationFrame(() => settled());
        }));
        if (!later) return watch.observe(drawn.built);
        requestAnimationFrame(() => {
          if (this.#legendWatch === watch) watch.observe(drawn.built);
        });
      });
      return measured;
    }

    // A new drawing's points. The reader stays on the point they were on, drawn again
    // where it now stands. A chart with none to read takes no Tab stop and no keys.
    // Leaf, where it has asked for a point, hears that it may ask again (`#find`).
    /** @param {Reading | null} reading */
    #read(reading) {
      const at = this.#at;
      /** @param {Point | null} point */
      const again = (point) =>
        reading && point ? datumPoint(reading, datumOf(point)) : null;
      this.#reading = reading;
      this.#at = null;
      this.#place = again(this.#place);
      this.#away = again(this.#away);
      this.#marks = new Map();
      if (this.#asked) this.#tell();
      const points = reading?.points.length ?? 0;
      if (points) this.tabIndex = 0;
      else this.removeAttribute("tabindex");
      this.lfCommands = reading && points ? this.#keys(reading) : null;
      commandsChanged(this);
      if (reading && at) this.#choose(again(at), this.#by);
      else if (at) previewChanged(this);
      this.#placeAim();
    }

    // The point an id names in the drawing showing, or null where the drawing has no
    // such datum: the bar, bin or cell Plot drew for it, or a ring drawn round it once
    // Leaf asks, which stays until the next drawing, as one does round a bar a render
    // transform has drawn again (`shapeOf`). Leaf asks for a comment's point each time
    // it places comments, and for the point `c` would comment on, the one the reader is
    // on, at each key step, which is found without a search of the drawing. So until
    // the next drawing a ring, unseen until Leaf strokes it, stands round each dot or
    // vertex the keys or a comment reached.
    /** @param {string} id */
    #find(id) {
      const reading = this.#reading;
      if (!id.startsWith(POINT)) return null;
      this.#asked = true;
      if (!reading) return null;
      let found = this.#marks.get(id);
      // A bar a render transform has drawn again, or joined to other data, is no longer
      // the point's (`shapeOf`), where a ring stays its point's.
      const { element } = found?.part ?? {};
      if (
        found &&
        element &&
        !reading.marks.contains(element) &&
        shapeOf(reading, found.point) !== element
      )
        found = undefined;
      if (found === undefined) {
        const datum = id.slice(POINT.length);
        const point =
          this.#at && datumOf(this.#at) === datum
            ? this.#at
            : datumPoint(reading, datum);
        found = point && { point, part: this.#mark(reading, point, id) };
        this.#marks.set(id, found);
      }
      return found?.part ?? null;
    }

    /** @param {Reading} reading @param {Point} point @param {string} id
     * @returns {Part} */
    #mark(reading, point, id) {
      let mark = shapeOf(reading, point);
      if (!mark) {
        const ring = document.createElementNS(SVG, "circle");
        ring.setAttribute("r", "7");
        ringRound(ring, point);
        reading.marks.append(ring);
        mark = ring;
      }
      return { id, element: mark, label: pointWords(point) };
    }

    // Puts the reader on the point an id names, as Leaf places focus on the chart for
    // it, travelling to a comment on it or handing the reader back from one: the chart
    // takes that focus itself, since a mark is no place to stand. The reading moves
    // now, since the chart may hold focus already, as it does when a link to another
    // of its points is followed, and focus it holds arrives as no new focus.
    /** @param {string} id */
    #focusOn(id) {
      const reading = this.#reading;
      const point =
        reading && id.startsWith(POINT)
          ? datumPoint(reading, id.slice(POINT.length))
          : null;
      if (point) this.#choose(point, "focus");
    }

    // The point a node of the chart stands for: for a node of the drawing, the point
    // the pointer aims at (`#placeAim`), and for the chart itself while it holds focus,
    // the point the reader is on. Leaf marks it on the bar Plot drew for it, or the
    // ring round it.
    /** @param {Element} node */
    #partAt(node) {
      const reading = this.#reading;
      const point =
        node === this
          ? this.matches(":focus")
            ? this.#at
            : null
          : reading?.svg.contains(node)
            ? (this.#at ?? this.#away)
            : null;
      if (!reading || !point) return null;
      return {
        id: `${POINT}${datumOf(point)}`,
        element: shapeOf(reading, point) ?? reading.aim,
        label: pointWords(point),
      };
    }

    // Tells Leaf, in the next frame, that a new drawing holds none of the marks it
    // found, so it finds them again.
    #tell() {
      if (this.#telling) return;
      this.#telling = true;
      requestAnimationFrame(() => {
        this.#telling = false;
        this.#parts?.update();
      });
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
      this.#at = point;
      const reading = this.#reading;
      if (reading) {
        const { ring } = reading;
        if (point) {
          ring.removeAttribute("display");
          ring.setAttribute("transform", `translate(${point.x} ${point.y})`);
          const rule = /** @type {SVGLineElement} */ (ring.firstElementChild);
          const across = reading.axis === "y";
          rule.setAttribute("x2", String(across ? point.drawn.left - point.x : 0));
          rule.setAttribute("y2", String(across ? 0 : point.drawn.bottom - point.y));
        } else ring.setAttribute("display", "none");
      }
      this.#placeAim();
      previewChanged(this, { aim: aim && point !== null });
    }

    // The mark round the point a pointer on the drawing aims at (`#partAt`): the
    // point it reads, or the one it rests on whose reading the page put away, as Escape
    // or a press does. It draws nothing of its own.
    #placeAim() {
      const reading = this.#reading;
      if (!reading) return;
      const point = this.#at ?? this.#away;
      const ringed = point && !shapeOf(reading, point) ? point : null;
      const { aim } = reading;
      if (ringed) {
        aim.removeAttribute("display");
        ringRound(aim, ringed);
      } else if (!aim.hasAttribute("display")) aim.setAttribute("display", "none");
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

    // A key's step is a walk along the reading's series, a new aim wherever it lands; a
    // redraw that keeps the reader on their point is none. It tells a listener where it
    // landed: the point's words, then its place in its series. The series' first and
    // last points bound the list, each by its shape, or by the drawing where the chart
    // draws no shape of the point's own, as a line's or a dot's.
    /** @param {Point | null} point */
    #step(point) {
      this.#place = null;
      this.#choose(point, "key", true);
      const reading = this.#reading;
      if (!point || !reading) return;
      const series = reading.series[point.series] ?? [];
      const ends = [series[0], series.at(-1)];
      const place = beginWalk(
        "chart-point",
        "Point",
        () => {
          const index = this.#at ? series.indexOf(this.#at) : -1;
          return index < 0
            ? null
            : {
                target: this.#at,
                position: index + 1,
                total: series.length,
                qualifier: "",
              };
        },
        {
          list: () => ends.map((end) => (end && shapeOf(reading, end)) ?? reading.svg),
        },
      );
      const { name, detail } = sayPoint(point);
      this.#says.textContent = [name, ...detail, place].filter(Boolean).join(", ");
    }

    // The pointer or finger left the drawing. A point the keyboard reached stays, and so
    // does one whose preview stands, which the page puts away, and the ring with it
    // (`PREVIEW_ENDED`), once the pointer is on neither the drawing nor the preview, or
    // at the next touch after a held finger lifts (preview.js); back on the drawing, it
    // reads from where it comes. A point no preview has shown yet goes with the pointer.
    #leave() {
      this.#over = false;
      this.#away = null;
      this.#placeAim();
      if (this.#by !== "pointer" || this.#declared) return;
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
      // The drawing is one picture, whose points the chart says itself (`lfPreview`,
      // `announce`), so nothing inside it needs to be reachable on its own to a screen
      // reader. `role="img"` closes the tree under it, and
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
        style.textContent = `@layer lf-base {\n${style.textContent}\n}`;
      // Plot writes a mark's `title` channel as each shape's <title>, the platform's
      // tooltip, which would stand beside the preview that says it.
      for (const title of drawing.querySelectorAll("title")) title.remove();
      // The marks of the points comments name (`#find`), and of the point the reader is
      // on (`#partAt`), which goes where the ring goes, under the ring.
      const marks = document.createElementNS(SVG, "g");
      marks.setAttribute("class", "lf-chart-marks");
      const aim = document.createElementNS(SVG, "circle");
      aim.setAttribute("class", "lf-chart-aim");
      aim.setAttribute("r", "7");
      aim.setAttribute("display", "none");
      marks.append(aim);
      const ring = document.createElementNS(SVG, "g");
      ring.setAttribute("class", "lf-chart-at");
      ring.setAttribute("display", "none");
      const dot = document.createElementNS(SVG, "circle");
      dot.setAttribute("r", "4");
      ring.append(document.createElementNS(SVG, "line"), dot);
      drawing.append(marks, ring);
      return {
        built,
        legend: built !== drawing,
        reading: {
          ...points.done(),
          svg: /** @type {SVGSVGElement} */ (drawing),
          ring,
          marks,
          aim,
        },
      };
    }
  },
);
