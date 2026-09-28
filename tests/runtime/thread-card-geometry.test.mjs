/* Where the inline thread card stands beside the cluster that opened it.

   A 900px-tall viewport throughout: the banner ends at 42 and the bottom chrome
   starts at 855, so the boundary the card is clamped inside runs from 50 to 847. */

import assert from "node:assert/strict";
import test from "node:test";

import { threadCardGeometry } from "/runtime/thread-card-geometry.js";

const boundary = (width) => new DOMRect(8, 50, width - 16, 797);
const cluster = (left, top) => new DOMRect(left, top, 37, 32);
// The words a cluster is about end 46px left of it, as a column's do.
const words = (at) => new DOMRect(at.left - 586, at.top, 540, at.height);
// A card of `natural` height, rendered as the browser renders it under the cap.
const place = (width, at, natural, { target = words(at), hold = null, edge } = {}) =>
  threadCardGeometry({
    cluster: at,
    target,
    boundary: boundary(width),
    gap: 8,
    minWidth: 320,
    preferredWidth: 460,
    heightAt: (_width, cap) => Math.min(natural, cap),
    hold,
    edge,
  });
const ask = (width, at, natural, target = words(at)) =>
  place(width, at, natural, { target });

test("the card takes the room right of its words, over its cluster if it must", () => {
  // Room for the preferred measure beside the cluster: the card clears it.
  const wide = ask(2000, cluster(1400, 100), 500);
  assert.deepEqual([wide.placement, wide.x, wide.width], ["right", 1445, 460]);
  // Less: the card keeps its measure by standing further left, over the cluster.
  const over = ask(1440, cluster(1000, 100), 500);
  assert.deepEqual([over.placement, over.x, over.width], ["right", 972, 460]);
  // Less again: it stands beside the words, as wide as the room from there.
  const beside = ask(1440, cluster(1126, 436), 500);
  assert.deepEqual(
    [beside.placement, beside.x, beside.width, beside.y],
    ["right", 1088, 344, 347],
  );
  // Tall enough to reach the boundary's foot, the card slides up to it rather than
  // being shortened; a card that fits keeps its cluster's top edge.
  assert.equal(ask(1440, cluster(1126, 100), 500).y, 100);
  // A thread with no target has only its cluster to stand clear of.
  const alone = ask(1440, cluster(1000, 100), 500, null);
  assert.deepEqual([alone.x, alone.width], [1045, 387]);
});

test("too little room right of its words puts the card under or over its cluster", () => {
  // At its minimum, its right edge on the visible edge. Too tall for the room under or
  // over the cluster, the card holds at the foot, across the cluster, rather than taking
  // either room's height.
  const crossing = ask(1024, cluster(871, 436), 500);
  assert.deepEqual(
    [crossing.placement, crossing.x, crossing.width, crossing.y],
    ["below", 696, 320, 347],
  );

  const under = ask(1024, cluster(871, 100), 300);
  assert.deepEqual([under.placement, under.y], ["below", 140]);
  const over = ask(1024, cluster(871, 700), 300);
  assert.deepEqual([over.placement, over.y], ["above", 392]);
  // No room over a cluster at the boundary's head, so the card goes under it.
  const top = ask(1024, cluster(871, 30), 300);
  assert.deepEqual([top.placement, top.y], ["below", 70]);
});

test("room exactly the card's minimum is still room beside its words", () => {
  // The edge case: 320px of room and a 320px minimum, where `>=` and `>` part.
  const exact = ask(1440, cluster(1150, 100), 500);
  assert.deepEqual([exact.placement, exact.x, exact.width], ["right", 1112, 320]);
});

test("a drafting card keeps its side and its foot as its reply grows", () => {
  // Beside the cluster, the foot holds and the top rises.
  const rail = ask(1920, cluster(934, 160), 160);
  assert.deepEqual(rail.hold, {
    placement: "right",
    width: 460,
    top: 0,
    foot: 160,
    height: 160,
    seen: true,
  });
  const grown = place(1920, cluster(934, 160), 180, { hold: rail.hold, edge: "foot" });
  assert.deepEqual(
    [grown.placement, grown.y, grown.y + grown.height],
    ["right", 140, 320],
  );

  // Grown past the room over its cluster, a card choosing again would stand under it.
  // Held, it stays over, and its height stops at the boundary's head.
  const over = ask(1024, cluster(871, 700), 300);
  assert.deepEqual([over.placement, over.y + over.height], ["above", 692]);
  assert.equal(ask(1024, cluster(871, 700), 700).placement, "below");
  const tall = place(1024, cluster(871, 700), 700, { hold: over.hold, edge: "foot" });
  assert.deepEqual([tall.placement, tall.y, tall.height], ["above", 50, 642]);

  // Under its cluster, the card grows upward across it rather than down.
  const under = ask(1024, cluster(871, 100), 300);
  const longer = place(1024, cluster(871, 100), 340, {
    hold: under.hold,
    edge: "foot",
  });
  assert.deepEqual(
    [longer.placement, longer.y, longer.y + longer.height],
    ["below", 100, under.y + under.height],
  );
});

