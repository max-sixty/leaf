import assert from "node:assert/strict";
import test from "node:test";

import { summaryRanges } from "/runtime/conversation/summary-ranges.js";
import { threadSearchReading } from "/runtime/conversation/narrowing.js";

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

test("malformed noncontiguous coverage leaves every original visible", () => {
  const ranges = summaryRanges(messages, [
    { id: "s1", covers: ["b", "d"], protected: [], text: "Invalid" },
  ]);
  assert.deepEqual(
    ranges.map(({ message }) => message.id),
    ["a", "b", "c", "d", "e"],
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
