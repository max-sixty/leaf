/* lf-shot owns screenshot inspection: paired frames, slider, pixel difference,
 * outlines, scale, crop and scrolling. A containing package supplies only capture
 * metadata through inspect({pixelRatio, captureWidth, focus, labels}) and allocates
 * its box. Fit keeps both frames in the allocated box. Actual size pans their
 * images together inside those same windows, keeping both labels and views visible.
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
 * All views share one allocation: the single image's fitted height in ordinary
 * flow, or the containing host's bounded height. Pair chooses the orientation
 * that gives both images the larger scale inside that allocation, so changing
 * views never moves the page below. Fit recalculates for that layout; 100% retains the captured CSS
 * scale, or bitmap pixels when no capture ratio is supplied. Inspection choices
 * belong to this element's lifetime, not the document's application state.
 *
 * Images and their source-coordinate marks share one clipped plane. Cropping moves
 * that plane, including pixel masks, rather than having each renderer reinterpret
 * the focus rectangle. Pixel comparison runs after presentation, one pair per
 * frame. Slider is the first view; its two native planes reserve and draw the same
 * half-reveal while Web Awesome loads after presentation. Pixel masks load only on
 * selection. The divider's exact position survives switching views. Replacing either
 * capture refreshes evidence inside the retained controls and viewports, preserving
 * the reader's inspection.
 * `difference` reads the requested pair; a superseded or refused load resolves null.
 * Pair's images are original-image links using the shared viewer; dragging or
 * scrolling them never opens the viewer. Image options holds scale and the pixel key.
 * Print shows both complete original images. */
// A containing widget can create a pair absent from the authored document.
import "/vendor/lf-shot-initial.js";
import {
  afterPresentation,
  announce,
  compareImagePixels,
  compareImages,
  describeDifference,
  once,
  offer,
  failSoft,
  placesFailure,
  focusDestination,
  showNativeLayer,
  closeNativeLayer,
  isNativeLayer,
  initialRender,
  nextFrame,
  isCanonicalMediaUrl,
  layoutChanged,
  commands,
  keeps,
  keepsText,
  paintKeys,
  plainPress,
  scopedMediaUrl,
  widgetController,
  move,
  whileConnected,
  sizeObserver,
  registerReadingRegion,
  compoundReadingRegionId,
} from "/runtime/widget-api.js";

let comparing = Promise.resolve();
const inTurn = (work) => {
  const turn = comparing
    .then(() => new Promise((resolve) => nextFrame(resolve)))
    .then(work);
  comparing = turn.catch(() => {});
  return turn;
};
let comparisonReady;
const loadComparison = () => (comparisonReady ??= import("/vendor/webawesome.esm.js"));
import {
  SHOT_VIEWS as VIEWS,
  fitShotGeometry,
  applyShotGeometry,
  shotAllocation,
} from "./shot-view.js";

