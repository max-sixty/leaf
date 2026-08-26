/* Leaf runtime, loaded via <script type="module" src="/leaf.js">: one module
 * owning both the widget layer and the comment layer.
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
 * live view is the version plus every action recorded up to it, replayed on each poll:
 * authored markup is what a widget was before anyone touched it, the log is every
 * transition since, and the log wins. A decision therefore outlives the version it
 * was made on, without the page's author having to copy it into the next one by
 * hand. When a version does mean to overrule one — the content the decision was
 * about got rewritten — `version check` makes the author say so (see restatement_errors in
 * leaf/validation.py); it is never inferred from the markup's silence. Widgets opt in via an
 * applyAction(action, detail) method stating an absolute value, so a reload keeps the
 * user's drag and a second tab follows along live.
 *
 * Comment layer: talks to interact.py's server — polls GET /api/state, posts events to
 * POST /api/event. Everything it injects is namespaced .lf-* and marked .lf-ui, and it
 * styles itself from the theme's tokens so it themes with the page.
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
 * marked. `offer` builds every press as a span wearing role="button" for that reason, and
 * wires the keys the UA would have given it.
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
 * Versions: the live page at `/` follows the newest version in the same document. It
 * fetches the next immutable file, upgrades and replays it behind a view-transition
 * boundary, then restores the reader's semantic landmark. Picking an older version
 * leaves the live page for that immutable file and pins it (?pin in the URL). One control
 * on the bar holds all of it — the version being read, the list of the rest with what each
 * changed, and the press on any older one that marks that change on the page.
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
 * One key sequence exists: g arms a mode in which a letter names one of the page's
 * lists — its comments, its asks, its links — and a digit is a place in that list,
 * so `g c 2` is the second reply box and `g l 3` the third link on screen; `g g` and
 * `g G` are the page's own edges, the top and the bottom, addresses with no list to name.
 * Which lists there are is one table (ADDRESSES) and no consumer branches on which one is
 * aimed at.
 * Arming shows the whole offer: everything addressable the reader can see wears its whole
 * address as a chip — `g c 1`, `g l 2` — with the keys already pressed dimmed, so the chip
 * states both which member this is and what is left to type. A letter then narrows the
 * chips to its own list, and reveals that
 * list where it draws nothing until asked. Any other key disarms the window and keeps its
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
import { createInput } from "./runtime/composing/input.js";
import {
  composerOpen,
  createSelectionComposer,
  pendingAbout,
  pendingAnchor,
} from "./runtime/composing/selection.js";
import { runtime } from "./runtime/context.js";
import { DESIGN_KEY, createDesign, designOn } from "./runtime/design.js";
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
import { createOutbox, outbox } from "./runtime/outbox.js";
import { createProjection } from "./runtime/projection.js";
import { createAnchors } from "./runtime/anchors.js";
import { createConversation } from "./runtime/conversation/reconcile.js";
import { createPassages } from "./runtime/passages.js";
import { createUpdates } from "./runtime/updates.js";
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
import {
  matchesWhen,
  registry,
  tagsDeclaring,
  widgetEntries,
} from "./runtime/registry.js";
import {
  MARK_RULES,
  createShadowStage,
  loadShadowRules,
  pageShadowRoots,
} from "./runtime/shadow.js";
import { VERSION_PATH, readerStore, tabStore, versionUrl } from "./runtime/storage.js";
import { highlightBlocks } from "./runtime/syntax.js";

// ---------- widget layer ----------

export const agentName = () => runtime.agent;

async function undoLast(...args) {
  return runtimeProjection.undoLast(...args);
}

// The document roots may carry authored classes, data attributes, and inline custom
// properties that page-local styles read. The live document also paints its own facts
// onto those same two elements. Remember exactly the authored share before the runtime
// writes anything so a version activation can replace that share without erasing the
// presentation, layout, and mode facts the surviving runtime owns.
const authoredAttributes = (root) =>
  new Map([...root.attributes].map(({ name, value }) => [name, value]));
let authoredHtmlAttributes = authoredAttributes(document.documentElement);
let authoredBodyAttributes = authoredAttributes(document.body);
const versionedHeadNode = (node) =>
  !(
    node.localName === "meta" &&
    node.getAttribute("name") === "lf-version" &&
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
let authoredHeadNodes = new Set([...document.head.children].filter(versionedHeadNode));

// A modal is promoted into the top layer and makes the rest of the document inert. Both
// facts escape an ancestor paint gate: hiding it with CSS alone would still disable the
// Comments chrome that deliberately remains usable while first replay waits. Custom
// widgets load after this module, so turn authored-main showModal() calls into measurable,
// non-modal dialogs until replay has produced the page. A widget can still close one
// while waiting; only a connected, still-open dialog whose post-replay place is visible
// is promoted, so replay retiring its authored branch cannot resurrect stale UI on top.
const nativeDialogShow = HTMLDialogElement.prototype.show;
const nativeDialogShowModal = HTMLDialogElement.prototype.showModal;
const nativeDialogClose = HTMLDialogElement.prototype.close;
const deferredModals = new Set();
const inAuthoredMain = (node) => {
  const main = document.querySelector("body > main");
  for (let at = node; at;) {
    if (at === main) return true;
    if (at.parentElement) at = at.parentElement;
    else {
      const root = at.getRootNode();
      at = root instanceof ShadowRoot ? root.host : null;
    }
  }
  return false;
};
HTMLDialogElement.prototype.showModal = function () {
  if (
    !document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented) &&
    inAuthoredMain(this)
  ) {
    if (!this.open) nativeDialogShow.call(this);
    deferredModals.add(this);
    return;
  }
  return nativeDialogShowModal.call(this);
};
HTMLDialogElement.prototype.show = function () {
  deferredModals.delete(this);
  return nativeDialogShow.call(this);
};
HTMLDialogElement.prototype.close = function (returnValue) {
  deferredModals.delete(this);
  return nativeDialogClose.call(this, returnValue);
};
function promoteDeferredModals() {
  for (const dialog of deferredModals) {
    if (
      !dialog.isConnected ||
      !dialog.open ||
      !inAuthoredMain(dialog) ||
      !dialog.checkVisibility({ opacityProperty: true, visibilityProperty: true })
    ) {
      dialog.removeAttribute("open");
      continue;
    }
    // Removing the non-modal state directly emits no spurious close event; the widget
    // asked for one opening, and this is that opening finally becoming modal.
    dialog.removeAttribute("open");
    nativeDialogShowModal.call(dialog);
  }
  deferredModals.clear();
}
// One-shot guard for connectedCallback: re-connection (a parent wrapping or moving an
// already-upgraded child) must be harmless, so upgrade order can't matter.
export function once(el) {
  if (el.hasAttribute(PAGE_PAINT_ATTRIBUTE.done)) return false;
  el.setAttribute(PAGE_PAINT_ATTRIBUTE.done, "1");
  return true;
}

// A data widget's body: the <pre> the content model requires, never the element's own
// textContent. The two used to be the same string and are not once the element holds a
// child — an HTML formatter is free to put the <pre> on its own line, and the newline
// and indent before it are the element's text too. Line one is load-bearing in every
// notation here, so that indent is not untidiness downstream: a diff's file header, a
// tree's root and mermaid's graph type stop parsing, and a walkthrough's `hi` ranges
// and note anchors all point one line off.
export const dataBody = (el) => el.querySelector(":scope > pre").textContent;

// A failed upgrade becomes a visible error box rather than a blank page.
export function failSoft(el, err, source) {
  const box = document.createElement("div");
  box.className = "lf-error";
  box.textContent = `<${el.tagName.toLowerCase()}> failed: ${err?.message || err}`;
  if (source) {
    const pre = document.createElement("pre");
    pre.textContent = source;
    box.append(pre);
  }
  el.replaceChildren(box);
}

// The page's one door to the log, spelled once. Two callers reach it — `post`, which
// orders the reader's own gestures through it, and the error report below, which
// deliberately doesn't — and what they share is the request rather than anything about
// the sending: same path, same method, same encoding, so a door that moved would move
// for both. Whether a send waits on the one before it belongs to the caller.
const vendoredLayerGeneration = "__LEAF_LAYER_GENERATION__";
let layerGeneration = vendoredLayerGeneration;
let revealLayer;
const layerReady = new Promise((resolve) => (revealLayer = resolve));
let layerReloading = false;
function sameLayer(generation) {
  if (generation === layerGeneration) return true;
  if (!layerReloading) {
    layerReloading = true;
    location.reload();
  }
  return false;
}

const postEvent = async (event) => {
  await layerReady;
  const response = await fetch("/api/event", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Leaf-Layer": layerGeneration,
    },
    body: JSON.stringify(event),
  });
  const responseGeneration = response.headers.get("Leaf-Layer");
  if (response.ok && responseGeneration && !sameLayer(responseGeneration)) return null;
  return response;
};

// The page reporting itself broken, to the party who can fix it: the agent
// authored the page and its widgets, and before this the only route for a
// live-session fault was the reader pasting a console nobody told them to
// open. The event lands in the log as kind "error", author "page" — the
// watcher hears it beside comments and reports; the reader's pending count
// never claims it. Deduped per message per load (a reload may repeat one —
// bounded noise over silence), capped so a fault in a loop cannot flood the
// log, and sent bare rather than through post(): a poll fault reporting
// itself through the poll would recurse, and nothing here needs the answer.
// Not part of the helper surface a module gets: an upgrade that throws is already on
// this path through window.error, and a widget that wants to say so itself has
// failSoft, which puts the message where the reader is looking.
const reportedErrors = new Set();
function reportPageError(text) {
  console.error(`leaf: ${text}`);
  if (reportedErrors.has(text) || reportedErrors.size >= 20) return;
  reportedErrors.add(text);
  postEvent({
    kind: "error",
    text,
    ...(runtime.currentVersion != null && { version: runtime.currentVersion }),
  }).catch(() => {});
}
window.addEventListener("error", (e) => {
  // Chrome also puts ResizeObserver loop notices on window.error without an
  // exception. This one live page cannot tell an occasional scheduling notice
  // from a layout feedback loop, so it persists neither in the reader's log. The
  // render gate and test navigation take one complete confirming reading and
  // report a notice that recurs there.
  if (e.message?.startsWith("ResizeObserver loop")) return;
  reportPageError(`${e.message} (${e.filename}:${e.lineno})`);
});
window.addEventListener("unhandledrejection", (e) => {
  // Chrome's stack embeds "Error: message"; Firefox's carries frames only, so a
  // stack alone can post an error event that never says what failed.
  const reason = String(e.reason);
  const stack = e.reason?.stack;
  reportPageError(
    !stack ? reason : stack.includes(reason) ? stack : `${reason}\n${stack}`,
  );
});

// An upgrade whose work is async (lf-diagram's mermaid render) registers its
// promise here, so the runtime can hold the view restore and first anchor pass
// until the page's geometry has settled. Rejections are the widget's own
// fail-soft path; settling ignores them.
const settling = [];
export function settle(promise) {
  settling.push(promise);
}

// A number a widget can only read off a box the browser has laid out. Three ship: the
// room a pick mark's word will need, the room a card keeps clear of its grip, the width
// of a roster's state column. Every one is measured rather than stated for the same
// reason — the face this page is actually set in, which no constant names across two
// platforms — and every one reads 0 where there is no box to read.
//
// A widget upgrades wherever the runtime connects it, and not every one of those places
// is drawn. A message body is built for every comment the log carries and connected
// whether or not the reader has opened the panel, and a shut panel is `display: none`:
// every box beneath it is zero. `once` then refuses the second upgrade that would put
// it right, and the body is cached for the life of the tab and never rebuilt — so a
// zero taken there is indistinguishable from a measurement and stands for good. A pick
// column collapsed to nothing, a grip drawn over the card's own title.
//
// So the module states the measurement and the runtime takes it: now, where there is
// something to read, and otherwise the first time there is. ResizeObserver is the
// browser's own answer to "this has a box now", and the one that answers it wherever
// the element sits — a message scrolled past the panel's own fold has been laid out
// just the same, which is the question an IntersectionObserver would get wrong.
//
// The observation ends at the reading it was waiting for, so what a measurement writes
// cannot return through what triggered it. The loop the page's other geometry writer
// guards against (syncLayout, and the rule stated with it) needs a second delivery to
// the element that was just written, and after the unobserve there is none.
const measurements = new WeakMap();
const drawn = (el) => {
  const box = shownBox(el);
  return Boolean(box.width || box.height);
};
const unmeasured = new ResizeObserver((entries) => {
  const taking = [];
  for (const { target } of entries) {
    if (!drawn(target)) continue;
    unmeasured.unobserve(target);
    taking.push(measurements.get(target));
    measurements.delete(target);
  }
  // Every one released before any of them is taken: a measurement writes room its own
  // widget spends, which resizes it, and a widget still observed when that happens is a
  // second delivery inside the round that wrote it.
  for (const take of taking) take();
});
export function measure(el, take) {
  // `shownBox`, not this element's own rect: a `display: contents` wrapper draws no box
  // of its own and never will, and its contents are what the measurement is about. Asked
  // the narrow way it would wait forever, holding the take and the observation with it.
  if (drawn(el)) {
    // A wait already standing for this element is over: it was waiting for the box
    // this reading just found. Left standing it would deliver a second reading of
    // the same number, which is harmless and still a claim that nothing was read.
    if (measurements.delete(el)) unmeasured.unobserve(el);
    return take();
  }
  measurements.set(el, take);
  unmeasured.observe(el);
}

// The theme's reduced-motion guard covers CSS animation and transitions; motion
// driven from JS — smooth scrolls here, Web-Animations moves in widgets — checks
// this instead.
export const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
export const SCROLL = REDUCED ? "instant" : "smooth";

// Web-Animations motion goes through here, so a reader who asked for stillness is
// answered in one place rather than by each widget remembering the check: null under
// reduce, and a caller treats "no animation" and "animation finished" as the same
// state. The board's FLIP and the folds (FOLD_MS) are the motions the product makes;
// they share one ease and one held-end-frame contract.
export function motion(el, keyframes, ms) {
  // First replay happens behind the presentation boundary. Its state should be the
  // first frame the reader sees, not a motion from authored state they never saw; it
  // collapses exactly as reduced motion does. This one shared check reaches folds and
  // FLIP alike without a widget learning whether the page has been presented.
  if (
    REDUCED ||
    runtime.projectingState ||
    !document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented)
  )
    return null;
  const played = el.animate(keyframes, {
    duration: ms,
    easing: "ease",
    fill: "forwards",
  });
  // Hold the last frame until the caller's direct `finished.then(cleanup)` has made
  // that frame true in DOM/CSS, then release the effect. The extra microtask is the
  // ordering: our reaction was registered first, so cancelling in it would expose the
  // unanimated box before the caller removed, hid or restated it. A FLIP has no cleanup
  // because its underlying placement already is its last frame; it still leaves no
  // filled animation behind. Cancellation is already the release, and the rejection
  // arm consumes it so an interrupted move reports no unhandled promise.
  played.finished.then(
    () => queueMicrotask(() => played.cancel()),
    () => {},
  );
  return played;
}

// How long room takes to go back. Long enough that the eye can follow a paragraph's
// worth of page closing, short enough that the act still reads as having happened at
// the press: the board's own FLIP is 150ms over a card's width, and this is a taller
// distance travelled by the whole column below it. One number, because the product
// makes this motion twice for one reason — a decided suggestion's retired slot and a
// resolved thread's place in the list are both room the reader watches come back —
// and two numbers would be that reason written down twice, free to disagree.
export const FOLD_MS = 220;

// Mention, not use: a widget inside one the registry marks x-exhibit is quoted
// material. An interactive widget consults this before wiring anything that would carry
// input back (a choose path, a drag grip), so an exhibit never takes the user's edits.
// Presentational upgrades and view state run regardless — a quoted diagram still
// renders, a quoted settled group still collapses.
export function quoted(el) {
  const exhibits = tagsDeclaring((entry) => entry["x-exhibit"]);
  return exhibits.length > 0 && el.closest(exhibits.join(",")) !== null;
}

// What a page's own markup works: a link to follow, a control to set, a disclosure to
// open, a player to start. HTML's interactive content is where this comes from rather
// than a list anyone here may add to, and it differs in two places, both about whether a
// click can arrive. `summary` stands for `details`, because only the summary is the press
// and the body under it is prose the reader may point at like any other. And nothing
// embedded (`iframe`, `embed`, `object`): a click inside one never crosses into this
// document, so listing them would guard a gesture no listener out here can see.
const WORKS = "a, audio, button, input, label, select, summary, textarea, video";

// A container that takes a gesture on its whole box has to tell one aimed at itself from
// one aimed at what it holds. This is the second: the nearest thing between `node` and
// `container` that has a use for the gesture, or null where the container is the aim.
//
// It exists because an option's case is now argued inside the option — a screenshot pair
// to flip, a disclosure to open, tabs to walk — while the whole card is what takes the
// pick. Reading the evidence then cast a vote: a click on a tab chose that option, and one
// on a shot's `after` radio chose it and cleared it again, two decisions the reader never
// made and only the log to show for them. Fail closed, because a pick is sent the moment
// it is made: a gesture nobody can prove was a choice is not one.
//
// Two vocabularies, because a container holds two kinds of thing. A widget it merely
// contains is its own world, and that is every lf-* tag bar the parts the registry says
// this container is made of (x-parent) — declared rather than listed, so the twelfth
// widget is covered by its entry and a widget whose gesture lands on its own words rather
// than on chrome (lf-draft's double-click) is covered with the rest. Inert ones go in with
// them: a diagram is evidence the reader studies with the pointer on it, and which
// evidence happens to carry a control is nothing they can see.
//
// `data-lf-offer` then catches the controls that belong to no widget — the runtime's own
// hidden line saying how many comments a block holds, which a screen reader reaches by
// Tab and which used to cast a vote on the way into the thread. It catches the container's
// own apparatus too, which no rule here could tell from the rest; a container excludes
// its own, being the only thing that can name them.
export function worksInside(node, container) {
  // The closure, not one level: "what this container is made of" includes a
  // part's own parts — a column's cards are the board's, and one level deep a
  // grandchild part would land in `held` and swallow the gesture.
  const parts = new Set([container.localName]);
  for (let grew = true; grew;) {
    grew = false;
    for (const tag of tagsDeclaring((entry) =>
      (entry["x-parent"] ?? []).some((parent) => parts.has(parent)),
    ))
      if (!parts.has(tag)) {
        parts.add(tag);
        grew = true;
      }
  }
  const held = tagsDeclaring(() => true).filter((tag) => !parts.has(tag));
  // `closest` walks past the container to the root, so a match has to be read back
  // against it: an ordinary pick on an option's prose finds the enclosing group, which
  // is a widget the option does not hold but is above it rather than inside it. And
  // `contains` counts an element as containing itself, so the container is ruled out by
  // name — the question is what stands between the two, and a container that is itself
  // a thing to work would otherwise answer with itself and never take a gesture again.
  // A local work line is runtime apparatus too. It may deliberately sit in one of
  // this container's declared parts, where the part is otherwise the gesture target;
  // reading or selecting the status must not cast that gesture on its way through.
  const inner = node.closest(
    [...held, WORKS, "[data-lf-offer]", ".lf-work-line"].join(","),
  );
  return inner && inner !== container && container.contains(inner) ? inner : null;
}

// The chrome a widget injects: a control, or the box that holds controls. Three
// markers, one per question asked of it — `lf-ui` for the runtime's look, which
// anchoring reads where no label speaks nearer; `data-lf-gen` so the diff looks away; `data-lf-offer`
// for a thing to work, which paper drops because there is nothing there to press.
// A widget writes none of the three by hand: they are what make an element chrome,
// and one of them going missing is invisible until something breaks.
//
// "button" names a thing to press, not the element. A real <button> is a wall a
// pointer's selection cannot cross — Chrome starts no selection inside a form
// control and `user-select: text` does not move it — so any word inside one is
// unreachable to a user whatever it is marked, and a control's label turns out
// to be one of the page's own words often enough (a tab's name, the card a settled
// group carries, the mark on a chosen option) that a widget cannot be trusted to
// have picked the element with that in mind. So a press is a span wearing the role,
// and the keys the UA would have supplied are wired once below. Nothing these controls
// do needed the element: no forms, no submit, and no `disabled` — which a widget's press
// therefore cannot have (the .lf-btn:disabled rule is the runtime's own buttons').
export function offer(tag, cls, label) {
  const press = tag === "button";
  const node = document.createElement(press ? "span" : tag);
  if (press) {
    node.setAttribute("role", "button");
    node.tabIndex = 0;
  }
  node.className = cls ? `${cls} lf-ui` : "lf-ui";
  node.dataset.lfGen = "1";
  // Whether this is a press, said in the one marker a widget has no reason to touch. The
  // tabindex cannot say it — every focus target wears one, and a conversation thread wears
  // one so j/k can land on it, which had the key line leading with "press it" over an
  // element that answers nothing. Nor can the role: `offer` writes `button` and a widget is
  // free to specialise it, which `lf-tabs` does (`role="tab"`), and reading the role took
  // Enter and Space off every tab — Space then scrolling the page out from under the
  // reader, which is the platform default this scope exists to consume.
  //
  // Every other consumer asks for the bare attribute, and `[data-lf-offer]` matches a
  // valued one, so this narrows what a press is without touching what chrome is.
  node.dataset.lfOffer = press ? "button" : "";
  if (label !== undefined) node.textContent = label;
  return node;
}

// The keys a <button> came with and a span does not — Enter and Space activate — are the
// CONTROL scope in the keyboard section below, one declaration covering every press any
// widget builds. It was a listener of its own, and the surfaces had no channel to it: the
// largest hole a survey of this runtime found was that Space activates nine classes of
// control across core and five widgets and only one of them ever said so. As a scope it is
// named once in the reference, and named on the line exactly while the reader stands on
// one — which is where the walk through the page's asks puts them.

// A drag that ends on a control is that selection's mouseup, not a press: the
// user was reaching for the words, and a control whose label is one of the
// page's own words is exactly where they reach. Here rather than in each widget,
// because `offer` is what made the thing pressable — the same reason the markers
// live there. A keyboard activation (detail 0) is never a drag.
//
// The question is whether *this* click's mouseup is where the selection stopped, so
// it reads the selection's focus end — the character the pointer was on when the
// button came up. Asking instead whether the selection contains the control is a
// question about the DOM, and it answers yes for any selection running over the
// control: a suggestion's row is the column's own child, in flow between the block
// holding the change and the next one, so a user who read across the change and
// then reached for Accept pressed a control that had gone dead — and stayed dead,
// because a press that refuses a drag (`user-select: none`) never collapses the
// selection that deadened it either.
// Which is a reading rather than this listener's own business, because the same press
// reaches things `offer` never made: the panel's quote, whose press travels the page to
// the passage, and the list's landing, which moves the card the words are on. Each was
// the same complaint in its own place — the reader drew across the words to take them
// and the page went somewhere.
// It asks only where the selection stopped, and not whether a press happened at all:
// which presses can be a drag is each caller's own question. A click carries the answer
// in `detail`, and a `pointerup` is a pointer by construction and carries no detail to
// read.
export function reachedForWords(el) {
  const sel = getSelection();
  return !!sel && !sel.isCollapsed && el.contains(sel.focusNode);
}

document.addEventListener(
  "click",
  (ev) => {
    if (ev.detail === 0) return;
    const control = ev.target.closest?.("[data-lf-offer]");
    if (control && reachedForWords(control)) {
      ev.stopPropagation();
      ev.preventDefault();
    }
  },
  true,
);

// A control's label, and which kind of word it is. Most are things to do — "Save",
// "choose", a grip — and go with the rest of the UI on paper, out of reach of a
// quote. Some are the page speaking: a pick mark reading "chosen" is the only place
// the page says which option it carries, and a tab's name is the panel's only name
// once the strip exists. One element wears both over its life, so the kind is
// restated on every write rather than settled at birth.
//
// This writes one marker and one only: data-lf-said, the page speaking. Anchoring
// takes it over the `.lf-ui` box around it — that box is a look, the chrome face, and
// it was standing in for a permission the user has no category for — and paper
// reads it beside data-lf-offer to keep a control whose label is one of the page's own
// words. data-lf-gen goes on either way, because the diff parses the base version
// unupgraded and would read any label as text that version lacked.
//
// It leaves data-lf-offer alone, which it used to clear. That attribute is what `offer`
// made: this is a control a widget injected, true for the mark's whole life however it
// is worded, and three passes ask it (print, the drag guard above, the render gate).
// Clearing it here made "paper drops this" the meaning and left the other two unable to
// see a control — a drag across a picked card's mark was a press again, and only
// lf-options' own guard on the card stood between that and clearing the pick.
//
// `says` has no default, because the answer a caller doesn't give is the one that
// costs a printed page its words, and silently. Refusing throws where the widget
// upgrades, which the console reports and the render gate reads back as a finding
// — the loud direction, in front of whoever wrote the label.
export function relabel(node, label, { says } = {}) {
  if (typeof says !== "boolean")
    throw new TypeError(
      `relabel(${label}): say whether this label is the page speaking`,
    );
  node.textContent = label;
  node.dataset.lfGen = "1";
  node.toggleAttribute("data-lf-said", says);
}

// Runtime-supplied data is a third kind of page word: it is neither prose the author
// put in the version nor apparatus the runtime asks the reader to operate. It belongs
// in `says` because the reader can point at it, and not in `wrote` because no version
// contains it. `projectData` states both facts on each rendered datum: data-lf-gen keeps
// it out of the authored reading, while data-lf-projection + data-lf-datum give it a
// logical identity that survives a renderer replacing its nodes.
//
// The source is the authored seat's id and the key is local to that seat. Keeping the
// pair in the DOM, rather than in a map beside it, preserves the document + log as the
// whole state model: records remain the caller's input, and this function owns only their
// current rendering. A module supplies fresh records on every call. `render` receives the
// prior node for the same key so an ordinary update can preserve focus and selection, but
// returning a replacement is valid—the anchor follows the key, not node identity.
//
// One projection owns all children of its root. Keys are required strings rather than
// coerced values: `1` and `"1"` becoming the same DOM attribute would silently merge two
// facts. The helper reconciles order without reinserting nodes already in place, then
// schedules the one shared anchor pass after the caller's synchronous projection work.
let dataPaintQueued = false;
function projectionChanged() {
  if (dataPaintQueued) return;
  dataPaintQueued = true;
  queueMicrotask(() => {
    dataPaintQueued = false;
    paintAnchors();
  });
}

export function projectData(root, records, keyOf, render) {
  if (!(root instanceof Element))
    throw new TypeError("projectData root must be an element");
  if (!root.id)
    throw new TypeError("projectData root needs an id to name its projection");
  if (!records?.[Symbol.iterator])
    throw new TypeError("projectData records must be iterable");
  if (typeof keyOf !== "function" || typeof render !== "function")
    throw new TypeError("projectData needs key and render functions");

  const prior = new Map();
  for (const child of root.children) {
    if (child.dataset.lfProjection !== root.id || !child.hasAttribute("data-lf-datum"))
      continue;
    const key = child.dataset.lfDatum;
    if (prior.has(key))
      throw new Error(`projectData(${root.id}) already renders duplicate key ${key}`);
    prior.set(key, child);
  }

  const keys = new Set();
  const nodes = new Set();
  const wanted = [];
  let index = 0;
  for (const record of records) {
    const key = keyOf(record, index);
    if (typeof key !== "string" || !key)
      throw new TypeError(
        `projectData(${root.id}) key ${index} must be a non-empty string`,
      );
    if (keys.has(key))
      throw new Error(`projectData(${root.id}) received duplicate key ${key}`);
    keys.add(key);
    const node = render(record, prior.get(key) ?? null, index);
    if (!(node instanceof Element))
      throw new TypeError(`projectData(${root.id}) render(${key}) returned no element`);
    if (node === root || nodes.has(node))
      throw new Error(`projectData(${root.id}) render reused the node for key ${key}`);
    nodes.add(node);
    node.dataset.lfGen = "1";
    node.dataset.lfProjection = root.id;
    node.dataset.lfDatum = key;
    wanted.push(node);
    index++;
  }

  // A projection's children are its rendering. Remove source whitespace or an old
  // non-element rendering first, then use the runtime's stable-child reconciler so a
  // node already in the right place is not detached and reinserted.
  for (const child of [...root.childNodes])
    if (child.nodeType !== Node.ELEMENT_NODE) child.remove();
  setChildren(root, wanted);
  projectionChanged();
  return wanted;
}

// A source value remains the server snapshot's to own. Subscribers name one input on
// their own widget; the declaration supplies its contract and the attribute where this
// page bound a concrete source. They receive a fresh JSON clone immediately, then
// whenever state asks subscribers to restate their reading, so a module cannot mutate
// the private accepted snapshot and a newly activated seat need not wait for the next
// poll.
// `projectData` remains the rendering boundary: this helper delivers records but writes no
// DOM and keeps no widget-specific cache.
export function watchData(element, input, callback) {
  if (!(element instanceof Element))
    throw new TypeError("watchData element must be a widget element");
  if (typeof input !== "string" || !input)
    throw new TypeError("watchData input must be a non-empty string");
  if (typeof callback !== "function")
    throw new TypeError(
      `watchData(${element.localName}, ${input}) callback must be a function`,
    );
  const declaration = registry[element.localName]?.["x-data"]?.[input];
  if (!declaration)
    throw new Error(
      `watchData(${element.localName}, ${input}) input is not declared by this widget`,
    );
  // Markup owns the binding. Capture it at mount so module code cannot turn a live
  // attribute mutation into an unvalidated rebind. Version activation mounts a new
  // element and therefore establishes a new subscription when authored markup changes.
  const source = element.getAttribute(declaration.source);
  const update = () => {
    if (!source) {
      callback(null);
      return;
    }
    const present = Object.hasOwn(runtime.data.sources, source);
    if (present && runtime.data.sources[source].contract !== declaration.contract)
      throw new Error(
        `watchData(${element.localName}, ${input}) expected contract ${declaration.contract}, ` +
          `but source ${source} carries ${runtime.data.sources[source].contract}`,
      );
    callback(present ? structuredClone(runtime.data.sources[source]) : null);
  };
  // Establish the subscription only after its first delivery succeeds. A package that
  // throws while mounting must not leave a listener behind to fail every later poll.
  update();
  document.addEventListener("lf-data", update);
  return () => document.removeEventListener("lf-data", update);
}

// Room for a word not yet said, taken from the words themselves. A control that will
// rewrite its own label ("✓ Accept" to "✓ Accepted", a count gaining a digit) must
// hold the widest word's room from the start, or the press rewrites the one line a
// press may not move. Stating that room as a number is a measurement that stops
// being true silently when the words or the font change, so the control measures the
// words instead — in its own box and its own computed face, at load — and floors
// itself there. The two sweeps (a press, and the poll) stay the check that the words
// listed here are the words the writers actually write.
//
// Measured in place: text-only controls, swapped and restored synchronously, so no
// frame paints mid-swap. Stood out of flow for the moment — absolute, hidden — so a
// control whose news hasn't arrived yet (display: none) measures all the same and
// its neighbours don't feel the fitting. Sized by its words alone while it stands
// there, its own width cleared along with its place: a stated width can mean "and grow
// past this" in flow — a table cell laid out at `width: 0` takes what its content
// needs — where out of flow it is simply obeyed, and the widest word then measures as
// whatever padding the control has.
//
// What it cannot stand out of is an ancestor that isn't drawn: display: none upward is
// nobody's box, and every word measures zero there. A control whose ancestors may be
// undrawn — anything a widget builds, since a widget upgrades wherever the runtime
// connects it and a shut panel is display: none — reserves from inside `measure`, which
// asks again the first time there is a box. A floor of zero is not a missing
// measurement to look at; it is the control holding no room at all.
export function reserve(control, labels) {
  const stood = { text: control.textContent, css: control.style.cssText };
  Object.assign(control.style, {
    minWidth: "0",
    width: "auto",
    display: "inline-block",
    position: "absolute",
    visibility: "hidden",
  });
  let widest = 0;
  for (const label of labels) {
    control.textContent = label;
    widest = Math.max(widest, control.getBoundingClientRect().width);
  }
  control.textContent = stood.text;
  control.style.cssText = stood.css;
  control.style.minWidth = Math.ceil(widest) + "px";
}

// The element the document scrolls: body, not the viewport (see the stylesheet below,
// and Scrolling in the module header). Anything that reads a reading position, sets
// one, or hands a scroll container to a library uses this — window.scrollY is always 0
// here, and document.scrollingElement still names the html element, which no longer
// scrolls. Vendored libraries that resolve the scroller themselves are the trap:
// SortableJS walks up from the dragged card and, on reaching body, hands back
// document.scrollingElement, so lf-board passes this in rather than letting it guess.
export const pageScroller = document.body;

let outboxRuntime;
export const actionAvailable = (...args) => outboxRuntime.actionAvailable(...args);
export function sendAction(...args) {
  return outboxRuntime.sendAction(...args);
}
export function actionStands(...args) {
  return outboxRuntime.actionStands(...args);
}
function accountOutbox(...args) {
  return outboxRuntime.accountOutbox(...args);
}
function removeOutbox(...args) {
  return outboxRuntime.removeOutbox(...args);
}
function post(...args) {
  return outboxRuntime.post(...args);
}

// The page seat of a widget's conversation (x-conversation). A module places the seat;
// the comment layer fills it from the whole log. Before a thread exists it is a box for
// an answer the widget's own controls do not cover. Sending starts an ordinary comment
// thread anchored exactly on the widget; the next poll replaces the box with that same
// thread's inline textual view, while the panel keeps the complete view including any
// interactive reply markup.
//
// A widget standing inside a thread gets no seat: the containing thread already owns
// the reply box, and no version carries the nested widget id an anchored root would need.
// The declaration is checked at the helper boundary so a module cannot quietly place a
// conversation for a tag whose registry says nothing about one.
export function conversationBox(el, hint) {
  if (inChrome(el) || quoted(el)) return null;
  const declaration = registry[el.localName]?.["x-conversation"];
  if (!declaration || !matchesWhen(el, declaration.when))
    throw new TypeError(
      `<${el.localName}> placed a conversation outside its x-conversation predicate`,
    );
  if (!el.id)
    throw new TypeError(`<${el.localName}> needs an id to own a conversation`);
  const box = offer("div", "lf-conversation");
  box.dataset.lfConversation = el.id;
  const row = offer("div", "lf-say");
  const ta = offer("textarea");
  const send = offer("button", "lf-btn primary", "Send");
  const hold = declaration.hold ? offer("button", "lf-btn", declaration.hold) : null;
  const ctx = "say:" + el.id;
  ta.value = loadDraft(ctx) ?? "";
  ta.setAttribute("aria-label", hint);
  row.append(ta, send, ...(hold ? [hold] : []));
  const sendComment = (text, raw, holds = false) =>
    sendDraft(
      ctx,
      () => ta.value === raw,
      (attempt) =>
        post({
          kind: "comment",
          version: runtime.currentVersion,
          anchor: { section: el.id },
          text,
          attempt,
          ...(holds && { holds: el.id }),
        }),
    );
  const sync = wireInput(ta, {
    hint,
    sends: "send",
    sendBtn: send,
    altBtn: hold,
    save: (v) => saveDraft(ctx, v),
    send: async (text, raw) => {
      if (!(await sendComment(text, raw))) return;
      showToast(`Sent to ${runtime.agent}`);
    },
    altSend: hold
      ? async (text, raw) => {
          if (!(await sendComment(text, raw, true))) return;
          showToast(`Sent to ${runtime.agent} — goal paused`);
        }
      : null,
  });
  sync();
  // Keep the first-message box reachable even while an existing exact-section
  // thread has displaced it. A draft edited in another tab can then restore the box
  // instead of surviving only in storage with no surface left to send it from.
  box.lfFirstMessage = row;
  const off = watchDraft(ctx, (value) => {
    if (!box.isConnected) return off();
    const text = value ?? "";
    if (ta.value !== text) ta.value = text;
    sync();
    renderPanel();
  });
  box.append(row);
  return box;
}

// Transient confirmation ("Moved to Doing — sent to Claude"), styled and placed by
// the comment layer. Announced too: toast routes through the live region.
export function toast(msg) {
  showToast(msg);
}

// Announce to assistive tech without a visual: the runtime's polite live region.
// Cleared first so repeating a message (two identical moves) re-announces.
export function announce(msg) {
  liveEl.textContent = "";
  setTimeout(() => (liveEl.textContent = msg), 30);
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
//   keys  — the bindings it answers: "d", "Escape", "Mod+Enter", "Shift+a", " ".
//           A function where the set is the page's (an option group's 1–N).
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
//   repeat— whether holding the key repeats the press. Off by default: a held `]` was a
//           page navigation per repeat, and a held pick a `choose` per repeat.
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

// Which platform's spelling, and which modifier is the chord's. Up here rather than beside
// the text inputs because the spelling table below is the first thing that needs it.
const MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

// How a key is spelled, in one column. The line said "esc" where the overlay said "Esc"
// for the same binding, and lf-options declared one pair of arrows twice, as "↑ / ↓" and
// "↑ ↓" — which is what a spelling kept per surface costs.
const GLYPH = {
  Enter: "⏎",
  " ": "space",
  Escape: "esc",
  ArrowUp: "↑",
  ArrowDown: "↓",
  ArrowLeft: "←",
  ArrowRight: "→",
  Home: "home",
  End: "end",
  Tab: "⇥",
  // Mod is the platform's own send modifier, and the matcher takes either it or Ctrl
  // (below): the chip says ⌘⏎ on a Mac and Ctrl+⏎ answers there too. A key that works
  // beyond what a surface promises is not a surface promising what does not work, which
  // is the rule this layer keeps.
  Mod: MAC ? "⌘" : "Ctrl",
  Shift: MAC ? "⇧" : "Shift",
  Alt: MAC ? "⌥" : "Alt",
};
// The modifiers the matcher implements, which is the whole of what a binding may carry.
// Read off `answers` rather than chosen here, so the list cannot claim more than the
// dispatcher does — a fourth name would have to be taught to both.
const MODIFIERS = ["Mod", "Alt", "Shift"];
// The same modifiers as the platform's own keydowns: what `ev.key` says when a modifier
// goes down alone, ahead of the key it modifies. The dispatcher's chord asks this to tell
// half a press from a key of its own.
const MODIFIER_KEYS = ["Shift", "Alt", "Control", "Meta"];
// One reading of a binding's syntax, for the three questions asked of it: how it is
// spelled, whether a press answers it, and whether a text box's letters cover it. Three
// hand-agreed splits is one representation too few — the moment one of them had to state
// the modifier set, the other two were free to disagree about what a modifier is.
const parsed = (binding) => {
  const mods = binding.split("+");
  return { key: mods.pop(), mods };
};
// A modifier joins its key with nothing between them where its glyph is a symbol and with
// a + where it is a word, so "⌘⏎" and "Ctrl+⏎" are each their own platform's spelling.
// Shift on a letter is the letter's own uppercase, which is how a keyboard draws it and
// how this page's reference always has: the binding says Shift+a because that is what the
// dispatcher must ask for, and the chip says A because that is what the reader presses.
const spell = (binding) => {
  const { key, mods } = parsed(binding);
  if (mods.length === 1 && mods[0] === "Shift" && /^[a-z]$/.test(key))
    return key.toUpperCase();
  return mods.reduceRight((rest, mod) => {
    const glyph = GLYPH[mod] ?? mod;
    return /^\w/.test(glyph) ? `${glyph}+${rest}` : `${glyph}${rest}`;
  }, GLYPH[key] ?? key);
};
// A cell is read where it is painted, never where it is written, so it may be a function
// of the page. That is what lets a key whose meaning moves say the meaning it has: the
// surfaces render this press rather than the set of presses the key could be.
const word = (cell) => (typeof cell === "function" ? cell() : cell);
const bindings = (row) => word(row.keys) ?? [];
// A row's rendering is made of its own bindings, so it cannot advertise a key it does not
// answer. Three rows existed only to carry a partner key — `u`, `k` and `]`, each
// invisible on both surfaces and reachable only through a sibling's hand-typed "d / u" —
// and folded into the rows that name them when this replaced those labels.
export const labelOf = (row) => word(row.label) ?? bindings(row).map(spell).join(" / ");
// Whether a row is live right now, asked through one predicate by the dispatcher, the line
// and the overlay alike, so no surface can promise a press the dispatcher refuses. A guard
// inside `run` instead is a liveness no surface can see.
const live = (row) => !row.when || row.when();

// Does this press answer this binding? Modifiers are matched exactly, so ⌘D is the
// browser's bookmark rather than half a page down, and ⌥ stays the aim chord's alone.
//
// A letter matches on its lowercase with Shift asked for separately, because caps lock
// writes an uppercase key out of an unshifted press and reads an unshifted one out of a
// shifted press. Read off the glyph, `A` would be the answer that ends the matter for
// every ask on the page: a reader with caps lock on gets it from a bare letter they
// meant as a letter, and can no longer reach it with the Shift the chip names. Asking
// for the modifier is what makes the chip true in both directions.
function answers(binding, ev) {
  const { key, mods } = parsed(binding);
  if (mods.includes("Mod") !== (ev.metaKey || ev.ctrlKey)) return false;
  if (mods.includes("Alt") !== ev.altKey) return false;
  const shift = mods.includes("Shift");
  if (key.length === 1 && key.toLowerCase() !== key.toUpperCase())
    return ev.key.toLowerCase() === key.toLowerCase() && ev.shiftKey === shift;
  // A punctuation key is reached with Shift on some layouts and without it on others
  // ("?" is Shift+/ here and a key of its own there), so its Shift is the layout's
  // business rather than the binding's. A named key carries no such ambiguity — no layout
  // hides ArrowLeft behind Shift — so there the modifier is asked for exactly, the way it
  // is on a letter. Shift+→ is how a reader extends a selection through the words of a
  // <summary> they are standing on, and the laxity here was closing the section under
  // them and eating the extension.
  return key.length > 1
    ? ev.key === key && ev.shiftKey === shift
    : ev.key === key && (!shift || ev.shiftKey);
}

// Checked where a scope is declared, which is the edge this data enters at: a row that
// presses must carry the word the line says over it. This is the whole failure the
// register was built for, wearing its smallest form — `d`/`u` stepped half a page for as
// long as the runtime has had them and no always-visible surface ever named them, because
// the word was an optional field and its absence read exactly like a decision. So the
// absence is refused rather than defaulted: falling back to the reference's sentence would
// have kept the row visible and spent the room of the four behind it, and there is nothing
// to compute a short word from. A row with no `run` is asked for none, since the press it
// names is not the runtime's — it either belongs to the platform, and says a word anyway
// because Enter really does open the focused leaf, or it is not a key at all.
// The other way a declaration can promise a press nothing will make, and the quieter one.
// `answers` asks after the three modifiers by name and treats every other prefix as absent,
// so a binding written `Ctrl+k` or `Cmd+Enter` is not a key that never fires — it is a
// different key that does. `Ctrl+k` spells itself "Ctrl+k" on both surfaces, matches a bare
// `k`, and refuses the press the chip is naming. A key on screen is a key that works, and
// nothing was reading the half of a binding that decides which key it is.
function checked(rows, where) {
  rows.forEach((row, i) => {
    if (row.run && !row.line)
      throw new Error(
        `leaf: row ${i} of ${where} presses with no word for the key line`,
      );
    for (const binding of bindings(row))
      for (const mod of parsed(binding).mods)
        if (!MODIFIERS.includes(mod))
          throw new Error(
            `leaf: row ${i} of ${where} binds ${binding}, and ${mod} is no modifier ` +
              `this dispatcher answers (${MODIFIERS.join(", ")})`,
          );
  });
  return rows;
}

// What activates a focused button, stated once because it is the platform's fact and not
// any one row's. Five rows spelled it by hand — the runtime's own control scope, a card
// grip in each of its two states, an option's pick mark, and the version menu's row — and
// the fifth spelled it short, naming Enter over a real <button> that answers Space too. A
// near-copy that has to change whenever the original does is a primitive not yet extracted,
// and the drift here was invisible: the key worked and the page under-promised it.
//
// A link is the case that keeps this honest. Enter follows an <a> and Space scrolls the
// page, so the leaves tray binds Enter alone and is right to — the shared fact is what a
// button answers, not what a control does.
export const PRESS = ["Enter", " "];

// A clamped walk over a list of focusable rows: the row `dir` steps to from wherever
// focus stands, or the end it is already on. Clamped rather than wrapping, because ↓ on
// the last row must land where it already stands — the press stays the panel's, so the
// list doesn't scroll out from under a walk that reached its end, which is also how j/k
// walks threads. A walk that wraps is a fact about that walk (lf-tabs, per the ARIA tabs
// pattern) and states its own; this is the one two panels share. It hands back the row it
// landed on, for a walk that does more than move — the versions menu states a comparison
// from it, and against the row focus was on, since the clamped press moved nothing.
const walkRows = (rows, dir) => {
  const row =
    rows[
      Math.max(0, Math.min(rows.length - 1, rows.indexOf(document.activeElement) + dir))
    ];
  row?.focus();
  return row;
};

// Where a disclosure keeps which way it stands, in both spellings. Declared up here
// because `shadowStage` calls it, far above the key line it repaints for.
const disclosureWatch = new MutationObserver(() => paintHere());
const watchDisclosures = (root) =>
  disclosureWatch.observe(root, {
    subtree: true,
    attributeFilter: ["open", "aria-expanded"],
  });
const shadowStage = createShadowStage(watchDisclosures);
export { shadowStage };

// The scopes declared against an element — a WeakMap, so a scope leaves with the element
// that owns it — and, for the overlay, their rows gathered under each title. A section is
// its sentences: the tenth grip on a page says what the first one says, so it is one
// section, while a widget whose keys are declared in two places (a draft's way in, and the
// editor it opens) contributes to one section from both.
// Two contributors to one section are live where either is, and the reader is in it where
// either says so — a `when` or an `at` nobody wrote means always, which is what makes the
// first contributor's silence carry rather than the second's answer.
const either = (a, b) => (a && b ? () => a() || b() : undefined);
// The same or, for a predicate whose silence means no rather than yes: what any contributor
// claims, the section claims. `either`'s identity is the wrong one here, and using it was
// this file's own bug one field over — a scope's claim deleted by a contributor that stated
// none, which is what `In a text box` is, the typing scope claiming the keys that put a
// character in a box and every wired box contributing a second section under its title
// claiming nothing. Takes the binding its callers take, where `when` and `at` take none.
const anyOf = (a, b) => (a && b ? (...args) => a(...args) || b(...args) : (a ?? b));
const elementScopes = new WeakMap();
// The weak map is the dispatcher's lookup. The reference also has to enumerate every
// connected contributor, so keep weak references beside it. A live-version replacement
// can then be collected, while an element temporarily moved out of the document keeps
// its declaration when it reconnects. Holding the elements or merged closures here
// retained an entire prior version.
const scopeRefs = new Set();
const scopeRefFor = new WeakMap();
const pruneScopedElements = () => {
  for (const ref of scopeRefs) if (!ref.deref()) scopeRefs.delete(ref);
};
function rememberScopedElement(el) {
  if (scopeRefFor.has(el)) return;
  const ref = new WeakRef(el);
  scopeRefFor.set(el, ref);
  scopeRefs.add(ref);
}
const sentence = (row) => (typeof row.does === "string" ? row.does : row);
const bySentence = (rows) => rows.map((row) => [sentence(row), row]);
// One section per title, gathered from every contributor. Written once because the gathering
// happens twice and used to be spelled three times: here at declaration, where a widget's
// contributors arrive an upgraded element at a time, and at each open of the reference, where
// core's scopes and the widgets' are gathered into one list of sections. The rules above are
// this function — rows keyed by sentence, `when` and `at` joined by or — and a near-copy of a
// merge is a merge that drifts on the day one of the three learns something.
function merge(sections, { title, when, at, claims, rows }) {
  // A contributor the page hasn't got brings nothing. A section's `when` is the OR of its
  // contributors, so a live one otherwise carried a dead one's keys into the reference
  // under the shared title — the versions menu named a walk on a page with one version,
  // where the only key it really has is the way out. That is the same "a key on screen is
  // a key that works" the row `when` keeps for the line, asked one level up, and it is
  // what lets two capabilities of different liveness share a heading: the walk states
  // "somewhere to step" and the mode carrying the Escape states "there is a menu", which
  // is what a layer's way out has to hold wherever the layer does.
  //
  // Asked here rather than at the reader, because the section is built once per open —
  // declaredStack has one caller, showHelp — where a `when` may be the whole event log
  // folded and the line's own walk avoids it for exactly that reason.
  if (when && !when()) return;
  const seen = sections.get(title);
  if (!seen) {
    sections.set(title, { title, when, at, claims, rows: new Map(rows) });
    return;
  }
  for (const [key, row] of rows) seen.rows.set(key, row);
  seen.when = either(seen.when, when);
  seen.at = either(seen.at, at);
  // The claim travels because the reference reads it: a section that takes the keyboard
  // whole is one the reader is in or is not near at all, and its rows are then read by
  // their own liveness (showHelp). Dropped here, the chord's section arrived claiming
  // nothing, was listed whole, and named a list the page had not got — a fact stated on
  // the scope and lost on the way to the one surface that asks for it.
  seen.claims = anyOf(seen.claims, claims);
}

/** Declare a scope's keys where the code implementing them is.
 *
 * `where` is the element focus must be inside, `title` names the scope in the "?" overlay
 * (null for one the reference has no room to name), `rows` are its bindings, and `when` is
 * whether the page has this scope at all.
 *
 * A scope's `when` and a row's `when` are different questions, and keeping them apart is
 * what lets one declaration feed both surfaces. The scope's is the capability — does this
 * machine have neighbours to walk, does this page have a second version — and it gates the
 * reference. The row's is whether this press would move now — is a card held, has this
 * thread a box to reply into — and it gates the line, where the reader is standing in the
 * scope and can see the answer. So the reference names `x` wherever the page has threads,
 * which is what a reader learning the keyboard needs, and the line offers it only on a
 * thread that has something to resolve, which is what "a key on screen is a key that
 * works" asks for. One `when` answering both left `x` and Enter live over the whole page,
 * where the press no-opped.
 *
 * A control whose keys change with its state declares every state's rows at once, each
 * gated by its own row `when`, and calls paintKeys() when the state moves — a grab is
 * Enter on an already-focused grip, so no focus event would repaint the line.
 *
 * Registering at upgrade rather than at module load is what keeps the reference honest:
 * every x-upgrade module loads on every page, so a scope declared at the top level is help
 * for a widget the page hasn't got. The dispatch scope leaves through the weak map; the
 * enumerable reference prunes its element when it disconnects. A connected control that
 * stops answering a key says so in the row's `when`, where every surface can read it.
 *
 * Returns the rows, so a widget that says its own keys out loud — a grip announcing what a
 * grabbed card answers — reads them back off the declaration rather than restating them.
 */
