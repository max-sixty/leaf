/* Version travel, comparison, and user continuity.
 *
 * The picker paints its immutable reading from what it reads of the application's
 * publication and comparison signals.
 * `prepareActivation` installs
 * a live revision; `goActive` also returns from a pinned document, while `goVersion`
 * opens a historical `?pin` address. The controller receives application and travel
 * capabilities before mount binds listeners; `installArrival` restores continuity once
 * the arriving geometry is ready.
 *
 * The picker owns the complete version list. Its focused row selects the comparison
 * base; the row for the displayed version clears comparison. The comparison and the
 * picker's presentation need no application capability, so they live at module scope,
 * one per document, and other surfaces import their readers directly; the controller
 * keeps travel and activation, which do. Block marks show changes, and
 * `inlineComparison` / `toggleInlineComparison` disclose a block's text diff on
 * request. `comparisonBase` names the current base. `comparisonChanges(owner)` selects
 * changed descendants from the same comparison reading. Its signal advances after
 * the marked DOM and comparison selection have changed together; a pending picker
 * choice stays separate from that committed reading.
 *
 * Executable identity selects the install. An unchanged registry, module graph, and
 * inline module bodies permit an in-place patch; changed executable inputs require a
 * fresh document. Prose, styles, and media can change without reloading. Served identity
 * is captured before upgrade: upgraded DOM cannot supply those baselines. The patch
 * retains unchanged widgets and recaptures replaced widgets against the arriving source. A widget declaring `x-patch: members` is
 * patched inside its members instead, while the revision keeps its shell.
 *
 * Composition defers a reload or a patch that would discard an active native editor
 * or change a selected passage/comment's complete authored anchor scope. Runtime
 * chrome stays outside the authored patch and follows its own editor continuation.
 * Unresolved delivery and an open version menu defer either install.
 * Ending composition releases its hold on the next heartbeat; pressing the newest-version
 * chip explicitly releases that hold. The chip remains available while activation waits.
 *
 * Retained nodes keep their mechanical state. Replaced nodes use `carry.js`'s authored-id
 * contract, and the obligation view restores the selected obligation by id. Both installs restore these
 * readings; the patch passes its retained nodes so restoration skips them. Unnamed
 * replaced controls receive no guessed focus. Authored controls and registered draft
 * editors carry native editing under their existing replacement identity; arbitrary
 * selections and module state cannot cross documents. Drafts and chrome preferences
 * use their own stores.
 *
 * A fresh-document install stores a page-scoped, one-use handoff: reading position,
 * comparison, pointer, margin and panel location, mechanical carry, and obligation location. A newer
 * revision may consume it, but ordinary reloads and history travel cannot replay it.
 * Explicit historical travel carries reading position and the decision landmark, without
 * mechanical carry or obligation location. State application serializes responses and remains
 * pending after navigation starts until the old document is discarded.
 *
 * `captureView` records a place (reading-place.js) for the page and each reading
 * region, and the decision landmark. `restoreView` returns the user to them. A fresh
 * navigation aimed at an element keeps it landed while the page arrives (`aimArrival`).
 * `landArrival` runs after presentation: a valid revision handoff restores continuity;
 * unexpected mechanical failures report without blocking proved state or deferred
 * arrivals. Otherwise a fresh navigation aimed nowhere restores a saved view from a
 * different revision. Ordinary reloads and full-document history travel keep the browser's
 * restored offset; history.js owns same-document working-place checkpoints.
 * Comparison is restored after activation because its base must be
 * fetched again. Reading position is restored even after a patch because content above
 * it may have changed height.
 *
 * `versionsOffered` controls the destination and the Versions row.
 */
import {
  nextAnimation,
  nextRender,
  renderingState,
  sizeObserver,
} from "./rendering.js";
import { frameFor } from "./arrivals.js";
import { LIVE_ROOT, layerRoot, pageUrl, revisionLabel, runtime } from "./context.js";
import { servedExecutable } from "./document-identity.js";

import { captureCarry, restoreCarry } from "./carry.js";
import {
  captureDraftEditing,
  draftEditingDestination,
  draftEditingStands,
  restoreDraftEditing,
} from "./drafts.js";
import { heldThreadId, replyDestination } from "./thread/focus.js";
import { restoreReplyEditing } from "./thread/replies.js";
import {
  focusDestination,
  onCurrentLocation,
  onUserInput,
  focused,
  inputCount,
} from "./focus.js";
import { restrictUserIntent, retainUserIntent } from "./user-intent.js";
import { focusedInView } from "./user-place.js";
import { patchTree, patchRetains } from "./dom-children.js";
import { move } from "./dom-move.js";
import { savedReadingSettled } from "./keyboard/bindings.js";
import { commandSteps } from "./keyboard/control-keys.js";
import { pruneScopedElements } from "./keyboard/scopes.js";
import { repaint } from "./repaint.js";
import { notice } from "./notifications.js";
import { backgroundFlash, flashDuration } from "./motion.js";
import {
  authored,
  elementById,
  inChrome,
  pageDocument,
  quoteFrom,
  rangeOf,
  readingFrom,
  textNodesUnder,
} from "./passages.js";
import { TEXT_BLOCK } from "./kernel-facts.js";
import { RUNTIME_PAINT_ATTRIBUTE } from "./page-paint.js";
import { registry, tagsDeclaring } from "./registry.js";
import {
  inlineMarkdownFragment,
  paintMarkdown,
  loadDeclaredMarkdown,
  formatDeclaredMarkdown,
} from "./markdown.js";
import {
  chosenSince,
  moveScrollerBy,
  pageScroller,
  placeKept,
  SCROLL_SLACK,
  scrollChoices,
  scrollLimit,
} from "./scrolling.js";
import {
  containingReadingRegionFor,
  effectiveScroller,
  onReadingInput,
  regionScrollBehavior,
  readingRegionFor,
  readingRegions,
  recentReadingRegion,
  regionsSettled,
  scrollChainOf,
  shownRegionBounds,
  watchReadingRegionTransitions,
} from "./reading-regions.js";
import { PAGE_SCOPE } from "./storage.js";
import { tabStore } from "./tab-store.js";
import { authoredBody } from "./widget-elements.js";
import { alignInlineText } from "./text-alignment.js";
import { el, reveal } from "./widget-elements.js";
import { layoutChanged } from "./widget-upgrade.js";
import { settleDocumentLayout } from "./content-layout.js";
import { keeps } from "./keeps.js";
import { PAGE_CONTROL_RANK, registerPageControl } from "./page-controls.js";
import { pointerAt, restorePointer } from "./pointer.js";

import { LayerRefused, admitReading, reportPageError } from "./layer-client.js";
import { projectView, readApplication } from "./semantic-state.js";
import { batch, effect, signal } from "/runtime/framework.js";

import { ADDRESSABLE, anchoringIsReady, fragmentTarget } from "./anchor-resolution.js";
import { scrollToFragment } from "./anchor-travel.js";
import { rememberAuthoredParents, stageAuthoredStates } from "./projection/authored.js";
import { foldWidgetStates, obligationValue } from "./projection/model.js";
import { runtimeRootState } from "./root-state.js";
import {
  commitWidgetDescriptors,
  quoted,
  stageWidgetDescriptors,
} from "./widget-descriptors.js";
import { latestVersionLabel, versionPicker } from "./version-picker.js";
import {
  preloadWidgets,
  patchDocument,
  reindexPassageOwners,
  rememberPassageParts,
} from "./widget-loader.js";
import { under } from "./shadow.js";
import { replaceEntry } from "./history.js";
import {
  blocksOnScreen,
  capturePlace,
  hasLandmark,
  rawOffsetFits,
  pageReadingBlock,
  placeNode,
  placeOffset,
  restorePlace,
  textBlocks,
} from "./reading-place.js";
import { holdingError, raiseError } from "./errors.js";
import { tick } from "./version-signal.js";

const PRIVATE_REVISION_PARAM = "_leaf-revision";

// The document roots may carry authored classes, data attributes, and inline custom
// properties that page-local styles read. The live document also paints its own facts
// onto those same two elements. Most arrive after this module, but the server's prepaint
// bootstrap deliberately runs before the module graph and has already written sample
// presentation facts. Authored markup cannot use the `data-lf-` or
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
// publication's card — and that share belongs to the document the user was
// served rather than to the revision arriving inside it.
const versionedHeadNode = (node) =>
  !node.hasAttribute("data-lf-runtime") &&
  (node.localName === "title" ||
    node.localName === "style" ||
    node.localName === "base" ||
    (node.localName === "meta" &&
      (node.hasAttribute("name") || node.hasAttribute("property"))) ||
    node.localName === "link");
// Keep one inert authored baseline before Leaf mounts or upgrades anything. Live
// revisions compare against it and pair retained source nodes with their live peers.
// Delivery's Markdown preview is presentation, so neither baseline includes it.
const authoredMarkup = (root) => {
  // Prepaint can already have painted the first document. Both source snapshots
  // exclude runtime-owned attributes; their live values stay with their writers.
  for (const name of Object.values(RUNTIME_PAINT_ATTRIBUTE))
    for (const element of root.querySelectorAll(`[${name}]`))
      element.removeAttribute(name);
  for (const member of root.querySelectorAll("[data-lf-view]"))
    member.removeAttribute("hidden");
  for (const preview of root.querySelectorAll("[data-lf-prepaint]")) preview.remove();
  return root;
};
const pairSources = (source, live, pairs) => {
  pairs.set(source, live);
  const held = source.localName === "template" ? source.content : source;
  const shown = live.localName === "template" ? live.content : live;
  const children = [...shown.childNodes].filter(
    (child) => !child.matches?.("[data-lf-prepaint]"),
  );
  for (const [at, child] of [...held.childNodes].entries()) {
    const peer = children[at];
    if (peer) pairSources(child, peer, pairs);
  }
  return pairs;
};
// Only the version controller keeps this baseline; replacing a revision releases
// its source and the source/live node pairs together.
let initialDocument = (() => {
  const main = pageDocument();
  const inert = document.implementation.createHTMLDocument("");
  const source = main ? authoredMarkup(inert.importNode(main, true)) : null;
  // Cloning transfers native dirty properties too. Read the initial condition from
  // the defaults, leaving markup and its exact text intact (reparsing drops a leading
  // newline in pre/textarea). Native setters apply each control's sanitization.
  for (const input of source?.querySelectorAll("input") ?? []) {
    if (
      !["file", "checkbox", "radio"].includes(input.type) &&
      input.value !== input.defaultValue
    )
      input.value = input.defaultValue;
    input.checked = input.defaultChecked;
  }
  for (const textarea of source?.querySelectorAll("textarea") ?? [])
    textarea.value = textarea.defaultValue;
  const pairs = main ? pairSources(source, main, new WeakMap()) : new WeakMap();
  // Native disclosures can already have been used while modules were loading.
  // Their parse-time owner supplies the authored default for the source baseline;
  // the live node keeps the user's choice, as it does for every later revision.
  for (const disclosure of source?.querySelectorAll("details") ?? []) {
    const open = document.documentElement.lfStorage.initialDisclosureOpen(
      pairs.get(disclosure),
    );
    if (open !== undefined) disclosure.toggleAttribute("open", open);
  }
  return {
    authoredBodyAttributes: authoredAttributes(document.body),
    authoredHeadNodes: new Set([...document.head.children].filter(versionedHeadNode)),
    authoredHtmlAttributes: authoredAttributes(document.documentElement),
    source,
    pairs,
  };
})();

