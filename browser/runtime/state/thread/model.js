// @ts-check
/* Pure thread structure and turn-taking projected by the server.

   A reaction is a message whose content is an emoji, and takes its turn as words do
   (events.md, "Reactions"). The panel lists `discussed` threads only: a thread that holds
   only the reaction that opened it is a mark on its anchor (`bareReaction`). Every drawing
   of a thread, a card or the message parts a presentation names
   (records/thread/primary-reader.js), shows its turns: each message but the user's
   reactions, which stand as chips in the strip of the agent's message they are on. So a
   thread that grew out of a reaction opens on the mark, and an agent's emoji stands as
   its message, whose body records/thread/messages.js writes as its emoji, or as Deleted
   once the user takes the mark back (`deleted`). Whose turn a thread is is read
   from the complete browser Thread's `attention` and nothing else, the obligation
   record that speaks for it: a user obligation outranks concurrent agent work, which
   stays the card's secondary status.

   A thread's `id` is its one identity: the id the server keys it by, which every obligation,
   workflow, placement, and view names it by. Its `root` is its opening message, a
   message like any other, and what a reply or settlement addresses as its `parent`. A
   thread this tab opened goes by its pending message's id until the log answers. */
import { sameAnchor } from "../../base/anchor-coordinate.js";
import { PENDING } from "./identity.js";
import { kept, keptEach } from "../kept.js";

/** @typedef {import("../../../types/domain.js").Thread} Thread */
/** @typedef {import("../../../types/domain.js").Message} Message */
/** @typedef {import("../../../types/domain.js").Settlement} Settlement */
/** @typedef {import("../../../types/domain.js").Anchor} Anchor */
/** @typedef {NonNullable<import("../semantic-application.js").SemanticDocument["messageBodies"]> extends ReadonlyMap<string, ReadonlyMap<string, infer B>> ? B : never} CapturedBody */

/** @param {{emoji?: string}} message */
export const isReaction = (message) => Boolean(message.emoji);
/** @param {Pick<Message, "addressable">} message */
const isAddressable = (message) => message.addressable !== false;

// The reactions the user may choose on one of the agent's messages, each with the
// reaction of theirs in force on it that a press takes back (`inForce`).
/** @template {Pick<Message, "agent"> & {key: string}} T
 * @template {{emoji?: string}} S
 * @param {string} thread @param {T} message @param {boolean} latest
 * @param {Reactions} emoji @param {readonly S[]} inForce
 */
const reactionChoices = (thread, message, latest, emoji, inForce) => ({
  thread,
  message: message.key,
  latest,
  agent: message.agent,
  choices: emojiChoices(emoji, inForce),
});

// The offered reactions as choices on one target, each its emoji with the reaction in
// force a press takes back. The bar, a reply's strip and the margin form render these;
// each surface keeps its own face, and the emoji is the control's face and its name on
// all of them.
/** @template {{emoji?: string}} S
 * @param {Reactions} emoji the layer's `$reactions.emoji`
 * @param {readonly S[]} inForce
 */
export const emojiChoices = (emoji, inForce) =>
  emoji.map((choice) => ({
    emoji: choice,
    inForce: inForce.find((item) => item.emoji === choice) ?? null,
  }));
// The user's reaction on a message, which its strip draws as a chip.
/** @param {{id: string, emoji?: string, author?: string}} message @param {{root: {id: string}}} thread */
const chip = (message, thread) =>
  isReaction(message) && message.author === "user" && message.id !== thread.root.id;
/** @template {{id: string, emoji?: string, author?: string, [field: string]: unknown}} T @param {{msgs: readonly T[], root: {id: string}}} thread */
export const turns = (thread) =>
  thread.msgs.filter((message) => !chip(message, thread));
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

// Every name that reaches a thread: its key (`threadKey`), its own id, the id of each
// message in it, which a reply or settlement names as its `parent`, and the pending id
// a message this tab sent went by before the log named it. A key that is an attempt
// can't be another thread's name: an attempt is 32 hex digits (base/ids.js) or one of the
// server's prefixed ones, and the log's ids are 8 (`event_log.new_event_id`).
/** @template {{id: string, root: {attempt?: string}, msgs: readonly {id: string, attempt?: string}[]}} T
 * @param {readonly T[]} threads */
