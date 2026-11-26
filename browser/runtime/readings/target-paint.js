/* The marks a gesture or the user's place puts on a box of the page: the Alt aim, the
 * margin trace, the proxy ring and the location ring, and the stamp on the decision the
 * user stands in, which draws nothing of its own (`paintLocation`).
 *
 * Each is an attribute on the box it marks (base/page-paint.js, `RUNTIME_PAINT_ATTRIBUTE`),
 * and the box draws the mark itself, as its own outline, or as its border image where
 * the mark reaches over a list marker (surfaces.css). So the mark moves with the box
 * through every scroll, transform and layout change in every engine, passes under what
 * the page stacks over the box, and needs no placement here. Only the design label, which names what the
 * aim marks, stands in Leaf's chrome beside the box (`labelAim`). Persistent
 * annotations mark their boxes through their own optional painter. */

import { nextRender } from "../lib/frame-pass.js";
import { move } from "../dom/dom-move.js";
import { keeps, keepsOnEach } from "../lib/keeps.js";
import { inkedBox, markedBox, readMarkerSides, shownParts } from "../dom/geometry.js";
import { renderedUnder } from "../lib/shadow-tree.js";
import { RUNTIME_PAINT_ATTRIBUTE } from "../base/page-paint.js";
import { paintStand, placement, standAt, standBox } from "./target-paint-geometry.js";
import { inChrome } from "../base/ui-marks.js";

// One mark: an attribute on what it marks at a time (base/page-paint.js), which is each box
// the element shows through (`shownParts`), or the boxes `boxesOf` names, so an
// element with no box of its own, such as a section styled `display: contents`, is
// marked on the boxes it shows. A layout change can replace those boxes, so `refresh`
// reads them again.
/** @param {string} attribute @param {(element: Element) => Element[]} [boxesOf] */
function markOne(attribute, boxesOf = shownParts) {
  /** @type {Element | null} */
  let target = null;
  const paint = keepsOnEach(attribute);
  function draw() {
    const boxes = target?.isConnected ? boxesOf(target) : [];
    const sideMarkers = readMarkerSides(boxes);
    paint(new Map(boxes.map((box) => [box, ""])));
    sideMarkers();
  }
  return {
    /** @param {Element | null} element */
    mark(element) {
      target = element;
      draw();
    },
    refresh: () => target && draw(),
    marks: () => target,
  };
}

const aimMark = markOne(RUNTIME_PAINT_ATTRIBUTE.aimed);
const traceMark = markOne(RUNTIME_PAINT_ATTRIBUTE.traced);
const proxyMark = markOne(RUNTIME_PAINT_ATTRIBUTE.proxied);

const labelStand = paintStand();
// What leaf.js mounts in the chrome: the stand the design label stands in.
export const aimLayer = labelStand.root;
// The aim's last placement, which the label at its corner is written from (`labelAim`).
/** @type {{placed: import("./target-paint-geometry.js").Placement & {shown: import("../base/box.js").Box}, surface: Element} | null} */
let aimed = null;

export function clearAim() {
  aimed = null;
  aimMark.mark(null);
}

// The aim marks `surface`, the element itself where nothing draws it for it, as a
// comment's mark does (annotations/anchor-paint.js). Answers the box it shows, or null where none of
// it shows.
/** @param {Element | null} element @param {Element | null} [surface] */
export function paintAim(element, surface) {
  surface ??= element;
  const placed = element && surface && placement(surface, inChrome(element));
  if (!surface || !placed?.shown) {
    clearAim();
    return null;
  }
  aimMark.mark(surface);
  aimed = { placed: { ...placed, shown: placed.shown }, surface };
  return placed.shown;
}

