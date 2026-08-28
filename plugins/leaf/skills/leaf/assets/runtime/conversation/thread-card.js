/* Retained comment-panel thread cards and their controls. */
export function createThreadCards(dependencies) {
  const {
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
  } = dependencies;

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
        if (ev.detail === 0 || !reachedForWords(quote)) scrollToThread(t.root.id);
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

  return { threadNode };
}
