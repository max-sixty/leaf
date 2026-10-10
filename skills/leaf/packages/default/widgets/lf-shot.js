/* lf-shot: registered before/after screenshots under one draggable divider.
 *
 * The target's shared margin entry shows a split circle: left filled for before, right for after.
 * Enter, Space, and clicks flip that projection between the endpoints without moving it.
 * Each rail label chooses its endpoint. Once the page has presented the static flip,
 * Web Awesome progressively upgrades it with pointer dragging and Arrow, Home, and End
 * adjustment; its bundle is not on the presentation path, and `afterPresentation` is
 * what holds it there, so the page still answers for the upgrade as an arrival of its
 * own. A click on either image keeps
 * the quick endpoint toggle, while a click on the handle only puts the user on it.
 * Separate Open before / Open after links inspect either full-size image in the
 * shared media viewer; modified presses keep their native link destination.
 * Both rail rows are reserved before upgrade. Print stacks both frames.
 *
 * Once the page has presented, the widget compares the two images pixel for pixel
 * (`runtime/image-difference.js` owns what counts as a difference) and puts its
 * `describeDifference` between the rail labels. Every pair says when it is identical,
 * only slightly changed, or changed throughout, so a reader of one side of the divider,
 * or of a screenshot of the page, still learns it. With `outlines`, each frame also
 * outlines its own regions, what changed and what moved, where they sit in that frame,
 * and the rail counts them. `difference` is that reading, in the images' own pixels,
 * or null for a pair the widget refused; a parent that hides the rail states it from
 * there.
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
  commandScope,
  compareImages,
  describeDifference,
  differenceKind,
  once,
  offer,
  failSoft,
  nextFrame,
  isCanonicalMediaUrl,
  layoutChanged,
  commands,
  keeps,
  contributionEntry,
  paintKeys,
  relabel,
  registerContribution,
  scopedMediaUrl,
  selectableOffer,
  widgetController,
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
const loadComparison = () =>
  (comparisonReady ??= import("../vendor/webawesome.esm.js"));

customElements.define(
  "lf-shot",
  class extends HTMLElement {
    #box;
    #alt;
    #margin;
    #flip;
    #comparison;
    #chromeState;
    #chose = false;
    #frames = [];
    #inspection;
    #frameLabels = new Map();
    #captions = new Map();
    #openers = new Map();
    #settleDifference;
    difference = new Promise((resolve) => {
      this.#settleDifference = resolve;
    });

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
        this.#offer();
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
        this.#margin?.unregister();
        this.#margin = null;
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
          if (label.parentNode !== frame) frame.prepend(label);
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
      if (!once(this)) {
        this.#offer();
        return;
      }
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
        const source = this.getAttribute(state);
        img.src = isCanonicalMediaUrl(source) ? scopedMediaUrl(source) : source;
        shots.push(img);
        frame.append(img);
        this.#frames.push(frame);
        this.append(frame);

        const open = offer("a", "lf-media-open lf-shot-open", `Open ${state}`);
        open.dataset.lfShotOpen = state;
        open.href = img.src;
        open.dataset.lfMediaUrl = img.src;
        this.#openers.set(state, open);
        rail.append(open);
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
        this.#paint();
      });
      // One declaration, two controls: the native checkbox the user stands on inside
      // the widget, and the margin entry the same flip is projected onto. A margin entry
      // is generated elsewhere, so ancestry cannot find this row for it — the capability
      // is how the flip keeps its name on both (`runtime/keyboard/scopes.js`,
      // `commandScope`).
      this.#flip = commandScope("On a screenshot", [
        {
          id: "screenshot.toggle",
          keys: [" "],
          title: () => `show ${this.#nextState()}`,
          when: () => this.#controlsEnabled,
          run: () => this.#show(this.#nextState()),
        },
      ]);
      commands(box, this.#flip);
      this.append(box);
      this.#paintAlt();
      this.#paintInspection();
      this.#offer();
      // A visual-review run creates shots after authored descriptor capture. Its
      // authored controller explicitly owns that generated child's preparation;
      // standalone authored shots own their presentation themselves.
      const present =
        this._lfPresentGenerated ??
        ((promise) => widgetController(this).present(promise));
      const registered = this.register(shots);
      present(registered);
      void registered.then(() => this.#requestComparison());
      this.#settleDifference(
        registered.then((aligned) =>
          aligned
            ? afterPresentation(() => inTurn(() => this.#markDifference(shots)))
            : null,
        ),
      );
      void this.difference.catch((reason) => failSoft(this, reason));
    }

    disconnectedCallback() {
      this.#margin?.unregister();
      this.#margin = null;
    }

    #paintAlt() {
      this.#alt = this.getAttribute("alt");
      for (const [state, caption] of this.#captions)
        keeps(caption, "aria-label", `${state} — ${this.#alt}`);
      for (const frame of this.#frames) {
        const state = frame.dataset.lfState;
        const alt = `${state}: ${this.#alt}`;
        frame.querySelector("img").alt = alt;
        const open = this.#openers.get(state);
        open.dataset.lfMediaAlt = alt;
        open.dataset.lfMediaCaption = alt;
        keeps(open, "aria-label", `Open ${state} image — ${this.#alt}`);
      }
      keeps(this.#box, "aria-label", `Compare before and after — ${this.#alt}`);
      this.#paint();
      this.#margin?.update();
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
        comparison.addEventListener("change", () => {
          dragged = true;
          this.#chose = true;
          this.#paint();
        });
        comparison.addEventListener("pointerdown", (event) => {
          if (event.button === 0) dragged = false;
        });
        comparison.addEventListener("click", (event) => {
          const onHandle = event
            .composedPath()
            .some(
              (node) =>
                node instanceof Element &&
                node.getAttribute("part")?.split(/\s+/).includes("handle"),
            );
          if (
            !dragged &&
            !onHandle &&
            !event.altKey &&
            !event.ctrlKey &&
            !event.metaKey &&
            !event.shiftKey
          )
            this.#show(this.#nextState());
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
        this.insertBefore(comparison, this.#box);
        this.#comparison = comparison;
        void comparison.updateComplete?.then(() => this.#paint());
      } else if (!enabled && this.#comparison) {
        for (const frame of this.#frames) {
          frame.removeAttribute("slot");
          this.insertBefore(frame, this.#comparison);
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
      const count = document.createElement("span");
      count.className = "lf-shotdelta";
      count.dataset.lfShotDelta = differenceKind(reading);
      relabel(count, describeDifference(reading), { says: false });
      this.#captions.get("before").after(count);
      return reading;
    }

    #show(state) {
      this.#chose = true;
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
      const chromeState =
        position === 0
          ? "before"
          : position === 100
            ? "after"
            : position > 50
              ? "after-side"
              : "before-side";
      if (chromeState === this.#chromeState) return;
      this.#chromeState = chromeState;
      this.#box.checked = position > 50;
      for (const [state, caption] of this.#captions) {
        const endpoint = state === "after" ? 100 : 0;
        keeps(caption, "aria-pressed", position === endpoint);
      }
      this.#margin?.update();
      paintKeys();
    }

    #offer() {
      if (!this.#controlsEnabled) {
        this.#margin?.unregister();
        this.#margin = null;
        return;
      }
      if (!this.#box || this.#margin) return;
      this.#margin = registerContribution({
        key: `shot:${this.id}`,
        target: () => this,
        read: () => {
          const next = this.#nextState();
          const label = `Show ${next}`;
          const position = this.#position();
          return {
            subject: null,
            state: "idle",
            side: "before",
            notice: null,
            entries: [
              contributionEntry({
                key: "toggle",
                icon: position > 50 ? "compare-after" : "compare-before",
                label,
                accessibleLabel: `${label} — ${this.#alt}`,
                activation: "screenshot.toggle",
                className: "lf-shot-toggle",
                scope: this.#flip,
              }),
            ],
            readings: [],
          };
        },
      });
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
