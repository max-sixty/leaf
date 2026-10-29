/* lf-gloss: a brief explanation at the phrase that needs it.
 *
 * The body stays where the author put it: it is the page's selectable, quotable
 * phrase. The explanation is the x-says rendering of the validated `tip` attribute:
 * generated for the diff, but still page text a user can select and comment on. Paper
 * places those same words after the phrase.
 *
 * Hover is only the fastest route. The phrase is the visible affordance; an ordinary
 * Leaf offer at the same place gives Tab, Enter, and Space their native route without
 * adding a second mark to the prose. Clicking the phrase pins the card for touch and
 * careful reading. An auto popover owns the top-layer lifecycle and light dismissal;
 * CSS anchors keep the card with its phrase. */
import {
  keeps,
  showNativeLayer,
  closeNativeLayer,
  isNativeLayer,
  offer,
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
    #bubble = null;
    #dismissed = false;
    #focused = false;
    #hovered = false;
    #mark = null;
    #pinned = false;
    #shown = false;

    connectedCallback() {
      if (!once(this)) return;
      this.#build();
      whileConnected(this, (signal) => {
        this.#listen(signal);
        this.#sync();
        return () => {
          this.#hovered = false;
          this.#focused = false;
          this.#pinned = false;
          this.#shown = false;
        };
      });
    }

    #build() {
      const phrase = this.textContent.replace(/\s+/g, " ").trim();
      this.#mark = offer("button", "lf-gloss-mark");
      this.#mark.setAttribute("aria-label", `Explain “${phrase}”`);
      this.#mark.setAttribute("aria-expanded", "false");

      this.#bubble = document.createElement("span");
      do this.#bubble.id = `lf-gloss-tip-${++nextId}`;
      while (document.getElementById(this.#bubble.id));
      this.#bubble.className = "lf-gloss-popover";
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
      // module, the tip stays pinned open, as a click pins it.
      this.#bubble.addEventListener("beforetoggle", (event) => {
        if (event.newState !== "open" || this.#shown) return;
        this.#dismissed = false;
        this.#pinned = true;
        this.#shown = true;
        this.#mark.setAttribute("aria-expanded", "true");
        commandsChanged(this);
      });
      this.#bubble.addEventListener("toggle", (event) => {
        if (event.newState !== "closed" || !this.#shown || isNativeLayer(this.#bubble))
          return;
        this.#shown = false;
        this.#pinned = false;
        this.#dismissed = true;
        this.#mark.setAttribute("aria-expanded", "false");
        commandsChanged(this);
      });
    }

    #listen(signal) {
      this.addEventListener(
        "pointerenter",
        (event) => {
          // A tap synthesizes pointerenter too. Treating that as hover leaves a card
          // permanently open after its click unpins it, so only a hovering mouse takes
          // this route; touch reaches the same state through click.
          if (event.pointerType !== "mouse") return;
          this.#hovered = true;
          this.#dismissed = false;
          this.#sync();
        },
        { signal },
      );
      this.addEventListener(
        "pointerleave",
        (event) => {
          if (event.pointerType !== "mouse") return;
          this.#hovered = false;
          this.#dismissed = false;
          this.#sync();
        },
        { signal },
      );
      this.addEventListener(
        "focusin",
        () => {
          this.#focused = true;
          this.#dismissed = false;
          this.#sync();
        },
        { signal },
      );
      this.addEventListener(
        "focusout",
        (event) => {
          if (this.contains(/** @type {Node | null} */ (event.relatedTarget))) return;
          this.#focused = false;
          this.#dismissed = false;
          this.#sync();
        },
        { signal },
      );
      this.addEventListener("click", (event) => this.#click(event), { signal });
    }

    #click(event) {
      if (event.defaultPrevented || reachedForWords(this)) return;
      const nested = worksInside(event.target, this);
      if (nested && nested !== this.#mark) return;
      if (event.target.closest(".lf-gloss-popover")) return;
      this.#dismissed = false;
      this.#pinned = !this.#pinned;
      this.#sync();
    }

    #sync() {
      if (!this.#bubble?.isConnected) return;
      const show = !this.#dismissed && (this.#hovered || this.#focused || this.#pinned);
      const open = isNativeLayer(this.#bubble);
      if (show === this.#shown && show === open) return;
      this.#shown = show;
      keeps(this.#mark, "aria-expanded", show);
      commandsChanged(this);

      if (show) {
        showNativeLayer(this.#bubble);
      } else {
        if (isNativeLayer(this.#bubble)) closeNativeLayer(this.#bubble);
      }
    }
  },
);
