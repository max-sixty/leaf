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
import { createConversationThreadList } from "./thread-list.js";
import { createAcknowledgments } from "./acknowledgments.js";

/* Conversation state and panel reconciliation. */
export function createConversation(dependencies) {
  const {
    FOLD_MS,
    MARKED_ANYWHERE,
    agentName,
    ago,
    buildReactSurface,
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
    mirrorDraft,
    motion,
    needsBtn,
    offer,
    pageParts,
    pageQueryAll,
    paintAnchors,
    paintHere,
    paintKeys,
    panelCovers,
    panelIsOpen,
    panelTitle,
    placedAt,
    pointerAt,
    post,
    PRESS,
    quietSince,
    reachScrollers,
    reachedForWords,
    reactDone,
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
    waitingForPickupSince,
    visualPartLabel,
    wireInput,
    withdraw,
  } = dependencies;
  // A reaction list owns the keyboard until it closes. Reconciliation can remove its
  // surface without a local gesture, so every removal path disarms it before detaching
  // the node; otherwise digits would keep acting on a reply no longer on screen.
  function removeNode(node) {
    if (node.matches?.(".lf-react-open") || node.querySelector?.(".lf-react-open"))
      reactDone();
    node.remove();
  }
  let threadList = [];
  let threadListRuntime;
  function renderThreads(...args) {
    return threadListRuntime.renderThreads(...args);
  }
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
    pageQueryAll,
    rememberAuthoredMarkup,
    renderQuiet,
    renderSaid,
    reportPageError,
    visualPartLabel,
    tokenEntry,
  });
  const { replyBoxHasDraft, wireReply } = createReplies({
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
    buildReactSurface,
    designIsOn,
    el,
    generalRow,
    isReaction,
    reactDone,
    removeNode,
    registry,
    runtime,
    sendReaction,
    withdraw,
  });
  const { paintPageStrip, paintReactStrips } = reactionStrips;

  // The open threads, in the order t/T walk. The list is the panel's own children rather
  // than a record kept beside them: a thread the log settles is renamed out of them in
  // that frame (foldOut), which takes it out of the walk and out of x's press in one
  // stroke.
  const openThreads = () => [...threadsBox.querySelectorAll(":scope > .lf-thread")];
  const placement = createThreadPlacement({
    inChrome,
    itemSays,
    itemWord,
    layerPart,
    pageParts,
    placedAt,
    sectionOf,
  });
  const { paintAcknowledgments: paintAcknowledgmentsUnheld } = createAcknowledgments({
    ago,
    claimState,
    droppedAt,
    el,
    elementById,
    inChrome,
    pageQueryAll,
    quietSince,
    runtime,
    threads: () => threadList,
    threadsBox,
    waitingForPickupSince,
  });
  function paintAcknowledgments(...args) {
    if (!threadListRuntime) return paintAcknowledgmentsUnheld(...args);
    return threadListRuntime.holdScrollPosition(() =>
      paintAcknowledgmentsUnheld(...args),
    );
  }

  const narrowing = createConversationNarrowing({
    anchorLabel,
    awaitsReader,
    el,
    findInput,
    needsBtn,
    paintAcknowledgments,
    panelTitle,
    renderThreads,
    runtime,
    threads: () => threadList,
    threadsBox,
  });
  const { narrowed, paintNarrowing, widen } = narrowing;
  const { revealThread, showThread } = createPanelLanding({
    reachedForWords,
    setPanel,
    threadsBox,
    widen,
  });
  const cards = createThreadCards({
    anchorLabel,
    el,
    isMarked,
    keys,
    msgNode,
    openThreads,
    paintKeys,
    paintReactStrips,
    panelCovers,
    placedAt,
    post,
    PRESS,
    reachedForWords,
    revealThread,
    scrollToThread,
    setPanel,
    showThread,
    syncMsgNode,
    threadList: () => threadList,
    threadsBox,
    turns,
    wireReply,
  });
  const folding = createThreadFolding({
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
    for (const child of [...parent.children]) if (!keep.has(child)) removeNode(child);
    let cursor = parent.firstChild;
    for (const node of nodes) {
      if (node === cursor) cursor = cursor.nextSibling;
      else parent.insertBefore(node, cursor);
    }
  }

  const waitingNote = el("div", "lf-empty", "Loading current threads…");

  const { renderConversations, renderMarginThread } = createInlineConversations({
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
  threadListRuntime = createConversationThreadList({
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
  });

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

  // The panel and the page marks are two views of the same threads, and the paint pass
  // reports back to the list renderThreads just reconciled — always render them as a pair.
  function renderPanel() {
    if (runtime.statePhase !== "ready") {
      waitingNote.textContent =
        runtime.statePhase === "offline"
          ? "Current threads are unavailable while the server is offline."
          : "Loading current threads…";
      setChildren(threadsBox, [waitingNote]);
      toggleBtn.textContent = "Threads";
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
    paintAcknowledgments();
  }

  return {
    buildThreads,
    bareReaction,
    reactionsOn,
    loadMarked,
    anchorLabel,
    openThreads,
    narrowed,
    awaitsReader,
    setChildren,
    paintAcknowledgments,
    widen,
    paintThreadQuotes: cards.paintThreadQuotes,
    renderMarginThread,
    renderPanel,
    replyBoxHasDraft,
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
