/* Pure conversation structure and turn-taking projected by the server.

   This reads projected threads by `isReaction`, `spoken`, `turns`, and `bareReaction`,
   the names `events.py` reads them by. The panel lists `conversational` threads only;
   a card shows its turns and its root, so a
   thread that grew out of a reaction opens on the mark, whose body
   conversation/messages.js writes as the glyph and its word. Whose turn a thread is
   (`awaitsReader`, `awaitsAgent`) is the server's projection, read here rather than
   derived: the banner's Ask count and the panel's narrowing ask the same question
   and must get one answer. */
import { sameAnchor } from "../anchor-coordinate.js";
import { PENDING } from "./identity.js";

export const isReaction = (message) => Boolean(message.token);
export const isAddressable = (message) => message.addressable !== false;
const spoken = (thread) => thread.msgs.filter((message) => !isReaction(message));
export const turns = (thread) =>
  thread.msgs.filter(
    (message) => message.id === thread.root.id || !isReaction(message),
  );
// The name for a thread that the log's answer does not change: the reader's own attempt
// where their gesture opened the conversation, else the id the log gave it. Anything
// that has to outlive that transition with the reader standing in it — a reply draft, a
// margin row — keys itself by this rather than by the id, which changes when the log
// answers.
export const threadKey = (thread) => thread.root.attempt ?? thread.root.id;

export const bareReaction = (thread) => thread.bare_reaction;
export const conversational = (thread) => !bareReaction(thread);
// Which widget's seat a pending thread stands in, by the rule `seat_root` reads the log
// by: an element anchor naming that widget and carrying nothing else. Spelled again here
// because the server has not seen this message yet, and a thread that seated itself
// differently for the half-second before it lands would move once it arrived.
const pendingSeat = (message) =>
  message.about || !message.anchor || Object.keys(message.anchor).length !== 1
    ? null
    : (message.anchor.section ?? null);

// The reader's own pending gestures, folded into the server's threads. A reply joins the
// thread it answers; a comment opens one where it was written; settlement changes its
// state. They leave again when the server accepts or refuses them, so this is a reading
// of the same outbox and log the server projects rather than a second store beside it.
//
// The derived facts a pending thread carries are the ones the reader just made true: the
// agent owes the next word, the reader owes none, and a thread the reader opened with
// words is a conversation rather than a mark.
export function foldThreads(threads, messages, reactions, settlements) {
  if (!messages.length && !reactions.length && !settlements.length) return threads;
  // A thread the reader opened answers to two names for as long as this tab holds a
  // reply written against the first: the one this page gave it, and the one the log
  // gave back. Both reach the one conversation, so a reply written into the card a
  // send had just drawn stays in it when the answer arrives.
  const byName = new Map();
  const copies = threads.map((thread) => {
    const copy = { ...thread, msgs: [...thread.msgs] };
    byName.set(thread.root.id, copy);
    if (thread.root.attempt) byName.set(PENDING + thread.root.attempt, copy);
    return copy;
  });
  const opened = [];
  // Open both kinds before attaching either kind of reply. The delivery queue lets a
  // reader answer a locally named root before the server has named it; that root may be
  // words or a reaction, independently of whether the answer itself carries a token.
  for (const root of [...messages, ...reactions]) {
    if (root.kind === "reply") continue;
    const reaction = isReaction(root);
    const thread = {
      root,
      anchor: root.anchor ?? null,
      msgs: [root],
      resolved: null,
      awaits_agent: !reaction,
      awaits_reader: false,
      bare_reaction: reaction,
      seat: pendingSeat(root),
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
      thread.awaits_agent = true;
      thread.awaits_reader = false;
    }
  }
  for (const thread of opened) {
    const said = spoken(thread);
    thread.bare_reaction = isReaction(thread.root) && !said.length;
    thread.awaits_agent = Boolean(said.length);
  }
  for (const settlement of settlements) {
    const thread = byName.get(settlement.parent) ?? byName.get(settlement.localParent);
    if (!thread) continue;
    thread.resolved =
      settlement.kind === "resolve" ? { author: "user", pending: true } : null;
    // Which way the thread is being settled, as well as where it lands. `resolved` alone
    // cannot say: a reopen leaves it null, exactly as an open thread the reader has not
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

export const awaitsAgent = (thread) => thread.awaits_agent;
export const awaitsReader = (thread) => thread.awaits_reader;
export const seatRoot = (thread) => thread.seat;

export const threadSummary = (thread) => ({
  topic: thread.title ?? thread.root.body.text.trim(),
  count: turns(thread).length,
  latest: turns(thread).at(-1)?.ts ?? null,
});

/* Public conversation values. The publisher calls this after folding local gestures
   and admitted obligations. Authored source stays with its prepared document; only
   captured words, registry identities and current unit state cross this boundary. */
export function readThreadRecords(threads, document, widgets, interactions) {
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
    const turnIds = new Set(turns(thread).map((message) => message.id));
    const msgs = thread.msgs.map((message) => {
      const record = {};
      for (const field of [
        "id",
        "attempt",
        "kind",
        "author",
        "agent",
        "ts",
        "parent",
        "pending",
        "anchor",
        "about",
        "drawing",
        "holds",
        "response",
        "token",
        "text",
        "edited",
        "failure",
        "stream_state",
        "addressable",
        "revision",
        "awaits",
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
      return {
        ...record,
        key: message.attempt ?? message.id,
        body,
        receipts: interactions.filter((receipt) => {
          if (receipt.target.kind === "thread") {
            if (thread.resolved || receipt.target.id !== thread.root.id) return false;
            return (
              (turnIds.has(receipt.event) ? receipt.event : thread.root.id) ===
              message.id
            );
          }
          return (
            receipt.target.kind === "widget" &&
            receipt.event &&
            receipt.revision <= document.revision &&
            units.some((unit) => unit.id === receipt.target.id)
          );
        }),
      };
    });
    return {
      key: threadKey(thread),
      title: thread.title ?? null,
      root: msgs.find((message) => message.id === thread.root.id),
      msgs,
      anchor: thread.anchor ?? null,
      detached_from: thread.detached_from ?? null,
      resolved: thread.resolved ?? null,
      settling: thread.settling ?? null,
      awaits_agent: thread.awaits_agent,
      awaits_reader: thread.awaits_reader,
      bare_reaction: thread.bare_reaction,
      seat: thread.seat,
      summaries: thread.summaries ?? [],
    };
  });
}
