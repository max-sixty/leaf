import assert from "node:assert/strict";
import test from "node:test";
import { savedAfter } from "/runtime/change-provenance.js";
import { wordsText } from "/runtime/voice.js";

const said = (provenance) => provenance.lines.map((line) => wordsText(line));
// A wait as places in the log: from `from` until `until`, or waiting still.
const wait = (message, from, until, words, thread = message) => ({
  id: `${message}:${from}`,
  thread,
  message,
  words,
  from,
  until,
});

test("a version says which messages waited while its revisions went live, each once, with the words it had then", () => {
  const waits = [
    wait("stall", 1, 20, "Make it blue"),
    wait("stall", 25, null, "Actually make it red"),
    wait("rollout", 30, 60, "What decides going past 5%?"),
    wait("reply", 31, 40, "Past 5%, I mean.", "rollout"),
  ];
  // A wait holds the places after its start, and its end, where the reply or note
  // that ended it published the revision; a message waiting twice is named once, with
  // the latest words.
  assert.deepEqual(said(savedAfter("v4", [20], waits)), [
    "v4 saved while your comment waited:",
    "“Make it blue”",
  ]);
  assert.deepEqual(said(savedAfter("v4", [20, 26], waits)), [
    "v4 saved while your comment waited:",
    "“Actually make it red”",
  ]);
  // Messages of both kinds are the user's updates, a message rewritten while the
  // version was saved reads as it did at its end, and past three quotes the rest is a
  // count.
  assert.deepEqual(said(savedAfter("Draft", [10, 35], waits)), [
    "Draft saved while your 3 updates waited:",
    "“Actually make it red”",
    "“What decides going past 5%?”",
    "“Past 5%, I mean.”",
  ]);
  assert.deepEqual(
    said(
      savedAfter(
        "Draft",
        [10, 35],
        [...waits, wait("title", 2, 12, "Is the title right?")],
      ),
    ),
    [
      "Draft saved while your 4 updates waited:",
      "“Actually make it red”",
      "“What decides going past 5%?”",
      "and 2 more",
    ],
  );
  // A version saved with nothing waiting says so, a wait's start included.
  assert.deepEqual(said(savedAfter("v2", [21, 25], waits)), [
    "v2 saved with none of your comments waiting",
  ]);
});
