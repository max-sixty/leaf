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
import { runtime } from "../context.js";

export const isReaction = (message) => Boolean(message.token);
const spoken = (thread) => thread.msgs.filter((message) => !isReaction(message));
export const turns = (thread) =>
  thread.msgs.filter(
    (message) => message.id === thread.root.id || !isReaction(message),
  );
export const bareReaction = (thread) => thread.bare_reaction;
export const conversational = (thread) => !bareReaction(thread);
export const tokenEntry = (name) => registry.$reactions.tokens[name];

let lastThreads = [];
export function buildThreads() {
  lastThreads = runtime.browser?.conversation?.threads ?? [];
  return lastThreads;
}

// The bare reactions standing on exactly this anchor — the bar's own question, asked
// so its pills can say which tokens are already there. Anchors are compared as
// records, the way the file compares them.
export const reactionsOn = (anchor) =>
  lastThreads
    .filter(
      (thread) =>
        bareReaction(thread) &&
        !thread.resolved &&
        sameAnchor(thread.root.anchor, anchor),
    )
    .map((thread) => thread.root);

const awaitsAgent = (thread) => thread.awaits_agent;
export const awaitsReader = (thread) => thread.awaits_reader;
export const seatRoot = (thread) => thread.seat;
