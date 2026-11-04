/* The marks a gesture or the user's place puts on a box of the page: the Alt aim, the
 * margin trace, the proxy ring and the location ring.
 *
 * Each is a class on the box it marks, and the box draws the mark itself, as its own
 * outline (surfaces.css). So the mark moves with the box through every scroll,
 * transform and layout change in every engine, passes under what the page stacks over
 * the box, and needs no placement here. Only the design label, which names what the
 * aim marks, stands in Leaf's chrome beside the box (`labelAim`). Persistent
 * annotations mark their boxes through their own optional painter. */

import { nextRender } from "./rendering.js";
import { move } from "./dom-move.js";
import { keeps } from "./keeps.js";
import { inChrome } from "./passages.js";
import { shownParts } from "./geometry.js";
import { locationStandsDown, paint } from "./page-paint.js";
import { paintStand, placement, standAt, standBox } from "./target-paint-geometry.js";

// One mark: a class on what it marks at a time, which is each box the element shows
// through (`shownParts`), so an element with no box of its own, such as a section
// styled `display: contents`, is marked on the boxes it shows. A layout change can
// replace those boxes, so `refresh` reads them again.
/** @param {string} className */
function markOne(className) {
  /** @type {Element | null} */
  let target = null;
  /** @type {Element[]} */
  let marked = [];
  function draw() {
    const boxes = target?.isConnected ? shownParts(target) : [];
    paint({ attribute: "class", token: className }, () => {
      for (const box of marked)
        if (!boxes.includes(box)) box.classList.toggle(className, false);
      for (const box of boxes) box.classList.toggle(className, true);
    });
    marked = boxes;
  }
  return {
    /** @param {Element | null} element */
    mark(element) {
      target = element;
      draw();
    },
    refresh: () => target && draw(),
  };
}

const aimMark = markOne("lf-aimed");
const traceMark = markOne("lf-traced");
const proxyMark = markOne("lf-proxied");

const labelStand = paintStand();
// What leaf.js mounts in the chrome: the stand the design label stands in.
export const aimLayer = labelStand.root;
// The aim's last placement, which the label at its corner is written from (`labelAim`).
/** @type {{placed: import("./target-paint-geometry.js").Placement & {shown: import("./rect.js").Box}, surface: Element} | null} */
let aimed = null;

export function clearAim() {
  aimed = null;
  aimMark.mark(null);
}

// The aim marks `surface`, the element itself where nothing draws it for it, as a
// comment's mark does (anchor-paint.js). Answers the box it shows, or null where none of
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
  const style = getComputedStyle(shownParts(surface)[0] ?? surface);
  const room = Math.max(
    0,
    Number.parseFloat(style.outlineOffset) + Number.parseFloat(style.outlineWidth),
  );
  // The label stacks with what it names: over the chrome's surfaces where the aimed
  // item stands in one, as a widget frozen in a reply does.
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
    left: Math.max(2, shown.left),
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
}

/** @type {Element | null} */
let locationElement = null;
let locationFrame = 0;
/** @type {Element[]} */
let locationProjected = [];
const PROJECTED_LOCATION = "lf-projected-location";

// The location ring round `element`, the decision the user stands in, or none
// (obligations/view.js, `markHere`). Each box the decision shows through draws it, as
// it would its focus ring, so it is also the focus ring of a decision the user arrived
// on, and the focus floor draws none of its own there (surfaces.css). A control inside
// the decision that carries the location itself stands it down (page-paint.js,
// `locationStandsDown`).
/** @param {Element | null} element */
export function paintLocation(element) {
  locationElement = element;
  drawLocation();
}

function drawLocation() {
  const element = locationElement;
  const boxes =
    element?.isConnected && !locationStandsDown(element)
      ? [element, ...shownParts(element)]
      : [];
  paint({ attribute: "class", token: PROJECTED_LOCATION }, () => {
    for (const box of locationProjected)
      if (!boxes.includes(box)) box.classList.toggle(PROJECTED_LOCATION, false);
    for (const box of boxes) box.classList.toggle(PROJECTED_LOCATION, true);
  });
  locationProjected = boxes;
}

// Layout can change which boxes a marked element shows through, and a control inside
// the decision can take the location over.
export function geometryChanged() {
  if (locationFrame) return;
  locationFrame = nextRender(() => {
    locationFrame = 0;
    drawLocation();
    aimMark.refresh();
    traceMark.refresh();
    proxyMark.refresh();
  });
}
export { geometryChanged as shifted };
