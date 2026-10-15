/* A moving widget for readiness and covered-word checks.
 * Its offset is authoritative; deep stages animated words in a shadow root, and
 * bare deliberately omits their element so the page must refuse presentation. */
import { LeafElement, motion, nothing } from "/runtime/widget-api.js";

customElements.define(
  "lf-drift",
  class extends LeafElement {
    setup() {
      // `deep` renders the same words from inside the widget's own root, and moves
      // them there: an animation a document-level reading cannot see.
      if (this.hasAttribute("deep")) {
        const root = this.attachShadow({ mode: "open" });
        // `bare` stages the words with no element over them — the page refuses that,
        // and the refusal is what one of the tests below reads.
        if (this.hasAttribute("bare")) {
          root.append(...this.childNodes);
          return;
        }
        const held = document.createElement("div");
        held.append(...this.childNodes);
        root.append(held);
        held.animate([{ transform: "translateY(120px)" }, { transform: "none" }], {
          duration: 30000,
        });
      }
      this.#place();
    }
    // Absolute, as every render is: the offset is stated, never stepped.
    render() {
      const from = this.getAttribute("offset");
      const to = String(this.state.settle.value);
      if (from === to) return nothing;
      this.setAttribute("offset", to);
      this.#place();
      // Held at the old offset for nine tenths of the run, so the words are over
      // their neighbour's for as long as the motion lasts. A move that eased the
      // whole way would leave a last fifth of a second in which a reading taken
      // then happened to be clean, and the test would be measuring when the gate
      // looked rather than whether it waited.
      motion(
        this,
        [
          { transform: `translateY(${from}px)` },
          { transform: `translateY(${from}px)`, offset: 0.9 },
          { transform: "none" },
        ],
        1200,
      );
      return nothing;
    }
    #place() {
      this.style.transform = `translateY(${this.getAttribute("offset")}px)`;
    }
  },
);
