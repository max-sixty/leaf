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
  bindings,
  checked,
  labelOf,
  live,
  parsed,
  spell,
  walkRows,
  word,
} from "./runtime/keyboard/bindings.js";
import { createAskModel } from "./runtime/asks/model.js";
import { createAskView } from "./runtime/asks/view.js";
import { createAddress } from "./runtime/keyboard/address.js";
import { createDispatch } from "./runtime/keyboard/dispatch.js";
import { createKeyline } from "./runtime/keyboard/keyline.js";
import { createReference } from "./runtime/keyboard/reference.js";
import { createScopes } from "./runtime/keyboard/scopes.js";
import { createNavigation } from "./runtime/navigation.js";
import { FOLD_MS, REDUCED, SCROLL, motion } from "./runtime/motion.js";
import { createOutbox, outbox } from "./runtime/outbox.js";
import { createDataProjection } from "./runtime/projection/data.js";
import { createProjection } from "./runtime/projection.js";
import { createAnchors } from "./runtime/anchors.js";
import { createBanner } from "./runtime/banner.js";
import { createConversation } from "./runtime/conversation/reconcile.js";
import { createPassages } from "./runtime/passages.js";
import { createPresence } from "./runtime/presence.js";
import { createUpdates } from "./runtime/updates.js";
import {
  captureVersionRoots,
  createVersionActivation,
} from "./runtime/version-activation.js";
import { createVersionDiff } from "./runtime/version-diff.js";
import { createVersionNavigation } from "./runtime/version-navigation.js";
import { failSoft, settle, settling } from "./runtime/widget-upgrade.js";
import {
  createMeasurements,
  installReachedForWordsGuard,
  offer,
  quoted,
  reachedForWords,
  relabel,
  reserve,
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
  loadShadowRules,
  pageShadowRoots,
} from "./runtime/shadow.js";
import { VERSION_PATH, readerStore, tabStore } from "./runtime/storage.js";
import { highlightBlocks } from "./runtime/syntax.js";

export { PRESS, labelOf };

// ---------- widget layer ----------

async function undoLast(...args) {
  return runtimeProjection.undoLast(...args);
}

// Capture the authored share before the runtime paints roots or appends head chrome.
const versionRoots = captureVersionRoots();

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
    ...(runtime.currentRevision != null && { revision: runtime.currentRevision }),
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

createMeasurements({ shownBox });

installReachedForWordsGuard();

createDataProjection({
  paintAnchors,
  setChildren,
});

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
          revision: runtime.currentRevision,
          anchor: { section: el.id },
          text,
          attempt,
          ...(declaration.response && { response: declaration.response }),
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