// Boot lends this same captured source and its original node pairs to typed
// capture, then transfers ownership to the version controller.
export function takeInitialDocument() {
  const captured = initialDocument;
  initialDocument = null;
  return captured;
}

// ---------- the version picker ----------
// Version facts are selectors of the accepted application reading.
const stamped = (version) =>
  runtime.versions.find((candidate) => candidate.version === version);
// The version picker: a press that says which version this is, and a menu that says
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
// ships a version whenever the work moves: what the user wants marked is what has
// changed since they last looked, which is as far back as they were away. The base is
// the menu's to say, so every version older than this one offers itself as one.
//
// The closed control is a destination, not the menu's account of the working document.
// Keep it to one stable version token (or Draft) through disclosure and comparison;
// those states remain in the menu, class, title, and accessible name. A state arriving
// on the poll therefore cannot resize this control and displace controls to its left.
// The visible label prefixes this token with Showing; comparisons keep the bare token.
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
const behindCurrent = () =>
  runtime.active !== null && runtime.currentRevision !== null && !runtime.showsActive;
// Which version a page behind the latest shows, in the few words a notice beside the
// floating panel's marks has room for: the version and the latest one's number, as in
// "v2 of 3", or a draft the agent has since revised.
const shownBehind = () =>
  runtime.currentStamp === null
    ? "An older draft"
    : runtime.active.version === null
      ? `v${runtime.currentStamp}`
      : `v${runtime.currentStamp} of ${runtime.active.version}`;

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
// One immutable, complete presentation reading for the native picker surfaces. The
// view deliberately retains the rows it is already showing while its popover stands;
// the candidate rows below keep advancing, so dismissal can commit them without
// replaying an accepted state or consulting the rendered DOM as authority.
function pickerModel(state) {
  const offered = state !== null && versionsOffered();
  const behind = behindCurrent();
  const sourceFailed = LIVE_ROOT && Boolean(state?.source_error);
  const currentLabel = runtime.currentLabel ?? "Draft";
  const newer = behind ? `; ${runtime.active.label} available` : "";
  return Object.freeze({
    picker: Object.freeze({
      offered,
      token: currentVersionToken(),
      compared: diffOn.value || diffPendingBase.value !== null,
      news: behind,
      keyTitle: offered
        ? diffPendingBase.value !== null
          ? `${currentLabel}: loading a comparison with v${diffPendingBase.value}${newer}`
          : diffOn.value
            ? `${currentLabel}: showing what changed since v${diffBase.value} — pick a version, or press Compare again to stop${newer}`
            : `${currentLabel}: versions; read one, or mark what changed since it${newer}`
        : currentLabel,
      ariaLabel: offered
        ? diffPendingBase.value !== null
          ? `${currentLabel}: loading comparison with v${diffPendingBase.value}; open versions${newer}`
          : diffOn.value
            ? `${currentLabel}: comparing with v${diffBase.value}; open versions${newer}`
            : `${currentLabel}: open versions${newer}`
        : currentLabel,
    }),
    latest: Object.freeze({
      // The agent's latest save failed its check, so the page shows the last one that
      // passed; `error` is what the check said.
      failed: sourceFailed,
      error: sourceFailed ? state.source_error : null,
      disabled: sourceFailed,
      keyTitle: sourceFailed ? state.source_error : "Open the current page",
      label: latestVersionLabel({
        failed: sourceFailed,
        activeLabel: behind ? runtime.active.label : null,
      }),
      shown: behind ? shownBehind() : null,
      news: sourceFailed || behind,
    }),
    rows:
      state === null || runtime.active === null
        ? Object.freeze([])
        : menuRows(state, runtime.browser?.version_notes ?? {}),
    selection: Object.freeze({
      base: diffPendingBase.value ?? (diffOn.value ? diffBase.value : null),
      currentRevision: runtime.currentRevision,
      on: diffOn.value,
      pendingBase: diffPendingBase.value,
      baseRevision: stamped(diffBase.value)?.revision ?? null,
    }),
  });
}

// The page before its first accepted state has a null `runtime.state`. Version controls
// read the immutable document revision and the accepted root.
// The agent's latest save failing its check is an error the user should see wherever
// they are (errors.js), held while the page shows the last one that passed; Versions
// says what the check found.
const holdFailedSave = holdingError();
function paintPicker() {
  const model = pickerModel(runtime.state);
  holdFailedSave(
    model.latest.failed
      ? "Latest edit not shown: it failed its check (see Versions)"
      : null,
  );
  repaint();
}
// The picker's reading for another presentation of the same versions, the floating
// panel's Versions view, derived where it is read so that paint follows its inputs.
export const versionsReading = () => pickerModel(runtime.state);
// Versions, a list of the floating panel's own, and a newer page to open, as rows of the
// page's controls.
registerPageControl({
  key: "versions",
  rank: PAGE_CONTROL_RANK.versions,
  label: "Versions",
  value: () => versionsReading().picker.token,
  shortcut: () => commandSteps("version.open"),
  disabled: () => !versionsReading().picker.offered,
  group: "page",
});
registerPageControl({
  key: "latest",
  rank: PAGE_CONTROL_RANK.latest,
  label: () => versionsReading().latest.label,
  offered: () => versionsReading().latest.news,
  disabled: () => versionsReading().latest.disabled,
  urgent: "new",
  press: () => versionPicker.latest(),
  group: "page",
});

// ---------- version diff ----------
// "Changes since vN": blocks (paragraphs, list items, Leaf elements) whose text
// isn't present in the base version get a tinted marker, so re-reading a
// revision is cheap. Block-level and additions-only — deleted text has no home
// to mark — and a widget that renders its own body is opaque to it. The base is
// any version older than the one being read, offered by its own row in the
// picker's menu, where the note saying what changed in words sits beside the
// press that marks it on the page.
//
// Both sides are sources: the base version's and this version's, each painted with
// the widget state it shows (`paintedSource`). What a module wrote into the page is in
// neither, so it can't read as a change, marked or not. A changed block then marks the
// live node its source node stands for (`standingFor`).
//
// Which blocks and which widgets is the registry's answer both times, so a widget added
// to the vocabulary diffs on the strength of its declaration: a compound member whose content
// model is prose is a block of the page's prose the same way a paragraph is.
const diffBlockSel = () =>
  [
    TEXT_BLOCK,
    "aside",
    ...tagsDeclaring((e) => e["x-owners"] && (e["x-content"] ?? "markup") === "markup"),
    // Preserving widgets contribute their own prose. The leaf-blocks-only rule
    // below avoids counting nested blocks twice. One set among the words around it
    // (x-inline), such as a gloss, is part of its paragraph's words instead, or that
    // rule would skip the paragraph and miss a change to the words around it. A
    // suggestion's slots stay blocks: the decision retiring one makes the suggestion
    // opaque, and its paragraph's words would run across it.
    ...tagsDeclaring((e) => !e["x-inline"] && e["x-verbatim"]),
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
    ...Object.entries(registry.$decisions)
      .filter(([, { retires }]) => Object.keys(retires).length)
      .map(([owner]) => owner),
    "svg",
  ].join(",");
// What is being compared, and whether the comparison is active. Every rendering of
// the pair — the picker's word and paint, each row's press, the rail down the span —
// comes from the immutable picker model and is read back by nothing. The comparison
// owns the marked identities; the CSS marks are only their rendering.
const diffOn = signal(false);
const diffBase = signal(null);
// Advanced after the marked DOM changes, so tracked readers see its new contents.
const comparisonGeneration = signal(0);
const diffPendingBase = signal(null);
const diffMarked = new Set();
// What each marked block said in the base version and says in this version's source,
// and which of those readings the user has open. The marks say a block changed; these
// say what it changed from, at the block, so learning it costs no travel to the other
// version and back.
//
// Identity across versions is the id — the fact threads and reading position already
// ride, and the same lookup the state half of applyDiff resolves its units by. A block
// with no id names nothing in the base document, so the comparison holds nothing for it
// and its Change reading stays the plain travel it always was. An opaque widget holds
// nothing either: what the user reads there is its module's rendering, not the source
// words the two versions hold.
/** @type {Map<Element, {was: string | null, is: string | null}>} */
const diffWordsOf = new Map();
const inlineOpen = new Map(); // marked element -> its generated nodes and highlight ranges
// The comparison request that owns the page. Every request takes the next number and every
// stop takes one too, so a base whose document lands after the user has moved on is
// dropped rather than painted over the base they are on now. Reachable because the
// walk asks per row: it is one fetch per press, and the presses come faster than the network.
let diffRequest = 0;
// A containing prose block owns its words, not an opaque child's rendered data.
// Use the same boundary for comparison keys, stored words and inline ranges.
// The child has its own identity and binding key in diffBlocks below.
const comparisonTextNodes = (root, opaque = diffOpaqueSel()) =>
  textNodesUnder(root, "wrote", (child) => child.matches(opaque));
const comparisonWords = (root, opaque) => quoteFrom(comparisonTextNodes(root, opaque));

// Formatting may render authored words while keeping their source on the formatted
// island. The keys compare that source; an inline comparison reads the formatted words,
// which are what the user sees.
function diffWords(block, opaque) {
  const words = (root) => comparisonWords(root, opaque);
  if (!block.querySelector("[data-lf-source-words]")) return words(block);
  const source = block.cloneNode(true);
  for (const island of source.querySelectorAll("[data-lf-source-words]"))
    island.replaceWith(document.createTextNode(island.dataset.lfSourceWords));
  return words(source);
}
// The blocks of a painted source (`paintedSource`), each keyed by its authored text
// (`wrote`), which leaves out what formatting generated, such as Markdown's media button.
function diffBlocks(root) {
  const pairs = [];
  const [blocks, opaque] = [diffBlockSel(), diffOpaqueSel()];
  // A data body is one source value. Its formatted paragraphs are its reading,
  // not independent source units; comparing the source also detects changed emphasis.
  for (const body of root.querySelectorAll(".lf-markdown-body")) {
    const owner = body.parentElement;
    if (owner.closest(opaque)) continue;
    pairs.push([owner, `markdown:${body.dataset.lfSourceWords}`]);
  }
  for (const b of root.querySelectorAll(blocks)) {
    if (b.closest(opaque) || b.closest(".lf-markdown-body")) continue;
    if ([...b.querySelectorAll(blocks)].some((child) => !child.closest(opaque)))
      continue; // leaf blocks only, excluding opaque children on both sides
    let key = diffWords(b, opaque);
    // An x-says value is the page's words at the element's edge (renderSaid), so it
    // belongs to what this block says: folded into the key at its declared edge, a
    // version that moves a metric's number or an event's time marks though no prose
    // changed. Both sources hold the attribute, so the key reads it on both sides.
    for (const [attr, edge] of Object.entries(
      registry[b.localName]?.["x-says"] ?? {},
    )) {
      const said = b.getAttribute(attr);
      if (said) key = edge === "before" ? `${said} ${key}` : `${key} ${said}`;
    }
    if (key) pairs.push([b, key]);
  }
  // Opaque widgets key by identity, not body, since the user reads their module's
  // rendering rather than those words — but a widget the base didn't have still marks.
  for (const w of root.querySelectorAll(opaque)) {
    // parentElement, not w itself: an svg inside a widget stays its widget's.
    if (w.parentElement?.closest(opaque)) continue;
    const entry = registry[w.localName] ?? {};
    // A data binding is authored semantics even though the body it fills is
    // opaque to comparison.
    const bindingAttrs = new Set();
    for (const input of Object.values(entry["x-data"] ?? {})) {
      if (input.source) bindingAttrs.add(input.source);
      if (input.reference) bindingAttrs.add(input.reference);
    }
    const binding = [...bindingAttrs]
      .sort()
      .map((attr) => [attr, w.getAttribute(attr)]);
    pairs.push([w, ` ${w.tagName}#${w.id}${JSON.stringify(binding)}`]);
  }
  return pairs;
}
/** One revision's browser reading at a log boundary, as `/api/view` answers it.
 * @returns {Promise<import("../types/contract.js").ServedViewAnswer["browser"]>} */
