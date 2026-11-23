/* lf-tabs: several views of one page, one panel on screen at a time.
 * Lit draws the generated strip from panel labels and tracked readings; authored
 * panels stay outside its render root. The upgrade hides
 * inactive panels with hidden="until-found", so browser find-in-page and
 * fragment navigation still reach them, and so does Leaf's travel to a comment
 * anchor, which reveals as they do: `beforematch` opens the owning tab. A page can
 * make a panel itself scroll with CSS, so the widget declares each panel as a scroll
 * surface; its CSS still decides
 * whether that panel scrolls. The open tab is view state for this user,
 * remembered per browser tab (`tabStore`): switching is reading, not editing, so it
 * never sends an action and no version carries it — this widget doesn't ride the
 * action channel at all. Which tab a set opens on is this module's (`#opening`): the
 * one holding what the address names, else the one this browser tab last had open, a
 * reload asking those two the other way round. Until the module runs, the package
 * theme shows the first panel (tabs.css, `:not(:defined)`).
 * The first tab set placed directly in main is the page's navigation over sections of
 * that page, whatever else main holds: its panel id is the URL fragment, and each
 * press adds a history entry naming its panel. A link inside a panel is still
 * fragment travel (history.js).
 *
 * The authored `flow="page"` puts the set in the document's flow (`flow`), and
 * the package styles its unframed face. This module reads that attribute for scrolling,
 * separately from primary URL/history ownership above. In document flow
 * ("page"), the strip sticks at the
 * window's top as a sticky header over the document it indexes, and its panels are sections of the
 * page, taking the page's width. Each is then a view with a place of its own: a switch
 * by press or key is not fragment travel, because a view is not a
 * destination, so the strip stays where it is on screen and the view opens at the
 * offset this user last left it at, or at its start when they never read past it.
 * Every other set is a
 * box ("box"): framed, its horizontal strip sticky within the set, each panel a bounded
 * box that what it holds measures itself against. A switch leaves the page where it
 * stands until the strip is pinned; then it opens the new panel at its start. `list="side"`
 * stands the list beside the panels, a queue beside the item it opens, walked up and
 * down as well as across (base.css says where it stacks); a side list is a box even as
 * the root set, which keeps the root's history. Its column sticks in the window beside the
 * item the page scrolls, and scrolls on its own past the window's height, so its list
 * is pinned as a box's strip is, and a switch made while it is opens the new item at
 * its start. Where a side list fills a height it is given, as a full-height
 * workspace's body (base.css), its list and its open item each scroll on their own.
 * Its panels are reading regions, and so is its list while it scrolls on its own, so
 * reading keys and the user's place follow the list or the item rather than the set.
 *
 * A page's parts (`lf-parts`, lf-parts.js) are this module's set under their own tag,
 * with `lf-part` members. They stand directly in a `main` that carries no Layout
 * (`page check` refuses one that carries one), and each part's child carries a Layout
 * of its own (layouts.css, "A page of parts"). They are the page's own flow: each part
 * has a place of its own,
 * and its id is the URL fragment, as a page tab's is. Their list runs down the window's
 * left edge, under the page's title, walked up and down as well as across, each row
 * drawn as a side list's is (below), with its part's `summary` and its obligations'
 * state under the name; the parts beside it start at the window's top, so the list is
 * no header over them. Where the window is too narrow for the column, as on a phone,
 * the list is a row of names sticking over the open part, a header as the page tabs'
 * row is. Parts placed anywhere else, as when the corpus embeds a page, are no page's
 * navigation, and list their names in a row.
 *
 * Travel into a hidden panel briefly highlights its selected name, without moving
 * focus from the destination or delaying it (tabs.css, `data-lf-revealed`). Reduced
 * motion keeps the selected state without the highlight.
 * Adjacent pointer choices along a horizontal strip move only the selection underline,
 * in a mark's time (`--lf-motion-mark`). Content and accessible selection change at
 * once; keyboard and vertical navigation stay immediate. A reversed choice continues
 * from the line's painted place, and scrolling or resizing the strip ends the cue at
 * its selected tab.
 * Every tab's accessible name is its label; what else the tab shows describes it. A
 * side list stands each run of neighbouring panels that share a `group` under a label
 * of that group, which each of their tabs' descriptions names. A side list's row adds
 * the panel's `summary` under the name, then its obligations' state on a reserved line. Counted
 * as an `lf-tally` counts them (`tally`), by the server's next actor: while one waits on the
 * user, the row ends its name's line with On Me's symbol (`on-me`), the panel's mark for what
 * waits on them, and the reserved line stays empty (its description says "To answer"). The
 * symbol's room is kept in every state, as the line's is, so a long name wraps the same
 * whatever its answer. A lone
 * open mark on that line read as an empty list bullet; Leaf's dot already means an unread
 * reply, and a mark before the name read as a bullet too. While one is open and none waits on
 * the user, the line shows an open mark and whose turn it is: "On Claude" (`agentName`) while
 * one is the agent's, as after the user comments on it, else "Open", as in a resolved thread.
 * Once every one is answered it shows a check, with the answer's own words where the panel
 * holds one obligation. So a queue shows each obligation's state and how far the user has
 * worked through it, and an undo that reopens an obligation puts On Me's symbol back. Which
 * obligations a panel holds is `obligationsByRegion` (obligations/place.js), read from the
 * admitted obligation inventory, so a tally of the queue counts the same obligations. A row
 * whose panel's markup asks the user something keeps the line's room either way
 * (`regionsAwaiting`), so an answer moves no row. While the version diff is on, each tab
 * counts the marked passages its panel holds, including inactive panels. Unupgraded,
 * panels stack as labeled sections; authored content is never replaced, so
 * there is no failSoft. */
