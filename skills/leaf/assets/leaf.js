/* Leaf runtime, loaded via <script type="module" src="/leaf.js">: the boot module
 * composing the owners of the widget layer and the comment layer.
 *
 * Widget layer: reads /registry.json (vendored per page) and dynamically imports one
 * module per tag marked x-upgrade — element-widgets need no JS at all; the theme's CSS
 * renders them. It also renders the attributes the registry marks x-says as real text
 * (renderSaid), for every widget alike: a word the page says has to be a word the
 * user can select. Upgrades flush before the first anchor pass, so comment quotes
 * always search the enhanced DOM. Widget modules import only the small helper surface
 * they need from /runtime/widget-api.js.
 *
 * Actions: an interactive widget (lf-board) reports the user editing the document
 * through it as an `action` event — sendAction posts it, `leaf wait` prints it,
 * and `leaf ack` records that the complete wait batch reached model context. The
 * live view is the version plus every action recorded up to it, replayed on each applied state:
 * authored markup is what a widget was before anyone touched it, the log is every
 * transition since, and the log wins. A decision therefore outlives the version it
 * was made on, without the page's author having to copy it into the next one by
 * hand. When a version does mean to overrule one — the content the decision was
 * about got rewritten — `version check` makes the author say so (see restatement_errors in
 * the leaf.validation package); it is never inferred from the markup's silence. Widgets opt in via an
 * applyAction(action, detail) method stating an absolute value, so a reload keeps the
 * user's drag and a second tab follows along live.
 *
 * Comment layer: talks to leaf's server — listens on GET /api/news and reads
 * GET /api/state when that stream says the page moved, posts events to POST /api/event.
 * Everything it injects is namespaced .lf-* and marked .lf-ui, and it styles itself
 * from the theme's tokens so it themes with the page.
 *
 * .lf-ui is the chrome face — the system-ui look that says "this is not the document" —
 * and it is anchoring's answer only where nothing nearer speaks. A label the widget
 * declares the page's own words (relabel's data-lf-said) is nearer, and wins: a heading
 * in a chrome-looking row and a tab's name inside its own strip button are both passages
 * a user can point at. Reading the class as the whole answer is what left a user
 * able to see a draft's heading and unable to comment on it. A widget's own label, note
 * or badge outside any control declares nothing at all: data-lf-gen alone keeps it out of
 * the diff and in reach of the anchor pass. CLAUDE.md carries why.
 *
 * Paper reads both: a control a widget injected (data-lf-offer) has nothing on paper to
 * be pressed, so it goes, unless its own label is words the page keeps — ones it speaks
 * (data-lf-said) or ones it echoes off the element a route points at (data-lf-echo,
 * which anchoring skips and paper keeps). Keying print on .lf-ui instead cost a printed
 * decision the only words that stated it (see CLAUDE.md), because a pick mark is a
 * control and a statement at once. render_version compares the two media and reports
 * what a page says on screen and not on paper.
 *
 * Native controls are the default. A control that also says selectable page words uses
 * the explicit selectable-offer exception, because Chrome starts no pointer selection
 * inside a form control; that widget owns its complete keyboard pattern.
 *
 * Passages and anchors: a comment points at an anchor (a section id, a quote, and the
 * neighbouring words where there are any). resolveAnchor is the only place the page is
 * searched and paintAnchors the only place it is marked; CLAUDE.md carries why.
 *
 * Never lose user text (CLAUDE.md): every unsent draft — the general box, each per-thread
 * reply, the selection composer (text + its anchor), a widget's box for words, and an
 * in-place draft edit — persists to the reader's own store (draftStore) on input. It
 * survives reload, version navigation and the close of the tab it was typed in, and every
 * tab open on the page shows one copy of it: a keystroke lands in the store and the
 * store's own event carries it to the rest (watchDraft), so a draft cleared by a send in
 * one tab arrives in the others as a box that has sent rather than as words gone missing.
 * A draft's attempt follows every request into the append-locked log. Two tabs may POST
 * the same generation together, but both receive the one event that attempt identifies;
 * a retry after a sender dies returns it too. Cleanup tombstones only that generation, so
 * a later edit remains. The same path serves general and selection comments, question
 * messages and replies, and lf-draft actions.
 *
 * Versions: the live page at `/` follows the active working revision in the same document.
 * It fetches each mapped immutable revision, upgrades and replays it behind a view-transition
 * boundary, then restores the reader's semantic landmark. Stamping that revision changes
 * its label without replacing the document. Picking a stamped version leaves the live page
 * for that virtual version URL, which stays pinned. One control on the bar holds all of
 * it — the revision being read, the stamped versions, and the press on an older one that
 * marks that change on the page.
 *
 * Composing: every textarea behaves identically — saves its draft on each keystroke,
 * sends on ⌘/Ctrl+Enter — because they are all wired through wireInput. Growing with
 * its content is the stylesheet's job: `field-sizing: content` on the one text-box rule,
 * which a widget's own box opts into by wearing `lf-ui`. No script measures a textarea,
 * so none can leave one momentarily too small for its own text — the shape of bug that
 * flashes a scrollbar per keystroke. The thread list is reconciled, never rebuilt: a
 * poll adds what arrived and touches nothing the user already holds, so scroll,
 * focus and caret keep themselves because the nodes holding them survive. News moves
 * nothing; a send reveals the message it just landed — the panel scrolls to it and
 * flashes that bounded destination, the same answer a click on a page mark gets — and
 * ends in the composer it was sent from. A composer open on a selection keeps that
 * passage marked in the page until it closes, because focusing the box drops the
 * browser's own selection — and that mark is what says which passage the box is on, so
 * the box only quotes the passage back when this version no longer has one to mark.
 * Whether the box is up is state the stylesheet renders, never state read back off the
 * stylesheet.
 *
 * Scrolling: the browser's root is the document scrollport, while body is the layout
 * shell whose margins keep the page clear of a standing panel or tray. Native fragments,
 * wheel/touch input, history restoration, and browser chrome therefore share the same
 * reading position; auxiliary workspaces keep their own nested scrollports. Runtime
 * reading position goes through pageScroller.
 * The page binds `j`/`k` to 60-pixel steps and `d`/`u` to 60% of the visible page,
 * through whichever region the reader is working in. Both share the same quick glide.
 * Space and the platform's remaining scroll keys keep their native meaning, including in
 * focused controls.
 *
 * Keyboard: one register, and every surface is a projection of it. A row binds keys and
 * says what pressing one does; a scope is where the keyboard means something particular,
 * and scopes nest. One dispatcher walks the stack innermost-first, so a focused control's
 * keys shadow the page's without either knowing about the other, and a scope's `claims`
 * stop the walk at the keys it owns whole — the ones that type a character into a box, or
 * the whole keyboard under the reference overlay. The register is the only way a key
 * enters the runtime: `keys(el, title, rows)` is what a widget calls, and the dispatcher
 * it feeds is the layer's one keydown listener bar the aim chord's modifier latch. The
 * full vocabulary — what a row's cells mean, and how a scope's `when` differs from a
 * row's — is written where the register is defined.
 *
 * The stack the rule is about is the reader's, and every key here answers to it: a press
 * that takes the reader in pushes one layer, and Escape pops one. So the way out is as
 * deep as the way in and can be walked back without being counted — three presses to get
 * somewhere, three to come back, each giving up the press that earned it. An entry row
 * declares one return frame. The dispatcher captures the exact focus or reading block
 * before the command and pushes only after its layer stands; Escape closes that frame and
 * restores the capture. Revealing containing chrome and focusing the requested destination
 * are one entry: page `c` enters the page-comment box, while `g T` enters the Threads list.
 * A later `c` from that list is a second entry, so two Escapes unwind both in reverse.
 *
 * Two page modes make a destination explicit before acting on it. `s` draws short,
 * viewport-local hints on stable items and declared visual parts. `/` searches all page
 * text directly or from those hints, Tab walks repeated matches, and Enter turns the
 * current result into an ordinary native selection. Both routes end at the same passage
 * or item the pointer path uses, so the existing `c` comments on it and no second anchor
 * vocabulary exists. `g` arms a mode in which a mnemonic names a panel or a
 * document list. `g T`, `g A`, and `g L` land in Threads, Asks, and All leaves;
 * `g M` opens the complete Page map, and `g V` opens Versions, each through the same
 * door as its banner control.
 * A lowercase mnemonic starts a numbered document list, so `g m 3` is the third
 * Page-map location and `g h 3` is the third hyperlink; `g g` and `g G` are the page's
 * top and bottom edges.
 * Arming shows every complete route in the key line. Pressed keys use the blue face and
 * pending keys use the ordinary face. Visible members show the same complete route in
 * adjacent fixed keycaps. A list letter narrows those inline hints without moving the
 * remaining routes. Any other key disarms the window and keeps its
 * ordinary meaning, which the dispatcher spells as disarming and walking the stack again.
 * Escape is a binding like any other. A control-specific inner step precedes the latest
 * active command frame, then generic focus and pointer fallbacks; the first live row owns
 * exactly one step, so the promise cannot drift from the press.
 *
 * What a key would do right now is state the user can read, not recall. The quiet fixed key
 * line starts with the first live row of the innermost scope, then a promotable Escape or
 * the next row, and retains registry rows marked persistent — on the page at rest, `c` and
 * `r`, the two presses that say something back. An active chord shows every
 * live row in its scope, including computed ranges. `? more` unfolds up to two rows of the
 * remaining current commands; `? all shortcuts` opens the complete reference, grouped by
 * scope and searchable by key, action, or scope. The hint chips are aria-hidden: they are
 * the eye's copy of facts spoken through placeholders and live announcements; More is the
 * accessible disclosure control.
 *
 * A message arrives as logged and renders here, in the same vendored layer that owns
 * the panel's styles — the two version together, and no wire vocabulary exists beyond
 * the log's own. Its text is Markdown, rendered with every raw tag escaped to the
 * characters it was written in, so prose that says `Vec<T>` keeps its own words and
 * text cannot inject markup. A widget rides the event's `markup` field instead, whose
 * one door is the CLI gate (`leaf comment`/`leaf reply` validate it against the
 * vendored registry; the browser door refuses the field), so what lands here is
 * injected as validated. A suggestion's text renders verbatim: its characters are
 * bound for the page as typed.
 *
 * A fragment link in a message ([the group](#d-channel)) points at an element of the
 * page, and the browser's own navigation is the travel — collapsed content wears
 * hidden="until-found", so the jump opens the tab or settled group holding it. The
 * runtime adds only the half the platform has no answer for: a comment outlives the
 * version it was written on, so a reference to an id this one hasn't got wears the
 * detached face a stranded quote wears, and its press is refused (paintAnchors). */

import { chromeStyle } from "./runtime/chrome-style.js";
import {
  COVERING,
  NON_COVERING,
  PANEL_KEY,
  PANEL_MIN,
  PANEL_PROP,
  PANEL_W,
  createChromeLayout,
} from "./runtime/chrome-layout.js";
import { createDrawnEdge } from "./runtime/drawn-edge.js";
import { createLiveLeaves } from "./runtime/live-leaves.js";
import { createAim } from "./runtime/composing/aim.js";
import { createSelectionCapture } from "./runtime/composing/capture.js";
import { createInput } from "./runtime/composing/input.js";
import {
  composerOpen,
  createSelectionComposer,
  pendingAbout,
  pendingAnchor,
} from "./runtime/composing/selection.js";
import { createSelectionSurface } from "./runtime/composing/surface.js";
import { createTargetSelection } from "./runtime/composing/targets.js";
import { agentName, runtime } from "./runtime/context.js";
import {
  acceptData,
  configureDataReporting,
  notifyDataSubscribers,
} from "./runtime/data.js";
import { createDeferredModals } from "./runtime/deferred-modals.js";
import { createLayerClient } from "./runtime/layer-client.js";
import {
  CONTROL_WORD_CAP,
  DESIGN_KEY,
  createDesign,
  designOn,
} from "./runtime/design.js";
import {
  clearDraft,
  draftContexts,
  loadDraft,
  mirrorDraft,
  newAttempt,
  saveDraft,
  sendDraft,
  settleAcceptedDrafts,
  tellDraft,
  watchDraft,
} from "./runtime/drafts.js";
import {
  PRESS,
  ariaShortcuts,
  bindings,
  checked,
  configureBindings,
  labelOf,
  live,
  parsed,
  spell,
  walkRows,
  word,
} from "./runtime/keyboard/bindings.js";
import {
  answeredContext,
  decisionSource,
  createDecisionModel,
  openDecisions,
} from "./runtime/decisions/model.js";
import { createDecisionView } from "./runtime/decisions/view.js";
import { createArrangements } from "./runtime/arrangements.js";
import { createAddress } from "./runtime/keyboard/address.js";
import { DISCLOSE, createDisclosure } from "./runtime/keyboard/disclosure.js";
import { createDispatch } from "./runtime/keyboard/dispatch.js";
import { createKeyline } from "./runtime/keyboard/keyline.js";
import { createReference } from "./runtime/keyboard/reference.js";
import { createReturnStack } from "./runtime/keyboard/return-stack.js";
import { createScopes, keys, paintKeys, saying } from "./runtime/keyboard/scopes.js";
import { createLivingMargin, marginButton } from "./runtime/living-margin.js";
import { createNavigation, scrollerFor } from "./runtime/navigation.js";
import { FOLD_MS, motion, reducedMotion, scrollBehavior } from "./runtime/motion.js";
import { announce, createNotifications, notice } from "./runtime/notifications.js";
import { createOutbox, outbox, sendAction } from "./runtime/outbox.js";
import { createRequests } from "./runtime/requests.js";
import { createDataProjection } from "./runtime/projection/data.js";
import { createProjection } from "./runtime/projection.js";
import { createAnchors, itemWord } from "./runtime/anchors.js";
import { createBanner } from "./runtime/banner.js";
import { createBannerShelf } from "./runtime/banner-shelf.js";
import { createConversationBox } from "./runtime/conversation/box.js";
import {
  backFromConversation,
  conversationInput,
  createConversationLanding,
  heldConversation,
  landIn,
  SAY_BOX,
  standingConversation,
} from "./runtime/conversation/landing.js";
import { createConversation } from "./runtime/conversation/reconcile.js";
import { shownBox, shownParts, shownRect, startsAt } from "./runtime/geometry.js";
import {
  createPassages,
  inChrome,
  inUi,
  renderRetired,
  says,
  textNodesUnder,
} from "./runtime/passages.js";
import { textUnits } from "./runtime/text-alignment.js";
import {
  ago,
  createPresence,
  observeServerNow,
  quietSince,
  waitingForPickupSince,
} from "./runtime/presence.js";
import { createPointer } from "./runtime/pointer.js";
import {
  createReactions,
  paintReactionStanding,
  responseAction,
} from "./runtime/reactions.js";
import { createStateApplication } from "./runtime/state-application.js";
import { createStateFeed } from "./runtime/state-feed.js";
import { createUpdates } from "./runtime/updates.js";
import { createVersion } from "./runtime/version.js";
import { createWidgetLoader } from "./runtime/widget-loader.js";
import { failSoft, settling } from "./runtime/widget-upgrade.js";
import {
  createMeasurements,
  focusDestination,
  installReachedForWordsGuard,
  offer,
  quoted,
  reachedForWords,
  relabel,
  reserve,
  WORKS,
  WORKS_WITHOUT_TAB_STOP,
} from "./runtime/widget-elements.js";
import {
  MARKED_ANYWHERE,
  MARKED_IN_PAGE,
  PAGE_PAINT_ATTRIBUTE,
  PAGE_PAINT_ATTRIBUTES,
  dress,
  markDeclared,
  renderQuiet,
  renderSaid,
  watchExternalLinks,
} from "./runtime/presentation.js";
import { FOCUSABLE, reachScrollers, runtimeOwnsScrollerStop } from "./runtime/reach.js";
import { pageScroller } from "./runtime/scrolling.js";
import {
  matchesWhen,
  registry,
  tagsDeclaring,
  widgetEntries,
} from "./runtime/registry.js";
import {
  MARK_RULES,
  createShadowStage,
  pageShadowRoots,
  shadowStage,
} from "./runtime/shadow.js";
import { VERSION_PATH, readerStore, tabStore } from "./runtime/storage.js";
import { highlightBlocks } from "./runtime/syntax.js";
import {
  createTrays,
  STRIP_TRAY_RULE,
  TRAY_COVERING,
  TRAY_KEY,
  TRAY_PROP,
} from "./runtime/trays.js";

// A reader preference, not page state: speech input and a stray key should not turn into
// commands unless this reader wants the Vim-like layer. It follows them across Leaf pages,
// while the visible More button keeps the setting reachable when its own `?` shortcut is off.
const CHARACTER_SHORTCUTS_KEY = "lf-character-shortcuts";
let characterShortcutsOn = readerStore.get(CHARACTER_SHORTCUTS_KEY) !== "0";
configureBindings({ characterShortcuts: () => characterShortcutsOn });

// ---------- widget layer ----------

async function undoLast(...args) {
  return runtimeProjection.undoLast(...args);
}

const { promoteDeferredModals } = createDeferredModals({
  presentedAttribute: PAGE_PAINT_ATTRIBUTE.presented,
});
const vendoredLayerGeneration = "__LEAF_LAYER_GENERATION__";
const { postEvent, reportPageError, revealLayer, sameLayer } = createLayerClient({
  currentRevision: () => runtime.currentRevision,
  layerGeneration: vendoredLayerGeneration,
  sayLine: (...args) => sayLine(...args),
});
configureDataReporting(reportPageError);
const { pointerAt } = createPointer();

createMeasurements({ shownBox });

installReachedForWordsGuard();

createDataProjection({
  paintAnchors,
  reachScrollers,
  setChildren,
});

let outboxRuntime;
function accountOutbox(...args) {
  return outboxRuntime.accountOutbox(...args);
}
function removeOutbox(...args) {
  return outboxRuntime.removeOutbox(...args);
}
function post(...args) {
  return outboxRuntime.post(...args);
}

let stateFeed;
function readAndApply(...args) {
  return stateFeed.readAndApply(...args);
}

let stateApplication;
function receiveState(...args) {
  return stateApplication.receiveState(...args);
}