export function keys(where, title, rows, when) {
  elementScopes.set(where, {
    title,
    el: where,
    rows: checked(rows, title ?? "a scope"),
    when,
  });
  rememberScopedElement(where);
  paintHere();
  return rows;
}
/** What a scope answers right now, as a listener hears it read out — key names rather than
 * the chips the eye reads, since a screen reader renders "esc" literally. Off the register,
 * so an announcement cannot name a key the rows stopped binding.
 */
export const saying = (rows) =>
  rows
    .filter(live)
    .map((row) => `${spoken(row)} ${word(row.line)}`)
    .join(", ");
// A row's own label where it has one, read the way every other surface reads a cell, and
// the bindings where it has none — which is what keeps a listener hearing "Escape" rather
// than the line's "esc". Asking whether the label was written as a string made the same fact
// announce two ways by accident: an option group's digits are spelled "1–3" because its label
// happens to be a string, while the chord's were read out as "1 or 2 or 3" because its label
// counts what the page holds and so has to be a function.
const spoken = (row) =>
  word(row.label) ??
  bindings(row)
    .map((b) => (b === " " ? "Space" : b))
    .join(" or ");
/** Repaint the surfaces after a state change no focus event reports. */
export const paintKeys = () => paintHere();

// Where the reader is standing, painted: the ring on the ask they are in, the mark on the
// passage of the comment they are in, and the line saying what the next press does from
// there. One repaint, because it is one question — every reading is of the focus and the
// open-ask list, and every signal that moves either (a focus move, an answer taken, a
// poll, a widget's own state) moves them all.
//
// Coalesced to a frame: a focus move is a focusout then a focusin, and painting between
// them would flash the scope of nowhere and drop the ring for a frame. Here rather than
// beside the renders it schedules, because the scopes core declares call it as the module
// evaluates, which is before the line has an element to draw into — the frame is what puts
// the first paint after both.
let herePending = false;
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
    renderLine();
  });
}

// Where the reader is standing, which is not what `document.activeElement` answers: focus
// inside a shadow tree retargets to the host, so every question the register asks about
// the focused element got the widget instead of the control. A staged control found no
// scope of its own, matched no control scope, and would have had a press aimed at its
// host. The climb out of a tree was written long ago (upFrom); the descent into one was
// not, and the comment below promised it anyway — lf-diff's per-file disclosure declared
// its keys and no surface said a word about them.
const focused = () => {
  let el = document.activeElement;
  while (el?.shadowRoot?.activeElement) el = el.shadowRoot.activeElement;
  return el;
};

// The element scopes covering a node, innermost first — the climb crosses a shadow
// boundary the way `closest` climbs inside one, so a widget staging its controls in a
// shadow tree declares them the same way.
function scopesFor(node) {
  const found = [];
  for (let a = node; a; a = upFrom(a)) {
    const scope = elementScopes.get(a);
    if (scope) found.push(scope);
  }
  return found;
}
// Whether the focused control has claimed Escape for itself. Asked of the control's own
// scopes and not of the stack, because both callers mean "this press already has an owner
// where the reader is standing": the chord refuses to arm there, and focus entering one
// disarms it. Every panel and mode in the runtime carries a rung of some kind, so a
// question asked of the whole stack would answer yes almost everywhere and the chord would
// never arm at all.
const claimsEsc = (node) =>
  scopesFor(node).some((scope) =>
    scope.rows.some((row) => live(row) && bindings(row).includes("Escape")),
  );

// How a widget collapses content it may need to show again (lf-tabs' inactive
// panels, a settled lf-options' cards): hidden="until-found", so find-in-page
// and fragment navigation still reach it — `beforematch` fires and the widget
// reopens what it owns. It is only a hide where the UA supports it (it rides
// content-visibility, and the theme's display:block outranks the boolean
// [hidden] rule) — without beforematch, fall back to plain boolean hidden,
// which the theme hides itself; the widget still collapses and reopens, ⌘F
// just can't see in.
export const HIDDEN = "onbeforematch" in document.body ? "until-found" : "";

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
// The file-side passage reader fences an upgraded element and each of its original
// direct children when the registry cannot promise its body is verbatim. Remember
// those parts before custom-element definitions can add or move anything, so the
// browser can stop captured context at the same seams after every upgrade has run.
const opaquePassageRoots = new WeakSet();
const opaquePassageParts = new WeakSet();

function rememberPassageParts(scope = document) {
  for (const tag of tagsDeclaring(
    (entry) => entry["x-upgrade"] && !entry["x-verbatim"],
  ))
    for (const root of scope.querySelectorAll(tag)) {
      opaquePassageRoots.add(root);
      for (const child of root.children) opaquePassageParts.add(child);
    }
}

async function upgradeWidgets() {
  const response = await fetch("/registry.json");
  if (!response.ok)
    throw new Error(`leaf: registry failed to load (${response.status})`);
  const responseGeneration = response.headers.get("Leaf-Layer");
  if (responseGeneration && !sameLayer(responseGeneration)) return;
  Object.assign(registry, await response.json());
  const registryGeneration = registry.$layer?.generation;
  if (typeof registryGeneration !== "string" || !registryGeneration)
    throw new Error("leaf: registry lacks $layer.generation");
  if (!sameLayer(registryGeneration)) return;
  if (
    !registry.$events?.kinds ||
    !registry.$languages?.names ||
    !registry.$languages?.paths ||
    !registry.$tones?.names
  )
    throw new Error("leaf: registry lacks $events, $languages or $tones");
  revealLayer();
  rememberPassageParts();
  rememberAuthoredMarkup();
  markDeclared(document.body, MARKED_IN_PAGE);
  // Before the modules import, because a widget's first render asks for these rules and
  // an async stage would put every x-shadow widget's look a fetch behind its own nodes.
  if (tagsDeclaring((entry) => entry["x-shadow"]).length) await loadShadowRules();
  await Promise.all(
    tagsDeclaring((entry) => entry["x-upgrade"]).map((tag) =>
      import(`/widgets/${tag}.js`).catch((err) =>
        reportPageError(`widget ${tag} failed to load: ${err?.message ?? err}`),
      ),
    ),
  );
  settle(dress(document.body));
  // Importing defined the elements and ran their connectedCallbacks; async ones
  // registered their work via settle(). Wait it out so geometry is final.
  await Promise.allSettled(settling);
  // After the wait, because the box a widget scrolls is a box its module built: run this
  // with the rest of the upgrade and a diff's pre and a code block's are half there.
  reachScrollers(document.body);
}

// ---------- comment layer ----------

const VERSION_MATCH = location.pathname.match(VERSION_PATH);
const LIVE_ROOT = location.pathname.endsWith("/") && !VERSION_MATCH;
const servedVersion = document.querySelector(
  'meta[name="lf-version"][data-lf-runtime]',
)?.content;
runtime.currentVersion = VERSION_MATCH
  ? parseInt(VERSION_MATCH[1], 10)
  : servedVersion
    ? parseInt(servedVersion, 10)
    : null;
const PINNED = new URLSearchParams(location.search).has("pin");
// Sign-off is the page's ask, not standing chrome: the approve button exists only
// when the version declares <meta name="lf-review" content="sign-off"> — a plan or
// proposed change seeking assent. An informational page takes comments only, and
// nothing stands in the button's place there. A neutral "End leaf" did once, and it
// ended nothing it named: the server went on serving, the watcher went on waiting,
// the status was untouched, and the agent side still finished at `leaf status idle`.
// So the one control a page that asks nothing put in front of its reader offered
// them an ending it could not deliver. The declaration rides the document, so a
// pinned older version keeps its own ask.
let signoff = document.querySelector('meta[name="lf-review"]')?.content === "sign-off";
const POLL_MS = 2000;
// The width the panel stands at for a reader who has not moved its edge. 420 since
// threads carry questions — option rows are the one thread content that can't scroll or
// scale its width away, and 360 crowded them. A default rather than the width, because
// what a conversation needs is a fact about the conversation: a thread quoting a table
// wants room the same thread quoting a sentence does not, and only the reader looking at
// it knows which this is. So the edge is a thing they take hold of (`drawnEdge`), and
// this is where it stands until they do.
const PANEL_W = 420;
// How narrow they may draw it in. 320 is the narrowest window the panel is held to
// standing up in (test_a_thread_gives_its_reply_the_full_row_and_its_actions_the_next),
// so it is the narrowest width anything has laid a thread's reply box and its two
// actions out at; below it nothing says they still fit. Wanting the panel gone is what
// closing it is for, and narrowing it to nothing is not the same wish.
const PANEL_MIN = 320;
// The window under which yielding the strip is worse than being covered by it, as a
// query rather than a number, because three things ask it: the rule that takes the strip,
// the rule that hands scrolling to the sheet instead, and the runtime, for what follows
// from which of those the page is under. Written as the covering half, since that is the
// half the runtime asks about; the strip is its complement, spelled `not` where it is
// taken.
//
// Asked of the default width and not of the reader's own, so widening the panel can never
// flip the posture out from under the hand doing it: a panel dragged past half its window
// would otherwise stop standing beside the page and cover it instead, which is the whole
// page rearranging itself in answer to one pixel of a drag. What the reader's width does
// answer to is the edge's own `cap`, which holds it to the same bargain this line
// strikes — the page keeps at least what the panel takes — without putting the posture
// itself in play.
const COVERING = `(width <= ${PANEL_W * 2}px)`;
// The trays' edge, on the left, and everything said above said again for it: the width
// it stands at until the reader moves it, how narrow they may draw it, and the window
// under which a tray covers the page rather than standing beside it. The same bargain at
// the same ratio, because a reader who has learned one edge has learned the other.
//
// 220 is where the tray's own row stops being one. A leaf's row spends 45px before any
// word of the page's — the status dot's 9px, its 8px gap, and the 20px and 8px the row
// and the tray take for padding — and what is left holds a title that ellipsizes rather
// than wrapping, so under this the tray is furniture showing the first syllable of every
// name on it. The asks tray's rows clamp to three lines instead and would go on reading
// further down, which is why the floor is the leaves tray's to set.
const TRAY_W = 300;
const TRAY_MIN = 220;
const TRAY_COVERING = `(width <= ${TRAY_W * 2}px)`;
// Where each standing width is written, and where the cascade reads it. Named rather than
// spelled, because the stylesheet below and the runtime's writer are two ends of one fact
// and a property spelled twice is two facts the day one of them moves.
const PANEL_PROP = "--lf-panel-w";
const TRAY_PROP = "--lf-tray-w";
// Which trays take their room out of the page rather than lying over it, read by the rule
// that takes the strip and by the runtime for what the page has left — so the two cannot
// disagree about whether the page is yielding one.
//
// The leaves tray is not on the list, and that is not an inconsistency between two twins:
// a leaf's row is a way out of this page and an ask's row is a way around it, so pressing
// an ask's row scrolls the document to the ask and stands you on the control that answers
// it — and a tray lying over the document would be hiding the very thing it just sent you
// to. A 300px tray and a 720px column overlap on any window under about 1320px, which is
// most of them, so this is the common case rather than the narrow one.
const STRIP_TRAYS = ["asks"];
const STRIP_TRAY_RULE = `body:is(${STRIP_TRAYS.map(
  (tray) => `[data-lf-tray="${tray}"]`,
).join(",")})`;
// The width the theme wants a page's box to have before it takes a strip of it for the
// margin (theme.css's --strip-min, stated there because that is where the strips and
// their breakpoints are). Read blind: the runtime reports how wide the box is against
// the number the theme states and never learns which idiom spends it. A theme without
// the token leaves this NaN, every comparison against it false, and the media query
// alone deciding — which is the same answer a page with no runtime already gets.
const STRIP_MIN = parseFloat(
  getComputedStyle(document.documentElement).getPropertyValue("--strip-min"),
);

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

// The step an arrow takes, in the column's own gutter: the smallest move that shows in a
// page of prose.
const EDGE_STEP = 24;
/** A region held to one side of the window, and the boundary the reader draws it by.
 *
 * The page has two — the comment panel on the right, the tray panel on the left — and
 * they are the same furniture reflected, so this is one function rather than two
 * near-copies. What differs is what it is handed: which side the region is held to, the
 * width it stands at until the reader says otherwise, how narrow they may draw it, the
 * property the cascade reads the standing width from, the key their store keeps the choice
 * under, and one noun, which every surface that names the region says in its own sentence.
 * Nothing below differs, which is the point: the second edge cost a call rather than a
 * copy, and a third would too.
 *
 * The width the reader asked for and the width the region stands at are two facts rather
 * than one. A window too narrow to honour a choice does not un-make it, and widening that
 * window again is not a request to be told what the reader once said — so the choice is
 * kept and the standing width is derived from it. Everything reads `width`; nothing holds
 * the number.
 *
 * One width, and a handle for each region on that side: the left edge holds two trays one
 * at a time, and each wears the edge it is drawn by, because a handle outside them both
 * would not slide in with the tray it belongs to. They are handles onto one fact rather
 * than two facts — `state` is the one writer, and it says the same thing on every one.
 */
function drawnEdge({ side, noun, wide, min, prop, key, covering, when }) {
  // Whether the region stands over the page rather than beside it — the same fact as
  // which of the two rules that take the strip the page is under. Asked of the query
  // rather than stored, so no reader of it can hold an answer from a window that has gone.
  const over = matchMedia(covering);
  const handles = new Set();
  let chosen = wide;
  // What the window will allow. Beside the page, half of it, which is the bargain the
  // covering query already strikes for the default width — the page keeps at least what
  // the region takes — asked here of whatever width this reader chose. Over the page the
  // region takes nothing from it, so the only bound there is the window itself.
  const cap = () => document.documentElement.clientWidth / (over.matches ? 1 : 2);
  // The floor gives way to the cap and not the other way about: a window too narrow for
  // the floor is still the window, and a region wider than the one it stands in has put
  // its own controls off the screen. Asked in two places and written once — of a width the
  // reader is dragging to, so the edge never goes anywhere their hand did not, and of the
  // width they chose on some other day, whose window is not this one.
  const held = (want) => Math.min(cap(), Math.max(min, want));
  const width = () => held(chosen);
  // The one writer of the property the cascade reads that width from: the region's own box
  // and the strip the page yields are both stated against it. Written rather than read back
  // off the region because a closed one measures zero, which is exactly when the page most
  // needs to know how wide it will be. The runtime's own readers — the toast's corner, the
  // room a wide widget spends — ask `width` instead of this property, so what the cascade
  // lays out and what the runtime measures cannot come apart.
  function state() {
    document.documentElement.style.setProperty(prop, width() + "px");
    // Where the edge stands and how far it may go, which is what a listener hears change
    // on every step — the platform's own announcement, and the whole reason the edge is a
    // separator. The cap moves with the window, so it is restated wherever the width is.
    for (const handle of handles) {
      handle.setAttribute("aria-valuenow", String(Math.round(width())));
      handle.setAttribute("aria-valuemax", String(Math.round(cap())));
    }
  }
  // The reader's answer, taken and kept. Held to the window on the way in, because a drag
  // is direct: what they see is what they asked for, and storing a width the window
  // refused would hand it back to them on some later window as a place they never put the
  // edge.
  function set(want) {
    chosen = Math.round(held(want));
    readerStore.set(key, String(chosen));
    state();
    stateStrip();
    syncLayout();
  }
  /** The region's own edge, said as what it is: a separator between two regions, which is
   * the platform's word for a boundary the reader moves. That word is worth having for
   * what comes with it — the edge carries the width it stands at, so an arrow step is
   * announced by the platform itself, where a press built for the job would have had to say
   * so in words of its own and would have promised an activation an edge has not got.
   *
   * It goes in the region rather than beside it, so it travels with whatever the region
   * does: the tray panel's edge slides in with the tray standing on it, and a closed
   * region's edge is hidden by the same rule that hides the region.
   */
  function handle(region) {
    const edge = el("div", "lf-ui lf-edge");
    edge.dataset.lfSide = side;
    edge.setAttribute("role", "separator");
    edge.setAttribute("aria-orientation", "vertical");
    // The name a listener hears, and the one design mode shows under the pointer, where
    // it is cut at CONTROL_WORD_CAP — so the noun leads and the word for what is being
    // measured follows it, which is what keeps the longer of the two inside the cut.
    edge.setAttribute("aria-label", `${noun[0].toUpperCase()}${noun.slice(1)} width`);
    edge.setAttribute("aria-valuemin", String(min));
    edge.tabIndex = 0;
    // Where on the edge the reader took hold, kept for the length of the drag so the
    // boundary stays under the point they grabbed. Without it the region jumps by up to
    // the handle's own width on the first move, which is the page moving under an aim that
    // had just arrived.
    let grab = 0;
    edge.addEventListener("pointerdown", (event) => {
      // Refusing the press stops the compatibility mouse events, and with them the
      // selection a drag makes: without it a gesture about the edge would drop whatever the
      // reader had selected and paint a new one over the paragraphs it passed. Focus is
      // then taken by hand, refusing the press having refused that too, so the arrows are
      // live on the edge the reader is holding.
      event.preventDefault();
      edge.setPointerCapture(event.pointerId);
      const box = region.getBoundingClientRect();
      grab = event.clientX - (side === "right" ? box.left : box.right);
      edge.focus({ preventScroll: true });
      document.body.toggleAttribute("data-lf-sizing", true);
    });
    edge.addEventListener("pointermove", (event) => {
      if (!edge.hasPointerCapture(event.pointerId)) return;
      // The region's far edge is the window's, so the width is what the pointer leaves
      // between the two — read off the window rather than off the region, which is the box
      // this is about to resize.
      const at = event.clientX - grab;
      set(side === "right" ? document.documentElement.clientWidth - at : at);
    });
    // Both ends of the gesture, because a drag the browser takes away — a window losing the
    // pointer, a touch cancelled — leaves the page in the sizing posture otherwise, and the
    // slide would be gone for the rest of the session with nothing to say why.
    for (const ending of ["pointerup", "pointercancel"])
      edge.addEventListener(ending, () =>
        document.body.toggleAttribute("data-lf-sizing", false),
      );
    // Arrows, and not a pair of letters, because the reader is standing on the edge
    // itself — the direction is the whole of what they have left to say. Away from the
    // side the region is held to widens it, which is the same reading the pointer makes of
    // the same gesture.
    const wider = side === "right" ? "ArrowLeft" : "ArrowRight";
    keys(
      edge,
      `On the ${noun}'s edge`,
      [
        {
          keys: ["ArrowLeft", "ArrowRight"],
          label: "arrows",
          does: `Resize the ${noun}`,
          line: `resize the ${noun}`,
          repeat: true,
          run: (binding) => set(width() + (binding === wider ? EDGE_STEP : -EDGE_STEP)),
        },
      ],
      when,
    );
    handles.add(edge);
    region.prepend(edge);
    state();
    return edge;
  }
  // The reader's own answer, put back over the default at the foot of the module, where
  // every other remembered arrangement is restored. Stated whether or not they have chosen
  // one, since a reader who has said nothing is a reader whose answer is the default.
  function restore() {
    chosen = parseFloat(readerStore.get(key)) || wide;
    state();
  }
  return { width, state, restore, handle, key, over };
}
// The rows' own box, one per tray. Collected as they are made, because what syncLayout
// reserves at the foot of one it reserves at the foot of every one — and a second place
// to remember that is exactly where the asks tray was left out of it: its walk parked
// the last row 47px under the key line, on the one tray nothing had ever walked to the
// end of.
const trayLists = [];
function trayList(panel) {
  const list = el("div", "lf-tray-list");
  panel.append(list);
  trayLists.push(list);
  return list;
}
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
const traysEdge = drawnEdge({
  side: "left",
  noun: "tray panel",
  wide: TRAY_W,
  min: TRAY_MIN,
  prop: TRAY_PROP,
  key: "lf-tray-width",
  covering: TRAY_COVERING,
  // A page with no tray to open has no edge to draw, so the reference does not name one.
  when: () => leavesOffered() || asksOffered(),
});

