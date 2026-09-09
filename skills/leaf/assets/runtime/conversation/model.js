/* Conversation structure and turn-taking projected by the server.

   This reads the log by `isReaction`, `spoken`, `turns`, and `bareReaction`, the names
   `events.py` reads it by, and answers `reactionsOn` from the fold it last built. The
   panel lists `conversational` threads only; a card shows its turns and its root, so a
   thread that grew out of a reaction opens on the mark, whose body
   conversation/messages.js writes as the glyph and its word. Whose turn a thread is
   (`awaitsReader`, `awaitsAgent`) is the server's projection, read here rather than
   derived: the banner's Ask count and the panel's narrowing ask the same question
   and must get one answer. */
import { sameAnchor } from "../anchors.js";
import { registry } from "../registry.js";
import { PENDING, runtime } from "../context.js";
import { pendingMessages } from "../outbox.js";

export const isReaction = (message) => Boolean(message.token);
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
export const tokenEntry = (name) => registry.$reactions.tokens[name];

// Which widget's seat a pending thread stands in, by the rule `seat_root` reads the log
// by: an element anchor naming that widget and carrying nothing else. Spelled again here
// because the server has not seen this message yet, and a thread that seated itself
// differently for the half-second before it lands would move once it arrived.
const pendingSeat = (message) =>
  message.about || !message.anchor || Object.keys(message.anchor).length !== 1
    ? null
    : (message.anchor.section ?? null);

// The reader's own unread messages, folded into the server's threads. A reply joins the
// thread it answers; a comment opens one where it was written. Both leave again the
// moment a receipt names their attempt, so this is a reading of the same log the server
// projects rather than a second store beside it.
//
// The derived facts a pending thread carries are the ones the reader just made true: the
// agent owes the next word, the reader owes none, and a thread the reader opened with
// words is a conversation rather than a mark.
function withPending(threads) {
  const messages = pendingMessages();
  if (!messages.length) return threads;
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
  for (const message of messages) {
    if (message.kind === "reply") continue;
    const thread = {
      root: message,
      anchor: message.anchor ?? null,
      msgs: [message],
      resolved: null,
      awaits_agent: true,
      awaits_reader: false,
      bare_reaction: false,
      seat: pendingSeat(message),
    };
    opened.push(thread);
    byName.set(message.id, thread);
  }
  // After the threads, so a reply into a conversation this tab has not sent yet finds
  // the one standing for it.
  for (const message of messages)
    if (message.kind === "reply") byName.get(message.parent)?.msgs.push(message);
  return [...copies, ...opened];
}

let lastThreads = [];
export function buildThreads() {
  lastThreads = withPending(runtime.browser?.conversation?.threads ?? []);
  return lastThreads;
}

// The bare reactions standing on exactly this anchor — the bar's own question, asked
// so its chips can say which tokens are already there. Anchors are compared as
// records, the way the file compares them.
export const reactionsOn = (anchor) =>
  lastThreads
    .filter(
      (thread) =>
        bareReaction(thread) && !thread.resolved && sameAnchor(thread.anchor, anchor),
    )
    .map((thread) => thread.root);

export const awaitsAgent = (thread) => thread.awaits_agent;
export const awaitsReader = (thread) => thread.awaits_reader;
export const seatRoot = (thread) => thread.seat;
