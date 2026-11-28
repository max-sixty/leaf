// Compiled from lf-tabs.ts by build/typescript.mjs; edit that file.
/* lf-tabs: several views of one page, one panel on screen at a time.
 * The upgrade hides inactive panels with hidden="until-found", so browser find-in-page
 * and fragment navigation still reach them, and so does Leaf's travel to a comment
 * anchor, which reveals as they do: `beforematch` opens the owning tab. A page can
 * make a panel itself scroll with CSS, so the widget declares each panel as a scroll
 * surface; its CSS still decides
 * whether that panel scrolls. The open tab is view state for this user,
 * remembered per browser tab (`KeepView`): switching is reading, not editing, so it
 * never sends an action and no version carries it — this widget doesn't ride the
 * action channel at all. Which tab a set opens on is the runtime's (`openingView`),
 * which selects the member before its first paint (`views`).
 * The first tab set placed directly in main is the page's navigation over sections of
 * that page, whatever else main holds, and says so on itself (`data-lf-page-views`).
 * Leaf then names the open panel in the address by its id, adds a history entry for
 * each switch the user makes, and shows an entry's panel again on Back and Forward
 * (the runtime's records/views.js). A link inside a panel is still fragment travel
 * (records/history.js). Which set is first is read as the set draws; a set that a
 * revision puts before it in `main` takes the page's address once the page draws its
 * sets again, as on a reload.
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
 * A page's parts (`lf-parts`, lf-parts.ts) are this module's set under their own tag,
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
 * A tab's accessible name is the words it shows, in the order it shows them, so a
 * user who speaks what they see reaches it (WCAG 2.5.3, Label in Name): its label, a
 * side list's summary and answer line, and its change count. A tab that shows its
 * panel's face (`face`) is named by its `label`, since the face is markup the agent
 * writes for the eye and Leaf derives no name from it (the maintainer's choice). What
 * a tab shows only as a mark, its group, and the state its name leaves out describe
 * it, so a row whose answer line reads "Alpha" is described "Answered", and one whose
 * line reads the turn says no turn again. A
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
 * there is no failSoft.
 *
 * How it is drawn: a decorating widget (lf-options.js, "How it is drawn"), in a
 * shadow root rather than the light-DOM box `defineWidget` draws by default
 * (browser/AGENTS.md, "Renderers"). That box is appended after the authored panels,
 * and a tablist has to stand before them in the document's order, not only on screen:
 * Tab from above the set would reach the open panel's links before its tabs, a screen
 * reader would read every panel before the list that names them, and a page-flow set
 * lays its strip out in block flow, where no CSS `order` can lift it above its panels
 * to stick there. A shadow root puts the strip first and shows the panels through a
 * `<slot>` after it.
 *
 * - The panels are the author's, in the light DOM, and show through the root's
 *   `<slot>`. What the widget states on them is the tab pattern's record: `role`,
 *   `aria-label` from the panel's `label`, `tabindex`, `data-lf-scroll`, and the
 *   `hidden` Leaf keeps (`KeepView`). The host wears `data-lf-down` while its list runs
 *   down, and `data-lf-page-views` where it is the page's navigation.
 * - The strip is drawn by Effect UI in the set's shadow root, from what `inputs` reads
 *   of each panel: its `label`, `summary`, `group`, the face its `<template>` holds,
 *   the version diff's count and its obligations. The face is the template's markup
 *   cloned into the tab, so the theme's faces for markup dress it, and the page's own
 *   stylesheet, which stops at the root, doesn't. The theme restyles the strip through
 *   shadow parts (`strip`, `tab`, `name`); tabs-shadow.css holds what the strip's
 *   pieces take from each other and from the host's state.
 * - The component's Model is the tab the user is on and how they got there. One Mount
 *   on the strip (`Strip`) does what only the host's own code can: it shows the panel
 *   through Leaf (`KeepView`) as the Model moves, keeps the tab in view, declares the
 *   strip's keys, decorates the panels, and hears a panel the browser reveals
 *   (`beforematch`) as a message. */
