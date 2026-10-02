/* lf-tabs: several views of one page, one panel on screen at a time.
 * The upgrade builds the strip from the panels' `label` attributes and hides
 * inactive panels with hidden="until-found", so browser find-in-page and
 * fragment navigation still reach them — `beforematch` opens the owning tab,
 * and the runtime's reveal() asks the same via the lf-reveal event when it
 * scrolls to a comment anchor. The open tab is view state for this user,
 * remembered per browser tab (`keepView`): switching is reading, not editing, so it
 * never sends an action and no version carries it — this widget doesn't ride the
 * action channel at all. Which tab a set opens on is the runtime's (`openingView`),
 * which shows the same panel at the first paint, before this module has loaded
 * (`x-views`).
 * The first tab set placed directly in main is the page's navigation over sections of
 * that page, whatever else main holds: its panel id is the URL fragment, and history
 * follows those panel entries. A link inside a panel is still fragment travel
 * (history.js).
 *
 * How a set is drawn is one fact, its flow (`data-lf-tabs-flow`), which this module
 * writes and reads and every rule for the set's presentation reads. The root set with
 * its strip written as a row is the page's own flow ("page"): its strip sticks under the
 * banner as a sticky header over the document it indexes, and its panels are sections of the
 * page, taking the page's width. Each is then a view with a place of its own: a switch,
 * by press, key, Back, or Forward, is not fragment travel, because a view is not a
 * destination, so the strip stays where it is on screen and the view opens where this
 * user last read it, or at its start when they never read past it. Every other set is a
 * box ("box"): framed, its strip in flow, each panel a bounded box that what it holds
 * measures itself against, and a switch leaves the page where it stands. `list="side"`
 * stands the list beside the panels, a queue beside the item it opens, walked up and
 * down as well as across (theme.css says where it stacks); a side list is a box even as
 * the root set, which keeps the root's history, and Back or Forward there lands the
 * set's start when the user stood below it.
 *
 * Every tab's accessible name is its label; what else the tab shows describes it. A
 * side list's row adds the panel's `summary` under the name. While the version diff is on,
 * each tab counts the marked passages its panel holds, including inactive panels. Unupgraded,
 * panels stack as labeled sections; authored content is never replaced, so
 * there is no failSoft. */
import {
  HIDDEN,
  PRESS,
  beginWalk,
  capturePlace,
  claimTraversals,
  commands,
  keepView,
  keeps,
  keepsText,
  layoutChanged,
  listWalkPosition,
  offer,
  once,
  openingView,
  pageScroller,
  preserveReadingRegions,
  pushEntry,
  relabel,
  removeRuntimeRootStyle,
  replaceEntry,
  restorePlace,
  selectableOffer,
  setRuntimeRootStyle,
  tabStore,
} from "/runtime/widget-api.js";

// The page's navigation strip, where one stands: the first tab set in main, drawn as
// a row (`#syncRootContext`).
const PAGE_STRIP = 'body > main > lf-tabs[data-lf-tabs-flow="page"]';

