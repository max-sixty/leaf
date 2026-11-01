/* lf-tabs: several views of one page, one panel on screen at a time.
 * Lit draws the generated strip from panel labels and tracked readings; authored
 * panels stay outside its render root. The upgrade hides
 * inactive panels with hidden="until-found", so browser find-in-page and
 * fragment navigation still reach them, and so does Leaf's travel to a comment
 * anchor, which reveals as they do: `beforematch` opens the owning tab. A page can
 * make a panel itself scroll with CSS, so the widget declares each panel as a scroll
 * surface; its CSS still decides
 * whether that panel scrolls. The open tab is view state for this user,
 * remembered per browser tab (`keepView`): switching is reading, not editing, so it
 * never sends an action and no version carries it — this widget doesn't ride the
 * action channel at all. Which tab a set opens on is the runtime's (`openingView`),
 * which selects the member before its first paint (`x-views`).
 * The first tab set placed directly in main is the page's navigation over sections of
 * that page, whatever else main holds: its panel id is the URL fragment, and history
 * follows those panel entries. A link inside a panel is still fragment travel
 * (history.js).
 *
 * The authored layout-flow declares document flow (`--lf-views-flow`, layouts.css);
 * the package styles its unframed face. This module reads that declaration for
 * scrolling, separately from primary URL/history ownership above. In document flow
 * ("page"), the strip sticks at the
 * window's top as a sticky header over the document it indexes, and its panels are sections of the
 * page, taking the page's width. Each is then a view with a place of its own: a switch,
 * by press, key, Back, or Forward, is not fragment travel, because a view is not a
 * destination, so the strip stays where it is on screen and the view opens where this
 * user last read it, or at its start when they never read past it. Every other set is a
 * box ("box"): framed, its horizontal strip sticky within the set, each panel a bounded
 * box that what it holds measures itself against. A switch leaves the page where it
 * stands until the strip is pinned; then it opens the new panel at its start. `list="side"`
 * stands the list beside the panels, a queue beside the item it opens, walked up and
 * down as well as across (base.css says where it stacks); a side list is a box even as
 * the root set, which keeps the root's history, and Back or Forward restores the
 * entry's viewport after showing its view. Where a side list fills a height it is
 * given, as a full-height workspace's body (base.css), its list and its open item each
 * scroll on their own. Its panels are reading regions, and so is its list while it
 * scrolls on its own, so reading keys and the user's place follow the list or the item
 * rather than the set.
 *
 * A page's parts (`lf-parts`, lf-parts.js) are this module's set under their own tag,
 * with `lf-part` members. They stand directly in a `main` that carries no Layout
 * (`page check` refuses one that carries one), and each part's child carries a Layout
 * of its own (layouts.css, "A page of parts"). They are the page's own flow: each part
 * has a place of its own,
 * and its id is the URL fragment, as a page tab's is. Their list runs down the window's
 * left edge, under the page's title, walked up and down as well as across, each row
 * with its part's `summary` as a side list's has; the parts beside it start at the
 * window's top, so the list is no header over them. Where the window is too narrow for
 * the column, as on a phone, the list is a row sticking over the open part, a header
 * as the page tabs' row is. Parts placed anywhere else, as when the corpus embeds a
 * page, are no page's navigation, and list their names in a row.
 *
 * Travel into a hidden panel briefly highlights its selected name, without moving
 * focus from the destination or delaying it. Reduced motion keeps the selected state
 * without the highlight; switching again or disconnecting cancels an unfinished cue.
 * Adjacent pointer choices along a horizontal strip move only the selection underline
 * for 160ms. Content and accessible selection change at once; keyboard and vertical
 * navigation stay immediate. A reversed choice continues from the line's painted place,
 * and scrolling or resizing the strip ends the cue at its selected tab.
 * Every tab's accessible name is its label; what else the tab shows describes it. A
 * side list stands each run of neighbouring panels that share a `group` under a label
 * of that group, which each of their tabs' descriptions names. A side list's row adds
 * the panel's `summary` under the name, then its obligations' state on a reserved line. While any
 * obligation the panel holds is unanswered, it shows an open mark and whose turn it is, by the
 * server's next actor, the reading an `lf-tally` and its Next on me use: the mark alone while one
 * waits on the user, since the mark and the tally already say so (its description says "To
 * answer"), else "On Claude" (`agentName`) while one is the agent's, as after the user
 * comments on it, else "Open", as in a resolved thread. Once every one is answered it shows a
 * check, with the answer's own words where the panel holds one obligation. So a queue shows each obligation's state
 * and how far the user has worked through it, and an undo that reopens an obligation puts the
 * open mark back. Which obligations a panel holds is `obligationsIn` (obligations/place.js), read from the
 * admitted obligation inventory, so a tally of the queue counts the same obligations. A row whose panel
 * authors an obligation keeps the mark's room either way, so an answer moves no row. While the
 * version diff is on, each tab counts the marked passages its panel holds, including
 * inactive panels. Unupgraded,
 * panels stack as labeled sections; authored content is never replaced, so
 * there is no failSoft. */