import {
  Component,
  Effect,
  Equal,
  Html,
  Mount,
  Queue,
  Schema,
  Stream,
  UiSchema,
} from "/vendor/effect-ui.js";
import {
  agentName,
  answerWords,
  backgroundFlash,
  comparisonChanges,
  focusDestination,
  landingInsets,
  nameOf,
  openingView,
  readObligations,
  scrollIntoView,
  viewMembers,
} from "/runtime/widget-api.js";
import { defineWidget, widgetProps } from "/runtime/effect-widget.js";
import { KeepView } from "/runtime/widget-services.js";
import { offerAttributes, selectableAttributes } from "/runtime/lib/controls.js";
import { sizeObserver } from "/runtime/lib/frame-pass.js";
import { iconElement, actionIcon } from "/runtime/lib/icon-paths.js";
import { PRESS, rowArrows } from "/runtime/lib/keys.js";
import { keeps, layoutPx } from "/runtime/lib/keeps.js";
import { tally } from "/runtime/lib/obligation-tally.js";

/** What `inputs` reads of one panel. */
const Panel = Schema.Struct({
  panel: Schema.instanceOf(Element),
  id: Schema.String,
  label: Schema.String,
  summary: Schema.NullOr(Schema.String),
  group: Schema.NullOr(Schema.String),
  // The markup of the `<template>` the panel opens with, which its tab shows in place
  // of its label and summary.
  face: Schema.NullOr(Schema.String),
  changed: Schema.Number,
  // Whether the panel's markup asks the user something, and its obligations as
  // `tally` counts them, with the answer's words where it holds one.
  asks: Schema.Boolean,
  onUser: Schema.Number,
  onAgent: Schema.Number,
  open: Schema.Number,
  total: Schema.Number,
  only: Schema.NullOr(Schema.String),
});

const TabsProps = Schema.Struct({
  ...widgetProps,
  panels: Schema.Array(Panel),
  side: Schema.Boolean,
  parts: Schema.Boolean,
  root: Schema.Boolean,
  pageFlow: Schema.Boolean,
  name: Schema.String,
  agent: Schema.String,
  opening: Schema.NullOr(Schema.String),
});

// How the user reached the open tab: a press, a key, or the browser revealing its
// panel, as find-in-page, a fragment or Back does.
const Via = Schema.Literals(["pointer", "key", "reveal"]);

const TabsModel = Schema.Struct({
  active: Schema.NullOr(Schema.String),
  via: Schema.NullOr(Via),
  // Counts the user's switches, a press on the open tab included, which brings that
  // tab back into the strip after the user scrolled it away.
  step: Schema.Number,
  // Whether the open tab's line travels to it from the tab before, as it does for a
  // press on a neighbour, until the strip scrolls or resizes under it. It is drawn with
  // the selection it travels to, so the line starts from where it was painted.
  travels: Schema.Boolean,
});

export const TabsMessage = UiSchema.TaggedEnum({
  Chose: { id: Schema.String, pointer: Schema.Boolean },
  Revealed: { id: Schema.String },
  // The strip scrolled or resized, which ends a line's travel at its tab.
  Settled: {},
});

// Whether the list runs down beside the panels: a side list's, and a page's list of
// parts. Parts placed anywhere else list their names in a row.
const runsDown = (props) => props.side || (props.parts && props.root);

// The open panel: the user's, else the one the set opened on, else the first.
const activeId = (model, props) => {
  const ids = props.panels.map((panel) => panel.id);
  if (model.active !== null && ids.includes(model.active)) return model.active;
  if (props.opening !== null && ids.includes(props.opening)) return props.opening;
  return ids[0] ?? null;
};

