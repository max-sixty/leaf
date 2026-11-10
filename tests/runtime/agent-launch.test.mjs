/* leaf.page answers a page with no private copy at the edge, and one whose container has
   stopped from its saved record, so the page's next write waits while its agent's
   container launches. The tab reads which from the answer it last admitted. */
import assert from "node:assert/strict";
import test from "node:test";

const { admitResponse, writeLaunchesAgent } = await import("/runtime/layer-client.js");

/** @param {Record<string, string>} headers */
const answer = (headers) => admitResponse(new Response(null, { headers }));

test("a write launches the agent after a passive or saved answer, not a live one", () => {
  assert.equal(writeLaunchesAgent(), false);
  answer({ "Leaf-Session": "passive" });
  assert.equal(writeLaunchesAgent(), true);
  answer({ "Leaf-Session": "active" });
  assert.equal(writeLaunchesAgent(), false);
  answer({ "Leaf-Session": "active", "Leaf-State-Source": "durable" });
  assert.equal(writeLaunchesAgent(), true);
});
