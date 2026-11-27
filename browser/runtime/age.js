// Compiled from age.ts by build/typescript.mjs; edit that file.
/* `lf-age`: how long ago a moment was, in the wording every age on the page has
   (state/presence.js, `ago`), kept current as the page's clock ticks, and previewing the
   clock time behind it as every age does (`agePreview`).

     <lf-age datetime="2026-11-24T18:05:00Z">24 Nov, 18:05 UTC</lf-age>

   An author writes it in the page, in a message or in a widget's template, with
   the time in their own words inside it or with nothing, and changes its `datetime`
   to show another moment.

   The decisions it embodies:

   - It is Leaf's own element, defined on every page, so it upgrades wherever it
     appears, in a shadow tree too, with no import. A package's widget could not be
     drawn from every template: its module loads only where its tag stands in markup
     the loader reads (records/widget-loader.js), and a page's own widget may not import a
     package's module. It would also need Leaf's wording (`ago`) kept public.
   - The words the author wrote in it stay in the document, undrawn: the age stands
     in a shadow root that has no slot, as a typeset formula stands over its LaTeX
     (readings/formulas.js). They are the page's words to every reader of its text, the file
     Python reads and a comment's quote among them, so a quote across an age holds
     the time the author wrote and still finds its passage after the age has ticked,
     where a quote of the age would lose it at the next tick. An age pays what a
     formula pays for that: a thread's mark stands on the words round it and not on
     it, and Leaf's page search finds the written time and not the age. A page
     without Leaf draws the words, and so does a served page until the runtime has
     defined the element. A file that runs no script can't keep an age, so a static
     export draws the words too, or the clock time where the author wrote none
     (src/leaf/pages/static-export.js).
   - It follows the clock with one effect of its own and writes one text node. A
     `LeafElement` would make each age a stage Leaf dresses and watches
     (dom/shadow-stage.js), which a list of ages pays once for each.
   - That text stands straight in the shadow root. Leaf finds the element holding a
     letter there through the root's host (lib/shadow-tree.js, `holdingElement`), as
     it does for any widget's top-level text, so a span round the words would add an
     element to every age and change nothing.
   - It stays inline, and never breaks across two lines. A zero-width no-break
     space (U+FEFF) leads the words, in the same text: Firefox selects nothing on a
     double-click of the first word of a shadow tree that stands flush against its
     host's start, and a comment made from that has no passage. A span round the
     words doesn't cure that. The character stands in the words' own text, so a caret
     either side of it stands before the age's first figure, the letter a measure of
     the caret reads (dom/native-selection.js, `userCaret`); the character has no width to
     measure. JavaScript counts that character as white space, so a reading of the
     age's text that trims it, as a test's text match does, reads the words alone; a
     copy that takes in an age carries the character. Three other cures fail: a word
     joiner (U+2060) stays in every such reading; after a zero-width space (U+200B)
     Chromium drops the space a line break in the source leaves before the tag; and
     an inline block takes no underline or strike from a link or an `<s>` round it,
     parts from an opening bracket before it, lets a comma after it start the next
     line, and is undone by a page that restyles the element. */
import { effect, signal } from "/vendor/signals-core.js";
import { agePreview, ago } from "./state/presence.js";

const unbroken = new CSSStyleSheet();
unbroken.replaceSync(":host { white-space: nowrap; }");

customElements.define(
  "lf-age",
  class extends HTMLElement {
    static observedAttributes = ["datetime"];

    #moment = signal(null);
    #words = new Text("");
    #following = null;

    lfPreview = agePreview;

    constructor() {
      super();
      const root = this.attachShadow({ mode: "open" });
      root.adoptedStyleSheets = [unbroken];
      root.append(this.#words);
    }

    attributeChangedCallback(_name, _was, moment) {
      this.#moment.value = moment;
    }

    connectedCallback() {
      this.#following ??= effect(() => {
        const words = `\ufeff${ago(this.#moment.value)}`;
        if (this.#words.data !== words) this.#words.data = words;
      });
    }

    disconnectedCallback() {
      this.#following?.();
      this.#following = null;
    }
  },
);