export function threadNames(threads) {
  /** @type {Map<string, T>} */
  const byName = new Map();
  for (const thread of threads) {
    byName.set(threadKey(thread), thread);
    byName.set(thread.id, thread);
    for (const message of thread.msgs) {
      byName.set(message.id, thread);
      if (message.attempt) byName.set(PENDING + message.attempt, thread);
    }
  }
  return byName;
}

// Where in `threads` the open conversations about each element stand, by the id of the
// element their anchor names (`section`): a resolved thread and a bare reaction stand
// under none, and nor does a thread with no anchor, which is about the page as a whole.
/** @param {readonly {anchor: {section?: string | null} | null, resolved?: unknown, bare_reaction: boolean}[]} threads */
export function threadsBySection(threads) {
  /** @type {Map<string, number[]>} */
  const bySection = new Map();
  threads.forEach((thread, at) => {
    const section = thread.anchor?.section;
    if (!section || thread.resolved || !discussed(thread)) return;
    const about = bySection.get(section);
    if (about) about.push(at);
    else bySection.set(section, [at]);
  });
  return bySection;
}

// A message whose words the user may rewrite: one of their own that the log holds, with
// words to revise. A reaction or a bare drawing has none (`event_contracts._edit_error`).
/** @param {{author?: string, pending?: boolean, emoji?: string, text?: string | undefined}} message */
export const editable = (message) =>
  message.author === "user" &&
  !message.pending &&
  !message.emoji &&
  Boolean(message.text);

// A message its author deleted: a rewrite took all its words, and no drawing stands in
// for them, or they took it back while something stood on it (events.md, "Messages").
// It keeps its place in its thread, where answers to it still stand.
/** @param {{text?: string | undefined, edited?: unknown, withdrawn?: unknown, drawing?: unknown}} message */
export const deleted = (message) =>
  Boolean(message.withdrawn) ||
  (Boolean(message.edited) && !message.text && !message.drawing);

/** @template {{readonly bare_reaction: boolean, readonly root: {readonly emoji?: string | null}}} T
 * @param {T} thread
 * @returns {thread is T & {bare_reaction: true, root: T["root"] & {emoji: string}}} */
export const bareReaction = (thread) => thread.bare_reaction;
/** @param {Pick<Thread, "bare_reaction">} thread */
export const discussed = (thread) => !thread.bare_reaction;
// A thread record's unread versions (`readThreadRecords`), in log order.
/** @typedef {{readonly unread: readonly unknown[]}} Unread */
/** Whether a thread holds words the user hasn't read.
 * @param {Unread} thread */
const hasUnread = (thread) => thread.unread.length > 0;
/**
 * Whether a thread announces the words that reach it: only while it stands open. A
 * resolved thread's unread words are no news, so the news the panel counts never
 * outnumbers the open threads; the user's reply reopens its thread, and the user chose
 * to leave what reaches a closed one unannounced, as the agent's message in a thread
 * they resolved is.
 * @param {{readonly resolved: unknown}} thread */
export const announces = (thread) => !thread.resolved;
/**
 * Whether a thread is news: one that announces its words (`announces`) and holds some
 * the user hasn't read.
 * @param {Pick<Thread, "resolved"> & Unread} thread */
export const isNews = (thread) => announces(thread) && hasUnread(thread);
/**
 * What the panel counts of the threads it lists: those still open, which Threads' tab
 * says, and those that are news (`isNews`), which the leaf's dot says. A page's
 * served row counts the same way
 * (`served_state.thread.thread_counts`); tests/thread_count_cases.json holds both.
 * @param {readonly (Pick<Thread, "bare_reaction" | "resolved"> & Unread)[]} threads
 */
export function threadCounts(threads) {
  const listed = threads.filter(discussed);
  return {
    open: listed.filter((thread) => !thread.resolved).length,
    unread: listed.filter(isNews).length,
  };
}
/**
 * Where in the log a thread last changed, its event's `seq`, which Threads lists its
 * rows by: a closed thread's closing, the event its row's age dates; an open thread's
 * latest turn as it last moved (`moved`), so a rewrite counts. The user's own reply,
 * rewrite or resolve on its way, which the log doesn't hold yet, is newer than all of
 * it. A reply still streaming counts once the log holds it. A message that reaches a closed thread without reopening it, as the
 * agent's unannounced one does, leaves the thread where its closing put it, so a row's
 * place and its age agree.
 * @template {{id: string, token?: string, seq?: number, edited?: {seq?: number, ts: string} | undefined, [field: string]: unknown}} T
 * @param {{msgs: readonly T[], root: {id: string}, resolved: {seq?: number | undefined} | null}} thread */
