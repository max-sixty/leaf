/* Retained comment-panel list reconciliation.

   `renderThreads` holds one live card through every list mutation. It chooses the card
   under the pointer while the pointer is in the list, then the card containing focus,
   then the topmost visible card. It records later visible cards before the mutation
   and refreshes their baselines after each correction, so a live successor can take
   over if the first leaves or becomes hidden. The held `paintAcknowledgments` call
   covers claim-only mutations too. The list follows changes in the card's content
   position, keeping reflow out from under the pointer without fighting an intentional
   scroll. Browser scroll anchoring is disabled only for the life of a hold so those two
   authorities cannot compensate the same change; outside a held mutation the browser
   keeps its native safety net. The correction runs after each mutation and on every
   frame of a resolution fold; fold completion removes its node through
   `renderThreads`, under the same hold.

   `pageOutline` reads the page's own headings, and `groupFor` names the run of threads
   under each (conversation/placement.js). A run's heading is one node kept across
   reconciles and stuck to the top of the list while its run scrolls past. A stuck box
   is held by its margin edge inside the scroller's content, so the room above a
   heading is its own padding and the pin is drawn back over `--lf-list-inset`, the
   property the list spends its own inset from. A margin there, or a `top` of zero,
   leaves a strip the list scrolls through in full view.

   Being pinned is `.lf-pinned`, worn by the run headings and by the resolved
   disclosure's summary, which takes the slot from the last heading when the reader
   reaches it. One class carries the mechanics, so the slot cannot move in one of them;
   it is also what `renderThreads` sweeps to answer how much of the list's top stands
   covered. That answer is the one number in the list's `scroll-padding` that CSS
   cannot work out, because a long heading wraps — the tallest is written to
   `--lf-head-room`, and a `ResizeObserver` on the list writes it again when the reader
   draws the panel narrower and a heading wraps — a drag posts no event, so a reconcile
   never comes. Without it a walk lands threads under the heading with the opening
   words of the comment behind it, which is what
   `test_no_focus_ring_the_keyboard_lands_on_is_cut_or_covered` holds.

   The measurement is taken only while the panel is open, and this is a rule rather
   than an optimization. Shut, the panel is `display: none` and every heading measures
   zero, so the number written is not the room a heading takes but the absence of a
   panel. Taking it anyway costs a forced layout on every reconcile, for a page whose
   reader may never open the panel at all — and that cost is not notional: it delayed
   an event's acknowledgement past the window an undo is offered in, so a press the key
   line had just promised was refused, which
   `test_an_action_response_accounts_for_its_gesture_without_a_follow_up_poll` caught
   under a loaded machine and nowhere else. The observer covers the reopen, a box
   arriving being a resize, so the number is written at the first moment it can be
   right. A retained value from the last open panel is a real measurement and stands
   until then; the property is unset until the first open, where the `0px` fallback in
   the rule is the honest answer.

   Reserved room only reaches a control that lands in it, and a press lands nowhere:
   the browser focuses the card under the pointer and scrolls nothing. So the thread
   list lands a thread that takes the focus, whoever moved it, and that is the row the
   ownership map in skills/leaf/CLAUDE.md carries. Without it a list nudged a dozen pixels leaves the first
   card of a run under its own stuck heading by the width of an inset ring, which is a
   card with three sides. A press lands when it is over rather than as focus arrives,
   because focus arrives on the way down and the press may be the start of a drag
   across the comment's own words; a drag that ends in the thread takes no landing at
   all. What it lands is the thread the completed gesture leaves the reader in, not the
   one the focus moved to, so a press on the thread they are already standing in —
   which moves no focus — brings it back like any other.

   This is an arrival rule and not a promise about the paint. Scrolling the list under
   a standing thread cuts its ring again, and nothing re-lands it: the reader is moving
   away from what they were standing in, and a control under something is a fact about
   where it was put. A thread taller than the list's own scrollport is the excepted
   case in both directions — there is no scroll that shows all of it, which is the same
   thing the ring reading declines to report. Landing in a reply inside such a thread
   reveals its composer and actions together; an editor too tall to fit with its
   actions reveals the focused control itself.

   `test_no_ring_the_panel_draws_on_a_walk_down_its_list_is_cut_or_covered`,
   `test_a_comment_the_pointer_lands_on_comes_out_from_under_the_run_heading`, and
   `test_every_ring_the_layer_draws_is_shown_whole_somewhere_in_the_corpus` hold this
   for the panel's own walk, for a press inside its list, and for every shipped page's
   tab order. They ask one question: where the control can be seen, so can the ring
   that names it. A control that itself stands under a fixed bar is not a finding —
   that is a fact about where it was put — and neither is a box too tall for the region
   it is in. */
