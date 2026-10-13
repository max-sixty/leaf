/* Data delivery and projection lifetime rules do not depend on Chrome layout.
   Native editing, syntax rendering, and reports reaching the page log stay in the
   browser journeys; these cases exercise the publisher and its real DOM owners. */
import assert from "node:assert/strict";
import test from "node:test";
import { adoptRegistry } from "/runtime/registry.js";
import { acceptData, notifyDataSubscribers } from "/runtime/data.js";

let fixtureSequence = 0;
async function scene() {
  adoptRegistry({
    "lf-feed": { "x-data": { rows: { source: "source", contract: "rows" } } },
    $data: { contracts: { rows: { records: { items: "", key: "key" } } } },
  });
  document.body.innerHTML =
    '<main><lf-feed id="deployments" source="deployments"></lf-feed></main>';
  acceptData(
    {
      version: `initial-${++fixtureSequence}`,
      sources: {
        deployments: {
          contract: "rows",
          revision: "initial-revision",
          value: [{ key: "api", value: "Running" }],
        },
      },
    },
    1,
  );
  await notifyDataSubscribers();
}

test("data subscriptions use own keys", async () => {
  await scene();
  const result = await (async () => {
    const { watchData } = await import("/runtime/widget-api.js");
    const { acceptData } = await import("/runtime/data.js");
    const { runtime } = await import("/runtime/context.js");
    const widget = document.querySelector("lf-feed");
    let currentRevision = null;
    const stopCurrent = watchData(widget, "rows", (snapshot) => {
      currentRevision = snapshot?.revision ?? null;
    });
    stopCurrent();
    widget.setAttribute("source", "constructor");
    let absent = "not-called";
    const stop = watchData(widget, "rows", (snapshot) => {
      absent = snapshot;
    });
    stop();

    const captured = [];
    const stopCaptured = watchData(widget, "rows", (snapshot) => {
      captured.push(snapshot);
    });
    widget.setAttribute("source", "deployments");
    const next = structuredClone(runtime.data);
    next.version = "next-version";
    next.sources.deployments.revision = "next-revision";
    acceptData(next, 1);
    stopCaptured();
    widget.removeAttribute("source");
    let unbound = "not-called";
    const stopUnbound = watchData(widget, "rows", (snapshot) => {
      unbound = snapshot;
    });
    stopUnbound();
    return { currentRevision, unbound, absent, captured };
  })();
  assert.deepEqual(result, {
    currentRevision: "initial-revision",
    unbound: null,
    absent: null,
    captured: [null],
  });
});

test("projection subscriptions follow their owner and cancel queued reads", async () => {
  await scene();
  const result = await (async () => {
    const { watchProjection } = await import("/runtime/projection-watch.js");
    const { clockValue, tickClock } = await import("/runtime/presence.js");
    const owner = document.createElement("div");
    document.body.append(owner);
    const changed = (action) =>
      new Promise((resolve) => {
        const observer = new MutationObserver(() => {
          observer.disconnect();
          resolve();
        });
        observer.observe(document.body, { childList: true, subtree: true });
        action();
      });
    let clock = 0;
    let cancelled = 0;
    const cancel = watchProjection(owner, () => {
      cancelled += 1;
      clockValue(() => clock);
    });
    cancel();
    await Promise.resolve();
    clock += 1;
    await tickClock((message) => {
      throw new Error(message);
    });
    let calls = 0;
    let trackClock = false;
    const stop = watchProjection(owner, () => {
      calls += 1;
      if (trackClock) clockValue(() => clock);
    });
    await Promise.resolve();
    const initial = calls;
    clock += 1;
    await tickClock((message) => {
      throw new Error(message);
    });
    const untracked = calls;
    trackClock = true;
    stop.refresh();
    const subscribed = calls;
    clock += 1;
    await tickClock((message) => {
      throw new Error(message);
    });
    const clocked = calls;
    await changed(() => {
      owner.remove();
      document.body.append(owner);
    });
    const moved = calls;
    await changed(() => owner.remove());
    clock += 1;
    await tickClock((message) => {
      throw new Error(message);
    });
    const detached = calls;
    await changed(() => document.body.append(owner));
    await Promise.resolve();
    const resumed = calls;
    await tickClock((message) => {
      throw new Error(message);
    });
    const ticked = calls;
    stop.refresh();
    const refreshed = calls;
    stop();
    stop.refresh();
    await changed(() => owner.remove());
    await changed(() => document.body.append(owner));
    clock += 1;
    await tickClock((message) => {
      throw new Error(message);
    });
    owner.remove();
    return {
      cancelled,
      initial,
      untracked,
      subscribed,
      clocked,
      moved,
      detached,
      resumed,
      ticked,
      refreshed,
      stopped: calls,
    };
  })();
  assert.deepEqual(result, {
    cancelled: 0,
    initial: 1,
    untracked: 1,
    subscribed: 2,
    clocked: 3,
    moved: 3,
    detached: 3,
    resumed: 3,
    ticked: 4,
    refreshed: 5,
    stopped: 5,
  });
});

