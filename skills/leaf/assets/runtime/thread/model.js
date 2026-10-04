/* Pure thread structure and turn-taking projected by the server.

   This reads projected threads by `isReaction`, `spoken`, `turns`, and `bareReaction`,
   the names `events.py` reads them by. The panel lists `discussed` threads only;
   a card shows its turns and its root, so a
   thread that grew out of a reaction opens on the mark, whose body
   thread/messages.js writes as the glyph and its word. Whose turn a thread is
   (`awaitsUser`, `awaitsAgent`) is read from the complete browser Thread's
   `attention` and nothing else, so a filter and the card it lists agree: a user
   obligation outranks concurrent agent work, which stays the card's secondary
   status.

   A thread's `id` is its one identity: the id the server keys it by, which every Ask,
   workflow, placement, and view names it by. Its `root` is the first message it still
   holds, a message like any other, and what a reply or settlement addresses as its
   `parent`. The two differ where the log lost a thread's opening message
   (`events.build_threads`), and for a thread this tab opened, whose id is its pending
   message's until the log answers. */
import { sameAnchor } from "../anchor-coordinate.js";
import { PENDING } from "./identity.js";

export const isReaction = (message) => Boolean(message.token);
export const isAddressable = (message) => message.addressable !== false;
const spoken = (thread) => thread.msgs.filter((message) => !isReaction(message));
export const turns = (thread) =>
  thread.msgs.filter(
    (message) => message.id === thread.root.id || !isReaction(message),
  );
// The name for a thread that the log's answer does not change: the user's own attempt
// where their gesture opened the thread, else the id the log gave it. Anything
// that has to outlive that transition with the user standing in it — a reply draft, a
// margin row — keys itself by this rather than by the id, which changes when the log
// answers.
export const threadKey = (thread) => thread.root.attempt ?? thread.id;

