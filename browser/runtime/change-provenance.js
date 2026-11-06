// @ts-check
/* Which of the user's comments a version was saved after: where the page compares a
   version with the one before it, as `v` does, every change it marks was made by that
   version's revisions, so one line under each change's count says the messages that
   waited while the version was saved (../SOUL.md, "Changes the user requests remain
   understandable as they happen").

   The server says which, with the base's reading the comparison asks for (`/api/view`,
   `saved_after`), from the threads as they stood before the version went live
   (src/leaf/provenance.py, `saved_after`, whose header says how far the order holds),
   or says nothing: for a comparison across several versions, and for a version a
   revision of which has no place in the log. This module says it in words
   (`versionProvenance`), naming the version by its stamp, else Draft.

   The tie is one of order, so the words state order: the version was saved while
   these comments waited, or with none waiting. They say neither that it answers a
   comment nor which paragraph followed which, since the log establishes neither. The
   user chose on 5 November 2026 to say what each change came from rather than only
   what it did; the version is the part of that the log can back.

   `versionProvenance` is the one value a surface that describes a change reads, the ⇄
   entry's label (annotation-inventory.js), reading it once for every change. Its
   `lines` are the words a surface shows, each in its speaker's face: the heading in
   Leaf's voice ("v4 saved while your comment waited:"), then each quoted message's
   opening line as it read where it waited, in quotes, the user's own words. */
import { runtime } from "./context.js";
import { comparisonSavedAfter } from "./version.js";
import { leafSays } from "./voice.js";
import { counted, quotedWords } from "./words.js";

/** One of the user's messages a version was saved after, as the server names it.
 * @typedef {NonNullable<import("../types/contract.js").ServedViewAnswer["saved_after"]>[number]} WaitedMessage */
/** What a version was saved after: its name and `lines`, what it says, each line a run
 * of words in their speakers' faces (voice.js).
 * @typedef {Readonly<{version: string, lines: readonly (readonly (string | import("./voice.js").Said)[])[]}>} VersionProvenance */

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
 * were sent: a heading, the quotes the server read words for (provenance.py,
 * `QUOTED`), and how many more, which takes the last quote's line where there are.
 * @param {string} version @param {readonly WaitedMessage[]} messages
 * @returns {VersionProvenance} */
export function savedAfter(version, messages) {
  const quotable = messages.flatMap(({ words }) =>
    words === undefined ? [] : [words],
  );
  const shown = messages.length > quotable.length ? quotable.slice(0, -1) : quotable;
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
      ...shown.map((words) => Object.freeze([quotedWords(words, QUOTE_CAP)])),
      ...(messages.length > shown.length
        ? [Object.freeze([leafSays(`and ${messages.length - shown.length} more`)])]
        : []),
    ]),
  });
}

// The last reading `versionProvenance` made, and what it was made from.
/** @type {{inputs: readonly unknown[], value: VersionProvenance | null} | null} */
let held = null;

/** What the version the comparison shows was saved after, or null where the server
 * says nothing of it. */
export function versionProvenance() {
  const messages = comparisonSavedAfter();
  const shown = runtime.currentRevision;
  const { versions } = runtime;
  const inputs = [messages, shown, versions];
  if (held && held.inputs.every((input, at) => input === inputs[at])) return held.value;
  const stamp = versions.find(({ revision }) => revision === shown);
  const value = messages && savedAfter(stamp ? `v${stamp.version}` : "Draft", messages);
  held = { inputs, value };
  return value;
}
