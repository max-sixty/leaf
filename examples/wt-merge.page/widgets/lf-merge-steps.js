// <lf-merge-steps>: the step list beside a merge film. Its text is authored markup, so
// every step's sentence can take a comment; this module draws the `frame` output of the
// film its `for` names: it marks which step is playing and how this run treats each one,
// and adds a line saying why where a step was skipped or stopped the merge. Each step's
// button is an authored `--seek` command on the film whose value names the step, so a
// press holds that step's result for reading; a press elsewhere on the step presses it.

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
      this.steps = [...this.querySelectorAll("li")].map((li) => ({
        li,
        button: li.querySelector("button"),
        run: li.querySelector(".this-run"),
      }));
      // Each step's run line is this module's, beside the authored sentence.
      for (const { run } of this.steps) generatedElement(run, { says: true });
      this.addEventListener("click", (e) => {
        const li = e.target.closest("li");
        if (li && !e.target.closest("button")) li.querySelector("button").click();
      });
    }

    updated(changed) {
      super.updated(changed);
      // A film that has left holds nothing, which draws no step as playing or reached.
      const d = this.frame;
      for (const { li, button, run } of this.steps) {
        const key = button.value;
        const now = key === d?.chapter;
        const state = d?.status[key] ?? "run";
        keeps(li, "data-state", state);
        keeps(button, "disabled", state === "unreached" ? "" : null);
        li.toggleAttribute("data-now", now);
        // The run's own line only where it adds something: why a step was skipped or
        // stopped, what the branch is, and how the run ended. The caption leads with the
        // step's number and name, which the list already shows.
        const telling = key === "setup" || key === "end" || state !== "run";
        keepsText(run, now && telling ? d.caption.replace(/^\d · [^—]+— /, "") : "");
        keeps(run, "data-tone", d?.captionTone ?? null);
      }
    }
  },
);
