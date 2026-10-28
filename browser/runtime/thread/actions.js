/* Typed commands over the current Thread reading.

   A package names a stable Thread key and the meaning of its gesture; this owner
   resolves the current message target and constructs the event. Core controls call
   these same commands. The application ledger remains the one optimistic and
   admission path, so a stale or unavailable command returns null. A new comment
   defaults to the active revision; a resumed draft supplies the revision captured
   with its anchor, even after the active document has changed. */
import { randomId } from "../ids.js";
import { editable } from "./model.js";
import { readThreads } from "./state.js";

export function createThreadActions({
  post,
  withdraw,
  sendReaction,
  currentRevision,
  open,
}) {
  const create = (command) => {
    const {
      text,
      anchor,
      revision = currentRevision(),
      attempt = randomId(),
      holds,
      about,
      drawing,
      suggestion,
    } = command;
    if (!text && !drawing) return null;
    const delivery = post({
      kind: "comment",
      revision,
      ...(text !== undefined && { text }),
      ...(anchor !== undefined && { anchor: structuredClone(anchor) }),
      ...(attempt !== undefined && { attempt }),
      ...(holds !== undefined && { holds }),
      ...(about !== undefined && { about }),
      ...(drawing !== undefined && { drawing: structuredClone(drawing) }),
      ...(suggestion !== undefined && { suggestion }),
    });
    return delivery ? Object.freeze({ key: attempt, delivery }) : null;
  };
  // A visible local thread is a current root while saved history is loading too.
  // Its replies and settlement use the same ledger dependency on that opening send.
  const find = (key) => readThreads().threads.find((thread) => thread.key === key);

  /** @param {string} key @param {string} text @param {{attempt?: string}} [options] */
  const reply = (key, text, { attempt } = {}) => {
    if (!text) return null;
    const thread = find(key);
    if (!thread) return null;
    return post({
      kind: "reply",
      revision: currentRevision(),
      parent: thread.root.id,
      text,
      ...(attempt && { attempt }),
    });
  };

  // The user rewriting a message of their own (`message-edit.js`), written over the
  // revision `base` names. Words the message already says, and none, send nothing.
  /** @param {string} key @param {string} messageId @param {string} text
   * @param {{attempt?: string, base?: string}} [options] */
  const edit = (key, messageId, text, { attempt, base } = {}) => {
    const thread = find(key);
    if (!thread) return null;
    const message = thread.msgs.find((item) => item.id === messageId);
    if (!message || !editable(message) || !text || text === message.text) return null;
    return post({
      kind: "edit",
      message: messageId,
      text,
      base,
      ...(attempt && { attempt }),
    });
  };

  // A thread that already stands as asked, such as one resolved elsewhere while its
  // card still draws it open (held-news.js), sends nothing.
  /** @param {string} key @param {boolean} resolved @param {{attempt?: string}} [options] */
  const settle = (key, resolved, { attempt } = {}) => {
    const thread = find(key);
    if (!thread || Boolean(thread.resolved) === resolved) return null;
    return post({
      kind: resolved ? "resolve" : "unresolve",
      parent: thread.root.id,
      ...(attempt && { attempt }),
    });
  };

  // An explicit desired state retains the meaning of a control drawn from a held
  // reading. A concurrent change that already achieved it sends nothing.
  const setReaction = (key, messageKey, token, active) => {
    if (typeof active !== "boolean")
      throw new TypeError("A reaction needs its desired state");
    const thread = find(key);
    const message = thread?.msgs.find((item) => item.key === messageKey);
    const choice =
      message && message.reactions?.choices.find((item) => item.name === token);
    if (!choice || active === Boolean(choice.inForce)) return null;
    if (choice.inForce) return withdraw(choice.inForce);
    return sendReaction(
      {
        kind: "reply",
        parent: message.id,
        revision: currentRevision(),
        token,
      },
      `${message.agent}'s reply`,
      post,
    );
  };

  return Object.freeze({
    async open(key, { message = null, ...options } = {}) {
      const thread = find(key);
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
