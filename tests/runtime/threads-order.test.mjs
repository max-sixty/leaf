/* Threads lists its rows newest first, by where in the log each thread last changed
   (`lastChange`, state/thread/model.js), so a resolved row's place agrees with the age
   it says. */
import assert from "node:assert/strict";
import test from "node:test";

import { lastChange, newestFirst } from "../../browser/runtime/state/thread/model.js";

/** @param {string} id @param {object[]} msgs @param {object | null} [resolved] */
const thread = (id, msgs, resolved = null) => ({ id, root: msgs[0], msgs, resolved });

test("Threads reads newest first by each thread's latest turn or its closing", () => {
  const threads = [
    // Resolved, then the agent's message reached it without reopening it: it stands at
    // its resolve, which its row's age dates.
    thread(
      "resolved-then-told",
      [
        { id: "a", seq: 1 },
        { id: "a2", seq: 9 },
      ],
      { seq: 3 },
    ),
    // A reaction is a turn as words are, and so is a rewrite, where the log holds it.
    thread("reacted", [
      { id: "b", seq: 4 },
      { id: "b2", seq: 10, emoji: "👍" },
    ]),
    thread("rewritten", [{ id: "c", seq: 2, edited: { seq: 8, ts: "" } }]),
    thread("replied", [
      { id: "d", seq: 5 },
      { id: "d2", seq: 7 },
    ]),
    // A reply still streaming counts once the log holds it.
    thread("streaming", [
      { id: "g", seq: 6 },
      { id: "g2", provisional: true },
    ]),
    // The user's own change the log doesn't hold yet is newest, the later of two
    // such first.
    thread("resolving", [{ id: "e", seq: 1 }], { author: "user", pending: true }),
    thread("rewriting", [{ id: "h", seq: 0, edited: { ts: "" } }]),
  ];
  assert.deepEqual(
    newestFirst(threads, lastChange).map(({ id }) => id),
    [
      "rewriting",
      "resolving",
      "reacted",
      "rewritten",
      "replied",
      "streaming",
      "resolved-then-told",
    ],
  );
});