const banner = el("div", "lf-ui lf-banner");
const dot = el("span", "lf-dot");
const statusText = el("span", "lf-status-text", "Connecting…");
// The controls the banner's news arrives as, each present only while it has
// something to say. Room a control has once taken is room it keeps for the rest of the
// page's life: before it first appears there is nothing to hold, so a page that never
// falls behind pays nothing for the chip, and once one has stood somewhere the others
// can't close ranks over it — a second tab deciding the last pending suggestion took the
// ✓ Accept all away and slid the New-version chip 148px right, under whoever was
// reaching for it. Reserving from the start instead would hold room on every row for news
// that page will never get, which shows as a gap the moment one of them is there and its
// neighbour isn't; reserving nothing is the movement. This spends only where the
// alternative is a control moving, and only on the pages that got the news.
//
// One setter stating the whole outcome, per showComposer and showFab, so no caller has
// to know which of the two ways of being absent this control is currently in.
const showNews = (control, on) => {
  if (on) control.dataset.lfStood = "1";
  control.style.display = on || control.dataset.lfStood ? "" : "none";
  control.style.visibility = on ? "" : "hidden";
};
const latestChip = el("button", "lf-ui lf-btn lf-latest-chip", "");
// The keyboard reaches this through the chooser rather than past it: v opens the menu, and
// the letter again takes the newest version. The chip names that motion, spelled from the
// two rows that make it rather than typed out beside them.
latestChip.title = "Open the newest version";
// What the page is still waiting on the reader for, and the way to the next one — the
// same list n/p step and the "?" overlay names, counted here so a reader who
// has not scrolled that far still knows there is something to answer.
const asksBtn = el("button", "lf-btn lf-asks", "");
asksBtn.title = "Go to the next thing this page is waiting on you for";
// The machine's live leaves and what each is doing: a left panel of rows, each a
// link opening that page in its own tab, judged by the same `presented` the banner
// answers with, from the same facts — `others` on /api/state carries them for every
// live page, and every URL in the list carries only the key this reader already
// holds, since there is one key for the machine (`host_key`). The current page heads
// the list as a marked, unlinked row, so the panel reads as the whole machine. A
// status tray's point is being live, so rows reconcile on every poll, keyed by URL —
// the stable identity, since address, port and key all survive a restart — and a
// status change repaints the row's own dot and words without moving it.
const othersBtn = el("button", "lf-btn lf-others", "");
othersBtn.title = "Leaves live on this machine, and what each is doing";
// A nav, because navigation is what it is and a bare div may not carry the
// aria-label the card needs (axe: aria-prohibited-attr, serious).
const othersPanel = el("nav", "lf-ui lf-tray-panel lf-others-panel");
othersPanel.setAttribute("aria-label", "Leaves on this machine");
traysEdge.handle(othersPanel);
const leavesList = trayList(othersPanel);
let others = [];
// A tray of the page's own open asks, on the same edge: one row per thing the page is
// waiting on the reader for, in the order the page asks them. The list is openAsks() and
// nothing else, so a widget joins the tray by declaring x-awaits and no row here knows
// what kind of thing it is standing for.
const asksPanel = el("nav", "lf-ui lf-tray-panel lf-asks-panel");
asksPanel.setAttribute("aria-label", "What this page is waiting on you for");
traysEdge.handle(asksPanel);
const asksList = trayList(asksPanel);

// The left edge holds one tray at a time. Leaves and asks are the same furniture asking
// at two scopes — which page needs me, and what this page needs of me — and each has to
// stand while the reader works, which is the whole reason either is a fixed edge rather
// than a menu over the page. So which one is up is one fact held in one place. A boolean
// per tray would be one guarantee written twice, and the two would first disagree on the
// day a third surface opened one without closing the other; the reader would then have
// two trays over one edge with the lower one unreachable.
//
// Registered rather than listed, for the same reason the widgets are: the toggle, the
// press, the reload and the Escape rung all read this map, so a third tray joins by
// registering and none of them names a tray to do its job.
const trays = new Map();
const TRAY_KEY = "lf-tray-up";
// The tray survives a reload like the comment panel does (see PANEL_KEY): reloading is
// not resetting, and a tray someone stood up to watch stays stood. Null until the
// restore at the foot of this module puts it back, which it does by opening the tray
// the way a press does. Reading the store into this declaration instead is what made
// registration a second opener, and a second opener here can reach almost nothing: it
// runs while this module is still evaluating, so the page's own asks — declared
// thousands of lines below — are not initialized yet, and the reader who had left the
// tray standing got a ReferenceError where their page should have been.
let trayUp = null;
const openTray = (key) => trayUp === key;
function showTray(key) {
  if (trayUp === key) return;
  trayUp = key;
  for (const [name, { panel, btn, paint }] of trays) {
    const open = name === key;
    btn.setAttribute("aria-expanded", String(open));
    if (open) {
      // Filled before it is shown, so the tray is its own list from the first frame of
      // the slide rather than a blank card that populates a moment later. The way down
      // is the mirror of it, below: emptied once it is hidden, never before, or the
      // reader watches the list they just closed blank out and an empty card slide away.
      paint?.();
      panel.classList.add("open");
      motion(
        panel,
        [{ transform: "translateX(-100%)" }, { transform: "translateX(0)" }],
        200,
      );
    } else if (panel.classList.contains("open")) {
      // Slid out before hidden, and hidden only if still closed on arrival — a
      // reopen mid-slide leaves the panel standing rather than racing the finish.
      const out = motion(
        panel,
        [{ transform: "translateX(0)" }, { transform: "translateX(-100%)" }],
        160,
      );
      const hide = () => {
        if (trayUp === name) return; // reopened mid-slide; it stays up, list and all
        panel.classList.remove("open");
        paint?.();
      };
      if (out) out.finished.then(hide, () => {});
      else hide();
      if (panel.contains(document.activeElement)) btn.focus();
    }
  }
  // Both of the page's answers to the tray are made here rather than left to the
  // observation, for the reasons setPanel gives at the same two lines: the strip the
  // idioms hang in is body's own padding, which the observation's writer may not touch,
  // and a tray that covers the page moves body's box by nothing at all, so there is no
  // observation to deliver.
  stateStrip();
  syncLayout();
  readerStore.set(TRAY_KEY, key ?? "");
  // Which tray is up, on the document, so the stylesheet can say what each one costs the
  // page's own box. One writer for it, here, beside the one variable that holds the fact.
  if (key) document.body.dataset.lfTray = key;
  else delete document.body.dataset.lfTray;
  paintHere();
}
// Registration and nothing else: no tray is up while this module is evaluating, and
// the one the reader left standing goes up in the restore section at the foot of the
// file, through showTray. So there is one opener, and every fact that carries "this
// tray is up" is written where it is decided.
function trayIs(key, panel, btn, paint) {
  trays.set(key, { panel, btn, paint });
  btn.onclick = () => showTray(openTray(key) ? null : key);
  btn.setAttribute("aria-expanded", "false");
}
trayIs("leaves", othersPanel, othersBtn);
trayIs("asks", asksPanel, asksBtn, () => renderAsks(openAsks()));
// A persisted tray is state-dependent chrome: Asks folds the log and Leaves comes from
// the first state response. Keep the remembered intent in trayUp, but restore its pixels
// only once that response has produced the page's presentation. Unlike showTray, this
// first paint does not animate — it is part of the page arriving, not a reader gesture.
function restoreTray() {
  if (!trayUp) return;
  const tray = trays.get(trayUp);
  if (!tray) return;
  tray.btn.setAttribute("aria-expanded", "true");
  tray.paint?.();
  tray.panel.classList.add("open");
  document.body.dataset.lfTray = trayUp;
}
// Each tray's one offer: something to show, or the tray already standing — the key that
// opened it must still close it, and its button must still be pressable. The button's
// visibility and the key both ask the tray's own predicate, so the two surfaces cannot
// disagree about whether there is a tray to open. A leaves tray of one — the page the
// reader is already on — is not worth a control; an asks tray of none is the same.
const pagePresented = () => document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented);
const leavesOffered = () =>
  pagePresented() && (others.length > 0 || openTray("leaves"));
const asksOffered = () =>
  pagePresented() && (openAsks().length > 0 || openTray("asks"));
// The tray's own scope. The walk is the tray's rather than the page's, because ArrowUp
// and ArrowDown anywhere else are the page's own scroll and stay so; Enter is the
// browser's, a row being a link, and the row says so with no `run` to give. The reader
// arrives here by key — `l` lands focus on the first neighbour — so the scope names what
// activating does rather than leaving it to the platform's own contract.
const othersLinks = () => [...othersPanel.querySelectorAll("a.lf-others-row")];
const askRows = () => [...asksPanel.querySelectorAll("button.lf-asks-row")];
// The asks tray's own walk, the leaves tray's twin: ArrowUp and ArrowDown are the page's
// scroll everywhere else and the tray's here, and Enter is the platform's, a row being a
// button — so the scope names what walking does and leaves the press to the button.
keys(asksPanel, "In the asks tray", [
  {
    keys: ["ArrowUp", "ArrowDown"],
    does: "Walk the asks",
    line: "walk the asks",
    repeat: true,
    run: (binding) => walkRows(askRows(), binding === "ArrowDown" ? 1 : -1),
  },
  {
    keys: ["Enter"],
    does: "Go to this ask and stand on the control that answers it",
  },
]);
keys(
  othersPanel,
  "In the leaves tray",
  [
    {
      keys: ["ArrowUp", "ArrowDown"],
      does: "Walk the leaves",
      line: "walk the leaves",
      repeat: true,
      run: (binding) => walkRows(othersLinks(), binding === "ArrowDown" ? 1 : -1),
    },
    // Enter is the browser's here, the row being a link — no `run`, because binding it
    // would click a control the platform has already activated. It carries a word all the
    // same: the press is real and immediate where the reader is standing, which is what
    // the line is for.
    { keys: ["Enter"], does: "Open that leaf in a tab", line: "open it in a tab" },
  ],
  leavesOffered, // the scope's own liveness: a tray with something to walk
);
// A row's whole account of a page: the dot's tone and one line of words, from the
// same judgment the banner's sentences come from — the judgment is shared, the
// wording is the seat's.
const TONE = {
  working: "working",
  listening: "listening",
  stalled: "away",
  away: "away",
  unheld: "",
  unattended: "",
  closed: "",
};
function rowPresence(entry) {
  const { kind, quiet, dropped, detail } = presented(entry);
  // The same join for both kinds that have words of their own. The reader opens this
  // panel to find which page needs them, so a bare `Awaits` beside a neighbour's
  // `Working — recording the demo` said least about the one row they are here to act
  // on: three pages waiting rendered as three identical rows, and which to go to
  // first is the whole question the panel was opened to answer.
  const stated = (word) => word + (detail ? " — " + detail : "");
  // The banner's two silences, dated the same way and worded for a row.
  const silence = dropped
    ? `Left (${ago(entry.turn_closed)})`
    : `Quiet (${ago(entry.status.ts)})`;
  const line =
    kind === "working"
      ? stated("Working")
      : kind === "listening"
        ? stated("Awaits")
        : kind === "stalled"
          ? stated(silence)
          : kind === "away"
            ? quiet
              ? silence
              : "Away"
            : kind === "unheld"
              ? "Unheld"
              : kind === "unattended"
                ? "Unattended"
                : "Closed";
  return { tone: TONE[kind], line };
}
// The whole of what the tray knows about one page, for its hover. Everything drawn
// on a row is cut to the panel's fixed width — the title ellipsizes, the line
// ellipsizes — and the fact that tells two rows apart is not drawn at all: where the
// session behind the leaf is working. A title is a sentence somebody wrote and two
// pages a week apart share one; the work each came out of is the thing the reader
// already holds in their head, so it is worth the room a hover has and a row hasn't.
//
// One tooltip for the row rather than one per part. The innermost title wins where two
// overlap, so a title left on the line would answer the hover most likely to be asking
// this question — a reader pointing at the words that ran out of room — with the one
// part of the account they can already read.
const rowAccount = (entry, title, line) =>
  [
    title,
    entry.session_cwd,
    line,
    // The reader's own words that page's agent hasn't taken in. The banner says this
    // number for this page; the tray says it for every page, which is the seat's
    // whole point — a leaf holding something of yours that nobody has read is a
    // reason to go there, and nothing else on the row says so.
    entry.pending && `${entry.pending} update${entry.pending === 1 ? "" : "s"} waiting`,
  ]
    .filter(Boolean)
    .join("\n");
const othersRows = new Map(); // keyed by URL; the self row under its own key
function renderOthers(state) {
  // An older server ships no list, which is an empty one. A closed leaf is not
  // one of the machine's live pages and drops out of the tray on the poll that says
  // so: its server stays up so the page stays readable — a standing one for good —
  // so nothing else would ever take the row off, and a count the reader glances at
  // to find who needs them would silently become a tally of everything that has run
  // here. Judged by the same `presented` the rows read, never by a second reading of
  // the status the server ships. This page's own row is not in the list and so is
  // never dropped: a reader looking at a closed page is still looking at it.
  others = (state.others ?? []).filter((entry) => presented(entry).kind !== "closed");
  // While the panel stands its button stands too, whatever the count just did.
  showNews(othersBtn, leavesOffered());
  const wanted = [
    { key: "self", title: document.title, entry: state },
    ...others.map((entry) => ({ key: entry.url, title: entry.title, entry })),
  ];
  // The button names the tray it opens, so the count is these rows — the list the
  // press will show, headed by this page's own row — and never arithmetic beside
  // them. "Other leaves" counted the neighbours alone, one off the list it
  // promised: a machine with one neighbour said (1) over a tray of two.
  othersBtn.textContent = `All leaves (${wanted.length})`;
  let anchor = null; // the row before this one, so order holds without rebuilding
  for (const { key, title, entry } of wanted) {
    let row = othersRows.get(key);
    if (!row) {
      // The self row is a marked div — the reader is already here, so there is
      // nothing to open; every other row is a link to its page's own tab.
      row =
        key === "self"
          ? el("div", "lf-others-row lf-others-self")
          : Object.assign(el("a", "lf-others-row"), {
              href: key,
              target: "_blank",
              rel: "noopener",
            });
      const head = el("div", "lf-others-head");
      head.append(el("span", "lf-dot"), el("span", "lf-others-title"));
      if (key === "self") head.append(el("span", "lf-pill", "this page"));
      row.append(head, el("div", "lf-others-line"));
      othersRows.set(key, row);
    }
    const { tone, line } = rowPresence(entry);
    const [rowDot, rowTitle] = row.querySelectorAll(".lf-dot, .lf-others-title");
    const rowLine = row.querySelector(".lf-others-line");
    // Written only on change: an unchanged poll must not feed the mutation stream
    // a screen reader rebuilds its buffer on.
    const dotCls = "lf-dot" + (tone ? " " + tone : "");
    if (rowDot.className !== dotCls) rowDot.className = dotCls;
    if (rowTitle.textContent !== title) rowTitle.textContent = title;
    if (rowLine.textContent !== line) rowLine.textContent = line;
    // Everything the row was too narrow to say, on the row itself (see rowAccount).
    const account = rowAccount(entry, title, line);
    if (row.title !== account) row.title = account;
    const place = anchor ? anchor.nextElementSibling : leavesList.firstElementChild;
    if (place !== row) leavesList.insertBefore(row, place);
    anchor = row;
  }
  for (const [key, row] of othersRows)
    if (!wanted.some((w) => w.key === key)) {
      row.remove();
      othersRows.delete(key);
    }
}
for (const control of [latestChip, asksBtn, othersBtn]) showNews(control, false);
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
const versionLabel = (comparing) =>
  (comparing ? "Δ " : "") +
  (runtime.currentVersion === null ? "▾" : `v${runtime.currentVersion} ▾`);
const versionBtn = el("button", "lf-btn lf-version", versionLabel(false));
// Nothing to open until the log says what versions there are, and a control that answers
// nothing is a way in painted where there is no layer behind it — the same reason the
// page's own approve button waits for the page. `versionsOffered` is what the key and the
// menu already read; this is the pointer's half of it, cleared by renderVersions.
versionBtn.disabled = true;
versionBtn.setAttribute("aria-haspopup", "menu");
versionBtn.setAttribute("aria-expanded", "false");
const versionMenu = el("div", "lf-ui lf-version-menu");
versionMenu.setAttribute("role", "menu");
versionMenu.setAttribute("aria-label", "Versions");
let versionMenuOpen = false;
// Two facts about the versions, which had been one comparison spelled in three places and
// read as though it answered both. Whether there is a menu to open is not whether there is
// anything in it to walk: a first version has no neighbour to step to, and its menu still
// holds that version and the note saying what it changed, which is the whole reason the
// chooser is a menu rather than a select.
//
// Conflated, they left the menu's way in live over a page its way out was not. `v` opened
// on any page while the mode binding the menu's Escape stood only above one version, so on
// the commonest page there is — a page with one version — `v` raised a menu no key could
// put down: the Escape chip read "back to the page", focus fell to body, and the menu
// stayed painted. A layer owes a way out over exactly the pages its way in is live on, and
// the way to keep that true is to stop asking one question for both.
//
// Named the way the trays name theirs (`leavesOffered`, `asksOffered`), so the next
// surface to ask reads the fact rather than spelling a comparison of its own.
const versionsOffered = () => versions.length > 0;
const versionsToWalk = () => versions.length > 1;
// The walk is the versions, not every press in the menu.
const versionRows = () => [...versionMenu.querySelectorAll(".lf-version-row")];
// One setter stating the whole outcome, per showComposer and showFab: nothing reads
// the class back to find out whether the menu is up.
function showVersionMenu(open) {
  versionMenuOpen = open;
  versionMenu.classList.toggle("open", open);
  versionBtn.setAttribute("aria-expanded", String(open));
  // Opening lands on the version being read, so the menu's own keys are the next
  // press rather than a Tab-hunt — the same move o makes into the leaves tray.
  //
  // Or on the standing base, where a comparison is up, because inside this menu the focused
  // row *is* the base (the walk below). Landing on the version being read instead left the
  // two disagreeing at the one moment the reader cannot see it coming: their first arrow
  // press would have moved the base off the version they had marked from to the neighbour of
  // the one they are reading, silently, with the marks redrawn to match.
  if (open)
    (
      versionRows().find(
        (r) =>
          r.dataset.lfVersion === String(diffOn ? diffBase : runtime.currentVersion),
      ) ?? versionRows()[0]
    )?.focus();
  else if (versionMenu.contains(document.activeElement)) versionBtn.focus();
  paintHere();
}
// The pointer's door, held to the same fact as the key's: a button that opened a menu
// nothing could close would put the trap back for the reader who never touches the
// keyboard.
versionBtn.onclick = () => showVersionMenu(versionsOffered() && !versionMenuOpen);
// The menu's own scope. The walk is the menu's rather than the page's, because ArrowUp and
// ArrowDown anywhere else are the page's own scroll; ⏎ is the browser's, a row being a
// button, and the row says so with no `run`. A row's Δ is the same comparison for the
// pointer, which has no walk to state it with, and takes no key of its own.
//
// v is the second half of the motion that opened the menu, and the one row worth a key of
// its own: the newest version is where the walk ends, and where a reader who came for the
// current state is going. The letter is the menu's here for the walk's own kind of reason
// — outside it, v is already the chooser — and being the inner scope's is what shadows the
// page's v, where the two listeners used to depend on one consuming the press.
//
// The scope is live while there is a list to walk. The menu's *way out* is not — it is the
// mode's below, on the wider fact that there is a menu at all, because a layer's Escape
// has to hold wherever the layer does. Reading one predicate for both is what left `v`
// opening a menu on a page whose Escape no scope was live to bind: the reader's next press
// was the page's own rung, focus fell to body, and the menu stayed painted. So this scope
// answers "is there anything to walk" and the mode answers "is there a menu", and the
// reference's section is the two of them merged by title — on a first version, the way out
// and nothing else.
const NEWEST = {
  keys: ["v"],
  does: "Open the newest version",
  line: "open the newest version",
  // Through its own row's press, so the key leaves the menu by the door the pointer uses —
  // the menu closes and the pin lifts, both goVersion's and showVersionMenu's to say,
  // neither restated here. There is always a row to press: the scope holds only with focus
  // inside the menu, and an open lands focus on a row.
  run: () => versionRows().at(-1).click(),
};
keys(
  versionMenu,
  "In the versions menu",
  [
    {
      keys: ["ArrowUp", "ArrowDown"],
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
        // states a comparison, landing is not free — it would re-fetch the base and toast
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
    { keys: PRESS, does: "Open that version", line: "open that version" },
    NEWEST,
  ],
  versionsToWalk,
);
// The way out is the menu standing, not the reader being inside it: a menu opened and
// then Tabbed out of is still over the page, and an Escape that could not reach it left
// the reader closing the panel underneath instead. So the rung is a mode rather than the
// element scope's — which is what every other layer that can outlive its own focus does
// (the composer holds a draft the reader clicked away from; the leaves tray stands while
// focus is on the button that opened it). The menu's walk stays the element scope's,
// because a walk has nothing to walk unless focus is on a row.
const VERSIONS = {
  title: "In the versions menu",
  // The way out is live wherever the way in is, which is the wider fact and not the walk's:
  // a menu holding one version is still a layer the reader is standing in, and its Escape
  // is the only key that ends it. Stated as the walk's liveness, this scope went quiet on
  // exactly the page where the menu could not otherwise be closed.
  when: versionsOffered,
  at: () => versionMenuOpen,
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
    {
      keys: ["Escape"],
      does: "Close the versions menu",
      line: "close versions",
      run: () => showVersionMenu(false),
    },
  ],
};
const toggleBtn = el("button", "lf-btn lf-comments", "Comments");
toggleBtn.title = "Show or hide the comment panel";
toggleBtn.setAttribute("aria-expanded", "false");
const approveBtn = el("button", "lf-btn primary lf-signoff", "✓ Looks good");
approveBtn.title = "Approve this work; the page stays open for follow-up";
// The page's ask is not actionable until the page itself is present. Discussion chrome
// stays live during replay, but approving hidden authored content would decide a version
// the reader has not seen yet.
approveBtn.disabled = true;
banner.append(
  dot,
  statusText,
  el("span", "lf-spacer"),
  othersBtn,
  latestChip,
  asksBtn,
  versionBtn,
  toggleBtn,
);
if (signoff) banner.append(approveBtn);

// Sign-off belongs to the authored version, while the control belongs to the live
// chrome that survives one. A soft activation can therefore add or remove the same
// control; rebuilding the banner would throw away focus and every reserved neighbour.
function stateSignoff(next) {
  if (next === signoff) return;
  signoff = next;
  if (signoff) {
    banner.append(approveBtn);
    reserve(approveBtn, ["✓ Looks good", "✓ Approved"]);
    paintApproval();
  } else approveBtn.remove();
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
commentsEdge.handle(panel);
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
// What is waiting on the reader: an open thread whose last word is the agent's. Derived
// from the log rather than stored, so it needs no record of what this reader has read and
// cannot go stale in another tab — and it is the same question the asks board asks of the
// page's widgets, asked of the conversation.
const needsBtn = el("button", "lf-btn lf-needs", "Waiting on you");
needsBtn.setAttribute("aria-pressed", "false");
findRow.append(findInput, needsBtn);
const threadsBox = el("div", "lf-threads");
// An Escape rung: backing out of the general box lands on the list (visible ring,
// j/k walk on from it) rather than on nothing. -1 keeps it out of the Tab order.
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

const fab = el("button", "lf-ui lf-pill lf-fab", "💬 Comment");
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
const helpEl = el("div", "lf-ui lf-help");
helpEl.setAttribute("role", "dialog");
helpEl.setAttribute("aria-label", "Keyboard reference");
helpEl.tabIndex = -1; // focused on open, so the dialog isn't silent to a screen reader
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
keylineMore.onclick = () => showHelp(true);

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
// The g chord's addresses: a numbered chip on every member of the list it has aimed at,
// drawn here for the same reason the legend is (paintAddresses, its one writer). The eye's
// copy of what the chord announces, so it says nothing to a screen reader.
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
  fab,
  composer,
  toastEl,
  liveEl,
  helpEl,
  keylineEl,
  inspectEl,
);
document.body.append(chromeRoot);
// The controls that rewrite their own words hold the widest of them now, measured in
// the face the banner just rendered them in (see the stylesheet's banner comment).
// The counters hold the widest they reach anywhere below a thousand, so no count
// they write can move them — a page with a thousand open threads, or a machine with
// a thousand live pages, is not one anyone hands a user.
if (signoff) reserve(approveBtn, ["✓ Looks good", "✓ Approved"]);
reserve(versionBtn, [versionLabel(false), versionLabel(true)]);
reserve(toggleBtn, ["Comments", "Comments (999)"]);
reserve(needsBtn, ["Waiting on you", "Waiting on you (999)"]);
reserve(asksBtn, ["Asks (999)"]);
reserve(othersBtn, ["All leaves (999)"]);
// The room the head of the document leaves for the bar, measured off the bar as
// rendered rather than stated as a number — --lf-banner-h is what the bar is drawn to
// and a second copy of it here would be a release behind it the day either moved. What
// spends this, and why it is spent as a box rather than as body's own padding, is the
// rule above that reads it. The key line's reservation at the foot is the same
// arrangement, written by syncLayout because it is the same measurement every time the
// line's height changes.
document.body.style.setProperty("--lf-head", banner.offsetHeight + "px");

// ---------- state ----------

// Until the first state answer, [] means "not read", not "no comments". Keep that
// distinction for a Comments panel restored or opened during startup; its General
// composer stays usable while the log-derived list says what it is waiting for.

let lastVersionsKey = "";

const versions = runtime.versions;
let agentMsgCount = -1;
// Whether the page currently believes anything is behind its work claim. An update
// remains in the feed after settlement, but no local seat presents it under a banner
// saying nobody holds the page.
let claimsHeld = false;
// When the claiming session's last turn ended, as this tab last heard it. Held beside
// the claims because it is the other half of reading one: a claim is renewed by the same
// command that renews the page's claim, so a turn ending under both is one fact, and
// the local seat has to reach it without asking the banner.
let agentTurnClosed = null;
// The exact session the turn-closed evidence belongs to. A delegate's update must not
// be called abandoned merely because the orchestrator's turn ended under it.
let claimingSession = null;
// The threads the panel last reconciled. A work line repaints on the poll's clock and
// not only on the log's, because its age is half of what it says and a claim nobody
// renews is exactly the one whose age has stopped moving. Keeping the last fold is what
// makes that cheap: buildThreads walks the log and the page, and a second walk every two
// seconds would answer nothing the last one didn't.
let panelOpen = false;
let selectionComposerRuntime;

let updateRuntime;
export const actionSequence = (widget, action) =>
  updateRuntime.actionSequence(widget, action);
export const updateSequence = (target = null) => updateRuntime.updateSequence(target);
export const publishedAt = () => updateRuntime.publishedAt();
export const saidAt = (el) => updateRuntime.saidAt(el);
export const watchActions = (widget, action, callback) =>
  updateRuntime.watchActions(widget, action, callback);
export const watchUpdates = (target, callback) =>
  updateRuntime.watchUpdates(target, callback);
export const watchHistory = (owner, callback) =>
  updateRuntime.watchHistory(owner, callback);
const claimUpdateSources = () => updateRuntime.claimUpdateSources();
const setClaimUpdateSources = (...args) => updateRuntime.setClaimUpdateSources(...args);

// Panel open/closed is remembered too: it survives live activation, document travel,
// and reload, so reopening the panel by hand after every revision gets old fast.
const PANEL_KEY = "lf-panel-open";
// Whether the panel stands over the page rather than beside it — the same fact as which
// of the two rules that take the strip the page is under, and as which region the
// reader's own scrolling moves. Asked of the edge's query rather than stored, so no reader
// of it can hold an answer from a window that has gone.
const panelCovers = () => panelOpen && commentsEdge.over.matches;
// The strip each side of the page yields, which is that edge's width until the window is
// too narrow to give one up — one expression each, because the margin the rule takes and
// the room measured against it have to mean the same thing by it. The tray panel yields
// one only for the trays the page gives room to at all, which is the same list the rule
// reads (STRIP_TRAYS).
const panelStrip = () => (panelOpen && !panelCovers() ? commentsEdge.width() : 0);
const trayStrip = () =>
  STRIP_TRAYS.includes(trayUp) && !traysEdge.over.matches ? traysEdge.width() : 0;
// Whether the page still has room for the margin the theme's idioms hang in. The strips
// are granted by a media query, which asks the window; the page's box is the window less
// whatever the panel holds of it, and this is the only thing that knows the difference. So
// it asks the theme's own floor of the box and vetoes the grant where the room has gone —
// a fact about the page rather than about any idiom that spends it. Without it a 1024px
// window with the panel beside it left a page carrying sidenotes a 151px column, painting
// its widest widgets out past the edge of one, and neither `version check --render` nor
// the render suite can see that posture: both open a 1200px window with no panel in it.
//
// Its own function, and not syncLayout's, because the strip it vetoes is body's own
// padding (theme.css) and syncLayout runs from an observation of that box — CLAUDE.md's
// "The one writer may not write the box the layout is measured from", and the same reason
// the strip the panel takes is a rule in the stylesheet above. Moving it costs nothing,
// because neither fact it turns on is a reading of that box: the window states one and the
// panel the other, and each arrives on an occasion of its own.
//
// The strip is stated rather than measured off body, whose clientWidth is the box itself
// and would be the natural reading. The margin transitions, so a measurement taken during
// the slide is the posture flipping and flipping back across a fifth of a second, which is
// a page rewrapping its notes into the margin and out of it while the panel opens. Stated,
// it is the width being arrived at.
// Two answers from the one reading, because they are the same fact asked coarsely and
// finely: whether the page can afford a margin strip at all, and how much of one it still
// owes. The width is published rather than spent here for the reason the floor is read
// blind — the runtime says how wide the page's box is and never learns which idiom hangs
// something in the margin, so an idiom's own rule does its own arithmetic against it, the
// way the wide rules already spend --lf-room. A query cannot see the panel and this can,
// which is the whole of what the runtime adds; a page with no runtime behind it falls back
// to the viewport in each rule that reads it.
function stateStrip() {
  const avail = document.documentElement.clientWidth - panelStrip() - trayStrip();
  document.body.toggleAttribute("data-lf-cramped", avail < STRIP_MIN);
  document.documentElement.style.setProperty("--lf-avail", avail + "px");
}
// A window that has changed is a cap that has changed, so the width each edge stands at
// is restated beside the veto — one listener, every fact on it being an answer to the same
// event, and none of them a reading of the box syncLayout measures.
addEventListener("resize", () => {
  commentsEdge.state();
  traysEdge.state();
  stateStrip();
});
// Every writer here is a writer of the chrome, so nothing this function does resizes the
// box it reads: the strip the page yields to the panel is the stylesheet's, and the strip
// it yields to a margin idiom is stated above.
function syncLayout() {
  const panelBeside = panelOpen && !panelCovers();
  // The toast lives in the same corner as the panel's Send button. Beside a wide
  // panel it steps left; over a covering sheet it stays inside the viewport and
  // rises above the whole composer, including a textarea grown by an unsent draft.
  toastEl.style.right = (panelBeside ? commentsEdge.width() + 18 : 18) + "px";
  toastEl.style.bottom = (panelCovers() ? generalRow.offsetHeight + 18 : 18) + "px";
  // The key line takes the toast's lift over a covering sheet, or the sheet's own
  // composer stands on the words saying what Esc will do to it.
  keylineEl.style.bottom = (panelCovers() ? generalRow.offsetHeight + 14 : 14) + "px";
  // Beside the page, the comment panel owns the right strip all the way to its foot. The
  // line starts at the window's left, so cap its room at that strip rather than letting a
  // long computed hint cross into the general comment box. A covering panel is handled by
  // the lift above and leaves the line the window's full width.
  keylineEl.style.setProperty(
    "--lf-keyline-right",
    (panelBeside ? commentsEdge.width() : 0) + "px",
  );
  // One line stands over two scroll regions, so one measurement is what they both
  // reserve — off the rendered line rather than stated as a number, which is what
  // keeps it true when the line's face or its padding moves.
  const clear = keylineEl.offsetHeight + 20 + "px";
  // The document's, taken as the chrome container's own box rather than as padding on
  // body: body's padding comes out of the box the room is measured from (stateRoom), so
  // writing it here made this function a writer of the box it reads, and every page that
  // watched that box — three do — was one change in the line's height from a
  // ResizeObserver loop on the window's error channel. CLAUDE.md's "The one writer may not
  // write the box the layout is measured from" carries the whole of it. The container is
  // in the flow, holds nothing but out-of-flow chrome, and is watched by nobody, so what
  // it takes is room the document has and no measurement's business.
  chromeRoot.style.paddingBottom = clear;
  // A tray's list is the page's other scroll region, in the corner the line is
  // written into, so it reserves the same room — and states it twice, because it reaches
  // the bottom two ways that take their room from different places. A wheel to the end
  // reads the padding. A walk's own scroll reads none of it: scroll-padding is what a
  // scroll-into-view stops short of, and without it the last row's clearance is however
  // far Chrome happens to overshoot, which is a fact about row height and not about the
  // line standing there. Stepping the line clear instead was the other answer, and it
  // takes the tray's width off the line's: a busy scope already fills a laptop's, so
  // the room it gives up is chips clipped off the right-hand end.
  for (const list of trayLists) {
    list.style.paddingBottom = clear;
    list.style.scrollPaddingBottom = clear;
  }
  stateRoom();
  syncFloats();
}
// The room a widget declared wide may take: the document's own content box, less the
// gutter the column already gives its prose, so a breakout is centred on the column's
// axis and stops where the page stops.
//
// Measured, and measured here, because the panel is the thing no stylesheet can see: it
// holds whatever of the window the reader has drawn it to while it is open, and no query
// can ask that, and a rule written against 100vw would also spend the rail a suggestion
// hangs in and the classic scrollbar this platform doesn't draw. The three of them come
// off body's own box for free. That box is watched (layoutSizes), so the room is restated
// whenever it changes shape whatever changed it, for the same reason the floats are
// placed again.
//
// The gutter is read off the column rather than stated, since 24px is theme.css's number
// and a second copy here would be a release behind it. Below the column's own width the
// two coincide exactly, so the rule that spends this is a no-op on a narrow window rather
// than a case anyone has to write.
//
// The strips the chrome holds are the part of that box which isn't settled when this
// runs: each is handed over as motion, so body's margins are still the old ones for the
// length of the transition and the box in front of us is neither the width the page has
// nor the one it is going to. Both readings are wrong, in opposite directions and at
// different prices, so the room takes whichever of the two is smaller and the page never
// owes room it hasn't got. Both sides, because both yield one: the tray panel's margin
// eases exactly as the comment panel's does, and reading it off the box alone left every
// exhibit a tray's width too wide for the fifth of a second the tray took to arrive.
//
// The two readings are compared rather than added, which is the same arithmetic done in
// whole pixels. Subtracting the margin the box has already taken from the strip it is
// going to take says the same thing and says it in two number systems at once: a client
// box is an integer and a transitioning margin is not, so their sum flickered a pixel
// either way on every frame of a slide — and a property every wide exhibit is laid out
// from cannot flicker, because each flicker is a relayout inside the observation that
// asked for it. Opening, that is the width being arrived at, stated at once: the strip
// is being taken away, and an exhibit that waited out the slide would spend it hanging
// over the panel with a sideways scrollbar underneath. Closing, it is the width in front
// of us: the strip is coming back, and an exhibit that took it before the page had it
// scrolled sideways for a fifth of a second every time the panel was dismissed — which
// is what the suggestion sweep caught, on a window narrow enough for the returning strip
// to matter. What is given back is picked up as it is given: the box is watched, so every
// frame of the slide is a reading of it, and the growth lands the frame the room is real.
function stateRoom() {
  const main = document.querySelector("main");
  if (!main) return;
  const body = getComputedStyle(document.body);
  const column = getComputedStyle(main);
  // The gutter body reserves for its own scrollbar, which the window does not know about
  // and the box in front of us has already given up. Read as the difference between the
  // two boxes rather than asked of the platform, which has no way to be asked; it is a
  // constant through a slide, both boxes moving with the margin together.
  const gutter = document.body.offsetWidth - document.body.clientWidth;
  const room =
    Math.min(
      document.body.clientWidth,
      document.documentElement.clientWidth - panelStrip() - trayStrip() - gutter,
    ) -
    parseFloat(body.paddingLeft) -
    parseFloat(body.paddingRight) -
    parseFloat(column.paddingLeft) -
    parseFloat(column.paddingRight);
  document.documentElement.style.setProperty(
    "--lf-room",
    Math.max(0, Math.floor(room)) + "px",
  );
}
// The floats live in the document, and syncLayout is where its box changes shape — the
// panel takes or returns its strip, a resize moves every rect, the composer's own
// textarea grows under typing — so whatever float is up is placed again against the
// new geometry: the composer from its own marks (a detached one re-clamps where it
// stands), the button from the live selection where one still stands, and by
// re-clamping alone where none does. Skipping this leaves a float placed at a wide
// window's edge overhanging the box a panel then narrows, and an absolute child past
// body's client box is sideways-scrollable overflow: the document panned 328px left
// under a trackpad, with the composer standing on the panel that had displaced it.
function syncFloats() {
  if (composerOpen) {
    const box = composer.getBoundingClientRect();
    placeComposer(box.left, box.top);
  }
  if (fabAnchor?.quote && pageSelection()) updateFab();
  else if (fabAnchor) {
    const box = fab.getBoundingClientRect();
    placeClear(fab, box.left, box.top);
  }
}
function setPanel(open) {
  // Closing while focus is inside would drop it on body, the user's place
  // lost silently; it lands on the one control that reopens what just closed.
  if (!open && panel.contains(document.activeElement))
    toggleBtn.focus({ preventScroll: true });
  panelOpen = open;
  // Twice, the two readers being on opposite sides of the chrome's own scope: the class
  // shows the panel, from a rule inside it, and the attribute is what the page yields its
  // strip to, from a rule outside. A document-level rule naming .lf-panel would be a name
  // a page could coin and take the strip with, which is the leak
  // test_a_coined_class_cannot_reach_the_chromes_rules pins, so the posture is stated on
  // body, beside data-lf-cramped.
  panel.classList.toggle("open", open);
  document.body.toggleAttribute("data-lf-panel", open);
  toggleBtn.setAttribute("aria-expanded", String(open));
  // Both of the page's answers to the panel are made here rather than left to the
  // observation, and for the same reason at each: the strip the idioms hang in is body's
  // own padding, which the observation's writer may not touch, and the chrome's posture
  // over a covering sheet follows an open that moves body's box by nothing at all — the
  // sheet stands over the page, so there is no observation to deliver.
  stateStrip();
  syncLayout();
  readerStore.set(PANEL_KEY, open ? "1" : "0");
  if (open) {
    renderPanel();
    syncGeneral(); // a restored draft has to reach the Send button's disabled state
  }
  paintHere();
  // The panel is one of the two surfaces the hover reads, so its arriving or going away
  // is the pointer moving even when the pointer has not: closing it with the keyboard,
  // from a hand resting on a card, took the card out from under the pointer and left the
  // page lit about a comment with no panel to explain it. The open half came free through
  // renderPanel; this is the half that has no render.
  refreshHover();
}
toggleBtn.onclick = () => setPanel(!panelOpen);
addEventListener("resize", pageShifted);
// field-sizing and every other rendered-size change feed the one geometry writer —
// the key line included, whose height is the room the chrome reserves under it.
const layoutSizes = new ResizeObserver(syncLayout);
// The page's own box, which is what the room is measured from and what the floats hang
// in. Watched rather than derived, because an enumeration of the occasions the box moves
// fails twice over. It cannot be complete: the room followed such a list once — the
// panel, the window, the one call at the end of upgrade — and a widget that took a margin
// any other way got no restatement at all. And each entry on it is read at a moment
// somebody chose, which the panel's strip breaks by being motion: read where the slide
// began and again where it was expected to end, a slide the reader interrupted was
// answered at neither. Watching is every frame of it, the last frame included, and the
// window comes with them — body is the window's own height and width here, so a `resize`
// listener beside this would be one fact arriving twice. Nothing this observer calls may
// write this box, which is what the key line's reservation being a flow box and the
// panel's strip being the cascade's are both about.
layoutSizes.observe(document.body);
layoutSizes.observe(generalRow);
layoutSizes.observe(keylineEl);
// The composer grows under typing (field-sizing), and a box placed above its passage
// grows downward, back over the mark it was moved off — so its own resize re-places it.
layoutSizes.observe(composer);

