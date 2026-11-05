// @ts-check
/* What a change since a version came after: the user's messages the revisions that made
   it came after while they waited for an answer, and the versions those revisions
   landed in, so a user reviewing a revision sees which of their comments each change
   followed and which came with none waiting (../SOUL.md, "Changes the user requests
   remain understandable as they happen").

   Python derives both halves from the log and the revisions (src/leaf/provenance.py),
   whose header says how a revision is tied to messages and how far the tie holds:
   `revision_messages` in every reading, and what each revision changed with the
   comparison's base (`/api/view`), from which version.js keeps on each change the
   revisions that made it (`madeBy`). This module selects from those readings
   (`provenanceOf`): the versions, by the first stamp at or after each revision, else
   Draft; and the messages, each read off its thread as the page now shows it.

   The tie is one of order, so the words state order: a change came after the comment
   it names, before the agent answered it, or with none of the user's comments
   waiting. They say neither that it answers the comment nor that no comment asked for
   it, since the log establishes neither: a revision the rule ties to one comment
   changed that comment's element in 68% of the cases measured, and one made after a
   quick answer to it no more often than chance. The user chose on 5 November 2026 to
   say what each change came from rather than only what it did; these words are the
   part of that the log can back.

   The revisions that made a change fall into groups, each saying one thing: those
   that came after the same messages, and those that came with none waiting. A change
   one revision made has one group; a run of blocks revisions made after different
   messages, or a block revised again, has one per thing they did. A change no
   revision made, as a pick is made in the log, has no provenance: the account of what
   it did says all there is.

   `changeProvenance` is the one value every surface that describes a change reads: the
   ⇄ entry's label (annotation-inventory.js), and what the change walk says
   (change-walk.js). Its `lines` are the words a surface shows, each in its speaker's
   face: a group's heading in Leaf's voice, as it reads the log ("In v4, after your
   comment:"), then the opening line of each of its messages in quotes, the user's own
   words. */
import { runtime } from "./context.js";
import { threadNamed } from "./thread/state.js";
import { messageText } from "./thread/messages.js";
import { leafSays } from "./voice.js";
import { counted, labelWords, quotedWords } from "./words.js";

/** One of the user's messages a change came after, as its thread now reads it: `words`
 * its opening line.
 * @typedef {Readonly<{thread: string, message: string, kind: "comment" | "reply", words: string}>} NamedMessage */
/** Revisions that made a change and came after the same messages: the versions they
 * landed in, and the messages, none for revisions made with none waiting.
 * @typedef {Readonly<{versions: readonly string[], messages: readonly NamedMessage[]}>} ProvenanceGroup */
/** What a change came after: its groups, and `lines`, what it says, each line a run of
 * words in their speakers' faces (voice.js).
 * @typedef {Readonly<{groups: readonly ProvenanceGroup[], lines: readonly (readonly (string | import("./voice.js").Said)[])[]}>} ChangeProvenance */
/** @typedef {import("../types/contract.js").ServedBrowser["revision_messages"]} RevisionMessages */

// The quoted lines a change's provenance shows at most before saying how many more.
const QUOTED = 3;
// The characters a quoted line keeps.
const QUOTE_CAP = 90;

/** @param {readonly string[]} names */
const listed = (names) =>
  names.length < 2
    ? names.join("")
    : `${names.slice(0, -1).join(", ")} and ${names.at(-1)}`;

/** What the messages are to the user: "your comment", "your 2 replies", or for kinds
 * mixed, "your 3 updates" (glossary.md, "Reader-facing words").
 * @param {readonly NamedMessage[]} messages */
function yours(messages) {
  const kinds = new Set(messages.map(({ kind }) => kind));
  const [one, many] =
    kinds.size > 1
      ? ["update", "updates"]
      : kinds.has("reply")
        ? ["reply", "replies"]
        : ["comment", "comments"];
  return messages.length === 1
    ? `your ${one}`
    : `your ${counted(messages.length, one, many)}`;
}

/** What a change the revisions `revisions` made came after, from the readings it is
 * selected from: the messages each revision came after (`revision_messages`), the
 * version each landed in, and each message as its thread reads it, null for one no
 * thread shows.
 * @param {readonly number[]} revisions @param {RevisionMessages} cameAfter
 * @param {(revision: number) => string} versionOf
 * @param {(named: {thread: string, message: string}) => NamedMessage | null} messageOf
 * @returns {ChangeProvenance | null} */
export function provenanceOf(revisions, cameAfter, versionOf, messageOf) {
  if (!revisions.length) return null;
  /** @type {Map<string, {versions: Set<string>, messages: NamedMessage[]}>} */
  const groups = new Map();
  for (const revision of revisions) {
    const messages = (cameAfter[String(revision)] ?? []).flatMap((named) => {
      const message = messageOf(named);
      return message ? [message] : [];
    });
    const key = messages.map(({ message }) => message).join(" ");
    const group = groups.get(key) ?? { versions: new Set(), messages };
    group.versions.add(versionOf(revision));
    groups.set(key, group);
  }
  /** @type {ChangeProvenance["lines"][number][]} */
  const lines = [];
  let quoted = 0;
  for (const { versions, messages } of groups.values()) {
    const where = `In ${listed([...versions])}`;
    lines.push([
      leafSays(
        messages.length
          ? `${where}, after ${yours(messages)}:`
          : `${where}, with none of your comments waiting`,
      ),
    ]);
    // A group whose messages overrun the room left says how many more in place of
    // its last quote.
    const room = Math.max(0, QUOTED - quoted);
    const shown = messages.slice(
      0,
      messages.length > room ? Math.max(0, room - 1) : room,
    );
    for (const { words } of shown) lines.push([quotedWords(words, QUOTE_CAP)]);
    quoted += shown.length;
    if (messages.length > shown.length)
      lines.push([leafSays(`and ${messages.length - shown.length} more`)]);
  }
  return Object.freeze({
    groups: Object.freeze(
      [...groups.values()].map(({ versions, messages }) =>
        Object.freeze({
          versions: Object.freeze([...versions]),
          messages: Object.freeze(messages),
        }),
      ),
    ),
    lines: Object.freeze(lines.map((line) => Object.freeze(line))),
  });
}

// The version a revision landed in: the first stamped at or after it, else Draft.
/** @param {number} revision */
const versionOf = (revision) => {
  const stamp = runtime.versions.find((entry) => entry.revision >= revision);
  return stamp ? `v${stamp.version}` : "Draft";
};

/** A message as its thread now reads it, or null where no thread shows it.
 * @param {{thread: string, message: string}} named @returns {NamedMessage | null} */
function namedMessage({ thread: threadId, message: id }) {
  const thread = threadNamed(threadId);
  const message = thread?.msgs.find((each) => each.id === id);
  if (!thread || !message) return null;
  const opening =
    messageText(message).split("\n").map(labelWords).find(Boolean) ??
    (message.drawing ? "Drawing" : "");
  return Object.freeze({
    thread: thread.id,
    message: id,
    kind: id === thread.root.id ? "comment" : "reply",
    words: opening,
  });
}

/** What a change came after, as the page now reads it, or null where no revision made
 * it (`provenanceOf`).
 * @param {import("./version.js").Change} change */
export const changeProvenance = (change) =>
  provenanceOf(
    change.revisions,
    runtime.browser?.revision_messages ?? {},
    versionOf,
    namedMessage,
  );