test("a card being read keeps its top as a turn arrives", () => {
  // Near the boundary's foot, a longer transcript stops there and scrolls inside the
  // card, rather than pushing the card's top up over the words being read.
  const reading = ask(1440, cluster(934, 600), 200);
  const turn = place(1440, cluster(934, 600), 400, { hold: reading.hold });
  assert.deepEqual([turn.y, turn.height], [600, 247]);
  // Starting to draft holds the foot where the card stands, with the editor on it, and
  // the transcript takes the room over the card that its top held it out of.
  const drafting = place(1440, cluster(934, 600), 400, {
    hold: turn.hold,
    edge: "foot",
  });
  assert.deepEqual([drafting.y + drafting.height, drafting.height], [847, 400]);
});

test("a card over its cluster grows upward as a turn arrives", () => {
  // Read, it holds its foot, the edge toward its cluster, rather than growing down
  // across the cluster and the words under it.
  const over = ask(1024, cluster(871, 700), 300);
  assert.equal(over.placement, "above");
  const turn = place(1024, cluster(871, 700), 400, { hold: over.hold });
  assert.deepEqual([turn.y + turn.height, turn.height], [over.y + over.height, 400]);
});

test("a scroll carries the held card inside the boundary and never squeezes it", () => {
  const over = ask(1024, cluster(871, 700), 300);
  // Scrolled up, the foot stops where the whole card still fits under the head.
  const up = place(1024, cluster(871, 200), 300, { hold: over.hold, edge: "foot" });
  assert.deepEqual([up.y, up.height], [50, 300]);
  const read = place(1024, cluster(871, 100), 300, { hold: over.hold });
  assert.deepEqual([read.y, read.height], [50, 300]);
  // Opened low in the window, the card is clamped over its cluster; scrolled up into
  // room, it stands at its cluster's top again.
  const low = ask(1440, cluster(934, 700), 300);
  assert.equal(low.y, 547);
  const risen = place(1440, cluster(934, 400), 300, { hold: low.hold });
  assert.equal(risen.y, 400);
});

test("the card leaves with its cluster and comes back with it", () => {
  const open = ask(1440, cluster(934, 100), 300);
  const at = (top) => place(1440, cluster(934, top), 300, { hold: open.hold });
  // Held at the head while any of the cluster shows.
  assert.equal(at(30).y, 50);
  // Past that, by exactly as far as the cluster has gone.
  assert.equal(at(0).y, 32);
  assert.equal(at(-400).y, -368);
  assert.equal(at(100).y, 100);
  assert.equal(at(-400).away, true);
  assert.equal(at(0).away, false);
  // A scroll carries the card with the window while the head holds it, and with the
  // page at its spot or once the head has given with its cluster.
  assert.deepEqual(
    [at(100), at(30), at(0), at(-400)].map((placed) => placed.plane),
    ["page", "window", "page", "page"],
  );
  // Through the foot the same way, whichever edge is held.
  const foot = (top) =>
    place(1440, cluster(934, top), 300, { hold: open.hold, edge: "foot" });
  assert.deepEqual([foot(900).y, foot(900).height], [600, 300]);
  assert.deepEqual([foot(700).plane, foot(900).plane], ["window", "page"]);
});

test("a card opened with its cluster out of the window stands in it", () => {
  // Words pressed deep in a tall block whose cluster is above the window: the card opens
  // at the window's head and stays there until the cluster has been in the window.
  const open = ask(1440, cluster(934, -600), 300);
  assert.deepEqual(
    [open.y, open.away, open.hold.seen, open.plane],
    [50, false, false, "window"],
  );
  const scrolled = place(1440, cluster(934, -500), 300, { hold: open.hold });
  assert.equal(scrolled.y, 50);
  const shown = place(1440, cluster(934, 100), 300, { hold: scrolled.hold });
  assert.equal(shown.hold.seen, true);
  assert.equal(place(1440, cluster(934, -400), 300, { hold: shown.hold }).y, -368);
});

test("a keyboard hiding the cluster keeps the card in what the user sees", () => {
  // A software keyboard shrinks the visible room to 50..400 without scrolling the page:
  // the cluster at 500 is under the keyboard, still inside the window.
  const open = ask(1440, cluster(934, 300), 300);
  const typing = threadCardGeometry({
    cluster: cluster(934, 500),
    boundary: new DOMRect(8, 50, 1424, 350),
    scrollport: boundary(1440),
    gap: 8,
    minWidth: 320,
    preferredWidth: 460,
    heightAt: (_width, cap) => Math.min(300, cap),
    hold: open.hold,
    edge: "foot",
  });
  assert.deepEqual([typing.y, typing.y + typing.height], [100, 400]);
});

test("a hold whose side or width the room no longer gives yields to a fresh choice", () => {
  const rail = ask(1920, cluster(934, 160), 160);
  const narrowed = place(1024, cluster(871, 160), 160, {
    hold: rail.hold,
    edge: "foot",
  });
  assert.deepEqual([narrowed.placement, narrowed.hold.placement], ["below", "below"]);
  // Narrower on the same side, a card whose words reflowed taller stands at its spot
  // again at its whole height, rather than capped by the room under its held top.
  const read = ask(1440, cluster(1126, 500), 300);
  const reflowed = place(1400, cluster(1106, 500), 500, { hold: read.hold });
  assert.deepEqual(
    [reflowed.placement, reflowed.width, reflowed.y, reflowed.height],
    ["right", 324, 347, 500],
  );
});

test("a boundary narrower than the card's minimum still bounds its width", () => {
  assert.equal(ask(316, cluster(100, 100), 200).width, 300);
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