export function createConversationThreadList(dependencies) {
  const {
    ago,
    captureAuthoredFacets,
    cards,
    conversational,
    el,
    focused,
    folding,
    narrowing,
    openThreads,
    paintHere,
    panelIsOpen,
    placement,
    pointerAt,
    reachScrollers,
    refreshHover,
    runtime,
    scrollToElement,
    setChildren,
    settling,
    threadsBox,
    toggleBtn,
  } = dependencies;
  const { paintThreadQuotes, threadNode } = cards;
  const { foldOut, hasFolding, isFolding } = folding;
  const { inFilter, noMatchNote, paintNarrowing } = narrowing;
  const { groupFor, inPageOrder, pageOutline } = placement;

  const emptyNote = el(
    "div",
    "lf-empty",
    "No threads yet. Select any text on the page to comment on it, or use the box below.",
  );

  // The heading over a run of threads, kept across reconciles so a scroll position, a focus
  // ring and the sticky pin survive a poll. A button where the page still holds the heading
  // it names — pressing it takes the reader there, which is the same move a thread's quote
  // makes — and a plain line for the three runs that name no place (groupFor). A key never
  // changes kind, so the node a key holds never has to.
  const groupNodes = new Map();
  function groupNode(key, group) {
    let node = groupNodes.get(key);
    if (!node) {
      node = group.target
        ? el("button", "lf-group lf-pinned")
        : el("div", "lf-group lf-pinned");
      if (group.target) {
        node.type = "button";
        node.title = "Jump to this part of the page";
      }
      node.dataset.group = key;
      groupNodes.set(key, node);
    }
    if (node.textContent !== group.label) node.textContent = group.label;
    // The press is rewired on every reconcile and the word is not: a version activation
    // replaces the heading the group names with a new element, and the same sentence.
    if (group.target) node.onclick = () => scrollToElement(group.target);
    return node;
  }

  // A terminal event's row, keyed like everything else in the list so its clock can
  // refresh in place.
  function systemNode(e, text) {
    let div = threadsBox.querySelector(`:scope > .lf-system[data-id="${e.id}"]`);
    if (!div) {
      div = el("div", "lf-system");
      div.dataset.id = e.id;
    }
    if (div.textContent !== text) div.textContent = text;
    return div;
  }

  // The resolved disclosure, one <details> for the page's life: the user's
  // open/closed toggle is the browser's state, and it survives arrivals only if the
  // element does — the rebuild this replaced snapped it shut on every one.
  let resolvedBox = null;

  // The one number in the list's scroll-padding that CSS cannot work out: a run heading
  // sticks over the top of this box, and a long one wraps, so how much of the top is
  // covered is a measurement rather than a constant. The tallest, not the stuck one — the
  // browser is given one number to scroll by and cannot be told which heading will be under
  // the landing, and reserving more than a shorter heading needs only lands the thread a few
  // pixels lower.
  //
  // It follows the box rather than the log. Wrapping is a function of the list's width, and
  // the reader sets that themselves by dragging the panel's edge — a drag posts no event, so
  // a reconcile never came, and a heading that had grown from one line to two went on being
  // reserved for at one. Threads then landed under it, which is the whole defect this
  // number exists to prevent. Writing a custom property does not resize the observed box,
  // so the observer cannot feed itself.
  function paintHeadRoom() {
    // Not while the panel is shut, which is most of a page's life. Every heading measures
    // zero in `display: none`, so the answer is never the room a heading takes — it is the
    // absence of a panel, written at the cost of a forced layout on every reconcile for a
    // number no reader can be standing in. That cost is not theoretical: under a loaded
    // machine it delayed an event's acknowledgement past the window an undo is offered in,
    // and `test_an_action_response_accounts_for_its_gesture_without_a_follow_up_poll` lost
    // its press to a gesture that had not settled yet. The observer fires when the panel
    // opens — a box arriving is a resize — so the measurement lands the moment it means
    // something, which is also the only moment it can be right.
    if (!panelIsOpen()) return;
    const heads = [...threadsBox.querySelectorAll(".lf-pinned")];
    threadsBox.style.setProperty(
      "--lf-head-room",
      `${Math.max(0, ...heads.map((h) => h.offsetHeight))}px`,
    );
  }
  new ResizeObserver(paintHeadRoom).observe(threadsBox);

  // Keep one card at the same viewport position while this list changes around it.
  // The pointer is the most recent place the reader named; focus is the standing place
  // when the hand is elsewhere, and the first visible card is the list's own fallback.
  // Capture the later visible cards too, so removing the first choice can hand the hold
  // to the next card without trying to recover its old position after the mutation.
  let activeHold = null;
  const contentTop = (card) => card.getBoundingClientRect().top + threadsBox.scrollTop;
  // The box a card can hold the list's place by, or null where it can hold nothing: a
  // fold renames its node out of .lf-thread on the way out, a narrowing takes one off
  // the list, and a closed disclosure leaves one connected with no box to measure. One
  // statement of it, so what takes a hold and what corrects one cannot disagree over
  // which cards are still standing.
  const heldBox = (card) => {
    if (
      !card.isConnected ||
      !threadsBox.contains(card) ||
      !card.matches(".lf-thread") ||
      !card.checkVisibility()
    )
      return null;
    const box = card.getBoundingClientRect();
    return box.width && box.height ? box : null;
  };
  function takeScrollHold() {
    const priorHold = activeHold;
    if (priorHold) correctScrollHold(priorHold);
    activeHold = null;
    if (!panelIsOpen()) {
      threadsBox.style.removeProperty("overflow-anchor");
      return null;
    }
    const view = threadsBox.getBoundingClientRect();
    if (!view.width || !view.height) {
      threadsBox.style.removeProperty("overflow-anchor");
      return null;
    }
    const cards = [...threadsBox.querySelectorAll(".lf-thread")];
    const boxes = new Map(cards.map((card) => [card, card.getBoundingClientRect()]));
    const { x, y } = pointerAt();
    const overList =
      x >= view.left && x <= view.right && y >= view.top && y <= view.bottom;
    const underPointer = overList
      ? document.elementFromPoint(x, y)?.closest?.(".lf-thread")
      : null;
    const standing = focused()?.closest?.(".lf-thread");
    const visible = cards
      .filter((card) => {
        const box = boxes.get(card);
        return (
          card.checkVisibility() &&
          box.width &&
          box.height &&
          box.bottom > view.top &&
          box.top < view.bottom
        );
      })
      .sort((a, b) => boxes.get(a).top - boxes.get(b).top);
    // A fold is a mutation still running, and the hold that took it is the page's one
    // account of where the reader was standing when it started. The list slides both
    // ways around a folding card — the room closes under the cards below it and the
    // cards above come down into it — so the pointer stops naming that place as soon as
    // the motion begins: read again mid-fold it answers with whatever slid under it,
    // and a hold taken from that pins the wrong side of the movement while everything
    // past the fold, the successor the reader was aiming at among it, goes on moving.
    // A render arriving inside a fold therefore inherits the standing hold's own
    // reference, which has already handed off past the card that is leaving.
    const inherited = hasFolding()
      ? priorHold?.references.find(({ card }) => heldBox(card))?.card
      : null;
    const lead = inherited || underPointer || standing || visible[0];
    const leadAt = visible.indexOf(lead);
    const fallbacks =
      leadAt < 0
        ? visible
        : [...visible.slice(leadAt + 1), ...visible.slice(0, leadAt + 1)];
    const seen = new Set();
    const references = [inherited, underPointer, standing, ...fallbacks]
      .filter((card) => {
        if (!card || !threadsBox.contains(card) || seen.has(card)) return false;
        seen.add(card);
        return true;
      })
      .map((card) => ({
        card,
        contentTop: contentTop(card),
      }));
    if (!references.length) {
      threadsBox.style.removeProperty("overflow-anchor");
      return null;
    }
    activeHold = { references };
    // This hold is the sole scroll-anchor authority for its mutation. Leaving the
    // browser's independent anchor enabled can compensate the same reflow twice.
    threadsBox.style.setProperty("overflow-anchor", "none");
    return activeHold;
  }

  function releaseScrollHold(hold) {
    if (activeHold !== hold) return;
    activeHold = null;
    threadsBox.style.removeProperty("overflow-anchor");
  }

  function correctScrollHold(hold) {
    if (activeHold !== hold || !panelIsOpen()) return false;
    let box = null;
    const reference = hold.references.find(({ card }) => {
      box = heldBox(card);
      return box;
    });
    if (!reference) return false;
    // A card's viewport top moves both when content before it reflows and when the reader
    // scrolls. Adding scrollTop removes the second term, so this follows only reflow and
    // never fights a wheel, keyboard landing, narrowing reset, or scrollIntoView.
    const nextContentTop = box.top + threadsBox.scrollTop;
    const delta = nextContentTop - reference.contentTop;
    if (delta) threadsBox.scrollTop += delta;
    // Every fallback observed this frame's reflow too. Refresh all live baselines after
    // the correction, or handing off later would apply movement already paid for while
    // the primary stood.
    for (const candidate of hold.references) {
      const candidateBox = heldBox(candidate.card);
      if (candidateBox) candidate.contentTop = candidateBox.top + threadsBox.scrollTop;
    }
    return true;
  }

  function followScrollHold(hold) {
    if (!correctScrollHold(hold)) {
      releaseScrollHold(hold);
      return;
    }
    if (hasFolding()) requestAnimationFrame(() => followScrollHold(hold));
    else releaseScrollHold(hold);
  }

  function finishScrollHold(hold) {
    if (!hold) return;
    correctScrollHold(hold);
    if (hasFolding()) requestAnimationFrame(() => followScrollHold(hold));
    else releaseScrollHold(hold);
  }

  function holdScrollPosition(mutate) {
    const hold = takeScrollHold();
    try {
      return mutate();
    } finally {
      finishScrollHold(hold);
    }
  }

  // The DOM is the one record of what's rendered, reconciled against the log: nodes the
  // list already holds are kept, and only what the log changed is added, moved, or
  // dropped. The rebuild this replaced destroyed every node on every render and then
  // hand-restored the reader's place — scroll offset, focused thread, caret — and what
  // no restore could give back was identity: nothing could animate, one send route kept
  // focus and the other dropped it, and a user's own comment landed below the fold
  // of a list put back exactly where it was. Nodes surviving is what deleted all of it.
  function renderThreads(all) {
    return holdScrollPosition(() => reconcileThreads(all));
  }

  function reconcileThreads(all) {
    // The conversations. A bare reaction is paint on the page and a pill on the page
    // row, and counts for nothing here: no card, no address, no place in the walk.
    const threads = all.filter(conversational);
    const open = threads.filter((t) => !t.resolved);
    // The page's outline, read once for the whole reconcile: every thread asks it where it
    // stands and which run it belongs to.
    const outline = pageOutline();
    const group = new Map(threads.map((t) => [t, groupFor(t, outline)]));
    // Newcomers settle in (`grow`) only when the user already has the list in front
    // of them: the first populated render is the page loading, not news arriving, and a
    // node animated while the panel is closed would replay the moment it opens.
    // (Reduced motion isn't asked here: grow is a CSS animation, and those are the
    // theme's one global guard's to stop.)
    const grow =
      panelIsOpen() && Boolean(threadsBox.querySelector(":scope > .lf-thread"));

    // Where the reader's own narrowing applies, and the only place it does: the page's
    // marks, the inline conversation seats and the banner's count are readings of the log
    // and go on saying what the log says. What the panel shows is the panel's business.
    const shown = inPageOrder(threads).filter((t) => inFilter(t, group.get(t)));
    const resolved = shown.filter((t) => t.resolved);

    const wanted = [];
    if (!threads.length) wanted.push(emptyNote);
    else if (!shown.length) wanted.push(noMatchNote());
    // Walked in the page's order rather than the log's (inPageOrder), because that is the
    // order every other reading of these threads is in: the marks down the page and the walk
    // t/T makes. A thread on its way out still stands between its
    // neighbours while it folds (foldOut), which is why the walk is over the whole list
    // with the resolved ones taken at their own place. A folding thread is walked by nothing: the log
    // has already settled it, and only its room is still here.
    //
    // A heading goes in wherever the run changes, so the reader scrolling a list four
    // thousand pixels long is told which part of the page they are reading about — and,
    // the headings being sticky, is still told halfway down a long run.
    let standing = null;
    for (const t of shown) {
      // A resolved thread is either still giving its room back in place, or gone from this
      // list entirely and rebuilt under the disclosure below.
      const node = t.resolved ? foldOut(t) : threadNode(t, grow);
      if (!node) continue;
      const here = group.get(t);
      if (here.key !== standing) {
        standing = here.key;
        if (here.label) wanted.push(groupNode(here.key, here));
      }
      wanted.push(node);
    }
    for (const e of runtime.browser?.conversation?.done ?? [])
      wanted.push(systemNode(e, `✓ Approved ${ago(e.ts)}`));
    if (resolved.length) {
      if (!resolvedBox) {
        resolvedBox = el("details", "lf-details");
        resolvedBox.append(el("summary", "lf-pinned"));
      }
      const summary = resolvedBox.firstChild;
      // Counted off what the panel is showing, listed off the page: a thread still folding
      // out of the open list is resolved and says so in the count from the first frame, and
      // is rebuilt in here when its fold is done rather than standing in two places at
      // once. Under a narrowing the count is of the resolved threads that match it, for the
      // same reason the head says "Showing 3 of 24" — a disclosure promising five where the
      // list holds one is the trap the head exists to close.
      const said = `Resolved (${resolved.length})`;
      if (summary.textContent !== said) summary.textContent = said;
      setChildren(resolvedBox, [
        summary,
        ...resolved
          .filter((t) => !isFolding(t.root.id))
          .map((t) => threadNode(t, false)),
      ]);
      wanted.push(resolvedBox);
    }
    // A narrowing can take the thread the reader is standing in out of the list —
    // answering the last one waiting on the reader is exactly that — and a removed node drops
    // focus to body, which hands the next Space to the page behind the panel. Land them on
    // the list, where Escape lands them and t/T can walk on from.
    const standingIn = threadsBox.contains(focused());
    setChildren(threadsBox, wanted);
    if (standingIn && !threadsBox.contains(focused()))
      threadsBox.focus({ preventScroll: true });
    paintHeadRoom();
    // Frozen markup has the same initial-value boundary as a page: connected and
    // fully upgraded, before its first projection. Async widgets register their work
    // on connection, so take the settling queue after setChildren above. Later list
    // reconciles retain the first capture instead of adopting a reader's live value.
    const prepared = Promise.allSettled(settling).then(() => {
      captureAuthoredFacets(threadsBox);
      reachScrollers(threadsBox);
    });

    toggleBtn.textContent = `Threads (${open.length})`;
    paintNarrowing(open, shown);
    // The anchor pass wrote its record before this list existed, and this reconcile may have
    // built the nodes that wear it. Both passes therefore repaint it: the one that changes
    // the record, and the one that changes what the record is painted on.
    paintThreadQuotes();
    paintHere(); // the t/T and g rows, and an armed window's chips, stand on this list
    // Narrowing and reconciliation can move another card under a pointer that did not
    // move. Read :hover after the browser has laid out this list, in refreshHover's frame.
    refreshHover();
    return prepared;
  }

  return { holdScrollPosition, renderThreads };
}