test("data subscriptions follow their owner and stop permanently", async () => {
  await scene();
  const result = await (async () => {
    const { watchData, clockValue } = await import("/runtime/widget-api.js");
    const { acceptData, notifyDataSubscribers } = await import("/runtime/data.js");
    const { tickClock } = await import("/runtime/presence.js");
    const { runtime } = await import("/runtime/context.js");
    const widget = document.querySelector("lf-feed");
    const home = widget.parentElement;
    const changed = (action) =>
      new Promise((resolve) => {
        const observer = new MutationObserver(() => {
          observer.disconnect();
          resolve();
        });
        observer.observe(document.body, { childList: true, subtree: true });
        action();
      });
    const deliveries = [];
    let clock = 0;
    let trackClock = false;
    let release;
    const stop = watchData(widget, "rows", (snapshot) => {
      if (trackClock) clockValue(() => clock);
      deliveries.push(snapshot?.revision ?? null);
      if (snapshot?.revision === "held-owner")
        return new Promise((resolve) => {
          release = resolve;
        });
    });
    const initial = deliveries.length;
    clock += 1;
    await tickClock((message) => {
      throw new Error(message);
    });
    const untracked = deliveries.length;
    trackClock = true;
    stop.refresh();
    const subscribed = deliveries.length;
    clock += 1;
    await tickClock((message) => {
      throw new Error(message);
    });
    const clocked = deliveries.length;
    await changed(() => document.body.append(widget));
    const moved = deliveries.length;
    await changed(() => widget.remove());
    clock += 1;
    await tickClock((message) => {
      throw new Error(message);
    });
    const detached = deliveries.length;
    await changed(() => home.append(widget));
    const resumed = deliveries.length;
    await tickClock((message) => {
      throw new Error(message);
    });
    const ticked = deliveries.length;
    const next = structuredClone(runtime.data);
    next.version = "held-owner-version";
    next.sources.deployments.revision = "held-owner";
    const beforeStaging = deliveries.at(-1);
    acceptData(next, 1);
    stop.refresh();
    const stagingKept = deliveries.at(-1) === beforeStaging;
    const pending = notifyDataSubscribers();
    const held = deliveries.at(-1);
    await changed(() => widget.remove());
    await pending;
    release();
    const newest = structuredClone(runtime.data);
    newest.version = "newest-owner-version";
    newest.sources.deployments.revision = "newest-owner";
    acceptData(newest, 1);
    await notifyDataSubscribers();
    const absent = deliveries.length;
    await changed(() => home.append(widget));
    const restored = deliveries.at(-1);
    stop.refresh();
    const refreshed = deliveries.at(-1);
    stop();
    stop.refresh();
    await changed(() => widget.remove());
    await changed(() => home.append(widget));
    clock += 1;
    await tickClock((message) => {
      throw new Error(message);
    });
    return {
      initial,
      untracked,
      subscribed,
      clocked,
      moved,
      detached,
      resumed,
      ticked,
      held,
      absent,
      restored,
      refreshed,
      stagingKept,
      stopped: deliveries.length,
    };
  })();
  assert.deepEqual(result, {
    initial: 1,
    untracked: 1,
    subscribed: 2,
    clocked: 3,
    moved: 3,
    detached: 3,
    resumed: 3,
    ticked: 4,
    held: "held-owner",
    absent: 6,
    restored: "newest-owner",
    refreshed: "newest-owner",
    stagingKept: true,
    stopped: 8,
  });
});