// What a tab says beyond its name: the version diff's marked passages, and in a list
// down beside the panels its obligations' state, with the answer once they are all
// answered.
const tabWords = (panel, props) => {
  const down = runsDown(props);
  const { onUser, onAgent, open, total, only } = panel;
  const answered = total > 0 && open === 0;
  const turn = onUser ? "To answer" : onAgent ? `On ${props.agent}` : "Open";
  const answer = answered
    ? total === 1
      ? (only ?? "")
      : ""
    : total && !onUser
      ? turn
      : "";
  const group = props.side ? panel.group : null;
  const summarized = down && panel.face === null && panel.summary !== null;
  // The answer line's words are in the name unless a face's label names the tab, so
  // the description then adds only the state they leave out.
  const said = panel.face === null && Boolean(answer);
  const counted = `${total - open} of ${total} answered`;
  const description = [
    group && `${group} group`,
    summarized ? "" : panel.summary,
    panel.changed === 1 ? "1 change" : panel.changed ? `${panel.changed} changes` : "",
    !total
      ? ""
      : !answered
        ? total === 1
          ? said
            ? ""
            : turn
          : said
            ? counted
            : `${turn}, ${counted}`
        : total === 1
          ? answer && !said
            ? `Answered: ${answer}`
            : "Answered"
          : `All ${total} answered`,
  ]
    .filter(Boolean)
    .join(". ");
  return { down, answered, answer, summarized, description };
};

// Each run of neighbouring panels that share a `group`, which a side list heads with
// the group's label; every other list is one run.
const runsOf = (props) => {
  const runs = [];
  for (const panel of props.panels) {
    const run = runs.at(-1);
    if (!run || (props.side && panel.group !== run.group))
      runs.push({ group: panel.group, panels: [panel] });
    else run.panels.push(panel);
  }
  return runs;
};

