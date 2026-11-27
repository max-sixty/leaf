// Compiled from target-paint-geometry.ts by build/typescript.mjs; edit that file.
/* Where paint Leaf stands beside the page's targets stands: the design legend and its
 * label, key chips, margin bars, the search's mark, drawing ink, and the comparison's
 * bars and change card. Marks round a box are drawn by the box itself (surfaces.css).
 *
 * A stand says nothing to assistive technology of its own: each painter hides what
 * only the eye reads, as the key chips' layers do beside the live region that speaks
 * them, and leaves readable what is read, as a change's card is.
 *
 * Stand each box in the planes of what carries its target (`paintStand`), alone or in a
 * set (`paintSet`); a set keeps which of its targets stand near enough to be shown. */

import {
  anchorAt,
  anchorBox,
  anchorElement,
  anchorReaches,
  anchorReading,
  cutFrames,
  nameAnchor,
  scrollsWith,
} from "../dom/css-anchors.js";
import {
  headerCuts,
  nearObserver,
  nearWindow,
  paintClips,
  scrollsContent,
  shownBox,
} from "../dom/geometry.js";
import { hasArea, intersect } from "../dom/rect.js";
import { move } from "../dom/dom-move.js";
import { objectIds } from "../base/ids.js";
import { keeps, layoutPx } from "../lib/keeps.js";

// A stand holds paint boxes over their targets in the planes of what carries the
// targets, through the anchored cut frames every box that follows scrolled content
// stands in (dom/css-anchors.js). Each box that clips a target (`paintClips`) gets a frame
// cut to its band, inside the frame of the box holding it; the boxes stand in a carrier
// in the innermost. The window's cuts, a header stuck over the page's top and, for paint
// stacked above them, the chrome's views, stand in the window's plane, as a frame
// fixed where the window holds it. Each other frame is anchored to the scroller whose
// band it cuts, and each box to its own target, so it follows that target through
// layout, a transform or a sticky offset as well: a scroll anywhere around a target
// moves its box and every cut over it in the frame that scrolls, and placing it again
// after the scroll writes nothing. Boxes the same frames cut share a stand (`standIn`,
// then `standBox` for each).
//
// Where an anchor cannot position the stand (`anchoredBy`), as for a target in a native
// layer the stand is not in or a box in the chrome after the stand, every frame and box
// stands where the window holds it as measured, and the pass a scroll brings places them
// again. The stand, not the box, carries the paint's stacking (`data-lf-paint-plane`),
// since the frames it holds stack what they hold.

export function paintStand(box = null) {
  const root = document.createElement("div");
  root.className = "lf-ui lf-target-paint lf-paint-stand";
  root.style.position = "fixed";
  const carrier = document.createElement("div");
  carrier.className = "lf-paint-carrier";
  if (box) carrier.append(box);
  root.append(carrier);
  return { root, carrier, box, anchored: false, frames: [] };
}

// The box an anchor carries `el` by for a stand at `root`: its anchor box
// (dom/css-anchors.js), where every scroll that moves `el` moves that box with it
// (`scrollsWith`), or that box's own parts where `el` draws none. Null where the anchor
// cannot position a box at `root` (`anchorReaches`).
function anchoredBy(el, root) {
  const anchor = anchorElement(el);
  if (!anchorReaches(anchor, root)) return null;
  return anchor === el ||
    (scrollsWith(el, anchor) && !scrollsContent(anchor)) ||
    scrollsWith(anchor, el)
    ? anchor
    : null;
}

const makeFrame = () => {
  const frame = document.createElement("div");
  frame.className = "lf-paint-frame";
  return frame;
};

// Each of `levels` with the anchor that carries its holder's frame for a stand at
// `root` (`anchoredBy`), null where it has no holder or the anchor cannot carry it, where
// that anchor stands (`at`, `anchorBox`) and its name (`reading`, `anchorReading`). Read
// before any write, since each reads style or layout.
/** @param anchors holder → its reading, shared by a pass's levels */
function anchorLevels(levels, root, anchors = new Map()) {
  return levels.map((level) => {
    const { holder } = level;
    if (!holder) return { ...level, anchor: null, at: null, reading: null };
    let reading = anchors.get(holder);
    if (!reading) {
      const anchor = anchoredBy(holder, root);
      reading = {
        anchor,
        at: anchor && anchorBox(anchor),
        reading: anchor && anchorReading(anchor),
      };
      anchors.set(holder, reading);
    }
    return { ...level, ...reading };
  });
}

