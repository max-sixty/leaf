import {
  localScrollBy,
  scrollAxes
} from "./bundle-chrome.js";
import {
  pageScroller,
  reachable,
  scrollersOf,
  startScroll
} from "./bundle-presence.js";
import {
  clippingAxes,
  landingBand,
  nearestScrollBy,
  notice,
  offer,
  placeBox,
  placeHolder,
  raiseError,
  seenRect,
  shownWindow,
  visibleBand
} from "./bundle-page-paint.js";
import {
  carriedFrom,
  deepFocus,
  focused,
  inputCount,
  nextRender,
  onCurrentLocation,
  renderedParent,
  renderedUnder,
  ringBox
} from "./bundle-frame-visibility.js";

// runtime/user-intent.js
var passed = /* @__PURE__ */ new WeakMap();
var passOn = (container, target) => passed.set(target, { container, intent: inputCount() });
var displaced = (source, at) => {
  if (!(source instanceof Node) || !at) return false;
  const via = passed.get(at);
  const carry = carriedFrom(at);
  return at.contains(source) || via?.intent === inputCount() && via.container.contains(source) || carry?.inputs === inputCount() && (carry.from === source || source.contains(carry.from));
};
function retainUserIntent({
  source = focused(),
  available = () => true,
  fallback = null,
  since = inputCount()
} = {}) {
  const retained = since;
  let held = source instanceof Node ? new WeakRef(source) : null;
  const current = () => {
    const at = focused();
    const from = held?.deref();
    const withinSource = from === document.body ? at === document.body : from?.contains(at);
    return available() && retained === inputCount() && (at === document.body || at === fallback || withinSource || displaced(from, at));
  };
  current.available = available;
  current.handoff = (move) => {
    if (!available() || retained !== inputCount()) return false;
    const moved = current();
    if (moved) move();
    const at = focused();
    held = at ? new WeakRef(at) : null;
    return moved && current();
  };
  return current;
}
function restrictUserIntent(retained, available) {
  const current = () => available() && retained();
  current.available = () => available() && retained.available();
  current.handoff = (move) => available() && retained.handoff(move);
  return current;
}