export const Tabs = Html.component({
  name: "Tabs",
  props: TabsProps,
  model: TabsModel,
  message: TabsMessage,
}).make({
  init: () => ({ active: null, via: null, step: 0, travels: false }),
  update: {
    Chose: ($, { id, pointer }) => {
      const ids = $.props.panels.map((panel) => panel.id);
      const to = ids.indexOf(id);
      if (to < 0) return $.model;
      const from = ids.indexOf(activeId($.model, $.props));
      return $.evolve({
        active: id,
        via: pointer ? "pointer" : "key",
        step: $.model.step + 1,
        // Only a press on a neighbour moves the line; keys land at once.
        travels: pointer && Math.abs(to - from) === 1,
      });
    },
    // The runtime has shown the panel the browser revealed; the strip follows it.
    Revealed: ($, { id }) =>
      id === activeId($.model, $.props) ||
      !$.props.panels.some((panel) => panel.id === id)
        ? $.model
        : $.evolve({
            active: id,
            via: "reveal",
            step: $.model.step + 1,
            travels: false,
          }),
    Settled: ($) => ($.model.travels ? $.evolve({ travels: false }) : $.model),
  },
  view: (h, model) => {
    const props = h.props;
    const active = activeId(model, props);
    const down = runsDown(props);
    const tab = (panel) => {
      const { answered, answer, summarized, description } = tabWords(panel, props);
      const selected = panel.id === active;
      const mark = h.span.class("lf-tab-mark").attr("aria-hidden", "true");
      return (
        h.span
          .key(panel.id)
          .attrs(selectableAttributes("tab", "lf-tab-btn"))
          // Its key in the set's shadow tree, by which Leaf returns focus to it, as Back
          // does to the tab the user stood on (records/carry.js).
          .attr("data-lf-carry", `tab-${panel.id}`)
          .attr("part", selected ? "tab selected" : "tab")
          .attr("aria-label", panel.face === null ? undefined : panel.label)
          .attr("aria-selected", String(selected))
          .attr("aria-description", description || undefined)
          .attr("tabindex", selected ? "0" : "-1")
          .prop("ariaControlsElements", [panel.panel])
          // A click no pointer made is a key's: Enter, Space, or the walk's own press.
          .on("click", (press) =>
            TabsMessage.Chose({ id: panel.id, pointer: press.pointerType !== "" }),
          )
          .children(
            h.span
              .class("lf-tab-name")
              .attr("part", "name")
              .attr("data-lf-gen", "1")
              .attr("data-lf-said", "")
              .children(
                panel.face === null
                  ? panel.label
                  : h.span
                      .class("lf-tab-face")
                      .onMount(ShowFace({ markup: panel.face })),
                down ? null : mark,
              ),
            summarized
              ? h.span
                  .class("lf-tab-summary")
                  .attr("data-lf-gen", "1")
                  .attr("data-lf-said", "")
                  .children(panel.summary)
              : null,
            panel.asks
              ? h.span
                  .class("lf-tab-answer")
                  .attr(
                    "data-lf-obligations",
                    answered ? "answered" : answer ? "open" : undefined,
                  )
                  .children(h.span.class("lf-tab-answer-words").children(answer))
              : null,
            h.span
              .class("lf-tabdiff lf-chip lf-change-count")
              .children(panel.changed ? `Δ${panel.changed}` : ""),
            panel.asks
              ? h.span
                  .class("lf-tab-on-me")
                  .attr("aria-hidden", "true")
                  .attr("data-lf-waiting", panel.onUser > 0 ? "" : undefined)
                  .onMount(ShowIcon({ icon: actionIcon("on-me"), name: "" }))
              : null,
            down ? mark : null,
          )
      );
    };
    // A press at one edge of the strip, which pages the names that run past it (the
    // package theme shows it only while there is more that way). It takes no tab stop:
    // the tabs are the keyboard's route, and a focused tab brings itself into view.
    const edge = (to) =>
      h.span
        .class("lf-tabstrip-scroll")
        .attr("data-lf-to", to)
        .attr("aria-hidden", "true")
        .children(
          h.span.onMount(
            ShowIcon({
              icon: actionIcon(to === "start" ? "previous" : "next"),
              name: "lf-tabstrip-scroll-icon",
            }),
          ),
        );
    const tabs = props.side
      ? runsOf(props).map((run) =>
          h.div
            .key(`run:${run.panels[0]?.id}`)
            .class("lf-tab-run")
            .attr("role", "none")
            .children(
              run.group
                ? h.span
                    .class("lf-tab-group lf-rows-head")
                    .attr("aria-hidden", "true")
                    .attr("data-lf-gen", "1")
                    .attr("data-lf-said", "")
                    .children(run.group)
                : null,
              ...run.panels.map(tab),
            ),
        )
      : props.panels.map(tab);
    return h.div.style({ display: "contents" }).children(
      h.div
        .attrs(offerAttributes("div", "lf-tabstrip"))
        .attr("part", "strip")
        .attr("role", "tablist")
        .attr("data-lf-down", down ? "" : undefined)
        // CSS carries one retained line between the selected marks, along a row.
        .attr("data-lf-selection-travel", model.travels ? "" : undefined)
        .attr("aria-label", props.name || undefined)
        .onMount(
          Strip({
            active,
            step: model.step,
            via: model.via,
            travels: model.travels,
            down,
            pageFlow: props.pageFlow,
            parts: props.parts,
            root: props.root,
          }),
        )
        .children(
          edge("start"),
          ...tabs,
          edge("end"),
          h.span.class("lf-tab-selection").attr("aria-hidden", "true"),
        ),
      h.slot,
    );
  },
});

// A face's markup, drawn into its tab: the agent's words for the eye, as its template
// holds them.
const ShowFace = Mount.make(
  "ShowFace",
  { args: { markup: Schema.String } },
  (span, _args, changes) =>
    Stream.runForEach(changes, ({ markup }) =>
      Effect.sync(() => {
        const template = document.createElement("template");
        template.innerHTML = markup;
        span.replaceChildren(template.content);
      }),
    ).pipe(Effect.as(Component.noop)),
);

// One of Leaf's icons (icon-paths.js), drawn into its node.
const ShowIcon = Mount.make(
  "ShowIcon",
  { args: { icon: Schema.String, name: Schema.String } },
  (node, _args, changes) =>
    Stream.runForEach(changes, ({ icon, name }) =>
      Effect.sync(() => {
        node.replaceChildren(iconElement(icon, name));
      }),
    ).pipe(Effect.as(Component.noop)),
);