// Stands `stand`'s frames over `placed`, whose levels carry their holders' anchors
// (`anchorLevels`), anchored where `anchored` says its boxes will be and every frame's
// holder can be, else where the window holds them, and answers how its boxes stand
// (`standBox`): anchored, or written from `origin`, the client point the carrier's
// corner stands at. It reads neither style nor layout, so a pass can stand many stands
// after its writes begin.
function standIn(stand, placed, anchored) {
  const { levels } = placed;
  anchored &&= levels.every(({ holder, anchor }) => !holder || anchor !== null);
  stand.anchored = anchored;
  stand.frames = cutFrames(
    levels.map(({ anchor, at, reading, band, axes }) => ({
      anchor: anchored ? anchor : null,
      at: anchored ? at : null,
      reading: anchored ? reading : null,
      band,
      axes,
    })),
    stand.frames.map(({ frame }) => frame),
    makeFrame,
  );
  const outer = stand.frames[0]?.frame;
  if (outer && outer.parentNode !== stand.root) move(stand.root, outer, null);
  const inner = stand.frames.at(-1)?.frame ?? stand.root;
  if (stand.carrier.parentNode !== inner) move(inner, stand.carrier, null);
  const band = levels.at(-1)?.band;
  return anchored
    ? { anchored: true, origin: null }
    : { anchored: false, origin: { x: band?.left ?? 0, y: band?.top ?? 0 } };
}

// Stands `box` over `rect` in a stand `stood` answered: anchored to `anchor`, read at
// `at` as `rect` was, or from `stood.origin`, the client point its containing frame's
// corner stands at. Without a size, `rect` is a point, the box's corner, and the box
// keeps its own size.
export function standBox(
  box,
  rect,
  stood,
  anchor = null,
  at = anchor && anchorBox(anchor),
) {
  if (stood.anchored) {
    anchorAt(box, anchor, rect, at, stood.visibility ?? "always");
    return;
  }
  Object.assign(box.style, {
    position: "",
    positionAnchor: "",
    positionVisibility: "",
    left: layoutPx(rect.left - stood.origin.x),
    top: layoutPx(rect.top - stood.origin.y),
    ...(rect.right === undefined
      ? {}
      : {
          width: layoutPx(rect.right - rect.left),
          height: layoutPx(rect.bottom - rect.top),
        }),
  });
}

// Stands `stand`'s frames over `placed`, anchored to its surface where the anchor
// reaches, and answers how a box in it stands (`standBox`) with the anchor and where it
// was read.
export function standAt(stand, placed) {
  const anchor = anchoredBy(placed.surface, stand.root);
  const at = anchor && anchorBox(anchor);
  const levels = anchorLevels(placed.levels, stand.root);
  return { ...standIn(stand, { levels }, Boolean(anchor)), anchor, at };
}

