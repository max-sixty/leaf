/* Interaction-scoped acknowledgment receipts and explicit work claims. */
export function createAcknowledgments(dependencies) {
  const {
    ago,
    claimState,
    droppedAt,
    el,
    elementById,
    inChrome,
    pageQueryAll,
    quietSince,
    runtime,
    threads,
    threadsBox,
    waitingForPickupSince,
  } = dependencies;

  const phaseText = (receipt) => {
    if (receipt.phase === "active")
      return receipt.detail ? `● Active — ${receipt.detail}` : "● Active";
    if (receipt.phase === "picked_up") return "✓ Picked up";
    return waitingForPickupSince(receipt.ts) ? "○ Waiting for pickup" : "✓ Sent";
  };

  // One retained node follows one reader move through every semantic phase. Only a
  // phase/detail change touches its live region; the heartbeat updates the separate
  // clock without making a screen reader repeat the state every two seconds. A phase
  // change is a change of words and paint and nothing else: motion here would answer
  // a question the reader already asked, and an animation the line wore would replay
  // on any move the heartbeat made (below).
  function paintReceipt(host, receipt, before, wanted) {
    if (!host) return;
    let line = [...host.children].find(
      (child) => child.matches(".lf-receipt") && child.dataset.receiptId === receipt.id,
    );
    if (!line) {
      line = el("div", "lf-receipt lf-ui");
      line.dataset.lfGen = "1";
      line.dataset.receiptId = receipt.id;
      const state = el("span", "lf-receipt-state");
      state.setAttribute("role", "status");
      state.setAttribute("aria-live", "polite");
      state.setAttribute("aria-atomic", "true");
      line.append(state, el("time"));
    }
    // `before` names the slot the line belongs in by the node standing there now, and
    // for an event-backed line that node is the line itself once it has been placed.
    // Inserting a node before itself is a move that changes nothing, but the platform
    // still takes it out of the document and puts it back — cancelling and restarting
    // every animation it wears, and re-announcing its live region — so a line already
    // in its slot is left where it stands.
    const next = before ?? null;
    if (next !== line && (line.parentElement !== host || line.nextSibling !== next))
      host.insertBefore(line, next);
    wanted.add(line);

    const state = line.querySelector(":scope > .lf-receipt-state");
    const semantic = phaseText(receipt);
    if (state.textContent !== semantic) state.textContent = semantic;
    line.classList.toggle("is-active", receipt.phase === "active");

    let quiet = line.querySelector(":scope > .lf-receipt-quiet");
    const turnClosed =
      receipt.session && receipt.session === claimState().claimingSession
        ? claimState().agentTurnClosed
        : null;
    const isQuiet =
      receipt.phase === "active" &&
      (quietSince(receipt.ts) || droppedAt(receipt.ts, turnClosed));
    if (isQuiet && !quiet) {
      quiet = el("span", "lf-receipt-quiet", "quiet");
      line.insertBefore(quiet, line.lastElementChild);
    } else if (!isQuiet) quiet?.remove();

    const time = line.querySelector(":scope > time");
    const age = ago(receipt.ts);
    if (time.textContent !== age) time.textContent = age;
  }

  function paintAcknowledgments() {
    const wanted = new Set();
    const receipts = runtime.browser?.acknowledgments ?? [];
    for (const projected of receipts) {
      if (projected.phase === "active" && !claimState().claimsHeld && !projected.event)
        continue;
      const receipt =
        projected.phase === "active" && !claimState().claimsHeld
          ? {
              ...projected,
              phase: projected.fallback_phase,
              ts: projected.fallback_ts,
              detail: null,
            }
          : projected;
      const { kind, id } = receipt.target;
      if (kind === "thread") {
        const thread = threads().find((candidate) => candidate.root.id === id);
        if (!thread || thread.resolved) continue;
        const complete = threadsBox.querySelector(
          `.lf-thread[data-id="${CSS.escape(id)}"]`,
        );
        const views = [
          complete,
          ...pageQueryAll(`.lf-conversation-thread[data-thread="${CSS.escape(id)}"]`),
        ].filter(Boolean);
        for (const view of views) {
          const source = receipt.event
            ? view.querySelector(
                `:scope > :is(.lf-msg[data-mid="${CSS.escape(receipt.event)}"], ` +
                  `.lf-conversation-msg[data-event="${CSS.escape(receipt.event)}"])`,
              )
            : null;
          paintReceipt(
            view,
            receipt,
            source?.nextSibling ??
              view.querySelector(
                ":scope > :is(.lf-compose, .lf-say, .lf-thread-actions, .lf-conversation-actions)",
              ),
            wanted,
          );
        }
        continue;
      }
      if (kind !== "widget") continue;
      if (receipt.revision > runtime.currentRevision) continue;
      const owner = elementById(id);
      // Frozen widgets sent in a message have no page edge of their own, so their
      // event-backed receipt remains local to the conversation. A page widget uses
      // its existing Target Button instead of growing another row inside authored
      // content; standalone claims in chrome remain unsupported claim subjects.
      if (owner && receipt.event && inChrome(owner))
        paintReceipt(owner, receipt, null, wanted);
    }
    for (const line of pageQueryAll(".lf-receipt"))
      if (!wanted.has(line)) line.remove();
  }

  return { paintAcknowledgments };
}
