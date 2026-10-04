/* The neutral job home runs in Node without installing any browser platform.
   Queues own scheduling; this owner binds only one synchronous invocation. */
import assert from "node:assert/strict";
import test from "node:test";
import {
  bindQueuedWork,
  observeQueuedWork,
} from "../../skills/leaf/assets/runtime/queued-work.js";

test("a queued invocation preserves arguments and leaves the callback receiver unbound", () => {
  const value = Object.freeze({});
  const work = bindQueuedWork(function (received, second) {
    assert.equal(this, undefined);
    assert.equal(second, 42);
    return received;
  });
  assert.equal(work(value, 42), value);
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