// A set of paint boxes, each over a target and standing in the frames that cut it
// (`placement`), anchored to it where the anchor reaches (`anchoredBy`), the boxes the
// same frames cut sharing a stand, so no scroll writes any of them. A box not `cut`, as
// a chip hung off its target's corner wherever the room around it seats it, or ink
// still being drawn past its target's edge, is cut by no scroller's edge where it is
// anchored, and hides once its target is scrolled out of sight (`position-visibility:
// var(--lf-anchor-visible)`, tokens.css); it still passes under the sticky headers declared over its target
// (dom/geometry.js, `headerCuts`), as every box following scrolled content does. A box
// with no target stands where the window holds it.
//
// Only a box whose target is near (dom/geometry.js, `nearWindow`) is in the document.
// `onNear` hears where that changed, once the boxes come near are seated.
//
// `place` takes every box of the set, in paint order, each `{ node, target, rect }`:
// `rect` in client coordinates, a point for a box that keeps its own size, or a
// function of the target's placement, which is the default. `held` places paint over
// what the target holds, cut by its own band too, `anchor` names what carries the box
// where that is not the target's own anchor, `plane` the stacking its stand takes
// (`data-lf-paint-plane`), the page's unless it says otherwise, and `cut: false` that
// no frame cuts it. It reads every box's geometry and
// anchor before it writes any, and the names those anchors need before it gives any,
// since reading an author's name after a write forces the style that write
// invalidated. It answers each box's placement, null where it stands nowhere.
export function paintSet(root, { onNear = () => {} } = {}) {
  const stands = new Map(); // key → stand
  const entries = new Map(); // node → how it stands
  // Each target is watched through the box it anchors by, which a target with no box
  // of its own has in its first shown part (`anchorElement`).
  const near = new Set(); // targets
  const watched = new Map(); // target → the box watched for it
  const watching = new Map(); // box → the targets it is watched for
  const nearBy = (target) => !target || near.has(target);
  const view = nearObserver((records) => {
    const moved = new Set();
    for (const { target: box, isIntersecting } of records)
      for (const target of watching.get(box) ?? []) {
        if (isIntersecting) near.add(target);
        else near.delete(target);
        moved.add(target);
      }
    for (const stand of stands.values())
      if (stand.members.some(({ target }) => moved.has(target))) seat(stand);
    onNear();
  });

  // A stand's key: the frames that cut it, each band from its holder's corner, which no
  // scroll moves, whether they are anchored, and the plane it stands in.
  const idOf = objectIds();
  const keyOf = ({ surface, levels }, anchor, plane, framed) =>
    !surface
      ? `${plane}|window`
      : [
          plane,
          framed ? "cut" : "open",
          anchor ? "anchored" : "window",
          ...levels.map(({ holder, band, from, axes }) => {
            const edges = [from.left, from.top, from.left + band.right - band.left];
            return `${holder ? idOf(holder) : "window"}:${[...edges, from.top + band.bottom - band.top]}:${axes.x}${axes.y}`;
          }),
        ].join("|");

  // A stand's boxes in its carrier in order, those whose target is near, the rest out of
  // the document. Each box seated here, every near one for a pass, is written.
  function seat(stand, all = false) {
    const { carrier, members } = stand;
    const seating = new Set(
      members.filter(
        ({ node, target }) => nearBy(target) && (all || node.parentElement !== carrier),
      ),
    );
    const readings = [...seating].flatMap(({ entry }) =>
      entry.anchor ? [anchorReading(entry.anchor)] : [],
    );
    for (const reading of readings) nameAnchor(reading);
    let cursor = carrier.firstElementChild;
    for (const member of members) {
      const { node, target, entry } = member;
      if (!nearBy(target)) {
        if (node.parentElement !== carrier) continue;
        if (cursor === node) cursor = node.nextElementSibling;
        node.remove();
        continue;
      }
      if (cursor === node) cursor = node.nextElementSibling;
      else move(carrier, node, cursor);
      if (seating.has(member))
        standBox(node, entry.rect, entry.stood, entry.anchor, entry.at);
    }
  }

  function place(items, clips = new Map()) {
    const holders = new Map();
    const holderAnchors = new Map();
    const targets = new Set();
    const read = items.map((item) => {
      const { node, held = false, anchor, plane = "page" } = item;
      const { cut: framed = true } = item;
      if (!item.target) {
        const placed = { surface: null, levels: [] };
        return {
          node,
          target: null,
          placed,
          rect: item.rect,
          plane,
          framed,
          anchor: null,
          at: null,
          key: keyOf(placed, null, plane, framed),
        };
      }
      const target = item.target;
      const rect = item.rect;
      targets.add(target);
      // A target with no box of its own stands where its parts do (`shownBox`).
      let placed = placement(target, false, clips, held);
      const { left, top, right, bottom } = placed.rect;
      if (!(right > left && bottom > top)) return { node, target, placed: null };
      const box = typeof rect === "function" ? rect(placed) : (rect ?? placed.rect);
      // Until the observer's first answer, near is read off the box itself, so a set's
      // first paint draws what it shows.
      if (!watched.has(target)) {
        const box = anchorElement(target);
        watched.set(target, box);
        let observed = watching.get(box);
        if (!observed) {
          observed = new Set();
          watching.set(box, observed);
          view.observe(box);
        }
        observed.add(target);
        if (nearWindow(target, clips)) near.add(target);
      }
      const carriedBy =
        anchor === undefined
          ? anchoredBy(target, root)
          : anchor && anchorReaches(anchor, root)
            ? anchor
            : null;
      // A box no scroller's edge cuts is carried by its anchor alone, under the frames
      // its target's headers cut.
      if (!framed)
        placed = {
          ...placed,
          levels: headerCuts(target, clips).map(({ box, band }) => ({
            holder: box === box.ownerDocument.scrollingElement ? null : box,
            band: band ?? { left: 0, top: 0, right: 0, bottom: 0 },
            axes: { x: false, y: true },
          })),
        };
      // Capture each holder's reading, and the anchor carrying its frame, with the
      // level it positions, each read once a pass.
      const levels = anchorLevels(placed.levels, root, holderAnchors).map((level) => {
        let at;
        if (level.holder) {
          at = holders.get(level.holder);
          if (!at) {
            at = level.holder.getBoundingClientRect();
            holders.set(level.holder, at);
          }
        } else at = { left: 0, top: 0 };
        return {
          ...level,
          from: { left: level.band.left - at.left, top: level.band.top - at.top },
        };
      });
      const placedLevels = { ...placed, levels };
      return {
        node,
        target,
        placed: placedLevels,
        rect: box,
        plane,
        framed,
        anchor: carriedBy,
        at: carriedBy && anchorBox(carriedBy),
        key: keyOf(placedLevels, carriedBy, plane, framed),
      };
    });
    for (const [target, box] of watched)
      if (!targets.has(target)) {
        watched.delete(target);
        near.delete(target);
        const observed = watching.get(box);
        observed?.delete(target);
        if (observed?.size) continue;
        watching.delete(box);
        view.unobserve(box);
      }
    // The writes: each stand's frames, in the order its first box comes, then each box
    // in its stand.
    const stood = new Map();
    let previous = null;
    for (const item of read) {
      if (!item.placed) continue;
      const { placed, key, anchor, plane, framed } = item;
      if (stood.has(key)) continue;
      const stand = stands.get(key) ?? { ...paintStand(), members: [] };
      stands.set(key, stand);
      keeps(stand.root, "data-lf-paint-plane", plane);
      const next = previous ? previous.root.nextElementSibling : root.firstElementChild;
      if (next !== stand.root) move(root, stand.root, next);
      const how = standIn(stand, placed, Boolean(anchor));
      stood.set(key, {
        stand,
        how: { ...how, visibility: framed ? "always" : "var(--lf-anchor-visible)" },
      });
      previous = stand;
    }
    for (const [key, stand] of stands)
      if (!stood.has(key)) {
        dropStand(stand);
        stands.delete(key);
      }
    for (const stand of stands.values()) stand.members = [];
    const placing = new Set();
    for (const item of read) {
      const { node, target } = item;
      placing.add(node);
      const standing = item.placed ? stood.get(item.key) : null;
      if (!item.placed || !standing) {
        node.remove();
        entries.set(node, null);
        continue;
      }
      const { stand, how } = standing;
      const { rect, anchor, at } = item;
      if (entries.get(node)?.stand !== stand) node.remove();
      const entry = { stand, stood: how, rect, anchor, at };
      entries.set(node, entry);
      stand.members.push({ node, target, entry });
    }
    for (const node of entries.keys())
      if (!placing.has(node)) {
        node.remove();
        entries.delete(node);
      }
    for (const stand of stands.values()) seat(stand, true);
    return read.map(({ placed }) => placed);
  }

  function clear() {
    for (const stand of stands.values()) dropStand(stand);
    for (const node of entries.keys()) node.remove();
    stands.clear();
    entries.clear();
    near.clear();
    watched.clear();
    watching.clear();
    view.disconnect();
  }

  return {
    place,
    clear,
    // Whether `target`'s boxes stand in the document, near enough to be shown.
    near: nearBy,
    // Whether `node` stands in the set, near or not.
    stands: (node) => Boolean(entries.get(node)?.stand),
  };
}

