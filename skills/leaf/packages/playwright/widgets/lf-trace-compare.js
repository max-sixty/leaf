/* One inspection workspace for independent recordings. Switching the visible
 * recording preserves the workspace's scroll position and each child's local
 * image view. Explicit bookmark keys pair results; this container supplies the
 * comparison identity, never inferring correspondence from labels or clocks.
 * Its single source chooser moves into the selected recording's permanent
 * header mount. Chooser and transport share one sticky box and the stage's
 * intrinsic viewport allocation, including while a recording has not arrived.
 * Each direct child that is or holds an lf-trace is one view, so a recording may
 * stand in a wrapper such as a <figure>, which shows and hides with it. */
import {
  HIDDEN,
  holdFocus,
  el,
  keepView,
  keeps,
  layoutChanged,
  once,
  move,
  offer,
  openingView,
  quoted,
} from "/runtime/widget-api.js";
import "./lf-trace.js";

customElements.define(
  "lf-trace-compare",
  class extends HTMLElement {
    #choices = null;
    #header = null;
    #views = [];
    #recordings = [];
    #selected = 0;

    connectedCallback() {
      if (!once(this)) return;
      for (const child of this.children) {
        const recording = child.matches("lf-trace")
          ? child
          : child.querySelector("lf-trace");
        if (!recording) continue;
        this.#views.push(child);
        this.#recordings.push(recording);
      }
      this.#selected = this.#views.indexOf(openingView(this, this.#views));
      const header = (this.#header = el("div", "lf-trace-compare-controls"));
      header.dataset.lfGen = "1";
      this.#choices = offer("wa-radio-group", "lf-trace-sources lf-label-hidden");
      this.#choices.label = "Recording";
      this.#choices.name = `${this.id}-recording`;
      this.#choices.size = "s";
      this.#choices.orientation = "horizontal";
      for (const [index, recording] of this.#recordings.entries()) {
        const view = this.#views[index];
        view.addEventListener("lf-reveal", (event) => {
          if (index !== this.#selected) event.detail.replacedView();
          this.#selected = index;
          this.#choices.value = String(index);
          event.detail.present(this.#draw());
        });
        view.addEventListener("beforematch", () => {
          this.#selected = index;
          this.#choices.value = String(index);
          this.#draw();
        });
        const choice = offer(
          "wa-radio",
          "lf-trace-source",
          recording.getAttribute("label") ?? recording.getAttribute("source"),
        );
        choice.value = String(index);
        choice.appearance = "button";
        choice.disabled = quoted(this);
        this.#choices.append(choice);
      }
      this.#choices.value = String(this.#selected);
      this.#choices.addEventListener("change", () => {
        this.#selected = Number(this.#choices.value);
        this.#draw();
      });
      header.append(this.#choices);
      this.#draw();
    }

    #draw() {
      const selected = this.#recordings[this.#selected];
      const mount = selected?.querySelector(
        ":scope > .lf-trace-view .lf-trace-comparison",
      );
      const transfer = mount && this.#header.parentElement !== mount;
      // Hiding its old view drops native focus before the chooser moves. Restore
      // through the shared focus owner once it stands in the visible header.
      const restore = transfer ? holdFocus(this.#header) : null;
      for (const [index, recording] of this.#recordings.entries()) {
        keeps(this.#views[index], "hidden", index === this.#selected ? null : HIDDEN);
        keeps(recording, "aria-label", recording.getAttribute("label"));
      }
      if (transfer) move(mount, this.#header, null);
      restore?.();

      if (this.#views[this.#selected]) keepView(this, this.#views[this.#selected]);
      return layoutChanged(this);
    }
  },
);
