/* One inspection workspace for independent recordings. Switching the visible
 * recording preserves the workspace's scroll position and each child's local
 * image view. Explicit bookmark keys pair results; this container supplies the
 * comparison identity, never inferring correspondence from labels or clocks.
 * Its one sticky source chooser declares its measured extent to the children,
 * so their inspection stages use the room below it. Measurement commits in the
 * rendering pass: changing a child's extent during observer delivery would
 * resize ancestors the browser has already visited in that delivery. */
import {
  HIDDEN,
  el,
  frameFor,
  keepView,
  keeps,
  layoutChanged,
  layoutPx,
  once,
  offer,
  openingView,
  quoted,
  sizeObserver,
  whileConnected,
} from "/runtime/widget-api.js";
await import("/vendor/webawesome.esm.js");

customElements.define(
  "lf-trace-compare",
  class extends HTMLElement {
    #choices = null;
    #recordings = [];
    #selected = 0;
    #measureHead = frameFor(this, () => {
      this.style.setProperty(
        "--lf-trace-compare-head",
        layoutPx(this.firstElementChild.getBoundingClientRect().height),
      );
      layoutChanged(this);
    });

    connectedCallback() {
      if (!once(this)) return;
      this.#recordings = [...this.querySelectorAll(":scope > lf-trace")];
      this.#selected = this.#recordings.indexOf(openingView(this, this.#recordings));
      const header = el("div", "lf-trace-compare-controls");
      header.dataset.lfGen = "1";
      this.#choices = offer("wa-radio-group", "lf-trace-sources lf-label-hidden");
      this.#choices.label = "Recording";
      this.#choices.name = `${this.id}-recording`;
      this.#choices.size = "s";
      this.#choices.orientation = "horizontal";
      for (const [index, recording] of this.#recordings.entries()) {
        recording.addEventListener("lf-reveal", (event) => {
          if (index !== this.#selected) event.detail.replacedView();
          this.#selected = index;
          this.#choices.value = String(index);
          event.detail.present(this.#draw());
        });
        recording.addEventListener("beforematch", () => {
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
      this.prepend(header);
      whileConnected(this, () => {
        const resize = sizeObserver(this.#measureHead);
        resize.observe(this.firstElementChild);
        this.#draw();
        return () => resize.disconnect();
      });
    }

    #draw() {
      for (const [index, recording] of this.#recordings.entries()) {
        keeps(recording, "hidden", index === this.#selected ? null : HIDDEN);
        keeps(recording, "aria-label", recording.getAttribute("label"));
      }
      if (this.#recordings[this.#selected])
        keepView(this, this.#recordings[this.#selected]);
      return layoutChanged(this);
    }
  },
);