// A stand whose box is put away keeps no frames, which would hold the scrollers they are
// anchored to after a revision removed them.
function dropStand(stand) {
  stand.frames = cutFrames(
    [],
    stand.frames.map(({ frame }) => frame),
    makeFrame,
  );
  stand.root.remove();
}

// Where a paint box stands over `surface`, and what cuts it, for paint stacked
// `aboveSurfaces` (`data-lf-paint-plane`) or under them: `rect` is the surface's box,
// and `shown` the part of it no cut hides, null where the cuts hide all of it. `levels`
// are the frames that cut it, outermost first, each with the box `holder` whose band it
// is, none for the window's. `clips` is the clip walk's cache, shared by a pass that
// places many. Paint over what `surface` holds (`held`), as words standing in it, is cut
// by its own band as well.
export function placement(surface, aboveSurfaces, clips = new Map(), held = false) {
  const { left, top, right, bottom } = shownBox(surface);
  const rect = { left, top, right, bottom };
  const cuts = paintClips(surface, rect, clips, aboveSurfaces, held);
  const levels = [];
  if (cuts.window)
    levels.push({ band: cuts.window, axes: { x: true, y: true }, holder: null });
  for (const { box: holder, band, axes } of cuts.bands)
    levels.push({ band, axes, holder });
  let shown = rect;
  for (const { band, axes } of levels) shown = intersect(shown, band, axes);
  return {
    rect,
    shown: hasArea(shown) ? shown : null,
    levels,
    surface,
    plane: cuts.plane,
  };
}