test("a superseded async data render cannot stamp the newer version", async () => {
  await scene();
  const result = await (async () => {
    const { watchData } = await import("/runtime/widget-api.js");
    const { acceptData, notifyDataSubscribers } = await import("/runtime/data.js");
    const { runtime } = await import("/runtime/context.js");
    const widget = document.querySelector("lf-feed");
    const taken = 1;
    const releases = new Map();
    const stop = watchData(widget, "rows", (snapshot) => {
      const value = snapshot?.value?.[0]?.value;
      if (!value?.startsWith("Held")) return;
      return new Promise((resolve) => releases.set(value, resolve));
    });
    const waitFor = async (value) => {
      while (!releases.has(value))
        await new Promise((resolve) => setTimeout(resolve, 0));
    };
    const dataAt = (version, value) => ({
      ...structuredClone(runtime.data),
      version,
      sources: {
        ...structuredClone(runtime.data.sources),
        deployments: {
          ...structuredClone(runtime.data.sources.deployments),
          revision: version,
          value: [{ key: "api", value }],
        },
      },
    });
    const before = document.body.getAttribute("data-lf-data-version");
    acceptData(dataAt("older", "Held older"), taken);
    const older = notifyDataSubscribers();
    await waitFor("Held older");
    acceptData(dataAt("newer", "Held newer"), taken);
    const newer = notifyDataSubscribers();
    await waitFor("Held newer");

    releases.get("Held older")();
    await older;
    const afterOlder = document.body.getAttribute("data-lf-data-version");
    releases.get("Held newer")();
    await newer;
    const afterNewer = document.body.getAttribute("data-lf-data-version");
    stop();
    return { before, afterOlder, afterNewer };
  })();
  assert.equal(result.afterOlder, result.before);
  assert.equal(result.afterNewer, "newer");
});

test("unchanged source waits for its inflight render", async () => {
  await scene();
  const result = await (async () => {
    const { watchData } = await import("/runtime/widget-api.js");
    const { acceptData, notifyDataSubscribers } = await import("/runtime/data.js");
    const { runtime } = await import("/runtime/context.js");
    const { readApplicationPresentation } = await import("/runtime/check-api.js");
    let release;
    let calls = 0;
    const stop = watchData(document.querySelector("lf-feed"), "rows", () => {
      if (++calls > 1)
        return new Promise((resolve) => {
          release = resolve;
        });
    });
    const initial = runtime.data.version;
    const next = structuredClone(runtime.data);
    next.version = "next-version";
    next.sources.deployments.revision = "next-revision";
    acceptData(next, 1);
    const selectedBeforeNotify = {
      calls,
      pending: readApplicationPresentation().pending.some((region) =>
        region.startsWith("data:deployments:rows:"),
      ),
    };
    const first = notifyDataSubscribers();
    while (!release) await new Promise((resolve) => setTimeout(resolve, 0));
    let complete = false;
    const again = notifyDataSubscribers().then(() => {
      complete = true;
    });
    await new Promise((resolve) => setTimeout(resolve, 0));
    const before = { complete, calls, ready: document.body.dataset.lfDataVersion };
    release();
    await Promise.all([first, again]);
    stop();
    return {
      selectedBeforeNotify,
      before,
      after: document.body.dataset.lfDataVersion,
      version: next.version,
      initial,
    };
  })();
  assert.deepEqual(result.selectedBeforeNotify, { calls: 1, pending: true });
  assert.deepEqual(result.before, { complete: false, calls: 2, ready: result.initial });
  assert.equal(result.after, result.version);
});

