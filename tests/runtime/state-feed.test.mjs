/* Returning catches up before protecting the resumed reading.

   Transport answers and the feed's injected presentation boundary are controlled,
   while the real semantic publisher and continuity owner supply their readings.
   Holding preparation or painting makes request interleavings deterministic. */
import assert from "node:assert/strict";
import { setImmediate } from "node:timers/promises";
import test from "node:test";
import { applicationState } from "/runtime/semantic-state.js";

const canonical = document.createElement("link");
canonical.rel = "canonical";
canonical.dataset.lfRuntime = "";
canonical.href = "https://leaf.test/";
document.head.append(canonical);
const { createStateFeed } = await import("/runtime/state-feed.js");
const { readingIsContinuous, readingReturn, completeReadingReturn } =
  await import("/runtime/reading-continuity.js");

let taken = 0;
const emptyProjection = () => ({ entries: [], actions: [], reports: [], desired: [] });
const noAsks = () => ({ all: [], user: [], unanswered: [] });
const state = (reading) => ({
  taken: ++taken,
  reading,
  layer: { generation: "test" },
  active: { revision: 1 },
  events: [],
  workflows: [],
  activity: null,
  browser: {
    basis: { through_seq: 0 },
    receipts: [],
    thread: { threads: [], projection: emptyProjection(), asks: noAsks() },
    views: {
      1: {
        basis: { revision: 1, through_seq: 0 },
        coverage: [],
        undo: [],
        document: { asks: noAsks(), projection: emptyProjection() },
      },
    },
  },
});

test("an earlier return cannot close a later absence", (t) => {
  let visible = "visible";
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    get: () => visible,
  });
  t.after(() => delete document.visibilityState);
  const visibility = (value) => {
    visible = value;
    document.dispatchEvent(new Event("visibilitychange"));
  };
  completeReadingReturn(readingReturn());
  visibility("hidden");
  const earlier = readingReturn();
  visibility("visible");
  visibility("hidden");
  const current = readingReturn();
  completeReadingReturn(current);
  assert.equal(readingIsContinuous(), false);
  visibility("visible");
  completeReadingReturn(earlier);
  assert.equal(readingIsContinuous(), false);
  completeReadingReturn(current);
  assert.equal(readingIsContinuous(), true);
});

test("a return stays interrupted until its refreshed reading is actually presented", async (t) => {
  t.after(() => window.happyDOM.cancelAsync());
  applicationState.identify(1);
  applicationState.captureDocument({
    ...applicationState.read().document,
    registry: {},
    authored: new Map(),
    descriptors: new Map(),
  });
  for (const mode of ["painting", "overtaken", "offline", "rejected"]) {
    await t.test(mode, async (t) => {
      let visible = "visible";
      Object.defineProperty(document, "visibilityState", {
        configurable: true,
        get: () => visible,
      });
      t.after(() => delete document.visibilityState);
      const visibility = (value) => {
        visible = value;
        document.dispatchEvent(new Event("visibilitychange"));
      };
      completeReadingReturn(readingReturn());
      const listeners = [];
      const add = document.addEventListener.bind(document);
      t.mock.method(document, "addEventListener", (name, listener, options) => {
        listeners.push([name, listener, options]);
        add(name, listener, options);
      });
      t.after(() => {
        for (const args of listeners) document.removeEventListener(...args);
      });
      const looks = [];
      t.mock.method(globalThis, "setTimeout", (callback, delay) => {
        if (delay === 250) looks.push(callback);
        return 1;
      });
      t.mock.method(globalThis, "clearTimeout", () => {});
      t.mock.method(globalThis, "setInterval", () => 1);
      t.mock.method(console, "error", () => {});

      let news = "initial";
      let reads = 0;
      t.mock.method(globalThis, "fetch", async (url) => {
        const path = new URL(url).pathname;
        if (path === "/api/news") return new Response(news);
        // The diagnostic stream may flush while this reading is held. Its POST,
        // and a reported presentation fault, are not state reads.
        if (path === "/api/interaction") return new Response(null, { status: 204 });
        if (path === "/api/event") return Response.json({ ok: true });
        assert.equal(path, "/api/state", `unexpected feed request: ${url}`);
        reads += 1;
        if (mode === "offline" && reads === 2) throw new Error("network absent");
        return Response.json(state(reads === 1 ? "first" : "second"));
      });

      let applying = false;
      const preparation = Promise.withResolvers();
      const paint = Promise.withResolvers();
      const painted = [];
      const statuses = [];
      const receiveState = async (answer) => {
        if (answer.reading === "initial") {
          applicationState.adopt(answer);
          return;
        }
        if (mode === "rejected") throw new Error("state presentation failed");
        if (mode === "overtaken" && answer.reading === "first") {
          await preparation.promise;
          assert.equal(applicationState.overtaken(answer), true);
          return;
        }
        applicationState.adopt(answer);
        applying = true;
        await paint.promise;
        painted.push(readingIsContinuous());
        applying = false;
      };
      const feed = createStateFeed({
        projectionDeferred: () => false,
        retryProjection: () => false,
        stateApplying: () => applying,
        releasePending: async () => {},
        invalidateDom: async () => {},
        receiveState,
        prepareActivation: async () => null,
        notifyDataSubscribers: async () => {},
        renderStatus: (status) => statuses.push(status),
      });
      feed.startFeed(async () => {}, Promise.resolve({ state: state("initial") }));
      await setImmediate();
      visibility("hidden");
      news = "first";
      visibility("visible");
      await setImmediate();
      assert.equal(reads, 1);
      assert.equal(readingIsContinuous(), false);

      if (mode === "rejected") {
        assert.equal(statuses.at(-1)?.message, "state presentation failed");
        return;
      }
      if (mode !== "painting") news = "second";
      looks.at(-1)();
      await setImmediate();
      assert.equal(reads, mode === "painting" ? 1 : 2);
      if (mode === "overtaken") {
        preparation.resolve();
        await setImmediate();
      }
      assert.equal(readingIsContinuous(), false);
      paint.resolve();
      await setImmediate();
      assert.deepEqual(painted, [false]);
      assert.equal(readingIsContinuous(), true);
    });
  }
});