import { html, nothing, render, repeat, ref } from "/vendor/lit.js";
import {
  addressableLabel,
  authoredTitle,
  actionTemplate,
  agentName,
  obligationsByRegion,
  regionsAwaiting,
  answerWords,
  tally,
  beginWalk,
  comparisonChanges,
  layoutChanged,
  registerReadingRegion,
  registerRootHeader,
  tabStore,
  landingInsets,
  LeafElement,
  commandsChanged,
} from "/runtime/widget-api.js";

// What this browser tab keeps: the open panel of each set, and for a view in the page's
// flow the offset the user left it at.
const OPEN_KEY = "lf-open:";
const PLACE_KEY = "lf-tabs-place:";
// The document's own scroller, which scrolls a page-flow set's views.
const pageScroller = /** @type {Element} */ (document.scrollingElement);
const stillness = matchMedia("(prefers-reduced-motion: reduce)");
/** @param {string} length */
const px = (length) => Number.parseFloat(length) || 0;
// The page element a URL fragment names.
/** @param {string} hash */
const named = (hash) => {
  try {
    return hash.length > 1
      ? document.getElementById(decodeURIComponent(hash.slice(1)))
      : null;
  } catch {
    return null;
  }
};
// Scrolls `box` along one axis, and no box around it, by the least that shows `rect`
// clear of the box's scroll padding and `target`'s scroll margin: what `scrollIntoView`
// does with `container: "nearest"`, which Firefox ignores, scrolling the page too.
/** @param {Element} box @param {"x" | "y"} axis @param {Element} target @param {DOMRect} rect */
const showWithin = (box, axis, target, rect) => {
  const port = box.getBoundingClientRect();
  const padding = getComputedStyle(box);
  const margin = getComputedStyle(target);
  const [start, end, from, to] =
    axis === "x"
      ? [
          rect.left - px(margin.scrollMarginLeft),
          rect.right + px(margin.scrollMarginRight),
          port.left + box.clientLeft + px(padding.scrollPaddingLeft),
          port.left + box.clientLeft + box.clientWidth - px(padding.scrollPaddingRight),
        ]
      : [
          rect.top - px(margin.scrollMarginTop),
          rect.bottom + px(margin.scrollMarginBottom),
          port.top + box.clientTop + px(padding.scrollPaddingTop),
          port.top + box.clientTop + box.clientHeight - px(padding.scrollPaddingBottom),
        ];
  const by =
    start < from ? start - from : end > to ? Math.min(end - to, start - from) : 0;
  // A row of right-to-left names scrolls from zero down to minus its range.
  const range =
    axis === "x"
      ? box.scrollWidth - box.clientWidth
      : box.scrollHeight - box.clientHeight;
  const low = axis === "x" && box.matches(":dir(rtl)") ? -range : 0;
  const at = axis === "x" ? box.scrollLeft : box.scrollTop;
  const next = Math.min(low + range, Math.max(low, at + by));
  if (Math.abs(next - at) >= 0.5)
    box.scrollTo({ [axis === "x" ? "left" : "top"]: next, behavior: "instant" });
};
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
// A member's face: markup its list shows in place of its `label` and `summary`, where
// text can't say it, such as a file's name in code type over a coloured diffstat. It
// opens the member as a <template>, which the page doesn't show, and the list shows one
// copy of it per template. `label` stays the member's name: the tab's accessible name,
// and every place that takes only text.
/** @type {WeakMap<HTMLTemplateElement, HTMLElement>} */
const faces = new WeakMap();
/** @param {Element} panel @returns {HTMLElement | null} */
const face = (panel) => {
  const template = panel.firstElementChild;
  if (!(template instanceof HTMLTemplateElement)) return null;
  let shown = faces.get(template);
  if (!shown) {
    shown = document.createElement("span");
    shown.className = "lf-tab-face";
    shown.append(template.content.cloneNode(true));
    faces.set(template, shown);
  }
  return shown;
};

