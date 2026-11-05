// @ts-check
/* What a change since a version answered: the user's messages the revisions that made
   it answered, and the versions those revisions landed in, so a user reviewing a
   revision learns which of their comments each change answers and which no comment
   asked for (../SOUL.md, "Changes the user requests remain understandable as they
   happen").

   Python derives both halves from the log and the revisions (src/leaf/provenance.py),
   whose header says how a revision is tied to the messages it answered and where the
   tie misleads: `revision_answers` in every reading, and what each revision changed
   with the comparison's base (`/api/view`), from which version.js keeps on each change
   the revisions that made it (`madeBy`). This module selects from those readings
   (`provenanceOf`): the versions, by the first stamp at or after each revision, else
   Draft; and the messages, each read off its thread as the page now shows it.

   The revisions that made a change fall into groups, each saying one thing: those that
   answered the same messages, those made while the same messages waited for an
   answer, which the agent may yet answer with them or with nothing, and those that
   answered none of the user's comments. A change one revision made has one group; a
   run of blocks revisions made for different messages, or a block revised again, has
   one per thing they did. A change no revision made, as a pick is made in the log, has
   no provenance: the account of what it did says all there is.

   `changeProvenance` is the one value every surface that describes a change reads: the
   ⇄ entry's label (annotation-inventory.js), and what the change walk says
   (change-walk.js). Its `lines` are the words a surface shows, each in its speaker's
   face: a group's heading in Leaf's voice, as it reads the log ("In v4, answering your
   comment:"), then the opening line of each of its messages in quotes, the user's own
   words. The user chose this attribution on 5 November 2026 over describing a change
   only by what it did. A change no comment asked for says it answered none of the
   user's comments rather than calling itself unprompted, since the page can't see a
   request made in the terminal; one made while a comment waits says it came after it,
   since the log doesn't yet say it answers it. */
import { runtime } from "./context.js";
import { threadNamed } from "./thread/state.js";
import { messageText } from "./thread/messages.js";
import { leafSays } from "./voice.js";
import { counted, labelWords, quotedWords } from "./words.js";

/** One of the user's messages a change answered, as its thread now reads it: `words`
 * its opening line.
 * @typedef {Readonly<{thread: string, message: string, kind: "comment" | "reply", words: string}>} AnsweredMessage */
/** Revisions that made a change and did one thing: the versions they landed in, the
 * messages they answered, none for revisions that answered none, and whether the agent
 * has answered them, false while they wait.
 * @typedef {Readonly<{versions: readonly string[], messages: readonly AnsweredMessage[], answered: boolean}>} ProvenanceGroup */
/** What a change answered: its groups, and `lines`, what it says, each line a run of
 * words in their speakers' faces (voice.js).
 * @typedef {Readonly<{groups: readonly ProvenanceGroup[], lines: readonly (readonly (string | import("./voice.js").Said)[])[]}>} ChangeProvenance */
/** @typedef {import("../types/contract.js").ServedBrowser["revision_answers"]} RevisionAnswers */

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
 * @param {readonly AnsweredMessage[]} messages */
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

/** What a change the revisions `revisions` made answered, from the readings it is
 * selected from: what each revision answered (`revision_answers`), the version each
 * landed in, and each message as its thread reads it, null for one no thread shows.
 * @param {readonly number[]} revisions @param {RevisionAnswers} answers
 * @param {(revision: number) => string} versionOf
 * @param {(named: {thread: string, message: string}) => AnsweredMessage | null} messageOf
 * @returns {ChangeProvenance | null} */
export function provenanceOf(revisions, answers, versionOf, messageOf) {
  if (!revisions.length) return null;
  /** @type {Map<string, {versions: Set<string>, messages: AnsweredMessage[], answered: boolean}>} */
  const groups = new Map();
  for (const revision of revisions) {
    const record = answers[String(revision)];
    const messages = (record?.messages ?? []).flatMap((named) => {
      const message = messageOf(named);
      return message ? [message] : [];
    });
    const answered = Boolean(record?.answered) && messages.length > 0;
    const key = `${answered}:${messages.map(({ message }) => message).join(" ")}`;
    const group = groups.get(key) ?? { versions: new Set(), messages, answered };
    group.versions.add(versionOf(revision));
    groups.set(key, group);
  }
  /** @type {ChangeProvenance["lines"][number][]} */
  const lines = [];
  let quoted = 0;
  for (const { versions, messages, answered } of groups.values()) {
    const where = `In ${listed([...versions])}`;
    lines.push([
      leafSays(
        !messages.length
          ? `${where}, answering none of your comments`
          : `${where}, ${answered ? "answering" : "after"} ${yours(messages)}:`,
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
      [...groups.values()].map(({ versions, messages, answered }) =>
        Object.freeze({
          versions: Object.freeze([...versions]),
          messages: Object.freeze(messages),
          answered,
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
 * @param {{thread: string, message: string}} named @returns {AnsweredMessage | null} */
function answeredMessage({ thread: threadId, message: id }) {
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

/** What a change answered, as the page now reads it, or null where no revision made
 * it (`provenanceOf`).
 * @param {import("./version.js").Change} change */
export const changeProvenance = (change) =>
  provenanceOf(
    change.revisions,
    runtime.browser?.revision_answers ?? {},
    versionOf,
    answeredMessage,
  );
