/* lf-shot owns screenshot inspection: paired frames, slider, pixel difference,
 * outlines, scale, crop and scrolling. A containing package supplies only capture
 * metadata through inspect({pixelRatio, captureWidth, focus, labels}) and allocates
 * its box. Fit keeps both frames in the allocated box. Actual size pans their
 * images together inside those same windows, keeping both labels and views visible.
 * Both frames always share one source scale. The retained header belongs to the
 * allocated viewport, outside the image canvas. Labels and controls never move
 * when views or scale change; only allocation width chooses its one- or two-row
 * layout. Source labels are passive, and images never change comparison modes.
 * In Slider, a plain image click alternates the divider's Before/After endpoints;
 * dragging and the divider's keyboard controls retain continuous adjustment.
 * A stacked pair also labels each frame, since the header's left/right bookends
 * cannot identify vertically arranged images.
 *
 * A bounded pair chooses the orientation that gives the images the larger scale;
 * in ordinary flow, wide frames stack instead of shrinking below half scale.
 * Fit recalculates for that layout; 100% retains the captured CSS
 * scale, or bitmap pixels when no capture ratio is supplied. Inspection choices
 * belong to this element's lifetime, not the document's application state.
 *
 * Images and their source-coordinate marks share one clipped plane. Cropping moves
 * that plane, including pixel masks, rather than having each renderer reinterpret
 * the focus rectangle. Pixel comparison runs after presentation, one pair per
 * frame. The expensive pixel masks and Web Awesome slider load only on selection.
 * The native image planes remain visible while either prepares. The divider's exact
 * position survives switching views. Original-image links use the shared viewer.
 * Print shows both complete original images. */
// A containing widget can create a pair absent from the authored document.
import "/vendor/lf-shot-initial.js";
import {
  afterPresentation,
  announce,
  compareImagePixels,
  compareImages,
  describeDifference,
  differenceKind,
  once,
  offer,
  failSoft,
  focusDestination,
  showNativeLayer,
  closeNativeLayer,
  isNativeLayer,
  iconElement,
  initialRender,
  nextFrame,
  isCanonicalMediaUrl,
  layoutChanged,
  commands,
  keeps,
  paintKeys,
  plainPress,
  relabel,
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
} from "./shot-view.js";

