/* A state answer that extends the reading a tab holds completes to the whole answer.

   The server writes each case (`served_records.py`, `tail_cases`): the reading the tab
   held, the answer to a request naming it, and the whole answer at the same position,
   so the completion is held to what the server would have sent rather than to a
   fixture's idea of it. */
import assert from "node:assert/strict";
import test from "node:test";
import { servedTails } from "../served.mjs";

const canonical = document.createElement("link");
canonical.rel = "canonical";
canonical.dataset.lfRuntime = "";
canonical.href = "https://leaf.test/";
document.head.append(canonical);
// Nothing here is sent; the page's background requests are answered and dropped.
globalThis.fetch = async () => new Response(null, { status: 204 });
const { completeState, heldHeaders } = await import("/runtime/layer-client.js");

for (const { name, held, tail, whole } of servedTails())
  test(`an answer completes the held reading to the whole answer: ${name}`, () => {
    const holding = { data: held.data, state: held };
    assert.equal(
      heldHeaders(holding)["Leaf-Held-Basis"],
      held.browser.basis.key,
      "the request names the reading the tab holds",
    );
    assert.deepEqual(completeState(tail, holding), whole);
  });

test("an answer extending a reading the tab did not name is a fault", () => {
  const [{ held, tail }, other] = servedTails();
  assert.throws(
    () => completeState(tail, { data: held.data, state: other.held }),
    /extends a reading this tab did not name/,
  );
});
