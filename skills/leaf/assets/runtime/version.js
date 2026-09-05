/* Version travel: everything the reader's move between two documents of one page takes.
 *
 * One owner, because it is one gesture: the walk through the chooser's menu states a
 * comparison per row, an activation drops the standing comparison and puts it back once
 * the new main stands, the chooser's word says whether one is standing, and the
 * activation captures the reading landmark before it replaces the authored main. Those
 * are local calls here rather than callbacks across a seam nothing else could stand at.
 *
 * The surface is the three key rows; the chooser's nodes (control, menu, newest-version
 * chip) and the labels the banner reserves width for (`versionLabels`); the two calls
 * state application drives — `renderVersions` paints the chooser from a state,
 * `prepareActivation` fetches the revision a state names ahead of the commit that
 * installs it; the arrival landing; the menu readings the composing surface and the
 * margin take (`closeVersionMenu`, `versionMenuIsOpen`, `comparisonBase`,
 * `comparisonChanges`); and `readingBlock`, the block the decision walk starts from.
 */
import { runtime } from "./context.js";
import { designOn } from "./design.js";
import { shownBox } from "./geometry.js";
import { PRESS, walkRows } from "./keyboard/bindings.js";
import { keys, paintKeys } from "./keyboard/scopes.js";
import { notice } from "./notifications.js";
import {
  authored,
  closestAcross,
  containsAcross,
  inChrome,
  TEXT_BLOCK,
  textNodesUnder,
  wrote,
} from "./passages.js";
import { MARKED_IN_PAGE, dress, markDeclared } from "./presentation.js";
import { reachScrollers } from "./reach.js";
import { registry, stateSpecs, tagsDeclaring } from "./registry.js";
import { targetElement, targetSegments } from "./resolved-target.js";
import { moveScrollerBy, pageScroller } from "./scrolling.js";
import { LIVE_ROOT, PAGE_SCOPE, versionUrl } from "./storage.js";
import { focusDestination, quoted } from "./widget-elements.js";
import { settle, settling } from "./widget-upgrade.js";

// The document roots may carry authored classes, data attributes, and inline custom
// properties that page-local styles read. The live document also paints its own facts
// onto those same two elements. The authored share is remembered at import, before the
// boot module has run a line: no runtime module writes the document at its own top
// level, and the runtime's stylesheet and the banner's icon link come later from the
// boot module. An activation can then replace exactly that share without erasing the
// presentation, layout, and mode facts the surviving runtime owns.
const authoredAttributes = (root) =>
  new Map([...root.attributes].map(({ name, value }) => [name, value]));
const versionedHeadNode = (node) =>
  !(
    node.localName === "meta" &&
    ["lf-revision", "lf-version"].includes(node.getAttribute("name")) &&
    node.hasAttribute("data-lf-runtime")
  ) &&
  (node.localName === "title" ||
    node.localName === "style" ||
    node.localName === "base" ||
    (node.localName === "meta" &&
      (node.hasAttribute("name") || node.hasAttribute("property"))) ||
    (node.localName === "link" &&
      !(
        node.rel === "stylesheet" &&
        new URL(node.href, document.baseURI).pathname === "/theme.css"
      )));
let authoredBodyAttributes = authoredAttributes(document.body);
let authoredHeadNodes = new Set([...document.head.children].filter(versionedHeadNode));
let authoredHtmlAttributes = authoredAttributes(document.documentElement);

/* Semantic reading position preserved across authored-document replacement. */
const VIEW_KEY = "lf-view";
const LANDMARK_CAP = 160;

