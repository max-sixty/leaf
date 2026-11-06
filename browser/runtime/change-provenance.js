// @ts-check
/* Which of the user's comments a version was saved after: where the page compares a
   version with the one before it, as `v` does, every change it marks was made by that
   version's revisions, so one line under each change's count says the messages that
   waited while the version was saved (../SOUL.md, "Changes the user requests remain
   understandable as they happen").

   The server says which, with the base's document the comparison asks for
   (`/api/view`, `saved_after`), each revision of the version judged by the log up to
   where it went live (src/leaf/provenance.py, `saved_after`, whose header says how far
   the order holds), or says nothing, for a comparison across several versions. This
   module says it in words (`versionProvenance`), naming the version by its stamp,
   else Draft.

   The tie is one of order, so the words state order: the version was saved while
   these comments waited, or with none waiting. They say neither that it answers a
   comment nor which paragraph followed which, since the log establishes neither. The
   user chose on 5 November 2026 to say what each change came from rather than only
   what it did; the version is the part of that the log can back.

   `versionProvenance` is the one value a surface that describes a change reads, the ⇄
   entry's label (annotation-inventory.js), reading it once for every change. Its
   `lines` are the words a surface shows, each in its speaker's face: the heading in
   Leaf's voice ("v4 saved while your comment waited:"), then each quoted message as
   its thread reads the whole message, with the words it had where it waited
   (`waitedWords`), in quotes, the user's own words: the server names the event whose
   words stood, and this reads the message from its thread (thread/messages.js,
   `messageWords`), so no second reading of a message's words exists. While no
   comparison stands it reads nothing else, and while one does, only the threads of
   the messages it quotes. */
import { runtime } from "./context.js";
import { markdownReady } from "./markdown.js";
import { messageWords } from "./thread/messages.js";
import { allThreads, threadNamed } from "./thread/state.js";
import { comparisonSavedAfter } from "./version.js";
import { leafSays } from "./voice.js";
import { counted, quotedWords } from "./words.js";

/** One of the user's messages a version was saved after, as the server names it.
 * @typedef {NonNullable<import("../types/contract.js").ServedViewAnswer["saved_after"]>[number]} WaitedMessage */
/** What a version was saved after: its name and `lines`, what it says, each line a run
 * of words in their speakers' faces (voice.js).
 * @typedef {Readonly<{version: string, lines: readonly (readonly (string | import("./voice.js").Said)[])[]}>} VersionProvenance */

// The quoted lines a version's provenance shows at most before saying how many more.
const QUOTED = 3;
// The characters a quoted line keeps.
const QUOTE_CAP = 90;

/** What the messages are to the user: "your comment", "your 2 replies", or for kinds
 * mixed, "your 3 updates" (glossary.md, "Reader-facing words"). A message that opened
 * its thread is a comment; any other a reply.
 * @param {readonly WaitedMessage[]} messages */
function yours(messages) {
  const kinds = new Set(
    messages.map(({ thread, message }) => (message === thread ? "comment" : "reply")),
  );
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

/** What the version `version` says it was saved after `messages`, in the order they
 * were sent: a heading, up to three quotes, each in the words `wordsOf` gives the
 * message, and past three how many more.
 * @param {string} version @param {readonly WaitedMessage[]} messages
 * @param {(message: WaitedMessage) => string} wordsOf
 * @returns {VersionProvenance} */
export function savedAfter(version, messages, wordsOf) {
  const shown = messages.slice(0, messages.length > QUOTED ? QUOTED - 1 : QUOTED);
  return Object.freeze({
    version,
    lines: Object.freeze([
      Object.freeze([
        leafSays(
          messages.length
            ? `${version} saved while ${yours(messages)} waited:`
            : `${version} saved with none of your comments waiting`,
        ),
      ]),
      ...shown.map((message) =>
        Object.freeze([quotedWords(wordsOf(message), QUOTE_CAP)]),
      ),
      ...(messages.length > shown.length
        ? [Object.freeze([leafSays(`and ${messages.length - shown.length} more`)])]
        : []),
    ]),
  });
}

/** A thread as the page holds it (thread/model.js).
 * @typedef {ReturnType<typeof allThreads>[number]} ThreadRecord */

/** The words a message had where it waited, as its thread reads the whole message
 * (thread/messages.js, `messageWords`): the thread's own reading where the words that
 * then stood are those it shows, else the message read with the words the server names,
 * those it was sent with or a rewrite's from the thread's rewrites.
 * @param {Pick<ThreadRecord, "msgs" | "revisions"> | null} thread
 * @param {WaitedMessage} waited */
export function waitedWords(thread, { message, said }) {
  const record = thread?.msgs.find(({ id }) => id === message);
  if (!record) return "";
  if (record.body.kind === "authored" || said === (record.edited?.id ?? message))
    return messageWords(record);
  const rewrites = thread?.revisions.filter((edit) => edit.message === message) ?? [];
  const text =
    said === message ? rewrites[0]?.was : rewrites.find(({ id }) => id === said)?.text;
  return messageWords({ ...record, id: `${message}@${said}`, text, edited: null });
}

// The last reading `versionProvenance` made, and what it was made from.
/** @type {{inputs: readonly unknown[], value: VersionProvenance | null} | null} */
let held = null;

/** What the version the comparison shows was saved after, or null where the server
 * says nothing of it. Nothing else is read while no comparison stands, and the words
 * quoted are read from the threads of the messages quoted. */
export function versionProvenance() {
  const messages = comparisonSavedAfter();
  if (!messages) return null;
  const shown = runtime.currentRevision;
  const { versions } = runtime;
  const threads = messages.length ? allThreads() : null;
  // A message's words read otherwise once the Markdown renderer has arrived.
  const inputs = [messages, shown, versions, threads, markdownReady()];
  if (held && held.inputs.every((input, at) => input === inputs[at])) return held.value;
  const stamp = versions.find(({ revision }) => revision === shown);
  const value = savedAfter(stamp ? `v${stamp.version}` : "Draft", messages, (waited) =>
    waitedWords(threadNamed(waited.thread), waited),
  );
  held = { inputs, value };
  return value;
}