// ---------- the key register ----------
// One register. A row binds keys and says what pressing one does, and every surface is a
// projection of it — the dispatcher, the key line, the "?" overlay, a control's tooltip
// and what announce() speaks all read the same object. So no surface can name a key the
// register does not answer, and no binding can exist that no surface will show. The
// register's own scopes and the dispatcher that walks them are in the keyboard section
// below; what is here is the vocabulary they and the widget modules share.
//
// A row:
//   id    — its stable dotted identity. Words and keys may change without changing the
//           route used by the reference and other projections.
//   keys  — the bindings it answers: "a", "Escape", "Mod+Enter", "Shift+a", "d".
//           A function where the set is the page's (an option group's 1–N).
//   routes— optional stable subcommands when those bindings mean different things. The
//           keyline keeps the compact row; the reference presents each route separately.
//           A route may override `line` and `label` for the case where a nearer scope
//           shadows only its sibling binding.
//   label — how it renders. Computed from `keys` unless the row is a chord whose second
//           half is another scope's row, and then built from that row rather than typed.
//   does  — the overlay's sentence.
//   line  — the line's word: a row carrying one stands on the key line, and a row that has
//           a `run` must carry one. That is the failure this register was built for, at
//           its smallest — page travel worked, and no always-visible surface named it,
//           because the field was optional and its absence read exactly like a decision.
//           A row with no `run` may carry one all the same, since a press can be real and
//           immediate without being the runtime's: Enter opens the focused leaf because
//           the row is a link. What carries no word is reference, named in the "?"
//           overlay and never promised as the next press — F7, ⌥ click, a press on a
//           draft's own box.
//   lineWhen — optional projection-only visibility on the key line. Unlike `when`, it
//           never changes whether the command dispatches or appears in the reference,
//           and an active chord shows every live row regardless of it.
//   promoteEscape — whether an Escape row takes the line's second visible slot. On by
//           default; a local action that happens to clear state can leave the slot to the
//           next action on that state.
//   when  — its liveness. The one predicate every surface asks.
//   run   — the press, taking the binding that fired.
//   native— whether the platform completes its default after `run`. Off by default: a
//           row normally owns the press it answers.
//   repeat— whether holding the key repeats the press. Off by default: a held `]` was a
//           page navigation per repeat, and a held pick a `choose` per repeat. It applies
//           to native rows too, independently of whether their platform default repeats.
//
// A scope is where the keyboard means something particular — the page, a focused thread,
// a card grip, a box being typed in. It declares its rows and where it holds, and where it
// holds is two questions:
//   the page HAS this scope  → the "?" overlay lists it
//   the reader is IN it now  → the key line renders it
// Both were already asked, by a pair of calls a widget made beside a listener of its own,
// so the display list and the dispatch were separate objects: a grip that answered Space
// said Enter on every surface, and three sites had to remember to re-declare on a state
// change. A row's `when` is the row's own liveness and says nothing about where the reader
// is; the scope answers that, and a row never restates it.

// Where a disclosure keeps which way it stands, in both spellings. Declared up here
// because `shadowStage` calls it, far above the surfaces it repaints for.
// This pair is what DISCLOSE reads, so a toggle moves every row bound through it — and a
// row's keys are named on two surfaces, the line the reader sees and the
// `aria-keyshortcuts` a listener is read. Repainting the line alone left the attribute
// standing whichever way the row was when its scope was declared, naming the arrow that no
// longer moves the section and withholding the one that does. `paintKeys()` is the superset
// — it revalidates the connected scopes and ends in `paintHere()` — so the watcher that
// already hears this write is the one place both surfaces are kept together, rather than a
// repaint each DISCLOSE row has to remember for itself.
// A write that says what the attribute already said is not a disclosure changing, and
// taking it for one closes a loop: paintCoreControls paints `aria-expanded` on the key
// line's More control, so every paint scheduled the next one and the page repainted for
// as long as it was open. Reading the old value is what tells the two apart. A real
// toggle still arrives, including one that lands back where it started, because the
// record for its return leg carries the other value.
const disclosureWatch = new MutationObserver((records) => {
  if (records.some((r) => r.target.getAttribute(r.attributeName) !== r.oldValue))
    paintKeys();
});
const watchDisclosures = (root) =>
  disclosureWatch.observe(root, {
    subtree: true,
    attributeFilter: ["open", "aria-expanded"],
    attributeOldValue: true,
  });
createShadowStage(watchDisclosures, watchExternalLinks);

const {
  byCommand,
  claimsEsc,
  documentFocused,
  elementScopes,
  focused,
  merge,
  pruneScopedElements,
  recoveredLabelFocus,
  scopeRefs,
  scopesFor,
} = createScopes({
  paintHere,
  upFrom: (node) => upFrom(node),
});

// Where the reader is standing, painted: the ring on the decision they are in, the mark on the
// passage of the comment they are in, the focused box's hint, and the line saying what the
// next press does from there. One repaint, because it is one question — every reading is of
// the focus and the open-decision list, and every signal that moves either (a focus move, an
// answer taken, a poll, a widget's own state) moves them all.
//
// Coalesced to a frame: a focus move is a focusout then a focusin, and painting between
// them would flash the scope of nowhere and drop the ring for a frame. Here rather than
// beside the renders it schedules, because the scopes core declares call it as the module
// evaluates, which is before the line has an element to draw into — the frame is what puts
// the first paint after both.
let herePending = false;
let paintInputHints = () => {};
function paintHere() {
  if (herePending) return;
  herePending = true;
  requestAnimationFrame(() => {
    herePending = false;
    markHere();
    paintStanding();
    // The chips are where the reader can go, beside the ring saying where they are and the
    // line saying what the next press does — one paint, because it is one question, and
    // because a chip repainted by its own door alone went stale on the door it did not
    // have: a poll that retires a decision moves the list under an armed window, and only the
    // panel's own render was calling the chip pass.
    paintAddresses();
    paintTargets();
    paintCoreControls();
    paintInputHints();
    renderLine();
  });
}

// A scroll target can sit inside a collapsed container — a closed <details>, an
// inactive tab. Opening what the platform owns (details) and letting a container
// widget open what it owns (the lf-reveal event; lf-tabs listens) gives the
// target geometry before the scroll. Called before every scroll-to-content.
function reveal(el) {
  const chain = [];
  for (let a = el; a; a = a.parentElement ?? a.getRootNode()?.host ?? null)
    chain.push(a);
  // Reveal outside-in so an inner widget has geometry when it handles the signal.
  for (const a of chain.reverse()) {
    if (a.tagName === "DETAILS" && !a.open) a.open = true;
    a.dispatchEvent(new CustomEvent("lf-reveal", { detail: { target: el } }));
  }
}

let anchoringReady = false;
const {
  importWidgets,
  opaquePassageParts,
  opaquePassageRoots,
  rememberPassageParts,
  upgradeWidgets,
} = createWidgetLoader({
  buildReactBar: (...args) => buildReactBar(...args),
  rememberAuthoredMarkup: (...args) => rememberAuthoredMarkup(...args),
  reportPageError,
  revealLayer,
  sameLayer,
});

// ---------- comment layer ----------

const VERSION_MATCH = location.pathname.match(VERSION_PATH);
const servedRevision = document.querySelector(
  'meta[name="lf-revision"][data-lf-runtime]',
)?.content;
const servedStampMarker = document.querySelector(
  'meta[name="lf-version"][data-lf-runtime]',
);
runtime.currentRevision = servedRevision ? parseInt(servedRevision, 10) : null;
runtime.currentStamp = servedStampMarker
  ? parseInt(servedStampMarker.content, 10)
  : VERSION_MATCH
    ? parseInt(VERSION_MATCH[1], 10)
    : null;
runtime.currentLabel =
  runtime.currentStamp === null ? null : `v${runtime.currentStamp}`;
servedStampMarker?.remove();
// Sign-off is the page's decision, not standing chrome: the approve button exists only
// when the version declares <meta name="lf-review" content="sign-off"> — a plan or
// proposed change seeking assent. An informational page takes comments only, and
// nothing stands in the button's place there. A neutral "End leaf" did once, and it
// ended nothing it named: the server went on serving, the watcher went on waiting,
// the status was untouched, and the agent side still finished at `leaf status idle`.
// So the one control a page that asks nothing put in front of its reader offered
// them an ending it could not deliver. The declaration rides the document, so a
// pinned older version keeps its own decision.
let signoffDeclared =
  document.querySelector('meta[name="lf-review"]')?.content === "sign-off";
let signoff = signoffDeclared && runtime.currentStamp !== null;
// How often the page re-renders what it already holds: a time that reads "4m ago", a
// claim ageing toward the threshold that makes it stale. Local — no request is made for
// it, and it keeps its cadence whether or not there is a server to talk to.
const TICK_MS = 2000;
// How long the outbox waits before re-sending, and how long the page waits before
// reopening a news stream the server refused. Both are the same "try again shortly",
// and neither is a cadence: a page with news gets it without waiting for either.
const RETRY_MS = 2000;
// How long the news stream may say nothing before the page takes it for dead. The
// server speaks at least every five seconds, so half a minute of silence is a
// connection something between them has quietly lost — a proxy, a laptop that slept —
// which is the one failure the browser cannot see for itself and would otherwise wait
// on forever.
const SILENCE_MS = 30_000;

// ---------- styles ----------
/* A marked passage is painted, not wrapped (see paintAnchors), so its rules reach it
   through the highlight registry — which styles glyphs, so the underline stands in for
   a border and the pointer's cursor comes from a class the hit-test puts on body. A
   posted thread's mark wears the comment layer's own violet (--mark-ink and the wash
   beside it, which is the same colour a marked element's ring is drawn in); the open
   composer's draft wears the accent, and outranks it where they overlap. Not dashed —
   dashed means detached.

   The wash and the ink answer two questions, so they are moved by two things. The wash
   says how near the reader's attention is, in three steps of one hue: --mark for a mark
   the page merely holds, --mark-hover for the one the pointer is indicating, and
   --mark-strong for the one the reader is standing in. The ink turns accent for that last
   one alone (paintStanding), because "you are here" is a different claim from "you are
   near here", and it is made in the one band this page spends on that fact everywhere
   else (--here-ring).

   Three steps and not two, because the hover is no longer a thing the reader does only by
   pointing at the prose. A card in the panel indicates its thread the same way (paintHover
   reads both surfaces), and the pointer is over the panel by construction in the moment
   after a reader presses a card — so a hover sharing the standing wash left the two lit
   identically whenever a hand rested where it had just clicked, with a 2px underline hue
   the only thing between them and, on a page of one mark, nothing to compare it against.

   What moved is the hover, downward. The constraint on the standing wash binds in one
   direction only — it cannot go past --mark-strong without spending what code read
   through a mark still has to clear — so the room was below rather than above, and taking
   it raises what a hovered passage's code reads at instead of spending any (theme.css
   states the numbers). The promise the hover's old strength was making is in any case
   already the cursor's (lf-over-mark). The draft's accent wash cannot be confused with the
   standing mark's accent ink, because one focus decides both and an open composer holds
   it.

   Stated once and installed twice, because the registry is the document's and the
   ::highlight() rule is not: a rule in the document styles no glyph inside a shadow
   tree, so a widget that renders the page's words into one (x-shadow) adopts this same
   text (`markSheet`). Two copies of these declarations would be two chances for a mark
   to mean one thing in the document and another inside a diff. */
const style = document.createElement("style");
style.dataset.lfRuntime = "1";
// The chrome's whole stylesheet, and a template literal, so a backtick anywhere in
// it — a CSS comment naming a command — ends the string and the rest of the sheet
// parses as code. `node --check` accepts the result and the browser refuses it, so a
// syntax check is not the gate here; the render suite is.
style.textContent = chromeStyle({
  COVERING,
  MARK_RULES,
  NON_COVERING,
  PAGE_PAINT_ATTRIBUTE,
  PANEL_PROP,
  STRIP_TRAY_RULE,
  TRAY_COVERING,
  TRAY_PROP,
});
document.head.appendChild(style);

// ---------- scaffold ----------
const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
};
let chromeLayout;
let livingMargin = null;
const syncLayout = (...args) => chromeLayout.syncLayout(...args);
const setPanel = (...args) => chromeLayout.setPanel(...args);
const moveShell = (...args) => chromeLayout.moveShell(...args);
const drawnEdge = createDrawnEdge({ el, keys, moveShell, readerStore, syncLayout });
// The thread panel's edge, on the right, and the tray panel's, on the left. Each keeps
// the reader's choice in their own store rather than the tab's, because where a reader
// keeps their conversations, and how much of the page they will give a tray, is the
// chrome they arrange and expect to find arranged wherever they are reading (see
// `readerStore`). Live activation keeps the edges themselves; document travel and reload
// restore the same choices, so no revision or visit asks the reader to draw them again.
const commentsEdge = drawnEdge({
  side: "right",
  noun: "thread panel",
  wide: PANEL_W,
  min: PANEL_MIN,
  prop: PANEL_PROP,
  key: "lf-panel-width",
  covering: COVERING,
});

const banner = el("header", "lf-ui lf-banner");
const dot = el("span", "lf-dot");
const statusText = el("span", "lf-status-text", "Connecting…");
// The line's momentary other words (notifications.js): a gesture recorded, a version
// arrived, a send refused. Seated after the line it stands in for, so the row holds
// one sentence at a time.
const noticeEl = el("span", "lf-ui lf-notice");
const bannerStatus = el("div", "lf-banner-status");
bannerStatus.append(dot, statusText, noticeEl);
const {
  bannerActions,
  foldShelf,
  overflowBtn,
  overflowMenu,
  reserveNewsSlot,
  showNews,
  unfoldShelf,
} = createBannerShelf({ el, paintHere: () => paintHere() });
const pagePresented = () => document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented);
const {
  decisionRows,
  decisionsBtn,
  decisionsList,
  decisionsOffered,
  decisionsPanel,
  currentTray,
  leavesList,
  openTray,
  othersBtn,
  othersPanel,
  reserveListClearance,
  restoreTray,
  restoreTrays,
  showTray,
  trayNames,
  traysEdge,
} = createTrays({
  beforeOpen: () => {
    if (chromeLayout?.panelIsOpen()) setPanel(false);
    livingMargin?.closePreview();
  },
  drawnEdge,
  el,
  keys,
  leavesOffered: () => leavesOffered(),
  moveShell,
  motion,
  openDecisions,
  pagePresented,
  paintKeys,
  PRESS,
  readerStore,
  renderDecisions: () => renderDecisions(openDecisions()),
  syncLayout,
  trayChanged: () => livingMargin?.render(),
  walkRows,
});
const { leavesOffered, othersLinks, renderOthers } = createLiveLeaves({
  ago,
  el,
  keys,
  leavesList,
  openTray,
  othersBtn,
  othersPanel,
  pagePresented,
  paintKeys,
  presented: (...args) => presented(...args),
  showNews,
  toneFor: (...args) => toneFor(...args),
  walkRows,
});
for (const control of [decisionsBtn, othersBtn]) showNews(control, false);
// One owner for everything a move between two documents of one page takes: the chooser
// and its key, the comparison marks, live activation, and the reading landmark that
// survives it. Wired here because the chooser's control belongs to the banner row built
// just above; the readings it needs from the page arrive as thunks, the way every owner
// composed after this point receives what is still being built.
const {
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
} = createVersion({
  allButTheReference,
  banner,
  captureAuthoredFacets: (...args) => captureAuthoredFacets(...args),
  cut: (...args) => cut(...args),
  domFacet: (...args) => domFacet(...args),
  el,
  elementById: (...args) => elementById(...args),
  focused,
  importWidgets,
  landedAt: (...args) => landedAt(...args),
  midComposition: () => midComposition(),
  pageText: (...args) => pageText(...args),
  paintHere,
  paintLegend,
  projectionFromView: (...args) => projectionFromView(...args),
  pruneScopedElements,
  quoteFrom: (...args) => quoteFrom(...args),
  rangeOf: (...args) => rangeOf(...args),
  readAndApply,
  rememberAuthoredMarkup: (...args) => rememberAuthoredMarkup(...args),
  rememberPassageParts,
  reportPageError,
  reserveNewsSlot,
  resetAuthoredPage: (...args) => resetAuthoredPage(...args),
  resolveAnchor,
  reveal,
  sameLayer,
  setLanded: (...args) => setLanded(...args),
  showNews,
  stateCoordinate: (...args) => stateCoordinate(...args),
  stateSignoff,
  style,
  syncLayout,
});
const toggleBtn = el("button", "lf-btn lf-workspace lf-threads-toggle", "Threads");
toggleBtn.title = "Show or hide the thread panel";
toggleBtn.setAttribute("aria-expanded", "false");
const approveBtn = el("button", "lf-btn primary lf-signoff", "Approve version");
approveBtn.title = "Approve this work; the page stays open for follow-up";
// The page's decision is not actionable until the page itself is present. Discussion chrome
// stays live during replay, but approving hidden authored content would decide a version
// the reader has not seen yet.
approveBtn.disabled = true;
// Seed the invariant middle once; arrangeBannerControls puts the two edge families
// around it and later preserves any registry-declared controls added among these three.
bannerActions.append(latestChip, decisionsBtn, versionBtn);
// One order, at every width. An edge's address sits at that edge: All leaves is the first
// address beside the tray it opens on the left, and approval and Threads finish beside the
// panel they open on the right. The row used to turn round at the covering breakpoint,
// which carried Threads from one end of the banner to the other and swapped the page's one
// committing press across it — so a reader who learned this row on a laptop had to learn
// it again on a phone, and a press they were reaching for was somewhere else. What a
// narrow window changes now is how many of these addresses stand on the row at once; the
// rest fold into the row's own menu, in this same order (`foldShelf`).
//
// This is DOM order rather than CSS `order`, so the tab route says the same thing the row
// draws. Reordering existing nodes can briefly drop native focus; put it back without
// moving the page, and hand it to the menu's door where the fold has taken the address
// the reader was standing on.
function arrangeBannerControls() {
  const focused = document.activeElement;
  const edges = new Set([toggleBtn, approveBtn, othersBtn]);
  // Registry-declared blanket answers can join the middle of this row after boot, and a
  // folded address is still on it. Preserve every such control in its standing relative
  // order while moving only the edge-owned addresses.
  const middle = [...overflowMenu.children, ...bannerActions.children].filter(
    (control) => control !== overflowBtn && !edges.has(control),
  );
  const controls = [othersBtn, ...middle, ...(signoff ? [approveBtn] : []), toggleBtn];
  bannerActions.append(...controls);
  foldShelf();
  if (
    focused?.isConnected &&
    controls.includes(focused) &&
    document.activeElement !== focused
  )
    (overflowMenu.contains(focused) ? overflowBtn : focused).focus({
      preventScroll: true,
    });
}
arrangeBannerControls();
banner.append(bannerStatus, bannerActions);