async function baseReading(baseRevision, throughSeq) {
  const params = new URLSearchParams({
    revision: String(baseRevision),
    through_seq: String(throughSeq),
  });
  const res = await fetch(pageUrl(`api/view?${params}`));
  // The reading is another revision's, so only its server is held to this document's.
  if (!admitReading(res)) throw new LayerRefused("Leaf changed while comparing");
  if (!res.ok) throw new Error(`couldn't project revision r${baseRevision}`);
  return (await res.json()).browser;
}
// The longest run of `after` that keeps the order `before` gave the same units:
// the units that did not move.
function inOrder(before, after) {
  const lengths = before.map(() => after.map(() => 0));
  const at = (i, j) => lengths[i]?.[j] ?? 0;
  for (let i = before.length - 1; i >= 0; i--)
    for (let j = after.length - 1; j >= 0; j--)
      lengths[i][j] =
        before[i] === after[j]
          ? at(i + 1, j + 1) + 1
          : Math.max(at(i + 1, j), at(i, j + 1));
  const kept = new Set();
  for (let i = 0, j = 0; i < before.length && j < after.length;)
    if (before[i] === after[j]) {
      kept.add(before[i]);
      i++;
      j++;
    } else if (at(i + 1, j) >= at(i, j + 1)) i++;
    else j++;
  return kept;
}
// A painted source holds the same accepted body projection as its version would
// show: the event's exact source, never a collapsed comparison value.
function paintBodies(doc, widgets) {
  for (const [id, { state, specs }] of widgets)
    for (const [verb, spec] of specs) {
      // A body record's state is an action's value.
      if (
        spec.record?.kind !== "body" ||
        !(/** @type {{action: string | null}} */ (state[verb]).action)
      )
        continue;
      const body = doc.getElementById(id)?.querySelector(":scope > .lf-markdown-body");
      if (body) paintMarkdown(body, state[verb].value);
    }
}
// A child an action in force created (`creates`) stood on the page that version
// showed, so its painted source holds it too, as passages.py adds it to the file's
// reading: at its owner's end, marked `data-lf-added`, its words formatted as its entry
// says. Without it, an option the user added before the base reads as changed since.
function placeCreated(doc, widgets) {
  for (const [id, { state, specs }] of widgets)
    for (const [verb, spec] of specs) {
      const owner = spec.creates && doc.getElementById(id);
      if (!owner) continue;
      const { child, words } = spec.creates;
      const markdown = registry[child]?.["x-text-format"] === "inline-markdown";
      for (const [unit, { detail }] of Object.entries(state[verb].units ?? {})) {
        if (doc.getElementById(unit)) continue;
        const created = doc.createElement(child);
        created.id = unit;
        created.toggleAttribute("data-lf-added", true);
        const text = detail[words];
        created.append(
          markdown ? doc.importNode(inlineMarkdownFragment(text), true) : text,
        );
        owner.append(created);
      }
    }
}
// A version's source as that version shows with `widgets`' state: a copy in a document
// of its own, its Markdown formatted, its body records painted and the children its
// actions created placed. `sourceOf` maps each copied element to the source element it
// copies, read before formatting replaces a Markdown body's <pre>; what the painting
// made has none. Formatting is synchronous: the renderer is loaded wherever a source
// declares Markdown, for the live page at its upgrade and for a base before this.
function paintedSource(source, widgets) {
  const doc = document.implementation.createHTMLDocument("");
  const root = doc.importNode(source, true);
  const sources = [source, ...source.querySelectorAll("*")];
  const sourceOf = new Map(
    [root, ...root.querySelectorAll("*")].map((copy, at) => [copy, sources[at]]),
  );
  doc.body.replaceChildren(root);
  formatDeclaredMarkdown(doc);
  paintBodies(doc, widgets);
  placeCreated(doc, widgets);
  return { doc, root, sourceOf };
}
// This version's source and the live node each of its nodes stands for, as the
// controller holds them.
/** @type {() => {source: Element | null, pairs: WeakMap<Node, Node>} | null} */
let versionSource = () => null;
// This version's source painted with the state the page shows now.
const currentSource = () =>
  paintedSource(versionSource().source, readApplication().effective.widgets);
// The live node a block of this version's painted source stands for: the one its source
// element is paired with, or else the page's element of its id, as for a child the
// painting created or an element a script replaced with a copy. Where a module took
// that node off the page, as a widget that redraws its words does, the nearest ancestor
// still on it stands for the block.
function standingFor(block, current) {
  const { pairs } = versionSource();
  for (let at = block; at && at !== current.root; at = at.parentElement) {
    const paired = current.sourceOf.has(at) && pairs.get(current.sourceOf.get(at));
    if (paired?.isConnected) return paired;
    const named = at.id && elementById(at.id, pageDocument());
    if (named?.isConnected) return named;
  }
  return null;
}
// The content half: the live nodes standing for the blocks of `current` whose words
// `base` doesn't hold, both painted sources. Multiset membership rather than an
// alignment: an unchanged block that merely moved stays unmarked; a changed or new one
// has no twin. A revision landing asks it of the source it replaced, to tint the blocks
// the revision changed.
function changedSince(base, current = currentSource()) {
  const held = new Map();
  for (const [, key] of diffBlocks(base.root)) held.set(key, (held.get(key) ?? 0) + 1);
  const changed = new Set();
  for (const [block, key] of diffBlocks(current.root)) {
    const left = held.get(key) ?? 0;
    if (left > 0) held.set(key, left - 1);
    else changed.add(standingFor(block, current));
  }
  changed.delete(null);
  return changed;
}
// The live elements this version's source wrote: whether the page or Leaf put an
// element there is this, not whether a module marked the words it fills it with.
export function servedElements() {
  const { source, pairs } = versionSource() ?? { source: null, pairs: new WeakMap() };
  const served = new Set();
  if (!source) return served;
  for (const node of [source, ...source.querySelectorAll("*")]) {
    const live = pairs.get(node);
    if (live) served.add(live);
  }
  return served;
}
function applyDiff(doc, baseAuthored, baseVersion, baseReading) {
  const baseView = baseReading.views[String(stamped(baseVersion).revision)];
  // The base version's widget state, folded as the publisher folds the current one:
  // its authored values, staged before its Markdown was formatted, under the
  // projection the server read for it. A report in force at the base painted there
  // just as an action did, so what the user saw includes it. The server reads each
  // event under the declaration it was admitted with, and the base's authored values
  // are decoded under this document's; an entry whose verb was declared otherwise
  // then has no value here to compare, so the fold leaves it out.
  const baseProjection = projectView(baseView);
  const declaredAlike = ({ e, spec }) => {
    const current = baseAuthored.get(e.widget)?.specs.get(e.action);
    return (
      current?.unit === spec.unit &&
      JSON.stringify(current.record ?? null) === JSON.stringify(spec.record ?? null)
    );
  };
  const baseWidgets = foldWidgetStates(baseAuthored, {
    ...baseProjection,
    desired: new Map(
      [...baseProjection.desired].filter(([, entry]) => declaredAlike(entry)),
    ),
  });
  const mark = (target) => {
    if (diffMarked.has(target)) return;
    target.classList.add("lf-ins-block");
    diffMarked.add(target);
  };
  const base = paintedSource(pageDocument(doc), baseWidgets);
  const current = currentSource();
  for (const block of changedSince(base, current)) mark(block);
  // The state half: block keys catch words, and a pure state change — a card
  // in a different column, a pick on a different option — has no text of its
  // own. Compare declared state instead: the base fold above against the
  // publisher's current one. Body records are words and the block keys above own
  // them.
  for (const [id, now] of readApplication().effective.widgets) {
    const before = baseWidgets.get(id);
    const widget = elementById(id);
    // New to this version: the content half marks it.
    if (!before || !widget || inChrome(widget) || quoted(widget)) continue;
    for (const [verb, spec] of now.specs) {
      if (!spec.record || spec.record.kind === "body" || !before.specs.has(verb))
        continue;
      if (spec.record.kind === "position") {
        // The moved card itself is where the change reads: one in another
        // container, or one out of order among those its container held at the
        // base, the fewest cards whose moving explains the new order.
        const was = before.state[verb].value;
        const placed = Object.values(was).flat();
        for (const [container, ids] of Object.entries(now.state[verb].value)) {
          const stayed = was[container] ?? [];
          const kept = inOrder(
            stayed.filter((unit) => ids.includes(unit)),
            ids.filter((unit) => stayed.includes(unit)),
          );
          for (const unit of ids) {
            if (!placed.includes(unit) || kept.has(unit)) continue;
            const moved = elementById(unit);
            if (moved) mark(moved);
          }
        }
        continue;
      }
      const { value } = obligationValue(now, verb, true);
      if (
        JSON.stringify(value) ===
        JSON.stringify(obligationValue(before, verb, true).value)
      )
        continue;
      // The option now picked is where a pick reads; anything else reads on its
      // widget.
      // An attribute record's value is the ids it picks.
      const ids = /** @type {string[]} */ (value);
      const picked =
        spec.record.kind === "attribute" && ids.length === 1
          ? elementById(ids[0])
          : null;
      mark(picked ?? widget);
    }
  }
  // One pass over everything marked, after both halves, because the two halves mark
  // for different reasons and a block reached by either is a block a user can ask
  // about. The words are taken here rather than at the press: this is the one moment
  // the two sources are in hand, and holding them open for a press that may never come
  // would keep two more documents alive for the life of the comparison.
  const opaque = diffOpaqueSel();
  for (const block of diffMarked) {
    if (!block.matches(ADDRESSABLE) || block.closest(opaque)) continue;
    const [was, is] = [base, current].map(({ doc }) => doc.getElementById(block.id));
    diffWordsOf.set(block, {
      was: was ? comparisonWords(was, opaque) : null,
      is: is ? comparisonWords(is, opaque) : null,
    });
  }
  return diffMarked.size;
}
// ---------- one marked block's inline comparison ----------
// `wrote` is the authority for the two texts, read from the two sources; the live block
// offers a comparison only while it reads the same as its source (`inlineComparison`).
// This companion reading keeps the same normalized text with a boundary back into the
// live block's authored text nodes, so a run the alignment calls inserted can be painted
// in place. Generated labels and deletions wear
// `.lf-ui`; comments, copies, and later comparisons therefore continue to read the exact
// current document rather than the temporary historical words on screen.
const inlineId = (target) => `lf-version-inline-${target.id}`;
const authoredReading = (target) => {
  const segments = comparisonTextNodes(target);
  return { ...readingFrom(segments), segments };
};

