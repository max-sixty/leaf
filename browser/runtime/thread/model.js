// @ts-check
/* Pure thread structure and turn-taking projected by the server.

   This reads projected threads by `isReaction`, `spoken`, `turns`, and `bareReaction`,
   the names `events.py` reads them by. The panel lists `discussed` threads only.
   Every drawing of a thread, a card or the message parts a presentation names
   (thread/primary-reader.js), shows its turns: its spoken messages and its root, so a
   thread that grew out of a reaction opens on the mark, whose body thread/messages.js
   writes as the glyph and its word, or as Deleted once the user takes the mark back
   (`deleted`), and any other reaction stands as its chip on the message it answers. Whose turn a thread is is read
   from the complete browser Thread's `attention` and nothing else, the obligation
   record that speaks for it: a user obligation outranks concurrent agent work, which
   stays the card's secondary status.

   A thread's `id` is its one identity: the id the server keys it by, which every obligation,
   workflow, placement, and view names it by. Its `root` is its opening message, a
   message like any other, and what a reply or settlement addresses as its `parent`. A
   thread this tab opened goes by its pending message's id until the log answers. */
import { sameAnchor } from "../anchor-coordinate.js";
import { PENDING } from "./identity.js";
import { BETWEEN, keptReadings } from "../kept.js";

/** @typedef {import("../../types/domain.js").Thread} Thread */
/** @typedef {import("../../types/domain.js").Message} Message */
/** @typedef {import("../../types/domain.js").Settlement} Settlement */
/** @typedef {import("../../types/domain.js").Anchor} Anchor */
/** @typedef {NonNullable<import("../framework/application.js").SemanticDocument["messageBodies"]> extends ReadonlyMap<string, infer B> ? B : never} CapturedBody */

/** @param {{token?: string}} message */
export const isReaction = (message) => Boolean(message.token);
/** @param {Pick<Message, "addressable">} message */
const isAddressable = (message) => message.addressable !== false;

// The reactions the user may choose on one of the agent's messages, each with the
// reaction of theirs in force on it that a press takes back (`inForce`).
/** @template {Pick<Message, "agent"> & {key: string}} T
 * @template {{token?: string}} S
 * @param {string} thread @param {T} message @param {boolean} latest
 * @param {Record<string, {glyph: string}>} tokens @param {readonly S[]} inForce
 */
const reactionChoices = (thread, message, latest, tokens, inForce) => ({
  thread,
  message: message.key,
  latest,
  agent: message.agent,
  choices: tokenChoices(tokens, inForce),
});

// The declared reaction tokens as choices on one target, each with the reaction in force
// a press takes back. The bar, a reply's strip and the margin form render these; each
// surface keeps its own face, and the token names the control on all of them.
/** @template {{token?: string}} S
 * @param {Record<string, {glyph: string}>} tokens
 * @param {readonly S[]} inForce
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

// Every name that reaches a thread: its key (`threadKey`), its own id, the id of each
// message in it, which a reply or settlement names as its `parent`, and the pending id
// a message this tab sent went by before the log named it. A key that is an attempt
// can't be another thread's name: an attempt is 32 hex digits (ids.js) or one of the
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
/** @param {{author?: string, pending?: boolean, token?: string, text?: string | undefined}} message */
export const editable = (message) =>
  message.author === "user" &&
  !message.pending &&
  !message.token &&
  Boolean(message.text);

// A message its author deleted: a rewrite took all its words, and no drawing stands in
// for them, or they took it back while something stood on it (events.md, "Messages").
// It keeps its place in its thread, where answers to it still stand.
/** @param {{text?: string | undefined, edited?: unknown, withdrawn?: unknown, drawing?: unknown}} message */
export const deleted = (message) =>
  Boolean(message.withdrawn) ||
  (Boolean(message.edited) && !message.text && !message.drawing);

/** @template {{readonly bare_reaction: boolean, readonly root: {readonly token?: string | null}}} T
 * @param {T} thread
 * @returns {thread is T & {bare_reaction: true, root: T["root"] & {token: string}}} */
export const bareReaction = (thread) => thread.bare_reaction;
/** @param {Pick<Thread, "bare_reaction">} thread */
export const discussed = (thread) => !thread.bare_reaction;
// A thread record's unread versions (`threadRecordReader`), in log order.
/** @typedef {{readonly unread: readonly unknown[]}} Unread */
/** Whether a thread holds words the user hasn't read.
 * @param {Unread} thread */