// Sign-off belongs to the authored version, while the control belongs to the live
// chrome that survives one. A soft activation can therefore add or remove the same
// control; rebuilding the banner would throw away focus and every reserved neighbour.
function stateSignoff(next) {
  signoffDeclared = next;
  const shown = signoffDeclared && runtime.currentStamp !== null;
  if (shown === signoff) return;
  signoff = shown;
  if (!signoff) approveBtn.remove();
  arrangeBannerControls();
  if (signoff) {
    reserve(approveBtn, ["Approve version", "✓ Version approved"]);
    paintApproval();
  }
  syncLayout();
}

const panel = el("dialog", "lf-ui lf-panel");
const panelHead = el("div", "lf-panel-head");
const closeBtn = Object.assign(el("button", "lf-btn", "×"), {
  title: "Close (Esc)",
  onclick: () => setPanel(false),
});
closeBtn.setAttribute("aria-label", "Close threads");
// The head's own line: the panel's name while it shows the whole conversation, and what
// it is showing instead the moment a narrowing stands. One slot, because they are one
// fact — how much of the log is in front of the reader — and a count in a second place
// is a count free to disagree with the list under it.
const panelTitle = el("span", "", "Threads");
panelHead.append(panelTitle, closeBtn);
commentsEdge.handle(panel, () => closeBtn);
// Narrowing the list, which is the panel's own view and not the page's state: neither
// box is remembered across a reload, the way a browser's find bar is not. A remembered
// narrowing is a trap: the reader returns to three of twenty-four threads with nothing on
// screen saying why, and a comment arriving outside it never appears at all. Here the head
// says "Showing 3 of 24" for as long as one stands, and a reload is the whole conversation
// again.
const findRow = el("div", "lf-find");
const findInput = document.createElement("input");
findInput.type = "search";
findInput.className = "lf-find-box";
findInput.placeholder = "Find in threads";
findInput.setAttribute("aria-label", "Find in threads");
// The register appends the key that reaches it (`also`), so the control and the row
// cannot spell the binding differently.
findInput.title = "Find in threads";
// What is waiting on the reader: an agent comment, an explicit question in a reply, or a
// reply whose own x-awaits markup still asks. The last case is derived from the same
// declaration-driven projection as the decisions tray; settling reactions can acknowledge
// either kind without closing the thread.
const needsBtn = el("button", "lf-btn lf-needs", "Waiting on you");
needsBtn.setAttribute("aria-pressed", "false");
findRow.append(findInput, needsBtn);
const threadsBox = el("div", "lf-threads");
// A stable panel landing for g T, for c entered from the list, and for pointer/Tab
// fallbacks that have no command frame. -1 keeps it out of the Tab order.
threadsBox.tabIndex = -1;
// And a name, because `g T` lands a reader here and the panel's visible heading alone does
// not name a focusable container. A page key's arrival has to say where it arrived — the
// other direct destinations are named by a leaf link, a decision row, or a Page-map marker
// — or the press is silent to exactly the reader who cannot see the ring it painted. The
// same reason the reference dialog carries a role and a label beside its -1.
// `group` rather than `list`: the box holds run headings as well as threads, so a list
// role fails `aria-required-children` outright and leaves a screen reader announcing a list
// with no items. The name is what the landing needed; the role is only there because a bare
// div may not carry one.
threadsBox.setAttribute("role", "group");
threadsBox.setAttribute("aria-label", "Threads");
const generalRow = el("div", "lf-general");
const generalInput = document.createElement("textarea");
const generalSend = el("button", "lf-btn primary", "Send");
generalRow.append(generalInput, generalSend);
// The panel's foot: everything standing below the scrolling thread list. The general
// box is what it holds at rest, and the page's own reaction strip joins it above that
// box when the registry offers reactions. One box rather than two siblings, because the
// chrome lifts the key line clear of the foot over a covering panel, and a lift
// measured off the composer alone stood it on the strip's pills.
const panelFoot = el("div", "lf-panel-foot");
panelFoot.append(generalRow);
panel.append(panelHead, findRow, threadsBox, panelFoot);

// The floating field immediately accepts a comment on the target the reader named.
// Pressing Tab or its ellipsis exchanges its field for the other responses in place.
// One affordance, raised only where the reader has already pointed:
// a selection, a visual's click, an aimed item, or a visual part.
const fabBar = el("div", "lf-ui lf-fab-bar lf-target-paint");
fabBar.setAttribute("role", "group");
fabBar.setAttribute("aria-label", "Respond");
const fabInput = document.createElement("textarea");
fabInput.className = "lf-ui lf-response-control lf-fab-input";
fabInput.rows = 1;
fabInput.autocomplete = "off";
fabInput.placeholder = "Comment…";
fabInput.setAttribute("aria-label", "Comment");
const fab = responseAction(el("button", "lf-ui lf-fab"), {
  icon: "comment",
  label: "Comment",
  behavior: "disclosure",
});
fab.setAttribute("aria-label", "Comment");
fab.title = "Comment";
fabBar.append(fab);
// The aim's box (see its rule above). Empty and pointer-inert, so it says nothing to a
// screen reader and takes nothing from the press it promises; refreshAim is its one
// writer, and data-for is the aimed id stated where a test can read the promise.
const aimBox = el("div", "lf-ui lf-aim lf-target-paint");
const composer = el("div", "lf-ui lf-composer");
// Only ever shown detached — paintAnchors, its one writer, keeps it out of sight while
// the page is marking the passage. lf-ui on the element itself, not just on the composer
// around it: this is the only injected chrome carrying an id, and "which section is this
// in" is asked as `[id]:not(.lf-ui)` of the element rather than of its ancestors, so
// without the class it answers that question with itself.
const composerQuote = el("blockquote", "lf-ui lf-quote detached");
composerQuote.id = "lf-composer-quote";
// Suggestion mode: the box holds replacement text for the quoted passage
// instead of a remark — Claude accepts it verbatim into the next version.
const suggestRow = el("label", "lf-suggest-row");
const suggestCheck = document.createElement("input");
suggestCheck.type = "checkbox";
suggestRow.append(suggestCheck, document.createTextNode("Suggest replacement text"));
// The page-anchored composer is the extended Comment control itself. The hidden
// composer node keeps the draft's controls and quote description, while this textarea
// stays in the response bar and never jumps to a second box.
const composerInput = fabInput;
// The mark is a paint, and a paint is nothing to a screen reader (see "Paint; don't wrap"
// in CLAUDE.md). So what the box is anchored to travels as the box's own description,
// announced on focus — which is more than the visible quote ever said, since nothing
// pointed a reader at it.
composerInput.setAttribute("aria-describedby", composerQuote.id);
const composerRow = el("div", "lf-composer-row");
const composerSend = el("button", "lf-btn primary", "Comment");
composerRow.append(composerSend);
composer.append(composerQuote, suggestRow, composerInput, composerRow);
fabBar.prepend(composer);
const liveEl = el("div", "lf-ui lf-live");
liveEl.setAttribute("aria-live", "polite");
const helpEl = document.createElement("dialog");
helpEl.className = "lf-ui lf-help";
helpEl.setAttribute("aria-label", "Keyboard reference");
helpEl.setAttribute("aria-modal", "true");
helpEl.tabIndex = -1; // focused on open, so the dialog isn't silent to a screen reader
const helpClose = el("button", "lf-btn lf-help-close", "Close");
helpClose.type = "button";
helpClose.title = "Close keyboard reference";
helpClose.setAttribute("aria-label", "Close keyboard reference");
// The key line — the register's short rendering. Its fact chips are aria-hidden (the spoken
// copies are placeholders, announcements, and the reference); More is a real button because
// a visible door to the complete list should be a door every reader can work.
const keylineEl = el("div", "lf-ui lf-keyline");
const keylineMore = el("button", "lf-key-more");
keylineMore.type = "button";
keylineMore.title = "More keyboard shortcuts";
keylineMore.setAttribute("aria-label", "? more");
const keylineMoreKey = document.createElement("kbd");
keylineMoreKey.textContent = "?";
const keylineMoreText = el("span", "", "more");
keylineMore.append(keylineMoreKey, keylineMoreText);
let keyline;
keylineMore.onclick = () => {
  setChord(false);
  setReact(false);
  keyline.more();
};

// The name of what the pointer is over in design mode, floated at its corner. Chrome
// nothing presses (pointer-events none, in the stylesheet); refreshAim is its one
// writer (paintInspect), beside the box it names.
const inspectEl = el("div", "lf-ui lf-inspect lf-target-paint");
inspectEl.setAttribute("aria-hidden", "true");
// Design mode's legend: a box for every item on the page while the mode stands, drawn
// here in the chrome's layer (paintLegend, its one writer). Paint about the page, so it
// says nothing to a screen reader — the mode's announcement and the names under the
// pointer are the spoken copy.
const legendRoot = el("div", "lf-ui lf-legend");
legendRoot.setAttribute("aria-hidden", "true");
// The g chord's numbered document destinations: a chip on each visible addressable member,
// narrowed to one list after its mnemonic is pressed. They are drawn here for the same reason
// the legend is (paintAddresses, its one writer). The eye's copy of what the chord announces,
// so it says nothing to a screen reader.
const addressLayer = el("div", "lf-ui lf-addresses");
addressLayer.setAttribute("aria-hidden", "true");
// Numeric actions for the Ask the reader is standing in. These share the address face
// but not the g chord's lifecycle: the decision view paints them whenever its semantic
// focus and the dispatch stack leave the digit row reachable.
const decisionActionLayer = el("div", "lf-ui lf-addresses lf-ask-addresses");
decisionActionLayer.setAttribute("aria-hidden", "true");
// The selection chooser's two faces. Hints and the active search result are paint only;
// the search box is a real control, kept beside them so its focus and accessible name are
// the platform's rather than a keyboard mode's imitation of one.
const selectionLayer = el("div", "lf-ui lf-targets");
selectionLayer.setAttribute("aria-hidden", "true");
const selectionSearch = el("div", "lf-ui lf-target-search");
selectionSearch.setAttribute("role", "search");
selectionSearch.hidden = true;
const selectionInput = document.createElement("input");
selectionInput.className = "lf-target-search-box";
selectionInput.type = "search";
selectionInput.autocomplete = "off";
selectionInput.spellcheck = false;
selectionInput.maxLength = 160;
selectionInput.placeholder = "Search page text";
selectionInput.setAttribute("aria-label", "Search page text");
const selectionStatus = el("span", "lf-target-search-status");
selectionStatus.setAttribute("role", "status");
selectionSearch.append(selectionInput, selectionStatus);
// The runtime's parts, named: a design comment can point at one, and an anchor names an
// element by id, so each part that is a thing to point at carries a stable one under the
// runtime's own prefix. `[id]:not(.lf-ui)` — how the anchor pass asks which section a
// passage is in — still passes over them, every one wearing lf-ui. What has no id is
// what nobody comments on: the notice, the live region, the scope root itself.
for (const [part, id] of [
  [banner, "lf-banner"],
  [versionMenu, "lf-versions"],
  [othersPanel, "lf-leaves"],
  [decisionsPanel, "lf-decisions"],
  [panel, "lf-threads"],
  [fab, "lf-comment-button"],
  [composer, "lf-composer"],
  [helpEl, "lf-help"],
  [keylineEl, "lf-keyline"],
])
  part.id = id;
// The one scope root for the chrome's private rules: they match nothing outside
// this container. A div, not a lf-* element — the render gate reads a lf-* ancestor
// as "inside a widget", and the runtime's layer is inside none.
const chromeRoot = el("div", "lf-chrome");
chromeRoot.append(
  banner,
  overflowMenu,
  versionMenu,
  othersPanel,
  decisionsPanel,
  panel,
  legendRoot,
  addressLayer,
  decisionActionLayer,
  selectionLayer,
  selectionSearch,
  aimBox,
  fabBar,
  liveEl,
  helpEl,
  keylineEl,
  inspectEl,
);
// The chrome follows `main` in the document, which is right for reading and wrong for
// reaching: nothing stood between the top of the page and the banner but the whole page,
// and the top of the page is where a keyboard reader's next Tab starts whenever they are
// holding no control. So one stop stands in front of everything, the way a skip link
// always has.
//
// Prepended to the body rather than put in the chrome, because tab order is document
// order and the chrome is last; there is no `tabindex` that would buy this and no reason
// to want one. It carries the offer marker `offer` writes, so paper drops it with every
// other injected control and a copy takes it out with the layer it points at. It takes no
// row in the register either: a control is a route to a capability rather than a
// capability of its own, and this one's whole design is to be the first thing a reader
// finds without having been told about it.
// Which control it lands is decided by the press taking, not by a reading of whether the
// control looks available. The banner's controls are conditional in several ways at once
// — Leaves is absent where the machine has one leaf, Asks where the page waits on
// nobody, the newest-version chip is drawn only while there is a newer version, and
// sign-off is disabled until the page is presented — and each of those makes focus
// silently do nothing rather than fail. So the walk asks the browser the only question
// that matters here, whether the reader ended up on it, and the banner itself is the
// answer when none of them will have them.
const skipToChrome = offer("button", "lf-skip", "Skip to Leaf controls");
skipToChrome.onclick = () => {
  for (const control of banner.querySelectorAll(FOCUSABLE)) {
    control.focus({ preventScroll: true });
    if (control.matches(":focus")) return;
  }
  focusDestination(banner);
};
document.body.prepend(skipToChrome);
document.body.append(chromeRoot);
// The controls that rewrite their own words hold the widest of them, measured in the
// face and padding the banner is using now (see the stylesheet's banner comment). The
// covering row deliberately spends less horizontal padding than the wide one, so its
// media-query transition has to renew these measurements in both directions; an inline
// minimum measured once on a desk would otherwise make that responsive padding inert.
// The counters hold the widest they reach anywhere below a thousand, so no count they
// write can move them — a page with a thousand open threads, or a machine with a thousand
// live pages, is not one anyone hands a user.
//
// Every address stands on the row while this runs. A control measures its own words in
// its own live face, and inside the shut menu the fold may have put it in there is no
// box to measure: every word comes back zero and the floor with it. The fold is asked
// again at the end, against the reservations this just took.
function reserveBannerControls() {
  unfoldShelf();
  if (signoff) reserve(approveBtn, ["Approve version", "✓ Version approved"]);
  // News keeps one readable address while it changes words. The row folds rather than
  // clips, so no control has to collapse into an illegible pressure release.
  reserve(latestChip, [
    "New page available → open v999",
    "Latest edit couldn't be shown",
  ]);
  reserve(versionBtn, versionLabels());
  reserve(toggleBtn, ["Threads", "Threads (999)"]);
  reserve(needsBtn, ["Waiting on you", "Waiting on you (999)"]);
  reserve(decisionsBtn, ["Asks (999/999)"]);
  reserve(othersBtn, ["All leaves (999)"]);
  foldShelf();
}
let reservedCovering = commentsEdge.over.matches;
reserveBannerControls();
// The reservations are measured in the padding the current breakpoint gives the row's
// controls, and the fold reads them to decide what the row can hold — so they have to be
// this breakpoint's before anything is measured against them. A crossing is two events, a
// resize and a media query change, and the platform does not order them against each
// other: a fold running on the resize measured the narrow row against the widths the
// window it had just left reserved, folded an address the narrow row had room for, handed
// the reader the door it went behind, and then had the renewal behind it take that door
// away with the reader still standing on it. Hung off the geometry writer instead, the
// renewal is always the crossing's first act, whichever event arrives first.
function currentBannerReservations() {
  if (reservedCovering === commentsEdge.over.matches) return;
  reservedCovering = commentsEdge.over.matches;
  reserveBannerControls();
}
// ---------- state ----------

// Until the first state answer, [] means "not read", not "no comments". Keep that
// distinction for a Threads panel restored or opened during startup; its General
// composer stays usable while the log-derived list says what it is waiting for.

// The threads the panel last reconciled. A receipt repaints on the heartbeat's clock and
// not only on the log's, because its age is half of what it says and a claim nobody
// renews is exactly the one whose age has stopped moving. Keeping the last fold is what
// makes that cheap: buildThreads walks the log and the page, and a second walk every two
// seconds would answer nothing the last one didn't.
let selectionComposerRuntime;

let updateRuntime;
const updateSequence = (target = null) => updateRuntime.updateSequence(target);
const replaceClaimState = (...args) => updateRuntime.replaceClaimState(...args);
const workClaimState = () => updateRuntime.workClaimState();

chromeLayout = createChromeLayout({
  chromeRoot,
  closeReactions: () => setReact(false),
  commentsEdge,
  containsAcross: (...args) => containsAcross(...args),
  currentTray,
  dockSeats: () => anchorRuntime?.dockSeats(),
  focused,
  foldShelf: () => {
    currentBannerReservations();
    foldShelf();
  },
  keylineEl,
  motion,
  pageShifted: (...args) => pageShifted(...args),
  paintHere,
  panel,
  panelChanged: (open) => {
    if (open) livingMargin?.closePreview();
  },
  panelFoot,
  panelList: threadsBox,
  readerStore,
  refreshFab: (...args) => refreshFab(...args),
  refreshHover: (...args) => refreshHover(...args),
  renderPanel: (...args) => renderPanel(...args),
  reserveListClearance,
  showTray,
  syncReactLayout: (...args) => syncReactLayout(...args),
  syncGeneral: (...args) => syncGeneral(...args),
  toggleBtn,
  traysEdge,
});
const { inPanel, panelCovers, panelIsOpen } = chromeLayout;
createNotifications({ liveEl, noticeEl });

// ---------- text inputs ----------
const { paint: paintInputs, wire: wireInput } = createInput({
  focused,
  keys,
  notice,
  spell,
});
paintInputHints = paintInputs;