customElements.define(
  "lf-shot",
  class extends HTMLElement {
    #stage;
    #canvas;
    #toolbar;
    #delta;
    #legend;
    #scaleReading;
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
    #view = "compare";
    #outlines = false;
    #actual = false;
    #full = false;
    #metadata = {};
    #reading;
    #pixelsView;
    #pixelsPainted;
    #difference = Promise.withResolvers();
    difference = this.#difference.promise;
    static observedAttributes = ["alt"];

    inspect({ pixelRatio, captureWidth, focus, labels }) {
      this.#metadata = { pixelRatio, captureWidth, focus, labels };
      this.#fit();
      this.#paintAlt();
    }

    connectedCallback() {
      if (!once(this)) return;
      const drawing = initialRender(this);
      this.#toolbar = drawing.toolbar;
      this.#viewButtons = drawing.views.choices;
      this.#scaleButtons = drawing.scale.choices;
      this.#outlinesButton = drawing.outlines;
      this.#scaleTrigger = drawing.scaleTrigger;
      this.#options = drawing.options;
      this.#fullInput = drawing.full.input;
      this.#fullLabel = drawing.full.label;
      this.#scaleReading = drawing.scaleReading;
      this.#stage = drawing.stage;
      this.#canvas = drawing.canvas;
      this.#frames = drawing.frames;
      this.#viewports = drawing.viewports;
      this.#shots = drawing.shots;
      this.#captions = drawing.captions;
      this.#frameCaptions = drawing.frameCaptions;
      this.#openers = drawing.openers;
      this.#delta = drawing.delta;
      this.#legend = drawing.legend;
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
      drawing.scaleIcon.append(iconElement("down", "lf-action-icon"));
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
      for (const [index, state] of ["before", "after"].entries()) {
        const viewport = this.#viewports[index];
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
        const image = this.#shots[index];
        const source = this.getAttribute(state);
        image.src = isCanonicalMediaUrl(source) ? scopedMediaUrl(source) : source;
        const open = this.#openers.get(state);
        open.href = image.src;
        open.dataset.lfMediaUrl = image.src;
        open.prepend(iconElement("expand", "lf-action-icon"));
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
      const present =
        /** @type {{_lfPresentGenerated?: (promise: Promise<unknown>) => void}} */ (
          this
        )._lfPresentGenerated ?? ((promise) => widgetController(this).present(promise));
      const registered = this.#register();
      present(registered);
      this.#difference.resolve(
        registered.then((aligned) =>
          aligned
            ? afterPresentation(() => inTurn(() => this.#markDifference()))
            : null,
        ),
      );
      void this.difference.catch((reason) => failSoft(this, reason));
    }

    attributeChangedCallback() {
      if (this.#toolbar) this.#paintAlt();
    }

    #paintAlt() {
      if (!this.#toolbar) return;
      const alt = this.getAttribute("alt");
      const labels = this.#metadata.labels ?? { before: "Before", after: "After" };
      for (const [index, state] of ["before", "after"].entries()) {
        relabel(this.#captions.get(state), labels[state], { says: true });
        relabel(this.#frameCaptions.get(state), labels[state], { says: false });
        keeps(this.#captions.get(state), "aria-label", `${labels[state]} — ${alt}`);
        keeps(this.#captions.get(state), "title", labels[state]);
        keeps(this.#frameCaptions.get(state), "title", labels[state]);
        keeps(this.#shots[index], "alt", `${state}: ${alt}`);
        keeps(this.#viewports[index], "aria-label", `${labels[state]} — ${alt}`);
        const open = this.#openers.get(state);
        keeps(open, "data-lf-media-alt", `${state}: ${alt}`);
        keeps(open, "data-lf-media-caption", `${state}: ${alt}`);
        keeps(open, "aria-label", `Open ${state} image — ${alt}`);
        keeps(open, "title", `Open ${state} image`);
      }
      if (this.#pixelsView)
        keeps(this.#pixelsView, "aria-label", `changed pixels: ${alt}`);
      keeps(this.#stage, "aria-label", `Screenshot comparison — ${alt}`);
      this.#paintHandle();
    }

    #fit() {
      if (!this.#stage || !this.#frames.length) return;
      const available = this.#stage.clientWidth;
      if (!available) return; // Hidden cases retain their last inspection until shown.
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
      if (
        focus &&
        this.#shots.every((image) => image.complete) &&
        this.#shots.some((image) => !image.naturalWidth)
      ) {
        failSoft(this, new Error("focus needs two decoded images"));
        return;
      }
      if (
        focus &&
        ((sourceWidth && focus.x + focus.width > sourceWidth) ||
          this.#shots.some(
            (image) =>
              image.naturalHeight &&
              focus.y + focus.height > image.naturalHeight / ratio,
          ))
      ) {
        failSoft(
          this,
          new Error(
            `focus ${focus.x},${focus.y} ${focus.width}×${focus.height} CSS px falls outside its captured images`,
          ),
        );
        return;
      }
      const geometry = fitShotGeometry({
        available,
        availableHeight:
          getComputedStyle(this).getPropertyValue("--lf-holds-height").trim() === "1"
            ? this.#stage.clientHeight
            : undefined,
        labelHeight: parseFloat(
          getComputedStyle(this.#frameCaptions.get("before").parentElement).blockSize,
        ),
        sourceWidth,
        sourceHeight,
        focus,
        full: this.#full,
        actual: this.#actual,
        view: this.#shownView,
        gap: parseFloat(getComputedStyle(this).getPropertyValue("--lf-shot-gap")),
      });
      if (!geometry) return;
      applyShotGeometry(this, geometry, keeps);
      this.#fullLabel.toggleAttribute("hidden", !focus);
      this.#fullInput.checked = this.#full;
      const fitDescription = `Fit · ${Math.round(geometry.fitScale * 100)}%`;
      keeps(this.#scaleButtons.get("fit"), "title", fitDescription);
      keeps(this.#scaleTrigger, "title", this.#actual ? "100%" : fitDescription);
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
        const comparison = offer("wa-comparison", "lf-shotcomparison");
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

    get #shownView() {
      // Until the optional divider is mounted, keep the usable pair and its
      // matching geometry. Requested view buttons still reflect the user's choice.
      return this.#view === "flip" && !this.#comparison ? "compare" : this.#view;
    }

    #paint() {
      if (!this.#toolbar) return;
      keeps(this, "data-lf-shot-mode", this.#shownView);
      keeps(this, "data-lf-shot-outlines", this.#outlines);
      this.#viewButtons.get("pixels").toggleAttribute("disabled", !this.#reading);
      for (const [view, button] of this.#viewButtons)
        keeps(button, "aria-pressed", view === this.#view);
      for (const [scale, button] of this.#scaleButtons)
        keeps(button, "aria-pressed", (scale === "actual") === this.#actual);
      relabel(this.#scaleReading, this.#actual ? "100%" : "Fit", { says: false });
      keeps(this.#outlinesButton, "aria-pressed", this.#outlines);
      this.#outlinesButton.toggleAttribute(
        "disabled",
        this.#view === "pixels" || !this.#reading?.regions.length,
      );
      this.#legend.toggleAttribute("hidden", this.#view !== "pixels");
      this.#syncComparison();
      this.#paintHandle();
      paintKeys();
    }

    async #markDifference() {
      const reading = await compareImages(...this.#shots);
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
        frame.querySelector(".lf-shotplane").append(marks);
      }
      const description = describeDifference(reading);
      this.#delta.dataset.lfShotDelta = differenceKind(reading);
      relabel(this.#delta, description, { says: false });
      this.#outlinesButton.setAttribute("aria-description", description);
      this.#paint();
      return reading;
    }

    #showPixels() {
      this.#view = "pixels";
      if (!this.#pixelsView) {
        const view = offer("div", "lf-shotpixels lf-shotimage");
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
        this.#pixelsPainted = inTurn(async () => {
          const { width, height, ...masks } = compareImagePixels(...this.#shots);
          await Promise.all(
            paints.map(async (paint) => {
              const canvas = new OffscreenCanvas(width, height);
              canvas
                .getContext("2d")
                .putImageData(
                  new ImageData(masks[paint.dataset.lfShotSide], width, height),
                  0,
                  0,
                );
              const blob = await canvas.convertToBlob({ type: "image/png" });
              paint.style.setProperty(
                "--lf-shot-pixels",
                `url("${URL.createObjectURL(blob)}")`,
              );
            }),
          );
        });
        void this.#pixelsPainted.catch((reason) => failSoft(this, reason));
      }
      this.#syncComparison();
      this.#fit();
      this.#paint();
      return this.#pixelsPainted;
    }

    async #register() {
      await Promise.all(this.#shots.map((image) => image.decode().catch(() => {})));
      const [before, after] = this.#shots.map((image) => image.naturalWidth);
      if (before && after && before !== after) {
        failSoft(
          this,
          new Error(
            `before is ${before}px wide and after is ${after}px — a pair has to be shot at one viewport, or the flip moves everything`,
          ),
        );
        return false;
      }
      this.#fit();
      this.dispatchEvent(new Event("captureload"));
      return Boolean(before && after);
    }
  },
);