import {
  setScroll,
  actionTemplate,
  agentName,
  PRESS,
  obligationsIn,
  answerWords,
  under,
  backgroundFlash,
  flashDuration,
  beginWalk,
  capturePlace,
  comparisonChanges,
  claimTraversals,
  compoundReadingRegionId,
  cycledRow,
  elementsDeclaring,
  keepView,
  keeps,
  layoutChanged,
  listWalkPosition,
  whileConnected,
  offer,
  generated,
  openingView,
  viewMembers,
  pageScroller,
  preserveReadingRegions,
  pushEntry,
  registerReadingRegion,
  registerRootHeader,
  replaceEntry,
  restorePlace,
  scrollBehavior,
  scrollIntoReadingBand,
  selectableOffered,
  sizeObserver,
  tabStore,
  focusDestination,
  fragmentTarget,
  rowArrows,
  scrollIntoView,
  focused,
  fitsWhole,
  landingInsets,
  layoutPx,
  pressIsKeyboardActivation,
  signal,
  LeafElement,
  html,
  nothing,
  render,
  repeat,
  ref,
  commandsChanged,
} from "/runtime/widget-api.js";

const PLACE_KEY = "lf-tabs-place:";
/** @param {Element} owner */
const substantiveChildren = (owner) =>
  [...owner.childNodes].filter(
    (child) =>
      (child instanceof Element && !child.matches("script, style, template")) ||
      (child instanceof Text && child.data.trim()),
  );
/** @param {Element} owner */
const soleSubstantiveElement = (owner) => {
  const children = substantiveChildren(owner);
  return children.length === 1 && children[0] instanceof Element ? children[0] : null;
};

export class TabSet extends LeafElement {
  // Whether the set is a page's parts (lf-parts.js).
  get parts() {
    return false;
  }
  #parts = this.parts;
  /** @type {Map<Element, HTMLElement>} */
  /** @type {Map<Element, HTMLElement>} */
  #buttons = new Map(); // panel → its strip button
  /** @type {Element[]} */
  #panels = [];
  /** @type {{panel: Element, group: string | null, panels: Element[]}[]} */
  #runs = [];
  #down = false;
  // The open panel, a signal because the strip's Enter row reads which tab is open.
  /** @type {import("@preact/signals-core").Signal<Element | null>} */
  #active = signal(null);
  #root = false;
  /** @type {(MutationObserver) | null} */
  #contextObserver = null;
  #strip = offer("div", "lf-tabstrip scroll");
  /** @type {(() => void) | null} */
  #stopHeader = null;
  #side = false;
  #pageFlow = false;
  /** @type {(ReturnType<typeof backgroundFlash>) | null} */
  #revealMotion = null;
  /** @type {(() => void) | null} */
  #stopList = null;

