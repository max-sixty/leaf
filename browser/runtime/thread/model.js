// @ts-check
/* Pure thread structure and turn-taking projected by the server.

   This reads projected threads by `isReaction`, `spoken`, `turns`, and `bareReaction`,
   the names `events.py` reads them by. The panel lists `discussed` threads only.
   Every drawing of a thread, a card or the message parts a presentation names
   (thread/primary-reader.js), shows its turns: its spoken messages and its root, so a
   thread that grew out of a reaction opens on the mark, whose body thread/messages.js
   writes as the glyph and its word, and any other reaction stands as its chip on the
   message it answers. Whose turn a thread is is read
   from the complete browser Thread's `attention` and nothing else: a user obligation
   outranks concurrent agent work, which stays the card's secondary status.

   A thread's `id` is its one identity: the id the server keys it by, which every obligation,
   workflow, placement, and view names it by. Its `root` is its opening message, a
   message like any other, and what a reply or settlement addresses as its `parent`. A
   thread this tab opened goes by its pending message's id until the log answers. */
import { sameAnchor } from "../anchor-coordinate.js";
import { PENDING } from "./identity.js";

/** @typedef {import("../../types/domain.js").Thread} Thread */
/** @typedef {import("../../types/domain.js").Message} Message */
/** @typedef {import("../../types/domain.js").Settlement} Settlement */
/** @typedef {import("../../types/domain.js").Anchor} Anchor */

/** @param {{token?: string}} message */
export const isReaction = (message) => Boolean(message.token);
/** @param {Pick<Message, "addressable">} message */
const isAddressable = (message) => message.addressable !== false;

// A known thread can be opened and answered before the saved inventory arrives.
// Its own settlement, rather than the collection's completeness, owns these offers.
/** @param {Thread} thread */
const threadOffers = (thread) => ({
  open: true,
  reply: !thread.settling,
  resolve: !thread.resolved && !thread.settling,
  reopen: Boolean(thread.resolved) && !thread.settling,
});

// The publisher supplies the vocabulary; controls and commands read these same
// choices, including the exact reaction in force an explicit removal withdraws.
/** @template {Pick<Message, "id" | "author" | "parent" | "token" | "addressable" | "agent"> & {key: string}} T
 * @param {{key: string, resolved: Thread["resolved"], msgs: T[]}} thread
 * @param {T} message
 * @param {Record<string, {glyph: string}>} tokens
 */
function reactionChoices(thread, message, tokens) {
  if (
    thread.resolved ||
    message.author !== "agent" ||
    !isAddressable(message) ||
    !Object.keys(tokens).length
  )
    return null;
  const latest = thread.msgs.findLast(
    (item) => item.author === "agent" && isAddressable(item),
  );
  const inForce = thread.msgs.filter(
    (item) => isReaction(item) && item.author === "user" && item.parent === message.id,
  );
  return {
    thread: thread.key,
    message: message.key,
    latest: latest?.id === message.id,
    agent: message.agent,
    choices: tokenChoices(tokens, inForce),
  };
}

// The declared reaction tokens as choices on one target, each with the reaction in force
// a press takes back. The bar, a reply's strip and the margin form render these; each
// surface keeps its own face, and the token names the control on all of them.
/** @template {{token?: string}} S
 * @param {Record<string, {glyph: string}>} tokens
 * @param {S[]} inForce
 */
export const tokenChoices = (tokens, inForce) =>
  Object.entries(tokens).map(([name, entry]) => ({
    name,
    glyph: entry.glyph,
    label: name,
    inForce: inForce.find((item) => item.token === name) ?? null,
  }));
/** @param {Thread} thread */
const spoken = (thread) => thread.msgs.filter((message) => !isReaction(message));
/** @template {{id: string, token?: string, [field: string]: unknown}} T @param {{msgs: readonly T[], root: {id: string}}} thread */
export const turns = (thread) =>
  thread.msgs.filter(
    (message) => message.id === thread.root.id || !isReaction(message),
  );
