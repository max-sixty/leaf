import assert from "node:assert/strict";
import test from "node:test";
import { parse, render } from "../../packages/diagram/vendor/pele.esm.js";

// Pele 1.9.0's flowchart converter dropped an edge's authored classes, so page CSS could
// mark a node in theme colours but not an edge. `build/vendor.mjs` carries them
// to the edge's group and its label's group, as node classes reach `.pele-node`.
test("a flowchart edge's class reaches its drawn group and its label's", () => {
  const { svg } = render(
    parse(`flowchart LR
  A e1@-->|new| B
  B --> C
  class e1 added`),
    { responsive: false },
  );
  /** @param {string} kind */
  const groups = (kind) =>
    [...svg.matchAll(/<g class="([^"]*)" data-id="([^"]+)"/g)]
      .filter(([, classes]) => classes.split(" ")[0] === kind)
      .map(([, classes, id]) => [id, classes]);
  assert.deepEqual(groups("pele-edge"), [
    ["e1", "pele-edge added"],
    ["L_B_C_0", "pele-edge"],
  ]);
  assert.deepEqual(groups("pele-edge-label"), [["e1", "pele-edge-label added"]]);
});