let toastTimer = 0;
function showToast(msg, onClick) {
  announce(msg);
  toastEl.textContent = msg;
  syncLayout();
  toastEl.onclick = onClick || null;
  toastEl.classList.add("show");
  toastEl.classList.toggle("clickable", Boolean(onClick));
  clearTimeout(toastTimer);
  // Drop `clickable` on the way out too: a faded-but-clickable toast is an invisible
  // target sitting over the corner of the page.
  toastTimer = setTimeout(() => {
    toastEl.classList.remove("show", "clickable");
    toastEl.onclick = null;
  }, 4000);
}

// ---------- text inputs ----------
const wireInput = createInput({ keys, showToast, spell });

// ---------- time ----------
// Elapsed, in the page's one wording. Exported for the same reason quietSince is: a
// widget rendering how long since it heard from someone is saying the sentence the
// banner and the leaves panel already say, and a second spelling of it — "12 min ago"
// against "12m ago", or a different rounding at the hour — would read as two clocks on
// one page. The coarseness is the point: elapsed time is a fact the reader acts on at a
// glance, and a ticking second hand is precision nobody asked for over a number nobody
// can trust to the second anyway.
// The reader's clock measured against the one that wrote the timestamps. Every ts a
// seat dates — a claim, a message, a worker's report — is written by the server, while
// `Date.now()` is whatever the machine holding the tab believes: a laptop an hour out
// reads every age on the page an hour wrong, in one direction, with nothing in the
// timestamp itself to give it away. The poll carries the server's own now, so the
// offset is measured rather than assumed, and it is applied in the two functions that
// turn a timestamp into something the reader is told — no seat can forget it, and no
// seat can hold a second opinion about what time it is. Zero until a state arrives,
// and zero for a page with no server behind it at all (the static site), where the
// reader's clock is the only one there is.
let clockSkew = 0;
const serverNow = () => Date.now() + clockSkew;
export const ago = (ts) => {
  if (!ts) return "";
  const secs = Math.max(0, (serverNow() - new Date(ts).getTime()) / 1000);
  if (secs < 45) return "just now";
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.round(secs / 3600)}h ago`;
  return `${Math.round(secs / 86400)}d ago`;
};

// ---------- selection → comment ----------
// Floating UI stays inside the document's own box, which is body's client box: it
// already ends at the open panel's edge (syncLayout's margin) and inside a classic
// scrollbar's gutter, so a float clamped to it can't hand body a sideways scrollbar
// by overhanging either. The covering sheet is the one strip that box no longer
// states — body keeps its full width under it — so the sheet's own width comes off
// here, and a float raised from the strip beside it can't stand over the thread list.
const rightEdge = () =>
  (panelCovers() ? innerWidth - panel.offsetWidth : pageScroller.clientWidth) - 8;
// The floats live in the document — they scroll with the passage they stand beside —
// while every caller reasons in viewport terms: rects, the pointer, the banner's own
// band. Named, because four sites had the number written out and it is neither of the
// two it stands near — the banner is 42px and the scroller's scroll-padding-top 54px,
// this being the slack over the first that says what the reader can actually see.
const BANNER_CLEAR = 48;
// So the one writer of their position is where the coordinates change space: clamp in
// the viewport, store in the document.
function place(node, left, top) {
  node.style.left = Math.max(8, Math.min(left, rightEdge() - node.offsetWidth)) + "px";
  node.style.top =
    Math.max(BANNER_CLEAR, Math.min(top, innerHeight - node.offsetHeight - 8)) +
    pageScroller.scrollTop +
    "px";
}
// The composer's first choice of a place is the column's margin, beside the passage, so
// the mark and the box stand side by side — where the box opened instead at the gesture
// (the fab, the ⌥-click's pointer), it stood on the page's own text next to the
// passage, which is the one thing a 320px card over a 720px column can't avoid doing
// there. placeClear steps it down past any control the page hangs out in that same
// margin (a suggestion's Accept/Reject row).
//
// A sidenote is out there too and the box covers one whole while it stands, which is
// where this stops short of stepping clear. What the walk steps past is controls,
// because a control the box hides is a press the reader was reaching for; a note is
// prose they are not mid-gesture on, and the box goes when they are done with it. The
// walk could be taught the note as easily — the cost is where it would then put the box
// on a page carrying a run of them, which is far enough down the margin to be about a
// different paragraph.
//
// Where the margin is too narrow for the box — a laptop window, the panel open — it
// has one thing left to stay clear of: its own mark. That mark is the only thing
// naming the passage the box is about, so a box standing on all of it is a box about
// nothing. Not "no overlap" — the box has always covered the tail of a long passage
// and that reads fine — but every rect hidden is the case to move for, and it is a
// case that happens: a restored draft reappears near the top of the viewport, and the
// reading position puts the passage it was made on back in the same place.
// Below the passage where the viewport has room, above it otherwise; place()'s own
// clamp has the last word, so a passage too tall for either side simply keeps the
// better spot.
function placeComposer(left, top) {
  place(composer, left, top);
  const rects = anchorRuntime.pendingMarks.flatMap((where) =>
    where instanceof Range
      ? [...where.getClientRects()]
      : [where.getBoundingClientRect()],
  );
  const box = composer.getBoundingClientRect();
  const column = document.querySelector("main")?.getBoundingClientRect();
  if (rects.length && column && column.right + 8 + box.width <= rightEdge())
    return placeClear(composer, column.right + 8, Math.min(...rects.map((r) => r.top)));
  // Vertically only: the document never scrolls sideways and body's margin keeps it clear
  // of the panel, so off-screen means scrolled past, and a mark scrolled past is not one
  // this box is standing on.
  const onScreen = (r) => r.bottom > BANNER_CLEAR && r.top < innerHeight;
  const behindBox = (r) =>
    r.left >= box.left &&
    r.right <= box.right &&
    r.top >= box.top &&
    r.bottom <= box.bottom;
  // A passage and a thing want different rules here, because
  // they are read differently. Covering the tail of a quote is fine — the user has read
  // it, and the mark still names where it starts. A card, a column, a metric is judged as
  // one object, so a box standing anywhere on it is a box between them and the thing they
  // are writing about. ⌥-click made that plain by opening the composer under the pointer,
  // which is by definition inside what was clicked.
  const whole = anchorRuntime.pendingMarks.some((where) => where instanceof Element);
  const touching = (r) =>
    r.left < box.right &&
    box.left < r.right &&
    r.top < box.bottom &&
    box.top < r.bottom;
  const clear = whole
    ? !rects.some((r) => onScreen(r) && touching(r))
    : rects.some((r) => onScreen(r) && !behindBox(r));
  if (!rects.length || clear) return;
  const below = Math.max(...rects.map((r) => r.bottom)) + 8;
  const above = Math.min(...rects.map((r) => r.top)) - box.height - 8;
  if (below + box.height <= innerHeight - 8) return place(composer, left, below);
  if (above >= BANNER_CLEAR) return place(composer, left, above);
  // Neither end has room, which a tall thing reaches easily: a board column is most of the
  // viewport before the box's own height is counted, and place()'s clamp would haul the box
  // back over it — the very thing this is here to stop. So go beside instead, even where
  // the margin is narrower than the box wants; the side is chosen rather than clamped,
  // because the clamp keeps a box on screen by sliding it left, back over the thing it
  // is avoiding.
  const rightOf = Math.max(...rects.map((r) => r.right)) + 8;
  const leftOf = Math.min(...rects.map((r) => r.left)) - box.width - 8;
  place(composer, rightOf + box.width <= rightEdge() ? rightOf : leftOf, top);
}
// The anchor a selection makes: the enclosing section, and the passage as the document
// holds it. Not the selection's own toString(), which is what the reader sees rendered —
// text-transform uppercases an eyebrow or a table header, and the runtime's own chrome
// inside the passage comes along — and a quote the search can't find is no highlight while
// composing and a comment that posts permanently detached. A selection with nothing
// quotable in it yields no quote, which makes it an element anchor on its section: what
// such a selection meant anyway.
//
// The whole of it, however long. A cap here read as an economy and was a claim: the
// stored quote is the passage, so the mark paints it and the comment is on it, and a
// reader who selected a paragraph past the cap got a comment on its opening and a
// highlight that shrank to match — silently, on most of the paragraphs a leaf page
// holds. What the cap was really bounding is the search's pattern, which is where the
// bound now lives (LEAD_CAP), so nothing has to be given up to keep it cheap.
const LANDMARK_CAP = 160;
// How much of a passage's surroundings an anchor writes down. Only the capture decides
// this; the search asks for whatever a given anchor happens to hold.
const CONTEXT = 24;
function selectionAnchor(sel) {
  const range = pageRange(sel);
  const node = range.commonAncestorContainer;
  const holder = node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
  // The neighbours come from the same indexed reading the search uses and stop at
  // the same opaque-widget fences as the file-side capture. The browser knows words
  // a module generated and may quote them; it does not pretend the file can confirm
  // context across their seam.
  const segments = segmentsIn(range);
  const quote = quoteFrom(segments);
  const dataNodes = new Set(
    segments.map((seg) => closestAcross(seg.node, DATUM)).filter(Boolean),
  );
  const [onlyDatum] = dataNodes;
  const datum =
    dataNodes.size === 1 &&
    segments.every((seg) => closestAcross(seg.node, DATUM) === onlyDatum)
      ? onlyDatum
      : null;
  const section =
    datum?.dataset.lfProjection ??
    closestAcross(holder, "[id]:not(.lf-ui)")?.id ??
    null;
  // Identity is the context for projected data. Neighbouring display values may reorder
  // or repeat, so storing their words as prefix/suffix would make incidental layout a
  // second, conflicting answer to which datum the reader selected.
  if (datum)
    return {
      section,
      datum: datum.dataset.lfDatum,
      quote,
    };
  const reading = pageText();
  const [start, stop] = spanIn(reading, segments);
  const prefix = cut(
    neighbourhood(reading.origin, reading.fences, start, CONTEXT, true),
    -CONTEXT,
    Infinity,
  );
  const suffix = cut(
    neighbourhood(reading.origin, reading.fences, stop, CONTEXT, false),
    0,
    CONTEXT,
  );
  // Only what there is. A passage against the document's own edge has no neighbour on
  // that side, and writing that down as an empty string puts a field in the event that
  // never says anything.
  return {
    section,
    quote,
    ...(prefix && { prefix }),
    ...(suffix && { suffix }),
  };
}

// Controls the page is standing on its own account, as against the ones in the runtime's
// layer: a reply's widget is markup frozen in the log, and the layer's own buttons are
// what floating chrome is allowed to sit beside. `data-lf-offer` is what makes a thing
// pressable (`offer`), so this asks after any widget's controls without naming one.
//
// The line saying how many comments a block holds is the one control out here that is
// still the layer's. It wears the marker because a screen reader reaches it by Tab, and
// it is clipped to a pixel where it stands (it only takes a box on focus, fixed under
// the banner) — so a float stepping down past it steps around nothing anyone can see,
// which is exactly the movement this walk exists to prevent.
const pageControls = () =>
  [...document.querySelectorAll(`[data-lf-offer]:not(.${NOTE})`)].filter(
    (c) => !inChrome(c),
  );

// The 💬 button carries the anchor it would open a composer on, so raising it and acting
// on it can't come to different conclusions about what the reader picked. Visibility is
// derived from that anchor and never read back off the stylesheet.
const beside = (rect) => [rect.right + 6, rect.top - 6];
// A float has one more thing to stay clear of, and it is the same kind of thing the
// composer's mark is: a control standing on the page. The floats float and they don't.
// A selection runs to the column's right edge on any line it fills, so `beside` puts
// the button in the margin — which is where a suggestion hangs the row deciding the
// change that selection just covered. The user's own gesture then hid the Accept
// they were reaching for, and the press that would have dismissed the button was the
// press it was covering. The composer's margin placement stands in the same column of
// rows, so it takes the same walk.
//
// Down, and past each in turn, because the margin runs down the page: clearing one row
// can land on the next, and walking a sorted list is the step the rows themselves take to
// nudge apart. place()'s clamp still has the last word, so a float with nowhere left to
// go keeps the best spot rather than leaving the screen.
function placeClear(node, left, top) {
  place(node, left, top);
  const box = node.getBoundingClientRect();
  const sharing = pageControls()
    .map((c) => c.getBoundingClientRect())
    .filter((r) => r.width && r.left < box.right && box.left < r.right)
    .sort((a, b) => a.top - b.top);
  let y = box.top;
  for (const r of sharing) if (r.top < y + box.height && y < r.bottom) y = r.bottom + 6;
  if (y !== box.top) place(node, left, y);
}
let fabAnchor = null;
function showFab(anchor, left, top) {
  fabAnchor = anchor;
  fab.style.display = anchor ? "block" : "none";
  if (anchor) placeClear(fab, left, top);
  paintHere(); // the c row names this anchor, so the line is one more rendering of it
}
// The one way an item under a gesture becomes the composer's anchor, so no two routes
// can come to write different anchors for the same press.
function openOnItem(item, from) {
  showFab(null);
  openComposer({ section: item.id }, "", from.left, from.top);
}
// The button follows the selection. What counts as one is measured on the quote it would
// store, not on the selection's own toString(): those are different strings, and gating on
// the one the reader sees while storing the one the document holds lets a two-character
// quote through behind a rendered three-character selection — a quote short enough to match
// almost anywhere.
const MIN_QUOTE = 3;
// A selection of the page's own words, as against none, a bare caret, or one made inside
// the runtime's own layer. That is the line between a user reaching for a passage and
// one working the chrome, and it is the question every caller here is really asking.
const pageSelection = () => {
  const sel = getSelection();
  return sel && !sel.isCollapsed && pageWords(sel.anchorNode) ? sel : null;
};
// Where a send ends is where typing continues, and the reader has the last word on it.
// A send is a round trip, so this step lands whenever the server answers — long after
// the gesture on a loaded machine — and focusing a box collapses whatever the page had
// selected. A passage picked out while the send was in the wire is a later gesture and
// stands, for the same reason a later edit does. It has less recourse than the edit:
// nothing re-decides the 💬 until the reader gestures again, so the words in front of
// them stop being something to comment on, and no surface says why. Stated once, for
// the three boxes a send can land in, because it is one fact about a send landing.
//
// A box is the whole of it, which is why this is named for typing rather than for
// focus. The panel's other two landings — a resolve and a reopen, each behind a round
// trip of its own — put the reader on a thread node instead, and Chrome collapses the
// selection for a landing that takes a caret, not a control as such — a button and a
// select leave it standing, and so does a `tabindex="-1"` div. Same
// shape, then, and not the same steal: those two keep the standing place a control
// that folds away with its thread owes the reader.
function landTyping(box) {
  if (!pageSelection()) box?.focus({ preventScroll: true });
}
// A drag stops where the hand stopped, not where the reader aimed: a release two glyphs
// short of a word's end meant the word, and the capture would store the fragment as if
// the fragment were the point. So the pointer path grows a selection outward — never
// inward — until each end sits on a boundary of the same word units the runtime already
// reads sequences by (textUnits), and only where the end fell strictly inside a
// word-like unit. An end resting on a boundary, in space, or against punctuation stays
// exactly where the reader put it, and keyboard selections never come here at all:
// shift-arrow is the reader being precise, and precision is not a thing to correct.
//
// One end, because the two are the same question asked at two places, and the words are
// read in the indexed text every other reading of the page uses. That is what keeps a
// snap from claiming what the capture would refuse: a word never continues across a
// fence, and never across a block seam, which is where the collapse writes the space the
// markup doesn't hold. One seam is snapping's own, past what the collapse knows: where
// machine-placed words (data-lf-gen) stand flush against the author's — a chip row is
// written with no space after the title it follows — the two runs read as one word, and
// growing across that seam would hand a selection of the chip the title too.
function snapOut(reading, at, back) {
  const { raw, origin, fences } = reading;
  const behind = fences.filter((f) => f <= at).at(-1) ?? 0;
  const ahead = fences.find((f) => f >= at) ?? raw.length;
  const spoke = (o) => elementOver(o.node).closest("[data-lf-gen]");
  // An EDGE's neighbours are the nearest characters, not the nearest cells: an empty
  // text node is an empty segment, which puts two EDGEs flush, and every reader of
  // `origin` steps over its nulls.
  const joined = (i) => {
    if (origin[i] !== null) return true;
    let a = i - 1;
    while (origin[a] === null) a--;
    let b = i + 1;
    while (b < origin.length && origin[b] === null) b++;
    const prev = origin[a];
    const next = origin[b];
    if (!prev || !next) return false;
    return blockOf(prev.node) === blockOf(next.node) && spoke(prev) === spoke(next);
  };
  const inRun = (i) => !/\s/.test(raw[i]) && joined(i);
  let lo = at;
  while (lo > behind && inRun(lo - 1)) lo--;
  let hi = at;
  while (hi < ahead && inRun(hi)) hi++;
  let run = "";
  let boundary = 0; // the end's own index within `run`
  const from = []; // from[i] = the raw index run[i] came from; an EDGE holds no character
  for (let i = lo; i < hi; i++) {
    if (origin[i] === null) continue;
    if (i < at) boundary++;
    from.push(i);
    run += raw[i];
  }
  const word = textUnits.segment(run).containing(boundary);
  if (!word || word.index >= boundary || !word.isWordLike) return at;
  return back ? from[word.index] : from[word.index + word.segment.length - 1] + 1;
}
// An end the snap didn't move keeps the boundary the browser gave it: a drag out into
// chrome ends past the last quotable character, and rewriting that end from the reading
// would pull the visible selection off words the reader chose to cover. The gesture's
// direction survives too, or the shift-click that next extends the selection would
// extend it from the wrong end.
function snapSelection() {
  if (!anchoringReady) return;
  const sel = pageSelection();
  if (!sel) return;
  const range = pageRange(sel);
  const segments = segmentsIn(range);
  if (!segments.length) return;
  const reading = pageText();
  const [start, stop] = spanIn(reading, segments);
  const lo = snapOut(reading, start, true);
  const hi = snapOut(reading, stop, false);
  if (lo === start && hi === stop) return;
  const head =
    lo === start
      ? [range.startContainer, range.startOffset]
      : [reading.origin[lo].node, reading.origin[lo].offset];
  const tail =
    hi === stop
      ? [range.endContainer, range.endOffset]
      : [reading.origin[hi - 1].node, reading.origin[hi - 1].offset + 1];
  // Backward means the anchor sits past the range's start — asked of boundary points,
  // because node order misreads containment: a focus on the element holding the anchor's
  // text node both precedes and contains it.
  //
  // Both points have to be in one tree to be compared at all. Inside an x-shadow widget
  // they are not: the selection's own anchorNode is the light-DOM one Chrome clamped to
  // the host, while the range is the composed one this snapped from, and comparing them
  // throws rather than answering. A selection that never left the widget has no direction
  // worth recovering — there is one text node under the pointer either way — so it snaps
  // forward, which is what a drag inside one block does regardless.
  const probe = document.createRange();
  probe.setStart(sel.anchorNode, sel.anchorOffset);
  const comparable =
    sel.anchorNode.getRootNode() === range.commonAncestorContainer.getRootNode();
  const backward =
    comparable && probe.compareBoundaryPoints(Range.START_TO_START, range) > 0;
  if (backward) sel.setBaseAndExtent(...tail, ...head);
  else sel.setBaseAndExtent(...head, ...tail);
}
// What the button is on, decided here alone. The selection is read fresh; a visual find —
// a clicked diagram or image, which has no text to select — comes in from the click that
// found it, and a qualifying selection outranks it. The last branch is why order between
// that click and the update queued behind its mouseup never matters: no selection speaks
// for an element anchor, so the selection's absence takes down only a quote, and the
// queued re-decide lands on the same outcome.
function updateFab(visual) {
  if (!anchoringReady) {
    showFab(null);
    return;
  }
  const sel = pageSelection();
  const anchor = sel ? selectionAnchor(sel) : null;
  if (anchor?.quote.length >= MIN_QUOTE)
    showFab(anchor, ...beside(pageRange(sel).getBoundingClientRect()));
  else if (visual) showFab({ section: visual.id }, visual.x + 6, visual.y - 40);
  else if (fabAnchor?.quote) showFab(null);
}
// Where the pointer stopped is not the question; where the selection is, is. The guard
// exists so a mouseup inside the runtime's layer — a click in the panel, the composer —
// can't re-decide the button out from under an open draft. A drag that ends on a widget's
// control is the opposite case: the user was selecting that control's label, and a
// tab's name runs to within a few pixels of the strip button's padding, so the mouseup
// lands on chrome while the selection is the page's. The snap runs in the same queued
// step that raises the button, so the button lands beside the selection as snapped and
// the capture reads the one the reader is looking at — and only for the primary
// button, because a right button's release precedes its context menu, and growing the
// selection there rewrites what Copy was aimed at.
document.addEventListener("mouseup", (ev) => {
  if (!pageWords(ev.target) && !pageSelection()) return;
  setTimeout(() => {
    if (ev.button === 0) snapSelection();
    updateFab();
  });
});
// Selections made from the keyboard (shift-arrows, ⌘A) deserve the same button. Typing in
// a box never does, whatever is selected elsewhere.
document.addEventListener("keyup", (ev) => {
  if (takesLetters(ev.target)) return;
  if (!pageWords(ev.target) && !pageSelection()) return;
  setTimeout(updateFab);
});
// Floating chrome getting out of the way of a press somewhere else, which is a fact about
// the press rather than about who receives it: the aim takes a press away from the page
// (see claimPress) and must not take this with it, or the keyboard reference stays up over
// the composer that press just opened. Hence one function, called from both.
// The two side panels are absent from it on purpose. A float answers the press in front
// of it and stands down behind it; the comment panel and the leaves tray are
// workspaces the reader stood up, kept through a reload (PANEL_KEY, TRAY_KEY) and so
// through a click all the more — a tray any press removes cannot be watched while
// working, which is the tray's point. Each closes by its own button, its key, or Esc.
function standDown(target) {
  if (!target.closest?.(".lf-fab, .lf-composer")) {
    showFab(null);
    // Keep a composer that holds unsent text open so a stray click can't drop it;
    // Cancel discards explicitly, and the draft is persisted regardless. Asked only of a
    // composer that is up, so an ordinary press in the page repaints nothing.
    if (composerOpen && !composerInput.value) hideComposer();
  }
  if (helpOpen && !target.closest?.(".lf-help")) showHelp(false);
  // The press on the button itself is its own toggle, so it is not an outside click;
  // without that the open and this close would both run and the menu could never open.
  if (versionMenuOpen && !target.closest?.(".lf-version-menu, .lf-version"))
    showVersionMenu(false);
}
document.addEventListener("mousedown", (ev) => standDown(ev.target));

// What a click on the page means, decided once. A mark under the pointer opens its thread;
// otherwise a diagram or image is a find handed to updateFab, which raises the same 💬
// button on an element anchor — the id the visual lives under — unless a selection
// outranks it.
//
// Once, because the hit-test reads layout and opening the panel rewrites it. Two handlers
// each asking `markAt` looked independent and were not: the first one's setPanel() reflowed
// the document out from under the second, which then missed the very mark it had just
// opened and raised the comment button on top of it — leaving an element anchor set, which
// midComposition() reads, so the page quietly stopped following new versions. The rule this
// file already carries covers it: a guard that reads state another function wrote is a sign
// the two are one function.
// What a click anchors on whole, because there is no text in it to select: the page's
// own pictures, and every widget that declares it renders as one.
const visualSel = () =>
  [...tagsDeclaring((e) => e["x-visual"]), "svg", "img", "figure"].join(",");
// While ⌥ is held the page shows what a click would take — the item under
// the pointer wears the aim's box (refreshAim), so the chord
// answers "which" before the click rather than asking the user to press and find out.
// `aiming` is the state and the class is a rendering of it; nothing reads the class back.
//
// It comes off on blur as well as on keyup, because the chord that switches windows takes
// the keyup with it, and a page left armed under nobody's hand is a claim the user
// cannot dismiss.
let aiming = false;
// The aim chord, declared once: the key listeners, the press guard (claimPress) and the
// reference's row all read this object. It is the register's one row that is not a key —
// a modifier held while the pointer clicks — so it binds nothing and carries no press, and
// the rule that keeps it off the key line is the same one that keeps F7 off it. The label
// is spelled from the modifier through the register's own table rather than written out
// twice in two platforms' glyphs.
const AIM = {
  modifier: "Alt",
  keys: [],
  label: `${spell("Alt")} click`,
  does: "Comment on the item under the pointer, whole",
};
// What the pointer is over, asked of the page rather than of an event, so pressing the key
// without moving the mouse answers too — the user holds ⌥ to find out what they would
// get, and the answer cannot wait for them to jiggle the mouse first. An open composer
// is no reason to say nothing: the press still acts (it re-anchors the box), so the
// promise still paints — what stood down here left that one press made blind.
function aimedItem() {
  if (pointer.x < 0) return null;
  const at = document.elementFromPoint(pointer.x, pointer.y);
  return at && !inChrome(at) ? itemAt(at) : null;
}
function setAiming(on) {
  aiming = on;
  document.body.classList.toggle("lf-aiming", on);
  refreshAim();
}
addEventListener("keydown", (ev) => ev.key === AIM.modifier && setAiming(true));
addEventListener("keyup", (ev) => ev.key === AIM.modifier && setAiming(false));
addEventListener("blur", () => setAiming(false));
// The keydown above can go unheard: a page reloaded under a held key — the poll following
// a new version — never hears it, and claimPress reads live modifier state, so every
// press on the new page was claimed while nothing could paint the promise. Mouse events
// carry that same live state, so the move re-derives the arm from the freshest carrier,
// through the one setter, rather than trusting the latch.
document.addEventListener("mousemove", (ev) => {
  // This listener used to follow the pointer recorder in the monolith. Keep that
  // ordering explicit now that the recorder is installed by the anchor module.
  pointer.x = ev.clientX;
  pointer.y = ev.clientY;
  const held = ev.getModifierState(AIM.modifier);
  if (held !== aiming) setAiming(held);
  else refreshAim();
});

// ⌥-click means the item under the pointer, whatever it holds. It costs the page no
// chrome and the user no selection, and it reaches an item whose words are all
// inside a control. What it costs is discoverability, which the cursor answers as far as
// a modifier can: while the key is down the pointer says a click will aim.
//
// The press it aims with is the aim's alone, so it is taken at capture — ahead of every
// handler out on the page, and of the browser's own defaults. Read on the way back up
// instead, it was a press the page had already had: ⌥-clicking an option card opened the
// composer *and* picked the option, sending Claude a decision the user never made,
// and ⌥-clicking a tab's name aimed at the widget while switching the panel under it.
// Every widget that takes a press had it, because none of them was ever told. The box
// is the promise, and a press keeps it by being the only thing the press does.
//
// Claimed at the press rather than judged at the click, because the press is where ⌥
// states what the user meant. A key released before the button comes back up would
// otherwise leave a press already taken from the page doing nothing at all.
//
// What is armed is the page rather than the items on it: an armed press aims where there
// is an item under it, and acts on nothing where there isn't. That is what the cursor is
// already saying, over everything the chrome doesn't hold out of it. Falling through to
// the page instead would leave the user reading the box to find out which of the
// two a press is about to be — and a suggestion's ✓ Accept hangs in the page's own
// column, outside the element it decides, so there is nothing above it to aim at and
// getting that wrong sends Claude a decision.
//
// A press is its down, its up and the click they make, a double press one event more, and
// the aim takes every one of them: which a widget listens on is not something the runtime
// can know, and lf-draft already opens its editor on the second mousedown rather than on
// the dblclick, for reasons of its own.
const PRESS_EVENTS = [
  "pointerdown",
  "mousedown",
  "pointerup",
  "mouseup",
  "click",
  "dblclick",
];
// The press the aim has taken — {item} for the ⌥ aim, {design} for design mode — until
// the next one starts.
let aimedPress = null;
function claimPress(ev) {
  // Made and dropped at the same moment, which is the start of a press: a drag already
  // under way when the key goes down keeps the events it is waiting for, and one that
  // ends after the aim's own press can still be ended.
  if (ev.type === "pointerdown") {
    const aim = ev.getModifierState(AIM.modifier) && !inChrome(ev.target);
    const design = !aim && designPress(ev.target) ? designTarget(ev.target) : null;
    aimedPress = aim ? { item: itemAt(ev.target) } : design ? { design } : null;
    if (aimedPress) standDown(ev.target);
  }
  if (!aimedPress) return;
  // A click carrying no press belongs to the control it is on rather than to a press that
  // has already finished: `offer` calls click() to supply the keys a span doesn't come
  // with, and the user's Enter must reach the control they are on whatever the last
  // press was.
  if (ev.type === "click" && !ev.detail) return;
  // Not on pointerdown, whose cancellation takes the mouse events with it — the click this
  // aim ends on included. On mousedown, which is where the selection, the focus and a
  // native drag would start, and on the click, since ⌥ on a link is a download.
  if (ev.type === "mousedown" || ev.type === "click") ev.preventDefault();
  ev.stopPropagation();
  if (ev.type !== "click") return;
  const from = { left: ev.clientX + 6, top: ev.clientY - 40 };
  if (aimedPress.item) openOnItem(aimedPress.item, from);
  else if (aimedPress.design) openOnDesign(aimedPress.design, from);
}
for (const type of PRESS_EVENTS) document.addEventListener(type, claimPress, true);

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

document.addEventListener("click", (ev) => {
  if (!pageWords(ev.target)) return;
  // A press design mode did not take at the press is a press on prose: a drag that
  // selected words has the 💬 (updateFab, on the mouseup) and is not a click on the
  // block; a plain click comments on the block it landed in.
  if (designOn) {
    if (pageSelection()) return;
    const target = designTarget(ev.target);
    if (target) openOnDesign(target, { left: ev.clientX + 6, top: ev.clientY - 40 });
    return;
  }
  const threadId = markAt(ev.clientX, ev.clientY);
  if (threadId) return showThread(threadId);
  if (ev.target.closest?.("a")) return;
  const sel = visualSel();
  let visual = ev.target.closest?.(sel);
  if (!visual) return;
  // Outermost visual: a rendered diagram's inner svg carries a generated id;
  // the anchor belongs to the widget (or figure) that holds it.
  while (visual.parentElement?.closest(sel)) visual = visual.parentElement.closest(sel);
  const id = visual.closest("[id]:not(.lf-ui)")?.id;
  if (!id) return;
  updateFab({ id, x: ev.clientX, y: ev.clientY });
});

selectionComposerRuntime = createSelectionComposer(runtime, {
  clearDraft,
  composer,
  composerCancel,
  composerInput,
  composerSend,
  designIsOn: () => designOn,
  draftContexts,
  fab,
  fabAnchor: () => fabAnchor,
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
  keys: ["c"],
  does: () => generalHint(),
  line: "comment",
  // Dead while the reader has a passage or an item in hand. `j` is a page key that
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
  // — the one `Enter` reaches from here and `g c N` addresses. Standing in a
  // conversation is the page's second destination, so the row stands down and lets it
  // answer, and the two ways into a thread's box stay one landing. A resolved card has
  // no box to be the nearer answer, and standingConversation reads the box rather than
  // the class, so the press there is the general box's after all.
  when: () => !fabAnchor && !standingConversation(),
  run: () => generalInput.focus({ preventScroll: true }),
};

const syncGeneral = wireInput(generalInput, {
  // The box has no anchor to decide it at an open, so what it posts is decided at the
  // send, by the mode standing then — and the hint says which, so the reader typing in
  // design mode knows their remark is about the layer as a whole.
  hint: generalHint,
  // The box's own address, the way a thread's reply carries "g c 2": unfocused, the
  // placeholder reads "Comment on the page · c", which is the panel's own c and the
  // second press of the page's. One key rather than a chord, because this box is the
  // panel's own and the scope that offers it is the one the reader is standing in.
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
    const event = { kind: "comment", version: runtime.currentVersion, text };
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
  const approved = runtime.events.some((e) => e.kind === "done");
  approveBtn.disabled =
    approving ||
    !document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented) ||
    approved;
  approveBtn.textContent = approved ? "✓ Approved" : "✓ Looks good";
}
approveBtn.onclick = async () => {
  if (approving) return;
  approving = true;
  approveBtn.setAttribute("aria-busy", "true");
  paintApproval();
  try {
    await post({ kind: "done", version: runtime.currentVersion, text: "Looks good" });
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

// ---------- the g chord: the page's addresses ----------
// g arms a mode in which a letter names one of the page's lists and a digit is a place in
// it: `g c 2` is the second open comment's reply box, `g a 1` the first thing the page is
// waiting on, `g l 3` the third link. Two completions take no digit: `g g` is the top of
// the page and `g G` the bottom — each edge is one place, so the second key is the whole
// address. `g G` rather than vim's bare G because g is the page's one go-to prefix, and
// an edge is one more place it names rather than a second leader. Naming a list shows it
// — the panel opens for the comments — and each of its addressable members then wears its
// digit as a chip, so the addresses are on screen wherever the reader is looking. A digit
// consumes the mode; so
// does Escape, and so does focus entering a box. Any other key disarms and then runs with
// its ordinary meaning, which the dispatcher spells as disarming and walking the stack
// again rather than as a rule of its own — a mistyped g therefore costs the reader nothing
// beyond the press their next key was going to make anyway.
//
// The chord was one list deep once — g then a digit, and the digit meant a reply box —
// which spent the whole of a leader on the one list that had asked for it first. The letter
// is what opens that: a second list costs a letter rather than a second chord, and the line
// says `g` alone rather than a range that only ever counted threads.
//
// Which lists there are is this table and nothing else. The chord's scope, the chips, the
// line's words and the reference are all readings of it, so a fourth list is an entry here
// rather than an edit to four consumers, and nothing that reads the table asks which list
// it is holding. One place names a list at all, and it is not a reader of the table: a
// member with a surface of its own has to say which list that surface belongs to, which is
// the reply box's placeholder (COMMENTS, below). An entry says its letter, the word every surface calls the list by, the sentence
// the reference reads, its members in address order, and how to arrive at one. `spot` is
// where the chip hangs when that is not the member itself — a comment's address belongs on
// the box the digit lands in, not on the thread's far corner.
// What the document holds, in reading order, as against what the chrome holds: the banner,
// the versions and the leaves tray have keys of their own, and a comment's message is the
// panel's rather than the page's. The addresses read the document through here, where
// a scope naming a platform key reads `pageQueryAll` and crosses the declared shadow roots
// as well: an address is a place in a list the reader counts down the page, and a tree a
// module built has no place in that count, while what the reader can stand on is wherever
// the markup ended up — a diff stages a <details> per file in a root they tab straight
// into.
//
// The whole document and not the parts on screen, which is the tempting reading and the
// wrong one twice over. An address that counted what is in the window is an address that
// means a different link at every scroll position, so a reader who has just learnt that the
// PR is `g l 2` is wrong a moment later; and it would put the key line's own truth on the
// scroll, since a row that goes dead as the page moves is a row the line has to be
// repainted to stop promising — a paint measured at 1.3ms on the gallery, on every scroll
// frame of every page, for one row. Document order costs the pages holding more than nine
// links their tail, which is the bound every list here has.
//
// Above the table rather than beside the other readings below it, because an entry
// holds the function itself and the array literal reads it as the module evaluates.
const pageParts = (sel) =>
  [...document.querySelectorAll(sel)].filter((el) => !inChrome(el));
const pageLinks = () => pageParts("a[href]");
// The summaries rather than the boxes they head: a summary is what the reader stands on,
// what a chip sits beside, and the only part of a disclosure the platform gives a key to —
// so a <details> whose author wrote no summary has nothing here to address. Every
// disclosure and not the shut ones, for the reason above: a list counting what is shut
// means a different section the moment one of them opens.
const pageDisclosures = () => pageParts("details > summary");
// Narrower than the disclosure scope's own reading on purpose, and in both directions: an
// address is a place in a list the reader counts down the authored page, so it stops at the
// document where the scope crosses declared roots, and it counts the platform's spelling
// where the scope also answers ARIA's. So a settled option group takes the arrows and takes
// no digit, and `g d` can say three where four things fold. Widening it is not free —
// `go` scrolls the box and leans on `reveal`, which cannot open a group from its row — and
// the count a reader wants under `g` is of the sections the author wrote.

// How many members of a list a digit can reach. The bound is the keyboard's — ten digits,
// one of them no ordinal — and not any list's, so it is stated once here rather than in
// each entry.
const ADDRESS_CAP = 9;
// The one entry with a name of its own, because one of its members has a standing
// surface to speak its address on: a reply box's placeholder says "Reply · g c 2" at
// all times, and the panel builds that box (threadNode). Every other list is reached
// through the table.
const COMMENTS = {
  key: "c",
  word: "comments",
  does: "Go to the nth open comment's reply box",
  list: openThreads,
  spot: (thread) => thread.querySelector(":scope > .lf-compose"),
  // What it takes to show this list, and the way back. The panel holds it and draws
  // nothing while closed, so a letter that named it and left the panel shut painted no
  // chip at all. An entry whose members are on the page states no reveal at all.
  //
  // The undo is the entry's for the same reason the reveal is: core never learns what a
  // panel is. It states none where the panel already stood, because then the aim put
  // nothing there — and closing it would be the chord taking back something that was
  // never its to take.
  reveal: () => {
    if (panelOpen) return null;
    setPanel(true);
    return () => setPanel(false);
  },
  // stepThread-to-nth and its Enter in one press. The box by its place in the thread and
  // not the first textarea inside it, a message being free to carry a widget with one of
  // its own — a draft's open editor stands before the reply box in the DOM.
  go: (thread) => landIn({ held: thread, box: thread.querySelector(SAY_BOX) }),
};
const ADDRESSES = [
  COMMENTS,
  {
    key: "a",
    word: "asks",
    does: "Go to the nth thing this page is waiting on you for",
    // The list n/p walk, addressed rather than stepped: one reading, so the digit and the
    // walk cannot disagree about which ask is the third one. The arrival is handed that
    // whole list and not the nine a digit can spell, so what it announces is the ask's
    // place among everything the page is waiting on.
    list: openAsks,
    go: (ask) => goToAsk(ask, openAsks()),
  },
  {
    key: "l",
    word: "links",
    does: "Go to the nth link",
    list: pageLinks,
    // Focus, not a follow: g says go, and what a focused link then answers is the
    // platform's Enter, which the link scope names on the line. A press that navigated
    // would be a door with no landing to look at first.
    go: (link) => {
      scrollToElement(link);
      link.focus({ preventScroll: true });
    },
  },
  {
    key: "d",
    word: "disclosures",
    does: "Go to the nth disclosure and open it",
    list: pageDisclosures,
    // Opening is the arrival and not a press that follows it. Every arrival here reveals
    // the collapsed containers on its way — this is the one whose target is the container,
    // so the reveal that was travel for the others is the whole motion for this one, and a
    // reader who wanted the section open has it open having asked once. The scroll takes
    // the box rather than the summary, since a section taller than the window starts at its
    // start where a centred summary would put half the screen above it. Standing on the
    // summary afterwards leaves the platform's own press to close it again, which the
    // disclosure scope names on the line.
    go: (summary) => {
      scrollToElement(summary.parentElement);
      summary.focus({ preventScroll: true });
    },
  },
];
// A list's addressable members, and the range its label names. Capped where it is read
// rather than where each list is written, so an entry states what it holds and this states
// what the keyboard can reach.
const addressed = (entry) => entry.list().slice(0, ADDRESS_CAP);
const range = (n) => (n > 1 ? `1–${n}` : "1");
// How an address is spelled, in one place and off the row that binds the key (GOTO): the
// keys it takes, in press order. A member with a standing surface of its own says the
// whole motion there — a reply box's placeholder reads "Reply · g c 2" — and the chord's
// own chip is built from the same array. Written out at each of them, `g` was a letter
// three sites had agreed on and none could correct.
//
// An array rather than a string, because the surfaces drawn inside the armed window differ
// only in how much of the address the reader has already pressed: the key line drops those
// keys, having said them once in the chip that heads it, and an address on the page dims
// them. `n` is a digit on a chip and a range on the line, which is the same array either
// way — spelled out at both, the space between letter and digit was a third site to keep
// in step.
const addressKeys = (entry, n) => [labelOf(GOTO), entry.key, String(n)];
const addressLabel = (entry, n) => addressKeys(entry, n).join(" ");
// How far the chord has come: `g`, and the list's letter once one has named a list. Every
// surface that shows an address asks it — the chip that heads the key line, the ranges
// beside it, the reference's rows and the dimmed half of a chip on the page — so none of
// them can disagree about which press comes next.
//
// The chord's stage and not the reader's presses, which is the reading the reference needs:
// `?` reaches it from a page nobody has armed (declaredStack walks every scope, live or
// not), and its rows belong under a heading that says "With g armed". So `g` is spoken for
// there by the section, exactly as the key line's own chip speaks for it, and the rows say
// what remains inside the mode either way. A chip is the one surface with nothing around
// it to carry the leader, and it is drawn only while the window is up, so its two questions
// — how far in, and how much the surroundings already say — have one answer.
const chordKeys = () => [labelOf(GOTO), aimedList?.key].filter(Boolean);
// An address as the page wears it: the whole of it, the keys already pressed standing back
// and the ones still to come lit. The whole of it, because a chip is the address — the same
// one its reply box's placeholder speaks while nothing is armed at all, and a chip saying
// `c 2` two pixels from a placeholder saying `g c 2` was a second spelling of one motion,
// the shorter of which reaches nothing from a standing start.
//
// Both halves are set at the chip's one size, and the split is carried by ground: the spent
// keys sit on the chip's own, the live ones on a lit block. Size was the channel once — the
// spent keys two points smaller — and it cost more than it bought. One box held two type
// sizes, which reads as a fault rather than a hierarchy; and because the split moves a key
// from one size to the other, naming a list re-set every chip on screen, each one narrowing
// 2.4px and sliding 1.2px under the eye that was reading them. Ground carries the same
// distinction and takes no advance, so a press lights one more key and moves no glyph.
// That last part is the stylesheet's doing and not this function's: the lit block's padding
// is cancelled by an equal negative margin. Paid for in advance instead, the key crossing
// between the halves stepped 3px on the press — measured, and larger than the 1.2px slide
// this replaced, so the fault would have survived one glyph smaller.
//
// The space between the two halves is the address's own, the one `addressLabel` joins on,
// so what the chip reads is what every other surface spells. It is a text node and the box
// is block rather than flex for exactly that reason: flex drops a whitespace-only child, and
// the chip came out `ga 1`.
//
// `lf-lit` and not `lf-live`, which this layer already spends on the visually-hidden live
// region: a span wearing that name is clipped to a pixel by the stylesheet's own rule, so
// the half of the address still to be pressed would have been drawn nowhere at all.
//
// Built only inside the armed window, which is where the chord's own keys are never none —
// and, past the letter, only for the list the chord has named (paintAddresses narrows to
// `aimedList` there), which is what makes those keys a prefix of this address rather than a
// different list's. So `.lf-spent` is always present on a chord chip and never on the bare
// digit an options group wears, which is how one stylesheet dresses both.
const addressChip = (entry, n) => {
  const keys = addressKeys(entry, n);
  const made = chordKeys().length;
  const chip = el("span", "lf-address");
  chip.append(
    el("span", "lf-spent", keys.slice(0, made).join(" ")),
    " ",
    el("span", "lf-lit", keys.slice(made).join(" ")),
  );
  return chip;
};

// Whether the chord is up, and the list a digit addresses once a letter has named one.
// The armed window is a mode the whole keyboard is in, and a digit pressed inside it
// belongs to the chord wherever focus sits. A widget's own digit keys used to have to ask
// this before consuming one; they no longer do, and lf-options no longer imports it — the
// chord's scope claims everything, so the dispatcher never reaches an inner scope while the
// window stands, and the mode enforces itself where it was a rule each widget had to keep.
//
// `aimedList` and not `aimed`, which this file already spends on the aim chord's element
// (refreshAim, aimTarget, aimBox): two concepts under one word, in one file, shadowing each
// other inside the functions that hold both.
let chordArmed = false;
let aimedList = null;
// What the aim put on screen, and the way to take it back. Naming a list that draws
// nothing until asked is one press doing two things — it narrows the window and opens the
// panel the chips are drawn from — so the press that gives the letter back has to give
// both back, or the reader keeps a layer they never asked for and the chord costs three
// presses out for two in. That is the keyboard-is-a-stack rule failing inside the fix
// written for it, which is how it was found.
//
// Every unused way down takes it back: Escape off the aim, a stray key, focus entering a
// box. What makes a way down *used* is the reader landing in what the reveal showed, which
// `keepShown` states — and both routes there have to say it. The digit is one; a click into
// the panel the chord just opened is the other, and with only the digit exempt that click
// closed the panel under the reader's own pointer and dropped them on the toggle button.
let aimShowed = null;
const keepShown = () => (aimShowed = null);
// Arming, aiming and disarming are one call, because they are one window: naming a list
// re-opens it rather than starting a second, and every way down — Escape, a stray key,
// focus entering a box — takes the aim with it.
//
// It stands until one of those, where it stood for a second and a half. A timeout is how a
// keyboard resolves an ambiguous prefix, and there is none here: `g` is a prefix and
// nothing else, any key the chord does not bind disarms it and then runs with its ordinary
// meaning, so nothing is ever swallowed by a window left open. What the clock did instead
// was charge the reader for reading the menu the press had just painted — and a letter
// arriving a moment late is not a no-op but the page's own key, so a slow reader pressing
// `l` got the leaves tray rather than the links.
function setChord(on, list = null) {
  // Armed over a control that has claimed Escape, one press would have two owners — the
  // control's rung and the chord's cancel — so the chord refuses to arm there at all.
  if (on && !chordArmed && claimsEsc(focused())) return;
  chordArmed = on;
  aimedList = on ? list : null;
  // A list the reader cannot see is a list wearing no addresses: the panel holds the
  // comments and draws nothing while closed, so naming that list opens it, and the chips
  // land on boxes that have a geometry to be placed from. The open belongs here rather
  // than in the arrival, where it left the letter painting nothing at all.
  //
  // Taken back before the next state is written, so an aim ending — into the bare window,
  // or out of the chord altogether — leaves the screen as the letter found it.
  aimShowed?.();
  aimShowed = list?.reveal ? list.reveal() : null;
  // The chips are the eye's copy; the window itself is spoken, or the mode change is
  // silent to exactly the reader who can't see them. Off the rows either way, since the
  // rows are what the window answers now — the letters at the first stage, the named
  // list's digits at the second — and a sentence written here for the second would have
  // been the row's own words, restated where nothing could correct them.
  if (on) announce(`Go to — ${saying(GO.rows)}`);
  paintHere();
}

// The chips: one per addressable member, drawn in the chrome's layer (addressLayer) and
// placed from the member's own visible box, so a chip cannot claim room the page has
// already refused — a thread scrolled out of the panel's list, a card half out of a board.
//
// Each carries its whole address, which is what lets every list paint at once: a bare
// digit promises nothing until a letter has named a list, so the chips could only follow
// the letter, and the press that opened the mode moved nothing the reader could see.
//
// The layer is the chrome's rather than the page's own markup for the reason every mark is
// (see "Paint; don't wrap"): the addressable things include links set mid-sentence, and a
// span written into a paragraph to carry a number is a span the passage walk then has to
// know about.
//
// Every chip is built detached and the layer takes them in one write, which is the rule
// the legend states for this same layer: a chip in the tree is a DOM write, and the next
// member's rect read after one is a layout forced per member — up to nine per list, and
// every list until a letter narrows them, on every scroll frame an armed window stands
// through.
function paintAddresses() {
  const chips = [];
  if (chordArmed) {
    const clips = new Map();
    // The banner stands over the page rather than in it, so shownRect says nothing about
    // it — that reading is what the page's own boxes clip, and the bar clips none of them.
    // The chip is the one thing that has to care, being drawn above the bar: placed on a
    // corner the bar has taken, it is an address floating over the status line, naming
    // nothing the reader can see there. So it rides the covered edge, and a member with
    // nothing left below that edge wears no chip at all.
    const covered = banner.getBoundingClientRect().bottom;
    // Every list until one is named, and then that one alone: the offer narrows as the
    // chord advances, and the addresses a reader was already reading keep their places.
    // Narrows rather than summons, for every list drawn where the reader can see it — a
    // list that draws nothing until revealed (the shut comment panel) has no box to place
    // a chip from, so its letter is what both reveals it and paints it.
    for (const entry of aimedList ? [aimedList] : ADDRESSES) {
      for (const [i, member] of addressed(entry).entries()) {
        const r = startsAt(entry.spot?.(member) ?? member, clips);
        if (!r || r.bottom <= covered) continue; // nothing to see, nothing to address
        const chip = addressChip(entry, i + 1);
        if (r.top < covered) chip.classList.add("lf-in");
        chip.style.left = `${r.left}px`;
        chip.style.top = `${Math.max(r.top, covered)}px`;
        chips.push(chip);
      }
    }
  }
  addressLayer.replaceChildren(...chips);
  // A chip that lands on one already drawn is taken down. Two addressable things can start
  // within a chip's width of each other — footnote markers in a row, a link that is the
  // whole of a summary — and stacked chips do not read as two: the one underneath shows an
  // edge, and its neighbour's digit is the number the reader takes for its own. That is the
  // one failure worse than saying nothing, because pressing it goes somewhere else.
  //
  // Dropping it costs nothing the page had promised. A chip is already only drawn for a
  // member the reader can see, and an address holds whether or not its chip does — so this
  // is the same answer, given to a member the page has no room to say it about rather than
  // to one that has scrolled away.
  //
  // Every box is read after the one write and every removal made after the last read, so
  // the pass stays at the single layout the write already cost.
  //
  // The key line is standing in that same corner and goes in first, so a chip loses to it
  // the way it loses to a chip already drawn. It is the legend saying what these digits
  // mean, on screen exactly as long as they are, so covering it is the one collision that
  // takes away the reader's answer rather than one of its members. The bar at the other
  // edge is dodged earlier and by clamping, because a chip has somewhere to go there: the
  // covered edge is above the member, while sliding clear of a line at the foot would put
  // the chip on a member it no longer sits on.
  const kept = [keylineEl.getBoundingClientRect()];
  const piled = [];
  for (const chip of chips) {
    const box = chip.getBoundingClientRect();
    if (kept.some((standing) => overlaps(box, standing))) piled.push(chip);
    else kept.push(box);
  }
  for (const chip of piled) chip.remove();
}
// Whether two boxes share any pixel. Touching edges do not, so two chips laid exactly a
// chip's width apart sit side by side rather than one of them being taken down. That
// boundary is the chip's own width and moves with it — the face is a little wider than it
// was — so what survives a crowded line is a fact about the face rather than a constant,
// and a page whose members used to clear it by a pixel is not promised to now.
const overlaps = (a, b) =>
  a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
// A page that moves under an armed window moves the boxes the chips were placed from, so
// the chips follow it rather than standing where the page used to be. Capture, because the
// panel's list and a board's own overflow scroll in boxes of their own and a scroll event
// does not bubble.
//
// Only while the chord is armed, which is why this is a listener of its own rather than a
// line in the page's own repaint door (pageShifted): what the line says about the chord
// holds at every scroll position, no list's membership moving with the page, so the door
// that repaints on every scroll of every page would be repainting for nobody. Armed, the
// paint is the whole of paintHere — the ring and the line are cheap beside the chips, and
// one door is what stops the chips having a repaint set of their own to keep in step.
addEventListener("scroll", () => chordArmed && paintHere(), {
  capture: true,
  passive: true,
});
addEventListener("resize", () => chordArmed && paintHere());

// ---------- what the page's keys are live over ----------
const hasThreads = () => openThreads().length > 0;
// The focused thread, one predicate: the row the line paints and the press the dispatcher
// takes ask the same question, so they cannot disagree about which thread this is. Not a
// control inside it, whose own press is its own; nor a resolved thread, which has no reply
// box for Enter to reach and no Resolve for x to press.
const focusedThread = () => {
  const active = document.activeElement;
  return active?.classList?.contains("lf-thread") ? active : null;
};
// The item the reader is standing in, which is what a press means when they have pointed
// at nothing. The ⌥ aim reaches an item through the pointer and the keyboard reached none
// at all: an address put the reader on an option and `c` still offered them the page.
//
// The open ask where the reader is standing on a control that works it, and the innermost
// item everywhere else. `g a 1` names the question rather than the first of its options,
// and the control the walk stands them on is one part of it (standOn) — so a press made
// from a pick, a ✓ or a mark means the question those answer. Standing *in* an ask is not
// the same fact: a reader who addressed a link (`g l 3`) or tabbed to one has said
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
// `document.activeElement` rather than `focused()`, for the reason askPosition gives: a
// control staged in a shadow tree retargets to its host, and the host is the place in the
// document both the chrome guard and the item walk want. standingConversation below wants
// the other reading, and says so.
const standingItem = () => {
  const held = document.activeElement;
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
// already crosses there and the register says so twice. `g c N` is a page address that
// lands the reader in a panel textarea, and `openAsks` counts a widget an agent sent as an
// ask like any other, so `g a N` can put them inside a thread. A page key that takes them
// somewhere owes them an answer once they are standing there.
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
const SAYS_IN = ".lf-thread, .lf-conversation-thread, .lf-conversation";
const SAY_BOX = ":scope > .lf-compose textarea, :scope > .lf-say textarea";
// The climb itself, named because it is read from both ends. `standingConversation`
// asks it of where the reader stands, to find the box a press should open; `backFromBox`
// asks it of the box, to find the way back out. One climb, so the press in and the press
// out cannot come to disagree about which conversation this is — and the word is the same
// at both ends, "comment on the thread" going in and "back to thread" coming out.
//
// `closestAcross` climbs through `upFrom`, which asks a null node for its parent. The
// body case standingItem also guards needs nothing here: the climb from `body` reaches
// `html`, whose root has no host, and ends on its own.
const heldConversation = () => focused() && closestAcross(focused(), SAYS_IN);
const standingConversation = () => {
  const held = heldConversation();
  const box = held?.querySelector(SAY_BOX);
  return box && shownBox(box).height ? { held, box } : null;
};
// Putting the reader in a conversation, in one place, so the three presses that do it —
// the `g c` address, `Enter` on a focused thread, and `c` from inside one — cannot come to
// mean three slightly different landings. The page follows a thread in the panel to the
// passage it is about; a conversation seated on the page is already standing at it.
function landIn({ held, box }) {
  box.focus({ preventScroll: true });
  held.scrollIntoView({ behavior: SCROLL, block: "nearest" });
  if (held.dataset.id) scrollToThread(held.dataset.id);
}
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
  if (fabAnchor)
    return {
      ...commenting(
        fabAnchor.quote
          ? "selection"
          : itemWord(elementById(fabAnchor.section)) || "item",
      ),
      go: () => fab.onclick(),
    };
  const said = standingConversation();
  if (said) return { ...commenting("thread"), go: () => landIn(said) };
  const here = standingItem();
  if (here) return { ...commenting(itemWord(here)), go: () => commentOnItem(here) };
  // Standing nowhere the press can name, so it means "take me to the conversation" and
  // lands on the list rather than in a box: the ring is visible, j/k walk on from it, and
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
// Inside the chrome it is the layers first, in the order the reader is in them: the leaves
// tray goes before the comment panel — it was opened for a glance, where the panel is the
// work itself — unless focus stands inside the panel, since a reader backing out of its
// general box is standing on its list, and their next Escape taking a tray off the far
// side of the screen took the key away from the work it was unwinding.
//
// Then the last rung leaves the chrome, because closing the panel does not put the reader
// back on the page: it lands them on the control that closes it, deliberately (setPanel
// says why), and the closing keypress rings a button a pointer-borne reader never chose.
// Their next Space is then that button rather than the page's scroll. CLAUDE.md's "The
// reader has to be standing somewhere" holds the rest.
function rung() {
  const active = document.activeElement;
  const holding = Boolean(active) && active !== document.body;
  if (holding && !inChrome(active))
    return { says: "let go", does: "Let go of what you are standing on", out: letGo };
  // Whichever tray holds the edge, named by the rung so the reader is told what the
  // press will take rather than being told "close the tray" over two of them.
  if (trayUp && !panel.contains(active))
    return {
      says: `close ${trayUp}`,
      does: `Close the ${trayUp} tray`,
      out: () => showTray(null),
    };
  // A narrowing is a layer of the panel the way a tray is a layer of the page: the
  // reader put it on, and the list in front of them is not the whole of the conversation
  // until it comes off. So it unwinds before the panel does, and from wherever they are
  // standing — the find box binds the same step for itself, being the one place the
  // reader can see what they are backing out of.
  if (panelOpen && narrowed())
    return { says: "show all", does: "Show every comment again", out: widen };
  if (panelOpen)
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
// A press that puts a character in the box: one character, and Shift is the only modifier
// that still types one — Shift+a is an A, so the page's answer-all must not fire behind it.
// Mod and Alt compose shortcuts a box has no use for, which is how the send key reaches its
// own row.
const PRINTABLE = (binding) => {
  const { key, mods } = parsed(binding);
  return [...key].length === 1 && mods.every((m) => m === "Shift");
};
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

// The chord: one scope, a row per addressable list, a row for the page's two edges, and
// the window's own way out. A list row holds the whole motion — its letter names the
// list, and the digits it then binds are the addresses into it. That is `v`'s shape, a
// chooser whose second key belongs to the scope the first one stood up, and the reason it
// is one row rather than two is that a digits row of its own could not name which list it
// meant. The edges row is the same motion one key shorter: an edge is one place, so its
// letter is the whole address, and it is why the scope has no `when` — every page has a
// top, so the window g arms is never empty.
//
// A row's `when` carries both questions here, where a scope usually carries one of them: a
// list the page hasn't got is a capability, and which list is aimed at is whether the press
// moves now. They can share the answer because a mode is not somewhere the reader stands
// near — see showHelp, which reads a mode's rows by their own liveness for exactly that
// reason. Written as a scope per list instead, each stating its own capability, the two
// were named apart at the price of three scopes under one title, and the reference then
// gathered them in the order it walks the stack — backwards, so it named the lists in the
// opposite order to the line that had just offered them.
const GO = {
  title: "With g armed",
  chord: () => chordKeys().join(" "),
  at: () => chordArmed,
  claims: EVERYTHING,
  rows: [
    ...ADDRESSES.map((entry) => ({
      keys: () =>
        aimedList === entry
          ? addressed(entry).map((_, i) => String(i + 1))
          : [entry.key],
      // The range the list actually holds, so the label cannot offer an address no member
      // wears; the keys already pressed drop off the front of it, the chip heading the
      // line having taken them (`g c`).
      label: () =>
        addressKeys(entry, range(addressed(entry).length))
          .slice(chordKeys().length)
          .join(" "),
      does: entry.does,
      line: entry.word,
      when: () => entry.list().length > 0 && (!aimedList || aimedList === entry),
      run: (binding) => {
        if (aimedList !== entry) return setChord(true, entry);
        const member = addressed(entry)[+binding - 1];
        // The reveal has done its work: the reader is about to stand in what it showed,
        // so it is theirs now rather than the aim's to take down.
        keepShown();
        setChord(false); // before the travel, so the arrival's own scrolling paints nothing
        entry.go(member);
      },
    })),
    {
      keys: ["g", "Shift+g"],
      does: "Go to the top / bottom of the page",
      line: "top / bottom",
      when: () => !aimedList,
      run: (binding) => {
        setChord(false); // before the travel, so the arrival's own scrolling paints nothing
        const box = seenScroller();
        glideTo(box, binding === "g" ? 0 : box.scrollHeight);
      },
    },
    {
      // Two presses in, two presses out. `g` opens the window and a letter names a list
      // inside it — the armed chip says so, reading `g` and then `g c`, and the chips on
      // the page narrow with it — so one Escape gives the letter back and the next
      // closes the window. It took both at once, which is the same drift `c` had at the
      // panel: a reader who had narrowed to the wrong list wanted the other one, and
      // cancelling put them back on the page, pressing `g` again to reach a window that
      // had been standing the whole time.
      keys: ["Escape"],
      does: () => (aimedList ? "Back to the lists" : "Cancel the chord"),
      line: () => (aimedList ? "back to the lists" : "cancel"),
      // Re-arming rather than a field of its own: `setChord` is where arming, aiming and
      // disarming already live, and re-opening the window with no list named is exactly
      // what the second stage backs out to.
      run: () => setChord(Boolean(aimedList)),
    },
  ],
};
const HELP = {
  title: "In this reference",
  at: () => helpOpen,
  claims: EVERYTHING,
  rows: [
    {
      keys: ["Escape"],
      does: "Close this reference",
      line: "close help",
      run: () => showHelp(false),
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
const inTheBox = () => panel.contains(document.activeElement);
// The panel thread the reader is in, asked by class because that is the anchors module's
// question: which logged thread's passage to paint. It is not the box's way out, which
// climbs further and answers for a seat on the page too — the two readings stayed apart
// rather than one standing in for the other.
const focusedThreadOf = () => document.activeElement?.closest?.(".lf-thread");
// Where a box hands the reader back to, which is the rung `c` came down. It asked
// `.lf-thread` and the panel alone, so the two boxes outside the chrome — a conversation
// seated on the page, and each thread on that seat — had no way out but the page's own
// "let go": one press in from the thread and one press out to nothing at all, which is
// the arithmetic the keyboard-is-a-stack rule exists to keep. The climb is
// `heldConversation`'s, so this is the same element `c` named on the way in.
//
// A seat holding no thread yet answers for itself. Its box is the whole of it and there
// is nothing outside the box to stand on, so it wears no seat of its own and the rung
// falls through — to the panel's list where the box is the chrome's, and to the page's
// own "let go" where it is not. Asked as "can the reader be put here", rather than by
// listing which two of the three containers happen to be focusable — which is also why a
// seat that `reachScrollers` makes focusable, having grown a scrollbar and no focusable
// child, becomes a rung without anyone editing this: the question is the same one, and the
// answer moved.
const backFromBox = () => {
  const held = heldConversation();
  return held?.hasAttribute("tabindex") ? held : null;
};
// A box words are typed into takes the keys that put a character in it, and only those:
// the page's bare letters are keystrokes here, while Escape and Enter are the box's to
// declare or to pass on. What it declares is the way back out — to the thread a reply
// belongs to, so Esc then Enter round-trips, or to the list, so j/k walk on from where the
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
const FINDING = {
  title: "In the find box",
  at: () => focused() === findInput,
  rows: [
    {
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
      keys: ["Enter"],
      does: "Go to the first comment found",
      line: "first found",
      when: hasThreads,
      run: () => stepThread(1),
    },
  ],
};

const TYPING = {
  title: "In a text box",
  at: () => takesLetters(focused()),
  claims: PRINTABLE,
  rows: [
    {
      keys: ["Escape"],
      does: "Leave the box, keeping what is typed",
      line: () => (backFromBox() ? "back to thread" : "back to list"),
      // The conversation the box belongs to, or the panel's list where it is the
      // chrome's own box. A page textarea that is neither leaves the row dead and the
      // page's rung standing, which is the honest answer: nothing there to go back to.
      when: () => Boolean(backFromBox()) || inTheBox(),
      run: () => {
        const held = backFromBox();
        document.activeElement.blur();
        (held ?? threadsBox).focus();
      },
    },
  ],
};

// The panel's own keys. What a press acts on is whose scope it belongs to: the page holds
// the presses whose subject is the page — `a` and `l` open what is about it — and a
// surface holds the presses whose subject is its own contents. `w` narrows this list and
// `/` searches it, and a list the reader is not looking at is neither a thing to narrow
// nor a thing to search. At page scope they were two bare letters spent on a panel that
// might be shut, promised by the key line over prose the presses said nothing about.
//
// `c` is the one row here whose subject is not this list, and it is the rule read one
// step further rather than the rule bending: the page's `c` follows the reader and is
// what lands them here, and this is the same intent one scope in, the way `g` names a
// list and then a member of it. The row's own comment carries where it stands down, so
// the page's answer is the one that runs wherever the page has a nearer one.
//
// Standing in the panel is where its focus is, not merely that it is open: the Comments
// button is the banner's, so opening by pointer leaves the reader outside, and `c`, `j`,
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
  at: () => panelOpen && containsAcross(panel, focused()),
  rows: [
    {
      // `w` for the words the control says, the way `l` spells the leaves and `a` the
      // asks. It is the phrase the page already uses for the same question asked of its
      // widgets (n/p), asked here of the conversation — so the reader learns one idea and
      // reaches it two ways rather than learning "needs you" beside it. The control was
      // renamed to earn the letter: `n` belongs to the asks walk, and a key spelling a
      // word nothing on screen says is a key nobody reaches for twice.
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
// other side. The compose row is what tells an open thread from a resolved one, which has
// neither a box for Enter to reach nor a Resolve for x to press.
const THREAD = {
  title: "On a focused thread",
  when: hasThreads,
  at: () => Boolean(focusedThread()),
  rows: [
    {
      keys: ["Enter"],
      does: "Write a reply",
      line: "reply",
      when: () => Boolean(focusedThread()?.querySelector(":scope > .lf-compose")),
      // The address's own arrival, so the two presses that reach a thread's reply box
      // reach the same one. This took the first textarea in the thread, which is not the
      // reply box when a message carries a widget holding one of its own — a draft's open
      // editor stands before it in the DOM, which is why `g c` was written to ask for the
      // box by its place (COMMENTS.go) and not by being first. Two readings of "the reply
      // box" is two answers the day a message carries an editor, and `c` standing in a
      // thread now reaches it too, so there would have been three.
      run: () => COMMENTS.go(focusedThread()),
    },
    {
      // `x` and not `r`, though resolve is the word it does: the press beside it in this
      // same scope is the reply, and a reader meeting `r` on the line reads "reply" before
      // they read "resolve". A key spelling its own word is the wrong key when the
      // neighbouring press owns the word it would be read as. `x` is the letter a thing
      // closes under, and no other scope had claimed it.
      keys: ["x"],
      does: "Resolve it",
      line: "resolve",
      // Through the thread's own button, so keyboard and mouse are one behaviour — the
      // focus landing included — and a resolved thread offers no button to find, which is
      // the row's own liveness rather than a silent no-op inside the press.
      when: () => Boolean(focusedThread()?.querySelector(":scope > .lf-compose")),
      run: () =>
        focusedThread()
          .querySelector(":scope > .lf-thread-actions > .lf-resolve")
          ?.click(),
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
  { keys: ["Enter"], does: "Follow it", line: "follow" },
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
export const DISCLOSE = (el) => {
  const open = disclosed(el);
  if (open === null) return [...PRESS, "ArrowLeft", "ArrowRight"];
  return inChrome(el) ? PRESS : [...PRESS, open ? "ArrowLeft" : "ArrowRight"];
};
const DISCLOSURE = standingOn("On a disclosure", DISCLOSURE_SELECTOR, [
  {
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
      keys: [],
      label: "click",
      does: "Comment on what the click lands on — a widget, a control, the chrome; prose still selects",
    },
    {
      // Both keys, on one row: i is the toggle and Escape the mode's own rung, and two
      // chips reading "leave design" said one thing twice on the line.
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
// takes the letter again for the newest version — one motion whose second half is a key of
// the scope the first half stood up, so it costs the table no row and holds whether or not
// this page is behind. Named, because the chip that jumps straight to the newest version
// spells that motion in its tooltip.
const CHOOSER = {
  keys: ["v"],
  does: "The versions, and what each one changed",
  line: "versions",
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
  keys: ["?"],
  does: "This key reference",
  line: "more",
  also: keylineMore,
  run: () => showHelp(true),
};
// The way in to the chord, named for the reason the two rows above it are: the armed chip
// and every address a member speaks are built from this row's own key (addressLabel), so
// the letter the reader presses and the letter the page prints cannot be two decisions.
//
// The key alone on the line: what it opens is a table, and a label naming one of its lists
// would be the chord's old shape wearing a letter — `g 1–9` said "threads" without saying
// it, and the day a second list arrived there was no honest range to print. The scope the
// press stands up names them all, one chip each.
const GOTO = {
  keys: ["g"],
  does: "Go by address — the next key names one of the page's lists, or its top or bottom",
  line: "go to",
  // No `when`: the window this press stands up always holds at least the page's edges.
  run: () => setChord(true),
};
const PAGE = {
  rows: [
    {
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
      keys: ["j", "k"],
      does: "Next / previous open thread",
      line: "threads",
      when: hasThreads,
      repeat: true,
      run: (binding) => stepThread(binding === "j" ? 1 : -1),
    },
    {
      // A borrowed pair, like the walks either side of it: j/k is vim's list, d/u is
      // less's half page, and n/p is next and previous wherever a keyboard walks a list
      // of things. The walk held `a` alone and then `a`/`p`, and
      // both were the same mistake in different sizes — a letter naming what is walked
      // rather than which way, so the second half had nowhere to come from and ended up
      // a pair only its author knew. Naming the direction is also what leaves the noun's
      // shifted letter to the answer that acts on all of them at once (A, below).
      keys: ["n", "p"],
      does: "Next / previous thing this page is waiting on you for",
      line: "asks",
      when: () => openAsks().length > 0,
      run: (binding) => stepAsk(binding === "n" ? 1 : -1),
    },
    {
      // `a` for the asks — the letter the walk gave up when it moved to naming directions
      // (n/p above), and the noun every surface names this tray by. What it opens is the
      // list those keys walk, which until now the reader could only reach by walking it:
      // there was no way to see what was waiting without visiting each one in turn.
      keys: ["a"],
      does: () =>
        `${openTray("asks") ? "Hide" : "Show"} what this page is waiting on you for`,
      line: () => `${openTray("asks") ? "hide" : "show"} asks`,
      also: asksBtn, // the banner count opens the same tray, which then names this key
      when: asksOffered,
      run: () => {
        showTray(openTray("asks") ? null : "asks");
        // Opening lands on the first row, so the tray's own keys are the next press
        // rather than a Tab-hunt across the banner — the move `l` makes into the leaves.
        // Closing hands focus back, which showTray owns.
        if (openTray("asks")) askRows()[0]?.focus();
      },
    },
    {
      keys: ["d", "u"],
      does: "Half a page down / up",
      line: "half a page",
      repeat: true,
      run: (binding) => stepPage(binding === "d" ? 0.5 : -0.5),
    },
    {
      // `l` for the leaves, the word every surface names this tray by. It was `o`,
      // for the "Other leaves" the button said before the count was one off the list
      // it promised — so the key went on spelling a word nothing on screen said, and
      // a mnemonic nobody can reconstruct is a key nobody reaches for twice.
      keys: ["l"],
      does: () => `${openTray("leaves") ? "Hide" : "Show"} the machine's leaves`,
      line: () => `${openTray("leaves") ? "hide" : "show"} leaves`,
      also: othersBtn,
      when: leavesOffered,
      run: () => {
        showTray(openTray("leaves") ? null : "leaves");
        // Opening lands on the first neighbour, so the tray's own keys are the next press
        // rather than a Tab-hunt across the banner — the move c makes into the comment
        // panel's box. Closing hands focus back, which showTray owns. The key is dead
        // with nothing to show, so an open always has a row to land on.
        if (openTray("leaves")) othersLinks()[0].focus();
      },
    },
    {
      // The same list n/p walk, answered at large: every blanket answer the page offers,
      // given through the banner's own presses, so a decision taken by key is a decision
      // taken by the control and the log records each one separately. Its words are the
      // registry's rather than a sentence written here — "accept" is one widget's verb,
      // and a key that said it in core would be the sentence the banner's count used to
      // be. `a` names the asks it answers and stands for nothing on its own: an
      // unshifted letter that ends the matter for every one of them is a press too
      // cheap for what it does. The walk is spelled in directions (n/p), so the noun was
      // free for the tray above, which is what it now opens.
      keys: ["Shift+a"],
      does: () =>
        standingAnswers()
          .map(({ label, n }) => `${label} all ${n}`)
          .join(", ") + " waiting on you",
      line: "answer all",
      when: () => standingAnswers().length > 0,
      run: () => {
        for (const { btn } of standingAnswers()) btn.click();
      },
    },
    {
      // The last thing the reader did to this page, put back. Its own key rather
      // than the platform's ⌘Z, which belongs to the box a reader is typing in and
      // is taken by the browser everywhere else: this is a page-level press like
      // every other letter here, and the typing scope keeps it off a composer's
      // words by claiming its letters. The word is "undo" and never the verb it is
      // about to state — `move` is one widget's word, and a line that said it would
      // be naming a member where the mechanism is what holds.
      keys: ["z"],
      does: "Take back the last change you made here",
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
  HELP,
  ELEMENTS,
  VERSIONS,
  COMPOSER,
  FINDING,
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
// correct. `also` is where a row says which control it duplicates; the chip's is the one
// motion no single row makes, so it is composed of the two rows that make it.
for (const scope of CORE)
  for (const row of scope.rows) if (row.also) row.also.title += ` (${labelOf(row)})`;
latestChip.title += ` (${labelOf(CHOOSER)} ${labelOf(NEWEST)})`;

// The two questions a scope answers, named apart because the surfaces ask them apart: the
// reference lists a scope the page *has* and filters its rows by liveness only where the reader
// is standing in it, while the dispatcher and the line want both at once. Spelled `!x || x()`
// in three places before, which is a rule written three times and named nowhere.
const pageHas = (scope) => !scope.when || scope.when();
const readerIn = (scope) => !scope.at || scope.at();
// Where the reader is first, and what the page has second: both are pure and the and is
// the same either way round, but `at` is a class check and a `when` may be the whole event
// log folded — so the walk asks the cheap question of every scope and the dear one only of
// the scopes it is already standing in. That is the rule the dispatcher's row loop already
// keeps and the control scope's own comment already claims ("`at` is asked first and answers
// false wherever this could be in doubt, so a paint never reaches it"), and the scope walk
// was the one place it was not true. The chord is what made it bite: its `when` reaches the
// asks fold and then every link on the page, once per keydown, from the first keystroke of
// the first comment.
const standing = (scope) => readerIn(scope) && pageHas(scope);
// Every scope the reader is standing in, innermost first. The whole list: what a nearer
// scope takes out of reach is the walk's own business, and both walkers say it the same
// way — a binding some nearer row has already named, or one a nearer scope claims. Cutting
// the list here instead was the same statement made where only one of the two shadowings
// could be seen.
function stack() {
  return SCOPES.flatMap((scope) =>
    scope === ELEMENTS ? scopesFor(focused()) : scope,
  ).filter(standing);
}
// The claims of every scope nearer the reader than this one, accumulated as either walk
// steps outward. A scope's own claim is pushed after its rows, because what it takes from
// the page it does not take from itself.
const shadow = () => {
  const claims = [];
  return {
    takes: (binding) => claims.some((c) => c(binding)),
    past: (scope) => {
      if (scope.claims) claims.push(scope.claims);
    },
  };
};
// Every scope the page has, gathered by title, for the reference. Not the stack: the
// reference answers "what could I do here", so it names a card grip's keys whether or not
// a grip has focus. What it does not name is a key that would refuse the press, which is
// the rows' own liveness.
//
// The runtime's own modes come through the same door as a widget's, and the reference was
// blind to them while they did not: the sharpest case was the overlay never saying how to
// close the overlay, and a quiet page naming no Escape at all. So a section is its title
// wherever the title comes from — the box a reply is typed into declares its send key from
// wireInput and its way out from the typing mode, and they are one heading.
//
// The stack backwards, so a reader learning the keyboard starts from the page in front of them
// and reads inward, and the widgets' sections land where their scopes stand in it rather than
// wherever a second list happened to put them.
function declaredStack() {
  pruneScopedElements();
  const sections = new Map();
  const named = (section) =>
    scopesFor(focused()).some((s) => s.title === section.title);
  for (const scope of SCOPES.toReversed()) {
    if (scope !== ELEMENTS) {
      merge(sections, { ...scope, rows: bySentence(scope.rows) });
      continue;
    }
    // Where the reader is, for a widget's section, is whether the focused element declares it
    // — the one thing core's own scopes state for themselves and an element scope cannot,
    // since it is gathered here by title and the elements wearing that title are many.
    const declared = new Map();
    // In the order the page holds them, not the order they registered. `scopeRefs` is
    // insertion-ordered and a widget registers at upgrade, so the sections came out in
    // whatever order the modules happened to finish in — the same build read twice put
    // "On a tab" above "On a card grip" once and below it the next time. A reference whose
    // headings move between loads is one a reader cannot learn the shape of, and any
    // assertion on it flakes rather than fails.
    const held = [...scopeRefs]
      .map((ref) => ref.deref())
      .filter((el) => el?.isConnected && elementScopes.get(el)?.title);
    held.sort((a, b) =>
      a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1,
    );
    for (const el of held) {
      const section = elementScopes.get(el);
      merge(declared, { ...section, rows: bySentence(section.rows) });
    }
    for (const section of declared.values())
      merge(sections, { ...section, at: () => named(section) });
  }
  // The way out reads last, after what the scope is for. A section gathers its rows from
  // wherever they were declared, and a mode contributing only its Escape would otherwise
  // put the exit above the walk it exits from.
  const exit = (row) => (bindings(row).includes("Escape") ? 1 : 0);
  return [...sections.values()].map((s) => ({
    ...s,
    rows: [...s.rows.values()].sort((a, b) => exit(a) - exit(b)),
  }));
}

// ---------- the dispatcher ----------
// One listener. Scoping is still the DOM's — an element scope holds while focus is inside
// it — but the walk is the stack's rather than the bubble's, so which scope wins is a
// statement here instead of an ordering between nine listeners. `isComposing` is the one
// guard that stays an event's rather than a scope's: an IME's own Escape is not the
// runtime's to take.
document.addEventListener("keydown", (ev) => {
  if (ev.isComposing) return;
  if (run(ev)) return;
  // Any other key disarms the chord and keeps its ordinary meaning, so a mistyped g costs
  // nothing: g j is a thread step and g g re-arms. A letter naming no list disarms the same
  // way, and so does a digit past the end of the list a letter named. Spelled as walking
  // again rather than as a rule, so the meaning a key keeps is the meaning the register
  // gives it. A modifier alone is half a press rather than a key: the Shift that
  // capitalizes G arrives as a keydown of its own ahead of it, and disarming on that
  // took the window down before the G it was armed for.
  if (chordArmed && !MODIFIER_KEYS.includes(ev.key)) {
    setChord(false);
    run(ev);
  }
});
function run(ev) {
  const nearer = shadow();
  for (const scope of stack()) {
    for (const row of scope.rows) {
      // The key first, then the claim, then the liveness: a `when` may be the whole event
      // log folded (`a` asks what the page is still waiting on), and asking it of every row
      // the press is not for makes the cost of a keystroke the size of the table rather
      // than the size of the match. A row that matches and is dead still falls through to
      // the scope behind it, which is what `continue` says either way round.
      if (!row.run) continue;
      const binding = bindings(row).find((b) => answers(b, ev));
      if (!binding || nearer.takes(binding) || !live(row)) continue;
      // A held key repeats keydown where a real button fires once, so a row says whether
      // it repeats: a held `]` was a page navigation per repeat and a held pick a `choose`
      // per repeat, where a walk wants the repeat and is the reason the flag exists. The
      // repeat is still consumed — Space is a page scroll if it isn't, so holding it on a
      // control would send the page out from under the press the first one made.
      ev.preventDefault();
      if (ev.repeat && !row.repeat) return true;
      row.run(binding);
      return true;
    }
    nearer.past(scope);
  }
  return false;
}

// A focus move is the one change in where the reader is standing that no state writer
// sees, so it asks for the paint itself — the ring and the line both, which is why one
// call answers for it. Focus entering a box, or a control that claims Escape, also disarms
// the chord — a digit typed in a box is text, and a chip left blooming would promise a
// cancel the control would consume.
document.addEventListener("focusin", () => {
  // The same question `setChord` asks before arming, so it takes the same answer: two
  // readings of where the reader is standing would refuse to arm somewhere they then
  // failed to disarm.
  const active = focused();
  if (chordArmed && (takesLetters(active) || claimsEsc(active))) {
    // Focus arriving inside what the aim revealed is the reader landing in it, the same
    // arrival the digit makes, so the reveal is theirs to keep rather than the aim's to
    // take down. Without this a click into the panel `g c` had just opened closed it again
    // under the click.
    if (containsAcross(panel, active)) keepShown();
    setChord(false);
  }
  paintHere();
});
document.addEventListener("focusout", () => paintHere());
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

// ---------- the key line ----------
// What the next press does, walked outward from where the reader stands. The full register
// has grown past what a glance can read, so this surface keeps two hints and leaves the rest
// one press or click away. Locality supplies the ranking: the same innermost-first scope
// order the dispatcher uses. The one override is an available Escape after the first hint,
// because a mode whose way in is visible and whose way out is not is a trap.
//
// The rows the line shows, innermost scope first: the ones carrying a word for it. A row
// is skipped where any of its bindings has been named already, so an inner scope's own
// word for a press wins and the generic one behind it stays quiet — the case that names
// this is `g c` aimed over an option's pick mark, where the chord's "1–3 comments" and the
// mark's "1–5 toggle the nth" would otherwise stand side by side, two promises for one
// press.
function lineRows(scopes) {
  const named = new Set();
  const nearer = shadow();
  const rows = [];
  for (const scope of scopes) {
    for (const row of scope.rows) {
      // Shadowing before liveness, for the reason the dispatcher matches the key first:
      // under the reference every page row is claimed away, and asking each one what the
      // page is waiting on to then say nothing about it is the table's cost per paint. A
      // dead row names nothing, so it shadows nothing either.
      if (!row.line) continue;
      const bound = bindings(row);
      if (bound.some((k) => named.has(k) || nearer.takes(k))) continue;
      if (!live(row)) continue;
      for (const k of bound) named.add(k);
      rows.push(row);
    }
    nearer.past(scope);
  }
  return rows;
}
function renderLine() {
  // One walk, read twice: `at` and `when` are the page's own state and a second walk would
  // ask every one of them again for the same frame.
  const scopes = stack();
  const rows = lineRows(scopes);
  // `?` has its own permanent More control, so its ordinary row remains in the DOM only as
  // the register's hidden projection. Keeping every live row there preserves one inspectable
  // reading of the current key scene while only the two selected rows paint.
  const ref = rows.findIndex((row) => bindings(row).includes("?"));
  const ordered =
    ref === -1 ? rows : [...rows.slice(0, ref), ...rows.slice(ref + 1), rows[ref]];
  const candidates = ordered.filter((row) => !bindings(row).includes("?"));
  const first = candidates[0];
  const wayOut = candidates.slice(1).find((row) => bindings(row).includes("Escape"));
  const short = new Set([first, wayOut ?? candidates[1]].filter(Boolean));
  // Read where it is painted, like every other cell: the chord's chip says which stage the
  // reader is at (`g`, then `g c`), and a string fixed at declaration could only say one.
  const chord = word(scopes.find((s) => s.chord)?.chord);
  // Everything but More, which the reader may be standing on. `textContent = ""` takes
  // it out of the document, and removing a focused element blurs it: it returns on the
  // same line as the same node, connected again, with the reader dropped to `body`. That
  // lands one frame after they tabbed to it, because this runs under paintHere's frame —
  // so the walk is whole at synthetic speed and broken at every human one, which is the
  // way round that hides from a suite. The line is cleared around it instead, and the
  // chips are drawn in front of it.
  for (const node of [...keylineEl.childNodes]) if (node !== keylineMore) node.remove();
  const seated = keylineMore.parentElement === keylineEl;
  const chip = (key, said, armed) => {
    const span = el("span", "lf-key");
    span.setAttribute("aria-hidden", "true");
    const kbd = document.createElement("kbd");
    if (armed) kbd.className = "armed";
    kbd.textContent = key;
    span.append(kbd);
    if (said) span.append(el("span", "", said));
    keylineEl.insertBefore(span, seated ? keylineMore : null);
    return span;
  };
  if (chord) chip(chord, "", true);
  const drawn = ordered.map((row) => {
    const span = chip(labelOf(row), word(row.line));
    span.hidden = !short.has(row);
    return span;
  });
  // The door is not useful behind the room it opens. While the reference stands, its
  // own Escape row is the short line and More leaves the focus order with the page. This
  // is the one removal that is meant: a reader standing on the door when the room opens
  // is a state change rather than a repaint, and the help takes the focus anyway.
  if (helpOpen) keylineMore.remove();
  else if (!seated) keylineEl.append(keylineMore);

  // Two is a ceiling, not permission to clip them. On a window narrower than those two
  // computed sentences, yield the lower-ranked hint and then the first; More is the one
  // control that always survives. At most two layouts are spent, independent of the size
  // of the register, while all hidden rows stay available to inspection and the reference.
  for (const span of drawn.filter((item) => !item.hidden).toReversed()) {
    if (keylineEl.scrollWidth <= keylineEl.clientWidth) break;
    span.hidden = true;
  }
}
paintHere();
// The room is the window's, so the window changing is a scope change like any other. It
// was the one edge no writer reported: a reader who narrowed their window kept the wide
// selection until they next moved focus, and the CSS clip did the cutting instead.
addEventListener("resize", paintHere);

// Where a comment about this item is written: the composer, on the item, which is what a
// click through the ⌥ aim already opens. It reached for the widget's own conversation seat
// first for a while, on the reasoning that a widget holding a box for its conversation
// should not be given a second one. That was the wrong shape. `openOnItem` writes
// `{section: item.id}`, which is exactly the anchor `renderConversations` collects into
// that seat — so the words land in the same conversation by either route, and the seat was
// buying a focus landing at the price of five separate questions: escaping an
// author-written id into a selector, whether the box can take focus at all (a settled
// group's seat is inside `hidden="until-found"` and silently swallowed the press), which
// box when the seat holds several threads, what design mode files, and where the reader
// was already standing. One route answers all five by not asking them.
//
// The scroll is for the standing that has gone stale — an address or a Tab leaves the item
// on screen, but focus outlives the scroll that put it there, and a box about something
// off screen is a box about nothing the reader can see.
function commentOnItem(item) {
  // Only where the item is not already in front of the reader. Travelling every time moved
  // the page under someone who could see the thing perfectly well: Tab leaves an item at an
  // edge (`block: nearest`), so centring took the page a third of a viewport with nothing on
  // screen to explain it — on the route this press exists for, and where the ⌥ aim it is the
  // twin of moves nothing at all. The travel is for the standing that has gone stale, focus
  // outliving the scroll that put it there: a box about something off screen is a box about
  // nothing the reader can see.
  //
  // What the page shows of it, which is the reading the aim's own paint takes
  // (`refreshAim`) — this being its keyboard twin, the two decide "is this in front of the
  // reader" the same way or they are not twins. `shownBox` alone is the box the item would
  // have, unclipped: an item scrolled out of a board's sideways scroller still reports one
  // inside the window, so a gate reading that called it showing and opened the box on
  // something off screen, which the unconditional travel it replaced never did. Any part
  // showing is enough, which is also what keeps a box taller than the window from jumping
  // to its top under a reader halfway down it.
  //
  // A collapsed ancestor zeroes its descendants' boxes, so a thing inside a shut
  // disclosure is never showing and takes the travel, `reveal` with it. Standing on the
  // summary itself is the one motion this drops: the disclosure stays shut and the box
  // opens on it where it is, rather than springing it open and reflowing the page under
  // the reader who was looking at it.
  //
  // Instant, and before the box is measured. Placing reads the item's box, so that has to
  // be the box the item keeps; and opening focuses the textarea, whose scroll-into-view
  // cancels a glide already under way — which is what left the item flush against an edge
  // rather than framed, and is not `openComposer`'s to give up, three other presses opening
  // that box against a passage they have not moved.
  const seen = shownRect(item, new Map());
  if (!seen || seen.bottom <= BANNER_CLEAR) scrollToElement(item, "instant");
  const [left, top] = beside(shownBox(item));
  openOnItem(item, { left, top });
}
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

// j/k walk the open threads: panel focus and the page highlight move as a pair — they are
// two views of the same thread. Clamped at the ends, not wrapped; never empty, because the
// keys are live only while open threads exist, and hasThreads counts what renderThreads
// wrote here in the same synchronous pass.
function stepThread(dir) {
  if (!panelOpen) setPanel(true);
  const threads = openThreads();
  const at = threads.indexOf(document.activeElement?.closest?.(".lf-thread"));
  const next =
    threads[
      at === -1
        ? dir > 0
          ? 0
          : threads.length - 1
        : Math.max(0, Math.min(threads.length - 1, at + dir))
    ];
  // Landing the thread is the list's, off the focus it is about to take. A press at
  // either end of the walk is the exception the list cannot answer: it names the thread
  // the reader already stands on, so no focus moves and nothing fires, while the page
  // half of the press still travels. Both halves therefore go where they were pointed.
  const standing = next === document.activeElement;
  next.focus({ preventScroll: true });
  if (standing) next.scrollIntoView({ behavior: SCROLL, block: "nearest" });
  scrollToThread(next.dataset.id);
}

// d and u step the reader half a page down and up — less's pair, and half a page rather
// than a whole one so the lines they were reading are still on screen to read on from.
// The browser's own keys are left to the browser (Space, Home/End, PageUp/Down all reach
// it untouched, and a test pins that); these are the runtime's.
//
// They move the region the reader's own scrolling moves, which under a covering sheet is
// its thread list rather than the page behind it — the rule syncLayout already states for
// the wheel, and a key is no different. Scrolling a page nobody can see reads to the user
// as the key doing nothing, and then the document is somewhere else when the sheet closes.
//
// The step moves at the pace of the browser's own paging keys. Native paging is a quick
// glide — PageDown covers a page here in ~140ms, and Space and the arrows ride the same
// animator — but that animator is the compositor's and JS cannot ask for it, while
// scrollTo's smooth takes three times as long over the same distance and has no dial,
// which is what read as gradual when the step rode it. So the runtime drives the step
// itself: PAGE_MS of easing out, each write `instant` rather than `auto` since a page is
// free to set `scroll-behavior: smooth` on the box it scrolls (jumpBy says the same) and
// a glide built from smooth writes would never land. A press mid-flight retargets from
// the goal, so two quick presses move exactly a page; the goal is clamped, so pressing on
// at the foot banks no debt for u to press back through; and the step stands down the
// moment the box moves under another hand — a wheel, a centering — because the reader's
// own gesture outranks a key's. Under reduced motion the step is a jump, the answer the
// rest of the runtime's motion already gives (SCROLL).
//
// The page the step halves is the one the reader can see. The document's box lends its
// top edge to the fixed banner, and scroll-padding-top — declared on that scroller, read
// exactly so by scrollToElement — is where the box already says how much of itself stands
// covered. The thread list says the same thing about itself: a stuck run heading covers
// its top, so a half-page step there is half of what is left rather than half of the
// box, which is the answer the reader wants — a step that landed them under the heading
// would be a step onto words they cannot read.
const PAGE_MS = 140;
let glide = null; // {box, goal, wrote, raf}
// The glide's claim on the box: it holds only while the box is where the glide last
// wrote it. The tick asks before every write, and a press asks the same question before
// trusting the goal — the reader can take the box between frames, and a press landing
// in that gap otherwise measures from a goal the box has already left.
const holding = (box) =>
  glide?.box === box && Math.abs(box.scrollTop - glide.wrote) <= 1;
// The box these motions move is the one the reader can see: the document's, or the
// thread list where the panel covers the page — a key is no different from a wheel
// there, and a page scrolling behind the sheet shows the reader nothing.
const seenScroller = () => (panelCovers() ? threadsBox : pageScroller);
// Which box scrolls a given element, for anything that has to name its scroller rather
// than search for one. The document's for everything the document holds — and the
// panel's own list for a widget an agent put in a reply, which is scrolled by that and
// by nothing else. A drag naming the wrong one sits at the edge waiting for a scroll
// that never comes.
export const scrollerFor = (el) => (inChrome(el) ? threadsBox : pageScroller);
function stepPage(fraction) {
  const box = seenScroller();
  const clear = parseFloat(getComputedStyle(box).scrollPaddingTop) || 0;
  const from = holding(box) ? glide.goal : box.scrollTop;
  glideTo(box, from + fraction * (box.clientHeight - clear));
}
// One eased travel to a goal, shared by the half-page step and the chord's edges. The
// goal is clamped here, so a step pressed on at the foot banks no debt for u to press
// back through, and an edge may be asked for as the height it cannot exceed.
function glideTo(box, goal) {
  goal = Math.max(0, Math.min(box.scrollHeight - box.clientHeight, goal));
  if (REDUCED) {
    box.scrollTo({ top: goal, behavior: "instant" });
    return;
  }
  cancelAnimationFrame(glide?.raf);
  const start = box.scrollTop;
  const t0 = performance.now();
  const tick = (now) => {
    if (!holding(box)) {
      glide = null; // the box moved under another hand; theirs wins
      return;
    }
    // Floored as well as capped: a rAF timestamp is its frame's start, which can precede
    // the press that scheduled the tick, and an unfloored t walks the ease out past the
    // start — to a write the box clamps, which the next tick then read as another hand.
    const t = Math.max(0, Math.min(1, (now - t0) / PAGE_MS));
    box.scrollTo({
      top: goal - (goal - start) * (1 - t) ** 3,
      behavior: "instant",
    });
    // Where the write left the box, not what it asked for: the box clamps at its ends
    // and snaps to pixels, and the claim the next tick tests is about the box.
    glide.wrote = box.scrollTop;
    if (t < 1) glide.raf = requestAnimationFrame(tick);
    else glide = null;
  };
  glide = { box, goal, wrote: start, raf: requestAnimationFrame(tick) };
}

// ---------- the reference ----------
// Every scope the page has, live rows only, so nothing on screen is a key that does
// nothing. It renders at open and can go stale while it stands, and the two directions
// cost differently, both acceptably: a row going dead under it cannot be pressed, since
// the overlay claims the keyboard and the page stands down beneath it, and a key going live under it
// is merely unlisted until the next open, one press away.
let helpOpen = false;
// Where the reference was opened from, so closing it hands the reader back. Any dialog that
// takes focus owes that; what makes it structural here is that a scope is *where focus is*,
// so the overlay explaining a walk was also the way out of it — open the reference from a
// version row or a held card and the row's keys, which it had just listed, reached nothing
// afterwards. A mode over the page keeps this one key (`allButTheReference`), and a kept key
// that costs the reader their place is not much of an exemption.
let helpFrom = null;
const helpWords = (value) =>
  String(value ?? "")
    .toLocaleLowerCase()
    .replace(/\s+/g, " ")
    .trim();
function showHelp(open) {
  // Focusing a text input replaces the document selection. Keep a passage the reader has
  // in hand when `?` opens the reference, while an ordinary open lands directly in search.
  // The dialog itself remains a focus stop, so either route keeps the page suspended.
  const preserveSelection = open && Boolean(pageSelection());
  if (open && !helpOpen) helpFrom = focused();
  helpOpen = open;
  if (open) {
    helpEl.textContent = "";
    helpEl.append(el("div", "lf-help-title", "Keyboard reference"));
    const search = document.createElement("input");
    search.type = "search";
    search.className = "lf-help-search";
    search.placeholder = "Find a key or action";
    search.setAttribute("aria-label", "Search keyboard shortcuts");
    search.autocomplete = "off";
    search.spellcheck = false;
    const meta = el("div", "lf-help-meta");
    meta.setAttribute("aria-live", "polite");
    const results = el("div", "lf-help-results");
    const empty = el("div", "lf-help-empty", "No matching shortcuts");
    empty.hidden = true;
    const sections = [];
    let total = 0;
    const table = (rows, scopeTitle) => {
      const t = document.createElement("table");
      const entries = [];
      for (const row of rows) {
        const tr = document.createElement("tr");
        const kbd = document.createElement("kbd");
        kbd.textContent = labelOf(row);
        const keyCell = document.createElement("td");
        keyCell.append(kbd);
        tr.append(keyCell, el("td", "", word(row.does)));
        t.append(tr);
        entries.push({
          el: tr,
          words: helpWords(
            `${scopeTitle} ${labelOf(row)} ${word(row.does)} ${word(row.line)}`,
          ),
        });
      }
      total += entries.length;
      return { el: t, entries };
    };
    for (const scope of declaredStack()) {
      // A scope the reader is standing in is filtered by each row's own liveness, because
      // they can see which state they are in and a row that would refuse the press must
      // not be on screen. A scope they are merely near is listed whole: a row's `when`
      // asks whether the press moves *here*, and here is not where they are, so a grip's
      // "arrows move" belongs in the reference though no card is held and `x` belongs in
      // it though no thread is focused. Filtering both by the same predicate is what took
      // the thread's own keys out of the reference altogether.
      //
      // A mode is the exception, and it is one because there is no standing near it: the
      // reader is in it or it is not there, so its rows answer about here whichever way the
      // reference was opened. The chord is what needs this said — its rows are the lists
      // the page has, and `?` reaches the reference only from a page nobody has armed, so
      // listed whole it would name `l` on a page holding no link at all.
      const inIt = readerIn(scope) || scope.claims === EVERYTHING;
      const rows = scope.rows.filter((row) => row.does && (!inIt || live(row)));
      if (!rows.length) continue;
      const title = scope.title ?? "On this page";
      const section = document.createElement("section");
      section.className = "lf-help-section";
      const heading = el("h3", "", title);
      const body = table(rows, title);
      section.append(heading, body.el);
      results.append(section);
      sections.push({
        el: section,
        heading,
        table: body.el,
        words: helpWords(title),
        entries: body.entries,
      });
    }
    results.append(empty);
    const filter = () => {
      const query = helpWords(search.value);
      let shown = 0;
      for (const section of sections) {
        const sectionMatch = query && section.words.includes(query);
        let sectionShown = 0;
        for (const entry of section.entries) {
          const match = !query || sectionMatch || entry.words.includes(query);
          entry.el.hidden = !match;
          if (match) sectionShown++;
        }
        section.el.hidden = sectionShown === 0;
        section.heading.hidden = sectionShown === 0;
        section.table.hidden = sectionShown === 0;
        shown += sectionShown;
      }
      empty.hidden = shown !== 0;
      meta.textContent = query
        ? `${shown} of ${total} shortcuts`
        : `${total} shortcuts`;
    };
    search.addEventListener("input", filter);
    filter();
    helpEl.append(search, meta, results);
  }
  helpEl.classList.toggle("open", open);
  // The reference is a list long enough to scroll, and anything a mouse can scroll a
  // keyboard has to reach. `reachScrollers` is the runtime's one answer to that and had
  // never been pointed at the chrome it builds after upgrade: its rows carry no control,
  // so a reader working from the keyboard could read the first screenful of the key
  // reference and had no way to the rest of it. Called with the overlay open, because the
  // sweep reads computed overflow and a hidden box has none.
  if (open) reachScrollers(helpEl);
  if (open)
    (preserveSelection ? helpEl : helpEl.querySelector(".lf-help-search")).focus({
      preventScroll: true,
    });
  // Only from inside the overlay: a mousedown somewhere else closes it (standDown), and the
  // press's own focus is the browser's default action, still to come — a restore made from
  // out here would be putting focus back for the click to take again.
  else if (helpEl.contains(focused()) && helpFrom?.isConnected)
    helpFrom.focus({ preventScroll: true });
  paintHere();
}

// ---------- the ask, collected ----------
// An ask is a standing request to the reader: a question with no pick on it, a change
// nobody has decided, a piece of work the page says is waiting on them. Which widgets
// can source one is the registry's answer (x-awaits); x-ask may give that source a
// broader reading and arrival surface. Nothing out here names a tag —
// the banner's count, the n/p walk, and the "?" overlay's row are three readings of this
// one list, so what the banner counts and what the key steps to cannot disagree. The
// count used to be a query for `lf-suggestion:not([data-lf-state])`, which was
// perfect for suggestions and silently blind to every other thing a page asks.
//
// Both halves of "unanswered" were already written down. Asking is the entry's own
// condition over the element's attributes: a group takes picks only with `choose` and
// stops asking once it is `settled`, a task waits only at `review` or `blocked`. And
// answered is the state of one of x-awaits' explicit answer verbs. An attribute record
// lets authored markup honor a pick and lets clearing it reopen the ask; another named
// verb answers through its surviving fold entry. Verbs not named there are orthogonal
// state, so moving a deadline cannot silently answer the decision it postpones.
const askEntry = (el) => registry[el.tagName.toLowerCase()]?.["x-awaits"];
// A request may begin before the widget that records its answer. x-ask gives that
// complete reading one authored region: the heading, context and evidence above the
// control travel with it, while the nested x-awaits widget remains the state owner.
// Both directions are structural and declaration-driven, so a custom region and a
// custom request join without core naming either tag. `version check` holds each region
// to one nested source, which makes askSource's answer unambiguous.
const askSurfaceTags = () => tagsDeclaring((entry) => entry["x-ask"]);
function askSurface(el) {
  const tags = askSurfaceTags();
  return (tags.length && closestAcross(el, tags.join(","))) || el;
}
export function askSource(el) {
  if (askEntry(el)) return el;
  const tags = askTags();
  if (!tags.length || !registry[el.localName]?.["x-ask"]) return el;
  return (
    [...el.querySelectorAll(tags.join(","))].find(
      (candidate) => askSurface(candidate) === el,
    ) ?? el
  );
}
// Every declared attribute holding one of the values that ask — a flag's two values
// being its presence and its absence, since it carries none of its own.
function answeredAsk(el, projection) {
  const entry = registry[el.tagName.toLowerCase()];
  const verbs = entry["x-awaits"].answers ?? [];
  // The fold holds one entry per facet and unit, so a recordless verb is
  // answered only by an entry that is actually its own — a `choose` surviving in
  // the selection facet says nothing about `answer`'s completion facet, and a
  // cleared pick must ask again.
  return verbs.some((verb) => {
    const spec = entry["x-state"][verb];
    return ["attribute", "value"].includes(spec.record?.kind)
      ? ![null, ""].includes(projectedFacet(el, spec, projection.actions))
      : projection.actions.get(stateCoordinate(el.id, el.id, spec))?.e.action === verb;
  });
}
const askTags = () => tagsDeclaring((entry) => entry["x-awaits"]);

function askContext(projection = stateProjection(runtime.currentVersion)) {
  const positionedParents = new Map();
  for (const { unit, e, spec } of projection.desired.values()) {
    if (spec.record?.kind !== "position") continue;
    const parent = elementById(e.detail[spec.record.value]);
    const moved = elementById(unit);
    let holder = parent;
    while (holder && !registry[holder.localName])
      holder = authoredParents.get(holder) ?? holder.parentElement;
    if (
      parent &&
      moved &&
      holder &&
      (registry[moved.localName]?.["x-parent"] ?? []).includes(holder.localName)
    )
      positionedParents.set(unit, parent);
  }
  return {
    projection,
    positionedParents,
    settled: new Set(
      buildThreads()
        .filter((thread) => thread.resolved)
        .map((thread) => thread.root.id),
    ),
  };
}

function askExists(el, context) {
  if (quoted(el) || settledAway(el)) return false;
  const thread = closestAcross(el, ".lf-thread, .lf-going");
  return !thread || !context.settled.has(thread.dataset.id);
}

function projectedParent(el, context) {
  return (
    (el.id && context.positionedParents.get(el.id)) ??
    authoredParents.get(el) ??
    el.parentElement
  );
}

function nearestRollup(el, context) {
  for (
    let node = projectedParent(el, context);
    node;
    node = projectedParent(node, context)
  )
    if (askEntry(node)?.rollup) return node;
  return null;
}

function projectedContains(ancestor, el, context) {
  for (let node = el; node; node = projectedParent(node, context))
    if (node === ancestor) return true;
  return false;
}

function locallyAsks(el, context) {
  return (
    askExists(el, context) &&
    matchesProjectedWhen(el, askEntry(el).when, context.projection)
  );
}

// The ordinary case is one local request. A roll-up is the same request projected
// through a nested plan: a non-requesting node stops the walk; direct interventions
// take precedence; otherwise child roll-ups recurse; a leaf
// that matches its condition waits. Every relation is discovered from x-awaits, so
// a custom goal and a custom intervention join without a tag branch.
function isAwaiting(el, context) {
  if (!askExists(el, context)) return false;
  if (!matchesProjectedWhen(el, askEntry(el).when, context.projection)) return false;
  const entry = askEntry(el);
  if (!entry.rollup)
    return !(inChrome(el)
      ? answeredThreadAsk(el, context.projection)
      : answeredAsk(el, context.projection));

  const tags = askTags();
  const direct = tags.length
    ? [...document.querySelectorAll(tags.join(","))].filter(
        (candidate) => candidate !== el && nearestRollup(candidate, context) === el,
      )
    : [];
  const interventions = direct.filter(
    (candidate) => !askEntry(candidate).rollup && locallyAsks(candidate, context),
  );
  if (interventions.length)
    return interventions.some((candidate) => isAwaiting(candidate, context));
  const children = direct.filter((candidate) => askEntry(candidate).rollup);
  if (children.length)
    return children.some((candidate) => isAwaiting(candidate, context));
  return !(inChrome(el)
    ? answeredThreadAsk(el, context.projection)
    : answeredAsk(el, context.projection));
}

// In document order, because that is the order the page asks them in and the order
// the reader walks — the chrome container sits after the page's blocks, so a thread's
// question queues behind the page's own. Quoted material asks nothing (an exhibited
// decision is a mention). A widget in a thread asks like one on the page: a question
// is a request to the reader wherever it stands, and the panel's count is a different
// fact — threads open, not answers owed.
export function openAsks() {
  // Before the first replay, the DOM carries authored initial state while the log may
  // already answer it. This list drives both pixels and actions, so an empty list is the
  // only honest answer until the presentation boundary says replay is complete.
  if (!pagePresented()) return [];
  const tags = askTags();
  if (!tags.length) return [];
  const context = askContext();
  const open = [...document.querySelectorAll(tags.join(","))].filter((el) =>
    isAwaiting(el, context),
  );
  // A roll-up delegates its visible request to the open intervention or child that
  // made it true. Keep the actionable leaf in the banner and keyboard walk, not the
  // same request repeated at each ancestor.
  const visible = open.filter(
    (el) =>
      !askEntry(el).rollup ||
      !open.some(
        (candidate) => candidate !== el && projectedContains(el, candidate, context),
      ),
  );
  // The source decides whether the request stands; the surface is what the reader is
  // asked to take in. A set keeps a malformed duplicate from inflating the chrome while
  // the authored boundary still reports the ambiguity at version check.
  return [...new Set(visible.map(askSurface))];
}
// A thread ask has no version or restatement, but undo still withdraws an action.
// `x-awaits.until` therefore reads the same standing action projection as the DOM:
// a posted answer closes the ask, and taking it back opens the ask again.
function answeredThreadAsk(el, projection) {
  const entry = registry[el.tagName.toLowerCase()];
  if (!Object.keys(entry["x-state"] ?? {}).length) return true;
  const until = entry["x-awaits"].until;
  if (until && matchesProjectedWhen(el, until.when, projection))
    return [...projection.actions.values()].some(
      ({ e }) => e.widget === el.id && e.action === until.verb,
    );
  return answeredAsk(el, projection);
}

// One blanket answer per verb a widget declares one for (x-awaits.all), each deciding
// its asks one at a time so the log records what was consented to rather than one
// blanket yes — accepting the rest after rejecting one stays honest. The widget
// exposes a method named for the verb; the label is built from the same word.
//
// Built when the registry lands rather than written out above, so the second widget to
// declare one gets its control by declaring it. Each takes its place in the row rather
// than a box of its own: a control with no siblings is a control the press sweep walks
// past, and one that only ever appears at upgrade spends the spacer's slack, not the
// room of anything to its right.
const bulkButtons = new Map();
function buildBulkAnswers() {
  for (const tag of tagsDeclaring((entry) => entry["x-awaits"]?.all)) {
    const verb = registry[tag]["x-awaits"].all;
    if (bulkButtons.has(verb)) continue;
    const label = verb[0].toUpperCase() + verb.slice(1);
    const btn = el("button", "lf-btn lf-answer-all", "");
    btn.title = `${label} every one still waiting on you`;
    btn.onclick = async () => {
      btn.disabled = true;
      try {
        for (const ask of openAsks()) {
          const source = askSource(ask);
          if (askEntry(source)?.all === verb) await source[verb]?.();
        }
      } finally {
        btn.disabled = false;
      }
    };
    showNews(btn, false);
    bulkButtons.set(verb, { btn, label });
    banner.insertBefore(btn, versionBtn);
    // In the row now, so it holds the widest it reaches below a thousand — the same
    // words syncAsks writes, measured in the face it will render in (see reserve).
    reserve(btn, [`✓ ${label} all (999)`]);
  }
}

// Each blanket answer with the asks it would take, from the list above. The banner
// writes its controls from this and the A key reads the same call, so the count on the
// row, the count the "?" reference promises, and the presses the key makes are one
// reading rather than three — and neither surface names a verb, since which verbs there
// are is the registry's answer.
function blanketAnswers(asks) {
  return [...bulkButtons].map(([verb, { btn, label }]) => ({
    btn,
    label,
    n: asks.filter((ask) => askEntry(askSource(ask))?.all === verb).length,
  }));
}
// The ones with something to answer right now. Declared rather than assigned, like
// openAsks above it: the key table is written further up the file, so a const would put
// this in its own dead zone for anything asked of that table before the module ends.
function standingAnswers() {
  return blanketAnswers(openAsks()).filter((a) => a.n);
}

// The banner's reading of that one list. Refreshed from every signal that can change
// it: a widget saying it has just taken an answer (lf-answered, which is also when the
// page's own words change), and every poll, which is where the fold moves and where a
// send that failed has its optimism taken back.
function syncAsks() {
  const asks = openAsks();
  // While the tray stands its button stands too, whatever the count just did — the
  // press that opened it has to be able to close it.
  showNews(asksBtn, asksOffered());
  asksBtn.textContent = `Asks (${asks.length})`;
  // Only while the tray is up: the count above is what a closed tray says, and these
  // rows are what an open one says. A closed tray reconciling a list on every poll is
  // work for a reader who cannot see it, and rows in a document nothing can press.
  if (openTray("asks")) renderAsks(asks);
  for (const { btn, label, n } of blanketAnswers(asks)) {
    showNews(btn, Boolean(n));
    btn.textContent = `✓ ${label} all (${n})`;
  }
  // The n/p and A rows stand on this list, so the surfaces reading them are repainted
  // where it changes — the rule showFab and showTray already keep for the words
  // they write.
  paintHere();
}
// An answer also changes what text the page has — a retired slot leaves it, a pick
// mark starts saying "your pick" — so the marks are repainted from the same signal,
// and a comment on text the user just removed says so at once rather than at the
// next poll.
document.addEventListener("lf-answered", () => {
  syncAsks();
  paintAnchors();
});
document.addEventListener("lf-actions", syncAsks);
// One row per open ask, reconciled on every signal that moves the list, the way the
// leaves tray reconciles its own — rows kept in place rather than rebuilt, so a
// repaint doesn't swap a row out from under a pressed pointer or drop focus inside it.
//
// Keyed by the ask's id and not by the element: a new version replaces every node on the
// page, and the row for a question that survived the republish is the same row. That is
// also what a press resolves through — the element this row stood for may be gone, and
// the ask with that id is the one the reader means.
//
// A row says what kind of thing is asking and then the ask's own opening words, which is
// itemSays — the same reading the comment panel labels an anchor with, so a row and a
// comment on that ask say the same thing. Nothing here asks which widget it is: the kind
// is the element's own word and the words are the element's own text, so the twelfth
// widget gets a row that reads properly on the day it declares x-awaits.
const askRowsById = new Map();
function renderAsks(asks) {
  let anchor = null;
  if (!openTray("asks")) {
    for (const [, row] of askRowsById) row.remove();
    askRowsById.clear();
    return;
  }
  for (const ask of asks) {
    let row = askRowsById.get(ask.id);
    if (!row) {
      row = el("button", "lf-asks-row");
      row.type = "button";
      // The attribute that already means "this chrome belongs to that ask" (askPlace),
      // so focus landing on a row is the reader standing in the ask it names, and the
      // ring, the walk's own measuring point and the mark all follow with nothing added.
      row.setAttribute(ASK_AT, ask.id);
      row.append(el("span", "lf-asks-kind"), el("span", "lf-asks-says"));
      row.onclick = () => {
        const to = openAsks().find((a) => a.id === ask.id);
        if (to) goToAsk(to, openAsks());
      };
      askRowsById.set(ask.id, row);
    }
    const [kind, says] = row.querySelectorAll(".lf-asks-kind, .lf-asks-says");
    const word = itemWord(ask);
    const said = itemSays(ask) || ask.id;
    // Written only on change: an unchanged poll must not feed the mutation stream a
    // screen reader rebuilds its buffer on.
    if (kind.textContent !== word) kind.textContent = word;
    if (says.textContent !== said) says.textContent = said;
    const account = `${word} · ${said}`;
    if (row.title !== account) row.title = account;
    const place = anchor ? anchor.nextElementSibling : asksList.firstElementChild;
    if (place !== row) asksList.insertBefore(row, place);
    anchor = row;
  }
  const live = new Set(asks.map((a) => a.id));
  for (const [id, row] of askRowsById)
    if (!live.has(id)) {
      // An answered ask takes its row with it, and may take the focus with it too — a
      // reader who answered from somewhere else while standing on this row. Hand focus
      // to whatever now stands in its place rather than letting it fall to the body,
      // which is nowhere and takes the ring with it.
      const held = row.contains(document.activeElement);
      const next = row.nextElementSibling ?? row.previousElementSibling;
      row.remove();
      askRowsById.delete(id);
      if (held) (next ?? asksBtn).focus();
    }
}

// The walk over what the page is waiting on the reader for. It wraps at both ends,
// because asks are a worklist rather than a document to read through: answering one takes
// it out of the list, so forward is the direction that has somewhere to go, and a walk
// that clamped there would strand them at the end of it.
//
// Somewhere inside the ask the reader can be stood: one within it, or one hoisted out of
// it and pointing back (a suggestion's row is the column's child, so that it can hang in
// the page margin). Landing on it rather than on the ask puts the reader on something
// that works it, and Tab walks the rest of that ask's own controls from there.
//
// Focusable, not pressable, and that is why it reads the tabindex where `CONTROL_SELECTOR`
// reads `data-lf-offer="button"`. The two selectors look like one that drifted and are two
// questions: what the reader can be put on, and what answers a press. Aligning this one to
// its twin would leave the ask walk with nowhere to land on any ask whose only chrome is a
// focus target — which is what a conversation thread is.
const ASK_CONTROL = "[data-lf-offer][tabindex]";
// Which ask such a control decides, where the widget hoisted it out of the element (the
// attribute lf-suggestion writes on the row it hangs in the margin).
const ASK_ROW = "data-lf-for";
// Chrome that stands *at* an ask without deciding it: the asks tray's rows. Separate
// from ASK_ROW above, because the two say different things about the same element and
// one of them has a consumer that must not confuse them — stepAsk looks through ASK_ROW
// for the control to put the reader on, and a row that merely points at the ask is not
// that control. What they share is this: focus on either means the reader is standing at
// that ask, which is the one question askPlace asks.
const ASK_AT = "data-lf-at";
// The tab stop this walk lends an ask that holds nothing to work: such an ask has no box
// in the tab order and the runtime writes it one — which is paint on the author's element,
// and PAGE_PAINT_ATTRIBUTES is the whole of what the runtime may leave standing there (a
// `tabindex` in it would blind the replay signature to an authored one). So the lend lasts
// exactly as long as the ring it goes with: the walk hands the stop over as it moves, and
// markHere takes it back when the reader leaves.
//
// One function for both ends of it, because written as statements at each end the walk's
// half only ever wrote — it took the last lend's reference with it and left the stop
// standing. Two control-less asks in a row is all it took, and the walk in the shipped
// examples goes through two: stepping off a task left it wearing a tab stop that nothing
// afterwards was ever going to remove.
let askLent = null;
function lend(ask) {
  if (askLent === ask) return;
  askLent?.removeAttribute("tabindex");
  askLent = ask;
  if (ask) ask.tabIndex = -1;
}
// Where the walk last left off. Not the same question as where the reader is standing,
// though one answer used to serve both: the ring said where they were and the walk read
// its own last landing off it. The Asks button is the walk's own control and focuses
// itself on the way to running a step, so a reader pressing it is standing in the banner
// and the ring is rightly gone from the page — leaving the walk with nothing to step from
// but whatever happens to be on screen, which would send every second press on that
// button back up the page.
let landed = null;
// A place in the document, stated as the ask it belongs to wherever it belongs to one: a
// control hoisted out of its ask and pointing back at it stands for that ask and not for
// the block it was hung beside, or stepping back from a suggestion's own ✓ Accept would
// land on the suggestion the reader is already standing on.
function askPlace(node) {
  const el = node.nodeType === 1 ? node : node.parentElement;
  const row = el?.closest(`[${ASK_ROW}], [${ASK_AT}]`);
  const at = row?.getAttribute(ASK_ROW) ?? row?.getAttribute(ASK_AT);
  return (at && elementById(at)) ?? node;
}
// The open ask the reader is standing in: the one holding the focus, or the one a control
// hoisted into the margin decides. The innermost of them, an ask being able to hold
// another (a question inside a suggestion's lf-new) — openAsks answers in document order,
// so the last container in the list is the nearest one.
//
// document.activeElement rather than focused(), for the reason askPosition gives: a
// control staged in a shadow tree retargets to its host, and the host is the place in the
// document this wants.
function standingIn() {
  const held = document.activeElement;
  if (!held || held === document.body) return null;
  const place = askPlace(held);
  return openAsks().findLast((ask) => ask === place || ask.contains(place)) ?? null;
}
// The ring that says so, painted from the focus rather than written where the reader was
// put. The walk used to write it, and it then said where the walk had left them rather
// than where they were: click away, work in the panel, come back tomorrow, and an ask
// nobody was standing in went on wearing "you are here". Every other way into an ask —
// Tab, a click on one of its controls — left the ring somewhere else entirely, so the
// same place was marked or not by how the reader had reached it.
//
// Keyed on focus and not on :focus-visible, which is a claim about the last input rather
// than about where the reader is: the Asks button's own press lands the focus by script
// after a click, and the ask it brought the reader to would wear nothing at all.
//
// The ask wears it, and so does every box it shows through (shownParts): the ask is
// what carries the id captureView writes down and the place askStep measures from,
// while an outline needs a box to hang on. Every widget in the vocabulary draws one
// box now — the wrapper that declined to took a form instead, in its own stylesheet,
// after the ring went out over its pieces and read as two boxes touching rather than
// as the one ask the reader is standing in — so on shipped pages the parts are the
// ask itself, and the fallback answers the wrapper any page can still style boxless
// in a line, the same way the thread's mark does (paintAnchors).
//
// The tray's row for the ask is a second surface showing this one fact, so it is
// painted from this one reading rather than from a mark the tray keeps for itself —
// and the ring is the chrome's as much as the page's (the [data-lf-ask] rule in the
// stylesheet is written against the attribute, not against the page), so wearing the
// attribute is the whole of what the row needs.
function markHere() {
  const here = standingIn();
  const row = here && asksPanel.querySelector(`[${ASK_AT}="${here.id}"]`);
  const wearing = new Set(
    here ? [here, ...shownParts(here), ...(row ? [row] : [])] : [],
  );
  // A walk that runs past the foot of an open tray leaves its mark off screen, which is
  // the tray saying nothing exactly while the reader is using it. `nearest` so a row
  // already in view moves nothing.
  if (row && openTray("asks")) row.scrollIntoView({ block: "nearest" });
  for (const marked of document.querySelectorAll(`[${PAGE_PAINT_ATTRIBUTE.ask}]`))
    if (!wearing.has(marked)) marked.removeAttribute(PAGE_PAINT_ATTRIBUTE.ask);
  // A control-less request can borrow its own tab stop while the broader x-ask
  // region wears the ring. Keep that stop until the reader leaves the region.
  if (askLent !== (here && askSource(here))) lend(null);
  for (const marked of wearing) marked.setAttribute(PAGE_PAINT_ATTRIBUTE.ask, "1");
}
const readingBlock = () => blocksOnScreen().next().value?.[0] ?? null;
// Where the walk measures from: where the reader is standing, rather than where the walk
// last put them. It carried an id of its own, so every walk the reader had not made with
// this key started at the top of the page — select a paragraph and press `n` and you were
// taken back past everything you had read, and so was anyone scrolled halfway down
// pressing it for the first time. d/u measure from the scroll position and j/k from the
// focused thread; this measured from its own memory, which is the one place the reader
// isn't.
//
// Read in the order of how directly each says where they are: what they have focused,
// what they have selected, where this walk last left off (`landed`), and what they are
// reading. Every one of them can be absent, and then the first ask is the only answer
// there is.
//
// document.activeElement rather than focused(): a control staged in a shadow tree
// retargets to its host, which is exactly what this question wants — a place in the
// document to measure the asks against, not the control the register would dispatch to.
function askPosition() {
  const held = document.activeElement;
  // The banner stands over the page rather than in it, and its controls are addresses
  // the reader holds from wherever they are. The Asks button focuses itself on the way
  // to running this, so measuring from it would send every press on it back to the top.
  if (held && held !== document.body && !banner.contains(held)) return askPlace(held);
  const sel = getSelection();
  // A caret counts here, where the composer's reading of the selection (pageSelection)
  // wants words to quote: a click that placed one is the reader saying where they are.
  if (sel?.focusNode && !inChrome(sel.focusNode)) return askPlace(sel.focusNode);
  // A landing whose element a later version dropped is no place at all, and
  // compareDocumentPosition against a detached node answers about no document.
  return (landed?.isConnected ? landed : null) ?? readingBlock();
}
// The ask `dir` steps to from there. Document position rather than an index into the
// list, because the reader's place is a place and not a row: an ask holding it is the one
// they are standing on, so it is what they step off rather than what they step to.
function askStep(asks, dir) {
  const here = askPosition();
  if (!here) return dir > 0 ? asks[0] : asks.at(-1);
  const side =
    dir > 0 ? Node.DOCUMENT_POSITION_FOLLOWING : Node.DOCUMENT_POSITION_PRECEDING;
  const reach = asks.filter((ask) => {
    const rel = here.compareDocumentPosition(ask);
    return !(rel & Node.DOCUMENT_POSITION_CONTAINS) && rel & side;
  });
  return dir > 0 ? (reach[0] ?? asks[0]) : (reach.at(-1) ?? asks.at(-1));
}
// Where the reader stands when they are put on an ask: the control that works it —
// one inside the ask, or one the widget hoisted into the margin and pointed back at
// it — or the ask itself, lent a tab stop where it holds nothing to work. Named
// because two presses put a reader on an ask and one of them is not a walk: a widget
// rebuilt under the reader (rebuild) has to hand back the place they were standing,
// and a second answer to "where is that" would drift from this one the first time the
// control rule changed.
function standOn(el) {
  const source = askSource(el);
  const control =
    source.querySelector(ASK_CONTROL) ??
    document.querySelector(`[${ASK_ROW}="${source.id}"] ${ASK_CONTROL}`);
  if (!control) lend(source);
  (control ?? source).focus({ preventScroll: true });
}

// Standing on one ask: what n and p do once they have decided which, what a press on a
// tray row does having been told outright, and where `g a` lands a digit. One function
// because it is one act — a second would be a second answer to "how do I put the reader on
// an ask", and the two would drift the first time either the reveal or the focus rule
// changed.
//
// The list comes with the ask, because the announcement names a place in it and the caller
// is the one that knows which list it walked: the walk's own, the tray's, or the whole of
// what the page is waiting on where an address reached past the nine it can spell.
function goToAsk(next, asks) {
  // A thread's ask lives in the panel, which has no geometry while closed — the
  // same reason reveal() opens a settled group before the scroll.
  if (inChrome(next) && !panelOpen) setPanel(true);
  reveal(next); // a settled group or an inactive tab has no geometry until it opens
  const source = askSource(next);
  if (source !== next) reveal(source); // let the answering widget settle its own chrome
  landed = next;
  // The ring follows: the focus move is what paints it, so the walk says where to stand
  // and markHere says where the reader is standing, rather than both saying the second.
  standOn(next);
  // A page Ask starts below the banner so its context comes before its control. A
  // thread Ask is in the panel's own list, whose arrival stays centred in that region.
  // One travel for both, because which box it moves is now the travel's own question
  // (scrollerFor) rather than a second one asked here; what stays is the destination,
  // which is the banner's clearance in the document and the middle of the list.
  scrollToElement(next, SCROLL, inChrome(next) ? "center" : "start");
  announce(`${asks.indexOf(next) + 1} of ${asks.length} waiting on you`);
}
function stepAsk(dir) {
  const asks = openAsks();
  if (!asks.length) return; // never: the key and the control are live only with asks
  goToAsk(askStep(asks, dir), asks);
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
    if (inChrome(w) || w.parentElement?.closest(opaque)) continue;
    pairs.push([w, ` ${w.tagName}#${w.id}`]);
  }
  return pairs;
}
// The base version's own document, which is the whole of what a comparison waits for. Split
// from the marking below so that everything touching the live page happens in one synchronous
// stretch after the single await: the walk through the menu asks for a comparison per row, and
// a marking pass that could interleave with the next row's would leave two bases' marks
// standing under a chooser naming one of them.
async function baseDocument(baseVersion) {
  const baseName = versionUrl(baseVersion);
  const res = await fetch(baseName);
  if (!res.ok) throw new Error(`couldn't load ${baseName}`);
  return new DOMParser().parseFromString(await res.text(), "text/html");
}
function applyDiff(doc, baseVersion) {
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
  const baseProjection = stateProjection(baseVersion);
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
        const before = writer
          ? foldedFacet(writer.e, spec.record)
          : domFacet(baseEl, spec.record);
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
  // Container widgets surface marks their panels hide (lf-tabs badges each tab).
  document.dispatchEvent(new CustomEvent("lf-comparison"));
  return diffMarked.length;
}
// Whether a version can be compared with the one being read: anything published
// before it, which is which rows the menu builds a press onto.
const comparable = (version) =>
  runtime.currentVersion !== null && version < runtime.currentVersion;
