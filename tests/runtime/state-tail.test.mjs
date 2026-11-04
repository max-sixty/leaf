/* A state answer that carries the changes since the reading a tab holds completes to
   the whole answer, and keeps every part the changes leave alone as the very object
   the held reading had.

   The server writes each case (`served_records.py`, `tail_cases`): the reading the tab
   held, the answer to a request naming it, and the whole answer at the same position,
   so the completion is held to what the server would have sent rather than to a
   fixture's idea of it. */
import assert from "node:assert/strict";
import test from "node:test";
import { isDeepStrictEqual } from "node:util";
import { servedTails } from "../served.mjs";

const canonical = document.createElement("link");
canonical.rel = "canonical";
canonical.dataset.lfRuntime = "";
canonical.href = "https://leaf.test/";
document.head.append(canonical);
// Nothing here is sent; the page's background requests are answered and dropped.
globalThis.fetch = async () => new Response(null, { status: 204 });
const { completeState, heldHeaders } = await import("/runtime/layer-client.js");

// Every object of `done` equal to the one at its place in `held` is that object, and
// every item of a list equal to an item the held list had is that item: the readers
// after completion compare by identity, so a copy would read as a change.
/** @param {unknown} held @param {unknown} done @param {string} path */
function assertKept(held, done, path) {
  if (!held || !done || typeof held !== "object" || typeof done !== "object") return;
  if (isDeepStrictEqual(held, done)) {
    assert.equal(done, held, `${path} was copied`);
    return;
  }
  if (Array.isArray(held) && Array.isArray(done)) {
    for (const item of done)
      if (held.some((each) => isDeepStrictEqual(each, item)))
        assert.ok(held.includes(item), `an item of ${path} was copied`);
    return;
  }
  for (const [key, value] of Object.entries(done))
    if (Object.hasOwn(held, key))
      assertKept(
        /** @type {Record<string, unknown>} */ (held)[key],
        value,
        `${path}.${key}`,
      );
}

for (const { name, held, tail, whole } of servedTails())
  test(`an answer completes the held reading to the whole answer: ${name}`, () => {
    const holding = { data: held.data, state: held };
    assert.equal(
      heldHeaders(holding)["Leaf-Held-Basis"],
      held.browser.basis.key,
      "the request names the reading the tab holds",
    );
    const done = completeState(tail, holding);
    assert.deepEqual(done, whole);
    // The log and the data keep their own mechanisms.
    const { events: _events, data: _data, ...rest } = done;
    assertKept(held, rest, "the answer");
  });

test("an answer extending a reading the tab did not name is a fault", () => {
  const [{ held, tail }, other] = servedTails();
  assert.throws(
    () => completeState(tail, { data: held.data, state: other.held }),
    /extends a reading this tab did not name/,
  );
});
