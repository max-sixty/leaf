/* Conversation structure and turn-taking projected by the server. */
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
