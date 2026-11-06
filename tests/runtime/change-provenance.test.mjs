import assert from "node:assert/strict";
import test from "node:test";
import { savedAfter } from "/runtime/change-provenance.js";
import { wordsText } from "/runtime/voice.js";

const said = (provenance) => provenance.lines.map((line) => wordsText(line));
// A message the server names, in the thread `thread`: a comment where it opened it.
const waited = (message, words, thread = message) => ({ thread, message, words });

test("a version says which of the user's messages waited while it was saved", () => {
  assert.deepEqual(said(savedAfter("v4", [waited("stall", "Make it blue")])), [
    "v4 saved while your comment waited:",
    "“Make it blue”",
  ]);
  // Messages of both kinds are the user's updates, and past the three the server read
  // words for (provenance.py, `QUOTED`) the rest is a count.
  const four = [
    waited("stall", "Actually make it red"),
    waited("rollout", "What decides going past 5%?"),
    waited("reply", "Past 5%, I mean.", "rollout"),
    { thread: "title", message: "title" },
  ];
  assert.deepEqual(said(savedAfter("Draft", four.slice(0, 3))), [
    "Draft saved while your 3 updates waited:",
    "“Actually make it red”",
    "“What decides going past 5%?”",
    "“Past 5%, I mean.”",
  ]);
  assert.deepEqual(said(savedAfter("Draft", four)), [
    "Draft saved while your 4 updates waited:",
    "“Actually make it red”",
    "“What decides going past 5%?”",
    "and 2 more",
  ]);
  assert.deepEqual(said(savedAfter("v2", [waited("reply", "Past 5%?", "rollout")])), [
    "v2 saved while your reply waited:",
    "“Past 5%?”",
  ]);
  // A version saved with nothing waiting says so.
  assert.deepEqual(said(savedAfter("v2", [])), [
    "v2 saved with none of your comments waiting",
  ]);
});