export function createVersion({
  allButTheReference,
  banner,
  captureAuthoredFacets,
  cut,
  domFacet,
  el,
  elementById,
  focused,
  importWidgets,
  landedAt,
  midComposition,
  pageText,
  paintHere,
  paintLegend,
  projectionFromView,
  pruneScopedElements,
  quoteFrom,
  rangeOf,
  readAndApply,
  rememberAuthoredParents,
  rememberPassageParts,
  reportPageError,
  reserveNewsSlot,
  resetAuthoredPage,
  resolveAnchor,
  reveal,
  sameLayer,
  setLanded,
  showNews,
  stateCoordinate,
  stateSignoff,
  style,
  syncLayout,
}) {
  // ---------- the version chooser ----------
  // `runtime.versions` is spliced in place, never reassigned: context's readers hold it.
  const stamped = (version) =>
    runtime.versions.find((candidate) => candidate.version === version);
  // The version chooser: a press that says which version this is, and a menu that says
  // what each one was and what it changed. It was a <select>, and the two things that
  // cost were both the control's rather than the styling's. A select takes its inner
  // height from Chrome's own metrics and refuses line-height, so it could never stand
  // level with the buttons beside it; and its closed label is its selected option's whole
  // text, so the note had to be in both places or neither — 190px of bar, the widest
  // control on the row, for about nine characters of a note that then ellipsized. A press
  // states the version alone, and the menu is the only place the notes are, where a row
  // can wrap and carry one whole.
  //
  // The diff was a second press beside it, and everything the two shared was in the
  // menu already. It named the previous version because a control with one label can
  // offer one base, and the previous version is the least useful of them on a page that
  // ships a version whenever the work moves: what the reader wants marked is what has
  // changed since they last looked, which is as far back as they were away. The base is
  // the menu's to say, so every version older than this one offers itself as one.
  //
  // Which version this is, is the live document's answer, so the
  // press says it now rather than standing empty until the first poll answers, and the
  // only word it ever rewrites is the Δ that says a comparison is standing — enumerable,
  // so the room for it is taken from the words themselves at load (reserve) and the
  // control still cannot move the row. It is a word rather than the accent alone because
  // a reader who leaves a comparison on and scrolls into a stretch that changed nothing
  // has only this control to read it back off, and a colour is not a thing a screen
  // reader announces.
  // The closed control is an address, not the menu's account of the working document.
  // Keep it to the stable version token (or Draft); the full "Draft after vN" context
  // remains in the menu row and the control's title. `versionLabels` is every compact
  // token the control can wear, for the banner to reserve the widest of without
  // reintroducing that account as dead width.
  const versionLabel = (
    comparing,
    label = runtime.currentStamp === null ? "Draft" : `v${runtime.currentStamp}`,
  ) => (comparing ? "Δ " : "") + `${label} ▾`;
  const versionLabels = () =>
    [undefined, "Draft", "v999"].flatMap((label) => [
      versionLabel(false, label),
      versionLabel(true, label),
    ]);
  const versionBtn = el("button", "lf-btn lf-version", versionLabel(false));
  versionBtn.setAttribute("aria-haspopup", "menu");
  versionBtn.setAttribute("aria-expanded", "false");
  const versionMenu = el("div", "lf-ui lf-version-menu");
  versionMenu.setAttribute("popover", "auto");
  versionMenu.setAttribute("role", "menu");
  versionMenu.setAttribute("aria-label", "Versions");
  const versionMenuIsOpen = () => versionMenu.matches(":popover-open");
  // Whether there is a menu to open is not whether there is anything in it to walk: a
  // first version has no neighbour, but its menu still explains that version. The
  // browser owns dismissal; Leaf only enables its version-walk bindings when a
  // neighbouring destination exists.
  const draftRevisions = () => {
    const revisions = new Set();
    if (runtime.currentStamp === null && runtime.currentRevision !== null)
      revisions.add(runtime.currentRevision);
    if (runtime.active?.version === null) revisions.add(runtime.active.revision);
    return revisions;
  };
  const versionCount = () => runtime.versions.length + draftRevisions().size;
  const versionsOffered = () => versionCount() > 0;
  const versionsToWalk = () => versionCount() > 1;
  // The walk is the versions, not every press in the menu.
  const versionRows = () => [...versionMenu.querySelectorAll(".lf-version-row")];
  const versionStops = () =>
    [...versionMenu.querySelectorAll("button:not(:disabled)")].filter(
      (control) => control.getClientRects().length,
    );
  // A menu is a transient reading of the chooser, not a layer over the next control a
  // reader Tabs to. Its comparison checkboxes are real internal Tab stops, so offer an
  // exit only from the boundary control in the direction being travelled. The native row
  // below closes the menu first and then leaves the browser to complete that same Tab.
  const atVersionBoundary = (end) => {
    const stops = versionStops();
    return document.activeElement === stops.at(end);
  };
  function focusVersionRow() {
    (
      versionRows().find(
        (r) =>
          (comparisonBase() !== null &&
            r.dataset.lfVersion === String(comparisonBase())) ||
          (comparisonBase() === null &&
            r.dataset.lfRevision === String(runtime.currentRevision)),
      ) ?? versionRows()[0]
    )?.focus();
  }

  // The browser owns top-layer state, light dismissal, Escape, and the handback. What it
  // restores focus to on a hide is the element that had it when the popover showed — not
  // the `source`, which buys the anchor and the invoker relationship and nothing about
  // focus — so every door into this menu shows it from the button and the way back out is
  // the platform's for pointer entry, because that press focuses the button first. Keyboard
  // `g V` clicks the same invoker without moving focus and its return frame restores the real
  // origin; the reference stands a layer back up from that invoker before restoring its own
  // origin. Scoping the platform handback to its door rather than to the state is what keeps
  // it off a light dismissal, which restores nothing on purpose: a reader who pressed away
  // into the page is left where they pressed rather than moved to the chooser they pressed
  // away from. Leaf is left with the close, which is the only end state it asks for.
  function closeVersionMenu() {
    if (versionMenuIsOpen()) versionMenu.hidePopover();
  }
  versionMenu.addEventListener("toggle", (event) => {
    const open = event.newState === "open";
    versionBtn.setAttribute("aria-expanded", String(open));
    // Focus is the menu's own only where nothing else has claimed it. An open lands on the
    // row the comparison stands on — unless the reader is already inside, which is where the
    // reference's restore puts them when it hands the menu back, and moving them off it
    // would undo the whole point of the exemption.
    if (open && !versionMenu.contains(document.activeElement)) focusVersionRow();
    paintHere();
  });
  // The press is the popover's declared invoker rather than a click handler that toggles by
  // reading the state: a press on the invoker of a standing auto popover is a light dismissal
  // *and* a press, so a handler asking whether the menu is open is asked after the dismissal
  // and opens it straight back — the menu could be pressed shut and never was. The browser
  // knows the two are one gesture. `lfInvoker` is the same relationship read from the other
  // end, which is the end anything standing a layer back up has: it holds the layer and needs
  // the control, and the platform offers no way back along its own link.
  versionBtn.popoverTargetElement = versionMenu;
  versionMenu.lfInvoker = versionBtn;
  // The newest-version chip. Its hidden pinned slot carries representative words as well
  // as a measured width: an empty button is shorter, so its first real label would still
  // move vertically. Its press goes through the chooser's one door (goActive): at the
  // live root an explicit in-place release of the composition hold, on an immutable page
  // ordinary version travel.
  const latestChip = el(
    "button",
    "lf-ui lf-btn lf-latest-chip",
    "New page available → open v999",
  );
  latestChip.onclick = () => goActive();
  // The one address on this row whose arrival a reader must not miss: what they are
  // reading has been replaced. Every other address is standing information, and being
  // behind the row's menu costs it nothing; this one is news, so the menu's door says so
  // while it holds it (banner-shelf.js, paintDoor).
  latestChip.dataset.lfUrgent = "1";
  if (!LIVE_ROOT) reserveNewsSlot(latestChip);
  const arriving = (label) => `New page available → open ${label}`;
  // The menu's own scope. The walk is the menu's rather than the page's, because ArrowUp and
  // ArrowDown anywhere else are the page's own scroll; ⏎ is the browser's, a row being a
  // button, and the row says so with no `run`. A row's Δ is the same comparison for the
  // pointer, which has no walk to state it with, and takes no key of its own.
  //
  // v is the one row worth a key of its own: the current page is where the walk ends, and
  // where a reader who came for the current state is going. It is local to the menu, so the
  // page-level destination remains the complete `g V` route rather than a second meaning for
  // a bare letter.
  //
  // This scope is live only while there is a list to walk. The mode below stays live for
  // every open menu so page-level Leaf shortcuts remain suspended while the browser owns
  // the transient layer.
  const NEWEST = {
    id: "version.current",
    keys: ["v"],
    does: "Open the current page",
    line: "open the current page",
    // A stamped row is deliberately historical, including the newest one. This key names
    // the live page instead, sharing the same route as the arrival chip while the focused
    // row remains Enter's exact-version destination.
    run: () => goActive(),
  };
  keys(
    versionMenu,
    "In the versions menu",
    [
      {
        id: "version.walk",
        keys: ["ArrowUp", "ArrowDown"],
        routes: [
          { id: "version.previous", binding: "ArrowUp", does: "Previous version" },
          { id: "version.next", binding: "ArrowDown", does: "Next version" },
        ],
        // The walk marks as it goes, which is what the list is for: the note says in words
        // what a version changed and the page behind the menu then says it in the passages
        // themselves, without the reader having to leave the list to find out. A note is
        // Claude's sentence about a version and the marks are the version's own account of
        // itself, so reading them together is the only way to tell the two apart.
        does: "Walk the versions, marking what changed since the one you are on",
        line: "walk — marking changes",
        repeat: true,
        run: (binding) => {
          const was = document.activeElement;
          const row = walkRows(versionRows(), binding === "ArrowDown" ? 1 : -1);
          // A press at either end lands on the row it started from, and now that the walk
          // states a comparison, landing is not free — it would re-fetch the base and say
          // its count again for a press that moved nothing.
          if (!row || row === was) return;
          // The comparison the row states: its own version as the base, or none at all where
          // that version is not older than the one being read. So the reader walks up to mark
          // from further back and back down to stop, and the row that stops it is the version
          // they are reading — the end of the walk in the direction they came from, which is
          // why it needs no key of its own and no reader has to be told where it is — and,
          // the page having no key for a comparison, the whole of the way off one.
          const version = +row.dataset.lfVersion;
          if (comparable(version)) showComparison(version);
          else setDiff(false);
        },
      },
      // The browser's own, the row being a real <button> — no `run`, or the press would
      // click a control the platform has already activated. The word is the line's all the
      // same, and the keys are the shared fact rather than this row's reading of it:
      // spelled by hand, it said Enter and left Space unnamed on a control that answers
      // both.
      {
        id: "version.activate",
        keys: PRESS,
        does: "Open that version",
        line: "open that version",
      },
      NEWEST,
    ],
    versionsToWalk,
  );
  // The mode represents the menu standing, not whether it has multiple versions to walk.
  // It suspends page shortcuts and owns only the Tab-boundary handoff that a popover does
  // not provide. A keyboard-opened menu has CHOOSER's exact return frame; Escape and light
  // dismissal remain native for pointer-opened menus.
  const VERSIONS = {
    title: "In the versions menu",
    when: versionsOffered,
    at: versionMenuIsOpen,
    // A mode over the page suspends the page, which the two modes above this one always did
    // and this one did not — so a reader in the middle of choosing a version could press `l`
    // and take focus out of the menu into the leaves tray, `d` and scroll a page they were
    // not looking at, or `c` and open the composer under the list. None of it fails loudly:
    // the press does exactly what it says on a page the reader has stopped reading. The
    // worst of them was a page-level key that set a comparison base, which the walk they
    // were standing in then disagreed with — that key is the menu's own business now, and
    // the claim is what would have held it either way. The claim is also what narrows
    // the line to the menu's own keys, so what the mode takes and what it offers are one
    // statement rather than a suspension the surfaces have to be told about separately.
    claims: allButTheReference,
    rows: [
      // Two rows, both live at either end of a one-row menu, so the line prints both at
      // once — and while they shared a word it printed it twice, leaving the reader to
      // tell them apart by their keycaps. The direction is the whole difference between
      // them and it is what each says.
      {
        id: "version.leave-forward",
        keys: ["Tab"],
        does: "Leave the versions menu forward",
        line: "leave forward",
        native: true,
        // A held Tab is still one continuous trip through the controls. When its repeated
        // keydown reaches the boundary, closing is part of that press just as it is for a
        // fresh Tab; only the platform's focus move remains native.
        repeat: true,
        when: () => atVersionBoundary(-1),
        run: closeVersionMenu,
      },
      {
        id: "version.leave-backward",
        keys: ["Shift+Tab"],
        does: "Leave the versions menu backward",
        line: "leave backward",
        native: true,
        repeat: true,
        when: () => atVersionBoundary(0),
        run: closeVersionMenu,
      },
    ],
  };

  // g V names the chooser, the control wearing the version number, and the menu it opens.
  // Named, because the chip that jumps straight to the current page spells that motion in
  // its tooltip, and because the closed control's own title says the press beside what
  // pressing it does.
  const CHOOSER = {
    id: "version.open",
    keys: ["Shift+v"],
    does: "The versions, and what each one changed",
    line: "versions",
    control: versionBtn,
    // The same predicate the menu's Escape stands on, so the key cannot open a layer the
    // way out is not live over. The walk being empty is the menu's business, not this key's.
    when: versionsOffered,
    // The popover is the control's own press, while the keyboard register owns the route
    // back to the place that pressed g V. Programmatically focusing the chooser first made
    // the browser return there instead, discarding the real origin before the menu opened.
    returnFrame: () => ({
      active: versionMenuIsOpen,
      close: closeVersionMenu,
      does: "Return from the versions menu",
      line: "back",
    }),
    run: () => versionBtn.click(),
  };

  let lastVersionsKey = "";
  let versionsWalkable = false;
  // A stamped version is historical and always pins. The active working document owns
  // the live root, whether or not that revision has already received a stamp.
  let forceActivation = false;
  const goVersion = (version) => {
    if (version === runtime.currentStamp) return;
    const target = stamped(version);
    if (!target) return;
    const url = new URL(target.url, location.href);
    url.searchParams.set("pin", "");
    location.href = url.href;
  };
  const goActive = () => {
    if (!runtime.active) return;
    if (LIVE_ROOT) {
      if (runtime.active.revision === runtime.currentRevision) return;
      forceActivation = true;
      closeVersionMenu();
      readAndApply();
      return;
    }
    location.href = PAGE_SCOPE || "/";
  };
  function menuRows(state, notes) {
    const latest = state.versions.at(-1)?.version;
    const entries = state.versions.map((entry) => ({
      revision: entry.revision,
      version: entry.version,
      name: `v${entry.version}${entry.version === latest ? " (latest version)" : ""}`,
      note: notes[entry.version],
      current: entry.version === runtime.currentStamp,
      open: () => goVersion(entry.version),
      comparable: comparable(entry.version),
    }));
    for (const revision of draftRevisions()) {
      const active = revision === state.active.revision;
      entries.push({
        revision,
        version: Infinity,
        name: `${active ? "Current" : "This view"} · ${
          revision === runtime.currentRevision
            ? runtime.currentLabel
            : state.active.label
        }`,
        current: revision === runtime.currentRevision,
        open: () => {
          if (active) goActive();
        },
        comparable: false,
      });
    }
    entries.sort(
      (left, right) => left.revision - right.revision || left.version - right.version,
    );
    return entries.flatMap((entry) => {
      const row = el("button", "lf-version-row");
      row.setAttribute("role", "menuitem");
      row.dataset.lfRevision = entry.revision;
      if (entry.version !== Infinity) row.dataset.lfVersion = entry.version;
      // The version and its note are two kinds of word — which one this is, and
      // what it was — so they are two elements rather than one string. That is
      // what lets the note wrap to as many lines as it needs, which is the whole
      // reason the notes are here rather than on a control 190px wide.
      row.append(el("span", "lf-version-num", entry.name));
      if (entry.note) row.append(el("span", "lf-version-note", entry.note));
      if (entry.current) row.setAttribute("aria-current", "true");
      row.onclick = () => {
        closeVersionMenu();
        entry.open();
      };
      if (!entry.comparable) return [row];
      // The comparison this row offers, in the menu's second column beside the note
      // that says the same thing in words. A grid sibling rather than a child, a
      // button inside a button being no markup at all, and named in full: the glyph
      // is the eye's shorthand and says nothing aloud.
      const press = el("button", "lf-version-diff", "Δ changes");
      press.setAttribute("role", "menuitemcheckbox");
      press.dataset.lfVersion = entry.version;
      press.setAttribute("aria-label", `Mark what changed since v${entry.version}`);
      press.title = `Mark what changed since v${entry.version}`;
      // The pointer's own door, and it closes the menu: the marks are on the page this
      // hangs over, and a pointer has no walk to be standing in the middle of. The
      // keyboard's is the walk itself, which leaves the list up.
      press.onclick = () => {
        closeVersionMenu();
        pressComparison(entry.version);
      };
      return [row, press];
    });
  }
  // `null` is the page before its first state. A rendering is a function of its argument
  // and the three current-document facts on `runtime`, so state application rolls a
  // refused candidate back by painting the last accepted state again.
  function renderVersions(state) {
    runtime.versions.splice(0, runtime.versions.length, ...(state?.versions ?? []));
    runtime.active = state === null ? null : structuredClone(state.active);
    if (
      LIVE_ROOT &&
      runtime.active !== null &&
      runtime.currentRevision === runtime.active.revision
    ) {
      runtime.currentStamp = runtime.active.version;
      runtime.currentLabel = runtime.active.label;
    } else if (runtime.currentStamp !== null) {
      runtime.currentLabel = `v${runtime.currentStamp}`;
      const current = stamped(runtime.currentStamp);
      if (current) runtime.currentRevision = current.revision;
    }
    // Nothing to open until the log says what versions there are, and a control that
    // answers nothing is a way in painted where there is no layer behind it — the same
    // reason the page's own approve button waits for the page. `versionsOffered` is what
    // the key and the menu already read; this is the pointer's half of it.
    versionBtn.disabled = state === null || !versionsOffered();
    const walkable = versionsToWalk();
    if (walkable !== versionsWalkable) {
      versionsWalkable = walkable;
      paintKeys();
    }
    const notes = runtime.browser?.version_notes ?? {};
    const key =
      state === null
        ? ""
        : JSON.stringify([
            state.active,
            state.versions,
            notes,
            runtime.currentRevision,
            runtime.currentStamp,
            runtime.currentLabel,
          ]);
    // Rebuilt rather than reconciled: this runs only when the versions or their notes
    // actually changed, which on a page's whole life is a handful of times, and the
    // menu is only ever read while it is open — where a rebuild would take the focused
    // row out from under a walk. So an open menu defers the rebuild, and the key is
    // what the built list holds rather than what the last poll saw: consuming it here
    // and skipping the build inside would mark the change handled and leave that
    // version out of the menu until some later one happened along. A version arriving
    // under an open menu is the new-version chip's news; the list catches up on the
    // next poll after it closes.
    if (key !== lastVersionsKey && !versionMenuIsOpen()) {
      lastVersionsKey = key;
      versionMenu.replaceChildren(...(state === null ? [] : menuRows(state, notes)));
    }
    paintDiff(); // the label may change even when an open menu defers its new rows
    // The keyboard reaches the chip through the chooser rather than past it — g V opens the
    // menu, and its local v takes the current page; the banner spells that motion
    // onto this title.
    const behind =
      runtime.active !== null &&
      runtime.currentRevision !== null &&
      runtime.active.revision !== runtime.currentRevision;
    const sourceFailed = LIVE_ROOT && Boolean(state?.source_error);
    latestChip.disabled = sourceFailed;
    latestChip.dataset.lfKeyTitle = sourceFailed
      ? state.source_error
      : "Open the current page";
    latestChip.title = latestChip.dataset.lfKeyTitle;
    if (sourceFailed) latestChip.textContent = "Latest edit couldn't be shown";
    else if (behind) latestChip.textContent = arriving(runtime.active.label);
    showNews(latestChip, sourceFailed || behind);
  }

  // ---------- version diff ----------
  // "Changes since vN": blocks (paragraphs, list items, widget items) whose text
  // isn't present in the base version get a tinted marker, so re-reading a
  // revision is cheap. Block-level and additions-only — deleted text has no home
  // to mark — and a widget that renders its own body is opaque to it. The base is
  // any version older than the one being read, offered by its own row in the
  // chooser's menu, where the note saying what changed in words sits beside the
  // press that marks it on the page.
  //
  // Which blocks and which widgets is the registry's answer both times, so a widget added
  // to the vocabulary diffs on the strength of its entry: a widget item whose content
  // model is prose is a block of the page's prose the same way a paragraph is.
  const diffBlockSel = () =>
    [
      TEXT_BLOCK,
      "aside",
      ...tagsDeclaring((e) => e["x-parent"] && (e["x-content"] ?? "prose") === "prose"),
      // A verbatim body reaches the reader as its own words, so the widget is a block
      // of the page's prose the way a paragraph is. The leaf-blocks-only rule below
      // keeps the two sides symmetric: unupgraded (the base document) the authored
      // <pre> inside is the leaf and keys the same collapsed text the upgraded
      // widget's standing body keys live — so a rewritten or new draft marks, where
      // it used to be the one block of prose the diff was blind to.
      ...tagsDeclaring((e) => e["x-verbatim"]),
    ].join(",");
  // Opaque: a widget whose upgrade renders its data body, so the text on screen is the
  // module's and can't compare; and one whose slots a decision retires, which holds two
  // versions of one passage and is already its own mark. Plus svg, drawn by either.
  const diffOpaqueSel = () =>
    [
      ...tagsDeclaring(
        (e) => e["x-upgrade"] && !e["x-verbatim"] && e["x-content"] === "data",
      ),
      // External data is absent from both authored documents. Its seat is opaque, and
      // the authored binding and immutable selector below are the comparison key.
      ...tagsDeclaring((e) => e["x-upgrade"] && e["x-data"]),
      // flatMap, so the set holds holder tags rather than the arrays naming them: a set
      // of arrays never dedupes, two array objects never being equal.
      ...new Set(
        tagsDeclaring((e) => e["x-retired-when"]).flatMap(
          (tag) => registry[tag]["x-parent"],
        ),
      ),
      "svg",
    ].join(",");
  // What is being compared, and whether the comparison is standing. Every rendering of
  // the pair — the chooser's word and paint, each row's press, the rail down the span —
  // is written by paintDiff and read back by nothing.
  let diffBase = null;
  let diffOn = false;
  const diffMarked = [];
  // The comparison request that owns the page. Every request takes the next number and every
  // stop takes one too, so a base whose document lands after the reader has moved on is
  // dropped rather than painted over the base they are standing on now. Reachable because the
  // walk asks per row: it is one fetch per press, and the presses come faster than the network.
  let diffRequest = 0;
  // A block's key is its *authored* text (`wrote`), which is why that reading exists: it
  // drops even the labels anchoring reads as the page's own words, because the base
  // version is parsed unupgraded and holds none of them.
  function diffBlocks(root) {
    const pairs = [];
    const [blocks, opaque] = [diffBlockSel(), diffOpaqueSel()];
    const authoredHere = authored(root);
    for (const b of root.querySelectorAll(blocks)) {
      if (inChrome(b) || b.closest(opaque)) continue;
      if (b.querySelector(blocks)) continue; // leaf blocks only, or nesting double-marks
      let key = wrote(b);
      // An x-says value is the page's words at the element's edge (renderSaid), so it
      // belongs to what this block says: folded into the key at its declared edge, a
      // version that moves a metric's number or an event's time marks though no prose
      // changed. Symmetric for free — the base parses unupgraded, where the same
      // attribute would have painted the same words through the pseudo-element.
      for (const [attr, edge] of Object.entries(
        registry[b.localName]?.["x-says"] ?? {},
      )) {
        const said = b.getAttribute(attr);
        if (said) key = edge === "before" ? `${said} ${key}` : `${key} ${said}`;
      }
      if (key) pairs.push([b, key]);
    }
    // Opaque widgets key by identity, not body: an upgrade rewrote the live body,
    // so text can't compare — but a widget the base didn't have still marks.
    for (const w of root.querySelectorAll(opaque)) {
      // parentElement, not w itself: an svg a widget rendered stays its widget's.
      if (!authoredHere(w) || inChrome(w) || w.parentElement?.closest(opaque)) continue;
      const entry = registry[w.localName] ?? {};
      // A data selection is authored semantics even though the generated children
      // of an upgraded widget are opaque to comparison.
      const bindingAttrs = new Set();
      for (const input of Object.values(entry["x-data"] ?? {})) {
        bindingAttrs.add(input.source);
        if (input.snapshot) bindingAttrs.add(input.snapshot);
      }
      const binding = [...bindingAttrs]
        .sort()
        .map((attr) => [attr, w.getAttribute(attr)]);
      pairs.push([w, ` ${w.tagName}#${w.id}${JSON.stringify(binding)}`]);
    }
    return pairs;
  }
  async function baseReading(baseRevision, throughSeq) {
    const params = new URLSearchParams({
      revision: String(baseRevision),
      through_seq: String(throughSeq),
    });
    const res = await fetch(`/api/view?${params}`);
    if (!res.ok) throw new Error(`couldn't project revision r${baseRevision}`);
    const generation = res.headers.get("Leaf-Layer");
    if (generation && !sameLayer(generation)) return null;
    const answer = await res.json();
    if (!answer.browser) throw new Error(`revision r${baseRevision} has no projection`);
    return answer.browser;
  }
  function applyDiff(doc, baseVersion, baseReading) {
    // Multiset membership rather than an alignment: an unchanged block that
    // merely moved stays unmarked; a changed or new one has no base twin.
    const base = new Map();
    for (const [, key] of diffBlocks(doc)) base.set(key, (base.get(key) ?? 0) + 1);
    for (const [b, key] of diffBlocks(document.body)) {
      const left = base.get(key) ?? 0;
      if (left > 0) base.set(key, left - 1);
      else {
        b.classList.add("lf-ins-block");
        diffMarked.push(b);
      }
    }
    // The state half: block keys catch words, and a pure state change — a card
    // in a different column, a pick on a different option — has no text of its
    // own. Compare declared facets instead: the base version's state (its markup
    // plus both folds as of it — a report standing at the base painted there
    // just as an action did, so what the reader saw includes it) against the
    // live DOM, which already wears the current folds. Body facets are words and
    // the block keys above own them.
    const baseRevision = stamped(baseVersion)?.revision;
    if (baseRevision == null)
      throw new Error(`version v${baseVersion} has no revision`);
    const baseView = baseReading?.views?.[String(baseRevision)];
    if (!baseView) throw new Error(`revision r${baseRevision} has no projection`);
    const baseProjection = projectionFromView(baseView, baseReading.conversation);
    for (const { tag, spec } of stateSpecs()) {
      if (!spec.record || spec.record.kind === "body") continue;
      for (const widget of document.body.querySelectorAll(tag)) {
        if (inChrome(widget) || quoted(widget)) continue;
        const units =
          spec.unit === "widget"
            ? widget.id
              ? [widget]
              : []
            : [...widget.querySelectorAll(`${spec.record.within} > [id]`)];
        for (const el of units) {
          const baseEl = doc.getElementById(el.id);
          if (!baseEl) continue; // new to this version: the content half marks it
          // A reader's action outranks provisional agent news on the same fact;
          // otherwise the standing writer is the report. The facet coordinate
          // means an unrelated fact on this unit never enters the choice.
          const coordinate = stateCoordinate(widget.id, el.id, spec);
          const writer = baseProjection.desired.get(coordinate);
          const before = writer ? writer.value : domFacet(baseEl, spec.record);
          const now = domFacet(el, spec.record);
          if (before === now) continue;
          // The element the change reads on: the option now picked, or the moved
          // card itself.
          const target =
            (spec.record.kind === "attribute" && now && elementById(now)) || el;
          if (!target.classList.contains("lf-ins-block")) {
            target.classList.add("lf-ins-block");
            diffMarked.push(target);
          }
        }
      }
    }
    return diffMarked.length;
  }
  // Whether a stamped version can be compared with the revision being read: any stamp
  // on an earlier revision, which is which rows the menu builds a press onto.
  const comparable = (version) => {
    const base = stamped(version);
    return (
      runtime.currentRevision !== null &&
      base !== undefined &&
      base.revision < runtime.currentRevision
    );
  };
  // Every rendering of the pair above, written in one place: the chooser's word, its
  // paint and what it says it will do, the checked state of each row's Δ, and the rail
  // down the rows the comparison spans. Called by the setter, by every chooser render —
  // the other thing that can leave a rendering behind the state — and so once at load,
  // where what the chooser says it will do is written from the start rather than
  // standing as a second copy of these sentences up where the control is built.
  function paintDiff() {
    versionBtn.textContent = versionLabel(diffOn);
    versionBtn.classList.toggle("on", diffOn);
    const currentLabel = runtime.currentLabel ?? "Draft";
    // Rewritten on every diff change, so the key it names is taken from the row each time
    // rather than typed into one of the two branches and forgotten in the other. The
    // closed face is deliberately compact, so its hover and accessible name keep the
    // full draft-after-version context that the open menu also spells out.
    versionBtn.dataset.lfKeyTitle = diffOn
      ? `${currentLabel}: showing what changed since v${diffBase} — pick a version, or press its Δ again to stop`
      : `${currentLabel}: versions; read one, or mark what changed since it`;
    versionBtn.setAttribute(
      "aria-label",
      diffOn
        ? `${currentLabel}: comparing with v${diffBase}; open versions`
        : `${currentLabel}: open versions`,
    );
    // paintCoreControls adds the complete route. Keeping the base title here lets the
    // keyboard register project a chord without this owner reconstructing one.
    versionBtn.title = versionBtn.dataset.lfKeyTitle;
    const baseRevision = stamped(diffBase)?.revision;
    for (const row of versionMenu.querySelectorAll(".lf-version-row")) {
      const revision = +row.dataset.lfRevision;
      row.classList.toggle(
        "lf-compared",
        diffOn &&
          baseRevision !== undefined &&
          revision >= baseRevision &&
          revision <= runtime.currentRevision,
      );
    }
    for (const press of versionMenu.querySelectorAll(".lf-version-diff"))
      press.setAttribute(
        "aria-checked",
        String(diffOn && +press.dataset.lfVersion === diffBase),
      );
    // The base title changed above; the shared projection adds the complete shortcut
    // after this paint, including when a comparison changes without moving focus.
    paintHere();
  }
  // Whether the comparison is standing and what against — the only thing that decides
  // it, the marks and the paint being renderings rather than a second copy.
  function setDiff(on, base) {
    diffOn = on;
    if (on) diffBase = base;
    if (!on) {
      diffRequest++; // a stop outranks a comparison still on its way
      for (const b of diffMarked) b.classList.remove("lf-ins-block");
      diffMarked.length = 0;
    }
    paintDiff();
    // Consumers read the settled comparison projection: on/off and its marks move
    // together, rather than announcing an applied DOM diff before it is standing.
    document.dispatchEvent(new CustomEvent("lf-comparison"));
  }
  // The one way a comparison starts, from a row's press, from the walk through the menu,
  // or from an activation putting back the one it dropped. It states a base rather than
  // toggling one — the toggle is a press's own reading of it, and the walk has none to
  // spend, standing on a row being what makes it the base however many times the reader
  // arrives there. Everything touching the live page happens in one synchronous stretch
  // after the single await: the walk asks for a comparison per row, and a marking pass
  // that could interleave with the next row's would leave two bases' marks standing
  // under a chooser naming one of them.
  async function showComparison(base) {
    const mine = ++diffRequest;
    const baseRevision = stamped(base)?.revision;
    if (baseRevision == null) {
      notice(`Couldn't load v${base}`);
      return;
    }
    const documentRequest = authoredDocument(versionUrl(base));
    let doc;
    let reading;
    try {
      while (mine === diffRequest) {
        const throughSeq = runtime.view?.basis?.through_seq;
        if (!Number.isInteger(throughSeq))
          throw new Error("the current reading has no log sequence");
        [doc, reading] = await Promise.all([
          documentRequest,
          baseReading(baseRevision, throughSeq),
        ]);
        if (doc === null || reading === null || mine !== diffRequest) return;
        if (runtime.view?.basis?.through_seq === throughSeq) break;
      }
    } catch {
      notice(`Couldn't load v${base}`);
      return;
    }
    if (mine !== diffRequest) return;
    if (diffOn) setDiff(false); // the old base's marks, before the new base's land
    const n = applyDiff(doc, base, reading);
    setDiff(true, base);
    notice(
      n
        ? `${n} changed passage${n === 1 ? "" : "s"} since v${base}`
        : `No text changes since v${base}`,
    );
  }
  // A press names one base, so pressing the standing one again is the way off it: a Δ is a
  // toggle where it is lit and a switch of base where it isn't. The keyboard's way off is the
  // walk itself — down to the version being read, which is comparable with nothing and so
  // stops rather than re-bases.
  const pressComparison = (base) =>
    diffOn && base === diffBase ? setDiff(false) : showComparison(base);

  const comparisonBase = () => (diffOn ? diffBase : null);
  const comparisonChanges = () => (diffOn ? [...diffMarked] : []);

  // ---------- another version's document ----------
  // One fetch for the comparison base and for the revision the live root follows. Null is
  // a document from a layer this page no longer runs; `sameLayer` has it reloading by then.
  async function authoredDocument(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`couldn't load ${url} (${response.status})`);
    const generation = response.headers.get("Leaf-Layer");
    if (generation && !sameLayer(generation)) return null;
    const doc = new DOMParser().parseFromString(await response.text(), "text/html");
    if (doc.querySelectorAll("body > main").length !== 1)
      throw new Error(`${url} has no single authored main`);
    return doc;
  }
  // State reads overlap, and two naming the same newer revision share one fetch.
  const revisionDocuments = new Map();
  function revisionDocument(revision) {
    if (!revisionDocuments.has(revision.revision))
      revisionDocuments.set(
        revision.revision,
        authoredDocument(revision.url).catch((error) => {
          revisionDocuments.delete(revision.revision);
          throw error;
        }),
      );
    return revisionDocuments.get(revision.revision);
  }

  // ---------- live revision activation ----------
  function replaceAuthoredAttributes(target, source, prior) {
    const scratch = document.createElement(target.localName);
    for (const [name, value] of prior) scratch.setAttribute(name, value);
    for (const name of prior.keys()) {
      if (name === "class")
        for (const token of scratch.classList) target.classList.remove(token);
      else if (name === "style")
        for (const property of scratch.style) target.style.removeProperty(property);
      else target.removeAttribute(name);
    }
    const next = authoredAttributes(source);
    for (const [name, value] of next) {
      if (name === "class")
        for (const token of source.classList) target.classList.add(token);
      else if (name === "style")
        for (const property of source.style)
          target.style.setProperty(
            property,
            source.style.getPropertyValue(property),
            source.style.getPropertyPriority(property),
          );
      else target.setAttribute(name, value);
    }
    return next;
  }

  function activateHead(doc, revision) {
    for (const node of authoredHeadNodes) node.remove();
    const runtimeStyle = style;
    const next = new Set();
    for (const node of doc.head.children) {
      if (!versionedHeadNode(node)) continue;
      const imported = document.importNode(node, true);
      document.head.insertBefore(imported, runtimeStyle);
      next.add(imported);
    }
    authoredHeadNodes = next;
    let marker = document.querySelector('meta[name="lf-revision"][data-lf-runtime]');
    if (!marker) {
      marker = document.createElement("meta");
      marker.name = "lf-revision";
      marker.dataset.lfRuntime = "1";
      document.head.insertBefore(marker, runtimeStyle);
    }
    marker.content = String(revision.revision);
    stateSignoff(doc.querySelector('meta[name="lf-review"]')?.content === "sign-off");
  }

  // Resolves to the second half of the move — the reader's place and standing, and the
  // comparison the replacement dropped — run once the state that brought the revision is
  // on the new main.
  async function activateRevision(doc, revision) {
    const view = captureView();
    const standing = captureStanding();
    const source = doc.querySelector("body > main");
    const fresh = document.importNode(source, true);
    revisionDocuments.delete(revision.revision);
    const settlingFrom = settling.length;
    const comparedFrom = comparisonBase();
    if (comparedFrom !== null) setDiff(false);

    resetAuthoredPage();
    rememberAuthoredParents(source);
    rememberAuthoredParents(fresh);
    rememberPassageParts(fresh);
    markDeclared(fresh, MARKED_IN_PAGE);
    authoredHtmlAttributes = replaceAuthoredAttributes(
      document.documentElement,
      doc.documentElement,
      authoredHtmlAttributes,
    );
    authoredBodyAttributes = replaceAuthoredAttributes(
      document.body,
      doc.body,
      authoredBodyAttributes,
    );
    runtime.currentRevision = revision.revision;
    runtime.currentStamp = revision.version;
    runtime.currentLabel = revision.label;
    activateHead(doc, revision);
    document.querySelector("body > main").replaceWith(fresh);
    pruneScopedElements();
    settle(dress(fresh));
    await Promise.allSettled(settling.slice(settlingFrom));
    reachScrollers(fresh);
    captureAuthoredFacets(fresh);
    syncLayout();
    if (designOn) paintLegend();
    return () => {
      restoreView(view);
      restoreStanding(standing);
      if (comparedFrom !== null) showComparison(comparedFrom);
    };
  }

  // The move a state asks of the live root, fetched ahead of the commit that makes it.
  // Null where there is nothing to follow — no newer revision, or a document that failed
  // to load, which is reported; the commit's own render then lights the chip as the way
  // to try again, and nothing here paints ahead of that commit, so a refused candidate
  // has nothing of this move to roll back. `stale` where the document came from a
  // re-vendored layer, so the page is reloading and the state belongs to the layer it is
  // leaving. Whether the move happens now is asked at the commit: `midComposition` or an
  // open menu defers it, unless the chip was pressed (goActive) — the one override, spent
  // by the install it forced.
  async function prepareActivation(state) {
    const target = state.active;
    if (
      !LIVE_ROOT ||
      runtime.currentRevision === null ||
      target.revision <= runtime.currentRevision
    )
      return null;
    let doc;
    try {
      doc = await revisionDocument(target);
    } catch (error) {
      reportPageError(
        `revision ${target.revision} failed to load: ${error?.message ?? error}`,
      );
      return null;
    }
    if (doc === null) return { stale: true };
    // Step 4 of the startup order, at the boundary that runs the same passes: this
    // version may introduce a tag the standing document never carried, and insertion is
    // where its connectedCallback runs. Fetched here, on the same background stretch as
    // the document itself, so the install below spends none of its view transition on a
    // module fetch and the page the reader is still looking at is whole for the length
    // of the import. activateRevision has no other caller, so this is the one import.
    await importWidgets(doc.querySelector("body > main"));
    return {
      stale: false,
      activates: () =>
        target.revision > runtime.currentRevision &&
        (!midComposition() || forceActivation) &&
        !versionMenuIsOpen(),
      install: () => {
        forceActivation = false;
        return activateRevision(doc, target);
      },
    };
  }

  // ---------- reading continuity across a replacement ----------
  // Following a new version replaces the authored main, whether the live root keeps this
  // document or historical travel opens another one. A raw replacement leaves the reader
  // at the top mid-session, standing nowhere in the walk they were making. Where they are
  // rides across as one semantic view — and through tabStore on document travel, per-tab
  // because a place in a page shouldn't outlive it. Two things are recorded, because
  // decisionPosition reads two the runtime can write down: the passage they were reading, and
  // the ask the a/A walk had stepped them to. The passage travels as a landmark rather
  // than a pixel offset, since content moves between versions: re-find it by its text
  // within its section, then the section alone, and only fall back to the raw offset when
  // neither survived the revision. The panel's own open state is restored separately
  // (PANEL_KEY); because that runs first, the column is already reflowed by the time we
  // scroll.

  // The page's own text blocks the reader can see, in document order, with the rect of each
  // one's first line — one reading of what is in front of them, for the two questions that
  // ask it: which passage a version change should land them back on (below), and where a
  // walk over the page's decisions starts when they have pointed at nothing (decisionPosition).
  // A block's landmark is the top of its first line (a range), not its border box; restore
  // measures the matched text the same way, so the line box's leading cancels out.
  function* blocksOnScreen() {
    // Read the painted edge directly. The declared height may contain a safe-area
    // `calc()`, whose serialized value is not a number even though its box is exact.
    const bannerBottom = banner.getBoundingClientRect().bottom;
    for (const block of document.querySelectorAll(TEXT_BLOCK)) {
      // [hidden] needs an explicit skip: hidden="until-found" resolves to
      // content-visibility, under which descendants still report real rects —
      // but what's behind an inactive tab isn't what the reader is reading.
      if (inChrome(block) || block.closest("[hidden]")) continue;
      const range = document.createRange();
      range.selectNodeContents(block);
      const rect = range.getBoundingClientRect();
      if (rect.height && rect.bottom > bannerBottom) yield [block, rect];
    }
  }
  // The one block the reader is on, which is the first the walk above yields. Two
  // things outside ask it — where a decision walk starts, and where the keyboard
  // reference hands a reader back to — and they were asking it in two places with the
  // same expression written out twice.
  const readingBlock = () => blocksOnScreen().next().value?.[0] ?? null;

  // The quote and the section it's searched in come from the same block, or the search is
  // filtered to a section the text isn't in and can only ever fail — restore then falls back
  // to the section, which doesn't absorb content added above the reader inside it.
  function captureView() {
    const view = { revision: runtime.currentRevision, y: pageScroller.scrollTop };
    // Where the decision walk left off, which is the reader's place stated more exactly than
    // any block can state it — the walk put them there on purpose. Its element identity
    // does not survive an authored-main replacement, and the module variable does not
    // survive document travel, so the id is the one form both can restore. The ring is not
    // recorded beside it: it is painted from focus, and another document starts on the page.
    view.decision = landedAt()?.id;
    for (const [block, rect] of blocksOnScreen()) {
      const section = block.closest("[id]");
      if (!view.section && section) {
        // The first on-screen block's section, kept only until a quotable block supplies
        // its own: a page with nothing quotable on screen still has somewhere to land.
        view.section = section.id;
        view.sectionTop = shownBox(section).top;
      }
      // Written down the way a comment's quote is, so the search that re-finds it is
      // looking for a string of the same kind.
      const text = cut(quoteFrom(textNodesUnder(block)), 0, LANDMARK_CAP);
      // A short line ("Risks") would match anywhere; keep scanning for a quotable block.
      if (text.length >= 24) {
        // Unconditionally, so a quotable block under no section clears the earlier one
        // rather than sending the search into a subtree its text isn't in.
        view.section = section?.id;
        view.sectionTop = section && shownBox(section).top;
        view.quote = text;
        view.quoteTop = rect.top;
        break;
      }
    }
    return view;
  }

  // A restore jumps rather than glides: a page is free to set scroll-behavior: smooth, and
  // animating from the replacement's raw position is worse than the jump it replaces.
  // Moving to a mark the reader asked for is the other case, and says so.
  function restoreView(view) {
    // Where the walk left off, put back before the scroll below restores the coarser
    // reading of the same fact — and put back whether or not this version answered that
    // decision, since a decision the reader has not stepped off is still the one they would step
    // from. The document's own lookup rather than elementById: the decision list is the
    // document's (openDecisions), and a landing inside a shadow tree is one decisionStep could never
    // measure against. A thread's decision is not here yet — the panel is rebuilt from the log
    // on the first poll, which is behind this — so the record answers for the page's decisions
    // and says nothing about the panel's, rather than restoring a second time later over a
    // walk the reader has made since.
    setLanded((view.decision && document.getElementById(view.decision)) || null);
    const text = pageText();
    const found = view.quote && resolveAnchor(view, text);
    const segments = targetSegments(found);
    if (segments.length) {
      reveal(segments[0].node.parentElement); // the passage may sit behind a tab
      moveScrollerBy(
        pageScroller,
        rangeOf(segments).getBoundingClientRect().top - view.quoteTop,
      );
      return;
    }
    const section = targetElement(resolveAnchor({ section: view.section }, text));
    if (section) {
      reveal(section);
      // The shown reading on both sides of the subtraction, because the landmark is
      // whatever id stands nearest the block the reader was on, and a section that
      // generates no box of its own is one a suggestion wrapping whole sections leaves
      // there. Read raw, both sides come back 0 and the correction is 0 — so the restore
      // that had somewhere to land did nothing, silently, and left the reader at the top.
      moveScrollerBy(pageScroller, shownBox(section).top - view.sectionTop);
    } else pageScroller.scrollTo({ top: view.y, behavior: "instant" });
  }

  // Where the reader is standing in the authored page, written down so the swap can hand
  // it back. The Ask's numbered actions remain live over a focused pick mark; those are
  // presses the reader is about to make, and a replacement that dropped the focus onto
  // body took the offer down with it — the digit then picked nothing, silently. Node
  // identity does not survive the swap, so the place is stated the way the decision above
  // is, by id: the nearest element carrying one, and within it the control by kind and
  // position, since a grip or a pick mark is the runtime's and carries no id of its own.
  // A control staged in a shadow tree is out of the place's own query and comes back as
  // the place. The chrome stays through a swap and so does focus inside it, so a reader
  // standing there has nothing to write down. The place is an authored element, read the
  // way the anchor pass reads which section a passage is in: an injected row carries an
  // id too, and is not a place a revision keeps.
  function captureStanding() {
    const held = focused();
    if (!held || held === document.body || inChrome(held)) return null;
    const main = document.querySelector("body > main");
    const place = closestAcross(held, "[id]:not(.lf-ui)");
    if (!place || !main || !containsAcross(main, place)) return null;
    if (place === held) return { id: place.id };
    // The first class is the one the control was built with; later ones are state the
    // fresh control will not be wearing yet. Escaped, since an authored class need not
    // be a bare identifier.
    const kind = [held.localName, held.classList[0] && CSS.escape(held.classList[0])]
      .filter(Boolean)
      .join(".");
    return {
      id: place.id,
      kind,
      index: [...place.querySelectorAll(kind)].indexOf(held),
    };
  }
  // The same control where the revision kept it; the place where it kept only that; and
  // nothing where it kept neither — a reader whose item the revision removed is standing
  // nowhere, and body, where the page's own keys are live, is the honest answer.
  function restoreStanding(standing) {
    if (!standing) return;
    // Only where the swap left the reader standing nowhere. The activation settles its
    // modules asynchronously after the swap, and a reader who moved into the chrome
    // across that gap has taken a place of their own.
    const held = focused();
    if (held && held !== document.body) return;
    const place = elementById(standing.id);
    if (!place) return;
    const control =
      standing.kind === undefined
        ? place
        : (place.querySelectorAll(standing.kind)[standing.index] ?? place);
    focusDestination(control);
  }

  function installArrival({ fragmentId, ready, scrollToElement, tabStore }) {
    // Ordinary reload and history travel belong to the browser. The root is its document
    // scrollport, so native restoration is both more complete and less surprising than a
    // parallel session-store reading. Leaf intervenes after upgrades only for two semantic
    // cases the platform cannot know: a fresh URL aimed at a target generated or hidden by
    // a widget, and travel to a different authored revision where a passage is a better
    // landmark than the old document's pixels.
    const navigationType = performance.getEntriesByType("navigation")[0]?.type;
    // Parsed inside its own guard, which is a different question from whether the store
    // answered: tabStore hands back null for a store that refused, and what a page wrote
    // there is only JSON while every version of this runtime agrees about the shape. A
    // landmark that no longer parses costs the reader their scroll position; throwing here
    // would cost them the page, at module top level, with nothing else having run.
    const savedView = (() => {
      try {
        return JSON.parse(tabStore.get(VIEW_KEY) || "null");
      } catch {
        return null;
      }
    })();
    addEventListener("pagehide", () => {
      if (!ready()) return;
      tabStore.set(VIEW_KEY, JSON.stringify(captureView()));
    });
    function landArrival() {
      const aimed =
        navigationType === "navigate" &&
        targetElement(resolveAnchor({ section: fragmentId(location.hash) }));
      if (aimed) scrollToElement(aimed, "instant");
      else if (
        navigationType === "navigate" &&
        savedView &&
        savedView.revision !== runtime.currentRevision
      )
        restoreView(savedView);
    }
    return { landArrival, savedView };
  }

  renderVersions(null);

  return {
    CHOOSER,
    NEWEST,
    VERSIONS,
    closeVersionMenu,
    comparisonBase,
    comparisonChanges,
    installArrival,
    latestChip,
    prepareActivation,
    readingBlock,
    renderVersions,
    versionBtn,
    versionLabels,
    versionMenu,
    versionMenuIsOpen,
  };
}
