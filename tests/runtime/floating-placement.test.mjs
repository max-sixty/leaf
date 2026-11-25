/* A floating box's placement: an answer computed for a placement a later one superseded
   writes nothing, so the later placement's plane and way of standing hold; and each
   scroll around the element it is watched against, and then around the words it stands
   beside, solves it again, once. */

import assert from "node:assert/strict";
import test from "node:test";

const { floatingPlacement, floatingUi } =
  await import("/runtime/annotations/annotation-overlay/floating.js");

test("a superseded answer leaves the newer placement's plane and spot", async () => {
  const floating = document.createElement("div");
  const placement = floatingPlacement({ floating, update: () => {} });
  let requested;
  const nextRequest = () => new Promise((resolve) => (requested = resolve));
  const computePosition = () => new Promise((resolve) => requested(resolve));
  const position = () =>
    placement.position(
      computePosition,
      { getBoundingClientRect: () => new DOMRect(10, 20, 50, 30) },
      { middleware: [] },
      ({ plane }) => plane,
      null,
    );

  placement.begin();
  const olderRequested = nextRequest();
  const older = position();
  const answerOlder = await olderRequested;
  placement.supersede();
  const newerRequested = nextRequest();
  const newer = position();
  const answerNewer = await newerRequested;

  const held = {
    edges: { x: "left", y: "top" },
    width: 50,
    height: 30,
    block: { width: 400, height: 300 },
  };
  const answer = {
    x: 10,
    y: 20,
    plane: "window",
    middlewareData: { held, anchorAt: { offset: null } },
  };
  answerNewer(answer);
  assert.ok(await newer);
  answerOlder({
    x: 0,
    y: 0,
    plane: "page",
    middlewareData: { held, anchorAt: { offset: { x: 0, y: 0 } } },
  });
  assert.equal(await older, null);

  assert.equal(floating.dataset.lfPlane, "window");
  placement.stand(answer);
  assert.equal(floating.style.left, "10px");
  assert.equal(floating.style.top, "20px");
});

test("each scroll around what a box is watched against or stood beside solves it again, once", async () => {
  const { getOverflowAncestors } = await floatingUi();
  const scroller = document.createElement("div");
  scroller.style.overflowY = "auto";
  const row = document.createElement("p");
  scroller.append(row);
  const floating = document.createElement("div");
  document.body.append(scroller, floating);
  let updates = 0;
  const placement = floatingPlacement({ floating, update: () => updates++ });
  /** @type {unknown} */
  let asked = null;
  placement.watch(
    row,
    { contextElement: row },
    (reference, box, update, options) => {
      asked = options;
      return () => {};
    },
    getOverflowAncestors,
  );
  assert.deepEqual(asked, { ancestorScroll: false });
  const answer = {
    x: 0,
    y: 0,
    middlewareData: {
      held: {
        edges: { x: "left", y: "top" },
        width: 50,
        height: 30,
        block: { width: 400, height: 300 },
      },
      anchorAt: { offset: null },
    },
  };
  const position = (contextNode) =>
    placement.position(
      async () => answer,
      { contextNode, getBoundingClientRect: () => new DOMRect(10, 20, 50, 30) },
      { middleware: [] },
      () => "window",
      contextNode,
    );
  const scrolled = () => {
    updates = 0;
    scroller.dispatchEvent(new Event("scroll"));
    return updates;
  };
  assert.equal(
    scrolled(),
    1,
    "watched before any placement stands it, the box hears the row's scroller",
  );
  placement.begin();
  await position(row);
  placement.begin();
  await position(row);
  assert.equal(scrolled(), 1, "the row's scroller solves the box once per scroll");
  placement.begin();
  await position(null);
  assert.equal(
    scrolled(),
    0,
    "placed against nothing it holds, the scroller is let go",
  );
  placement.begin();
  await position(row);
  placement.stop();
  assert.equal(scrolled(), 0, "a stopped placement hears no scroll");
  scroller.remove();
  floating.remove();
});