const hasUnread = (thread) => thread.unread.length > 0;
/**
 * Whether a thread is news: still open and holding words the user hasn't read. A
 * resolved thread's unread words aren't, so the news the panel counts never outnumbers
 * the open threads; a reply reopens its thread, and the user chose on 21 October to
 * leave what reaches a closed one unannounced.
 * @param {Pick<Thread, "resolved"> & Unread} thread */
export const isNews = (thread) => !thread.resolved && hasUnread(thread);
/**
 * What the panel counts of the threads it lists: those still open, which Threads' tab
 * says, and those that are news (`isNews`), which the On Me mark's dot says. A page's
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
// (`application.js`, `localUpdates`), and asks nothing yet.
/** @param {{id: string}} turn @returns {import("../../types/domain.js").Attention} */
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
  const { token, drawing, suggestion, edited, ...rest } = message;
  const sent = thread.revisions.find((edit) => edit.message === message.id)?.was;
  const was = token ?? sent ?? message.text ?? "";
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
 * @param {readonly import("../../types/domain.js").ThreadGesture[]} gestures
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
        : isReaction(message) && message.id !== thread.root.id
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
        unread: {},
        attention: reaction ? null : sending(gesture),
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
      // A reaction is no turn, so it reopens nothing.
      if (!isReaction(gesture)) thread.resolved = null;
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
        !discussed(thread) && !thread.resolved && sameAnchor(thread.anchor, anchor),
    )
    .map((thread) => thread.root);

/** @param {Pick<Thread, "seat">} thread */
export const seatRoot = (thread) => thread.seat;

// When a message last moved: its latest edit, else its own arrival. Every ordering that
// asks what is newest in a thread — the first unread, news — reads this,
// so an agent message edited today is today's in all of them. A message still being
// sent carries the clock the user's gesture gave it and no log position yet.
/** @param {{edited?: {seq?: number, ts: string} | undefined, seq?: number, ts?: string}} message */
export const moved = (message) => ({
  seq: message.edited?.seq ?? message.seq ?? null,
  ts: message.edited?.ts ?? message.ts ?? null,
});

// When a thread last moved: the latest move of any of its turns.
/** @param {{msgs: readonly {id: string, token?: string, edited?: {seq?: number, ts: string} | undefined, seq?: number, ts?: string}[], root: {id: string}}} thread */
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
   has not taken in, by message, less those this tab is marking read now: the page
   draws them read in the turn it sends that, and the answer confirms rather than
   decides it. A record lists them in its messages' order.

   A reader made by `threadRecordReader` keeps each thread's record (`kept.js`), and
   reads it again only where the thread or something it holds has changed: the served
   thread, its unread versions, workflows, obligations and to-dos, and the state of the
   widgets frozen into its messages. Within a thread it reads again, it keeps each
   message's reading in turn, so a reply to a long thread reads one message and the
   reactions it touches. A message's captured words (`messageBodies`) are prepared from
   the message itself, so the message stands for them. A workflow stands in the thread
   of the message it serves, so the thread's workflows hold every message's. */

// The reactions a registry declares none of.
/** @type {Record<string, {glyph: string}>} */
const NO_TOKENS = Object.freeze({});

/** @type {readonly never[]} */
const NONE = Object.freeze([]);

/** @template T @param {readonly T[]} items @param {(item: T) => string | null | undefined} key */
function grouped(items, key) {
  /** @type {Map<string, T[]>} */
  const groups = new Map();
  for (const item of items) {
    const name = key(item);
    if (name == null) continue;
    const group = groups.get(name);
    if (group) group.push(item);
    else groups.set(name, [item]);
  }
  return groups;
}

/** @typedef {{id: string, tag: string, state: import("../../types/domain.js").AuthoredWidget["state"]}} Unit */

