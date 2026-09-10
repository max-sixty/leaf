/* The selection composer: the response bar's field bound to a passage's draft.

   The selection composer keeps its passage painted after an explicit Comment gesture
   moves focus into the textarea. Automatic passage selection leaves the native
   selection in place. Its `.lf-composer` wrapper contributes state and draft machinery
   through `display: contents`; only `.lf-fab-input` draws. `showComposer` states the
   whole visible outcome from `composerOpen`, `pendingAnchor`, and `fabAnchor`;
   `openComposer`'s `focus` option decides focus independently. Outside clicks and
   Escape hide without discarding words. A successful send or an explicit draft close
   discards the local record.

   A hidden draft is news and a place: hiding one that still holds words says so once,
   and `KEPT_DRAFT` is the address that brings it back — the same stored record startup
   reopens (`openDraft`), reached mid-session. Every path that discards words empties
   the box first, so those hide silently.

   Boot constructs the command owner with explicit travel, delivery, and repaint
   capabilities. Importing this module exposes only passive nodes and live draft
   readings. mount binds the field and its controls after those owners exist. */
import { el, keeps, responseAction } from "../widget-elements.js";

import {
  clearDraft,
  draftContexts,
  loadDraft,
  saveDraft,
  sendMessage,
  watchDraft,
} from "../drafts.js";

import { threadsBox } from "../conversation/panel-elements.js";
import { landTyping, mayLandTyping } from "./capture.js";
import { focused, paintKeys } from "../keyboard/scopes.js";
import { repaint } from "../repaint.js";

import { elementById, inChrome } from "../passages.js";

import { notice } from "../notifications.js";
import { validDrawing } from "./drawing-record.js";
import { beginWalk, listWalkPosition } from "../walk-position.js";

// The floating field immediately accepts a comment on the target the reader named.
// Its ellipsis unfolds every other response the target offers. The field is the
// group's stable primary control; reaction vocabulary changes the choices, not the
// disclosure or the field's place.
// One affordance, raised only where the reader has already pointed: a native text
// selection or an explicit Comment target gesture on an item or visual part.
export const fabBar = el("div", "lf-ui lf-fab-bar lf-target-paint");
fabBar.setAttribute("role", "group");
fabBar.setAttribute("aria-label", "Respond");
export const fabInput = document.createElement("textarea");
fabInput.className = "lf-ui lf-response-control lf-fab-input";
fabInput.name = "comment";
fabInput.rows = 1;
fabInput.autocomplete = "off";
fabInput.placeholder = "Comment…";
fabInput.setAttribute("aria-label", "Comment");
export const fab = responseAction(el("button", "lf-ui lf-fab"), {
  icon: "comment",
  label: "Comment",
  behavior: "disclosure",
});
fab.id = "lf-comment-button";
fab.setAttribute("aria-label", "Comment");
fab.title = "Comment";
export const fabMore = responseAction(el("button", "lf-ui lf-response-more"), {
  icon: "more",
  label: "Other responses",
  behavior: "disclosure",
  collapse: true,
});
fabMore.setAttribute("aria-label", "Show other responses");
fabMore.title = "Show other responses";
export const fabOptions = el("span", "lf-response-options");
fabOptions.id = "lf-response-options";
fabOptions.setAttribute("role", "group");
fabOptions.setAttribute("aria-label", "Other responses");
fabMore.setAttribute("aria-controls", fabOptions.id);
fabMore.setAttribute("aria-expanded", "false");
export const fabSuggest = responseAction(el("button", "lf-ui lf-fab-suggest"), {
  icon: "edit",
  label: "Suggest",
  collapse: true,
});
fabOptions.append(fabSuggest);
fabBar.append(fab, fabMore, fabOptions);

export const composer = el("div", "lf-ui lf-composer");
composer.id = "lf-composer";
// Only ever shown detached — anchor paint, its one writer, keeps it out of sight while
// the page is marking the passage. lf-ui on the element itself, not just on the composer
// around it: this is the only injected chrome carrying an id, and "which section is this
// in" is asked as `[id]:not(.lf-ui)` of the element rather than of its ancestors, so
// without the class it answers that question with itself.
export const composerQuote = el("blockquote", "lf-ui lf-quote detached");
composerQuote.id = "lf-composer-quote";
// Suggestion mode: the box holds replacement text for the quoted passage
// instead of a remark — Claude accepts it verbatim into the next version.
const suggestRow = el("label", "lf-suggest-row");
const suggestCheck = document.createElement("input");
suggestCheck.type = "checkbox";
suggestCheck.name = "suggest-replacement";
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
const composerSend = el("button", "lf-btn primary", "Comment");
composer.append(composerQuote, suggestRow, composerInput, composerSend);
fabBar.prepend(composer);

