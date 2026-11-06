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
// A message's wait: sent on `from`, ended on `until`, or waiting still.
const wait = (id, from, until = null) => ({
  id,
  thread: messages[id].thread,
  message: id,
  from,
  until,
});

test("a change says, for each set of messages waiting while the revisions that made it were written, where they landed and which", () => {
  const waits = [wait("stall", 0, 2), wait("rollout", 3, 6), wait("reply", 3, 4)];
  // Revisions written while the same messages waited share their line, whichever
  // versions they landed in.
  assert.deepEqual(said(provenanceOf([1, 2], waits, versionOf, messageOf)), [
    "In v2, after your comment:",
    "“Why ship with that?”",
  ]);
  // A revision written with none waiting says so; messages of both kinds are the
  // user's updates; a wait that has ended names no revision after it.
  assert.deepEqual(said(provenanceOf([3, 4, 6], waits, versionOf, messageOf)), [
    "In v3, with none of your comments waiting",
    "In v3, after your 2 updates:",
    "“What decides going past 5%?”",
    "“Past 5%, I mean.”",
    "In Draft, after your comment:",
    "“What decides going past 5%?”",
  ]);
  // Past three quoted lines, the rest is a count; a wait still open names every
  // revision after it.
  const many = provenanceOf(
    [2, 4, 9],
    [wait("stall", 1), wait("rollout", 1), wait("reply", 1, 4)],
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
  // A change no revision made, as a pick is, has no provenance.
  assert.equal(provenanceOf([], waits, versionOf, messageOf), null);
});
