/* lf-shot: registered before/after screenshots in one fixed frame.
 *
 * The target's shared margin entry shows a split circle: left filled for before, right for after.
 * Enter, Space, and clicks flip the comparison without moving the margin entry.
 * Each rail label chooses its own frame. Clicking the image works a transparent native
 * checkbox directly, keeping focus at the clicked frame even when a tall comparison
 * extends beyond the viewport. Every door changes that checkbox; CSS alone chooses the
 * visible image. Export makes the rail labels static, removes the margin control, and
 * keeps the native image control, so a standalone copy still flips with a click or Space.
 * Print stacks both frames.
 *
 * One two-ended rail stays fixed above the frames while CSS moves its active rule. Its
 * labels are generated page words, available to selection, and become the order key
 * above the two stacked frames on paper.
 * A parent that reuses the aligned frames under another inspector sets
 * `data-lf-shot-controls="off"`; lf-shot then withdraws its commands and margin action
 * without disabling the native checkbox a standalone copy needs.
 * Commentary about the change belongs in authored prose around the widget. */
import {
  PRESS,
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

    static observedAttributes = ["data-lf-shot-controls"];

    connectedCallback() {
      if (!once(this)) {
        this.#offer();
        return;
      }
      const alt = this.getAttribute("alt");
      this.#alt = alt;
      const shots = [];
      const captions = new Map();

      const rail = document.createElement("div");
      rail.className = "lf-shotrail";
      rail.dataset.lfGen = "1";
      for (const state of ["before", "after"]) {
        const caption = selectableOffer("button", "lf-shotcap");
        caption.dataset.lfState = state;
        caption.ariaLabel = `${state} — ${alt}`;
        relabel(caption, state, { says: true });
        captions.set(state, caption);
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
        this.append(frame);
      }

      const box = offer("input", "lf-shotflip", undefined, "checkbox");
      this.#box = box;
      box.name = "comparison";
      box.ariaLabel = `Compare before and after — ${alt}`;
      const show = (state) => {
        const checked = state === "after";
        if (box.checked === checked) return;
        box.checked = checked;
        box.dispatchEvent(new Event("change", { bubbles: true }));
      };
      for (const [state, caption] of captions) {
        caption.addEventListener("click", () => show(state));
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
              box.checked !== (state === "after"),
            run: () => caption.click(),
          },
        ]);
      }
      const paint = () => {
        const visible = box.checked ? "after" : "before";
        for (const [state, caption] of captions)
          caption.setAttribute("aria-pressed", String(state === visible));
        this.#margin?.update();
        paintKeys();
      };
      box.addEventListener("change", paint);
      commands(box, "On a screenshot", [
        {
          id: "screenshot.toggle",
          keys: [" "],
          does: () => `Show the ${box.checked ? "before" : "after"} frame`,
          line: () => `show ${box.checked ? "before" : "after"}`,
          when: () => this.dataset.lfShotControls !== "off",
          run: () => this.#margin?.activate("toggle"),
        },
      ]);
      paint();
      this.append(box);
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
      this.#offer();
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
          const label = `Show ${this.#box.checked ? "before" : "after"}`;
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
                icon: this.#box.checked ? "compare-after" : "compare-before",
                label,
                accessibleLabel: `${label} — ${this.#alt}`,
                activation: "toggle",
                className: "lf-shot-toggle",
              }),
            ],
            readings: [],
          };
        },
        activate: (activation) => {
          if (activation === "toggle") this.#box.click();
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
    }
  },
);
