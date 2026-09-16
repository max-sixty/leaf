/* Version travel: everything the reader's move between two documents of one page takes.
 *
 * One owner, because it is one gesture: the walk through the chooser's menu states a
 * comparison per row, an activation drops the standing comparison and puts it back once
 * new document stands, the chooser's word says whether one is standing, and the
 * activation captures the reading landmark before navigating. Those
 * are local calls here rather than callbacks across a seam nothing else could stand at.
 *
 * The surface is its key rows; the two calls state application drives —
 * `renderVersions` supplies one immutable chooser reading from a state,
 * `prepareActivation` prepares navigation to the revision a state names; the arrival
 * landing; the menu readings the composing surface and the
 * margin take (`closeVersionMenu`, `comparisonBase`,
 * `comparisonChanges`, and the pair the margin's Change reading discloses with,
 * `inlineComparison` and `toggleInlineComparison`); `readingBlock`, the block the decision
 * walk and the command reference start from; and `captureReturnPlace`, the control or
 * reading landmark a keyboard entry returns to.
 *
 * A comparison has two depths and both are this owner's. The marks say which blocks
 * changed; the inline comparison splices dropped text into one of them and paints its
 * added text in place. The second is per block and asked for, because a page's
 * worth of before-and-after opened at once is a diff view rather than the version the
 * reader chose to read. Nothing else shows a base version's words: this is the one place
 * that document is ever in hand.
 *
 * One surface owns each destination. The version control opens the complete version list
 * with notes and comparison controls. There are no separate older/newer page keys. A
 * comparison base is the focused row in the menu; opening the menu lands on the current
 * base, and walking to the version being read clears the comparison because it has no
 * earlier base to mark against.
 *
 * A live revision arrives through one door, `prepareActivation`, with two installs
 * behind it, and one server fact decides which. Each revision's delivery states the
 * digest of what it is as running code — registry, module graph, inline module bodies —
 * and the state naming the next revision carries the same digest for it. Equal, and the
 * revision is taken on in the document the reader is standing in: the authored page is
 * patched onto the arriving source, the widgets it rewrote are recaptured, and the rest
 * of the document is untouched. Different, and it opens a fresh one, because a live
 * document cannot re-evaluate a module graph or redefine a custom element. Content,
 * prose, styling, and media are not executable and cost nobody a reload.
 *
 * `midComposition`, an unresolved delivery, or an open version menu defers either
 * install and leaves the newest-version chip visible. Ending composition releases it on
 * the next heartbeat; pressing the chip explicitly releases the composition hold.
 * `goActive` is that door and the way back from a pinned document; `goVersion` opens an
 * older public version.
 *
 * What a patch keeps, it keeps by keeping the node: caret, native selection, hover,
 * scroll, focus, an armed key sequence over the ids in front of the reader, and every
 * widget the revision left word-for-word alone, with the state the log gave it. Nothing
 * is carried across anything, because nothing crosses. The reading landmark and the
 * standing comparison are still recorded, because content above the reader can change
 * height and the base document is another fetch.
 *
 * An older version is historical rather than live: choosing one navigates to its virtual
 * version address with `?pin`, and it stays at the revision it was pinned at while
 * offering the newest-version chip. The view record carries reading position and the
 * decision-walk landmark across navigation. A reload install additionally carries a
 * one-use handoff containing that reading, the standing comparison, the pointer, and the
 * margin's own retained standing, which is keyed by the entries and owners it names
 * rather than by where anything sat. Focus on the page is not in it: an authored control
 * has no identity a new document could be sure it had found again, only a shape — an
 * owner's id, a tag, a class, a count among its siblings, a string of its words — and a
 * guess that lands on the wrong control hands it the reader's next press. Focus goes to
 * the page instead, where its keys are live. Explicit historical travel carries neither
 * focus nor a selection. Durable drafts and stored chrome arrangement use their existing
 * stores. Native selections and arbitrary module state never cross documents.
 *
 * The handoff is scoped to this page and consumed once, even when a newer revision
 * overtakes the one that triggered navigation. Ordinary reloads and history travel
 * cannot replay an old focus handoff. State responses serialize at the application
 * boundary; after navigation begins the old application stays pending until its
 * document is discarded.
 *
 * `captureView` stores a passage-based reading landmark, correction within the block,
 * and the last decision landmark. `restoreView` resolves the landmark after upgrade and
 * corrects the scroll from the rendered box. It retains an ordinary passage's exact
 * viewport coordinate; capture normalizes a heading to its scroller's declared
 * scroll-padding edge, because a title with opening lines behind fixed chrome is not a
 * valid semantic view to carry into another document. A URL fragment outranks the saved
 * view on a fresh navigation; the saved view outranks a leftover fragment on reload or
 * back navigation. `landArrival` applies that ranking only after final page geometry is
 * available.
 *
 * Neither install claims the reader still stands on a control. A patch does not have to
 * claim it: focus the revision did not disturb was never lost, because the control is
 * the same element. A reload cannot, so it does not try.
 *
 * Served identity is read before boot mutates the document, and it includes what each
 * declared widget in this page was written as, one digest per id, decided by the capture
 * that wrote the revision. A patch keeps the widgets the arriving revision spells the
 * same way. The page cannot answer that for itself — after upgrade a controller owns
 * every widget's children — and does not have to: both maps arrive in a document head,
 * this one at boot and the other inside the revision document a patch already fetches.
 *
 * A layer also owes a way out at all, over the same page the way in is live on.
 * `versionsOffered` (there is a menu) answers for the destination, the chooser standing over
 * the page, and the button; `versionsToWalk` (there is somewhere to step) answers for the
 * menu's own scope. One predicate for both left `g V` opening a menu on a page whose way
 * out no scope was live over. Where the platform owns the dismissal the chooser's own rows
 * still have to be live over the same page, since a chooser with no live row is a claim the
 * surfaces never hear. A section merges the rows of every scope sharing its title, so a
 * contributor the page hasn't got must bring none — `merge` drops it — or the two
 * capabilities cannot differ in liveness under one heading.
 *
 * Served identity is captured before boot mutates the document. The controller receives
 * application and travel capabilities;
 * mount binds chooser/intent listeners and paints the initial version reading.
 * installArrival remains the later geometry-ready continuity boundary.
 */
import { revisionLabel, runtime } from "./context.js";
import {
  documentWidgetDigests,
  servedExecutable,
  servedWidgets,
} from "./document-identity.js";

import { patchTree } from "./dom-children.js";
import { clippedRect, shownBox } from "./geometry.js";
import { PRESS } from "./keyboard/bindings.js";
import { focused, keys, paintKeys, pruneScopedElements } from "./keyboard/scopes.js";
import { repaint } from "./repaint.js";
import { notice } from "./notifications.js";
import {
  authored,
  closestAcross,
  containsAcross,
  cut,
  elementById,
  inChrome,
  pageText,
  quoteFrom,
  readingFrom,
  rangeOf,
  TEXT_BLOCK,
  textNodesUnder,
  wrote,
} from "./passages.js";
import { registry, stateSpecs, tagsDeclaring } from "./registry.js";
import { targetElement, targetSegments } from "./resolved-target.js";
import { moveScrollerBy, pageScroller } from "./scrolling.js";
import {
  containingReadingRegionFor,
  effectiveScroller,
  readingPosture,
  readingRegionFor,
  readingRegions,
  shownRegionBounds,
  watchReadingRegionTransitions,
} from "./reading-regions.js";
import { LIVE_ROOT, PAGE_SCOPE, tabStore, versionUrl } from "./storage.js";
import { alignInlineText } from "./text-alignment.js";
import { el, layoutChanged, quoted, reveal } from "./widget-elements.js";
import { foldShelf, reserveNewsSlot, showNews } from "./banner-shelf.js";
import { allButCommandReference } from "./keyboard/register.js";
import { pointerAt, restorePointer } from "./pointer.js";

import { reportPageError, sameDelivery } from "./layer-client.js";
import { projectView, readApplication } from "./semantic-state.js";

