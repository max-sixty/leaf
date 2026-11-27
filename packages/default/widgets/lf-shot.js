import { ShotView } from "./shot-view.js";
/* lf-shot owns screenshot inspection: paired frames, slider, pixel difference,
 * outlines, scale, crop and scrolling. Its attributes state the captures' facts:
 * `density`, their device pixel ratio, and `focus-x`, `focus-y`, `focus-width` and
 * `focus-height`, the region in their CSS pixels that every view opens cropped to.
 * The maintainer chose to let markup state them, so a pair written in a page opens on
 * its change; a containing package states them as an author does, and allocates the
 * box. The region is the author's to state rather than
 * the comparison's to find: the comparison runs after presentation, so a region it
 * found would resize a shot the reader already sees, and its bounds would take in
 * whatever else moved, such as every row below one that grew. Four attributes rather
 * than one list let the stylesheet hold the cropped frame's room before this module
 * draws (shot.css), since `attr()` reads one number from an attribute.
 * Fit keeps both frames in the allocated box and never enlarges a capture
 * past 100%, because stretching a capture blurs it. A capture narrower than the box
 * sits at its own size; how large to capture is the author's call. Actual size pans
 * their images together inside those same windows, keeping both labels and views
 * visible.
 * Both frames always share one source scale. The retained header belongs to the
 * allocated viewport, outside the image canvas. Controls stay in place when views
 * or scale change. Source labels are passive, and images never change modes.
 * In Slider, a plain image click alternates the divider's Before/After endpoints;
 * dragging and the divider's keyboard controls retain continuous adjustment.
 * Source labels retain their color while any of that image is visible; a fully
 * hidden source has a muted label, so endpoints identify the image being inspected.
 * A stacked pair labels each frame instead of the header, since left/right
 * bookends cannot identify vertically arranged images. Other views label the header.
 *
 * Pair chooses the orientation that gives both images the larger scale. A bounded
 * host supplies the height; stacked frames in flow fit the screen below the toolbar.
 * In ordinary flow it takes only the height its windows need; the toolbar stays
 * in place while content below follows the images. Fit recalculates for that
 * layout; 100% retains the captured CSS
 * scale, or bitmap pixels when no `density` is stated. Inspection choices
 * belong to this element's lifetime, not the document's application state.
 *
 * Images and their source-coordinate marks share one clipped plane. Cropping moves
 * that plane, including pixel masks, rather than having each renderer reinterpret
 * the focus rectangle. Pixel comparison runs after presentation, one comparison at a
 * time and a frame apart, so a page of shots stays responsive. A difference reading
 * waits its turn; a mask the reader pressed for goes to the front and waits only for
 * the comparison already running.
 *
 * A pair opens in the view its `view` attribute names, Slider by default, and the
 * reader chooses from there. The maintainer chose to make it the author's setting,
 * since each view shows a different kind of change best and Slider's even split shows
 * only one version of a change that sits in one half of the frame. The divider and the view radios are Web Awesome's, and this module loads
 * those three controls with itself (`webawesome-views`), so every view takes the first
 * press the reader makes once the page shows. That puts them on the startup path;
 * loading them after presentation kept them off, but left the radios inert until they
 * arrived. Pixels needs only the two images, so it shows at once, and its mask
 * follows. Masks are computed only once Pixels shows. The divider's exact position
 * survives switching views.
 * Replacing either capture refreshes evidence inside the retained controls and
 * viewports, preserving the reader's inspection.
 * `difference` reads the requested pair, with its `description` in words; a superseded
 * or refused load resolves null.
 * Pair's images are original-image links using the shared viewer; dragging or
 * scrolling them never opens the viewer. Image options holds scale, outlines and the
 * pixel key, so the row holds only the views and nothing there reads as a fourth one.
 * Print shows both complete original images. */
import { render } from "/vendor/lit.js";
import {
  afterPresentation,
  frameFor,
  focusDestination,
  scopedMediaUrl,
  move,
  whileConnected,
} from "/runtime/widget-api.js";
import { failSoft, placesFailure } from "/runtime/lib/failure.js";
import { PendingTaskEvent } from "/runtime/lib/pending-task.js";
import { offer } from "/runtime/lib/controls.js";
import { once } from "/runtime/lib/once.js";
import { nextFrame, sizeObserver } from "/runtime/lib/frame-pass.js";
import { keeps } from "/runtime/lib/keeps.js";
import { plainPress } from "/runtime/lib/keys.js";
import { canvas2D } from "/runtime/lib/canvas.js";
import { scrollMoves } from "/runtime/lib/scroll-range.js";
import "/vendor/webawesome-views.js";

