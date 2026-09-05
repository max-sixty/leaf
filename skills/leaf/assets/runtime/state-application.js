import { LIVE_ROOT } from "./storage.js";

// What an application writes to the runtime and a refused one gives back, the three
// current-document facts included, so the chooser re-renders from the restored state.
const APPLICATION_RUNTIME_FIELDS = Object.freeze([
  "agent",
  "browser",
  "currentLabel",
  "currentRevision",
  "currentStamp",
  "events",
  "lastEventSeq",
  "reading",
  "state",
  "statePhase",
  "view",
]);

export function createStateApplication(dependencies) {
  const {
    PAGE_PAINT_ATTRIBUTE,
    acceptData,
    accountOutbox,
    getSignoffDeclared,
    importWidgets,
    loadMarked,
    notifyDataSubscribers,
    observeServerNow,
    paintApproval,
    panelIsOpen,
    prepareActivation,
    reconcileState,
    replaceClaimState,
    refreshHover,
    renderOthers,
    renderPanel,
    renderStatus,
    renderVersions,
    runtime,
    sameLayer,
    sayLine,
    notice,
    settleAcceptedDrafts,
    stateSignoff,
    updateFab,
  } = dependencies;

  let agentMsgCount = -1;
  // Which frozen markup has already been read for the modules it needs. A state read
  // carries the whole log, an event's markup never changes, and the parse is the only
  // way to know which tags are in it — so each one is read once rather than on every
  // poll of a conversation that may be full of widgets.
  const markupRead = new Set();
  // Polls and POST answers may overlap, but an application owns its document and
  // newly connected thread widgets through upgrade, capture, and projection. Every
  // read waits for that application before judging its own revision and sequence.
  let applying = null;

  // Whether an answer was taken before the one the page holds. Answers cross — a read
  // held by a slow proxy or a test while a later one lands, a POST's answer beside a
  // read — and the log's sequence and the data's revision order everything in a state
  // but the reading, which is a hash with no order of its own. The server stamps each
  // answer with the moment it was taken, inside the transaction every answer is built
  // under, so this is the order they were taken in whichever order they land. Equal is
  // not before: deferred activation may reapply the held answer itself.
  const takenBefore = (state) =>
    runtime.state !== null && state.taken < runtime.state.taken;

  async function receiveState(state) {
    // Every state this page reads passes here — the poll's, and the one an accepted
    // event response carries — so the generation is checked once for both rather than
    // at each door it arrives through.
    if (!sameLayer(state.layer.generation)) return;
    if (typeof state.taken !== "number")
      throw new TypeError("state must say when it was taken");
    // Events and source snapshots are independent authorities serialized by the same page
    // transaction but observed through overlapping responses. Their revisions form a pair,
    // not one total order: a response with an older event tail may still carry the newest
    // data. Accept that component before the event gate, and never move either one backward.
    const dataChanged = acceptData(state.data);
    const notifyChangedData = async () => {
      if (dataChanged) await notifyDataSubscribers();
    };
    const nextEvents = state.events;
    const nextBrowser = state.browser;
    const eventSeq = nextBrowser?.basis?.through_seq;
    if (!Number.isInteger(eventSeq) || eventSeq < 0)
      throw new TypeError("state browser must name its log sequence");
    // An answer taken before the one the page holds is judged as a stale sequence is
    // (takenBefore). Before the sequence gate because a stale answer may carry the same
    // sequence as the newer one and differ in everything the sequence does not order —
    // status, claims, the reading itself.
    if (takenBefore(state)) {
      while (applying) await applying;
      await notifyChangedData();
      return;
    }
    // A POST's answer and a read can cross. The log is append-only, so a response
    // behind one already rendered is unambiguously stale; accepting it would move
    // every event-derived view backwards until the next read. Kept beside the stamp's
    // gate: that orders the server's answers, and this holds the log's order against
    // any answer at all, one a test built included.
    if (eventSeq < runtime.lastEventSeq) {
      while (applying) await applying;
      await notifyChangedData();
      return;
    }
    while (applying) await applying;
    if (eventSeq < runtime.lastEventSeq || takenBefore(state)) {
      await notifyChangedData();
      return;
    }
    const targetRevision = state.active?.revision ?? null;
    if (!Number.isInteger(targetRevision) || targetRevision < 1)
      throw new TypeError("state active must name a positive revision");
    if (LIVE_ROOT && runtime.currentRevision === null)
      throw new TypeError("the live document has no lf-revision marker");
    if (runtime.active && targetRevision < runtime.active.revision) {
      await notifyChangedData();
      return;
    }
    // Messages render from Markdown; have the renderer in hand before the panel
    // builds a body, so msgNode stays synchronous. The next authored document, where
    // the state names one the live root can follow, is fetched on the same background
    // stretch rather than making either network trip wait on the other.
    const preparations = [
      prepareActivation(state),
      nextEvents.some((e) => e.kind === "comment" || e.kind === "reply")
        ? loadMarked()
        : null,
    ];
    // And the modules for the widgets a message carries, on the same stretch and for the
    // same reason: a reply's frozen markup may hold a tag this document never had, and
    // buildMsgBody instantiates it synchronously once the panel builds a body.
    for (const e of nextEvents) {
      if (!e.markup || markupRead.has(e.id)) continue;
      // Parsed the way buildMsgBody parses it, so the tags found here are the tags that
      // will stand in the body: an inert template, one fragment at a time.
      const frozen = document.createElement("template");
      frozen.innerHTML = e.markup;
      // The loader shares in-flight module promises. Only completed preparation is
      // cached here: a crossed response must join that import before it mounts or
      // captures the same frozen widget.
      preparations.push(importWidgets(frozen.content).then(() => markupRead.add(e.id)));
    }
    const [activation] = await Promise.all(preparations);
    if (activation?.stale) {
      await notifyChangedData();
      return;
    }
    // The preparation above yields. A newer response may have completed while this one was
    // waiting, and two responses may have joined the same version-file promise before
    // either had an activation to await. Serialize again at the commit boundary, then
    // judge this candidate against the version and sequence the winner installed.
    while (applying) await applying;
    if (eventSeq < runtime.lastEventSeq || takenBefore(state)) {
      await notifyChangedData();
      return;
    }
    if (runtime.active && targetRevision < runtime.active.revision) {
      await notifyChangedData();
      return;
    }
    const willActivate = activation !== null && activation.activates();
    // The last coordinate the commit boundary judges, beside sequence and active
    // revision: the answer holds a view of the revision the page named when it asked and
    // of the one it may activate into, and of no others. An activation between the decision
    // and the answer leaves the page on neither — it is showing a revision this answer
    // says nothing about, so there is no view here to install and no version to move to.
    // Dropped like the gates above: the page's next read names the revision it holds
    // now, and that answer projects it.
    const showing = willActivate ? targetRevision : runtime.currentRevision;
    if (!nextBrowser.views?.[String(showing)]) {
      await notifyChangedData();
      return;
    }
    // Calibrate only an accepted reading. A delayed response carries an old clock
    // as well as old state; rejecting its state must not rewind timestamp aging.
    if (state !== runtime.state) observeServerNow(state.now);
    const prior = {
      runtime: Object.fromEntries(
        APPLICATION_RUNTIME_FIELDS.map((field) => [field, runtime[field]]),
      ),
    };
    let nextAgentMsgCount = null;
    let replyNotice = null;
    let restoreClaimState = () => {};
    const apply = async () => {
      runtime.events = nextEvents;
      runtime.browser = nextBrowser;
      let finishActivation = null;
      runtime.statePhase = "ready";
      if (willActivate) finishActivation = await activation.install();
      runtime.view = nextBrowser.views?.[String(runtime.currentRevision)] ?? null;
      // What is left for this to catch, now that a late answer is dropped above: an
      // answer that is malformed rather than late, and an activation that left the page
      // somewhere the gate did not predict. Both are faults, so both are loud.
      if (
        !runtime.view ||
        runtime.view.basis?.through_seq !== eventSeq ||
        runtime.view.basis?.revision !== runtime.currentRevision
      )
        throw new TypeError("state browser has no matching revision view");
      settleAcceptedDrafts();
      runtime.agent = state.agent || "Claude";
      restoreClaimState = replaceClaimState({
        sources: state.claims || [],
        presence: state,
        agentTurnClosed: state.turn_closed || null,
        claimingSession: state.claim_session || null,
      });
      renderStatus(state);
      renderVersions(state);
      stateSignoff(getSignoffDeclared());
      paintApproval();
      renderOthers(state);
      if (eventSeq > runtime.lastEventSeq || finishActivation) {
        await renderPanel();
        // Sign-off is a fact in the log, not a click this tab happens to remember, so a
        // reload (or the other tab) shows it too.
        const agentReplies = (runtime.browser.conversation?.threads ?? []).flatMap(
          (thread) =>
            thread.msgs.filter(
              (message) => message.author === "claude" && message.kind === "reply",
            ),
        );
        if (agentMsgCount >= 0 && agentReplies.length > agentMsgCount && !panelIsOpen())
          replyNotice = `${agentReplies.at(-1).agent || "Agent"} replied — open Threads`;
        nextAgentMsgCount = agentReplies.length;
      }
      // Last, because the panel has just rendered the log: a widget carried by a reply is
      // on the page by now, so an action naming one that isn't names a widget no version
      // holds, and reconciliation can retire it instead of looking for it forever.
      reconcileState();
      // One complete tail after widget rendering: it may change derived content, including
      // the row and outlet holding a local thread. Re-resolve anchors, reconcile declared
      // surfaces, then their fallbacks and receipts from that final DOM. This also repaints
      // time-dependent claim chrome on a state heartbeat with no new event.
      await renderPanel();
      if (finishActivation) {
        finishActivation();
        updateFab();
        notice(`Updated to ${runtime.currentLabel}`);
      }
      // Only a complete application advances the read boundary. A render fault may
      // already have changed some local surfaces, but it has not made a state safe to use
      // for replay or undo; leaving the sequence unresolved retries the whole read.
      runtime.lastEventSeq = Math.max(runtime.lastEventSeq, eventSeq);
      // Stamped in the same place, because it answers the same question about a
      // wider subject: the sequence says how much of the log the page holds, the
      // reading how much of the page's whole state — status, data, claims, versions
      // — none of which moves the sequence at all. Not by the same rule: a hash has
      // no order, so the moment the server took the answer is what keeps a stale one
      // from writing it, and that answer was turned away at the door above.
      runtime.reading = state.reading ?? null;
      // Kept so the heartbeat can re-render time-dependent chrome without asking the
      // server for a copy of what the page already has, and for `taken`, which the
      // door above judges the next answer by.
      runtime.state = state;
      if (runtime.reading !== null)
        document.body.setAttribute(PAGE_PAINT_ATTRIBUTE.reading, runtime.reading);
      // Accounting changes no hold by itself. It first projects this complete log plus
      // every surviving optimistic action, then releases the entries whose attempts the
      // read contained. A same-widget event later in this state can therefore never be
      // skipped under the hold and exposed only after the hold disappears.
      accountOutbox(nextBrowser.receipts ?? []);
      // Sequence consumers render after replay, so their history and the widget's
      // standing body describe the same poll. This also fires when the event list did
      // not grow: renderState may have deferred while a user was typing, then become
      // applicable on the next poll after they close the editor.
      document.dispatchEvent(new Event("lf-actions"));
      await notifyDataSubscribers();
    };
    try {
      const running = (async () => {
        if (willActivate && document.startViewTransition) {
          document.documentElement.classList.add("lf-versioning");
          try {
            const transition = document.startViewTransition(apply);
            // Skipping the visual transition still runs the application, but rejects
            // ready. Its finished promise remains the complete application boundary.
            transition.ready.catch(() => {});
            await transition.finished;
          } finally {
            document.documentElement.classList.remove("lf-versioning");
            refreshHover();
          }
        } else await apply();
      })();
      applying = running;
      try {
        await running;
      } finally {
        if (applying === running) applying = null;
      }
    } catch (error) {
      // Candidate history is useful only while this one application is
      // rendering it. If any required surface refuses the state, restore the last whole
      // reading so focus, panel, and undo cannot consume a log tail the page never
      // adopted. The next poll retries the candidate from the same complete boundary.
      // The chooser is painted from the restored state, which leaves it as it stood: an
      // open menu's rows are never rebuilt under the reader, so a focused row survives
      // both the candidate and its rollback.
      Object.assign(runtime, prior.runtime);
      renderVersions(runtime.state);
      if (runtime.reading === null)
        document.body.removeAttribute(PAGE_PAINT_ATTRIBUTE.reading);
      else document.body.setAttribute(PAGE_PAINT_ATTRIBUTE.reading, runtime.reading);
      stateSignoff(getSignoffDeclared());
      restoreClaimState();
      // A version the page could not show, and the reader is left looking at the one it
      // was leaving. Say what the reload is for before making it: a tab that reloads
      // itself in silence reads as the page having lost their place for no reason.
      if (willActivate) {
        sayLine("Couldn't show that version — reloading this page.");
        location.reload();
      }
      throw error;
    }
    if (nextAgentMsgCount !== null) agentMsgCount = nextAgentMsgCount;
    if (replyNotice) notice(replyNotice);
  }

  return { receiveState };
}
