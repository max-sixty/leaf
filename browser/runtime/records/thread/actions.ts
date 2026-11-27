/* Typed commands over the current Thread reading.

   A package names a stable Thread key and the meaning of its gesture; this owner
   resolves the current message target and constructs the event. Core controls call
   these same commands. The application ledger remains the one optimistic and
   admission path, so a stale or unavailable command returns null. A new comment
   defaults to the active revision; a resumed draft supplies the revision captured
   with its anchor, even after the active document has changed. */
import { randomId } from "../../base/ids.js";
import { discussed, editable } from "../../state/thread/model.js";
import { threadNamed } from "./state.js";
import type { PendingCommand } from "../../../types/domain.js";
import type { createCommandDispatch } from "../pending/dispatch.js";
import type { createUndo } from "../undo.js";
import type { createThreadDestinations } from "./destination.js";

type Post = ReturnType<typeof createCommandDispatch>["post"];
type CommentInput<T> = T extends unknown
  ? Omit<T, "kind" | "revision"> & { revision?: number | null }
  : never;
export type CreateComment = CommentInput<Extract<PendingCommand, { kind: "comment" }>>;
export function createThreadActions({
  post,
  withdraw,
  sendReaction,
  currentRevision,
  open,
}: {
  post: Post;
  withdraw: ReturnType<typeof createUndo>["withdraw"];
  sendReaction: (
    event: Extract<Parameters<Post>[0], { kind: "comment" | "reply" }>,
    where: string,
    postReaction: Post,
  ) => Promise<Awaited<ReturnType<Post>>>;
  currentRevision: () => number | null;
  open: ReturnType<typeof createThreadDestinations>["openPageThread"];
}) {
  const create = (command: CreateComment) => {
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
  // A visible local thread is a current root while saved history is loading too.
  // Its replies and settlement use the same ledger dependency on that opening send.
  const find = (key: string) => {
    const thread = threadNamed(key);
    return thread && discussed(thread) ? thread : null;
  };

  const reply = (key: string, text: string, { attempt }: { attempt?: string } = {}) => {
    if (!text) return null;
    const thread = find(key);
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
  const edit = (
    key: string,
    messageId: string,
    text: string,
    { attempt, base }: { attempt?: string; base?: string } = {},
  ) => {
    const thread = find(key);
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
  const settle = (
    key: string,
    resolved: boolean,
    { attempt }: { attempt?: string } = {},
  ) => {
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
  const setReaction = (
    key: string,
    messageKey: string,
    emoji: string,
    active: boolean,
  ) => {
    if (typeof active !== "boolean")
      throw new TypeError("A reaction needs its desired state");
    const thread = find(key);
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
    async open(
      key: string,
      {
        message = null,
        ...options
      }: { message?: string | null } & Parameters<
        ReturnType<typeof createThreadDestinations>["openPageThread"]
      >[1] = {},
    ) {
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
    resolve: (key: string, options?: { attempt?: string }) =>
      settle(key, true, options),
    reopen: (key: string, options?: { attempt?: string }) =>
      settle(key, false, options),
    setReaction,
  });
}
