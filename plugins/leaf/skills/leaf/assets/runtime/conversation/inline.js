/* Textual conversation views rendered outside the retained Threads list. */
export function createInlineConversations({
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
}) {
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
      const open = offer("button", "lf-btn lf-conversation-open", "Open in Threads");
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
      // in Threads; the agent's response is the next authored version.
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

  function renderMarginThread(host, thread) {
    const node = conversationThreadNode(host, thread);
    setChildren(host, [node]);
    return node;
  }

  return { renderConversations, renderMarginThread };
}