// Stands `node`, a label naming what the aim marks, at the box's top-left corner: above
// it, clear of the mark, where the window and the frames cutting the box leave room,
// inside it otherwise, and inside the corner of what shows where a cut hides the box's
// own. It stands in the plane the scrolls carry that corner in, so a scroll carries it
// with what it names.
/** @param {HTMLElement} node */
export function labelAim(node) {
  if (!aimed) return;
  const {
    placed,
    placed: { rect, shown, levels },
    surface,
  } = aimed;
  // The label stands clear above the marks at the box's top (dom/geometry.js, `markedBox`),
  // and at the start of what the box draws (`inkedBox`), over a list marker beside it.
  const room = Math.max(0, rect.top - (markedBox(surface) ?? rect).top);
  const reach = Math.max(0, rect.left - (inkedBox(surface) ?? rect).left);
  // The label stacks with what it names: over the chrome's surfaces where the aimed
  // item stands in one, as a widget in a reply does.
  keeps(labelStand.root, "data-lf-paint-plane", inChrome(surface) ? "chrome" : "page");
  const stood = standAt(labelStand, placed);
  const above = shown.top - node.offsetHeight - room;
  // The frames cut the label too, so the room above is what every band leaves.
  const clear = Math.max(
    0,
    ...levels.filter(({ axes }) => axes.y).map(({ band }) => band.top),
  );
  const cutTop = shown.top > rect.top;
  const at = {
    left: Math.max(2, shown.left > rect.left ? shown.left : shown.left - reach),
    top: !cutTop && above >= clear ? above : shown.top + 2,
  };
  // The level whose band is the edge that cut the corner, the top's before the left's.
  const cut = cutTop
    ? labelStand.frames.findLast(
        ({ level: { axes, band } }) => axes.y && band.top === shown.top,
      )
    : shown.left > rect.left
      ? labelStand.frames.findLast(
          ({ level: { axes, band } }) => axes.x && band.left === shown.left,
        )
      : undefined;
  if (cut) {
    const {
      frame,
      level: { band },
    } = cut;
    if (node.parentElement !== frame) move(frame, node, null);
    standBox(node, at, { anchored: false, origin: { x: band.left, y: band.top } });
    return;
  }
  if (node.parentElement !== labelStand.carrier) move(labelStand.carrier, node, null);
  standBox(node, at, stood, stood.anchor, stood.at);
}

/** @param {Element | null} element @param {Element | null} [surface] */
export function paintTrace(element, surface = element) {
  traceMark.mark(element && surface?.isConnected ? surface : null);
}

/** @param {Element | null} element @param {Element | null} [surface] */
export function paintProxyRing(element, surface = element) {
  proxyMark.mark(element && surface?.isConnected ? surface : null);
  locationMark.refresh();
}

// The decision the user stands in, and each box it shows through.
/** @param {Element} element */
const decisionBoxes = (element) => [element, ...shownParts(element)];
const locationMark = markOne(RUNTIME_PAINT_ATTRIBUTE.location, (element) =>
  locationStandsDown(element) ? [] : decisionBoxes(element),
);
// `data-lf-obligation` stamps the decision whether or not its ring shows, so what
// reads it, such as a landing's room for the ring (chrome.css), finds the decision
// while a focus ring inside it stands the ring down.
const paintDecision = keepsOnEach(RUNTIME_PAINT_ATTRIBUTE.obligation);

// Stamps `element`, the decision the user stands in (records/obligations/view.js, `markHere`),
// or none, and draws the location ring round it. Each box the decision shows through
// draws the ring, as it would its focus ring, so it is also the focus ring of a
// decision the user arrived on, and the focus floor draws none of its own there. A
// trace or focus mark on a ringed box draws the ring (surfaces.css). A focus ring
// inside the decision stands it down (`locationStandsDown`).
/** @param {Element | null} element */
export function paintLocation(element) {
  paintDecision(
    new Map(element ? decisionBoxes(element).map((box) => [box, "1"]) : []),
  );
  locationMark.mark(element);
}

// Whether Leaf draws the user's focus ring on something inside the decision
// `element`: visible focus there, or the proxy ring round what a focused note on the
// details shelf stands for. That ring already says where the user is, so the location
// ring stands down rather than drawing a second band round the same place: one band
// says where the user is, whichever widget holds the focus. Rejected: each widget
// declaring that its focus carries the location, which leaves two bands round every
// widget that doesn't say so.
/** @param {Element} element */
function locationStandsDown(element) {
  if (
    element.hasAttribute("data-lf-focus-visible-within") &&
    !element.hasAttribute("data-lf-focus-visible")
  )
    return true;
  const proxied = proxyMark.marks();
  return proxied !== null && proxied !== element && renderedUnder(proxied, element);
}

// Layout can change which boxes a marked element shows through, and focus inside the
// decision can stand the location ring down.
let refreshFrame = 0;
export function geometryChanged() {
  if (refreshFrame) return;
  refreshFrame = nextRender(() => {
    refreshFrame = 0;
    for (const mark of [locationMark, aimMark, traceMark, proxyMark]) mark.refresh();
  });
}
export { geometryChanged as shifted };