const { landTyping, mayLandTyping, pageSelection, selectionAnchor, snapSelection } =
  createSelectionCapture({
    anchoringIsReady: () => anchoringReady,
    blockOf: (...args) => blockOf(...args),
    closestAcross: (...args) => closestAcross(...args),
    collapseWhitespace: (text) => text.replace(COLLAPSE, " "),
    cut: (...args) => cut(...args),
    datumSelector: () => DATUM,
    elementOver: (...args) => elementOver(...args),
    focused,
    neighbourhood: (...args) => neighbourhood(...args),
    pageRange: (...args) => pageRange(...args),
    pageText: (...args) => pageText(...args),
    pageWords: (...args) => pageWords(...args),
    quoteFrom: (...args) => quoteFrom(...args),
    segmentText: (...args) => textUnits.segment(...args),
    segmentsIn: (...args) => segmentsIn(...args),
    spanIn: (...args) => spanIn(...args),
    takesLetters: (node) => takesLetters(node),
  });

const {
  BANNER_CLEAR,
  activateVisual,
  dismissFab,
  fabAnchorAt,
  fabOptionsAvailable,
  fabTargetAt,
  fabReturnTo,
  focusFabComment,
  focusTargetComment,
  openOnItem,
  refreshFab,
  selectResponseTarget,
  showFab,
  showFabOptions,
  standDown,
  updateFab,
} = createSelectionSurface({
  anchoringIsReady: () => anchoringReady,
  anchorLabel: (...args) => anchorLabel(...args),
  banner,
  blockAt: (...args) => blockAt(...args),
  composerIsOpen: () => composerOpen,
  closeVersionMenu,
  collapseKeyline: () => keyline?.less(),
  designIsOn: () => designOn,
  designTarget,
  fab,
  fabBar,
  fabInput,
  hideComposer: () => hideComposer(),
  hideReference: () => reference.show(false, false),
  hasOtherResponses: (anchor) =>
    reactionTokens().length > 0 || Boolean(anchor?.quote && !designOn),
  inChrome: (node) => inChrome(node),
  isReactArmed: () => isReactArmed(),
  keylineEl,
  leavePageControl: () => letGo(),
  markAt,
  noteClass: () => NOTE,
  openComposer,
  openOnDesign,
  pageRange: (...args) => pageRange(...args),
  pageSelection,
  pageText: (...args) => pageText(...args),
  pageWords: (...args) => pageWords(...args),
  paintAnchors,
  paintHere,
  paintStanding: paintReactionStanding,
  panel,
  panelCovers,
  panelList: threadsBox,
  pointerAt,
  reactionContextContains: (node) => reactionContextContains(node),
  reactionsOn: (anchor) => conversationRuntime.reactionsOn(anchor),
  referenceIsOpen: () => reference.open,
  resolveAnchor: (...args) => resolveAnchor(...args),
  selectionAnchor,
  setReact: (on) => setReact(on),
  showThread,
  snapSelection,
  shownParts,
  shownRect: (...args) => shownRect(...args),
  takesLetters: (node) => takesLetters(node),
  versionMenuIsOpen,
  visualActionAnchor: (...args) => visualActionAnchor(...args),
  visualAt: (...args) => visualAt(...args),
});

const { AIM, aimIsOn, aimedItem } = createAim({
  aimTargetAt,
  designIsOn: () => designOn,
  designPress,
  designTarget,
  elementFromPointAcross: (...args) => elementFromPointAcross(...args),
  inChrome: (node) => inChrome(node),
  focusTargetComment,
  openOnDesign,
  pointerAt,
  refreshAim,
  spell,
  standDown,
});
// ---------- design mode ----------
let designRuntime;
function setDesign(...args) {
  return designRuntime.setDesign(...args);
}
function paintLegend(...args) {
  return designRuntime.paintLegend(...args);
}
function queueLegend(...args) {
  return designRuntime.queueLegend(...args);
}
function designTarget(...args) {
  return designRuntime.designTarget(...args);
}
function designName(...args) {
  return designRuntime.designName(...args);
}
function designPress(...args) {
  return designRuntime.designPress(...args);
}
function openOnDesign(...args) {
  return designRuntime.openOnDesign(...args);
}

selectionComposerRuntime = createSelectionComposer(runtime, {
  clearDraft,
  closeReactions: () => setReact(false),
  composer,
  composerInput,
  composerSend,
  designIsOn: () => designOn,
  draftContexts,
  elementById: (...args) => elementById(...args),
  fab,
  fabAnchor: fabAnchorAt,
  fabBar,
  inChrome,
  landTyping,
  loadDraft,
  mayLandTyping,
  openInlineThread: (...args) => livingMargin?.openInlineThread(...args) ?? null,
  panelIsOpen,
  paintAnchors,
  paintHere,
  post,
  refreshFab,
  saveDraft,
  sendDraft,
  showFab,
  showThread,
  suggestCheck,
  suggestRow,
  threadsBox,
  watchDraft,
  wireInput,
});

function openComposer(anchor, text, options = {}) {
  return selectionComposerRuntime.openComposer(anchor, text, options);
}
const hideComposer = () => selectionComposerRuntime.hideComposer();

// What the general box is for, said once: its own placeholder wears it, and so does the
// panel row whose key opens it. Two strings would be two chances to rename the mode in
// one of them.
const generalHint = () => (designOn ? "Comment on the layer" : "Comment on the page");

// The row whose key opens that box, standing here beside the sentence they share rather
// than down among the panel's other rows. The box paints its placeholder as `wireInput`
// builds it, and the placeholder names this row's key — read off the row, so rebinding it
// corrects the box too. Built later, the row is still in its dead zone at that first
// paint and the whole layer stops on the reference. The comment above already calls the
// two a pair; this is the pair being one thing rather than two that agree by hand.
const PANEL_SAY = {
  // From the Threads list this puts the reader in the page-comment box. Page c reaches
  // the same box directly; this is the same contextual intent from a surface whose local
  // w and / commands remain useful until the reader asks to write.
  id: "comment.write",
  keys: ["c"],
  does: () => generalHint(),
  line: "comment",
  // Dead while the reader has a passage or an item in hand. `t` is a page key that
  // lands focus in the panel, so a reader who selected a paragraph and then walked
  // the threads is standing in this scope with their selection still live — and this
  // row, being the innermost, would have taken the press and spent it on the general
  // box, collapsing the selection as the box took focus. A gesture the reader made
  // outranks the room they happen to be standing in, so the row stands down and the
  // page's own c answers, on the passage, saying so on the key line first.
  //
  // Dead inside a conversation for the same reason read the other way. This scope is
  // live wherever focus is in the panel, a card the reader has walked to included, and
  // that card's own reply box is a nearer answer to "comment" than the general box is
  // — the one `Enter` reaches from here. Standing in a
  // conversation is the page's second destination, so the row stands down and lets it
  // answer, and the two ways into a thread's box stay one landing. A resolved card has
  // no box to be the nearer answer, and standingConversation reads the box rather than
  // the class, so the press there is the general box's after all.
  when: () => !fabAnchorAt() && !standingConversation(),
  returnFrame: () => ({
    active: () => generalRow.contains(documentFocused()),
    close: () => generalInput.blur(),
    does: "Return to the thread panel",
    line: "back to threads",
  }),
  run: () => generalInput.focus({ preventScroll: true }),
};

const syncGeneral = wireInput(generalInput, {
  // The box has no anchor to decide it at an open, so what it posts is decided at the
  // send, by the mode standing then — and the hint says which, so the reader typing in
  // design mode knows their remark is about the layer as a whole.
  hint: generalHint,
  // The box's own address: unfocused, the placeholder reads "Comment on the page · c".
  // The same c reaches this box from the page or from the panel list. One key rather than
  // a chord, because “comment” is the intent in both contexts.
  //
  // Read off the row that answers the press rather than spelled here, which is the rule
  // the reference states about itself: a fact about a binding written somewhere the
  // binding cannot correct it goes on promising a key nobody rebound it with. Named for
  // that alone — the row is otherwise `PANEL`'s like any other. The forward reference is
  // only ever resolved at paint.
  address: () => labelOf(PANEL_SAY),
  sends: "send",
  sendBtn: generalSend,
  save: (v) => saveDraft("general", v),
  send: async (text, raw) => {
    const event = { kind: "comment", revision: runtime.currentRevision, text };
    if (designOn) event.about = "layer";
    const sent = await sendDraft(
      "general",
      () => generalInput.value === raw,
      (attempt) => post({ ...event, attempt }),
    );
    if (!sent) return;
    const shouldLand = mayLandTyping(generalInput);
    showThread(sent.id, { stand: false });
    if (shouldLand) landTyping(generalInput); // both send routes end where typing was
  },
});
mirrorDraft(generalInput, syncGeneral, "general");

let approving = false;
function paintApproval() {
  const approved = (runtime.browser?.conversation?.done ?? []).some(
    (e) =>
      e.kind === "done" &&
      e.revision === runtime.currentRevision &&
      e.version === runtime.currentStamp,
  );
  approveBtn.disabled =
    approving ||
    runtime.currentStamp === null ||
    !document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented) ||
    approved;
  approveBtn.textContent = approved ? "✓ Version approved" : "Approve version";
  // The word and the title turn over together. The title read "Approve this work; the
  // page stays open for follow-up" whether or not the work had been approved, so the one
  // surface that could have told a reader what pressing it would do next went on
  // describing a press they had already made. Approved, it says the state and the way
  // out of it, which is `z` like every other reader gesture.
  approveBtn.title = approved
    ? "Approved. Press z to take it back while it is still your last gesture"
    : "Approve this work; the page stays open for follow-up";
  paintHere();
}
approveBtn.onclick = async () => {
  if (approving) return;
  approving = true;
  approveBtn.setAttribute("aria-busy", "true");
  paintApproval();
  try {
    await post({
      kind: "done",
      revision: runtime.currentRevision,
      version: runtime.currentStamp,
      text: "Looks good",
    });
  } finally {
    approving = false;
    approveBtn.removeAttribute("aria-busy");
    paintApproval();
  }
};

// ---------- keyboard ----------
// The register's scopes, and the one dispatcher that walks them. What a row and a scope
// are is written where the vocabulary is defined (the key register, above).
//
// The stack is innermost-first: the g chord and the help overlay above everything, then
// whatever element scopes focus stands inside, then the page's own modes and the page. The
// line walks it outward, the dispatcher matches down it, and a row sharing any binding with
// one already named is skipped — so a focused control's keys shadow the page's without
// either knowing about the other, and no press is promised twice. A scope's `claims` stop
// both walks at the keys it owns whole: the ones that type a character into a box, and the
// whole keyboard under the reference overlay. Both walks read the one declaration, where
// two guards in two functions had drifted.
//
// Escape is a binding like any other. A control's own inner step precedes the latest
// command return frame; generic text and pointer/traversal fallbacks stand behind it.
// The dispatcher runs the first live row and no other. It alone captures and pushes
// command frames, and declaration validation refuses an incomplete return contract, so
// an entry cannot restore at a different point on its key and reference routes.

const pageParts = (sel) =>
  [...document.querySelectorAll(sel)].filter((el) => !inChrome(el));

// ---------- what the page's keys are live over ----------
const hasThreads = () => openThreads().length > 0;
// The focused thread, one predicate: the row the line paints and the press the dispatcher
// takes ask the same question, so they cannot disagree about which thread this is. Not a
// control inside it, whose own press is its own. Open and resolved threads both qualify:
// each has a primary Enter action and x changes the same resolution state in either direction.
const focusedThread = () => {
  const active = documentFocused();
  return active?.classList?.contains("lf-thread") ? active : null;
};
// The item the reader is standing in, which is what a press means when they have pointed
// at nothing. The ⌥ aim reaches an item through the pointer and focus used to reach none
// at all: tabbing to a link in an option left `c` offering the page.
//
// The unanswered decision where the reader is standing on a control that works it, and the innermost
// item everywhere else. The control the walk stands them on is one part of the question
// (standOn), so a press made
// from a pick, a ✓ or a mark means the question those answer. Standing *in* a decision is not
// the same fact: a reader who tabbed to a hyperlink has said
// something more particular than the question containing it, and answering the question
// there both overrides what they named and made the same markup answer differently
// according to whether its question was still open — a link in a settled group gave the
// option, the identical link in an open one gave the whole group.
//
// So the ring `markHere` paints and this are two questions, and the earlier version had
// them confused. The ring says which decision the reader is in, for the walk and the answering
// keys; this says what a remark made here is about. They agree wherever the reader is
// working the decision, which is every arrival the decision walk makes.
//
// Below that, the innermost item — the aim's own reading — through `decisionPlace`, so a
// control a widget hoisted into the margin speaks for the decision it points back at rather
// than for the block it hangs beside.
//
// Focus in the chrome is not a place in the page. The banner, the panel and the trays are
// where a reader works on the page rather than where they stand in it, so a press made
// from one means the page whole. A box that takes letters never arrives here at all: the
// typing scope claims the letter before the page is asked.
//
// `documentFocused()` rather than `focused()`, for the reason decisionPosition gives: a control
// staged in a shadow tree retargets to its host, and the host is the place in the document
// both the chrome guard and the item walk want. standingConversation below wants the inner
// reading, and says so.
const standingItem = () => {
  const held = documentFocused();
  if (!held || held === document.body || inChrome(held)) return null;
  const working = held.matches?.(DECISION_CONTROL) ? standingIn() : null;
  return working ?? itemAt(decisionPlace(held));
};
// The conversation the reader is standing in, and the box it is written in. Three
// containers hold one and the reader can stand in any of them: the panel's thread, a
// conversation seated on the page (x-conversation), and each thread inside that seat. They
// are one question — a press meaning "say something about this" belongs to the box of the
// conversation the reader is already in — so they get one reading rather than a rule for
// the panel and a different one for the page. `conversationBox` states the same rule from
// the other side when it declines to seat a widget standing inside a thread.
//
// One of the three is in the chrome, which is not the exception it looks like: page scope
// already crosses there. A page key that takes the reader somewhere owes them an answer
// once they are standing there.
//
// The box decides membership, rather than the container's class deciding it. A resolved
// thread is built by the same function, wears the same class, and keeps a tab stop and a
// Reopen button — reading the class alone put the reader in a thread whose box is not
// there and the press died on the null. Asking for the box answers both shapes at once,
// and answers a container that is merely collapsed the same honest way: no box, so this is
// not where the press goes.
//
// `focused()` here where standingItem takes the host: this asks whether the reader is
// inside a conversation, and a widget an agent sent stages its controls in a shadow tree
// of its own, so the innermost focus is where they actually are. The climb out is
// closestAcross's.
// What `c` acts on, decided once and read twice: the row's words are `word` and the press
// is `go`, so the line, the reference and the box that opens cannot come to name different
// things. Spelled out at each of them the ladder was two hand-written copies in the same
// order kept in step by hand, which is the mistake `focusedThread` already names — the row
// the line paints and the press the dispatcher takes have to ask one question.
//
// One aim and then one climb, rather than four cases. The pointer's aim outranks position,
// being the more recent thing the reader said; below it the answer walks outward from where
// they are standing — the nearest conversation's box, then the nearest item, then the page,
// which is what is left when they are standing nowhere in it. An element anchor answers in
// its own word (a figure, a card), the way the panel names one.
//
// Every destination is a box to write in and says so in the same sentence; the word is
// what varies.
const commenting = (word) => ({
  does: `Comment on the ${word}`,
  line: `comment on the ${word}`,
});
function workspaceControlRoute(control) {
  if (!control || control === document.body) return () => null;
  const decision = control?.closest?.(".lf-decisions-row[data-lf-at]");
  if (decision) {
    const target = decision.dataset.lfAt;
    return () =>
      [...decisionsPanel.querySelectorAll(".lf-decisions-row[data-lf-at]")].find(
        (row) => row.dataset.lfAt === target,
      ) ?? null;
  }
  const thread = control?.closest?.(".lf-thread[data-id]");
  if (thread) {
    const id = thread.dataset.id;
    return () =>
      [...panel.querySelectorAll(".lf-thread[data-id]")].find(
        (row) => row.dataset.id === id,
      ) ?? null;
  }
  const leaf = control?.closest?.(".lf-others-panel a[href]");
  if (leaf) {
    const href = leaf.href;
    return () =>
      [...othersPanel.querySelectorAll("a[href]")].find((link) => link.href === href) ??
      null;
  }
  return () => (control?.isConnected ? control : null);
}
const workspaceState = () => ({
  panel: panelIsOpen(),
  tray: currentTray(),
  control: workspaceControlRoute(documentFocused()),
});
function restoreWorkspace(state) {
  const { panel: hadPanel, tray } = state;
  if (tray) showTray(tray);
  else if (hadPanel) {
    showTray(null);
    setPanel(true);
  } else {
    showTray(null);
    setPanel(false);
  }
  return state.control();
}
const composerReturnFrame = () => ({
  active: () => composerOpen,
  close: dismissFab,
  does: "Return to where you were",
  line: "back",
});
const boxReturnFrame = (held, box, does = "Return to the thread") => ({
  active: () =>
    held?.isConnected && (containsAcross(held, focused()) || box === focused()),
  close: () => box.blur(),
  does,
  line: "back to thread",
});
const commentDestination = () => {
  const anchor = fabAnchorAt();
  if (anchor)
    return {
      ...commenting(
        anchor.quote ? "selection" : itemWord(elementById(anchor.section)) || "item",
      ),
      go: focusFabComment,
      returnFrame: composerReturnFrame,
    };
  const inline = livingMargin?.activeInlineThread();
  const inlineBox = inline && conversationInput(inline);
  const said =
    standingConversation() ?? (inlineBox ? { held: inline, box: inlineBox } : null);
  if (said)
    return {
      ...commenting("thread"),
      go: () => landIn(said),
      returnFrame: () => boxReturnFrame(said.held, said.box),
    };
  const here = standingItem();
  if (here)
    return {
      ...commenting(itemWord(here)),
      go: () => commentOnItem(here),
      returnFrame: composerReturnFrame,
    };
  return {
    ...commenting("page"),
    go: () => {
      setPanel(true);
      generalInput.focus({ preventScroll: true });
    },
    returnFrame: () => {
      const workspace = workspaceState();
      return {
        active: () => panelIsOpen() && generalRow.contains(documentFocused()),
        close: () => restoreWorkspace(workspace),
        does: "Return to where you were",
        line: "back",
      };
    },
  };
};
const hasCapturedTarget = () => Boolean(fabAnchorAt());
// c goes where commenting happens: a live selection gets the composer (what the floating
// button does), an element click's pending 💬 gets that, an open thread the reader is
// standing in gets its own reply box, the item they are standing in gets the box belonging
// to it, and otherwise the page's general box. That box lives in Threads, but c names and
// focuses the box directly; g T independently names the list. Never the panel's collapse:
// c doubled as the toggle once, so with the panel standing open the key that promised
// “comment” answered “close”. Backing out is the entry's return frame.
//
// Standing outranks the page and not the pointer: a reader who has just selected words or
// raised the 💬 on something has said what they mean more recently than the focus they left
// behind, which is the order decisionPosition reads its own answers in.
function commentKey() {
  updateFab(); // the selection may be newer than the mouseup that last placed the bar
  commentDestination().go();
}

