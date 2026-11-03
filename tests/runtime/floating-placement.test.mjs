/* A floating box's placement: an answer computed for a placement a later one superseded
   writes nothing, so the later placement's plane and way of standing hold; and the
   scroll invalidation a held plane adds leaves the watch's own when it ends. */

import assert from "node:assert/strict";
import test from "node:test";

const { floatingPlacement } = await import("/runtime/annotation-overlay/floating.js");

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

test("leaving a held plane keeps the watch's own scroll invalidation", async () => {
  const scroller = document.createElement("div");
  scroller.style.overflowY = "auto";
  const row = document.createElement("p");
  scroller.append(row);
  const floating = document.createElement("div");
  document.body.append(scroller, floating);
  let updates = 0;
  const placement = floatingPlacement({ floating, update: () => updates++ });
  // Floating UI's autoUpdate registers the update it is given on each scroller around
  // the reference.
  placement.watch(row, { contextElement: row }, (reference, box, update) => {
    scroller.addEventListener("scroll", update);
    return () => scroller.removeEventListener("scroll", update);
  });
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
  // Held in, the placement solves again on each scroll around the row; placed again
  // against nothing those scrollers hold, it stops.
  placement.begin();
  await position(row);
  placement.begin();
  await position(null);

  updates = 0;
  scroller.dispatchEvent(new Event("scroll"));
  assert.equal(updates, 1, "the watch no longer hears the scroller");
  placement.stop();
  scroller.remove();
  floating.remove();
});
