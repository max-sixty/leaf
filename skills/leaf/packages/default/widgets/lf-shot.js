/* lf-shot: registered before/after screenshots under one draggable divider.
 *
 * The rail's Before/After labels choose their endpoint by click, Enter or Space;
 * comparison controls stay in that rail or in the native divider, leaving captured
 * image content clear of an additional floating action. After the page presents
 * the static flip, Web Awesome upgrades it with pointer dragging and Arrow,
 * Home, and End adjustment. `afterPresentation` keeps that bundle off the
 * presentation path while the page answers for its upgrade as its own arrival.
 * Clicking either image keeps the quick endpoint toggle; clicking the handle
 * only puts the user on it.
 * A small expand link beside each rail label inspects that full-size image in the
 * shared media viewer; modified presses keep their native link destination. The
 * rail reserves its rows before upgrade, with inspection actions below the
 * endpoints on narrow pairs. Print stacks both frames.
 *
 * Once the page has presented, the widget compares the two images pixel for pixel
 * (`runtime/image-difference.js` owns what counts as a difference) and puts its
 * `describeDifference` reading in the rail or Changes tooltip. Every pair says when
 * it is identical, only slightly changed, or changed throughout, so a reader of one side of the divider,
 * or of a screenshot of the page, still learns it. With `outlines`, each frame also
 * outlines its own regions, what changed and what moved, where they sit in that frame,
 * and Changes toggles them together, with the full count on hover. `difference` is
 * that reading, in the images' own pixels, or null for a pair the widget refused;
 * a parent that hides the rail states it from there. With `pixels`, a separate
 * Pixels action opens the after image greyed with each changed pixel painted
 * through `changedPixels`' mask in the theme's warning colour. The mask is built
 * on the first press, since most readers never open it. Pixels again or clicking
 * the picture returns to the comparison as it stood; choosing an endpoint leaves
 * the view.
 * Pairs compare one per frame, so a page of large captures does not hold input for the
 * whole batch.
 *
 * One two-ended rail sticks above the visible frames while CSS moves its active rule. Its
 * labels are generated page words, available to selection, and become the order key
 * above the two stacked frames on paper.
 * A containing inspector calls `inspect({mode, layout, scale, pixelRatio, focus,
 * crop, opacity, labels, captureWidth})`. Mode is compare, overlay or flip; layout is
 * side or stack; scale is the image's CSS-pixel scale; pixelRatio maps the captured
 * CSS pixels to bitmap pixels. Focus is a rectangle in captured CSS pixels, and
 * crop chooses that rectangle instead of marking it on the complete image. Labels
 * name the before and after frames. Optional captureWidth reserves their
 * CSS-pixel width until decode when delivery has supplied no media dimensions.
 * lf-shot owns the frames, labels, crop, outlines, opacity, controls and print view.
 * The containing inspector owns its available box and chooses the scale/layout.
 * `captureGeometry` returns the decoded image dimensions, completion flags and
 * resolved frame border, comparison gap, label and rail heights. `captureload`
 * announces a completed decode; consumers never inspect or restyle frame nodes.
 * `supportsCrop` states whether this browser can crop without distortion.
 * These are local inspection choices, never authored application state.
 * Accessible descriptions update in place when alt changes, retaining the current
 * comparison choice and its focused control. A different image pair is a new shot.
 * Commentary about the change belongs in authored prose around the widget. */
