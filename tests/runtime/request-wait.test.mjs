/* A request the server can't take yet goes again after the wait the server names, for
   as long as its caller's patience lasts, telling the caller as each wait begins
   (`requestJson`, layer-client.js). leaf.page's edge answers so while a deploy rolls a
   visitor's container onto the new release. */
import assert from "node:assert/strict";
import test from "node:test";
import { setImmediate as settled } from "node:timers/promises";

const canonical = document.createElement("link");
canonical.rel = "canonical";
canonical.dataset.lfRuntime = "";
canonical.href = "https://leaf.test/";
document.head.append(canonical);
// A canonical page also posts diagnostic interactions outside the tested request.
globalThis.fetch = async () => new Response(null, { status: 204 });
const { RequestError, requestJson } = await import("/runtime/layer-client.js");

// The edge's answer while the visitor's container is on the previous release.
const notYet = () =>
  new Response("this release is still starting", {
    status: 503,
    headers: { "Retry-After": "60" },
  });
const sample = (notYet) =>
  requestJson("https://leaf.test/api/samples", { method: "POST" }, "sample", notYet);

test("a request waits as the server asks and returns the answer that comes", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout", "Date"] });
  const fetch = t.mock.method(globalThis, "fetch", async () => notYet());
  const waiting = t.mock.fn();
  const answer = sample({ patience: 10 * 60_000, waiting });
  await settled();
  assert.equal(waiting.mock.callCount(), 1);
  t.mock.timers.tick(59_999);
  await settled();
  assert.equal(fetch.mock.callCount(), 1);
  fetch.mock.mockImplementation(
    async () => new Response(JSON.stringify({ url: "/api/samples/s1/" })),
  );
  t.mock.timers.tick(1);
  assert.deepEqual(await answer, { url: "/api/samples/s1/" });
  assert.equal(fetch.mock.callCount(), 2);
  assert.equal(waiting.mock.callCount(), 1);
});

test("a request fails as the 503 once the next wait would outlast its patience", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout", "Date"] });
  const fetch = t.mock.method(globalThis, "fetch", async () => notYet());
  const refused = (error) => error instanceof RequestError && error.status === 503;
  // A caller that names no patience sends once.
  await assert.rejects(sample(), refused);
  assert.equal(fetch.mock.callCount(), 1);

  const answer = sample({ patience: 150_000 });
  await settled();
  t.mock.timers.tick(60_000);
  await settled();
  t.mock.timers.tick(60_000);
  await assert.rejects(answer, refused);
  // Asked at 0, 60 and 120 s; a third wait would end at 180 s.
  assert.equal(fetch.mock.callCount(), 4);
});
