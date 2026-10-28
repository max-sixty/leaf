/* Generation sends once to this page's server. The network boundary stands in
   for the harness-backed server; browser failures must not resend. */
import assert from "node:assert/strict";
import test from "node:test";

const canonical = document.createElement("link");
canonical.rel = "canonical";
canonical.dataset.lfRuntime = "";
canonical.href = "https://leaf.test/pages/feed/";
document.head.append(canonical);
// A canonical page also posts diagnostic interactions outside the tested request.
globalThis.fetch = async () => new Response(null, { status: 204 });
const { generate } = await import("/runtime/llm-api.js");
const { applicationState } = await import("/runtime/semantic-state.js");

test("generation returns the host answer at the page's address without publishing state", async (t) => {
  applicationState.identify(1, null, true);
  const before = applicationState.read();
  const request = {
    input: "Story",
    schema: { type: "object", properties: {}, additionalProperties: false },
  };
  const answer = {
    value: { headline: "A story" },
    model: "host-model",
    usage: { inputTokens: 10, outputTokens: 5 },
    durationMs: 123,
  };
  const fetch = t.mock.method(globalThis, "fetch", async (url, init) => {
    assert.equal(url, "https://leaf.test/pages/feed/api/llm");
    assert.equal(init.method, "POST");
    assert.deepEqual(JSON.parse(init.body), request);
    return new Response(JSON.stringify(answer));
  });
  assert.deepEqual(await generate(request), answer);
  assert.equal(fetch.mock.callCount(), 1);
  assert.equal(applicationState.read(), before);
});

test("a failed generation surfaces the server error and never retries", async (t) => {
  applicationState.identify(1, null, true);
  const fetch = t.mock.method(
    globalThis,
    "fetch",
    async () =>
      new Response(JSON.stringify({ error: "Provider refused the request" }), {
        status: 502,
        headers: { "Content-Type": "application/json" },
      }),
  );
  await assert.rejects(
    generate({
      input: "Story",
      schema: { type: "object", properties: {}, additionalProperties: false },
    }),
    {
      message: "Provider refused the request",
      status: 502,
    },
  );
  assert.equal(fetch.mock.callCount(), 1);
});

test("a captured document cannot start generation", async (t) => {
  applicationState.identify(1, null, false);
  const fetch = t.mock.method(globalThis, "fetch", async () => {
    throw new Error("Unexpected request");
  });
  await assert.rejects(generate({ input: "Story" }), /available in live pages/);
  assert.equal(fetch.mock.callCount(), 0);
});