function pointAt(target, reading, offset) {
  if (!reading.units.length) return { node: target, offset: 0 };
  return offset === reading.units.length
    ? reading.units.at(-1).end
    : reading.units[offset].start;
}

function insertAt(target, reading, offset, node) {
  const point = pointAt(target, reading, offset);
  if (point.node.nodeType === Node.ELEMENT_NODE) {
    move(point.node, node, point.node.childNodes[point.offset] ?? null);
    return;
  }
  const text = point.node;
  if (point.offset === 0) move(text.parentNode, node, text);
  else if (point.offset === text.data.length)
    move(text.parentNode, node, text.nextSibling);
  else move(text.parentNode, node, text.splitText(point.offset));
}

function rangesAt(reading, start, end) {
  const first = reading.units[start];
  const last = reading.units[end - 1];
  if (!first || !last) return [];
  // Normalized characters can span nodes, even a collapsed space on either side
  // of an excluded widget. Paint only the retained segments, never the DOM gap.
  return reading.segments
    .slice(
      reading.segments.findIndex(({ node }) => node === first.start.node),
      reading.segments.findIndex(({ node }) => node === last.end.node) + 1,
    )
    .map((segment) => ({
      ...segment,
      start: segment.node === first.start.node ? first.start.offset : segment.start,
      end: segment.node === last.end.node ? last.end.offset : segment.end,
    }))
    .filter(({ start, end }) => end > start)
    .map((segment) => rangeOf([segment]));
}

function paintInlineInsertions() {
  const ranges = [...inlineOpen.values()].flatMap((entry) => entry.ranges);
  if (ranges.length) CSS.highlights.set("lf-version-insert", new Highlight(...ranges));
  else CSS.highlights.delete("lf-version-insert");
}