import { anchoringIsReady, fragmentId, resolveAnchor } from "./anchor-resolution.js";
import { beginWalk } from "./walk-position.js";
import {
  domFacet,
  rememberAuthoredParents,
  stageAuthoredFacets,
  stateCoordinate,
} from "./projection/authored.js";
import { whenApplicationRegionsPresented } from "./semantic-state.js";
import { MARKED_IN_PAGE, markDeclared, settlePageInterface } from "./presentation.js";
import { runtimeRootState } from "./root-state.js";
import {
  commitWidgetDescriptors,
  stageWidgetDescriptors,
} from "./widget-descriptors.js";
import {
  latestChip,
  latestVersionLabel,
  versionBtn,
  versionChooser,
  versionMenu,
  versionMenuIsOpen,
} from "./version-chooser.js";
import {
  importWidgets,
  patchDocument,
  reindexPassageOwners,
  rememberPassageParts,
} from "./widget-loader.js";

const PRIVATE_REVISION_PARAM = "_leaf-revision";

// The document roots may carry authored classes, data attributes, and inline custom
// properties that page-local styles read. The live document also paints its own facts
// onto those same two elements. Most arrive after this module, but the server's prepaint
// bootstrap deliberately runs before the module graph and has already written the live
// shell and provisional reader layout. Authored markup cannot use the `data-lf-` or
// `lf-` namespaces, so that boundary identifies the authored share without mistaking
// early runtime state for page source. An activation can then replace exactly that share
// without erasing the presentation, layout, and mode facts the surviving runtime owns.
function authoredAttributes(root) {
  const attributes = new Map();
  for (const { name, value } of root.attributes) {
    if (name.startsWith("data-lf-")) continue;
    if (name === "class") {
      const authoredClasses = [...root.classList]
        .filter((token) => !token.startsWith("lf-"))
        .join(" ");
      if (authoredClasses) attributes.set(name, authoredClasses);
    } else attributes.set(name, value);
  }
  return attributes;
}
// The authored share of the head, which a revision brings with it. Delivery marks
// what it inserts — the identity markers, the page's canonical address, a
// publication's card — and that share belongs to the document the reader was
// served rather than to the revision arriving inside it.
const versionedHeadNode = (node) =>
  !node.hasAttribute("data-lf-runtime") &&
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
// This document as its author wrote it, kept inert beside the page it became. A patch
// applies the difference between two revisions, so it needs the revision the page is
// standing on as source — not the page, which by then carries a tokenizer's spans, a
// reader's open disclosure, a tab stop the runtime lent, and whatever a page module
// built. The module graph can define chrome-only elements before this clone, but authored
// markup cannot contain those tags, so the authored main is still untouched. Runtime-owned
// head nodes carry `data-lf-runtime` and are excluded from the separate head baseline above.
// The source and live main are therefore the same tree, which makes the pairing below a
// plain walk of the two together.
const pairSources = (source, live, pairs) => {
  pairs.set(source, live);
  const held = source.localName === "template" ? source.content : source;
  const shown = live.localName === "template" ? live.content : live;
  const children = [...shown.childNodes];
  for (const [at, child] of [...held.childNodes].entries())
    if (children[at]) pairSources(child, children[at], pairs);
  return pairs;
};
// Where a delivered document's captured resources are addressed: the directory its
// registry probe names, which is the revision's own root.
const artifactRoot = (root) =>
  root
    .querySelector("script[data-lf-runtime][data-lf-probe]")
    ?.dataset.lfProbe.replace(/registry\.json$/, "") ?? "";
const servedMain = document.querySelector("body > main");
const initialDocument = {
  authoredBodyAttributes: authoredAttributes(document.body),
  authoredHeadNodes: new Set([...document.head.children].filter(versionedHeadNode)),
  authoredHtmlAttributes: authoredAttributes(document.documentElement),
  source: servedMain?.cloneNode(true) ?? null,
};
const initialPairs = servedMain
  ? pairSources(initialDocument.source, servedMain, new WeakMap())
  : new WeakMap();

