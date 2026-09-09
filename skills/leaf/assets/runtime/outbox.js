/* A widget's report of the user editing the document through it (a card dragged
 * between columns). The caller has already applied the edit to its own DOM; the
 * projection reconciler states it again once the log contains it, through the complete widget renderer. It must be idempotent so accepting a gesture
 * does not change the state the reader already sees.
 *
 * The outbox is the one representation of a gesture the page has made and has not yet
 * read back into a complete rendered state. It orders every user event, tells replay
 * which optimistic actions stand over authoritative state, and tells undo/navigation
 * whether any action is unresolved. An accepted entry may remain here after its caller is
 * answered: delivery can be certain while applying the response's state failed locally.
 * A second pending map used to mirror part of the same lifecycle and then needed a
 * protocol of its own to agree with the send queue and the reads.
 *
 * Every browser event receives an `attempt` before its first POST. The attempt is the
 * idempotency key for one user gesture, not for a payload shape or a button. Under the
 * server's append lock:
 *
 * - the first accepted attempt appends one event;
 * - an exact concurrent request or retry returns that event;
 * - the same attempt with a different payload is refused;
 * - a completed refusal leaves no durable receipt, so the same attempt may be
 *   evaluated again after the state that caused the refusal changes.
 *
 * The browser sends through `post`. It rejects reuse of an attempt already present in
 * this tab's `outbox`, appends one entry, stages an optimistic action when
 * appropriate, repaints key availability, and starts `drainOutbox`. There is one queue
 * and one delivery loop. Entries send in browser gesture order because the log order is
 * part of the user's statement.
 *
 * Each entry separates three facts:
 *
 * - `answered`: the server definitively accepted or refused the request;
 * - `readEvent`: a complete state read contained the accepted attempt;
 * - `projection`: the local semantic coordinate and value that the widget already
 *   painted;
 * - `message`: the comment or reply the conversation is already showing.
 *
 * Acceptance and application are not the same fact. A successful POST must include state
 * containing the event minted for the attempt. `deliver` then knows the request was
 * accepted and may open the queue for the next entry. No caller waits for that: a
 * message is painted and its thread opened in the gesture that sends it, so the
 * continuation runs against a card that is already on screen and the round trip happens
 * behind it.
 *
 * An accepted action stays in the outbox until a complete applied state contains its
 * attempt and `committedProjection` proves the authoritative coordinate now represented
 * by the DOM. If applying the POST's state throws, the caller still receives the
 * accepted event and the queue advances, but the entry keeps replay and undo held until
 * a later poll applies a complete state. Do not resend an accepted event because its
 * rendering failed.
 *
 * Every action paints before it enters the optimistic overlay. A recorded toggle that
 * the next gesture computes from must paint before the next gesture, so the next absolute
 * detail includes the state the reader just chose. Delivery status may stand beside that
 * semantic result; it never substitutes for it.
 *
 * `deliver` races the POST against `entry.read`. A poll can account for an attempt whose
 * POST response was lost, and the accepted POST state can account for it without another
 * GET. Transport errors, undecodable answers, and incomplete answers retry the same
 * attempt after `RETRY_MS`. A response with `final: true` and `ok: false` is a
 * definitive refusal only when it names this attempt, or omits an attempt. A
 * layer-generation refusal reloads instead of retrying a body under the wrong
 * vocabulary.
 *
 * On refusal, `drainOutbox` marks an optimistic action `rejected`. It immediately stops
 * contributing an optimistic winner, then `reconcileKnownState` restores the coordinate
 * from the last complete authoritative state. The entry remains until
 * `localCoordinateCommitted` proves the optimistic token no longer represents the DOM.
 * Delivery may continue while that correction waits for a live drag or editor to finish.
 *
 * `accountOutbox` runs only after `receiveState` has installed and rendered a complete
 * state. It links receipt events to entries, resolves readers waiting on those events,
 * removes non-action entries whose delivery is complete, and calls
 * `releaseProjectedOutbox` for actions. Never remove an action merely because a POST
 * returned 200 or because an attempt appears in a receipt list that failed partway
 * through rendering.
 *
 * `unaccountedGesture` is true while undo is in flight, the outbox is nonempty, or a
 * widget is visibly dragging. Navigation and undo both consult it. Navigating would
 * destroy unresolved local work; undo cannot choose a stable last gesture while an
 * earlier gesture is unresolved.
 *
 * `actionStands` answers whether one accepted action is still the reader's winner for
 * its semantic coordinate. It treats a newly accepted event as standing when the tab has
 * not yet installed an event list containing its id, then asks the installed projection
 * once an authoritative receipt contains it. Modules use this after a send whose visible
 * choreography depends on whether the accepted action survived later events. */
