/* The selection composer: the response bar's field bound to a passage's draft.

   The selection composer keeps its passage painted after an explicit Comment gesture
   moves focus into the field. Automatic passage selection leaves the native
   selection in place. Its `.lf-composer` wrapper contributes state and draft machinery
   through `display: contents`; only `.lf-fab-input` draws. `showComposer` states
   whether it is open through `data-lf-open`; the shared response stylesheet derives
   its field and bar's visible shape from that and the surface's target-only state.
   Reopening the same passage resumes its words, seed, and modes; omitted modes
   initialize only a new passage, while explicit options restore a stored record.
   `openComposer`'s `focus` option decides focus independently. Outside clicks and
   Escape hide without discarding words. A successful send settles only the submitted draft generation.

   A hidden draft is news and a place: hiding one that still holds words says so once,
   and Resume writing brings its editor back. A refused send reopens its box with the
   words while the user has done nothing since Send. Startup reopens a stored composer
   record through `openDraft`. Every path that discards words empties
   the box first, so those hide silently.

   The response surface (composing/surface.js) constructs the command owner with its bar's
   commands and boot's travel, delivery, and repaint capabilities. Importing this module exposes only passive nodes and live draft
   readings. mount binds the field and its controls after those owners exist. */
import { el, offerAction, responseAction } from "../widget-elements.js";
import { anchorKey } from "../anchor-coordinate.js";
import { keeps, keepsHidden } from "../keeps.js";

import {
  clearDraft,
  draftContexts,
  loadDraft,
  loadDraftPayload,
  saveDraft,
  sendMessage,
  transferDraft,
  watchDraft,
  watchDrafts,
  rememberWriting,
  registerWritingDestination,
} from "../drafts.js";

import { pageSelection } from "./capture.js";
import { anchorForRange } from "../anchor-resolution.js";
import { THREAD } from "../thread/selectors.js";
import { keys, paintKeys } from "../keyboard/scopes.js";
import { showNativeLayer, closeNativeLayer } from "../keyboard/layer-stack.js";
import { pageScope } from "../keyboard/register.js";
import {
  PRESS,
  cycledRow,
  rowArrows,
  savedReadingSettled,
} from "../keyboard/bindings.js";
import {
  onCurrentLocation,
  takesLetters,
  focusDestination,
  focused,
  closeLayer,
} from "../focus.js";
import { repaint } from "../repaint.js";
import { restrictUserIntent, retainUserIntent } from "../user-intent.js";
import { applicationState } from "../semantic-state.js";
import { bindQueuedWork } from "../queued-work.js";

import { closestAcross, elementById, inChrome } from "../passages.js";

import { notice } from "../notifications.js";
import { sentDrawing } from "./drawing-record.js";
import { DRAFT_FORMAT } from "../kernel-facts.js";
import { commitPoint } from "../pointed-place.js";
import { beginWalk, listWalkPosition } from "../walk-position.js";
import { textField } from "./text-field.js";
import { raiseError } from "../errors.js";
import { isNativeLayer } from "../shadow-tree.js";