export function lastChange(thread) {
  if (thread.resolved) return thread.resolved.seq ?? Infinity;
  let last = -Infinity;
  for (const message of thread.msgs)
    if (!message.provisional) last = Math.max(last, moved(message).seq ?? Infinity);
  return last;
}
/**
 * `items` newest first by `at`, the later of two that tie first, as the later of two
 * threads in the log's order is the later started.
 * @template T @param {readonly T[]} items @param {(item: T) => number} at */
export const newestFirst = (items, at) =>
  items
    .map((item) => ({ item, at: at(item) }))
    .reverse()
    .sort((a, b) => b.at - a.at)
    .map(({ item }) => item);
// Which widget's seat a message the server has not seen stands in, a pending thread's
// root or the comment being written, by the rule `seat_root` reads the log by: an
// element anchor naming that widget and carrying nothing else. Spelled again here
// because a thread that seated itself differently for the half-second before it lands
// would move once it arrived.
/** @param {{anchor?: import("../../../types/domain.js").Anchor | null | undefined, about?: string | null | undefined}} message */
export const seatOf = (message) =>
  message.about || !message.anchor || Object.keys(message.anchor).length !== 1
    ? null
    : (message.anchor.section ?? null);

// The user's own pending gestures, folded into the server's threads in the order this
// tab made them, as `events.build_threads` folds the log. A comment opens a thread where
// it was written; a reply joins the thread it answers; a rewrite shows as its message's
// new words; settlement changes the thread's state, and a turn reopens a resolved one;
// taking back a message takes its words or mark away, and taking back a rewrite gives
// its message the words it replaced. Whether a message taken back keeps its place,
// and a thread it opened stands, depends on what else the log holds, so the press
// leaves the message's place Deleted and the server's reading decides; a mark drawn
// as a chip, or alone on the page, has no place of its own and comes off. They leave again when the server accepts or refuses them, so
// this is a reading of the same outbox and log the server projects rather than a second
// store beside it.
//
// The fold draws only what a gesture settles by itself. Whose turn a served thread is
// depends on what the rest of the log leaves in force, so it keeps the attention the
// server read until the log answers the gesture. A thread the user opened with words has
// no log beyond the gesture: it waits on the agent for its send, whose record the
// publisher makes under the pending id its local workflow shares
// (`host/application.js`, `localUpdates`), and asks nothing yet.
/** @param {{id: string}} turn @returns {import("../../../types/domain.js").Attention} */
const sending = (turn) => `update:${turn.id}`;

// A message as the log's answer will draw it once the rewrite the user is taking back
// is gone: with the words that rewrite replaced, under the rewrite before it, if any.
/** @param {Thread} thread @param {Thread["msgs"][number]} message
 * @param {ReadonlySet<string>} withdrawn */
function unedited(thread, message, withdrawn) {
  const { edited, ...rest } = message;
  if (!edited || !withdrawn.has(edited.id)) return message;
  const revisions = thread.revisions.filter((edit) => edit.message === message.id);
  const at = revisions.findIndex(({ id }) => id === edited.id);
  const before = revisions.slice(0, at).findLast(({ id }) => !withdrawn.has(id));
  if (!before) return { ...rest, text: edited.was, content_version: message.id };
  const { id, ts, was } = before;
  return {
    ...rest,
    text: edited.was,
    content_version: id,
    edited: "seq" in before ? { id, seq: before.seq, ts, was } : { id, ts, was },
  };
}

// A message the user is taking back, as the press draws it: in its place, with no words
// and no mark, saying the words it was sent with, which its first rewrite replaced, as
// the log's placeholder does (`events.message_reading`).
/** @param {Thread} thread @param {Thread["msgs"][number]} message
 * @returns {Thread["msgs"][number]} */
function takenBack(thread, message) {
  const { emoji, drawing, suggestion, edited, ...rest } = message;
  const sent = thread.revisions.find((edit) => edit.message === message.id)?.was;
  const was = emoji ?? sent ?? message.text ?? "";
  return {
    ...rest,
    text: "",
    content_version: message.id,
    withdrawn: { was, pending: true },
  };
}

