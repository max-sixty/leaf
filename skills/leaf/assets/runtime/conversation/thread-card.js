/* Retained comment-panel thread cards and their controls. */
export function createThreadCards(dependencies) {
  const {
    anchorLabel,
    el,
    focusThreadSurface,
    isMarked,
    keys,
    msgNode,
    openThreads,
    paintKeys,
    paintReactStrips,
    panelCovers,
    placedAt,
    PRESS,
    reachedForWords,
    retainPanelLanding,
    scrollToThread,
    setPanel,
    settlementControl,
    showThread,
    syncMsgNode,
    threadList,
    threadsBox,
    turns,
    wireReply,
  } = dependencies;
  const hasDestination = (id) => isMarked(id) || Boolean(placedAt(id));

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
        existing.querySelector(":scope > .lf-receipt") ??
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
    div.tabIndex = -1; // t/T focus target; the thread scope's Enter drops into its reply box
    div.dataset.id = t.root.id;
    if (grow) div.classList.add("grow");
    const label = anchorLabel(t.root.anchor, t.root.about);
    if (label) {
      const quote = el("blockquote", "lf-quote");
      quote.append(el("span", "lf-quote-label", label));
      quote.tabIndex = 0;
      quote.setAttribute("role", "button");
      // The quote is words and a press at once: it says which passage the comment is
      // about, and pressing it travels there. A drag across it is the reader taking the
      // words, so the travel stands down — the reading `offer` makes of its own
      // controls, which this is not one of.
      quote.onclick = (ev) => {
        if (ev.detail !== 0 && reachedForWords(quote)) return;
        // A covering sheet should spend itself only on a real return. `detached` cannot
        // answer that: a resolved thread has no painted mark but keeps the placement it
        // can still travel to. Read the anchor pass's two destination records instead.
        if (!hasDestination(t.root.id)) return;
        if (panelCovers()) setPanel(false);
        scrollToThread(t.root.id, {
          land: () => focusThreadSurface(t.root.id),
        });
      };
      keys(quote, "On a comment's quoted passage", [
        {
          id: "passage.return",
          keys: PRESS,
          does: "Return to the quoted passage on the page",
          line: "return to the passage",
          when: () => hasDestination(t.root.id),
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
      wireReply(t, input, send);
      const actions = el("div", "lf-thread-actions");
      // Resolving takes this node out of the open list and focus with it — the blind
      // drive fell to body here. Land where t would have gone: the thread that now
      // holds this one's place, else the previous, else the list. Which is read after
      // the trip, off the list the fold has already left (foldOut renames the node the
      // frame the log settles it), so the landing is a thread rather than the room the
      // pressed one is still giving back.
      const resolve = settlementControl(t, {
        prepareLanding: () => {
          const mayLand = retainPanelLanding(div);
          const at = openThreads().indexOf(div);
          return () => {
            if (!mayLand()) return;
            const kept = openThreads();
            (kept[at] ?? kept[at - 1] ?? threadsBox).focus({ preventScroll: true });
          };
        },
      });
      actions.append(send, resolve);
      row.append(actions);
      div.append(row);
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
      const reopen = settlementControl(t, {
        prepareLanding: () => {
          const mayLand = retainPanelLanding(div);
          return () => {
            if (mayLand()) showThread(t.root.id);
          };
        },
      });
      actions.append(status, reopen);
      div.append(actions);
    }
    return div;
  }

  // The panel's side of what the anchor pass drew, read off that pass's own record so the
  // two views can't disagree: a passage rewritten in a later version has no home to jump to,
  // and a dead-looking link is worse than one that says so. Called by the pass that writes
  // the record, and again by a narrowing that rebuilt the nodes the record was painted on.
  function paintThreadQuotes() {
    const threads = new Map(threadList().map((t) => [t.root.id, t]));
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
      const label = quote.querySelector(":scope > .lf-quote-label");
      if (said && label.textContent !== said) label.textContent = said;
      const outdated = placedAt(div.dataset.id)?.status === "outdated";
      let status = quote.querySelector(":scope > .lf-anchor-status");
      if (outdated && !status) {
        status = el("span", "lf-anchor-status", "Outdated");
        quote.append(status);
      } else if (!outdated) status?.remove();
      // Resolved threads deliberately carry no mark, but retain the placement their
      // folded quote can return to. One reading owns visual, assistive, keyboard, and
      // pointer availability so the same quote never becomes a pointer-only action.
      const found = hasDestination(div.dataset.id);
      quote.classList.toggle("detached", !found);
      quote.setAttribute("aria-disabled", String(!found));
      quote.title = found
        ? outdated
          ? "This comment refers to an earlier data revision"
          : "Jump to this passage"
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

  return { paintThreadQuotes, threadNode };
}
