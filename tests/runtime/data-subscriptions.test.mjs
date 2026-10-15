/* Data delivery and projection lifetime rules do not depend on Chrome layout.
   Native editing, syntax rendering, and reports reaching the page log stay in the
   browser journeys; these cases exercise the publisher and its real DOM owners. */
import assert from "node:assert/strict";
import test from "node:test";
import { adoptRegistry } from "/runtime/registry.js";
import { acceptData, notifyDataSubscribers } from "/runtime/data.js";
import { LeafElement, nothing } from "/runtime/widget-api.js";

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

// A widget bound to the deployments source, as the scene's <lf-feed> is, drawing each
// delivery through `draw(snapshot)`; a promise it returns is the draw's drawing.
let feeds = 0;
async function feed(
  draw,
  bind = (element) => element.setAttribute("source", "deployments"),
) {
  const tag = `lf-feed-${++feeds}`;
  adoptRegistry({
    [tag]: { "x-data": { rows: { source: "source", contract: "rows" } } },
    $data: { contracts: { rows: { records: { items: "", key: "key" } } } },
  });
  customElements.define(
    tag,
    class extends LeafElement {
      render() {
        this.snapshot = this.data("rows");
        return nothing;
      }
      updated(changed) {
        super.updated(changed);
        const work = draw(this.snapshot);
        if (work) this.drawing(work);
      }
    },
  );
  const element = document.createElement(tag);
  element.id = "deployments";
  bind(element);
  document.querySelector("main").append(element);
  await new Promise((resolve) => setTimeout(resolve, 0));
  await element.updateComplete;
  return element;
}

test("a widget reads its own binding, captured at its first read", async () => {
  await scene();
  const { runtime } = await import("/runtime/context.js");
  const current = [];
  const bound = await feed((snapshot) => current.push(snapshot?.revision ?? null));
  bound.remove();
  const absent = [];
  const elsewhere = await feed(
    (snapshot) => absent.push(snapshot),
    (element) => element.setAttribute("source", "constructor"),
  );
  // A live attribute change does not rebind what the element reads.
  elsewhere.setAttribute("source", "deployments");
  const next = structuredClone(runtime.data);
  next.version = "next-version";
  next.sources.deployments.revision = "next-revision";
  acceptData(next, 1);
  await notifyDataSubscribers();
  elsewhere.remove();
  const unbound = [];
  const loose = await feed(
    (snapshot) => unbound.push(snapshot),
    () => {},
  );
  loose.remove();
  assert.deepEqual(current, ["initial-revision"]);
  assert.deepEqual(absent, [null]);
  assert.deepEqual(unbound, [null]);
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
    // The time it shows aged while it was away, so its return paints it at once.
    resumed: 4,
    ticked: 4,
    refreshed: 5,
    stopped: 5,
  });
});

test("a superseded async data render cannot stamp the newer version", async () => {
  await scene();
  const result = await (async () => {
    const { acceptData, notifyDataSubscribers } = await import("/runtime/data.js");
    const { runtime } = await import("/runtime/context.js");
    const taken = 1;
    const releases = new Map();
    const widget = await feed((snapshot) => {
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
    widget.remove();
    return { before, afterOlder, afterNewer };
  })();
  assert.equal(result.afterOlder, result.before);
  assert.equal(result.afterNewer, "newer");
});

test("an unchanged source waits for its inflight drawing", async () => {
  await scene();
  const { runtime } = await import("/runtime/context.js");
  let release;
  let calls = 0;
  const widget = await feed(() => {
    if (++calls > 1)
      return new Promise((resolve) => {
        release = resolve;
      });
  });
  const initial = document.body.dataset.lfDataVersion;
  const next = structuredClone(runtime.data);
  next.version = "next-version";
  next.sources.deployments.revision = "next-revision";
  acceptData(next, 1);
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
  widget.remove();
  assert.deepEqual(before, { complete: false, calls: 2, ready: initial });
  assert.equal(document.body.dataset.lfDataVersion, next.version);
});

test("a departure that cuts a drawing short owes it again; a finished one stands", async () => {
  await scene();
  const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
  const leaveAndReturn = async (widget) => {
    const main = widget.parentNode;
    widget.remove();
    await settle();
    main.append(widget);
    await settle();
    await widget.updateComplete;
  };
  let draws = 0;
  let finish;
  const finished = new Promise((resolve) => (finish = resolve));
  const widget = await feed(() => {
    draws += 1;
    return finished;
  });
  await leaveAndReturn(widget);
  const interrupted = draws;
  finish();
  await finished;
  await settle();
  await leaveAndReturn(widget);
  widget.remove();
  // A newer update that draws at once replaces a drawing still pending.
  let superseding = 0;
  const superseded = await feed(() => {
    superseding += 1;
    if (superseding === 1) return new Promise(() => {});
  });
  superseded.requestUpdate();
  await superseded.updateComplete;
  await leaveAndReturn(superseded);
  superseded.remove();
  assert.deepEqual(
    { interrupted, kept: draws, superseded: superseding },
    { interrupted: 2, kept: 2, superseded: 2 },
  );
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

test("a projection watcher repaints for a part its own paint published after reading it", async () => {
  const { watchProjection } = await import("/runtime/projection-watch.js");
  const { applicationState, readPart } = await import("/runtime/semantic-state.js");
  const host = readPart((root) => root.effective.hostAvailable);
  const owner = document.createElement("div");
  document.body.append(owner);
  const drawn = [];
  const stop = watchProjection(owner, () => {
    drawn.push(host());
    if (drawn.length === 1) applicationState.setHostAvailable(!host());
  });
  await new Promise((resolve) => setTimeout(resolve));
  stop();
  owner.remove();
  assert.deepEqual(drawn, [drawn[0], !drawn[0]]);
});

test("a projection watcher repaints for an outside reading its own paint moved", async () => {
  const { watchProjection } = await import("/runtime/projection-watch.js");
  const { outsideReading } = await import("/vendor/browser-runtime.js");
  let value = false;
  const heard = new Set();
  const flag = outsideReading(
    () => value,
    (moved) => {
      heard.add(moved);
      return () => heard.delete(moved);
    },
  );
  const owner = document.createElement("div");
  document.body.append(owner);
  const drawn = [];
  const stop = watchProjection(owner, () => {
    drawn.push(flag.read());
    if (drawn.length === 1) {
      value = true;
      for (const moved of [...heard]) moved({});
    }
  });
  await new Promise((resolve) => setTimeout(resolve));
  stop();
  owner.remove();
  assert.deepEqual(drawn, [false, true]);
});

test("a projection watcher's paint that reads the whole publication fails", async (t) => {
  // Every publication moves the root, so such a paint would repaint on all of them.
  await scene();
  const errors = t.mock.method(console, "error", () => {});
  const { watchProjection } = await import("/runtime/projection-watch.js");
  const { readApplication } = await import("/runtime/semantic-state.js");
  const owner = document.createElement("div");
  document.body.append(owner);
  const stop = watchProjection(owner, () => readApplication().phase);
  await new Promise((resolve) => setTimeout(resolve));
  stop();
  owner.remove();
  assert.equal(errors.mock.callCount(), 1);
  assert.match(errors.mock.calls[0].arguments[0], /whole publication/);
});