// `gestures` are the ledger's thread gestures, oldest first: each comment, reply or
// rewrite as the thread draws it, each settlement with the `localParent` its pending
// parent went by, and each undo.
/** @param {readonly Thread[]} threads
 * @param {readonly import("../../../types/domain.js").ThreadGesture[]} gestures
 * @returns {Thread[]}
 */
export function foldThreads(threads, gestures) {
  if (!gestures.length) return [...threads];
  const withdrawn = new Set(
    gestures.flatMap((gesture) => (gesture.kind === "undo" ? [gesture.undoes] : [])),
  );
  // Each served thread a gesture leaves alone stands as served, the very object, so
  // the readings after this one can tell it unchanged by identity. `owned` holds the
  // threads this fold made, which a gesture may change in place.
  /** @type {Set<Thread>} */
  const owned = new Set();
  /** @param {Thread} thread @returns {Thread[]} */
  const without = (thread) => {
    if (thread.bare_reaction && withdrawn.has(thread.root.id)) return [];
    const msgs = thread.msgs.flatMap((message) =>
      !withdrawn.has(message.id) || message.withdrawn
        ? [unedited(thread, message, withdrawn)]
        : chip(message, thread)
          ? []
          : [takenBack(thread, message)],
    );
    // A thread whose closing event the user is taking back stands open again; the
    // log's answer restores any earlier closure.
    const reopened = Boolean(
      thread.resolved && "id" in thread.resolved && withdrawn.has(thread.resolved.id),
    );
    if (
      !reopened &&
      msgs.length === thread.msgs.length &&
      msgs.every((message, at) => message === thread.msgs[at])
    )
      return [thread];
    /** @type {Thread} */
    const copy = {
      ...thread,
      root: msgs.find(({ id }) => id === thread.root.id) ?? thread.root,
      msgs,
      ...(reopened ? { resolved: null } : {}),
    };
    owned.add(copy);
    return [copy];
  };
  /** @type {Thread[]} */
  const copies = withdrawn.size ? threads.flatMap(without) : [...threads];
  // A thread the user opened answers to two names for as long as this tab holds a
  // reply written against the first: the one this page gave it, and the one the log
  // gave back. Both reach the one thread, so a reply written into the card a
  // send had just drawn stays in it when the answer arrives.
  const byName = threadNames(copies);
  // A served thread a gesture changes is copied first, where it stands in the list
  // and under each of its names.
  /** @param {Thread} thread */
  const own = (thread) => {
    if (owned.has(thread)) return thread;
    const copy = { ...thread };
    owned.add(copy);
    copies[copies.indexOf(thread)] = copy;
    for (const [name, named] of threadNames([thread]))
      if (named === thread) byName.set(name, copy);
    return copy;
  };
  /** @type {Thread[]} */
  const opened = [];
  for (const gesture of gestures) {
    if (gesture.kind === "comment") {
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
        bare_reaction: isReaction(gesture),
        seat: seatOf(gesture),
        summaries: [],
        unread: {},
        attention: sending(gesture),
      };
      opened.push(thread);
      owned.add(thread);
      byName.set(gesture.id, thread);
    } else if (gesture.kind === "reply") {
      const named = byName.get(gesture.parent);
      if (!named) continue;
      const thread = own(named);
      // A reply still streaming stands last, where the log will take its answer, so the
      // user's message joins the thread above it and its acceptance moves nothing.
      const streaming = thread.msgs.at(-1)?.provisional ? 1 : 0;
      thread.msgs = thread.msgs.toSpliced(thread.msgs.length - streaming, 0, gesture);
      thread.resolved = null;
    } else if (gesture.kind === "edit") {
      // An edit shows as its message's new words, and is a turn as a reply is, under
      // the edit's own pending id (`events.exchange`).
      const named = byName.get(gesture.message);
      const at = named?.msgs.findIndex(({ id }) => id === gesture.message) ?? -1;
      const message = named?.msgs[at];
      if (!named || !message) continue;
      const thread = own(named);
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
      const named =
        byName.get(gesture.parent) ??
        (gesture.localParent ? byName.get(gesture.localParent) : undefined);
      if (!named) continue;
      own(named).resolved =
        gesture.kind === "resolve" ? { author: "user", pending: true } : null;
    }
  }
  for (const thread of opened)
    thread.bare_reaction = isReaction(thread.root) && thread.msgs.length === 1;
  return [...copies, ...opened];
}

