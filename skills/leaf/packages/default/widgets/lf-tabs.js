/* lf-tabs: several views of one page, one panel on screen at a time.
 * The upgrade builds the strip from the panels' `label` attributes and hides
 * inactive panels with hidden="until-found", so browser find-in-page and
 * fragment navigation still reach them — `beforematch` opens the owning tab,
 * and the runtime's reveal() asks the same via the lf-reveal event when it
 * scrolls to a comment anchor. The open tab is view state for this reader,
 * remembered per browser tab in the runtime's tabStore:
 * switching is reading, not editing, so it never sends an action and no
 * version carries it — this widget doesn't ride the action channel at all.
 * A tab set that is the main element's sole substantive child, below an optional
 * header, becomes the page composition: its panel id is the URL fragment, history
 * follows those panel entries. Switching views and browser history use native
 * fragment navigation to the chosen panel.
 * Embedded tab sets retain the ordinary framed-widget behavior.
 * While the version diff is on, a tab whose panel holds marked passages wears
 * a Δ count, so a change can't hide behind an inactive tab. Unupgraded,
 * panels stack as labeled sections; authored content is never replaced, so
 * there is no failSoft. */
import {
  HIDDEN,
  PRESS,
  beginWalk,
  commands,
  layoutChanged,
  listWalkPosition,
  offer,
  once,
  preserveReadingRegions,
  relabel,
  removeRuntimeRootStyle,
  selectableOffer,
  setRuntimeRootStyle,
  tabStore,
} from "/runtime/widget-api.js";

const TAB_KEY = "lf-tabs:";
const substantiveChildren = (owner) =>
  [...owner.childNodes].filter(
    (child) =>
      (child.nodeType === Node.ELEMENT_NODE &&
        !child.matches("script, style, template")) ||
      (child.nodeType === Node.TEXT_NODE && child.textContent.trim()),
  );
const soleSubstantiveElement = (owner) => {
  const children = substantiveChildren(owner);
  return children.length === 1 && children[0] instanceof Element ? children[0] : null;
};