const {
  bySentence,
  claimsEsc,
  elementScopes,
  focused,
  keys,
  merge,
  pruneScopedElements,
  saying,
  scopeRefs,
  scopesFor,
} = createScopes({
  paintHere,
  upFrom: (node) => upFrom(node),
});
export { keys, saying };
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
    !registry.$tones?.names ||
    !registry.$reactions?.tokens
  )
    throw new Error("leaf: registry lacks $events, $languages, $tones or $reactions");
  revealLayer();
  buildReactBar();
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
// alone deciding — which is the same answer a page with no runtime already gets. Read
// from body at the moment of the question rather than caching root's default: a composed
// margin posture may override the floor under the media query that grants it, and an
// arriving panel must ask that composed value without the runtime learning which idioms
// contributed it.
const stripMin = () =>
  parseFloat(getComputedStyle(document.body).getPropertyValue("--strip-min"));

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
// the letter again takes the current page. The chip names that motion, spelled from the
// two rows that make it rather than typed out beside them.
latestChip.title = "Open the current page";
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
  return { tone: toneFor(kind), line };
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
const {
  NEWEST,
  VERSIONS,
  activationIsForced,
  clearForcedActivation,
  goActive,
  renderVersions,
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
  poll,
  pressComparison: (...args) => pressComparison(...args),
  setDiff: (...args) => setDiff(...args),
  showComparison: (...args) => showComparison(...args),
  showNews,
});
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
  signoffDeclared = next;
  const shown = signoffDeclared && runtime.currentStamp !== null;
  if (shown === signoff) return;
  signoff = shown;
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
  fabBar,
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
const draftVersionLabel = "Draft after v999 ▾";
reserve(versionBtn, [
  versionLabel(false),
  versionLabel(true),
  draftVersionLabel,
  `Δ ${draftVersionLabel}`,
]);
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
const updateSequence = (target = null) => updateRuntime.updateSequence(target);
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
// Whether the reader is standing in the panel rather than merely looking at it — focus,
// not visibility, the same line PANEL draws for its own scope and the one every surface
// here reads. A press that acts on where the reader is standing has to ask it of the
// focus: beside the page the panel is a column of its own, and a reader working down the
// list is in it whatever the window is wide enough to show behind them.
const inPanel = () => panelOpen && containsAcross(panel, focused());
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
// the strip the panel takes is a rule in the stylesheet above.
//
// So it is called and not observed, and it is only as fresh as its callers — which is
// enough, because each fact it turns on either arrives on an occasion of its own or does
// not move at all. The window states the cap on a resize, and the panel its strip on the
// gesture that moves it. The scroller's gutter is the one with no occasion to arrive on:
// body gains or loses its bar as the document's height crosses the viewport, and replay
// retiring a slot, a widget settling late, or an image arriving can each do that with no
// resize and no chrome gesture behind it. What answers that is the stylesheet rather than
// a call from every such path — body is given scrollbar-gutter: stable in the same rule
// that makes it the scroller (chrome-style.js), so the room is reserved whether or not a
// bar is drawn in it and the difference between the two boxes holds still for the page's
// life. Joining layoutSizes would be the fix if it did not, and it is the one the rule
// above forbids: the strip this vetoes is padding on the observed box, and stateRoom can
// be observed only because it writes nothing that box is measured from.
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
// way the wide rules already spend --lf-room. A query cannot see the panel or the
// scroller's own bar and this can, which is the whole of what the runtime adds; a page with
// no runtime behind it falls back to the viewport in each rule that reads it.
function stateStrip() {
  // The scroller's gutter, which stateRoom takes off for the same reason and by the same
  // reading: body is the document's scroller, so a classic bar comes out of the room this
  // page has while the window says nothing about it. The coarse answer owes it as much as
  // the fine one. Without it the floor was met by a window with a bar's width less page
  // behind it, and the strip came out of the column the floor exists to keep it out of —
  // a sidenote page at exactly 1152px read at a 705px measure, and a sidebar and a note at
  // 1416px did the same.
  const avail =
    document.documentElement.clientWidth -
    scrollerGutter() -
    panelStrip() -
    trayStrip();
  document.body.toggleAttribute("data-lf-cramped", avail < stripMin());
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
  anchorRuntime?.dockSeats();
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
  // and the box in front of us has already given up. One reading (scrolling.js), because
  // the veto above owes the same number and a second spelling of it here would be true by
  // inspection rather than by construction.
  const room =
    Math.min(
      document.body.clientWidth,
      document.documentElement.clientWidth -
        panelStrip() -
        trayStrip() -
        scrollerGutter(),
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
  const anchor = fabAnchorAt();
  if (anchor?.quote && pageSelection()) updateFab();
  else if (anchor) {
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

const { landTyping, pageSelection, selectionAnchor, snapSelection } =
  createSelectionCapture({
    anchoringIsReady: () => anchoringReady,
    blockOf: (...args) => blockOf(...args),
    closestAcross: (...args) => closestAcross(...args),
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
  beside,
  fabAnchorAt,
  openOnItem,
  openOnVisual,
  placeClear,
  raiseOnItem,
  placeComposer,
  showFab,
  standDown,
  updateFab,
  visualAt,
} = createSelectionSurface({
  anchoringIsReady: () => anchoringReady,
  composer,
  composerInput,
  composerIsOpen: () => composerOpen,
  designIsOn: () => designOn,
  designTarget,
  fab,
  fabBar,
  fabSep,
  hideComposer: () => hideComposer(),
  hideReference: () => reference.show(false),
  inChrome: (node) => inChrome(node),
  markAt,
  noteClass: () => NOTE,
  openComposer,
  openOnDesign,
  pageRange: (...args) => pageRange(...args),
  pageScroller,
  pageSelection,
  pageWords: (...args) => pageWords(...args),
  paintHere,
  paintStanding: (...args) => conversationRuntime.paintStanding(...args),
  panel,
  panelCovers,
  pendingMarks: () => anchorRuntime.pendingMarks,
  pointerAt: () => pointer,
  reactionTokens: () => reactionTokens(),
  reactionsOn: (anchor) => conversationRuntime.reactionsOn(anchor),
  referenceIsOpen: () => reference.open,
  selectionAnchor,
  setReact: (on) => setReact(on),
  showThread,
  showVersionMenu,
  snapSelection,
  tagsDeclaring,
  takesLetters: (node) => takesLetters(node),
  versionMenuIsOpen,
  visualPartAt: (...args) => visualPartAt(...args),
});

const { AIM, aimIsOn, aimedItem } = createAim({
  designPress,
  designTarget,
  inChrome: (node) => inChrome(node),
  itemAt,
  openOnDesign,
  openOnVisual,
  pointerAt: () => pointer,
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
  when: () => !fabAnchorAt() && !standingConversation(),
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
  const approved = runtime.events.some(
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
  approveBtn.textContent = approved ? "✓ Approved" : "✓ Looks good";
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
// The unanswered ask where the reader is standing on a control that works it, and the innermost
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
const conversationInputOf = (held) => {
  const box = held?.querySelector(SAY_BOX);
  return box && shownBox(box).height ? box : null;
};
// The current box belonging to the nearest conversation around a widget. A behavior
// module may supply words the conversation itself owns without knowing whether that
// conversation is seated on the page or in the panel, or how its shadow boundary is
// staged. `conversationBox` answers the inverse question when the widget owns the seat.
export function conversationInput(node) {
  const held = node && closestAcross(node, SAYS_IN);
  return conversationInputOf(held);
}
// A keyboard press that steps from a control into a conversation box owes the reader
// the same control on the way out. Focusable conversations already own that rung — a
// thread's Escape returns to the thread — while a page-owned first-message seat has no
// standing place of its own. Remember the control only for that focus visit, so reaching
// the same box later by Tab does not inherit an old route.
const conversationReturns = new WeakMap();
const standingConversation = () => {
  const held = heldConversation();
  const box = conversationInputOf(held);
  return box ? { held, box } : null;
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
export function landInConversation(box, route = null) {
  if (
    route &&
    (!(route.target instanceof Element) ||
      typeof route.line !== "string" ||
      !route.line.trim())
  )
    throw new TypeError(
      "landInConversation return route needs an element target and a non-empty line",
    );
  const held = box && closestAcross(box, SAYS_IN);
  if (!held) return false;
  if (route && !held.hasAttribute("tabindex")) {
    conversationReturns.set(box, route);
    box.addEventListener("blur", () => conversationReturns.delete(box), { once: true });
  }
  landIn({ held, box });
  return true;
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

const {
  answeredContext,
  askEntry,
  askSource,
  isAwaiting,
  openAsks,
  projectedParent,
  unansweredAsks,
} = createAskModel({
  authoredParentOf: (node) => authoredParents.get(node),
  awaitsAgent,
  buildThreads,
  closestAcross: (...args) => closestAcross(...args),
  elementById: (...args) => elementById(...args),
  inChrome: (node) => inChrome(node),
  matchesProjectedWhen: (...args) => matchesProjectedWhen(...args),
  matchesWhen,
  pagePresented,
  projectedFacet: (...args) => projectedFacet(...args),
  quoted,
  registry,
  runtime,
  seatRoot,
  settledAway: (...args) => settledAway(...args),
  stateCoordinate: (...args) => stateCoordinate(...args),
  stateProjection: (...args) => stateProjection(...args),
  tagsDeclaring,
});
export { answeredContext, askSource, openAsks };

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
  standingAnswers,
  standingIn,
  stepAsk,
  syncAsks,
} = createAskView({
  PAGE_PAINT_ATTRIBUTE,
  SCROLL,
  announce,
  askEntry,
  askSource,
  asksBtn,
  asksList,
  asksOffered,
  asksPanel,
  banner,
  blocksOnScreen,
  el,
  elementById: (...args) => elementById(...args),
  inChrome: (node) => inChrome(node),
  itemSays,
  itemWord,
  openAsks,
  openTray,
  paintAnchors,
  paintHere,
  panelIsOpen: () => panelOpen,
  registry,
  reserve,
  reveal,
  scrollToElement,
  setPanel,
  showNews,
  shownParts,
  tagsDeclaring,
  unansweredAsks,
  versionBtn,
});

const { commentOnItem, glideTo, scrollerFor, seenScroller, stepPage, stepThread } =
  createNavigation({
    BANNER_CLEAR,
    REDUCED,
    SCROLL,
    beside,
    inChrome: (node) => inChrome(node),
    inPanel,
    openOnItem,
    openThreads,
    pageScroller,
    panelCovers,
    panelIsOpen: () => panelOpen,
    scrollToElement,
    scrollToThread,
    setPanel,
    shownBox,
    shownRect,
    threadsBox,
  });
export { scrollerFor };

const {
  COMMENTS,
  GO,
  GOTO,
  addressLabel,
  addressed,
  isChordArmed,
  keepShown,
  paintAddresses,
  setChord,
} = createAddress({
  EVERYTHING,
  SAY_BOX,
  addressLayer,
  announce,
  banner,
  claimsEsc,
  el,
  focused,
  glideTo,
  goToAsk,
  keylineEl,
  landIn,
  openAsks,
  openThreads,
  pageParts,
  paintHere,
  panelIsOpen: () => panelOpen,
  saying,
  seenScroller,
  setPanel,
  startsAt,
  scrollToElement,
});

// ---------- reactions ----------
// The layer's reaction vocabulary, in declared order. The bar, a thread's strip, the
// page row and the armed digits all read this one list, so a layer that renames, adds
// or removes a token moves every surface at once, and core never learns a token's name:
// what a press means is the entry's `means`, printed to the agent by `leaf wait`, and
// what it does structurally is the entry's own flag (`settles`, read by the panel).
// Empty until the registry has arrived: the register checks every core row's bindings
// as the module evaluates, which is before the vocabulary is known.
const reactionTokens = () => Object.entries(registry.$reactions?.tokens ?? {});
// One token as a press, built the same way wherever it stands — the bar beside a
// selection, the strip under a message, the panel's page row. The digit is the address
// the armed mode paints (the chip an option wears while its mark holds focus) and shows
// only while armed; the word shows only while the token stands on its target, so a strip
// reads "✓ ok" where the reader pressed and a bare glyph everywhere else. The chip is
// aria-hidden the way the key line's are: the announcement made on arming says the keys.
function reactPill(name, entry, ordinal, pressed) {
  const pill = offer("button", "lf-pill lf-react");
  pill.dataset.token = name;
  pill.title = `${name} — ${entry.means}`;
  pill.setAttribute("aria-label", name);
  const digit = el("span", "lf-address", String(ordinal));
  digit.setAttribute("aria-hidden", "true");
  pill.append(
    digit,
    el("span", "lf-react-glyph", entry.glyph),
    el("span", "lf-react-word", name),
  );
  pill.onclick = () => pressed(name, pill);
  return pill;
}
const reactPills = (pressed) =>
  reactionTokens().map(([name, entry], i) => reactPill(name, entry, i + 1, pressed));
function buildReactBar() {
  for (const pill of reactPills(reactHere)) fabBar.insertBefore(pill, fab);
}
// What the bar's target is called, for the line, the reference and the announcement:
// the selection, a declared visual part by its own label, or the item by its own word.
const anchorWord = (anchor) => {
  if (anchor.quote) return "the selection";
  const item = elementById(anchor.section);
  if (anchor.visual) return visualPartLabel(item, anchor.visual) ?? anchor.visual;
  return itemWord(item) || "the item";
};
// A reaction aimed where the bar is: a comment carrying a token in place of words, on
// the same anchor a comment from here would carry — the passage a selection named or
// the item the bar was raised on — so the file meets it the way it meets a comment.
// Design mode makes it about the layer, as it does a comment. Sent, the bar and the
// selection stand down: the mark on the passage is the receipt, and a selection left
// standing would cover it.
async function reactHere(name, pill) {
  const anchor = fabAnchorAt();
  if (!anchor) return;
  if (pill.lfReaction) {
    await withdraw(pill.lfReaction);
    showFab(null);
    setReact(false);
    return;
  }
  const event = {
    kind: "comment",
    revision: runtime.currentRevision,
    token: name,
    anchor: structuredClone(anchor),
  };
  if (designOn) event.about = "layer";
  const sent = await sendReaction(event, pill, anchorWord(anchor));
  if (!sent) return;
  showFab(null);
  setReact(false);
  getSelection()?.removeAllRanges();
}
// One send for every reaction surface. A press whose result has not changed the DOM
// waits for the log — the outbox's rule — so the pill says busy for the round trip and
// the paint arrives with the accepted state. Announced, because the paint is silent.
async function sendReaction(event, pill, where) {
  pill.setAttribute("aria-busy", "true");
  try {
    const sent = await post(event);
    if (sent) announce(`${event.token} on ${where}`);
    return sent;
  } finally {
    pill.removeAttribute("aria-busy");
  }
}

// The armed react press: `r` puts a digit on every token of one surface, and the digit
// sends. Digits rather than letters because the vocabulary is configuration — a letter
// spelled from a token's word breaks the day a layer replaces it, where position
// survives any set. The surface is whichever strip of pills the reader's place names:
// the strip under the latest agent message where they are standing in a thread; the bar,
// where one stands or can be raised on the item they are standing on; and the panel's
// page strip where nothing stands, the page whole being what an anchorless reaction is
// aimed at. Armed, the mode owns the keys (REACT claims everything, as the address chord
// does); Escape or a stray key lets it go, and what the arming raised — the bar, or the
// panel — goes down with it, unless a digit spent it, which is the reader landing in
// what the arming showed (the chord's `keepShown`).
let reactArmed = false;
let reactRaised = false;
let reactRevealed = null;
let reactSurface = null;
// The strip the panel has open — the latest agent message's — asked of the class the
// list paints it with rather than of DOM order, so arming and offering cannot disagree
// about which message is the latest one.
const latestAgentStrip = (held) => held.querySelector(".lf-react-strip.lf-open");
function setReact(on, { spent = false } = {}) {
  if (on === reactArmed) return;
  // Armed over a control that has claimed Escape, one press would have two owners, so
  // the mode refuses to arm there — the chord's own rule.
  if (on && claimsEsc(focused())) return;
  reactSurface?.classList.remove("lf-armed");
  if (on) {
    const said = standingConversation();
    const strip = said && latestAgentStrip(said.held);
    const here = !strip && !fabAnchorAt() && standingItem();
    if (strip) reactSurface = strip;
    else if (fabAnchorAt() || here) {
      if (here) {
        showFab(
          { section: here.id },
          ...beside(shownRect(here, new Map()) ?? shownBox(here)),
        );
        reactRaised = true;
      }
      reactSurface = fabBar;
    } else {
      reactSurface = conversationRuntime.pageStrip;
      if (!reactSurface) return;
      reactRevealed = COMMENTS.reveal();
    }
    reactArmed = true;
    reactSurface.classList.add("lf-armed");
    announce(`React — ${saying(REACT.rows)}`);
  } else {
    reactArmed = false;
    reactSurface = null;
    if (reactRaised) showFab(null);
    if (!spent) reactRevealed?.();
    reactRaised = false;
    reactRevealed = null;
  }
  paintHere();
}
const reactTargetWord = () =>
  reactSurface === fabBar
    ? anchorWord(fabAnchorAt())
    : reactSurface === conversationRuntime.pageStrip
      ? "the page"
      : "the reply";
// The armed react press's own scope: the digits, and the way out. It claims everything
// for the reason the chord does — a digit pressed while it stands belongs to it wherever
// focus sits — and, as with the chord, any key it does not bind disarms it and keeps its
// ordinary meaning (the dispatcher).
const REACT = {
  title: "With r armed",
  at: () => reactArmed,
  claims: EVERYTHING,
  rows: [
    {
      keys: () =>
        reactionTokens()
          .slice(0, 9)
          .map((_, i) => String(i + 1)),
      label: () => {
        const n = Math.min(reactionTokens().length, 9);
        return n > 1 ? `1–${n}` : "1";
      },
      does: () =>
        `Put a reaction on ${reactTargetWord()}: ${reactionTokens()
          .slice(0, 9)
          .map(([name, entry], i) => `${i + 1} ${entry.glyph} ${name}`)
          .join(", ")}`,
      line: "react",
      run: (binding) => {
        // The surface's own pill, pressed: keyboard and pointer are one behaviour,
        // the busy paint and the announcement included.
        reactSurface?.querySelectorAll(".lf-react")[+binding - 1]?.click();
        setReact(false, { spent: true });
      },
    },
    {
      keys: ["Escape"],
      does: "Put the reaction down",
      line: "cancel",
      run: () => setReact(false),
    },
  ],
};
const HELP = {
  title: "In this reference",
  at: () => reference.open,
  claims: EVERYTHING,
  rows: [
    {
      keys: ["Escape"],
      does: "Close this reference",
      line: "close help",
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
  const route = conversationReturns.get(focused());
  return route?.target?.isConnected ? route : null;
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
  at: inPanel,
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
// takes the letter again for the current page — one motion whose second half is a key of
// the scope the first half stood up, so it costs the table no row and holds whether or not
// this page is behind. Named, because the chip that jumps straight to the current page
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
  run: () => reference.show(true),
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
      // `r` from the bar's own word (its name is "React or comment"). What it arms is
      // the bar the pointer sees, digits on: the same tokens in the same order, so a
      // reader who has seen the bar once knows the keys. Nine at most, the digits being
      // the addresses.
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
  REACT,
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

const { readerIn, shadow, stack } = createDispatch({
  claimsEsc,
  containsAcross: (container, node) => containsAcross(container, node),
  ELEMENTS,
  focused,
  isChordArmed,
  isReactArmed: () => reactArmed,
  keepShown,
  paintHere,
  panel,
  SCOPES,
  scopesFor,
  setChord,
  setReact,
  takesLetters,
});
const reference = createReference({
  bySentence,
  el,
  elementScopes,
  ELEMENTS,
  EVERYTHING,
  focused,
  helpEl,
  merge,
  pageSelection,
  paintHere,
  pruneScopedElements,
  reachScrollers,
  readerIn,
  scopeRefs,
  SCOPES,
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
  paintDiff,
  pressComparison,
  setDiff,
  showComparison,
} = createVersionDiff({
  chooserLabel: () => labelOf(CHOOSER),
  domFacet: (...args) => domFacet(...args),
  elementById: (...args) => elementById(...args),
  foldedFacet: (...args) => foldedFacet(...args),
  inChrome: (...args) => inChrome(...args),
  quoted,
  showToast,
  stateCoordinate: (...args) => stateCoordinate(...args),
  stateProjection: (...args) => stateProjection(...args),
  stateSpecs: (...args) => stateSpecs(...args),
  textBlockSelector: () => TEXT_BLOCK,
  versionBtn,
  versionLabel,
  versionMenu,
  wrote: (...args) => wrote(...args),
});
const { droppedAt, presented, quietSince } = createPresence({ serverNow });
export { quietSince };

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
  Boolean(fabAnchorAt()) ||
  unaccountedGesture() ||
  (document.activeElement?.tagName === "TEXTAREA" &&
    (document.activeElement.value !== "" ||
      document.activeElement.hasAttribute("data-lf-offer")));
// Through the chooser's one door, so the chip opens exactly the version it names. At the
// live root that is an explicit in-place release of the composition hold; on an immutable
// page it is ordinary version travel.
latestChip.onclick = () => goActive();

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
// The z row's sentence for a reaction: the token and where it stands, so the line is
// the receipt after the press and the promise before the next.
function reactionPlace(e) {
  if (e.kind === "reply") return "the reply";
  if (!e.anchor) return "the page";
  const label = anchorLabel(e.anchor, e.about);
  return [...label].length > CONTROL_WORD_CAP
    ? cut(label, 0, CONTROL_WORD_CAP) + "…"
    : label;
}
const undoSentence = () => {
  const e = undoable();
  return e?.token
    ? `Take back: ${e.token} on ${reactionPlace(e)}`
    : "Take back the last change you made here";
};
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
function visualPartAt(...args) {
  return anchorRuntime.visualPartAt(...args);
}
function visualPartLabel(...args) {
  return anchorRuntime.visualPartLabel(...args);
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
  quoted,
  renderRetired,
  says,
  textNodesUnder,
  uiInside,
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
  // Whether a reaction still paints, off the conversation's last fold — built after this
  // module, so asked lazily.
  reactionStanding: (e) => conversationRuntime.reactionStanding(e),
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
  resetAuthoredPage,
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
  withdraw,
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
  announce,
  designIsOn: () => designOn,
  captureAuthoredFacets,
  claimState: () => ({ agentTurnClosed, claimingSession, claimsHeld }),
  designName,
  droppedAt,
  el,
  elementById,
  findInput,
  focused,
  generalRow,
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
  reactDone: () => setReact(false, { spent: true }),
  reactPills,
  sendReaction,
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
  visualPartLabel,
  wireInput,
  withdraw,
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
  SCROLL,
  TEXT_BLOCK,
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
  landedAt,
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
  setLanded,
  setPanel,
  settledAway,
  tagsDeclaring,
  textNodesUnder,
  threadsBox,
  uiInside,
  under,
  withdraw,
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
    const activation = currentActivation();
    if (activation) await activation;
    notifyChangedData();
    return;
  }
  // Polls and POST answers may overlap. A document activation is the one state read
  // that cannot safely interleave: a second one would capture or replace the halfway
  // upgraded main. Let it commit, then judge this response against its resulting
  // version and sequence.
  let activationInFlight = currentActivation();
  if (activationInFlight) await activationInFlight;
  if (eventSeq < runtime.lastEventSeq) {
    notifyChangedData();
    return;
  }
  const targetRevision = state.active?.revision ?? null;
  if (!Number.isInteger(targetRevision) || targetRevision < 1)
    throw new TypeError("state active must name a positive revision");
  if (LIVE_ROOT && runtime.currentRevision === null)
    throw new TypeError("the live document has no lf-revision marker");
  if (runtime.active && targetRevision < runtime.active.revision) {
    notifyChangedData();
    return;
  }
  const wantsActivation =
    LIVE_ROOT &&
    runtime.currentRevision !== null &&
    targetRevision > runtime.currentRevision;
  let incoming = null;
  let incomingFailed = false;
  if (wantsActivation) {
    latestChip.textContent = `New page available → open ${state.active.label}`;
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
      revisionDocument(state.active)
        .then((doc) => (incoming = doc))
        .catch((error) => {
          incomingFailed = true;
          reportPageError(
            `revision ${targetRevision} failed to load: ${error?.message ?? error}`,
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
  activationInFlight = currentActivation();
  if (activationInFlight) await activationInFlight;
  if (eventSeq < runtime.lastEventSeq) {
    notifyChangedData();
    return;
  }
  if (runtime.active && targetRevision < runtime.active.revision) {
    notifyChangedData();
    return;
  }
  const willActivate =
    Boolean(incoming) &&
    targetRevision > runtime.currentRevision &&
    (!midComposition() || activationIsForced()) &&
    !versionMenuIsOpen() &&
    targetRevision === state.active.revision;
  const priorEvents = runtime.events;
  const priorStatePhase = runtime.statePhase;
  const priorLastEventSeq = runtime.lastEventSeq;
  const priorActive = runtime.active;
  const priorVersions = runtime.versions;
  const priorCurrentLabel = runtime.currentLabel;
  const priorCurrentRevision = runtime.currentRevision;
  const priorCurrentStamp = runtime.currentStamp;
  const priorClaimUpdateSources = claimUpdateSources();
  const priorClaimsHeld = claimsHeld;
  const priorAgentTurnClosed = agentTurnClosed;
  const priorClaimingSession = claimingSession;
  const apply = async () => {
    runtime.events = nextEvents;
    let activation = null;
    runtime.statePhase = "ready";
    if (willActivate) {
      clearForcedActivation();
      activation = await activateRevision(incoming, state.active);
    }
    settleAcceptedDrafts();
    runtime.agent = state.agent || "Claude";
    setClaimUpdateSources(state.claims || []);
    claimsHeld = presented(state).held;
    agentTurnClosed = state.turn_closed || null;
    claimingSession = state.claim_session || null;
    renderStatus(state);
    renderVersions(state);
    stateSignoff(signoffDeclared);
    paintApproval();
    renderOthers(state);
    if (eventSeq > runtime.lastEventSeq || activation) {
      renderPanel();
      // Sign-off is a fact in the log, not a click this tab happens to remember, so a
      // reload (or the other tab) shows it too.
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
      showToast(`Updated to ${runtime.currentLabel}`);
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
            // pointer move reports the change.
            refreshHover();
          }
        } else await apply();
      })();
      const clearActivation = trackActivation(running);
      try {
        await running;
      } finally {
        clearActivation();
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
    runtime.active = priorActive;
    runtime.versions = priorVersions;
    runtime.currentLabel = priorCurrentLabel;
    runtime.currentRevision = priorCurrentRevision;
    runtime.currentStamp = priorCurrentStamp;
    stateSignoff(signoffDeclared);
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