// The user's reactions in force on exactly this anchor — the bar's own question, asked
// so its chips can say which emoji are already there and a press can take one back:
// the root of each open thread a reaction of theirs opened there, whether or not the
// agent has answered it. Anchors are compared as records, the way the file compares
// them.
/** @template {Pick<Thread, "resolved" | "anchor"> & {root: {emoji?: string, author?: string}}} T
 * @param {readonly T[]} threads @param {Anchor} anchor
 * @returns {T["root"][]} */
export const reactionsAt = (threads, anchor) =>
  threads
    .filter(
      (thread) =>
        isReaction(thread.root) &&
        thread.root.author === "user" &&
        !thread.resolved &&
        sameAnchor(thread.anchor, anchor),
    )
    .map((thread) => thread.root);

/** @param {Pick<Thread, "seat">} thread */
export const seatRoot = (thread) => thread.seat;

// When a message last moved: its latest edit, else its own arrival. Every ordering that
// asks what is newest — the first unread, news, Threads' rows — reads this,
// so an agent message edited today is today's in all of them. A message or rewrite still
// being sent carries the clock the user's gesture gave it and no log position yet.
/** @param {{edited?: {seq?: number, ts: string} | undefined, seq?: number, ts?: string}} message */
export const moved = (message) =>
  message.edited
    ? { seq: message.edited.seq ?? null, ts: message.edited.ts }
    : { seq: message.seq ?? null, ts: message.ts ?? null };

/** @param {import("../../../types/domain.js").ContentVersion} item */
const versionKey = ({ message, version }) => `${message}\u0000${version}`;

/* Public thread values. The publisher calls this after folding local gestures
   and admitted obligations. Authored source stays with its prepared document; only
   captured words, registry identities and current unit state cross this boundary.

   A Thread's `unread` is the server's reading of the agent content versions the user
   has not taken in, by message, less those this tab is marking read now: the page
   draws them read in the turn it sends that, and the answer confirms rather than
   decides it. A record lists them in its messages' order.

   Each thread's record is kept (`state/kept.js`) by the served thread and what it holds:
   the versions this tab is marking read of it, its workflows, obligations and to-dos,
   the widgets in its messages with their state, and its messages' captured words
   (`messageBodies`), which adoption keeps by thread while they read the same. Within a
   thread made again, each message's reading is kept by the message and what it holds,
   so a reply to a long thread reads one message and the reactions it touches. A
   workflow stands in the thread of the message it serves, so the thread's workflows
   hold every message's. */

// The reactions a registry declares none of.
/** @typedef {readonly string[]} Reactions */
/** @type {Reactions} */
const NO_REACTIONS = Object.freeze([]);

/** @type {readonly never[]} */
const NONE = Object.freeze([]);

/** @template T @param {readonly T[]} items @param {(item: T) => string | null | undefined} key */
function grouped(items, key) {
  const groups = Map.groupBy(items, key);
  groups.delete(null);
  groups.delete(undefined);
  return /** @type {Map<string, T[]>} */ (groups);
}

/** @typedef {{id: string, tag: string, message: string | undefined, state: import("../../../types/domain.js").AuthoredWidget["state"]}} Unit */
/** @typedef {import("../../../types/domain.js").Workflow} Workflow */
/** @typedef {import("../semantic-application.js").ObligationRecord} ObligationRecord */
/** @typedef {import("../../../types/domain.js").ContentVersion} ContentVersion */
/** @typedef {ReadonlyMap<string, CapturedBody>} ThreadBodies */

// A widget whose state no action has set.
/** @type {Unit["state"]} */
const NO_STATE = Object.freeze({});

