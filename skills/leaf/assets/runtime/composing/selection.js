export let pendingAnchor = null;
export let pendingAbout = null;
export let composerOpen = false;

export function createSelectionComposer(runtime, dependencies) {
  const {
    clearDraft,
    closeReactions,
    composer,
    composerInput,
    composerSend,
    designIsOn,
    draftContexts,
    elementById,
    fab,
    fabAnchor,
    fabBar,
    inChrome,
    landTyping,
    loadDraft,
    mayLandTyping,
    openInlineThread,
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
  } = dependencies;

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
      ["section", "quote", "prefix", "suffix", "part"].map(
        (key) => anchor?.[key] ?? "",
      ),
    );
  const saveComposerDraft = () =>
    saveDraft(
      composerCtx(pendingAnchor),
      JSON.stringify({
        text: composerInput.value,
        anchor: pendingAnchor,
        suggest: suggestCheck.checked,
        about: pendingAbout,
        touched: Date.now(),
      }),
    );
  // An open box the reader emptied keeps its record, which is what tells another tab's
  // composer on that passage that this one is merely empty rather than settled — and leaves
  // nothing to reopen on. So the draft to come back to is the most recently touched one
  // that still holds words.
  function pendingComposer() {
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
      if (record?.text && (!best || record.touched > best.touched)) best = record;
    }
    return best;
  }
  let inFlight = null;
  let composerEpoch = 0;
  const syncComposer = wireInput(composerInput, {
    hint: () =>
      suggestCheck.checked
        ? "Replacement text"
        : pendingAbout
          ? "About the layer"
          : "Comment…",
    sends: () => (suggestCheck.checked ? "suggest" : "comment"),
    sendBtn: composerSend,
    sendKey: "Enter",
    save: saveComposerDraft,
    layout: refreshFab,
    send: async (text, raw) => {
      const anchor = structuredClone(pendingAnchor);
      const ctx = composerCtx(anchor);
      const suggestion = suggestCheck.checked;
      const about = pendingAbout;
      const flight = { ctx, raw, epoch: composerEpoch };
      inFlight = flight;
      let sent;
      try {
        sent = await sendDraft(
          ctx,
          () => composerCtx(pendingAnchor) === ctx && composerInput.value === raw,
          (attempt) => {
            const event = {
              kind: "comment",
              revision: runtime.currentRevision,
              anchor,
              text,
              attempt,
            };
            if (suggestion) event.suggestion = true;
            if (about) event.about = about;
            return post(event);
          },
        );
      } finally {
        if (inFlight === flight) inFlight = null;
      }
      if (!sent) return;
      let reply = threadsBox.querySelector(`.lf-thread[data-id="${sent.id}"] textarea`);
      // A later draft or selection keeps its focus. The accepted comment still belongs
      // in an open panel, including when revealing it must widen the panel's filter.
      const shouldLand =
        composerEpoch === flight.epoch &&
        loadDraft(ctx) === null &&
        mayLandTyping(reply, composerInput);
      // Continue in the surface already in use. Closing an open panel here reflows the
      // passage just as the reader's comment moves across it to a new floating card.
      const inlineReply =
        shouldLand && !panelIsOpen() ? openInlineThread(sent.id) : null;
      reply = inlineReply ?? reply;
      if (!inlineReply && (shouldLand || panelIsOpen())) {
        showThread(sent.id, { stand: shouldLand });
        reply ??= threadsBox.querySelector(`.lf-thread[data-id="${sent.id}"] textarea`);
      }
      // The composer this was sent from is gone with the send; the thread it became
      // carries the same conversation, so its reply box is where typing continues.
      if (shouldLand) {
        landTyping(reply, composerInput);
      }
    },
  });
  // The composer's suggest-mode rendering — the offer of it, the button label and the
  // placeholder — derived from the standing state in one place, so the four paths that
  // set that state (toggle, open, close, another tab's keystroke) can't each restate
  // half of it. The placeholder itself is wireInput's to write; syncComposer repaints it
  // from the hint above.
  function syncSuggestMode() {
    // A suggestion is replacement text for a passage of the page; a remark about the
    // layer proposes no words, whatever it quotes.
    suggestRow.style.display = pendingAnchor?.quote && !pendingAbout ? "flex" : "none";
    composerSend.textContent = suggestCheck.checked ? "Suggest" : "Comment";
    syncComposer();
    paintHere(); // the line's send row says which of the two the box will do
  }
  function setSuggestionMode(suggest) {
    suggestCheck.checked = Boolean(suggest);
    // Entering suggestion mode seeds the box with the passage to edit in place.
    if (suggestCheck.checked && !composerInput.value.trim() && pendingAnchor?.quote) {
      composerInput.value = seededQuote = pendingAnchor.quote;
      syncComposer();
    }
    syncSuggestMode();
    saveComposerDraft();
    composerInput.focus({ preventScroll: true });
  }
  suggestCheck.onchange = () => setSuggestionMode(suggestCheck.checked);

  // Whether the composer is up, and the only thing that decides it. The stylesheet renders
  // this state; nothing reads it back, because the rendering has a third value the state
  // doesn't — display is "" before the first open, which is neither "block" nor "none", and
  // a guard testing for one of them ran on every mousedown in the page and swallowed the
  // click. Painting hangs off the same call, so the mark and the box are up together.
  function showComposer(open) {
    composerOpen = open;
    // The wrapper contributes no card or box. Its textarea is the extended Comment
    // control inside the response bar; the other composer controls stay hidden there.
    composer.style.display = open ? "contents" : "none";
    composer.toggleAttribute("data-lf-open", open);
    // An explicit Comment gesture focuses the textarea and drops the native selection, so
    // this mark then becomes the durable pointer to the quoted passage. Automatic passage
    // selection leaves both readings standing until the reader enters the field.
    paintAnchors();
    paintHere();
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
      carry = false,
      focus = true,
    } = {},
  ) {
    closeReactions();
    if (composerInput.value === seededQuote) composerInput.value = "";
    seededQuote = "";
    const ctx = composerCtx(anchor || null);
    const previousCtx = composerCtx(pendingAnchor);
    let carriedDraft = false;
    if (previousCtx !== ctx) {
      composerEpoch += 1;
      const previousText = composerInput.value;
      const leavesFlight =
        inFlight?.ctx === previousCtx && previousText === inFlight.raw;
      composerInput.value = "";
      // Automatic selection merely opens another passage's view. An explicit Comment
      // gesture may instead carry unsent words there, which preserves the old Alt-click
      // promise without making a reader's next selection silently re-anchor their draft.
      if (carry && previousText && !leavesFlight) {
        clearDraft(previousCtx);
        text ||= previousText;
        carriedDraft = true;
      } else {
        const held = text ? null : loadDraft(ctx);
        if (held) ({ text, suggest, about } = JSON.parse(held));
      }
    }
    pendingAnchor = anchor || null;
    pendingAbout = about;
    const target = pendingAnchor?.section ? elementById(pendingAnchor.section) : null;
    fabBar.dataset.lfPaintPlane = target && inChrome(target) ? "chrome" : "page";
    composerInput.value = text || composerInput.value;
    suggestCheck.checked = Boolean(suggest);
    syncSuggestMode();
    showComposer(true);
    showFab(anchor);
    syncComposer();
    if (focus) composerInput.focus();
    watchComposer();
    // Programmatic carrying fires no input event, so persist that one move explicitly.
    // An automatically opened empty field has no draft to save; its first edit does.
    if (carriedDraft) saveComposerDraft();
  }
  // The box is one view of the draft standing on this passage, and it follows the plain
  // boxes' rule with one thing of its own: the composer is chrome as well as a box, so a
  // draft settled in another tab — sent, or discarded — leaves it nothing to be open about
  // and it goes down. The subscription moves with the anchor, because the key does.
  let composerWatch = null;
  function watchComposer() {
    composerWatch?.();
    composerWatch = watchDraft(composerCtx(pendingAnchor), (value) => {
      if (value === null) return closeComposer();
      const { text, suggest, about } = JSON.parse(value);
      if (composerInput.value !== text) {
        composerInput.value = text;
        // Whatever stood here is another tab's words now, not this box's machine seed.
        seededQuote = "";
      }
      // The whole record, not the words alone: the mode a draft was written in rides with
      // it (pendingAbout, above), so a box taking up those words sends them under the word
      // they were written with. Design mode is this tab's and the draft's about is not.
      pendingAbout = about;
      suggestCheck.checked = Boolean(suggest);
      syncSuggestMode();
    });
  }
  // Hiding keeps the draft and closing discards it, but the mark goes down with the box
  // either way: a marked passage with no composer on screen points at nothing.
  const hideComposer = () => showComposer(false);
  function closeComposer() {
    clearDraft(composerCtx(pendingAnchor)); // before the anchor goes: the key is the anchor
    composerWatch?.();
    composerWatch = null;
    composerInput.value = "";
    seededQuote = "";
    suggestCheck.checked = false;
    pendingAnchor = null;
    pendingAbout = null;
    syncSuggestMode(); // after the state it renders, which is now all of it
    hideComposer();
    showFab(null, null, { returnFocus: "none" });
  }

  // The response bar's Comment action returns to this same compact field on the anchor
  // the bar is carrying. It remains a button only while the choices are visible.
  fab.onclick = () => {
    if (!fabAnchor()) return;
    openComposer(fabAnchor(), "");
  };
  return { hideComposer, openComposer, pendingComposer, setSuggestionMode };
}