// Pages are authored documents where typing can start at any moment, so a scope whose keys
// are bare letters stands down wherever a letter is a keystroke. That is the whole of the
// question, and asking a wider one cost the page its keyboard: every `<input>` counted,
// so a reader standing on a screenshot's before/after radio — which consumes no letter the
// platform ever gave it — lost c, page travel, decision travel and the rest, with nothing on screen saying why.
// A select is in, its letters jumping its options; a radio, a checkbox, a slider, a colour
// or file button are out. The platform's set of text-entry types, stated whole: a denylist
// named the two controls to hand and left a slider swallowing the Escape rung the same way
// the version chooser had. A bare or unknown type resolves to "text", so the default lands
// on the typed side.
const TYPED_TYPES = new Set([
  "text",
  "search",
  "url",
  "tel",
  "email",
  "password",
  "number",
  "date",
  "time",
  "datetime-local",
  "month",
  "week",
]);
const takesLetters = (node) =>
  Boolean(node) &&
  (node.tagName === "TEXTAREA" ||
    node.tagName === "SELECT" ||
    node.isContentEditable ||
    (node.tagName === "INPUT" && TYPED_TYPES.has(node.type)));

// Letting go of what the reader is standing on. One act at both ends of the ladder, and
// one line of code, because standing on a decision out on the page and standing on a banner
// button are the same state — the reader holding something — reached from either side of
// the chrome. What the two rungs do not share is the word, and neither word is the other's:
// leaving the chrome names where the reader lands, since that is the whole of what the
// rung is for, and letting go of a decision names the act, since they were on the page all
// along.
//
// Focus rather than blur, because the two differ in what Space does next: a focused
// control owns the key, while body hands it back to the browser's root scrollport. A blur
// names no deliberate destination even when activeElement subsequently reads as body.
//
// Body therefore needs to be somewhere a reader can be put even on a short page. The
// explicit tab stop is programmatic only and gives every Escape handoff the same stable
// page destination without adding a visible stop to the Tab order.
document.body.tabIndex = -1;
const letGo = () => document.body.focus({ preventScroll: true });
// Auto popovers and modal dialogs already put Escape in the platform contract. When one
// stands, let the browser dismiss the topmost layer and let that layer's toggle/close
// event update Leaf state. Product modes with a nearer Escape row (the composer, help's
// two-step shelf, a text box) still own their deliberate unwind step.
const browserDismissesTopLayer = () =>
  Boolean(document.querySelector(":popover-open, dialog:modal"));
// The fallback Escape reading for state reached without a registered keyboard entry:
// pointer-opened workspaces, captured targets, and ordinary focus traversal. Commanded
// entries use the return stack and never infer their inverse from this resulting scene.
//
// So the first rung is theirs: out on the page, the innermost thing they are in is the decision
// they are standing on, and a panel behind them is a layer they are not in. Nothing said
// this before — a reader the walk had brought to a decision could press Escape all day and the
// ring stayed on it, the one place in the runtime a key put the reader somewhere with no
// key to take them out again.
//
// Inside the chrome it is the open workspace first. Trays and Threads replace one
// another, so a standing tray is the one auxiliary layer Escape can unwind.
//
// Then the last rung leaves the chrome, because closing the panel does not put the reader
// back on the page: it lands them on the control that closes it, deliberately (setPanel
// says why), and the closing keypress rings a button a pointer-borne reader never chose.
// Their next Space is then that button rather than the page's scroll. CLAUDE.md's "The
// reader has to be standing somewhere" holds the rest.
function rung() {
  const active = documentFocused();
  const holding = Boolean(active) && active !== document.body;
  if (pageSelection() || fabAnchorAt())
    return {
      says: "unselect",
      does: "Clear the selection",
      out: dismissFab,
    };
  if (holding && !inChrome(active))
    return { says: "let go", does: "Let go of what you are standing on", out: letGo };
  // Whichever tray holds the edge, named by the rung so the reader is told what the
  // press will take rather than being told "close the tray" over two of them.
  const tray = currentTray();
  if (tray)
    return {
      says: `close ${tray}`,
      does: `Close the ${tray} tray`,
      out: () => showTray(null),
    };
  // A narrowing is a layer of the panel the way a tray is a layer of the page: the
  // reader put it on, and the list in front of them is not the whole of the conversation
  // until it comes off. So it unwinds before the panel does, and from wherever they are
  // standing — the find box binds the same step for itself, being the one place the
  // reader can see what they are backing out of.
  if (panelIsOpen() && narrowed())
    return { says: "show all", does: "Show every thread again", out: widen };
  if (panelIsOpen())
    return {
      says: "close threads",
      does: "Close the thread panel",
      out: () => setPanel(false),
    };
  if (holding)
    return { says: "back to the page", does: "Back out onto the page", out: letGo };
  return null;
}
// The page's own Escape, said and run off one object: each rung states the act, the word
// the line paints over it and the sentence the reference lists. A row rather than a rung,
// so the reference names it beside every other key and cannot list a stale half of the
// ladder.
//
// The sentence is the rung's for the reason `c`'s is the anchor's: the reader can see
// which branch they are in, so a word covering all of them tells them nothing. "Back out
// one layer" was true while every rung took a layer of chrome off the page, and stopped
// being true the day the first rung became letting go of a decision, which is no layer at
// all — the line saying "let go" while the reference said "layer" about the same press.
const BACK_OUT = {
  id: "navigation.back",
  keys: ["Escape"],
  does: () => rung()?.does,
  line: () => rung()?.says,
  // Clearing a captured target is still available, but c and r are the two actions on the
  // thing the reader just chose. Keep both on the short line and leave this row in the full
  // reference until the target is gone.
  promoteEscape: () => !hasCapturedTarget() || reactionTokens().length === 0,
  when: () => !returnStack.current() && !browserDismissesTopLayer() && Boolean(rung()),
  run: () => rung().out(),
};

// ---------- what a scope takes ----------
// A scope shadows what stands behind it two ways, and they are one rule: a row of its own
// that names the key, and a claim on keys it has no row for. The second is the platform's
// share — where the reader stands, the browser already answers these and the register has
// nothing to run and nothing to say, so an outer row that named one would be promising a
// press it will not get. Everything not claimed stacks: a scope's rows are reached
// wherever no nearer scope has taken the binding.
//
// This was a blanket (`only: true`), and the blanket is what put a working keyboard out of
// a reader's reach. A text box does claim every key that types a character, so the blanket
// was right about the case it was written for and wrong about the class: the box also took
// the Escape it has no use for, which one branch inside its own row then hand-rescued for
// the controls that type nothing. One key rescued and every other one left swallowed is the
// shape of a menu being extended. Named as a claim instead, the rescue is deleted rather than
// widened: a select's typeahead takes the letters and leaves the page's Escape standing,
// and a radio, which types nothing, claims nothing and keeps the whole keyboard.
const EVERYTHING = () => true;
// A character key belongs to the box with any modifier: Shift changes its case, Alt may
// compose it, and Mod chords copy, select, or undo. The editing keys below stay the box's
// with modifiers too, so Shift+Arrow can extend a selection and Mod+Backspace can delete a
// word without an ancestor widget turning either into its own action. An exact element
// scope still stands nearer and can specialise a chord such as Mod+Enter for send.
const CHARACTER = (binding) => [...parsed(binding).key].length === 1;
const EDITING = new Set([
  "Enter",
  "Backspace",
  "Delete",
  "ArrowLeft",
  "ArrowRight",
  "ArrowUp",
  "ArrowDown",
  "Home",
  "End",
  "PageUp",
  "PageDown",
]);
const TEXT_ENTRY = (binding) => CHARACTER(binding) || EDITING.has(parsed(binding).key);
// What a mode standing over the page takes: the page's keys, and every scope between, minus
// the one key that says what this mode's own keys are. The reference is the exemption for the
// same reason the line draws its chip last whatever the room — a reader who has just opened
// something unfamiliar is exactly the reader who needs it, and a mode that swallowed it would
// leave the line naming a walk and no way to ask about anything else.
//
// A `function`, so the row it reads can be the one the page's own table declares: the modes
// are built beside the controls they belong to, further up than that table, and a claim is
// only ever called at a press. A blanket suits a mode that cannot outlive a keystroke — the
// chord disarms on any key and runs it again, so `?` still reaches the page behind it — and
// the versions menu is the other kind, standing until the reader closes it.
function allButTheReference(binding) {
  return !bindings(REFERENCE).includes(binding);
}

// ---------- the scopes ----------
// Above everything: the chord is armed, or the reference is up. Both claim everything — the
// page stands down under them — and each declares what it keeps, which is how the
// reference's own key goes on working while every other one is suspended.

const { decisionEntry, isAwaiting, projectedParent, unansweredDecisions } =
  createDecisionModel({
    authoredParentOf: (node) => authoredParents.get(node),
    closestAcross: (...args) => closestAcross(...args),
    elementById: (...args) => elementById(...args),
    pagePresented,
    registry,
    runtime,
    stateProjection: (...args) => stateProjection(...args),
    tagsDeclaring,
  });

// Dispatch is composed after the page table. Until then the decision view can paint its
// ring but has no complete scope stack from which to claim that a digit is reachable.
let decisionActionReachable = () => false;
const {
  DECISION_CONTROL,
  DECISION_ROW,
  actionRow,
  decisionPlace,
  buildBulkAnswers,
  goToDecision,
  landedAt,
  markHere,
  renderDecisions,
  setLanded,
  standOn,
  standingIn,
  stepDecision,
  syncDecisions,
} = createDecisionView({
  PAGE_PAINT_ATTRIBUTE,
  actionLayer: decisionActionLayer,
  actionReachable: () => decisionActionReachable(),
  scrollBehavior,
  documentFocused,
  announce,
  decisionEntry,
  decisionSource,
  decisionsBtn,
  decisionsList,
  decisionsOffered,
  decisionsPanel,
  banner,
  readingBlock,
  closeTray: () => showTray(null),
  el,
  elementById: (...args) => elementById(...args),
  focusForNavigation: (control) => {
    if (livingMargin) livingMargin.focusForNavigation(control);
    else control.focus({ preventScroll: true });
  },
  focused,
  inChrome: (node) => inChrome(node),
  itemSays,
  itemWord,
  keylineEl,
  keys,
  openDecisions,
  openTray,
  paintAnchors,
  paintHere,
  paintKeys,
  PRESS,
  panelIsOpen,
  presentedActionControl: (control) =>
    livingMargin?.presentedControl(control) ?? control,
  readableDestination: (...args) => readableDestination(...args),
  registry,
  reserve,
  reveal,
  scrollToElement,
  setPanel,
  showNews,
  shownParts,
  tagsDeclaring,
  trayCovers: () => traysEdge.over.matches,
  unansweredDecisions,
  versionBtn,
});

const {
  commentOnItem,
  glideTo,
  placeThreadEdge,
  seenScroller,
  stepReading,
  stepThread,
} = createNavigation({
  BANNER_CLEAR,
  reducedMotion,
  scrollBehavior,
  inChrome: (node) => inChrome(node),
  inPanel,
  openOnItem,
  openThreads,
  pageScroller,
  panelCovers,
  panelIsOpen,
  scrollToElement,
  scrollToThread,
  setPanel,
  shownRect,
  threadsBox,
});

const landInThreadReply = (thread) =>
  landIn({ held: thread, box: thread.querySelector(SAY_BOX) });

const { GO, GOTO, isChordArmed, paintAddresses, setChord } = createAddress({
  EVERYTHING,
  addressLayer,
  announce,
  decisionRows,
  decisionsPanel,
  decisionsOffered,
  directDestinations: [CHOOSER],
  banner,
  claimsEsc,
  el,
  enterPageMap: () => livingMargin?.enterPageMap(),
  leavePageMap: () => livingMargin?.leavePageMap(),
  focused,
  focusedThread,
  fragmentId,
  glideTo,
  inPanel,
  itemSays,
  keylineEl,
  leavesOffered,
  letGo,
  openPageMapItem: (item) => livingMargin?.openPageMapItem(item),
  othersLinks,
  othersPanel,
  pageMapItems: () => livingMargin?.pageMapItems() ?? [],
  pageParts,
  paintHere,
  panelCovers,
  panelIsOpen,
  pageMapIsActive: () => livingMargin?.pageMapIsActive() ?? false,
  placeThreadEdge,
  resolveAnchor,
  saying,
  seenScroller,
  setPanel,
  showTray,
  currentTray,
  workspaceState,
  restoreWorkspace,
  startsAt,
  scrollToElement,
  threadsBox,
});

const { PAGE_SEARCH, SELECT, isSelecting, paintTargets, startSelecting } =
  createTargetSelection({
    aimTargets,
    allButTheReference,
    anchoringIsReady: () => anchoringReady,
    announce,
    banner,
    blockAt: (...args) => blockAt(...args),
    contextAround: (...args) => contextAround(...args),
    cut: (...args) => cut(...args),
    el,
    findText: (...args) => findText(...args),
    focused,
    hasCapturedTarget,
    inChrome: (node) => inChrome(node),
    keyline: keylineEl,
    pageText: (...args) => pageText(...args),
    paintHere,
    quoteFrom: (...args) => quoteFrom(...args),
    rangeOf: (...args) => rangeOf(...args),
    scrollToRange,
    selectionInput,
    selectionLayer,
    selectionSearch,
    selectionStatus,
    selectResponseTarget,
    shownParts,
    shownRect: (...args) => shownRect(...args),
    updateFab,
  });

// ---------- reactions ----------
const {
  REACT,
  buildReactBar,
  buildReactSurface,
  isReactArmed,
  reactionContextContains,
  reactionTokens,
  sendReaction,
  setReact,
  syncReactLayout,
  undoSentence,
} = createReactions({
  CONTROL_WORD_CAP,
  EVERYTHING,
  PRESS,
  anchorLabel: (...args) => anchorLabel(...args),
  announce,
  buttonChoices: (target) => livingMargin?.buttonChoices(target) ?? [],
  buttonContextContains: (target, node) =>
    livingMargin?.buttonContextContains(target, node) ?? false,
  claimsEsc,
  currentRevision: () => runtime.currentRevision,
  cut: (...args) => cut(...args),
  designIsOn: () => designOn,
  el,
  elementById: (...args) => elementById(...args),
  fabAnchorAt,
  fabTargetAt,
  fabReturnTo,
  fabBar,
  focused,
  hideComposer: () => hideComposer(),
  foldButtonOptions: () => livingMargin?.foldButtonOptions(),
  itemWord,
  offer,
  openButtonOptions: (target) => livingMargin?.openButtonOptions(target) ?? false,
  paintHere,
  post,
  reactionVocabulary: () => registry.$reactions?.tokens,
  saying,
  showFab,
  notice,
  standingConversation,
  standingItem,
  suggestHere: () => selectionComposerRuntime.setSuggestionMode(true),
  undoable: (...args) => undoable(...args),
  unfoldedButtons: () => livingMargin?.unfoldedButtons() ?? null,
  visualPartLabel: (...args) => visualPartLabel(...args),
  withdraw: (...args) => withdraw(...args),
});
const HELP = {
  title: "In this reference",
  at: () => reference.open,
  claims: EVERYTHING,
  rows: [
    {
      id: "reference.focus.walk",
      keys: ["Tab", "Shift+Tab"],
      does: "Move through this reference",
      line: "move",
      repeat: true,
      runFromReference: false,
      run: (binding) => reference.move(binding === "Tab" ? 1 : -1),
    },
    {
      id: "reference.command.next",
      keys: ["ArrowDown"],
      does: "Choose the next command",
      line: "next command",
      repeat: true,
      runFromReference: false,
      // The list is built before search receives focus, so physical liveness is false at
      // that instant even though this is one of the reference's standing instructions.
      referenceWhen: () => true,
      when: () => reference.onCommandRail,
      run: () => reference.moveCommand(1),
    },
    {
      id: "reference.command.previous",
      keys: ["ArrowUp"],
      does: "Choose the previous command",
      line: "previous command",
      repeat: true,
      runFromReference: false,
      referenceWhen: () => true,
      when: () => reference.onCommandRail,
      run: () => reference.moveCommand(-1),
    },
    {
      id: "reference.command.run",
      keys: ["Enter"],
      does: "Run the chosen command",
      line: "run command",
      runFromReference: false,
      referenceWhen: () => true,
      when: () => reference.onCommandRail,
      run: () => reference.runSelected(),
    },
    {
      id: "reference.close",
      keys: ["Escape"],
      does: () =>
        keyline?.expanded ? "Back to more keyboard shortcuts" : "Close this reference",
      line: () => (keyline?.expanded ? "back to more shortcuts" : "close help"),
      also: helpClose,
      runFromReference: false,
      run: () => helpClose.click(),
    },
  ],
};
const LESS_SHORTCUTS = {
  id: "keyline.less",
  keys: ["Escape"],
  does: "Show fewer keyboard shortcuts",
  line: "less",
  referenceWhen: () => false,
  runFromReference: false,
  run: () => keyline.less(),
};
const SHORTCUT_SHELF = {
  title: "With more keyboard shortcuts",
  at: () => Boolean(keyline?.expanded),
  rows: [LESS_SHORTCUTS],
};

// A Thread card and the unfolded Button cluster that owns it are one page-map stack,
// though the card itself is hoisted into the chrome. This registered rung precedes the
// reaction and navigation modes just as the surface's old local listener did: Escape
// closes the card first, then folds the cluster on a second press.
const pageMapRung = (atFocus = true) => livingMargin?.keyboardRung({ atFocus }) ?? null;
const PAGE_MAP = {
  title: "In the page map",
  when: () => Boolean(pageMapRung(false)),
  at: () => Boolean(pageMapRung()),
  rows: [
    {
      id: "margin.back",
      keys: ["Escape"],
      does: () => pageMapRung(false)?.does,
      line: () => pageMapRung()?.says,
      referenceWhen: () => Boolean(pageMapRung(false)),
      when: () => Boolean(pageMapRung()),
      run: () => pageMapRung()?.out(),
    },
  ],
};