// Every name that reaches a thread: its own id, the id of each message in it, which a
// reply or settlement names as its `parent`, and the pending id a message this tab sent
// went by before the log named it.
export function threadNames(threads) {
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

export const bareReaction = (thread) => thread.bare_reaction;
export const discussed = (thread) => !bareReaction(thread);
// Which widget's seat a pending thread stands in, by the rule `seat_root` reads the log
// by: an element anchor naming that widget and carrying nothing else. Spelled again here
// because the server has not seen this message yet, and a thread that seated itself
// differently for the half-second before it lands would move once it arrived.
const pendingSeat = (message) =>
  message.about || !message.anchor || Object.keys(message.anchor).length !== 1
    ? null
    : (message.anchor.section ?? null);

// The user's own pending gestures, folded into the server's threads. A reply joins the
// thread it answers; a comment opens one where it was written; settlement changes its
// state; taking back a reaction, the one message the user can withdraw, drops it from
// its thread, and a thread it opened goes with it, as the log's reading will. They leave
// again when the server accepts or refuses them, so this is a reading of the same
// outbox and log the server projects rather than a second store beside it.
//
// The derived facts a pending thread carries are the ones the user just made true: a
// thread the user opened with words is a thread rather than a mark, and its attention
// waits on the newest send, whose local workflow shares the pending message's id, so
// the agent owes the next word and the user none. Every other thread keeps the
// attention the server derived.
const sending = (message) => ({
  kind: "waiting",
  reason: "workflow",
  workflow: message.id,
});

export function foldThreads(threads, messages, reactions, settlements, withdrawn) {
  if (!messages.length && !reactions.length && !settlements.length && !withdrawn.size)
    return threads;
  // A thread the user opened answers to two names for as long as this tab holds a
  // reply written against the first: the one this page gave it, and the one the log
  // gave back. Both reach the one thread, so a reply written into the card a
  // send had just drawn stays in it when the answer arrives.
  const copies = threads
    .filter((thread) => !withdrawn.has(thread.root.id))
    .map((thread) => ({
      ...thread,
      msgs: thread.msgs.filter((message) => !withdrawn.has(message.id)),
    }));
  const byName = threadNames(copies);
  const opened = [];
  // Open both kinds before attaching either kind of reply. The delivery queue lets a
  // user answer a locally named root before the server has named it; that root may be
  // words or a reaction, independently of whether the answer itself carries a token.
  for (const root of [...messages, ...reactions]) {
    if (root.kind === "reply") continue;
    const reaction = isReaction(root);
    const thread = {
      id: root.id,
      root,
      title: null,
      anchor: root.anchor ?? null,
      detached_from: null,
      msgs: [root],
      resolved: null,
      user_prompt: null,
      bare_reaction: reaction,
      seat: pendingSeat(root),
      summaries: [],
      unread: [],
    };
    opened.push(thread);
    byName.set(root.id, thread);
  }
  for (const reply of [...messages, ...reactions]) {
    if (reply.kind !== "reply") continue;
    const thread = byName.get(reply.parent);
    if (!thread) continue;
    thread.msgs.push(reply);
    if (!isReaction(reply)) {
      thread.resolved = null;
      thread.attention = sending(reply);
    }
  }
  for (const thread of opened) {
    const said = spoken(thread);
    thread.bare_reaction = isReaction(thread.root) && !said.length;
    thread.attention = said.length ? sending(said.at(-1)) : null;
  }
  for (const settlement of settlements) {
    const thread = byName.get(settlement.parent) ?? byName.get(settlement.localParent);
    if (!thread) continue;
    thread.resolved =
      settlement.kind === "resolve" ? { author: "user", pending: true } : null;
    // Which way the thread is being settled, as well as where it lands. `resolved` alone
    // cannot say: a reopen leaves it null, exactly as an open thread the user has not
    // touched does. Views read this to draw the gesture as unfinished, so it has to be a
    // fact of the published fold — the ledger empties after the answer lands without
    // changing anything else, and a view reading the ledger would keep the state it drew
    // before that.
    thread.settling = settlement.kind;
  }
  return [...copies, ...opened];
}

// The bare reactions standing on exactly this anchor — the bar's own question, asked
// so its chips can say which tokens are already there. Anchors are compared as
// records, the way the file compares them.
export const reactionsAt = (threads, anchor) =>
  threads
    .filter(
      (thread) =>
        bareReaction(thread) && !thread.resolved && sameAnchor(thread.anchor, anchor),
    )
    .map((thread) => thread.root);

export const awaitsAgent = (thread) =>
  !thread.resolved && thread.attention?.kind === "waiting";
export const awaitsUser = (thread) =>
  !thread.resolved && thread.attention?.kind === "needs_user";
export const seatRoot = (thread) => thread.seat;

// The passage the opening comment quoted, once a later version rewrote it: the words no
// longer resolve, so the thread stands on their section alone (`reanchor`, events.md).
// The opening comment keeps its anchor and the revision it was written on, so what the
// comment was about stays readable however far the page has moved on. A reply that moved
// the thread chose its new place and said why, so it is not a rewrite.
export function rewrittenFrom(thread) {
  const opening = thread.root.anchor;
  const now = thread.anchor;
  if (!opening?.quote || !now || now.quote || now.section !== opening.section)
    return null;
  return { passage: opening, revision: thread.root.revision ?? null };
}

// When a message last moved: its latest edit, else its own arrival. Every ordering that
// asks what is newest in a thread — Recent, the first unread, news — reads this,
// so an agent message edited today is today's in all of them. A message still being
// sent carries the clock the user's gesture gave it and no log position yet.
export const moved = (message) => ({
  seq: message.edited?.seq ?? message.seq ?? null,
  ts: message.edited?.ts ?? message.ts ?? null,
});

// When a thread last moved: the latest move of any of its turns.
function lastMovedAt(thread) {
  let latest = null;
  for (const message of turns(thread)) {
    const { ts } = moved(message);
    if (ts !== null && (latest === null || Date.parse(ts) > Date.parse(latest)))
      latest = ts;
  }
  return latest;
}

export const threadSummary = (thread) => ({
  topic: thread.title ?? thread.root.body.text.trim(),
  latest: lastMovedAt(thread),
});

const versionKey = ({ message, version }) => `${message}\u0000${version}`;

/* Public thread values. The publisher calls this after folding local gestures
   and admitted obligations. Authored source stays with its prepared document; only
   captured words, registry identities and current unit state cross this boundary.

   A Thread's `unread` is the server's reading of the agent content versions the user
   has not taken in, less those this tab is marking read now: the page draws them read
   in the turn it sends that, and the answer confirms rather than decides it. */
export function readThreadRecords(
  threads,
  document,
  widgets,
  workflows,
  markingRead = [],
) {
  const locallyRead = new Set(markingRead.map(versionKey));
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
      const record = {};
      for (const field of [
        "id",
        "attempt",
        "kind",
        "author",
        "agent",
        "ts",
        "seq",
        "parent",
        "pending",
        "anchor",
        "about",
        "drawing",
        "holds",
        "token",
        "text",
        "edited",
        "failure",
        "addressable",
        "revision",
        "awaits",
        "ephemeral",
        "suggestion",
      ])
        if (message[field] !== undefined) record[field] = message[field];
      const units = unitsByMessage.get(message.id) ?? [];
      const authored = document.messageBodies?.get(message.id);
      const body = message.markup
        ? { kind: "authored", ...authored, units }
        : {
            kind: message.token
              ? "reaction"
              : message.suggestion
                ? "suggestion"
                : "prose",
            text:
              authored?.text ??
              message.plainText ??
              message.text ??
              message.token ??
              "",
          };
      if (message.markup && !authored)
        throw new Error(`Authored message ${message.id} has no captured body`);
      const unitIds = new Set(units.map((unit) => unit.id));
      return {
        ...record,
        unread: unreadMessages.has(message.id),
        key: message.attempt ?? message.id,
        body,
        // The message's own input and the moves on widgets frozen into it, in the
        // published order `strongestWorkflow` reads.
        workflows: workflows.filter(
          (workflow) =>
            workflow.input === message.id ||
            (workflow.subject.kind === "widget" && unitIds.has(workflow.subject.id)),
        ),
      };
    });
    return {
      id: thread.id,
      key: threadKey(thread),
      title: thread.title,
      root: msgs.find((message) => message.id === thread.root.id),
      msgs,
      unread: Object.freeze(unread),
      anchor: thread.anchor,
      detached_from: thread.detached_from,
      resolved: thread.resolved,
      settling: thread.settling ?? null,
      user_prompt: thread.user_prompt,
      attention: thread.attention,
      workflows: workflows.filter((workflow) => workflow.thread === thread.id),
      bare_reaction: thread.bare_reaction,
      seat: thread.seat,
      summaries: thread.summaries,
    };
  });
}
