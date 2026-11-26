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
 * which selects the member before its first paint (`views`).
 * The first tab set placed directly in main is the page's navigation over sections of
 * that page, whatever else main holds, and says so on itself (`data-lf-page-views`).
 * Leaf then names the open panel in the address by its id, adds a history entry for
 * each switch the user makes, and shows an entry's panel again on Back and Forward
 * (the runtime's records/views.js). A link inside a panel is still fragment travel
 * (records/history.js).
 *
 * The authored `flow="page"` puts the set in the document's flow (`flow`), and
 * the package styles its unframed face, separately from the address above. In
 * document flow ("page"), the strip sticks at the
 * window's top as a sticky header over the document it indexes, and its panels are sections of the
 * page, taking the page's width. Each is then a view with a place of its own, which
 * Leaf keeps: a switch by press or key is not fragment travel, because a view is not a
 * destination, so the strip stays where it is on screen and the view opens where this
 * user last read it, or at its start when they never read past it; Back and Forward
 * return to where the user was on the entry. Every other set is a
 * box ("box"): framed, its horizontal strip sticky within the set, each panel a bounded
 * box that what it holds measures itself against. A switch leaves the page where it
 * stands until the strip is pinned; then it opens the new panel at its start. `list="side"`
 * stands the list beside the panels, a queue beside the item it opens, walked up and
 * down as well as across (base.css says where it stacks); a side list is a box even as
 * the root set, which keeps the root's address. Its column sticks in the window beside the
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
 * Travel into a hidden panel, as Back or Forward to one, briefly highlights its
 * selected name, without moving focus from the destination or delaying it. Reduced motion keeps the selected state
 * without the highlight; switching again or disconnecting cancels an unfinished cue.
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
 * obligations a panel holds is `readObligations(panel)`, read from the admitted obligation
 * inventory, so a tally of the queue counts the same obligations. A row whose panel's
 * markup asks the user something keeps the line's room either way (`asks`), so an answer
 * moves no row. While the version diff is on, each tab
 * counts the marked passages its panel holds, including inactive panels. Unupgraded,
 * panels stack as labeled sections; authored content is never replaced, so
 * there is no failSoft. */
import { html, nothing, render, repeat, ref } from "/vendor/lit.js";
import {
  nameOf,
  agentName,
  answerWords,
  backgroundFlash,
  comparisonChanges,
  keepView,
  whileConnected,
  openingView,
  viewMembers,
  readObligations,
  focusDestination,
  scrollIntoView,
  landingInsets,
} from "/runtime/widget-api.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { offer, selectableOffered } from "/runtime/lib/controls.js";
import { sizeObserver } from "/runtime/lib/frame-pass.js";
import { actionTemplate } from "/runtime/lib/icons.js";
import { PRESS, rowArrows } from "/runtime/lib/keys.js";
import { keeps, layoutPx } from "/runtime/lib/keeps.js";
import { tally } from "/runtime/lib/obligation-tally.js";

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
  /** @type {Map<Element, HTMLElement>} */
  #buttons = new Map(); // panel → its strip button
  /** @type {Element[]} */
  #panels = [];
  /** @type {{panel: Element, group: string | null, panels: Element[]}[]} */
  #runs = [];
  #down = false;
  // The open panel, which the strip's Enter row reads too.
  /** @type {Element | null} */
  #active = null;
  #root = false;
  /** @type {(MutationObserver) | null} */
  #contextObserver = null;
  #strip = offer("div", "lf-tabstrip");
  #side = false;
  #pageFlow = false;
  /** @type {(ReturnType<typeof backgroundFlash>) | null} */
  #revealMotion = null;

  createRenderRoot() {
    return this.#strip;
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
    // placed anywhere else list their names in a row (the package theme). The set wears
    // `data-lf-down` while its list runs down, and the theme draws a row's summary and
    // state lines from that mark alone (tabs.css).
    const down = side || (this.#parts && this.#root);
    this.#down = down;
    this.toggleAttribute("data-lf-down", down);
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
      // Every panel is a scroll surface, and a side list's is a reading region too
      // (`#syncListRegion`).
      keeps(panel, "data-lf-scroll", side ? "panel" : "");
      panel.setAttribute("role", "tabpanel");
      keeps(panel, "aria-label", panel.getAttribute("label"));
      // The browser found something inside (find-in-page, an anchor jump), or
      // Leaf is about to scroll a comment anchor into view: open up.
      panel.addEventListener("beforematch", () =>
        this.#activate(panel, { reveal: true }),
      );
    }
    // Build the strip before opening its panel: activation measures the selected
    // name and the underline in this same task. Later publication uses LeafElement's
    // tracked render; its unchanged Lit parts retain these exact nodes.
    render(this.render(), strip);
    // Roving focus per the ARIA tabs pattern: arrows move and activate, and come round
    // at the ends. The strip takes no tab stop of its own, so focus inside it, which is
    // the whole of when this scope holds, is always one of these buttons.
    const tabs = () => [...this.#buttons.values()];
    // The element focus is on, in the tree the strip stands in.
    const here = () =>
      /** @type {Document | ShadowRoot} */ (strip.getRootNode()).activeElement;
    const focusedTab = () => tabs().find((button) => button === here());
    /** @param {HTMLElement | undefined} next */
    const walk = (next) => {
      if (!next) return;
      // Native focus scrolling would carry a stuck tab back to its place in flow and
      // move the view being left before the switch records it. So the tab comes into
      // the window after the switch (`#showTab`), once the focus paint marks its ring,
      // as every walk's landing does (records/walk-position.js, `rowWalk`). The move queues that
      // paint for the end of this script, so a microtask queued after the move runs
      // behind it. Left out of sight, the tab would lose focus to the next key
      // (panel/page-keys/controller.js).
      focusDestination(next, "move");
      next.click();
      queueMicrotask(() => this.#showTab(next, null));
      const all = tabs();
      next.dispatchEvent(
        new CustomEvent("lf-walk", {
          bubbles: true,
          composed: true,
          detail: {
            noun: "Tab",
            position: all.indexOf(next) + 1,
            total: all.length,
            list: [all[0], all.at(-1)],
          },
        }),
      );
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
          when: () => here() !== this.#currentButton(),
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
            const at = all.findIndex((button) => button === focusedTab());
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
    this.prepend(strip);
    strip.dispatchEvent(
      new CustomEvent("lf-commands", { bubbles: true, composed: true }),
    );
    this.#declareHeader();
    this.classList.add("lf-rendered"); // the upgraded marker every widget uses
    // The set rings its open panel (surfaces.css, `.lf-ring-frame`).
    this.classList.add("lf-ring-frame");
    // Open the tab the address names, or this
    // user's last, whose id resolves in later versions because check forbids
    // dropping ids. It opens here, during upgrade, so the runtime's view restore
    // measures final geometry.
    this.#activate(openingView(this) ?? null);
    whileConnected(this, (signal) => {
      this.#watchRootContext();
      this.#syncRootContext();
      const stripSize = this.#watchStrip();
      strip.addEventListener("scroll", this.#stopSelectionMotion, { signal });
      this.#syncListRegion();
      return () => {
        this.#revealMotion?.cancel();
        this.#revealMotion = null;
        this.#stopSelectionMotion();
        stripSize.disconnect();
        this.#contextObserver?.disconnect();
        this.#contextObserver = null;
      };
    });
  }

  // A side list's panels are reading regions whatever their posture, as panes are
  // (`setup` marks them), so the user's place in an item survives the workspace flowing
  // and filling the window again. Its list is one only while it scrolls on its own,
  // which the theme declares on it (`--lf-holds-height`): a column, sticking beside the
  // item or filling the height a full-height workspace gives it, or that workspace's
  // stacked row. A row over the item elsewhere keeps its open tab in view itself
  // (`#showTab`), and observed as a region there, its own scrolling as it turned into a
  // row ended the size observers' pass with notifications undelivered. Which it is
  // follows the window, so the strip's size observer asks again.
  #syncListRegion() {
    if (!this.#side || !this.isConnected) return;
    const holds =
      getComputedStyle(this.#strip).getPropertyValue("--lf-holds-height").trim() ===
      "1";
    keeps(this.#strip, "data-lf-scroll", holds ? "list" : "");
  }

  // What each panel holds, said with its summary as the tab's description: the
  // version diff's marked passages, and in a list down beside the panels its obligations'
  // state, with the answer once they are all answered.
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
                          data-lf-gen="1"
                          data-lf-said
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
    const active = this.#active;
    return active ? this.#buttons.get(active) : undefined;
  }

  /** @param {Element} panel */
  #tab(panel) {
    const changed = comparisonChanges(panel).length;
    // A side list's row keeps the answer's room where its panel's markup asks the user
    // something.
    const held = this.#down ? readObligations(panel) : null;
    const hasAnswer = Boolean(held?.asks);
    const items = held?.asks ? held.all : [];
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
      ${selectableOffered("tab", "lf-tab-btn")}
      ${ref((button) => {
        if (button instanceof HTMLElement) this.#buttons.set(panel, button);
      })}
      aria-controls=${panel.id}
      aria-label=${panel.getAttribute("label")}
      aria-selected=${panel === this.#active}
      aria-description=${description || nothing}
      tabindex=${panel === this.#active ? 0 : -1}
      @click=${(/** @type {MouseEvent} */ event) =>
        this.#activate(panel, { pointer: event.detail !== 0 })}
      ><span class="lf-tab-name" data-lf-gen="1" data-lf-said
        >${face(panel) ?? panel.getAttribute("label")}${this.#down ? nothing : mark}</span
      >${
        this.#down && !face(panel) && panel.hasAttribute("summary")
          ? html`<span class="lf-tab-summary" data-lf-gen="1" data-lf-said
              >${panel.getAttribute("summary")}</span
            >`
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

  // Open a panel: the user's own switch, by `pointer` or key, or a `reveal`, which is
  // travel to something inside the panel, or Back and Forward, each landing the user
  // itself.
  /** @param {Element | null} active @param {{reveal?: boolean, pointer?: boolean}} [how] */
  #activate(active, { reveal = false, pointer = false } = {}) {
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
      previous &&
      Math.abs(order.indexOf(active) - order.indexOf(previous)) === 1 &&
      getComputedStyle(this.#strip).flexDirection === "row";
    // CSS carries one retained line between the selected marks. Keeping the
    // transition enabled lets a reversed choice continue from its painted place.
    keeps(this.#strip, "data-lf-selection-travel", travels ? "" : null);
    // A box's own switch made while its strip is pinned opens the panel at its start.
    const pinnedBox =
      previous &&
      !this.#pageFlow &&
      !reveal &&
      this.getBoundingClientRect().top < this.#strip.getBoundingClientRect().top - 1;
    // Leaf shows the panel, names it in the address where the set is the page's
    // navigation, and keeps the user's place in each view of a page-flow set.
    keepView(this, active);
    for (const panel of this.#panels) {
      // A tabpanel of prose has no focusable content, so Tab reaches the open
      // panel itself. hidden="until-found" skips only what a panel holds, not
      // the panel. A scrolling panel also takes a native browser stop without
      // tabindex, so explicitly exclude closed panels from the tab order.
      keeps(panel, "tabindex", panel === active ? 0 : -1);
    }
    this.#active = active;
    // Selection changes in this task. The update asked for then replaces no
    // node, and has Leaf read the strip's keys again.
    render(this.render(), this.#strip);
    this.requestUpdate();
    this.#showTab(activeButton);
    this.#revealMotion?.cancel();
    this.#revealMotion = null;
    // A destination walk can change tabs without touching the strip. Give its
    // selected name one quiet highlight; focus stays on the destination, and
    // motion's shared gate answers reduced motion and initial presentation.
    if (previous && reveal) {
      const name = activeButton.querySelector(":scope > .lf-tab-name");
      if (name) this.#revealMotion = backgroundFlash(name);
    }
    if (pinnedBox) scrollIntoView(this, { block: "start", behavior: "instant" });

    for (const panel of previous ? [previous, active] : [active]) {
      const child = soleSubstantiveElement(panel);
      if (child)
        child.dispatchEvent(
          new CustomEvent("lf-layout", { bubbles: true, composed: true }),
        );
    }
    this.dispatchEvent(new CustomEvent("lf-layout", { bubbles: true, composed: true }));
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
    // The page's navigation says so, and Leaf names its open panel in the address.
    keeps(this, "data-lf-page-views", this.#root ? "" : null);
    this.#pageFlow = this.#parts ? this.#root : this.getAttribute("flow") === "page";
    // The strip is named as the chrome names the set (`nameOf`): its author's
    // `aria-label`, else the nearest element holding it that has a name, such as its
    // section. The page's navigation stands in no section, and the page's `<title>`
    // names it: `main` has no name of its own, so its label would be its words run
    // together.
    keeps(
      this.#strip,
      "aria-label",
      nameOf(this) || (this.#root ? nameOf(document) : "") || null,
    );
    this.#declareHeader();
    // A set that changed flow drew its open panel at another width.
    if (wasFlow !== this.#pageFlow && this.#active) {
      const child = soleSubstantiveElement(this.#active);
      if (child)
        child.dispatchEvent(
          new CustomEvent("lf-layout", { bubbles: true, composed: true }),
        );
      this.dispatchEvent(
        new CustomEvent("lf-layout", { bubbles: true, composed: true }),
      );
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
  // through its `data-lf-root-header` mark, and every landing arrives
  // below it. What the strip stands over inside its panels stacks through `--lf-top`
  // (the package theme). A set that stops being the page's strip withdraws it only
  // where no other set has become that strip. A page's list of parts is that header
  // only while it is a row over the open part, as on a phone; beside the part it covers
  // none of it. Which the list is follows the window, so the strip's size observer asks
  // again.
  #declareHeader() {
    const over = !this.#parts || Boolean(this.#active && this.#listOver(this.#active));
    const header = this.#pageFlow && over && this.#strip.isConnected;
    this.#strip.toggleAttribute("data-lf-root-header", header);
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
          const ahead = getComputedStyle(strip).direction === "rtl" ? -1 : 1;
          strip.scrollBy({
            left: ahead * (to === "start" ? -0.8 : 0.8) * strip.clientWidth,
            behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
              ? "instant"
              : "smooth",
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
  // tab, shows it in the window too (`within` null). A stuck strip's tab already
  // shows there.
  // Where the strip has room for it, the tab comes in with its run's label, so the
  // name of the group the user opened stays beside it. Down a column that room is
  // the landing's own (`including`) and the run from heading to tab lands together.
  // Along a row the label sticks at the row's start as the run scrolls under it (the
  // package theme), so a range over the two measures where the label stands rather
  // than the run's length; the row's room is asked whether the label and the tab
  // can share it side by side, and the tab lands clear of the label's room through
  // the theme's `scroll-margin`, which this measures for it (`--lf-tab-group-size`):
  // the run's first tab brings the label in with it, standing in its own place, and
  // a later tab comes in beside the stuck label. Where they cannot share the row,
  // the tab lands whole and the label gives way (`data-lf-group-apart`).
  /** @param {HTMLElement | undefined} btn @param {Element | null} [within] */
  #showTab(btn, within = this.#strip) {
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
      run.style.setProperty("--lf-tab-group-size", layoutPx(size));
      scrollIntoView(btn, { block: "nearest", within });
      return;
    }
    const range = label && document.createRange();
    if (range) {
      range.setStartBefore(label);
      range.setEndAfter(btn);
    }
    scrollIntoView(btn, { including: range, block: "nearest", within });
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

  // The tablist says which way its names run, the way the theme lays them
  // (`--lf-tabstrip-flow`): down a column, and across the row a narrow window stacks a
  // side list or a page's parts into, as every other strip runs (the tablist default).
  #positionStrip = () => {
    keeps(
      this.#strip,
      "aria-orientation",
      getComputedStyle(this.#strip).flexDirection === "column" ? "vertical" : null,
    );
    this.#stopSelectionMotion();
    this.#syncListRegion();
    this.#declareHeader();
    this.#showTab(this.#currentButton());
  };

  #stopSelectionMotion = () => {
    keeps(this.#strip, "data-lf-selection-travel", null);
  };
}

customElements.define("lf-tabs", TabSet);
