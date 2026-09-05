/* Leaf runtime, loaded via <script type="module" src="/leaf.js">: the boot module.
 * Every owner is a module that exports its capability and imports what it needs; this
 * file imports them and runs the boot sequence (CLAUDE.md: Startup and presentation).
 * Nothing here is a capability, and no owner imports this file back.
 *
 * Owners may not read each other as they evaluate; the rule and its remedies are under
 * Runtime ownership in CLAUDE.md.
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
 * the leaf.validation package); it is never inferred from the markup's silence. Widgets opt in via a
 * renderState(state) method stating an absolute value, so a reload keeps the
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
 * Composing: every composition textarea behaves identically — saves its draft on each
 * keystroke and submits its contextual action on ⌘/Ctrl+Enter — because runtime and
 * widget composition boxes are all wired through wireInput. Direct editors register the
 * same Enter and Mod+Enter meanings with their additional commands. Growing with
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

import chromeSheet from "./runtime/chrome.css" with { type: "css" };
import { syncLayout } from "./runtime/chrome-layout.js";

import { leavesOffered } from "./runtime/live-leaves.js";

import { openComposer, pendingComposer } from "./runtime/composing/selection.js";
import { updateFab } from "./runtime/composing/surface.js";

import { runtime } from "./runtime/context.js";
import { promoteDeferredModals } from "./runtime/deferred-modals.js";
import { reportPageError } from "./runtime/layer-client.js";

import { buildBulkAnswers, syncAsks } from "./runtime/asks/view.js";

import { paintHere, paintKeys, paintsHere } from "./runtime/keyboard/scopes.js";
import { paintStandingChrome } from "./runtime/standing.js";

import { notice } from "./runtime/notifications.js";

import { setAnchoringReady } from "./runtime/anchors.js";
import { loadIcon, paintApproval, renderStatus } from "./runtime/banner.js";
import { showNews } from "./runtime/banner-shelf.js";

import { renderPanel } from "./runtime/conversation/reconcile.js";

import { beginRead, startFeed } from "./runtime/state-feed.js";

import { installArrival } from "./runtime/version.js";
import { upgradeWidgets } from "./runtime/widget-loader.js";

import { PAGE_PAINT_ATTRIBUTE } from "./runtime/presentation.js";

import { marksSheet } from "./runtime/shadow.js";

import { othersBtn, restoreTray } from "./runtime/trays.js";
import { letGo } from "./runtime/keyboard/page.js";
import { mountChrome } from "./runtime/chrome.js";
import { restoreArrangements } from "./runtime/arrangements.js";
import { captureAuthoredFacets } from "./runtime/projection/authored.js";

// The register's repaint frame paints the standing chrome: registered here, first,
// because the painter imports every owner and no owner may import it.
paintsHere(paintStandingChrome);

// ---------- styles ----------
// The chrome's sheet and the marks' arrive as CSS modules: part of the import graph, so
// both are constructed before this module's first line runs, and adopted rather than
// written into the head, so a version activation's head reconciliation never meets
// them. shadowStage adopts the marks into every root it builds; the bake writes both
// into a <style> for a copy, which has no module graph to carry them.
document.adoptedStyleSheets = [chromeSheet, marksSheet];

mountChrome();

// The server can build the authoritative page state while the browser loads and settles
// the registry's widget modules. Its answer stays buffered until startPage has captured
// the upgraded authored facets that replay starts from.
const initialStateRead = beginRead();

// A fresh arrival starts on the page, the same stable focus destination the Escape ladder
// uses after chrome. Root scrolling no longer depends on this handoff; focus ownership
// still does, since Space on a button presses it rather than scrolling the document.
//
// Here rather than in the start block below, which runs asynchronous upgrades while the
// authored document is already readable: body can name the page now, and stateful widget
// controls remain unavailable until presentPage crosses their semantic boundary.
restoreArrangements();
letGo();
const { landArrival, savedView } = installArrival();
const savedComposer = pendingComposer();

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
  setAnchoringReady(true);
  try {
    renderPanel();
  } catch (error) {
    setAnchoringReady(false);
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
// async function, never top-level await: every owner has evaluated before boot runs, and
// the behavior modules that consume the public facade are imported after it.
async function startPage() {
  const [upgraded] = await Promise.all([
    upgradeWidgets(),
    // Alongside rather than after, and caught rather than fatal: the tab icon is not
    // what the page is for, so a layer missing it says so in the console and leaves the
    // rest working. It is still awaited here, because `version export` copies the
    // page at the stamp below, and an icon arriving later would leave the copy's
    // tab to chance.
    loadIcon().catch((err) => console.error(err)),
  ]);
  if (!upgraded) return;
  syncLayout();
  // Before the first poll's replay: the authored facets are the markup's
  // initial condition, and replay is about to overwrite them in the DOM.
  captureAuthoredFacets();
  buildBulkAnswers();
  syncAsks();
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
  startFeed(presentPage, initialStateRead);
}

startPage().catch((error) => {
  // The boundary itself must fail visibly. Authored HTML remains readable, while the
  // status names the fault and the absent presented stamp keeps durable controls closed.
  window.dispatchEvent(new Event("lf-startup-failed"));
  reportPageError(`page failed to start: ${error?.message ?? error}`);
  renderStatus(error);
});
