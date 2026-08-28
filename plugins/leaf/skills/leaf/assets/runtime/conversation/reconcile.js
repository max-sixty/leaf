import { createThreadModel } from "./model.js";
import { createThreadFolding } from "./folding.js";
import { createInlineConversations } from "./inline.js";
import { createPanelLanding } from "./landing.js";
import { createConversationMessages } from "./messages.js";
import { createConversationNarrowing } from "./narrowing.js";
import { createThreadPlacement } from "./placement.js";
import { createConversationReactionStrips } from "./reaction-strips.js";
import { createReplies } from "./replies.js";
import { createThreadCards } from "./thread-card.js";
import { createWorkLines } from "./work-lines.js";

/* Conversation state and panel reconciliation. */
export function createConversation(dependencies) {
  const {
    COMMENTS,
    FOLD_MS,
    MARKED_ANYWHERE,
    addressLabel,
    addressed,
    agentName,
    ago,
    captureAuthoredFacets,
    claimState,
    designIsOn,
    designName,
    droppedAt,
    el,
    elementById,
    findInput,
    focused,
    generalRow,
    highlightBlocks,
    inChrome,
    isMarked,
    itemSays,
    itemWord,
    keys,
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
    paintKeys,
    panelIsOpen,
    panelTitle,
    placedAt,
    post,
    PRESS,
    quietSince,
    reachScrollers,
    reachedForWords,
    reactDone,
    reactPills,
    refreshHover,
    registry,
    rememberAuthoredMarkup,
    renderQuiet,
    renderSaid,
    reportPageError,
    runtime,
    saveDraft,
    scrollToElement,
    scrollToThread,
    sectionOf,
    sendDraft,
    sendReaction,
    setPanel,
    settling,
    tellDraft,
    threadsBox,
    toggleBtn,
    updateSequence,
    visualPartLabel,
    wireInput,
    withdraw,
  } = dependencies;
  let threadList = [];
  const {
    awaitsAgent,
    awaitsReader,
    bareReaction,
    buildThreads,
    conversational,
    isReaction,
    reactionsOn,
    spoken,
    seatRoot,
    tokenEntry,
    turns,
  } = createThreadModel({
    registry,
    runtime,
  });
  const {
    anchorLabel,
    loadMarked,
    msgBody,
    msgNode,
    renderMessageMarkdown,
    syncEdited,
    syncMsgNode,
  } = createConversationMessages({
    MARKED_ANYWHERE,
    ago,
    captureAuthoredFacets,
    designName,
    el,
    elementById,
    highlightBlocks,
    isReaction,
    itemSays,
    itemWord,
    markDeclared,
    rememberAuthoredMarkup,
    renderQuiet,
    renderSaid,
    reportPageError,
    visualPartLabel,
    tokenEntry,
  });
  const { wireReply } = createReplies({
    landTyping,
    loadDraft,
    mirrorDraft,
    post,
    runtime,
    saveDraft,
    sendDraft,
    tellDraft,
    wireInput,
  });
  const reactionStrips = createConversationReactionStrips({
    bareReaction,
    designIsOn,
    el,
    generalRow,
    isReaction,
    reactDone,
    reactPills,
    registry,
    runtime,
    sendReaction,
    withdraw,
  });
  const { paintPageStrip, paintReactStrips } = reactionStrips;

  // The open threads, in the order j/k walk and `g c` addresses. The list is the panel's own
  // children rather than a record kept beside them: a thread the log settles is renamed out
  // of them in that frame (foldOut), which takes it out of the walk, out of the addresses and
  // out of x's press in one stroke. A map of id → address stood here once, written by
  // renderThreads and read back by the chip and the placeholder — one list held twice, and
  // the copy free to be a reconcile behind the panel it described.
  const openThreads = () => [...threadsBox.querySelectorAll(":scope > .lf-thread")];
  const { groupFor, inPageOrder, pageOutline } = createThreadPlacement({
    inChrome,
    itemSays,
    itemWord,
    layerPart,
    pageParts,
    placedAt,
    sectionOf,
  });
  const { paintWorkLines } = createWorkLines({
    agentName,
    ago,
    claimState,
    droppedAt,
    el,
    elementById,
    inChrome,
    matchesWhen,
    pageQueryAll,
    quietSince,
    registry,
    runtime,
    threads: () => threadList,
    threadsBox,
    updateSequence,
  });

  const narrowing = createConversationNarrowing({
    anchorLabel,
    awaitsReader,
    el,
    findInput,
    needsBtn,
    paintWorkLines,
    panelTitle,
    renderThreads,
    runtime,
    threads: () => threadList,
    threadsBox,
  });
  const { inFilter, narrowed, noMatchNote, paintNarrowing, widen } = narrowing;
  const { revealThread, showThread } = createPanelLanding({
    reachedForWords,
    setPanel,
    threadsBox,
    widen,
  });
  const { threadNode } = createThreadCards({
    COMMENTS,
    addressLabel,
    addressed,
    anchorLabel,
    el,
    keys,
    msgNode,
    openThreads,
    paintKeys,
    paintReactStrips,
    post,
    PRESS,
    reachedForWords,
    revealThread,
    scrollToThread,
    showThread,
    syncMsgNode,
    threadsBox,
    turns,
    wireReply,
  });
  const { foldOut, isFolding } = createThreadFolding({
    FOLD_MS,
    motion,
    renderPanel,
    threadsBox,
  });

  // The reconcile's one mover, shared by the list and the resolved disclosure: make
  // `parent`'s children `nodes`, in that order, touching nothing already in its place.
  // Not touching it matters beyond economy: reinserting a node restarts its CSS
  // animations, drops any focus and caret inside it, and swaps it out from under a
  // pressed pointer, which swallows the click. Stale nodes go first for the same
  // reason — with one removed mid-list, everything after it is exactly one place
  // forward, so the walk keeps those where they stand instead of reinserting each.
  function setChildren(parent, nodes) {
    const keep = new Set(nodes);
    for (const child of [...parent.children]) if (!keep.has(child)) child.remove();
    let cursor = parent.firstChild;
    for (const node of nodes) {
      if (node === cursor) cursor = cursor.nextSibling;
      else parent.insertBefore(node, cursor);
    }
  }

  const emptyNote = el(
    "div",
    "lf-empty",
    "No comments yet. Select any text on the page to comment on it, or use the box below.",
  );
  const waitingNote = el("div", "lf-empty", "Loading current comments…");

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

  const { renderConversations } = createInlineConversations({
    ago,
    el,
    elementById,
    focused,
    loadDraft,
    offer,
    registry,
    renderMessageMarkdown,
    seatRoot,
    setChildren,
    showThread,
    syncEdited,
    turns,
    wireReply,
  });

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

  // The DOM is the one record of what's rendered, reconciled against the log: nodes the
  // list already holds are kept, and only what the log changed is added, moved, or
  // dropped. The rebuild this replaced destroyed every node on every render and then
  // hand-restored the reader's place — scroll offset, focused thread, caret — and what
  // no restore could give back was identity: nothing could animate, one send route kept
  // focus and the other dropped it, and a user's own comment landed below the fold
  // of a list put back exactly where it was. Nodes surviving is what deleted all of it.
  function renderThreads(all) {
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
    // order every other reading of these threads is in: the marks down the page, the walk
    // j/k makes, the digits g c spells. A thread on its way out still stands between its
    // neighbours while it folds (foldOut), which is why the walk is over the whole list
    // with the resolved ones taken at their own place. The first nine open threads are
    // addressable (g c 1–9), in the order j/k walk; past nine, digits stop and j/k still
    // reach everything. A folding thread takes no address and is walked by nothing: the log
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
    // the list, where Escape lands them and j/k can walk on from.
    const standingIn = threadsBox.contains(focused());
    setChildren(threadsBox, wanted);
    if (standingIn && !threadsBox.contains(focused()))
      threadsBox.focus({ preventScroll: true });
    paintHeadRoom();
    // A thread's widget markup is authored too, but it arrives after the page's startup
    // capture. Take its baseline on the first frame it is connected, before a reader can
    // act on it; later reconciles keep the first capture rather than mistaking a live
    // choice for authored state. Thread markup is frozen in its event, so unlike page
    // markup it has no version window to move under.
    captureAuthoredFacets(threadsBox);
    // A comment carries whatever widget markup the gate allows, so the panel holds the
    // same scroll boxes the page does, in a column half the width — and reachScrollers
    // wants two things that are only true here, after this line. A message body is built
    // detached, where `getComputedStyle` answers "" for every property, so a sweep at the
    // point the body is filled tagged nothing at all and had done since it was written,
    // reading like coverage the whole time. And a widget in that body upgrades on being
    // connected, not on being written, so the queue it registers its render with
    // (`settling`) has the promise only once this reconcile has appended it — which is
    // why the wait is here rather than a snapshot taken earlier. The queue is read, never
    // joined: nothing about the page's own first anchor pass waits on a message.
    Promise.allSettled(settling).then(() => reachScrollers(threadsBox));

    // Each reply box speaks its own address, repainted after ordering because resolving an
    // early thread renumbers everything after it — and read off the list this reconcile has
    // just written, which is why the loop is here and not where the boxes were built.
    for (const div of openThreads()) div.lfSync();
    toggleBtn.textContent = `Comments (${open.length})`;
    paintNarrowing(open, shown);
    // The anchor pass wrote its record before this list existed, and this reconcile may have
    // built the nodes that wear it. Both passes therefore repaint it: the one that changes
    // the record, and the one that changes what the record is painted on.
    paintThreadQuotes();
    paintHere(); // the j/k and g rows, and an armed window's chips, stand on this list
    // Narrowing and reconciliation can move another card under a pointer that did not
    // move. Read :hover after the browser has laid out this list, in refreshHover's frame.
    refreshHover();
  }

  // An unresolved hold thread is the pause. Derive the mark from the thread fold so
  // resolution removes it and undo restores it without a second state store.
  function renderHolds(threads) {
    for (const node of document.querySelectorAll("[data-lf-held]"))
      node.removeAttribute("data-lf-held");
    for (const thread of threads) {
      if (thread.resolved || !thread.root.holds) continue;
      const target = elementById(thread.root.holds);
      if (target && !inChrome(target)) target.dataset.lfHeld = thread.root.id;
    }
  }

  // The panel's side of what the anchor pass drew, read off that pass's own record so the
  // two views can't disagree: a passage rewritten in a later version has no home to jump to,
  // and a dead-looking link is worse than one that says so. Called by the pass that writes
  // the record, and again by a narrowing that rebuilt the nodes the record was painted on.
  function paintThreadQuotes() {
    const threads = new Map(threadList.map((t) => [t.root.id, t]));
    for (const div of threadsBox.querySelectorAll(".lf-thread")) {
      const quote = div.querySelector(".lf-quote");
      if (!quote) continue;
      // The words too, for the same reason the class below is repainted here rather than
      // written where the node was built. An element anchor is labelled with its item's
      // own opening words, and the item may be a widget an agent sent — built by this
      // same reconcile and not yet in the document when the node wearing the label was
      // made, so the reading came back empty and the label fell to the bare id. The
      // reconcile keeps a node it has already built, so nothing else ever asked again:
      // `§ off-slip` stood where `§ options · If their release comes and goes…` belonged,
      // for the life of the tab.
      const thread = threads.get(div.dataset.id);
      const said = thread && anchorLabel(thread.root.anchor, thread.root.about);
      if (said && quote.textContent !== said) quote.textContent = said;
      const found = isMarked(div.dataset.id);
      quote.classList.toggle("detached", !found);
      quote.setAttribute("aria-disabled", String(!found));
      quote.title = found
        ? "Jump to this passage"
        : "This passage can't be identified in the version you're viewing";
    }
    paintKeys();
  }

  // A kept node may still be moved by a later reconcile, and reinsertion restarts CSS
  // animations — so the class comes off the moment its animation has run. A node grown
  // while its list was off-screen never ran one; the panelOpen gate above is what keeps
  // that replay from greeting the panel's next open.
  threadsBox.addEventListener("animationend", (ev) =>
    ev.target.classList.remove("grow"),
  );

  // The panel and the page marks are two views of the same threads, and the paint pass
  // reports back to the list renderThreads just reconciled — always render them as a pair.
  function renderPanel() {
    if (runtime.statePhase !== "ready") {
      waitingNote.textContent =
        runtime.statePhase === "offline"
          ? "Current comments are unavailable while the server is offline."
          : "Loading current comments…";
      setChildren(threadsBox, [waitingNote]);
      toggleBtn.textContent = "Comments";
      // Nothing read yet, so nothing to count and nothing to narrow. The same writer, so
      // the button says exactly what it will say the moment the log arrives empty.
      paintNarrowing([], []);
      threadList = [];
      paintHere();
      return;
    }
    const threads = buildThreads();
    renderHolds(threads);
    threadList = threads.filter(conversational);
    // The marks first, because the list is ordered by where they landed: one resolution of
    // every anchor, read by the page for its paint and by the panel for its order. Resolving
    // a second time for the order would be a second answer to where a thread is, free to
    // disagree with the first over a page that changed between them — and it would walk the
    // document's whole text again to say it.
    paintAnchors(threads);
    renderThreads(threads);
    renderConversations(threadList);
    paintPageStrip(threads);
    paintWorkLines();
  }

  return {
    buildThreads,
    bareReaction,
    reactionsOn,
    loadMarked,
    anchorLabel,
    openThreads,
    narrowed,
    awaitsAgent,
    awaitsReader,
    seatRoot,
    setChildren,
    paintWorkLines,
    widen,
    paintThreadQuotes,
    syncReplyAddresses: () => {
      for (const thread of threadsBox.querySelectorAll(":scope > .lf-thread"))
        thread.lfSync?.();
    },
    renderPanel,
    showThread,
    get threadList() {
      return threadList;
    },
    get needsYou() {
      return narrowing.needsYou;
    },
    get pageStrip() {
      return reactionStrips.pageStrip;
    },
  };
}
