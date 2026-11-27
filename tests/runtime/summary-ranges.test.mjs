import assert from "node:assert/strict";
import test from "node:test";

import { summaryRanges, workingPlace } from "/runtime/records/thread/summary-ranges.js";

const messages = ["a", "b", "c", "d", "e"].map((id) => ({ id, key: id }));

test("summary ranges replace their contiguous originals without taking later messages", () => {
  const summary = {
    id: "s1",
    covers: ["b", "c", "d"],
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

test("reaction ids inside canonical coverage do not break the visible range", () => {
  const ranges = summaryRanges(messages, [
    {
      id: "s1",
      covers: ["b", "reaction", "c"],
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

test("a face stands after the range holding the last message said before it, or first", () => {
  // The transcript hands no step to the ranges: it draws each as a face.
  const thread = [
    { id: "a", key: "a" },
    { id: "c", key: "c" },
    { id: "d", key: "d" },
    { id: "e", key: "e" },
  ].map((message, index) => ({ ...message, sequence: (index + 1) * 10 }));
  const folded = {
    id: "s1",
    covers: ["b", "c", "d"],
    text: "Checkpoint",
  };
  const ranges = summaryRanges(thread, [folded]);
  // After a message of its own, and after a summary holding the message before it,
  // even where the face falls inside the summary's interval.
  assert.deepEqual(
    [15, 25, 35, 45].map((position) => workingPlace(ranges, position)),
    [0, 1, 1, 2],
  );
  assert.equal(workingPlace(ranges, 0), -1);
});
