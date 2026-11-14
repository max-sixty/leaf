/* Returning catches up before protecting the resumed reading.

   Transport answers and the feed's injected presentation boundary are controlled,
   while the real semantic publisher and continuity owner supply their readings.
   Holding preparation or painting makes request interleavings deterministic. */
import assert from "node:assert/strict";
import { setImmediate } from "node:timers/promises";
import test from "node:test";
import { applicationState } from "/runtime/semantic-state.js";
import { servedState } from "../served.mjs";

const canonical = document.createElement("link");
canonical.rel = "canonical";
canonical.dataset.lfRuntime = "";
canonical.href = "https://leaf.test/";
document.head.append(canonical);
const { beginRead, createStateFeed } = await import("/runtime/state-feed.js");
const { readingIsContinuous, readingReturn, completeReadingReturn } =
  await import("/runtime/reading-continuity.js");
const { runtime } = await import("/runtime/context.js");
// The feed's answers are adopted into one identified document.
applicationState.identify(1);
applicationState.captureDocument({
  ...applicationState.read().document,
  registry: {},
  authored: new Map(),
  descriptors: new Map(),
});

let taken = 0;
const state = (reading) => servedState({ taken: ++taken, reading });

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
        stateApplying: () => applying,
        stateInHand: () => runtime.state,
        invalidateDom: async () => {},
        receiveState,
        prepareActivation: async () => null,
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
        assert.equal(applicationState.read().reach.reach, "broken");
        return;
      }
      if (mode !== "painting") news = "second";
      looks.at(-1)();
      await setImmediate();
      assert.equal(reads, mode === "painting" ? 1 : 2);
      // A read that brings nothing says so to whatever reads the server's reach.
      if (mode === "offline")
        assert.equal(applicationState.read().reach.reach, "unreachable");
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

test("the page asks for no reading it already has in hand", async (t) => {
  t.after(() => window.happyDOM.cancelAsync());
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
  let clock;
  t.mock.method(globalThis, "setTimeout", (callback, delay) => {
    if (delay === 250) looks.push(callback);
    return 1;
  });
  t.mock.method(globalThis, "clearTimeout", () => {});
  t.mock.method(globalThis, "setInterval", (callback, delay) => {
    if (delay === 2000) clock = callback;
    return 1;
  });
  let news = "initial";
  const answers = [];
  let answering = null;
  t.mock.method(globalThis, "fetch", async (url) => {
    const path = new URL(url).pathname;
    if (path === "/api/news") return new Response(news);
    assert.equal(path, "/api/state", `unexpected feed request: ${url}`);
    await answering?.promise;
    return Response.json(state(answers.shift()));
  });
  const reads = () =>
    globalThis.fetch.mock.calls.filter(
      (call) => new URL(call.arguments[0]).pathname === "/api/state",
    ).length;
  // An answer is prepared before the page adopts it, which is when `runtime.reading`
  // names it; until then the answer is in hand, as `state-application.js` keeps it.
  const preparing = new Map();
  let inHand = null;
  const receiveState = async (answer) => {
    inHand = answer;
    await preparing.get(answer.reading)?.promise;
    applicationState.adopt(answer);
    if (inHand === answer) inHand = null;
  };
  const prepare = (reading) => {
    preparing.set(reading, Promise.withResolvers());
    return () => preparing.get(reading).resolve();
  };
  createStateFeed({
    stateApplying: () => false,
    stateInHand: () => inHand ?? runtime.state,
    invalidateDom: async () => {},
    receiveState,
    prepareActivation: async () => null,
  }).startFeed(async () => {}, Promise.resolve({ state: state("initial") }));
  await setImmediate();
  assert.equal(reads(), 0);

  // A saved revision: the look asks once, and neither the clock nor the next look
  // asks again while its answer is prepared.
  const revised = prepare("revised");
  news = "revised";
  answers.push("revised");
  looks.at(-1)();
  await setImmediate();
  assert.equal(reads(), 1);
  clock();
  looks.at(-1)();
  await setImmediate();
  assert.equal(reads(), 1, "the page asked again for the revision being prepared");
  revised();
  await setImmediate();

  // A gesture's POST answer arrives outside the feed, and the news names it.
  const posted = prepare("posted");
  const applying = receiveState(state("posted"));
  news = "posted";
  clock();
  looks.at(-1)();
  await setImmediate();
  clock();
  await setImmediate();
  assert.equal(reads(), 1, "the page asked again for the gesture's own answer");
  posted();
  await applying;

  // A read that crossed a short-lived lease named a reading the news never did.
  answers.push("crossed", "leased");
  news = "leased";
  looks.at(-1)();
  await setImmediate();
  assert.equal(reads(), 2);
  looks.at(-1)();
  await setImmediate();
  clock();
  await setImmediate();
  assert.equal(reads(), 3, "the clock left a crossed reading standing");

  // A read still out when the next save lands can wait out its activation and answer
  // with the newer revision, which the look heard of meanwhile.
  answering = Promise.withResolvers();
  answers.push("saved again");
  news = "saved";
  looks.at(-1)();
  await setImmediate();
  assert.equal(reads(), 4);
  news = "saved again";
  looks.at(-1)();
  await setImmediate();
  answering.resolve();
  await setImmediate();
  await setImmediate();
  assert.equal(
    reads(),
    4,
    "the page read again for the revision its read answered with",
  );

  // An activity transition that comes due asks once, and the answer in hand settles it.
  const due = new Date(Date.now() - 60_000).toISOString();
  applicationState.adopt(
    servedState({
      taken: ++taken,
      reading: "due",
      activity: { next_transition_at: due },
    }),
  );
  news = "due";
  looks.at(-1)();
  await setImmediate();
  const aged = prepare("aged");
  answers.push("aged");
  clock();
  await setImmediate();
  assert.equal(reads(), 5);
  clock();
  await setImmediate();
  assert.equal(reads(), 5, "the clock read again for a transition its answer settles");
  aged();
  await setImmediate();
});

