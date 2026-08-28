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
 * Comment layer: talks to interact.py's server — listens on GET /api/news and reads
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
 * be pressed, so it goes, unless its own label is one of the page's words. Keying print
 * on .lf-ui instead cost a printed decision the only words that stated it (see
 * CLAUDE.md), because a pick mark is a control and a statement at once. render_version
 * compares the two media and reports what a page says on screen and not on paper.
 *
 * A control that says one of the page's words is never a <button>: Chrome starts no
 * pointer selection inside a form control, so its label would be unreachable however it is
 * marked. `offer` builds it as a selectable span carrying the control's role. The shared
 * scope wires button keys; a specialised control such as an option checkbox registers its
 * own keys.
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
 * It fetches each immutable revision file, upgrades and replays it behind a view-transition
 * boundary, then restores the reader's semantic landmark. Stamping that revision changes
 * its label without replacing the document. Picking a stamped version leaves the live page
 * for that immutable version URL, which stays pinned. One control on the bar holds all of
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
 * flashes its thread, the same answer a click on a page mark gets — and ends in the
 * composer it was sent from. A composer open on a selection keeps that passage marked
 * in the page until it closes, because focusing the box drops the browser's own
 * selection — and that mark is what says which passage the box is on, so the box only
 * quotes the passage back when this version no longer has one to mark. Whether the box
 * is up is state the stylesheet renders, never state read back off the stylesheet.
 *
 * Scrolling: the document scrolls body, not the viewport, and body's margin keeps its
 * box clear of the open panel. Two scroll regions side by side, each scrollbar drawn
 * inside its own region — a viewport-scrolled document would paint its scrollbar over
 * the panel, stacked on the panel's own. Reading position goes through pageScroller.
 * The page binds none of the browser's own scroll keys (Space, arrows, Home/End,
 * PageUp/Down); a focused control may, and a disclosure's arrows are core's own case of
 * that. d and u are the runtime's, stepping half the visible page at the browser's own
 * paging pace through whichever of the two regions the reader's own scrolling moves.
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
 * somewhere, three to come back, each giving up the press that earned it. A key that
 * opened a surface and then also stepped into something inside it puts two layers on for
 * one press, and Escape can only ever hand one of them back; the reader reads that as
 * Escape not undoing what the key did. `c` is the case that named the rule, having opened
 * the comment panel and landed in its general box together.
 *
 * Landing focus in what a press opened is arrival, not a second layer — a tray on its
 * first row, the versions menu on a version, the panel on its list. A second layer is a
 * box the surface does not shadow, and it earns a press of its own: `c` again, from the
 * panel this time. The layer that leaves between is where the surface's own keys can be
 * reached at all.
 *
 * One key sequence exists: g arms a mode in which a mnemonic names a panel or a
 * document list. `g c`, `g a`, and `g l` land in Comments, Asks, and All leaves.
 * A following digit names a member of a document list, so `g h 3` is the third
 * hyperlink; `g g` and `g G` are the page's top and bottom edges.
 * Arming shows the whole offer: everything addressable the reader can see wears its whole
 * address as a chip — `g h 1`, `g d 2` — with the keys already pressed dimmed, so the chip
 * states both which member this is and what is left to type. A letter then narrows the
 * chips to its own list. Any other key disarms the window and keeps its
 * ordinary meaning, which the dispatcher spells as disarming and walking the stack again.
 * Escape is a binding like any other, and the rung is whichever scope in reach binds it
 * first, so backing out is one layer per press and the promise cannot drift from the
 * press.
 *
 * What a key would do right now is state the user can read, not recall. The key line (one
 * quiet fixed line, bottom left) shows two hints: the first live row of the innermost
 * scope, then an available Escape or the next row. `? more` always opens the complete
 * reference, grouped by scope and searchable by key, action, or scope. The two hint chips
 * are aria-hidden: they are the eye's copy of facts spoken through placeholders and live
 * announcements; More is the accessible control leading to the full reference.
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
import { agentName, runtime } from "./runtime/context.js";
import { acceptData, notifyDataSubscribers } from "./runtime/data.js";
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
  askSource,
  createAskModel,
  openAsks,
} from "./runtime/asks/model.js";
import { createAskView } from "./runtime/asks/view.js";
import { createArrangements } from "./runtime/arrangements.js";
import { createAddress } from "./runtime/keyboard/address.js";
import { DISCLOSE, createDisclosure } from "./runtime/keyboard/disclosure.js";
import { createDispatch } from "./runtime/keyboard/dispatch.js";
import { createKeyline } from "./runtime/keyboard/keyline.js";
import { createReference } from "./runtime/keyboard/reference.js";
import { createScopes, keys, paintKeys, saying } from "./runtime/keyboard/scopes.js";
import { createLivingMargin } from "./runtime/living-margin.js";
import { createNavigation, scrollerFor } from "./runtime/navigation.js";
import { FOLD_MS, motion, reducedMotion, scrollBehavior } from "./runtime/motion.js";
import { announce, createNotifications, toast } from "./runtime/notifications.js";
import {
  actionAvailable,
  actionStands,
  createOutbox,
  outbox,
  sendAction,
} from "./runtime/outbox.js";
import { createRequests } from "./runtime/requests.js";
import { createDataProjection } from "./runtime/projection/data.js";
import { createProjection, shallowSigs, standingState } from "./runtime/projection.js";
import { createAnchors, itemWord } from "./runtime/anchors.js";
import { createBanner } from "./runtime/banner.js";
import { createBannerShelf } from "./runtime/banner-shelf.js";
import { createConversationBox } from "./runtime/conversation/box.js";
import {
  backFromConversation,
  createConversationLanding,
  heldConversation,
  landIn,
  SAY_BOX,
  standingConversation,
} from "./runtime/conversation/landing.js";
import { createConversation } from "./runtime/conversation/reconcile.js";
import {
  shownBand,
  shownBox,
  shownParts,
  shownRect,
  startsAt,
} from "./runtime/geometry.js";
import {
  createPassages,
  inChrome,
  inUi,
  renderRetired,
  says,
  textNodesUnder,
  uiInside,
  wrote,
} from "./runtime/passages.js";
import { createViewContinuity } from "./runtime/view-continuity.js";
import { textUnits } from "./runtime/text-alignment.js";
import {
  ago,
  createPresence,
  observeServerNow,
  quietSince,
} from "./runtime/presence.js";
import { createPointer } from "./runtime/pointer.js";
import { createReactions, paintReactionStanding } from "./runtime/reactions.js";
import { createStateApplication } from "./runtime/state-application.js";
import { createStateFeed } from "./runtime/state-feed.js";
import { createUpdates } from "./runtime/updates.js";
import {
  captureVersionRoots,
  createVersionActivation,
} from "./runtime/version-activation.js";
import { createVersionDiff } from "./runtime/version-diff.js";
import { createVersionNavigation } from "./runtime/version-navigation.js";
import { createWidgetLoader } from "./runtime/widget-loader.js";
import { failSoft, settle, settling } from "./runtime/widget-upgrade.js";
import {
  createMeasurements,
  installReachedForWordsGuard,
  offer,
  quoted,
  reachedForWords,
  relabel,
  reserve,
  WORKS,
  worksInside,
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
} from "./runtime/presentation.js";
import { reachScrollers } from "./runtime/reach.js";
import { pageScroller, scrollerGutter } from "./runtime/scrolling.js";
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

// Capture the authored share before the runtime paints roots or appends head chrome.
const versionRoots = captureVersionRoots();

const { promoteDeferredModals } = createDeferredModals({
  presentedAttribute: PAGE_PAINT_ATTRIBUTE.presented,
});
const vendoredLayerGeneration = "__LEAF_LAYER_GENERATION__";
const { postEvent, reportPageError, revealLayer, sameLayer } = createLayerClient({
  currentRevision: () => runtime.currentRevision,
  layerGeneration: vendoredLayerGeneration,
});
const { pointerAt } = createPointer();

createMeasurements({ shownBox });

installReachedForWordsGuard();