// The comment field keeps Send or Dictate as its primary action. Other responses
// open in one anchored picker from a ⋯ in the field's corner, Tab, or e. The same
// picker follows the composer between the floating panel, a passage, and a widget
// outlet; opening it never changes the field's size or position.
//
// The ⋯ stands beside Dictate only while the field is empty, and the draft's first
// word takes its place, so the field spans the bar in every state and nothing moves
// as the user starts typing (response.css). Max chose this on 25 October 2026 over a
// bordered button beside the field, which kept 40px of a 294px bar from the words
// and ended a sent card's message short of its Reply field, over hiding that button
// at the first key, which widened the field under the caret, and over no button at
// all, which left a mouse or finger no way to Suggest or a reaction. It replaces
// #4124's ⋯ over the field's end, in the head row the floating frame reserves, which
// only the floating presentation had.
export const fabBar = el("div", "lf-ui lf-fab-bar lf-target-paint");
fabBar.dataset.lfRuntime = ""; // Leaf's own when seated in a widget (passages.js, leafSurface)
fabBar.setAttribute("role", "group");
fabBar.setAttribute("aria-label", "Respond");
export const fabInput = textField();
fabInput.className = "lf-ui lf-response-control lf-fab-input";
fabInput.name = "comment";
fabInput.placeholder = "Comment…";
fabInput.setAttribute("aria-label", "Comment");
const fab = responseAction(el("button", "lf-ui lf-fab"), {
  icon: "comment",
  label: "Comment",
  behavior: "disclosure",
});
fab.id = "lf-comment-button";
fab.title = "Comment";
export const fabOptions = el("span", "lf-response-options");
fabOptions.id = "lf-response-options";
fabOptions.popover = "auto";
fabOptions.setAttribute("role", "group");
fabOptions.setAttribute("aria-label", "Other responses");
const fabSuggest = responseAction(el("button", "lf-ui lf-fab-suggest"), {
  icon: "edit",
  label: "Suggest",
  collapse: true,
});
fabOptions.append(fabSuggest);
// It joins the field `wireInput` builds around the editor when the composer mounts.
export const fabOptionsTrigger = offerAction(
  "symbol",
  "lf-response-trigger",
  "Other responses",
  { icon: "more" },
);
fabOptionsTrigger.setAttribute("aria-controls", fabOptions.id);
fabOptionsTrigger.setAttribute("aria-expanded", "false");
fabOptionsTrigger.popoverTargetElement = fabOptions;
fabBar.append(fab, fabOptions);

const composer = el("div", "lf-ui lf-composer");
composer.id = "lf-composer";
// Never shown: anchor paint, its one writer, fills it with the words the field's
// description reads (below). lf-ui on the element itself, not just on the composer
// around it: this is the only injected chrome carrying an id, and "which section is this
// in" is asked as `[id]:not(.lf-ui)` of the element rather than of its ancestors, so
// without the class it answers that question with itself.
export const composerQuote = el("blockquote", "lf-ui lf-quote detached");
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
const composerSend = el("button", "", "Comment");
// The field, and the shelf and controls `wireInput` gathers around it, wait outside the
// page until the composer first opens (`showComposer`), since a connected field builds
// its editor: a page whose composer never opens builds none. Everything that reads the
// field before then reads its words and draft, which it holds unconnected.
const composerField = document.createDocumentFragment();
composerField.append(composerInput);
composer.append(composerQuote, composerSend);
fabBar.prepend(composer);

export let pendingAnchor = null;
export let pendingAbout = null;
export let pendingDrawing = null;

// The words of the element a comment was pointed at, as the passage that finds them
// again once a re-render has replaced the element (pointed-place.js); null for none.
function wordsOf(element) {
  const range = document.createRange();
  range.selectNodeContents(element);
  const words = anchorForRange(range);
  return words.quote?.trim() ? words : null;
}
export let composerOpen = false;