// Every rendering of the pair above, written in one place: the chooser's word, its
// paint and what it says it will do, the checked state of each row's Δ, and the rail
// down the rows the comparison spans. Called by the setter, by a menu rebuild — the
// other thing that can leave a rendering behind the state — and once at load, so what
// the chooser says it will do is written here from the start rather than standing as a
// second copy of these sentences up where the control is built.
function paintDiff() {
  versionBtn.textContent = versionLabel(diffOn);
  versionBtn.classList.toggle("on", diffOn);
  // Rewritten on every diff change, so the key it names is taken from the row each time
  // rather than typed into one of the two branches and forgotten in the other.
  versionBtn.title = diffOn
    ? `Showing what changed since v${diffBase} — pick a version, or press its Δ again to stop`
    : `Versions: read one, or mark what changed since it (${labelOf(CHOOSER)})`;
  for (const row of versionMenu.querySelectorAll(".lf-version-row")) {
    const version = +row.dataset.lfVersion;
    row.classList.toggle(
      "lf-compared",
      diffOn && version >= diffBase && version <= runtime.currentVersion,
    );
  }
  for (const press of versionMenu.querySelectorAll(".lf-version-diff"))
    press.setAttribute(
      "aria-checked",
      String(diffOn && +press.dataset.lfVersion === diffBase),
    );
}
paintDiff();
// Whether the comparison is standing and what against — the only thing that decides
// it, the marks and the paint being renderings rather than a second copy.
function setDiff(on, base) {
  diffOn = on;
  if (on) diffBase = base;
  if (!on) {
    diffRequest++; // a stop outranks a comparison still on its way
    for (const b of diffMarked) b.classList.remove("lf-ins-block");
    diffMarked.length = 0;
    document.dispatchEvent(new CustomEvent("lf-comparison"));
  }
  paintDiff();
}
// The one way a comparison starts, from a row's press or from the walk through the menu.
// It states a base rather than toggling one — the toggle is a press's own reading of it,
// and the walk has none to spend, standing on a row being what makes it the base however
// many times the reader arrives there.
async function showComparison(base) {
  const mine = ++diffRequest;
  let doc;
  try {
    doc = await baseDocument(base);
  } catch {
    showToast(`Couldn't load v${base}`);
    return;
  }
  if (mine !== diffRequest) return;
  if (diffOn) setDiff(false); // the old base's marks, before the new base's land
  const n = applyDiff(doc, base);
  setDiff(true, base);
  showToast(
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

// ---------- banner ----------
// "Claude is working" is a claim in status.json, and nothing revises a claim once the
// session behind it walks away — so a page nobody is watching reads exactly like a page
// whose user has said nothing yet. The banner asks whether anyone is attending, and
// only two things answer yes: Claude is credibly busy, or a `leaf wait` is live.
// Everything else is absence, where the reason and the remedy are all that vary.
//
// One of those absences is not a fault, and reading it as one was the bug. A page served
// across sessions — a command hub, a dashboard left open for a fortnight — is unheld for
// most of its life, and a night of it is Tuesday. So the banner separates "somebody is
// behind this page and isn't keeping up", which is worth an amber dot and a nudge, from
// "nobody is behind it", which is the standing page at rest: grey, and the plain fact
// that it picks up again when a session does.
//
// Every one of those answers is about a session that exists or existed, and a page can be
// served with none — the whole of leaf.page is, each example a working page on a static
// host where the log is the reader's own browser and no agent will ever read it. The
// banner had no way to say that, so the page said the nearest thing it could and claimed
// to be listening: green dot, "awaits", over a page waiting for nobody. Whoever answers
// the poll declares it instead (`unattended`), and it is judged ahead of the rest because
// it is not a state the evidence below could reach — there is no claim to weigh, no
// lifetime to look for, and nothing coming that would change the answer.
const HANDOFF_GRACE_MS = 2 * 60 * 1000;
const WORKING_GRACE_MS = 15 * 60 * 1000;
// How long a claim of work may go unrefreshed before the page stops taking its word for
// it. Exported, because the banner is not the only thing that judges one: a page running
// a fleet says the same sentence per row, and a second threshold spelled in a widget
// would be a second answer to "how long is too long" — free to disagree with the banner
// directly above it about the very same silence. The caller supplies the rope where its
// claim has a shorter one; the constant is the default because that is the case there is
// only one of.
export const quietSince = (ts, grace = WORKING_GRACE_MS) =>
  Boolean(ts) && serverNow() - new Date(ts).getTime() > grace;
// How long after a turn closes a claim it left behind is still believed. The grace
// above asks how long a claim has gone unrenewed; this one exists because the answer
// to "is anything still behind it" arrives before the answer to "has it gone stale",
// and it needs a margin: the agent claims the work, hands it to a delegate and ends
// the turn in the same second, and the delegate's first note is a minute or so behind
// that. Shorter than the grace by an order of magnitude, because it is measured from
// an observed event rather than from the absence of one.
const PICKUP_GRACE_MS = 2 * 60 * 1000;
// The second question the page asks of a claim, beside how long it has gone
// unrenewed: did the turn behind it end with nothing picking it up. This one has an
// answer the moment it becomes true, because the Stop hook watches the ending rather
// than inferring it from silence. Written no later than the ending counts as written
// by the turn that ended — both stamps carry seconds, and an agent's last word about
// its work and the end of the turn that wrote it land in the same one all the time.
// Shared, because a page claim and a note on a thread are written by one command and
// a seat answering this differently for one of them is the two of them arguing about
// a single silence.
const droppedAt = (ts, turnClosed) =>
  Boolean(turnClosed) &&
  Date.parse(ts) <= Date.parse(turnClosed) &&
  quietSince(turnClosed, PICKUP_GRACE_MS);
// Which claim each kind reads out, and so whose detail it may speak. The question
// sits here rather than at each seat, for the reason `kind` does: two seats answering
// it separately is two answers to what the page may say it is waiting for. A kind
// absent here is a judgment against the claim — nobody is behind the page, or the page
// is closed — and the claim's words about the work are not the news there.
//
// `stalled` reads a `working` claim's detail like `working` does, and that is the whole
// difference between the two: same words, a sentence that dates them. They were one
// judgment once, folded into `listening` because a watcher was live, and the detail was
// dropped on the way — so a page whose agent had said "revising the plan" and then
// spent twenty minutes in a delegate's hands read "Claude awaits — select text to
// comment", inviting the reader to start something over a page already mid-answer. The
// dropping was right for the sentence it was under: what the agent was doing is the
// wrong half of the loop to read out after "awaits". The sentence was the mistake.
const DETAIL_FROM = { working: "working", listening: "waiting", stalled: "working" };
// The claim-against-proof judgment, one function for every surface that shows a
// status: the banner's sentence about this page and a panel row about a neighbour
// read the same fields the server gathers in one place (`presence`), so the two can
// never disagree about what "working" means. `kind` is the judged state and `detail`
// the claim's own words where that state licenses them; the caller words it for its
// seat.
function presented(state) {
  const { status, listening, session_alive, unattended, turn_closed } = state;
  // How long the claim has gone unrefreshed. The rope is short for the status
  // `leaf wait` writes as it prints a batch, because the agent writes its own
  // `leaf status` after acknowledgement — that mark outliving minutes is a dropped
  // pickup, not a long turn.
  const aged = quietSince(
    status.ts,
    status.handoff ? HANDOFF_GRACE_MS : WORKING_GRACE_MS,
  );
  // The same silence reached by evidence instead of by a clock. A claim is written by
  // a model's turn, and when that turn ends nothing runs — so the page could only ever
  // find an abandoned claim by waiting out the grace, saying "Claude is working" over
  // nobody for most of a quarter of an hour. The Stop hook records the ending, and a
  // claim older than it is one that neither a next turn nor a delegate renewed across
  // the boundary. A delegate that does check in writes a `ts` past the stamp and
  // carries the claim on its own from then on, which is the same one command that
  // writes its note — so this costs the delegate case nothing and closes the window
  // on the case it was hiding.
  const dropped = droppedAt(status.ts, turn_closed);
  const quiet = aged || dropped;
  // Nothing is behind the claim. The claimant's lifetime settles it where there is
  // one: over is over, whatever the claim says and whether a stray `leaf wait` still
  // holds a lease for a session that can no longer read it. Where nothing claimed the
  // page — a server started outside an agent host — there is no lifetime to read, so a
  // live watcher or a claim still inside its grace is the whole of the evidence, and
  // once both are spent the page is unheld too.
  const unheld =
    session_alive === false || (session_alive === null && !listening && quiet);
  const kind = unattended
    ? "unattended"
    : status.state === "idle"
      ? "closed"
      : unheld
        ? "unheld"
        : status.state === "working"
          ? // A claim of work outranks the watcher under it, fresh or stale: what the
            // agent said it was doing is the news either way, and going quiet on it is
            // the news the reader is least able to work out for themselves. The rope is
            // the same one a roster row holds a worker to, so "gone quiet" means one
            // thing on the page whoever is being judged — and a note on a thread
            // (`leaf status … --on`) renews the claim, which is how work handed to a
            // delegate stays true across a turn boundary the session cannot write over.
            !quiet
            ? "working"
            : listening
              ? "stalled"
              : "away"
          : listening
            ? "listening"
            : "away";
  return {
    kind,
    quiet,
    // Which of the two silences this is, for the seat that has to date it. Not a kind
    // of its own: whether the reader's next word still reaches anyone is the question
    // `stalled` and `away` already split on, and this is orthogonal to it.
    dropped,
    // Whether anything at all answers for the claim. The banner drops a claim
    // nothing is behind rather than repeating it, and every other seat reading
    // the same claim has to drop it on the same evidence: a note left on a
    // thread by a session that has since died would sit under a line saying no
    // session holds the page, each half arguing with the other about the same
    // fact. Not the same question as `quiet`, which is about a claim going
    // unrenewed by somebody who is still there.
    held: kind !== "unheld" && kind !== "unattended",
    detail: status.state === DETAIL_FROM[kind] ? status.detail : "",
  };
}
// The judgment's third seat. A reader keeps a leaf in a tab for days and looks at
// six of them; the tab strip is the whole of what the browser shows about a page nobody
// has open, so the state that decides whether to go there belongs in it. Same judgment
// (presented), same writer as the dot and the line, and the tone is taken off the dot
// itself rather than mapped from kind to token again — one answer to what a tone looks
// like, so a project overriding --ok overrides the tab with it and the two cannot come
// apart. It is a read of the theme, not of the rendering: what colour this tone paints
// as is a question nothing else can answer, where what state the page is in is already
// in hand.
//
// The mark is the vendored icon.svg — the page's own asset like the theme, so a project
// can put its own there — and all the runtime does to it is paint the one element it
// declares. Refused rather than defaulted, as the theme's shadow block is: a mark with
// no lf-tone leaves a tab that never changes, which is a status readout that silently
// isn't one.
const tabLink = Object.assign(document.createElement("link"), {
  rel: "icon",
  type: "image/svg+xml",
  href: "/icon.svg",
});
document.head.append(tabLink);
let iconMark = null;
const iconUrls = new Map();
// The mark with one colour written over it, or — for "" — the mark as authored. A style
// element appended last outranks the file's own rules, the dark-scheme block included,
// since a media query carries no specificity of its own. So this knows nothing about the
// icon beyond the class it promises, and a project's own mark is painted on the same
// terms.
function iconUrl(color) {
  let url = iconUrls.get(color);
  if (url === undefined) {
    const svg = iconMark.cloneNode(true);
    if (color) {
      const style = svg.ownerDocument.createElementNS(
        "http://www.w3.org/2000/svg",
        "style",
      );
      style.textContent = `.lf-tone { fill: ${color} }`;
      svg.append(style);
    }
    url =
      "data:image/svg+xml," +
      encodeURIComponent(new XMLSerializer().serializeToString(svg));
    iconUrls.set(color, url);
  }
  return url;
}
async function loadIcon() {
  const response = await fetch("/icon.svg");
  if (!response.ok)
    throw new Error(`leaf: the tab icon failed to load (${response.status})`);
  const doc = new DOMParser().parseFromString(await response.text(), "image/svg+xml");
  // Two failures, and the same symptom: no element to paint. A parse error is reported
  // as a document rather than thrown, so a mark that isn't SVG at all reaches the class
  // check and fails it — sending whoever overrode the file to look for a class that is
  // sitting right there in it.
  const broken = doc.querySelector("parsererror");
  if (broken)
    throw new Error(
      // Collapsed, because the browser's report is laid out as a page and reads as
      // several lines of it; what matters is the line and column it names.
      `leaf: icon.svg is not SVG — ${broken.textContent.replace(/\s+/g, " ").trim()}`,
    );
  if (!doc.querySelector(".lf-tone"))
    throw new Error(
      "leaf: icon.svg carries no lf-tone element, which is where the page's " +
        "status is painted",
    );
  iconMark = doc.documentElement;
  // Left where `version export` can find it: a file has no session behind it, so a copy
  // wears the mark saying nothing rather than the tone it was exported under.
  tabLink.dataset.lfRest = iconUrl("");
  paintTab();
}
// A declaration, and called from two places, because the fetch above can land after the
// first poll has already judged the page.
function paintTab() {
  if (!iconMark) return;
  const url = iconUrl(getComputedStyle(dot).backgroundColor);
  // Written only on change: an unchanged poll must not hand the browser its icon again
  // every two seconds.
  if (tabLink.getAttribute("href") !== url) tabLink.setAttribute("href", url);
}
// One writer for the dot, the line and the tab, offline included: null is the poll saying
// it couldn't reach the server, not a second function's own rendering. The line is one of
// the two things on the row that give up width when it runs out (see the theme), so what
// a narrow window clips is a hover away, the way the version chooser's label is — worth
// more now that the line carries the ask and not only the state. Written every time
// rather than only when the box clips, because whether it does is a fact about the
// rendering and nothing here reads that back.
const showStatus = (tone, ...parts) => {
  dot.className = "lf-dot" + (tone ? " " + tone : "");
  statusText.textContent = "";
  statusText.append(...parts);
  statusText.title = statusText.textContent;
  paintTab();
};
function renderStatus(state) {
  if (state instanceof Error) {
    showStatus("offline", "Page couldn't apply current state — reload");
    return;
  }
  if (state === null) {
    showStatus("offline", "Server offline — comments won't send");
    return;
  }
  const { status, pending } = state;
  const { kind, quiet, dropped, detail } = presented(state);
  // What the user's words do meanwhile. The log takes them with nobody on the other
  // end; the only thing attendance changes is when they are read.
  const saved = pending
    ? `${pending} update${pending === 1 ? "" : "s"} waiting.`
    : "Your comments are saved.";
  // Dated by whichever fact ended the belief. A dropped claim is dated by the ending
  // and not by its own last word, because "last checked in just now" under an amber
  // dot is the line arguing with the dot beside it.
  const dated = dropped
    ? `${agentName()} left this when its turn ended ${ago(state.turn_closed)}`
    : `${agentName()} last checked in ${ago(status.ts)}`;
  let text = "",
    showAge = false;
  if (kind === "closed") text = "Leaf closed";
  else if (kind === "unattended")
    // No agent named and no pickup promised, which is the whole difference from
    // `unheld` below: there is nobody to name and nothing coming. What the reader can
    // still do is everything — the page works, it just works alone — so the line says
    // where their gestures go rather than that they are saved for someone.
    text = "Nobody is behind this page. What you do here stays in this browser.";
  else if (kind === "unheld")
    // No agent is named, because which one picks the page up next is not a fact this
    // page holds — only that the log is there for whichever does.
    text = `No session holds this page. ${saved} It picks up again when a session does.`;
  else if (kind === "working") {
    showAge = Boolean(status.ts);
    text = `${agentName()} is working${detail ? " — " + detail : ""}`;
  } else if (kind === "listening") {
    // Attendance is half the news; the other half is what the page wants back. The
    // Asks count beside it says how many things are unanswered and nothing about what
    // any of them is, so the claim's detail says that here in the agent's own words,
    // the way a `working` claim's says what it is doing. With nothing declared it is
    // the standing instruction, which is what a page asking nothing wanted anyway.
    //
    // "awaits" while the judged kind stays `listening`: they name different things.
    // The kind and the server field behind it are the evidence — a watcher live on the
    // other end — and the words are the stance it supports, which is the registry's
    // own word for a standing request to the reader (x-awaits). Wording is the seat's,
    // per `presented`, so a row in the leaves panel leads with the bare word and
    // carries the same ask behind it.
    text = `${agentName()} awaits — ${detail || "select text to comment"}`;
  } else if (kind === "stalled") {
    // The claim stands, dated, with no remedy attached: a watcher is live, so the
    // reader's next word reaches the agent without anyone touching a terminal. What
    // they are owed is the age, which is the one thing they cannot see for themselves
    // and the whole of what separates a delegate mid-answer from a dropped thread. It
    // is spoken in the same words the branch below uses for the same silence, rather
    // than in the muted parenthesis a live `working` claim wears: there the age is a
    // footnote to news, and here it is the news.
    text = `${dated}${detail ? ": " + detail : ""}. ${saved}`;
  } else {
    // Somebody is behind the page and isn't attending: say which and what to do. A
    // long silence means Claude lost the thread; a recent check-in means it is
    // mid-turn and the next one collects.
    const [why, how] = quiet
      ? [`${dated}.`, "Nudge it in the terminal."]
      : [`${agentName()} isn't watching right now.`, "It picks them up next turn."];
    text = `${why} ${saved} ${how}`;
  }
  const line = [text];
  if (showAge)
    line.push(
      " ",
      Object.assign(el("span", "lf-age"), { textContent: `(${ago(status.ts)})` }),
    );
  showStatus(TONE[kind], ...line);
}

// ---------- live version activation ----------
const versionDocuments = new Map();
let activatingState = null;
function versionDocument(version) {
  if (versionDocuments.has(version)) return versionDocuments.get(version);
  const name = versionUrl(version);
  const loading = fetch(name)
    .then(async (response) => {
      if (!response.ok) throw new Error(`couldn't load ${name} (${response.status})`);
      const generation = response.headers.get("Leaf-Layer");
      if (generation && !sameLayer(generation)) return null;
      const doc = new DOMParser().parseFromString(await response.text(), "text/html");
      if (
        !doc.querySelector("body > main") ||
        doc.querySelectorAll("body > main").length !== 1
      )
        throw new Error(`${name} has no single authored main`);
      return doc;
    })
    .catch((error) => {
      versionDocuments.delete(version);
      throw error;
    });
  versionDocuments.set(version, loading);
  return loading;
}

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

function activateHead(doc, version) {
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
  let marker = document.querySelector('meta[name="lf-version"][data-lf-runtime]');
  if (!marker) {
    marker = document.createElement("meta");
    marker.name = "lf-version";
    marker.dataset.lfRuntime = "1";
    document.head.insertBefore(marker, runtimeStyle);
  }
  marker.content = String(version);
  stateSignoff(doc.querySelector('meta[name="lf-review"]')?.content === "sign-off");
}

function resetAuthoredPage() {
  authoredFacets.clear();
  authoredDetails.clear();
  authoredStatements.clear();
  authoredMarkup.clear();
  authoredWidgets.clear();
  committedProjection.clear();
  for (const attr of [
    PAGE_PAINT_ATTRIBUTE.applied,
    PAGE_PAINT_ATTRIBUTE.replayWrote,
    PAGE_PAINT_ATTRIBUTE.reportWrote,
  ])
    document.body.removeAttribute(attr);
}

async function activateVersion(doc, version) {
  const view = captureView();
  const source = doc.querySelector("body > main");
  const fresh = document.importNode(source, true);
  versionDocuments.delete(version);
  const settlingFrom = settling.length;
  const comparedFrom = diffOn ? diffBase : null;
  if (diffOn) setDiff(false);

  resetAuthoredPage();
  rememberAuthoredMarkup(source);
  rememberAuthoredMarkup(fresh);
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
  runtime.currentVersion = version;
  activateHead(doc, version);
  document.querySelector("body > main").replaceWith(fresh);
  pruneScopedElements();
  settle(dress(fresh));
  await Promise.allSettled(settling.slice(settlingFrom));
  reachScrollers(fresh);
  captureAuthoredFacets(fresh);
  stateStrip();
  syncLayout();
  if (designOn) paintLegend();
  return { view, comparedFrom };
}

// Navigate to a version with the pin semantics every chooser shares: an older
// version pins the view, the newest unpins it.
let forceActivation = false;
const goVersion = (version) => {
  if (LIVE_ROOT && version === runtime.currentVersion) return;
  if (LIVE_ROOT && version === runtime.latestVersion) {
    forceActivation = true;
    showVersionMenu(false);
    poll();
    return;
  }
  const path = versionUrl(version);
  location.href = version === runtime.latestVersion ? path : `${path}?pin`;
};
function renderVersions(state) {
  versions.splice(0, versions.length, ...state.versions);
  versionBtn.disabled = !versionsOffered();
  const notes = {};
  for (const e of runtime.events) if (e.kind === "note") notes[e.version] = e.text;
  const key = JSON.stringify([state.versions, notes]);
  const current = state.versions.includes(runtime.currentVersion)
    ? runtime.currentVersion
    : null;
  // Rebuilt rather than reconciled: this runs only when the versions or their notes
  // actually changed, which on a page's whole life is a handful of times, and the
  // menu is only ever read while it is open — where a rebuild would take the focused
  // row out from under a walk. So an open menu defers the rebuild, and the key is
  // what the built list holds rather than what the last poll saw: consuming it here
  // and skipping the build inside would mark the change handled and leave that
  // version out of the menu until some later one happened along. A version arriving
  // under an open menu is the new-version chip's news; the list catches up on the
  // next poll after it closes.
  if (key !== lastVersionsKey && !versionMenuOpen) {
    lastVersionsKey = key;
    versionMenu.textContent = "";
    for (const version of state.versions) {
      const isLatest = version === state.versions.at(-1);
      const row = el("button", "lf-version-row");
      row.setAttribute("role", "menuitem");
      row.dataset.lfVersion = version;
      // The version and its note are two kinds of word — which one this is, and
      // what it was — so they are two elements rather than one string. That is
      // what lets the note wrap to as many lines as it needs, which is the whole
      // reason the notes are here rather than on a control 190px wide.
      row.append(
        el("span", "lf-version-num", `v${version}${isLatest ? " (latest)" : ""}`),
      );
      if (notes[version]) row.append(el("span", "lf-version-note", notes[version]));
      if (version === current) row.setAttribute("aria-current", "true");
      row.onclick = () => {
        showVersionMenu(false);
        goVersion(version);
      };
      versionMenu.append(row);
      // The comparison this row offers, in the menu's second column beside the note
      // that says the same thing in words. A grid sibling rather than a child, a
      // button inside a button being no markup at all, and named in full: the glyph
      // is the eye's shorthand and says nothing aloud.
      if (comparable(version)) {
        const press = el("button", "lf-version-diff", "Δ");
        press.setAttribute("role", "menuitemcheckbox");
        press.dataset.lfVersion = version;
        press.setAttribute("aria-label", `Mark what changed since v${version}`);
        press.title = `Mark what changed since v${version}`;
        // The pointer's own door, and it closes the menu: the marks are on the page this
        // hangs over, and a pointer has no walk to be standing in the middle of. The
        // keyboard's is the walk itself, which leaves the list up.
        press.onclick = () => {
          showVersionMenu(false);
          pressComparison(version);
        };
        versionMenu.append(press);
      }
    }
    paintDiff(); // a fresh list, and a standing comparison to show on it
  }
  runtime.latestVersion = state.versions.at(-1) ?? null;
  const behind =
    runtime.latestVersion !== null &&
    runtime.currentVersion !== null &&
    runtime.latestVersion !== runtime.currentVersion;
  // An immutable unpinned document still follows by navigation. The live root's
  // activation decision was made before this rendering, where its fetched document and
  // the composition hold were both available. Either route leaves the chip as news
  // while it is behind.
  if (behind && !LIVE_ROOT && !PINNED && !midComposition()) {
    location.replace(versionUrl(runtime.latestVersion));
    return;
  }
  showNews(latestChip, behind);
  if (behind)
    latestChip.textContent = `New version available → open v${runtime.latestVersion}`;
}
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
export const dragging = (el, on) => {
  el.classList.toggle("lf-dragging", on);
  paintKeys();
};
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
const midComposition = () =>
  composerOpen ||
  Boolean(fabAnchor) ||
  unaccountedGesture() ||
  (document.activeElement?.tagName === "TEXTAREA" &&
    (document.activeElement.value !== "" ||
      document.activeElement.hasAttribute("data-lf-offer")));
// Through the chooser's one door, so the chip opens exactly the version it names. At the
// live root that is an explicit in-place release of the composition hold; on an immutable
// page it is ordinary version travel.
latestChip.onclick = () => goVersion(runtime.latestVersion);

// ---------- polling ----------
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
  return anchorRuntime.blocksOnScreen(...args);
}
function captureView(...args) {
  return anchorRuntime.captureView(...args);
}
function restoreView(...args) {
  return anchorRuntime.restoreView(...args);
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
export function itemWord(...args) {
  return anchorRuntime.itemWord(...args);
}
function itemSays(...args) {
  return anchorRuntime.itemSays(...args);
}
function resolveAnchor(...args) {
  return anchorRuntime.resolveAnchor(...args);
}
export function shownBand(...args) {
  return anchorRuntime.shownBand(...args);
}
export function shownBox(...args) {
  return anchorRuntime.shownBox(...args);
}
export function shownParts(...args) {
  return anchorRuntime.shownParts(...args);
}
function shownRect(...args) {
  return anchorRuntime.shownRect(...args);
}
function startsAt(...args) {
  return anchorRuntime.startsAt(...args);
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
  renderRetired,
  settledAway,
  DATUM,
  uiInside,
  inUi,
  inChrome,
  pageWords,
  layerPart,
  TEXT_BLOCK,
  elementOver,
  under,
  authored,
  textNodesUnder,
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
  textUnits,
  alignText,
  movedWords,
  says,
  wrote,
  rangeOf,
  holds,
  neighbourhood,
  pageText,
  spanIn,
  findQuote,
} = passageRuntime;
export {
  alignText,
  inChrome,
  inUi,
  movedWords,
  renderRetired,
  says,
  textNodesUnder,
  wrote,
};

const runtimeProjection = createProjection(runtime, {
  ASK_ROW,
  COLLAPSE,
  MARKED_ANYWHERE,
  MARKED_IN_PAGE,
  PAGE_PAINT_ATTRIBUTE,
  PAGE_PAINT_ATTRIBUTES,
  agentName,
  askContext,
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
  foldedFacet,
  markSettled,
  matchesProjectedWhen,
  paintPending,
  projectedFacet,
  projectionCommitted,
  rebuild,
  reconcileKnownState,
  reconcileState,
  releaseProjectedOutbox,
  rememberAuthoredMarkup,
  requirementMatches,
  retractedIds,
  retractionFloors,
  shallowSigs,
  stageOutboxAction,
  standingState,
  stateCoordinate,
  stateProjection,
  stateSpecs,
  takenBack,
  undoable,
  unitOf,
} = runtimeProjection;

outboxRuntime = createOutbox(runtime, {
  POLL_MS,
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

conversationRuntime = createConversation({
  COMMENTS,
  FOLD_MS,
  MARKED_ANYWHERE,
  SCROLL,
  addressLabel,
  addressed,
  agentName,
  ago,
  captureAuthoredFacets,
  claimState: () => ({ agentTurnClosed, claimingSession, claimsHeld }),
  designName,
  droppedAt,
  el,
  elementById,
  findInput,
  focused,
  highlightBlocks,
  inChrome,
  isMarked: (id) => marked.has(id),
  itemSays,
  itemWord,
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
  panelIsOpen: () => panelOpen,
  panelTitle,
  placedAt: (id) => placed.get(id),
  post,
  quietSince,
  reachScrollers,
  reachedForWords,
  refreshHover,
  registry,
  rememberAuthoredMarkup,
  renderQuiet,
  renderSaid,
  reportPageError,
  retractedIds,
  retractionFloors,
  runtime,
  saveDraft,
  scrollToElement,
  scrollToThread,
  sectionOf,
  sendDraft,
  setPanel,
  settling,
  takenBack,
  tellDraft,
  threadsBox,
  toggleBtn,
  updateSequence,
  wireInput,
});

updateRuntime = createUpdates(runtime, {
  closestAcross,
  coordinateProjectionCommitted,
  inChrome,
  projectionCommitted,
  stateProjection,
  threadList: () => conversationRuntime.threadList,
});

anchorRuntime = createAnchors({
  DATUM,
  LANDMARK_CAP,
  SCROLL,
  TEXT_BLOCK,
  aimBox,
  aimIsOn: () => aiming,
  aimedItem,
  anchorLabel,
  anchorsReady: () => anchoringReady,
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
  elementById,
  elementFromPointAcross,
  elementOver,
  findQuote,
  focusedThreadOf,
  inChrome,
  inUi,
  inspectEl,
  landedAt: () => landed,
  offer,
  pageQueryAll,
  pageScroller,
  pageText,
  pageWords,
  paintThreadQuotes,
  panel,
  quoteFrom,
  queueLegend,
  rangeOf,
  registry,
  reveal,
  runtime,
  scrollerFor,
  setLanded: (value) => (landed = value),
  setPanel,
  settledAway,
  tagsDeclaring,
  textNodesUnder,
  threadsBox,
  uiInside,
  under,
});
const { VIEW_KEY, ITEM, NOTE, marked, placed, pointer } = anchorRuntime;

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
});

export { shallowSigs, standingState };

async function poll() {
  let res;
  try {
    res = await fetch("/api/state");
  } catch {
    // Network absence is a completed answer: there is no log to replay, so the offline
    // authored page is honest. A successful but malformed response is different — let
    // JSON or processing errors escape so the caller retains the recovery boundary.
    res = null;
  }
  const responseGeneration = res?.ok && res.headers.get("Leaf-Layer");
  if (responseGeneration && !sameLayer(responseGeneration)) return;
  // A refusal is not state: the server answers a missing key with error-shaped JSON at
  // 403. A live server refusing the key and a dead one both leave the page unreachable
  // from here, and the terminal link is the recourse for both.
  const state = res?.ok ? await res.json() : null;
  if (!state) {
    const refusedCorrection = outbox.some((entry) => entry.answered && entry.rejected);
    if (runtime.statePhase === "waiting") runtime.statePhase = "offline";
    renderStatus(null);
    if (panelOpen) renderPanel();
    // The sequence consumers still hear the tick. A poll that brought nothing changes
    // no history, so they re-render what they already held — but anything of theirs
    // that reads a clock rather than the log has to keep moving, and a dead server is
    // exactly when it matters: the banner says the server is gone while a roster row
    // froze its "last heard 4m ago" at the moment the answers stopped, which is the
    // authored freshness this widget layer exists to replace, produced by the layer
    // itself. A first failed read has no projection to claim. Once a complete read has
    // installed one, though, an offline tick is still the wake-up for a correction a
    // live editor deferred; a definitively refused local action has the same authored
    // correction even when no read has succeeded yet. Never project a newer event list
    // whose surrounding state threw before lastEventSeq advanced.
    if (
      (runtime.statePhase === "ready" || refusedCorrection) &&
      reconcileKnownState() &&
      releaseProjectedOutbox()
    )
      paintKeys();
    document.dispatchEvent(new Event("lf-actions"));
    notifyDataSubscribers();
    return;
  }
  return receiveState(state);
}

function acceptData(candidate) {
  if (
    !candidate ||
    typeof candidate !== "object" ||
    Array.isArray(candidate) ||
    !Number.isInteger(candidate.revision) ||
    candidate.revision < 0 ||
    !candidate.sources ||
    typeof candidate.sources !== "object" ||
    Array.isArray(candidate.sources)
  )
    throw new TypeError("state data must carry a non-negative revision and sources");
  if (candidate.revision <= runtime.data.revision) return false;
  runtime.data = structuredClone(candidate);
  return true;
}

function notifyDataSubscribers() {
  document.dispatchEvent(new Event("lf-data"));
  // The revision becomes a readiness fact only after synchronous subscribers have
  // rendered it. Render checks and export compare this stamp with the server snapshot,
  // so a data-only page cannot be read between acceptance and projection.
  if (runtime.data.revision >= 0)
    document.body.setAttribute(
      PAGE_PAINT_ATTRIBUTE.dataRevision,
      String(runtime.data.revision),
    );
}

async function receiveState(state) {
  // Every state this page reads passes here — the poll's, and the one an accepted
  // event response carries — so the generation is checked once for both rather than
  // at each door it arrives through.
  if (!sameLayer(state.layer)) return;
  // Ahead of the sequence checks below, which drop a response as state: a reading
  // that arrives out of order still says what time it is where the timestamps are
  // written, and that is the one thing in it that cannot be stale.
  if (state.now) clockSkew = Date.parse(state.now) - Date.now();
  // Events and source snapshots are independent authorities serialized by the same page
  // transaction but observed through overlapping responses. Their revisions form a pair,
  // not one total order: a response with an older event tail may still carry the newest
  // data. Accept that component before the event gate, and never move either one backward.
  const dataChanged = acceptData(state.data);
  const notifyChangedData = () => {
    if (dataChanged) notifyDataSubscribers();
  };
  const nextEvents = state.events;
  const eventSeq = nextEvents.at(-1)?.seq ?? 0;
  // post() and the timer can poll together. The log is append-only, so a response
  // behind one already rendered is unambiguously stale; accepting it would move
  // every event-derived view backwards until the next poll.
  if (eventSeq < runtime.lastEventSeq) {
    if (activatingState) await activatingState;
    notifyChangedData();
    return;
  }
  // Polls and POST answers may overlap. A document activation is the one state read
  // that cannot safely interleave: a second one would capture or replace the halfway
  // upgraded main. Let it commit, then judge this response against its resulting
  // version and sequence.
  if (activatingState) await activatingState;
  if (eventSeq < runtime.lastEventSeq) {
    notifyChangedData();
    return;
  }
  const targetVersion = state.versions.at(-1) ?? null;
  const wantsActivation =
    LIVE_ROOT &&
    targetVersion !== null &&
    runtime.currentVersion !== null &&
    targetVersion > runtime.currentVersion;
  let incoming = null;
  let incomingFailed = false;
  if (wantsActivation) {
    runtime.latestVersion = targetVersion;
    latestChip.textContent = `New version available → open v${targetVersion}`;
    showNews(latestChip, true);
  }
  // Messages render from Markdown; have the renderer in hand before the panel
  // builds a body, so msgNode stays synchronous. Fetch the next authored document on
  // the same background stretch rather than making either network trip wait on the
  // other.
  const preparations = [];
  if (nextEvents.some((e) => e.kind === "comment" || e.kind === "reply"))
    preparations.push(loadMarked());
  if (wantsActivation)
    preparations.push(
      versionDocument(targetVersion)
        .then((doc) => (incoming = doc))
        .catch((error) => {
          incomingFailed = true;
          reportPageError(
            `version v${targetVersion} failed to load: ${error?.message ?? error}`,
          );
        }),
    );
  await Promise.all(preparations);
  if (wantsActivation && incoming === null && !incomingFailed) {
    notifyChangedData();
    return;
  }
  // The preparation above yields. A newer response may have completed while this one was
  // waiting, and two responses may have joined the same version-file promise before
  // either had an activation to await. Serialize again at the commit boundary, then
  // judge this candidate against the version and sequence the winner installed.
  if (activatingState) await activatingState;
  if (eventSeq < runtime.lastEventSeq) {
    notifyChangedData();
    return;
  }
  const willActivate =
    Boolean(incoming) &&
    targetVersion > runtime.currentVersion &&
    (!midComposition() || forceActivation) &&
    !versionMenuOpen &&
    targetVersion === state.versions.at(-1);
  const priorEvents = runtime.events;
  const priorStatePhase = runtime.statePhase;
  const priorLastEventSeq = runtime.lastEventSeq;
  const priorClaimUpdateSources = claimUpdateSources();
  const priorClaimsHeld = claimsHeld;
  const priorAgentTurnClosed = agentTurnClosed;
  const priorClaimingSession = claimingSession;
  const apply = async () => {
    runtime.events = nextEvents;
    let activation = null;
    runtime.statePhase = "ready";
    if (willActivate) {
      forceActivation = false;
      activation = await activateVersion(incoming, targetVersion);
    }
    settleAcceptedDrafts();
    runtime.agent = state.agent || "Claude";
    setClaimUpdateSources(state.claims || []);
    claimsHeld = presented(state).held;
    agentTurnClosed = state.turn_closed || null;
    claimingSession = state.claim_session || null;
    renderStatus(state);
    renderVersions(state);
    renderOthers(state);
    if (eventSeq > runtime.lastEventSeq || activation) {
      renderPanel();
      // Sign-off is a fact in the log, not a click this tab happens to remember, so a
      // reload (or the other tab) shows it too.
      paintApproval();
      const agentReplies = runtime.events.filter(
        (e) => e.author === "claude" && e.kind === "reply",
      );
      if (agentMsgCount >= 0 && agentReplies.length > agentMsgCount && !panelOpen)
        showToast(
          `${agentReplies.at(-1).agent || "Agent"} replied — open Comments`,
          () => setPanel(true),
        );
      agentMsgCount = agentReplies.length;
    }
    // Last, because the panel has just rendered the log: a widget carried by a reply is
    // on the page by now, so an action naming one that isn't names a widget no version
    // holds, and reconciliation can retire it instead of looking for it forever.
    reconcileState();
    // Outside the log-growth block: a work claim lands and ages without changing an
    // event this tab holds. After widget reconciliation because a module may rebuild
    // its authored subtree; the local line is the transient overlay that follows it.
    paintWorkLines();
    if (activation) {
      restoreView(activation.view);
      paintAnchors();
      updateFab();
      if (activation.comparedFrom !== null) showComparison(activation.comparedFrom);
      showToast(`Updated to v${runtime.currentVersion}`);
    }
    // Only a complete application advances the read boundary. A render fault may
    // already have changed some local surfaces, but it has not made a state safe to use
    // for replay or undo; leaving the sequence unresolved retries the whole read.
    runtime.lastEventSeq = Math.max(runtime.lastEventSeq, eventSeq);
    // Accounting changes no hold by itself. It first projects this complete log plus
    // every surviving optimistic action, then releases the entries whose attempts the
    // read contained. A same-widget event later in this state can therefore never be
    // skipped under the hold and exposed only after the hold disappears.
    accountOutbox(nextEvents);
    // Sequence consumers render after replay, so their history and the widget's
    // standing body describe the same poll. This also fires when the event list did
    // not grow: applyAction may have deferred while a user was typing, then become
    // applicable on the next poll after they close the editor.
    document.dispatchEvent(new Event("lf-actions"));
    notifyDataSubscribers();
  };
  try {
    if (willActivate) {
      const running = (async () => {
        if (document.startViewTransition) {
          document.documentElement.classList.add("lf-versioning");
          try {
            const transition = document.startViewTransition(apply);
            // A skipped transition — the document hidden at the call or
            // mid-flight, or a second transition starting — still runs the
            // update and settles `finished` with it, but rejects `ready`,
            // which nothing here awaits. Unhandled, that rejection reaches
            // the page's error report as a logged fault.
            transition.ready.catch(() => {});
            await transition.finished;
          } finally {
            document.documentElement.classList.remove("lf-versioning");
            // The transition's snapshots temporarily replace what is under a parked
            // pointer. Ask again once the live page owns those pixels, even when no
            // mousemove reports the change.
            refreshHover();
          }
        } else await apply();
      })();
      activatingState = running;
      try {
        await running;
      } finally {
        if (activatingState === running) activatingState = null;
      }
    } else await apply();
  } catch (error) {
    // Candidate history is useful only while this one synchronous application is
    // rendering it. If any required surface refuses the state, restore the last whole
    // reading so focus, panel, and undo cannot consume a log tail the page never
    // adopted. The next poll retries the candidate from the same complete boundary.
    runtime.events = priorEvents;
    runtime.statePhase = priorStatePhase;
    runtime.lastEventSeq = priorLastEventSeq;
    setClaimUpdateSources(priorClaimUpdateSources);
    claimsHeld = priorClaimsHeld;
    agentTurnClosed = priorAgentTurnClosed;
    claimingSession = priorClaimingSession;
    if (willActivate) location.reload();
    throw error;
  }
}
// ---------- restore ----------
// The general box and reply textareas repopulate as they render; a saved composer draft
// resurfaces visibly near the top so it isn't stranded in storage after a reload.
generalInput.value = loadDraft("general") ?? "";
// The widths first, so a panel or a tray put back open is open at the width the reader
// left it at rather than sliding to it afterwards.
commentsEdge.restore();
traysEdge.restore();
if (readerStore.get(PANEL_KEY) === "1") setPanel(true);
// Remembered tray intent is staged here, after every declaration exists. Its strip is
// part of the arrival geometry, but its state-dependent rows stay hidden until the first
// replay presents the page and restoreTray paints them. An already-presented document
// (an exported or pre-presented DOM) can restore immediately through the same function.
trayUp = readerStore.get(TRAY_KEY) || null;
if (trayUp) document.body.dataset.lfTray = trayUp;
if (pagePresented()) restoreTray();
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
export const ARRANGEMENTS = [
  { name: "the comment panel open", ...readerStore.where(PANEL_KEY), value: "1" },
  {
    name: "the comment panel at the width the reader drew it to",
    ...readerStore.where(commentsEdge.key),
    value: "560",
  },
  {
    name: "the tray panel at the width the reader drew it to",
    ...readerStore.where(traysEdge.key),
    value: "260",
  },
  ...[...trays.keys()].map((tray) => ({
    name: `the ${tray} tray standing`,
    ...readerStore.where(TRAY_KEY),
    value: tray,
  })),
  { name: "design mode on", ...tabStore.where(DESIGN_KEY), value: "1" },
];
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
// Where an arrival lands — version switch, reload, back, a URL naming an element (the
// panel and a remembered tray's strip are restored just above, so the column is already
// reflowed; the tray's pixels wait for replay). The browser answers
// this twice, and both answers are taken before the page is done becoming itself:
// upgrades change its height afterwards (tabs collapse, diagrams render, diff files
// fold), so a restored offset points into a document that no longer exists and a
// fragment jump lands at an element a tab has since closed over. Hence manual
// restoration, and hence the fragment travelling the same road — that was the half of
// this takeover left to the platform, which cannot see the page the upgrade makes.
//
// The ranking is the browser's own, restated once the geometry has settled. A fresh
// navigation is someone arriving at a named place, so the fragment outranks the saved
// position: that position is wherever this tab last left this page, and a URL naming an
// element is not a request to resume it. A reload or a back is someone returning, where
// the fragment is left over from a reference followed earlier and their own position is
// the answer. An id this version hasn't got falls through to that position, the same way
// a reference naming one paints detached rather than dead-ending.
history.scrollRestoration = "manual";
const ARRIVING = performance.getEntriesByType("navigation")[0]?.type === "navigate";
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
  if (!anchoringReady) return;
  tabStore.set(VIEW_KEY, JSON.stringify(captureView()));
});
function landArrival() {
  const aimed =
    ARRIVING && resolveAnchor({ section: fragmentId(location.hash) })?.element;
  if (aimed) scrollToElement(aimed, "instant");
  else if (savedView) restoreView(savedView);
}
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
  document.dispatchEvent(new Event("lf-actions"));
  paintApproval();
  promoteDeferredModals();
}

// Upgrades flush before the anchor pass and the view restore, so quotes and reading
// positions are re-found in the enhanced DOM, not the pre-upgrade one. An async function,
// never a top-level await: widget modules import widget-api.js, which temporarily
// reexports helpers from this entry, and awaiting their import at top level would
// deadlock the cycle (their evaluation waits on this module's async evaluation
// completing).
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
  if (savedView && savedView.v < runtime.currentVersion)
    showToast(`Updated to v${runtime.currentVersion}`);
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
  // presentation boundary; only after it settles does the ordinary polling cadence begin,
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
  const pollAndPresent = async () => {
    try {
      await poll();
      if (!document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented))
        await ensurePresentation();
    } catch (error) {
      reportPageError(`poll failed: ${error?.message ?? error}`);
      renderStatus(error);
    }
  };
  pollAndPresent().finally(() => setInterval(pollAndPresent, POLL_MS));
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