// The name for a thread that the log's answer does not change: the user's own attempt
// where their gesture opened the thread, else the id the log gave it. Anything
// that has to outlive that transition with the user in it — a reply draft, a
// margin row — keys itself by this rather than by the id, which changes when the log
// answers.
/** @param {{id: string, root: {attempt?: string}}} thread */
export const threadKey = (thread) => thread.root.attempt ?? thread.id;
// The name a message is drawn under, which the log's answer does not change: the
// server's `key` where it names one, as it does for an agent's answer to an input and
// the provisional reply that stood for it (`served_state/thread.py`), else the user's
// own attempt for a message this tab sent, else the id the log gave it.
/** @param {Pick<Message, "id" | "key" | "attempt">} message */
export const messageKey = (message) => message.key ?? message.attempt ?? message.id;

// Every name that reaches a thread: its own id, the id of each message in it, which a
// reply or settlement names as its `parent`, and the pending id a message this tab sent
// went by before the log named it.
/** @template {{id: string, msgs: readonly {id: string, attempt?: string}[]}} T
 * @param {readonly T[]} threads */
export function threadNames(threads) {
  /** @type {Map<string, T>} */
  const byName = new Map();
  for (const thread of threads) {
    byName.set(thread.id, thread);
    for (const message of thread.msgs) {
      byName.set(message.id, thread);
      if (message.attempt) byName.set(PENDING + message.attempt, thread);
    }
  }
  return byName;
}

// A message whose words the user may rewrite: one of their own that the log holds, with
// words to revise. A reaction or a bare drawing has none (`event_contracts._edit_error`).
/** @param {{author?: string, pending?: boolean, token?: string, text?: string}} message */
export const editable = (message) =>
  message.author === "user" &&
  !message.pending &&
  !message.token &&
  Boolean(message.text);

/** @param {Pick<Thread, "bare_reaction">} thread */
export const bareReaction = (thread) => thread.bare_reaction;
/** @param {Pick<Thread, "bare_reaction">} thread */
export const discussed = (thread) => !bareReaction(thread);
/** Whether a thread holds words the user hasn't read.
 * @param {Pick<Thread, "unread">} thread */
const hasUnread = (thread) => thread.unread.length > 0;
/**
 * Whether a thread is news: still open and holding words the user hasn't read. A
 * resolved thread's unread words aren't, so the news the panel counts never outnumbers
 * the open threads; a reply reopens its thread, and the user chose on 21 October to
 * leave what reaches a closed one unannounced.
 * @param {Pick<Thread, "resolved" | "unread">} thread */
export const isNews = (thread) => !thread.resolved && hasUnread(thread);
/**
 * What the panel counts of the threads it lists: those still open, which Threads' tab
 * says, and those that are news (`isNews`), which the On me mark's dot says. A page's
 * served row counts the same way
 * (`served_state.thread.thread_counts`); tests/thread_count_cases.json holds both.
 * @param {readonly Pick<Thread, "bare_reaction" | "resolved" | "unread">[]} threads
 */
export function threadCounts(threads) {
  const listed = threads.filter(discussed);
  return {
    open: listed.filter((thread) => !thread.resolved).length,
    unread: listed.filter(isNews).length,
  };
}
// Which widget's seat a pending thread stands in, by the rule `seat_root` reads the log
// by: an element anchor naming that widget and carrying nothing else. Spelled again here
// because the server has not seen this message yet, and a thread that seated itself
// differently for the half-second before it lands would move once it arrived.
/** @param {Message} message */
const pendingSeat = (message) =>
  message.about || !message.anchor || Object.keys(message.anchor).length !== 1
    ? null
    : (message.anchor.section ?? null);

