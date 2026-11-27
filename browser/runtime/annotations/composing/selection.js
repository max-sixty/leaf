/* The selection composer: the response bar's field bound to a passage's draft.

   The selection composer keeps its passage painted after an explicit Comment gesture
   moves focus into the field. Automatic passage selection leaves the native
   selection in place. Its `.lf-composer` wrapper contributes state and draft machinery
   and draws nothing: seated in a widget it is `display: contents`, and floating it is
   the box holding what moves as the field changes size (annotation-chrome.css), and
   only the field's frame draws. `showComposer` states
   whether it is open through `data-lf-open`; the shared response stylesheet derives
   its field and bar's visible shape from that and the surface's target-only state.
   Reopening the same passage resumes its words, seed, and modes; omitted modes
   initialize only a new passage, while explicit options restore a stored record.
   `openComposer`'s `focus` option decides focus independently. Outside clicks and
   Escape hide without discarding words. A successful send settles only the submitted draft generation.

   A hidden draft is news and a place: hiding one that still holds words, or moving the
   box off it to another passage or a thread, says so once, and Resume writing or its
   row under Threads' Drafts brings its editor back. A refused send reopens its box with the
   words while the user has done nothing since Send. Startup reopens a stored composer
   record through `openDraft`. Every path that discards words empties
   the box first, so those hide silently.

   The response surface (annotations/composing/surface.js) constructs the command owner with its bar's
   commands and boot's travel, delivery, and repaint capabilities. Importing this module exposes only passive nodes and live draft
   readings. mount binds the field and its controls after those owners exist. */
import { responseAction } from "../../dom/widget-elements.js";
import { el } from "../../lib/elements.js";
import { offerAction } from "../../lib/controls.js";
import { COMMENT_HINT } from "../../base/voice.js";
import { keeps, keepsHidden } from "../../lib/keeps.js";

import {
  clearDraft,
  commentContext,
  composerCtx,
  composerPayload,
  draftContexts,
  isComposerDraft,
  loadDraft,
  noticeDraftKept,
  saveDraft,
  sendMessage,
  watchDraft,
  watchDrafts,
  rememberWriting,
  registerWritingDestination,
} from "../../records/drafts.js";

import { pageSelection } from "./capture.js";
import { anchorForRange } from "../../readings/anchor-resolution.js";
import { THREAD } from "../../records/thread/selectors.js";
import { keys, paintKeys } from "../../dom/keyboard/scopes.js";
import { showNativeLayer, closeNativeLayer } from "../../dom/keyboard/layer-stack.js";
import { pageScope } from "../../dom/keyboard/register.js";
import {
  cycledRow,
  hasRows,
  savedReadingSettled,
} from "../../dom/keyboard/bindings.js";
import {
  onCurrentLocation,
  takesLetters,
  focusDestination,
  focused,
  closeLayer,
} from "../../dom/focus.js";
import { repaint } from "../../dom/repaint.js";
import { restrictUserIntent, retainUserIntent } from "../../dom/user-intent.js";
import { applicationState } from "../../state/semantic-state.js";
import { bindQueuedWork } from "../../lib/queued-work.js";

import { elementById } from "../../readings/passages.js";

import { notice } from "../../transport/notifications.js";
import { sentDrawing } from "./drawing-record.js";
import { commitPoint } from "../../readings/pointed-place.js";
import { textField } from "./text-field.js";
import { raiseError } from "../../transport/errors.js";
import { isNativeLayer, closestAcross } from "../../lib/shadow-tree.js";
import { inChrome } from "../../base/ui-marks.js";
import { PRESS, rowArrows } from "../../lib/keys.js";

// The comment field keeps Send or Dictate as its primary action. Other responses
// open in one anchored picker from a ⋯ in the field's corner, Tab, or e. The same
// picker follows the composer between the floating panel, a passage, and a widget
// outlet; opening it never changes the field's size or position.
//
// The ⋯ stands beside Dictate only while the field is empty, and the draft's first
// word takes its place, so the field spans the bar in every state and nothing moves
// as the user starts typing (response.css). Max chose this over a
// bordered button beside the field, which keeps part of the bar from the words
// and ends a sent card's message short of its Reply field, over hiding that button
// at the first key, which widens the field under the caret, and over no button at
// all, which leaves a mouse or finger no way to Suggest or a reaction. Rejected too: a
// ⋯ over the field's end, in the head row the floating frame reserves, which
// only the floating presentation has.
export const fabBar = el("div", "lf-ui lf-fab-bar lf-target-paint");
fabBar.dataset.lfRuntime = ""; // Leaf's own when seated in a widget (readings/passages.js, leafSurface)
fabBar.setAttribute("role", "group");
fabBar.setAttribute("aria-label", "Respond");
// A public part a theme restyles (`layer.chrome_restyle`), its ground inside it.
fabBar.setAttribute("part", "composer");
export const fabInput = textField();
fabInput.className = "lf-ui lf-response-control lf-fab-input";
fabInput.name = "comment";
fabInput.placeholder = COMMENT_HINT;
fabInput.setAttribute("data-lf-voice", "leaf");
fabInput.setAttribute("aria-label", "Comment");
const fab = responseAction(offerAction("response", "lf-fab"), {
  action: "comment",
  label: "Comment",
  behavior: "disclosure",
});
fab.id = "lf-comment-button";
// The field's face while the box rests (annotations/composing/surface.js, `restFab`). `c` is its
// keyboard route, and the box goes with the focus Tab would take to it, so Tab skips it.
export const fabRest = offerAction("response", "lf-fab-rest");
fabRest.tabIndex = -1;
export const fabOptions = el("span", "lf-response-options");
fabOptions.id = "lf-response-options";
fabOptions.popover = "auto";
fabOptions.setAttribute("role", "group");
fabOptions.setAttribute("aria-label", "Other responses");
const fabSuggest = responseAction(offerAction("response", "lf-fab-suggest"), {
  action: "suggest",
  label: "Suggest",
  collapse: true,
});
fabOptions.append(fabSuggest);
// It joins the field `wireInput` builds around the editor when the composer mounts.
export const fabOptionsTrigger = offerAction(
  "symbol",
  "lf-response-trigger",
  "Other responses",
  { action: "more" },
);
fabOptionsTrigger.setAttribute("data-lf-disc", "");
fabOptionsTrigger.setAttribute("aria-controls", fabOptions.id);
// The layer stack keeps it as the options open and close (dom/keyboard/layer-stack.js).
fabOptionsTrigger.setAttribute("aria-expanded", "false");
fabOptionsTrigger.popoverTargetElement = fabOptions;
fabBar.append(fab, fabRest, fabOptions);