/** @type {(() => Promise<void>)[]} */
const turns = [];
let comparing = false;
const takeTurns = async () => {
  comparing = true;
  while (turns.length) {
    await new Promise((resolve) => nextFrame(() => resolve(undefined)));
    await turns.shift()?.();
  }
  comparing = false;
};
/** @template T @param {() => T | PromiseLike<T>} work @param {boolean} [pressed] @returns {Promise<T>} */
const inTurn = (work, pressed = false) =>
  new Promise((resolve, reject) => {
    const turn = () => Promise.resolve().then(work).then(resolve, reject);
    if (pressed) turns.unshift(turn);
    else turns.push(turn);
    if (!comparing) void takeTurns();
  });
import { shotBox } from "./shot-view.js";
import {
  compareImagePixels,
  paperOf,
  compareImages,
  describeDifference,
} from "./image-difference.js";

/** @typedef {import("./shot-view.js").ShotMetadata} ShotMetadata */
const FOCUS = ["focus-x", "focus-y", "focus-width", "focus-height"];
/** @typedef {import("./image-difference.js").Difference & {description: string}} DescribedDifference */
/** @typedef {{images: [HTMLImageElement, HTMLImageElement], loaded: Promise<boolean>, metadata: ShotMetadata, difference: Promise<DescribedDifference | null>}} Capture */
export class Shot extends HTMLElement {
  /** @type {ShotView | undefined} */
  #drawingOwner;
  get #drawing() {
    return (this.#drawingOwner ??= new ShotView(this));
  }
  /** @type {import("@awesome.me/webawesome/dist/components/comparison/comparison.js").default | null} */
  #comparison = null;
  /** @type {Promise<void> | null} */
  #pixelsPainted = null;
  /** @type {Capture | null} */
  #capture = null;
  /** @type {Element | null} */
  #error = null;
  static observedAttributes = ["alt", "before", "after", "density", ...FOCUS];

  get difference() {
    return this.#capture?.difference ?? Promise.resolve(null);
  }