// The user's own pending gestures, folded into the server's threads in the order this
// tab made them, as `events.build_threads` folds the log. A comment opens a thread where
// it was written; a reply joins the thread it answers; a rewrite shows as its message's
// new words; settlement changes the thread's state, and a turn reopens a resolved one;
// taking back a reaction, the one message the user can withdraw, drops it from its
// thread, and a thread it opened goes with it. They leave again when the server accepts
// or refuses them, so this is a reading of the same outbox and log the server projects
// rather than a second store beside it.
//
// The fold draws only what a gesture settles by itself. Whose turn a served thread is
// depends on what the rest of the log leaves in force, so it keeps the attention the
// server read until the log answers the gesture. A thread the user opened with words has
// no log beyond the gesture: it waits on the agent for its send, under the pending id its
// local workflow shares, and asks nothing yet.
/** @param {{id: string}} turn @returns {import("../../types/domain.js").Attention} */
const sending = (turn) => ({
  kind: "waiting",
  reason: "workflow",
  workflow: turn.id,
});

// `gestures` are the ledger's thread gestures, oldest first: each comment, reply or
// rewrite as the thread draws it, each settlement with the `localParent` its pending
// parent went by, and each undo.
/** @param {readonly Thread[]} threads
 * @param {readonly import("../../types/domain.js").ThreadGesture[]} gestures
 * @returns {Thread[]}
 */
export function foldThreads(threads, gestures) {
  if (!gestures.length) return [...threads];
  const withdrawn = new Set(
    gestures.flatMap((gesture) => (gesture.kind === "undo" ? [gesture.undoes] : [])),
  );
  // A thread the user opened answers to two names for as long as this tab holds a
  // reply written against the first: the one this page gave it, and the one the log
  // gave back. Both reach the one thread, so a reply written into the card a
  // send had just drawn stays in it when the answer arrives.
  /** @type {Thread[]} */
  const copies = threads
    .filter((thread) => !withdrawn.has(thread.root.id))
    .map((thread) => ({
      ...thread,
      msgs: thread.msgs.filter((message) => !withdrawn.has(message.id)),
      // A thread whose closing event the user is taking back stands open again, as a
      // to-do whose Done they undo does; the log's answer restores any earlier closure.
      ...(thread.resolved &&
      "id" in thread.resolved &&
      withdrawn.has(thread.resolved.id)
        ? { resolved: null }
        : {}),
    }));
  const byName = threadNames(copies);
  /** @type {Thread[]} */
  const opened = [];
  for (const gesture of gestures) {
    if (gesture.kind === "comment") {
      const reaction = isReaction(gesture);
      /** @type {Thread} */
      const thread = {
        id: gesture.id,
        root: gesture,
        title: null,
        anchor: gesture.anchor ?? null,
        detached_from: null,
        rewritten_from: null,
        msgs: [gesture],
        revisions: [],
        resolved: null,
        bare_reaction: reaction,
        seat: pendingSeat(gesture),
        summaries: [],
        unread: [],
        attention: reaction ? null : sending(gesture),
      };
      opened.push(thread);
      byName.set(gesture.id, thread);
    } else if (gesture.kind === "reply") {
      const thread = byName.get(gesture.parent);
      if (!thread) continue;
      // A reply still streaming stands last, where the log will take its answer, so the
      // user's message joins the thread above it and its acceptance moves nothing.
      const streaming = thread.msgs.at(-1)?.provisional ? 1 : 0;
      thread.msgs = thread.msgs.toSpliced(thread.msgs.length - streaming, 0, gesture);
      // A reaction is no turn, so it reopens nothing.
      if (!isReaction(gesture)) thread.resolved = null;
    } else if (gesture.kind === "edit") {
      // An edit shows as its message's new words, and is a turn as a reply is, under
      // the edit's own pending id (`events.exchange`).
      const thread = byName.get(gesture.message);
      const at = thread?.msgs.findIndex(({ id }) => id === gesture.message) ?? -1;
      const message = thread?.msgs[at];
      if (!thread || !message) continue;
      thread.msgs = thread.msgs.with(at, {
        ...message,
        text: gesture.text,
        content_version: gesture.id,
        edited: {
          id: gesture.id,
          ts: gesture.ts,
          was: message.text ?? "",
          pending: true,
        },
      });
      if (thread.root.id === gesture.message) thread.root = thread.msgs[at] ?? message;
      thread.resolved = null;
    } else if (gesture.kind === "resolve" || gesture.kind === "unresolve") {
      const thread =
        byName.get(gesture.parent) ??
        (gesture.localParent ? byName.get(gesture.localParent) : undefined);
      if (!thread) continue;
      thread.resolved =
        gesture.kind === "resolve" ? { author: "user", pending: true } : null;
      // Which way the thread is being settled, as well as where it lands. `resolved`
      // alone cannot say: a reopen leaves it null, exactly as an open thread the user
      // has not touched does. Views read this to draw the gesture as unfinished, so it
      // has to be a fact of the published fold — the ledger empties after the answer
      // lands without changing anything else, and a view reading the ledger would keep
      // the state it drew before that.
      thread.settling = gesture.kind;
    }
  }
  for (const thread of opened)
    thread.bare_reaction = isReaction(thread.root) && !spoken(thread).length;
  return [...copies, ...opened];
}