// runtime/landing-scroll.js
var land = (box, by, behavior) => {
  if (behavior !== "instant") startScroll(box);
  box.scrollBy({ ...by, behavior });
};
function scrollMargin(where, side = "Top") {
  if (!(where instanceof Range))
    return Number.parseFloat(getComputedStyle(where)[`scrollMargin${side}`]) || 0;
  const edges = [
    where.startContainer.childNodes[where.startOffset],
    where.endContainer.childNodes[where.endOffset - 1]
  ].filter((edge) => edge instanceof Element);
  return edges.length ? Math.max(...edges.map((edge) => scrollMargin(edge, side))) : 0;
}
function shownFor(where) {
  const ring = ringBox(where);
  if (ring === where) return where;
  const box = placeBox(ring);
  const room = roomAround(ring, where);
  return box.height <= room.height && box.width <= room.width ? ring : where;
}
var destinationBox = (where) => placeBox(shownFor(where));
var holderOf = (where) => placeHolder(shownFor(where));
var readingTop = (holder, box) => visibleBand(box, holder)?.top ?? landingBand(box).top;
function topMargin(where, box, holder = holderOf(where)) {
  const band = landingBand(box);
  return Math.max(scrollMargin(where), readingTop(holder, box) - band.top);
}
var landingRoom = (where, until = where) => roomAround(shownFor(where), where, until);
function roomAround(shown, where, until = where) {
  const holder = placeHolder(shown);
  const regions = [...scrollersOf(holder)];
  let { width, height } = shownWindow();
  for (let box = shown instanceof Range ? holder : renderedParent(shown); box instanceof Element; box = renderedParent(box)) {
    const band = (until === where || renderedUnder(until, box)) && landingBand(box);
    if (band) {
      const axes = box === pageScroller ? { x: true, y: true } : clippingAxes(getComputedStyle(box));
      const at = regions.indexOf(box);
      const clearance = at === 0 ? topMargin(where, box, holder) + scrollMargin(until, "Bottom") : at > 0 ? Math.max(0, readingTop(regions[at - 1], box) - band.top) : 0;
      if (axes.x) width = Math.min(width, band.right - band.left);
      if (axes.y) height = Math.min(height, band.bottom - band.top - clearance);
    }
    if (box === pageScroller || getComputedStyle(box).position === "fixed") break;
  }
  return { width, height };
}
function fitsWhole(where) {
  const box = destinationBox(where);
  const room = landingRoom(where);
  return box.height <= room.height && box.width <= room.width;
}
function seesWhole(where, box, out) {
  const seen = seenRect(shownFor(where), /* @__PURE__ */ new Map(), out);
  if (!seen) return false;
  const room = landingRoom(where);
  return (box.height > room.height || seen.top <= out.top && seen.bottom >= out.bottom) && (box.width > room.width || seen.left <= out.left && seen.right >= out.right);
}
function alreadyShown(where) {
  const box = destinationBox(where);
  return seesWhole(where, box, box);
}
function ringShown(where) {
  const box = destinationBox(where);
  const [top, right, bottom, left] = ["Top", "Right", "Bottom", "Left"].map(
    (side) => scrollMargin(where, side)
  );
  return seesWhole(
    where,
    box,
    new DOMRect(
      box.left - left,
      box.top - top,
      box.width + left + right,
      box.height + top + bottom
    )
  );
}
function placementBy(where, block, box, margin) {
  const rect = destinationBox(where);
  const band = landingBand(box);
  const room = band.bottom - band.top;
  const place = block === "start" ? margin : block === "end" ? room - rect.height - scrollMargin(where, "Bottom") : Math.max((room - rect.height) / 2, margin);
  const movement = block === "nearest" ? nearestScrollBy(
    rect.top - margin,
    rect.bottom + scrollMargin(where, "Bottom"),
    band.top,
    band.bottom
  ) : rect.top - band.top - place;
  return movement;
}
function verticalTravel(box, movement) {
  const scale = scrollAxes(box).y.y;
  const local = scale === 0 ? 0 : reachable(box, movement / scale);
  return { local, moved: local * scale };
}
function scrollIntoReadingBand(where, holder, block, behavior) {
  const [box, ...around] = scrollersOf(holder);
  if (!box) return;
  const rect = destinationBox(where);
  const margin = topMargin(where, box);
  let { top, bottom } = rect;
  if (block === "start") {
    top -= margin;
  } else if (block === "end") {
    top = bottom - 1;
    bottom += scrollMargin(where, "Bottom");
  }
  let { local, moved } = verticalTravel(box, placementBy(where, block, box, margin));
  if (Math.abs(moved) >= 1) land(box, { top: local }, behavior);
  let inner = box;
  for (const outer of around) {
    top -= moved;
    bottom -= moved;
    const band = landingBand(outer);
    if (!band) return;
    band.top = Math.max(band.top, readingTop(inner, outer));
    if (block === "start") bottom = Math.min(bottom, top + band.bottom - band.top);
    ({ local, moved } = verticalTravel(
      outer,
      nearestScrollBy(top, bottom, band.top, band.bottom)
    ));
    if (Math.abs(moved) >= 1) land(outer, { top: local }, behavior);
    inner = outer;
  }
}
function scrollIntoView(where, { alignment = where, behavior = "auto", block = "start", within = null } = {}) {
  if (!where) return;
  const holder = holderOf(alignment);
  if (!holder) return;
  const targetScroller = within ? null : scrollersOf(holder).next().value;
  let inside = true;
  const start = holderOf(where);
  for (let box = start; box instanceof Element; box = renderedParent(box)) {
    if (box === targetScroller) inside = false;
    const band = landingBand(box);
    if (band) {
      const { left, right } = band;
      const destination = destinationBox(where);
      const byX = nearestScrollBy(
        destination.left - scrollMargin(where, "Left"),
        destination.right + scrollMargin(where, "Right"),
        left,
        right
      );
      const byY = inside ? placementBy(where, "nearest", box, topMargin(where, box, start)) : 0;
      if (byX || byY) land(box, localScrollBy(box, { x: byX, y: byY }), "instant");
    }
    if (box === within || box === pageScroller || getComputedStyle(box).position === "fixed")
      break;
  }
  if (targetScroller) scrollIntoReadingBand(alignment, holder, block, behavior);
}
onCurrentLocation((node, cause) => {
  if (cause !== "step" || !node) return;
  nextRender(() => {
    if (deepFocus() !== node) return;
    if (!ringShown(node)) scrollIntoView(node, { block: "nearest" });
    for (let box = node; box instanceof Element; box = renderedParent(box)) {
      if (!box.matches("[data-lf-obligation]")) continue;
      if (getComputedStyle(box).outlineStyle === "none") continue;
      if (!ringShown(box)) scrollIntoView(box, { block: "nearest" });
      break;
    }
  });
});

// runtime/copy-control.js
function copyControl(className, { label = "", success, error }) {
  const copy = offer("wa-copy-button", className);
  if (label) copy.copyLabel = label;
  copy.successLabel = success;
  copy.errorLabel = error;
  copy.tooltip = "none";
  copy.addEventListener("wa-copy", () => notice(success, { announce: false }));
  copy.addEventListener("wa-error", () => raiseError(error, { announce: false }));
  return copy;
}

export {
  passOn,
  retainUserIntent,
  restrictUserIntent,
  landingRoom,
  fitsWhole,
  alreadyShown,
  scrollIntoReadingBand,
  scrollIntoView,
  copyControl
};
