/* Conversation structure and turn-taking projected by the server.

   This reads the log by `isReaction`, `spoken`, `turns`, and `bareReaction`, the names
   `events.py` reads it by, and answers `reactionsOn` from the fold it last built. The
   panel lists `conversational` threads only; a card shows its turns and its root, so a
   thread that grew out of a reaction opens on the mark, whose body
   conversation/messages.js writes as the glyph and its word. Whose turn a thread is
   (`awaitsReader`, `awaitsAgent`) is the server's projection, read here rather than
   derived: the banner's decision count and the panel's narrowing ask the same question
   and must get one answer. */
import { sameAnchor } from "../anchors.js";

export function createThreadModel({ registry, runtime }) {
  const isReaction = (message) => Boolean(message.token);
  const spoken = (thread) => thread.msgs.filter((message) => !isReaction(message));
  const turns = (thread) =>
    thread.msgs.filter(
      (message) => message.id === thread.root.id || !isReaction(message),
    );
  const bareReaction = (thread) => thread.bare_reaction;
  const conversational = (thread) => !bareReaction(thread);
  const tokenEntry = (name) => registry.$reactions.tokens[name];

  let lastThreads = [];
  function buildThreads() {
    lastThreads = runtime.browser?.conversation?.threads ?? [];
    return lastThreads;
  }

  // The bare reactions standing on exactly this anchor — the bar's own question, asked
  // so its pills can say which tokens are already there. Anchors are compared as
  // records, the way the file compares them.
  const reactionsOn = (anchor) =>
    lastThreads
      .filter(
        (thread) =>
          bareReaction(thread) &&
          !thread.resolved &&
          sameAnchor(thread.root.anchor, anchor),
      )
      .map((thread) => thread.root);
  return {
    awaitsAgent: (thread) => thread.awaits_agent,
    awaitsReader: (thread) => thread.awaits_reader,
    bareReaction,
    buildThreads,
    conversational,
    isReaction,
    reactionsOn,
    seatRoot: (thread) => thread.seat,
    spoken,
    tokenEntry,
    turns,
  };
}
