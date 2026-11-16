/* How an obligation the agent ended reads: Leaf's word for its outcome, which a folded
   Done row shows alone, and after a dot the agent's note, which every surface with room
   for a sentence adds, each in its speaker's voice. */
import assert from "node:assert/strict";
import test from "node:test";
import { obligationEnding, obligationOutcome } from "/runtime/obligations/answer.js";

/** @param {string} status @param {string | null} detail */
const ended = (status, detail) => ({
  source: { kind: "message", id: "q1" },
  answer: null,
  status,
  end: { detail, event: { id: "e1", seq: 2, ts: "", author: "agent" } },
});

test("an obligation the agent ended says its outcome, then the agent's note", () => {
  const settled = ended("answered_elsewhere", "Merged as a29");
  assert.deepEqual(obligationOutcome(settled), { text: "Settled", voice: "leaf" });
  assert.deepEqual(obligationEnding(settled), [
    { text: "Settled", voice: "leaf" },
    " · ",
    { text: "Merged as a29", voice: "agent" },
  ]);
  assert.deepEqual(obligationEnding(ended("withdrawn", "The list moved")), [
    { text: "Withdrawn", voice: "leaf" },
    " · ",
    { text: "The list moved", voice: "agent" },
  ]);
  assert.deepEqual(obligationEnding(ended("answered_elsewhere", null)), {
    text: "Settled",
    voice: "leaf",
  });
});
