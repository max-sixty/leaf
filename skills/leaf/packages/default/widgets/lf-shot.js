/* lf-shot: registered before/after screenshots in one fixed frame.
 *
 * The target's shared Button shows a split circle: left filled for before, right for after.
 * Enter, Space, and clicks flip the comparison without moving the Button.
 * Clicking the image works a transparent native checkbox directly, keeping focus at
 * the clicked frame even when a tall comparison extends beyond the viewport. Both
 * doors change that checkbox; CSS alone chooses the visible image. Export removes the
 * scripted Button and keeps the native image control, so a standalone copy still
 * flips with a click or Space. Print stacks both frames and drops the controls.
 *
 * One two-ended rail stays fixed above the frames while CSS moves its active rule. Its
 * labels are generated page words, available to selection, and become the order key
 * above the two stacked frames on paper.
 * Commentary about the change belongs in authored prose around the widget. */
import {
  PRESS,
  once,
  offer,
  failSoft,
  commands,
  marginAction,
  paintKeys,
  registerMarginItem,
  settle,
} from "/runtime/widget-api.js";

customElements.define(
  "lf-shot",
  class extends HTMLElement {
    #button;
    #margin;

    connectedCallback() {
      if (!once(this)) {
        this.#offer();
        return;
      }
      const alt = this.getAttribute("alt");
      const shots = [];

      const rail = document.createElement("div");
      rail.className = "lf-shotrail";
      rail.dataset.lfGen = "1";
      for (const state of ["before", "after"]) {
        const caption = document.createElement("span");
        caption.className = "lf-shotcap";
        caption.dataset.lfGen = "1";
        caption.dataset.lfState = state;
        caption.textContent = state;
        rail.append(caption);
      }
      this.append(rail);

      for (const state of ["before", "after"]) {
        const frame = document.createElement("div");
        frame.className = "lf-shotframe";
        frame.dataset.lfGen = "1";
        frame.dataset.lfState = state;

        const img = document.createElement("img");
        img.src = this.getAttribute(state);
        img.alt = `${state}: ${alt}`;
        shots.push(img);
        frame.append(img);
        this.append(frame);
      }

      const box = offer("input", "lf-shotflip");
      box.type = "checkbox";
      box.ariaLabel = `Compare before and after — ${alt}`;
      this.#button = offer("button", "lf-shot-toggle");
      this.#button.addEventListener("click", () => box.click());
      const paint = () => {
        const label = `Show ${box.checked ? "before" : "after"}`;
        this.#button.ariaLabel = `${label} — ${alt}`;
        marginAction(this.#button, {
          key: "toggle",
          icon: box.checked ? "compare-after" : "compare-before",
          label,
        });
        this.#margin?.update();
        paintKeys();
      };
      box.addEventListener("change", paint);
      // Both native controls own activation. These rows only name its current effect.
      for (const [control, bindings] of [
        [box, [" "]],
        [this.#button, PRESS],
      ]) {
        commands(control, "On a screenshot", [
          {
            id: "screenshot.toggle",
            keys: bindings,
            does: () => `Show the ${box.checked ? "before" : "after"} frame`,
            line: () => `show ${box.checked ? "before" : "after"}`,
          },
        ]);
      }
      paint();
      this.append(box, this.#button);
      this.#offer();
      settle(this.register(shots));
    }

    disconnectedCallback() {
      this.#margin?.unregister();
      this.#margin = null;
    }

    #offer() {
      if (!this.#button || this.#margin) return;
      this.#margin = registerMarginItem({
        key: `shot:${this.id}`,
        target: () => this,
        controls: this.#button,
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
