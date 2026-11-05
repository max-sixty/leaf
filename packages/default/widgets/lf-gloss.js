/* lf-gloss: a brief explanation at the phrase that needs it.
 *
 * The body stays where the author put it: it is the page's selectable, quotable
 * phrase. The explanation is the x-says rendering of the validated `tip` attribute:
 * generated for the diff, but still page text a user can select and comment on. Paper
 * places those same words after the phrase.
 *
 * Pointing reads; pressing acts. A pointer resting on the phrase, keyboard focus on it
 * and a finger holding it read the explanation as the phrase's preview, in the popover
 * face (`lfPreview`, module-input.md, "Previews"). A press pins the explanation's own
 * card open, where its words can be selected and commented on, and a second press puts
 * it away. The phrase is the visible affordance; a proxy at the same place
 * (control-faces.js, `proxy`) gives Tab, Enter, and Space their native route without
 * adding a second mark to the prose, and its description is the card, which a screen
 * reader hears on focus. An auto popover owns the card's top-layer lifecycle and light
 * dismissal; CSS anchors keep the card with its phrase. */
import {
  keeps,
  showNativeLayer,
  closeNativeLayer,
  isNativeLayer,
  offerAction,
  generatedElement,
  once,
  reachedForWords,
  worksInside,
  whileConnected,
  commandsChanged,
} from "/runtime/widget-api.js";

let nextId = 0;

customElements.define(
  "lf-gloss",
  class extends HTMLElement {
    #bubble = document.createElement("span");
    #mark = offerAction("proxy", "lf-gloss-mark");
    #pinned = false;
    // A pinned card already shows the explanation, so the phrase previews nothing.
    lfPreview = () =>
      this.#pinned ? null : { popover: this.getAttribute("tip") ?? "" };

    connectedCallback() {
      if (!once(this)) return;
      this.#build();
      whileConnected(this, (/** @type {AbortSignal} */ signal) => {
        this.addEventListener("click", (event) => this.#click(event), { signal });
        this.#sync();
        return () => {
          this.#pinned = false;
        };
      });
    }

    #build() {
      const phrase = this.textContent.replace(/\s+/g, " ").trim();
      this.#mark.setAttribute("aria-label", `Explain “${phrase}”`);
      this.#mark.setAttribute("aria-expanded", "false");

      do this.#bubble.id = `lf-gloss-tip-${++nextId}`;
      while (document.getElementById(this.#bubble.id));
      this.#bubble.className = "lf-gloss-popover lf-popover";
      this.#bubble.dataset.lfSaid = "tip";
      generatedElement(this.#bubble, { says: true });
      this.#bubble.setAttribute("popover", "auto");
      this.#bubble.setAttribute("role", "note");
      this.#bubble.textContent = this.getAttribute("tip");
      const anchor = `--lf-gloss-${nextId}`;
      this.style.anchorName = anchor;
      this.#bubble.style.positionAnchor = anchor;
      this.#mark.setAttribute("aria-controls", this.#bubble.id);
      this.#mark.setAttribute("aria-describedby", this.#bubble.id);
      // x-says="after" puts the tip directly after the authored body and before any
      // trailing generated chrome. Writing that declared span here lets this module
      // also make it the popover; renderSaid sees the same marker and adds no duplicate.
      this.append(this.#bubble, this.#mark);
      // A comment can rest on the x-says tip itself, and following it opens the tip as
      // Leaf opens any closed popover holding a destination. Opened by anyone but this
      // module, the tip stays pinned open, as a click pins it; a light dismissal unpins it.
      this.#bubble.addEventListener("beforetoggle", (event) => {
        if (event.newState === "open" && !this.#pinned) this.#pin(true);
      });
      this.#bubble.addEventListener("toggle", (event) => {
        if (event.newState === "closed" && this.#pinned && !isNativeLayer(this.#bubble))
          this.#pin(false);
      });
    }

    /** @param {MouseEvent} event */
    #click(event) {
      if (event.defaultPrevented || reachedForWords(this)) return;
      const target = event.target;
      if (!(target instanceof Element)) return;
      const nested = worksInside(target, this);
      if (nested && nested !== this.#mark) return;
      if (event.composedPath().includes(this.#bubble)) return;
      this.#pin(!this.#pinned);
      this.#sync();
    }

    /** @param {boolean} pinned */
    #pin(pinned) {
      this.#pinned = pinned;
      keeps(this.#mark, "aria-expanded", pinned);
      commandsChanged(this);
    }

    #sync() {
      if (!this.#bubble?.isConnected) return;
      const open = isNativeLayer(this.#bubble);
      if (this.#pinned && !open) showNativeLayer(this.#bubble);
      else if (!this.#pinned && open) closeNativeLayer(this.#bubble);
    }
  },
);