const composer = el("div", "lf-ui lf-composer");
composer.id = "lf-composer";
// Never shown: anchor paint, its one writer, fills it with the words the field's
// description reads (below). lf-ui on the element itself, not just on the composer
// around it: this is the only injected chrome carrying an id, and "which section is this
// in" is asked as `[id]:not(.lf-ui)` of the element rather than of its ancestors, so
// without the class it answers that question with itself.
export const composerQuote = el("blockquote", "lf-ui");
composerQuote.id = "lf-composer-quote";
composerQuote.hidden = true;
// The page-anchored composer is the extended Comment control itself. The hidden
// composer node keeps the draft's controls and quote description, while this field
// stays in the response bar and never jumps to a second box.
const composerInput = fabInput;
// The mark is a paint, and a paint is nothing to a screen reader. So what the box is anchored to travels as the box's own description,
// announced on focus — which is more than the visible quote ever said, since nothing
// pointed a user at it.
composerInput.setAttribute("aria-describedby", composerQuote.id);
// The field, and the shelf and controls `wireInput` gathers around it, wait outside the
// page until the composer first opens (`showComposer`), since a connected field builds
// its editor: a page whose composer never opens builds none. Everything that reads the
// field before then reads its words and draft, which it holds unconnected.
const composerField = document.createDocumentFragment();
composerField.append(composerInput);
composer.append(composerQuote);
fabBar.prepend(composer);

/** @typedef {NonNullable<import("../../../types/contract.js").EventMap["comment"]["anchor"]>} Anchor
 * @typedef {import("../../records/drafts.js").ComposerDraft} ComposerDraft
 * @typedef {ComposerDraft & {text: string}} ComposerRecord
 * @typedef {import("../../records/thread/destination.js").SendFrame | null} ComposerFrame
 * @typedef {Object} ComposerOptions
 * @property {(on: boolean) => unknown} setReact
 * @property {typeof import("../reactions.js").reactionEmoji} reactionEmoji
 * @property {typeof import("../reactions.js").reactionAvailable} reactionAvailable
 * @property {() => boolean} designModeActive
 * @property {ReturnType<typeof import("../../records/thread/destination.js").createThreadDestinations>["openPageThread"]} openPageThread
 * @property {(anchor: Anchor | null) => Element | Range | null} anchorTravelAt
 * @property {() => Anchor | null} fabAnchorAt
 * @property {() => string | null} fabHoldAt
 * @property {() => Element | null} fabPointAt
 * @property {() => ComposerFrame} fabFrameAt
 * @property {() => Promise<boolean>} fabPositioned
 * @property {() => import("./surface.js").FabFocusHandoff} beginFabFocus
 * @property {(handoff?: import("./surface.js").FabFocusHandoff | null) => unknown} endFabFocus
 * @property {(handoff: import("./surface.js").FabFocusHandoff, anchor: Anchor | null, stands: () => boolean) => unknown} landFabFocus
 * @property {(anchor: Anchor | null, options?: {point?: Element | null | undefined, reveal?: boolean}) => unknown} showFab
 * @property {() => unknown} letGoOfFab
 * @property {() => () => unknown} takeDownFab
 * @property {(command: import("../../records/thread/actions.js").CreateComment) => NonNullable<ReturnType<ReturnType<typeof import("../../records/thread/actions.js").createThreadActions>["create"]>>["delivery"] | null} createComment
 * @property {(destination: Element) => unknown} landSent
 * @property {() => Promise<unknown>} refreshThread
 * @property {ReturnType<typeof import("./input.js").createCompositionInputs>["wireInput"]} wireInput
 * @property {{target: (anchor: Anchor | null) => Element | null, replace: (anchor: Anchor | null, drawing: import("../../../types/domain.js").DraftDrawing | null) => unknown, undoStroke: (anchor: Anchor | null) => unknown, remove: (anchor: Anchor | null) => unknown}} drawingEdits
 */