customElements.define(
  "lf-tabs",
  class extends HTMLElement {
    #buttons = new Map(); // panel → its strip button
    #diffEvents = null;
    #historyEvents = null;
    #active = null;
    #root = false;
    #contextObserver = null;
    #strip = null;
    #stripResize = null;

    connectedCallback() {
      if (!once(this)) {
        this.#watchRootContext();
        this.#watchStrip();
        this.#syncRootContext();
        this.#listenForHistory();
        return this.#listenForDiff();
      }
      // Own panels only (a nested lf-tabs wires its own).
      const panels = [...this.querySelectorAll(":scope > lf-tab")];
      if (!panels.length) return;
      this.#watchRootContext();
      this.#syncRootContext();
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
      this.#strip = strip;
      strip.setAttribute("role", "tablist");
      for (const panel of panels) {
        const btn = selectableOffer("tab", "lf-tab-btn");
        btn.setAttribute("aria-controls", panel.id);
        const name = document.createElement("span");
        relabel(name, panel.getAttribute("label"), { says: true });
        btn.append(name);
        btn.onclick = () => this.#activate(panel, true, "ordinary");
        strip.append(btn);
        this.#buttons.set(panel, btn);
        panel.setAttribute("role", "tabpanel");
        panel.setAttribute("aria-label", panel.getAttribute("label"));
        panel.tabIndex = 0; // a tabpanel of prose has no focusable content; Tab must still reach it
        // The browser found something inside (find-in-page, an anchor jump), or
        // the runtime is about to scroll a comment anchor into view: open up.
        panel.addEventListener("beforematch", () =>
          this.#activate(panel, true, "reveal"),
        );
        panel.addEventListener("lf-reveal", (event) => {
          const ready = this.#activate(panel, true, "reveal");
          event.detail?.present?.(ready);
        });
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
        beginWalk("tab", "Tab", () =>
          listWalkPosition([...this.#buttons.values()], document.activeElement),
        );
      };
      commands(strip, "On a tab", [
        {
          id: "tab.activate",
          keys: PRESS,
          does: "Open the focused tab",
          line: "open the tab",
          // The tab already open has nothing for this press to do, so the line does not
          // name it there; the walk beside it is what moves.
          when: () => document.activeElement?.getAttribute("aria-selected") !== "true",
          run: () => document.activeElement.click(),
        },
        {
          id: "tab.walk",
          keys: ["ArrowLeft", "ArrowRight"],
          routes: [
            { id: "tab.previous", binding: "ArrowLeft", does: "Previous tab" },
            { id: "tab.next", binding: "ArrowRight", does: "Next tab" },
          ],
          does: "Previous / next tab, wrapping at the ends",
          line: "walk the tabs",
          repeat: true,
          run: (binding) =>
            walk((at, n) => (binding === "ArrowRight" ? at + 1 : at - 1 + n) % n),
        },
        {
          id: "tab.edge",
          keys: ["Home", "End"],
          routes: [
            { id: "tab.first", binding: "Home", does: "First tab" },
            { id: "tab.last", binding: "End", does: "Last tab" },
          ],
          does: "First / last tab",
          line: "first / last",
          run: (binding) => walk((at, n) => (binding === "Home" ? 0 : n - 1)),
        },
      ]);
      this.prepend(strip);
      this.#watchStrip();
      this.classList.add("lf-rendered"); // the upgraded marker every widget uses
      // Restore this reader's tab; a remembered id always resolves in later
      // versions because check forbids dropping ids. Restoration happens here,
      // during upgrade, so the runtime's view restore measures final geometry.
      const saved = tabStore.get(TAB_KEY + this.id);
      const arrived = this.#panelForLocation(panels);
      this.#activate(
        arrived || panels.find((panel) => panel.id === saved) || panels[0],
        false,
        "arrival",
      );
      if (this.#root) {
        this.#listenForHistory();
        this.#replaceLocation(this.#active);
      }
      // Δ badges follow the version diff; the runtime announces each toggle.
      this.#listenForDiff();
    }

    disconnectedCallback() {
      this.#diffEvents?.abort();
      this.#diffEvents = null;
      this.#historyEvents?.abort();
      this.#historyEvents = null;
      this.#contextObserver?.disconnect();
      this.#contextObserver = null;
      this.#stripResize?.disconnect();
      this.#stripResize = null;
      this.#clearStickyClearance();
    }

    #listenForDiff() {
      if (!this.#buttons.size || this.#diffEvents) return;
      this.#diffEvents = new AbortController();
      document.addEventListener("lf-comparison", () => this.#badges(), {
        signal: this.#diffEvents.signal,
      });
    }

    #activate(active, remember, reason) {
      if (!this.#buttons.has(active)) return;
      if (active === this.#active) {
        if (this.#root && reason === "ordinary") this.#navigateTo(active);
        return Promise.resolve();
      }
      const previous = this.#active;
      const change = () => {
        for (const [panel, btn] of this.#buttons) {
          if (panel === active) panel.removeAttribute("hidden");
          else panel.setAttribute("hidden", HIDDEN);
          panel.toggleAttribute("data-lf-root-reading", this.#root && panel === active);
          btn.setAttribute("aria-selected", panel === active ? "true" : "false");
          btn.tabIndex = panel === active ? 0 : -1;
        }
        this.#active = active;
        if (remember) tabStore.set(TAB_KEY + this.id, active.id);
        const presentation = [];
        for (const panel of [previous, active].filter(Boolean)) {
          const child = soleSubstantiveElement(panel);
          if (child) presentation.push(layoutChanged(child));
        }
        presentation.push(layoutChanged(this));
        if (this.#root && reason === "ordinary") this.#navigateTo(active);
        return Promise.all(presentation);
      };
      return this.#root && previous ? preserveReadingRegions(this, change) : change();
    }

    #panelForLocation(panels) {
      if (!this.#root || !location.hash) return null;
      const target = this.#targetForLocation();
      return target
        ? (panels.find((panel) => panel === target || panel.contains(target)) ?? null)
        : null;
    }

    #targetForLocation() {
      let id;
      try {
        id = decodeURIComponent(location.hash.slice(1));
      } catch {
        return null;
      }
      return document.getElementById(id);
    }

    #syncRootContext() {
      const wasRoot = this.#root;
      const main = this.parentElement;
      const rootContent = main?.matches("body > main") ? substantiveChildren(main) : [];
      this.#root =
        rootContent.length <= 2 &&
        rootContent.at(-1) === this &&
        (rootContent.length === 1 || rootContent[0].tagName === "HEADER");
      this.dataset.lfTabsContext = this.#root ? "root" : "embedded";
      if (!this.#root) {
        this.#historyEvents?.abort();
        this.#historyEvents = null;
      } else if (this.#buttons.size) {
        this.#listenForHistory();
      }
      for (const panel of this.#buttons.keys()) {
        const marked = panel.hasAttribute("data-lf-root-reading");
        const rootPanel = this.#root && panel === this.#active;
        panel.toggleAttribute("data-lf-root-reading", rootPanel);
        if (marked !== rootPanel) {
          const child = soleSubstantiveElement(panel);
          if (child) layoutChanged(child);
        }
      }
      this.#syncStickyClearance();
      if (wasRoot !== this.#root) layoutChanged(this);
    }

    #watchRootContext() {
      this.#contextObserver?.disconnect();
      this.#contextObserver = null;
      const main = this.parentElement;
      if (!main?.matches("body > main")) return;
      this.#contextObserver = new MutationObserver((records) => {
        if (
          records.some(
            (record) =>
              (record.type === "childList" && record.target === main) ||
              (record.type === "characterData" && record.target.parentNode === main),
          )
        )
          this.#syncRootContext();
      });
      this.#contextObserver.observe(main, {
        childList: true,
        characterData: true,
        subtree: true,
      });
    }

    #watchStrip() {
      this.#stripResize?.disconnect();
      this.#stripResize = null;
      if (!this.#strip) return;
      this.#stripResize = new ResizeObserver(() => this.#syncStickyClearance());
      this.#stripResize.observe(this.#strip);
      this.#syncStickyClearance();
    }

    #syncStickyClearance() {
      if (!this.#root || !this.#strip?.isConnected) {
        this.#clearStickyClearance();
        return;
      }
      setRuntimeRootStyle(
        document.documentElement,
        "--lf-root-tab-clear",
        `${this.#strip.getBoundingClientRect().height}px`,
      );
    }

    #clearStickyClearance() {
      if (!document.querySelector('body > main > lf-tabs[data-lf-tabs-context="root"]'))
        removeRuntimeRootStyle(document.documentElement, "--lf-root-tab-clear");
    }

    #listenForHistory() {
      if (!this.#root || this.#historyEvents) return;
      this.#historyEvents = new AbortController();
      const followLocation = () => {
        const panel = this.#panelForLocation([...this.#buttons.keys()]);
        if (panel && panel !== this.#active) this.#activate(panel, true, "reveal");
      };
      window.addEventListener("popstate", followLocation, {
        signal: this.#historyEvents.signal,
      });
      window.addEventListener("hashchange", followLocation, {
        signal: this.#historyEvents.signal,
      });
    }

    #locationFor(panel) {
      const url = new URL(location.href);
      url.hash = panel.id;
      return url;
    }

    #replaceLocation(panel) {
      if (!panel || location.hash) return;
      history.replaceState(history.state, "", this.#locationFor(panel));
    }

    #navigateTo(panel) {
      if (location.hash === `#${panel.id}`) return;
      location.hash = panel.id;
      // Fragment travel focuses its target; a tab press keeps the roving strip
      // focused so another arrow can continue the same walk.
      this.#buttons.get(panel).focus({ preventScroll: true });
    }

    // One Δn chip per tab holding marked passages, so the notice's count is
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