test("data readiness does not wait for an unrelated widget region", async () => {
  await scene();
  const result = await (async () => {
    const { notifyDataSubscribers } = await import("/runtime/data.js");
    const { attachApplicationPresentation } =
      await import("/runtime/semantic-state.js");
    const unrelated = attachApplicationPresentation(
      "widget:unrelated:render",
      document.body,
    );
    const held = unrelated.present("held");
    let ready = false;
    const data = notifyDataSubscribers().then(() => {
      ready = true;
    });
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
    const beforeRelease = ready;
    held.resolve();
    await Promise.all([held.ready, data]);
    unrelated.disconnect();
    return beforeRelease;
  })();
  assert.equal(result, true);
});

test("a subscriber that fails on return reports once and draws the next reading", async (t) => {
  await scene();
  const errors = t.mock.method(console, "error", () => {});
  const result = await (async () => {
    const { watchData } = await import("/runtime/widget-api.js");
    const { acceptData, notifyDataSubscribers } = await import("/runtime/data.js");
    const { runtime } = await import("/runtime/context.js");
    const widget = document.querySelector("lf-feed");
    const at = (revision) => {
      const next = structuredClone(runtime.data);
      next.version = revision;
      next.sources.deployments.revision = revision;
      return next;
    };
    const drawn = [];
    let refuse = false;
    const stop = watchData(widget, "rows", (snapshot) => {
      drawn.push(snapshot.revision);
      if (refuse) throw new Error("return refused");
    });
    const parent = widget.parentNode;
    const next = widget.nextSibling;
    widget.remove();
    await new Promise((resolve) => setTimeout(resolve));
    acceptData(at("changed-away"), 1);
    refuse = true;
    parent.insertBefore(widget, next);
    await new Promise((resolve) => setTimeout(resolve));
    refuse = false;
    acceptData(at("after-return"), 1);
    await notifyDataSubscribers();
    stop();
    return drawn.slice(1);
  })();
  assert.deepEqual(result, ["changed-away", "after-return"]);
  assert.equal(errors.mock.callCount(), 1);
  assert.match(errors.mock.calls[0].arguments[0], /return refused/);
});

test("a projection watcher repaints for what its paint read, however it read it", async () => {
  const { watchProjection } = await import("/runtime/projection-watch.js");
  const { applicationState, readPart } = await import("/runtime/semantic-state.js");
  const host = readPart((root) => root.effective.hostAvailable);
  const revision = readPart((root) => root.document.revision);
  // Read through a helper, as a widget reads through `readWork`: the watcher is never
  // told which part it draws.
  const describe = () => (host() ? "online" : "offline");
  const settle = () => new Promise((resolve) => setTimeout(resolve));
  const owner = document.createElement("div");
  document.body.append(owner);
  const drawn = [];
  const stop = watchProjection(owner, () => drawn.push(describe()));
  await settle();
  const initial = drawn.length;
  applicationState.identify(revision() === 41 ? 42 : 41);
  await settle();
  const unread = drawn.length;
  applicationState.setHostAvailable(!host());
  await settle();
  const read = drawn.length;
  // A part that moved while the owner was away paints on its return; a return with
  // nothing moved paints nothing.
  owner.remove();
  await settle();
  applicationState.setHostAvailable(!host());
  await settle();
  document.body.append(owner);
  await settle();
  const returned = drawn.length;
  owner.remove();
  await settle();
  document.body.append(owner);
  await settle();
  const unchanged = drawn.length;
  stop();
  applicationState.setHostAvailable(!host());
  await settle();
  owner.remove();
  assert.deepEqual(
    { initial, unread, read, returned, unchanged, stopped: drawn.length },
    { initial: 1, unread: 1, read: 2, returned: 3, unchanged: 3, stopped: 3 },
  );
});
