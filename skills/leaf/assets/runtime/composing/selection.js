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
    fab,
    fabAnchor,
    landTyping,
    loadDraft,
    mayLandTyping,
    openInlineThread,
    paintAnchors,
    paintHere,
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
      // A later edit is still the reader's standing gesture. The earlier comment may
      // render in another conversation view, but it may not close or move the composer
      // holding that edit.
      if (composerEpoch !== flight.epoch || loadDraft(ctx) !== null) return;
      let reply = threadsBox.querySelector(`.lf-thread[data-id="${sent.id}"] textarea`);
      const shouldLand = mayLandTyping(reply, composerInput);
      // Opening an inline view closes the panel and moves focus. Decide from the standing
      // view first, so a later gesture in another reply box survives an earlier send.
      const inlineReply = shouldLand ? openInlineThread(sent.id) : null;
      reply = inlineReply ?? reply;
      if (!inlineReply) {
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
    // The reader's own selection is gone by now — focusing a textarea drops it — so this
    // mark is the only thing left pointing at the passage being quoted.
    paintAnchors();
    paintHere();
  }

  // The quote suggestion mode auto-seeded, so reopening on a new anchor can tell
  // machine seed from user text: the seed belongs to its old anchor and is dropped;
  // anything the user typed or edited rides forward — never lose user text.
  let seededQuote = "";
  // `about` defaults to the mode standing at the open — a composer opened in design mode
  // is about the layer — and a restored draft passes the word it was saved with.
  function openComposer(
    anchor,
    text,
    left,
    top,
    suggest = false,
    about = designIsOn() ? "layer" : null,
  ) {
    closeReactions();
    if (composerInput.value === seededQuote) composerInput.value = "";
    seededQuote = "";
    const ctx = composerCtx(anchor || null);
    const previousCtx = composerCtx(pendingAnchor);
    if (previousCtx !== ctx) composerEpoch += 1;
    // Re-anchoring while this exact value is being sent is a new response gesture, not
    // an edit of the submitted words on a different passage. Leave the sending draft at
    // its original coordinate so a failed request can recover it, and start the new
    // field clean. The eventual success settles that original generation in place.
    const leavesFlight =
      previousCtx !== ctx &&
      inFlight?.ctx === previousCtx &&
      composerInput.value === inFlight.raw;
    if (leavesFlight) composerInput.value = "";
    // A draft already standing on this passage is what the box opens with — one left hidden
    // here, or one being typed in another tab — unless the caller brought words of its own
    // or the box is already carrying some.
    const held = text || composerInput.value ? null : loadDraft(ctx);
    if (held) ({ text, suggest, about } = JSON.parse(held));
    // The draft moves with the box, and one draft is one record: the passage the words were
    // on lets go of them as they arrive on the next one. A press that re-anchors an open
    // draft is where this lands, and a key left standing there would hand the same words
    // back on the old passage at the next load.
    if (previousCtx !== ctx && !leavesFlight) clearDraft(previousCtx);
    pendingAnchor = anchor || null;
    pendingAbout = about;
    composerInput.value = text || composerInput.value;
    suggestCheck.checked = Boolean(suggest);
    syncSuggestMode();
    showComposer(true);
    showFab(anchor);
    syncComposer();
    composerInput.focus();
    watchComposer();
    // The store hears about the anchor now, not at the next keystroke: saving only on
    // input left a re-anchored draft stored against the anchor the press had just moved
    // it off, and a reload between the press and the next character quietly un-made the
    // move.
    saveComposerDraft();
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
    const anchor = fabAnchor();
    const { left, top } = fab.getBoundingClientRect();
    openComposer(anchor, "", left, top);
  };
  return { hideComposer, openComposer, pendingComposer, setSuggestionMode };
}
