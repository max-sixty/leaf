import { createThreadModel } from "./model.js";
import { createConversationMessages } from "./messages.js";
import { createThreadPlacement } from "./placement.js";
import { createWorkLines } from "./work-lines.js";

/* Conversation folding and panel reconciliation. */
export function createConversation(dependencies) {
  const {
    COMMENTS,
    FOLD_MS,
    MARKED_ANYWHERE,
    scrollBehavior,
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
    panelCovers,
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
    retractedIds,
    retractionFloors,
    runtime,
    saveDraft,
    scrollToElement,
    scrollToThread,
    sectionOf,
    sendDraft,
    sendReaction,
    setPanel,
    settling,
    takenBack,
    tellDraft,
    threadsBox,
    threadMarkupAwaiting,
    toggleBtn,
    updateSequence,
    visualPartLabel,
    wireInput,
    withdraw,
  } = dependencies;
  let threadList = [];
  const markupAwaiting = new Map();
  const {
    awaitsAgent,
    awaitsReader,
    bareReaction,
    buildThreads,
    conversational,
    isReaction,
    reactionStanding,
    reactionsOn,
    spoken,
    seatRoot,
    tokenEntry,
    turns,
  } = createThreadModel({
    elementById,
    registry,
    retractedIds,
    retractionFloors,
    runtime,
    takenBack,
    markupAwaiting: (message) => markupAwaiting.get(message.id) ?? null,
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

  // ---------- narrowing the list ----------
  // Two narrowings, and they compose: the words a reader is looking for, and whether the
  // thread is one the agent has left with them. Neither is stored — see the find row's own
  // comment for why a remembered narrowing is the trap rather than the convenience.
  //
  // Whose turn a thread is (`awaitsReader`) belongs to the model rather than to this file,
  // because the banner's ask count asks the same question from the other side: a request
  // whose own conversation is with the agent is not the reader's to deal with. The panel
  // saying so while the banner went on counting the ask was one fact told two ways.
  let finding = "";
  let needsYou = false;
  const narrowed = () => Boolean(finding) || needsYou;

  // What a search reads: everything the panel shows of a thread, plus the part of the page
  // it is on — so "merge rule" finds the threads under that heading as well as the ones
  // that say the words. The label is the panel's own rendering of the anchor, which is what
  // the reader can see and therefore what they would search for.
  const threadWords = (t, group) =>
    [
      anchorLabel(t.root.anchor, t.root.about),
      group.label,
      ...t.msgs.map((m) => m.text ?? m.token),
    ]
      .join("\n")
      .toLowerCase();

  const inFilter = (t, group) =>
    (!needsYou || awaitsReader(t)) &&
    (!finding || threadWords(t, group).includes(finding));

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
  // The page has comments and the reader's narrowing is standing between them and it. It
  // names the narrowing rather than saying nothing was found, because the reader may have
  // arrived here from a key or from a second tab and what is on screen has to say why.
  const noMatch = el("div", "lf-empty");
  function noMatchNote() {
    const said = finding
      ? needsYou
        ? `Nothing waiting on you says “${finding}”.`
        : `No comment says “${finding}”.`
      : "Nothing is waiting on you.";
    if (noMatch.textContent !== said) noMatch.textContent = said;
    return noMatch;
  }

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

  // A thread has one send in flight even though its reply draft has two views. wireInput's
  // private hold is still the right scope for every other composer, which has one control;
  // a reply adds this thread-scoped hold and announces it on the document bus so both Send
  // controls render the same fact. The promise is the post itself, because a queue would
  // serialize the duplicate rather than refuse it.
  const REPLY_FLIGHT_NEWS = "lf-reply-flight";
  const replyFlights = new Map(); // thread id -> post in flight
  const replyBusy = (id) => replyFlights.has(id);
  const tellReplyFlight = (id) =>
    document.dispatchEvent(new CustomEvent(REPLY_FLIGHT_NEWS, { detail: { id } }));

  function mirrorReplyFlight(ta, sync, id) {
    const update = (ev) => {
      if (ev.detail.id !== id) return;
      if (!ta.isConnected)
        return document.removeEventListener(REPLY_FLIGHT_NEWS, update);
      sync();
    };
    document.addEventListener(REPLY_FLIGHT_NEWS, update);
  }

  async function sendReply(t, text, raw, owns) {
    const id = t.root.id;
    if (replyBusy(id)) return null;
    const draftCtx = "reply:" + id;
    const flight = sendDraft(draftCtx, owns, (attempt) =>
      post({
        kind: "reply",
        parent: id,
        revision: runtime.currentRevision,
        text,
        attempt,
      }),
    );
    replyFlights.set(id, flight);
    tellReplyFlight(id);
    try {
      return await flight;
    } finally {
      replyFlights.delete(id);
      tellReplyFlight(id);
    }
  }

  // One reply draft and one send path, however many views the thread has. The panel adds
  // an address and reveals the sent message; an inline conversation supplies neither.
  // Everything else — persistence, mirroring, the wire event and the focus landing — is
  // the thread's and is therefore stated once.
  function wireReply(t, input, send, { address, landed } = {}) {
    const draftCtx = "reply:" + t.root.id;
    input.value = loadDraft(draftCtx) ?? "";
    const sync = wireInput(input, {
      hint: "Reply",
      sends: "send",
      address,
      sendBtn: send,
      busy: () => replyBusy(t.root.id),
      // localStorage notifies other tabs but skips this document. A conversation's
      // inline and panel boxes are two views here, so reply drafts take the same bus
      // directly. Other draft kinds still have one view per document.
      save: (v) => {
        saveDraft(draftCtx, v);
        tellDraft(draftCtx, v);
      },
      send: async (text, raw) => {
        const sent = await sendReply(t, text, raw, () => input.value === raw);
        if (!sent) return;
        landed?.(sent);
        landTyping(input);
      },
    });
    sync();
    mirrorDraft(input, sync, draftCtx);
    mirrorReplyFlight(input, sync, t.root.id);
    return sync;
  }

  function conversationMessageNode(thread, message) {
    let node = thread.querySelector(
      `:scope > .lf-conversation-msg[data-event="${message.id}"]`,
    );
    if (node) {
      const time = node.querySelector("time");
      const when = ago(message.ts);
      if (time.textContent !== when) time.textContent = when;
      syncEdited(node.querySelector(":scope > .lf-conversation-head"), message);
      const body = node.querySelector(":scope > .lf-conversation-body");
      const revision = message.edited?.id ?? "";
      if (node.lfRevision !== revision) {
        if (message.suggestion) body.textContent = message.text;
        else body.innerHTML = renderMessageMarkdown(message.text);
        node.lfRevision = revision;
      }
      return node;
    }
    node = offer("div", `lf-conversation-msg ${message.author}`);
    node.dataset.event = message.id;
    const head = el("div", "lf-conversation-head");
    head.append(
      el("b", "", message.author === "claude" ? message.agent || "Agent" : "You"),
      el("time", "", ago(message.ts)),
    );
    syncEdited(head, message);
    const body = el("div", "lf-conversation-body");
    if (message.suggestion) body.textContent = message.text;
    else body.innerHTML = renderMessageMarkdown(message.text);
    node.lfRevision = message.edited?.id ?? "";
    node.append(head, body);
    if (message.markup) {
      const open = offer("button", "lf-btn lf-conversation-open", "Open in Comments");
      open.onclick = () => showThread(message.id);
      node.append(open);
    }
    return node;
  }

  function conversationThreadNode(host, t) {
    let thread = host.querySelector(
      `:scope > .lf-conversation-thread[data-thread="${t.root.id}"]`,
    );
    if (!thread) {
      thread = offer("div", "lf-conversation-thread");
      thread.dataset.thread = t.root.id;
      thread.tabIndex = -1;
    }
    // Turns only: a reaction on a message is the panel's strip to show, and the seat is
    // the textual projection of the exchange.
    const messages = turns(t).map((message) =>
      conversationMessageNode(thread, message),
    );
    let tail;
    if (t.resolved) {
      const compose = thread.querySelector(":scope > .lf-say");
      if (compose?.contains(focused())) thread.focus({ preventScroll: true });
      tail = thread.querySelector(":scope > .lf-conversation-resolved");
      const settledBy =
        t.resolved.author === "claude"
          ? `✓ Resolved by ${t.resolved.agent || "Agent"}`
          : "✓ Resolved";
      if (!tail) tail = offer("div", "lf-conversation-resolved");
      if (tail.textContent !== settledBy) tail.textContent = settledBy;
    } else if (t.root.response?.kind === "version") {
      // The page seat shows what the reader proposed. Their reply workspace remains
      // in Comments; the agent's response is the next authored version.
      tail = null;
    } else {
      tail = thread.querySelector(":scope > .lf-say");
      if (!tail) {
        tail = offer("div", "lf-say");
        const input = offer("textarea");
        const send = offer("button", "lf-btn primary", "Send");
        tail.append(input, send);
        wireReply(t, input, send);
      }
    }
    const work = thread.querySelector(":scope > .lf-work-line");
    setChildren(thread, [
      ...messages,
      ...(work ? [work] : []),
      ...(tail ? [tail] : []),
    ]);
    return thread;
  }

  function renderConversations(threads) {
    for (const host of document.querySelectorAll(
      ".lf-conversation[data-lf-conversation]",
    )) {
      const owner = elementById(host.dataset.lfConversation);
      const owned = threads.filter((thread) => seatRoot(thread) === owner.id);
      // Before the first comment, conversationBox's first-message composer is already
      // the complete view. An externally arriving root may find unsent first-message
      // words here, so the root does not get to take their only box. A hold-capable seat
      // stays reachable after every root so an ordinary conversation cannot remove the
      // stronger send route.
      if (!owned.length) continue;
      const first = host.lfFirstMessage;
      const hold = registry[owner.localName]?.["x-conversation"]?.hold;
      const pending = hold || loadDraft("say:" + owner.id) !== null ? first : null;
      const work = host.querySelector(":scope > .lf-work-line");
      setChildren(host, [
        ...(work ? [work] : []),
        ...owned.map((thread) => conversationThreadNode(host, thread)),
        ...(pending ? [pending] : []),
      ]);
    }
  }

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

  // A thread's node is found where it already stands — the open list or the resolved
  // disclosure — and kept: the log is append-only, so a kept node only ever gains
  // messages and refreshes its clocks. A settlement transition reshapes a node: resolving
  // removes the reply box and reopening restores it, so either one rebuilds the node;
  // msgBodies carries the rendered bodies across. `grow` animates what this call creates,
  // for arrivals into a list the user is already looking at.
  function threadNode(t, grow) {
    const existing = threadsBox.querySelector(`.lf-thread[data-id="${t.root.id}"]`);
    const existingResolved =
      existing && !existing.querySelector(":scope > .lf-compose");
    if (existing && existingResolved === Boolean(t.resolved)) {
      const compose = existing.querySelector(":scope > .lf-compose");
      const tail =
        existing.querySelector(":scope > .lf-work-line") ??
        compose ??
        existing.querySelector(":scope > .lf-thread-actions");
      for (const m of turns(t)) {
        let msg = existing.querySelector(`:scope > .lf-msg[data-mid="${m.id}"]`);
        if (!msg) {
          msg = msgNode(m);
          if (grow) msg.classList.add("grow");
          existing.insertBefore(msg, tail);
        }
        syncMsgNode(msg, m);
      }
      paintReactStrips(existing, t);
      return existing;
    }

    const div = el("div", "lf-thread");
    div.tabIndex = -1; // j/k focus target; the thread scope's Enter drops into its reply box
    div.dataset.id = t.root.id;
    if (grow) div.classList.add("grow");
    const label = anchorLabel(t.root.anchor, t.root.about);
    if (label) {
      const quote = el("blockquote", "lf-quote", label);
      quote.tabIndex = 0;
      quote.setAttribute("role", "button");
      // The quote is words and a press at once: it says which passage the comment is
      // about, and pressing it travels there. A drag across it is the reader taking the
      // words, so the travel stands down — the reading `offer` makes of its own
      // controls, which this is not one of.
      quote.onclick = (ev) => {
        if (ev.detail !== 0 && reachedForWords(quote)) return;
        // Beside the page, the panel is a working index and stays standing. As a
        // covering sheet it would hide the destination it promises to show, so travel
        // dismisses it first and lands on visible paper.
        if (panelCovers()) setPanel(false);
        scrollToThread(t.root.id);
      };
      keys(quote, "On a comment's quoted passage", [
        {
          id: "passage.return",
          keys: PRESS,
          does: "Return to the quoted passage on the page",
          line: "return to the passage",
          when: () => !quote.classList.contains("detached"),
          run: () => quote.click(),
        },
      ]);
      div.append(quote);
    }
    turns(t).forEach((m) => div.append(msgNode(m)));
    paintReactStrips(div, t);
    if (!t.resolved) {
      const row = el("div", "lf-compose");
      const input = document.createElement("textarea");
      const send = el("button", "lf-btn primary lf-thread-send", "Send");
      row.append(input);
      div.lfSync = wireReply(t, input, send, {
        // The box's address, spoken by its own placeholder at all times ("Reply · g c 2")
        // — which is what a screen reader hears, the chip the chord paints being the eye's
        // copy of the same fact. Read off the list rather than off a number written here,
        // because the address is positional: resolving an early thread renumbers every one
        // after it without touching their nodes, and renderThreads repaints them all.
        address: () => {
          const num = addressed(COMMENTS).indexOf(div) + 1;
          return num ? addressLabel(COMMENTS, num) : "";
        },
        landed: (sent) => revealThread(sent.id),
      });
      const actions = el("div", "lf-thread-actions");
      const resolve = el("button", "lf-btn lf-resolve", "Resolve");
      // Resolving takes this node out of the open list and focus with it — the blind
      // drive fell to body here. Land where j would have gone: the thread that now
      // holds this one's place, else the previous, else the list. Which is read after
      // the trip, off the list the fold has already left (foldOut renames the node the
      // frame the log settles it), so the landing is a thread rather than the room the
      // pressed one is still giving back.
      // Disabled for the flight (the bulk-answer buttons' shape): the r key repeats while
      // held, and every repeat before the poll replaces this node would post the
      // same resolve again. Re-enabled for the one path that keeps the node — a
      // send that failed, where the press must stay pressable; where it went through,
      // the fold has made the whole node inert and there is nothing to re-enable into.
      resolve.onclick = async () => {
        const at = openThreads().indexOf(div);
        resolve.disabled = true;
        paintKeys();
        try {
          await post({ kind: "resolve", parent: t.root.id });
        } finally {
          resolve.disabled = false;
          paintKeys();
        }
        const kept = openThreads();
        (kept[at] ?? kept[at - 1] ?? threadsBox).focus({ preventScroll: true });
      };
      keys(resolve, "On a thread's Resolve button", [
        {
          id: "thread.resolve",
          keys: [...PRESS, "x"],
          does: "Resolve it",
          line: "resolve",
          when: () => !resolve.disabled,
          run: () => resolve.click(),
        },
      ]);
      actions.append(send, resolve);
      div.append(row, actions);
    } else {
      const actions = el("div", "lf-thread-actions");
      const status = el("span");
      if (t.resolved.author === "claude") {
        // Said only where the reader was not the one who closed it. Their own resolve
        // needs no telling: they pressed it, and the disclosure they find it under is
        // already headed "Resolved". A thread closed from the other side settles with
        // nothing in this tab to watch it happen, so the page is the only thing that can
        // say who did.
        const by = t.resolved.agent || "Agent";
        status.append(el("span", "lf-resolved-by", `✓ Resolved by ${by}`));
      }
      const reopen = el("button", "lf-reopen lf-thread-action", "Reopen");
      reopen.onclick = async () => {
        reopen.disabled = true;
        paintKeys();
        try {
          await post({ kind: "unresolve", parent: t.root.id });
        } finally {
          reopen.disabled = false;
          paintKeys();
        }
        threadsBox
          .querySelector(`:scope > .lf-thread[data-id="${t.root.id}"]`)
          ?.focus({ preventScroll: true });
        showThread(t.root.id);
      };
      keys(reopen, "On a resolved thread", [
        {
          id: "thread.reopen",
          keys: [...PRESS, "x"],
          does: "Reopen it",
          line: "reopen",
          when: () => !reopen.disabled,
          run: () => reopen.click(),
        },
      ]);
      actions.append(status, reopen);
      div.append(actions);
    }
    return div;
  }

  // The strip under each of the agent's messages: every token the layer declares, the
  // ones the reader has put on that message reading pressed and wearing their word.
  // Press one to put it there — a reply carrying the token, on that message — and press it
  // again to take it back, an ordinary undo naming the reply. Rebuilt from the thread on
  // each reconcile rather than from the press, so a reaction arriving from another tab,
  // and an undo, land the same way. A resolved thread offers none: resolve is the floor
  // after which a reaction stops painting, on the page and here alike.
  // Open — every token offered — on the latest agent message, which is the one `r`
  // arms and the one a `settles` token answers. The rest of the thread keeps the tokens
  // standing on it and offers its own row only while the reader is standing in the
  // thread (the stylesheet), so a thread at rest wears one row rather than one a turn.
  function paintReactStrips(node, t) {
    const latest = t.msgs.findLast((x) => x.author === "claude")?.id ?? null;
    for (const msg of node.querySelectorAll(":scope > .lf-msg")) {
      const m = t.msgs.find((x) => x.id === msg.dataset.mid);
      if (!m || m.author !== "claude") continue;
      let strip = msg.querySelector(":scope > .lf-react-strip");
      if (t.resolved) {
        strip?.remove();
        continue;
      }
      if (!strip) {
        strip = el("div", "lf-react-strip");
        strip.setAttribute("role", "group");
        strip.setAttribute("aria-label", "React to this reply");
        for (const pill of reactPills((name, pill) => pressStrip(m, name, pill)))
          strip.append(pill);
        msg.append(strip);
      }
      strip.classList.toggle("lf-open", m.id === latest);
      paintStanding(
        strip,
        t.msgs.filter((x) => isReaction(x) && x.author === "user" && x.parent === m.id),
      );
    }
  }
  // Which tokens stand on a target, painted on its strip: pressed, wearing the word, and
  // carrying the event a second press takes back. The reaction rides the pill rather than
  // a map beside it, so a reconcile that keeps the node keeps the fact with it.
  function paintStanding(strip, standing) {
    const by = new Map(standing.map((x) => [x.token, x]));
    for (const pill of strip.querySelectorAll(":scope > .lf-react")) {
      const on = by.get(pill.dataset.token) ?? null;
      pill.setAttribute("aria-pressed", on ? "true" : "false");
      pill.lfReaction = on;
    }
  }
  async function pressStrip(m, name, pill) {
    if (pill.lfReaction) await withdraw(pill.lfReaction);
    else
      await sendReaction(
        { kind: "reply", parent: m.id, revision: runtime.currentRevision, token: name },
        pill,
        `${m.agent || "the agent"}'s reply`,
      );
    reactDone();
  }
  // The page whole, from the panel: the same strip, above the general box, aimed at
  // nothing in particular — the shape an unanchored comment already has. What stands
  // here is every bare reaction with no anchor; a press puts one there or takes it back.
  let pageStrip = null;
  function paintPageStrip(threads) {
    if (!Object.keys(registry.$reactions.tokens).length) return;
    if (!pageStrip) {
      pageStrip = el("div", "lf-react-strip lf-page-strip lf-open");
      pageStrip.setAttribute("role", "group");
      pageStrip.setAttribute("aria-label", "React to the page");
      for (const pill of reactPills(pressPage)) pageStrip.append(pill);
      generalRow.before(pageStrip);
    }
    paintStanding(
      pageStrip,
      threads
        .filter((t) => bareReaction(t) && !t.resolved && !t.root.anchor)
        .map((t) => t.root),
    );
  }
  // About the layer in design mode, as the general box's own comment is: the subject is
  // decided at the send, by the mode standing then.
  async function pressPage(name, pill) {
    if (pill.lfReaction) {
      await withdraw(pill.lfReaction);
      reactDone();
      return;
    }
    const event = { kind: "comment", revision: runtime.currentRevision, token: name };
    if (designIsOn()) event.about = "layer";
    await sendReaction(event, pill, "the page");
    reactDone();
  }

  // A thread the log has resolved and the open list is still holding. Its place is not
  // given up in the frame the log settles it: the node stays where it stood, says what
  // was done to it on the control that was pressed, and folds, so the threads under it
  // rise where the eye can follow instead of arriving somewhere else. The disclosure
  // gets the thread when the fold is over, which is what keeps one node per thread the
  // whole way through.
  //
  // Driven from the reconcile rather than from the press, because the log is what
  // resolves a thread and a resolve with no gesture behind it — a second tab's, or the
  // agent's — takes the same room out of the same list. That is the case that needs the
  // motion more: nothing in this tab moved, so the fold is the only thing saying so.
  //
  // Everything that walks the list asks for .lf-thread, so the one rename takes the
  // node out of j/k, out of the g addresses, out of x's press and out of what the panel
  // repaints, in a stroke: what stands there is room, not a thread. `inert` says the
  // same to the pointer and the tab order, so the fold can't be pressed a second time
  // or typed into on its way out.
  //
  // Null where there is nothing to fold: a thread this page never drew open, or a
  // reader who asked for less motion, for whom the room goes in the frame it always did.
  const folding = new Map(); // thread id -> the node folding out of the open list
  function foldOut(t) {
    const going = folding.get(t.root.id);
    // For as long as it stands in the list, which is the whole of what the record
    // claims. A reader who reopens a thread mid-fold has that render drop the folding
    // node from the list, and the entry left behind names a node in nothing: handed
    // back when they settle the thread again, it would stand a spent animation where
    // the thread is, saying what the thread said before it reopened, and the thread
    // would leave with no fold at all. The node's own connectedness is that fact, read
    // here rather than written from wherever a node leaves the list, which is the
    // difference between one writer and every caller of setChildren remembering.
    // Dropped rather than passed over, because the two returns below leave without
    // setting one, and an entry over a thread nothing is folding hides that thread
    // from the disclosure that should be holding it by then.
    if (going?.isConnected) return going;
    folding.delete(t.root.id);
    const node = threadsBox.querySelector(
      `:scope > .lf-thread[data-id="${t.root.id}"]`,
    );
    if (!node) return null;
    // Measured before anything about the node changes, and stated as a border box —
    // the measurement to hand is the rendered one, and .lf-going sizes to match. The
    // border and padding go with the height because border-box floors the box at
    // their sum: left standing, they would hold 22px open under a height of zero.
    const style = getComputedStyle(node);
    const from = {
      height: node.getBoundingClientRect().height + "px",
      marginBottom: style.marginBottom,
      borderTopWidth: style.borderTopWidth,
      borderBottomWidth: style.borderBottomWidth,
      paddingTop: style.paddingTop,
      paddingBottom: style.paddingBottom,
      opacity: 1,
    };
    const to = Object.fromEntries(Object.keys(from).map((k) => [k, "0px"]));
    to.opacity = 0;
    const played = motion(node, [from, to], FOLD_MS);
    if (!played) return null;
    // The control the press was made on states the outcome where it stood. It needs no
    // reservation for the longer word: Send and Resolve hold the two edges, so the
    // longer outcome takes room from the gap and moves neither edge. Send stays in the
    // row with visibility hidden, keeping the same room without reading as live.
    node.querySelector(":scope > .lf-thread-actions > .lf-resolve").textContent =
      "✓ Resolved";
    node.className = "lf-going";
    node.inert = true;
    // A key on screen is a key that works, and this box's placeholder was still
    // offering the address the thread under it has just taken: the repaint every other
    // reply box gets is the trailing loop's, which asks for .lf-thread and so no longer
    // finds this one. Painted here, from the same map, at the one moment the answer
    // changes — the address is gone the frame the log settles the thread, and what the
    // box says on its way out is "Reply" and no promise.
    node.lfSync();
    folding.set(t.root.id, node);
    // Straight off the promise, and nothing between: motion() holds the last keyframe
    // while this direct reaction makes that frame true by removing the node, then its
    // shared reaction releases the effect. Deferring this cleanup past that contract
    // would put the whole thread back before it goes. What holds the line is
    // test_the_fold_never_paints_a_frame_that_undoes_the_last, since no held frame can
    // see it.
    played.finished.then(() => {
      // This node's own entry, never whatever the thread's key holds now: a fold the
      // line above superseded is still running, and the older one finishing must not
      // take the live one's record with it.
      if (folding.get(t.root.id) === node) folding.delete(t.root.id);
      node.remove();
      renderPanel();
    });
    return node;
  }

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

    // A structured reply asks through its x-awaits widgets. Project the last reply bodies
    // before applying the panel's narrowing, so a new question cannot be excluded before
    // its markup has had a chance to admit the thread. Stage only the cached bodies, never
    // complete hidden thread cards: building a card wires its reply box to document-level
    // draft and flight listeners, and a filtered card has no node the next reconcile can
    // reuse. Each body keeps skeletal thread/message ancestry while connected: widget
    // setup may read its message timestamp or card geometry, and upgrades only once before
    // the cache moves it into the lasting card. Connection lets the shared action fold
    // find widget ids and distinguish an open request from one the reader already answered.
    // The stage leaves synchronously, before a frame can expose it.
    const markupReplies = [];
    for (const t of open) {
      const last = spoken(t).at(-1);
      if (last?.kind !== "reply") continue;
      if (!last.markup) {
        markupAwaiting.set(last.id, null);
        continue;
      }
      markupReplies.push({ reply: last, thread: t });
    }
    const bodies = markupReplies.map(({ reply }) => msgBody(reply));
    const stage = el("div", "lf-thread-stage");
    bodies.forEach((body, index) => {
      if (body.isConnected) return;
      const { reply, thread } = markupReplies[index];
      const skeleton = el("div", "lf-thread");
      skeleton.dataset.id = thread.root.id;
      skeleton.append(msgNode(reply));
      stage.append(skeleton);
    });
    if (stage.childElementCount) {
      threadsBox.append(stage);
      captureAuthoredFacets(stage);
    }
    const readings = threadMarkupAwaiting(bodies);
    markupReplies.forEach(({ reply }, index) =>
      markupAwaiting.set(reply.id, readings[index]),
    );
    stage.remove();
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
    for (const e of runtime.events) {
      if (e.kind === "done") wanted.push(systemNode(e, `✓ Approved ${ago(e.ts)}`));
    }
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
          .filter((t) => !folding.has(t.root.id))
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

  // The two surfaces that say what the narrowing is doing, written together because they
  // are one fact told twice: how much of the conversation is in front of the reader, and
  // how much of it is still theirs to answer. One writer, so the phase before the log has
  // been read and the phase after it cannot come to spell the same state differently.
  //
  // The banner counts what the page has; the head says how much of that is on screen. They
  // differ only while a narrowing stands, which is exactly when the reader needs telling
  // that the list is not the whole of it — and there is nothing to tell where the page has
  // no open threads to narrow.
  function paintNarrowing(open, shown) {
    const showing = shown.filter((t) => !t.resolved).length;
    panelTitle.textContent =
      narrowed() && open.length ? `Showing ${showing} of ${open.length}` : "Comments";
    const waiting = open.filter(awaitsReader).length;
    needsBtn.textContent = waiting ? `Waiting on you (${waiting})` : "Waiting on you";
    // Pressable while it stands pressed, so the reader can always let it go; dead only when
    // there is nothing for it to show and it is not the thing hiding the list.
    needsBtn.disabled = !needsYou && !waiting;
  }

  // Re-render the list alone, for the one change that is the panel's own rather than the
  // log's: the reader narrowing it. Nothing about the page moved, so the anchor pass is not
  // asked again — the list is rebuilt from the record it already wrote.
  function renarrow() {
    if (runtime.statePhase !== "ready") return;
    renderThreads(threadList);
    paintWorkLines();
    // A new set of results starts at its own beginning. Keeping the old offset lands the
    // reader in the middle of a shorter list, or past the end of it, over a change they
    // made a keystroke at a time.
    threadsBox.scrollTop = 0;
  }
  findInput.addEventListener("input", () => {
    finding = findInput.value.trim().toLowerCase();
    renarrow();
  });
  needsBtn.onclick = () => {
    needsYou = !needsYou;
    needsBtn.setAttribute("aria-pressed", String(needsYou));
    needsBtn.classList.toggle("on", needsYou);
    renarrow();
  };
  // Everything the reader narrowed, let go at once — what Escape in the find box does, and
  // what a thread arriving from outside the narrowing needs before it can be revealed.
  function widen() {
    if (!narrowed()) return false;
    finding = "";
    needsYou = false;
    findInput.value = "";
    needsBtn.setAttribute("aria-pressed", "false");
    needsBtn.classList.remove("on");
    renarrow();
    return true;
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

  // Landing belongs to the list, not to whatever moved the focus. The list already says
  // which of its own edges cannot be stood on — `scroll-padding`, room for a stuck
  // heading and for a ring — and every route that could reach a thread was scrolling it
  // into that band for itself, so a route that did not scroll got nothing. A press does
  // not: the browser focuses the card under the pointer and scrolls nothing, so a list
  // nudged a dozen pixels leaves the first card of a run two pixels under its heading,
  // which is the whole of an inset ring's top run and reads as a card with three sides.
  // The routes that resolve a thread rather than press one — a page mark's comment note,
  // the thread a resolve or a reopen hands the reader on to — landed only by chance of
  // having remembered the line.
  //
  // Focus is the one fact all of them share, so the landing hangs off that and each of
  // them gives up its copy. Four callers still write this list's scroll, and each says
  // something focus cannot: `stepThread` for the press at either end of the walk, which
  // moves no focus at all; `revealThread` for a deliberate centring, which runs after
  // the focus it follows and wins; `placeThreadEdge` for an explicit edge placement;
  // and `landIn`, which puts the reader in a thread's box and lands the thread around it,
  // the same correction this makes and the reason a reply box reached by key was never
  // the case that was wrong.
  //
  // The thread holding the focus, not the card alone: the ring is the thread's, drawn
  // for `:focus-within`, so it is cut in the same place whether the reader is standing
  // on the card or writing in its box. `block: "nearest"` moves the least that clears
  // the band, so a control at the card's foot comes with it rather than going under.
  //
  // A press is the reader's hand, and it may be the start of a drag across the comment's
  // own words. Focus lands on the way down, so scrolling there takes the words out from
  // under the pointer and the selection runs on past where they stopped — measured at
  // three times the run the reader drew. A press therefore holds its landing until the
  // hand comes up, and gives it up altogether where the press was a drag for the
  // thread's own words: the question `offer` already asks of a click, read the same way,
  // since the selection's focus end is the character the button came up on.
  //
  // The hand comes up before the press's click, which is where a deliberate placement
  // begins — a quote jumping to its passage, a travel centring a widget in a reply. So
  // the order holds without a word between them: the landing is a correction under the
  // gesture, and whatever the gesture then asks for is later and wins.
  //
  // What the press lands is where it left the reader, which is not the same question as
  // which thread the focus moved to. A press on the thread the reader is already in
  // moves no focus and so was heard as nothing at all — and that is the reader's own
  // gesture: they are standing in a comment, the list carries a little, and they press
  // the card to bring it back. Asking the completed gesture instead of the focus event
  // costs a variable rather than buying one, and the walk's own end-of-clamp press is
  // the same shape one scope out.
  let pressing = false;
  const standing = () => focused()?.closest?.(".lf-thread");
  const land = (thread) => {
    if (thread && threadsBox.contains(thread))
      thread.scrollIntoView({ behavior: scrollBehavior(), block: "nearest" });
  };
  threadsBox.addEventListener("pointerdown", () => (pressing = true));
  addEventListener(
    "pointerup",
    () => {
      const began = pressing;
      pressing = false;
      const thread = began && standing();
      if (thread && !reachedForWords(thread)) land(thread);
    },
    true,
  );
  threadsBox.addEventListener("focusin", () => {
    if (!pressing) land(standing());
  });

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

  // One answer to "show me that thread", whoever asks: a click on a mark out on the page
  // and a send that just landed both come here, with a thread's id or a message's. The
  // panel scrolls its own list — moving the page to a thread's passage is scrollToThread,
  // a different question — and flashes the thread. The flash takes over from a running
  // grow explicitly: both classes bind the element's one animation declaration, and the
  // send's confirmation is the one the gesture asked for.
  const listNode = (id) =>
    threadsBox.querySelector(`.lf-thread[data-id="${id}"], .lf-msg[data-mid="${id}"]`);

  function revealThread(id) {
    setPanel(true);
    const node = listNode(id);
    if (!node) return;
    const thread = node.closest(".lf-thread");
    node.scrollIntoView({
      behavior: scrollBehavior(),
      block: node === thread ? "center" : "nearest",
    });
    thread.classList.remove("grow");
    thread.classList.add("flash");
    setTimeout(() => thread.classList.remove("flash"), 1300);
  }

  // The same ask, insisted on. Two callers mean the thread has to be on screen and cannot
  // see the narrowing they would be asking past: a press out on the page or in a message,
  // which knows nothing of the panel at all, and a comment the reader has just written,
  // which cannot be allowed to vanish into a narrowing it does not match. So the narrowing
  // goes rather than the thread.
  //
  // Every other reveal is a confirmation of something the reader was already watching — a
  // reply landing in a thread in front of them — and takes the list as it stands. A
  // narrowing that let go for having been used would be worse than one that hid something:
  // answering a thread is exactly how the reader empties the waiting-on-you list.
  function showThread(id) {
    setPanel(true);
    if (!listNode(id)) widen();
    // Showing a thread is an arrival in the panel, not a glimpse from the page. Focus is
    // the standing fact shared by the card and its mark, so the route that begins on a
    // painted passage has to end on the same focus target as j/k and the address chord.
    // preventScroll keeps this call out of the scroll: the list lands a thread that takes
    // the focus, and the reveal below is the deliberate placement that follows and wins.
    listNode(id)?.closest(".lf-thread")?.focus({ preventScroll: true });
    revealThread(id);
  }

  return {
    buildThreads,
    bareReaction,
    paintStanding,
    reactionsOn,
    reactionStanding,
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
      return needsYou;
    },
    get pageStrip() {
      return pageStrip;
    },
  };
}