// Below the element scopes: the page's own modes, then the page. The composer's rung is
// its own scope rather than the box's, because the box may not have focus — the reader
// clicked away and the composer still stands, holding their draft.
const COMPOSER = {
  title: "In the composer",
  at: () => composerOpen,
  rows: [
    {
      id: "comment.options",
      keys: ["Tab"],
      does: "Show other responses",
      line: "other responses",
      when: fabOptionsAvailable,
      run: showFabOptions,
    },
    {
      id: "composer.close",
      keys: ["Escape"],
      does: "Close the composer, keeping the draft",
      line: "close — draft kept",
      promoteEscape: false,
      run: dismissFab,
    },
  ],
};
// The box a reply or a comment is typed into, which is the panel's; a page's own control
// is somewhere the reader is standing, not something they are writing in. Declared above
// the scope rather than below it, because a row naming a predicate directly reads the
// binding as the table is built — the deferring wrapper the branch here used to need was
// the only thing hiding that.
const inTheBox = () => panel.contains(documentFocused());
// The panel thread the reader is in, asked by class because that is the anchors module's
// question: which logged thread's passage to paint. It is not the box's way out, which
// climbs further and answers for a seat on the page too — the two readings stayed apart
// rather than one standing in for the other.
const focusedThreadOf = () => documentFocused()?.closest?.(".lf-thread");
// Where a box reached by Tab or pointer hands the reader back. Keyboard entry carries its
// own captured return frame before this fallback is reached. This once asked only for
// `.lf-thread` and the panel, so the two boxes outside the chrome — a conversation seated
// on the page, and each thread on that seat — had no relation to return through. The climb
// is `heldConversation`'s, the same relation contextual `c` uses when it names a thread.
//
// A seat holding no thread yet has no standing place of its own. A widget control that
// explicitly sends the reader into that box can supply its own return through
// `landInConversation`; a visit reached by Tab still falls through to the page's "let go".
// Otherwise the question is "can the reader be put here", rather than a list of which two
// containers happen to be focusable — which is also why a seat that `reachScrollers` makes
// focusable, having grown a scrollbar and no focusable child, becomes a rung without anyone
// editing this: the question is the same one, and the answer moved.
const backFromBox = () => {
  const held = heldConversation();
  if (held?.hasAttribute("tabindex")) return { target: held, line: "back to thread" };
  const route = backFromConversation(focused());
  return route?.target?.isConnected ? route : null;
};
// A box words are typed into takes character keys and the keys that edit it: Enter,
// deletion, caret movement, Home/End, and page movement, including their modified forms.
// Escape remains the box's to declare or pass on. What it declares is the way back out —
// to the thread a reply
// belongs to, so Esc then Enter round-trips, or to the list, so t/T walk on from where the
// backing-out started. Drafts are kept at every rung.
//
// A control the reader is standing on rather than writing in keeps that rung without this
// scope carrying a second branch for it. That branch is what this replaced: the swallow
// took the page's Escape from a select out on the page, so the row reimplemented the
// panels' rung inside its own `when` and `run` and said the other scope's word on the line.
// The keys nothing here reimplemented — c, the walks, the versions, the reference — were
// swallowed and stayed swallowed, which is the whole argument for claiming rather than
// swallowing.
// The find box is a text box and takes the letters like any other, so it stands inside the
// typing scope and states only what it does differently: Escape lets the narrowing go
// rather than merely leaving the box, and Enter walks into the list the words just found.
// Nearer than TYPING in the stack, which is the whole of how it shadows that scope's own
// Escape — no listener of its own, no preventDefault written by hand.
keys(
  findInput,
  "In the find box",
  [
    {
      id: "thread.find.close",
      keys: ["Escape"],
      does: () =>
        narrowed() ? "Show every thread again" : "Leave the box, keeping what is typed",
      line: () => (narrowed() ? "show all" : "back to list"),
      // One press, one step, like every other Escape in the register: the narrowing goes
      // first and the box is left on the next press, rather than both at once.
      run: () => {
        if (widen()) return;
        findInput.blur();
        threadsBox.focus();
      },
    },
    {
      id: "thread.find.first",
      keys: ["Enter"],
      does: "Go to the first thread found",
      line: "first found",
      when: hasThreads,
      run: () => stepThread(1),
    },
  ],
  pagePresented,
);

const TYPING = {
  title: "In a text box",
  at: () => takesLetters(focused()),
  claims: TEXT_ENTRY,
  rows: [
    {
      id: "text.leave",
      keys: ["Escape"],
      does: "Leave the box, keeping what is typed",
      line: () => backFromBox()?.line ?? "back to list",
      // The conversation the box belongs to, or the panel's list where it is the
      // chrome's own box. A page textarea that is neither leaves the row dead and the
      // page's rung standing, which is the honest answer: nothing there to go back to.
      when: () => Boolean(backFromBox()) || inTheBox(),
      run: () => {
        const back = backFromBox();
        document.activeElement.blur();
        (back?.target ?? threadsBox).focus();
      },
    },
  ],
};

// The panel's own keys. What a press acts on is whose scope it belongs to: the page holds
// the presses whose subject is the page — `t`/`T` and `a`/`A` walk its open sets, and
// `g` opens its destinations — while a surface holds presses for its own contents. `w`
// narrows this list and `/` searches it, and a list the reader is not looking at is
// neither a thing to narrow nor a thing to search. At page scope they were two bare
// letters spent on a panel that might be shut, promised by the key line over prose the
// presses said nothing about.
//
// `c` is the one row here whose subject is not this list: it carries the page's contextual
// comment intent into the general box. The row's own guard carries where it stands down,
// so the page's nearer selection, item, or conversation answer wins there.
//
// Standing in the panel is where its focus is, not merely that it is open: the Threads
// button is the banner's, so opening by pointer leaves the reader outside, and `g T`, `t`,
// Tab or a click on a thread is what puts them in. The same line `THREAD` draws one step
// further in, which is why that scope sits before this one and its rows shadow these.
// Whether the page has this scope at all is not a question the log answers: every page
// has a thread panel, and its general box stands and takes words from the first paint —
// the offline banner says a comment will not send, not that there is nowhere to write it.
// What the log answers is whether the waiting filter is useful, which is `w`'s own
// condition and is now said on that row. The find box needs no such condition: searching
// an empty list yields no matches, and its visible control remains available.

const PANEL = {
  title: "In the thread panel",
  at: inPanel,
  rows: [
    {
      id: "thread.waiting.toggle",
      // `w` for the words the control says. It is the phrase the page already uses for
      // the same question asked of its widgets (a/A), asked here of the conversation —
      // so the reader learns one idea and reaches it two ways rather than learning
      // "needs you" beside it.
      //
      // A narrowing is a mode, so the row states it as one: the sentence and line turn
      // on whether it stands, and a successful keyboard activation pushes its return
      // frame. The scene rung remains only for pointer activation. Dead while there is nothing waiting
      // and nothing hidden, which is the same fact that greys the control — and dead
      // before the log arrives, which is the one part of that the standing narrowing
      // cannot say for itself: `needsYou` is a flag the reader set, and it outlives a
      // list that has gone back to empty. `/` needs no such clause, `renderPanel`
      // emptying `threadList` at every phase but ready.
      keys: ["w"],
      does: () =>
        conversationRuntime.needsYou
          ? "Show every thread again"
          : "Show only the threads waiting on you",
      line: () => (conversationRuntime.needsYou ? "all threads" : "waiting on you"),
      also: needsBtn,
      when: () =>
        runtime.statePhase === "ready" &&
        (conversationRuntime.needsYou ||
          conversationRuntime.threadList.some(awaitsReader)),
      returnFrame: () => ({
        active: () => panelIsOpen() && conversationRuntime.needsYou,
        close: () => needsBtn.click(),
        does: "Show every thread again",
        line: "show all",
      }),
      run: () => needsBtn.click(),
    },
    {
      id: "thread.find",
      // `/` is what every list with a search field takes it with, and the one letter a
      // text box does not shadow: the typing scope claims what types a character, so the
      // press only ever reaches here from the list rather than from a box in it.
      keys: ["/"],
      does: "Find in the threads",
      line: "find",
      also: findInput,
      returnFrame: () => ({
        active: () => panelIsOpen() && (findInput === documentFocused() || narrowed()),
        close: () => {
          if (widen()) return false;
          findInput.blur();
        },
        does: () =>
          narrowed() ? "Show every thread again" : "Leave the thread search",
        line: () => (narrowed() ? "show all" : "back to threads"),
      }),
      run: () => {
        findInput.focus();
        findInput.select();
      },
    },
    // Last, because `w` and `/` are the list's own operations while this is a contextual
    // route through it. The latest return frame already owns the first key-line slot; the
    // remaining one should say what the list can do. The page-comment box advertises `c`
    // in its own placeholder, and the complete reference retains this row.
    PANEL_SAY,
  ],
};

// A focused thread: the reply and the resolve are this scope's, not the page's. They said
// "On a focused thread" in their own sentences and were live over the whole page, so a
// reader who had focused nothing was offered a press that no-opped — the old page-step bug from the
// other side. The reopen button tells the two states apart; absent a focused thread, the
// reference describes the open state readers first meet rather than inventing a third one.
const THREAD = {
  title: "On a focused thread",
  when: () => conversationRuntime.threadList.length > 0,
  at: () => Boolean(focusedThread()),
  rows: [
    {
      id: "thread.primary",
      keys: ["Enter"],
      does: () =>
        focusedThread()?.querySelector(":scope > .lf-thread-actions > .lf-reopen")
          ? "Reopen it"
          : "Write a reply",
      line: () =>
        focusedThread()?.querySelector(":scope > .lf-thread-actions > .lf-reopen")
          ? "reopen"
          : "reply",
      when: () =>
        Boolean(focusedThread()?.querySelector(":scope > .lf-compose")) ||
        Boolean(
          focusedThread()?.querySelector(
            ':scope > .lf-thread-actions > .lf-reopen:not(:disabled, [aria-disabled="true"])',
          ),
        ),
      returnFrame: () => {
        const thread = focusedThread();
        const box = thread && conversationInput(thread);
        return box ? boxReturnFrame(thread, box) : null;
      },
      // Find the thread's own compose row rather than the first textarea: a message may
      // contain a widget with an editor of its own before the reply box in DOM order.
      run: () => {
        const thread = focusedThread();
        const reopen = thread.querySelector(":scope > .lf-thread-actions > .lf-reopen");
        if (reopen) reopen.click();
        else landInThreadReply(thread);
      },
    },
    {
      id: "thread.resolution.toggle",
      // `x` and not `r`, though resolve is the word it does: the press beside it in this
      // same scope is the reply, and a reader meeting `r` on the line reads "reply" before
      // they read "resolve". A key spelling its own word is the wrong key when the
      // neighbouring press owns the word it would be read as. `x` is the letter a thing
      // closes under, and no other scope had claimed it.
      keys: ["x"],
      does: () =>
        focusedThread()?.querySelector(":scope > .lf-thread-actions > .lf-reopen")
          ? "Reopen it"
          : "Resolve it",
      line: () =>
        focusedThread()?.querySelector(":scope > .lf-thread-actions > .lf-reopen")
          ? "reopen"
          : "resolve",
      // Through the thread's own button, so keyboard and mouse are one behaviour — the
      // focus landing included. Both states offer exactly one resolution button, and the
      // row's liveness names that reachable capability instead of hiding a no-op in run.
      when: () =>
        Boolean(
          focusedThread()?.querySelector(
            ':scope > .lf-compose > .lf-thread-actions > .lf-resolve:not(:disabled, [aria-disabled="true"]), :scope > .lf-thread-actions > .lf-reopen:not(:disabled, [aria-disabled="true"])',
          ),
        ),
      run: () =>
        focusedThread()
          .querySelector(
            ':scope > .lf-compose > .lf-thread-actions > .lf-resolve:not(:disabled, [aria-disabled="true"]), :scope > .lf-thread-actions > .lf-reopen:not(:disabled, [aria-disabled="true"])',
          )
          .click(),
    },
  ],
};

// Where the reader is standing, when what they are standing on is one of the page's own
// parts rather than a widget's own declaration. The control scope below cannot cover
// these: it works a span `offer` made pressable, where these arrive with platform keys
// already bound. Enter follows an <a> while Space scrolls the page out from under it;
// both work a disclosure. `g f` puts the reader on a disclosure, and Tab can put them on
// either. Until a scope existed the line went quiet at exactly the moment they arrived,
// with the press that finishes the motion unnamed.
//
// The page's parts and not every one, which is the reading the addresses take as well:
// the chrome's own links are the leaves tray's and its resolved comments are the panel's,
// and both of those declare what they answer themselves. Asked of the document at large,
// "On a link" was had by every page — a machine with one neighbour has a tray full of
// links — so the reference named it wherever the reader went, on pages holding none to
// stand on. One derivation and not a copy apiece: what a scope here asks is the same pair
// of questions of a different selector, and the day the chrome rule changes is the day a
// second copy of it is wrong.
const standingOn = (title, sel, rows) => ({
  title,
  at: () => {
    const el = focused();
    return Boolean(el?.matches?.(sel)) && !inChrome(el);
  },
  // Across the declared shadow roots, where the addresses stop at the document: a row on
  // a staged disclosure names a key the browser does not answer, so a scope that could not
  // see one would leave the line promising a press nothing makes.
  when: () => pageQueryAll(sel).some((el) => !inChrome(el)),
  rows,
});

// A link's press is the browser's whole answer, so this row binds no `run`: it promises
// nothing the browser does not already do, and what it adds is the promise being on
// screen. Enter alone, Space under a link being the page's own scroll.
const LINK = standingOn("On a link", "a[href]", [
  { id: "link.follow", keys: ["Enter"], does: "Follow it", line: "follow" },
]);

// A disclosure, in either spelling the page has for one. The platform's <details> keeps
// the state on itself; a control a widget built out of a span says the same thing through
// ARIA's own attribute, which it already writes for the theme and the screen reader. Two
// vocabularies, one capability — and a reader standing on a settled group cannot see
// which of the two they are standing on, so a scope apiece would be the same press
// answered on one of them and not the other.
//
// ARIA's disclosure pattern and not the attribute at large. A combobox wears
// aria-expanded over a box words are typed into and a treeitem wears it in a walk of its
// own, and ← / → belong to the caret and the walk there. The pattern is the pair, so the
// selector asks for the button half too — which is what `offer` writes, and what a real
// <button> brings with it.
const DISCLOSURE_SELECTOR =
  'details > summary, :is(button, [role="button"])[aria-expanded]';
// Which way the disclosure at this element is standing: open, shut, or null where it is
// not a disclosure at all — which is a question asked from wherever the reader happens to
// be, the reference listing a scope the page has rather than the one they are in.
const disclosed = (el) =>
  !el?.matches?.(DISCLOSURE_SELECTOR)
    ? null
    : el.matches("details > summary")
      ? el.parentElement.open
      : el.getAttribute("aria-expanded") === "true";
// The keys that work the disclosure at `el`, which is the whole of what a row over one has
// to know — this scope's row, and a widget's own row re-wording the same press in its own
// terms. Named once here so the two cannot come to name different sets, which `lineRows`
// would resolve by printing the nearer one and dropping the other whole: a widget naming
// one key fewer takes the rest off the line, and one key more promises what nothing runs.
//
// The press is answered wherever the element stands, being the platform's on a <summary>
// or native button. The arrows are this scope's alone, so they
// are named where this scope reaches — the page, and not the runtime's own layer, where a
// diff inside a comment message keeps the platform's pair and nothing more.
//
// Only the direction that changes something, so every key a surface names is a key that
// works: over an open section the chip reads ←, over a shut one →. Both of them where the
// reader stands on no disclosure at all, because the question there is what this scope can
// do rather than what this press will do.
//
// Asked whether it is a disclosure before asked where it stands, which is the order the
// answers want anyway — what a scope can do is the same wherever the reader is — and the
// order module evaluation needs: `checked` reads every core row's bindings as the register
// is declared, which is before the passage runtime this file destructures `inChrome` from
// has been bound. Reversed, the layer takes down the first page it loads.
createDisclosure({ disclosed, inChrome });
const DISCLOSURE = standingOn("On a disclosure", DISCLOSURE_SELECTOR, [
  {
    id: "disclosure.toggle",
    keys: () => DISCLOSE(focused()),
    does: "Open or close it",
    // Read where it is painted rather than named once for both branches, the way a diff's
    // own file rows read theirs: what the press does is whichever way the disclosure is
    // standing, and a word fixed at declaration could only ever say one of them.
    line: () => (disclosed(focused()) ? "close" : "open"),
    // Through the element's own click, so keyboard and pointer are one behaviour: a
    // <summary>'s click is the toggle the browser was already making, and a widget's
    // control runs the handler its own pointer press runs. Enter and Space are the
    // runtime's here rather than the platform's, because a row owns its whole binding set
    // and the dispatcher takes the key before the platform sees it. One toggle answers all
    // three: the arrow bound is the one that changes this disclosure, so a press cannot
    // mean anything else.
    run: () => focused().click(),
  },
]);

// Design mode: a page mode the reader stands in for a batch of remarks about the layer.
// Its Escape is the innermost rung while it stands — a composer opened in it closes
// first (COMPOSER is nearer), then the mode, then the panels — and the press it is made
// of is not a key at all, so that row binds nothing and says nothing on the line, the
// way the ⌥ aim's row does.
const DESIGN = {
  title: "In design mode",
  at: () => designOn,
  rows: [
    {
      id: "design.comment",
      keys: [],
      label: "click",
      does: "Comment on what the click lands on — a widget, a control, the chrome; prose still selects",
    },
    {
      // Both keys, on one row: i is the toggle and Escape the mode's own rung, and two
      // chips reading "leave design" said one thing twice on the line.
      id: "design.leave",
      keys: ["Escape", "i"],
      does: "Leave design mode",
      line: "leave design",
      run: () => setDesign(false),
    },
  ],
};

