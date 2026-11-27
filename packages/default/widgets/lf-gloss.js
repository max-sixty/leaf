/* lf-gloss: a brief explanation at the phrase that needs it.
 *
 * The body stays where the author put it: the phrase, then the explanation the author
 * wrote in a child element marked with HTML's `popover` attribute, which the platform
 * keeps out of the sentence until it is shown. Both are the page's authored words, so
 * the user selects, quotes and comments on the explanation as on the phrase, and
 * Python's reading of the file holds them where the page shows them. Paper places the
 * explanation after the phrase. A gloss with no such child is the phrase alone.
 *
 * Pointing reads; pressing acts. A pointer resting on the phrase, keyboard focus on it
 * and a finger holding it read the explanation as the phrase's preview, in the face
 * every preview wears (`lfPreview`, module-previews.md). A press pins the
 * explanation's own card open, where its words can be selected and commented on, and a
 * second press puts it away. The phrase is the visible affordance; a proxy at the same place
 * (control-faces.js, `proxy`) gives Tab, Enter, and Space their native route without
 * adding a second mark to the prose, and its description is the card, which a screen
 * reader hears on focus. An auto popover owns the card's top-layer lifecycle and light
 * dismissal; CSS anchors keep the card with its phrase. */
import { aimedAt, says, whileConnected } from "/runtime/widget-api.js";
import { offerAction } from "/runtime/lib/controls.js";
import { once } from "/runtime/lib/once.js";
import { keeps } from "/runtime/lib/keeps.js";

let nextId = 0;

customElements.define(
  "lf-gloss",
  class extends HTMLElement {
    /** @type {HTMLElement | null} */
    #bubble = null;
    #mark = offerAction("proxy", "lf-gloss-mark");
    #pinned = false;
    // A pinned card already shows the explanation, so nothing previews over it.
    lfPreview = () =>
      this.#pinned || !this.#bubble
        ? false
        : { name: this.#phrase(), detail: [says(this.#bubble)] };

    connectedCallback() {
      if (!once(this)) return;
      this.#bubble = this.querySelector(":scope > [popover]");
      if (!this.#bubble) return;
      this.#build(this.#bubble);
      whileConnected(this, (/** @type {AbortSignal} */ signal) => {
        this.addEventListener("click", (event) => this.#click(event), { signal });
        this.#sync();
        return () => {
          this.#pinned = false;
        };
      });
    }

    // The authored phrase, which names the gloss, without the words of its card.
    #phrase() {
      return [...this.childNodes]
        .filter((node) => node !== this.#bubble && node !== this.#mark)
        .map((node) => node.textContent)
        .join("")
        .replace(/\s+/g, " ")
        .trim();
    }

    /** @param {HTMLElement} bubble */
    #build(bubble) {
      const phrase = this.#phrase();
      this.#mark.setAttribute("aria-label", `Explain “${phrase}”`);
      this.#mark.setAttribute("aria-expanded", "false");

      // The mark names the card by id. One the author gave stays; one written here is
      // the runtime's (`lf-`), which an anchor never takes for its section.
      let n = ++nextId;
      while (!bubble.id && document.getElementById(`lf-gloss-tip-${n}`)) n = ++nextId;
      bubble.id ||= `lf-gloss-tip-${n}`;
      bubble.classList.add("lf-gloss-popover", "lf-popover");
      keeps(bubble, "role", "note");
      const anchor = `--lf-gloss-${n}`;
      this.style.anchorName = anchor;
      bubble.style.positionAnchor = anchor;
      this.#mark.setAttribute("aria-controls", bubble.id);
      this.#mark.setAttribute("aria-describedby", bubble.id);
      this.append(this.#mark);
      // A comment can rest on the explanation itself, and following it opens the card
      // as Leaf opens any closed popover holding a destination. Opened by anyone but
      // this module, the card stays pinned open, as a click pins it; a light dismissal
      // unpins it.
      bubble.addEventListener("beforetoggle", (event) => {
        if (event.newState === "open" && !this.#pinned) this.#pin(true);
      });
      bubble.addEventListener("toggle", (event) => {
        if (
          event.newState === "closed" &&
          this.#pinned &&
          !bubble.matches(":popover-open")
        )
          this.#pin(false);
      });
    }

    /** @param {MouseEvent} event */
    #click(event) {
      if (event.defaultPrevented) return;
      const at = aimedAt(event, this);
      if (at !== this && at !== this.#mark) return;
      if (this.#bubble && event.composedPath().includes(this.#bubble)) return;
      event.preventDefault();
      this.#pin(!this.#pinned);
      this.#sync();
    }

    /** @param {boolean} pinned */
    #pin(pinned) {
      this.#pinned = pinned;
      keeps(this.#mark, "aria-expanded", pinned);
      this.dispatchEvent(
        new CustomEvent("lf-commands", { bubbles: true, composed: true }),
      );
    }

    #sync() {
      if (!this.#bubble?.isConnected) return;
      const open = this.#bubble.matches(":popover-open");
      if (this.#pinned && !open) this.#bubble.showPopover();
      else if (!this.#pinned && open) this.#bubble.hidePopover();
    }
  },
);
