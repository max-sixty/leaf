/* The host transport stands in for an authenticated upstream. The browser only
   names its grant and path, with no credential or configurable request method. */
import assert from "node:assert/strict";
import test from "node:test";

const canonical = document.createElement("link");
canonical.rel = "canonical";
canonical.dataset.lfRuntime = "";
canonical.href = "https://leaf.test/pages/feed/";
document.head.append(canonical);
globalThis.fetch = async () => new Response(null, { status: 204 });
const { connection } = await import("/runtime/http-api.js");
const { applicationState } = await import("/runtime/semantic-state.js");

test("a connection returns the host response without publishing or retrying", async (t) => {
  applicationState.identify(1, null, true);
  const before = applicationState.read();
  const answer = {
    status: 200,
    headers: { "content-type": "application/json" },
    body: '{"ok":true}',
  };
  const fetch = t.mock.method(globalThis, "fetch", async (url, init) => {
    assert.ok(String(url).endsWith("/api/connections/example"));
    assert.equal(init.method, "POST");
    assert.deepEqual(JSON.parse(init.body), { path: "/items?page=2" });
    return new Response(JSON.stringify(answer));
  });
  assert.deepEqual(await connection("example").fetch("/items?page=2"), answer);
  assert.equal(applicationState.read(), before);
  assert.equal(fetch.mock.callCount(), 1);
  fetch.mock.mockImplementation(
    async () =>
      new Response('{"error":"Grant exhausted"}', {
        status: 429,
        headers: { "Content-Type": "application/json" },
      }),
  );
  await assert.rejects(connection("example").fetch("/items"), /Grant exhausted/);
  assert.equal(fetch.mock.callCount(), 2);
});

test("captured documents cannot use host connections", async (t) => {
  applicationState.identify(1, null, false);
  const fetch = t.mock.method(globalThis, "fetch", async () => {
    throw new Error("Unexpected network access");
  });
  await assert.rejects(connection("example").fetch("/items"), /live pages/);
  assert.equal(fetch.mock.callCount(), 0);
});