export let pendingAnchor = null;
export let pendingAbout = null;
export let pendingDrawing = null;
export let composerOpen = false;

export function createSelectionComposer({
  panelIsOpen,
  setReact,
  designIsOn,
  marginOpenInlineThread,
  threadTransitionOrigin,
  anchorStands,
  anchorTargetAt,
  bringForward,
  fabAnchorAt,
  holdFabLeft,
  refreshFab,
  showFab,
  goAddress,
  createComment,
  focusSurface,
  showThread,
  refreshConversation,
  wireInput,
}) {
  const closeReactions = () => setReact(false);
  const openInlineThread = (id, ...rest) => {
    const local = focusSurface(id);
    return (
      local?.closest(".lf-conversation-thread") ?? marginOpenInlineThread(id, ...rest)
    );
  };

  // What the open composer's comment is about: "layer" for one opened in design mode, so
  // the anchor chosen there — a widget, a control, a runtime part — posts with the word
  // that says so. Decided at the open, where the anchor is, and carried with the draft: a
  // draft on the banner is about the layer however the mode stands by the time it is sent.
  // The composer's draft is keyed by the passage it is on. Under one key — which is what it
  // was while a draft lived and died in one tab — two tabs composing on different passages
  // would each overwrite the other's words, so the key says which passage and the record
  // says the rest: the anchor itself (a version that drops the passage still has to say
  // what the draft was about), the mode it was written in, and when it was last touched,
  // which is what picks the one to reopen at load.
  const COMPOSER_KEY = "composer:";
  const composerCtx = (anchor) =>
    COMPOSER_KEY +
    JSON.stringify(
      Object.entries(anchor ?? {})
        .filter(([, value]) => ["string", "number", "boolean"].includes(typeof value))
        .sort(([left], [right]) => left.localeCompare(right)),
    );
  let syncComposer;
  const saveComposerDraft = (text = syncComposer.value()) =>
    saveDraft(
      composerCtx(pendingAnchor),
      JSON.stringify({
        text,
        anchor: pendingAnchor,
        suggest: suggestCheck.checked,
        about: pendingAbout,
        drawing: pendingDrawing,
        touched: Date.now(),
      }),
    );
  // An open box the reader emptied keeps its record, which is what tells another tab's
  // composer on that passage that this one is merely empty rather than settled — and leaves
  // nothing to reopen on. So the draft to come back to is the most recently touched one
  // that still holds words — and, for a caller that has to land on it rather than merely
  // reopen what it can, the most recently touched one this document can still stand a box
  // against.
  function pendingComposer(accepts = () => true) {
    let best = null;
    for (const ctx of draftContexts()) {
      if (!ctx.startsWith(COMPOSER_KEY)) continue;
      let record;
      // Parsed under its own guard: a record that no longer parses costs the reader that
      // one draft, where throwing would cost them the page, at module top level.
      try {
        record = JSON.parse(loadDraft(ctx));
      } catch {
        continue;
      }
      if (
        (record?.text || validDrawing(record?.drawing)) &&
        (!best || record.touched > best.touched) &&
        accepts(record)
      )
        best = record;
    }
    return best;
  }
  // The kept draft an address can offer: startup reopens whatever it finds and lets
  // placement decide, while a press promising a destination has to know there is one.
  const keptDraft = () => pendingComposer((record) => anchorStands(record.anchor));
  let composerEpoch = 0;
  // What the box holds that a reader would miss, asked once. The complete draft, because a
  // pasted image is in it and not in the textarea, plus a drawing, which stands beside the
  // words rather than in them. Three places ask: the send's own guard, the sentence a
  // hiding box says about what became of the words, and the word Escape's row shows. They
  // had a spelling each, and the one over the textarea alone read a box holding a picture
  // and nothing else as empty.
  const holdsContent = (draft) => Boolean(draft || pendingDrawing);
  const composerHolds = () => holdsContent(syncComposer.value());

  // The composer's suggest-mode rendering — the offer of it, the button label and the
  // placeholder — derived from the standing state in one place, so the four paths that
  // set that state (toggle, open, close, another tab's keystroke) can't each restate
  // half of it. The placeholder itself is wireInput's to write; syncComposer repaints it
  // from the hint above.
  function syncSuggestMode() {
    // A suggestion is replacement text for a passage of the page; a remark about the
    // layer proposes no words, whatever it quotes.
    suggestRow.style.display =
      pendingAnchor?.quote && !pendingAbout && !pendingDrawing ? "flex" : "none";
    const suggest = !suggestCheck.checked;
    responseAction(fabSuggest, {
      icon: suggest ? "edit" : "comment",
      label: suggest ? "Suggest" : "Comment",
      collapse: true,
    });
    keeps(fabSuggest, "aria-label", suggest ? "Suggest" : "Comment");
    fabSuggest.title = suggest ? "Suggest" : "Comment";
    syncComposer();
    syncResponseOptions();
    repaint(); // the submit action says which of the two the box will do
  }
  function setSuggestionMode(suggest) {
    suggestCheck.checked = Boolean(suggest);
    if (suggestCheck.checked && syncComposer.hasMedia()) {
      suggestCheck.checked = false;
      syncSuggestMode();
      notice("Remove pasted images before suggesting replacement text");
      composerInput.focus({ preventScroll: true });
      return;
    }
    // Entering suggestion mode seeds the box with the passage to edit in place.
    if (suggestCheck.checked && !syncComposer.value() && pendingAnchor?.quote)
      syncComposer.load((seededQuote = pendingAnchor.quote));
    syncSuggestMode();
    saveComposerDraft();
    composerInput.focus({ preventScroll: true });
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
    const options = responseOptionButtons();
    const tabbing = binding === "Tab" || binding === "Shift+Tab";
    const field = composerOpen && fabInput.checkVisibility() ? fabInput : null;
    const choices = tabbing && field ? [field, ...options] : options;
    if (!choices.length) return;
    const at = choices.indexOf(focused());
    const backward =
      binding === "Shift+Tab" || binding === "ArrowLeft" || binding === "ArrowUp";
    const next =
      at < 0
        ? backward
          ? choices.length - 1
          : 0
        : (at + (backward ? -1 : 1) + choices.length) % choices.length;
    choices[next].focus({ preventScroll: true });
    beginWalk("response-option", "Response", () =>
      listWalkPosition(responseOptionButtons(), focused()),
    );
  }

  // More has the same contract as a target's margin disclosure: replace the ellipsis
  // with the remaining local actions and keep the group's primary control in place.
  // The composer supplies a field instead of a primary margin element, so it owns this layout
  // adapter rather than borrowing the margin's target aggregation and spill machinery.
  function setResponseOptions(
    open,
    { focus = null, returnFocus = false, place = true } = {},
  ) {
    const next = Boolean(open && fabAnchorAt() && responseOptionsAvailable());
    if (next === responseOptionsOpen) {
      if (next && focus) {
        const options = responseOptionButtons();
        (focus === "reaction"
          ? options.find((control) => control.classList.contains("lf-react"))
          : options[0]
        )?.focus({ preventScroll: true });
      }
      return next;
    }
    holdFabLeft(next && place);
    if (next) setReact(false);
    responseOptionsOpen = next;
    fabBar.classList.toggle("lf-response-open", next);
    fabMore.setAttribute("aria-expanded", String(next));
    if (place && fabAnchorAt()) showFab(fabAnchorAt());
    if (next && focus) {
      const options = responseOptionButtons();
      const destination =
        focus === "reaction"
          ? options.find((control) => control.classList.contains("lf-react"))
          : options[0];
      destination?.focus({ preventScroll: true });
    } else if (!next && returnFocus) {
      (composerOpen && fabInput.checkVisibility() ? fabInput : fabMore).focus({
        preventScroll: true,
      });
    }
    paintKeys();
    return next;
  }

  function syncResponseOptions(anchor = fabAnchorAt()) {
    fabSuggest.hidden = !(
      anchor?.quote &&
      !designIsOn() &&
      (!composerOpen || (!pendingAbout && !pendingDrawing))
    );
    fabMore.hidden = !anchor || !responseOptionsAvailable();
    if (responseOptionsOpen && !responseOptionsAvailable())
      setResponseOptions(false, { place: false });
  }

  function resetResponseOptions() {
    setResponseOptions(false, { place: false });
  }

  // Whether the composer is up, and the only thing that decides it. The stylesheet renders
  // this state; nothing reads it back, because the rendering has a third value the state
  // doesn't — display is "" before the first open, which is neither "block" nor "none", and
  // a guard testing for one of them ran on every mousedown in the page and swallowed the
  // click. Painting hangs off the same call, so the mark and the box are up together.
  function showComposer(open) {
    // Hiding keeps the words and used to say nothing at all, so a press on the banner took
    // the box off screen with the reader's sentence in it and left no sign the sentence
    // still existed — recoverable only by reselecting that exact passage on that exact
    // version. Said here rather than at each dismissal because every one of them — an
    // outside press, Escape, a covering panel taking the room — leaves the same state, and
    // every path that discards the words empties the box before hiding it (leaveComposer),
    // so those stay silent. The sentence names the address that brings the draft back,
    // which is the whole of what the reader needs from this moment.
    if (composerOpen && !open && composerHolds())
      notice(
        anchorStands(pendingAnchor)
          ? `Draft kept — ${goAddress(KEPT_DRAFT)} returns to it`
          : "Draft kept — it returns when its passage does",
      );
    composerOpen = open;
    // The wrapper contributes no card or box. Its textarea is the extended Comment
    // control inside the response bar; the other composer controls stay hidden there.
    composer.style.display = open ? "contents" : "none";
    composer.toggleAttribute("data-lf-open", open);
    // An explicit Comment gesture focuses the textarea and drops the native selection, so
    // this mark then becomes the durable pointer to the quoted passage. Automatic passage
    // selection leaves both readings standing until the reader enters the field.
    refreshConversation();
    repaint();
  }

  // The quote suggestion mode auto-seeded, so reopening on a new anchor can tell
  // machine seed from user text: the seed belongs to its old anchor and is dropped;
  // user text stays with its passage unless an explicit Comment gesture carries it.
  let seededQuote = "";
  // `about` defaults to the mode standing at the open — a composer opened in design mode
  // is about the layer — and a restored draft passes the word it was saved with.
  function openComposer(
    anchor,
    text,
    {
      suggest = false,
      about = designIsOn() ? "layer" : null,
      drawing = undefined,
      carry = false,
      focus = true,
    } = {},
  ) {
    closeReactions();
    // A box holding nothing but the machine's seed is a box holding nothing. Asked of the
    // seed rather than of the box, because an empty seed matches an empty textarea, and a
    // draft that is one pasted image and no words has exactly that textarea.
    if (seededQuote && composerInput.value === seededQuote) syncComposer.load("");
    seededQuote = "";
    const ctx = composerCtx(anchor || null);
    const previousCtx = composerCtx(pendingAnchor);
    const drawingSupplied = drawing !== undefined;
    let carriedDraft = false;
    if (previousCtx !== ctx) {
      composerEpoch += 1;
      const previousText = syncComposer.value();
      const previousDrawing = pendingDrawing;
      syncComposer.load("");
      // Automatic selection merely opens another passage's view. An explicit Comment
      // gesture may instead carry unsent words there, which preserves the old Alt-click
      // promise without making a reader's next selection silently re-anchor their draft.
      if (carry && (previousText || previousDrawing)) {
        clearDraft(previousCtx);
        text ||= previousText;
        if (!drawingSupplied) drawing = previousDrawing;
        carriedDraft = true;
      } else {
        const held = text ? null : loadDraft(ctx);
        if (held) {
          const record = JSON.parse(held);
          ({ text, suggest, about } = record);
          if (!drawingSupplied) drawing = record.drawing ?? null;
        } else if (!drawingSupplied) drawing = null;
      }
    }
    pendingAnchor = anchor || null;
    pendingAbout = about;
    if (previousCtx !== ctx || drawingSupplied)
      pendingDrawing = validDrawing(drawing) ? drawing : null;
    const target = pendingAnchor?.section ? elementById(pendingAnchor.section) : null;
    fabBar.dataset.lfPaintPlane = target && inChrome(target) ? "chrome" : "page";
    if (text) syncComposer.load(text);
    suggestCheck.checked = Boolean(suggest);
    syncSuggestMode();
    showComposer(true);
    showFab(anchor);
    syncComposer();
    if (focus) composerInput.focus();
    watchComposer();
    // Programmatic carrying fires no input event, so persist that one move explicitly.
    // An automatically opened empty field has no draft to save; its first edit does.
    if (carriedDraft || drawingSupplied) saveComposerDraft();
  }
  // The box is one view of the draft standing on this passage, and it follows the plain
  // boxes' rule with one thing of its own: the composer is chrome as well as a box, so a
  // draft settled in another tab — sent, or discarded — leaves it nothing to be open about
  // and it goes down. The subscription moves with the anchor, because the key does.
  let composerWatch = null;
  function watchComposer() {
    composerWatch?.();
    composerWatch = watchDraft(composerCtx(pendingAnchor), (value) => {
      // Settled, not discarded. A send masks its generation and leaves the record
      // standing, because a refusal has to give the words back; discarding here would
      // tombstone them first and there would be nothing left to give.
      if (value === null) return settleComposer();
      const { text, suggest, about, drawing = null } = JSON.parse(value);
      if (syncComposer.value() !== text) {
        syncComposer.load(text);
        // Whatever stood here is another tab's words now, not this box's machine seed.
        seededQuote = "";
      }
      // The whole record, not the words alone: the mode a draft was written in rides with
      // it (pendingAbout, above), so a box taking up those words sends them under the word
      // they were written with. Design mode is this tab's and the draft's about is not.
      pendingAbout = about;
      pendingDrawing = validDrawing(drawing) ? drawing : null;
      suggestCheck.checked = Boolean(suggest);
      syncSuggestMode();
      refreshConversation();
    });
  }
  // Hiding keeps the draft and closing discards it, but the mark goes down with the box
  // either way: a marked passage with no composer on screen points at nothing.
  const hideComposer = () => showComposer(false);
  function leaveComposer(discard) {
    if (discard) clearDraft(composerCtx(pendingAnchor)); // before the anchor goes: the key is the anchor
    composerWatch?.();
    composerWatch = null;
    syncComposer.load(""); // the whole draft, so a pasted image does not outlive its send
    seededQuote = "";
    suggestCheck.checked = false;
    pendingAnchor = null;
    pendingAbout = null;
    pendingDrawing = null;
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
  function closeComposer() {
    leaveComposer(true);
    showFab(null, null, { returnFocus: "none" });
  }
  // The composer going down because its draft is spent rather than because the reader
  // dropped it: the words are somewhere else now, or on their way back.
  function settleComposer() {
    leaveComposer(false);
    showFab(null, null, { returnFocus: "none" });
  }

  // The response bar's Comment action returns to this same compact field on the anchor
  // the bar is carrying. It remains a button only while the choices are visible.

  // The one place a stored composer record becomes an open box. Startup reopens the most
  // recently touched draft through it, and the address below returns to that same record
  // mid-session; two hand-written copies of "what a record means" would be free to drift
  // about the mode a draft was written in.
  function openDraft(record = pendingComposer()) {
    if (!record) return false;
    openComposer(record.anchor, record.text, {
      suggest: Boolean(record.suggest),
      about: record.about ?? null,
      drawing: record.drawing ?? null,
    });
    return true;
  }

  // `g D`: the draft the composer put away, as a place. Hiding the box keeps its words and
  // the only route back was to reselect that exact passage on that exact version — durable
  // and unreachable, which is the same as lost for a reader who does not know where the
  // words went. A destination rather than a page letter: the page's alphabet is small, and
  // what this press does is travel to a passage and open the box standing on it, which is
  // what every other uppercase mnemonic in the sequence does with its own workspace.
  //
  // Dead while the composer is up, because then the draft is already in front of the
  // reader and `c` is the press that enters it. Live off the stored record rather than
  // this module's own state: a draft written in another tab, or before a reload, is the
  // same draft and answers the same address.
  //
  // Dead too where this version no longer holds the passage the draft is about. Those
  // words survive the version they were written against and come back when their passage
  // does; until then there is nowhere to stand the box, and a destination that lands
  // nowhere is worse than none.
  const KEPT_DRAFT = {
    id: "composer.kept-draft",
    keys: ["Shift+d"],
    does: "Go to the draft you have not sent",
    line: "your draft",
    when: () => !composerOpen && keptDraft() !== null,
    returnFrame: () => ({
      active: () => composerOpen,
      close: () => hideComposer(),
      does: "Return from the draft",
      line: "back",
    }),
    run: () => {
      const record = keptDraft();
      if (!record) return;
      // The box is placed against its passage, so the passage has to be somewhere the
      // reader can see before the box is measured — the same travel `c` makes to an item
      // it is about to open a box on.
      bringForward(anchorTargetAt(record.anchor));
      openDraft(record);
    },
  };

  function mount() {
    syncComposer = wireInput(composerInput, {
      hint: () =>
        suggestCheck.checked
          ? "Replacement text"
          : pendingAbout
            ? "About the layer"
            : "Comment…",
      sends: () => (suggestCheck.checked ? "suggest" : "comment"),
      sendBtn: composerSend,
      allowsMedia: () =>
        suggestCheck.checked
          ? "Images can be added to comments, not replacement text"
          : true,
      hasContent: holdsContent,
      save: saveComposerDraft,
      layout: refreshFab,
      send: async (_text, raw, owns, visible) => {
        const anchor = structuredClone(pendingAnchor);
        const ctx = composerCtx(anchor);
        const suggestion = suggestCheck.checked;
        const about = pendingAbout;
        const drawing = structuredClone(pendingDrawing);
        // The accepted comment becomes a thread card. Keep the last box the reader was
        // looking at so the inline card can carry that box into its new surface after the
        // draft settlement has removed the composer from the page.
        const transition = threadTransitionOrigin(composerInput, visible);
        const epoch = composerEpoch;
        const sent = sendMessage(
          ctx,
          () => composerCtx(pendingAnchor) === ctx && owns(),
          (attempt) => {
            const event = { anchor, attempt };
            if (raw) event.text = raw;
            if (suggestion) event.suggestion = true;
            if (about) event.about = about;
            if (drawing) event.drawing = drawing;
            return createComment(event);
          },
        );
        if (!sent) return;
        let reply = threadsBox.querySelector(
          `.lf-thread[data-id="${sent.id}"] textarea`,
        );
        // A later draft or selection keeps its focus. The accepted comment still belongs
        // in an open panel, including when revealing it must widen the panel's filter.
        const shouldLand =
          composerEpoch === epoch &&
          loadDraft(ctx) === null &&
          mayLandTyping(reply, composerInput);
        // Continue in the surface already in use. Closing an open panel here reflows the
        // passage just as the reader's comment moves across it to a new floating card.
        const inlineThread =
          shouldLand && !panelIsOpen() ? openInlineThread(sent.id, transition) : null;
        const inlineReply = inlineThread?.querySelector("textarea") ?? null;
        reply = inlineReply ?? reply;
        if (!inlineReply && (shouldLand || panelIsOpen())) {
          showThread(sent.id, { focus: shouldLand ? "reply" : false });
          reply ??= threadsBox.querySelector(
            `.lf-thread[data-id="${sent.id}"] textarea`,
          );
        }
        // The composer this was sent from is gone with the send; the thread it became
        // carries the same conversation, so its reply box is where typing continues.
        if (shouldLand) {
          landTyping(reply, composerInput);
        }
      },
    });
    suggestCheck.onchange = () => setSuggestionMode(suggestCheck.checked);
    fabSuggest.onclick = () => setSuggestionMode(!suggestCheck.checked);
    fabMore.onclick = () =>
      setResponseOptions(!responseOptionsOpen, {
        focus: responseOptionsOpen ? null : "first",
        returnFocus: responseOptionsOpen,
      });
    document.addEventListener("focusin", (event) => {
      if (responseOptionsOpen && !fabBar.contains(event.composedPath()[0]))
        setResponseOptions(false);
    });
    fab.onclick = () => {
      if (!fabAnchorAt()) return;
      openComposer(fabAnchorAt(), "");
    };
  }
  return {
    pendingComposer,
    keptDraft,
    composerHolds,
    setSuggestionMode,
    responseOptionsAreOpen,
    responseOptionsAvailable,
    responseOptionButtons,
    focusedResponseOption,
    responseReactionButtons,
    stepResponseOptions,
    setResponseOptions,
    syncResponseOptions,
    resetResponseOptions,
    openComposer,
    hideComposer,
    detachComposer,
    openDraft,
    KEPT_DRAFT,
    mount,
  };
}
