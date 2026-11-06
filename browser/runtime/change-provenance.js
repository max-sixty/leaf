// @ts-check
/* Which of the user's comments a version was saved after: where the page compares a
   version with the one before it, as `v` does, every change it marks was made by that
   version's revisions, so one line under each change's count says the messages that
   waited while the version was saved (../SOUL.md, "Changes the user requests remain
   understandable as they happen").

   Python derives the waits from the log (src/leaf/provenance.py, `message_waits`),
   whose header says how far the order holds: each message's wait as places in the log,
   from its own until the agent answered it or its thread closed, with the words it had
   then. A revision's place is the seq of the event that names its bundle in
   `publication`: the reply or note that published it, or the `activation` a read
   appended. This module selects from those (`versionProvenance`): the revisions after
   the comparison's base through the one shown, the waits any of them went live
   inside, and the version they make, by its stamp, else Draft.

   The tie is one of order, so the words state order: the version was saved while
   these comments waited, or with none waiting. They say neither that it answers a
   comment nor which paragraph followed which, since the log establishes neither
   (provenance.py, "What reads it" and "How far the order holds"), and a comparison
   across several versions says nothing of this. The user chose on 5 November 2026 to
   say what each change came from rather than only what it did; the version is the
   part of that the log can back.

   `versionProvenance` is the one value a surface that describes a change reads, the ⇄
   entry's label (annotation-inventory.js), reading it once for every change. Its
   `lines` are the words a surface shows, each in its speaker's face: the heading in
   Leaf's voice ("v4 saved while your comment waited:"), then the opening line each
   message had then, in quotes, the user's own words. */
import { runtime } from "./context.js";
import { comparisonBase } from "./version.js";
import { leafSays } from "./voice.js";
import { counted, quotedWords } from "./words.js";

/** One of the user's messages a version was saved after: `words`, the opening line it
 * had then.
 * @typedef {Readonly<{thread: string, message: string, kind: "comment" | "reply", words: string}>} NamedMessage */
/** What a version was saved after: its name, the messages, and `lines`, what it says,
 * each line a run of words in their speakers' faces (voice.js).
 * @typedef {Readonly<{version: string, messages: readonly NamedMessage[], lines: readonly (readonly (string | import("./voice.js").Said)[])[]}>} VersionProvenance */
/** @typedef {import("../types/contract.js").ServedBrowser["message_waits"]} MessageWaits */

// The quoted lines a version's provenance shows at most before saying how many more.
const QUOTED = 3;
// The characters a quoted line keeps.
const QUOTE_CAP = 90;

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

/** What the version `version`, whose revisions went live at the places `places` in the
 * log, was saved after: each message a wait of which any of them went live inside,
 * once, with the words of the latest such wait, in the order the messages were sent.
 * A place inside a wait comes after its start, and at its end only where the reply or
 * note that ended it published the revision.
 * @param {string} version @param {readonly number[]} places ascending
 * @param {MessageWaits} waits @returns {VersionProvenance} */
export function savedAfter(version, places, waits) {
  /** @type {Map<string, NamedMessage>} */
  const messages = new Map();
  for (const wait of waits) {
    // The first place after the wait began, which must not come after it ended.
    let low = 0;
    let high = places.length;
    while (low < high) {
      const middle = (low + high) >> 1;
      if (/** @type {number} */ (places[middle]) <= wait.from) low = middle + 1;
      else high = middle;
    }
    const place = places[low];
    if (place === undefined || (wait.until !== null && place > wait.until)) continue;
    messages.set(
      wait.message,
      Object.freeze({
        thread: wait.thread,
        message: wait.message,
        kind: wait.message === wait.thread ? "comment" : "reply",
        words: wait.words,
      }),
    );
  }
  const said = [...messages.values()];
  const shown = said.slice(0, said.length > QUOTED ? QUOTED - 1 : QUOTED);
  return Object.freeze({
    version,
    messages: Object.freeze(said),
    lines: Object.freeze([
      Object.freeze([
        leafSays(
          said.length
            ? `${version} saved while ${yours(said)} waited:`
            : `${version} saved with none of your comments waiting`,
        ),
      ]),
      ...shown.map(({ words }) => Object.freeze([quotedWords(words, QUOTE_CAP)])),
      ...(said.length > shown.length
        ? [Object.freeze([leafSays(`and ${said.length - shown.length} more`)])]
        : []),
    ]),
  });
}

// The last reading `versionProvenance` made, and what it was made from.
/** @type {{inputs: readonly unknown[], value: VersionProvenance | null} | null} */
let held = null;

/** What the version the comparison shows was saved after, where the comparison's base
 * is the version before it; null for a comparison across several versions, and for a
 * version none of whose revisions has a place in the log. */
export function versionProvenance() {
  const base = comparisonBase();
  const shown = runtime.currentRevision;
  const { versions, events } = runtime;
  const waits = runtime.browser?.message_waits ?? [];
  const inputs = [base, shown, versions, events, waits];
  if (held && held.inputs.every((input, at) => input === inputs[at])) return held.value;
  /** @type {VersionProvenance | null} */
  let value = null;
  if (base && shown !== null) {
    const between = versions.some(
      ({ revision }) => base.revision < revision && revision < shown,
    );
    const places = events
      .flatMap((event) =>
        "publication" in event &&
        event.publication &&
        event.revision !== undefined &&
        base.revision < event.revision &&
        event.revision <= shown
          ? [event.seq]
          : [],
      )
      .sort((a, b) => a - b);
    const stamp = versions.find(({ revision }) => revision === shown);
    if (!between && places.length)
      value = savedAfter(stamp ? `v${stamp.version}` : "Draft", places, waits);
  }
  held = { inputs, value };
  return value;
}