customElements.define(
  "lf-shot",
  class extends HTMLElement {
    #stage;
    #canvas;
    #toolbar;
    #scaleTrigger;
    #options;
    #outlinesButton;
    #fullInput;
    #fullLabel;
    #viewButtons = new Map();
    #scaleButtons = new Map();
    #frames = [];
    #viewports = [];
    #shots = [];
    #captions = new Map();
    #frameCaptions = new Map();
    #openers = new Map();
    #comparison;
    #position = 50;
    #view = "flip";
    #outlines = false;
    #actual = false;
    #full = false;
    #metadata = {};
    #reading;
    #pixelsView;
    #pixelsPainted;
    #pixelUrls = [];
    #capture;
    #error;
    static observedAttributes = ["alt", "before", "after"];

    get difference() {
      return this.#capture.difference;
    }

    inspect(metadata) {
      if (!this.#capture) {
        this.#metadata = metadata;
        return;
      }
      if (JSON.stringify(metadata) === JSON.stringify(this.#capture.metadata)) return;
      this.#prepare(this.#capture.images, this.#capture.loaded, metadata);
      if (!this.#reading) {
        this.#metadata = metadata;
        this.#fit();
        this.#paintAlt();
      }
    }

    connectedCallback() {
      if (!once(this)) return;
      placesFailure(this, (box) => {
        if (this.#error?.textContent === box.textContent) return true;
        this.#error?.remove();
        this.#error = box;
        this.append(box);
        return true;
      });
      const drawing = initialRender(this);
      this.#toolbar = drawing.toolbar;
      this.#viewButtons = drawing.views.choices;
      this.#scaleButtons = drawing.scale.choices;
      this.#outlinesButton = drawing.outlines;
      this.#scaleTrigger = drawing.scaleTrigger;
      this.#options = drawing.options;
      this.#fullInput = drawing.full.input;
      this.#fullLabel = drawing.full.label;
      this.#stage = drawing.stage;
      this.#canvas = drawing.canvas;
      this.#frames = drawing.frames;
      this.#viewports = drawing.viewports;
      this.#shots = drawing.shots;
      this.#captions = drawing.captions;
      this.#frameCaptions = drawing.frameCaptions;
      this.#openers = drawing.openers;
      for (const [view, button] of this.#viewButtons)
        button.addEventListener("click", () => this.#chooseView(view));
      for (const [scale, button] of this.#scaleButtons)
        button.addEventListener("click", () => {
          this.#actual = scale === "actual";
          this.#fit();
          this.#paint();
          closeNativeLayer(this.#options);
          focusDestination(this.#scaleTrigger, "move");
        });
      this.#scaleTrigger.addEventListener("click", (event) => {
        event.preventDefault();
        if (isNativeLayer(this.#options)) closeNativeLayer(this.#options);
        else {
          focusDestination(this.#scaleTrigger, "press");
          showNativeLayer(this.#options, { source: this.#scaleTrigger });
          focusDestination(
            this.#scaleButtons.get(this.#actual ? "actual" : "fit"),
            "move",
          );
        }
      });
      this.#options.addEventListener("toggle", () => {
        keeps(this.#scaleTrigger, "aria-expanded", isNativeLayer(this.#options));
        paintKeys();
      });
      this.#outlinesButton.addEventListener("click", () => {
        this.#outlines = !this.#outlines;
        this.#paint();
      });
      this.#fullInput.addEventListener("change", () => {
        this.#full = this.#fullInput.checked;
        this.#fit();
        this.#paint();
      });
      for (const [index, viewport] of this.#viewports.entries()) {
        viewport.addEventListener(
          "scroll",
          () => {
            if (this.#view !== "compare" || !this.#actual) return;
            const peer = this.#viewports[1 - index];
            if (
              peer.scrollLeft !== viewport.scrollLeft ||
              peer.scrollTop !== viewport.scrollTop
            )
              peer.scrollTo({
                left: viewport.scrollLeft,
                top: viewport.scrollTop,
                behavior: "instant",
              });
          },
          { passive: true },
        );
      }
      this.#paintAlt();
      this.#fit();
      this.#paint();
      whileConnected(this, () => {
        const observer = sizeObserver(() => this.#fit());
        observer.observe(this.#stage);
        const unregister = [
          registerReadingRegion({
            id: compoundReadingRegionId(this, "capture"),
            host: this,
            body: this.#stage,
          }),
          ...this.#viewports.map((body, index) =>
            registerReadingRegion({
              id: compoundReadingRegionId(this, index === 0 ? "before" : "after"),
              host: this.#frames[index],
              body,
            }),
          ),
        ];
        return () => {
          observer.disconnect();
          for (const release of unregister) release();
        };
      });
      this.#loadImages();
      this.#requestComparison();
    }

    #loadImages() {
      const images = [];
      const loaded = Promise.all(
        ["before", "after"].map((state) => {
          const image = document.createElement("img");
          image.crossOrigin = "anonymous";
          images.push(image);
          return new Promise((resolve) => {
            image.onload = () => resolve(true);
            image.onerror = () => resolve(false);
            const source = this.getAttribute(state);
            image.src = isCanonicalMediaUrl(source) ? scopedMediaUrl(source) : source;
          });
        }),
      ).then((loaded) => loaded.every(Boolean));
      this.#prepare(images, loaded, this.#capture?.metadata ?? this.#metadata);
    }

    #prepare(images, loaded, metadata) {
      // A requested capture owns its metadata snapshot. A metadata revision reuses
      // this pair's load; it cannot mutate validation already in flight or retry a
      // failed network request as a side effect of an unrelated presentation.
      const capture = { images, loaded, metadata, difference: null };
      this.#capture = capture;
      const present =
        /** @type {{_lfPresentGenerated?: (promise: Promise<unknown>) => void}} */ (
          this
        )._lfPresentGenerated ?? ((promise) => widgetController(this).present(promise));
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
        if (!this.#reading) this.#commitImages(capture);
        return true;
      });
      present(registered);
      capture.difference = registered
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

    #commitImages(capture, pixels = null) {
      const changed = this.#shots !== capture.images;
      for (const [index, image] of capture.images.entries()) {
        if (this.#shots[index].src === image.src)
          capture.images[index] = this.#shots[index];
        else this.#shots[index].replaceWith(image);
      }
      this.#shots = capture.images;
      this.#metadata = capture.metadata;
      this.#error?.remove();
      this.#error = null;
      if (changed) {
        this.#paintPixels(pixels ?? []);
        this.#pixelsPainted = pixels ? Promise.resolve() : null;
      }
      this.#fit();
      this.#paintAlt();
      this.#paint();
    }

    attributeChangedCallback(name, before, after) {
      if (!this.#toolbar || before === after) return;
      if (name === "alt") this.#paintAlt();
      else this.#loadImages();
    }

    #paintAlt() {
      if (!this.#toolbar) return;
      const alt = this.getAttribute("alt");
      const labels = this.#metadata.labels ?? { before: "Before", after: "After" };
      for (const [index, state] of ["before", "after"].entries()) {
        keepsText(this.#captions.get(state), labels[state]);
        keepsText(this.#frameCaptions.get(state), labels[state]);
        keeps(this.#captions.get(state), "aria-label", `${labels[state]} — ${alt}`);
        keeps(this.#captions.get(state), "title", labels[state]);
        keeps(this.#frameCaptions.get(state), "title", labels[state]);
        keeps(this.#shots[index], "alt", `${state}: ${alt}`);
        keeps(this.#viewports[index], "aria-label", `${labels[state]} — ${alt}`);
        const open = this.#openers.get(state);
        keeps(open, "data-lf-media-caption", `${state}: ${alt}`);
        keeps(open, "aria-label", `Open ${state} image — ${alt}`);
      }
      if (this.#pixelsView)
        keeps(this.#pixelsView, "aria-label", `changed pixels: ${alt}`);
      keeps(this.#stage, "aria-label", `Screenshot comparison — ${alt}`);
      this.#paintHandle();
    }

    #fit() {
      if (!this.#stage || !this.#frames.length) return;
      // Show the selected presentation before reading its shared allocation.
      keeps(this, "data-lf-shot-mode", this.#view);
      const allocation = shotAllocation(this, this.#stage);
      if (allocation.available <= 0) return; // Hidden cases retain their last inspection until shown.
      const ratio = this.#metadata.pixelRatio ?? 1;
      const sourceWidth =
        this.#shots[0].naturalWidth / ratio ||
        Number(this.dataset.lfMediaWidth) / ratio ||
        this.#metadata.captureWidth;
      const sourceHeight =
        Math.max(...this.#shots.map((image) => image.naturalHeight)) / ratio ||
        Number(this.dataset.lfMediaHeight) / ratio;
      const focus = this.#metadata.focus;
      const crop = focus && !this.#full;
      // Capture metadata fixes the cropped viewport before images decode; source
      // dimensions become available independently and size only its inner plane.
      if (!(crop || (sourceWidth && sourceHeight))) return;
      const geometry = fitShotGeometry({
        ...allocation,
        labelHeight: parseFloat(
          getComputedStyle(this.#frameCaptions.get("before").parentElement).blockSize,
        ),
        sourceWidth,
        sourceHeight,
        focus,
        full: this.#full,
        actual: this.#actual,
        view: this.#view,
        gap: parseFloat(getComputedStyle(this).getPropertyValue("--lf-shot-gap")),
      });
      if (!geometry) return;
      applyShotGeometry(this, geometry, keeps);
      this.#fullLabel.toggleAttribute("hidden", !focus);
      this.#fullInput.checked = this.#full;
      const fitDescription = `Fit · ${Math.round(geometry.fitScale * 100)}%`;
      keeps(this.#scaleButtons.get("fit"), "title", fitDescription);
      keeps(
        this.#scaleButtons.get("actual"),
        "title",
        this.#metadata.pixelRatio
          ? "Captured CSS size"
          : "One image pixel per CSS pixel",
      );
      layoutChanged(this);
    }

    #chooseView(view) {
      if (view === this.#view) return;
      if (view === "pixels") void this.#showPixels();
      else {
        this.#view = view;
        this.#syncComparison();
        this.#fit();
        this.#paint();
        if (view === "flip") this.#requestComparison();
      }
      announce(`Showing ${VIEWS[view].toLowerCase()}`);
    }

    #syncComparison() {
      if (this.#view !== "flip" && this.#comparison) {
        this.#position = this.#comparison.position;
        for (const frame of this.#frames) {
          frame.removeAttribute("slot");
          move(this.#canvas, frame);
        }
        this.#comparison.remove();
        this.#comparison = null;
      }
      if (
        this.#view === "flip" &&
        !this.#comparison &&
        customElements.get("wa-comparison")
      ) {
        const comparison = offer("wa-comparison", "lf-shotcomparison lf-media-frame");
        comparison.position = this.#position;
        const handle = offer("span", "lf-shot-handle");
        handle.slot = "handle";
        handle.ariaHidden = "true";
        comparison.append(handle);
        for (const frame of this.#frames) {
          frame.slot = frame.dataset.lfState === "before" ? "after" : "before";
          comparison.append(frame);
        }
        let dragged = false;
        const handleOf = (event) =>
          event
            .composedPath()
            .find(
              (node) =>
                node instanceof Element &&
                node.getAttribute("part")?.split(/\s+/).includes("handle"),
            );
        comparison.addEventListener("change", () => {
          dragged = true;
          this.#position = comparison.position;
          this.#paint();
        });
        comparison.addEventListener("pointerdown", (event) => {
          if (!event.isPrimary || event.button !== 0) return;
          dragged = false;
          const handle = handleOf(event);
          if (handle) focusDestination(handle, "press");
        });
        comparison.addEventListener("click", (event) => {
          if (dragged || handleOf(event) || !plainPress(event)) return;
          comparison.position = comparison.position > 50 ? 0 : 100;
        });
        commands(comparison, "On a screenshot divider", [
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
        ]);
        this.#canvas.append(comparison);
        this.#comparison = comparison;
        void comparison.updateComplete.then(() => this.#paintHandle());
      }
    }

    #requestComparison() {
      void afterPresentation(async () => {
        await loadComparison();
        if (this.isConnected && this.#view === "flip") {
          this.#syncComparison();
          this.#fit();
          this.#paint();
        }
      }).catch((reason) => failSoft(this, reason));
    }

    #paintHandle() {
      const handle = this.#comparison?.shadowRoot?.querySelector('[role="scrollbar"]');
      if (!handle) return;
      keeps(handle, "aria-label", `Before and after — ${this.getAttribute("alt")}`);
      keeps(
        handle,
        "aria-valuetext",
        `Before ${this.#position}%, after ${100 - this.#position}%`,
      );
    }

    #paint() {
      if (!this.#toolbar) return;
      keeps(this, "data-lf-shot-outlines", this.#outlines);
      this.#viewButtons.get("pixels").toggleAttribute("disabled", !this.#reading);
      for (const [view, button] of this.#viewButtons)
        keeps(button, "aria-pressed", view === this.#view);
      for (const [scale, button] of this.#scaleButtons)
        keeps(button, "aria-pressed", (scale === "actual") === this.#actual);
      keeps(this.#outlinesButton, "aria-pressed", this.#outlines);
      this.#outlinesButton.toggleAttribute(
        "disabled",
        this.#view === "pixels" || !this.#reading?.regions.length,
      );
      this.#syncComparison();
      for (const [state, caption] of this.#captions)
        caption.toggleAttribute(
          "data-lf-shot-hidden",
          this.#view === "flip" &&
            (state === "before" ? this.#position === 0 : this.#position === 100),
        );
      for (const [index, state] of ["before", "after"].entries()) {
        const open = this.#openers.get(state);
        const pair = this.#view === "compare";
        keeps(open, "href", pair ? this.#shots[index].src || null : null);
        keeps(open, "tabindex", pair ? null : -1);
        keeps(open, "title", pair ? `Open ${state} image` : null);
      }
      this.#paintHandle();
      paintKeys();
    }

    async #markDifference(capture) {
      if (capture !== this.#capture) return null;
      const reading = await compareImages(...capture.images);
      const pixels =
        this.#view === "pixels" && this.#shots !== capture.images
          ? await this.#pixelMasks(capture.images)
          : null;
      if (capture !== this.#capture) {
        for (const url of pixels ?? []) URL.revokeObjectURL(url);
        return null;
      }
      this.#commitImages(capture, pixels);
      this.#reading = reading;
      const { width, height, regions } = reading;
      for (const frame of this.#frames) {
        const marks = offer("div", "lf-shotdiff");
        marks.ariaHidden = "true";
        for (const region of regions) {
          if (region.side !== frame.dataset.lfState) continue;
          const mark = document.createElement("span");
          mark.dataset.lfShotMark = region.kind;
          for (const [key, value, whole] of [
            ["x", region.x, width],
            ["y", region.y, height],
            ["w", region.width, width],
            ["h", region.height, height],
          ])
            mark.style.setProperty(`--lf-shot-${key}`, `${(100 * value) / whole}%`);
          marks.append(mark);
        }
        const plane = frame.querySelector(".lf-shotplane");
        const previous = plane.querySelector(".lf-shotdiff");
        if (!previous) plane.append(marks);
        else if (!previous.isEqualNode(marks)) previous.replaceWith(marks);
      }
      const description = describeDifference(reading);
      keeps(this.#outlinesButton, "aria-description", description);
      this.#paint();
      return reading;
    }

    #showPixels() {
      this.#view = "pixels";
      if (!this.#pixelsView) {
        const view = offer("div", "lf-shotpixels lf-shotimage lf-media-frame");
        view.role = "img";
        view.ariaLabel = `changed pixels: ${this.getAttribute("alt")}`;
        const plane = offer("div", "lf-shotplane");
        const ground = document.createElement("img");
        ground.alt = "";
        ground.src = this.#shots[1].src;
        const paints = ["both", "before", "after"].map((side) => {
          const paint = document.createElement("span");
          paint.dataset.lfShotSide = side;
          return paint;
        });
        plane.append(ground, ...paints);
        view.append(plane);
        this.#canvas.append(view);
        this.#pixelsView = view;
      }
      if (!this.#pixelsPainted) {
        const images = this.#shots;
        this.#pixelsPainted = inTurn(async () => {
          const urls = await this.#pixelMasks(images);
          if (images !== this.#shots) {
            for (const url of urls) URL.revokeObjectURL(url);
            return;
          }
          this.#paintPixels(urls);
        });
        void this.#pixelsPainted.catch((reason) => {
          if (images === this.#shots) failSoft(this, reason);
        });
      }
      this.#syncComparison();
      this.#fit();
      this.#paint();
      return this.#pixelsPainted;
    }

    async #pixelMasks(images) {
      const { width, height, ...masks } = compareImagePixels(...images);
      const blobs = await Promise.all(
        ["both", "before", "after"].map(async (side) => {
          const canvas = new OffscreenCanvas(width, height);
          canvas
            .getContext("2d")
            .putImageData(new ImageData(masks[side], width, height), 0, 0);
          return canvas.convertToBlob({ type: "image/png" });
        }),
      );
      const urls = blobs.map((blob) => URL.createObjectURL(blob));
      try {
        await Promise.all(
          urls.map((url) => {
            const image = document.createElement("img");
            image.src = url;
            return image.decode();
          }),
        );
        return urls;
      } catch (reason) {
        for (const url of urls) URL.revokeObjectURL(url);
        throw reason;
      }
    }

    #paintPixels(urls) {
      if (this.#pixelsView) {
        keeps(this.#pixelsView.querySelector("img"), "src", this.#shots[1].src);
        for (const [index, paint] of [
          ...this.#pixelsView.querySelectorAll("[data-lf-shot-side]"),
        ].entries()) {
          if (urls[index])
            paint.style.setProperty("--lf-shot-pixels", `url("${urls[index]}")`);
          else paint.style.removeProperty("--lf-shot-pixels");
        }
      }
      for (const url of this.#pixelUrls) URL.revokeObjectURL(url);
      this.#pixelUrls = urls;
    }

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
  },
);