createDataProjection({
  paintAnchors,
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
//   keys  — the bindings it answers: "d", "Escape", "Mod+Enter", "Shift+a", " ".
//           A function where the set is the page's (an option group's 1–N).
//   routes— optional stable subcommands when those bindings mean different things. The
//           keyline keeps the compact row; the reference presents each route separately.
//   label — how it renders. Computed from `keys` unless the row is a chord whose second
//           half is another scope's row, and then built from that row rather than typed.
//   does  — the overlay's sentence.
//   line  — the line's word: a row carrying one stands on the key line, and a row that has
//           a `run` must carry one. That is the failure this register was built for, at
//           its smallest — `d` and `u` pressed, and no always-visible surface named them,
//           because the field was optional and its absence read exactly like a decision.
//           A row with no `run` may carry one all the same, since a press can be real and
//           immediate without being the runtime's: Enter opens the focused leaf because
//           the row is a link. What carries no word is reference, named in the "?"
//           overlay and never promised as the next press — F7, ⌥ click, a draft's
//           double-click.
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
// because `shadowStage` calls it, far above the key line it repaints for.
const disclosureWatch = new MutationObserver(() => paintHere());
const watchDisclosures = (root) =>
  disclosureWatch.observe(root, {
    subtree: true,
    attributeFilter: ["open", "aria-expanded"],
  });
createShadowStage(watchDisclosures);

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

// Where the reader is standing, painted: the ring on the ask they are in, the mark on the
// passage of the comment they are in, the focused box's hint, and the line saying what the
// next press does from there. One repaint, because it is one question — every reading is of
// the focus and the open-ask list, and every signal that moves either (a focus move, an
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
    // have: a poll that retires an ask moves the list under an armed window, and only the
    // panel's own render was calling the chip pass.
    paintAddresses();
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
  for (let a = el; a; a = a.parentElement) chain.push(a);
  // Reveal outside-in so an inner widget has geometry when it handles the signal.
  for (const a of chain.reverse()) {
    if (a.tagName === "DETAILS" && !a.open) a.open = true;
    a.dispatchEvent(new CustomEvent("lf-reveal", { detail: { target: el } }));
  }
}

let anchoringReady = false;
const { opaquePassageParts, opaquePassageRoots, rememberPassageParts, upgradeWidgets } =
  createWidgetLoader({
    buildReactBar: (...args) => buildReactBar(...args),
    rememberAuthoredMarkup: (...args) => rememberAuthoredMarkup(...args),
    reportPageError,
    revealLayer,
    sameLayer,
  });

// ---------- comment layer ----------

const VERSION_MATCH = location.pathname.match(VERSION_PATH);
const LIVE_ROOT = location.pathname.endsWith("/") && !VERSION_MATCH;
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
// Sign-off is the page's ask, not standing chrome: the approve button exists only
// when the version declares <meta name="lf-review" content="sign-off"> — a plan or
// proposed change seeking assent. An informational page takes comments only, and
// nothing stands in the button's place there. A neutral "End leaf" did once, and it
// ended nothing it named: the server went on serving, the watcher went on waiting,
// the status was untouched, and the agent side still finished at `leaf status idle`.
// So the one control a page that asks nothing put in front of its reader offered
// them an ending it could not deliver. The declaration rides the document, so a
// pinned older version keeps its own ask.
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
const stateStrip = (...args) => chromeLayout.stateStrip(...args);
const syncLayout = (...args) => chromeLayout.syncLayout(...args);
const setPanel = (...args) => chromeLayout.setPanel(...args);
const drawnEdge = createDrawnEdge({ el, keys, readerStore, stateStrip, syncLayout });
// The comment panel's edge, on the right, and the tray panel's, on the left. Each keeps
// the reader's choice in their own store rather than the tab's, because where a reader
// keeps their conversations, and how much of the page they will give a tray, is the
// chrome they arrange and expect to find arranged wherever they are reading (see
// `readerStore`). Live activation keeps the edges themselves; document travel and reload
// restore the same choices, so no revision or visit asks the reader to draw them again.
const commentsEdge = drawnEdge({
  side: "right",
  noun: "comment panel",
  wide: PANEL_W,
  min: PANEL_MIN,
  prop: PANEL_PROP,
  key: "lf-panel-width",
  covering: COVERING,
});

const banner = el("div", "lf-ui lf-banner");
const dot = el("span", "lf-dot");
const statusText = el("span", "lf-status-text", "Connecting…");
const bannerStatus = el("div", "lf-banner-status");
bannerStatus.append(dot, statusText);
const { bannerActions, reserveNewsSlot, revealFocus, showNews } = createBannerShelf({
  banner,
  el,
  pageScroller,
});
// The hidden pinned slot carries representative words as well as a measured width: an
// empty button is shorter, so its first real label would still move vertically.
const latestChip = el(
  "button",
  "lf-ui lf-btn lf-latest-chip",
  "New page available → open v999",
);
// The keyboard reaches this through the chooser rather than past it: v opens the menu, and
// the letter again takes the current page. The chip names that motion, spelled from the
// two rows that make it rather than typed out beside them.
latestChip.dataset.lfKeyTitle = "Open the current page";
latestChip.title = latestChip.dataset.lfKeyTitle;
if (!LIVE_ROOT) reserveNewsSlot(latestChip);
const pagePresented = () => document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented);
const {
  askRows,
  asksBtn,
  asksList,
  asksOffered,
  asksPanel,
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
  trayStrip,
} = createTrays({
  beforeOpen: () => {
    if (chromeLayout?.panelIsOpen()) setPanel(false);
  },
  drawnEdge,
  el,
  keys,
  leavesOffered: () => leavesOffered(),
  motion,
  openAsks,
  pagePresented,
  paintKeys,
  PRESS,
  readerStore,
  renderAsks: () => renderAsks(openAsks()),
  stateStrip,
  syncLayout,
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
for (const control of [latestChip, asksBtn, othersBtn]) showNews(control, false);
const {
  NEWEST,
  VERSIONS,
  activationIsForced,
  clearForcedActivation,
  goActive,
  renderVersions,
  snapshotVersionNavigation,
  showVersionMenu,
  versionBtn,
  versionLabel,
  versionMenu,
  versionMenuIsOpen,
  versionsOffered,
} = createVersionNavigation({
  allButTheReference,
  comparable: (...args) => comparable(...args),
  comparisonBase: (...args) => comparisonBase(...args),
  el,
  keys,
  latestChip,
  liveRoot: LIVE_ROOT,
  midComposition: (...args) => midComposition(...args),
  paintDiff: (...args) => paintDiff(...args),
  paintHere,
  paintKeys,
  readAndApply,
  pressComparison: (...args) => pressComparison(...args),
  setDiff: (...args) => setDiff(...args),
  showComparison: (...args) => showComparison(...args),
  showNews,
});
const toggleBtn = el("button", "lf-btn lf-comments", "Comments");
toggleBtn.title = "Show or hide the comment panel";
toggleBtn.setAttribute("aria-expanded", "false");
const approveBtn = el("button", "lf-btn primary lf-signoff", "Approve version");
approveBtn.title = "Approve this work; the page stays open for follow-up";
// The page's ask is not actionable until the page itself is present. Discussion chrome
// stays live during replay, but approving hidden authored content would decide a version
// the reader has not seen yet.
approveBtn.disabled = true;
// Seed the invariant middle once; arrangeBannerControls moves the two edge families
// around it and later preserves any registry-declared controls added among these three.
bannerActions.append(latestChip, asksBtn, versionBtn);
// On a wide row, an edge's address sits at that edge: All leaves is the first control
// beside the tray it opens on the left, and Comments (plus approval) finishes beside
// the panel it opens on the right. A covering shelf instead begins with the primary
// Comments loop, keeping it in the first phone view. This is DOM order rather than CSS
// `order`, so the tab route says the same thing the row draws. Reordering existing nodes
// can briefly drop native focus; put it back without moving the page, then make its new
// shelf position wholly visible.
function arrangeBannerControls() {
  const focused = bannerActions.contains(document.activeElement)
    ? document.activeElement
    : null;
  const edges = new Set([toggleBtn, approveBtn, othersBtn]);
  // Registry-declared blanket answers can join the middle of this shelf after boot.
  // Preserve every such control in its standing relative order while moving only the
  // edge-owned addresses; a breakpoint must not strand a later extension at an edge.
  const middle = [...bannerActions.children].filter((control) => !edges.has(control));
  const controls = commentsEdge.over.matches
    ? [toggleBtn, ...(signoff ? [approveBtn] : []), ...middle, othersBtn]
    : [othersBtn, ...middle, ...(signoff ? [approveBtn] : []), toggleBtn];
  bannerActions.append(...controls);
  if (focused && controls.includes(focused)) {
    focused.focus({ preventScroll: true });
    revealFocus(focused);
    // A MediaQueryList change can arrive before its new grid geometry is observable.
    // Reveal once more in the first frame painted with that geometry; keep the identity
    // check so a user who has moved focus meanwhile is never pulled back.
    requestAnimationFrame(() => {
      if (document.activeElement === focused) revealFocus(focused);
    });
  }
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

const panel = el("aside", "lf-ui lf-panel");
const panelHead = el("div", "lf-panel-head");
const closeBtn = Object.assign(el("button", "lf-btn", "×"), {
  title: "Close (Esc)",
  onclick: () => setPanel(false),
});
closeBtn.setAttribute("aria-label", "Close comments");
// The head's own line: the panel's name while it shows the whole conversation, and what
// it is showing instead the moment a narrowing stands. One slot, because they are one
// fact — how much of the log is in front of the reader — and a count in a second place
// is a count free to disagree with the list under it.
const panelTitle = el("span", "", "Comments");
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
findInput.placeholder = "Find in comments";
findInput.setAttribute("aria-label", "Find in comments");
// The register appends the key that reaches it (`also`), so the control and the row
// cannot spell the binding differently.
findInput.title = "Find in comments";
// What is waiting on the reader: an agent comment, an explicit prose ask in a reply, or a
// reply whose own x-awaits markup still asks. The last case is derived from the same
// declaration-driven projection as the asks board; settling reactions can acknowledge
// either kind without closing the thread.
const needsBtn = el("button", "lf-btn lf-needs", "Waiting on you");
needsBtn.setAttribute("aria-pressed", "false");
findRow.append(findInput, needsBtn);
const threadsBox = el("div", "lf-threads");
// An Escape rung: backing out of the general box lands on the list (visible ring,
// t/T walk on from it) rather than on nothing. -1 keeps it out of the Tab order.
threadsBox.tabIndex = -1;
// And a name, because `c` now lands a reader here rather than in the general box, whose
// own label spoke for it. A page key's arrival has to say where it arrived — the two
// landings this one matches are both named, a leaf row by its link text and an ask row by
// the ask — or the press is silent to exactly the reader who cannot see the ring it
// painted. The same reason the reference dialog carries a role and a label beside its -1.
// `group` rather than `list`: the box holds run headings as well as threads, so a list
// role fails `aria-required-children` outright and leaves a screen reader announcing a list
// with no items. The name is what the landing needed; the role is only there because a bare
// div may not carry one.
threadsBox.setAttribute("role", "group");
threadsBox.setAttribute("aria-label", "Comments");
const generalRow = el("div", "lf-general");
const generalInput = document.createElement("textarea");
const generalSend = el("button", "lf-btn primary", "Send");
generalRow.append(generalInput, generalSend);
panel.append(panelHead, findRow, threadsBox, generalRow);

// The floating control a selection raises, grown from one press into a bar: the
// reaction tokens the layer declares ($reactions) and then Comment, so the cheapest
// answer to a passage stands beside the composed one. `.lf-fab` stays the Comment press
// — every route into the composer still goes through it — and the bar is what is
// placed and shown (showFab), the pills being built once the registry has said what
// they are (buildReactBar). One affordance, raised only where the reader has already
// pointed: a selection, a visual's click, the ⌥-click on an item, or `r`.
const fabBar = el("div", "lf-ui lf-fab-bar");
fabBar.setAttribute("role", "group");
fabBar.setAttribute("aria-label", "React or comment");
const fab = el("button", "lf-ui lf-pill lf-fab", "💬 Comment");
const fabSep = el("span", "lf-ui lf-fab-sep");
fabSep.setAttribute("aria-hidden", "true");
fabBar.append(fabSep, fab);
// The aim's box (see its rule above). Empty and pointer-inert, so it says nothing to a
// screen reader and takes nothing from the press it promises; refreshAim is its one
// writer, and data-for is the aimed id stated where a test can read the promise.
const aimBox = el("div", "lf-ui lf-aim");
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
const composerInput = document.createElement("textarea");
// The mark is a paint, and a paint is nothing to a screen reader (see "Paint; don't wrap"
// in CLAUDE.md). So what the box is anchored to travels as the box's own description,
// announced on focus — which is more than the visible quote ever said, since nothing
// pointed a reader at it.
composerInput.setAttribute("aria-describedby", composerQuote.id);
const composerRow = el("div", "lf-composer-row");
const composerCancel = el("button", "lf-btn", "Cancel");
const composerSend = el("button", "lf-btn primary", "Comment");
composerRow.append(composerCancel, composerSend);
composer.append(composerQuote, suggestRow, composerInput, composerRow);
const toastEl = el("div", "lf-ui lf-toast");
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
// The key line — the register's short rendering. Its two fact chips are aria-hidden (the
// spoken copies are placeholders, announcements, and the reference); More is a real button
// because a visible door to the complete list should be a door every reader can work.
const keylineEl = el("div", "lf-ui lf-keyline");
const keylineMore = el("button", "lf-key-more");
keylineMore.type = "button";
keylineMore.title = "More keyboard shortcuts";
keylineMore.setAttribute("aria-label", "? more");
const keylineMoreKey = document.createElement("kbd");
keylineMoreKey.textContent = "?";
keylineMore.append(keylineMoreKey, document.createTextNode("more"));
keylineMore.onclick = () => reference.show(true);

// The name of what the pointer is over in design mode, floated at its corner. Chrome
// nothing presses (pointer-events none, in the stylesheet); refreshAim is its one
// writer (paintInspect), beside the box it names.
const inspectEl = el("div", "lf-ui lf-inspect");
inspectEl.setAttribute("aria-hidden", "true");
// Design mode's legend: a box for every item on the page while the mode stands, drawn
// here in the chrome's layer (paintLegend, its one writer). Paint about the page, so it
// says nothing to a screen reader — the mode's announcement and the names under the
// pointer are the spoken copy.
const legendRoot = el("div", "lf-ui lf-legend");
legendRoot.setAttribute("aria-hidden", "true");
// The g chord's numbered document destinations: a chip on every member of the list it has
// aimed at, drawn here for the same reason the legend is (paintAddresses, its one writer).
// The eye's copy of what the chord announces, so it says nothing to a screen reader.
const addressLayer = el("div", "lf-ui lf-addresses");
addressLayer.setAttribute("aria-hidden", "true");
// The runtime's parts, named: a design comment can point at one, and an anchor names an
// element by id, so each part that is a thing to point at carries a stable one under the
// runtime's own prefix. `[id]:not(.lf-ui)` — how the anchor pass asks which section a
// passage is in — still passes over them, every one wearing lf-ui. What has no id is
// what nobody comments on: the toast, the live region, the scope root itself.
for (const [part, id] of [
  [banner, "lf-banner"],
  [versionMenu, "lf-versions"],
  [othersPanel, "lf-leaves"],
  [asksPanel, "lf-asks"],
  [panel, "lf-comments"],
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
  versionMenu,
  othersPanel,
  asksPanel,
  panel,
  legendRoot,
  addressLayer,
  aimBox,
  fabBar,
  composer,
  toastEl,
  liveEl,
  helpEl,
  keylineEl,
  inspectEl,
);
document.body.append(chromeRoot);
// The controls that rewrite their own words hold the widest of them, measured in the
// face and padding the banner is using now (see the stylesheet's banner comment). The
// covering shelf deliberately spends less horizontal padding than the wide row, so its
// media-query transition has to renew these measurements in both directions; an inline
// minimum measured once on a desk would otherwise make that responsive padding inert.
// The counters hold the widest they reach anywhere below a thousand, so no count they
// write can move them — a page with a thousand open threads, or a machine with a thousand
// live pages, is not one anyone hands a user.
function reserveBannerControls() {
  if (signoff) reserve(approveBtn, ["Approve version", "✓ Version approved"]);
  // News keeps one readable address while it changes words. The action row itself owns
  // overflow now, so no control has to collapse into an illegible pressure release. The
  // covering rule fully removes an unseen slot, including from measurement, so lend it
  // the shown class for this synchronous, invisible reading and put its actual state
  // straight back.
  const latestWasShown = latestChip.classList.contains("lf-news-shown");
  latestChip.classList.add("lf-news-shown");
  reserve(latestChip, [
    "New page available → open v999",
    "Latest edit couldn't be shown",
  ]);
  latestChip.classList.toggle("lf-news-shown", latestWasShown);
  reserve(versionBtn, [
    versionLabel(false),
    versionLabel(true),
    versionLabel(false, "Draft"),
    versionLabel(true, "Draft"),
    versionLabel(false, "v999"),
    versionLabel(true, "v999"),
  ]);
  reserve(toggleBtn, ["Comments", "Comments (999)"]);
  reserve(needsBtn, ["Waiting on you", "Waiting on you (999)"]);
  reserve(asksBtn, ["Asks (999)"]);
  reserve(othersBtn, ["All leaves (999)"]);
}
reserveBannerControls();
commentsEdge.over.addEventListener("change", () => {
  arrangeBannerControls();
  reserveBannerControls();
});
// ---------- state ----------

// Until the first state answer, [] means "not read", not "no comments". Keep that
// distinction for a Comments panel restored or opened during startup; its General
// composer stays usable while the log-derived list says what it is waiting for.

// The threads the panel last reconciled. A work line repaints on the heartbeat's clock and
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
  banner,
  chromeRoot,
  commentsEdge,
  composer,
  composerIsOpen: () => composerOpen,
  containsAcross: (...args) => containsAcross(...args),
  currentTray,
  dockSeats: () => anchorRuntime?.dockSeats(),
  focused,
  generalRow,
  keylineEl,
  pageShifted: (...args) => pageShifted(...args),
  paintHere,
  panel,
  placeComposer: (...args) => placeComposer(...args),
  readerStore,
  refreshFab: (...args) => refreshFab(...args),
  refreshHover: (...args) => refreshHover(...args),
  renderPanel: (...args) => renderPanel(...args),
  reserveListClearance,
  scrollerGutter,
  showTray,
  syncGeneral: (...args) => syncGeneral(...args),
  toastEl,
  toggleBtn,
  trayStrip,
  traysEdge,
});
const { inPanel, panelCovers, panelIsOpen } = chromeLayout;
const { showToast } = createNotifications({ liveEl, syncLayout, toastEl });

// ---------- text inputs ----------
const { paint: paintInputs, wire: wireInput } = createInput({
  focused,
  keys,
  showToast,
  spell,
});
paintInputHints = paintInputs;

const { landTyping, pageSelection, selectionAnchor, snapSelection } =
  createSelectionCapture({
    anchoringIsReady: () => anchoringReady,
    blockOf: (...args) => blockOf(...args),
    closestAcross: (...args) => closestAcross(...args),
    collapseWhitespace: (text) => text.replace(COLLAPSE, " "),
    cut: (...args) => cut(...args),
    datumSelector: () => DATUM,
    elementOver: (...args) => elementOver(...args),
    neighbourhood: (...args) => neighbourhood(...args),
    pageRange: (...args) => pageRange(...args),
    pageText: (...args) => pageText(...args),
    pageWords: (...args) => pageWords(...args),
    quoteFrom: (...args) => quoteFrom(...args),
    segmentText: (...args) => textUnits.segment(...args),
    segmentsIn: (...args) => segmentsIn(...args),
    spanIn: (...args) => spanIn(...args),
  });

const {
  BANNER_CLEAR,
  activateVisual,
  beside,
  dismissFab,
  fabAnchorAt,
  openOnItem,
  openOnVisual,
  placeClear,
  placeComposer,
  raiseOnItem,
  refreshFab,
  showFab,
  standDown,
  updateFab,
} = createSelectionSurface({
  anchoringIsReady: () => anchoringReady,
  anchorLabel: (...args) => anchorLabel(...args),
  composer,
  composerInput,
  composerIsOpen: () => composerOpen,
  designIsOn: () => designOn,
  designTarget,
  fab,
  fabBar,
  fabSep,
  hideComposer: () => hideComposer(),
  hideReference: () => reference.show(false, false),
  inChrome: (node) => inChrome(node),
  keylineEl,
  leavePageControl: () => letGo(),
  markAt,
  noteClass: () => NOTE,
  openComposer,
  openOnDesign,
  pageRange: (...args) => pageRange(...args),
  pageScroller,
  pageSelection,
  pageText: (...args) => pageText(...args),
  pageWords: (...args) => pageWords(...args),
  paintAnchors,
  paintHere,
  paintStanding: paintReactionStanding,
  panel,
  panelCovers,
  pendingMarkParts,
  pointerAt,
  reactionTokens: () => reactionTokens(),
  reactionsOn: (anchor) => conversationRuntime.reactionsOn(anchor),
  referenceIsOpen: () => reference.open,
  resolveAnchor: (...args) => resolveAnchor(...args),
  selectionAnchor,
  setReact: (on) => setReact(on),
  showThread,
  showVersionMenu,
  snapSelection,
  shownParts,
  shownRect: (...args) => shownRect(...args),
  takesLetters: (node) => takesLetters(node),
  versionMenuIsOpen,
  visualActionAnchor: (...args) => visualActionAnchor(...args),
  visualAt: (...args) => visualAt(...args),
});

const { AIM, aimIsOn, aimedItem } = createAim({
  designPress,
  designTarget,
  inChrome: (node) => inChrome(node),
  itemAt,
  openOnDesign,
  openOnVisual,
  pointerAt,
  raiseOnItem,
  refreshAim,
  spell,
  standDown,
  visualAt,
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
  composer,
  composerCancel,
  composerInput,
  composerSend,
  designIsOn: () => designOn,
  draftContexts,
  fab,
  fabAnchor: fabAnchorAt,
  landTyping,
  loadDraft,
  paintAnchors,
  paintHere,
  placeComposer,
  post,
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

function pendingComposer() {
  return selectionComposerRuntime.pendingComposer();
}
function openComposer(
  anchor,
  text,
  left,
  top,
  suggest = false,
  about = designOn ? "layer" : null,
) {
  return selectionComposerRuntime.openComposer(anchor, text, left, top, suggest, about);
}
const hideComposer = () => selectionComposerRuntime.hideComposer();
function closeComposer() {
  return selectionComposerRuntime.closeComposer();
}

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
  // The page's c brought the reader here; this one puts them in the box. Same letter
  // twice because it is the same intent one scope further in, which is how the rest
  // of the register reads too — g names a list and then a member of it. The box says
  // the same key from its own placeholder, so the second press is discoverable from
  // the panel without the reference open.
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
  run: () => generalInput.focus({ preventScroll: true }),
};

const syncGeneral = wireInput(generalInput, {
  // The box has no anchor to decide it at an open, so what it posts is decided at the
  // send, by the mode standing then — and the hint says which, so the reader typing in
  // design mode knows their remark is about the layer as a whole.
  hint: generalHint,
  // The box's own address: unfocused, the placeholder reads "Comment on the page · c".
  // That c is the panel's own and the second press of the page's. One key rather than a
  // chord, because this box is the panel's own and the scope that offers it is the one
  // the reader is standing in.
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
    showThread(sent.id);
    landTyping(generalInput); // both send routes end where typing was
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
// Escape is a binding like any other. It was a ladder of its own — a says/out pair per
// branch of a scene() function, plus a hand-written sentence in the reference that listed
// six of its eight rungs — and as a row the rung is whichever scope in reach binds it
// first, said and run off one object. What that retires is a contract a widget used to
// keep by hand: a control declaring its own Escape had to consume the press, or the
// runtime's ladder ran behind it and closed the panel under a line that promised one
// action. The dispatcher runs the innermost rung and no other, so the promise is
// structural.

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
// at nothing. The ⌥ aim reaches an item through the pointer and the keyboard reached none
// at all: an address put the reader on an option and `c` still offered them the page.
//
// The unanswered ask where the reader is standing on a control that works it, and the innermost
// item everywhere else. The control the walk stands them on is one part of the question
// (standOn), so a press made
// from a pick, a ✓ or a mark means the question those answer. Standing *in* an ask is not
// the same fact: a reader who addressed a hyperlink (`g h 3`) or tabbed to one has said
// something more particular than the question containing it, and answering the question
// there both overrides what they named and made the same markup answer differently
// according to whether its question was still open — a link in a settled group gave the
// option, the identical link in an open one gave the whole group.
//
// So the ring `markHere` paints and this are two questions, and the earlier version had
// them confused. The ring says which ask the reader is in, for the walk and the answering
// keys; this says what a remark made here is about. They agree wherever the reader is
// working the ask, which is every arrival the ask walk makes.
//
// Below that, the innermost item — the aim's own reading — through `askPlace`, so a
// control a widget hoisted into the margin speaks for the ask it points back at rather
// than for the block it hangs beside.
//
// Focus in the chrome is not a place in the page. The banner, the panel and the trays are
// where a reader works on the page rather than where they stand in it, so a press made
// from one means the page whole. A box that takes letters never arrives here at all: the
// typing scope claims the letter before the page is asked.
//
// `documentFocused()` rather than `focused()`, for the reason askPosition gives: a control
// staged in a shadow tree retargets to its host, and the host is the place in the document
// both the chrome guard and the item walk want. standingConversation below wants the inner
// reading, and says so.
const standingItem = () => {
  const held = documentFocused();
  if (!held || held === document.body || inChrome(held)) return null;
  const working = held.matches?.(ASK_CONTROL) ? standingIn() : null;
  return working ?? itemAt(askPlace(held));
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
// Three of the four are a box to write in and say so in the same sentence, so the sentence
// is written once here and the word is what varies. The fourth is not a comment at all but
// the room the comments are in, and states its own words rather than being bent to the
// pattern — naming it by word alone is what produced "comment on the comments".
const commenting = (word) => ({
  does: `Comment on the ${word}`,
  line: `comment on the ${word}`,
});
const commentDestination = () => {
  const anchor = fabAnchorAt();
  if (anchor)
    return {
      ...commenting(
        anchor.quote ? "selection" : itemWord(elementById(anchor.section)) || "item",
      ),
      go: () => fab.onclick(),
    };
  const said = standingConversation();
  if (said) return { ...commenting("thread"), go: () => landIn(said) };
  const here = standingItem();
  if (here) return { ...commenting(itemWord(here)), go: () => commentOnItem(here) };
  // Standing nowhere the press can name, so it means "take me to the conversation" and
  // lands on the list rather than in a box: the ring is visible, t/T walk on from it, and
  // w and / are live, because the scope the reader is now standing in is the panel's
  // rather than a text box's. Landing in the general box put them in the one place in the
  // panel where the panel's own keys are all shadowed — TYPING claims a letter before
  // PANEL can — so the reader who pressed c to reach the comments had to press Escape
  // before they could use them. The box is one more c away (PANEL's own row), which is the
  // shape of every other way in: a scope names its keys, and typing is a scope you enter.
  return {
    does: "Go to the comments",
    line: "comments",
    go: () => {
      setPanel(true);
      threadsBox.focus({ preventScroll: true });
    },
  };
};
// c goes where commenting happens: a live selection gets the composer (what the floating
// button does), an element click's pending 💬 gets that, an open thread the reader is
// standing in gets its own reply box, the item they are standing in gets the box belonging
// to it, and otherwise the conversation itself, the panel opening and the list taking the
// focus — the general box being the panel's own c, one press further in. Never the panel's
// collapse: c doubled as the toggle once, so with the panel standing open the one key that
// promised "comment" answered "close", and no shortcut reached the box. Backing out is
// Escape's, which already closes the panel rung by rung.
//
// Standing outranks the page and not the pointer: a reader who has just selected words or
// raised the 💬 on something has said what they mean more recently than the focus they left
// behind, which is the order askPosition reads its own answers in.
function commentKey() {
  updateFab(); // the selection may be newer than the mouseup that last placed the button
  commentDestination().go();
}

// Pages are authored documents where typing can start at any moment, so a scope whose keys
// are bare letters stands down wherever a letter is a keystroke. That is the whole of the
// question, and asking a wider one cost the page its keyboard: every `<input>` counted,
// so a reader standing on a screenshot's before/after radio — which consumes no letter the
// platform ever gave it — lost c, d/u, a and the rest, with nothing on screen saying why.
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
// one line of code, because standing on an ask out on the page and standing on a banner
// button are the same state — the reader holding something — reached from either side of
// the chrome. What the two rungs do not share is the word, and neither word is the other's:
// leaving the chrome names where the reader lands, since that is the whole of what the
// rung is for, and letting go of an ask names the act, since they were on the page all
// along.
//
// Focus rather than blur, because the two differ in what Space does next: `html` is
// `overflow: hidden` here so the document scrolls in `body`, and the browser scrolls
// whichever box it last saw the reader put themselves in. A blur names none —
// activeElement reads as body either way — and Space goes on doing nothing until the next
// click in the page.
//
// Which asks that body be somewhere a reader can be put, and it is not one by default.
// Chrome makes a scroll container focusable so the keyboard can scroll it, and that was
// the whole of what made this call work: on a page long enough to scroll, focus landed on
// body; on a page that fits the window, `body.focus()` moved nothing and the reader stayed
// on the control the line had just promised to take them off — measured both ways on one
// page, by shrinking its content until it fit. So the rung failed exactly where its own
// reason for existing is strongest, a short page having no scroll to hand back and every
// bit as much of a Space that presses whatever the reader was left standing on.
document.body.tabIndex = -1;
const letGo = () => document.body.focus({ preventScroll: true });
// The Escape ladder, one definition for every scope that reaches past the focused control,
// so the thread's, the list's and the page's cannot disagree. It unwinds from where the
// reader is standing, not from what happens to be open.
//
// So the first rung is theirs: out on the page, the innermost thing they are in is the ask
// they are standing on, and a panel behind them is a layer they are not in. Nothing said
// this before — a reader the walk had brought to an ask could press Escape all day and the
// ring stayed on it, the one place in the runtime a key put the reader somewhere with no
// key to take them out again.
//
// Inside the chrome it is the open workspace first. Trays and Comments replace one
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
  if (fabAnchorAt())
    return {
      says: "close actions",
      does: "Close the reaction and comment actions",
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
    return { says: "show all", does: "Show every comment again", out: widen };
  if (panelIsOpen())
    return {
      says: "close comments",
      does: "Close the comment panel",
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
// being true the day the first rung became letting go of an ask, which is no layer at
// all — the line saying "let go" while the reference said "layer" about the same press.
const BACK_OUT = {
  id: "navigation.back",
  keys: ["Escape"],
  does: () => rung()?.does,
  line: () => rung()?.says,
  when: () => Boolean(rung()),
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

const { askEntry, isAwaiting, projectedParent, unansweredAsks } = createAskModel({
  authoredParentOf: (node) => authoredParents.get(node),
  closestAcross: (...args) => closestAcross(...args),
  elementById: (...args) => elementById(...args),
  pagePresented,
  registry,
  runtime,
  stateProjection: (...args) => stateProjection(...args),
  tagsDeclaring,
});

const {
  ASK_CONTROL,
  ASK_ROW,
  askPlace,
  buildBulkAnswers,
  goToAsk,
  landedAt,
  markHere,
  renderAsks,
  setLanded,
  standOn,
  standingIn,
  stepAsk,
  syncAsks,
} = createAskView({
  PAGE_PAINT_ATTRIBUTE,
  scrollBehavior,
  documentFocused,
  announce,
  askEntry,
  askSource,
  asksBtn,
  asksList,
  asksOffered,
  asksPanel,
  banner,
  blocksOnScreen,
  closeTray: () => showTray(null),
  el,
  elementById: (...args) => elementById(...args),
  inChrome: (node) => inChrome(node),
  itemSays,
  itemWord,
  keys,
  openAsks,
  openTray,
  paintAnchors,
  paintHere,
  paintKeys,
  PRESS,
  panelIsOpen,
  registry,
  reserve,
  reveal,
  scrollToElement,
  setPanel,
  showNews,
  shownParts,
  tagsDeclaring,
  trayCovers: () => traysEdge.over.matches,
  unansweredAsks,
  versionBtn,
});

const { commentOnItem, glideTo, placeThreadEdge, seenScroller, stepPage, stepThread } =
  createNavigation({
    BANNER_CLEAR,
    reducedMotion,
    scrollBehavior,
    beside,
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
    shownBox,
    shownRect,
    threadsBox,
  });

const revealComments = () => {
  if (panelIsOpen()) return null;
  setPanel(true);
  return () => setPanel(false);
};
const landInThreadReply = (thread) =>
  landIn({ held: thread, box: thread.querySelector(SAY_BOX) });

const { GO, GOTO, isChordArmed, paintAddresses, setChord } = createAddress({
  EVERYTHING,
  addressLayer,
  announce,
  askRows,
  asksPanel,
  asksOffered,
  banner,
  claimsEsc,
  el,
  focused,
  focusedThread,
  glideTo,
  inPanel,
  keylineEl,
  leavesOffered,
  letGo,
  othersLinks,
  othersPanel,
  pageParts,
  paintHere,
  panelCovers,
  placeThreadEdge,
  saying,
  seenScroller,
  setPanel,
  showTray,
  startsAt,
  scrollToElement,
  threadsBox,
});

// ---------- reactions ----------
const {
  REACT,
  buildReactBar,
  isReactArmed,
  reactPills,
  reactionTokens,
  sendReaction,
  setReact,
  undoSentence,
} = createReactions({
  CONTROL_WORD_CAP,
  EVERYTHING,
  anchorLabel: (...args) => anchorLabel(...args),
  announce,
  claimsEsc,
  commentsReveal: revealComments,
  currentRevision: () => runtime.currentRevision,
  cut: (...args) => cut(...args),
  designIsOn: () => designOn,
  el,
  elementById: (...args) => elementById(...args),
  fab,
  fabAnchorAt,
  fabBar,
  focused,
  itemWord,
  offer,
  pageStrip: () => conversationRuntime.pageStrip,
  paintHere,
  post,
  reactionVocabulary: () => registry.$reactions?.tokens,
  saying,
  showFab,
  standingConversation,
  standingItem,
  undoable: (...args) => undoable(...args),
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
      does: "Close this reference",
      line: "close help",
      also: helpClose,
      runFromReference: false,
      run: () => reference.show(false),
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
      id: "composer.close",
      keys: ["Escape"],
      does: "Close the composer, keeping the draft",
      line: "close — draft kept",
      run: () => {
        hideComposer();
        showFab(null);
      },
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
// Where a box hands the reader back to, which is the rung `c` came down. It asked
// `.lf-thread` and the panel alone, so the two boxes outside the chrome — a conversation
// seated on the page, and each thread on that seat — had no way out but the page's own
// "let go": one press in from the thread and one press out to nothing at all, which is
// the arithmetic the keyboard-is-a-stack rule exists to keep. The climb is
// `heldConversation`'s, so this is the same element `c` named on the way in.
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
      id: "comment.find.close",
      keys: ["Escape"],
      does: () =>
        narrowed()
          ? "Show every comment again"
          : "Leave the box, keeping what is typed",
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
      id: "comment.find.first",
      keys: ["Enter"],
      does: "Go to the first comment found",
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
// `c` is the one row here whose subject is not this list, and it is the rule read one
// step further rather than the rule bending: the page's `c` follows the reader and is
// what lands them here, and this is the same intent one scope in, the way `g` names a
// list and then a member of it. The row's own comment carries where it stands down, so
// the page's answer is the one that runs wherever the page has a nearer one.
//
// Standing in the panel is where its focus is, not merely that it is open: the Comments
// button is the banner's, so opening by pointer leaves the reader outside, and `c`, `t`,
// Tab or a click on a thread is what puts them in. The same line `THREAD` draws one step
// further in, which is why that scope sits before this one and its rows shadow these.
// Whether the page has this scope at all is not a question the log answers: every page
// has a comment panel, and its general box stands and takes words from the first paint —
// the offline banner says a comment will not send, not that there is nowhere to write it.
// What the log answers is whether there is a list, which is `w`'s and `/`'s own condition
// and is now said on each of them. Said once here for all three, it took `c` down with
// them: the page's `c` stands the reader on the list, the panel's `c` was out of the
// stack, and the second press was the page's own again, landing focus where it already
// was. The box went on naming the key in its placeholder with no press able to reach it.

const PANEL = {
  title: "In the comment panel",
  at: inPanel,
  rows: [
    {
      id: "comment.waiting.toggle",
      // `w` for the words the control says. It is the phrase the page already uses for
      // the same question asked of its widgets (a/A), asked here of the conversation —
      // so the reader learns one idea and reaches it two ways rather than learning
      // "needs you" beside it.
      //
      // A narrowing is a mode, so the row states it as one: the sentence and the line
      // both turn on whether it stands, and Escape takes it off through the rung ladder
      // rather than through a second binding here. Dead while there is nothing waiting
      // and nothing hidden, which is the same fact that greys the control — and dead
      // before the log arrives, which is the one part of that the standing narrowing
      // cannot say for itself: `needsYou` is a flag the reader set, and it outlives a
      // list that has gone back to empty. `/` needs no such clause, `renderPanel`
      // emptying `threadList` at every phase but ready.
      keys: ["w"],
      does: () =>
        conversationRuntime.needsYou
          ? "Show every comment again"
          : "Show only the comments waiting on you",
      line: () => (conversationRuntime.needsYou ? "all comments" : "waiting on you"),
      also: needsBtn,
      when: () =>
        runtime.statePhase === "ready" &&
        (conversationRuntime.needsYou ||
          conversationRuntime.threadList.some(awaitsReader)),
      run: () => needsBtn.click(),
    },
    {
      id: "comment.find",
      // `/` is what every list with a search field takes it with, and the one letter a
      // text box does not shadow: the typing scope claims what types a character, so the
      // press only ever reaches here from the list rather than from a box in it.
      keys: ["/"],
      does: "Find in the comments",
      line: "find",
      also: findInput,
      // A conversation with nothing in it has nothing to find in, and the panel says so
      // itself; a page still reading the log is not yet a page with no comments, which
      // the scope's own `when` answers for both rows here.
      when: () => conversationRuntime.threadList.length > 0,
      run: () => {
        findInput.focus();
        findInput.select();
      },
    },
    // Last, because the line paints two chips and the first is this scope's first live
    // row. Standing here, `w` and `/` are the only rows that can ever hold that slot —
    // inside a thread THREAD is nearer, inside a box TYPING claims the letters, outside
    // the panel this scope is not standing — so a `c` in front of them is the two keys
    // this landing exists to expose going unadvertised at the one place they work. The
    // second press has a surface of its own: the box says the key in its placeholder.
    PANEL_SAY,
  ],
};

// A focused thread: the reply and the resolve are this scope's, not the page's. They said
// "On a focused thread" in their own sentences and were live over the whole page, so a
// reader who had focused nothing was offered a press that no-opped — d/u's bug from the
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
            ":scope > .lf-thread-actions > .lf-reopen:not(:disabled)",
          ),
        ),
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
            ":scope > .lf-thread-actions > :is(.lf-resolve, .lf-reopen):not(:disabled)",
          ),
        ),
      run: () =>
        focusedThread()
          .querySelector(
            ":scope > .lf-thread-actions > :is(.lf-resolve, .lf-reopen):not(:disabled)",
          )
          .click(),
    },
  ],
};

// Where the reader is standing, when what they are standing on is one of the page's own
// parts rather than a widget's own declaration. The control scope below cannot cover
// these: it works a span `offer` made pressable, where these arrive with keys already
// bound, and which keys differ — Enter follows an <a> while Space scrolls the page out
// from under it, and both work a disclosure. `g` puts the reader on both of them by key,
// and until a scope existed the line went quiet at exactly the moment they arrived, with
// the press that finishes the motion unnamed.
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
// and the control scope's on an offered span. The arrows are this scope's alone, so they
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

// Every press the runtime builds out of a span, in one declaration. `offer` writes
// role="button" onto an element the platform gives no keys, so these two are the UA's
// contract restored — and the survey's largest hole was that nine classes of control
// across core and five widgets answered Space while one of them said so. Outermost of the
// control scopes, so a widget whose press means something more (a grip grabs, a mark
// toggles) names it in its own words and the walk's dedupe keeps this row from saying it
// again.
// `offer` says whether it built a press, and this is that answer read back. Neither the
// tabindex nor the role can stand in for it: every focus target wears a tabindex, so this
// scope promised "press it" on a seated conversation thread that answers nothing, and a
// widget may specialise the role, so `lf-tabs` lost Enter and Space when this read it.
const CONTROL_SELECTOR = '[data-lf-offer="button"]';
const CONTROL = {
  title: "On a control",
  at: () => Boolean(focused()?.matches?.(CONTROL_SELECTOR)),
  // The page has to have built one, or the reference names a place the reader can't
  // stand. The query is the reference's cost and not the line's: `at` is asked first and
  // answers false wherever this could be in doubt, so a paint never reaches it.
  when: () => Boolean(document.querySelector(CONTROL_SELECTOR)),
  rows: [
    {
      id: "control.activate",
      keys: PRESS,
      does: "Work the focused control",
      line: "press it",
      // Space would take the page out from under the press, which is why the row consumes
      // it; the dispatcher does that for every row that runs.
      run: () => focused().click(),
    },
  ],
};

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
// Escape is the one promotion over this order, because the way out of a current scene must
// survive beside its way in.
// v names the chooser, the control wearing the version number, and the menu it opens
// takes the letter again for the current page — one motion whose second half is a key of
// the scope the first half stood up, so it costs the table no row and holds whether or not
// this page is behind. Named, because the chip that jumps straight to the current page
// spells that motion in its tooltip.
const CHOOSER = {
  id: "version.open",
  keys: ["v"],
  does: "The versions, and what each one changed",
  line: "versions",
  also: versionBtn,
  // The same predicate the menu's Escape stands on, so the key cannot open a layer the
  // way out is not live over. The walk being empty is the menu's business, not this key's.
  when: versionsOffered,
  run: () => versionBtn.onclick(),
};
// Named for the same kind of reason: a mode standing over the page suspends the page's keys
// and keeps this one (`allButTheReference`), and the claim reads the binding off the row
// rather than spelling "?" beside it — a fact about a binding written where the binding
// cannot correct it is the register's own oldest bug. Its place in the table is nominal:
// renderLine gives it the permanent More control instead of spending a hint slot on it.
const REFERENCE = {
  id: "reference.open",
  runFromReference: false,
  keys: ["?"],
  does: "This key reference",
  line: "more",
  also: keylineMore,
  run: () => reference.show(true),
};
const PAGE = {
  rows: [
    {
      id: "comment.create",
      keys: ["c"],
      // One key, four destinations, and the surfaces name the one in front of the reader:
      // a live selection, the item a click raised the 💬 on, the box belonging to whatever
      // the reader is standing in, or — when none of those is in hand — the conversation
      // itself. "Comment" covered them all and so promised none of them.
      //
      // The last of the four used to be "comment on the page" and put the reader straight
      // into the general box; it now names the room, and the panel's own c names the box
      // in it. Both words are stated beside the press they belong to, so the sentence, the
      // key line and what the press does cannot come to disagree.
      does: () => commentDestination().does,
      line: () => commentDestination().line,
      // A selection made before the anchor pass has run can't be quoted yet, and
      // commenting on the page instead is not what the reader asked for — so the press
      // waits, and the row's own liveness is where that is said rather than a refusal
      // inside run that no surface can see.
      when: () => anchoringReady || !pageSelection(),
      run: commentKey,
    },
    {
      // `r` from the bar's own word (its name is "React or comment"). What it arms is
      // the bar the pointer sees, digits on: the same tokens in the same order, so a
      // reader who has seen the bar once knows the keys. Nine at most, the digits being
      // the addresses.
      id: "reaction.open",
      keys: ["r"],
      does: () =>
        `React — ${reactionTokens()
          .slice(0, 9)
          .map(([name, entry]) => `${entry.glyph} ${name}`)
          .join(", ")} — on the selection, the item you are standing on, or the page`,
      line: "react",
      when: () => reactionTokens().length > 0 && (anchoringReady || !pageSelection()),
      run: () => setReact(true),
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
      id: "ask.walk",
      keys: ["a", "Shift+a"],
      routes: [
        {
          id: "ask.next",
          binding: "a",
          does: "Next thing this page is waiting on you for",
        },
        {
          id: "ask.previous",
          binding: "Shift+a",
          does: "Previous thing this page is waiting on you for",
        },
      ],
      does: "Next / previous thing this page is waiting on you for",
      line: "asks",
      when: () => openAsks().length > 0,
      repeat: true,
      run: (binding) => stepAsk(binding === "a" ? 1 : -1),
    },
    {
      id: "page.half-scroll",
      keys: ["d", "u"],
      routes: [
        { id: "page.half-down", binding: "d", does: "Half a page down" },
        { id: "page.half-up", binding: "u", does: "Half a page up" },
      ],
      does: "Half a page down / up",
      line: "half a page",
      repeat: true,
      run: (binding) => stepPage(binding === "d" ? 0.5 : -0.5),
    },
    {
      id: "version.approve",
      keys: ["Shift+l"],
      does: "Approve this version",
      line: "looks good",
      also: approveBtn,
      when: () => signoff && !approveBtn.disabled,
      run: () => approveBtn.click(),
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
    // 1280px line — the reader standing on an ask, which is the one place the way out was
    // written for. What it costs to yield is small and what it buys is not: `g` opens a
    // door to three lists the walks above already reach one at a time, so a narrow window
    // hides a second way to somewhere; the press it was crowding out is the only way back
    // from where a press had just put the reader.
    GOTO,
    CHOOSER,
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
// element scopes splice in where ELEMENTS stands — between the two modes that suspend the page
// and the page's own, because a widget's control shadows the page and nothing shadows an armed
// chord or the reference — and every other reading is taken from here: the dispatcher and the
// line walk it as it stands, the reference walks it backwards.
//
// Three lists said this, and the third was the reference's own, in its own order, holding the
// same eight scopes by hand. A mode left out of that one was a mode the reference never named
// — which is not a hypothetical, being the failure it had already made when core's modes were
// not declared the way a widget's are. A list that must be edited in step with another is the
// same bug waiting on the next mode.
const ELEMENTS = Symbol("the scopes of the focused element");
const SCOPES = [
  GO,
  REACT,
  HELP,
  ELEMENTS,
  VERSIONS,
  COMPOSER,
  TYPING,
  THREAD,
  PANEL,
  LINK,
  DISCLOSURE,
  CONTROL,
  DESIGN,
  PAGE,
];
const CORE = SCOPES.filter((scope) => scope !== ELEMENTS);
// Core's scopes are checked at module load by the rule every widget's are checked by at
// upgrade, so a row here that presses with nothing to say for itself takes down the layer on
// the first page rather than going quiet on every one.
for (const scope of CORE) checked(scope.rows, scope.title ?? "the page's own keys");
// A control the keyboard also reaches names its key, and names it off the row. Three
// tooltips spelled theirs in prose — "(a)", "(o)", "(v v)" — which is the field the key
// line's word used to be, a fact about a binding written somewhere the binding cannot
// correct. `also` is where a row says which control it duplicates; its projection follows
// liveness too, so a disabled decision does not advertise a shortcut the dispatcher has
// withdrawn. The chip's is the one motion no single row makes, so it remains composed of
// the two rows that make it.
function paintCoreControls() {
  for (const scope of CORE)
    for (const row of scope.rows)
      if (row.also) {
        if (!("lfKeyTitle" in row.also.dataset))
          row.also.dataset.lfKeyTitle = row.also.title;
        const active = live(row) && bindings(row).length > 0;
        row.also.title =
          row.also.dataset.lfKeyTitle + (active ? ` (${labelOf(row)})` : "");
        if (active)
          row.also.setAttribute("aria-keyshortcuts", ariaShortcuts([row], false));
        else row.also.removeAttribute("aria-keyshortcuts");
      }
  const referenceBound = bindings(REFERENCE).length > 0;
  keylineMoreKey.hidden = !referenceBound;
  keylineMore.setAttribute(
    "aria-label",
    referenceBound ? "? more" : "More keyboard shortcuts",
  );
  const latestBound = bindings(CHOOSER).length && bindings(NEWEST).length;
  latestChip.title =
    latestChip.dataset.lfKeyTitle +
    (latestBound ? ` (${labelOf(CHOOSER)} ${labelOf(NEWEST)})` : "");
}

const { availableCommands, executeCommand, readerIn, shadow, stack } = createDispatch({
  claimsEsc,
  ELEMENTS,
  focused,
  isChordArmed,
  isReactArmed,
  paintHere,
  recoveredLabelFocus,
  SCOPES,
  scopesFor,
  setChord,
  setReact,
  takesLetters,
  TYPING,
});
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

const { renderLine } = createKeyline({
  el,
  keylineEl,
  keylineMore,
  paintHere,
  reference,
  shadow,
  stack,
});
const {
  comparable,
  comparisonBase,
  comparisonChanges,
  paintDiff,
  pressComparison,
  setDiff,
  showComparison,
} = createVersionDiff({
  chooserLabel: () => labelOf(CHOOSER),
  domFacet: (...args) => domFacet(...args),
  elementById: (...args) => elementById(...args),
  inChrome: (...args) => inChrome(...args),
  quoted,
  projectionFromView: (...args) => projectionFromView(...args),
  sameLayer,
  showToast,
  stateCoordinate: (...args) => stateCoordinate(...args),
  stateSpecs: (...args) => stateSpecs(...args),
  textBlockSelector: () => TEXT_BLOCK,
  versionBtn,
  versionLabel,
  versionMenu,
  wrote: (...args) => wrote(...args),
});
const { droppedAt, presented } = createPresence();

const { loadIcon, renderStatus, toneFor } = createBanner({
  agentName,
  ago,
  dot,
  el,
  presented,
  statusText,
});

const { activateRevision, currentActivation, revisionDocument, trackActivation } =
  createVersionActivation(versionRoots, {
    captureAuthoredFacets: (...args) => captureAuthoredFacets(...args),
    captureView,
    comparisonBase,
    designIsOn: () => designOn,
    paintLegend,
    pruneScopedElements,
    rememberAuthoredMarkup: (...args) => rememberAuthoredMarkup(...args),
    rememberPassageParts,
    resetAuthoredPage: (...args) => resetAuthoredPage(...args),
    sameLayer,
    setDiff,
    settle,
    settling,
    stateSignoff,
    stateStrip,
    style,
    syncLayout,
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
// have typed — a composition surface is a focused textarea, any holding words, or a
// widget-built one (data-lf-offer) even empty, because deleting everything is still an
// edit.
const midComposition = () => {
  const active = focused();
  return (
    composerOpen ||
    Boolean(fabAnchorAt()) ||
    unaccountedGesture() ||
    (active?.tagName === "TEXTAREA" &&
      (active.value !== "" || active.hasAttribute("data-lf-offer")))
  );
};
// Through the chooser's one door, so the chip opens exactly the version it names. At the
// live root that is an explicit in-place release of the composition hold; on an immutable
// page it is ordinary version travel.
latestChip.onclick = () => goActive();

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
let viewRuntime;

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
function awaitsAgent(...args) {
  return conversationRuntime.awaitsAgent(...args);
}
function seatRoot(...args) {
  return conversationRuntime.seatRoot(...args);
}
function setChildren(...args) {
  return conversationRuntime.setChildren(...args);
}
function paintWorkLines(...args) {
  return conversationRuntime.paintWorkLines(...args);
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

function blocksOnScreen(...args) {
  return viewRuntime.blocksOnScreen(...args);
}
function captureView(...args) {
  return viewRuntime.captureView(...args);
}
function restoreView(...args) {
  return viewRuntime.restoreView(...args);
}
function sectionOf(...args) {
  return anchorRuntime.sectionOf(...args);
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
function visualPartAt(...args) {
  return anchorRuntime.visualPartAt(...args);
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
function scrollToElement(...args) {
  return anchorRuntime.scrollToElement(...args);
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
function pendingMarkParts(...args) {
  return anchorRuntime.pendingMarkParts(...args);
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
  TEXT_BLOCK,
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
} = passageRuntime;

const runtimeProjection = createProjection(runtime, {
  ASK_ROW,
  COLLAPSE,
  MARKED_ANYWHERE,
  MARKED_IN_PAGE,
  PAGE_PAINT_ATTRIBUTE,
  PAGE_PAINT_ATTRIBUTES,
  agentName,
  answeredContext,
  askEntry,
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
  paintWorkLines,
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
  toast,
  widgetEntries,
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
  stateSpecs,
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
  showToast,
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
  post,
  PRESS,
  quietSince,
  reachScrollers,
  reachedForWords,
  reactDone: () => setReact(false, { spent: true }),
  reactPills,
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
  worksSelector: WORKS,
});
const { ITEM, NOTE } = anchorRuntime;

createLivingMargin({
  anchorLabel,
  announce,
  approveBtn,
  banner,
  chromeRoot,
  claimState: workClaimState,
  comparisonBase,
  comparisonChanges,
  compact: commentsEdge.over,
  el,
  elementById,
  goToAsk,
  inChrome,
  itemSays,
  itemWord,
  keys,
  offer,
  openAsks,
  pageScroller,
  paintKeys,
  placedAt,
  scrollBehavior,
  scrollToElement,
  showThread,
  stateProjection,
  threads: () => conversationRuntime.threadList,
  toggleBtn,
  updateSequence,
  versionBtn,
});

viewRuntime = createViewContinuity({
  TEXT_BLOCK,
  banner,
  cut,
  inChrome,
  landedAt,
  pageScroller,
  pageText,
  quoteFrom,
  rangeOf,
  resolveAnchor,
  reveal,
  runtime,
  setLanded,
  textNodesUnder,
});

createConversationLanding({ scrollToThread });
createConversationBox({ post, renderPanel, showToast, wireInput });

designRuntime = createDesign({
  ITEM,
  announce,
  banner,
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
  openComposer,
  pageScroller,
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
  LIVE_ROOT,
  PAGE_PAINT_ATTRIBUTE,
  acceptData,
  activateRevision,
  activationIsForced,
  accountOutbox,
  clearForcedActivation,
  currentActivation,
  getSignoffDeclared: () => signoffDeclared,
  latestChip,
  loadMarked,
  midComposition,
  notifyDataSubscribers,
  observeServerNow,
  paintAnchors,
  paintApproval,
  paintWorkLines,
  panelIsOpen,
  presented,
  reconcileState,
  refreshHover,
  replaceClaimState,
  renderOthers,
  renderPanel,
  renderStatus,
  renderVersions,
  reportPageError,
  restoreView,
  revisionDocument,
  runtime,
  sameLayer,
  setPanel,
  showComparison,
  showNews,
  showToast,
  snapshotVersionNavigation,
  settleAcceptedDrafts,
  stateSignoff,
  trackActivation,
  updateFab,
  versionMenuIsOpen,
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
// Where the reader stands, which is the half of an arrival the browser cannot answer on
// a page that moves its own scrolling: `html` is `overflow: hidden` so the document
// scrolls in `body`, and the browser scrolls whichever box it last saw the reader put
// themselves in — on a fresh load, none of them, so Space, PageDown and the arrows did
// nothing at all until the reader happened to click somewhere in the page. Literally the
// move the Escape ladder makes of letting go, since an arrival and a reader who has just
// put something down are standing in the same place; `letGo` carries the reasons, the
// focus rather than a blur among them, and CLAUDE.md's "The reader has to be standing
// somewhere" holds the rest.
//
// Here rather than in the start block below, which runs asynchronous upgrades with the
// chrome clickable throughout: a reader who took a control in that window would have it
// taken back off them. Main is withheld from paint, but body is the visible scroll box and
// can name itself to Chrome now.
letGo();
const { landArrival, savedView } = viewRuntime.installArrival({
  fragmentId,
  ready: () => anchoringReady,
  scrollToElement,
  tabStore,
});
const savedComposer = pendingComposer();

// ---------- start ----------
const PRESENTATION_WAIT_ANIMATION = "lf-presentation-wait";
const cssMilliseconds = (name) => {
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
  if (value.endsWith("ms")) return Number(value.slice(0, -2));
  if (value.endsWith("s")) return Number(value.slice(0, -1)) * 1000;
  return Number(value);
};

// One positive fact for the one presentation boundary. Success has applied the log;
// an unavailable first poll has painted the offline status and deliberately hands the
// authored page back. A caught startup failure cannot make that promise, so it leaves
// the fixed recovery surface in place rather than exposing decisions it never read. A
// fast answer releases before the delayed waiting surface can paint. Once that surface
// has started, its CSS animation is the clock and the CSS dwell is the budget: the message
// stays long enough to read instead of becoming the flash it was meant to prevent.
async function presentPage() {
  if (document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented)) return;
  const wait = document
    .getAnimations()
    .find((animation) => animation.animationName === PRESENTATION_WAIT_ANIMATION);
  const current = Number(wait?.currentTime);
  const delay = Number(wait?.effect.getTiming().delay);
  if (wait && Number.isFinite(current) && current >= delay) {
    const shownAt = (wait.startTime ?? document.timeline.currentTime - current) + delay;
    const releaseAt = shownAt + cssMilliseconds("--lf-presentation-dwell");
    // Timers are a wake-up hint, not the presentation clock: a browser may service one
    // a few milliseconds before its requested deadline. Re-read the CSS timeline after
    // every wake so the recovery message never loses the end of its promised dwell.
    while (document.timeline.currentTime < releaseAt) {
      await new Promise((resolve) =>
        setTimeout(resolve, releaseAt - document.timeline.currentTime),
      );
    }
  }
  document.body.setAttribute(PAGE_PAINT_ATTRIBUTE.presented, "1");
  // Repaint state-dependent chrome in this same task. The presentation attribute opens
  // the gate, replay is already complete, and no frame can expose the authored count or
  // an empty persisted tray between those facts.
  restoreTray();
  showNews(othersBtn, leavesOffered());
  paintKeys();
  document.dispatchEvent(new Event("lf-actions"));
  paintApproval();
  promoteDeferredModals();
}

// Upgrades flush before the anchor pass and the view restore, so quotes and reading
// positions are re-found in the enhanced DOM, not the pre-upgrade one. An async function,
// never top-level await: boot first publishes every factory-built owner capability, then
// imports the behavior modules that consume the public facade.
async function startPage() {
  await Promise.all([
    upgradeWidgets(),
    // Alongside rather than after, and caught rather than fatal: the tab icon is not
    // what the page is for, so a layer missing it says so in the console and leaves the
    // rest working — the same bargain a widget module that fails to import makes. It is
    // still awaited here, because `version export` copies the page at the stamp below
    // and a mark that arrived after it would leave the copy's tab to chance.
    loadIcon().catch((err) => console.error(err)),
  ]);
  // The box the page ends up with is not the one it started in, because a module may
  // change it while upgrading: a page with a change to decide gives up a rail of the
  // controls' own width, and lf-suggestion states that from the first row it builds,
  // which is long after the layout first ran. Every reader of the box is therefore
  // re-run here rather than left holding the pre-upgrade one — the room a wide widget
  // spends was the one that noticed, standing a diagram out over the rail on the first
  // shipped page to carry both.
  //
  // The observer watches that box now, so the standing answer is not this line's. What
  // is this line's is the timing: an observation is answered at the next rendering
  // update, which is a frame past the stamp below, and the stamp is where `version check
  // --render` and an exported copy read the page. So the observer keeps the room true for
  // the page's life and this makes it true at the moment the page is called finished,
  // which is what test_the_room_is_measured_after_a_late_rail holds it to. The strip is
  // stated first, being padding on the box the room comes off.
  stateStrip();
  syncLayout();
  // Before the first poll's replay: the authored facets are the markup's
  // initial condition, and replay is about to overwrite them in the DOM.
  captureAuthoredFacets();
  buildBulkAnswers();
  syncAsks();
  anchoringReady = true;
  paintAnchors(); // an early general post may already have loaded anchored threads
  updateFab(); // an early selection is now read from the fully upgraded page
  paintHere(); // c is live again, whether or not that selection raised the button
  landArrival();
  if (savedView && savedView.revision < runtime.currentRevision)
    showToast(`Updated to ${runtime.currentLabel}`);
  if (savedComposer)
    openComposer(
      savedComposer.anchor,
      savedComposer.text,
      (innerWidth - 320) / 2,
      64,
      Boolean(savedComposer.suggest),
      savedComposer.about ?? null,
    );
  // Start replay before stamping the document, preserving the two readiness facts, but
  // present neither half on its own. The first completed read — state or offline — is the
  // presentation boundary; only after it settles do the heartbeat and the stream begin,
  // so a held first request cannot be overtaken by a second answer and leave presentation
  // waiting on the wrong call.
  let presentationAttempt;
  const ensurePresentation = () => {
    if (!presentationAttempt)
      presentationAttempt = presentPage().finally(() => {
        presentationAttempt = null;
      });
    return presentationAttempt;
  };
  const present = async () => {
    if (!document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented))
      await ensurePresentation();
  };
  stateFeed.start(present);
  // Every widget has upgraded and every async one has settled, so the geometry and
  // the drawn SVG are final. `version export` copies the page at this moment and has no
  // other way to know it arrived: a load event fires before the modules run, and
  // networkidle only says a bundle finished downloading, not that it finished
  // drawing. The stamp says the document is done becoming itself.
  document.body.setAttribute(PAGE_PAINT_ATTRIBUTE.upgraded, "1");
}

startPage().catch((error) => {
  // The boundary itself must fail visibly. The fixed recovery surface stays in front:
  // this failure happened before the log was read, so the authored decisions underneath
  // are not an honest page to release.
  reportPageError(`page failed to start: ${error?.message ?? error}`);
  renderStatus(error);
});
