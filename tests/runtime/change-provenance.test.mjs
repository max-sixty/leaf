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
const answered = (...ids) => ({
  messages: ids.map((id) => ({ thread: messages[id].thread, message: id })),
  answered: true,
});

test("a change says, for each thing the revisions that made it did, where they landed and what they answered", () => {
  const answers = {
    1: answered("stall"),
    2: answered("stall"),
    4: answered("rollout", "reply"),
    6: { ...answered("rollout"), answered: false },
  };
  // Revisions that answered one thing share its line, whichever versions they landed in.
  assert.deepEqual(said(provenanceOf([1, 2], answers, versionOf, messageOf)), [
    "In v2, answering your comment:",
    "“Why ship with that?”",
  ]);
  // A revision that answered nothing says so; one made while a message waits stands
  // after it; messages of both kinds are the user's updates.
  assert.deepEqual(said(provenanceOf([3, 4, 6], answers, versionOf, messageOf)), [
    "In v3, answering none of your comments",
    "In v3, answering your 2 updates:",
    "“What decides going past 5%?”",
    "“Past 5%, I mean.”",
    "In Draft, after your comment:",
    "“What decides going past 5%?”",
  ]);
  // Past three quoted lines, the rest is a count.
  const many = provenanceOf(
    [2, 4, 6],
    { ...answers, 2: answered("stall", "rollout", "reply") },
    versionOf,
    messageOf,
  );
  assert.deepEqual(said(many).slice(0, 4), [
    "In v2, answering your 3 updates:",
    "“Why ship with that?”",
    "“What decides going past 5%?”",
    "“Past 5%, I mean.”",
  ]);
  assert.deepEqual(said(many).slice(4), [
    "In v3, answering your 2 updates:",
    "and 2 more",
    "In Draft, after your comment:",
    "and 1 more",
  ]);
  // A change no revision made, as a pick is, has no provenance.
  assert.equal(provenanceOf([], answers, versionOf, messageOf), null);
});
