/* A refusal from a server that can't take a request yet carries the wait the server
   names, for the caller to send it again after (`requestJson`, layer-client.js).
   leaf.page's edge answers so while a deploy rolls a visitor's container onto the new
   release. The request itself is sent once: the server may already have run it. */
import assert from "node:assert/strict";
import test from "node:test";

const canonical = document.createElement("link");
canonical.rel = "canonical";
canonical.dataset.lfRuntime = "";
canonical.href = "https://leaf.test/";
document.head.append(canonical);
// A canonical page also posts diagnostic interactions outside the tested request.
globalThis.fetch = async () => new Response(null, { status: 204 });
const { RequestError, requestJson } = await import("/runtime/layer-client.js");

const sample = () =>
  requestJson("https://leaf.test/api/samples", { method: "POST" }, "sample");

test("a 503 naming Retry-After fails once, carrying the wait", async (t) => {
  for (const [headers, retryAfter] of [
    [{ "Retry-After": "5" }, 5000],
    [{}, undefined],
  ]) {
    const fetch = t.mock.method(
      globalThis,
      "fetch",
      async () =>
        new Response("this release is still starting", { status: 503, headers }),
    );
    await assert.rejects(
      sample(),
      (error) =>
        error instanceof RequestError &&
        error.status === 503 &&
        error.retryAfter === retryAfter,
    );
    assert.equal(fetch.mock.callCount(), 1);
    fetch.mock.restore();
  }
});
