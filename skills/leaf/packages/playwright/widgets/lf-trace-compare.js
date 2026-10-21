/* A comparison keeps its source chooser in place while each recording owns its
 * native timeline, playback and moments. Explicit bookmark keys pair results;
 * elapsed times and labels never establish correspondence. A chosen key also
 * reaches recordings whose data arrives later. Source switches share the image
 * inspection view and pause hidden recordings without moving their playheads.
 * Each direct child that holds a trace is one view, including its caption. */
import {
  el,
  keepView,
  keeps,
  layoutChanged,
  once,
  offered,
  createView,
  html,
  For,
  openingView,
  quoted,
} from "/runtime/widget-api.js";
import "./lf-trace.js";

customElements.define(
  "lf-trace-compare",
  class extends HTMLElement {
    #views = [];
    #recordings = [];
    #selected = 0;
    #moment = null;
    #drawing = null;

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
      const header = el("div", "lf-trace-compare-controls");
      header.dataset.lfGen = "1";
      const options = this.#recordings.map((recording, index) => ({
        index,
        label: recording.getAttribute("label") ?? recording.getAttribute("source"),
      }));
      this.#drawing = createView(
        header,
        (read) =>
          html` <fieldset
            role="radiogroup"
            ref=${offered("lf-trace-sources lf-radio-group")}
            disabled=${quoted(this)}
          >
            <legend>Recording</legend>
            ${For({
              each: options,
              children: (option) =>
                html` <label class="lf-radio-choice lf-trace-source">
                  <input
                    ref=${offered("")}
                    type="radio"
                    name=${`${this.id}-recording`}
                    value=${String(option.index)}
                    checked=${() => read().selected === option.index}
                    onChange=${(event) => {
                    if (!event.currentTarget.checked) return;
                    const view = this.#recordings[this.#selected].inspectionView;
                    this.#selected = option.index;
                    this.#draw();
                    this.#recordings[this.#selected].inspectionView = view;
                  }}
                  />
                  <span>${option.label}</span>
                </label>`,
            })}
          </fieldset>`,
        { selected: this.#selected },
      );
      for (const [index, recording] of this.#recordings.entries()) {
        const view = this.#views[index];
        view.addEventListener("lf-reveal", (event) => {
          if (index !== this.#selected) event.detail.replacedView();
          this.#selected = index;
          event.detail.present(this.#draw());
        });
        view.addEventListener("beforematch", () => {
          this.#selected = index;
          this.#draw();
        });
        recording.addEventListener("lf-trace-ready", () => {
          if (this.#moment) recording.selectMoment(this.#moment);
        });
        recording.addEventListener("lf-trace-moment", (event) => {
          this.#moment = event.detail.key;
          for (const peer of this.#recordings)
            if (peer !== recording) peer.selectMoment(this.#moment);
        });
      }
      this.prepend(header);
      this.#draw();
    }

    #draw() {
      this.#drawing.update({ selected: this.#selected });
      // Reveal first, so a synchronous layout read never observes an empty
      // workspace and clamps the document's scroll position to its shorter end.
      keeps(this.#views[this.#selected], "hidden", null);
      for (const [index, recording] of this.#recordings.entries()) {
        if (index !== this.#selected) recording.pause();
        keeps(
          this.#views[index],
          "hidden",
          index === this.#selected ? null : "until-found",
        );
        keeps(recording, "aria-label", recording.getAttribute("label"));
      }
      if (this.#views[this.#selected]) keepView(this, this.#views[this.#selected]);
      return layoutChanged(this);
    }
  },
);