function openInlineComparison(target) {
  const before = diffWordsOf.get(target).was;
  const reading = authoredReading(target);
  const current = currentVersionToken();
  const label = el(
    "span",
    "lf-ui lf-quiet lf-version-inline-label",
    before === null
      ? `New since v${diffBase.value}`
      : `v${diffBase.value} → ${current}`,
  );
  label.id = inlineId(target);
  label.setAttribute(
    "aria-label",
    before === null
      ? `New since version ${diffBase.value}`
      : `Inline comparison from version ${diffBase.value} to ${current}`,
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
  const ranges = additions.flatMap(([start, end]) =>
    rangesAt(currentReading, start, end),
  );
  target.classList.toggle("lf-version-inline", hasTextChange);
  inlineOpen.set(target, { nodes, ranges });
  paintInlineInsertions();
  layoutChanged(target);
  return before === null
    ? `v${diffBase.value} had nothing here`
    : `showing an inline diff from v${diffBase.value}`;
}

function closeInlineComparison(target) {
  const entry = inlineOpen.get(target);
  inlineOpen.delete(target);
  target.classList.remove("lf-version-inline");
  for (const node of entry?.nodes ?? []) node.remove();
  paintInlineInsertions();
  layoutChanged(target);
  return `inline diff from v${diffBase.value} hidden`;
}

// What a text-changing marked block holds for the margin's disclosure reading. A pure
// state change remains marked but offers no empty prose comparison. The one controlled
// id is a quiet label at the start of the block. It names the versions for assistive
// reading while the margin and Page Map carry that provenance visually, outside the
// passage whose words are being compared. The comparison paints the source's words onto
// the live block's, so a block whose live words aren't its source's, such as one a
// module writes into, stays marked whole and offers none.
export const inlineComparison = (target) => {
  const words = diffOn.value ? diffWordsOf.get(target) : undefined;
  return words && words.was !== words.is && words.is === comparisonWords(target)
    ? {
        id: inlineId(target),
        open: inlineOpen.has(target),
        offer: `v${diffBase.value} → ${currentVersionToken()}`,
      }
    : null;
};

// The press, and the sentence to say about it — composed here, where the versions are
// named. The comparison signal also tracks its current rendering: the same pass
// that reads the marks reads the margin entry's relation back.
export function toggleInlineComparison(target) {
  if (!inlineComparison(target)) return null;
  const said = inlineOpen.has(target)
    ? closeInlineComparison(target)
    : openInlineComparison(target);
  tick(comparisonGeneration);
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
// Whether the comparison is active and what against, or which base a stopped one is
// waiting on — the only thing that decides it, the marks and the paint being renderings
// rather than a second copy.
function setDiff(on, base, pendingBase = null) {
  batch(() => {
    diffOn.value = on;
    diffPendingBase.value = pendingBase;
    if (on) diffBase.value = base;
    if (!on) {
      diffRequest++; // a stop outranks a comparison still on its way
      // Inline diffs leave with the block marks. Historical words or insertion paint
      // under a block nothing marks any more would leave half of the comparison behind.
      for (const target of [...inlineOpen.keys()]) closeInlineComparison(target);
      diffWordsOf.clear();
      for (const b of diffMarked) b.classList.remove("lf-ins-block");
      diffMarked.clear();
    }
    // Native effects run after both the selection and its marked DOM have settled.
    tick(comparisonGeneration);
  });
}
// The one way a comparison starts, from a row's press, from the walk through the menu,
// or from an activation putting back the one it dropped. It states a base rather than
// toggling one — the toggle is a press's own reading of it, and the walk has none to
// spend, standing on a row being what makes it the base however many times the user
// arrives there. Everything touching the live page happens in one synchronous stretch
// after the single await: the walk asks for a comparison per row, and a marking pass
// that could interleave with the next row's would leave two bases' marks in place
// under a picker naming one of them.
async function showComparison(base) {
  // Selection is immediate even though its result needs two documents. Clear the prior
  // marks, move the menu's checked state to the requested base, and expose the wait as
  // busy. A fast walk then never leaves the last completed base highlighted under focus
  // on a different row. One presentation says both, so the picker never passes through
  // an unlit state it is about to leave.
  setDiff(false, null, base);
  const mine = ++diffRequest;
  const baseVersion = stamped(base);
  const baseRevision = baseVersion?.revision;
  if (baseRevision == null) {
    diffPendingBase.value = null;
    raiseError(`Couldn't load v${base}`);
    return;
  }
  const documentRequest = authoredDocument(baseVersion.url);
  let doc;
  let reading;
  let baseAuthored;
  try {
    while (mine === diffRequest) {
      const throughSeq = runtime.lastEventSeq;
      [doc, reading] = await Promise.all([
        documentRequest,
        baseReading(baseRevision, throughSeq),
      ]);
      if (mine !== diffRequest) return;
      if (runtime.lastEventSeq === throughSeq) break;
    }
    if (mine !== diffRequest) return;
    // Typed authored state reads the source, which formatting leaves alone: it formats
    // a copy (`paintedSource`), with the renderer loaded here.
    baseAuthored = stageAuthoredStates(doc, new Map());
    await loadDeclaredMarkdown(doc);
  } catch {
    if (mine === diffRequest) {
      diffPendingBase.value = null;
      raiseError(`Couldn't load v${base}`);
    }
    return;
  }
  if (mine !== diffRequest) return;
  const n = applyDiff(doc, baseAuthored, base, reading);
  setDiff(true, base);
  notice(
    n
      ? `${n} changed passage${n === 1 ? "" : "s"} since v${base}`
      : `No text changes since v${base}`,
  );
}
// A press names one base, so pressing the current one again is the way off it: Compare is a
// toggle where it is lit and a switch of base where it isn't. The keyboard's way off is the
// walk itself — up to the version being read, which is comparable with nothing and so
// stops rather than re-bases.
const pressComparison = (base) =>
  (diffOn.value && base === diffBase.value) || diffPendingBase.value === base
    ? setDiff(false)
    : showComparison(base);

export const comparisonBase = () => (diffOn.value ? diffBase.value : null);
// Selection leads the documents it needs. Menu focus follows that immediate reading,
// while the public projection above stays paired with the marks that have settled.
const selectedBase = () => diffPendingBase.value ?? comparisonBase();

export function comparisonChanges(owner = null) {
  comparisonGeneration.value;
  const changes = diffOn.value ? [...diffMarked] : [];
  return owner
    ? changes.filter((block) => block !== owner && under(block, owner))
    : changes;
}

// ---------- another version's document ----------
// Comparison reads an inert document. A revision keeps the layer it captured, and the
// server says so — both this document and the projection beside it answer for that
// generation rather than the page's — so neither is a delivery answer and neither goes
// through the gate. A layer that really did move under the user reaches them through
// the state feed, which is the live channel.
async function authoredDocument(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`couldn't load ${url} (${response.status})`);
  const doc = new DOMParser().parseFromString(await response.text(), "text/html");
  return authoredMarkup(doc);
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

/**
 * @template RetainedLocation
 * @template ObligationLocation
 * @param {{
 *   initialDocument: NonNullable<ReturnType<typeof takeInitialDocument>>,
 *   compositionInput: any,
 *   openThread: any,
 *   refreshThread: any,
 *   midComposition: any,
 *   hasPending: any,
 *   readAndApply: any,
 *   syncLayout: any,
 *   captureRetainedCurrentLocation?: () => RetainedLocation,
 *   restoreRetainedCurrentLocation?: (currentLocation: RetainedLocation) => boolean,
 *   captureObligationCurrentLocation?: () => ObligationLocation,
 *   restoreObligationCurrentLocation?: (currentLocation: ObligationLocation) => void,
 *   versions: { press: () => void },
 * }} controller */
export function createVersionController({
  initialDocument,
  compositionInput,
  openThread,
  refreshThread,
  midComposition,
  hasPending,
  readAndApply,
  syncLayout,
  captureRetainedCurrentLocation = () => null,
  restoreRetainedCurrentLocation = () => false,
  captureObligationCurrentLocation = () => null,
  restoreObligationCurrentLocation = () => {},
  // The chrome's Versions, which `g V` opens or puts away (floating-panel.js, `doors`).
  versions,
}) {
  let {
    authoredBodyAttributes,
    authoredHeadNodes,
    authoredHtmlAttributes,
    source: authoredSource,
  } = initialDocument;
  // Every revision pairs its own source here; a superseded source's pairs leave with it.
  const sourcePairs = initialDocument.pairs;
  versionSource = () => ({ source: authoredSource, pairs: sourcePairs });
  // The delivery root removed when comparing this revision with the next.
  let authoredRoot = layerRoot(document);
  // Semantic reading position preserved across authored-document replacement.
  const VIEW_KEY = "lf-view";
  const HANDOFF_KEY = "lf-revision-handoff";

  // g V names the versions, and what each one changed: the chrome's Versions, which the
  // press opens or puts away, as its menu row does.
  const PICKER = {
    id: "version.open",
    ready: savedReadingSettled,
    keys: ["Shift+v"],
    title: "versions",
    run: () => versions.press(),
    // The same predicate the menu's Escape stands on, so the key cannot open a layer the
    // way out is not live over. The walk being empty is the menu's business, not this key's.
    when: versionsOffered,
  };

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
      if (runtime.showsActive) return;
      forceActivation = true;
      readAndApply();
      return;
    }
    location.href = PAGE_SCOPE || "/";
  };

  // ---------- live revision activation ----------
  // What the outgoing revision wrote on a root and the arriving one does not comes off,
  // what the arriving one writes differently goes on, and what both write is left
  // in place. These roots are `html` and `body`, where a class or attribute that comes
  // off and goes back on restyles the whole document, so the layer's rule against
  // rewriting what a node already says (`keeps`) matters most here.
  function replaceAuthoredAttributes(target, source, prior) {
    const runtimeState = runtimeRootState(target);
    const next = authoredAttributes(source);
    const tokens = (value) => new Set(value?.split(" "));
    const nextTokens = tokens(next.get("class"));
    for (const token of tokens(prior.get("class")))
      if (!nextTokens.has(token)) target.classList.remove(token);
    for (const token of nextTokens)
      if (!target.classList.contains(token)) target.classList.add(token);
    // Inline style is the one root attribute whose members can have different owners.
    // Registered runtime properties survive; every other declaration is authored and
    // retires with its revision like every other source attribute. Declarations are
    // compared by name, not value, since an empty custom property (`--x: ;`) reads
    // back as "", and `setProperty` with "" removes rather than declares, so an empty
    // one is written as the single space that parses to it.
    const declared = new Set(source.style);
    const priorStyle = document.createElement(target.localName).style;
    priorStyle.cssText = prior.get("style") ?? "";
    for (const property of priorStyle)
      if (!runtimeState.styles.has(property) && !declared.has(property))
        target.style.removeProperty(property);
    const existing = new Set(target.style);
    for (const property of declared) {
      if (runtimeState.styles.has(property)) continue;
      const value = source.style.getPropertyValue(property);
      const priority = source.style.getPropertyPriority(property);
      if (
        !existing.has(property) ||
        target.style.getPropertyValue(property) !== value ||
        target.style.getPropertyPriority(property) !== priority
      )
        target.style.setProperty(property, value || " ", priority);
    }
    const plain = (name) =>
      name !== "class" && name !== "style" && !runtimeState.attributes.has(name);
    for (const name of prior.keys())
      if (plain(name) && !next.has(name)) target.removeAttribute(name);
    for (const [name, value] of next) if (plain(name)) keeps(target, name, value);
    return next;
  }

  // The chrome's sheets are adopted, not head nodes, so they cascade after everything
  // the head holds whatever order it is written in; the authored share goes at the end.
  function activateHead(doc, revision) {
    const source = [...doc.head.children].filter(versionedHeadNode);
    const current = [...document.head.children].filter((node) =>
      authoredHeadNodes.has(node),
    );
    if (
      current.length !== authoredHeadNodes.size ||
      current.length !== source.length ||
      current.some((node, index) => !node.isEqualNode(source[index]))
    ) {
      for (const node of authoredHeadNodes) node.remove();
      const next = new Set();
      for (const node of source) {
        const imported = document.importNode(node, true);
        document.head.append(imported);
        next.add(imported);
      }
      authoredHeadNodes = next;
    }
    /** @type {HTMLMetaElement | null} */
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

  // Every element under a root in document order, including inert template contents.
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
  // never touched it. Any attribute may name media; comparison removes only the
  // exact delivery root rather than keeping a second list of resource attributes.
  // Script and style bodies use that same rule without reclassifying their content.
  const deferredScript = "data:text/javascript;charset=utf-8,";
  const unrooted = (value, root) => {
    if (value.startsWith(deferredScript)) {
      // revision_delivery defers inline classics as URL-encoded source, padded to
      // their document line. That diagnostic padding is not the script's identity.
      value =
        deferredScript + value.slice(deferredScript.length).replace(/^(?:%0A)+/, "");
      if (root) value = value.split(encodeURIComponent(root)).join("%2F");
    }
    return root && value.includes(root) ? value.split(root).join("/") : value;
  };
  // One attribute, read the same way: an address that differs only by the revision it
  // was delivered under is the same address, and the page keeps the one it has, which
  // is still served because revisions are immutable.
  const sameValue = (held, value, arrivingRoot) =>
    unrooted(held, authoredRoot) === unrooted(value, arrivingRoot);
  function sameAuthoredMarkup(before, after, arrivingRoot) {
    if (before.isEqualNode(after)) return true;
    const strip = (element, root) => {
      const copy = element.cloneNode(true);
      if (!root) return copy;
      for (const node of [copy, ...elementsWithin(copy)]) {
        if (node.matches("style, script"))
          node.textContent = unrooted(node.textContent, root);
        for (const attribute of node.attributes)
          attribute.value = unrooted(attribute.value, root);
      }
      return copy;
    };
    return strip(before, authoredRoot).isEqualNode(strip(after, arrivingRoot));
  }
  // An x-patch container retains authored markup while the inputs its renderer
  // consumes stay the same. A structured member list, or a declared x-views list,
  // consumes its direct members' identities and attributes. A markup container
  // without views consumes only its own attributes: the patch owns its evidence,
  // including native attributes. A generated authored body likewise separates that
  // evidence from the renderer's inputs.
  const shell = (element, members) => {
    const copy = element.cloneNode(false);
    if (members)
      for (const child of element.childNodes) copy.append(child.cloneNode(false));
    return copy;
  };
  const reachesMembers = (before, after, arrivingRoot) => {
    const entry = registry[before.localName];
    if (entry?.["x-patch"] !== "members") return false;
    const members =
      !authoredBody(sourcePairs.get(before)) &&
      (entry["x-content"] === "members" || entry["x-views"]);
    return sameAuthoredMarkup(
      shell(before, members),
      shell(after, members),
      arrivingRoot,
    );
  };

  // Preparation and installation use the same matching, widget ownership, and resource
  // equality. A retained subject is proved through every containing owner, not by an
  // id or matching markup alone.
  function patchRules(doc) {
    const arrivingRoot = layerRoot(doc);
    return {
      pairs: sourcePairs,
      contains: under,
      declared: upgraded,
      body: authoredBody,
      reaches: (before, after) => reachesMembers(before, after, arrivingRoot),
      same: (before, after) => sameAuthoredMarkup(before, after, arrivingRoot),
      sameValue: (held, value) => sameValue(held, value, arrivingRoot),
    };
  }

  // Patch against the authored baselines. Retained nodes keep their live state;
  // replacement nodes recover eligible state through carry and obligation restoration.
  function captureEditingContinuity() {
    const draftEditing = captureDraftEditing();
    return {
      draftEditing,
      replyThread: draftEditing?.mirrored ? heldThreadId() : null,
      // A replaced reply box takes focus back either way, but is brought into view only
      // where it marked the user's place (user-place.js, `focusedInView`).
      replyInView: focusedInView() !== null,
      // Obligation location is the fallback for unnamed controls. An exact editor already
      // has a replacement identity, so its parent obligation does not also own focus.
      obligationCurrentLocation: draftEditing
        ? null
        : captureObligationCurrentLocation(),
    };
  }

  // Mechanical landing is outside proved semantic presentation. An unexpected
  // failure reports once through the page error owner and leaves both installs free
  // to finish receipt accounting and initial presentation/deferred arrivals.
  async function landContinuity(land) {
    try {
      await land();
    } catch (error) {
      reportPageError(error, `Revision continuity failed`);
    }
  }

  async function restoreEditingContinuity(continuity, currentIntent) {
    if (!currentIntent()) return;
    const { draftEditing, replyThread, replyInView, obligationCurrentLocation } =
      continuity;
    restoreObligationCurrentLocation(obligationCurrentLocation);
    const mayRestore = restrictUserIntent(currentIntent, () =>
      draftEditingStands(draftEditing),
    );
    if (!mayRestore()) return;
    if (restoreDraftEditing(draftEditing, focused())) return;
    const input = replyThread
      ? await restoreReplyEditing(draftEditing, async () => {
          // Mechanical recovery changes which settled discussion currently stands.
          // Present that session before its route reads the annotation directory.
          await refreshThread();
          return mayRestore()
            ? replyDestination(replyThread, openThread, mayRestore, {
                scroll: replyInView,
              })
            : null;
        })
      : draftEditingDestination(draftEditing, mayRestore.handoff);
    if (!replyThread && input)
      mayRestore.handoff(() => focusDestination(input, "return"));
    if (mayRestore()) restoreDraftEditing(draftEditing, input);
  }

  async function activateRevision(doc, target) {
    const currentIntent = retainUserIntent();
    const view = captureView();
    const retainedCurrentLocation = captureRetainedCurrentLocation();
    const editingContinuity = captureEditingContinuity();
    // A pending selection counts too: cancel its old-document request before the
    // authored page changes, then restore that base against the arriving revision.
    const comparedFrom = selectedBase();
    if (comparedFrom !== null) setDiff(false);
    const live = pageDocument();
    const outgoing = authoredSource;
    // Capture before replacing nodes, using the outgoing source as the baseline.
    const carry = captureCarry(live, authoredSource);
    const source = pageDocument(doc);
    const arrivingRoot = layerRoot(doc);
    const rules = patchRules(doc);
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
    const arrivedDescriptors = new Map();
    const prior = readApplication().document;
    // The arriving revision's source is the complete page baseline. Capture it before
    // insertion can connect a custom element and turn authored input into presentation.
    rememberAuthoredParents(source);
    const sourceAuthored = stageAuthoredStates(source, new Map());
    const sourceDescriptors = stageWidgetDescriptors(source, {
      kind: "page",
      revision: target.revision,
    });
    // Elements whose attributes the patch rewrote in place. What a dressing pass reads
    // off an attribute — a word an element says, the language of a code block — is
    // owed again, and these are the roots the install dresses beside the arrivals.
    const touched = [];
    const arrive = (node, parent) => {
      const arriving = document.importNode(node, true);
      pairSources(node, arriving, sourcePairs);
      if (arriving.nodeType === Node.ELEMENT_NODE) {
        rememberPassageParts(arriving);
        // Keep authored parentage for later passage readings. Widget identity was
        // already captured from the complete incoming source, where every enclosing
        // owner is present; copied arrivals bind that same reading before connection.
        rememberAuthoredParents(arriving, parent);
        const bindings = [];
        for (const element of [arriving, ...arriving.querySelectorAll("[id]")]) {
          const descriptor = sourceDescriptors.descriptors.get(element.id);
          if (!descriptor) continue;
          bindings.push({ element, descriptor });
          arrivedDescriptors.set(element.id, descriptor);
        }
        // Bind the actual arrival before insertion can synchronously connect its
        // custom element. The publisher still holds the outgoing document until the
        // patch and matching server reading are admitted together, so this descriptor
        // cannot borrow the old widget's semantic state during preparation.
        commitWidgetDescriptors({ bindings });
        formatDeclaredMarkdown(arriving);
        arrived.push(arriving);
      }
      return arriving;
    };

    let restoreCarryScroll;
    await patchDocument(live, () => {
      authoredHtmlAttributes = replaceAuthoredAttributes(
        document.documentElement,
        doc.documentElement,
        authoredHtmlAttributes,
      );
      // Delivery states each revision's page Layout on its root, where the Layout reads
      // its body's geometry, so the arriving revision's comes across with it.
      keeps(
        document.documentElement,
        "data-lf-layout",
        doc.documentElement.getAttribute("data-lf-layout"),
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
        ...rules,
        arrive,
        generated,
        touched: (element) => touched.push(element),
      });
      restoreCarryScroll = restoreCarry(
        carry.records,
        carry.held,
        currentIntent.handoff,
      );
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
    authoredSource = source;
    authoredRoot = arrivingRoot;
    const nextAuthored = new Map(
      [...prior.authored].filter(
        ([id]) => prior.descriptors.get(id)?.document.kind === "thread",
      ),
    );
    for (const [id, value] of sourceAuthored) nextAuthored.set(id, value);
    // The incoming source owns page order. Retained controllers keep the descriptor
    // identity captured with their live node; new or rewritten nodes use the incoming
    // source's capture. Frozen thread documents follow the page in log order.
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
      document: {
        ...prior,
        revision: target.revision,
        stamp: target.version ?? null,
        authored: nextAuthored,
        descriptors,
      },
      // The incoming publication opens recovered editors. State application alone
      // adopts this capture and proves that epoch before returning mechanical places.
      // This continuation never enters the semantic document snapshot.
      land: () =>
        landContinuity(async () => {
          // A revision ends every hold, whether or not the reader's intent lets the
          // view be restored: its own handoff places the reader.
          releaseHolds();
          settleDocumentLayout();
          syncLayout();
          if (currentIntent()) {
            restoreView(view, currentIntent);
            restoreRetainedCurrentLocation(retainedCurrentLocation);
            restoreCarryScroll();
            await restoreEditingContinuity(editingContinuity, currentIntent);
          }
          if (comparedFrom !== null) showComparison(comparedFrom);
          // Each block the revision changed takes a newly arrived message's tint,
          // which paints and moves nothing.
          const outgoingSource = paintedSource(
            outgoing,
            readApplication().effective.widgets,
          );
          for (const block of changedSince(outgoingSource))
            backgroundFlash(block, flashDuration());
          notice(`Updated to ${target.label}`, { background: true });
        }),
    };
  }

  // The move a state asks of the live root, prepared ahead of the commit that makes it.
  // Null where there is nothing to follow — no newer revision, or a document that failed
  // to load, which is reported; the commit's own render then lights the chip as the way
  // to try again. A new layer generation arrives here as a revision whose executable
  // changed, since the server answers this tab in its revision's layer (http.py,
  // `_named_layer`); only one this Leaf can no longer admit input against is refused
  // instead, and the refusal's probe of the document source reloads it at once
  // (layer-client.js, `sourceMovedOn`).
  // Whether the move happens now is asked at the commit: an unresolved delivery,
  // `midComposition`, or an open menu defers it, unless the chip was pressed (goActive)
  // — the one override, spent by the install it forced.
  async function prepareActivation(state) {
    const target = state.active;
    if (
      !LIVE_ROOT ||
      runtime.currentRevision === null ||
      target.revision <= runtime.currentRevision
    )
      return null;
    const activates = (retains) =>
      target.revision > runtime.currentRevision &&
      !hasPending() &&
      (!midComposition(retains) || forceActivation);
    // The revision either install leaves this document showing. State application reads
    // it to judge the answer before the install edits anything, and adopts the answer
    // against it afterwards, so the document's revision and the state that speaks for it
    // become current in one reading.
    if (!servedExecutable || target.executable !== servedExecutable)
      return {
        revision: target.revision,
        activates: () => activates(),
        install: reloadInto(target),
      };
    let doc;
    try {
      doc = await revisionDocument(target);
      // Step 6 of the startup order, on the same background stretch as the document
      // itself: this revision may carry a tag the current document never held, and
      // insertion is where its element is constructed. Asked for here so the install
      // spends nothing on a fetch while the user is looking at the page. Inside this
      // try, because the loader keeps a rejected import: one 404 on a module an arriving
      // revision introduces would otherwise reject every later state read for good.
      await preloadWidgets(pageDocument(doc));
    } catch (error) {
      reportPageError(error, `revision ${target.revision} failed to load`);
      return null;
    }
    return {
      revision: target.revision,
      activates: () =>
        activates(
          (node) =>
            // Installation closes inline comparisons, which can own the comment’s
            // rendered subject independently of the authored patch.
            selectedBase() === null &&
            patchRetains(authoredSource, pageDocument(doc), node, patchRules(doc)),
        ),
      install: () => {
        forceActivation = false;
        return activateRevision(doc, target);
      },
    };
  }

  // Changed executable identity requires a fresh document. Serialize the continuity
  // handoff before reload; installArrival consumes it once after upgrade.
  const reloadInto = (target) => () => {
    forceActivation = false;
    const view = captureView();
    const editingContinuity = captureEditingContinuity();
    tabStore.set(VIEW_KEY, JSON.stringify(view));
    tabStore.set(
      HANDOFF_KEY,
      JSON.stringify({
        revision: target.revision,
        url: location.href,
        view,
        retainedCurrentLocation: captureRetainedCurrentLocation(),
        ...editingContinuity,
        carry: captureCarry(pageDocument(), authoredSource).records,
        comparison: selectedBase(),
        pointer: pointerAt(),
      }),
    );
    const marked = new URL(location.href);
    marked.searchParams.set(PRIVATE_REVISION_PARAM, String(target.revision));
    replaceEntry(marked);
    location.reload();
    // The new document owns the continuation. Keeping this activation pending
    // prevents the old realm from applying state while navigation commits.
    return new Promise(() => {});
  };

  // ---------- reading continuity across a replacement ----------
  // Capture passage and decision landmarks plus each reading region's position. Resolve
  // a passage first, then its section, then a raw offset in the same scroller at the
  // same width and revision (reading-place.js, `rawOffsetFits`). Document travel stores
  // this reading per tab; restored chrome layout precedes scroll recovery.

  function captureView() {
    dropGonePlaces();
    const blocks = textBlocks();
    const active = activeReadingRegion(readingRegions(), blocks);
    const view = Object.assign(capturePlace(null, blocks), {
      revision: runtime.currentRevision,
      activeRegion: active?.id,
      regions: Object.fromEntries(
        [...places].flatMap(([id, { reading }]) =>
          id === PAGE ? [] : [[id, reading]],
        ),
      ),
    });
    for (const region of readingRegions()) {
      if (!shownRegionBounds(region)) continue;
      if (regionScrollBehavior(region) === "bounded" || region.id === active?.id)
        view.regions[region.id] = capturePlace(region, blocks);
    }
    return view;
  }

  function restoreView(view, currentIntent) {
    // Every restore of a whole view is a handoff that supersedes the places a shift
    // was holding, as a shift while widgets upgrade before an arrival lands.
    releaseHolds();
    const regions = new Map(readingRegions().map((region) => [region.id, region]));
    const active =
      regions.get(view.activeRegion) ??
      containingReadingRegionFor(focusedInView()) ??
      readingRegionFor(pageReadingBlock());
    if (active) reveal(active.host, currentIntent);
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
      restorePlace(activeReading, regions.get(active.id), currentIntent);
      restored.add(activeScroller);
    } else {
      restorePlace(view, null, currentIntent);
      restored.add(pageScroller);
    }
    // A bounded region can stand in a page that scrolls as well, as a visual review's
    // capture does in a document page: the page keeps its own place beside the region's.
    if (
      !restored.has(pageScroller) &&
      (hasLandmark(view) || rawOffsetFits(view, pageScroller))
    ) {
      restorePlace(view, null, currentIntent);
      restored.add(pageScroller);
    }
    for (const [id, reading] of Object.entries(view.regions ?? {})) {
      const region = regions.get(id);
      if (!region || !shownRegionBounds(region)) continue;
      const box = effectiveScroller(region);
      if (restored.has(box)) continue;
      if (!hasLandmark(reading) && !rawOffsetFits(reading, box)) continue;
      restorePlace(reading, region, currentIntent);
      restored.add(box);
    }
  }

  // The revision handoff restores the region the user works first, so that a box two
  // regions share lands where that one left it. Focus names a region only while in view
  // (user-place.js, `focusedInView`): a pane the reader scrolled away from, though it
  // keeps their focus, would take them back to it.
  const activeReadingRegion = (
    candidates = readingRegions(),
    blocks = textBlocks(),
  ) => {
    const focusedRegion = containingReadingRegionFor(focusedInView());
    if (focusedRegion && candidates.some(({ id }) => id === focusedRegion.id))
      return focusedRegion;
    const recent = candidates.find(({ id }) => id === recentReadingRegion()?.id);
    if (recent) return recent;
    return candidates
      .map((region) => [region, blocksOnScreen(region, blocks).next().value?.[1]])
      .filter(([, rect]) => rect)
      .sort(([, a], [, b]) => a.top - b.top)[0]?.[0];
  };

  // ---------- the user's place in each scroller, across layout changes ----------
  // A window crossing a width, a viewport changing height or a panel opening rewraps the
  // page and its regions, and can hand a region to another scroller, in layout, with no
  // moment before it to read the user's place in. So each scroller's place is recorded as
  // the user leaves it, and restored when its layout shifts.
  //
  // One place per scroller, read from the words that scroller carries: the page's from
  // every word outside a box that scrolls on its own, flowing regions included
  // (reading-place.js, `capturePlace`), and each bounded region's from its body. It is
  // recorded when a scroll the reader made comes to rest or ends in that scroller, and
  // where the user is or steps, in the scroller holding them (`recordPlaces`). A
  // place whose scroller is gone goes with the next record.
  //
  // After a shift, each scroller it touched takes the newest place that speaks for it,
  // newest by the reader's acts rather than by when it was read:
  // its own, one recorded in a scroller that carried its words before the shift, or one
  // whose landmark it now carries. Where a region was handed across, that is usually the
  // place recorded in the scroller that carried it before, so a pane that turns into
  // flow brings its passage to the page, and a passage the page carried is found in the
  // pane that now scrolls it. Where the newest such place has no landmark the scroller
  // carries, it lands nowhere rather than on an older place the user has since left. A
  // scroller given no place keeps what the browser's anchoring left, moved with its
  // landing band.
  //
  // Only the user moves their place, and a scroll is theirs when it ends as their choice
  // (scrolling.js, `chosenSince`): a wheel, a key, a landing, a page's script or the
  // browser's own travel, but not a clamp, an anchoring adjustment or a place keeper's
  // write. A restore is the runtime's move: read back, it can name other words than the
  // place it restored, and it can fall short of that place, cut off by its box's range,
  // as a pane already at its top cannot lower its words to where the page had them, or a
  // page cannot reach a passage below a widget still drawn at its old size. So a box the
  // runtime restored holds the place it was given until someone moves it (`held`): input
  // the reader aims at the box, or a scroll that carries the held landmark with it.
  // Leaving the window or opening the browser's find bar moves nothing, so neither ends
  // a hold; the scroll find makes is read like any other. Nothing records over a held
  // box, so the next shift starts from the words the user read rather than from wherever
  // the runtime left them, and while the shift's layout settles the place is applied
  // again (`watchHolds`), as a widget drawing a frame late moves it. A revision ends
  // every hold, since its own handoff places the reader. Between a shift and its restore
  // nothing is recorded, since the shift's own scrolls are no one's place, and a box the
  // reader chose a scroll in since its place was recorded is left where they chose. The
  // end of a scroll a restore started is the runtime's, wherever layout carried the box
  // before it (`writing`), and input counts for the box it scrolls, not the document.
  //
  // A region can show one subject of several in turn (reading-regions.js,
  // `showReadingSubject`). The place of a subject leaving is kept by subject, and the
  // one showing returns the reader to theirs.
  const PAGE = "$page";
  const places = new Map();
  let placeCount = 0;
  let shifting = false;
  // Each hold by the scroller it holds, named as places are: the page, or a bounded
  // region's id. The box itself is held weakly, so a box a widget replaces without a
  // revision leaves memory with the document, and its hold ends at its next reading.
  const holds = new Map();
  const subjectPlaces = new Map();
  let reapply = null;
  // The identity a box scrolls as: the page, a bounded region's id, or undefined.
  const boxId = (box) => (box === pageScroller ? PAGE : regionForBox(box)?.id);
  // The hold `box` still keeps, or null once someone has moved it: input aimed at the
  // box, or a scroll that carried the held landmark with it. Which moved, the box or
  // what it shows, says whose the move was. A scroll moves the box and the landmark by
  // the same distance, whoever made it and whether or not its sequence has ended yet.
  // Layout moves the words, under a box that stays or that anchoring moves to keep
  // something else still, by a distance of its own, and the next application puts them
  // back. A scroll and a layout change in one frame are ambiguous: they read as
  // layout's only while the shift's layout settles, and as someone's after that. A
  // landmark the box no longer carries, or a box that no longer scrolls as the one held,
  // ends the hold.
  const held = (box) => {
    const id = boxId(box);
    return id === undefined ? null : holdOf(id);
  };
  function holdOf(id) {
    const hold = holds.get(id);
    if (!hold) return null;
    const box = hold.box.deref();
    const region = box && boxId(box) === id ? regionForBox(box) : undefined;
    const moved = region === undefined ? "gone" : movedAway(box, hold, region);
    const acted = Boolean(box) && inputSince(box, hold.since);
    if (!moved && !acted && hold.currentIntent()) return hold;
    holds.delete(id);
    // Where the reader acted in the box the restore put them in, that place is theirs,
    // as if recorded before they acted, so whatever their act moves records over it.
    // Where a scroll carried the landmark away, the place it left is that scroll's.
    if (moved === "carried" || (!moved && acted))
      places.set(id, {
        reading: moved ? capturePlace(region) : hold.reading,
        at: ++placeCount,
        choices: scrollChoices(),
        inputs: moved ? inputCount() : hold.since,
      });
    return null;
  }
  // Whether the held place still stands in its box: null where it does, or where
  // layout alone moved it; "carried" where a scroll took the landmark with the box;
  // "gone" where the box no longer carries it. A box that scrolled while its landmark
  // moved by another distance is layout's while the shift's layout settles, when
  // anchoring answers a change the layout made, and someone's after that, as a script
  // that scrolls as content grows above the reader. A landmark a widget is repainting is
  // missing only for a moment while the layout settles, so the hold waits it out.
  const movedAway = (box, hold, region) => {
    const settling = reapply !== null;
    const node = placeNode(hold.reading);
    if (!node) return settling ? null : "gone";
    // A landmark another box now carries, as a pane taking its words from the page, is
    // no place of this box's to hold.
    if (boxOf(node) !== box) return "gone";
    const now = placeOffset(hold.reading, region);
    if (now === null) return settling ? null : "gone";
    const scrolled = box.scrollTop - hold.top;
    const shifted = now - hold.offset;
    if (Math.abs(shifted) <= SCROLL_SLACK) {
      hold.top = box.scrollTop;
      return null;
    }
    if (Math.abs(scrolled) <= SCROLL_SLACK) return null;
    if (Math.abs(shifted + scrolled) <= SCROLL_SLACK) return "carried";
    return settling ? null : "carried";
  };
  // The input count when the reader last aimed input at each box: a wheel or touch at
  // the box under it, a key at the box holding focus. A scroll the box passes on to the
  // one around it is that one's to record when it ends.
  const touched = new WeakMap();
  const inputSince = (box, count) => (touched.get(box) ?? 0) > count;
  // A scroll the runtime's own restore started is the runtime's when it ends, wherever
  // layout settling carried the box before the end, unless the reader aimed input at
  // the box meanwhile: the end of a keeper's sequence the layout moved on is no choice
  // of the reader's (scrolling.js counts it as one). `writing` holds each box a restore
  // moved until its sequence ends; `ownEnd` the choice count of that end.
  const writing = new WeakMap();
  const ownEnd = new WeakMap();
  const wrote = (box, from) => {
    if (box.scrollTop !== from) writing.set(box, inputCount());
  };
  const readerChose = (box, count) =>
    chosenSince(box, Math.max(count, ownEnd.get(box) ?? 0));
  // The box an input scrolls: along the chain native scrolling follows from where it
  // lands, the first that can still move the wheel's way, so a pane at its end passes
  // the wheel to the page around it, unless it contains its overscroll. A wheel nothing
  // can follow, and every other input, aims at the innermost box.
  const inputBox = (element, event) => {
    if (!element) return pageScroller;
    const chain = [];
    for (const box of scrollChainOf(element)) {
      chain.push(box);
      // The browser's own chaining rule: a box that contains its overscroll passes
      // nothing on.
      if (getComputedStyle(box).overscrollBehaviorY !== "auto") break;
    }
    const innermost = chain[0] ?? pageScroller;
    if (event.type !== "wheel" || !event.deltaY) return innermost;
    const down = event.deltaY > 0;
    return (
      chain.find((box) =>
        down
          ? box.scrollTop < scrollLimit(box) - SCROLL_SLACK
          : box.scrollTop > SCROLL_SLACK,
      ) ?? innermost
    );
  };
  // The bounded region scrolling a box, null for the page, undefined for neither.
  const regionForBox = (box) =>
    box === pageScroller
      ? null
      : readingRegions().find(
          (region) => region.body === box && regionScrollBehavior(region) === "bounded",
        );
  const boxOf = (node) => effectiveScroller(containingReadingRegionFor(node));
  const dropGonePlaces = () => {
    const present = new Set(readingRegions().map(({ id }) => id));
    for (const map of [places, subjectPlaces])
      for (const id of map.keys()) if (id !== PAGE && !present.has(id)) map.delete(id);
  };

  // A place is the reader's when they chose a scroll in its box since it was last
  // recorded (scrolling.js, `chosenSince`), acted since, as a wheel does before its
  // scroll ends, or stand in the box (`currentLocation`). Only those records rank (`at`): a
  // scroll layout made, a clamp or an anchoring adjustment, records nothing, and a box's
  // first place, taken as the page arrives, ranks below every one the reader made.
  function recordPlaces(boxes, { currentLocation = false } = {}) {
    if (shifting || compositionChanges.size || !regionsSettled()) return;
    dropGonePlaces();
    for (const box of boxes) {
      const region = regionForBox(box);
      if (region === undefined || held(box)) continue;
      if (region && !(under(region.host, pageDocument()) && shownRegionBounds(region)))
        continue;
      const before = places.get(region ? region.id : PAGE);
      const acted =
        currentLocation ||
        readerChose(box, before?.choices ?? 0) ||
        inputSince(box, before?.inputs ?? 0);
      if (before && !acted) continue;
      const reading = capturePlace(region);
      places.set(reading.scroller, {
        reading,
        at: acted ? ++placeCount : 0,
        choices: scrollChoices(),
        inputs: inputCount(),
      });
    }
  }

  // The newest place speaking for `box`, where it lands there: by a landmark the box now
  // carries, by a section holding the whole box, which lands it at its start, or by the
  // box's own end, or its raw offset where its width and revision are those it was read
  // at (reading-place.js, `rawOffsetFits`). `before` names the scrollers that carried the
  // box's words before the shift; with none, as for a region returning from
  // concealment, only the box's own place speaks for it. Places the reader made rank
  // by when they made them; among places none of them made, such as those the page
  // arrived with, the box's own speaks for it, so a region the reader never read in
  // doesn't move the page to itself as a resize carries it into the page.
  function placeFor(box, recorded, before) {
    const own = box === pageScroller ? PAGE : regionForBox(box).id;
    let found = null;
    for (const [id, entry] of recorded) {
      if (!before && id !== own) continue;
      const node = placeNode(entry.reading);
      const carried = node
        ? boxOf(node) === box
        : id === own && (entry.reading.end || rawOffsetFits(entry.reading, box));
      const ranks =
        !found || entry.at > found.at || (entry.at === found.at && id === own);
      if ((carried || id === own || before?.has(id)) && ranks)
        found = { ...entry, lands: carried || (node && under(box, node)) };
    }
    return found?.lands ? found : null;
  }

  function restoreShifted(shifted, currentIntent, recorded) {
    shifting = false;
    if (compositionChanges.size) return;
    if (!currentIntent()) return;
    const page = shifted.find(({ region }) => !region);
    if (page?.band) {
      const from = pageScroller.scrollTop;
      moveScrollerBy(pageScroller, -page.band);
      placeKept(pageScroller);
      wrote(pageScroller, from);
    }
    const boxes = new Map(page ? [[pageScroller, new Set()]] : []);
    const returning = new Set();
    const touch = (box) => boxes.get(box) ?? boxes.set(box, new Set()).get(box);
    const idOf = (box) =>
      box === pageScroller
        ? PAGE
        : readingRegions().find(({ body }) => body === box)?.id;
    for (const { region, from, to, returned } of shifted) {
      if (!region || !shownRegionBounds(region)) continue;
      // The box a region left keeps its own place: it holds the rest of its words,
      // which the region's leaving moved only as layout moves them. A region returning
      // from concealment had no words in the box that carried it.
      if (returned) returning.add(to);
      touch(to);
      if (from && from !== to && !returned) touch(to).add(idOf(from));
    }
    for (const [box, before] of boxes) {
      const region = regionForBox(box);
      if (region === undefined) continue;
      const place = placeFor(box, recorded, returning.has(box) ? null : before);
      if (!place || readerChose(box, place.choices)) continue;
      const from = box.scrollTop;
      restorePlace(place.reading, region, currentIntent);
      wrote(box, from);
      holds.set(region ? region.id : PAGE, {
        box: new WeakRef(box),
        reading: place.reading,
        since: inputCount(),
        offset: placeOffset(place.reading, region),
        top: box.scrollTop,
        currentIntent,
      });
    }
    // The layout is settling from here, so the holds are read under its window.
    watchHolds();
    for (const id of [...holds.keys()]) holdOf(id);
  }

  // Apply each held place again while the shift's layout settles, as a widget drawing
  // a frame late changes it, and only then: re-application exists for that late layout,
  // and outliving it would put back a place under whatever else changes the page. The
  // window closes when Leaf's rendering reads settled (rendering.js, `renderingState`)
  // and every region stands where it was last seen (`regionsSettled`), or after
  // `SETTLING` deliveries or `SETTLING_MS` whatever happens: a widget that keeps
  // resizing, or a rendering hold that never releases, would otherwise keep reading
  // every later move as layout's. What moves a place is the page's
  // own content or its bounded region's, and it lands only in the box it was restored
  // into.
  const SETTLING = 12;
  const SETTLING_MS = 1000;
  let reapplyTimer;
  const stopReapplying = () => {
    reapply?.disconnect();
    clearTimeout(reapplyTimer);
    reapply = null;
  };
  const releaseHolds = () => {
    holds.clear();
    stopReapplying();
  };
  function watchHolds() {
    stopReapplying();
    if (!holds.size) return;
    const again = frameFor(document.documentElement, () => {
      for (const id of [...holds.keys()]) {
        const hold = holdOf(id);
        if (!hold) continue;
        const box = hold.box.deref();
        const region = regionForBox(box);
        const now = placeOffset(hold.reading, region);
        if (now === null || Math.abs(now - hold.offset) <= SCROLL_SLACK) continue;
        const from = box.scrollTop;
        restorePlace(hold.reading, region, hold.currentIntent);
        wrote(box, from);
        hold.offset = placeOffset(hold.reading, region);
        hold.top = box.scrollTop;
      }
      if (!holds.size) stopReapplying();
    });
    let deliveries = 0;
    const observer = sizeObserver(() => {
      if (reapply !== observer) return;
      if (++deliveries > SETTLING) return stopReapplying();
      again();
    });
    reapply = observer;
    reapplyTimer = setTimeout(stopReapplying, SETTLING_MS);
    const settled = () =>
      nextAnimation(() => {
        if (reapply !== observer) return;
        const { updatesSettled, preparationsSettled } = renderingState();
        if (updatesSettled && preparationsSettled && regionsSettled()) stopReapplying();
        else settled();
      });
    settled();
    reapply.observe(pageDocument());
    for (const hold of holds.values()) {
      const box = hold.box.deref();
      if (box && box !== pageScroller)
        for (const child of box.children) reapply.observe(child);
    }
  }

  // Each composition change in progress (`preserveReadingRegions`), by its owner: the
  // user's intent when it began and the places of its own scrollers then. Inside a
  // composition only its own scrollers are restored: document travel belongs to the
  // navigation that changed it. A widget may recompose without the user, so what it
  // captures serves its own restore and is no place the user recorded.
  const compositionChanges = new Map();
  const ownBoxes = (owner) =>
    readingRegions()
      .filter(
        (region) =>
          regionScrollBehavior(region) === "bounded" &&
          under(region.body, owner) &&
          shownRegionBounds(region),
      )
      .map((region) => region.body);

  // A subject leaving keeps the reader's place in it, read now where the region's own
  // box scrolls it, on screen or not; the one showing returns them to theirs. Neither
  // waits on a composition around it, which restores where the reader is in what shows
  // rather than which subject shows.
  function showSubject(phase, region) {
    const box = region.body;
    const own = regionForBox(box) && box.checkVisibility();
    if (phase === "leaving") {
      if (own) recordPlaces([box]);
      const place = places.get(region.id);
      if (!place) return;
      if (!subjectPlaces.has(region.id)) subjectPlaces.set(region.id, new Map());
      subjectPlaces.get(region.id).set(region.subject, place.reading);
      return;
    }
    holds.delete(region.id);
    const reading = subjectPlaces.get(region.id)?.get(region.subject);
    if (!reading) {
      places.delete(region.id);
      return;
    }
    // The place stands for this subject from now: the reader's scrolls in the box under
    // another subject chose nothing in this one.
    places.set(region.id, {
      reading,
      at: ++placeCount,
      choices: scrollChoices(),
      inputs: inputCount(),
    });
    if (own) restorePlace(reading, regionForBox(box));
  }

  function readingRegionTransition({
    phase,
    owner,
    region,
    cancelled,
    retained,
    shifted,
  }) {
    if (phase === "leaving" || phase === "showing") {
      showSubject(phase, region);
      return;
    }
    // Announced from a resize observer's delivery; restoring there could reveal a
    // region and resize what the observer watches, so it waits for the next frame.
    // Nothing is recorded from the announcement until then: a scroll the shift itself
    // causes must not replace the place it is about to restore.
    if (phase === "shift") {
      const currentIntent = retainUserIntent();
      const recorded = new Map(places);
      // The holds already in place stay under the window: this shift is more of the
      // same settling, and its restore reopens the window for what it holds.
      shifting = true;
      nextRender(() => restoreShifted(shifted, currentIntent, recorded));
      return;
    }
    // A composition change captures the intact places before hiding any region, and its
    // restore owns the whole change: one nested inside it, such as tabs inside a
    // switching tab, must not replace those places with an intermediate layout. A region
    // it hides keeps its place for its return, but continuity does not reveal it over a
    // newer choice.
    if (
      cancelled ||
      [...compositionChanges.keys()].some(
        (ancestor) => ancestor !== owner && under(owner, ancestor),
      )
    ) {
      compositionChanges.delete(owner);
      return;
    }
    if (phase === "before") {
      if (retained && compositionChanges.has(owner)) {
        compositionChanges.get(owner).currentIntent = retainUserIntent();
        return;
      }
      const captured = new Map(
        ownBoxes(owner).map((box) => {
          const region = regionForBox(box);
          return [region.id, capturePlace(region)];
        }),
      );
      compositionChanges.set(owner, { currentIntent: retainUserIntent(), captured });
      return;
    }
    const change = compositionChanges.get(owner);
    compositionChanges.delete(owner);
    if (!change?.currentIntent()) return;
    for (const box of ownBoxes(owner)) {
      const region = regionForBox(box);
      const reading = change.captured.get(region.id) ?? places.get(region.id)?.reading;
      if (reading && (hasLandmark(reading) || rawOffsetFits(reading, box)))
        restorePlace(reading, region, change.currentIntent);
    }
  }

  let readingContinuityInstalled = false;
  function installReadingContinuity() {
    if (readingContinuityInstalled) return;
    readingContinuityInstalled = true;
    watchReadingRegionTransitions(readingRegionTransition);
    // A scroll is recorded on the first frame no scroll event reached: a long page is
    // read once a gesture rather than each frame. `scrollend` would say the same, but
    // Chrome holds it for a wheel until its gesture times out, past a resize that soon.
    const moving = new Set();
    let scrolls = 0;
    let resting = false;
    const rest = (seen) =>
      nextRender(() => {
        if (seen !== scrolls) return rest(scrolls);
        resting = false;
        const boxes = [...moving];
        moving.clear();
        recordPlaces(boxes);
      });
    const scrolled = (event) => {
      moving.add(event.target === document ? pageScroller : event.target);
      scrolls++;
      if (resting) return;
      resting = true;
      rest(scrolls);
    };
    document.addEventListener("scroll", scrolled, { capture: true, passive: true });
    // A scroll's end is the reader's choice (scrolling.js), and a place taken before it
    // would read as older than that choice. WebKit, and Chromium for touch, end a scroll
    // frames after its last scroll event, so the end takes a place of its own.
    document.addEventListener(
      "scrollend",
      ({ target }) => {
        const box = target === document ? pageScroller : target;
        if (writing.has(box)) {
          if (!inputSince(box, writing.get(box))) ownEnd.set(box, scrollChoices());
          writing.delete(box);
        }
        nextRender(() => recordPlaces([box]));
      },
      { capture: true, passive: true },
    );
    for (const type of ["popstate", "hashchange"]) addEventListener(type, releaseHolds);
    // Arriving or editing changes the place even when no scroller moves. Keep the intact
    // place now: an immediate resize can invalidate geometry before a later record runs.
    // Record again after any seat or layout commits.
    const recordCurrentLocation = () => {
      const at = focused();
      if (!at || !under(at, pageDocument())) return;
      const box = boxOf(at);
      recordPlaces([box], { currentLocation: true });
      nextRender(() => recordPlaces([box], { currentLocation: true }));
    };
    onCurrentLocation(recordCurrentLocation);
    onReadingInput(recordCurrentLocation);
    // Caret and selection keys are work in the same focused destination even
    // when they change no text and produce no input or focus event.
    onUserInput((event) => {
      if (event.type === "keydown" || event.type === "input") recordCurrentLocation();
      if (!["wheel", "touchstart", "keydown", "pointerdown"].includes(event.type))
        return;
      const at = event.type === "keydown" ? focused() : event.composedPath()[0];
      const element = at instanceof Element ? at : at?.parentElement;
      const box = inputBox(element, event);
      touched.set(box, inputCount());
      held(box);
    });
    nextRender(() =>
      recordPlaces([
        pageScroller,
        ...readingRegions()
          .filter((region) => regionScrollBehavior(region) === "bounded")
          .map((region) => region.body),
      ]),
    );
  }

  function installArrival() {
    installReadingContinuity();
    // Ordinary reload and full-document history travel keep the browser's restored
    // offset; history.js owns same-document working-place checkpoints. The root is
    // its document scrollport, so native restoration is both
    // more complete and less surprising than a parallel session-store reading. Leaf
    // intervenes for two semantic cases the platform cannot know: a fresh URL aimed at a
    // target a widget generates, hides, or moves (`aimArrival`), and travel to a
    // different authored revision, where a passage is a better landmark than the old
    // document's pixels.
    const navigationType = /** @type {PerformanceNavigationTiming | undefined} */ (
      performance.getEntriesByType("navigation")[0]
    )?.type;
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
    // Unreadable saved JSON means no saved view; it must not prevent page startup.
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
    const currentIntent = retainUserIntent({ fallback: compositionInput, since: 0 });
    const restoreCarryScroll =
      handoff && restoreCarry(handoff.carry, new Map(), currentIntent.handoff);
    const landArrival = () =>
      landContinuity(async () => {
        if (!currentIntent()) return;
        if (handoff) {
          restorePointer(handoff.pointer);
          restoreView(handoff.view, currentIntent);
          restoreRetainedCurrentLocation(handoff.retainedCurrentLocation);
          restoreCarryScroll();
          await restoreEditingContinuity(handoff, currentIntent);
          if (handoff.comparison !== null && stamped(handoff.comparison))
            showComparison(handoff.comparison);
          return;
        }
        // A URL aimed somewhere has already landed there (`aimArrival`).
        if (
          navigationType === "navigate" &&
          !aimedAt &&
          savedView &&
          savedView.revision !== runtime.currentRevision
        )
          restoreView(savedView, currentIntent);
      });
    return { landArrival, savedView };
  }

  // A fresh URL aimed at an element stays landed while the page arrives. The browser
  // lands it at parse time, before a widget hides the tabs around it, collapses a
  // disclosure over it, or declares a strip that covers it, and before presentation
  // adds controls above it; so the arrival lands it again at each step that changes
  // the page's geometry: once widgets upgrade, before the first state read, once
  // the page presents, and after declared deferred arrivals settle. Each landing is
  // the browser's own rule (`scrollToFragment`), the
  // target's start at its scroller's landing edge, taken in the geometry of that step,
  // so a target nothing moved stays where it is. The fragment is read before widgets
  // upgrade, since a widget may write its own view into the URL (a root tab set names
  // its open panel), and that is display state, not a destination. A reload or history
  // traversal keeps the browser's restored offset instead, and input during the arrival
  // ends it. A fragment followed once the page is here is travel's (anchor-travel.js,
  // `followFragment`), as is Back or Forward to one the page has hidden since
  // (`returnToFragment`); both read the same destination and reveal it the same way.
  let aimedAt = null;
  function aimArrival() {
    const fresh =
      /** @type {PerformanceNavigationTiming | undefined} */ (
        performance.getEntriesByType("navigation")[0]
      )?.type === "navigate";
    const arrivedAt = location.hash;
    const currentIntent = retainUserIntent({ since: 0 });
    return function landFragment() {
      aimedAt ??= fresh && fragmentTarget(arrivedAt);
      if (!aimedAt || !currentIntent()) return;
      reveal(aimedAt, currentIntent);
      scrollToFragment(aimedAt);
    };
  }

  function mount() {
    versionPicker.configure({
      activate: (entry) => {
        if (entry.version !== null) goVersion(entry.version);
        else if (entry.active) goActive();
      },
      compare: pressComparison,
      latest: goActive,
    });
    effect(paintPicker);
  }

  return {
    PICKER,
    prepareActivation,
    aimArrival,
    installArrival,
    mount,
  };
}
