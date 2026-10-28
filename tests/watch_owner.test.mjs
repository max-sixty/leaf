// Host process termination is external: hold it explicitly so replacement and
// shutdown races are checked independently of process speed or event timing.
import assert from "node:assert/strict";
import { test } from "node:test";
import { WatchOwner } from "../hooks/watch.ts";

function processWatch() {
  const exit = Promise.withResolvers();
  const stopping = Promise.withResolvers();
  return { done: exit.promise, stop: () => stopping.resolve(), exit, stopping };
}

test("replacement retains termination and only the latest ending starts", async () => {
  const owner = new WatchOwner();
  const old = processWatch();
  const next = processWatch();
  const starts = [];
  const wakes = [];
  await owner.ensure(
    false,
    () => old,
    (out) => wakes.push(out),
  );
  await owner.ensure(
    false,
    () => assert.fail("a Stop replaces no Stop"),
    () => {},
  );
  const first = owner.ensure(
    true,
    () => assert.fail("superseded start"),
    () => {},
  );
  await old.stopping.promise;
  const last = owner.ensure(
    true,
    () => {
      starts.push("Interrupt");
      return next;
    },
    (out) => wakes.push(out),
  );
  // A macrotask gives an incorrectly unlocked slot time to spawn early.
  await new Promise(setImmediate);
  assert.deepEqual(starts, []);
  old.exit.resolve("stale wake");
  await Promise.all([first, last]);
  assert.deepEqual(starts, ["Interrupt"]);
  assert.deepEqual(wakes, []);
  const stopping = owner.close();
  await next.stopping.promise;
  next.exit.resolve("stale shutdown wake");
  await stopping;
  assert.deepEqual(wakes, []);
});

test("shutdown waits for termination and invalidates queued replacements", async () => {
  const owner = new WatchOwner();
  const old = processWatch();
  await owner.ensure(
    false,
    () => old,
    () => assert.fail("shutdown wakes"),
  );
  const replacing = owner.ensure(
    true,
    () => assert.fail("shutdown starts"),
    () => {},
  );
  await old.stopping.promise;
  let closed = false;
  const closing = owner.close().then(() => {
    closed = true;
  });
  await new Promise(setImmediate);
  assert.equal(closed, false);
  old.exit.resolve("stale");
  await Promise.all([replacing, closing]);
  await owner.ensure(
    false,
    () => assert.fail("closed owner starts"),
    () => {},
  );
  assert.equal(closed, true);
});

test("completion releases the slot for the next Stop", async () => {
  const owner = new WatchOwner();
  const old = processWatch();
  const next = processWatch();
  const woke = Promise.withResolvers();
  await owner.ensure(
    true,
    () => old,
    () => woke.resolve(),
  );
  old.exit.resolve("input");
  await woke.promise;
  await owner.ensure(
    false,
    () => next,
    () => {},
  );
  const stopping = owner.close();
  await next.stopping.promise;
  next.exit.resolve("");
  await stopping;
});
