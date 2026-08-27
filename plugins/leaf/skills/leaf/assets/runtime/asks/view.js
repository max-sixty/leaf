export function createAskView({
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
  elementById,
  inChrome,
  itemSays,
  itemWord,
  openAsks,
  openTray,
  paintAnchors,
  paintHere,
  paintKeys,
  panelIsOpen,
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
}) {
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
  let shortcutsOffered = false;
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
    // they write. A capability change also moves the tray edge's machine-readable keys.
    const offered = asksOffered();
    if (offered !== shortcutsOffered) {
      shortcutsOffered = offered;
      paintKeys();
    } else paintHere();
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
  // page, and the row for a question that survived the revision is the same row. That is
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
  // The ask the reader is standing in: the one holding the focus, or the one a control
  // hoisted into the margin decides. The innermost of them, an ask being able to hold
  // another (a question inside a suggestion's lf-new) — the list answers in document order,
  // so the last container in the list is the nearest one.
  //
  // The unanswered asks rather than the reader's list, because standing in a question is
  // about where the reader is working and not about what they owe. The two part on a widget
  // whose own seat is mid-conversation with the agent: it leaves the list while its pick
  // stays unmade and its controls stay live, and reading the list took the ring off that
  // widget and moved `c` from the seat the reader was writing in down to whichever option
  // their focus rested on — a second thread on the child rather than the next line of their
  // own. The agent's reply put both back. Nothing the reader did moved either. An answered
  // ask parts from neither list: its question is settled, so there is nothing left there to
  // be standing in, and a settled group goes on being named by its own words.
  //
  // document.activeElement rather than focused(), for the reason askPosition gives: a
  // control staged in a shadow tree retargets to its host, and the host is the place in the
  // document this wants.
  function standingIn() {
    const held = document.activeElement;
    if (!held || held === document.body) return null;
    const place = askPlace(held);
    return (
      unansweredAsks().findLast((ask) => ask === place || ask.contains(place)) ?? null
    );
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
    if (inChrome(next) && !panelIsOpen()) setPanel(true);
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

  const landedAt = () => landed;
  const setLanded = (value) => (landed = value);
  return {
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
  };
}