/** @type {Anchor | null} */
export let pendingAnchor = null;
/** @type {"design" | null} */
export let pendingAbout = null;
/** @type {import("../../../types/domain.js").DraftDrawing | null} */
export let pendingDrawing = null;

// The words of the element a comment was pointed at, as the passage that finds them
// again once a re-render has replaced the element (readings/pointed-place.js); null for none.
/** @param {Element} element */
function wordsOf(element) {
  const range = document.createRange();
  range.selectNodeContents(element);
  const words = anchorForRange(range);
  return words?.quote?.trim() ? words : null;
}
export let composerOpen = false;

/** @param {ComposerOptions} options */
export function createSelectionComposer({
  setReact,
  reactionEmoji,
  reactionAvailable,
  designModeActive,
  openPageThread,
  anchorTravelAt,
  fabAnchorAt,
  fabHoldAt,
  fabPointAt,
  fabFrameAt,
  fabPositioned,
  beginFabFocus,
  endFabFocus,
  landFabFocus,
  showFab,
  letGoOfFab,
  takeDownFab,
  createComment,
  landSent,
  refreshThread,
  wireInput,
  drawingEdits,
}) {
  const closeReactions = () => setReact(false);

  // What the open composer's comment is about: "design" for one opened in design mode, so
  // the anchor chosen there — a widget, a control, a runtime part — posts with the word
  // that says so. Decided at the open, where the anchor is, and carried with the draft: a
  // draft in the panel remains about design however the mode stands when it is sent.
  // The composer's draft is keyed by the passage it is on. Under one key — which is what it
  // was while a draft lived and died in one tab — two tabs composing on different passages
  // would each overwrite the other's words, so the key says which passage and the record
  // says the rest: the anchor and its capture revision (a later document still has to
  // say what the draft was about), the mode it was written in, and when it was last touched,
  // which is what picks the one to reopen at load. The key is the anchor's identity, so a
  // draft follows an identified subject across a data replacement as `sameAnchor` does;
  // reopened on the re-minted anchor, it posts that anchor, the rendering last aimed at.
  const COMPOSER_KEY = commentContext("");
  /** @type {import("../../records/composition-input.js").InputSync} */
  let syncComposer;
  let pendingRevision = applicationState.read().document.revision;
  // The draft owns its mode; the response action and editor hint present it.
  let suggestionMode = false;
  const composerDraftPayload = () =>
    composerPayload({
      anchor: pendingAnchor,
      revision: pendingRevision,
      suggest: suggestionMode,
      about: pendingAbout,
      drawing: pendingDrawing,
    });
  const saveComposerDraft = (text = syncComposer.value()) =>
    saveDraft(composerCtx(pendingAnchor), text, composerDraftPayload());
  // Words and their submission metadata belong to the shared draft generation.
  // The draft store parses and caches it once for every reader, including parked ink.
  /** @param {string} ctx */
  const composerRecord = (ctx) => {
    const draft = loadDraft(ctx);
    return draft && isComposerDraft(draft.payload)
      ? { ...draft.payload, text: draft.text }
      : null;
  };
  // The drawing a passage's draft holds, whether or not its box is up: putting the box
  // away keeps the draft, strokes included.
  /** @param {Anchor | null} anchor */
  const draftDrawing = (anchor) => {
    return composerRecord(composerCtx(anchor))?.drawing ?? null;
  };
  // Every passage's draft that holds a drawing, box up or not: each is ink the user drew
  // and has neither sent nor taken back, so the page shows all of it. `open` says the
  // composer stands on it now.
  function heldDrawings() {
    const at = composerCtx(pendingAnchor);
    const held = [];
    for (const ctx of draftContexts()) {
      if (!ctx.startsWith(COMPOSER_KEY)) continue;
      const record = composerRecord(ctx);
      const drawing = ctx === at ? pendingDrawing : record?.drawing;
      if (!record || !drawing) continue;
      held.push({ anchor: record.anchor, drawing, open: composerOpen && ctx === at });
    }
    return held;
  }
  // Replace the drawing a passage's draft holds, or take it off with null, leaving the
  // words. The composer on that passage, up or put away, holds the draft's
  // current reading, so it takes the change and saves it; any other draft is rewritten
  // where it is stored, and one left holding nothing is settled.
  /** @param {Anchor | null} anchor @param {import("../../../types/domain.js").DraftDrawing | null} drawing */
  function setDraftDrawing(anchor, drawing) {
    const ctx = composerCtx(anchor);
    if (ctx === composerCtx(pendingAnchor)) {
      pendingDrawing = drawing;
      saveComposerDraft();
      syncSuggestMode();
      return;
    }
    const record = composerRecord(ctx);
    if (!record) return;
    const { text, ...payload } = record;
    if (!text && !drawing) clearDraft(ctx);
    else saveDraft(ctx, text, { ...payload, drawing });
  }
  // News of any passage's draft, whose ink the page shows whether or not its box is up.
  /** @param {() => void} callback */
  const watchHeldDrawings = (callback) => watchDrafts(COMPOSER_KEY, callback);
  // An empty open box is not settled, but holds nothing to reopen. The newest draft
  // with words or ink stays recoverable even when its original passage is detached.
  function pendingComposer() {
    let best = null;
    for (const ctx of draftContexts()) {
      if (!ctx.startsWith(COMPOSER_KEY)) continue;
      const record = composerRecord(ctx);
      if ((record?.text || record?.drawing) && (!best || record.touched > best.touched))
        best = record;
    }
    return best;
  }
  let composerEpoch = 0;
  // What the box holds that a user would miss, asked once. The complete draft, because a
  // attached image is in it and not in the field, plus a drawing, which stands beside the
  // words rather than in them. Three places ask: the send's own guard, the sentence a
  // hiding box says about what became of the words, and the word Escape's row shows. With
  // a spelling each, the one over the field alone would read a box holding a picture
  // and nothing else as empty.
  /** @param {string | null | undefined} draft */
  const holdsContent = (draft) => Boolean(draft || pendingDrawing);
  const composerHolds = () => holdsContent(syncComposer.value());

  // The composer's suggest-mode rendering — the offer of it, the button label and the
  // placeholder — derived from the current state in one place, so the four paths that
  // set that state (toggle, open, close, another tab's keystroke) can't each restate
  // half of it. The placeholder itself is wireInput's to paint, from the box's hint;
  // syncComposer asks for that paint.
  function syncSuggestMode() {
    const suggest = !suggestionMode;
    responseAction(fabSuggest, {
      action: suggest ? "suggest" : "comment",
      label: suggest ? "Suggest" : "Comment",
      collapse: true,
    });
    keeps(fabSuggest, "aria-label", suggest ? "Suggest" : "Comment");
    syncComposer();
    syncResponseOptions();
    repaint(); // the submit action says which of the two the box will do
  }
  /** @param {boolean} suggest */
  function setSuggestionMode(suggest) {
    suggestionMode = Boolean(suggest);
    if (suggestionMode && syncComposer.hasMedia()) {
      suggestionMode = false;
      syncSuggestMode();
      raiseError("Remove attached images before suggesting replacement text");
      focusDestination(composerInput, "return");
      return;
    }
    // Entering suggestion mode seeds the box with the passage to edit in place.
    if (suggestionMode && !syncComposer.value() && pendingAnchor?.quote)
      syncComposer.load((seededQuote = pendingAnchor.quote));
    syncSuggestMode();
    saveComposerDraft();
    focusDestination(composerInput, "return");
  }

  let responseOptionsOpen = false;
  const availableResponseOptions = () => {
    /** @type {NodeListOf<HTMLButtonElement>} */
    const controls = fabOptions.querySelectorAll(".lf-response-action:not([hidden])");
    return [...controls];
  };

  const responseOptionsAreOpen = () => responseOptionsOpen;
  const responseOptionsAvailable = () => availableResponseOptions().length > 0;
  const responseOptionButtons = () =>
    availableResponseOptions().filter((control) => control.checkVisibility());
  const focusedResponseOption = () =>
    responseOptionButtons().find((control) => control === focused()) ?? null;
  const responseReactionButtons = () =>
    responseOptionButtons().filter((control) => control.classList.contains("lf-react"));

  // The options stand whole around the ring, so a step says no position.
  /** @param {string} binding */
  function stepResponseOptions(binding) {
    const choices = responseOptionButtons();
    if (!hasRows(choices)) return;
    const backward = [rowArrows(choices[0])[0], "ArrowUp"].includes(binding);
    focusDestination(
      cycledRow(
        choices,
        choices.find((control) => control === focused()),
        backward ? -1 : 1,
      ),
      "move",
    );
  }

  /** @param {"reaction" | "first"} focus */
  const focusResponseOption = (focus) => {
    // The bar may place a frame or more later; a newer input meanwhile keeps the user
    // where it put them.
    const mayFocus = retainUserIntent();
    void fabPositioned().then((positioned) => {
      if (!positioned || !responseOptionsOpen) return;
      const options = responseOptionButtons();
      const destination =
        focus === "reaction"
          ? options.find((control) => control.classList.contains("lf-react"))
          : options[0];
      if (destination) mayFocus.handoff(() => focusDestination(destination, "move"));
      paintKeys();
    });
  };

  /** @param {boolean} open @param {{focus?: "reaction" | "first" | null}} [options] */
  function setResponseOptions(open, { focus = null } = {}) {
    const next = Boolean(open && fabAnchorAt() && responseOptionsAvailable());
    if (next === responseOptionsOpen) {
      if (next && focus) focusResponseOption(focus);
      return next;
    }
    if (next) setReact(false);
    responseOptionsOpen = next;
    if (next) showNativeLayer(fabOptions, { source: fabOptionsTrigger });
    else closeNativeLayer(fabOptions);
    if (next && focus) focusResponseOption(focus);
    paintKeys();
    return next;
  }

  /** @param {Anchor | null} [anchor] */
  function syncResponseOptions(anchor = fabAnchorAt()) {
    keepsHidden(
      fabSuggest,
      !(
        anchor?.quote &&
        !designModeActive() &&
        (!composerOpen || (!pendingAbout && !pendingDrawing))
      ),
    );
    keepsHidden(fabOptionsTrigger, !responseOptionsAvailable());
    if (responseOptionsOpen && !responseOptionsAvailable()) setResponseOptions(false);
  }

  function resetResponseOptions() {
    setResponseOptions(false);
  }

  // Whether the composer is up, and the only thing that decides it. The stylesheet renders
  // this state; nothing reads it back, because the rendering has a third value the state
  // doesn't — display is "" before the first open, which is neither "block" nor "none", and
  // a guard testing for one of them ran on every mousedown in the page and swallowed the
  // click. Painting hangs off the same call, so the mark and the box are up together.
  /** @param {boolean} open */
  function showComposer(open) {
    if (open && composerField.hasChildNodes()) composer.append(composerField);
    if (!open) syncComposer.cancelDictation();
    // Hiding keeps the words and says so: a hide that says nothing lets a press on the
    // chrome take the box off screen with the user's sentence in it and leaves no sign the
    // sentence still exists — recoverable only by reselecting that exact passage on that
    // exact version. Said here rather than at each dismissal because every one of them — an
    // outside press, Escape, another target — leaves the same state, and
    // every path that discards the words empties the box before hiding it (leaveComposer),
    // so those stay silent. The notice offers the press that brings the draft back,
    // which is the whole of what the user needs from this moment.
    if (composerOpen && !open && composerHolds()) noticeDraftKept();
    composerOpen = open;
    // The wrapper contributes no card or box. Its field is the extended Comment
    // control inside the response bar; the other composer controls stay hidden there.
    composer.toggleAttribute("data-lf-open", open);
    // An explicit Comment gesture focuses the field and drops the native selection, so
    // this mark then becomes the durable pointer to the quoted passage. Automatic passage
    // selection leaves both readings in place until the user enters the field.
    refreshThread();
    repaint();
  }

  // The quote suggestion mode auto-seeded, so reopening on a new anchor can tell
  // machine seed from user text: the seed belongs to its old anchor and is dropped;
  // user text stays with its passage.
  let seededQuote = "";
  // Every view adopts the complete draft here. A fresh capture supplies its own
  // anchor/revision while taking existing words and modes; Resume supplies the saved
  // pair. Mirroring another tab takes that same pair rather than only its new text.
  /** @param {Omit<ComposerRecord, "format" | "touched">} record */
  function adoptComposerDraft({ anchor, revision, text, suggest, about, drawing }) {
    const retargeted = JSON.stringify(pendingAnchor) !== JSON.stringify(anchor);
    if (syncComposer.value() !== text) {
      syncComposer.load(text);
      seededQuote = "";
    }
    pendingAnchor = anchor;
    pendingRevision = revision;
    pendingAbout = about ?? null;
    pendingDrawing = drawing ?? null;
    suggestionMode = Boolean(suggest);
    return retargeted;
  }
  // A new passage defaults to the mode current at the open — a composer opened in
  // design mode is about design — and a restored draft passes its saved modes. A pointing
  // gesture passes the row inside the target it landed on (`point`, readings/pointed-place.js),
  // or null; a route that names no point leaves the bar where it stands on this anchor.
  /** @param {Anchor | null} anchor @param {string | null | undefined} text @param {{suggest?: boolean | undefined, about?: "design" | null | undefined, drawing?: import("../../../types/domain.js").DraftDrawing | null | undefined, focus?: boolean, point?: Element | null | undefined, revision?: number | null}} [options] */
  function openComposer(
    anchor,
    text,
    {
      suggest = undefined,
      about = undefined,
      drawing = undefined,
      focus = true,
      point = undefined,
      revision = applicationState.read().document.revision,
    } = {},
  ) {
    closeReactions();
    const ctx = composerCtx(anchor || null);
    const previousCtx = composerCtx(pendingAnchor);
    const drawingSupplied = drawing !== undefined;
    let storedDrawing = null;
    if (previousCtx !== ctx) {
      suggest = suggest === undefined ? false : suggest;
      about = about === undefined ? (designModeActive() ? "design" : null) : about;
      // The machine's untouched seed belongs to its passage. Resuming that passage
      // retains it; moving to another neither carries it nor mistakes it for user words.
      if (seededQuote && composerInput.value === seededQuote) syncComposer.load("");
      seededQuote = "";
      composerEpoch += 1;
      // Every passage keeps its own draft (records/drafts.js, `draftSubject`), so the box
      // takes up the one at the passage it opens on, whatever gesture opened it, and
      // the words it leaves stay with their passage, listed under Threads' Drafts.
      const leaves = composerOpen && composerHolds();
      syncComposer.load("");
      if (leaves) noticeDraftKept();
      const record = text ? null : composerRecord(ctx);
      storedDrawing = composerRecord(ctx)?.drawing ?? null;
      if (record) ({ text, suggest, about } = record);
    }
    adoptComposerDraft({
      anchor: anchor || null,
      revision,
      text: text || syncComposer.value(),
      suggest: suggest === undefined ? suggestionMode : suggest,
      about: about === undefined ? pendingAbout : about,
      drawing: previousCtx !== ctx ? storedDrawing : pendingDrawing,
    });
    const target = pendingAnchor?.section ? elementById(pendingAnchor.section) : null;
    keeps(
      fabBar,
      "data-lf-paint-plane",
      target && inChrome(target) ? "chrome" : "page",
    );
    // The box takes up the passage's draft as it stands, and its history starts there; a
    // drawing the gesture brings is a change to that draft, which the history holds.
    if (previousCtx !== ctx) syncComposer.arrive();
    if (drawingSupplied) pendingDrawing = drawing ?? null;
    // Chromium may collapse the native page Selection before dispatching the field's
    // focus event. Mark the handoff before showing the surface so that an intermediate
    // selectionchange cannot dismiss the durable passage this composer is opening on.
    const handoff = focus ? beginFabFocus() : null;
    if (!focus) endFabFocus();
    showComposer(true);
    showFab(anchor, { point, reveal: true });
    // The suggest mode renders against the bar once it stands on this anchor with the box
    // open: rendered before, its response choices would follow the bar's previous
    // anchor and flip as the bar arrived.
    syncSuggestMode();
    // The landing waits on the placement this open is about to ask for, so it is set up
    // after the surface is shown rather than against the previous anchor's placement.
    if (handoff) {
      const focusEpoch = composerEpoch;
      landFabFocus(handoff, pendingAnchor, () => focusEpoch === composerEpoch);
    }
    watchComposer();
    // An automatically opened empty field has no draft to save; its first edit does.
    if (
      drawingSupplied &&
      JSON.stringify(composerRecord(ctx)?.drawing ?? null) !==
        JSON.stringify(pendingDrawing)
    ) {
      saveComposerDraft();
      rememberWriting(composerInput);
    }
  }
  // A capture arrives with its passage and bytes together. Opening and attaching in one
  // synchronous turn binds delivery to that draft's arrival generation. Upload
  // completion cannot retarget the picture if the user moves this composer to another
  // passage.
  /** @param {Anchor | null} anchor @param {readonly Blob[]} images @param {Parameters<typeof openComposer>[2]} [options] */
  function openComposerWithMedia(anchor, images, options = {}) {
    openComposer(anchor, "", options);
    return syncComposer.addMedia(images);
  }
  // The box is one view of the draft on this passage, and it follows the plain
  // boxes' rule with one thing of its own: the composer is chrome as well as a box, so a
  // draft settled in another tab — sent, or discarded — leaves it nothing to be open about
  // and it goes down. The subscription moves with the anchor, because the key does.
  /** @type {(() => void) | null} */
  let composerWatch = null;
  function watchComposer() {
    composerWatch?.();
    composerWatch = watchDraft(
      composerCtx(pendingAnchor),
      (value) => {
        // Settled, not discarded. A send masks its generation and leaves the record
        // in place, because a refusal has to give the words back; discarding here would
        // tombstone them first and there would be nothing left to give.
        if (value === null) return settleComposer();
        const record = composerRecord(composerCtx(pendingAnchor));
        if (!record) return settleComposer();
        const outside =
          syncComposer.value() !== record.text ||
          JSON.stringify(record.drawing ?? null) !== JSON.stringify(pendingDrawing);
        const retargeted = adoptComposerDraft(record);
        if (retargeted && composerOpen) showFab(pendingAnchor);
        // Another tab's change is the draft this box takes up, not a step it can take back.
        if (outside) syncComposer.arrive();
        syncSuggestMode();
        refreshThread();
      },
      { input: fabInput, box: () => syncComposer.composition().frame },
    );
  }
  // Hiding keeps the draft and closing discards it, but the mark goes down with the box
  // either way: a marked passage with no composer on screen points at nothing.
  const hideComposer = () => showComposer(false);
  /** @param {boolean} discard */
  function leaveComposer(discard) {
    if (discard) clearDraft(composerCtx(pendingAnchor)); // before the anchor goes: the key is the anchor
    composerWatch?.();
    composerWatch = null;
    syncComposer.load(""); // the whole draft, so an attached image does not outlive its send
    seededQuote = "";
    suggestionMode = false;
    pendingAnchor = null;
    pendingRevision = null;
    pendingAbout = null;
    pendingDrawing = null;
    syncComposer.arrive();
    syncSuggestMode(); // after the state it renders, which is now all of it
    hideComposer();
  }
  // `c` taking the user into a thread's reply leaves the composer's passage. Its draft
  // stays there (records/drafts.js, `draftSubject`), and the box going down says so where it
  // held words. Advancing the generation makes the detachment later than both a draft
  // watch and a send already in flight, so neither can reclaim the view when it settles.
  function leaveForThread() {
    if (!pendingAnchor) return;
    const kept = composerOpen && composerHolds();
    composerEpoch += 1;
    leaveComposer(false);
    showFab(null);
    if (kept) noticeDraftKept();
  }
  // This tab's send, while it settles the composer it sends from (`send` below).
  /** @type {{letGo: (() => unknown) | null} | null} */
  let sending = null;
  // The composer going down because its draft is spent rather than because the user
  // dropped it: the words are somewhere else now, or on their way back.
  function settleComposer() {
    leaveComposer(false);
    // A send lands the user itself, on the conversation it opens, so the bar it takes
    // down lets go of no one first. Letting go reads the page's reading place, which
    // the first read after a change measures across the whole page (readings/reading-place.js,
    // `runsIn`), only for the send to move the user on.
    if (sending) {
      sending.letGo = takeDownFab();
      return;
    }
    // Settlement may arrive after Escape has already started another keyboard gesture.
    // Move focus only when it still belongs to the field this settlement hid; showFab's
    // page return makes that distinction from a later focus elsewhere.
    letGoOfFab();
  }

  // The response bar's Comment action returns to this same compact field on the anchor
  // the bar is carrying. It remains a button only while the choices are visible.

  // The one place a stored composer record becomes an open box. Startup reopens the most
  // recently touched draft through it, and the address below returns to that same record
  // mid-session; two hand-written copies of "what a record means" would be free to drift
  // about the mode a draft was written in. A detached record retains its native editor
  // in the shared unanchored window posture; losing the passage never loses its words.
  function openDraft(record = pendingComposer(), { focus = true } = {}) {
    if (!record) return false;
    openComposer(record.anchor, record.text, { ...record, focus });
    return true;
  }

  registerWritingDestination(COMPOSER_KEY, (ctx) => {
    const record = composerRecord(ctx);
    if (!record) return null;
    return {
      hasContent: Boolean(record.text || record.drawing),
      // A detached draft's destination is its native editor, not a guessed passage.
      // Arrival clears covering surfaces before this same field is materialized.
      where: anchorTravelAt(record.anchor) ?? composerInput,
      input: () =>
        composerOpen && composerCtx(pendingAnchor) === ctx ? composerInput : null,
      frame: () =>
        composerOpen && composerCtx(pendingAnchor) === ctx
          ? syncComposer.composition().field
          : null,
      close: () => {
        if (composerOpen && composerCtx(pendingAnchor) === ctx) leaveForThread();
      },
      open: () => {
        openDraft(composerRecord(ctx), { focus: false });
        const handoff = beginFabFocus();
        return () => endFabFocus(handoff);
      },
      present: fabPositioned,
    };
  });

  function mount() {
    declareResponseOptionKeys();
    syncComposer = wireInput(composerInput, {
      hint: () =>
        suggestionMode
          ? "Replacement text"
          : pendingAbout
            ? "About the layer"
            : COMMENT_HINT,
      sends: () => (suggestionMode ? "suggest" : "comment"),
      allowsMedia: () =>
        suggestionMode ? "Images can be added to comments, not replacement text" : true,
      hasContent: holdsContent,
      save: saveComposerDraft,
      drawing: {
        read: () => pendingDrawing,
        target: () => drawingEdits.target(pendingAnchor),
        replace: (drawn) => drawingEdits.replace(pendingAnchor, drawn),
        undoStroke: () => drawingEdits.undoStroke(pendingAnchor),
        remove: () => drawingEdits.remove(pendingAnchor),
      },
      // The second send an outlet's hold offers (`fabHoldAt`), whose comment holds the
      // widget it is about while its thread is open. A suggestion and a drawing's
      // comment hold nothing (`$events`, comment).
      altLabel: () => (suggestionMode || pendingDrawing ? null : fabHoldAt()),
      send: async (_text, raw, owns, _typed, alternate) => {
        const anchor = structuredClone(pendingAnchor);
        const holds = alternate ? anchor?.section : null;
        const revision = pendingRevision;
        const ctx = composerCtx(anchor);
        const suggestion = suggestionMode;
        const about = pendingAbout;
        const drawing = pendingDrawing && sentDrawing(structuredClone(pendingDrawing));
        // The accepted comment becomes a thread, drawn as a card beside the passage unless
        // Threads is open. The new card stands where the field did (`origin`).
        const origin = fabFrameAt();
        const point = fabPointAt();
        const epoch = composerEpoch;
        const currentIntent = retainUserIntent();
        // A send that lands the user nowhere, its conversation unshown or a later
        // gesture taking over, lets them go from the bar it took down as the
        // settlement would have (`takeDownFab`).
        /** @type {{letGo: (() => unknown) | null}} */
        const settling = { letGo: null };
        sending = settling;
        const landElsewhere = () => settling.letGo?.();
        /** @type {ReturnType<typeof sendMessage>} */
        let sent;
        try {
          sent = sendMessage(
            ctx,
            () => composerCtx(pendingAnchor) === ctx && owns(),
            (attempt) => {
              // Kept under the attempt, which names the thread before and after the log
              // answers (`threadKey`), with the words that find the row again.
              if (point) commitPoint(attempt, point, wordsOf(point));
              const content = drawing
                ? raw
                  ? { text: raw, drawing }
                  : { drawing }
                : { text: raw };
              return createComment({
                ...content,
                revision,
                attempt,
                ...(anchor && { anchor }),
                ...(suggestion && { suggestion: true }),
                ...(about && { about }),
                ...(holds && { holds }),
              });
            },
            // A refusal withdraws the thread the send drew and hands the words back to
            // this passage's draft, and the user who has done nothing since back to its
            // box (records/drafts.js, `sendMessage`), as the page comment card's does, unless
            // another passage's composer stands meanwhile.
            () => {
              if (composerEpoch !== epoch || composerOpen) return;
              const record = composerRecord(ctx);
              if (record) openDraft(record);
            },
          );
        } finally {
          sending = null;
        }
        if (!sent) return landElsewhere();
        // The thread the send starts is its acknowledgement. The hold says what its
        // press did beyond sending, and names the comment too, since it is the later
        // write to the live region and would otherwise be all a listener heard. What
        // being held means is the widget's to say, as it labelled the press.
        if (holds) notice("Held until resolved");
        const revealSent = bindQueuedWork(
          /** @param {Parameters<typeof openPageThread>[1]} options */ (options) =>
            openPageThread(sent.id, options),
        );
        // The semantic publication is synchronous, while the retained thread list
        // commits its keyed DOM asynchronously. Wait for that presentation before
        // choosing the destination: otherwise an already-open panel can be asked to
        // focus a pending thread before the thread exists.
        await refreshThread();
        // A later draft or selection keeps its focus. The accepted comment still belongs
        // in an open panel, including when revealing it must widen the panel's filter.
        const revealAvailable = () =>
          composerEpoch === epoch && loadDraft(ctx) === null && !pageSelection();
        const mayReveal = () => revealAvailable() && currentIntent();
        const shouldReveal = mayReveal();
        // Land where any send leaves the user (`landSent`): on the conversation's
        // card or title, never back on its page target. A later
        // gesture may already have moved the user elsewhere while presentation was
        // settling.
        if (shouldReveal) {
          const destination = await revealSent({
            part: "thread",
            focus: true,
            travel: false,
            intent: restrictUserIntent(currentIntent, revealAvailable),
            origin,
          });
          const thread = destination && closestAcross(destination, THREAD);
          if (mayReveal() && thread) currentIntent.handoff(() => landSent(thread));
        }
        landElsewhere();
      },
    });
    syncComposer.composition().field.append(fabOptionsTrigger);
    fabSuggest.onclick = () => {
      setResponseOptions(false);
      setSuggestionMode(!suggestionMode);
    };
    fabOptions.addEventListener("toggle", () => {
      if (!isNativeLayer(fabOptions)) setResponseOptions(false);
    });
    onCurrentLocation(
      /** @param {Element | null} node */ (node) => {
        if (node && responseOptionsOpen && !fabBar.contains(node))
          setResponseOptions(false);
      },
    );
    fab.onclick = () => {
      if (!fabAnchorAt()) return;
      openComposer(fabAnchorAt(), "");
    };
  }
  // The other-responses disclosure. Its choices apply only while focus is inside them, so
  // they stand ahead of neither the field's exact send command nor native text entry. The
  // same rows are declared twice on purpose: once as a page scope, which answers while the
  // field itself holds focus, and once on the disclosure element, where the arrows move
  // through the choices themselves. Tab is the browser's: it walks the field and the
  // choices in their order and on out of the bar, which closes them.
  const RESPONSE_OPTIONS_TITLE = "With other responses open";
  /** @type {import("../../dom/keyboard/bindings.js").Command} */
  const RESPONSE_REACTION = {
    id: "response.reaction.choose",
    touch: false,
    ready: savedReadingSettled,
    keys: () =>
      reactionEmoji()
        .slice(0, 9)
        .map((_, index) => String(index + 1)),
    label: () => {
      const count = Math.min(reactionEmoji().length, 9);
      return count > 1 ? `1–${count}` : "1";
    },
    description: () =>
      reactionEmoji()
        .slice(0, 9)
        .map((emoji, index) => `${index + 1} ${emoji}`)
        .join(", "),
    title: "react",
    when: () =>
      reactionAvailable() &&
      !takesLetters(focused()) &&
      responseReactionButtons().length > 0,
    runKey: /** @param {string} binding */ (binding) =>
      responseReactionButtons()[+binding - 1]?.click(),
  };
  /** @type {import("../../dom/keyboard/bindings.js").Command} */
  const RESPONSE_MOVE = {
    id: "response.move",
    touch: false,
    keys: ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"],
    title: "move",
    repeat: true,
    when: () => focusedResponseOption() !== null,
    runKey: stepResponseOptions,
  };
  /** @type {import("../../dom/keyboard/bindings.js").Command} */
  const RESPONSE_ACTIVATE = {
    id: "response.activate",
    touch: false,
    keys: PRESS,
    title: "choose",
    when: () => {
      const option = focusedResponseOption();
      return (
        option !== null &&
        (!option.classList.contains("lf-react") || reactionAvailable())
      );
    },
    run: () => focusedResponseOption()?.click(),
  };
  /** @type {import("../../dom/keyboard/bindings.js").Command} */
  const RESPONSE_CLOSE = {
    id: "response.close",
    touch: false,
    keys: ["Escape"],
    title: "close",
    // Closing the other responses hands the user back to the bar they opened them from.
    run: () =>
      closeLayer(
        () => setResponseOptions(false),
        () => {
          const back = [fabInput, fab].find((control) => control.checkVisibility());
          if (back) focusDestination(back, "return");
        },
      ),
  };
  const responseOptionRows = () => [
    RESPONSE_REACTION,
    RESPONSE_MOVE,
    RESPONSE_ACTIVATE,
    RESPONSE_CLOSE,
  ];
  pageScope("response options", {
    title: RESPONSE_OPTIONS_TITLE,
    escape: "inner",
    at: () => responseOptionsAreOpen() && focused() === fabInput,
    rows: responseOptionRows(),
  });
  function declareResponseOptionKeys() {
    keys(fabOptions, RESPONSE_OPTIONS_TITLE, responseOptionRows(), {
      when: responseOptionsAreOpen,
      escape: "inner",
    });
  }

  return {
    composition: () => syncComposer.composition(),
    frame: composer,
    pendingComposer,
    draftDrawing,
    heldDrawings,
    watchHeldDrawings,
    setDraftDrawing,
    draftKey: composerCtx,
    composerHolds,
    responseOptionsAreOpen,
    responseOptionsAvailable,
    setResponseOptions,
    syncResponseOptions,
    resetResponseOptions,
    openComposer,
    openComposerWithMedia,
    hideComposer,
    leaveForThread,
    openDraft,
    mount,
  };
}
