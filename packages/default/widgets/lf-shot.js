import { ShotView } from "./shot-view.js";
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
 * Pair chooses the orientation that gives both images the larger scale. A bounded
 * host supplies the height; stacked frames in flow fit the screen below the toolbar.
 * In ordinary flow it takes only the height its windows need; the toolbar stays
 * in place while content below follows the images. Fit recalculates for that
 * layout; 100% retains the captured CSS
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
 * `difference` reads the requested pair, with its `description` in words; a superseded
 * or refused load resolves null.
 * Pair's images are original-image links using the shared viewer; dragging or
 * scrolling them never opens the viewer. Image options holds scale and the pixel key.
 * Print shows both complete original images. */
// A containing widget can create a pair absent from the authored document.
import {
  afterPresentation,
  announce,
  once,
  offer,
  failSoft,
  frameFor,
  placesFailure,
  focusDestination,
  showNativeLayer,
  closeNativeLayer,
  isNativeLayer,
  render,
  nextFrame,
  isCanonicalMediaUrl,
  layoutChanged,
  commands,
  keeps,
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
import { SHOT_VIEWS as VIEWS, shotBox } from "./shot-view.js";
import {
  compareImagePixels,
  compareImages,
  describeDifference,
} from "./image-difference.js";

customElements.define(
  "lf-shot",
  class extends HTMLElement {
    #drawing;
    #comparison;
    #pixelsPainted;
    #capture;
    #error;
    static observedAttributes = ["alt", "before", "after"];

    get difference() {
      return this.#capture.difference;
    }

    inspect(metadata) {
      if (!this.#capture) {
        (this.#drawing ??= new ShotView(this)).metadata = metadata;
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
      placesFailure(this, (box) => {
        if (this.#error?.textContent === box.textContent) return true;
        this.#error?.remove();
        this.#error = box;
        this.append(box);
        return true;
      });
      const drawing = (this.#drawing ??= new ShotView(this));
      render(drawing.render(), drawing.root ?? this, { host: this });
      drawing.fit();
      render(drawing.render(), this, { host: this });
      Object.assign(drawing, {
        chooseView: (view) => this.#chooseView(view),
        chooseScale: (scale) => {
          this.#drawing.actual = scale === "actual";
          this.#fit();
          closeNativeLayer(drawing.options);
          focusDestination(drawing.scaleTrigger, "move");
        },
        toggleOptions: (event) => {
          event.preventDefault();
          if (isNativeLayer(drawing.options)) closeNativeLayer(drawing.options);
          else {
            focusDestination(drawing.scaleTrigger, "press");
            showNativeLayer(drawing.options, { source: drawing.scaleTrigger });
            focusDestination(
              drawing.options.querySelector('[aria-pressed="true"]'),
              "move",
            );
          }
        },
        toggleOutlines: () => {
          this.#drawing.outlines = !this.#drawing.outlines;
          this.#paint();
        },
        changeFull: (event) => {
          this.#drawing.full = event.currentTarget.checked;
          this.#fit();
        },
      });
      for (const [index, viewport] of this.#drawing.viewports.entries()) {
        viewport.addEventListener(
          "scroll",
          () => {
            if (this.#drawing.view !== "compare" || !this.#drawing.actual) return;
            const peer = this.#drawing.viewports[1 - index];
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
        const unregister = [
          registerReadingRegion({
            id: compoundReadingRegionId(this, "capture"),
            host: this,
            body: this.#drawing.stage,
          }),
          ...this.#drawing.viewports.map((body, index) =>
            registerReadingRegion({
              id: compoundReadingRegionId(this, index === 0 ? "before" : "after"),
              host: this.#drawing.frames[index],
              body,
            }),
          ),
        ];
        return () => {
          observer.disconnect();
          window.removeEventListener("resize", refit);
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
      this.#prepare(images, loaded, this.#capture?.metadata ?? this.#drawing.metadata);
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
        if (!this.#drawing.reading) this.#commitImages(capture);
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
      const changed = this.#drawing.images !== capture.images;
      this.#drawing.images = capture.images;
      this.#drawing.metadata = capture.metadata;
      this.#error?.remove();
      this.#error = null;
      if (changed) {
        this.#setPixelUrl(pixels);
        this.#pixelsPainted = pixels ? Promise.resolve() : null;
      }
      this.#fit();
    }

    attributeChangedCallback(name, before, after) {
      if (!this.#drawing || before === after) return;
      if (name === "alt") this.#paint();
      else this.#loadImages();
    }

    #fit() {
      if (!this.#drawing.stage || !this.#drawing.frames.length) return;
      this.#syncComparison();
      // Show the selected presentation before reading its shared allocation.
      keeps(this, "data-lf-shot-mode", this.#drawing.view);
      this.#drawing.fit();
      this.#paint();
      layoutChanged(this);
    }

    #chooseView(view) {
      if (view === this.#drawing.view) return;
      if (view === "pixels") void this.#showPixels();
      else {
        this.#drawing.view = view;
        this.#fit();
        if (view === "flip") this.#requestComparison();
      }
      announce(`Showing ${VIEWS[view].toLowerCase()}`);
    }

    #syncComparison() {
      if (this.#drawing.view !== "flip" && this.#comparison) {
        this.#drawing.position = this.#comparison.position;
        for (const frame of this.#drawing.frames) {
          frame.removeAttribute("slot");
          move(this.#drawing.canvas, frame);
        }
        this.#comparison.remove();
        this.#comparison = null;
      }
      if (
        this.#drawing.view === "flip" &&
        !this.#comparison &&
        customElements.get("wa-comparison")
      ) {
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
          this.#drawing.position = comparison.position;
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
        this.#drawing.canvas.append(comparison);
        this.#comparison = comparison;
        void comparison.updateComplete.then(() => this.#paintHandle());
      }
    }

    #requestComparison() {
      void afterPresentation(async () => {
        await loadComparison();
        if (this.isConnected && this.#drawing.view === "flip") {
          this.#fit();
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
        `Before ${this.#drawing.position}%, after ${100 - this.#drawing.position}%`,
      );
    }

    #paint() {
      if (!this.#drawing) return;
      render(this.#drawing.render(), this, { host: this });
      this.#paintHandle();
      paintKeys();
    }

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
        this.#pixelsPainted = inTurn(async () => {
          const url = await this.#pixelMask(images);
          if (images !== this.#drawing.images) {
            URL.revokeObjectURL(url);
            return;
          }
          this.#setPixelUrl(url);
          this.#paint();
        });
        void this.#pixelsPainted.catch((reason) => {
          if (images === this.#drawing.images) failSoft(this, reason);
        });
      }
      this.#fit();
      return this.#pixelsPainted;
    }

    async #pixelMask(images) {
      const { width, height, data } = await compareImagePixels(...images);
      const canvas = new OffscreenCanvas(width, height);
      canvas.getContext("2d").putImageData(new ImageData(data, width, height), 0, 0);
      const url = URL.createObjectURL(
        await canvas.convertToBlob({ type: "image/png" }),
      );
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

    #setPixelUrl(url) {
      if (this.#drawing.pixelUrl) URL.revokeObjectURL(this.#drawing.pixelUrl);
      this.#drawing.pixelUrl = url;
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
