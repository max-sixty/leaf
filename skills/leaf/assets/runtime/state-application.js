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
    loadMarked,
    notifyDataSubscribers,
    observeServerNow,
    paintAnchors,
    paintApproval,
    paintAcknowledgments,
    panelIsOpen,
    prepareActivation,
    presented,
    reconcileState,
    replaceClaimState,
    refreshHover,
    renderOthers,
    renderPanel,
    renderStatus,
    renderVersions,
    runtime,
    sameLayer,
    notice,
    settleAcceptedDrafts,
    stateSignoff,
    updateFab,
  } = dependencies;

  let agentMsgCount = -1;
  // The state read installing a document, while it is. Polls and POST answers may
  // overlap, and a document activation is the one application that cannot safely
  // interleave: a second one would capture or replace the halfway upgraded main. Every
  // read lets it commit before judging its own answer against the resulting version,
  // sequence and stamp.
  let activating = null;

  // Whether an answer was taken before the one the page holds. Answers cross — a read
  // held by a slow proxy or a test while a later one lands, a POST's answer beside a
  // read — and the log's sequence and the data's revision order everything in a state
  // but the reading, which is a hash with no order of its own. The server stamps each
  // answer with the moment it was taken, inside the transaction every answer is built
  // under, so this is the order they were taken in whichever order they land. Equal is
  // not before: the heartbeat re-applies the held answer itself.
  const takenBefore = (state) =>
    runtime.state !== null && state.taken < runtime.state.taken;

  async function receiveState(state) {
    // Every state this page reads passes here — the poll's, and the one an accepted
    // event response carries — so the generation is checked once for both rather than
    // at each door it arrives through.
    if (!sameLayer(state.layer.generation)) return;
    if (typeof state.taken !== "number")
      throw new TypeError("state must say when it was taken");
    // Ahead of the sequence checks below, which drop a response as state: a reading
    // that arrives out of order still says what time it is where the timestamps are
    // written, and that is the one thing in it that cannot be stale.
    observeServerNow(state.now);
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
      if (activating) await activating;
      await notifyChangedData();
      return;
    }
    // A POST's answer and a read can cross. The log is append-only, so a response
    // behind one already rendered is unambiguously stale; accepting it would move
    // every event-derived view backwards until the next read. Kept beside the stamp's
    // gate: that orders the server's answers, and this holds the log's order against
    // any answer at all, one a test built included.
    if (eventSeq < runtime.lastEventSeq) {
      if (activating) await activating;
      await notifyChangedData();
      return;
    }
    if (activating) await activating;
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
    const [activation] = await Promise.all([
      prepareActivation(state),
      nextEvents.some((e) => e.kind === "comment" || e.kind === "reply")
        ? loadMarked()
        : null,
    ]);
    if (activation?.stale) {
      await notifyChangedData();
      return;
    }
    // The preparation above yields. A newer response may have completed while this one was
    // waiting, and two responses may have joined the same version-file promise before
    // either had an activation to await. Serialize again at the commit boundary, then
    // judge this candidate against the version and sequence the winner installed.
    if (activating) await activating;
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
        claimsHeld: presented(state).held,
        agentTurnClosed: state.turn_closed || null,
        claimingSession: state.claim_session || null,
      });
      renderStatus(state);
      renderVersions(state);
      stateSignoff(getSignoffDeclared());
      paintApproval();
      renderOthers(state);
      if (eventSeq > runtime.lastEventSeq || finishActivation) {
        renderPanel();
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
      // Outside the log-growth block: a work claim lands and ages without changing an
      // event this tab holds. After widget reconciliation because a module may rebuild
      // its authored subtree; the local line is the transient overlay that follows it.
      paintAcknowledgments();
      if (finishActivation) {
        finishActivation();
        paintAnchors();
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
      // not grow: applyAction may have deferred while a user was typing, then become
      // applicable on the next poll after they close the editor.
      document.dispatchEvent(new Event("lf-actions"));
      await notifyDataSubscribers();
    };
    try {
      if (willActivate) {
        const running = (async () => {
          if (document.startViewTransition) {
            document.documentElement.classList.add("lf-versioning");
            try {
              const transition = document.startViewTransition(apply);
              // A skipped transition — the document hidden at the call or
              // mid-flight, or a second transition starting — still runs the
              // update and settles `finished` with it, but rejects `ready`,
              // which nothing here awaits. Unhandled, that rejection reaches
              // the page's error report as a logged fault.
              transition.ready.catch(() => {});
              await transition.finished;
            } finally {
              document.documentElement.classList.remove("lf-versioning");
              // The transition's snapshots temporarily replace what is under a parked
              // pointer. Ask again once the live page owns those pixels, even when no
              // pointer move reports the change.
              refreshHover();
            }
          } else await apply();
        })();
        activating = running;
        try {
          await running;
        } finally {
          if (activating === running) activating = null;
        }
      } else await apply();
    } catch (error) {
      // Candidate history is useful only while this one synchronous application is
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
      if (willActivate) location.reload();
      throw error;
    }
    if (nextAgentMsgCount !== null) agentMsgCount = nextAgentMsgCount;
    if (replyNotice) notice(replyNotice);
  }

  return { receiveState };
}
