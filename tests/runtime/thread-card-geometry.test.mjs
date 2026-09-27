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

// A card of `natural` height, rendered as the browser renders it under the cap.
const drafted = (width, at, natural, held) =>
  threadCardGeometry({
    cluster: at,
    boundary: boundary(width),
    gap: 8,
    minWidth: 320,
    preferredWidth: 460,
    heightAt: (_width, cap) => Math.min(natural, cap),
    held,
  });

test("a drafting card keeps its side and its foot as its reply grows", () => {
  // Beside the cluster, the foot holds and the top rises.
  const rail = ask(1920, cluster(934, 160), 160);
  assert.deepEqual(rail.hold, { placement: "right", foot: 160, height: 160 });
  const grown = drafted(1920, cluster(934, 160), 180, rail.hold);
  assert.deepEqual(
    [grown.placement, grown.y, grown.y + grown.height],
    ["right", 140, 320],
  );

  // Grown past the room over its cluster, a card choosing again would stand under it.
  // Held, it stays over, and its height stops at the boundary's head.
  const over = ask(1024, cluster(871, 700), 300);
  assert.deepEqual([over.placement, over.y + over.height], ["above", 692]);
  assert.equal(ask(1024, cluster(871, 700), 700).placement, "below");
  const tall = drafted(1024, cluster(871, 700), 700, over.hold);
  assert.deepEqual([tall.placement, tall.y, tall.height], ["above", 50, 642]);

  // Under its cluster, the card grows upward across it rather than down.
  const under = ask(1024, cluster(871, 100), 300);
  const longer = drafted(1024, cluster(871, 100), 340, under.hold);
  assert.deepEqual(
    [longer.placement, longer.y, longer.y + longer.height],
    ["below", 100, under.y + under.height],
  );
});

test("a held foot rides its cluster inside the boundary", () => {
  const over = ask(1024, cluster(871, 700), 300);
  // Scrolled up, the foot stops where the room above it is still the held height.
  const up = drafted(1024, cluster(871, 200), 300, over.hold);
  assert.deepEqual([up.y, up.height], [50, 300]);
  // Scrolled down, it stops at the boundary's foot.
  const down = drafted(1024, cluster(871, 900), 300, over.hold);
  assert.equal(down.y + down.height, 847);
});

test("a held side the room no longer allows gives way to a fresh choice", () => {
  const rail = ask(1920, cluster(934, 160), 160);
  const narrowed = drafted(1024, cluster(871, 160), 160, rail.hold);
  assert.deepEqual([narrowed.placement, narrowed.hold.placement], ["below", "below"]);
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
