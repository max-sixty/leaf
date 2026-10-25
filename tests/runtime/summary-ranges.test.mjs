import assert from "node:assert/strict";
import test from "node:test";

import {
  summaryRanges,
  withPendingProgress,
  workingPlace,
} from "/runtime/thread/summary-ranges.js";

const messages = ["a", "b", "c", "d", "e"].map((id) => ({ id, key: id }));

test("summary ranges replace their contiguous originals without taking later messages", () => {
  const summary = {
    id: "s1",
    covers: ["b", "c", "d"],
    protected: [],
    text: "Checkpoint",
  };
  const ranges = summaryRanges(messages, [summary]);
  assert.deepEqual(
    ranges.map(({ kind, message, messages: covered }) =>
      kind === "message" ? message.id : covered.map(({ id }) => id),
    ),
    ["a", ["b", "c", "d"], "e"],
  );
});

test("progress no fold covers is gathered per run, named for its first message", () => {
  // a and d are the user's; b, c and e are pending progress; f is covered by
  // an explicit summary, which stays as the server named it.
  const thread = [
    { id: "a", key: "a" },
    { id: "b", key: "b", progress: true },
    { id: "c", key: "c", progress: true },
    { id: "d", key: "d" },
    { id: "e", key: "e", progress: true },
    { id: "f", key: "f", progress: true },
  ];
  const folded = { id: "s1", covers: ["f"], text: "Checkpoint" };
  const ranges = withPendingProgress(summaryRanges(thread, [folded]));
  assert.deepEqual(
    ranges.map(({ kind, message, summary }) =>
      kind === "message" ? message.id : [summary.id, summary.covers, summary.pending],
    ),
    [
      "a",
      ["progress:b", ["b", "c"], true],
      "d",
      ["progress:e", ["e"], true],
      ["s1", ["f"], undefined],
    ],
  );
});

test("reaction ids inside canonical coverage do not break the visible range", () => {
  const ranges = summaryRanges(messages, [
    {
      id: "s1",
      covers: ["b", "reaction", "c"],
      protected: [],
      text: "Includes an omitted reaction",
    },
  ]);
  assert.deepEqual(
    ranges.map(({ kind, message, messages: covered }) =>
      kind === "message" ? message.id : covered.map(({ id }) => id),
    ),
    ["a", ["b", "c"], "d", "e"],
  );
});

test("the working message stands after the range holding the last message said before it", () => {
  const thread = [
    { id: "a", key: "a" },
    { id: "b", key: "b", progress: true },
    { id: "c", key: "c" },
    { id: "d", key: "d", progress: true },
    { id: "e", key: "e" },
  ];
  const folded = { id: "s1", covers: ["c", "d"], protected: [], text: "Checkpoint" };
  const ranges = withPendingProgress(summaryRanges(thread, [folded]));
  // A step's run, a summary holding the message, and a message of its own.
  assert.deepEqual(
    ["b", "d", "e"].map((after) => workingPlace(ranges, after)),
    [1, 2, 3],
  );
  assert.throws(() => workingPlace(ranges, "z"));
});
