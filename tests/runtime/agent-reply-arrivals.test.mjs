import assert from "node:assert/strict";
import test from "node:test";

import {
  agentReplyArrivals,
  agentReplyNotice,
} from "/runtime/conversation/arrivals.js";

const thread = (root, ...msgs) => ({ root: { id: root }, msgs });
const reply = (id, extra = {}) => ({ id, kind: "reply", author: "agent", ...extra });

test("reply arrivals compare canonical identities across complete readings", () => {
  const initial = agentReplyArrivals(null, [thread("a", reply("old"))]);
  assert.deepEqual(initial.arrivals, []);

  const next = agentReplyArrivals(initial.observed, [
    thread("a", reply("old"), reply("new-a")),
    thread("b", reply("new-b")),
  ]);
  assert.equal(agentReplyNotice(next.arrivals), "2 replies in 2 threads");
  assert.deepEqual(
    agentReplyArrivals(next.observed, [
      thread("a", reply("old"), reply("new-a", { text: "edited" })),
      thread("b", reply("new-b")),
    ]).arrivals,
    [],
  );

  // Equal totals can still include a new reply, and a temporarily absent reply
  // does not arrive again when it returns.
  const changed = agentReplyArrivals(next.observed, [
    thread("a", reply("old"), reply("new-c")),
    thread("b", reply("new-b")),
  ]);
  assert.deepEqual(
    changed.arrivals.map(({ message }) => message.id),
    ["new-c"],
  );
  assert.equal(agentReplyNotice(changed.arrivals), "Agent replied");
  assert.deepEqual(
    agentReplyArrivals(changed.observed, [
      thread("a", reply("old"), reply("new-a"), reply("new-c")),
      thread("b", reply("new-b")),
    ]).arrivals,
    [],
  );
});

test("an accepted id keeps the optimistic attempt identity", () => {
  const first = agentReplyArrivals(null, [
    thread("pending:root", reply("pending:reply", { attempt: "reply-attempt" })),
  ]);
  const accepted = agentReplyArrivals(first.observed, [
    thread("root", reply("server-reply", { attempt: "reply-attempt" })),
  ]);
  assert.deepEqual(accepted.arrivals, []);
});

test("provisional streamed turns arrive only after admission to the log", () => {
  const initial = agentReplyArrivals(null, [thread("root", reply("old"))]);
  const streaming = agentReplyArrivals(initial.observed, [
    thread(
      "root",
      reply("old"),
      reply("stream:turn", {
        attempt: "reply-attempt",
        addressable: false,
        pending: true,
      }),
    ),
  ]);
  assert.deepEqual(streaming.arrivals, []);
  const interrupted = agentReplyArrivals(streaming.observed, [
    thread(
      "root",
      reply("old"),
      reply("stream:turn", {
        attempt: "reply-attempt",
        addressable: false,
        pending: false,
      }),
    ),
  ]);
  assert.deepEqual(interrupted.arrivals, []);
  const admitted = agentReplyArrivals(interrupted.observed, [
    thread("root", reply("old"), reply("real", { attempt: "reply-attempt" })),
  ]);
  assert.deepEqual(
    admitted.arrivals.map(({ message }) => message.id),
    ["real"],
  );
});

test("host failure receipts do not claim the agent answered", () => {
  const baseline = agentReplyArrivals(null, [thread("root", reply("old"))]);
  const receipt = agentReplyArrivals(baseline.observed, [
    thread("root", reply("old"), reply("failed", { failure: "turn_failed" })),
  ]);
  assert.deepEqual(receipt.arrivals, []);
  const answer = agentReplyArrivals(receipt.observed, [
    thread(
      "root",
      reply("old"),
      reply("failed", { failure: "turn_failed" }),
      reply("answer"),
    ),
  ]);
  assert.deepEqual(
    answer.arrivals.map(({ message }) => message.id),
    ["answer"],
  );
});
