/* A widget's report of the user editing the document through it (a card dragged
 * between columns). The caller has already applied the edit to its own DOM; the
 * projection reconciler states it again once the log contains it, which is why applyAction
 * implementations must state an absolute placement, never a relative mutation.
 *
 * The outbox is the one representation of a gesture the page has made and has not yet
 * read back into a complete rendered state. It orders every user event, tells replay
 * which optimistic actions stand over authoritative state, and tells undo/navigation
 * whether any action is unresolved. An accepted entry may remain here after its caller is
 * answered: delivery can be certain while applying the response's state failed locally.
 * A second pending map used to mirror part of the same lifecycle and then needed a
 * protocol of its own to agree with the send queue and the polling loop. */
export const outbox = [];

export function createOutbox(runtime, dependencies) {
  const {
    POLL_MS,
    elementById,
    newAttempt,
    paintKeys,
    postEvent,
    quoted,
    receiveState,
    reconcileKnownState,
    registry,
    releaseProjectedOutbox,
    requirementMatches,
    showToast,
    stageOutboxAction,
    stateCoordinate,
    stateProjection,
    unitOf,
  } = dependencies;
  let outboxOrder = 0;

  const actionMatches = (el, action) => {
    const spec = registry[el.localName]?.["x-state"]?.[action];
    if (!spec) return false;
    if (spec.requires && !requirementMatches(el, spec)) return false;
    return true;
  };

  // Whether this action is available from the durable state the tab currently projects.
  // Modules use it to paint controls and guard gestures; sendAction asks it again at the
  // common browser door. POST interprets the same x-state declaration under the append
  // lock, because this tab's projection may be stale rather than authoritative.
  const actionAvailable = (el, action) => !quoted(el) && actionMatches(el, action);

  async function sendAction(el, action, detail, { attempt } = {}) {
    // The exhibit rule enforced at the layer's own door, not left to each module
    // remembering quoted(): an exhibited widget is a mention, and a gesture on a
    // mention must not become a decision Claude reads. Failing closed costs a
    // press that does nothing; the console error makes a module that wired one
    // a finding of the render gate.
    if (quoted(el)) {
      console.error(
        `leaf: <${el.localName}> is exhibited (x-exhibit); action ${action} refused`,
      );
      return null;
    }
    if (!actionMatches(el, action)) return null;
    return post({
      kind: "action",
      revision: runtime.currentRevision,
      widget: el.id,
      action,
      detail,
      ...(attempt && { attempt }),
    });
  }

  // Whether the latest event list this tab has seen still leaves an accepted action as
  // the reader's statement of its semantic coordinate. An options `answer` does not erase
  // its picks because completion and selection are different facets, while a later
  // suggestion `reject` supersedes `accept` because both state settlement.
  // A response can fail before installing its event list at all; acceptance is then the
  // only statement this tab knows, so its caller may paint while the outbox keeps replay
  // and undo held for a complete read.
  function actionStands(event) {
    if (!runtime.events.some((candidate) => candidate.id === event.id)) return true;
    const el = elementById(event.widget);
    const spec = el && registry[el.localName]?.["x-state"]?.[event.action];
    if (!el || !spec) return false;
    const unit = unitOf(event, spec);
    if (typeof unit !== "string") return false;
    return (
      stateProjection(runtime.currentRevision).actions.get(
        stateCoordinate(event.widget, unit, spec),
      )?.e.id === event.id
    );
  }

  // Returns the event the server minted — the id is the sender's only handle on the
  // thread or message it just created, which is what revealThread is handed — or null
  // when the server definitively refused it. Every event carries one browser-minted
  // attempt, so a lost answer is retried without becoming a second gesture.
  //
  // The outbox sends one at a time because the log's order is the order the reader acted
  // in and concurrent requests are not. It is also the page's only record of unresolved
  // work: an action in this list is the widget replay leaves alone and the fact that keeps
  // undo dead. A separate promise chain plus a pending-widget map used to describe those
  // same records twice, then reconcile them through a later poll.
  //
  // A successful POST returns the server's state through the event it accepted. Acceptance
  // answers the caller and lets the next entry send. The entry itself leaves only after a
  // complete state application accounts for its attempt, keeping replay and undo away from
  // stale history if rendering the response fails. A periodic poll may account for the
  // attempt first after a response is lost, or later after a local render fault.
  const retryPause = () => new Promise((resolve) => setTimeout(resolve, POLL_MS));
  let drainingOutbox = false;
  function removeOutbox(entry) {
    const index = outbox.indexOf(entry);
    if (index >= 0) outbox.splice(index, 1);
  }
  function accountOutbox(readEvents) {
    let removed = false;
    for (const entry of [...outbox]) {
      const accepted = readEvents.find(
        (candidate) => candidate.attempt === entry.event.attempt,
      );
      if (!accepted) continue;
      entry.readEvent = accepted;
      entry.resolveRead(accepted);
      if (!entry.answered) continue;
      if (entry.event.kind !== "action") {
        removeOutbox(entry);
        removed = true;
      }
    }
    if (releaseProjectedOutbox()) removed = true;
    if (removed) paintKeys();
  }
  async function deliver(entry) {
    let announced = false;
    for (;;) {
      const { event } = entry;
      if (entry.readEvent) return { answer: entry.readEvent };
      const sent = await Promise.race([
        postEvent(event).then(
          (res) => ({ res }),
          (error) => ({ error }),
        ),
        entry.read.then((answer) => ({ answer })),
      ]);
      if (sent.answer) return { answer: sent.answer };
      if (sent.error) {
        if (!announced) showToast("Connection lost — retrying your change…");
        announced = true;
        await retryPause();
        continue;
      }
      const res = sent.res;
      // A newer layer is taking this tab over, and `postEvent` has already started the
      // reload. The server refused to read this body in a vocabulary it no longer
      // speaks, so nothing was appended and there is nothing here to retry: the page
      // comes back from the log, under the layer it is reloading into.
      if (!res) return { answer: null };
      const decoded = await Promise.race([
        res.json().then(
          (answer) => ({ answer }),
          (error) => ({ error }),
        ),
        entry.read.then((answer) => ({ readAnswer: answer })),
      ]);
      if (decoded.readAnswer) return { answer: decoded.readAnswer };
      if (decoded.error) {
        if (!announced) showToast("Couldn't read the answer — retrying your change…");
        announced = true;
        await retryPause();
        continue;
      }
      const answer = decoded.answer;
      const acceptedEvent = answer?.state?.events?.find(
        (candidate) => candidate.attempt === event.attempt,
      );
      if (res.ok && answer?.ok === true && acceptedEvent) {
        // The send succeeded the moment the answer named the accepted event. A fault
        // rendering that state is its own news and must not re-send: the next poll
        // paints it, and re-posting an attempt the log already holds is a request the
        // server can only answer the same way. Where the throw lands before the events
        // are stored, the retry would not even end at the top of this loop — the
        // attempt is in no list to be found — so the page would post forever and this
        // gesture would never settle.
        const settled = receiveState(answer.state).catch((error) =>
          console.error("leaf: state in event response", error),
        );
        return {
          answer: acceptedEvent,
          settled,
        };
      }
      if (
        answer?.final === true &&
        (!("attempt" in answer) || answer.attempt === event.attempt) &&
        answer.ok === false
      ) {
        showToast(`Couldn't send — ${answer.error || "the server refused it"}`);
        return { answer: null };
      }
      if (!announced) showToast("Server answer was incomplete — retrying your change…");
      announced = true;
      await retryPause();
    }
  }
  async function drainOutbox() {
    if (drainingOutbox) return;
    drainingOutbox = true;
    try {
      for (;;) {
        const entry = outbox.find((candidate) => !candidate.answered);
        if (!entry) break;
        const { answer, settled } = await deliver(entry);
        entry.answered = true;
        entry.rejected = !answer && entry.event.kind === "action";
        if (entry.event.kind !== "action" && (!answer || entry.readEvent))
          removeOutbox(entry);
        // A rejected action stops contributing its optimistic winner immediately, but
        // stays in this outbox until the semantic projector has committed the resulting
        // authoritative state. Delivery can advance; replay and undo cannot see the hold
        // disappear first. Accepted entries are released by the complete read that
        // contains their attempt, never merely by a response whose rendering failed.
        if (entry.rejected || entry.readEvent) {
          if (reconcileKnownState()) releaseProjectedOutbox();
        }
        // The list is an input to the key line and no focus/mouse event accompanies
        // either edge. Repaint before resolving the caller, whose own settlement may
        // move a second row on the same frame.
        paintKeys();
        // Acceptance opens the delivery queue immediately, but a successful caller
        // resumes only after this answer's state has either painted or reported why it
        // could not. Comment callers reveal and focus the thread that state creates;
        // tying their continuation to POST delivery made that focus a race. A failed
        // render still resolves with the accepted event and leaves this outbox entry
        // holding replay and undo for the next complete poll.
        if (settled) void settled.then(() => entry.resolve(answer));
        else entry.resolve(answer);
      }
    } finally {
      drainingOutbox = false;
    }
  }
  function post(event) {
    const attempted = { ...event, attempt: event.attempt || newAttempt() };
    // One attempt names one gesture. A caller that reuses it while the first gesture
    // is still here has made a local protocol conflict; letting both entries wait for
    // the same attempt would make the first accepted read resolve the second with the
    // wrong payload before that payload ever reached the server's conflict gate.
    if (outbox.some((entry) => entry.event.attempt === attempted.attempt)) {
      showToast(`Couldn't send — attempt ${attempted.attempt} is already in use`);
      return Promise.resolve(null);
    }
    const answer = new Promise((resolve) => {
      let resolveRead;
      const read = new Promise((readResolve) => {
        resolveRead = readResolve;
      });
      const entry = {
        event: attempted,
        resolve,
        read,
        resolveRead,
        answered: false,
        rejected: false,
        readEvent: null,
        order: ++outboxOrder,
        localId: Symbol("uncommitted local action"),
        projection: null,
      };
      outbox.push(entry);
      stageOutboxAction(entry);
    });
    paintKeys();
    void drainOutbox();
    return answer;
  }

  return {
    accountOutbox,
    actionAvailable,
    actionStands,
    post,
    removeOutbox,
    sendAction,
  };
}
