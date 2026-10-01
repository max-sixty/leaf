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
 * reads it to fit its ticks to the room. The height is stated (x-height, or the
 * occurrence's data-height, painted as data-lf-height), and the page lays that box out
 * before the drawing arrives, so the drawing and any legend Plot sets beside it are
 * drawn to fill it and move nothing below it. Its type and ink are the theme's, and so
 * are its series colours, because Plot takes `var(--series-N)` wherever it takes a colour. A user
 * who cannot see it hears Plot's `ariaLabel` in its place. It is one comment target,
 * through `x-visual: whole`. And a chart that cannot draw says why over its own source.
 *
 * The vendored bundle loads once, on the first draw rather than with this module: a chart
 * in a shut panel has no box, so measure holds its draw, and the 384KB bundle waits with
 * it instead of loading in front of a user who never opens that panel. */
import {
  bodyText,
  cancelRender,
  failSoft,
  measure,
  nextRender,
  once,
  sizeObserver,
  widgetController,
} from "/runtime/widget-api.js";

let plotReady;
const loadPlot = () => (plotReady ??= import("/vendor/plot.esm.js"));

/* The body as a function of Plot and the width, which returns the chart's options. The
 * newline before the closing parenthesis ends a trailing line comment. */
function compile(source) {
  try {
    return new Function("Plot", "width", `"use strict";\nreturn (\n${source}\n);`);
  } catch (err) {
    if (!(err instanceof SyntaxError)) throw err;
    throw new Error(
      `the body is a JavaScript expression for Plot.plot's options, and it does not parse: ${err.message}`,
    );
  }
}

/* The options one drawing is made from, made afresh for each so that no mark Plot has
 * already rendered is handed to it a second time. */
function drawOptions(body, Plot, width, height) {
  const spec = body(Plot, width);
  // Plot's own examples end in Plot.plot(...), which returns the drawing rather than
  // its options, at a width the body chose.
  if (spec instanceof Node)
    throw new Error(
      "give the options rather than Plot.plot(...): lf-chart calls Plot.plot itself, at the width it has",
    );
  if (spec === null || typeof spec !== "object" || Array.isArray(spec))
    throw new Error("the body gives one object: the options Plot.plot takes");
  if (!spec.ariaLabel)
    throw new Error(
      "give Plot an ariaLabel: it is what a user who cannot see the chart hears",
    );
  if ("height" in spec)
    throw new Error(
      "state the chart's height as data-height on the element rather than in the options: the page holds that box before the chart draws",
    );
  return { ...spec, width, height };
}

customElements.define(
  "lf-chart",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      // A chart is drawn to the room it has, so the first draw waits for a box. On the
      // page that box is there already and this settles inside the upgrade, holding the
      // view restore and the first anchor pass until the drawing is in and the page's
      // geometry is final. In a shut panel there is no box at all and measure holds the
      // draw instead of the page.
      measure(this, () => widgetController(this).present(this.draw()));
    }

    disconnectedCallback() {
      this.watching?.disconnect();
      cancelRender(this.paintFrame);
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
        this.drawing = document.createElement("div");
        this.drawing.className = "lf-chart-drawing";
        this.replaceChildren(this.drawing);
        this.paint(Plot, body);
        this.classList.add("lf-rendered");
        // Only the width is watched, and only when it lands on a new whole pixel; the
        // height is stated and stays. The redraw is scheduled after ResizeObserver
        // delivery, so the layout a paint reads never lands inside the delivery cycle
        // that asked for it, which the browser reports as undelivered notifications.
        let pending = this.drawn;
        this.watching = sizeObserver(() => {
          const width = Math.round(this.clientWidth);
          if (!width || width === pending) return;
          pending = width;
          if (this.paintFrame) return;
          this.paintFrame = nextRender(() => {
            this.paintFrame = 0;
            if (!this.isConnected || pending === this.drawn) return;
            try {
              this.paint(Plot, body);
            } catch (err) {
              this.watching.disconnect();
              failSoft(this, err, source);
            }
          });
        });
        this.watching.observe(this);
      } catch (err) {
        failSoft(this, err, source);
      }
    }

    paint(Plot, body) {
      const width = Math.round(this.clientWidth);
      const box = Number(this.getAttribute("data-lf-height"));
      this.drawing.replaceChildren(this.plot(Plot, body, width, box));
      // A legend Plot sets beside the drawing takes its own height, which only laying it
      // out says, so a chart with one is drawn again into the room the legend leaves.
      const legend = this.drawing.offsetHeight - box;
      if (legend > 0)
        this.drawing.replaceChildren(this.plot(Plot, body, width, box - legend));
      this.drawn = width;
    }

    plot(Plot, body, width, height) {
      let built = Plot.plot(drawOptions(body, Plot, width, Math.max(1, height)));
      // With a legend, Plot returns a <figure> holding it and the drawing. The page gives
      // its own figures margins and reads them as blocks a comment can stand on, and this
      // one is neither: the chart is the comment target and its box is the widget's. So
      // it becomes a plain box, keeping the class Plot styles it by.
      if (built.matches("figure")) {
        const box = document.createElement("div");
        box.className = built.getAttribute("class");
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
      for (const named of built.querySelectorAll("g[aria-label]")) {
        named.dataset.lfPart = named.getAttribute("aria-label");
        named.removeAttribute("aria-label");
      }
      drawing.setAttribute("role", "img");
      // Plot styles its legends and its paper from a <style> of its own, unlayered, and
      // every theme rule sits in a cascade layer, which loses to any unlayered rule however
      // specific. So the page's face and paper are set on those elements directly, where
      // the author's own `style` has not set them: Plot's legends would stay in its system
      // face, and its halos and tips would be filled white on a dark page.
      for (const legend of built.querySelectorAll(
        '[class$="-swatches"], [class*="-swatches "]',
      ))
        legend.style.fontFamily ||= "inherit";
      if (!drawing.style.getPropertyValue("--plot-background"))
        drawing.style.setProperty("--plot-background", "var(--paper)");
      return built;
    }
  },
);