import { pendingTraffic } from "./traffic.js";
import { saidNow } from "./presence.js";
import { registry } from "./registry.js";
import {
  reconcileKnownState,
  releaseProjectedOutbox,
  requirementMatches,
  stageOutboxAction,
} from "./projection.js";
import { PENDING, runtime } from "./context.js";
import { quoted } from "./widget-elements.js";
import { elementById } from "./passages.js";
import { RETRY_MS } from "./state-feed.js";
import { paintKeys } from "./keyboard/scopes.js";
import { postEvent } from "./layer-client.js";
import { announce, notice } from "./notifications.js";
import { receiveState } from "./state-application.js";
import { newAttempt } from "./drafts.js";
import { stateCoordinate, unitOf } from "./projection/authored.js";
import { stateProjection } from "./projection/fold.js";
import { renderPanel } from "./conversation/reconcile.js";

export const outbox = [];

// The delivery ledger's reading of this list: every attempt still without an outcome.
const unresolved = () =>
  outbox.filter((entry) => !entry.answered).map((entry) => entry.event.attempt);

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
export const actionAvailable = (el, action) =>
  runtime.statePhase !== "waiting" && !quoted(el) && actionMatches(el, action);

export async function sendAction(el, action, detail, { attempt } = {}) {
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
  // Modules ask the same predicate before optimistic paint. Repeat it at the common
  // door so authored HTML cannot post while the first state projection is pending.
  if (!actionAvailable(el, action)) return null;
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
export function actionStands(event) {
  if (!(runtime.browser?.receipts ?? []).some((candidate) => candidate.id === event.id))
    return true;
  const el = elementById(event.widget);
  const spec = el && registry[el.localName]?.["x-state"]?.[event.action];
  if (!el || !spec) return false;
  const unit = unitOf(event, spec);
  if (typeof unit !== "string") return false;
  return (
    stateProjection().actions.get(stateCoordinate(event.widget, unit, spec))?.e.id ===
    event.id
  );
}

// A comment or reply is the one gesture whose visible result is the words themselves,
// so the conversation projection reads this list the way the widget projection reads a
// staged action: authored state, then the log, then what this tab has said and has not
// yet read back. The reader's words are on screen in the gesture that sends them, and
// the round trip happens behind them.
//
// A reaction is a comment too, and it is not a message: it paints as a mark on the page
// through its own chip, and has no card in the list for a record to stand in.
const messageKind = (event) =>
  (event.kind === "comment" || event.kind === "reply") && !event.token;

// The record the panel renders from while the log is still answering. `pending` is what
// it renders differently by, and the attempt is the join: the server's own event carries
// it back, so the message that arrives adopts this one's node instead of replacing it.
function stageOutboxConversation(entry) {
  if (entry.event.kind !== "comment" && entry.event.kind !== "reply") return;
  entry.conversation = {
    ...entry.event,
    id: `${PENDING}${entry.event.attempt}`,
    author: "user",
    ts: saidNow(),
    pending: true,
  };
  if (messageKind(entry.event)) entry.message = entry.conversation;
}

// An entry stands here until an installed receipt names its attempt. That boundary
// rather than its removal from the outbox, because `accountOutbox` runs after the panel
// has already rendered the state carrying the message: keyed on the receipt, the pending
// record and the server's own thread change places within one render, instead of both
// standing for a frame.
export const pendingMessages = () =>
  outbox
    .filter(
      (entry) =>
        entry.message &&
        !(runtime.browser?.receipts ?? []).some(
          (candidate) => candidate.attempt === entry.event.attempt,
        ),
    )
    .map((entry) => entry.message);

const pendingEvents = (...kinds) =>
  outbox
    .filter(
      (entry) =>
        !entry.rejected &&
        kinds.includes(entry.event.kind) &&
        !(runtime.browser?.receipts ?? []).some(
          (candidate) => candidate.attempt === entry.event.attempt,
        ),
    )
    .map((entry) => entry.event);

export const pendingReactions = () =>
  outbox
    .filter(
      (entry) =>
        entry.conversation?.token &&
        !(runtime.browser?.receipts ?? []).some(
          (candidate) => candidate.attempt === entry.event.attempt,
        ),
    )
    .map((entry) => entry.conversation);

export const pendingSettlements = () =>
  outbox
    .filter(
      (entry) =>
        !entry.rejected &&
        (entry.event.kind === "resolve" || entry.event.kind === "unresolve") &&
        !(runtime.browser?.receipts ?? []).some(
          (candidate) => candidate.attempt === entry.event.attempt,
        ),
    )
    .map((entry) => ({ ...entry.event, localParent: entry.namedParent }));

export const pendingApprovals = () => pendingEvents("done");
export const pendingRequests = () => pendingEvents("request");

// Returns the event the server minted — the id is the sender's only handle on the
// thread or message it just created, which is what showThread is handed — or null
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
// stale history if rendering the response fails. A later read may account for the attempt
// first after a response is lost, or later after a local render fault — and a lost answer
// is the case that read reaches soonest, because the append it lost the answer to is
// itself what ends the held request.
// A gesture the reader made against a message this tab knew only by the name it had
// given it: a reply into the card a send had just drawn, a reaction on it, a resolve.
// The server must be sent the log's name, since one only this page ever used names
// nothing there.
//
// Read from the parent's own entry rather than from the installed state. The queue is
// serial, so the parent is answered before this one is sent — but delivery advances on
// acceptance, and applying that answer runs behind it, so the event the server minted is
// known here a beat before any state read contains it. The installed receipts are the
// fallback for an entry this tab has already read back and dropped.
//
// Written onto the entry, so a retry carries the body the first attempt did.
function nameParent(entry) {
  const parent = entry.event.parent;
  if (typeof parent !== "string" || !parent.startsWith(PENDING)) return;
  const attempt = parent.slice(PENDING.length);
  const named =
    outbox.find((candidate) => candidate.event.attempt === attempt)?.acceptedId ??
    (runtime.browser?.receipts ?? []).find((candidate) => candidate.attempt === attempt)
      ?.id;
  if (!named) return;
  // Kept, because the control that made this gesture is on a card the log has not
  // renamed yet and looks its own pending work up by the name it still wears.
  entry.namedParent = parent;
  entry.event.parent = named;
}

// A gesture made against a message the log refused has nothing left to be about.
// Withdraw it here rather than sending a name the server can only refuse in its turn,
// in an answer naming an id this page invented. Resolving it null is what gives the
// reader their words back, through the same path any other refusal takes.
function withdrawChildren(entry) {
  const name = PENDING + entry.event.attempt;
  for (const child of [...outbox])
    if (child !== entry && child.event.parent === name) {
      removeOutbox(child);
      child.resolve(null);
    }
}

const retryPause = () => new Promise((resolve) => setTimeout(resolve, RETRY_MS));
let drainingOutbox = false;
export function removeOutbox(entry) {
  const index = outbox.indexOf(entry);
  if (index >= 0) outbox.splice(index, 1);
}
export function accountOutbox(readEvents) {
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
    nameParent(entry);
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
      if (!announced) notice("Connection lost — retrying your change…");
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
      if (!announced) notice("Couldn't read the answer — retrying your change…");
      announced = true;
      await retryPause();
      continue;
    }
    const answer = decoded.answer;
    const acceptedEvent = answer?.state?.browser?.receipts?.find(
      (candidate) => candidate.attempt === event.attempt,
    );
    if (res.ok && answer?.ok === true && acceptedEvent) {
      // The send succeeded the moment the answer named the accepted event. A fault
      // rendering that state is its own news and must not re-send: a later read
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
      notice(`Couldn't send — ${answer.error || "the server refused it"}`);
      return { answer: null };
    }
    if (!announced) notice("Server answer was incomplete — retrying your change…");
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
      // What the log called this gesture, for the entries queued behind it that named
      // it by this page's own word for it (nameParent).
      entry.acceptedId = answer?.id ?? null;
      if (!answer && entry.message) withdrawChildren(entry);
      pendingTraffic(unresolved());
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
        // Sequence consumers hear a reconciliation performed here the way they hear
        // every other one. This one withdraws a refused winner from the projection, and
        // a surface reading the projection rather than the DOM — the margin's row for
        // that winner, acknowledgment face and all — would otherwise stand on the
        // withdrawn state until the heartbeat's next tick.
        document.dispatchEvent(new Event("lf-actions"));
      }
      if (!answer && (entry.event.kind === "done" || entry.event.kind === "request"))
        document.dispatchEvent(new Event("lf-actions"));
      // A refused message leaves this list at once, and the reader's words leave the
      // panel with it. An accepted one needs no render here: the state the answer
      // carried has already painted the message the log now holds.
      if (
        !answer &&
        (entry.conversation ||
          entry.event.kind === "resolve" ||
          entry.event.kind === "unresolve")
      )
        void renderPanel();
      // The list is an input to the shortcut bar and no focus/mouse event accompanies
      // either edge. Repaint before resolving the caller, whose own settlement may
      // move a second row on the same frame.
      paintKeys();
      // Acceptance opens the delivery queue immediately, but a successful caller
      // resumes only after this answer's state has either painted or reported why it
      // could not. Comment callers reveal and focus the thread that state creates;
      // tying their continuation to POST delivery made that focus a race. A failed
      // render still resolves with the accepted event and leaves this outbox entry
      // holding replay and undo for the next complete read.
      if (settled) void settled.then(() => entry.resolve(answer));
      else entry.resolve(answer);
    }
  } finally {
    drainingOutbox = false;
  }
}
export function post(event) {
  const attempted = { ...event, attempt: event.attempt || newAttempt() };
  // One attempt names one gesture. A caller that reuses it while the first gesture
  // is still here has made a local protocol conflict; letting both entries wait for
  // the same attempt would make the first accepted read resolve the second with the
  // wrong payload before that payload ever reached the server's conflict gate.
  if (outbox.some((entry) => entry.event.attempt === attempted.attempt)) {
    notice(`Couldn't send — attempt ${attempted.attempt} is already in use`);
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
    pendingTraffic(unresolved());
    stageOutboxAction(entry);
    stageOutboxConversation(entry);
    // Locally projected actions, approval, and requests have semantic consumers beyond
    // their pressed control. Invalidate those readings while the POST is still waiting.
    if (entry.projection || attempted.kind === "done" || attempted.kind === "request")
      document.dispatchEvent(new Event("lf-actions"));
    // The panel is the message's consumer, and it reads the conversation rather than
    // this list, so it has to be asked. This render is the send's visible result — and
    // for a reader who has no view of it, the live region is. Said here rather than by
    // each of the four boxes that send a message, so a fifth cannot arrive silent: this
    // is the one place that has already decided the gesture was a message. A reaction
    // is not one, and says its own richer sentence where it is sent.
    if (entry.message) {
      announce("Message sent");
    }
    if (
      entry.conversation ||
      attempted.kind === "resolve" ||
      attempted.kind === "unresolve"
    )
      void renderPanel();
  });
  paintKeys();
  void drainOutbox();
  return answer;
}
