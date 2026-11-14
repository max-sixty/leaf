// <lf-merge-steps>: the step list beside a merge film. Its text is authored markup, so
// every step's sentence can take a comment; this module draws the `frame` output of the
// film its `for` names: it marks which step is playing and how this run treats each one,
// and adds a line saying why where a step was skipped or stopped the merge. A click on a
// step holds its result for reading.

import {
  LeafElement,
  generatedElement,
  keeps,
  keepsText,
} from "/runtime/widget-api.js";

customElements.define(
  "lf-merge-steps",
  class extends LeafElement {
    static properties = { frame: { attribute: false } };

    setup() {
      const film = document.getElementById(this.getAttribute("for"));
      this.items = [...this.querySelectorAll("li[data-chapter]")];
      // Each step's run line is this module's, beside the authored sentence.
      for (const li of this.items)
        generatedElement(li.querySelector(".this-run"), { says: true });
      for (const li of this.items)
        li.addEventListener("click", () => {
          film.seekChapter(li.dataset.chapter);
        });
    }

    updated(changed) {
      super.updated(changed);
      // A film that leaves publishes null, which draws no step as playing or reached.
      const d = this.frame;
      for (const li of this.items) {
        const key = li.dataset.chapter;
        const now = key === d?.chapter;
        const state = d?.status[key] ?? "run";
        keeps(li, "data-state", state);
        keeps(
          li.querySelector("button"),
          "disabled",
          state === "unreached" ? "" : null,
        );
        li.toggleAttribute("data-now", now);
        // The run's own line only where it adds something: why a step was skipped or
        // stopped, what the branch is, and how the run ended. The caption leads with the
        // step's number and name, which the list already shows.
        const telling = key === "setup" || key === "end" || state !== "run";
        const run = li.querySelector(".this-run");
        keepsText(run, now && telling ? d.caption.replace(/^\d · [^—]+— /, "") : "");
        keeps(run, "data-tone", d?.captionTone ?? null);
      }
    }
  },
);
