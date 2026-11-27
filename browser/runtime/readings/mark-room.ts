/* The room the marks round a subject take beside it, which every surface that stands
 * beside the subject keeps clear of: a thread's card, the comment box and a preview.
 *
 * The marks are the subject's own (dom/geometry.js, `markedBox`), and those of each box
 * round it that Leaf marks, one a comment or the aim can name (anchor-resolution.js,
 * `isAddressable`), whose edge on a side stands within the surface's gap past the room
 * so far. So a card or a preview beside a widget stands past the ring round the
 * decision that holds it rather than on that ring, though the widget rings on its own
 * frame. A box whose every edge stands further out holds the surface inside it, as a
 * section holds the card beside one of its paragraphs, so the surface stands over that
 * box's ring; the walk ends there, since the boxes round it stand further out still.
 * Every box states the room its marks take (element-marks.css, `:where(*)`) whether or not
 * Leaf ever marks it, so the walk skips a box nothing can name, such as a padded
 * wrapper, which never wears a mark and would otherwise push the surface out.
 * A margin seat stands for the element it marks (`[data-lf-margin-for]`, whose
 * `lfTarget` names it) and stands at that element's edge, wherever the seat sits in
 * the tree, so the walk goes on from that element: a preview of a decision's margin
 * marker that reaches back over the decision stands past the decision's ring.
 *
 * The design label is no such surface: it names the aim's ring and stands on it
 * (target-paint.js, `labelAim`). */

import { markedBox } from "../dom/geometry.js";
import { closestAcross, renderedParent } from "../lib/shadow-tree.js";
import { isAddressable } from "./anchor-resolution.js";
import type { Box } from "../base/box.js";

export type MarkRoom = { left: number; top: number; right: number; bottom: number };

const EDGES: readonly ["left", "top", "right", "bottom"] = [
  "left",
  "top",
  "right",
  "bottom",
];

// How far `outer` reaches past `box` on each side.
const reachPast = (outer: Box, box: Box): MarkRoom => ({
  left: box.left - outer.left,
  top: box.top - outer.top,
  right: outer.right - box.right,
  bottom: outer.bottom - box.bottom,
});

// The room the marks round `subject` take past `box`, its box, on each side, for a
// surface that stands `gap` past them; none where no part of the subject shows.
export function markRoom(subject: Element, box: Box, gap: number): MarkRoom {
  const own = markedBox(subject);
  if (!own) return { left: 0, top: 0, right: 0, bottom: 0 };
  const room = reachPast(own, box);
  const marks = closestAcross(subject, "[data-lf-margin-for]")?.lfTarget;
  for (
    let at = marks?.isConnected ? marks : renderedParent(subject);
    at && at !== document.body;
    at = renderedParent(at)
  ) {
    // A `display: contents` box draws its marks round its parts, the subject among them.
    if (getComputedStyle(at).display === "contents") continue;
    const edges = reachPast(at.getBoundingClientRect(), box);
    const near = EDGES.filter((edge) => edges[edge] <= room[edge] + gap);
    if (!near.length) break;
    if (!isAddressable(at)) continue;
    const theirs = markedBox(at);
    if (!theirs) continue;
    const marks = reachPast(theirs, box);
    for (const edge of near) room[edge] = Math.max(room[edge], marks[edge]);
  }
  return room;
}