export function threadRecordReader() {
  // Each thread's record, beside the readings of its messages: `bases`, a message's
  // reading of its own, and `messages`, that reading with the reactions on it.
  /** @type {ReturnType<typeof keptReadings<{record: unknown, bases: ReturnType<typeof keptReadings<unknown>>, messages: ReturnType<typeof keptReadings<unknown>>}>>} */
  const records = keptReadings();
  /** @param {readonly Thread[]} threads
   * @param {import("../framework/application.js").SemanticDocument} document
   * @param {ReturnType<typeof import("../projection/model.js").foldWidgetStates>} widgets
   * @param {import("../framework/application.js").Workflow[]} workflows
   * @param {readonly import("../framework/application.js").ObligationRecord[]} obligations
   *   the view's obligations, of which each thread holds those that stand in it
   * @param {import("../../types/domain.js").ContentVersion[]} markingRead
   * @param {boolean} ready
   */
  return function readThreadRecords(
    threads,
    document,
    widgets,
    workflows,
    obligations = [],
    markingRead = [],
    ready = true,
  ) {
    const locallyRead = new Set(markingRead.map(versionKey));
    const markingIn = grouped(markingRead, (item) => item.message);
    const tokens = document.registry.$reactions?.tokens ?? NO_TOKENS;
    const reacts = ready && Object.keys(tokens).length > 0;
    // The widgets frozen into each message, and into each thread, with their state.
    /** @type {Map<string | undefined, Unit[]>} */
    const unitsByMessage = new Map();
    /** @type {Map<string | undefined, Unit[]>} */
    const unitsByThread = new Map();
    for (const descriptor of document.descriptors.values()) {
      if (descriptor.document.kind !== "thread") continue;
      const unit = {
        id: descriptor.id,
        tag: descriptor.tag,
        state: widgets.get(descriptor.id)?.state ?? {},
      };
      for (const [by, key] of /** @type {const} */ ([
        [unitsByMessage, descriptor.document.message],
        [unitsByThread, descriptor.document.thread],
      ])) {
        const units = by.get(key);
        if (units) units.push(unit);
        else by.set(key, [unit]);
      }
    }
    /** @param {readonly Unit[] | undefined} units */
    const unitInputs = (units) =>
      (units ?? NONE).flatMap((unit) => [unit.id, unit.tag, unit.state]);
    // Each list a thread or message holds, selected once for every thread, in the
    // published order.
    /** @type {Map<unknown, number> | undefined} */
    let published;
    const workflowsIn = grouped(workflows, (workflow) => workflow.thread);
    const workflowsOf = grouped(workflows, (workflow) => workflow.message);
    const workflowsOn = grouped(workflows, (workflow) =>
      workflow.subject.kind === "widget" ? workflow.subject.id : null,
    );
    const obligationsIn = grouped(obligations, (obligation) => obligation.thread);
    // The message's own inputs, its first words and each rewrite of them, and the
    // actions on widgets frozen into it, in the published order `strongestWorkflow`
    // reads.
    /** @param {Message} message */
    const messageWorkflows = (message) => {
      const own = workflowsOf.get(message.id) ?? [];
      const units = unitsByMessage.get(message.id);
      if (!units) return own;
      const all = new Set([
        ...own,
        ...units.flatMap((unit) => workflowsOn.get(unit.id) ?? []),
      ]);
      const order = (published ??= new Map(workflows.map((each, at) => [each, at])));
      return [...all].sort(
        (a, b) =>
          /** @type {number} */ (order.get(a)) - /** @type {number} */ (order.get(b)),
      );
    };
    /** @param {Message} message @param {boolean} unread @param {string} thread */
    const readMessage = (message, unread, thread) => {
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
      /** @type {({kind: "authored", units: typeof units} & CapturedBody)
       * | {kind: "reaction" | "suggestion" | "prose", text: string}} */
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
      return {
        ...record,
        thread,
        unread,
        key: messageKey(message),
        body,
        workflows: messageWorkflows(message),
      };
    };
    // Public readings carry presentation state, including a prior reading's absent
    // fields explicitly restored while news is held. They preserve the values an
    // admitted message can carry without claiming its admission-only correlations.
    /** @typedef {Omit<ReturnType<typeof readMessage>, "text" | "edited" | "provisional" | "completed_by"> & {
     * text?: Message["text"], edited?: Message["edited"],
     * provisional?: Message["provisional"], completed_by?: Message["completed_by"]
     * }} PublishedMessage */
    /** @param {Thread} thread
     * @param {{bases: ReturnType<typeof keptReadings<unknown>>, messages: ReturnType<typeof keptReadings<unknown>>} | undefined} earlier */
    const readRecord = (thread, earlier) => {
      const key = threadKey(thread);
      /** @type {import("../../types/domain.js").ContentVersion[]} */
      const unread = thread.msgs.flatMap(({ id }) => {
        const version = thread.unread[id];
        return version !== undefined &&
          !locallyRead.has(versionKey({ message: id, version }))
          ? [{ message: id, version }]
          : [];
      });
      const unreadMessages = new Set(unread.map((item) => item.message));
      const bases = earlier?.bases ?? keptReadings();
      const msgs = thread.msgs.map(
        (message) =>
          /** @type {PublishedMessage} */ (
            bases.read(
              message.id,
              [
                message,
                key,
                unreadMessages.has(message.id),
                BETWEEN,
                ...messageWorkflows(message),
                BETWEEN,
                ...unitInputs(unitsByMessage.get(message.id)),
              ],
              () => readMessage(message, unreadMessages.has(message.id), key),
            )
          ),
      );
      bases.done();
      // A user's reaction in force on each message, and the agent's newest message
      // the user may address, read once for the thread rather than once per message.
      const resolved = Boolean(thread.resolved);
      const latest = msgs.findLast(
        (message) => message.author === "agent" && isAddressable(message),
      );
      const reactionsOn = grouped(
        msgs.filter((message) => isReaction(message) && message.author === "user"),
        (message) => message.parent,
      );
      // The publisher supplies the vocabulary; controls and commands read these same
      // choices, including the exact reaction in force an explicit removal withdraws.
      /** @param {PublishedMessage} message @param {boolean} choosing
       * @param {readonly PublishedMessage[]} inForce */
      const withReactions = (message, choosing, inForce) => ({
        ...message,
        reactions: choosing
          ? reactionChoices(key, message, latest === message, tokens, inForce)
          : null,
      });
      const messages = earlier?.messages ?? keptReadings();
      const published = msgs.map((message) => {
        const choosing =
          reacts && !resolved && message.author === "agent" && isAddressable(message);
        const inForce = choosing ? (reactionsOn.get(message.id) ?? []) : [];
        return /** @type {ReturnType<typeof withReactions>} */ (
          messages.read(
            message.id,
            [message, choosing, choosing && latest === message, tokens, ...inForce],
            () => withReactions(message, choosing, inForce),
          )
        );
      });
      messages.done();
      const root = published.find((message) => message.id === thread.root.id);
      if (!root) throw new Error(`Thread ${thread.id} has no root message`);
      return {
        id: thread.id,
        key,
        title: thread.title,
        root,
        msgs: published,
        unread: Object.freeze(unread),
        anchor: thread.anchor,
        detached_from: thread.detached_from,
        rewritten_from: thread.rewritten_from,
        resolved: thread.resolved,
        // The record that speaks for the thread, one of those standing in it: whose
        // turn it is and where it stands.
        attention:
          (obligationsIn.get(thread.id) ?? NONE).find(
            (obligation) => obligation.id === thread.attention,
          ) ?? null,
        // The obligations that stand in it: those widgets in its messages make, such as
        // an `lf-ask` the user owes words to there, those its updates publish, and the
        // agent's to-dos on it. A reply that promised a to-do says it is still open (a
        // to-do a reply opens takes the reply's id, `todos.py`), and a running one is
        // work the thread's working message reads whoever's turn the thread is.
        obligations: obligationsIn.get(thread.id) ?? [],
        workflows: workflowsIn.get(thread.id) ?? [],
        bare_reaction: thread.bare_reaction,
        seat: thread.seat,
        summaries: thread.summaries,
      };
    };
    const read = threads.map(
      (thread) =>
        /** @type {ReturnType<typeof readRecord>} */ (
          records.read(
            thread.id,
            [
              thread,
              ready,
              tokens,
              // What this tab is marking read of the thread's unread messages.
              ...Object.keys(thread.unread).flatMap((id) => markingIn.get(id) ?? NONE),
              BETWEEN,
              ...(workflowsIn.get(thread.id) ?? NONE),
              BETWEEN,
              ...(obligationsIn.get(thread.id) ?? NONE),
              BETWEEN,
              ...unitInputs(unitsByThread.get(thread.id)),
            ],
            (earlier) => {
              const bases = earlier?.bases ?? keptReadings();
              const messages = earlier?.messages ?? keptReadings();
              return {
                record: readRecord(thread, { bases, messages }),
                bases,
                messages,
              };
            },
          ).record
        ),
    );
    records.done();
    return read;
  };
}

// One reading with nothing kept from an earlier one.
export const readThreadRecords = (
  /** @type {Parameters<ReturnType<typeof threadRecordReader>>} */ ...args
) => threadRecordReader()(...args);
