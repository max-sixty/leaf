/* lf-shot: registered before/after screenshots under one draggable divider.
 *
 * The target's shared margin entry shows a split circle: left filled for before, right for after.
 * Enter, Space, and clicks flip that projection between the endpoints without moving it.
 * Each rail label chooses its endpoint; the Web Awesome comparison between them owns
 * pointer dragging and Arrow, Home, and End adjustment. A click on either image keeps
 * the old quick endpoint toggle, while a click on the handle only puts the reader on it.
 * Export makes the rail labels static, removes the live comparison and margin control,
 * and reveals the transparent native checkbox over the image, so a standalone copy
 * still flips with a click or Space.
 * Print stacks both frames.
 *
 * One two-ended rail stays fixed above the frames while CSS moves its active rule. Its
 * labels are generated page words, available to selection, and become the order key
 * above the two stacked frames on paper.
 * A parent that reuses the aligned frames under another inspector sets
 * `data-lf-shot-controls="off"`; lf-shot then withdraws its commands and margin action
 * without disabling the native checkbox a standalone copy needs.
 * Commentary about the change belongs in authored prose around the widget. */
import "../vendor/webawesome.esm.js";

import {
  PRESS,
  commandScope,
  once,
  offer,
  failSoft,
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

customElements.define(
  "lf-shot",
  class extends HTMLElement {
    #box;
    #alt;
    #margin;
    #flip;
    #comparison;
    #frames = [];
    #captions = new Map();

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
              this.#comparison?.position !== (state === "after" ? 100 : 0),
            run: () => caption.click(),
          },
        ]);
      }
      box.addEventListener("change", () => this.#paint());
      // One declaration, two controls: the native checkbox the reader stands on inside
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
      this.#syncComparison();
      this.#paint();
      this.#offer();
      // A visual-review run creates shots after authored descriptor capture. Its
      // authored controller explicitly owns that generated child's preparation;
      // standalone authored shots own their presentation themselves.
      const present =
        this._lfPresentGenerated ??
        ((promise) => widgetController(this).present(promise));
      present(this.register(shots));
    }

    disconnectedCallback() {
      this.#margin?.unregister();
      this.#margin = null;
    }

    attributeChangedCallback() {
      if (!this.isConnected) return;
      this.#syncComparison();
      this.#offer();
      paintKeys();
    }

    #syncComparison() {
      const enabled = this.dataset.lfShotControls !== "off";
      if (enabled && !this.#comparison) {
        const comparison = document.createElement("wa-comparison");
        comparison.className = "lf-shotcomparison";
        comparison.dataset.lfGen = "1";
        comparison.position = 50;
        const handle = document.createElement("span");
        handle.className = "lf-shot-handle";
        handle.slot = "handle";
        handle.ariaHidden = "true";
        comparison.append(handle);
        for (const frame of this.#frames) {
          frame.slot = frame.dataset.lfState;
          comparison.append(frame);
        }
        let dragged = false;
        comparison.addEventListener("change", () => {
          dragged = true;
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
        void comparison.updateComplete.then(() => this.#paint());
      } else if (!enabled && this.#comparison) {
        for (const frame of this.#frames) {
          frame.removeAttribute("slot");
          this.insertBefore(frame, this.#comparison);
        }
        this.#comparison.remove();
        this.#comparison = null;
      }
    }

    #show(state) {
      if (this.#comparison) {
        const position = state === "after" ? 100 : 0;
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
      return (this.#comparison?.position ?? (this.#box.checked ? 100 : 0)) > 50
        ? "before"
        : "after";
    }

    #paint() {
      const position = this.#comparison?.position ?? (this.#box.checked ? 100 : 0);
      this.#box.checked = position > 50;
      for (const [state, caption] of this.#captions) {
        const endpoint = state === "after" ? 100 : 0;
        caption.setAttribute("aria-pressed", String(position === endpoint));
      }
      const handle = this.#comparison?.shadowRoot?.querySelector('[role="scrollbar"]');
      if (handle) {
        const before = Number((100 - position).toFixed(2));
        handle.setAttribute("aria-label", `Before and after — ${this.#alt}`);
        handle.setAttribute("aria-valuetext", `Before ${before}%, after ${position}%`);
        handle.style.setProperty("--lf-here-ring", "shot");
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
          const position = this.#comparison?.position ?? (this.#box.checked ? 100 : 0);
          return {
            subject: null,
            state: "idle",
            side: "before",
            claim: true,
            reserve: 0,
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
    // reader has no way to tell it from the truth. Heights may differ freely —
    // content reflowing taller is a real thing to see, and it stays registered.
    async register(shots) {
      await Promise.all(shots.map((img) => img.decode().catch(() => {})));
      const [before, after] = shots.map((img) => img.naturalWidth);
      if (before && after && before !== after)
        failSoft(
          this,
          new Error(
            `before is ${before}px wide and after is ${after}px — a pair has to be shot ` +
              `at one viewport, or the flip moves everything`,
          ),
        );
      const height = Math.max(...shots.map((img) => img.naturalHeight));
      if (before && height)
        this.style.setProperty("--lf-shot-ratio", `${before} / ${height}`);
      await this.#comparison?.updateComplete;
    }
  },
);
