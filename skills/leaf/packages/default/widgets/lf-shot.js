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
 * Print stacks both frames.
 *
 * Once the page has presented, the widget compares the two images pixel for pixel
 * (`runtime/image-difference.js` owns what counts as a difference) and outlines each
 * region that changed over both frames, with a count between the rail labels. A reader
 * looking at one side of the divider, or at a screenshot of the page, then still sees
 * where the pair differs, and that it differs nowhere when the two are one picture.
 * `difference` is that reading, `{width, height, changed, regions}` in the images' own
 * pixels, or null for a pair the widget refused; a parent that hides the rail states
 * it from there. Pairs compare one per frame, so a page of
 * large captures does not hold input for the whole batch.
 *
 * One two-ended rail stays fixed above the frames while CSS moves its active rule. Its
 * labels are generated page words, available to selection, and become the order key
 * above the two stacked frames on paper.
 * A parent that reuses the aligned frames under another inspector sets
 * `data-lf-shot-controls="off"`; lf-shot then withdraws its commands and margin action
 * and leaves the native checkbox as the flip.
 * Commentary about the change belongs in authored prose around the widget. */
import {
  PRESS,
  afterPresentation,
  commandScope,
  compareImages,
  once,
  offer,
  failSoft,
  nextFrame,
  isCanonicalMediaUrl,
  commands,
  marginEntry,
  paintKeys,
  relabel,
  registerMarginContribution,
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
    #captions = new Map();
    #settleDifference;
    difference = new Promise((resolve) => {
      this.#settleDifference = resolve;
    });

    static observedAttributes = ["data-lf-shot-controls"];

    connectedCallback() {
      if (!once(this)) {
        this.#offer();
        return;
      }
      const alt = this.getAttribute("alt");
      this.#alt = alt;
      const shots = [];

      const rail = document.createElement("div");
      rail.className = "lf-shotrail";
      rail.dataset.lfGen = "1";
      for (const state of ["before", "after"]) {
        const caption = selectableOffer("button", "lf-shotcap");
        caption.dataset.lfState = state;
        caption.ariaLabel = `${state} — ${alt}`;
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
        img.alt = `${state}: ${alt}`;
        shots.push(img);
        frame.append(img);
        this.#frames.push(frame);
        this.append(frame);
      }

      const box = offer("input", "lf-shotflip", undefined, "checkbox");
      this.#box = box;
      box.name = "comparison";
      box.ariaLabel = `Compare before and after — ${alt}`;
      for (const [state, caption] of this.#captions) {
        caption.addEventListener("click", () => this.#show(state));
        commands(caption, "On a screenshot", [
          {
            id: `screenshot.${state}`,
            keys: PRESS,
            does: `Show the ${state} frame`,
            line: `show ${state}`,
            // The frame already shown has nothing for this press to do, so the line
            // does not name it there.
            when: () =>
              this.dataset.lfShotControls !== "off" &&
              this.#position() !== (state === "after" ? 100 : 0),
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
          does: () => `Show the ${this.#nextState()} frame`,
          line: () => `show ${this.#nextState()}`,
          when: () => this.dataset.lfShotControls !== "off",
          run: () => this.#margin?.activate("toggle"),
        },
      ]);
      commands(box, this.#flip);
      this.append(box);
      this.#paint();
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

    attributeChangedCallback() {
      if (!this.isConnected) return;
      this.#syncComparison();
      this.#requestComparison();
      this.#offer();
      paintKeys();
    }

    #syncComparison() {
      const enabled =
        this.dataset.lfShotControls !== "off" &&
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
            does: "Adjust the before and after divider",
            line: "adjust the comparison",
            repeat: true,
          },
          {
            id: "screenshot.edge",
            keys: ["Home", "End"],
            does: "Show only before or after",
            line: "jump to an endpoint",
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
      if (
        !this.isConnected ||
        this.#box.parentNode !== this ||
        this.dataset.lfShotControls === "off"
      )
        return;
      await loadComparison();
      if (this.isConnected) this.#syncComparison();
    }

    #requestComparison() {
      if (this.dataset.lfShotControls === "off") return;
      void afterPresentation(() => this.#upgradeComparison()).catch((reason) =>
        failSoft(this, reason),
      );
    }

    // Each region is placed in shares of the pair's frame, the natural width by the
    // taller image's height that `--lf-shot-ratio` sizes, so the marks scale with the
    // images at every width.
    #markDifference(shots) {
      const reading = compareImages(...shots);
      const { width, height, regions } = reading;
      const share = (length, whole) => `${(100 * length) / whole}%`;
      for (const frame of this.#frames) {
        const marks = document.createElement("div");
        marks.className = "lf-shotdiff";
        marks.dataset.lfGen = "1";
        marks.ariaHidden = "true";
        for (const region of regions) {
          const mark = document.createElement("span");
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
      count.dataset.lfShotDelta = regions.length ? "changed" : "identical";
      relabel(
        count,
        regions.length === 0
          ? "identical"
          : `${regions.length} changed ${regions.length === 1 ? "area" : "areas"}`,
        { says: false },
      );
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
        handle.setAttribute("aria-label", `Before and after — ${this.#alt}`);
        handle.setAttribute("aria-valuetext", `Before ${before}%, after ${position}%`);
        handle.style.setProperty("--lf-here-ring", "shot");
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
        caption.setAttribute("aria-pressed", String(position === endpoint));
      }
      this.#margin?.update();
      paintKeys();
    }

    #offer() {
      if (this.dataset.lfShotControls === "off") {
        this.#margin?.unregister();
        this.#margin = null;
        return;
      }
      if (!this.#box || this.#margin) return;
      this.#margin = registerMarginContribution({
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
              marginEntry({
                key: "toggle",
                icon: position > 50 ? "compare-after" : "compare-before",
                label,
                accessibleLabel: `${label} — ${this.#alt}`,
                activation: "toggle",
                className: "lf-shot-toggle",
                scope: this.#flip,
              }),
            ],
            readings: [],
          };
        },
        activate: (activation) => {
          if (activation === "toggle") this.#show(this.#nextState());
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