// The page itself. Table order is the line's priority order — a total order every row has
// already, rather than a field one can forget — so the first live rows are the short hints.
// Escape is the default promotion over this order, because the way out of a current scene
// must survive beside its way in. A row can waive only that promotion when two local actions
// on the current state belong together; the binding remains live and stays in the reference.
// Named for the same kind of reason: a mode standing over the page suspends the page's keys
// and keeps this one (`allButTheReference`), and the claim reads the binding off the row
// rather than spelling "?" beside it — a fact about a binding written where the binding
// cannot correct it is the register's own oldest bug. Its place in the table is nominal:
// renderLine gives it the permanent More control instead of spending a hint slot on it.
const REFERENCE = {
  id: "reference.open",
  runFromReference: false,
  keys: ["?"],
  does: () =>
    keyline?.expanded ? "The complete keyboard reference" : "More keyboard shortcuts",
  line: () => (keyline?.expanded ? "all shortcuts" : "more"),
  also: keylineMore,
  run: () => keylineMore.click(),
};
const PAGE = {
  rows: [
    actionRow,
    // The two presses that say something back, first, because the resting line is the
    // only sentence a reader who has not pressed anything yet will read. It used to open
    // `/ search page · s select item`, which are both ways of *finding* a thing to act on
    // and so named no act at all: a page whose whole point is the remark it carries never
    // said the word "comment" until the reader pressed `?`. The captured-target case had
    // already worked this out for itself — `s` steps off the line and BACK_OUT gives up
    // its promotion so that `c` and `r` own the two slots on the thing just chosen — and
    // this is that same ranking with nothing chosen. Finding is still a press away;
    // saying something was three.
    {
      id: "comment.create",
      keys: ["c"],
      // One key, four destinations, and the surfaces name the one in front of the reader:
      // a live selection, the item a click raised the 💬 on, the box belonging to whatever
      // the reader is standing in, or — when none of those is in hand — the page itself.
      // "Comment" covered them all and so promised none of them. All four enter their
      // actual box; the panel's contextual c reaches the same general box from its list.
      does: () => commentDestination().does,
      line: () => commentDestination().line,
      // A selection made before the anchor pass has run can't be quoted yet, and
      // commenting on the page instead is not what the reader asked for — so the press
      // waits, and the row's own liveness is where that is said rather than a refusal
      // inside run that no surface can see.
      when: () => anchoringReady || !pageSelection(),
      returnFrame: () => {
        updateFab();
        return commentDestination().returnFrame?.() ?? null;
      },
      run: commentKey,
    },
    {
      // `r` opens the list on the target the reader has already named: the current
      // selection, item, or agent reply. Digits are optional accelerators in the
      // registry's declared order.
      id: "reaction.open",
      keys: ["r"],
      does: () =>
        `Open reactions — ${reactionTokens()
          .slice(0, 9)
          .map(([name, entry]) => `${entry.glyph} ${name}`)
          .join(
            ", ",
          )} — for the selection, the item you are standing on, or the reply you are reading`,
      line: "react",
      when: () => reactionTokens().length > 0 && (anchoringReady || !pageSelection()),
      run: () => {
        // Selection capture normally follows the pointer gesture in its queued turn.
        // A fast `r` may arrive before that turn even though the native Selection is
        // already complete. Capture it now so the command cannot advertise reaction
        // digits while opening no corresponding choices.
        if (pageSelection() && !fabAnchorAt()) updateFab();
        setReact(true);
      },
    },
    // Then the two ways of choosing what to say it about. They are one press from the
    // shelf and named in full by the reference, which is where a capability the reader
    // has not asked for yet belongs.
    PAGE_SEARCH,
    {
      id: "selection.open",
      keys: ["s"],
      does: "Select a visible item by hint",
      line: "select item",
      // Once a target is in hand, its actions own the two short-line slots. Escape clears
      // it, while this projection-only gate leaves s live to replace the target and keeps
      // that capability in the complete reference.
      lineWhen: () => !hasCapturedTarget(),
      when: () => anchoringReady,
      run: startSelecting,
    },
    {
      id: "thread.walk",
      // A walk's letter names its category; Shift reverses it. The two existing
      // page categories therefore use the same compact, repeatable grammar.
      keys: ["t", "Shift+t"],
      routes: [
        { id: "thread.next", binding: "t", does: "Next open thread" },
        { id: "thread.previous", binding: "Shift+t", does: "Previous open thread" },
      ],
      does: "Next / previous open thread",
      line: "threads",
      when: hasThreads,
      repeat: true,
      run: (binding) => stepThread(binding === "t" ? 1 : -1),
    },
    {
      id: "decision.walk",
      keys: ["a", "Shift+a"],
      routes: [
        {
          id: "decision.next",
          binding: "a",
          does: "Next ask this page is waiting on you for",
        },
        {
          id: "decision.previous",
          binding: "Shift+a",
          does: "Previous ask this page is waiting on you for",
        },
      ],
      does: "Next / previous ask this page is waiting on you for",
      line: "asks",
      when: () => openDecisions().length > 0,
      repeat: true,
      run: (binding) => stepDecision(binding === "a" ? 1 : -1),
    },
    {
      id: "page.move",
      keys: ["d", "u"],
      routes: [
        {
          id: "page.down",
          binding: "d",
          does: "Move 60% of a page down",
          line: "page down",
        },
        {
          id: "page.up",
          binding: "u",
          does: "Move 60% of a page up",
          line: "page up",
        },
      ],
      does: "Move 60% of a page down or up",
      line: "page down / up",
      // An ordinary row, ranked where it stands. It was the one persistent declaration in
      // the runtime, which spent a third of the resting line restating what every reader
      // already does with a wheel, a trackpad or the space bar — and spent it on every
      // page, in every scope, beside whatever the reader was actually doing. Scrolling is
      // the one capability no page has to advertise. The shelf and the reference still
      // name it, which is where a key the reader has not asked after belongs.
      repeat: true,
      run: (binding) => stepReading(binding === "d" ? 0.6 : -0.6, "page"),
    },
    {
      id: "scroll.move",
      keys: ["j", "k"],
      routes: [
        {
          id: "scroll.down",
          binding: "j",
          does: "Scroll down a little",
          line: "scroll down",
        },
        {
          id: "scroll.up",
          binding: "k",
          does: "Scroll up a little",
          line: "scroll up",
        },
      ],
      does: "Scroll down or up a little",
      line: "scroll down / up",
      repeat: true,
      run: (binding) => stepReading(binding === "j" ? 60 : -60, "pixel"),
    },
    {
      // The last thing the reader did to this page, put back. Its own key rather
      // than the platform's ⌘Z, which belongs to the box a reader is typing in and
      // is taken by the browser everywhere else: this is a page-level press like
      // every other letter here, and the typing scope keeps it off a composer's
      // words by claiming its letters. The word is "undo" and never the verb it is
      // about to state — `move` is one widget's word, and a line that said it would
      // be naming a member where the mechanism is what holds.
      id: "history.undo",
      keys: ["z"],
      does: () => undoSentence(),
      line: "undo",
      // Dead while the page holds a gesture no log read accounts for, this one's
      // own send included: the walk would name the gesture *before* the one they
      // just made and take that back instead. The line drops the chip for as long
      // as that is true rather than promising a press that would undo the wrong thing.
      when: () => !unaccountedGesture() && Boolean(undoable()),
      run: undoLast,
    },
    // Above the page's furniture, because it is the way out of wherever the reader is
    // standing and they are standing somewhere far more often than a panel is open: it
    // ranks with the presses that act on where they are, not with the versions and the
    // modes. Below it, the line drops chips a window at a time, and this is the one that
    // says how to undo the press that put them there.
    BACK_OUT,
    // And the chord below it, having sat among the walks and pushed it off the end of a
    // 1280px line — the reader standing on a decision, which is the one place the way out was
    // written for. What it costs to yield is small and what it buys is not: `g` opens a
    // door to three lists the walks above already reach one at a time, so a narrow window
    // hides a second way to somewhere; the press it was crowding out is the only way back
    // from where a press had just put the reader.
    GOTO,
    {
      // The way in; the mode's own scope takes the letter back out (DESIGN), nearer
      // than this row, so while it stands this one is shadowed off the line.
      id: "design.enter",
      keys: ["i"],
      does: "Design mode: comment on the layer — a widget, a control, the chrome — rather than the page",
      line: "design mode",
      run: () => setDesign(true),
    },
    REFERENCE,
    // Reference: a real key the browser owns, and one gesture that is not a key at all.
    // Neither says a word for the line, so neither is ever promised as the next press —
    // one rule where the three exemptions this replaced were three.
    {
      id: "browser.caret",
      keys: ["F7"],
      does: "Caret browsing (the browser's): select text by keyboard, then c",
    },
    AIM,
  ],
};

// The stack, innermost first, and the whole of what the runtime says about the order. The
// Element scopes splice in where ELEMENTS stands. RETURN follows that placeholder in this
// canonical list; the dispatcher places it at the dynamic boundary after the exact control
// and before generic typing and ancestor rows, so an input can clear its own query before
// leaving while a plain composer returns in the one Escape its entry earned. Every reading
// starts from this stack: the dispatcher and line walk it inward, and the reference walks it
// backwards.
//
// Three lists said this, and the third was the reference's own, in its own order, holding the
// same eight scopes by hand. A mode left out of that one was a mode the reference never named
// — which is not a hypothetical, being the failure it had already made when core's modes were
// not declared the way a widget's are. A list that must be edited in step with another is the
// same bug waiting on the next mode.
const ELEMENTS = Symbol("the scopes of the focused element");
const returnStack = createReturnStack({ focused, paintHere, readingBlock });
const { RETURN } = returnStack;
const SCOPES = [
  HELP,
  SHORTCUT_SHELF,
  PAGE_MAP,
  GO,
  REACT,
  SELECT,
  ELEMENTS,
  RETURN,
  VERSIONS,
  COMPOSER,
  TYPING,
  THREAD,
  PANEL,
  LINK,
  DISCLOSURE,
  DESIGN,
  PAGE,
];
const CORE = SCOPES.filter((scope) => scope !== ELEMENTS);
// Core's scopes are checked at module load by the rule every widget's are checked by at
// upgrade, so a row here that presses with nothing to say for itself takes down the layer on
// the first page rather than going quiet on every one.
for (const scope of CORE) checked(scope.rows, scope.title ?? "the page's own keys");
// A control the keyboard also reaches names its shortcut from the row. `also` is where a
// row says which control it duplicates; its projection follows liveness too, so a disabled
// decision does not advertise a shortcut the dispatcher has withdrawn. The latest-version
// chip's route spans two rows, so it is composed from both.
function paintCoreControls() {
  const returningToMore = Boolean(keyline?.expanded);
  helpClose.textContent = returningToMore ? "Back to more shortcuts" : "Close";
  helpClose.dataset.lfKeyTitle = returningToMore
    ? "Back to more shortcuts"
    : "Close keyboard reference";
  helpClose.setAttribute(
    "aria-label",
    returningToMore ? "Back to more shortcuts" : "Close keyboard reference",
  );
  const controlShortcut = (scope, row) =>
    [...(word(scope.chordPrefix ?? scope.chord) ?? []), labelOf(row)]
      .filter(Boolean)
      .join(" ");
  for (const scope of CORE)
    for (const row of scope.rows)
      if (row.also) {
        if (!("lfKeyTitle" in row.also.dataset))
          row.also.dataset.lfKeyTitle = row.also.title;
        const active = live(row) && bindings(row).length > 0;
        row.also.title =
          row.also.dataset.lfKeyTitle +
          (active ? ` (${controlShortcut(scope, row)})` : "");
        // aria-keyshortcuts has no syntax for sequential shortcuts: its spaces separate
        // alternatives. The complete chord remains in the visible hint and accessible
        // keyboard reference instead of claiming its final press works alone.
        if (active && !scope.chord)
          row.also.setAttribute("aria-keyshortcuts", ariaShortcuts([row], false));
        else row.also.removeAttribute("aria-keyshortcuts");
      }
  const referenceBound = bindings(REFERENCE).length > 0;
  keylineMoreKey.hidden = !referenceBound;
  const shelf = referenceBound && Boolean(keyline?.expanded) && !reference.open;
  keylineMoreText.textContent = shelf ? "all shortcuts" : "more";
  keylineMore.title = shelf ? "All keyboard shortcuts" : "More keyboard shortcuts";
  keylineMore.setAttribute("aria-expanded", String(shelf));
  keylineMore.setAttribute(
    "aria-label",
    referenceBound ? (shelf ? "? all shortcuts" : "? more") : "More keyboard shortcuts",
  );
  const latestBound = bindings(CHOOSER).length && bindings(NEWEST).length;
  latestChip.title =
    latestChip.dataset.lfKeyTitle +
    (latestBound ? ` (${controlShortcut(GO, CHOOSER)} ${labelOf(NEWEST)})` : "");
}

const { availableCommands, executeCommand, readerIn, shadow, stack } = createDispatch({
  beforeCommand: (row) => {
    if (
      keyline?.expanded &&
      !reference.open &&
      row !== REFERENCE &&
      row !== LESS_SHORTCUTS
    )
      keyline.less({ silent: true });
  },
  claimsEsc,
  ELEMENTS,
  focused,
  isChordArmed,
  paintHere,
  REACT,
  recoveredLabelFocus,
  RETURN,
  returnStack,
  SCOPES,
  scopesFor,
  setChord,
  setReact,
  takesLetters,
  TYPING,
});
decisionActionReachable = () => availableCommands().has(actionRow.id);
const reference = createReference({
  byCommand,
  characterShortcutsOn: () => characterShortcutsOn,
  availableCommands,
  el,
  elementScopes,
  ELEMENTS,
  EVERYTHING,
  executeCommand,
  focused,
  helpClose,
  helpEl,
  merge,
  pageSelection,
  paintHere,
  pruneScopedElements,
  reachScrollers,
  readerIn,
  readingBlock,
  scopeRefs,
  SCOPES,
  setCharacterShortcuts: (on) => {
    const before = characterShortcutsOn;
    characterShortcutsOn = on;
    setChord(false);
    setReact(false);
    try {
      paintKeys();
      syncGeneral();
    } catch (error) {
      characterShortcutsOn = before;
      paintKeys();
      syncGeneral();
      throw error;
    }
    readerStore.set(CHARACTER_SHORTCUTS_KEY, on ? null : "0");
  },
  scopesFor,
});
// A disclosure opening or closing changes what the next press does, and no writer in this
// file reports it: the word on a summary's row is read off `open`, and the reader standing
// there has moved nothing else. Left unpainted, the line said "close" for the three seconds
// until a poll happened past — a key line stale about the press under the reader's finger,
// where every gate reads it as eventually right.
//
// Watched as state rather than heard as an event, because the event only covers one of the
// two spellings and only in one of the two trees. `toggle` is not composed, so a <details>
// a widget staged in a shadow root fires nothing a document listener hears — measured: a
// diff's file rows sat stale until the poll for as long as this listener has existed. And a
// control keeping its state in aria-expanded fires nothing anywhere. Both keep that state
// in an attribute, so one observer over the two attributes answers for both, and
// `shadowStage` hands it each root it attaches. It is the document's rather than each
// element's for the reason the listener before it was: the disclosures on a page are
// whatever its author wrote and whatever its widgets built, which is not a list this file
// can hold.
watchDisclosures(document);

keyline = createKeyline({
  announce,
  backRow: LESS_SHORTCUTS,
  el,
  keylineEl,
  keylineMore,
  paintHere,
  reference,
  referenceRow: REFERENCE,
  shadow,
  stack,
});
const { renderLine } = keyline;
const { droppedAt, presented } = createPresence();

const { loadIcon, renderStatus, sayLine, toneFor } = createBanner({
  agentName,
  ago,
  announce,
  dot,
  el,
  presented,
  statusText,
  notice,
});

/** The reader's hand on a widget, in the layer's own word: a drag the log has not taken
 * yet. The class is half of `unaccountedGesture` below, so taking it up or putting it
 * down moves core's `z` row — a row no widget declares, and therefore the one no widget
 * would think to repaint. Both edges of a pointer drag went unpainted for exactly that
 * reason, and on a quiet board the line went on offering `undo` for as long as the
 * reader held the card, over a press the dispatcher was already refusing. So the paint
 * is owed here, where the class is written, rather than by whoever remembers.
 *
 * Coalesced to a frame like every paint, which is what lets it stand for everything else
 * the same gesture moved: the widget's own rows where the grab is a press on an
 * already-focused grip and no focus event fires, and a send the drop states after this
 * returns — so a drop that sends still reads as a gesture the log has not taken.
 */
// A gesture of the reader's that the page has not accounted for in a log read, asked of
// the layer's own signals rather than of any widget by name: a drag wears .lf-dragging
// (dragging, above), every unresolved browser event is in the outbox, and an undo
// in flight is its own — it is tracked separately because the walk itself cannot be
// offered again while its event is being answered.
// Two questions want the answer,
// which is why it has a name of its own: navigating away would destroy such a gesture,
// and the undo walk reads the log to find the last thing the reader did, so it cannot
// answer while the page is holding one. Its own press included — a second `z` landing
// inside the first one's trip would read the log from before it and withdraw the same
// gesture again, which the door refuses and the reader hears as a page that couldn't
// reach its server.
const unaccountedGesture = () =>
  runtime.undoing ||
  outbox.length > 0 ||
  Boolean(document.querySelector(".lf-dragging"));
// The user is mid-something navigation would destroy: the above, and the words they
// have typed — a composition surface is a focused textarea holding words or a draft, or
// a widget-built one (data-lf-offer) even empty, because deleting everything is still an
// edit. A reply the runtime merely opened and focused is the exception: that landing has
// no reader-authored draft to preserve and therefore does not stop a live page following.
const midComposition = () => {
  const active = focused();
  const replyDraft = conversationRuntime?.replyBoxHasDraft(active) ?? null;
  return (
    composerOpen ||
    isSelecting() ||
    Boolean(fabAnchorAt()) ||
    unaccountedGesture() ||
    (active?.tagName === "TEXTAREA" &&
      (active.value !== "" ||
        replyDraft === true ||
        (replyDraft === null && active.hasAttribute("data-lf-offer"))))
  );
};
// ---------- reading ----------
// Rendering version V means making its DOM equal the log's desired projection.
// Each `(owner widget, unit, facet)` keeps its last surviving action or report, with
// a reader action outranking provisional agent news on the same coordinate. Widgets state
// those winners through an absolute applyAction(action, detail); when several units
// share one ordered container, their winners are applied together in log order.
//
// Absolute is what makes projection converge. Reader actions outrank provisional agent
// reports on the same coordinate; winners on different coordinates are applied in their
// original order so sibling position units compose. Recorded outbox actions form an
// optimistic overlay after the log until accepted or definitively refused. A refusal
// removes only its overlay, then the same projector derives the widget from authored
// records, authoritative winners, and every surviving local action. Live drags and
// widgets that return false defer that correction without advancing its commit.
//
// The log outranks the markup, and that is the whole rule: authored state is the
// initial condition, never a later correction, so nothing a version does or
// omits can un-make a decision by itself. The repo's own CLAUDE.md carries why,
// and what it cost to learn. Replay used to stop at the handoff cursor, on the
// premise that a version written after the agent saw an action encoded it — a
// premise nothing checked, and acknowledgement is not assent. Only a version can say
// what the agent did with an action, and saying it is `version check`'s business now
// (restatement_errors), not something inferred here from silence.
let conversationRuntime;
let anchorRuntime;

