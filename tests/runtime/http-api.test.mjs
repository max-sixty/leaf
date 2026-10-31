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

test("file conflicts use the public RequestError constructor and retain the server snapshot", async (t) => {
  const { boundFile, RequestError } = await import("/runtime/widget-api.js");
  applicationState.identify(1, null, true);
  const current = { label: "Notes", text: "new disk text", revision: "disk-revision" };
  const body = JSON.stringify({ error: "Changed on disk", current });
  t.mock.method(
    globalThis,
    "fetch",
    async () =>
      new Response(body, {
        status: 409,
        headers: { "Content-Type": "application/json" },
      }),
  );
  await assert.rejects(
    boundFile("notes").save({ revision: "old-revision", text: "draft" }),
    (error) => {
      assert.ok(error instanceof RequestError);
      assert.equal(error.status, 409);
      assert.equal(error.body, body);
      assert.equal(error.said, "Changed on disk");
      assert.deepEqual(error.current, current);
      return true;
    },
  );
});

test("a file request without an answer retains its original cause", async (t) => {
  const { boundFile } = await import("/runtime/widget-api.js");
  applicationState.identify(1, null, true);
  const fault = new TypeError("Network unavailable");
  t.mock.method(globalThis, "fetch", async () => {
    throw fault;
  });
  await assert.rejects(boundFile("notes").read(), (error) => {
    assert.equal(error.message, "The page's server did not answer.");
    assert.equal(error.cause, fault);
    return true;
  });
});