  createRenderRoot() {
    return this.#strip ?? this;
  }

  setup() {
    const panels = viewMembers(this);
    if (!panels.length) return;
    this.#panels = panels;
    const side = this.getAttribute("list") === "side";
    this.#side = side;
    this.#watchRootContext();
    this.#syncRootContext();
    // A side list and a page's list of parts both run down beside their panels; parts
    // placed anywhere else list their names in a row (the package theme).
    const down = side || (this.#parts && this.#root);
    this.#down = down;
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
    const strip = this.#strip;
    strip.setAttribute("role", "tablist");
    if (down) strip.setAttribute("aria-orientation", "vertical");
    // Group runs are fixed by authored panels. Lit owns every generated child;
    // panel nodes stay outside its render root, with native reading and focus state.
    /** @type {{panel: Element, group: string | null, panels: Element[]} | undefined} */
    let run;
    for (const panel of panels) {
      const group = panel.getAttribute("group");
      if (!run || (side && group !== run.group)) {
        run = { panel, group, panels: [] };
        this.#runs.push(run);
      }
      run.panels.push(panel);
      if (!panel.classList.contains("scroll")) panel.classList.add("scroll");
      panel.setAttribute("role", "tabpanel");
      keeps(panel, "aria-label", panel.getAttribute("label"));
      // The browser found something inside (find-in-page, an anchor jump), or
      // Leaf is about to scroll a comment anchor into view: open up.
      panel.addEventListener("beforematch", () => this.#activate(panel, "reveal"));
    }
    // Build the strip before opening its panel: activation measures the selected
    // name and the underline in this same task. Later publication uses LeafElement's
    // tracked render; its unchanged Lit parts retain these exact nodes.
    render(this.render(), strip);
    // Roving focus per the ARIA tabs pattern: arrows move and activate, and come round
    // at the ends as every cyclic walk does (`cycledRow`). The strip takes no tab stop
    // of its own, so focus inside it, which is the whole of when this scope holds, is
    // always one of these buttons.
    const tabs = () => [...this.#buttons.values()];
    const focusedTab = () => tabs().find((button) => button === focused());
    /** @param {HTMLElement | undefined} next */
    const walk = (next) => {
      if (!next) return;
      // The strip is always on screen; focus scrolling a stuck tab back to its place
      // in flow would move the view being left before the switch records it.
      focusDestination(next, "move");
      next.click();
      beginWalk("tab", "Tab", () => listWalkPosition(tabs(), focused()));
    };
    // Across the row, back is the way the names run from.
    const arrows = rowArrows(this);
    const back = arrows[0];
    const ahead = arrows[1];
    strip.lfCommands = {
      title: "On a tab",
      rows: [
        {
          id: "tab.activate",
          keys: PRESS,
          title: "open the tab",

          // The tab already open has nothing for this press to do, so the line does not
          // name it there; the walk beside it is what moves.
          when: () => focused() !== this.#currentButton(),
          run: () => {
            focusedTab()?.click();
          },
        },
        {
          id: "tab.walk",
          // A list standing beside its panels is read down, so it walks down too.
          keys: down
            ? ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"]
            : ["ArrowLeft", "ArrowRight"],
          routes: [
            ...(down
              ? [
                  { id: "tab.up", binding: "ArrowUp", title: "Previous tab" },
                  { id: "tab.down", binding: "ArrowDown", title: "Next tab" },
                ]
              : []),
            { id: "tab.previous", binding: back, title: "Previous tab" },
            { id: "tab.next", binding: ahead, title: "Next tab" },
          ],
          title: "walk the tabs",
          repeat: true,
          travels: true,
          runKey: (binding) => {
            const step = [ahead, "ArrowDown"].includes(binding) ? 1 : -1;
            walk(cycledRow(tabs(), focusedTab(), step));
          },
        },
        {
          id: "tab.edge",
          keys: ["Home", "End"],
          routes: [
            { id: "tab.first", binding: "Home", title: "First tab" },
            { id: "tab.last", binding: "End", title: "Last tab" },
          ],
          title: "first / last",
          travels: true,
          runKey: (binding) => walk(binding === "Home" ? tabs()[0] : tabs().at(-1)),
        },
      ],
    };
    commandsChanged(strip);
    this.prepend(strip);
    this.#declareHeader();
    this.classList.add("lf-rendered"); // the upgraded marker every widget uses
    // Open the tab the address names, or this
    // user's last, whose id resolves in later versions because check forbids
    // dropping ids. It opens here, during upgrade, so the runtime's view restore
    // measures final geometry.
    this.#activate(openingView(this) ?? null, "arrival");
    if (this.#root) {
      this.#replaceLocation(this.#active.value);
    }
    whileConnected(this, (signal) => {
      this.#watchRootContext();
      this.#syncRootContext();
      this.#listenForHistory(signal);
      const stripSize = this.#watchStrip();
      strip.addEventListener("scroll", this.#stopSelectionMotion, { signal });
      const stopPanels = this.#side
        ? [...this.#buttons.keys()].map((panel) =>
            registerReadingRegion({
              id: compoundReadingRegionId(this, `panel-${panel.id}`),
              host: panel,
              body: panel,
            }),
          )
        : [];
      this.#syncRegions();
      return () => {
        for (const stop of stopPanels) stop();
        this.#stopList?.();
        this.#stopList = null;
        this.#revealMotion?.cancel();
        this.#revealMotion = null;
        this.#stopSelectionMotion();
        stripSize.disconnect();
        this.#contextObserver?.disconnect();
        this.#contextObserver = null;
        this.#stopHeader?.();
        this.#stopHeader = null;
      };
    });
  }

  // A side list's panels are reading regions whatever their posture, as panes are, so
  // the user's place in an item survives the workspace flowing and filling the window
  // again. Its list is one only while it is a column scrolling on its own, while the
  // set is told it has a definite height to fill (`--lf-full-height`, base.css):
  // elsewhere the strip keeps its open tab in view itself (`#showTab`), and observed
  // as a region there, its own scrolling as it turned into a row ended the size
  // observers' pass with notifications undelivered. Whether the set is told follows
  // the window, so the strip's size observer asks again.
  #syncRegions() {
    if (!this.#side || !this.isConnected) return;
    const told =
      getComputedStyle(this).getPropertyValue("--lf-full-height").trim() === "1";
    if (told === Boolean(this.#stopList)) return;
    this.#stopList?.();
    this.#stopList = told
      ? registerReadingRegion({
          id: compoundReadingRegionId(this, "list"),
          host: this.#strip,
          body: this.#strip,
        })
      : null;
  }

  // What each panel holds, said with its summary as the tab's description: the
  // version diff's marked passages, and in a side list its obligations' state, with the answer
  // once they are all answered.
  render() {
    if (!this.#panels.length) return nothing;
    return html`${this.#edge("start")}${
        this.#side
          ? repeat(
              this.#runs,
              (run) => run.panel,
              (run) =>
                html` <div class="lf-tab-run" role="none">
                  ${
                    run.group
                      ? html`<span
                          class="lf-tab-group lf-rows-head"
                          aria-hidden="true"
                          ${generated({ says: true })}
                          >${run.group}</span
                        >`
                      : nothing
                  }
                  ${repeat(
                    run.panels,
                    (panel) => panel,
                    (panel) => this.#tab(panel),
                  )}
                </div>`,
            )
          : repeat(
              this.#panels,
              (panel) => panel,
              (panel) => this.#tab(panel),
            )
      }${this.#edge("end")}<span class="lf-tab-selection" aria-hidden="true"></span>`;
  }

  #currentButton() {
    const active = this.#active.value;
    return active ? this.#buttons.get(active) : undefined;
  }

  /** @param {Element} panel */
  #tab(panel) {
    const changed = comparisonChanges(panel).length;
    const hasAnswer = this.#side && elementsDeclaring(panel, "x-awaits").length > 0;
    const items = hasAnswer ? obligationsIn(panel) : [];
    // Withdrawn items are already left out; an answer given elsewhere ends one too.
    const done = items.filter((item) => item.status !== "open");
    const answered = items.length > 0 && done.length === items.length;
    const only = items.length === 1 ? items[0] : null;
    const open = items.filter((item) => item.status === "open");
    const onUser = open.some((item) => item.next_actor === "user");
    const turn = onUser
      ? "To answer"
      : open.some((item) => item.next_actor === "agent")
        ? `On ${agentName()}`
        : "Open";
    const answer = answered
      ? only
        ? answerWords(only)
        : ""
      : items.length && !onUser
        ? turn
        : "";
    const group = this.#side && panel.getAttribute("group");
    const description = [
      group && `${group} group`,
      panel.getAttribute("summary"),
      changed === 1 ? "1 change" : changed ? `${changed} changes` : "",
      !items.length
        ? ""
        : !answered
          ? only
            ? turn
            : `${turn}, ${done.length} of ${items.length} answered`
          : only
            ? answer
              ? `Answered: ${answer}`
              : "Answered"
            : `All ${items.length} answered`,
    ]
      .filter(Boolean)
      .join(". ");
    const mark = html`<span class="lf-tab-mark" aria-hidden="true"></span>`;
    return html`<span
      ${selectableOffered("tab", "lf-tab-btn")}
      ${ref((button) => {
        if (button instanceof HTMLElement) this.#buttons.set(panel, button);
      })}
      aria-controls=${panel.id}
      aria-label=${panel.getAttribute("label")}
      aria-selected=${panel === this.#active.value}
      aria-description=${description || nothing}
      tabindex=${panel === this.#active.value ? 0 : -1}
      @click=${(/** @type {MouseEvent} */ event) =>
        this.#activate(panel, "ordinary", !pressIsKeyboardActivation(event))}
      ><span class="lf-tab-name" ${generated({ says: true })}
        >${panel.getAttribute("label")}${this.#down ? nothing : mark}</span
      >${
        this.#down && panel.hasAttribute("summary")
          ? html`<span class="lf-tab-summary" ${generated({ says: true })}
              >${panel.getAttribute("summary")}</span
            >`
          : nothing
      }${
        hasAnswer
          ? html`<span
              class="lf-tab-answer"
              aria-hidden="true"
              data-lf-obligations=${
                answered ? "answered" : items.length ? "open" : nothing
              }
              ><span class="lf-tab-answer-words">${answer}</span></span
            >`
          : nothing
      }<span class="lf-tabdiff lf-chip lf-change-count" aria-hidden="true"
        >${changed ? `Δ${changed}` : ""}</span
      >${this.#down ? mark : nothing}</span
    >`;
  }

  /** @param {Element | null} active @param {"ordinary" | "reveal" | "history" | "arrival"} reason @param {boolean} [pointer] */
  #activate(active, reason, pointer = false) {
    const activeButton = active ? this.#buttons.get(active) : undefined;
    if (!active || !activeButton) return;
    // The open tab pressed again, or walked to, is the user's way back to it after
    // scrolling the row away.
    if (active === this.#active.value) {
      this.#showTab(this.#buttons.get(active));
      return;
    }
    const previous = this.#active.value;
    const order = [...this.#buttons.keys()];
    const travels =
      pointer &&
      previous &&
      Math.abs(order.indexOf(active) - order.indexOf(previous)) === 1 &&
      getComputedStyle(this.#strip).flexDirection === "row";
    // CSS carries one retained line between the selected marks. Keeping the
    // transition enabled lets a reversed choice continue from its painted place.
    keeps(this.#strip, "data-lf-selection-travel", travels ? "" : null);
    // A press or a traversal between views switches them; a reveal is travel to
    // something inside the view, which the traveller lands.
    const switched = this.#pageFlow && ["ordinary", "history"].includes(reason);
    const pinnedBox =
      previous &&
      !this.#pageFlow &&
      !this.#side &&
      reason === "ordinary" &&
      this.getBoundingClientRect().top < this.#strip.getBoundingClientRect().top - 1;
    const change = () => {
      const from = pageScroller.scrollTop;
      if (this.#pageFlow && previous) this.#leave(previous);
      if (this.#root && reason === "ordinary") this.#pushLocation(active);
      // Whatever opened another view, the entry the user is on names it, so
      // Back and Forward to that entry return to this view. A fragment already
      // inside it (a link's target) says so and stays.
      else if (
        this.#root &&
        reason === "reveal" &&
        this.#panelForLocation([active]) !== active
      )
        replaceEntry(this.#locationFor(active));
      keepView(this, active);
      for (const panel of this.#panels) {
        // A tabpanel of prose has no focusable content, so Tab reaches the open
        // panel itself. hidden="until-found" skips only what a panel holds, not
        // the panel. A scrolling panel also takes a native browser stop without
        // tabindex, so explicitly exclude closed panels from the tab order.
        keeps(panel, "tabindex", panel === active ? 0 : -1);
      }
      this.#active.value = active;
      // Selection changes in this task. Lit's scheduled update then
      // keeps its dependency subscription current without replacing any nodes.
      render(this.render(), this.#strip);
      const button = activeButton;
      this.#showTab(button);
      this.#revealMotion?.cancel();
      this.#revealMotion = null;
      // A destination walk can change tabs without touching the strip. Give its
      // selected name one quiet highlight; focus stays on the destination, and
      // motion's shared gate answers reduced motion and initial presentation.
      if (previous && reason === "reveal") {
        const name = button.querySelector(":scope > .lf-tab-name");
        if (name) this.#revealMotion = backgroundFlash(name, flashDuration());
      }
      if (switched) this.#open(active, from);
      else if (pinnedBox) scrollIntoReadingBand(this, this, "start", "instant");

      for (const panel of previous ? [previous, active] : [active]) {
        const child = soleSubstantiveElement(panel);
        if (child) layoutChanged(child);
      }
      layoutChanged(this);
    };
    return this.#pageFlow && previous ? preserveReadingRegions(this, change) : change();
  }

  // The panel holding what the fragment names, read as Leaf's own arrival reads it, so
  // the traversal and the landing agree on an id inside a widget's shadow tree.
  /** @param {readonly Element[]} panels @param {string} [hash] */
  #panelForLocation(panels, hash = location.hash) {
    if (!this.#root) return null;
    const target = fragmentTarget(hash);
    return target ? (panels.find((panel) => under(target, panel)) ?? null) : null;
  }

  #syncRootContext() {
    const wasFlow = this.#pageFlow;
    // The first tab set directly in the page is its navigation, whatever else the page
    // holds beside it; a later one is a tabbed section like any nested set. A page's
    // parts are its navigation where the page lays them out, in a `main` that is no
    // Layout's box (layouts.css, `--lf-layout-box`), as the theme and content-layout
    // read it; in any other `main` they stand as if placed anywhere else.
    const main = this.parentElement;
    this.#root =
      !!main &&
      main.matches("body > main") &&
      (this.#parts
        ? getComputedStyle(main).getPropertyValue("--lf-layout-box").trim() !== "1"
        : main.querySelector(":scope > lf-tabs") === this);
    this.#pageFlow = this.#parts
      ? this.#root
      : getComputedStyle(this).getPropertyValue("--lf-views-flow").trim() === "page";
    this.#declareHeader();
    // A set that changed flow drew its open panel at another width.
    if (wasFlow !== this.#pageFlow && this.#active.value) {
      const child = soleSubstantiveElement(this.#active.value);
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

  // A page-flow strip sticks at the window's top over the whole document, so it is a
  // sticky header of the root: its border-box height joins the root landing inset
  // through registerRootHeader, and every landing arrives
  // below it. What the strip stands over inside its panels stacks through `--lf-top`
  // (the package theme). A set that stops being the page's strip withdraws it only
  // where no other set has become that strip. A page's list of parts is that header
  // only while it is a row over the open part, as on a phone; beside the part it covers
  // none of it. Which the list is follows the window, so the strip's size observer asks
  // again.
  #declareHeader() {
    const over =
      !this.#parts || Boolean(this.#active.value && this.#listOver(this.#active.value));
    const header = this.#pageFlow && over && Boolean(this.#strip?.isConnected);
    if (header === Boolean(this.#stopHeader)) return;
    this.#stopHeader?.();
    this.#stopHeader = header ? registerRootHeader(this.#strip) : null;
  }

  // Whether a page's list of parts stands over the open part rather than beside it.
  /** @param {Element} panel */
  #listOver(panel) {
    const list = this.#strip.getBoundingClientRect();
    return list.right > panel.getBoundingClientRect().left + 1;
  }

  // A press at one edge of the strip, which pages the names that run past it (the
  // package theme shows it only while there is more that way). It takes no tab stop:
  // the tabs are the keyboard's route, and a focused tab brings itself into view.
  /** @param {"start" | "end"} to */
  #edge(to) {
    return html`<span class="lf-tabstrip-scroll" data-to=${to} aria-hidden="true"
      ><span
        @click=${() => {
          const strip = this.#strip;
          const ahead = getComputedStyle(strip).direction === "rtl" ? -1 : 1;
          setScroll(strip, {
            left:
              strip.scrollLeft +
              ahead * (to === "start" ? -0.8 : 0.8) * strip.clientWidth,
            behavior: scrollBehavior(),
          });
        }}
        >${actionTemplate(to === "start" ? "previous" : "next", "lf-tabstrip-scroll-icon")}</span
      ></span
    >`;
  }

  // A tab the row runs past is scrolled into the strip, and only the strip: a page
  // strip sticks, and scrolling the page to it would move the view being read. It
  // stops clear of the edge's press, which the strip states as its inline
  // `scroll-padding` (the package theme). A row runs past where it holds more names
  // than it shows. A side list's column runs past only where it scrolls on its own,
  // in a workspace that fills the window (base.css), and the tab comes into it the
  // same way, down the column.
  // Where the strip has room for it, the tab comes in with its run's label, so the
  // name of the group the user opened stays beside it. Down a column that room is
  // the landing's own (`fitsWhole`) and the run from heading to tab lands together.
  // Along a row the label sticks at the row's start as the run scrolls under it (the
  // package theme), so a range over the two measures where the label stands rather
  // than the run's length; the row's room is asked whether the label and the tab
  // can share it side by side, and the tab lands clear of the label's room through
  // the theme's `scroll-margin`, which this measures for it (`--lf-tab-group-size`):
  // the run's first tab brings the label in with it, standing in its own place, and
  // a later tab comes in beside the stuck label. Where they cannot share the row,
  // the tab lands whole and the label gives way (`data-lf-group-apart`).
  /** @param {HTMLElement | undefined} btn */
  #showTab(btn) {
    const strip = this.#strip;
    if (!btn) return;
    const run = btn.parentElement;
    if (!run) return;
    const label = run.querySelector(":scope > .lf-tab-group");
    if (label && getComputedStyle(strip).flexDirection === "row") {
      const inset = landingInsets(strip);
      const room = strip.clientWidth - inset.left - inset.right;
      const gap = Number.parseFloat(getComputedStyle(run).columnGap) || 0;
      const size = label.getBoundingClientRect().width;
      const apart = size + gap + btn.getBoundingClientRect().width > room;
      run.toggleAttribute("data-lf-group-apart", apart);
      const measured = layoutPx(size);
      if (run.style.getPropertyValue("--lf-tab-group-size") !== measured)
        run.style.setProperty("--lf-tab-group-size", measured);
      scrollIntoView(btn, { block: "nearest", within: strip });
      return;
    }
    const range = label && document.createRange();
    if (range && label) {
      range.setStartBefore(label);
      range.setEndAfter(btn);
    }
    scrollIntoView(range && fitsWhole(range) ? range : btn, {
      block: "nearest",
      within: strip,
    });
  }

  // The open tab stays in the row as the strip's width changes, and not only when a
  // tab opens: a narrowed window, a panel opening beside the page, or a side list's
  // column turning into a row would otherwise leave the open tab past the edge. It
  // follows the size delivery before the resized strip paints.
  #watchStrip() {
    const stripSize = sizeObserver(this.#positionStrip);
    stripSize.observe(this.#strip);
    return stripSize;
  }

  #positionStrip = () => {
    this.#stopSelectionMotion();
    this.#syncRegions();
    this.#declareHeader();
    this.#showTab(this.#currentButton());
  };

  #stopSelectionMotion = () => {
    keeps(this.#strip, "data-lf-selection-travel", null);
  };

  /** @param {AbortSignal} signal */
  #listenForHistory(signal) {
    // Back or Forward to an entry in another view switches to it, as a press does.
    // One within the open view is the browser's to restore (history.js).
    claimTraversals(
      (url) => {
        if (!this.#root) return null;
        const view = this.#panelForLocation([...this.#buttons.keys()], url.hash);
        return view && view !== this.#active.value
          ? async () => {
              const placesPage = this.#pageFlow;
              await this.#activate(view, "history");
              return placesPage;
            }
          : null;
      },
      { signal },
    );
  }

  /** @param {Element} panel */
  #locationFor(panel) {
    const url = new URL(location.href);
    url.hash = panel.id;
    return url;
  }

  /** @param {Element | null} panel */
  #replaceLocation(panel) {
    if (!panel || location.hash) return;
    replaceEntry(this.#locationFor(panel));
  }

  /** @param {Element} panel */
  #pushLocation(panel) {
    if (location.hash === `#${panel.id}`) return;
    pushEntry(this.#locationFor(panel));
  }

  // A page-flow view starts where its strip sticks, so an offset short of that is the
  // shared header, not a place in the view. A part starts where it stands, less the
  // list where that sticks over it as a row.
  /** @param {Element} panel */
  #start(panel) {
    if (this.#parts) {
      const top = panel.getBoundingClientRect().top + pageScroller.scrollTop;
      if (!this.#listOver(panel)) return top;
      return (
        top - parseFloat(getComputedStyle(this.#strip).top) - this.#strip.offsetHeight
      );
    }
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
  /** @param {Element} panel */
  #leave(panel) {
    const read = pageScroller.scrollTop > this.#start(panel) + 0.5;
    tabStore.set(this.#placeKey(panel), read ? JSON.stringify(capturePlace()) : null);
  }

  // A view reopens at its place. One without keeps the header as the user has it,
  // clamped to the view's start so a stuck strip stays stuck.
  /** @param {Element} panel @param {number} from */
  #open(panel, from) {
    const start = this.#start(panel);
    let place = null;
    try {
      const stored = tabStore.get(this.#placeKey(panel));
      if (stored !== null) place = JSON.parse(stored);
    } catch {
      // An unreadable place is no place.
    }
    setScroll(pageScroller, {
      top: place ? start : Math.min(from, start),
      behavior: "instant",
    });
    if (place) restorePlace(place);
  }

  /** @param {Element} panel */
  #placeKey(panel) {
    return `${PLACE_KEY}${this.id}:${panel.id}`;
  }
}

customElements.define("lf-tabs", TabSet);
