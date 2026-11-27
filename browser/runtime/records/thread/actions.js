// Compiled from actions.ts by build/typescript.mjs; edit that file.
/* Typed commands over the current Thread reading.

   A package names a stable Thread key and the meaning of its gesture; this owner
   resolves the current message target and constructs the event. Core controls call
   these same commands. The application ledger remains the one optimistic and
   admission path, so a stale or unavailable command returns null. A new comment
   defaults to the active revision; a resumed draft supplies the revision captured
   with its anchor, even after the active document has changed. */
import { randomId } from "../../base/ids.js";
import { editable } from "../../state/thread/model.js";
import { threadNamed } from "./state.js";

export function createThreadActions({
  post,
  withdraw,
  sendReaction,
  currentRevision,
  open,
}) {
  const create = (command) => {
    if (!command.text && !command.drawing) return null;
    const { revision = currentRevision(), attempt = randomId(), ...content } = command;
    if (revision === null) return null;
    const delivery = post({
      ...structuredClone(content),
      kind: "comment",
      revision,
      attempt,
    });
    return Object.freeze({ key: attempt, delivery });
  };
  const reply = (key, text, { attempt } = {}) => {
    if (!text) return null;
    const thread = threadNamed(key);
    if (!thread) return null;
    const revision = currentRevision();
    if (revision === null) return null;
    return post({
      kind: "reply",
      revision,
      parent: thread.root.id,
      text,
      ...(attempt && { attempt }),
    });
  };

  // The user rewriting a message of their own (`message-edit.js`), written over the
  // revision `base` names. Words the message already says send nothing; none at all
  // delete it.
  const edit = (key, messageId, text, { attempt, base } = {}) => {
    const thread = threadNamed(key);
    if (!thread) return null;
    const message = thread.msgs.find((item) => item.id === messageId);
    if (!message || !editable(message) || text === message.text) return null;
    return post({
      kind: "edit",
      message: messageId,
      text,
      ...(base !== undefined && { base }),
      ...(attempt && { attempt }),
    });
  };

  // A thread that already stands as asked, such as one resolved elsewhere while its
  // card still draws it open (held-news.js), sends nothing.
  const settle = (key, resolved, { attempt } = {}) => {
    const thread = threadNamed(key);
    if (!thread || Boolean(thread.resolved) === resolved) return null;
    return post({
      kind: resolved ? "resolve" : "unresolve",
      parent: thread.root.id,
      ...(attempt && { attempt }),
    });
  };

  // An explicit desired state retains the meaning of a control drawn from a held
  // reading. A concurrent change that already achieved it sends nothing.
  const setReaction = (key, messageKey, emoji, active) => {
    if (typeof active !== "boolean")
      throw new TypeError("A reaction needs its desired state");
    const thread = threadNamed(key);
    const message = thread?.msgs.find((item) => item.key === messageKey);
    const choice =
      message && message.reactions?.choices.find((item) => item.emoji === emoji);
    if (!choice || active === Boolean(choice.inForce)) return null;
    if (choice.inForce) return withdraw(choice.inForce);
    const revision = currentRevision();
    if (revision === null) return null;
    return sendReaction(
      {
        kind: "reply",
        parent: message.id,
        revision,
        emoji,
      },
      `${message.agent}'s reply`,
      post,
    );
  };

  return Object.freeze({
    async open(key, { message = null, ...options } = {}) {
      const thread = threadNamed(key);
      if (!thread) return null;
      const target =
        message === null ? thread : thread.msgs.find((item) => item.key === message);
      if (!target) return null;
      return open(
        target.id,
        message === null ? options : { ...options, part: "message" },
      );
    },
    create,
    reply,
    edit,
    resolve: (key, options) => settle(key, true, options),
    reopen: (key, options) => settle(key, false, options),
    setReaction,
  });
}
