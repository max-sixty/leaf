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
const after = (...ids) =>
  ids.map((id) => ({ thread: messages[id].thread, message: id }));

test("a change says, for each set of messages the revisions that made it came after, where they landed and which", () => {
  const cameAfter = {
    1: after("stall"),
    2: after("stall"),
    4: after("rollout", "reply"),
    6: after("rollout"),
  };
  // Revisions after the same messages share their line, whichever versions they
  // landed in.
  assert.deepEqual(said(provenanceOf([1, 2], cameAfter, versionOf, messageOf)), [
    "In v2, after your comment:",
    "“Why ship with that?”",
  ]);
  // A revision with no message waiting says so; messages of both kinds are the
  // user's updates.
  assert.deepEqual(said(provenanceOf([3, 4, 6], cameAfter, versionOf, messageOf)), [
    "In v3, with none of your comments waiting",
    "In v3, after your 2 updates:",
    "“What decides going past 5%?”",
    "“Past 5%, I mean.”",
    "In Draft, after your comment:",
    "“What decides going past 5%?”",
  ]);
  // Past three quoted lines, the rest is a count.
  const many = provenanceOf(
    [2, 4, 6],
    { ...cameAfter, 2: after("stall", "rollout", "reply") },
    versionOf,
    messageOf,
  );
  assert.deepEqual(said(many), [
    "In v2, after your 3 updates:",
    "“Why ship with that?”",
    "“What decides going past 5%?”",
    "“Past 5%, I mean.”",
    "In v3, after your 2 updates:",
    "and 2 more",
    "In Draft, after your comment:",
    "and 1 more",
  ]);
  // A change no revision made, as a pick is, has no provenance.
  assert.equal(provenanceOf([], cameAfter, versionOf, messageOf), null);
});
