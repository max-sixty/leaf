/* `lf-age`: how long ago a moment was, in the wording every age on the page has
   (presence.js, `ago`), kept current as the page's clock ticks, and previewing the
   clock time behind it as every age does (`agePreview`).

     <lf-age datetime="2026-11-24T18:05:00Z">24 Nov, 18:05 UTC</lf-age>

   An author writes it in the page, in a message or in a widget's template, and
   changes its `datetime` to show another moment.

   The decisions it embodies:

   - It is Leaf's own element, defined on every page. A widget's module loads only
     where its tag stands in markup the loader reads (widget-loader.js), and a
     page-owned widget can't import a package's module, so as a package's widget
     it would draw nothing in such a template. Defined here, it upgrades wherever
     it appears, in a shadow tree too, with no import.
   - The words the author wrote in it stay in the document, undrawn: the age stands
     in a shadow root that has no slot. They are the page's words to every reader
     of its text, the file Python reads and a comment's quote among them, so a quote
     across an age holds the time the author wrote and still finds its passage
     after the age has ticked. A page without Leaf draws them.
   - It follows the clock with one effect of its own and writes one text node. A
     `LeafElement` would make each age a stage Leaf dresses and watches
     (shadow-stage.js), which a list of ages pays once for each. */
import { effect, signal } from "/runtime/framework.js";
import { agePreview, ago } from "./presence.js";

customElements.define(
  "lf-age",
  class extends HTMLElement {
    static observedAttributes = ["datetime"];

    #moment = signal(/** @type {string | null} */ (null));
    #words = this.attachShadow({ mode: "open" }).appendChild(new Text(""));
    /** @type {(() => void) | null} */
    #following = null;

    lfPreview = agePreview;

    /** @param {string} _name @param {string | null} _was @param {string | null} moment */
    attributeChangedCallback(_name, _was, moment) {
      this.#moment.value = moment;
    }

    connectedCallback() {
      this.#following ??= effect(() => {
        const words = ago(this.#moment.value);
        if (this.#words.data !== words) this.#words.data = words;
      });
    }

    disconnectedCallback() {
      this.#following?.();
      this.#following = null;
    }
  },
);
