/* lf-chart: a chart drawn by Observable Plot, written in Plot's own API. The body is the
 * options object an author would hand `Plot.plot`, as JSON, and every mark, scale, format
 * and time zone in it is Plot's. Leaf keeps no chart vocabulary of its own for an author
 * to learn or for Plot to outgrow.
 *
 * JSON rather than a script, because a chart has to stand wherever markup does: in a page
 * with no module of its own, in a reply an agent sends into a thread, in an export. The one
 * thing JSON cannot say is a call, and Plot's marks and transforms are calls, so an object
 * whose only key names a Plot export is that call: {"Plot.barY": [data, options]} is
 * Plot.barY(data, options), its value always the argument list. The prefix keeps a field
 * or a domain value that happens to share a mark's name ("line", "text") from being read
 * as one. Plot draws strings as categories and coerces ISO strings to dates only on a scale
 * the options say is time ("utc", or "time" for the reader's own zone), so what a column
 * holds is the author's to say, in Plot's words.
 *
 * What the host adds is what a drawing needs from the page it sits in. It is drawn for the
 * room it has and drawn again when that room changes, since a drawing scaled into a new
 * box takes its labels below legibility with it: the width is the host's. Its type and ink
 * are the theme's, and so are its series colours, because Plot takes `var(--series-N)`
 * wherever it takes a colour. A user who cannot see it hears Plot's `ariaLabel` in its
 * place. It is one comment target, through `x-visual: whole`. And a chart that cannot
 * draw says why over its own source.
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

const CALL = "Plot.";

const XLINK = "http://www.w3.org/1999/xlink";

/* The body's JSON as the value it stands for, with each call made. */
function evaluate(Plot, value) {
  if (Array.isArray(value)) return value.map((item) => evaluate(Plot, item));
  if (value === null || typeof value !== "object") return value;
  const keys = Object.keys(value);
  if (keys.length === 1 && keys[0].startsWith(CALL)) {
    const name = keys[0].slice(CALL.length);
    const args = value[keys[0]];
    if (typeof Plot[name] !== "function") throw new Error(`Plot has no ${name}`);
    if (!Array.isArray(args))
      throw new Error(
        `${keys[0]} takes its arguments as a list: {"${keys[0]}": [...]}`,
      );
    return Plot[name](...args.map((arg) => evaluate(Plot, arg)));
  }
  return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [key, evaluate(Plot, item)]),
  );
}

function read(source) {
  let spec;
  try {
    spec = JSON.parse(source);
  } catch (err) {
    throw new Error(
      `the body is Plot's options as JSON, and it does not parse: ${err.message}`,
    );
  }
  if (spec === null || typeof spec !== "object" || Array.isArray(spec))
    throw new Error("the body is one JSON object: the options Plot.plot takes");
  if (!spec.ariaLabel)
    throw new Error(
      "give Plot an ariaLabel: it is what a user who cannot see the chart hears",
    );
  return spec;
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
        const spec = read(source);
        const Plot = await loadPlot();
        // The box each drawing goes in. A redraw replaces what is in it and nothing else,
        // because by then the runtime may have hung its own words on the widget — the
        // line saying a comment stands on this chart is a child of the element.
        this.drawing = document.createElement("div");
        this.drawing.className = "lf-chart-drawing";
        this.replaceChildren(this.drawing);
        this.paint(Plot, spec);
        this.classList.add("lf-rendered");
        // Only the width is watched, and only when it lands on a new whole pixel. The
        // redraw is scheduled after ResizeObserver delivery: painting changes the height,
        // and feeding that back through the same delivery cycle produces the browser's
        // "undelivered notifications" warning even though this observer ignores height.
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
              this.paint(Plot, spec);
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

    paint(Plot, spec) {
      const width = Math.round(this.clientWidth);
      // Evaluated afresh for each drawing, so no mark Plot has already rendered is handed
      // to it a second time.
      let built = Plot.plot({ ...evaluate(Plot, spec), width });
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
      // A mark's `href` channel wraps it in a link to whatever its data says. The door that
      // admits markup reads a javascript: link as code the page runs; one written into
      // this body's data is past it, so it draws as the mark alone.
      for (const link of built.querySelectorAll("a")) {
        const href =
          link.getAttributeNS(XLINK, "href") ?? link.getAttribute("href") ?? "";
        if (href.replace(/\s/g, "").toLowerCase().startsWith("javascript:"))
          link.replaceWith(...link.childNodes);
      }
      this.drawing.replaceChildren(built);
      this.drawn = width;
    }
  },
);