  /** The capture facts the attributes state; a focus missing a side states none,
   * which `page check` refuses. */
  #metadata() {
    /** @type {ShotMetadata} */
    const metadata = {};
    const density = Number(this.getAttribute("density"));
    if (density > 0) metadata.pixelRatio = density;
    const side = (/** @type {string} */ name) =>
      Number(this.getAttribute(`focus-${name}`) ?? NaN);
    const focus = {
      x: side("x"),
      y: side("y"),
      width: side("width"),
      height: side("height"),
    };
    if (focus.x >= 0 && focus.y >= 0 && focus.width > 0 && focus.height > 0)
      metadata.focus = focus;
    return metadata;
  }

  // A metadata revision reuses the pair's load, and the reading shown for it.
  #inspect() {
    const metadata = this.#metadata();
    if (!this.#capture) {
      this.#drawing.metadata = metadata;
      return;
    }
    if (JSON.stringify(metadata) === JSON.stringify(this.#capture.metadata)) return;
    this.#prepare(this.#capture.images, this.#capture.loaded, metadata);
    if (!this.#drawing.reading) {
      this.#drawing.metadata = metadata;
      this.#fit();
    }
  }

  connectedCallback() {
    if (!once(this)) return;
    placesFailure(this, (/** @type {Element} */ box) => {
      if (this.#error?.textContent === box.textContent) return true;
      this.#error?.remove();
      this.#error = box;
      this.append(box);
      return true;
    });
    // The shot hosts its stage's reading region (shot-view.js marks the stage).
    keeps(this, "data-lf-scroll-host", "capture");
    const drawing = this.#drawing;
    drawing.view = this.getAttribute("view") ?? drawing.view;
    drawing.metadata = this.#metadata();
    render(drawing.render(), this, { host: this });
    drawing.fit();
    render(drawing.render(), this, { host: this });
    drawing.chooseView = (view) => this.#chooseView(view);
    drawing.chooseScale = (scale) => {
      this.#drawing.actual = scale === "actual";
      this.#fit();
      drawing.options.hidePopover();
      focusDestination(drawing.scaleTrigger, "move");
    };
    drawing.optionsToggled = (event) => {
      if (event.newState !== "open") return;
      const selected = drawing.options.querySelector('button[aria-pressed="true"]');
      if (selected) focusDestination(selected, "move");
    };
    drawing.toggleOutlines = () => {
      this.#drawing.outlines = !this.#drawing.outlines;
      this.#paint();
    };
    drawing.changeFull = (event) => {
      const control = event.currentTarget;
      if (!(control instanceof HTMLInputElement)) return;
      this.#drawing.full = control.checked;
      this.#fit();
    };
    for (const [index, viewport] of this.#drawing.viewports.entries()) {
      viewport.addEventListener(
        "scroll",
        () => {
          if (this.#drawing.view !== "pair" || !this.#drawing.actual) return;
          const peer = index === 0 ? drawing.viewports[1] : drawing.viewports[0];
          const at = { left: viewport.scrollLeft, top: viewport.scrollTop };
          if (scrollMoves(peer, at)) peer.scrollTo({ ...at, behavior: "instant" });
        },
        { passive: true },
      );
    }
    this.#fit();
    // A fit can change the stage's own height, which follows the frames it sizes, so
    // it runs after ResizeObserver delivery: a fit inside the delivery that asked for
    // it resizes the box being watched, which the browser reports as undelivered
    // notifications.
    const fit = frameFor(this, () => this.#fit());
    whileConnected(this, () => {
      const observer = sizeObserver(fit);
      observer.observe(this.#drawing.stage);
      // Pair's bound in flow is the screen's height, which the stage doesn't track.
      const refit = () => this.#fit();
      window.addEventListener("resize", refit, { passive: true });
      return () => {
        observer.disconnect();
        window.removeEventListener("resize", refit);
      };
    });
    this.#loadImages();
  }

  #loadImages() {
    /** @type {[HTMLImageElement, HTMLImageElement]} */
    const images = [document.createElement("img"), document.createElement("img")];
    const loaded = Promise.all(
      images.map((image, index) => {
        const state = index === 0 ? "before" : "after";
        image.crossOrigin = "anonymous";
        return new Promise((resolve) => {
          image.onload = () => resolve(true);
          image.onerror = () => resolve(false);
          const source = this.getAttribute(state);
          if (source !== null)
            image.src = source.startsWith("/media/") ? scopedMediaUrl(source) : source;
          else resolve(false);
        });
      }),
    ).then((loaded) => loaded.every(Boolean));
    this.#prepare(images, loaded, this.#metadata());
  }

  /** @param {[HTMLImageElement, HTMLImageElement]} images @param {Promise<boolean>} loaded @param {ShotMetadata} metadata */
  #prepare(images, loaded, metadata) {
    // A requested capture owns its metadata snapshot. A metadata revision reuses
    // this pair's load; it cannot mutate validation already in flight or retry a
    // failed network request as a side effect of an unrelated presentation. The
    // comparison reads the whole images, so the reading already shown for them stands
    // under a new focus or density, which shows at once.
    const shown =
      this.#drawing.reading && this.#drawing.images === images
        ? this.#capture?.difference
        : undefined;
    /** @type {Capture} */
    const capture = { images, loaded, metadata, difference: Promise.resolve(null) };
    this.#capture = capture;
    const registered = loaded.then((loaded) => {
      if (capture !== this.#capture) return false;
      if (!loaded) {
        failSoft(
          this,
          new Error(
            metadata.focus
              ? "focus needs two decoded images"
              : "could not load the capture pair",
          ),
        );
        return false;
      }
      if (!this.#validImages(images, metadata)) return false;
      // First arrival can show its images before deferred comparison. A refresh
      // keeps the complete outgoing evidence until its replacement reading is ready.
      if (!this.#drawing.reading || shown) this.#commitImages(capture);
      return true;
    });
    this.#present(registered);
    capture.difference =
      shown ??
      registered
        .then((aligned) =>
          aligned
            ? afterPresentation(() => inTurn(() => this.#markDifference(capture)))
            : null,
        )
        .catch((reason) => {
          if (capture === this.#capture) failSoft(this, reason);
          return null;
        });
  }

  /** Hold the page's readiness until `promise` settles, so a reader outside the page
   * waits for what this shot draws when it lands.
   * @param {Promise<unknown>} promise */
  #present(promise) {
    this.dispatchEvent(new PendingTaskEvent(promise));
  }

  /** @param {Capture} capture @param {string | null} [pixels] */
  #commitImages(capture, pixels = null) {
    const changed = this.#drawing.images !== capture.images;
    this.#drawing.images = capture.images;
    this.#drawing.metadata = capture.metadata;
    this.#error?.remove();
    this.#error = null;
    if (changed) {
      this.#drawing.paper = null;
      this.#setPixelUrl(pixels);
      this.#pixelsPainted = pixels ? Promise.resolve() : null;
    }
    if (this.#drawing.view === "pixels" && !this.#pixelsPainted)
      void this.#showPixels();
    else this.#fit();
  }

  /** @param {string} name @param {string | null} before @param {string | null} after */
  attributeChangedCallback(name, before, after) {
    if (!this.#drawingOwner || before === after) return;
    if (name === "alt") this.#paint();
    else if (name === "before" || name === "after") this.#loadImages();
    else this.#inspect();
  }

  #fit() {
    if (!this.#drawing.hasDrawn) return;
    this.#syncComparison();
    // Show the selected presentation before reading its shared allocation.
    keeps(this, "data-lf-shot-mode", this.#drawing.view);
    const shown = this.#drawing.images[1];
    if (this.#drawing.view === "pixels" && shown)
      this.#drawing.paper ??= paperOf(shown);
    this.#drawing.fit();
    this.#paint();
    this.dispatchEvent(new CustomEvent("lf-layout", { bubbles: true, composed: true }));
  }

  // The view's own radio says which view shows, as focus lands on it.
  /** @param {string} view */
  #chooseView(view) {
    if (view === this.#drawing.view) return;
    if (view === "pixels") void this.#showPixels();
    else {
      this.#drawing.view = view;
      this.#fit();
    }
  }

  #syncComparison() {
    if (this.#drawing.view !== "slider" && this.#comparison) {
      this.#drawing.position = this.#comparison.position;
      for (const frame of this.#drawing.frames) {
        frame.removeAttribute("slot");
        move(this.#drawing.canvas, frame);
      }
      this.#comparison.remove();
      this.#comparison = null;
    }
    if (this.#drawing.view === "slider" && !this.#comparison) {
      const comparison = shotBox("wa-comparison", "lf-shotcomparison lf-media-frame");
      comparison.position = this.#drawing.position;
      const handle = offer("span", "lf-shot-handle");
      handle.slot = "handle";
      handle.ariaHidden = "true";
      comparison.append(handle);
      for (const frame of this.#drawing.frames) {
        frame.slot = frame.dataset.lfState === "before" ? "after" : "before";
        comparison.append(frame);
      }
      let dragged = false;
      /**
       * @param {Event} event
       * @param {string} part
       */
      const partOf = (event, part) =>
        event
          .composedPath()
          .find(
            (node) =>
              node instanceof Element &&
              node.getAttribute("part")?.split(/\s+/).includes(part),
          );
      comparison.addEventListener("change", () => {
        dragged = true;
        this.#drawing.position = comparison.position;
        this.#paint();
      });
      comparison.addEventListener("pointerdown", (event) => {
        if (!event.isPrimary || event.button !== 0) return;
        dragged = false;
        const handle = partOf(event, "handle");
        if (handle instanceof HTMLElement || handle instanceof SVGElement)
          focusDestination(handle, "press");
      });
      comparison.addEventListener("click", (event) => {
        // A modified click keeps its usual meaning. A press on the divider drags it,
        // and Web Awesome captures that pointer on the divider, so the click that
        // ends a press on the handle targets the divider rather than the handle.
        if (dragged || partOf(event, "divider") || !plainPress(event)) return;
        event.preventDefault();
        comparison.position = comparison.position > 50 ? 0 : 100;
      });
      comparison.lfCommands = {
        title: "On a screenshot divider",
        rows: [
          {
            id: "screenshot.adjust",
            keys: ["ArrowLeft", "ArrowRight"],
            repeat: true,
            title: "adjust the comparison",
          },
          {
            id: "screenshot.edge",
            keys: ["Home", "End"],
            title: "show before or after",
          },
        ],
      };
      this.#drawing.canvas.append(comparison);
      comparison.dispatchEvent(
        new CustomEvent("lf-commands", { bubbles: true, composed: true }),
      );
      this.#comparison = comparison;
      void comparison.updateComplete.then(() => this.#paintHandle());
    }
  }

  #paintHandle() {
    const handle = this.#comparison?.shadowRoot?.querySelector('[role="scrollbar"]');
    if (!handle) return;
    keeps(handle, "aria-label", `Before and after — ${this.getAttribute("alt")}`);
    // The alt describes the picture the user is looking at, so the divider's preview
    // names only the divider.
    Object.assign(handle, { lfPreview: () => ({ name: "Before and after" }) });
    keeps(
      handle,
      "aria-valuetext",
      `Before ${this.#drawing.position}%, after ${100 - this.#drawing.position}%`,
    );
  }

  #paint() {
    if (!this.#drawingOwner) return;
    render(this.#drawing.render(), this, { host: this });
    this.#paintHandle();
    this.dispatchEvent(
      new CustomEvent("lf-commands", { bubbles: true, composed: true }),
    );
  }

  /** @param {Capture} capture */
  async #markDifference(capture) {
    if (capture !== this.#capture) return null;
    const reading = await compareImages(...capture.images);
    const pixels =
      this.#drawing.view === "pixels" && this.#drawing.images !== capture.images
        ? await this.#pixelMask(capture.images)
        : null;
    if (capture !== this.#capture) {
      if (pixels) URL.revokeObjectURL(pixels);
      return null;
    }
    this.#commitImages(capture, pixels);
    this.#drawing.reading = reading;
    const description = (this.#drawing.description = describeDifference(reading));
    this.#paint();
    return { ...reading, description };
  }

  #showPixels() {
    this.#drawing.view = "pixels";
    this.#drawing.pixels = true;
    if (!this.#pixelsPainted) {
      const images = this.#drawing.images;
      if (images.length !== 2) return;
      const pending = (this.#pixelsPainted = inTurn(async () => {
        const url = await this.#pixelMask(images);
        if (images !== this.#drawing.images) {
          URL.revokeObjectURL(url);
          return;
        }
        this.#setPixelUrl(url);
        this.#paint();
      }, true));
      this.#present(
        pending.catch((reason) => {
          if (images === this.#drawing.images) failSoft(this, reason);
        }),
      );
    }
    this.#fit();
    return this.#pixelsPainted;
  }

  /** @param {[HTMLImageElement, HTMLImageElement]} images */
  async #pixelMask(images) {
    const { width, height, data } = compareImagePixels(...images);
    const canvas = new OffscreenCanvas(width, height);
    canvas2D(canvas).putImageData(new ImageData(data, width, height), 0, 0);
    const url = URL.createObjectURL(await canvas.convertToBlob({ type: "image/png" }));
    try {
      const image = document.createElement("img");
      image.src = url;
      await image.decode();
      return url;
    } catch (reason) {
      URL.revokeObjectURL(url);
      throw reason;
    }
  }

  /** @param {string | null} url */
  #setPixelUrl(url) {
    if (this.#drawing.pixelUrl) URL.revokeObjectURL(this.#drawing.pixelUrl);
    this.#drawing.pixelUrl = url;
  }

  /** @param {[HTMLImageElement, HTMLImageElement]} images @param {ShotMetadata} metadata */
  #validImages(images, { focus = undefined, pixelRatio = 1 }) {
    const [before, after] = images.map((image) => image.naturalWidth);
    let error;
    if (before && after && before !== after)
      error = `before is ${before}px wide and after is ${after}px — a pair has to be shot at one viewport, or the flip moves everything`;
    else if (
      focus &&
      images.some(
        (image) =>
          focus.x + focus.width > image.naturalWidth / pixelRatio ||
          focus.y + focus.height > image.naturalHeight / pixelRatio,
      )
    )
      error = `focus ${focus.x},${focus.y} ${focus.width}×${focus.height} CSS px falls outside its captured images`;
    if (!error) return true;
    failSoft(this, new Error(error));
    return false;
  }
}
customElements.define("lf-shot", Shot);