export function createVersionController({
  midComposition,
  hasPending,
  readAndApply,
  banner,
  landedAt,
  setLanded,
  readableDestination,
  scrollToElement,
  forgetAuthoredOwners,
  retireProjectionCoverage,
  syncLayout,
  captureRetainedStanding = () => null,
  restoreRetainedStanding = () => false,
}) {
  let { authoredBodyAttributes, authoredHeadNodes, authoredHtmlAttributes } =
    initialDocument;
  // What this document's widgets were written as, and the source each live node stands
  // for. Both are replaced by every revision this document takes on.
  let authoredWidgets = servedWidgets;
  let authoredSource = initialDocument.source;
  let authoredRoot = artifactRoot(document);
  let sourcePairs = initialPairs;
  // Semantic reading position preserved across authored-document replacement.
  const VIEW_KEY = "lf-view";
  const HANDOFF_KEY = "lf-revision-handoff";
  const LANDMARK_CAP = 160;
  const HEADING = "h1, h2, h3, h4, h5, h6";

  // ---------- the version chooser ----------
  // Version facts are selectors of the accepted application reading.
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
  // The closed control is a destination, not the menu's account of the working document.
  // Keep it to one stable version token (or Draft) through disclosure and comparison;
  // those states remain in the menu, class, title, and accessible name. A state arriving
  // on the poll therefore cannot resize this control and displace controls to its left.
  // The chooser view reserves this compact token range once at load.
  const currentVersionToken = () =>
    runtime.currentStamp === null ? "Draft" : `v${runtime.currentStamp}`;

  // Whether there is a menu to open is not whether there is anywhere to walk: a first
  // version has no neighbour, but its menu still explains that version. The browser owns
  // dismissal; Leaf enables its version-walk bindings only when a neighbouring destination
  // exists.
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
  const behindCurrent = () =>
    runtime.active !== null &&
    runtime.currentRevision !== null &&
    runtime.active.revision !== runtime.currentRevision;
  let offeredBefore = null;
  // A menu is a transient reading of the chooser, not a layer over the next control a
  // reader Tabs to. Its comparison checkboxes are real internal Tab stops, so offer an
  // exit only from the boundary control in the direction being travelled. The native row
  // below closes the menu first and then leaves the browser to complete that same Tab.
  const atVersionBoundary = (end) => versionChooser.atBoundary(end);

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
    versionChooser.close();
  }

  const numberedVersionRoutes = () => versionChooser.numberedRoutes();
  const OPEN_NUMBER = {
    id: "version.open-number",
    keys: () => numberedVersionRoutes().map(({ binding }) => binding),
    routes: numberedVersionRoutes,
    label: () => {
      const routes = numberedVersionRoutes();
      return routes.length > 1
        ? `${routes[0].binding}–${routes.at(-1).binding}`
        : routes[0]?.binding;
    },
    does: "Open a numbered version",
    line: "open version",
    when: () => versionsToWalk() && numberedVersionRoutes().length > 0,
    // The focused menu and its standing chooser share this route. The first gives g V a
    // visible compact hint; the second preserves the key across a browser hand-back that
    // leaves the menu open with focus at its door. Close first, as the numbered key is the
    // keyboard form of pressing that row; this matters when it names the version already
    // being read and travel itself is a no-op.
    run: (binding) => {
      closeVersionMenu();
      goVersion(+binding);
    },
  };
  // The menu's own scope. The walk is the menu's rather than the page's, because ArrowUp and
  // ArrowDown anywhere else are the page's own scroll; ⏎ is the browser's, a row being a
  // button, and the row says so with no `run`. A row's Compare is the same comparison for the
  // pointer, which has no walk to state it with. Exact number keys are shared with the
  // standing menu chooser below, so they stay visible in this focused scope and survive a
  // browser hand-back that lands at its door.
  //
  // v is the one row worth a key of its own: the current page is where the walk ends, and
  // where a reader who came for the current state is going. It is local to the menu, so the
  // page-level destination remains the complete `g V` route rather than a second meaning for
  // a bare letter.
  //
  // This scope is live only while there is a list to walk. The chooser below stays live for
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
  const VERSION_WALK = {
    id: "version.walk",
    keys: ["ArrowUp", "ArrowDown"],
    routes: [
      { id: "version.later", binding: "ArrowUp", does: "Later version" },
      { id: "version.earlier", binding: "ArrowDown", does: "Earlier version" },
    ],
    // The walk marks as it goes, which is what the list is for: the note says in words
    // what a version changed and the page behind the menu then says it in the passages
    // themselves, without the reader having to leave the list to find out. A note is
    // Claude's sentence about a version and the marks are the version's own account of
    // itself, so reading them together is the only way to tell the two apart.
    does: "Walk the versions, marking what changed since the one you are on",
    line: "walk — marking changes",
    repeat: true,
    when: versionsToWalk,
    run: (binding) => {
      const was = document.activeElement;
      const row = versionChooser.walk(binding === "ArrowDown" ? 1 : -1);
      if (!row) return;
      beginWalk("version", "Version", () => versionChooser.walkPosition());
      // A press at either end lands on the row it started from, and now that the walk
      // states a comparison, landing is not free — it would re-fetch the base and say
      // its count again for a press that moved nothing.
      if (row === was) return;
      // The comparison the row states: its own version as the base, or none at all where
      // that version is not older than the one being read. So the reader walks down to mark
      // from further back and back up to stop, and the row that stops it is the version
      // they are reading — the end of the walk in the direction they came from, which is
      // why it needs no key of its own and no reader has to be told where it is — and,
      // the page having no key for a comparison, the whole of the way off one.
      const version = +row.dataset.lfVersion;
      if (comparable(version)) showComparison(version);
      else setDiff(false);
    },
  };

  // The chooser represents the menu standing, not whether it has multiple versions to walk.
  // It suspends page shortcuts and owns exact numbered destinations plus the Tab-boundary
  // handoff that a popover does not provide. A keyboard-opened menu has CHOOSER's exact
  // return frame; light dismissal stays native for pointer-opened menus, and their Escape
  // is named by the menu's own row (`version.close`), which runs the same close.
  const VERSIONS = {
    title: "In the versions menu",
    root: () => versionMenu,
    when: versionsOffered,
    at: versionMenuIsOpen,
    // Opening the modal reference dismisses this popover. Retain the menu-boundary
    // reading so the reference filters member-dependent rows by their actual liveness.
    liveInCommandReference: true,
    // A chooser over the page suspends the page, which the two transient contexts above this one always did
    // and this one did not — so a reader in the middle of choosing a version could press `l`
    // and take focus out of the menu into the leaves tray, `d` and scroll a page they were
    // not looking at, or `c` and open the composer under the list. None of it fails loudly:
    // the press does exactly what it says on a page the reader has stopped reading. The
    // worst of them was a page-level key that set a comparison base, which the walk they
    // were standing in then disagreed with — that key is the menu's own business now, and
    // the claim is what would have held it either way. The claim is also what narrows
    // the line to the menu's own keys, so what the chooser takes and what it offers are one
    // statement rather than a suspension the surfaces have to be told about separately.
    claims: allButCommandReference,
    rows: [
      VERSION_WALK,
      OPEN_NUMBER,
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
      // A pointer-opened menu closes on the platform's own Escape, and the line said
      // nothing about it: the page's Escape rung stands down under an open popover
      // (browserDismissesTopLayer) and the return frame only exists for a keyboard entry.
      // The row names the press; RETURN stands nearer in the scope order and takes the key
      // whenever a frame is live, so "back" and "close" never print together.
      {
        id: "version.close",
        keys: ["Escape"],
        does: "Close the versions menu",
        line: "close",
        // Exact travel is the menu's unfamiliar action and keeps the compact line's
        // second slot from either door. Escape remains live and stays in the complete
        // reference as the platform-standard close.
        promoteEscape: false,
        native: true,
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
      // Arrow comparison and exact numbered travel are the two unfamiliar menu actions;
      // keep both on the compact line. Escape remains the platform-standard way back and
      // stays in the complete reference.
      promoteEscape: false,
    }),
    run: () => versionBtn.click(),
  };

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
      note: notes[entry.version] ?? null,
      current: entry.version === runtime.currentStamp,
      active: false,
      comparable: comparable(entry.version),
    }));
    for (const revision of draftRevisions()) {
      const active = revision === state.active.revision;
      entries.push({
        revision,
        version: null,
        name: `${active ? "Current" : "This view"} · ${
          revision === runtime.currentRevision
            ? (runtime.currentLabel ?? revisionLabel(revision))
            : state.active.label
        }`,
        note: null,
        current: revision === runtime.currentRevision,
        active,
        comparable: false,
      });
    }
    entries.sort(
      (left, right) =>
        right.revision - left.revision ||
        (right.version ?? Infinity) - (left.version ?? Infinity),
    );
    return Object.freeze(entries.map((entry) => Object.freeze(entry)));
  }
  // One immutable, complete presentation reading for the native chooser surfaces. The
  // view deliberately retains the rows it is already showing while its popover stands;
  // the candidate rows below keep advancing, so dismissal can commit them without
  // replaying an accepted state or consulting the rendered DOM as authority.
  function chooserModel(state) {
    const offered = state !== null && versionsOffered();
    const behind = behindCurrent();
    const sourceFailed = LIVE_ROOT && Boolean(state?.source_error);
    const currentLabel = runtime.currentLabel ?? "Draft";
    const newer = behind ? `; ${runtime.active.label} available` : "";
    return Object.freeze({
      chooser: Object.freeze({
        offered,
        token: currentVersionToken(),
        compared: diffOn || diffPendingBase !== null,
        news: behind,
        keyTitle: offered
          ? diffPendingBase !== null
            ? `${currentLabel}: loading a comparison with v${diffPendingBase}${newer}`
            : diffOn
              ? `${currentLabel}: showing what changed since v${diffBase} — pick a version, or press Compare again to stop${newer}`
              : `${currentLabel}: versions; read one, or mark what changed since it${newer}`
          : currentLabel,
        ariaLabel: offered
          ? diffPendingBase !== null
            ? `${currentLabel}: loading comparison with v${diffPendingBase}; open versions${newer}`
            : diffOn
              ? `${currentLabel}: comparing with v${diffBase}; open versions${newer}`
              : `${currentLabel}: open versions${newer}`
          : currentLabel,
      }),
      latest: Object.freeze({
        disabled: sourceFailed,
        keyTitle: sourceFailed ? state.source_error : "Open the current page",
        label: latestVersionLabel({
          failed: sourceFailed,
          activeLabel: behind ? runtime.active.label : null,
        }),
        news: sourceFailed || behind,
      }),
      rows:
        state === null || runtime.active === null
          ? Object.freeze([])
          : menuRows(state, runtime.browser?.version_notes ?? {}),
      selection: Object.freeze({
        base: diffPendingBase ?? (diffOn ? diffBase : null),
        currentRevision: runtime.currentRevision,
        on: diffOn,
        pendingBase: diffPendingBase,
        baseRevision: stamped(diffBase)?.revision ?? null,
      }),
    });
  }

  function presentChooser(state = runtime.state) {
    const model = chooserModel(state);
    versionChooser.present(model);
    showNews(latestChip, model.latest.news);
    repaint();
    return model;
  }

  // `null` is the page before its first accepted state. Version controls read the
  // immutable document revision and the accepted root.
  function renderVersions(state) {
    const model = presentChooser(state);
    const offered = model.chooser.offered;
    const walkable = versionsToWalk();
    if (walkable !== versionsWalkable) {
      versionsWalkable = walkable;
      paintKeys();
    }
    if (state !== null && offered !== offeredBefore) {
      offeredBefore = offered;
      foldShelf();
    }
  }

  // ---------- version diff ----------
  // "Changes since vN": blocks (paragraphs, list items, Leaf elements) whose text
  // isn't present in the base version get a tinted marker, so re-reading a
  // revision is cheap. Block-level and additions-only — deleted text has no home
  // to mark — and a widget that renders its own body is opaque to it. The base is
  // any version older than the one being read, offered by its own row in the
  // chooser's menu, where the note saying what changed in words sits beside the
  // press that marks it on the page.
  //
  // Which blocks and which widgets is the registry's answer both times, so a widget added
  // to the vocabulary diffs on the strength of its declaration: a compound member whose content
  // model is prose is a block of the page's prose the same way a paragraph is.
  const diffBlockSel = () =>
    [
      TEXT_BLOCK,
      "aside",
      ...tagsDeclaring(
        (e) => e["x-owners"] && (e["x-content"] ?? "markup") === "markup",
      ),
      // Preserving widgets contribute their own prose. The leaf-blocks-only rule
      // below avoids counting nested blocks twice and keeps base and live readings
      // symmetric: a draft's authored <pre> and rendered body key the same words.
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
      // flatMap, so the set holds owner tags rather than the arrays naming them: a set
      // of arrays never dedupes, two array objects never being equal.
      ...new Set(
        tagsDeclaring((e) => e["x-retired-when"]).flatMap(
          (tag) => registry[tag]["x-owners"],
        ),
      ),
      "svg",
    ].join(",");
  // What is being compared, and whether the comparison is standing. Every rendering of
  // the pair — the chooser's word and paint, each row's press, the rail down the span —
  // comes from the immutable chooser model and is read back by nothing.
  let diffBase = null;
  let diffOn = false;
  let diffPendingBase = null;
  const diffMarked = [];
  // What each marked block said in the base version, and which of those readings the
  // reader has open. The marks say a block changed; these say what it changed from, at
  // the block, so learning it costs no travel to the other version and back.
  //
  // Identity across versions is the id — the fact threads and reading position already
  // ride, and the same lookup the state half of applyDiff resolves its units by. A block
  // with no id names nothing in the base document, so the comparison holds nothing for it
  // and its Change reading stays the plain travel it always was. An opaque widget holds
  // nothing either, and for the reason the pass keys those by identity rather than by
  // words: the live one is upgraded and the base one is not, so their texts were never
  // each other's to compare.
  const diffBefore = new Map(); // marked element -> the base version's words, or null
  const inlineOpen = new Map(); // marked element -> its generated nodes and highlight ranges
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
    if (!sameDelivery(res)) return null;
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
    const baseProjection = projectView(baseView, baseReading.conversation);
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
    // One pass over everything marked, after both halves, because the two halves mark
    // for different reasons and a block reached by either is a block a reader can ask
    // about. The words are taken here rather than at the press: this is the one moment
    // the base document is in hand, and holding it open for a press that may never come
    // would keep a whole second document alive for the life of the comparison.
    const opaque = diffOpaqueSel();
    for (const block of diffMarked) {
      if (!block.id || block.closest(opaque)) continue;
      const baseBlock = doc.getElementById(block.id);
      diffBefore.set(block, baseBlock ? wrote(baseBlock) : null);
    }
    return diffMarked.length;
  }
  // ---------- one marked block's inline comparison ----------
  // `wrote` is the authority for the two texts. This companion reading keeps the same
  // normalized text with a boundary back into the authored text nodes, so a run the
  // alignment calls inserted can be painted in place. Generated labels and deletions wear
  // `.lf-ui`; comments, copies, and later comparisons therefore continue to read the exact
  // current document rather than the temporary historical words on screen.
  const inlineId = (target) => `lf-version-inline-${target.id}`;
  const authoredReading = (target) =>
    readingFrom(textNodesUnder(target, authored(target)));

  function pointAt(target, reading, offset) {
    if (!reading.units.length) return { node: target, offset: 0 };
    return offset === reading.units.length
      ? reading.units.at(-1).end
      : reading.units[offset].start;
  }

  function insertAt(target, reading, offset, node) {
    const point = pointAt(target, reading, offset);
    if (point.node.nodeType === Node.ELEMENT_NODE) {
      point.node.insertBefore(node, point.node.childNodes[point.offset] ?? null);
      return;
    }
    const text = point.node;
    if (point.offset === 0) text.parentNode.insertBefore(node, text);
    else if (point.offset === text.data.length)
      text.parentNode.insertBefore(node, text.nextSibling);
    else text.parentNode.insertBefore(node, text.splitText(point.offset));
  }

  function rangeAt(reading, start, end) {
    const first = reading.units[start];
    const last = reading.units[end - 1];
    if (!first || !last) return null;
    const range = document.createRange();
    range.setStart(first.start.node, first.start.offset);
    range.setEnd(last.end.node, last.end.offset);
    return range;
  }

  function paintInlineInsertions() {
    const ranges = [...inlineOpen.values()].flatMap((entry) => entry.ranges);
    if (ranges.length)
      CSS.highlights.set("lf-version-insert", new Highlight(...ranges));
    else CSS.highlights.delete("lf-version-insert");
  }

  function openInlineComparison(target) {
    const before = diffBefore.get(target);
    const reading = authoredReading(target);
    const current = currentVersionToken();
    const label = el(
      "span",
      "lf-ui lf-quiet lf-version-inline-label",
      before === null ? `New since v${diffBase}` : `v${diffBase} → ${current}`,
    );
    label.id = inlineId(target);
    label.setAttribute(
      "aria-label",
      before === null
        ? `New since version ${diffBase}`
        : `Inline comparison from version ${diffBase} to ${current}`,
    );

    const nodes = [label];
    const additions = [];
    const insertions = [{ offset: 0, node: label }];
    let afterOffset = 0;
    let hasTextChange = false;
    for (const run of before === null ? [] : alignInlineText(before, reading.text)) {
      if (run.kind === "delete") {
        const dropped = el("span", "lf-ui lf-version-inline-deletion");
        dropped.append(el("del", "", run.text));
        nodes.push(dropped);
        insertions.push({ offset: afterOffset, node: dropped });
        hasTextChange = true;
      } else {
        // The passage reading indexes characters by code point while DOM Range offsets
        // are UTF-16. Keep the alignment cursor in the reading's units; an astral
        // character must advance it once, not by the two code units String.length sees.
        const length = [...run.text].length;
        if (run.kind === "insert") {
          additions.push([afterOffset, afterOffset + length]);
          hasTextChange = true;
        }
        afterOffset += length;
      }
    }
    insertions
      .sort((left, right) => right.offset - left.offset)
      .forEach(({ offset, node }) => insertAt(target, reading, offset, node));

    const currentReading = authoredReading(target);
    const ranges = additions
      .map(([start, end]) => rangeAt(currentReading, start, end))
      .filter(Boolean);
    target.classList.toggle("lf-version-inline", hasTextChange);
    inlineOpen.set(target, { nodes, ranges });
    paintInlineInsertions();
    layoutChanged(target);
    return before === null
      ? `v${diffBase} had nothing here`
      : `showing an inline diff from v${diffBase}`;
  }

  function closeInlineComparison(target) {
    const entry = inlineOpen.get(target);
    inlineOpen.delete(target);
    target.classList.remove("lf-version-inline");
    for (const node of entry?.nodes ?? []) node.remove();
    paintInlineInsertions();
    layoutChanged(target);
    return `inline diff from v${diffBase} hidden`;
  }

  // What a text-changing marked block holds for the margin's disclosure reading. A pure
  // state change remains marked but offers no empty prose comparison. The one controlled
  // id is a quiet label at the start of the block. It names the versions for assistive
  // reading while the margin and Page Map carry that provenance visually, outside the
  // passage whose words are being compared.
  const inlineComparison = (target) =>
    diffOn &&
    diffBefore.has(target) &&
    (diffBefore.get(target) === null || diffBefore.get(target) !== wrote(target))
      ? {
          id: inlineId(target),
          open: inlineOpen.has(target),
          offer: `v${diffBase} → ${currentVersionToken()}`,
        }
      : null;

  // The press, and the sentence to say about it — composed here, where the versions are
  // named. The event is the comparison's, because what changed is its standing
  // rendering: the same pass that reads the marks reads the margin entry's relation back.
  function toggleInlineComparison(target) {
    if (!inlineComparison(target)) return null;
    const said = inlineOpen.has(target)
      ? closeInlineComparison(target)
      : openInlineComparison(target);
    document.dispatchEvent(new CustomEvent("lf-comparison"));
    return said;
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
  // Whether the comparison is standing and what against — the only thing that decides
  // it, the marks and the paint being renderings rather than a second copy.
  function setDiff(on, base) {
    diffOn = on;
    diffPendingBase = null;
    if (on) diffBase = base;
    if (!on) {
      diffRequest++; // a stop outranks a comparison still on its way
      // Inline diffs leave with the block marks. Historical words or insertion paint
      // under a block nothing marks any more would leave half of the comparison behind.
      for (const target of [...inlineOpen.keys()]) closeInlineComparison(target);
      diffBefore.clear();
      for (const b of diffMarked) b.classList.remove("lf-ins-block");
      diffMarked.length = 0;
    }
    presentChooser();
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
    // Selection is immediate even though its result needs two documents. Clear the prior
    // marks, move the menu's checked state to the requested base, and expose the wait as
    // busy. A fast walk then never leaves the last completed base highlighted under focus
    // on a different row.
    setDiff(false);
    const mine = ++diffRequest;
    diffPendingBase = base;
    presentChooser();
    const baseRevision = stamped(base)?.revision;
    if (baseRevision == null) {
      diffPendingBase = null;
      presentChooser();
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
      if (mine === diffRequest) {
        diffPendingBase = null;
        presentChooser();
        notice(`Couldn't load v${base}`);
      }
      return;
    }
    if (mine !== diffRequest) return;
    const n = applyDiff(doc, base, reading);
    setDiff(true, base);
    notice(
      n
        ? `${n} changed passage${n === 1 ? "" : "s"} since v${base}`
        : `No text changes since v${base}`,
    );
  }
  // A press names one base, so pressing the standing one again is the way off it: Compare is a
  // toggle where it is lit and a switch of base where it isn't. The keyboard's way off is the
  // walk itself — up to the version being read, which is comparable with nothing and so
  // stops rather than re-bases.
  const pressComparison = (base) =>
    (diffOn && base === diffBase) || diffPendingBase === base
      ? setDiff(false)
      : showComparison(base);

  const comparisonBase = () => (diffOn ? diffBase : null);
  // Selection leads the documents it needs. Menu focus follows that immediate reading,
  // while the public projection above stays paired with the marks that have settled.
  const selectedBase = () => diffPendingBase ?? comparisonBase();
  const comparisonChanges = () => (diffOn ? [...diffMarked] : []);

  // ---------- another version's document ----------
  // Comparison reads an inert document. A different delivery generation already starts
  // navigation through sameDelivery, so the departing runtime must not use that reading.
  async function authoredDocument(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`couldn't load ${url} (${response.status})`);
    if (!sameDelivery(response)) return null;
    const doc = new DOMParser().parseFromString(await response.text(), "text/html");
    if (doc.querySelectorAll("body > main").length !== 1)
      throw new Error(`${url} has no single authored main`);
    return doc;
  }
  // Repeated comparisons of the same immutable revision share its document fetch.
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
    const runtimeState = runtimeRootState(target);
    for (const name of prior.keys()) {
      if (name === "class")
        for (const token of scratch.classList) target.classList.remove(token);
      else if (name === "style")
        for (const property of scratch.style) {
          // Inline style is the one root attribute whose members can have different
          // owners. Registered runtime properties survive; every other declaration is
          // authored and retires with its revision like every other source attribute.
          if (!runtimeState.styles.has(property)) target.style.removeProperty(property);
        }
      else if (!runtimeState.attributes.has(name)) target.removeAttribute(name);
    }
    const next = authoredAttributes(source);
    for (const [name, value] of next) {
      if (name === "class") {
        for (const token of value.split(" ")) target.classList.add(token);
      } else if (name === "style") {
        for (const property of source.style)
          if (!runtimeState.styles.has(property))
            target.style.setProperty(
              property,
              source.style.getPropertyValue(property),
              source.style.getPropertyPriority(property),
            );
      } else if (!runtimeState.attributes.has(name)) target.setAttribute(name, value);
    }
    return next;
  }

  // The chrome's sheets are adopted, not head nodes, so they cascade after everything
  // the head holds whatever order it is written in; the authored share goes at the end.
  function activateHead(doc, revision) {
    for (const node of authoredHeadNodes) node.remove();
    const next = new Set();
    for (const node of doc.head.children) {
      if (!versionedHeadNode(node)) continue;
      const imported = document.importNode(node, true);
      document.head.append(imported);
      next.add(imported);
    }
    authoredHeadNodes = next;
    let marker = document.querySelector('meta[name="lf-revision"][data-lf-runtime]');
    if (!marker) {
      marker = document.createElement("meta");
      marker.name = "lf-revision";
      marker.dataset.lfRuntime = "1";
      document.head.append(marker);
    }
    marker.content = String(revision.revision);
  }

  const upgraded = (element) => Boolean(registry[element.localName]?.["x-upgrade"]);

  // Every declared widget in one revision's authored page, named the way its capture
  // named it: by id where the author gave one, and otherwise by tag and place among the
  // others of that tag. An unnamed widget is as much the reader's as a named one, and
  // without a key of its own it could never answer that its markup was unchanged, so
  // every revision rebuilt it — taking with it whatever the reader had open in it.
  function widgetKeys(source) {
    const keys = new Map();
    const counts = new Map();
    for (const element of elementsWithin(source)) {
      if (!upgraded(element)) continue;
      if (element.id) keys.set(element, element.id);
      else {
        const seen = counts.get(element.localName) ?? 0;
        counts.set(element.localName, seen + 1);
        keys.set(element, `${element.localName}#${seen}`);
      }
    }
    return keys;
  }

  // Every element under a root in document order, a template's content included: the
  // capture walks the parsed tree the same way, and a widget written inside a template
  // counts among the others of its tag on both sides or on neither.
  function* elementsWithin(root) {
    const inner = root.localName === "template" ? root.content : root;
    for (const child of inner.children) {
      yield child;
      yield* elementsWithin(child);
    }
  }

  // Two source elements spelled the same way once the address each revision was
  // delivered at is read out of them. Delivery writes the revision's own root into every
  // page and media reference, so the same `<img>` differs between two revisions that
  // never touched it; a widget's capture digested the markup before that, and this is
  // the same reading for an element no capture digested.
  const RESOURCE_ATTRIBUTES = ["src", "href", "srcset", "poster", "data", "style"];
  const unrooted = (value, root) =>
    root && value.includes(root) ? value.split(root).join("/") : value;
  // One attribute, read the same way: an address that differs only by the revision it
  // was delivered under is the same address, and the page keeps the one it has, which
  // is still served because revisions are immutable.
  const sameValue = (name, held, value, arrivingRoot) =>
    RESOURCE_ATTRIBUTES.includes(name)
      ? unrooted(held, authoredRoot) === unrooted(value, arrivingRoot)
      : held === value;
  function sameAuthoredMarkup(before, after, arrivingRoot) {
    const strip = (element, root) => {
      const copy = element.cloneNode(true);
      if (!root) return copy;
      for (const node of [copy, ...elementsWithin(copy)])
        for (const name of RESOURCE_ATTRIBUTES) {
          const value = node.getAttribute(name);
          if (value?.includes(root)) node.setAttribute(name, unrooted(value, root));
        }
      return copy;
    };
    return strip(before, authoredRoot).isEqualNode(strip(after, arrivingRoot));
  }

  // The revision arriving in the document the reader is standing in. Their caret,
  // selection, parked pointer, focus and armed key sequence live on the nodes they are
  // over, so the page keeps every node this revision did not rewrite and nothing has to
  // be carried across anything.
  async function activateRevision(doc, target) {
    const view = captureView();
    // A pending selection is standing too: cancel its old-document request before the
    // authored page changes, then restore that base against the arriving revision.
    const comparedFrom = selectedBase();
    if (comparedFrom !== null) setDiff(false);
    const live = document.querySelector("body > main");
    const source = doc.querySelector("body > main");
    const arrivingWidgets = documentWidgetDigests(doc);
    const arrivingRoot = artifactRoot(doc);
    const heldKeys = widgetKeys(authoredSource);
    const arrivingKeys = widgetKeys(source);
    retireProjectionCoverage();
    revisionDocuments.delete(target.revision);

    // A node with nothing over it is inside a template's content fragment, where a page
    // may hold authored markup and `elementOver` has no element to answer with. Nothing
    // there is the runtime's.
    const isAuthored = authored(live);
    const generated = (node) =>
      (node.nodeType === Node.ELEMENT_NODE || node.parentElement !== null) &&
      !isAuthored(node);
    // Step 5 of the startup order, for the markup this revision brings: read while it is
    // still what its author wrote, because connecting a widget is what hands its children
    // to a controller. The nodes read here are the nodes that end up in the page, and the
    // roots among them are what the install dresses.
    const arrived = [];
    const descriptorStages = [];
    const prior = readApplication().document;
    // The arriving revision's source is the complete page baseline. Capture it before
    // insertion can connect a custom element and turn authored input into presentation.
    rememberAuthoredParents(source);
    const sourceAuthored = stageAuthoredFacets(source, new Map());
    const sourceDescriptors = stageWidgetDescriptors(
      source,
      { kind: "page", revision: target.revision },
      live,
    );
    // Elements whose attributes the patch rewrote in place. What a dressing pass reads
    // off an attribute — a word an element says, the language of a code block — is
    // owed again, and these are the roots the install dresses beside the arrivals.
    const touched = [];
    const arrive = (node, parent) => {
      const arriving = document.importNode(node, true);
      pairSources(node, arriving, sourcePairs);
      if (arriving.nodeType === Node.ELEMENT_NODE) {
        rememberPassageParts(arriving);
        // Stated rather than read, because the node is not in the document yet and
        // the readings below ask where it stands: whether an exhibit quotes it, and
        // which declared elements enclose it.
        rememberAuthoredParents(arriving, parent);
        markDeclared(arriving, MARKED_IN_PAGE);
        const descriptors = stageWidgetDescriptors(
          arriving,
          { kind: "page", revision: target.revision },
          live,
        );
        descriptorStages.push(descriptors);
        // Bind the actual arrival before insertion can synchronously connect its
        // custom element. The publisher still holds the outgoing document until the
        // patch and matching server reading are admitted together, so this descriptor
        // cannot borrow the old widget's semantic state during preparation.
        commitWidgetDescriptors(descriptors);
        arrived.push(arriving);
      }
      return arriving;
    };

    await patchDocument(live, () => {
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
      activateHead(doc, target);
      // The patch pairs what it walks into, and what it is handed stands outside that
      // walk: `main` is the one node whose pairing has to be stated rather than found,
      // and the revision after this one is the patch that reads it.
      sourcePairs.set(source, live);
      patchTree(authoredSource, source, {
        pairs: sourcePairs,
        arrive,
        generated,
        declared: upgraded,
        // The capture that wrote each revision said what every declared widget in it
        // was written as. A widget the arriving revision spells the same way is the
        // widget the reader is holding, so it stays.
        unchanged: (before, after) => {
          const digest = authoredWidgets[heldKeys.get(before)];
          return Boolean(digest) && arrivingWidgets[arrivingKeys.get(after)] === digest;
        },
        same: (before, after) => sameAuthoredMarkup(before, after, arrivingRoot),
        sameValue: (name, held, value) => sameValue(name, held, value, arrivingRoot),
        touched: (element) => touched.push(element),
        // An element going is not the same as its name going. Authored facet capture
        // still needs to forget removed upgraded owners here; the complete incoming
        // descriptor inventory below decides which identities actually retired.
        retire: (element) => {
          if (!element.id || !registry[element.localName]) return;
          for (const claimant of live.querySelectorAll(`#${CSS.escape(element.id)}`))
            if (claimant !== element) return;
          if (upgraded(element)) forgetAuthoredOwners(new Set([element.id]));
        },
      });
      // After the patch, over the document the patch left: an owner's number is its
      // place among the document's preserving owners, and an insertion moves the ones
      // after it.
      reindexPassageOwners(live);
      pruneScopedElements();
      // The roots the install dresses, and the widgets among the arrivals whose
      // rendering and preparation it waits for: what this patch brought, and only that.
      return {
        roots: [...arrived, ...touched],
        widgets: arrived
          .flatMap((root) => [root, ...elementsWithin(root)])
          .filter((element) => upgraded(element) && element.id)
          .map((element) => element.id),
      };
    });
    authoredWidgets = arrivingWidgets;
    authoredSource = source;
    authoredRoot = arrivingRoot;
    await settlePageInterface(() =>
      whenApplicationRegionsPresented(["page-interface"], () => true),
    );
    syncLayout();
    restoreView(view);
    // Focus is not restored, because a patch does not take it: a control the revision
    // kept is the same element, still holding it, with the tab stop it was lent. One the
    // revision replaced drops focus to `body`, where the page's own keys are live, which
    // is the honest answer for a reader whose control the revision took away.
    if (comparedFrom !== null) showComparison(comparedFrom);
    // The same words the fresh document says on arrival. The page changing under a
    // reader is the thing announced, and which install carried it is not their business.
    // Named from the descriptor rather than the current label, which still reads the
    // revision this document is a statement away from leaving.
    notice(`Updated to ${target.label}`, { background: true });
    const authoredFacets = new Map(
      [...prior.authored].filter(
        ([id]) => prior.descriptors.get(id)?.document.kind === "thread",
      ),
    );
    for (const [id, value] of sourceAuthored) authoredFacets.set(id, value);
    const arrivedDescriptors = new Map();
    for (const stage of descriptorStages)
      for (const [id, value] of stage.descriptors) arrivedDescriptors.set(id, value);
    // The incoming source owns page order. Retained controllers keep the descriptor
    // identity captured with their live node; new or rewritten nodes use their arrival
    // capture. Frozen thread documents follow the page in their standing log order.
    const descriptors = new Map();
    for (const [id, incoming] of sourceDescriptors.descriptors)
      descriptors.set(
        id,
        arrivedDescriptors.get(id) ?? prior.descriptors.get(id) ?? incoming,
      );
    for (const [id, descriptor] of prior.descriptors)
      if (descriptor.document.kind === "thread") descriptors.set(id, descriptor);
    const retired = new Set(
      [...prior.descriptors]
        .filter(
          ([id, descriptor]) =>
            descriptor.document.kind === "page" &&
            !sourceDescriptors.descriptors.has(id),
        )
        .map(([id]) => id),
    );
    commitWidgetDescriptors({ bindings: [] }, retired);
    return {
      ...prior,
      revision: target.revision,
      stamp: target.version ?? null,
      authored: authoredFacets,
      descriptors,
    };
  }

  // The move a state asks of the live root, prepared ahead of the commit that makes it.
  // Null where there is nothing to follow — no newer revision, or a document that failed
  // to load, which is reported; the commit's own render then lights the chip as the way
  // to try again. `stale` where the document came from a re-vendored layer, so the page
  // is reloading and the state belongs to the layer it is leaving. Whether the move
  // happens now is asked at the commit: an unresolved delivery, `midComposition`, or an
  // open menu defers it, unless the chip was pressed (goActive) — the one override,
  // spent by the install it forced.
  async function prepareActivation(state) {
    const target = state.active;
    if (
      !LIVE_ROOT ||
      runtime.currentRevision === null ||
      target.revision <= runtime.currentRevision
    )
      return null;
    const activates = () =>
      target.revision > runtime.currentRevision &&
      !hasPending() &&
      (!midComposition() || forceActivation) &&
      !versionMenuIsOpen();
    // The revision either install leaves this document showing. State application reads
    // it to judge the answer before the install edits anything, and adopts the answer
    // against it afterwards, so the document's revision and the state that speaks for it
    // become current in one reading.
    if (!servedExecutable || target.executable !== servedExecutable)
      return {
        stale: false,
        revision: target.revision,
        activates,
        install: reloadInto(target),
      };
    let doc;
    try {
      doc = await revisionDocument(target);
      if (doc === null)
        // Every answer carries `activates`, so no caller has to know which shapes this
        // can return. `stale` says why this one refuses — the document came from a
        // re-vendored layer and the page is already reloading — and the heartbeat, which
        // asks nothing but `activates`, is right without a second reading of that fact.
        return { stale: true, activates: () => false };
      // Step 6 of the startup order, on the same background stretch as the document
      // itself: this revision may carry a tag the standing document never held, and
      // insertion is where its element is constructed. Asked for here so the install
      // spends nothing on a fetch while the reader is looking at the page. Inside this
      // try, because the loader keeps a rejected import: one 404 on a module an arriving
      // revision introduces would otherwise reject every later state read for good.
      await importWidgets(doc.querySelector("body > main"));
    } catch (error) {
      reportPageError(
        `revision ${target.revision} failed to load: ${error?.message ?? error}`,
      );
      return null;
    }
    return {
      stale: false,
      revision: target.revision,
      activates,
      install: () => {
        forceActivation = false;
        return activateRevision(doc, target);
      },
    };
  }

  // The other install, for a revision whose executable identity differs: a live document
  // cannot re-evaluate a module graph or redefine a custom element, so arbitrary page
  // modules, listeners, custom elements, and styles start together in a fresh one. The
  // reader's place, standing, comparison, and pointer are the only things a new document
  // can be given, and they ride across as a one-use handoff.
  const reloadInto = (target) => () => {
    forceActivation = false;
    const view = captureView();
    tabStore.set(VIEW_KEY, JSON.stringify(view));
    tabStore.set(
      HANDOFF_KEY,
      JSON.stringify({
        revision: target.revision,
        url: location.href,
        view,
        retainedStanding: captureRetainedStanding(),
        comparison: selectedBase(),
        pointer: pointerAt(),
      }),
    );
    const marked = new URL(location.href);
    marked.searchParams.set(PRIVATE_REVISION_PARAM, String(target.revision));
    history.replaceState(history.state, "", marked);
    location.reload();
    // The new document owns the continuation. Keeping this activation pending
    // prevents the old realm from applying state while navigation commits.
    return new Promise(() => {});
  };

  // ---------- reading continuity across a replacement ----------
  // Following a new version opens a fresh document. A raw navigation leaves the reader
  // at the top mid-session, standing nowhere in the walk they were making. Where they are
  // rides across as one semantic view — and through tabStore on document travel, per-tab
  // because a place in a page shouldn't outlive it. Two things are recorded, because
  // the runtime records two things it can write down: the passage they were reading, and
  // the ask the a/A walk had stepped them to. The passage travels as a landmark rather
  // than a pixel offset, since content moves between versions: re-find it by its text
  // within its section, then the section alone, and only fall back to the raw offset when
  // neither survived the revision. The panel's own open state is restored separately
  // (THREAD_PANEL_KEY); because that runs first, the column is already reflowed by the time we
  // scroll.

  // The page's own text blocks the reader can see, in document order, with the rect of each
  // one's first line — one reading of what is in front of them, for the two questions that
  // ask it: which passage a version change should land them back on (below), and where a
  // walk over the page's Asks starts when they have pointed at nothing.
  // A block's landmark is the top of its first line (a range), not its border box; restore
  // measures the matched text the same way, so the line box's leading cancels out.
  function textBlocks() {
    const main = document.querySelector("body > main");
    const seen = new Set();
    // Walk the page's composed text rather than querying only its light DOM. A declared
    // shadow root renders authored words at its host's place in reading order; those
    // words are pointable and resolvable through the shared passage reading, so version
    // continuity must be able to choose the same blocks as landmarks.
    return textNodesUnder(main)
      .map(({ node }) => closestAcross(node.parentElement, TEXT_BLOCK))
      .filter((block) => block && !seen.has(block) && seen.add(block));
  }

  function* blocksOnScreen(region = null, blocks = textBlocks()) {
    // Read the painted edge directly. The declared height may contain a safe-area
    // `calc()`, whose serialized value is not a number even though its box is exact.
    const bounds = region
      ? shownRegionBounds(region)
      : { top: banner.getBoundingClientRect().bottom, bottom: innerHeight };
    if (!bounds) return;
    for (const block of blocks) {
      // [hidden] needs an explicit skip: hidden="until-found" resolves to
      // content-visibility, under which descendants still report real rects —
      // but what's behind an inactive tab isn't what the reader is reading.
      if (
        inChrome(block) ||
        closestAcross(block, "[hidden]") ||
        (region && !containsAcross(region.body, block)) ||
        (!region &&
          readingRegionFor(block) &&
          readingPosture(readingRegionFor(block)) === "bounded")
      )
        continue;
      const range = document.createRange();
      range.selectNodeContents(block);
      const rect = range.getBoundingClientRect();
      const seen = clippedRect(rect, block, new Map());
      if (seen && seen.bottom > bounds.top && seen.top < bounds.bottom)
        yield [block, rect];
    }
  }
  // The one block the reader is on, which is the first the walk above yields. Two
  // things outside ask it — where an Ask walk starts, and where the keyboard
  // reference hands a reader back to — and they were asking it in two places with the
  // same expression written out twice.
  const readingBlock = () => blocksOnScreen().next().value?.[0] ?? null;

  function captureReturnPlace() {
    const control = focused();
    return control && control !== document.body
      ? { control, reading: null }
      : { control: null, reading: readingBlock() };
  }

  // The quote and the section it's searched in come from the same block, or the search is
  // filtered to a section the text isn't in and can only ever fail — restore then falls back
  // to the section, which doesn't absorb content added above the reader inside it.
  function captureRegion(region = null, blocks = textBlocks()) {
    const box = region ? effectiveScroller(region) : pageScroller;
    const boxTop = shownBox(box).top;
    const inset = Number.parseFloat(getComputedStyle(box).scrollPaddingTop) || 0;
    const landmarkTop = (top, block, blockTop = top) =>
      block?.matches(HEADING) ? top + Math.max(0, inset - blockTop) : top;
    const view = { y: box.scrollTop, scroller: scrollerIdentity(box) };
    for (const [block, rect] of blocksOnScreen(region, blocks)) {
      const section = closestAcross(block, "[id]");
      if (!view.section && section) {
        // The first on-screen block's section, kept only until a quotable block supplies
        // its own: a page with nothing quotable on screen still has somewhere to land.
        view.section = section.id;
        view.sectionTop = landmarkTop(
          shownBox(section).top - boxTop,
          block,
          rect.top - boxTop,
        );
      }
      // Written down the way a comment's quote is, so the search that re-finds it is
      // looking for a string of the same kind.
      const text = cut(quoteFrom(textNodesUnder(block)), 0, LANDMARK_CAP);
      // A short line ("Risks") would match anywhere; keep scanning for a quotable block.
      if (text.length >= 24) {
        // Unconditionally, so a quotable block under no section clears the earlier one
        // rather than sending the search into a subtree its text isn't in.
        view.section = section?.id;
        view.sectionTop =
          section &&
          landmarkTop(shownBox(section).top - boxTop, block, rect.top - boxTop);
        view.quote = text;
        // A partially covered paragraph is still a reading place: its visible lines
        // should stay where the reader left them. A heading identifies the place as a
        // whole, so a coordinate that hides its opening words is not a valid heading
        // landmark. Normalize both quote and fallback section state here, once, rather
        // than teaching every restore path to repair it after document replacement.
        view.quoteTop = landmarkTop(rect.top - boxTop, block);
        break;
      }
    }
    return view;
  }

  function captureView() {
    const blocks = textBlocks();
    const active = activeReadingRegion(readingRegions(), blocks);
    const view = Object.assign(captureRegion(null, blocks), {
      revision: runtime.currentRevision,
      ask: landedAt()?.id,
      activeRegion: active?.id,
      regions: Object.fromEntries(regionViews),
    });
    for (const region of readingRegions()) {
      if (!shownRegionBounds(region)) continue;
      const reading = captureRegion(region, blocks);
      if (readingPosture(region) === "bounded" || region.id === active?.id) {
        regionViews.set(region.id, reading);
        view.regions[region.id] = reading;
      }
    }
    return view;
  }

  // A restore jumps rather than glides: a page is free to set scroll-behavior: smooth, and
  // animating from the replacement's raw position is worse than the jump it replaces.
  // Moving to a mark the reader asked for is the other case, and says so.
  const hasLandmark = (reading) => Boolean(reading?.quote || reading?.section);
  const rawOffsetFits = (reading, scroller) =>
    reading.scroller !== undefined && reading.scroller === scrollerIdentity(scroller);
  function scrollerIdentity(scroller) {
    if (scroller === pageScroller) return "$page";
    return readingRegions().find(({ body }) => body === scroller)?.id;
  }

  function restoreRegion(view, region = null) {
    if (!view) return;
    const box = region ? effectiveScroller(region) : pageScroller;
    const boxTop = shownBox(box).top;
    const text = pageText();
    const found = view.quote && resolveAnchor(view, text);
    const segments = targetSegments(found);
    if (segments.length) {
      reveal(segments[0].node.parentElement); // the passage may sit behind a tab
      moveScrollerBy(
        box,
        rangeOf(segments).getBoundingClientRect().top - boxTop - view.quoteTop,
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
      moveScrollerBy(box, shownBox(section).top - boxTop - view.sectionTop);
    } else if (rawOffsetFits(view, box))
      box.scrollTo({ top: view.y, behavior: "instant" });
  }

  function restoreView(view) {
    setLanded((view.ask && document.getElementById(view.ask)) || null);
    const regions = new Map(readingRegions().map((region) => [region.id, region]));
    const active =
      regions.get(view.activeRegion) ??
      containingReadingRegionFor(focused()) ??
      readingRegionFor(readingBlock());
    if (active) reveal(active.host);
    const restored = new Set();
    const activeReading = active && view.regions?.[active.id];
    const activeScroller = active && effectiveScroller(regions.get(active.id));
    // An empty flow region has only the page scroller's raw offset. Let the containing
    // page landmark restore that shared box instead; a raw offset belongs only to the
    // same semantic scrollport that supplied it.
    if (
      activeReading &&
      (hasLandmark(activeReading) ||
        (rawOffsetFits(activeReading, activeScroller) &&
          activeScroller !== pageScroller))
    ) {
      restoreRegion(activeReading, regions.get(active.id));
      restored.add(activeScroller);
    } else {
      restoreRegion(view);
      restored.add(pageScroller);
    }
    for (const [id, reading] of Object.entries(view.regions ?? {})) {
      const region = regions.get(id);
      if (!region) continue;
      const box = effectiveScroller(region);
      if (restored.has(box)) continue;
      if (!hasLandmark(reading) && !rawOffsetFits(reading, box)) continue;
      restoreRegion(reading, region);
      restored.add(box);
    }
  }

  // A posture change replaces scroll containers without replacing the document. Keep each
  // semantic region's last reading so a pane that becomes inactive does not inherit the
  // shared page offset when it becomes bounded again. In flow, only the region the reader
  // is working represents the shared page scroller.
  const regionViews = new Map();
  let navigationIntent = 0;
  let lastReadingRegionId = null;

  // Continuity restores scroll geometry, not the reading-key subject. Frame furniture
  // still names its own pane to d/u through readingRegionFor; because the furniture does
  // not live in that pane's scroller, a posture change preserves the outer region that
  // geometrically contains it. The same distinction keeps an inline response outside a
  // nested region body with the outer scroller that actually carries it.
  const activeReadingRegion = (
    candidates = readingRegions(),
    blocks = textBlocks(),
  ) => {
    const focusedRegion = containingReadingRegionFor(focused());
    if (focusedRegion && candidates.some(({ id }) => id === focusedRegion.id))
      return focusedRegion;
    const recent = candidates.find(({ id }) => id === lastReadingRegionId);
    if (recent) return recent;
    return candidates
      .map((region) => [region, blocksOnScreen(region, blocks).next().value?.[1]])
      .filter(([, rect]) => rect)
      .sort(([, a], [, b]) => a.top - b.top)[0]?.[0];
  };

  const postureTransitions = new Map();
  function readingRegionTransition({ phase, owner, from, to, regions }) {
    if (phase === "before") {
      const blocks = textBlocks();
      const active = activeReadingRegion(regions, blocks);
      const captured =
        from === "flow" ? regions.filter(({ id }) => id === active?.id) : regions;
      for (const region of captured)
        if (shownRegionBounds(region))
          regionViews.set(region.id, captureRegion(region, blocks));
      postureTransitions.set(owner, {
        intent: navigationIntent,
        to,
        regions: regions.map(({ id }) => id),
      });
      return;
    }
    const transition = postureTransitions.get(owner);
    postureTransitions.delete(owner);
    if (!transition || transition.intent !== navigationIntent) return;
    const live = new Map(readingRegions().map((region) => [region.id, region]));
    const candidates = transition.regions.map((id) => live.get(id)).filter(Boolean);
    const active = activeReadingRegion(candidates);
    const restored = new Set();
    const ordered = active
      ? [active, ...candidates.filter(({ id }) => id !== active.id)]
      : candidates;
    for (const region of ordered) {
      const reading = regionViews.get(region.id);
      const box = effectiveScroller(region);
      if (!reading || restored.has(box)) continue;
      if (!hasLandmark(reading) && !rawOffsetFits(reading, box)) continue;
      restoreRegion(reading, region);
      restored.add(box);
    }
  }

  let readingContinuityInstalled = false;
  function installReadingContinuity() {
    if (readingContinuityInstalled) return;
    readingContinuityInstalled = true;
    watchReadingRegionTransitions(readingRegionTransition);
  }

  function installArrival() {
    installReadingContinuity();
    // Ordinary reload and history travel belong to the browser. The root is its document
    // scrollport, so native restoration is both more complete and less surprising than a
    // parallel session-store reading. Leaf intervenes after upgrades only for two semantic
    // cases the platform cannot know: a fresh URL aimed at a target generated or hidden by
    // a widget, and travel to a different authored revision where a passage is a better
    // landmark than the old document's pixels.
    const navigationType = performance.getEntriesByType("navigation")[0]?.type;
    const handoff = (() => {
      const serialized = tabStore.get(HANDOFF_KEY);
      tabStore.set(HANDOFF_KEY, null);
      try {
        const value = JSON.parse(serialized || "null");
        return LIVE_ROOT &&
          navigationType === "reload" &&
          value?.url === location.href &&
          Number.isInteger(value.revision) &&
          value.revision <= runtime.currentRevision &&
          Number.isInteger(value.view?.revision) &&
          value.view.revision < runtime.currentRevision
          ? value
          : null;
      } catch {
        return null;
      }
    })();
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
      if (!anchoringIsReady()) return;
      tabStore.set(VIEW_KEY, JSON.stringify(captureView()));
    });
    function landArrival() {
      if (handoff) {
        restorePointer(handoff.pointer);
        restoreView(handoff.view);
        restoreRetainedStanding(handoff.retainedStanding);
        if (handoff.comparison !== null && stamped(handoff.comparison))
          showComparison(handoff.comparison);
        return;
      }
      const aimed =
        navigationType === "navigate" &&
        targetElement(resolveAnchor({ section: fragmentId(location.hash) }));
      // Native fragment navigation has already landed an ordinary authored target.
      // Keep that position when upgrades left the complete destination readable: moving
      // it to the centre after presentation makes a loaded page visibly jump for no gain.
      // A generated, collapsed, clipped, or displaced target still needs the semantic
      // arrival pass because the browser could not land its final geometry at parse time.
      if (aimed) {
        if (!readableDestination(aimed)) scrollToElement(aimed, "instant");
      } else if (
        navigationType === "navigate" &&
        savedView &&
        savedView.revision !== runtime.currentRevision
      )
        restoreView(savedView);
    }
    return { landArrival, savedView };
  }

  function mount() {
    versionChooser.configure({
      activate: (entry) => {
        if (entry.version !== null) goVersion(entry.version);
        else if (entry.active) goActive();
      },
      compare: pressComparison,
      latest: goActive,
      toggle: repaint,
    });
    if (!LIVE_ROOT) reserveNewsSlot(latestChip);
    keys(
      versionMenu,
      "In the versions menu",
      [
        VERSION_WALK,
        OPEN_NUMBER,
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
    for (const type of ["pointerdown", "keydown", "wheel", "touchstart"])
      addEventListener(
        type,
        (event) => {
          navigationIntent++;
          const region = readingRegionFor(event.composedPath()[0]);
          if (region) lastReadingRegionId = region.id;
        },
        { capture: true, passive: true },
      );
    renderVersions(null);
  }
  return {
    closeVersionMenu,
    NEWEST,
    VERSIONS,
    CHOOSER,
    renderVersions,
    inlineComparison,
    toggleInlineComparison,
    comparisonBase,
    comparisonChanges,
    prepareActivation,
    readingBlock,
    captureReturnPlace,
    installArrival,
    mount,
  };
}