// The bare reactions in force on exactly this anchor — the bar's own question, asked
// so its chips can say which tokens are already there. Anchors are compared as
// records, the way the file compares them.
/** @template {Pick<Thread, "bare_reaction" | "resolved" | "anchor"> & {root: unknown}} T
 * @param {readonly T[]} threads @param {Anchor} anchor
 * @returns {T["root"][]} */
export const reactionsAt = (threads, anchor) =>
  threads
    .filter(
      (thread) =>
        bareReaction(thread) && !thread.resolved && sameAnchor(thread.anchor, anchor),
    )
    .map((thread) => thread.root);

/** @param {Thread} thread */
export const seatRoot = (thread) => thread.seat;

// When a message last moved: its latest edit, else its own arrival. Every ordering that
// asks what is newest in a thread — the first unread, news — reads this,
// so an agent message edited today is today's in all of them. A message still being
// sent carries the clock the user's gesture gave it and no log position yet.
/** @param {{edited?: {seq?: number, ts: string}, seq?: number, ts?: string}} message */
export const moved = (message) => ({
  seq: message.edited?.seq ?? message.seq ?? null,
  ts: message.edited?.ts ?? message.ts ?? null,
});

// When a thread last moved: the latest move of any of its turns.
/** @param {{msgs: readonly {id: string, token?: string, edited?: {seq?: number, ts: string}, seq?: number, ts?: string}[], root: {id: string}}} thread */
export function lastMovedAt(thread) {
  let latest = null;
  for (const message of turns(thread)) {
    const { ts } = moved(message);
    if (ts !== null && (latest === null || Date.parse(ts) > Date.parse(latest)))
      latest = ts;
  }
  return latest;
}

/** @param {import("../../types/domain.js").ContentVersion} item */
const versionKey = ({ message, version }) => `${message}\u0000${version}`;

/* Public thread values. The publisher calls this after folding local gestures
   and admitted obligations. Authored source stays with its prepared document; only
   captured words, registry identities and current unit state cross this boundary.

   A Thread's `unread` is the server's reading of the agent content versions the user
   has not taken in, less those this tab is marking read now: the page draws them read
   in the turn it sends that, and the answer confirms rather than decides it. */
/** @param {readonly Thread[]} threads
 * @param {import("../framework/application.js").SemanticDocument} document
 * @param {ReturnType<typeof import("../projection/model.js").foldWidgetStates>} widgets
 * @param {import("../framework/application.js").Workflow[]} workflows
 * @param {readonly import("../framework/application.js").WireTodo[]} todos
 *   the open to-dos, of which each thread holds the agent's and the user's on it apart
 * @param {readonly import("../framework/application.js").ObligationRecord[]} obligations
 *   the view's obligations, of which each thread holds those its messages make
 * @param {import("../../types/domain.js").ContentVersion[]} markingRead
 * @param {boolean} ready
 */
