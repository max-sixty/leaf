/* lf-gloss: a brief explanation at the phrase that needs it.
 *
 * The body stays where the author put it: it is the page's selectable, quotable
 * phrase. The explanation is the x-says rendering of the validated `tip` attribute:
 * generated for the diff, but still page text a reader can select and comment on. A
 * static copy and paper place those same words after the phrase.
 *
 * Hover is only the fastest route. The raised mark is an ordinary Leaf offer, so Tab,
 * Enter, and Space reach it; clicking either the phrase or mark pins the card for touch
 * and careful reading. The manual popover puts the card in the top layer, clear of
 * clipping widgets, while this module owns its viewport placement. */
import {
  keys,
  offer,
  once,
  paintKeys,
  reachedForWords,
  worksInside,
} from "/runtime/widget-api.js";

let nextId = 0;

customElements.define(
  "lf-gloss",
  class extends HTMLElement {
    #bubble = null;
    #dismissed = false;
    #events = null;
    #focused = false;
    #hovered = false;
    #mark = null;
    #openEvents = null;
    #pinned = false;
    #shown = false;

    connectedCallback() {
      if (once(this)) this.#build();
      this.#listen();
      this.#sync();
    }

    disconnectedCallback() {
      this.#events?.abort();
      this.#events = null;
      this.#openEvents?.abort();
      this.#openEvents = null;
      this.#hovered = false;
      this.#focused = false;
      this.#pinned = false;
      this.#shown = false;
    }

    #build() {
      const phrase = this.textContent.replace(/\s+/g, " ").trim();
      this.#mark = offer("button", "lf-gloss-mark", "°");
      this.#mark.setAttribute("aria-label", `Explain “${phrase}”`);
      this.#mark.setAttribute("aria-expanded", "false");

      this.#bubble = document.createElement("span");
      do this.#bubble.id = `lf-gloss-tip-${++nextId}`;
      while (document.getElementById(this.#bubble.id));
      this.#bubble.className = "lf-gloss-popover";
      this.#bubble.dataset.lfGen = "1";
      this.#bubble.dataset.lfSaid = "tip";
      this.#bubble.setAttribute("popover", "manual");
      this.#bubble.setAttribute("role", "note");
      this.#bubble.textContent = this.getAttribute("tip");
      this.#mark.setAttribute("aria-controls", this.#bubble.id);
      this.#mark.setAttribute("aria-describedby", this.#bubble.id);
      // x-says="after" puts the tip directly after the authored body and before any
      // trailing generated chrome. Writing that declared span here lets this module
      // also make it the popover; renderSaid sees the same marker and adds no duplicate.
      this.append(this.#bubble, this.#mark);

      keys(this.#mark, "On an explanation", [
        {
          id: "explanation.close",
          keys: ["Escape"],
          does: "Close this explanation",
          line: "close explanation",
          when: () => this.#shown,
          run: () => this.#dismiss(),
        },
      ]);
    }

    #listen() {
      if (this.#events || !this.#mark) return;
      this.#events = new AbortController();
      const { signal } = this.#events;

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
          if (this.contains(event.relatedTarget)) return;
          this.#focused = false;
          this.#dismissed = false;
          this.#sync();
        },
        { signal },
      );
      this.addEventListener(
        "lf-reveal",
        (event) => {
          // A comment can rest on the x-says tip itself. Following it asks every
          // ancestor to reveal the target before scrolling; open only for that hidden
          // span, not for an ordinary comment on the phrase beside it.
          const target = event.detail?.target;
          if (target !== this.#bubble && !this.#bubble.contains(target)) return;
          this.#dismissed = false;
          this.#pinned = true;
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
      if (show === this.#shown) {
        if (show) this.#place();
        return;
      }
      this.#shown = show;
      this.#mark.setAttribute("aria-expanded", String(show));
      paintKeys();

      if (show) {
        this.#bubble.showPopover();
        this.#place();
        this.#openEvents = new AbortController();
        const { signal } = this.#openEvents;
        window.addEventListener("resize", () => this.#place(), { signal });
        window.addEventListener("scroll", () => this.#place(), {
          capture: true,
          passive: true,
          signal,
        });
        // The scoped key row above owns Escape while its mark has focus. Hover opens
        // the same surface without moving focus, so that scope cannot see the key. Let
        // the one document dispatcher run first: an open composer or another nearer
        // scope prevents the event, and the top-layer card takes only the unclaimed
        // hover route that reaches window afterward.
        window.addEventListener(
          "keydown",
          (event) => {
            if (event.key !== "Escape" || document.activeElement === this.#mark) return;
            // A nearer scope may already have used the key (the comment composer is
            // the corpus case). It keeps ownership; the hover card merely leaves with
            // it so the one Escape does not expose a second transient layer underneath.
            if (!event.defaultPrevented) event.preventDefault();
            this.#dismiss();
          },
          { signal },
        );
        document.addEventListener(
          "pointerdown",
          (event) => {
            if (this.contains(event.target)) return;
            this.#pinned = false;
            this.#dismissed = true;
            this.#sync();
          },
          { signal },
        );
      } else {
        this.#openEvents?.abort();
        this.#openEvents = null;
        if (this.#bubble.matches(":popover-open")) this.#bubble.hidePopover();
        this.#bubble.style.removeProperty("left");
        this.#bubble.style.removeProperty("top");
        if (!this.#bubble.style.length) this.#bubble.removeAttribute("style");
      }
    }

    #dismiss() {
      this.#pinned = false;
      this.#dismissed = true;
      this.#sync();
    }

    #place() {
      if (!this.#shown || !this.#bubble.matches(":popover-open")) return;
      const anchor = this.getBoundingClientRect();
      const card = this.#bubble.getBoundingClientRect();
      const inset = 12;
      const gap = 8;
      const left = Math.min(
        Math.max(anchor.left + anchor.width / 2 - card.width / 2, inset),
        innerWidth - card.width - inset,
      );
      const below = anchor.bottom + gap;
      const top =
        below + card.height <= innerHeight - inset
          ? below
          : Math.max(inset, anchor.top - gap - card.height);
      this.#bubble.style.left = `${Math.round(left)}px`;
      this.#bubble.style.top = `${Math.round(top)}px`;
    }
  },
);