function buildThreads(...args) {
  return conversationRuntime.buildThreads(...args);
}
function loadMarked(...args) {
  return conversationRuntime.loadMarked(...args);
}
function anchorLabel(...args) {
  return conversationRuntime.anchorLabel(...args);
}
function openThreads(...args) {
  return conversationRuntime.openThreads(...args);
}
function narrowed(...args) {
  return conversationRuntime.narrowed(...args);
}
function awaitsReader(...args) {
  return conversationRuntime.awaitsReader(...args);
}
function setChildren(...args) {
  return conversationRuntime.setChildren(...args);
}
function paintAcknowledgments(...args) {
  return conversationRuntime.paintAcknowledgments(...args);
}
function widen(...args) {
  return conversationRuntime.widen(...args);
}
function paintThreadQuotes(...args) {
  return conversationRuntime.paintThreadQuotes(...args);
}
function renderPanel(...args) {
  return conversationRuntime.renderPanel(...args);
}
function showThread(...args) {
  return conversationRuntime.showThread(...args);
}

function sectionOf(...args) {
  return anchorRuntime.sectionOf(...args);
}
function aimTargetAt(...args) {
  return anchorRuntime.aimTargetAt(...args);
}
function aimTargets(...args) {
  return anchorRuntime.aimTargets(...args);
}
function isItem(...args) {
  return anchorRuntime.isItem(...args);
}
function itemAt(...args) {
  return anchorRuntime.itemAt(...args);
}
function itemSays(...args) {
  return anchorRuntime.itemSays(...args);
}
function visualPartLabel(...args) {
  return anchorRuntime.visualPartLabel(...args);
}
function visualAt(...args) {
  return anchorRuntime.visualAt(...args);
}
function visualActionAnchor(...args) {
  return anchorRuntime.visualActionAnchor(...args);
}
function resolveAnchor(...args) {
  return anchorRuntime.resolveAnchor(...args);
}
function refreshAim(...args) {
  return anchorRuntime.refreshAim(...args);
}
function paintAnchors(...args) {
  return anchorRuntime.paintAnchors(...args);
}
function fragmentId(...args) {
  return anchorRuntime.fragmentId(...args);
}
function markAt(...args) {
  return anchorRuntime.markAt(...args);
}
function readableDestination(...args) {
  return anchorRuntime.readableDestination(...args);
}
function scrollToElement(...args) {
  return anchorRuntime.scrollToElement(...args);
}
function scrollToRange(...args) {
  return anchorRuntime.scrollToRange(...args);
}
function scrollToThread(...args) {
  return anchorRuntime.scrollToThread(...args);
}
function paintStanding(...args) {
  return anchorRuntime.paintStanding(...args);
}
function refreshHover(...args) {
  return anchorRuntime.refreshHover(...args);
}
function pageShifted(...args) {
  return anchorRuntime.pageShifted(...args);
}
function isMarked(...args) {
  return anchorRuntime.isMarked(...args);
}
function placedAt(...args) {
  return anchorRuntime.placedAt(...args);
}

const passageRuntime = createPassages({
  PAGE_PAINT_ATTRIBUTE,
  opaquePassageParts,
  opaquePassageRoots,
  pageShadowRoots,
  registry,
  widgetEntries,
});
const {
  settlementSlots,
  settledAway,
  DATUM,
  pageWords,
  layerPart,
  elementOver,
  under,
  authored,
  upFrom,
  containsAcross,
  closestAcross,
  elementById,
  elementFromPointAcross,
  pageQueryAll,
  pageRange,
  segmentsIn,
  blockAt,
  blockOf,
  COLLAPSE,
  quoteFrom,
  cut,
  rangeOf,
  holds,
  neighbourhood,
  pageText,
  spanIn,
  findQuote,
  findText,
  contextAround,
} = passageRuntime;

const runtimeProjection = createProjection(runtime, {
  unaccountedGesture,
  DECISION_ROW,
  COLLAPSE,
  MARKED_ANYWHERE,
  MARKED_IN_PAGE,
  PAGE_PAINT_ATTRIBUTE,
  PAGE_PAINT_ATTRIBUTES,
  agentName,
  answeredContext,
  authored,
  decisionEntry,
  containsAcross,
  dress,
  elementById,
  failSoft,
  focused,
  inChrome,
  isAwaiting,
  markDeclared,
  outbox,
  pagePresented,
  pageQueryAll,
  pageShifted,
  paintAnchors,
  paintKeys,
  paintAcknowledgments,
  post,
  projectedParent,
  quoteFrom,
  reachScrollers,
  rememberPassageParts,
  removeOutbox,
  renderQuiet,
  renderRetired,
  reportPageError,
  settling,
  settlementSlots,
  standOn,
  textNodesUnder,
  notice,
});
const {
  authoredDetails,
  authoredFacets,
  authoredMarkup,
  authoredParents,
  authoredStatements,
  authoredWidgets,
  captureAuthoredFacets,
  committedProjection,
  coordinateProjectionCommitted,
  domFacet,
  markSettled,
  matchesProjectedWhen,
  paintPending,
  projectedFacet,
  projectionFromView,
  projectionCommitted,
  rebuild,
  reconcileKnownState,
  reconcileState,
  releaseProjectedOutbox,
  rememberAuthoredMarkup,
  resetAuthoredPage,
  requirementMatches,
  stageOutboxAction,
  stateCoordinate,
  stateProjection,
  undoable,
  unitOf,
  withdraw,
} = runtimeProjection;

outboxRuntime = createOutbox(runtime, {
  RETRY_MS,
  elementById,
  newAttempt,
  paintKeys,
  postEvent,
  quoted,
  receiveState,
  reconcileKnownState,
  registry,
  releaseProjectedOutbox,
  requirementMatches,
  notice,
  stageOutboxAction,
  stateCoordinate,
  stateProjection,
  unitOf,
});

createRequests(runtime, {
  inChrome,
  post: outboxRuntime.post,
  quoted,
  registry,
});

conversationRuntime = createConversation({
  FOLD_MS,
  MARKED_ANYWHERE,
  agentName,
  ago,
  announce,
  designIsOn: () => designOn,
  captureAuthoredFacets,
  claimState: workClaimState,
  designName,
  droppedAt,
  el,
  elementById,
  findInput,
  focused,
  generalRow,
  highlightBlocks,
  inChrome,
  isMarked,
  itemSays,
  itemWord,
  keys,
  landTyping,
  layerPart,
  loadDraft,
  markDeclared,
  matchesWhen,
  mayLandTyping,
  mirrorDraft,
  motion,
  needsBtn,
  offer,
  pageParts,
  pageQueryAll,
  paintAnchors,
  paintHere,
  paintKeys,
  panelIsOpen,
  panelCovers,
  panelTitle,
  placedAt,
  pointerAt,
  post,
  PRESS,
  quietSince,
  waitingForPickupSince,
  reachScrollers,
  reachedForWords,
  reactDone: () => setReact(false),
  buildReactSurface,
  sendReaction,
  refreshHover,
  registry,
  rememberAuthoredMarkup,
  renderQuiet,
  renderSaid,
  reportPageError,
  runtime,
  saveDraft,
  scrollToElement,
  scrollToThread,
  sectionOf,
  sendDraft,
  setPanel,
  settling,
  tellDraft,
  threadsBox,
  toggleBtn,
  updateSequence,
  visualPartLabel,
  wireInput,
  withdraw,
});

updateRuntime = createUpdates(runtime, {
  closestAcross,
  coordinateProjectionCommitted,
  projectionCommitted,
  stateProjection,
});

anchorRuntime = createAnchors({
  DATUM,
  scrollBehavior,
  actionAnchor: fabAnchorAt,
  activateVisual,
  aimBox,
  aimIsOn,
  aimedItem,
  announce,
  anchorLabel,
  anchorsReady: () => anchoringReady,
  bareReaction: (t) => conversationRuntime.bareReaction(t),
  blockAt,
  buildThreads,
  closestAcross,
  composerAbout: () => pendingAbout,
  composerAnchor: () => pendingAnchor,
  composerIsOpen: () => composerOpen,
  composerQuote,
  containsAcross,
  cut,
  designIsOn: () => designOn,
  designName,
  designTarget,
  el,
  elementById,
  elementFromPointAcross,
  elementOver,
  findQuote,
  focusedThreadOf,
  glideTo,
  inChrome,
  inUi,
  inspectEl,
  offer,
  pageQueryAll,
  pageScroller,
  pageText,
  pageWords,
  paintThreadQuotes,
  panel,
  pointerAt,
  quoteFrom,
  queueLegend,
  rangeOf,
  refreshAction: refreshFab,
  registry,
  reveal,
  scrollerFor,
  setPanel,
  settledAway,
  tagsDeclaring,
  textNodesUnder,
  threadsBox,
  under,
  withdraw,
  worksWithoutTabStopSelector: WORKS_WITHOUT_TAB_STOP,
  runtimeOwnsScrollerStop,
});
const { ITEM, NOTE } = anchorRuntime;

livingMargin = createLivingMargin({
  ago,
  anchorLabel,
  acknowledgments: () => runtime.browser?.acknowledgments ?? [],
  announce,
  blockAt,
  chromeRoot,
  claimState: workClaimState,
  comparisonBase,
  comparisonChanges,
  compact: commentsEdge.over,
  closestAcross,
  currentRevision: () => runtime.currentRevision,
  designIsOn: () => designOn,
  droppedAt,
  el,
  elementById,
  focused,
  foldShelf,
  goToDecision,
  inChrome,
  itemSays,
  itemWord,
  keys,
  motion,
  offer,
  openDecisions,
  panelIsOpen: chromeLayout.panelIsOpen,
  paintKeys,
  placedAt,
  quietSince,
  renderMarginThread: conversationRuntime.renderMarginThread,
  says,
  scrollBehavior,
  scrollToElement,
  setPanel,
  showThread,
  stateProjection,
  threadPanel: panel,
  threads: () => conversationRuntime.threadList,
  updateSequence,
  versionBtn,
  waitingForPickupSince,
});

createConversationLanding({ scrollToThread });
createConversationBox({ post, renderPanel, notice, wireInput });

designRuntime = createDesign({
  ITEM,
  announce,
  banner,
  closePageMapPreview: livingMargin.closePreview,
  closestAcross,
  containsAcross,
  cut,
  el,
  inChrome,
  isItem,
  itemAt,
  itemWord,
  layerPart,
  legendRoot,
  marginTargetAt: (...args) => livingMargin.marginTargetAt(...args),
  openComposer,
  pageShifted,
  paintHere,
  refreshAim,
  showFab,
  shownRect,
  syncGeneral,
  tagsDeclaring,
  tabStore,
  worksSelector: WORKS,
});

stateApplication = createStateApplication({
  PAGE_PAINT_ATTRIBUTE,
  acceptData,
  accountOutbox,
  getSignoffDeclared: () => signoffDeclared,
  importWidgets,
  loadMarked,
  notifyDataSubscribers,
  observeServerNow,
  paintAnchors,
  paintApproval,
  paintAcknowledgments,
  panelIsOpen,
  prepareActivation,
  presented,
  reconcileState,
  refreshHover,
  replaceClaimState,
  renderOthers,
  renderPanel,
  renderStatus,
  renderVersions,
  runtime,
  sameLayer,
  sayLine,
  notice,
  settleAcceptedDrafts,
  stateSignoff,
  updateFab,
});

stateFeed = createStateFeed({
  RETRY_MS,
  SILENCE_MS,
  TICK_MS,
  notifyDataSubscribers,
  outbox,
  paintKeys,
  panelIsOpen,
  receiveState,
  reconcileKnownState,
  releaseProjectedOutbox,
  renderPanel,
  renderStatus,
  reportPageError,
  runtime,
  sameLayer,
});
// The server can build the authoritative page state while the browser loads and settles
// the registry's widget modules. Its answer stays buffered until startPage has captured
// the upgraded authored facets that replay starts from.
const initialStateRead = stateFeed.beginRead();

// ---------- restore ----------
// The general box and reply textareas repopulate as they render; a saved composer draft
// resurfaces visibly near the top so it isn't stranded in storage after a reload.
generalInput.value = loadDraft("general") ?? "";
// The widths first, so a panel or a tray put back open is open at the width the reader
// left it at rather than sliding to it afterwards.
commentsEdge.restore();
traysEdge.restore();
if (readerStore.get(PANEL_KEY) === "1") setPanel(true);
restoreTrays();
if (tabStore.get(DESIGN_KEY) === "1") setDesign(true, { spoken: false });
// Every way this page can come up that is not a first visit — the restores above, each
// named by the fact its store holds. The browser gate arrives once in each, because
// every other reading it takes is of a first visit: a fresh context holds nothing, so
// the panel is shut, no tray stands and the mode is off. That made the restores the one
// road onto the page with no gate on it, and a tray left standing came up as a
// ReferenceError rather than a page — on every load, for the only readers who had asked
// for it. Declared here rather than listed in the gate, because a list over there stops
// at the surfaces it was taught; this one is read on the day a surface starts
// remembering something. One stored fact each rather than the combinations of them: what
// a finding has to name is the restore that broke, and the geometry the combinations
// would add is measured on the first visit already.
createArrangements({
  CHARACTER_SHORTCUTS_KEY,
  DESIGN_KEY,
  PANEL_KEY,
  TRAY_KEY,
  commentsEdge,
  readerStore,
  tabStore,
  trayNames,
  traysEdge,
});
// A fresh arrival starts on the page, the same stable focus destination the Escape ladder
// uses after chrome. Root scrolling no longer depends on this handoff; focus ownership
// still does, since Space on a button presses it rather than scrolling the document.
//
// Here rather than in the start block below, which runs asynchronous upgrades while the
// authored document is already readable: body can name the page now, and stateful widget
// controls remain unavailable until presentPage crosses their semantic boundary.
letGo();
const { landArrival, savedView } = installArrival({
  fragmentId,
  ready: () => anchoringReady,
  scrollToElement,
  tabStore,
});
const savedComposer = selectionComposerRuntime.pendingComposer();

// ---------- start ----------
// One positive fact for the semantic-interaction boundary. Authored HTML already paints.
// Success has applied the log; an unavailable first poll has painted the offline status
// and deliberately lets the authored state accept durable interaction. A caught startup
// failure cannot make either promise, so controls and top-layer UI remain unavailable.
function presentPage() {
  if (document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented)) return;
  // Anchors are durable coordinates, so their pass and every route that can mint one
  // begin only after replay has reconciled the authored document. An early native text
  // selection can then resolve against the standing DOM, while a retired passage cannot
  // leave a composer carrying its authored words.
  anchoringReady = true;
  try {
    paintAnchors();
  } catch (error) {
    anchoringReady = false;
    throw error;
  }
  // The stamp is the promise that every semantic prerequisite above succeeded, not merely
  // that presentation was attempted. Keep it absent when a malformed widget makes the
  // anchor reading fail, so durable controls remain withheld on that partial page.
  document.body.setAttribute(PAGE_PAINT_ATTRIBUTE.presented, "1");
  updateFab();
  paintHere();
  landArrival();
  if (savedView && savedView.revision < runtime.currentRevision)
    notice(`Updated to ${runtime.currentLabel}`);
  if (savedComposer)
    openComposer(savedComposer.anchor, savedComposer.text, {
      suggest: Boolean(savedComposer.suggest),
      about: savedComposer.about ?? null,
    });
  // Repaint the remaining state-dependent chrome and controls in this same task. Replay
  // is already complete, so the presented attribute opens interaction on the state it names.
  restoreTray();
  showNews(othersBtn, leavesOffered());
  paintKeys();
  document.dispatchEvent(new Event("lf-actions"));
  paintApproval();
  promoteDeferredModals();
}

// Upgrades flush before the anchor pass and the view restore, so quotes and reading
// positions are re-found in the enhanced, replayed DOM rather than authored markup. An
// async function, never top-level await: boot first publishes every factory-built owner
// capability, then imports the behavior modules that consume the public facade.
async function startPage() {
  const [upgraded] = await Promise.all([
    upgradeWidgets(),
    // Alongside rather than after, and caught rather than fatal: the tab icon is not
    // what the page is for, so a layer missing it says so in the console and leaves the
    // rest working — the same bargain a widget module that fails to import makes. It is
    // still awaited here, because `version export` copies the page at the stamp below
    // and a mark that arrived after it would leave the copy's tab to chance.
    loadIcon().catch((err) => console.error(err)),
  ]);
  if (!upgraded) return;
  syncLayout();
  // Before the first poll's replay: the authored facets are the markup's
  // initial condition, and replay is about to overwrite them in the DOM.
  captureAuthoredFacets();
  buildBulkAnswers();
  syncDecisions();
  // Every widget has upgraded and every async one has settled, so the geometry and
  // the drawn SVG are final. `version export` copies the page at this moment and has no
  // other way to know it arrived: a load event fires before the modules run, and
  // networkidle only says a bundle finished downloading, not that it finished
  // drawing. The stamp says the document is done becoming itself.
  document.body.setAttribute(PAGE_PAINT_ATTRIBUTE.upgraded, "1");
  // Apply the buffered first read only after that stamp, preserving the two readiness
  // facts but presenting neither half on its own. The first completed read — state or
  // offline — is the presentation boundary; only after it settles do the heartbeat and
  // the stream begin, so a held first request cannot be overtaken by a second answer and
  // leave presentation waiting on the wrong call.
  stateFeed.start(presentPage, initialStateRead);
}

startPage().catch((error) => {
  // The boundary itself must fail visibly. Authored HTML remains readable, while the
  // status names the fault and the absent presented stamp keeps durable controls closed.
  reportPageError(`page failed to start: ${error?.message ?? error}`);
  renderStatus(error);
});