import {
  PRESS,
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
  iconElement,
  nextFrame,
  isCanonicalMediaUrl,
  layoutChanged,
  commands,
  keeps,
  paintKeys,
  plainPress,
  relabel,
  scopedMediaUrl,
  selectableOffer,
  widgetController,
  move,
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

customElements.define(
  "lf-shot",
  class extends HTMLElement {
    #box;
    #alt;
    #comparison;
    #chromeState;
    #chose = false;
    #pixelsShown = false;
    #pixelsView;
    #changes;
    #changesShown = true;
    #pixelsAction;
    #frames = [];
    #inspection;
    #frameLabels = new Map();
    #captions = new Map();
    #openers = new Map();
    #difference = Promise.withResolvers();
    difference = this.#difference.promise;

    static observedAttributes = ["alt"];

    get #controlsEnabled() {
      return !this.#inspection || this.#inspection.mode === "flip";
    }

    get supportsCrop() {
      return globalThis.CSS?.supports?.("object-view-box", "inset(0px)") === true;
    }

    get captureGeometry() {
      const style = getComputedStyle(this);
      const length = (name) => parseFloat(style.getPropertyValue(name));
      const rail = this.querySelector(".lf-shotrail");
      const railStyle = rail && getComputedStyle(rail);
      const railHeight = railStyle
        ? parseFloat(railStyle.height) +
          (railStyle.boxSizing === "border-box"
            ? 0
            : parseFloat(railStyle.paddingTop) +
              parseFloat(railStyle.paddingBottom) +
              parseFloat(railStyle.borderTopWidth) +
              parseFloat(railStyle.borderBottomWidth))
        : 0;
      return {
        images: this.#frames.map((frame) => {
          const image = frame.querySelector("img");
          return {
            width: image.naturalWidth,
            height: image.naturalHeight,
            complete: image.complete,
          };
        }),
        frameBorder: length("--lf-shot-frame-border"),
        labelHeight: length("--lf-shot-label-height"),
        gap: length("--lf-shot-gap"),
        railHeight,
      };
    }

    inspect(configuration) {
      const next = { ...this.#inspection, ...configuration };
      const controlsChanged = this.#controlsEnabled !== (next.mode === "flip");
      this.#inspection = next;
      keeps(this, "data-lf-shot-controls", next.mode === "flip" ? null : "off");
      if (this.#box && controlsChanged) {
        this.#syncComparison();
        this.#requestComparison();
        paintKeys();
      }
      this.#paintInspection();
    }

    #paintInspection() {
      if (!this.#inspection || !this.#frames.length) return;
      const {
        mode,
        layout = "side",
        scale = 1,
        pixelRatio = 1,
        focus = null,
        crop = false,
        opacity = 0.5,
        labels = { before: "Before", after: "After" },
        captureWidth,
      } = this.#inspection;
      const images = this.captureGeometry.images;
      const decoded = images.every((image) => image.width && image.height);
      let error;
      if (focus && !decoded && images.every((image) => image.complete))
        error = "focus needs two decoded images";
      else if (
        focus &&
        decoded &&
        images.some(
          (image) =>
            focus.x + focus.width > image.width / pixelRatio ||
            focus.y + focus.height > image.height / pixelRatio,
        )
      )
        error = `focus ${focus.x},${focus.y} ${focus.width}×${focus.height} CSS px falls outside its captured images`;
      if (error) {
        this.#frames = [];
        failSoft(this, new Error(error));
        return;
      }
      const activeFocus = focus && crop && this.supportsCrop;
      const previous = [
        "data-lf-shot-mode",
        "data-lf-shot-layout",
        "data-lf-shot-crop",
      ].map((name) => this.getAttribute(name));
      let changed = false;
      keeps(this, "data-lf-shot-mode", mode);
      keeps(this, "data-lf-shot-layout", layout);
      keeps(this, "data-lf-shot-focus", Boolean(focus));
      keeps(this, "data-lf-shot-crop", Boolean(activeFocus));
      const set = (name, value) => {
        if (this.style.getPropertyValue(name) !== value) {
          this.style.setProperty(name, value);
          changed = true;
        }
      };
      const sourceWidth =
        this.#frames[0].querySelector("img").naturalWidth / pixelRatio ||
        Number(this.dataset.lfMediaWidth) / pixelRatio ||
        captureWidth;
      const width = activeFocus ? focus.width : sourceWidth;
      if (width) set("--lf-shot-frame-width", `${Math.max(1, width * scale)}px`);
      set("--lf-shot-opacity", String(opacity));
      for (const frame of this.#frames) {
        const state = frame.dataset.lfState;
        let label = this.#frameLabels.get(state);
        if (mode === "compare") {
          if (!label) {
            label = document.createElement("span");
            label.className = "lf-shot-frame-label lf-ui";
            label.dataset.lfGen = "1";
            label.ariaHidden = "true";
            this.#frameLabels.set(state, label);
          }
          keeps(
            label,
            "data-label",
            state === "before" && layout === "stack"
              ? `${labels.before} · ${labels.after} below`
              : labels[state],
          );
          if (label.parentNode !== frame) move(frame, label, frame.firstChild);
        } else label?.remove();
        if (focus) {
          const image = frame.querySelector("img");
          const width = image.naturalWidth;
          const height = image.naturalHeight;
          const view =
            `inset(${focus.y * pixelRatio}px ${width - (focus.x + focus.width) * pixelRatio}px ` +
            `${height - (focus.y + focus.height) * pixelRatio}px ${focus.x * pixelRatio}px)`;
          if (frame.style.getPropertyValue("--lf-shot-focus-view") !== view)
            frame.style.setProperty("--lf-shot-focus-view", view);
        }
      }
      if (focus) {
        for (const key of ["x", "y", "width", "height"])
          set(`--lf-shot-focus-${key}`, `${focus[key] * scale}px`);
      }
      const decodedWidth =
        this.#frames[0].querySelector("img").naturalWidth / pixelRatio;
      if (decodedWidth) set("--lf-shot-capture-width", `${decodedWidth}px`);
      const current = [
        "data-lf-shot-mode",
        "data-lf-shot-layout",
        "data-lf-shot-crop",
      ].map((name) => this.getAttribute(name));
      if (changed || previous.some((value, index) => value !== current[index]))
        layoutChanged(this);
    }

    connectedCallback() {
      if (!once(this)) return;
      const shots = [];

      const rail = document.createElement("div");
      rail.className = "lf-shotrail";
      rail.dataset.lfGen = "1";
      for (const state of ["before", "after"]) {
        const caption = selectableOffer("button", "lf-shotcap");
        caption.dataset.lfState = state;
        relabel(caption, state, { says: true });
        this.#captions.set(state, caption);
        rail.append(caption);
      }
      this.append(rail);

      for (const state of ["before", "after"]) {
        const frame = document.createElement("div");
        frame.className = "lf-shotframe";
        frame.dataset.lfGen = "1";
        frame.dataset.lfState = state;

        const img = document.createElement("img");
        // Opaque samples need CORS mode to keep pixels readable for comparison.
        img.crossOrigin = "anonymous";
        const source = this.getAttribute(state);
        img.src = isCanonicalMediaUrl(source) ? scopedMediaUrl(source) : source;
        shots.push(img);
        frame.append(img);
        this.#frames.push(frame);
        this.append(frame);

        // Each label's link sits on its inner side, so the rail reads
        // BEFORE ⤢ … ⤢ AFTER in document and visual order alike.
        const open = offer("a", "lf-media-open lf-shot-open");
        open.dataset.lfShotOpen = state;
        open.href = img.src;
        open.dataset.lfMediaUrl = img.src;
        open.append(iconElement("expand", "lf-action-icon"));
        this.#openers.set(state, open);
        const caption = this.#captions.get(state);
        if (state === "before") caption.after(open);
        else caption.before(open);
      }

      const box = offer("input", "lf-shotflip", undefined, "checkbox");
      this.#box = box;
      box.name = "comparison";
      for (const [state, caption] of this.#captions) {
        caption.addEventListener("click", () => this.#show(state));
        commands(caption, "On a screenshot", [
          {
            id: `screenshot.${state}`,
            keys: PRESS,
            title: `show ${state}`,

            // Selectable captions own activation even at the selected endpoint:
            // Space must not fall through to the browser's page scrolling.
            when: () => this.#controlsEnabled,
            run: () => caption.click(),
          },
        ]);
      }
      box.addEventListener("change", () => {
        this.#chose = true;
        this.#pixelsShown = false;
        this.#paint();
      });
      // The native checkbox owns endpoint toggling until the divider upgrades.
      commands(box, "On a screenshot", [
        {
          id: "screenshot.toggle",
          keys: [" "],
          title: () => `show ${this.#nextState()}`,
          when: () => this.#controlsEnabled,
          run: () => this.#show(this.#nextState()),
        },
      ]);
      this.append(box);
      this.#paintAlt();
      this.#paintInspection();

      // A visual-review run creates shots after authored descriptor capture. Its
      // authored controller explicitly owns that generated child's preparation;
      // standalone authored shots own their presentation themselves.
      const present =
        this._lfPresentGenerated ??
        ((promise) => widgetController(this).present(promise));
      const registered = this.register(shots);
      present(registered);
      void registered.then(() => this.#requestComparison());
      this.#difference.resolve(
        registered.then((aligned) =>
          aligned
            ? afterPresentation(() => inTurn(() => this.#markDifference(shots)))
            : null,
        ),
      );
      void this.difference.catch((reason) => failSoft(this, reason));
    }

    #paintAlt() {
      this.#alt = this.getAttribute("alt");
      for (const state of ["before", "after"])
        keeps(this.#captions.get(state), "aria-label", `${state} — ${this.#alt}`);
      if (this.#pixelsView)
        keeps(this.#pixelsView, "aria-label", `changed pixels: ${this.#alt}`);
      for (const frame of this.#frames) {
        const state = frame.dataset.lfState;
        const alt = `${state}: ${this.#alt}`;
        frame.querySelector("img").alt = alt;
        const open = this.#openers.get(state);
        open.dataset.lfMediaAlt = alt;
        open.dataset.lfMediaCaption = alt;
        keeps(open, "aria-label", `Open ${state} image — ${this.#alt}`);
        keeps(open, "title", `Open ${state} image`);
      }
      keeps(this.#box, "aria-label", `Compare before and after — ${this.#alt}`);
      this.#paint();
    }

    attributeChangedCallback(name) {
      if (!this.isConnected || !this.#box) return;
      if (name === "alt") this.#paintAlt();
    }

    #syncComparison() {
      const enabled =
        this.#controlsEnabled &&
        this.#box.parentNode === this &&
        customElements.get("wa-comparison");
      if (enabled && !this.#comparison) {
        const comparison = document.createElement("wa-comparison");
        comparison.className = "lf-shotcomparison";
        comparison.dataset.lfGen = "1";
        comparison.position = 100 - (this.#chose ? this.#position() : 50);
        const handle = document.createElement("span");
        handle.className = "lf-shot-handle";
        handle.slot = "handle";
        handle.ariaHidden = "true";
        comparison.append(handle);
        // Web Awesome draws its `after` slot on the inline-start side of the divider,
        // which is the side the rail labels before, so each frame takes the other's
        // slot and the component's position is the before frame's share.
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
          this.#chose = true;
          this.#pixelsShown = false;
          this.#paint();
        });
        comparison.addEventListener("pointerdown", (event) => {
          if (!event.isPrimary || event.button !== 0) return;
          dragged = false;
          // The vendor cancels native focus when it starts dragging. The handle
          // remains the input destination, so arrows can continue the adjustment.
          const target = handleOf(event);
          if (target) focusDestination(target, "press");
        });
        comparison.addEventListener("click", (event) => {
          const onHandle = handleOf(event);
          if (!dragged && !onHandle && plainPress(event)) this.#show(this.#nextState());
        });
        commands(comparison, "On a screenshot divider", [
          {
            id: "screenshot.adjust",
            keys: ["ArrowLeft", "ArrowRight"],
            title: "adjust the comparison",
            repeat: true,
          },
          {
            id: "screenshot.edge",
            keys: ["Home", "End"],
            title: "show before or after",
          },
        ]);
        move(this, comparison, this.#box);
        this.#comparison = comparison;
        void comparison.updateComplete?.then(() => this.#paint());
      } else if (!enabled && this.#comparison) {
        for (const frame of this.#frames) {
          frame.removeAttribute("slot");
          move(this, frame, this.#comparison);
        }
        this.#comparison.remove();
        this.#comparison = null;
        this.#chromeState = null;
        this.#paint();
      }
    }

    async #upgradeComparison() {
      if (!this.isConnected || this.#box.parentNode !== this || !this.#controlsEnabled)
        return;
      await loadComparison();
      if (this.isConnected) this.#syncComparison();
    }

    #requestComparison() {
      if (!this.#controlsEnabled) return;
      void afterPresentation(() => this.#upgradeComparison()).catch((reason) =>
        failSoft(this, reason),
      );
    }

    // Each region is placed in shares of the pair's frame, the natural width by the
    // taller image's height that `--lf-shot-ratio` sizes, so the marks scale with the
    // images at every width.
    async #markDifference(shots) {
      const reading = await compareImages(...shots);
      const { width, height, regions } = reading;
      const share = (length, whole) => `${(100 * length) / whole}%`;
      for (const frame of this.#frames) {
        const marks = document.createElement("div");
        marks.className = "lf-shotdiff";
        marks.dataset.lfGen = "1";
        marks.ariaHidden = "true";
        for (const region of regions) {
          if (region.side !== frame.dataset.lfState) continue;
          const mark = document.createElement("span");
          mark.dataset.lfShotMark = region.kind;
          mark.style.setProperty("--lf-shot-x", share(region.x, width));
          mark.style.setProperty("--lf-shot-y", share(region.y, height));
          mark.style.setProperty("--lf-shot-w", share(region.width, width));
          mark.style.setProperty("--lf-shot-h", share(region.height, height));
          marks.append(mark);
        }
        frame.append(marks);
      }
      const kind = differenceKind(reading);
      const count = document.createElement("span");
      count.className = "lf-shotdelta";
      count.dataset.lfShotDelta = kind;
      const description = describeDifference(reading);
      if (kind !== "areas") relabel(count, description, { says: false });
      if (this.hasAttribute("outlines") && kind === "areas") {
        const changes = offer("button", "lf-shotchanges", "Changes");
        changes.title = description;
        keeps(changes, "aria-description", description);
        changes.addEventListener("click", () => {
          this.#changesShown = !this.#changesShown;
          this.#pixelsShown = false;
          this.#paint();
        });
        commands(changes, "On a screenshot", [
          {
            id: "screenshot.changes",
            keys: PRESS,
            title: "toggle change outlines",
            when: () => this.#controlsEnabled,
            run: () => changes.click(),
          },
        ]);
        this.#changes = changes;
        count.append(changes);
      }
      if (this.hasAttribute("pixels")) {
        const pixels = offer("button", "lf-shotpixels-action", "Pixels");
        pixels.addEventListener("click", () => {
          if (this.#pixelsShown) {
            this.#pixelsShown = false;
            this.#paint();
          } else this.#showPixels(shots);
        });
        commands(pixels, "On a screenshot", [
          {
            id: "screenshot.pixels",
            keys: PRESS,
            title: () => pixels.title.toLowerCase(),
            when: () => this.#controlsEnabled,
            run: () => pixels.click(),
          },
        ]);
        this.#pixelsAction = pixels;
        count.append(pixels);
      }
      this.#openers.get("before").after(count);
      this.#paint();
      return reading;
    }

    // The Pixels view: the after image greyed, under the changed pixels that a mask
    // paints in the theme's colour. The view stands in the press's turn; the mask is
    // read on the next frame and its paint lands when encoded.
    #showPixels(shots) {
      this.#chose = true;
      this.#pixelsShown = true;
      if (!this.#pixelsView) {
        const view = document.createElement("div");
        view.className = "lf-shotpixels";
        view.dataset.lfGen = "1";
        view.role = "img";
        keeps(view, "aria-label", `changed pixels: ${this.#alt}`);
        const ground = document.createElement("img");
        ground.alt = "";
        ground.crossOrigin = "anonymous";
        ground.src = shots[1].src;
        const paint = document.createElement("span");
        view.append(ground, paint);
        view.addEventListener("click", (event) => {
          if (!plainPress(event)) return;
          this.#pixelsShown = false;
          this.#paint();
        });
        // Before the rail in the tree, so the sticky rail, at the same z-index, stands
        // over it.
        this.prepend(view);
        this.#pixelsView = view;
        nextFrame(() => {
          const { width, height, data } = compareImagePixels(...shots);
          const canvas = new OffscreenCanvas(width, height);
          canvas
            .getContext("2d")
            .putImageData(new ImageData(data, width, height), 0, 0);
          void canvas
            .convertToBlob({ type: "image/png" })
            .then((blob) =>
              paint.style.setProperty(
                "--lf-shot-pixels",
                `url("${URL.createObjectURL(blob)}")`,
              ),
            )
            .catch((reason) => failSoft(this, reason));
        });
      }
      this.#paint();
    }

    #show(state) {
      this.#chose = true;
      this.#pixelsShown = false;
      if (this.#comparison) {
        const position = state === "after" ? 0 : 100;
        if (this.#comparison.position !== position)
          this.#comparison.position = position;
        else this.#paint();
        return;
      }
      const checked = state === "after";
      if (this.#box.checked === checked) {
        this.#paint();
        return;
      }
      this.#box.checked = checked;
      this.#box.dispatchEvent(new Event("change", { bubbles: true }));
    }

    #nextState() {
      return this.#position() > 50 ? "before" : "after";
    }

    // The after frame's share of the pair: 0 shows before whole, 100 after.
    #position() {
      if (this.#comparison) return Number((100 - this.#comparison.position).toFixed(2));
      return this.#box.checked ? 100 : 0;
    }

    #paint() {
      const position = this.#position();
      const handle = this.#comparison?.shadowRoot?.querySelector('[role="scrollbar"]');
      if (handle) {
        const before = Number((100 - position).toFixed(2));
        keeps(handle, "aria-label", `Before and after — ${this.#alt}`);
        keeps(handle, "aria-valuetext", `Before ${before}%, after ${position}%`);
        handle.style.setProperty("--lf-focus-ring", "shot");
      }
      const chromeState = this.#pixelsShown
        ? "pixels"
        : position === 0
          ? "before"
          : position === 100
            ? "after"
            : position > 50
              ? "after-side"
              : "before-side";
      // The covered comparison leaves the tab order while the view stands over it,
      // including a comparison that upgrades under it.
      for (const node of [this.#comparison, this.#box])
        node?.toggleAttribute("inert", this.#pixelsShown);
      keeps(this, "data-lf-shot-changes", this.#changesShown ? null : "off");
      if (this.#changes) keeps(this.#changes, "aria-pressed", this.#changesShown);
      if (this.#pixelsAction) {
        const description = this.#pixelsShown
          ? "Hide changed pixels"
          : "Show changed pixels";
        keeps(this.#pixelsAction, "title", description);
        keeps(this.#pixelsAction, "aria-description", description);
      }
      if (chromeState === this.#chromeState) return;
      const previousChromeState = this.#chromeState;
      this.#chromeState = chromeState;
      this.#box.checked = position > 50;
      keeps(this, "data-lf-shot-view", this.#pixelsShown ? "pixels" : null);
      for (const [state, caption] of this.#captions)
        keeps(
          caption,
          "aria-pressed",
          !this.#pixelsShown && position === (state === "after" ? 100 : 0),
        );
      if (chromeState === "pixels" || previousChromeState === "pixels")
        announce(this.#pixelsShown ? "Showing changed pixels" : "Showing comparison");
      paintKeys();
    }

    // Both frames render at the frame's width, so a pair shot at two different
    // viewports is scaled by two different factors and every line in it lands
    // somewhere new. The flip then says the whole page changed, which is the one
    // failure this widget cannot afford: it is silent, it is convincing, and the
    // user has no way to tell it from the truth. Heights may differ freely —
    // content reflowing taller is a real thing to see, and it stays registered.
    // Answers whether the pair decoded at one width, which is when comparing it
    // pixel for pixel means anything.
    async register(shots) {
      await Promise.all(shots.map((img) => img.decode().catch(() => {})));
      this.#paintInspection();
      this.dispatchEvent(new Event("captureload"));
      if (!this.#frames.length) return false;
      const [before, after] = shots.map((img) => img.naturalWidth);
      if (before && after && before !== after) {
        failSoft(
          this,
          new Error(
            `before is ${before}px wide and after is ${after}px — a pair has to be shot ` +
              `at one viewport, or the flip moves everything`,
          ),
        );
        return false;
      }
      const height = Math.max(...shots.map((img) => img.naturalHeight));
      if (before && height)
        this.style.setProperty("--lf-shot-ratio", `${before} / ${height}`);
      return Boolean(before && after);
    }
  },
);
