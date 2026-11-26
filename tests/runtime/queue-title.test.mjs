/* An On list row's title, read from what the row names: here, a thread the user's
   reaction opened, which the agent owes an answer. */
import assert from "node:assert/strict";
import test from "node:test";
import { queueTitle } from "/runtime/panel/queue-title.js";
import { applicationState } from "/runtime/state/semantic-state.js";
import { servedReading } from "../served.mjs";

test("a reaction the agent owes is named by its emoji on the agent's list", () => {
  const served = servedReading("a reaction waiting");
  applicationState.identify(served.active.revision);
  assert.equal(applicationState.adopt(served), true);
  const [row] = applicationState.read().effective.queues.on_agent;
  assert.equal(row.kind, "update");
  assert.equal(queueTitle(row), "✂️");
});