export function createSelectionComposer({
  setReact,
  reactionTokens,
  reactionAvailable,
  designModeActive,
  openPageThread,
  anchorTravelAt,
  bringForward,
  fabAnchorAt,
  fabPointAt,
  fabFrameAt,
  fabPositioned,
  beginFabFocus,
  endFabFocus,
  landFabFocus,
  showFab,
  letGoOfFab,
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
  const COMPOSER_KEY = "composer:";
  const composerCtx = (anchor) => COMPOSER_KEY + anchorKey(anchor);
  let syncComposer;
  let pendingRevision = null;
  // The draft owns its mode; the response action and editor hint present it.
  let suggestionMode = false;
  const composerDraftPayload = () => ({
    format: DRAFT_FORMAT,
    anchor: pendingAnchor,
    revision: pendingRevision,
    suggest: suggestionMode,
    about: pendingAbout,
    drawing: pendingDrawing,
    touched: Date.now(),
  });
  const saveComposerDraft = (text = syncComposer.value()) =>
    saveDraft(composerCtx(pendingAnchor), text, composerDraftPayload());
  // Words and their submission metadata belong to the shared draft generation.
  // The draft store parses and caches it once for every reader, including parked ink.
  const composerRecord = (ctx) => {
    const payload = loadDraftPayload(ctx);
    return payload?.format === DRAFT_FORMAT
      ? { ...payload, text: loadDraft(ctx) }
      : null;
  };
  // The drawing a passage's draft holds, whether or not its box is up: putting the box
  // away keeps the draft, strokes included.
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
  // hiding box says about what became of the words, and the word Escape's row shows. They
  // had a spelling each, and the one over the field alone read a box holding a picture
  // and nothing else as empty.
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
      icon: suggest ? "edit" : "comment",
      label: suggest ? "Suggest" : "Comment",
      collapse: true,
    });
    keeps(fabSuggest, "aria-label", suggest ? "Suggest" : "Comment");
    keeps(fabSuggest, "title", suggest ? "Suggest" : "Comment");
    syncComposer();
    syncResponseOptions();
    repaint(); // the submit action says which of the two the box will do
  }
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
  const availableResponseOptions = () => [
    ...fabOptions.querySelectorAll(".lf-response-action:not([hidden])"),
  ];

  const responseOptionsAreOpen = () => responseOptionsOpen;
  const responseOptionsAvailable = () => availableResponseOptions().length > 0;
  const responseOptionButtons = () =>
    availableResponseOptions().filter((control) => control.checkVisibility());
  const focusedResponseOption = () => responseOptionButtons().includes(focused());
  const responseReactionButtons = () =>
    responseOptionButtons().filter((control) => control.classList.contains("lf-react"));

  function stepResponseOptions(binding) {
    const choices = responseOptionButtons();
    if (!choices.length) return;
    const backward = [rowArrows(choices[0])[0], "ArrowUp"].includes(binding);
    focusDestination(cycledRow(choices, focused(), backward ? -1 : 1), "move");
    beginWalk("response-option", "Response", () =>
      listWalkPosition(responseOptionButtons(), focused()),
    );
  }

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

  function setResponseOptions(open, { focus = null } = {}) {
    const next = Boolean(open && fabAnchorAt() && responseOptionsAvailable());
    if (next === responseOptionsOpen) {
      if (next && focus) focusResponseOption(focus);
      return next;
    }
    if (next) setReact(false);
    responseOptionsOpen = next;
    keeps(fabOptionsTrigger, "aria-expanded", String(next));
    if (next) showNativeLayer(fabOptions, { source: fabOptionsTrigger });
    else closeNativeLayer(fabOptions);
    if (next && focus) focusResponseOption(focus);
    paintKeys();
    return next;
  }

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
  function showComposer(open) {
    if (open && composerField.hasChildNodes()) composer.append(composerField);
    if (!open) syncComposer?.cancelDictation();
    // Hiding keeps the words and used to say nothing at all, so a press on the chrome took
    // the box off screen with the user's sentence in it and left no sign the sentence
    // still existed — recoverable only by reselecting that exact passage on that exact
    // version. Said here rather than at each dismissal because every one of them — an
    // outside press, Escape, another target — leaves the same state, and
    // every path that discards the words empties the box before hiding it (leaveComposer),
    // so those stay silent. The sentence names the address that brings the draft back,
    // which is the whole of what the user needs from this moment.
    if (composerOpen && !open && composerHolds())
      notice("Draft kept — g i resumes writing");
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
  // user text stays with its passage unless an explicit Comment gesture carries it.
  let seededQuote = "";
  // Every view adopts the complete draft here. A fresh capture supplies its own
  // anchor/revision while taking existing words and modes; Resume supplies the saved
  // pair. Mirroring another tab takes that same pair rather than only its new text.
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
  // gesture passes the row inside the target it landed on (`point`, pointed-place.js),
  // or null; a route that names no point leaves the bar where it stands on this anchor.
  function openComposer(
    anchor,
    text,
    {
      suggest = undefined,
      about = undefined,
      drawing = undefined,
      carry = false,
      focus = true,
      point = undefined,
      revision = applicationState.read().document.revision,
    } = {},
  ) {
    closeReactions();
    const ctx = composerCtx(anchor || null);
    const previousCtx = composerCtx(pendingAnchor);
    const drawingSupplied = drawing !== undefined;
    let carriedDraft = false;
    let storedDrawing = null;
    if (previousCtx !== ctx) {
      suggest = suggest === undefined ? false : suggest;
      about = about === undefined ? (designModeActive() ? "design" : null) : about;
      // The machine's untouched seed belongs to its passage. Resuming that passage
      // retains it; moving to another neither carries it nor mistakes it for user words.
      if (seededQuote && composerInput.value === seededQuote) syncComposer.load("");
      seededQuote = "";
      composerEpoch += 1;
      const previousText = syncComposer.value();
      const previousDrawing = pendingDrawing;
      syncComposer.load("");
      // Automatic selection merely opens another passage's view. An explicit Comment
      // gesture may instead carry unsent words into an empty passage, which preserves
      // the old Alt-click promise without replacing independent work already held at
      // the destination or making a user's next selection silently re-anchor a draft.
      const record = text ? null : composerRecord(ctx);
      storedDrawing = composerRecord(ctx)?.drawing ?? null;
      // A drawing marks its own passage, so a draft holding one stays where it is, as
      // its words do with it (`carryComposerToReply` says the same of a reply).
      const carrying =
        carry && previousText && !previousDrawing && !(record?.text || record?.drawing);
      if (carrying) {
        text ||= previousText;
        carriedDraft = true;
      } else if (record) {
        ({ text, suggest, about } = record);
      }
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
    let handoff = 0;
    if (focus) handoff = beginFabFocus();
    else endFabFocus();
    showComposer(true);
    showFab(anchor, { point, reveal: true });
    // The suggest mode renders against the bar once it stands on this anchor with the box
    // open: rendered before, its response choices would follow the bar's previous
    // anchor and flip as the bar arrived.
    syncSuggestMode();
    // The landing waits on the placement this open is about to ask for, so it is set up
    // after the surface is shown rather than against the previous anchor's placement.
    if (focus) {
      const focusEpoch = composerEpoch;
      landFabFocus(handoff, pendingAnchor, () => focusEpoch === composerEpoch);
    }
    watchComposer();
    // Programmatic carrying fires no input event, so persist that one move explicitly.
    // An automatically opened empty field has no draft to save; its first edit does.
    if (carriedDraft)
      transferDraft(previousCtx, ctx, syncComposer.value(), composerDraftPayload());
    else if (
      drawingSupplied &&
      JSON.stringify(composerRecord(ctx)?.drawing ?? null) !==
        JSON.stringify(pendingDrawing)
    ) {
      saveComposerDraft();
      rememberWriting(composerInput);
    }
  }
  // A capture arrives with its passage and bytes together. Opening and attaching in one
  // synchronous turn binds delivery to that draft's arrival generation, while carrying
  // unsent words under the same rule as an explicit Comment gesture. Upload completion
  // cannot retarget the picture if the user moves this composer to another passage.
  function openComposerWithMedia(anchor, images, options = {}) {
    openComposer(anchor, "", { carry: true, ...options });
    return syncComposer.addMedia(images);
  }
  // The box is one view of the draft on this passage, and it follows the plain
  // boxes' rule with one thing of its own: the composer is chrome as well as a box, so a
  // draft settled in another tab — sent, or discarded — leaves it nothing to be open about
  // and it goes down. The subscription moves with the anchor, because the key does.
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
      { input: fabInput },
    );
  }
  // Hiding keeps the draft and closing discards it, but the mark goes down with the box
  // either way: a marked passage with no composer on screen points at nothing.
  const hideComposer = () => showComposer(false);
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
  // Detaching leaves the prior draft in its own context but removes this view from it.
  // Advancing the generation makes the detachment later than both a draft watch and a
  // send already in flight, so neither can reclaim the view when it settles.
  function detachComposer() {
    composerEpoch += 1;
    leaveComposer(false);
  }
  // Reply drafts hold ordinary message text. A passage's replacement, design remark,
  // drawing, or attached media stays in its original context rather than losing its
  // meaning when the user continues a different conversation.
  function carryComposerToReply(ctx) {
    if (!pendingAnchor) return;
    const text = syncComposer.value();
    if (
      ctx &&
      text &&
      !loadDraft(ctx) &&
      !suggestionMode &&
      !pendingAbout &&
      !pendingDrawing &&
      !syncComposer.hasMedia()
    )
      transferDraft(composerCtx(pendingAnchor), ctx, text);
    detachComposer();
    showFab(null);
  }
  // The composer going down because its draft is spent rather than because the user
  // dropped it: the words are somewhere else now, or on their way back.
  function settleComposer() {
    leaveComposer(false);
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
            : "Comment…",
      sends: () => (suggestionMode ? "suggest" : "comment"),
      sendBtn: composerSend,
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
      send: async (_text, raw, owns, visible) => {
        const anchor = structuredClone(pendingAnchor);
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
        const untouched = retainUserIntent({ source: document.documentElement });
        let flight = null;
        const sent = sendMessage(
          ctx,
          () => composerCtx(pendingAnchor) === ctx && owns(),
          (attempt) => {
            // Kept under the attempt, which names the thread before and after the log
            // answers (`threadKey`), with the words that find the row again.
            if (point) commitPoint(attempt, point, wordsOf(point));
            const event = { anchor, revision, attempt };
            if (raw) event.text = raw;
            if (suggestion) event.suggestion = true;
            if (about) event.about = about;
            if (drawing) event.drawing = drawing;
            return (flight = createComment(event));
          },
        );
        if (!sent) return;
        // A refusal withdraws the thread the send drew and hands the words back to this
        // passage's draft. While the user has done nothing since Send, the box comes back
        // with them, as the page comment card's does. Withdrawing the thread the send
        // landed them on hands their focus on (`handBack`), so where focus stands is no
        // reading of their intent here, only whether they have acted since. After a
        // later gesture the words wait for Resume writing.
        void Promise.resolve(flight).then((accepted) => {
          if (accepted || composerEpoch !== epoch || composerOpen) return;
          const record = composerRecord(ctx);
          if (record && untouched()) untouched.handoff(() => openDraft(record));
        });
        const revealSent = bindQueuedWork((options) =>
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
      },
    });
    composerInput.parentElement.append(fabOptionsTrigger);
    fabSuggest.onclick = () => {
      setResponseOptions(false);
      setSuggestionMode(!suggestionMode);
    };
    fabOptions.addEventListener("toggle", () => {
      if (!isNativeLayer(fabOptions)) setResponseOptions(false);
    });
    onCurrentLocation((node) => {
      if (node && responseOptionsOpen && !fabBar.contains(node))
        setResponseOptions(false);
    });
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
  const RESPONSE_REACTION = {
    id: "response.reaction.choose",
    touch: false,
    ready: savedReadingSettled,
    keys: () =>
      reactionTokens()
        .slice(0, 9)
        .map((_, index) => String(index + 1)),
    label: () => {
      const count = Math.min(reactionTokens().length, 9);
      return count > 1 ? `1–${count}` : "1";
    },
    description: () =>
      reactionTokens()
        .slice(0, 9)
        .map(([name, entry], index) => `${index + 1} ${entry.glyph} ${name}`)
        .join(", "),
    title: "react",
    when: () =>
      reactionAvailable() &&
      !takesLetters(focused()) &&
      responseReactionButtons().length > 0,
    run: (binding) => responseReactionButtons()[+binding - 1]?.click(),
  };
  const RESPONSE_MOVE = {
    id: "response.move",
    touch: false,
    keys: ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"],
    title: "move",
    repeat: true,
    when: () => focusedResponseOption(),
    run: stepResponseOptions,
  };
  const RESPONSE_ACTIVATE = {
    id: "response.activate",
    touch: false,
    keys: PRESS,
    title: "choose",
    when: () =>
      focusedResponseOption() &&
      (!focused().classList.contains("lf-react") || reactionAvailable()),
    run: () => focused()?.click(),
  };
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
    detachComposer,
    carryComposerToReply,
    openDraft,
    mount,
  };
}
