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
  assert.equal(owner.open, false);
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

test("completion releases the slot and asynchronous wakes lose ownership", async () => {
  const owner = new WatchOwner();
  const old = processWatch();
  const next = processWatch();
  const woke = Promise.withResolvers();
  let live;
  await owner.ensure(
    true,
    () => old,
    (_out, current) => {
      live = current;
      woke.resolve();
    },
  );
  old.exit.resolve("input");
  await woke.promise;
  assert.equal(live(), true);
  await owner.ensure(
    false,
    () => next,
    () => {},
  );
  assert.equal(live(), false);
  assert.equal(owner.open, true);
  const stopping = owner.close();
  await next.stopping.promise;
  next.exit.resolve("");
  await stopping;
});

test("a rejected cancellation still waits for exit and allows shutdown", async () => {
  const owner = new WatchOwner();
  const old = processWatch();
  old.stop = () => {
    old.stopping.resolve();
    throw new Error("cancelled iterator");
  };
  await owner.ensure(
    false,
    () => old,
    () => assert.fail("cancelled watch wakes"),
  );
  const failed = assert.rejects(
    owner.ensure(
      true,
      () => assert.fail("failed replacement starts"),
      () => {},
    ),
    /cancelled iterator/,
  );
  await old.stopping.promise;
  let closed = false;
  const closing = owner.close().then(() => {
    closed = true;
  });
  await new Promise(setImmediate);
  assert.equal(closed, false);
  old.exit.resolve("");
  await Promise.all([failed, closing]);
  assert.equal(closed, true);
});

test("failed host operations leave the next Stop free to start", async () => {
  for (const failure of ["start", "stop"]) {
    const owner = new WatchOwner();
    if (failure === "stop") {
      const old = processWatch();
      old.stop = () => {
        old.exit.resolve("");
        throw new Error("host unavailable");
      };
      await owner.ensure(
        true,
        () => old,
        () => {},
      );
    }
    await assert.rejects(
      owner.ensure(
        false,
        () => {
          throw new Error("host unavailable");
        },
        () => {},
      ),
      /host unavailable/,
    );
    let started = false;
    await owner.ensure(
      false,
      () => {
        started = true;
        return { stop() {}, done: Promise.resolve("") };
      },
      () => {},
    );
    assert.equal(started, true, `${failure} failure kept an absent watch`);
    await owner.close();
  }
});
