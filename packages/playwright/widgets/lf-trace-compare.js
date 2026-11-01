/* A comparison keeps its source chooser in place while each recording owns its
 * native timeline, playback and moments. Explicit bookmark keys pair results;
 * elapsed times and labels never establish correspondence. A chosen key also
 * reaches recordings whose data arrives later. Source switches share the image
 * inspection view and pause hidden recordings without moving their playheads.
 * Each direct child is one recording view: a trace or any wrapper holding one,
 * including its caption. Membership is known from its start tag, so a partial
 * second wrapper stays hidden while the parser is still receiving its trace.
 * Shared introductory text belongs outside the comparison. The chooser's
 * measured height clears focus and navigation inside those views. */
import {
  cancelRender,
  el,
  generatedElement,
  keepView,
  keeps,
  layoutChanged,
  layoutPx,
  nextRender,
  once,
  offer,
  openingView,
  viewMembers,
  quoted,
  sizeObserver,
  whileConnected,
} from "/runtime/widget-api.js";
import "./lf-trace.js";

customElements.define(
  "lf-trace-compare",
  class extends HTMLElement {
    #views = [];
    #recordings = [];
    #selected = 0;
    #moment = null;

    connectedCallback() {
      if (!once(this)) return;
      for (const child of viewMembers(this)) {
        const recording = child.matches("lf-trace")
          ? child
          : child.querySelector("lf-trace");
        if (!recording)
          throw new Error(
            "Each lf-trace-compare child must be an lf-trace or contain one; put shared introductory text outside the comparison.",
          );
        this.#views.push(child);
        this.#recordings.push(recording);
      }
      this.#selected = this.#views.indexOf(openingView(this));
      const header = el("div", "lf-trace-compare-controls");
      generatedElement(header, { says: false });
      /** @type {any} Web Awesome's radio group exposes form properties. */
      const choices = offer("wa-radio-group", "lf-trace-sources lf-label-hidden");
      choices.label = "Recording";
      choices.name = `${this.id}-recording`;
      choices.size = "s";
      choices.orientation = "horizontal";
      for (const [index, recording] of this.#recordings.entries()) {
        const view = this.#views[index];
        view.addEventListener("beforematch", () => {
          this.#selected = index;
          choices.value = String(index);
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
        const choice = offer(
          "wa-radio",
          "lf-trace-source",
          recording.getAttribute("label") ?? recording.getAttribute("source"),
        );
        choice.value = String(index);
        choice.appearance = "button";
        choice.disabled = quoted(this);
        choices.append(choice);
      }
      choices.value = String(this.#selected);
      choices.addEventListener("change", () => {
        const view = this.#recordings[this.#selected].inspectionView;
        this.#selected = Number(choices.value);
        this.#draw();
        this.#recordings[this.#selected].inspectionView = view;
      });
      header.append(choices);
      this.prepend(header);
      whileConnected(this, () => {
        const paintHeight = (height) =>
          this.style.setProperty("--lf-trace-compare-head-h", layoutPx(height));
        paintHeight(header.getBoundingClientRect().height);
        let paint;
        const size = sizeObserver(([entry]) => {
          cancelRender(paint);
          // Clearance resizes the stage; publish outside size delivery.
          paint = nextRender(() => {
            paintHeight(entry.borderBoxSize[0].blockSize);
          });
        });
        size.observe(header, { box: "border-box" });
        return () => {
          size.disconnect();
          cancelRender(paint);
        };
      });
      this.#draw();
    }

    #draw() {
      // Reveal first, so a synchronous layout read never observes an empty
      // workspace and clamps the document's scroll position to its shorter end.
      keepView(this, this.#views[this.#selected]);
      for (const [index, recording] of this.#recordings.entries()) {
        if (index !== this.#selected) recording.pause();
        keeps(recording, "aria-label", recording.getAttribute("label"));
      }
      layoutChanged(this);
    }
  },
);
