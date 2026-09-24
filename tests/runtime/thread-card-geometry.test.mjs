/* Where the inline thread card stands beside the cluster that opened it.

   A 900px-tall viewport throughout: the banner ends at 42 and the bottom chrome
   starts at 855, so the boundary the card is clamped inside runs from 50 to 847. */

import assert from "node:assert/strict";
import test from "node:test";

import { threadCardGeometry } from "/runtime/thread-card-geometry.js";

const boundary = (width) => new DOMRect(8, 50, width - 16, 797);
const cluster = (left, top) => new DOMRect(left, top, 37, 32);
const ask = (width, at, natural, target = null) =>
  threadCardGeometry({
    cluster: at,
    target,
    boundary: boundary(width),
    gap: 8,
    minWidth: 320,
    preferredWidth: 460,
    heightAt: () => natural,
  });

test("the card takes the rail's room beside its cluster", () => {
  const clamped = ask(1440, cluster(934, 436), 500);
  assert.deepEqual(
    [clamped.placement, clamped.x, clamped.width, clamped.y, clamped.detached],
    ["right", 979, 453, 347, false],
  );
  // Tall enough to reach the boundary's foot, the card slides up to it rather than
  // being shortened; a card that fits keeps its cluster's top edge.
  assert.equal(ask(1440, cluster(934, 100), 500).y, 100);
  const wide = ask(2000, cluster(1400, 100), 500);
  assert.deepEqual([wide.x, wide.width], [1445, 460]);
});

test("too little room beside it puts the card under or over its cluster", () => {
  // Too tall for the room under or over the cluster, the card holds at the foot,
  // across the cluster, rather than taking either room's height.
  const rail = ask(1160, cluster(794, 436), 500);
  assert.deepEqual(
    [rail.placement, rail.x, rail.width, rail.y],
    ["below", 794, 358, 347],
  );
  const crossing = ask(1024, cluster(871, 436), 500);
  assert.deepEqual([crossing.x, crossing.width, crossing.y], [696, 320, 347]);

  const under = ask(1024, cluster(871, 100), 300);
  assert.deepEqual([under.placement, under.y], ["below", 140]);
  const over = ask(1024, cluster(871, 700), 300);
  assert.deepEqual([over.placement, over.y], ["above", 392]);
  // No room over a cluster at the boundary's head, so the card goes under it.
  const top = ask(1024, cluster(871, 30), 300);
  assert.deepEqual([top.placement, top.y, top.detached], ["below", 70, false]);
});

test("room exactly the card's minimum is still room beside it", () => {
  // The rail's edge case: 320px of room and a 320px minimum, where `>=` and `>` part.
  const exact = ask(1440, cluster(1067, 100), 500);
  assert.deepEqual([exact.placement, exact.x, exact.width], ["right", 1112, 320]);
});

test("a boundary narrower than the card's minimum still bounds its width", () => {
  assert.equal(ask(316, cluster(100, 100), 200).width, 300);
});

test("a cluster scrolled clear of the boundary is detached", () => {
  assert.deepEqual(
    [cluster(934, 900), cluster(934, 0)].map((at) => ask(1440, at, 500).detached),
    [true, true],
  );
});

test("a card crossing the column stands clear of the target it is about", () => {
  // The cluster sits at the target's head; under the cluster alone the card would
  // cover the target's right end, so it goes under the target instead.
  const target = new DOMRect(340, 100, 540, 120);
  const clear = ask(1024, cluster(871, 100), 300, target);
  assert.deepEqual([clear.placement, clear.y], ["below", 228]);
  // No room under it, so over it, clear of the target's top.
  const low = new DOMRect(340, 500, 540, 120);
  const over = ask(1024, cluster(871, 500), 300, low);
  assert.deepEqual([over.placement, over.y], ["above", 192]);
  // A card beside its cluster in the rail never reaches the target.
  const beside = ask(1440, cluster(934, 100), 300, new DOMRect(340, 100, 580, 600));
  assert.deepEqual([beside.placement, beside.y], ["right", 100]);
});
