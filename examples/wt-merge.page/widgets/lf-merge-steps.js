// <lf-merge-steps>: the step list beside a merge film. Its text is authored markup, so
// every step's sentence can take a comment; this module only marks which step is playing
// and how this run treats each one, and adds a line saying why where a step was skipped
// or stopped the merge. A click on a step plays the film from it.

import { once } from "/runtime/widget-api.js";

customElements.define(
  "lf-merge-steps",
  class extends HTMLElement {
    #last = "";

    connectedCallback() {
      if (!once(this)) return;
      const film = document.getElementById(this.getAttribute("for"));
      this.items = [...this.querySelectorAll("li[data-chapter]")];
      for (const li of this.items)
        li.addEventListener("click", () => {
          const key = li.dataset.chapter;
          if (key === "setup") film.seek(0);
          else film.seekChapter(key);
        });
      film.addEventListener("film-frame", (e) => this.#show(e.detail));
      // The film may have painted before this list upgraded; ask for the current frame.
      customElements.whenDefined("lf-merge-film").then(() => film.announce());
    }

    #show(d) {
      const sig = `${d.chapter}|${d.caption}|${JSON.stringify(d.status)}`;
      if (sig === this.#last) return;
      this.#last = sig;
      for (const li of this.items) {
        const key = li.dataset.chapter;
        const now = key === d.chapter;
        li.dataset.state = d.status[key] ?? "run";
        li.toggleAttribute("data-now", now);
        // The run's own line only where it adds something: why a step was skipped or
        // stopped, what the branch is, and how the run ended. The caption leads with the
        // step's number and name, which the list already shows.
        const telling = key === "setup" || key === "end" || li.dataset.state !== "run";
        const run = li.querySelector(".this-run");
        run.textContent = now && telling ? d.caption.replace(/^\d · [^—]+— /, "") : "";
        run.dataset.tone = d.captionTone;
      }
    }
  },
);