const PLACE_KEY = "lf-tabs-place:";
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
    #covering = false;
    #side = false;
    #pageFlow = false;

    connectedCallback() {
      if (!once(this)) {
        this.#watchRootContext();
        this.#syncRootContext();
        this.#listenForHistory();
        return this.#listenForDiff();
      }
      // Own panels only (a nested lf-tabs wires its own).
      const panels = [...this.querySelectorAll(":scope > lf-tab")];
      if (!panels.length) return;
      const side = this.getAttribute("list") === "side";
      this.#side = side;
      this.#watchRootContext();
      this.#syncRootContext();
      // The strip is a thing to work, and its tabs ride inside it, so paper drops the
      // whole row and puts each panel's label back on the panel. What a tab says is not
      // the strip's word though — it is the panel's name, and once the strip exists it
      // is the only place that name is written. So the name goes in its own span,
      // declared the page speaking, and the anchor pass reads it over the chrome around
      // it: a user points at a tab's name the way they point at a heading. Its own
      // span rather than the tab's whole text, because the Δ count lands here too and
      // it is the runtime talking about the document.
      //
      // A press is a span wearing the role rather than a <button> (see `offer`), which
      // is what makes a drag across the name possible at all.
      const strip = offer("div", "lf-tabstrip");
      this.#strip = strip;
      strip.setAttribute("role", "tablist");
      if (side) strip.setAttribute("aria-orientation", "vertical");
      strip.append(this.#edge("start"));
      for (const panel of panels) {
        const btn = selectableOffer("tab", "lf-tab-btn");
        btn.setAttribute("aria-controls", panel.id);
        const name = document.createElement("span");
        name.className = "lf-tab-name";
        relabel(name, panel.getAttribute("label"), { says: true });
        btn.append(name);
        btn.setAttribute("aria-label", panel.getAttribute("label"));
        // A queue's row says more than its name: in a side list the panel's `summary`
        // stands under it, the page's words like the name.
        if (side && panel.hasAttribute("summary")) {
          const summary = document.createElement("span");
          summary.className = "lf-tab-summary";
          relabel(summary, panel.getAttribute("summary"), { says: true });
          btn.append(summary);
        }
        const chip = document.createElement("span");
        chip.className = "lf-tabdiff";
        chip.setAttribute("aria-hidden", "true");
        btn.append(chip);
        btn.onclick = () => this.#activate(panel, "ordinary");
        strip.append(btn);
        this.#buttons.set(panel, btn);
        panel.setAttribute("role", "tabpanel");
        panel.setAttribute("aria-label", panel.getAttribute("label"));
        panel.tabIndex = 0; // a tabpanel of prose has no focusable content; Tab must still reach it
        // The browser found something inside (find-in-page, an anchor jump), or
        // the runtime is about to scroll a comment anchor into view: open up.
        panel.addEventListener("beforematch", () => this.#activate(panel, "reveal"));
        panel.addEventListener("lf-reveal", (event) => {
          const ready = this.#activate(panel, "reveal");
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
        // The strip is always on screen; focus scrolling a stuck tab back to its place
        // in flow would move the view being left before the switch records it.
        next.focus({ preventScroll: true });
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
          // A list standing beside its panels is read down, so it walks down too.
          keys: side
            ? ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"]
            : ["ArrowLeft", "ArrowRight"],
          routes: [
            ...(side
              ? [
                  { id: "tab.up", binding: "ArrowUp", does: "Previous tab" },
                  { id: "tab.down", binding: "ArrowDown", does: "Next tab" },
                ]
              : []),
            { id: "tab.previous", binding: "ArrowLeft", does: "Previous tab" },
            { id: "tab.next", binding: "ArrowRight", does: "Next tab" },
          ],
          does: "Previous / next tab, wrapping at the ends",
          line: "walk the tabs",
          repeat: true,
          run: (binding) =>
            walk((at, n) =>
              ["ArrowRight", "ArrowDown"].includes(binding)
                ? (at + 1) % n
                : (at - 1 + n) % n,
            ),
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
      strip.append(this.#edge("end"));
      this.prepend(strip);
      this.#declareHeader();
      this.classList.add("lf-rendered"); // the upgraded marker every widget uses
      // Open on the tab the first paint showed: the one the address names, or this
      // user's last, whose id resolves in later versions because check forbids
      // dropping ids. It opens here, during upgrade, so the runtime's view restore
      // measures final geometry.
      this.#activate(openingView(this, panels), "arrival");
      if (this.#root) {
        this.#listenForHistory();
        this.#replaceLocation(this.#active);
      }
      // The Δ count follows the version diff; the runtime announces each toggle.
      this.#listenForDiff();
    }

    disconnectedCallback() {
      this.#diffEvents?.abort();
      this.#diffEvents = null;
      this.#historyEvents?.abort();
      this.#historyEvents = null;
      this.#contextObserver?.disconnect();
      this.#contextObserver = null;
      // A revision that rebuilds the page's set disconnects this one and connects its
      // replacement in one operation, so the header is withdrawn only once that
      // operation is over and no strip has taken this one's place: withdrawn and
      // declared again, it would restyle the whole document for nothing.
      if (this.#covering) {
        this.#covering = false;
        queueMicrotask(() => {
          if (!document.querySelector(PAGE_STRIP))
            removeRuntimeRootStyle(document.documentElement, "--lf-root-headers");
        });
      }
    }

    // The version diff's marked passages in each panel, said with its summary as
    // the tab's description.
    #marks() {
      for (const [panel, btn] of this.#buttons) {
        const changed = panel.querySelectorAll(".lf-ins-block").length;
        keepsText(
          btn.querySelector(":scope > .lf-tabdiff"),
          changed ? `Δ${changed}` : "",
        );
        const description = [
          panel.getAttribute("summary"),
          changed === 1 ? "1 change" : changed ? `${changed} changes` : "",
        ]
          .filter(Boolean)
          .join(". ");
        keeps(btn, "aria-description", description || null);
      }
    }

    #listenForDiff() {
      if (!this.#buttons.size || this.#diffEvents) return;
      this.#diffEvents = new AbortController();
      document.addEventListener("lf-comparison", () => this.#marks(), {
        signal: this.#diffEvents.signal,
      });
      this.#marks();
    }

    #activate(active, reason) {
      if (!this.#buttons.has(active)) return;
      if (active === this.#active) return Promise.resolve();
      const previous = this.#active;
      // A press or a traversal between views switches them; a reveal is travel to
      // something inside the view, which the traveller lands.
      const switched = this.#pageFlow && ["ordinary", "history"].includes(reason);
      const change = () => {
        const from = pageScroller.scrollTop;
        if (this.#pageFlow && previous) this.#leave(previous);
        if (this.#root && reason === "ordinary") this.#pushLocation(active);
        // Whatever opened another view, the entry the user stands on names it, so
        // Back and Forward to that entry return to this view. A fragment already
        // inside it (a link's target) says so and stays.
        else if (
          this.#root &&
          reason === "reveal" &&
          this.#panelForLocation([active]) !== active
        )
          replaceEntry(this.#locationFor(active));
        for (const [panel, btn] of this.#buttons) {
          keeps(panel, "hidden", panel === active ? null : HIDDEN);
          keeps(btn, "aria-selected", panel === active);
          keeps(btn, "tabindex", panel === active ? 0 : -1);
        }
        this.#active = active;
        this.#showTab(this.#buttons.get(active));
        if (switched) this.#open(active, from);
        else if (reason === "history") this.#land();
        keepView(this, active);
        const presentation = [];
        for (const panel of [previous, active].filter(Boolean)) {
          const child = soleSubstantiveElement(panel);
          if (child) presentation.push(layoutChanged(child));
        }
        presentation.push(layoutChanged(this));
        return Promise.all(presentation);
      };
      return this.#pageFlow && previous
        ? preserveReadingRegions(this, change)
        : change();
    }

    #panelForLocation(panels, hash = location.hash) {
      if (!this.#root || !hash) return null;
      const target = this.#targetFor(hash);
      return target
        ? (panels.find((panel) => panel === target || panel.contains(target)) ?? null)
        : null;
    }

    #targetFor(hash) {
      let id;
      try {
        id = decodeURIComponent(hash.slice(1));
      } catch {
        return null;
      }
      return id ? document.getElementById(id) : null;
    }

    #syncRootContext() {
      const wasFlow = this.#pageFlow;
      // The first tab set directly in the page is its navigation, whatever else the page
      // holds beside it; a later one is a tabbed section like any nested set.
      const main = this.parentElement;
      this.#root =
        Boolean(main?.matches("body > main")) &&
        main.querySelector(":scope > lf-tabs") === this;
      this.#pageFlow = this.#root && !this.#side;
      keeps(this, "data-lf-tabs-flow", this.#pageFlow ? "page" : "box");
      if (!this.#root) {
        this.#historyEvents?.abort();
        this.#historyEvents = null;
      } else if (this.#buttons.size) {
        this.#listenForHistory();
      }
      this.#declareHeader();
      // A set that changed flow drew its open panel at another width.
      if (wasFlow !== this.#pageFlow && this.#active) {
        const child = soleSubstantiveElement(this.#active);
        if (child) layoutChanged(child);
        layoutChanged(this);
      }
    }

    #watchRootContext() {
      this.#contextObserver?.disconnect();
      this.#contextObserver = null;
      const main = this.parentElement;
      if (!main?.matches("body > main")) return;
      // Only a tab set arriving or leaving among main's children can change which is
      // first.
      this.#contextObserver = new MutationObserver(() => this.#syncRootContext());
      this.#contextObserver.observe(main, { childList: true });
    }

    // A page-flow strip sticks under the banner over the whole document, so it is a
    // sticky header of the root: its stated height (`--lf-tabstrip-h`, theme.css) joins
    // the root's `scroll-padding` as `--lf-root-headers`, and every landing arrives
    // below it. What the strip stands over inside its panels stacks through `--lf-top`
    // (the package theme). A set that stops being the page's strip withdraws it only
    // where no other set has become that strip.
    #declareHeader() {
      const covering = this.#pageFlow && Boolean(this.#strip?.isConnected);
      if (covering === this.#covering) return;
      this.#covering = covering;
      const root = document.documentElement;
      if (covering)
        setRuntimeRootStyle(root, "--lf-root-headers", "var(--lf-tabstrip-h)");
      else if (!document.querySelector(PAGE_STRIP))
        removeRuntimeRootStyle(root, "--lf-root-headers");
    }

    // A press at one edge of the strip, which pages the names that run past it (the
    // package theme shows it only while there is more that way). It takes no tab stop:
    // the tabs are the keyboard's route, and a focused tab brings itself into view.
    #edge(to) {
      const edge = document.createElement("span");
      edge.className = "lf-tabstrip-scroll";
      edge.dataset.to = to;
      edge.setAttribute("aria-hidden", "true");
      const face = document.createElement("span");
      face.onclick = () => {
        const strip = this.#strip;
        const ahead = getComputedStyle(strip).direction === "rtl" ? -1 : 1;
        strip.scrollBy({
          left: ahead * (to === "start" ? -0.8 : 0.8) * strip.clientWidth,
          behavior: "smooth",
        });
      };
      edge.append(face);
      return edge;
    }

    // A tab the row runs past is scrolled into the strip, and only the strip: the
    // strip sticks, and scrolling the page to it would move the view being read. It
    // stops clear of the edge's press, which the strip states as its inline
    // `scroll-padding` (the package theme).
    #showTab(btn) {
      if (!this.#pageFlow || !btn) return;
      const strip = this.#strip;
      const room = strip.getBoundingClientRect();
      const box = btn.getBoundingClientRect();
      const { scrollPaddingLeft, scrollPaddingRight } = getComputedStyle(strip);
      const left = room.left + (Number.parseFloat(scrollPaddingLeft) || 0);
      const right = room.right - (Number.parseFloat(scrollPaddingRight) || 0);
      if (box.left < left) strip.scrollLeft -= left - box.left;
      else if (box.right > right) strip.scrollLeft += box.right - right;
    }

    #listenForHistory() {
      if (!this.#root || this.#historyEvents) return;
      this.#historyEvents = new AbortController();
      const { signal } = this.#historyEvents;
      // Back or Forward to an entry in another view switches to it, as a press does.
      // One within the open view is the browser's to restore (history.js).
      claimTraversals(
        (url) => {
          const view = this.#panelForLocation([...this.#buttons.keys()], url.hash);
          return view && view !== this.#active
            ? () => this.#activate(view, "history")
            : null;
        },
        { signal },
      );
    }

    #locationFor(panel) {
      const url = new URL(location.href);
      url.hash = panel.id;
      return url;
    }

    #replaceLocation(panel) {
      if (!panel || location.hash) return;
      replaceEntry(this.#locationFor(panel));
    }

    #pushLocation(panel) {
      if (location.hash === `#${panel.id}`) return;
      pushEntry(this.#locationFor(panel));
    }

    // A page-flow view starts where its strip sticks, so an offset short of that is the
    // shared header, not a place in the view.
    #start() {
      return (
        this.getBoundingClientRect().top +
        pageScroller.scrollTop -
        parseFloat(getComputedStyle(this.#strip).top)
      );
    }

    // A view the user read past its start keeps that place as a landmark in its own
    // words, so the place survives what moves the pixels while the view is hidden: a
    // resize, a new revision. It is kept per browser tab like the open tab itself, so a
    // reload still returns each view to its place. A view left at its start keeps none.
    #leave(panel) {
      const read = pageScroller.scrollTop > this.#start() + 0.5;
      tabStore.set(this.#placeKey(panel), read ? JSON.stringify(capturePlace()) : null);
    }

    // A view reopens at its place. One without keeps the header as the user has it,
    // clamped to the view's start so a stuck strip stays stuck.
    #open(panel, from) {
      const start = this.#start();
      let place = null;
      try {
        place = JSON.parse(tabStore.get(this.#placeKey(panel)));
      } catch {
        // An unreadable place is no place.
      }
      pageScroller.scrollTop = place ? start : Math.min(from, start);
      if (place) restorePlace(place);
    }

    // A box's views have no places of their own, and Back or Forward is made from wherever
    // the user reads: left where it stood, a view shorter than the one it replaced puts
    // them at the page's end, partway down it. So a traversal lands the set's start, as a
    // page-flow view without a place lands at its own, and leaves a set already in view
    // where it is.
    #land() {
      if (this.getBoundingClientRect().top < 0)
        this.scrollIntoView({ block: "start", behavior: "instant" });
    }

    #placeKey(panel) {
      return `${PLACE_KEY}${this.id}:${panel.id}`;
    }
  },
);
