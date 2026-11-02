/* A gesture's post asks the browser to carry it past the page that sends it
   (`keepalive`), so an edit recorded as the tab closes can still reach the log. A body
   the browser would refuse that for, at 64 KiB, goes out as an ordinary request, which
   still gets through while the page stays; the limit counts bytes, not characters. */
import assert from "node:assert/strict";
import test from "node:test";

const canonical = document.createElement("link");
canonical.rel = "canonical";
canonical.dataset.lfRuntime = "";
canonical.href = "https://leaf.test/";
document.head.append(canonical);
/** @type {RequestInit[]} */
const sent = [];
// The log's door answers every post; only the events' requests are read here.
globalThis.fetch = async (url, init) => {
  if (String(url).endsWith("/api/event")) sent.push(init);
  return new Response(null, { status: 204 });
};
const { postEvent, revealLayer } = await import("/runtime/layer-client.js");
revealLayer();

test("a gesture's post asks to outlive its page unless it is too long to", async () => {
  /** @param {string} text */
  const comment = (text) => ({ kind: "comment", attempt: "a1", text });
  await postEvent(comment("The corners are too round"));
  // 35,000 characters, 70,000 bytes.
  await postEvent(comment("é".repeat(35_000)));
  assert.deepEqual(
    sent.map((init) => init.keepalive),
    [true, false],
  );
});
