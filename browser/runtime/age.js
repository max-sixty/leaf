/* `lf-age`: how long ago a moment was, in the wording every age on the page has
   (presence.js, `ago`), kept current as the page's clock ticks, and previewing the
   clock time behind it as every age does (`agePreview`).

     <lf-age datetime="2026-11-24T18:05:00Z">24 Nov, 18:05 UTC</lf-age>

   An author writes it in the page, in a message or in a widget's template, and
   changes its `datetime` to show another moment.

   The decisions it embodies:

   - It is Leaf's own element, defined on every page, so it upgrades wherever it
     appears, in a shadow tree too, with no import. A package's widget could not be
     drawn from every template: its module loads only where its tag stands in markup
     the loader reads (widget-loader.js), and a page's own widget may not import a
     package's module. It would also need Leaf's wording (`ago`) kept public.
   - The words the author wrote in it stay in the document, undrawn: the age stands
     in a shadow root that has no slot, as a typeset formula stands over its LaTeX
     (formulas.js). They are the page's words to every reader of its text, the file
     Python reads and a comment's quote among them, so a quote across an age holds
     the time the author wrote and still finds its passage after the age has ticked,
     where a quote of the age would lose it at the next tick. An age pays what a
     formula pays for that: a thread's mark stands on the words round it and not on
     it, and Leaf's page search finds the written time and not the age. A page
     without Leaf draws the words, as this one does until the element is defined.
   - It follows the clock with one effect of its own and writes one text node. A
     `LeafElement` would make each age a stage Leaf dresses and watches
     (shadow-stage.js), which a list of ages pays once for each.
   - It is an inline block, so an age never breaks across two lines and a width the
     page's CSS gives it holds. Firefox needs the block too: where the drawn words
     stand flush against the host's start, a double-click on the first of them
     selects nothing, and a comment made from it has no passage. */
import { effect, signal } from "/runtime/framework.js";
import { agePreview, ago } from "./presence.js";

const block = new CSSStyleSheet();
block.replaceSync(":host { display: inline-block; }");

customElements.define(
  "lf-age",
  class extends HTMLElement {
    static observedAttributes = ["datetime"];

    #moment = signal(/** @type {string | null} */ (null));
    #words = new Text("");
    /** @type {(() => void) | null} */
    #following = null;

    lfPreview = agePreview;

    constructor() {
      super();
      const root = this.attachShadow({ mode: "open" });
      root.adoptedStyleSheets = [block];
      root.append(this.#words);
    }

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
