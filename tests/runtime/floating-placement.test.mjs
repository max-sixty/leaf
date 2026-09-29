/* A floating box's placement: an answer computed for a placement a later one superseded
   writes nothing, so the later placement's plane and way of standing hold. */

import assert from "node:assert/strict";
import test from "node:test";

const { floatingPlacement } = await import("/runtime/floating.js");

test("a superseded answer leaves the newer placement's plane and spot", async () => {
  const floating = document.createElement("div");
  const placement = floatingPlacement({ floating, update: () => {} });
  const answers = [];
  const computePosition = () => new Promise((resolve) => answers.push(resolve));
  const position = () =>
    placement.position(
      computePosition,
      {},
      { middleware: [] },
      ({ plane }) => plane,
      null,
    );

  placement.begin();
  const older = position();
  placement.supersede();
  const newer = position();

  answers[1]({ x: 10, y: 20, plane: "window", middlewareData: {} });
  assert.ok(await newer);
  answers[0]({
    x: 0,
    y: 0,
    plane: "page",
    middlewareData: { anchorAt: { x: 0, y: 0 } },
  });
  assert.equal(await older, null);

  assert.equal(floating.dataset.lfPlane, "window");
  placement.stand(10, 20);
  assert.equal(floating.style.left, "10px");
  assert.equal(floating.style.top, "20px");
});
