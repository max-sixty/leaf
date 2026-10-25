/* A page script's view of a widget: it starts at the page interface, holding
   presentation until it has connected, declares once per lifetime, and reconnects at
   once without declaring again. */
import assert from "node:assert/strict";
import test from "node:test";

const { PAGE_INTERFACE, whileInterfaceConnected } =
  await import("/runtime/presentation.js");

// A second observer acknowledges delivery of the same mutation batch as arrivals.
async function mutate(change) {
  const observed = new Promise((resolve) => {
    const observer = new MutationObserver(() => {
      observer.disconnect();
      resolve();
    });
    observer.observe(document.body, { childList: true, subtree: true });
  });
  change();
  await observed;
}

// Startup's dispatch, returning what the listeners passed to present().
async function pageInterface() {
  const pending = [];
  document.dispatchEvent(
    new CustomEvent(PAGE_INTERFACE, {
      detail: { present: (promise) => (pending.push(promise), promise) },
    }),
  );
  await Promise.all(pending);
  return pending.length;
}

test("a view declares once, connects at the page interface and again on return", async () => {
  const view = document.createElement("section");
  const calls = [];
  const stop = whileInterfaceConnected(view, {
    declare: () => calls.push("declare"),
    connect: (signal) => {
      calls.push("connect");
      return () => calls.push(`cleanup ${signal.aborted}`);
    },
  });
  try {
    await mutate(() => document.body.append(view));
    assert.deepEqual(calls, []);
    assert.equal(await pageInterface(), 1);
    assert.deepEqual(calls, ["declare", "connect"]);
    // A revision applied in place finds the view connected.
    await pageInterface();
    assert.deepEqual(calls, ["declare", "connect"]);
    await mutate(() => view.remove());
    assert.deepEqual(calls, ["declare", "connect", "cleanup true"]);
    await mutate(() => document.body.append(view));
    assert.deepEqual(calls, ["declare", "connect", "cleanup true", "connect"]);
  } finally {
    stop();
    view.remove();
  }
});

test("a view that leaves before the page interface connects on its return", async () => {
  const view = document.createElement("section");
  const calls = [];
  const stop = whileInterfaceConnected(view, {
    connect: () => void calls.push("connect"),
  });
  try {
    await mutate(() => document.body.append(view));
    await mutate(() => view.remove());
    assert.equal(await pageInterface(), 0);
    await mutate(() => document.body.append(view));
    assert.deepEqual(calls, []);
    await pageInterface();
    assert.deepEqual(calls, ["connect"]);
  } finally {
    stop();
    view.remove();
  }
});