export function readThreadRecords(
  threads,
  document,
  widgets,
  workflows,
  todos = [],
  obligations = [],
  markingRead = [],
  ready = true,
) {
  const locallyRead = new Set(markingRead.map(versionKey));
  /** @type {Map<string | undefined, {id: string, tag: string, state: import("../../types/domain.js").AuthoredWidget["state"]}[]>} */
  const unitsByMessage = new Map();
  for (const descriptor of document.descriptors.values()) {
    if (descriptor.document.kind !== "thread") continue;
    const units = unitsByMessage.get(descriptor.document.message) ?? [];
    units.push({
      id: descriptor.id,
      tag: descriptor.tag,
      state: widgets.get(descriptor.id)?.state ?? {},
    });
    unitsByMessage.set(descriptor.document.message, units);
  }
  return threads.map((thread) => {
    const unread = thread.unread.filter((item) => !locallyRead.has(versionKey(item)));
    const unreadMessages = new Set(unread.map((item) => item.message));
    const msgs = thread.msgs.map((message) => {
      const {
        markup,
        plainText,
        attention,
        session,
        publication,
        responds,
        start,
        title,
        ...record
      } = message;
      const units = unitsByMessage.get(message.id) ?? [];
      const authored = document.messageBodies?.get(message.id);
      if (markup && !authored)
        throw new Error(`Authored message ${message.id} has no captured body`);
      const body =
        markup && authored
          ? { kind: "authored", ...authored, units }
          : {
              kind: message.token
                ? "reaction"
                : message.suggestion
                  ? "suggestion"
                  : "prose",
              text: authored?.text ?? plainText ?? message.text ?? message.token ?? "",
            };
      const unitIds = new Set(units.map((unit) => unit.id));
      return {
        ...record,
        unread: unreadMessages.has(message.id),
        key: messageKey(message),
        body,
        // The message's own inputs, its first words and each rewrite of them, and the
        // actions on widgets frozen into it, in the published order `strongestWorkflow`
        // reads.
        workflows: workflows.filter(
          (workflow) =>
            workflow.message === message.id ||
            (workflow.subject.kind === "widget" && unitIds.has(workflow.subject.id)),
        ),
      };
    });
    const reactions = { key: threadKey(thread), resolved: thread.resolved, msgs };
    const messages = msgs.map((message) => ({
      ...message,
      reactions: ready
        ? reactionChoices(
            reactions,
            message,
            document.registry.$reactions?.tokens ?? {},
          )
        : null,
    }));
    const root = messages.find((message) => message.id === thread.root.id);
    if (!root) throw new Error(`Thread ${thread.id} has no root message`);
    return {
      id: thread.id,
      key: threadKey(thread),
      title: thread.title,
      root,
      msgs: messages,
      unread: Object.freeze(unread),
      anchor: thread.anchor,
      detached_from: thread.detached_from,
      rewritten_from: thread.rewritten_from,
      resolved: thread.resolved,
      settling: thread.settling ?? null,
      attention: thread.attention,
      // The obligations that stand in it: those widgets in its messages make, such as an
      // `lf-ask` the user owes words to there, and those its updates publish.
      obligations: obligations.filter((obligation) => obligation.thread === thread.id),
      // The agent's open to-dos on the thread: a reply that promised one says it is
      // still open (a to-do a reply opens takes the reply's id, `todos.py`), the first
      // is the one a thread waiting on a to-do waits on, and a running one is work the
      // thread's working message reads whoever's turn the thread is.
      todos: todos.filter(
        (todo) => todo.owner === "agent" && todo.thread === thread.id,
      ),
      // The user's open to-dos on the thread, which its head names with their Done: a
      // to-do on a thread has no place on the page (obligations/place.js), so the
      // thread draws it.
      userTodos: todos.filter(
        (todo) => todo.owner === "user" && todo.thread === thread.id,
      ),
      workflows: workflows.filter((workflow) => workflow.thread === thread.id),
      bare_reaction: thread.bare_reaction,
      seat: thread.seat,
      summaries: thread.summaries,
      offers: threadOffers(thread),
    };
  });
}
