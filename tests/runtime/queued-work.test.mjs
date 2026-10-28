/* The neutral job home runs in Node without installing any browser platform.
   Queues own scheduling; this owner binds only one synchronous invocation. */
import assert from "node:assert/strict";
import test from "node:test";
import {
  bindQueuedWork,
  cancelWork,
  enqueueWork,
  observeQueuedWork,
  runWork,
} from "../../browser/runtime/queued-work.js";

test("a queued invocation preserves arguments and leaves the callback receiver unbound", () => {
  const value = Object.freeze({});
  const work = bindQueuedWork(function (received, second) {
    assert.equal(this, undefined);
    assert.equal(second, 42);
    return received;
  });
  assert.equal(work(value, 42), value);
});

test("retirement can reenter a bound invocation without running or attributing it twice", () => {
  const phases = [];
  let reenter = true;
  let work;
  const stop = observeQueuedWork((phase) => {
    phases.push(phase);
    if (phase === "finish" && reenter) {
      reenter = false;
      work();
    }
  });
  let calls = 0;
  try {
    work = bindQueuedWork(() => calls++);
    work();
    assert.equal(calls, 1);
    assert.deepEqual(phases, ["enqueue", "run", "finish"]);
  } finally {
    stop();
  }
});

test("cancellation can reenter while its successor keeps its own attribution", () => {
  const events = [];
  let successor;
  let reenter = true;
  const stop = observeQueuedWork((phase, job) => {
    events.push([phase, job]);
    if (phase === "cancel" && reenter) {
      reenter = false;
      successor = enqueueWork(() => "successor");
      cancelWork(job);
      runWork(job);
    }
  });
  try {
    const first = enqueueWork(() => assert.fail("cancelled work ran"));
    cancelWork(first);
    assert.equal(runWork(successor), "successor");
    assert.deepEqual(events, [
      ["enqueue", first],
      ["cancel", first],
      ["enqueue", successor],
      ["run", successor],
      ["finish", successor],
    ]);
  } finally {
    stop();
  }
});

test("a host-bound invocation returns its result and retires before its native async tail", async () => {
  const phases = [];
  const stop = observeQueuedWork((phase) => phases.push(phase));
  let release;
  const held = new Promise((resolve) => {
    release = resolve;
  });
  const work = bindQueuedWork(async (value) => {
    phases.push(`start:${value}`);
    await held;
    phases.push("tail");
    return value;
  });
  assert.deepEqual(phases, ["enqueue"]);
  const result = work(42);
  assert.deepEqual(phases, ["enqueue", "run", "start:42", "finish"]);
  stop();
  release();
  assert.equal(await result, 42);
  assert.deepEqual(phases, ["enqueue", "run", "start:42", "finish", "tail"]);
});
