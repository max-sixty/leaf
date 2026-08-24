/* lf-tabs: parallel workstreams on one page, one panel on screen at a time.
 * The upgrade builds the strip from the panels' `label` attributes and hides
 * inactive panels with hidden="until-found", so browser find-in-page and
 * fragment navigation still reach them — `beforematch` opens the owning tab,
 * and the runtime's reveal() asks the same via the lf-reveal event when it
 * scrolls to a comment anchor. The open tab is view state for this reader,
 * remembered per browser tab in the runtime's tabStore like the scroll position:
 * switching is reading, not editing, so it never sends an action and no
 * version carries it — this widget doesn't ride the action channel at all.
 * While the version diff is on, a tab whose panel holds marked passages wears
 * a Δ count, so a change can't hide behind an inactive tab. Unupgraded,
 * panels stack as labeled sections; authored content is never replaced, so
 * there is no failSoft. */
import { once, keys, offer, relabel, tabStore, HIDDEN } from "/leaf.js";

const TAB_KEY = "lf-tabs:";

customElements.define(
  "lf-tabs",
  class extends HTMLElement {
    #buttons = new Map(); // panel → its strip button
    #diffEvents = null;

    connectedCallback() {
      if (!once(this)) return this.#listenForDiff();
      // Own panels only (a nested lf-tabs wires its own).
      const panels = [...this.querySelectorAll(":scope > lf-tab")];
      if (!panels.length) return;
      // The strip is a thing to work, and its tabs ride inside it, so paper drops the
      // whole row and puts each panel's label back on the panel. What a tab says is not
      // the strip's word though — it is the panel's name, and once the strip exists it
      // is the only place that name is written. So the name goes in its own span,
      // declared the page speaking, and the anchor pass reads it over the chrome around
      // it: a user points at a tab's name the way they point at a heading. Its own
      // span rather than the tab's whole text, because the Δ badge lands here too and
      // that one is the runtime talking about the document.
      //
      // A press is a span wearing the role rather than a <button> (see `offer`), which
      // is what makes a drag across the name possible at all.
      const strip = offer("div", "lf-tabstrip");
      strip.setAttribute("role", "tablist");
      for (const panel of panels) {
        const btn = offer("button", "lf-tab-btn");
        btn.setAttribute("role", "tab");
        btn.setAttribute("aria-controls", panel.id);
        const name = document.createElement("span");
        relabel(name, panel.getAttribute("label"), { says: true });
        btn.append(name);
        btn.onclick = () => this.#activate(panel, true);
        strip.append(btn);
        this.#buttons.set(panel, btn);
        panel.setAttribute("role", "tabpanel");
        panel.setAttribute("aria-label", panel.getAttribute("label"));
        panel.tabIndex = 0; // a tabpanel of prose has no focusable content; Tab must still reach it
        // The browser found something inside (find-in-page, an anchor jump), or
        // the runtime is about to scroll a comment anchor into view: open up.
        panel.addEventListener("beforematch", () => this.#activate(panel, true));
        panel.addEventListener("lf-reveal", () => this.#activate(panel, true));
      }
      // Roving focus per the ARIA tabs pattern: arrows move and activate, and wrap, which
      // is a fact about this walk and so belongs in the words that name it.
      const walk = (to) => {
        const order = [...this.#buttons.values()];
        // The strip takes no tab stop of its own, so focus inside it — which is the
        // whole of when this scope holds — is always one of these buttons.
        const at = order.indexOf(document.activeElement);
        const next = order[to(at, order.length)];
        next.focus();
        next.click();
      };
      keys(strip, "On a tab", [
        {
          keys: ["ArrowLeft", "ArrowRight"],
          does: "Previous / next tab, wrapping at the ends",
          line: "walk the tabs",
          repeat: true,
          run: (binding) =>
            walk((at, n) => (binding === "ArrowRight" ? at + 1 : at - 1 + n) % n),
        },
        {
          keys: ["Home", "End"],
          does: "First / last tab",
          line: "first / last",
          run: (binding) => walk((at, n) => (binding === "Home" ? 0 : n - 1)),
        },
      ]);
      this.prepend(strip);
      this.classList.add("lf-rendered"); // the upgraded marker every widget uses
      // Restore this reader's tab; a remembered id always resolves in later
      // versions because check forbids dropping ids. Restoration happens here,
      // during upgrade, so the runtime's view restore measures final geometry.
      const saved = tabStore.get(TAB_KEY + this.id);
      this.#activate(panels.find((p) => p.id === saved) || panels[0], false);
      // Δ badges follow the version diff; the runtime announces each toggle.
      this.#listenForDiff();
    }

    disconnectedCallback() {
      this.#diffEvents?.abort();
      this.#diffEvents = null;
    }

    #listenForDiff() {
      if (!this.#buttons.size || this.#diffEvents) return;
      this.#diffEvents = new AbortController();
      document.addEventListener("lf-comparison", () => this.#badges(), {
        signal: this.#diffEvents.signal,
      });
    }

    #activate(active, remember) {
      for (const [panel, btn] of this.#buttons) {
        if (panel === active) panel.removeAttribute("hidden");
        else panel.setAttribute("hidden", HIDDEN);
        btn.setAttribute("aria-selected", panel === active ? "true" : "false");
        btn.tabIndex = panel === active ? 0 : -1;
      }
      if (remember) tabStore.set(TAB_KEY + this.id, active.id);
    }

    // One Δn chip per tab holding marked passages, so the toast's count is
    // accounted for even where the marks sit behind an inactive tab.
    #badges() {
      for (const [panel, btn] of this.#buttons) {
        btn.querySelector(".lf-tabdiff")?.remove();
        const n = panel.querySelectorAll(".lf-ins-block").length;
        if (!n) continue;
        const chip = document.createElement("span");
        chip.className = "lf-tabdiff";
        chip.textContent = `Δ${n}`;
        btn.append(chip);
      }
    }
  },
);