// Each list a thread holds, selected once for every thread while the lists stand.
const byThread = kept(
  /** @param {readonly Workflow[]} workflows @param {readonly ObligationRecord[]} obligations */
  (workflows, obligations) => ({
    workflows: grouped(workflows, (workflow) => workflow.thread),
    obligations: grouped(obligations, (obligation) => obligation.thread),
  }),
);
// What this tab is marking read, by message.
const markingByMessage = kept((/** @type {readonly ContentVersion[]} */ marking) =>
  grouped(marking, (item) => item.message),
);
// A widget in a thread's message, with its state, kept while that state stands.
const unitOf = keptEach(
  /** @param {import("../semantic-application.js").WidgetDescriptor} descriptor
   * @param {Unit["state"]} state @returns {Unit} */
  (descriptor, state) => ({
    id: descriptor.id,
    tag: descriptor.tag,
    message:
      descriptor.document.kind === "thread" ? descriptor.document.message : undefined,
    state,
  }),
);
// The widgets in each thread's messages, with their state.
const unitsByThread = kept(
  /** @param {import("../semantic-application.js").SemanticDocument["descriptors"]} descriptors
   * @param {ReturnType<typeof import("../projection/model.js").foldWidgetStates>} widgets */
  (descriptors, widgets) => {
    /** @type {Map<string | undefined, Unit[]>} */
    const units = new Map();
    for (const descriptor of descriptors.values()) {
      if (descriptor.document.kind !== "thread") continue;
      const unit = unitOf(descriptor, widgets.get(descriptor.id)?.state ?? NO_STATE);
      const held = units.get(descriptor.document.thread);
      if (held) held.push(unit);
      else units.set(descriptor.document.thread, [unit]);
    }
    return units;
  },
);

// A message's own reading: its fields less those its turn's admission alone carries,
// its captured words with the state of the widgets in them, and the workflows serving
// it, the message's own inputs and the actions on widgets in it, in the published order
// `strongestWorkflow` reads.
const messageReading = keptEach(
  /** @param {Message} message @param {string} thread @param {boolean} unread
   * @param {readonly Workflow[]} workflows @param {readonly Unit[]} units
   * @param {CapturedBody | undefined} authored */
  (message, thread, unread, workflows, units, authored) => {
    const {
      html,
      plainText,
      attention,
      session,
      publication,
      responds,
      start,
      title,
      ...record
    } = message;
    if (html && !authored)
      throw new Error(`Authored message ${message.id} has no captured body`);
    /** @type {({kind: "authored", units: readonly Unit[]} & CapturedBody)
     * | {kind: "reaction" | "suggestion" | "prose", text: string}} */
    const body =
      html && authored
        ? { kind: "authored", ...authored, units }
        : {
            kind: message.emoji
              ? "reaction"
              : message.suggestion
                ? "suggestion"
                : "prose",
            text: authored?.text ?? plainText ?? message.text ?? message.emoji ?? "",
          };
    return { ...record, thread, unread, key: messageKey(message), body, workflows };
  },
);
// Public readings carry presentation state, including a prior reading's absent fields
// explicitly restored while news is held. They preserve the values an admitted message
// can carry without claiming its admission-only correlations.
/** @typedef {Omit<ReturnType<typeof messageReading>, "text" | "edited" | "provisional" | "completed_by"> & {
 * text?: Message["text"], edited?: Message["edited"],
 * provisional?: Message["provisional"], completed_by?: Message["completed_by"]
 * }} PublishedMessage */
// A message's reading with the reactions the user may choose on it, where it is one of
// the agent's they may answer, each with the user's reaction in force on it that a
// press takes back. The publisher supplies the vocabulary; controls and commands read
// these same choices, including the exact reaction in force an explicit removal
// withdraws.
const withReactions = keptEach(
  /** @param {PublishedMessage} message @param {string} thread @param {boolean} choosing
   * @param {boolean} latest @param {Reactions} emoji
   * @param {readonly PublishedMessage[]} inForce */
  (message, thread, choosing, latest, emoji, inForce) => ({
    ...message,
    reactions: choosing
      ? reactionChoices(thread, message, latest, emoji, inForce)
      : null,
  }),
);