export class TabSet extends LeafElement {
  static lfPatch = "members";
  // Whether the set is a page's parts (lf-parts.js).
  get parts() {
    return false;
  }
  #parts = this.parts;
  /** @type {Map<Element, HTMLElement>} */
  #buttons = new Map(); // panel → its strip button
  /** @type {Element[]} */
  #panels = [];
  /** @type {{panel: Element, group: string | null, panels: Element[]}[]} */
  #runs = [];
  #down = false;
  /** @type {Element | null} */
  #active = null;
  #root = false;
  /** @type {(MutationObserver) | null} */
  #contextObserver = null;
  #strip = document.createElement("div");
  /** @type {(() => void) | null} */
  #stopHeader = null;
  #side = false;
  #pageFlow = false;
  /** @type {Element | null} */
  #revealed = null;
  /** @type {(() => void) | null} */
  #stopList = null;
  // The listeners, observers and regions the set keeps while it stands in the page.
  /** @type {AbortController | null} */
  #standing = null;

  createRenderRoot() {
    return this.#strip ?? this;
  }

  setup() {
    const member = this.#parts ? "lf-part" : "lf-tab";
    const panels = [...this.children].filter((child) => child.localName === member);
    if (!panels.length) return;
    this.#panels = panels;
    const side = this.getAttribute("list") === "side";
    this.#side = side;
    this.#watchRootContext();
    this.#syncRootContext();
    // A side list and a page's list of parts both run down beside their panels; parts
    // placed anywhere else list their names in a row (the package theme). The set wears
    // `data-lf-down` while its list runs down, and the theme draws a row's summary and
    // state lines from that mark alone (tabs.css).
    const down = side || (this.#parts && this.#root);
    this.#down = down;
    this.toggleAttribute("data-lf-down", down);
    // A tab is a span wearing the role rather than a <button>, so its name stays text
    // the user can select in every engine: WebKit starts no selection inside a button.
    const strip = this.#strip;
    strip.className = "lf-tabstrip lf-ui lf-ui-face";
    strip.setAttribute("role", "tablist");
    strip.toggleAttribute("data-lf-scroll", true);
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
      panel.toggleAttribute("data-lf-scroll", true);
      panel.setAttribute("role", "tabpanel");
      panel.setAttribute("aria-label", panel.getAttribute("label") ?? "");
      // The browser found something inside (find-in-page, an anchor jump), or
      // Leaf is about to scroll a comment anchor into view: open up.
      panel.addEventListener("beforematch", () => this.#activate(panel, "reveal"));
    }
    // Build the strip before opening its panel: activation measures the selected
    // name and the underline in this same task. Later publication uses LeafElement's
    // tracked render; its unchanged Lit parts retain these exact nodes.
    render(this.render(), strip);
    // Roving focus per the ARIA tabs pattern: arrows move and activate, and come round
    // at the ends. The strip takes no tab stop of its own, so focus inside it, which
    // is the whole of when this scope holds, is always one of these buttons.
    const tabs = () => [...this.#buttons.values()];
    const focused = () =>
      /** @type {Document | ShadowRoot} */ (this.getRootNode()).activeElement;
    const focusedTab = () => tabs().find((button) => button === focused());
    /** @param {HTMLElement | undefined} next */
    const walk = (next) => {
      if (!next) return;
      // Native focus scrolling would carry a stuck tab back to its place in flow and
      // move the view being left before the switch records it. So the tab comes into
      // the window after the switch (`#showTab`).
      next.focus({ preventScroll: true });
      next.click();
      queueMicrotask(() => this.#showTab(next, true));
      beginWalk(
        "tab",
        "Tab",
        () => {
          const all = tabs();
          const at = all.findIndex((button) => button === focused());
          return at < 0
            ? null
            : { target: all[at], position: at + 1, total: all.length, qualifier: "" };
        },
        { list: () => [tabs()[0], tabs().at(-1)] },
      );
    };
    // Across the row, back is the way the names run from.
    const [back, ahead] = this.matches(":dir(rtl)")
      ? ["ArrowRight", "ArrowLeft"]
      : ["ArrowLeft", "ArrowRight"];
    strip.lfCommands = {
      title: "On a tab",
      rows: [
        {
          id: "tab.activate",
          keys: ["Enter", " "],
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
            const all = tabs();
            const current = focusedTab();
            const at = current ? all.indexOf(current) : step > 0 ? -1 : all.length;
            walk(all[(at + step + all.length) % all.length]);
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
    // The set rings its open panel (surfaces.css, `.lf-ring-frame`).
    this.classList.add("lf-ring-frame");
    // Open the tab the address names, or this
    // user's last, whose id resolves in later versions because check forbids
    // dropping ids. It opens here, during upgrade, so the runtime's view restore
    // measures final geometry.
    this.#activate(this.#opening(), "arrival");
    if (this.#root) {
      this.#replaceLocation(this.#active);
    }
  }

  connectedCallback() {
    super.connectedCallback();
    if (!this.#active || this.#standing) return;
    const { signal } = (this.#standing = new AbortController());
    this.#watchRootContext();
    this.#syncRootContext();
    const stripSize = new ResizeObserver(this.#positionStrip);
    stripSize.observe(this.#strip);
    this.#strip.addEventListener("scroll", this.#stopSelectionMotion, { signal });
    const stopPanels = this.#side
      ? this.#panels.map((panel) =>
          registerReadingRegion({
            id: `lf-region:${this.id}:panel-${panel.id}`,
            host: panel,
            body: panel,
          }),
        )
      : [];
    this.#syncRegions();
    signal.addEventListener("abort", () => {
      for (const stop of stopPanels) stop();
      this.#stopList?.();
      this.#stopList = null;
      this.#stopSelectionMotion();
      stripSize.disconnect();
      this.#contextObserver?.disconnect();
      this.#contextObserver = null;
      this.#stopHeader?.();
      this.#stopHeader = null;
    });
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this.#standing?.abort();
    this.#standing = null;
  }

  // A move within the document (`moveBefore`) is neither a departure nor an arrival.
  connectedMoveCallback() {}

  // The panel a set opens on: the one holding what the address names, else the one
  // this browser tab last had open, else the first. A reload asks its memory first: the
  // address may still name a place in a panel the user has since left.
  #opening() {
    const reload =
      /** @type {PerformanceNavigationTiming | undefined} */ (
        performance.getEntriesByType("navigation")[0]
      )?.type === "reload";
    const saved = tabStore.get(OPEN_KEY + this.id);
    const targets = [
      named(location.hash),
      saved ? document.getElementById(saved) : null,
    ];
    if (reload) targets.reverse();
    for (const target of targets) {
      const panel = target && this.#panels.find((each) => each.contains(target));
      if (panel) return panel;
    }
    return this.#panels[0] ?? null;
  }

  // A side list's panels are reading regions whatever their posture, as panes are, so
  // the user's place in an item survives the workspace flowing and filling the window
  // again. Its list is one only while it scrolls on its own, which the theme declares
  // on it (`--lf-holds-height`): a column, sticking beside the item or filling the
  // height a full-height workspace gives it, or that workspace's stacked row. A row
  // over the item elsewhere keeps its open tab in view itself (`#showTab`), and
  // observed as a region there, its own scrolling as it turned into a row ended the
  // size observers' pass with notifications undelivered. Which it is follows the
  // window, so the strip's size observer asks again.
  #syncRegions() {
    if (!this.#side || !this.isConnected) return;
    const holds =
      getComputedStyle(this.#strip).getPropertyValue("--lf-holds-height").trim() ===
      "1";
    if (holds === Boolean(this.#stopList)) return;
    this.#stopList?.();
    this.#stopList = holds
      ? registerReadingRegion({
          id: `lf-region:${this.id}:list`,
          host: this.#strip,
          body: this.#strip,
        })
      : null;
  }

  // What each panel holds, said with its summary as the tab's description: the
  // version diff's marked passages, and in a list down beside the panels its obligations'
  // state, with the answer once they are all answered.
  render() {
    if (!this.#panels.length) return nothing;
    // Every panel's obligations in one pass, read once the first panel asks for them.
    /** @type {ReturnType<typeof obligationsByRegion> | undefined} */
    let byPanel;
    const held = (/** @type {Element} */ panel) =>
      (byPanel ??= obligationsByRegion(this.#panels)).get(panel) ?? [];
    // The panels whose markup asks the user something, whose rows keep the answer's room.
    const asking = this.#down ? regionsAwaiting(this.#panels) : new Set();
    return html`${this.#edge("start")}${
        this.#side
          ? repeat(
              this.#runs,
              (run) => run.panel,
              (run) =>
                html` <div class="lf-tab-run" role="none">
                  ${
                    run.group
                      ? html`<span class="lf-tab-group lf-rows-head" aria-hidden="true"
                          >${run.group}</span
                        >`
                      : nothing
                  }
                  ${repeat(
                    run.panels,
                    (panel) => panel,
                    (panel) => this.#tab(panel, held, asking),
                  )}
                </div>`,
            )
          : repeat(
              this.#panels,
              (panel) => panel,
              (panel) => this.#tab(panel, held, asking),
            )
      }${this.#edge("end")}<span class="lf-tab-selection" aria-hidden="true"></span>`;
  }

  #currentButton() {
    return this.#active ? this.#buttons.get(this.#active) : undefined;
  }

  /** @param {Element} panel @param {(panel: Element) => NonNullable<ReturnType<ReturnType<typeof obligationsByRegion>["get"]>>} held @param {ReadonlySet<Node>} asking */
  #tab(panel, held, asking) {
    const changed = comparisonChanges(panel).length;
    const hasAnswer = asking.has(panel);
    const items = hasAnswer ? held(panel) : [];
    // Counted as an `lf-tally` of the panel would count them (`tally`). Withdrawn items
    // are already left out, so every item that isn't open is answered.
    const { onUser, onAgent, open, total } = tally(items);
    const answered = total > 0 && open === 0;
    const only = total === 1 ? items[0] : null;
    const turn = onUser ? "To answer" : onAgent ? `On ${agentName()}` : "Open";
    const answer = answered
      ? only
        ? answerWords(only)
        : ""
      : total && !onUser
        ? turn
        : "";
    const group = this.#side && panel.getAttribute("group");
    const description = [
      group && `${group} group`,
      panel.getAttribute("summary"),
      changed === 1 ? "1 change" : changed ? `${changed} changes` : "",
      !total
        ? ""
        : !answered
          ? only
            ? turn
            : `${turn}, ${total - open} of ${total} answered`
          : only
            ? answer
              ? `Answered: ${answer}`
              : "Answered"
            : `All ${total} answered`,
    ]
      .filter(Boolean)
      .join(". ");
    const mark = html`<span class="lf-tab-mark" aria-hidden="true"></span>`;
    return html`<span
      class="lf-tab-btn lf-ui lf-ui-face"
      role="tab"
      ${ref((button) => {
        if (button instanceof HTMLElement) this.#buttons.set(panel, button);
      })}
      aria-controls=${panel.id}
      aria-label=${panel.getAttribute("label")}
      aria-selected=${panel === this.#active}
      aria-description=${description || nothing}
      tabindex=${panel === this.#active ? 0 : -1}
      @click=${(/** @type {MouseEvent} */ event) =>
        this.#activate(panel, "ordinary", event.detail > 0)}
      ><span class="lf-tab-name"
        >${face(panel) ?? panel.getAttribute("label")}${this.#down ? nothing : mark}</span
      >${
        this.#down && !face(panel) && panel.hasAttribute("summary")
          ? html`<span class="lf-tab-summary">${panel.getAttribute("summary")}</span>`
          : nothing
      }${
        hasAnswer
          ? html`<span
              class="lf-tab-answer"
              aria-hidden="true"
              data-lf-obligations=${answered ? "answered" : answer ? "open" : nothing}
              ><span class="lf-tab-answer-words">${answer}</span></span
            >`
          : nothing
      }<span class="lf-tabdiff lf-chip lf-change-count" aria-hidden="true"
        >${changed ? `Δ${changed}` : ""}</span
      >${
        hasAnswer
          ? html`<span
              class="lf-tab-on-me"
              aria-hidden="true"
              ?data-lf-waiting=${onUser > 0}
              >${actionTemplate("on-me")}</span
            >`
          : nothing
      }${this.#down ? mark : nothing}</span
    >`;
  }

  /** @param {Element | null} active @param {"ordinary" | "reveal" | "arrival"} reason @param {boolean} [pointer] */
  #activate(active, reason, pointer = false) {
    const activeButton = active ? this.#buttons.get(active) : undefined;
    if (!active || !activeButton) return;
    // The open tab pressed again, or walked to, is the user's way back to it after
    // scrolling the row away.
    if (active === this.#active) {
      this.#showTab(this.#buttons.get(active));
      return;
    }
    const previous = this.#active;
    const order = [...this.#buttons.keys()];
    const travels =
      pointer &&
      previous !== null &&
      Math.abs(order.indexOf(active) - order.indexOf(previous)) === 1 &&
      getComputedStyle(this.#strip).flexDirection === "row";
    // CSS carries one retained line between the selected marks. Keeping the
    // transition enabled lets a reversed choice continue from its painted place.
    this.#strip.toggleAttribute("data-lf-selection-travel", travels);
    // A press switches views; a reveal is travel to something inside the view, which
    // the traveller lands.
    const switched = this.#pageFlow && reason === "ordinary";
    const pinnedBox =
      previous &&
      !this.#pageFlow &&
      reason === "ordinary" &&
      this.getBoundingClientRect().top < this.#strip.getBoundingClientRect().top - 1;
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
      history.replaceState(history.state, "", this.#locationFor(active));
    // hidden="until-found" keeps a closed panel within reach of find-in-page and of
    // a fragment, either of which opens it (`beforematch`, above).
    for (const panel of previous ? [previous, active] : this.#panels) {
      if (panel === active) panel.removeAttribute("hidden");
      else if (panel.getAttribute("hidden") !== "until-found")
        panel.setAttribute("hidden", "until-found");
      // A tabpanel of prose has no focusable content, so Tab reaches the open
      // panel itself. hidden="until-found" skips only what a panel holds, not
      // the panel. A scrolling panel also takes a native browser stop without
      // tabindex, so explicitly exclude closed panels from the tab order.
      panel.setAttribute("tabindex", panel === active ? "0" : "-1");
    }
    tabStore.set(OPEN_KEY + this.id, active.id || null);
    this.#active = active;
    render(this.render(), this.#strip);
    commandsChanged(this.#strip);
    this.#showTab(activeButton);
    // A destination walk can change tabs without touching the strip. Give its
    // selected name one quiet highlight; focus stays on the destination.
    this.#revealed?.removeAttribute("data-lf-revealed");
    this.#revealed =
      previous && reason === "reveal"
        ? activeButton.querySelector(":scope > .lf-tab-name")
        : null;
    this.#revealed?.setAttribute("data-lf-revealed", "");
    if (switched) this.#open(active, from);
    else if (pinnedBox) this.scrollIntoView({ block: "start", behavior: "instant" });

    for (const panel of previous ? [previous, active] : [active]) {
      const child = soleSubstantiveElement(panel);
      if (child) layoutChanged(child);
    }
    layoutChanged(this);
  }

  // The panel holding what the fragment names.
  /** @param {readonly Element[]} panels @param {string} [hash] */
  #panelForLocation(panels, hash = location.hash) {
    if (!this.#root) return null;
    const target = named(hash);
    return target ? (panels.find((panel) => panel.contains(target)) ?? null) : null;
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
    this.#pageFlow = this.#parts ? this.#root : this.getAttribute("flow") === "page";
    // The strip is named as the chrome names the set (`addressableLabel`): its author's
    // `aria-label`, else the nearest element holding it that has a name, such as its
    // section. The page's navigation stands in no section, and the page's `<title>`
    // names it: `main` has no name of its own, so its label would be its words run
    // together.
    const label = addressableLabel(this) || (this.#root ? authoredTitle() : "");
    if (!label) this.#strip.removeAttribute("aria-label");
    else if (this.#strip.getAttribute("aria-label") !== label)
      this.#strip.setAttribute("aria-label", label);
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
    const over = !this.#parts || Boolean(this.#active && this.#listOver(this.#active));
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
    return html`<span class="lf-tabstrip-scroll" data-lf-to=${to} aria-hidden="true"
      ><span
        @click=${() => {
          const strip = this.#strip;
          const ahead = strip.matches(":dir(rtl)") ? -1 : 1;
          strip.scrollBy({
            left: ahead * (to === "start" ? -0.8 : 0.8) * strip.clientWidth,
            behavior: stillness.matches ? "instant" : "smooth",
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
  // than it shows. A side list's column runs past where it scrolls on its own, as it
  // does wherever it is a column (the package theme), and the tab comes into it the
  // same way, down the column. Until the column sticks it stands where the page put
  // it, and can reach past the window's foot, so the walk, which puts focus on the
  // tab, shows it in the window too (`inWindow`). A stuck strip's tab already
  // shows there.
  // Where the strip has room for it, the tab comes in with its run's label, so the
  // name of the group the user opened stays beside it. Down a column the run from
  // heading to tab lands together where the column's room holds both.
  // Along a row the label sticks at the row's start as the run scrolls under it (the
  // package theme), so the row's room is asked whether the label and the tab
  // can share it side by side, and the tab lands clear of the label's room through
  // the theme's `scroll-margin`, which this measures for it (`--lf-tab-group-size`):
  // the run's first tab brings the label in with it, standing in its own place, and
  // a later tab comes in beside the stuck label. Where they cannot share the row,
  // the tab lands whole and the label gives way (`data-lf-group-apart`).
  /** @param {HTMLElement | undefined} btn @param {boolean} [inWindow] */
  #showTab(btn, inWindow = false) {
    const strip = this.#strip;
    if (!btn) return;
    const run = btn.parentElement;
    if (!run) return;
    const label = run.querySelector(":scope > .lf-tab-group");
    const row = getComputedStyle(strip).flexDirection === "row";
    let rect = btn.getBoundingClientRect();
    if (label && row) {
      const inset = landingInsets(strip);
      const room = strip.clientWidth - inset.left - inset.right;
      const gap = Number.parseFloat(getComputedStyle(run).columnGap) || 0;
      const size = label.getBoundingClientRect().width;
      run.toggleAttribute("data-lf-group-apart", size + gap + rect.width > room);
      run.style.setProperty("--lf-tab-group-size", `${Math.round(size * 64) / 64}px`);
    } else if (label) {
      const inset = landingInsets(strip);
      const top = label.getBoundingClientRect().top;
      if (rect.bottom - top <= strip.clientHeight - inset.top - inset.bottom)
        rect = new DOMRect(rect.left, top, rect.width, rect.bottom - top);
    }
    showWithin(strip, row ? "x" : "y", btn, rect);
    if (inWindow) btn.scrollIntoView({ block: "nearest", inline: "nearest" });
  }

  // The tablist says which way its names run, the way the theme lays them
  // (`--lf-tabstrip-flow`): down a column, and across the row a narrow window stacks a
  // side list or a page's parts into, as every other strip runs (the tablist default).
  // The open tab stays in the row as the strip's width changes, and not only when a
  // tab opens: a narrowed window, a panel opening beside the page, or a side list's
  // column turning into a row would otherwise leave the open tab past the edge.
  #positionStrip = () => {
    const column = getComputedStyle(this.#strip).flexDirection === "column";
    if (column !== this.#strip.hasAttribute("aria-orientation")) {
      if (column) this.#strip.setAttribute("aria-orientation", "vertical");
      else this.#strip.removeAttribute("aria-orientation");
    }
    this.#stopSelectionMotion();
    this.#syncRegions();
    this.#declareHeader();
    this.#showTab(this.#currentButton());
  };

  #stopSelectionMotion = () => {
    this.#strip.removeAttribute("data-lf-selection-travel");
  };

  /** @param {Element} panel */
  #locationFor(panel) {
    const url = new URL(location.href);
    url.hash = panel.id;
    return url;
  }

  /** @param {Element | null} panel */
  #replaceLocation(panel) {
    if (!panel || location.hash) return;
    history.replaceState(history.state, "", this.#locationFor(panel));
  }

  /** @param {Element} panel */
  #pushLocation(panel) {
    if (location.hash === `#${panel.id}`) return;
    history.pushState(null, "", this.#locationFor(panel));
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

  // A view the user read past its start keeps the offset they left it at, per browser
  // tab like the open tab itself, so a reload still returns each view to it. A view
  // left at its start keeps none.
  /** @param {Element} panel */
  #leave(panel) {
    const offset = pageScroller.scrollTop - this.#start(panel);
    tabStore.set(this.#placeKey(panel), offset > 0.5 ? String(offset) : null);
  }

  // A view reopens at its offset. One without keeps the header as the user has it,
  // clamped to the view's start so a stuck strip stays stuck.
  /** @param {Element} panel @param {number} from */
  #open(panel, from) {
    const start = this.#start(panel);
    const offset = Number(tabStore.get(this.#placeKey(panel)));
    const top = offset > 0 ? start + offset : Math.min(from, start);
    // A page already there is left alone, so a scroll under way is not stopped.
    if (Math.abs(top - pageScroller.scrollTop) >= 1)
      pageScroller.scrollTo({ top, behavior: "instant" });
  }

  /** @param {Element} panel */
  #placeKey(panel) {
    return `${PLACE_KEY}${this.id}:${panel.id}`;
  }
}

customElements.define("lf-tabs", TabSet);
