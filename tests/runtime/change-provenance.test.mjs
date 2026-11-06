import assert from "node:assert/strict";
import test from "node:test";
import { provenanceOf } from "/runtime/change-provenance.js";
import { wordsText } from "/runtime/voice.js";

const versionOf = (revision) => (revision <= 2 ? "v2" : revision <= 4 ? "v3" : "Draft");
const thread = (id, words) => ({ thread: id, message: id, kind: "comment", words });
const messages = {
  stall: thread("stall", "Why ship with that?"),
  rollout: thread("rollout", "What decides going past 5%?"),
  reply: {
    thread: "rollout",
    message: "reply",
    kind: "reply",
    words: "Past 5%, I mean.",
  },
};
const messageOf = ({ message }) => messages[message] ?? null;
const said = (provenance) => provenance.lines.map((line) => wordsText(line));
// A message's wait as places in the log: sent at `from`, ended at `until`, or waiting.
const wait = (id, from, until = null) => ({
  id,
  thread: messages[id].thread,
  message: id,
  from,
  until,
});
// A revision that went live after the log's event `after`.
const made = (revision, after) => ({ revision, after });

test("a change says, for each set of messages waiting as the revisions that made it went live, where they landed and which", () => {
  const waits = [wait("stall", 1, 20), wait("rollout", 30, 60), wait("reply", 31, 40)];
  // Revisions that went live while the same messages waited share their line, whichever
  // versions they landed in; a message's own place counts as before the revision.
  assert.deepEqual(
    said(provenanceOf([made(1, 1), made(2, 19)], waits, versionOf, messageOf)),
    ["In v2, after your comment:", "“Why ship with that?”"],
  );
  // A revision that went live with none waiting says so, a wait's end included;
  // messages of both kinds are the user's updates.
  assert.deepEqual(
    said(
      provenanceOf(
        [made(3, 20), made(4, 35), made(6, 45)],
        waits,
        versionOf,
        messageOf,
      ),
    ),
    [
      "In v3, with none of your comments waiting",
      "In v3, after your 2 updates:",
      "“What decides going past 5%?”",
      "“Past 5%, I mean.”",
      "In Draft, after your comment:",
      "“What decides going past 5%?”",
    ],
  );
  // Past three quoted lines, the rest is a count; a wait still open spans every
  // revision after it.
  const many = provenanceOf(
    [made(2, 5), made(4, 9), made(9, 90)],
    [wait("stall", 1), wait("rollout", 1), wait("reply", 1, 10)],
    versionOf,
    messageOf,
  );
  assert.deepEqual(said(many), [
    "In v2 and v3, after your 3 updates:",
    "“Why ship with that?”",
    "“What decides going past 5%?”",
    "“Past 5%, I mean.”",
    "In Draft, after your 2 comments:",
    "and 2 more",
  ]);
  // A change no revision made, as a pick is, and one only revisions with no place in
  // the log made, say nothing.
  assert.equal(provenanceOf([], waits, versionOf, messageOf), null);
  assert.equal(provenanceOf([made(2, null)], waits, versionOf, messageOf), null);
});
