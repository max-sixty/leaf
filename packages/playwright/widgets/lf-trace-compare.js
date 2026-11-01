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

/** @typedef {{index: number, view: Element, recording: import("./lf-trace.js").Trace}} TraceMember */

customElements.define(
  "lf-trace-compare",
  class extends HTMLElement {
    /** @type {TraceMember[]} */
    #members = [];
    /** @type {TraceMember | null} */
    #selected = null;
    /** @type {string | null} */
    #moment = null;

    connectedCallback() {
      if (!once(this)) return;
      const recordings = [...this.querySelectorAll("lf-trace")];
      for (const child of viewMembers(this)) {
        const recording = recordings.find(
          (trace) => trace === child || child.contains(trace),
        );
        if (!recording)
          throw new Error(
            "Each lf-trace-compare child must be an lf-trace or contain one; put shared introductory text outside the comparison.",
          );
        this.#members.push({ index: this.#members.length, view: child, recording });
      }
      const opening = openingView(this);
      this.#selected = this.#members.find((member) => member.view === opening) ?? null;
      const header = el("div", "lf-trace-compare-controls");
      generatedElement(header, { says: false });
      /** @type {import("@awesome.me/webawesome/dist/components/radio-group/radio-group.js").default} */
      const choices = offer("wa-radio-group", "lf-trace-sources lf-label-hidden");
      choices.label = "Recording";
      choices.name = `${this.id}-recording`;
      choices.size = "s";
      choices.orientation = "horizontal";
      for (const member of this.#members) {
        const { index, recording, view } = member;
        view.addEventListener("beforematch", () => {
          this.#selected = member;
          choices.value = String(index);
          this.#draw();
        });
        recording.addEventListener("lf-trace-ready", () => {
          if (this.#moment) recording.selectMoment(this.#moment);
        });
        recording.addEventListener("lf-trace-moment", (event) => {
          this.#moment = event.detail.key;
          for (const peer of this.#members)
            if (peer.recording !== recording) peer.recording.selectMoment(this.#moment);
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
      choices.value = String(this.#selected?.index ?? -1);
      choices.addEventListener("change", () => {
        const selected = this.#members.find(
          (member) => String(member.index) === choices.value,
        );
        if (!selected) return;
        const view = this.#selected?.recording.inspectionView ?? null;
        this.#selected = selected;
        this.#draw();
        selected.recording.inspectionView = view;
      });
      header.append(choices);
      this.prepend(header);
      whileConnected(this, () => {
        const paintHeight = (/** @type {number} */ height) =>
          this.style.setProperty("--lf-trace-compare-head-h", layoutPx(height));
        paintHeight(header.getBoundingClientRect().height);
        let paint = 0;
        const size = sizeObserver((entries) => {
          cancelRender(paint);
          // Clearance resizes the stage; publish outside size delivery.
          paint = nextRender(() => {
            for (const entry of entries)
              for (const box of entry.borderBoxSize) paintHeight(box.blockSize);
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
      keepView(this, this.#selected?.view ?? null);
      for (const member of this.#members) {
        const { recording } = member;
        if (member !== this.#selected) recording.pause();
        keeps(recording, "aria-label", recording.getAttribute("label"));
      }
      layoutChanged(this);
    }
  },
);