test("a read waits while the news answers and ends when a look does not", async (t) => {
  t.after(() => window.happyDOM.cancelAsync());
  const listeners = [];
  const add = document.addEventListener.bind(document);
  t.mock.method(document, "addEventListener", (name, listener, options) => {
    listeners.push([name, listener, options]);
    add(name, listener, options);
  });
  t.after(() => {
    for (const args of listeners) document.removeEventListener(...args);
  });
  // Only the looks end a read here: no bound comes due on its own.
  t.mock.method(globalThis.AbortSignal, "timeout", () => new AbortController().signal);
  const looks = [];
  t.mock.method(globalThis, "setTimeout", (callback, delay) => {
    if (delay === 250) looks.push(callback);
    return 1;
  });
  t.mock.method(globalThis, "clearTimeout", () => {});
  t.mock.method(globalThis, "setInterval", () => 1);
  let news = "initial";
  let answering = true;
  t.mock.method(globalThis, "fetch", async (url, init) => {
    const path = new URL(url).pathname;
    if (path === "/api/news") {
      if (!answering) throw new TypeError("Failed to fetch");
      return new Response(news);
    }
    assert.equal(path, "/api/state", `unexpected feed request: ${url}`);
    // A server still working on the answer, which only the page can end.
    return new Promise((_, reject) =>
      init.signal.addEventListener("abort", () => reject(init.signal.reason)),
    );
  });
  createStateFeed({
    stateApplying: () => false,
    stateInHand: () => runtime.state,
    invalidateDom: async () => {},
    receiveState: async (answer) => applicationState.adopt(answer),
    prepareActivation: async () => null,
  }).startFeed(async () => {}, Promise.resolve({ state: state("initial") }));
  await setImmediate();
  news = "moved";
  looks.at(-1)();
  await setImmediate();
  looks.at(-1)();
  await setImmediate();
  assert.equal(applicationState.read().reach.reach, "reached");
  answering = false;
  looks.at(-1)();
  await setImmediate();
  assert.equal(applicationState.read().reach.reach, "unreachable");
});

test("a matching response completes from its held data after a newer admission", async (t) => {
  const held = {
    version: "initial",
    sources: { builds: { contract: "c", value: "old" } },
  };
  const newer = {
    version: "new",
    sources: { builds: { contract: "c", value: "new" } },
  };
  const { acceptData } = await import("/runtime/data.js");
  applicationState.acceptData(held, ++taken);
  t.mock.method(globalThis.AbortSignal, "timeout", () => new AbortController().signal);
  const response = Promise.withResolvers();
  const earlier = state("initial-response");
  t.mock.method(globalThis, "fetch", async (url, init) => {
    assert.equal(new Headers(init.headers).get("Leaf-Data-Version"), "initial");
    return response.promise;
  });
  const reading = beginRead();
  acceptData(newer, ++taken);
  response.resolve(Response.json({ ...earlier, data: { version: "initial" } }));
  const { state: answer } = await reading;
  assert.deepEqual(answer.data, held);
  assert.equal(acceptData(answer.data, answer.taken), false);
  assert.deepEqual(runtime.data, newer);
});

test("a read keeps the data it named when the answer leaves its sources out", async (t) => {
  const held = {
    version: "v1",
    sources: { builds: { contract: "c", value: "green" } },
  };
  applicationState.acceptData(held, ++taken);
  // The read's bound would otherwise hold the test open for two minutes.
  t.mock.method(globalThis.AbortSignal, "timeout", () => new AbortController().signal);
  t.mock.method(globalThis, "fetch", async (url, init) => {
    assert.equal(new URL(url).pathname, "/api/state");
    assert.equal(new Headers(init.headers).get("Leaf-Data-Version"), "v1");
    return Response.json({ ...state("unmoved"), data: { version: "v1" } });
  });
  const { state: answer } = await beginRead();
  assert.deepEqual(answer.data, held);
});

test("a live server's error is its fault, while a gateway with nothing behind it is no answer", async (t) => {
  t.mock.method(globalThis.AbortSignal, "timeout", () => new AbortController().signal);
  let answer;
  t.mock.method(globalThis, "fetch", async () => answer);
  answer = Response.json({ error: "projection failed" }, { status: 500 });
  assert.deepEqual(await beginRead(), { state: null, fault: "projection failed" });
  answer = new Response("<h1>oops</h1>", { status: 500 });
  assert.deepEqual(await beginRead(), { state: null, fault: "HTTP 500" });
  for (const status of [401, 502, 503, 504]) {
    answer = new Response("", { status });
    assert.deepEqual(await beginRead(), { state: null, fault: null }, `HTTP ${status}`);
  }
});

test("a state body lost in transit is no answer, while malformed JSON remains a fault", async (t) => {
  t.mock.method(globalThis.AbortSignal, "timeout", () => new AbortController().signal);
  let answer = new Response(
    new globalThis.ReadableStream({
      start(controller) {
        controller.error(new TypeError("Failed to fetch"));
      },
    }),
  );
  t.mock.method(globalThis, "fetch", async () => answer);
  assert.deepEqual(await beginRead(), { state: null, fault: null });
  answer = new Response("{");
  const result = await beginRead();
  assert.ok(result.error instanceof SyntaxError);
});