/** What the set does beside its drawing, kept by the strip's mount. */
class StripWork {
  args;
  host;
  // The panel the set last showed, which the next switch leaves.
  #shown = null;
  #step = -1;
  #flash = null;
  // What a switch read before its panel showed, for the rest of it.
  #landing = null;
  #size;
  #panels;

  strip;
  send;

  constructor(strip, args, send) {
    this.strip = strip;
    this.send = send;
    this.args = args;
    this.host = strip.getRootNode().host;
    this.#panels = viewMembers(this.host);
    for (const panel of this.#panels) {
      // Each panel's stop (`#switch`) stands before it is named a scroll surface, so
      // Leaf's reach reads it as the panel's own (dom/reach.js) and never takes it back.
      keeps(panel, "tabindex", panel.id === args.active ? 0 : -1);
      // Every panel is a scroll surface, and a side list's is a reading region too
      // (`#syncListRegion`).
      keeps(
        panel,
        "data-lf-scroll",
        this.host.getAttribute("list") === "side" ? "panel" : "",
      );
      keeps(panel, "role", "tabpanel");
      keeps(panel, "aria-label", panel.getAttribute("label"));
      // The browser found something inside (find-in-page, an anchor jump), or
      // Leaf is about to scroll a comment anchor into view: open up.
      panel.addEventListener("beforematch", this.#revealed);
    }
    keeps(strip, "data-lf-scroll", "");
    // The upgraded marker every widget uses, and the ring the set draws round its open
    // panel (surfaces.css, `.lf-ring-frame`). A set mounted again, as on its return to
    // the page, already wears them, and an unchanged write would tell Leaf it changed.
    for (const mark of ["lf-rendered", "lf-ring-frame"])
      if (!this.host.classList.contains(mark)) this.host.classList.add(mark);
    this.#size = sizeObserver(this.#positionStrip);
    this.#size.observe(strip);
    strip.addEventListener("scroll", this.#stopSelectionMotion);
    strip.addEventListener("click", this.#page);
    this.#declareKeys();
    this.#syncListRegion();
  }

  close() {
    for (const panel of this.#panels)
      panel.removeEventListener("beforematch", this.#revealed);
    this.strip.removeEventListener("scroll", this.#stopSelectionMotion);
    this.strip.removeEventListener("click", this.#page);
    this.#size.disconnect();
    this.#flash?.cancel();
    this.#flash = null;
  }

  // Take the newest args: the panel to show where they move the set to another one,
  // which the mount has Leaf show before the rest of the switch (`landed`).
  update(args) {
    this.args = args;
    const { host } = this;
    host.toggleAttribute("data-lf-down", args.down);
    // The page's navigation says so, and Leaf names its open panel in the address.
    keeps(host, "data-lf-page-views", args.root ? "" : null);
    const step = args.step !== this.#step;
    this.#step = args.step;
    const panel = step ? this.#switch() : null;
    if (!panel) this.#declareHeader();
    return panel;
  }

  #tabs() {
    return [...this.strip.querySelectorAll(".lf-tab-btn")];
  }

  #tabOf(panel) {
    return this.#tabs()[panel ? this.#panels.indexOf(panel) : -1];
  }

  // Open the panel the args name: the user's own switch, by press or key, or a reveal,
  // which is travel to something inside the panel, or Back and Forward, each landing
  // the user itself; on the first draw, the panel the set opened on. What it reads of
  // the page before the panel shows, it reads here; the rest waits for `landed`.
  #switch() {
    const { active, via, pageFlow } = this.args;
    const panel = this.#panels.find((each) => each.id === active) ?? null;
    const tab = this.#tabOf(panel);
    if (!panel || !tab) return null;
    const strip = this.strip;
    const previous = this.#shown;
    // The open tab pressed again, or walked to, is the user's way back to it after
    // scrolling the row away.
    if (panel === previous) {
      this.#showTab(tab);
      return null;
    }
    // A box's own switch made while its strip is pinned opens the panel at its start.
    const pinnedBox =
      previous !== null &&
      !pageFlow &&
      via !== "reveal" &&
      this.host.getBoundingClientRect().top < strip.getBoundingClientRect().top - 1;
    this.#landing = { previous, pinnedBox };
    this.#shown = panel;
    for (const each of this.#panels)
      // A tabpanel of prose has no focusable content, so Tab reaches the open
      // panel itself. hidden="until-found" skips only what a panel holds, not
      // the panel. A scrolling panel also takes a native browser stop without
      // tabindex, so explicitly exclude closed panels from the tab order.
      keeps(each, "tabindex", each === panel ? 0 : -1);
    return panel;
  }

  // The rest of a switch, once Leaf has shown the panel, named it in the address where
  // the set is the page's navigation, and kept the user's place in each view of a
  // page-flow set (`KeepView`).
  landed() {
    const panel = this.#shown;
    const tab = this.#tabOf(panel);
    const landing = this.#landing;
    this.#landing = null;
    if (!panel || !tab || !landing) return;
    const { previous, pinnedBox } = landing;
    const { via } = this.args;
    // A walk shows the tab in the window too, since focus is on it (`#declareKeys`).
    this.#showTab(tab, via === "key" ? null : this.strip);
    this.#flash?.cancel();
    this.#flash = null;
    // A destination walk can change tabs without touching the strip. Give its
    // selected name one quiet highlight; focus stays on the destination, and
    // motion's shared gate answers reduced motion and initial presentation.
    if (previous && via === "reveal") {
      const name = tab.querySelector(":scope > .lf-tab-name");
      if (name) this.#flash = backgroundFlash(name);
    }
    if (pinnedBox) scrollIntoView(this.host, { block: "start", behavior: "instant" });
    for (const each of previous ? [previous, panel] : [panel]) laidOut(each);
    this.host.dispatchEvent(
      new CustomEvent("lf-layout", { bubbles: true, composed: true }),
    );
    // The open tab takes no press to open it, so Leaf reads the strip's keys again.
    this.strip.dispatchEvent(
      new CustomEvent("lf-commands", { bubbles: true, composed: true }),
    );
    this.#declareHeader();
  }

  // Roving focus per the ARIA tabs pattern: arrows move and activate, and come round
  // at the ends. The strip takes no tab stop of its own, so focus inside it, which is
  // the whole of when this scope holds, is always one of its tabs.
  #declareKeys() {
    const strip = this.strip;
    const down = this.args.down;
    const tabs = () => this.#tabs();
    const here = () => strip.getRootNode().activeElement;
    const focusedTab = () => tabs().find((tab) => tab === here());
    const walk = (next) => {
      if (!next) return;
      // Native focus scrolling would carry a stuck tab back to its place in flow and
      // move the view being left before the switch records it. So the tab comes into
      // the window after the switch (`#showTab`), once the focus paint marks its ring,
      // as every walk's landing does (records/walk-position.js, `rowWalk`). Left out of
      // sight, the tab would lose focus to the next key (panel/page-keys/controller.js).
      focusDestination(next, "move");
      next.click();
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
    const [back, ahead] = rowArrows(this.host);
    strip.lfCommands = {
      title: "On a tab",
      rows: [
        {
          id: "tab.activate",
          keys: PRESS,
          title: "open the tab",
          // The tab already open has nothing for this press to do, so the line does not
          // name it there; the walk beside it is what moves.
          when: () => here() !== this.#tabOf(this.#shown),
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
            const at = all.findIndex((tab) => tab === focusedTab());
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
    strip.dispatchEvent(
      new CustomEvent("lf-commands", { bubbles: true, composed: true }),
    );
  }

  #revealed = (event) => {
    const panel = event.currentTarget;
    this.send(TabsMessage.Revealed({ id: panel.id }));
  };

  // A press on an edge's face pages the strip that way.
  #page = (event) => {
    const press = event.target.closest(".lf-tabstrip-scroll > span");
    const to = press?.parentElement?.getAttribute("data-lf-to");
    if (!to) return;
    const strip = this.strip;
    const ahead = getComputedStyle(strip).direction === "rtl" ? -1 : 1;
    strip.scrollBy({
      left: ahead * (to === "start" ? -0.8 : 0.8) * strip.clientWidth,
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
    });
  };

  // A side list's panels are reading regions whatever their posture, as panes are
  // (the constructor marks them), so the user's place in an item survives the
  // workspace flowing and filling the window again. Its list is one only while it
  // scrolls on its own, which the theme declares on it (`--lf-holds-height`): a column,
  // sticking beside the item or filling the height a full-height workspace gives it,
  // or that workspace's stacked row. A row over the item elsewhere keeps its open tab
  // in view itself (`#showTab`), and observed as a region there, its own scrolling as
  // it turned into a row ended the size observers' pass with notifications
  // undelivered. Which it is follows the window, so the strip's size observer asks
  // again.
  #syncListRegion() {
    if (this.host.getAttribute("list") !== "side" || !this.strip.isConnected) return;
    const holds =
      getComputedStyle(this.strip).getPropertyValue("--lf-holds-height").trim() === "1";
    keeps(this.strip, "data-lf-scroll", holds ? "list" : "");
  }

  // A page-flow strip sticks at the window's top over the whole document, so it is a
  // sticky header of the root: its border-box height joins the root landing inset
  // through its `data-lf-root-header` mark, and every landing arrives below it. What
  // the strip stands over inside its panels stacks through `--lf-top` (the package
  // theme). A page's list of parts is that header only while it is a row over the open
  // part, as on a phone; beside the part it covers none of it. Which the list is
  // follows the window, so the strip's size observer asks again.
  #declareHeader() {
    const { parts, pageFlow } = this.args;
    const shown = this.#shown;
    const over =
      !parts ||
      Boolean(
        shown &&
        this.strip.getBoundingClientRect().right >
          shown.getBoundingClientRect().left + 1,
      );
    this.strip.toggleAttribute(
      "data-lf-root-header",
      pageFlow && over && this.strip.isConnected,
    );
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
  #showTab(tab, within = this.strip) {
    const strip = this.strip;
    const run = tab?.parentElement;
    if (!tab || !run) return;
    const label = run.querySelector(":scope > .lf-tab-group");
    if (label && getComputedStyle(strip).flexDirection === "row") {
      const inset = landingInsets(strip);
      const room = strip.clientWidth - inset.left - inset.right;
      const gap = Number.parseFloat(getComputedStyle(run).columnGap) || 0;
      const size = label.getBoundingClientRect().width;
      const apart = size + gap + tab.getBoundingClientRect().width > room;
      run.toggleAttribute("data-lf-group-apart", apart);
      run.style.setProperty("--lf-tab-group-size", layoutPx(size));
      scrollIntoView(tab, { block: "nearest", within });
      return;
    }
    const range = label && document.createRange();
    if (range && label) {
      range.setStartBefore(label);
      range.setEndAfter(tab);
    }
    scrollIntoView(tab, { including: range, block: "nearest", within });
  }

  // The tablist says which way its names run, the way the theme lays them
  // (`--lf-tabstrip-flow`): down a column, and across the row a narrow window stacks a
  // side list or a page's parts into, as every other strip runs (the tablist default).
  // The open tab stays in the row as the strip's width changes, and not only when a
  // tab opens: a narrowed window, a panel opening beside the page, or a side list's
  // column turning into a row would otherwise leave the open tab past the edge. It
  // follows the size delivery before the resized strip paints.
  #positionStrip = () => {
    keeps(
      this.strip,
      "aria-orientation",
      getComputedStyle(this.strip).flexDirection === "column" ? "vertical" : null,
    );
    this.#stopSelectionMotion();
    this.#syncListRegion();
    this.#declareHeader();
    this.#showTab(this.#tabOf(this.#shown));
  };

  #stopSelectionMotion = () => {
    if (this.args.travels) this.send(TabsMessage.Settled());
  };
}

// A panel whose one block was drawn at another width, or shown or hidden, tells it.
const laidOut = (panel) => {
  const children = [...panel.childNodes].filter(
    (child) =>
      (child instanceof Element && !child.matches("script, style, template")) ||
      (child instanceof Text && child.data.trim()),
  );
  const [only] = children;
  if (children.length === 1 && only instanceof Element)
    only.dispatchEvent(new CustomEvent("lf-layout", { bubbles: true, composed: true }));
};

const Strip = Mount.makeStream(
  "Strip",
  {
    args: {
      active: Schema.NullOr(Schema.String),
      step: Schema.Number,
      via: Schema.NullOr(Via),
      travels: Schema.Boolean,
      down: Schema.Boolean,
      pageFlow: Schema.Boolean,
      parts: Schema.Boolean,
      root: Schema.Boolean,
    },
  },
  (strip, args, changes) =>
    Stream.callback((queue) =>
      Effect.gen(function* () {
        const keepView = yield* KeepView;
        const work = new StripWork(strip, args, (message) =>
          Queue.offerUnsafe(queue, message),
        );
        yield* Effect.addFinalizer(() => Effect.sync(() => work.close()));
        // The first args are the set's opening, which Leaf shows as a switch's panel
        // in the mount itself, so a module that builds a set reads its open panel as
        // soon as it appends it, as lf-text-document.js measures its preview.
        const opening = work.update(args);
        if (opening) {
          yield* keepView({ member: opening });
          work.landed();
        }
        yield* Effect.forkScoped(
          Stream.runForEach(changes, (next) =>
            Effect.gen(function* () {
              const member = work.update(next);
              if (!member) return;
              yield* keepView({ member });
              work.landed();
            }),
          ),
        );
      }),
    ),
);

/** The options both of this module's tags define their widget with. */
export const tabSetOptions = {
  shadow: true,
  statics: { lfPatch: "members" },
  inputs: (element) => {
    const parts = element.localName === "lf-parts";
    // The first tab set directly in the page is its navigation, whatever else the page
    // holds beside it; a later one is a tabbed section like any nested set. A page's
    // parts are its navigation where the page lays them out, in a `main` that is no
    // Layout's box (layouts.css, `--lf-layout-box`), as the theme and content-layout
    // read it; in any other `main` they stand as if placed anywhere else.
    const main = element.parentElement;
    const root =
      !!main &&
      main.matches("body > main") &&
      (parts
        ? getComputedStyle(main).getPropertyValue("--lf-layout-box").trim() !== "1"
        : main.querySelector(":scope > lf-tabs") === element);
    const panels = viewMembers(element).map((panel) => {
      Equal.byReferenceUnsafe(panel);
      const template = panel.firstElementChild;
      // A row keeps the answer's room where its panel's markup asks the user something.
      const held = readObligations(panel);
      const items = held.asks ? held.all : [];
      // Counted as an `lf-tally` of the panel would count them (`tally`). Withdrawn
      // items are already left out, so every item that isn't open is answered.
      const { onUser, onAgent, open, total } = tally(items);
      const [only] = items;
      return {
        panel,
        id: panel.id,
        label: panel.getAttribute("label") ?? "",
        summary: panel.getAttribute("summary"),
        group: panel.getAttribute("group"),
        face: template instanceof HTMLTemplateElement ? template.innerHTML : null,
        changed: comparisonChanges(panel).length,
        asks: Boolean(held.asks),
        onUser,
        onAgent,
        open,
        total,
        only: total === 1 && open === 0 && only ? answerWords(only) : null,
      };
    });
    return {
      panels,
      side: element.getAttribute("list") === "side",
      parts,
      root,
      pageFlow: parts ? root : element.getAttribute("flow") === "page",
      // The strip is named as the chrome names the set (`nameOf`): its author's
      // `aria-label`, else the nearest element holding it that has a name, such as its
      // section. The page's navigation stands in no section, and the page's `<title>`
      // names it: `main` has no name of its own, so its label would be its words run
      // together.
      name: nameOf(element) || (root ? nameOf(document) : ""),
      agent: agentName(),
      // Open the tab the address names, or this user's last, whose id resolves in
      // later versions because check forbids dropping ids.
      opening: openingView(element)?.id ?? null,
    };
  },
};

defineWidget("lf-tabs", Tabs, tabSetOptions);
