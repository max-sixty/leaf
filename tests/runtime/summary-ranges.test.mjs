import assert from "node:assert/strict";
import test from "node:test";

import { summaryRanges, withPendingProgress } from "/runtime/thread/summary-ranges.js";
import { threadSearchReading } from "/runtime/thread/narrowing.js";

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
  // a and d are the user's; b, c and e are progress no answer has folded; f is progress
  // the server already folded behind its answer, which stays as the server named it.
  const thread = [
    { id: "a", key: "a" },
    { id: "b", key: "b", progress: true },
    { id: "c", key: "c", progress: true },
    { id: "d", key: "d" },
    { id: "e", key: "e", progress: true },
    { id: "f", key: "f", progress: true },
  ];
  const folded = { id: "ephemeral:f:g", covers: ["f"], trigger: "g" };
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
      ["ephemeral:f:g", ["f"], undefined],
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

test("thread search identifies matching originals independently of summary prose", () => {
  const thread = {
    msgs: [
      {
        id: "a",
        text: "opening words",
        body: { kind: "prose", text: "opening words" },
      },
      {
        id: "b",
        text: "original camera detail",
        body: { kind: "authored", text: "Measured in 18 minutes" },
      },
    ],
    summaries: [{ id: "s1", text: "checkpoint about the schedule" }],
  };
  assert.deepEqual(threadSearchReading(thread, "camera").messages, ["b"]);
  assert.deepEqual(threadSearchReading(thread, "schedule").messages, []);
  assert.deepEqual(threadSearchReading(thread, "18 minutes").messages, ["b"]);
});
