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
const { connection } = await import("/runtime/host/http-api.js");
const { applicationState } = await import("/runtime/state/semantic-state.js");

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

test("a refused save resolves the server's reason and the newer file it holds", async (t) => {
  const { boundFile } = await import("/runtime/widget-api.js");
  applicationState.identify(1, null, true);
  const current = { label: "Notes", text: "new disk text", revision: "disk-revision" };
  const fetch = t.mock.method(
    globalThis,
    "fetch",
    async () =>
      new Response(JSON.stringify({ error: "Changed on disk", current }), {
        status: 409,
        headers: { "Content-Type": "application/json" },
      }),
  );
  const file = boundFile("notes");
  const snapshot = { revision: "old-revision", text: "draft" };
  assert.deepEqual(await file.save(snapshot), { refused: "Changed on disk", current });
  fetch.mock.mockImplementation(
    async () =>
      new Response(JSON.stringify({ error: "The file is not writable" }), {
        status: 403,
        headers: { "Content-Type": "application/json" },
      }),
  );
  assert.deepEqual(await file.save(snapshot), {
    refused: "The file is not writable",
    current: null,
  });
  // An answer that says nothing of its own may come from a proxy, with the save
  // having reached the file.
  fetch.mock.mockImplementation(
    async () => new Response("Bad gateway", { status: 502 }),
  );
  await assert.rejects(file.save(snapshot), /HTTP 502/);
  // A fault in the server's words may come after the write, as when the host's store
  // refuses to keep it.
  fetch.mock.mockImplementation(
    async () =>
      new Response(JSON.stringify({ error: "PageStoreRefused: 503" }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }),
  );
  await assert.rejects(file.save(snapshot), /PageStoreRefused/);
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