// One thread's record.
const threadRecord = keptEach(
  /** @param {Thread} thread @param {boolean} ready
   * @param {Reactions} emoji
   * @param {readonly ContentVersion[]} marking what this tab is marking read of its messages
   * @param {readonly Workflow[]} workflows @param {readonly ObligationRecord[]} obligations
   * @param {readonly Unit[]} units @param {ThreadBodies | undefined} bodies */
  (thread, ready, emoji, marking, workflows, obligations, units, bodies) => {
    const key = threadKey(thread);
    const locallyRead = new Set(marking.map(versionKey));
    /** @type {ContentVersion[]} */
    const unread = thread.msgs.flatMap(({ id }) => {
      const version = thread.unread[id];
      return version !== undefined &&
        !locallyRead.has(versionKey({ message: id, version }))
        ? [{ message: id, version }]
        : [];
    });
    const unreadMessages = new Set(unread.map((item) => item.message));
    const unitsIn = grouped(units, (unit) => unit.message);
    const workflowsOf = grouped(workflows, (workflow) => workflow.message);
    const workflowsOn = grouped(workflows, (workflow) =>
      workflow.subject.kind === "widget" ? workflow.subject.id : null,
    );
    /** @param {Message} message @returns {readonly Workflow[]} */
    const messageWorkflows = (message) => {
      const own = workflowsOf.get(message.id) ?? NONE;
      const inIt = unitsIn.get(message.id);
      if (!inIt) return own;
      const serving = new Set([
        ...own,
        ...inIt.flatMap((unit) => workflowsOn.get(unit.id) ?? NONE),
      ]);
      return workflows.filter((workflow) => serving.has(workflow));
    };
    const msgs = thread.msgs.map(
      (message) =>
        /** @type {PublishedMessage} */ (
          messageReading(
            message,
            key,
            unreadMessages.has(message.id),
            messageWorkflows(message),
            unitsIn.get(message.id) ?? NONE,
            bodies?.get(message.id),
          )
        ),
    );
    // A user's reaction in force on each message, and the agent's newest message the
    // user may address, read once for the thread rather than once per message.
    const reacts = ready && emoji.length > 0 && !thread.resolved;
    const latest = msgs.findLast(
      (message) => message.author === "agent" && isAddressable(message),
    );
    const reactionsOn = grouped(
      msgs.filter((message) => chip(message, thread)),
      (message) => message.parent,
    );
    const published = msgs.map((message) => {
      const choosing = reacts && message.author === "agent" && isAddressable(message);
      return withReactions(
        message,
        key,
        choosing,
        choosing && latest === message,
        emoji,
        choosing ? (reactionsOn.get(message.id) ?? NONE) : NONE,
      );
    });
    const root = published.find((message) => message.id === thread.root.id);
    if (!root) throw new Error(`Thread ${thread.id} has no root message`);
    return {
      id: thread.id,
      key,
      title: thread.title,
      root,
      msgs: published,
      // What a drawing of the thread shows (`turns`), for a reader that holds only the
      // record, as a package's presentation does.
      turns: Object.freeze(turns({ msgs: published, root })),
      unread: Object.freeze(unread),
      anchor: thread.anchor,
      detached_from: thread.detached_from,
      rewritten_from: thread.rewritten_from,
      resolved: thread.resolved,
      // The record that speaks for the thread, one of those standing in it: whose
      // turn it is and where it stands.
      attention:
        obligations.find((obligation) => obligation.id === thread.attention) ?? null,
      // The obligations that stand in it: those widgets in its messages make, such as
      // an `lf-options` the user owes a pick there, those its updates publish, and the
      // agent's to-dos on it. A reply that promised a to-do says it is still open (a
      // to-do a reply opens takes the reply's id, `todos.py`), and a running one is
      // work the thread's working message reads whoever's turn the thread is.
      obligations,
      workflows,
      bare_reaction: thread.bare_reaction,
      seat: thread.seat,
      summaries: thread.summaries,
    };
  },
);

/** Each thread's record, kept until the thread or something it holds moves (state/kept.js).
 * @param {readonly Thread[]} threads
 * @param {import("../semantic-application.js").SemanticDocument} document
 * @param {ReturnType<typeof import("../projection/model.js").foldWidgetStates>} widgets
 * @param {readonly Workflow[]} workflows
 * @param {readonly ObligationRecord[]} obligations
 *   the view's obligations, of which each thread holds those that stand in it
 * @param {readonly ContentVersion[]} markingRead
 * @param {boolean} ready
 */
export function readThreadRecords(
  threads,
  document,
  widgets,
  workflows,
  obligations = NONE,
  markingRead = NONE,
  ready = true,
) {
  const emoji = document.registry.$reactions?.emoji ?? NO_REACTIONS;
  const lists = byThread(workflows, obligations);
  const marking = markingByMessage(markingRead);
  const units = unitsByThread(document.descriptors, widgets);
  return threads.map((thread) =>
    threadRecord(
      thread,
      ready,
      emoji,
      Object.keys(thread.unread).flatMap((id) => marking.get(id) ?? []),
      lists.workflows.get(thread.id) ?? NONE,
      lists.obligations.get(thread.id) ?? NONE,
      units.get(thread.id) ?? NONE,
      document.messageBodies?.get(thread.id),
    ),
  );
}
