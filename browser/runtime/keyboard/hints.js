/* The transient keyboard hint session, and the code and placement policy under it.

   Two vocabularies stand on this one interaction: the Go-to sequence's map of visible
   page targets, and the target picker's map of addressable elements. Arming reads a
   scene, gives each member an opaque prefix-free code, and paints a chip on it. Typed
   letters narrow the map, Tab walks it aloud, Enter takes the one just heard, and
   Escape gives a letter back. A letter that names nothing is reported and the current
   map is left alone, because a mistyped route should not cost the user the letters
   they had right. A scroll holds the map as it stands, each chip riding with what it
   names, and the map is read and seated again once the scroll settles, so a target
   arriving mid-scroll is named at rest rather than on the frame it appears.
   A candidate is revalidated against a fresh reading before it is taken, so a target
   that left the scene cannot be worked by a stale label. Disabled character routes
   remove their chips and spoken codes; the target inventory and Tab/Enter walk remain.

   What the members are, what a chip says, what taking one does, and where chrome stands
   belong to the caller. Everything above is here once.

   A hint code is generated from a caller-owned alphabet. Replacing one leaf with all of
   its children keeps the result prefix-free while leaving most targets on one letter;
   only the tail branches when a scene contains more targets than the alphabet. The
   placement pass spreads colliding chips apart, side by side further apart than a
   code's own keycaps, but only to seats where each still reads as its own target's
   (`seatHints`): a chip standing beside another target names
   that one, and its press would act on the wrong thing. In a list of rows shorter than
   a chip, every other row's corner chip steps out a column, level with its row, so every
   row keeps a chip where there is room beside the list. A chip with no seat at all is
   withheld, as is each chip of a run of targets side by side too narrow to tell apart,
   and its member stays in the map, which the walk still reaches aloud. Where
   seating in page order would withhold the chip the walk is on, that chip is seated
   first, so it shows wherever its target leaves room for one. A withheld chip's code
   still takes it, as every member's does. Until 11 November 2026 every chip was shown,
   moved up or down as far as a free seat lay, so a crowded column's chips slid rows
   past their targets. Geometry belongs to each caller and is passed in so this module
   introduces no ownership cycle through its callers. */
import { bindingEnabled, cycledRow, hasRows, spell } from "./bindings.js";
import { html, render } from "/runtime/framework.js";
import { keySequenceModel, keySequenceTemplate } from "./key-sequence.js";
import { clamp, overlaps, overlapsAcross } from "../rect.js";
import { chipSeats } from "./chip-seats.js";
import { layoutWindow } from "../geometry.js";
import { scrolling, watchScrollEnds } from "../arrivals.js";
import { announce } from "../notifications.js";
import { repaint } from "../repaint.js";
import { beginWalk, listWalkPosition } from "../walk-position.js";

/** @typedef {import("../rect.js").Box & {held?: boolean}} HintBarrier */
/** @typedef {import("../rect.js").Box & {width: number, height: number, held?: boolean, clippedTop?: boolean}} HintBox
 * @typedef {"corner" | "before" | "above"} HintPlacement
 * @typedef {{start: HintBox, target: HintBox, placement?: HintPlacement}} HintFace
 */

export const HINT_KEYS = [..."asdfghjklqwertyuiopzxcvbnm"];

/** Associate every member with its prefix-free address. Expansion replaces the last
 * shortest leaf, so earlier short addresses remain stable as the map grows.
 * @template {object} T @param {readonly T[]} members @param {string} [alphabet] */
export function codedHints(members, alphabet = HINT_KEYS.join("")) {
  const radix = alphabet.length;
  let depth = 1;
  let shallow = radix;
  let leaves = radix;
  while (leaves < members.length) {
    if (shallow === 0) {
      depth += 1;
      shallow = leaves;
    }
    shallow -= 1;
    leaves += radix - 1;
  }
  /** @param {number} value @param {number} digits */
  const code = (value, digits) => {
    let address = "";
    for (let at = 0; at < digits; at += 1) {
      address = alphabet.charAt(value % radix) + address;
      value = Math.floor(value / radix);
    }
    return address;
  };
  return members.map((member, index) => ({
    ...member,
    code:
      index < shallow
        ? code(index, depth)
        : code(shallow + Math.floor((index - shallow) / radix), depth) +
          alphabet.charAt((index - shallow) % radix),
  }));
}

// Lit sees only an opaque primitive. The native row or target remains controller state,
// while an unchanged owner retains its seat, chip and keycaps across paint-only updates.
export function renderKeys() {
  /** @type {WeakMap<object, number>} */
  const keys = new WeakMap();
  let next = 1;
  /** @param {object} owner */
  return (owner) => {
    let key = keys.get(owner);
    if (key === undefined) {
      key = next++;
      keys.set(owner, key);
    }
    return key;
  };
}

/** @param {HintBox} box @param {number} left @param {number} top @returns {HintBox} */
const movedTo = (box, left, top) => ({
  left,
  right: left + box.width,
  top,
  bottom: top + box.height,
  width: box.width,
  height: box.height,
});

/** @param {import("../rect.js").Box} one @param {import("../rect.js").Box} other */
const sameBox = (one, other) =>
  one.left === other.left &&
  one.top === other.top &&
  one.right === other.right &&
  one.bottom === other.bottom;
/** @param {readonly import("../rect.js").Box[]} some @param {readonly import("../rect.js").Box[]} others */
const sameBoxes = (some, others) =>
  some.length === others.length &&
  some.every((box, index) => {
    const other = others[index];
    return other !== undefined && sameBox(box, other);
  });

// Of the preferred top, the window's edges and the tops just clear of each barrier, the
// open one nearest `preferred` that `admits`, and what decided it: the window's edge, a
// barrier the seat stands clear of, or nothing where the preferred top is open. None
// where none of those is admitted.
/** @param {HintBox} box @param {number} preferred @param {HintBarrier[]} barriers @param {number} top @param {number} bottom @param {number} gap @param {(top: number) => boolean} admits */
function nearestOpenTop(box, preferred, barriers, top, bottom, gap, admits) {
  const last = Math.max(top, bottom - box.height);
  /** @type {{at: number, by: null | "edge" | HintBarrier}[]} */
  const seats = [
    { at: preferred, by: null },
    { at: top, by: "edge" },
    { at: last, by: "edge" },
  ];
  for (const barrier of barriers)
    seats.push(
      { at: barrier.bottom + gap, by: barrier },
      { at: barrier.top - gap - box.height, by: barrier },
    );
  return seats
    .map(
      /** @returns {{at: number, by: null | "edge" | HintBarrier}} */ ({ at, by }) => {
        const held = clamp(at, top, last);
        return { at: held, by: held === at ? by : "edge" };
      },
    )
    .filter(
      ({ at }) =>
        admits(at) &&
        !barriers.some((barrier) => overlaps(movedTo(box, box.left, at), barrier)),
    )
    .sort(
      (left, right) => Math.abs(left.at - preferred) - Math.abs(right.at - preferred),
    )[0];
}

// Read every face before seating one, keeping the pass to one layout. Callers put every
// chip in its seat first and provide the visible rectangle each chip names and the
// place `at` its seat is drawn from; each face is read there, and the answer is where
// each seat stands (chip-seats.js), its `box` a barrier for a following pass. A chip
// withheld for want of a seat that reads as its target's stays where it was drawn,
// hidden rather than removed, so a pass that changes nothing writes nothing.
// `placement` chooses the corner, before or above the target (`seatHints`).
/** @param {ReturnType<typeof chipSeats>} seats
 * @param {{seat: HTMLElement, at: {left: number, top: number}, target: HintBox, placement?: HintPlacement, element: Element | null, browsed: boolean}[]} hints
 * @param {{barriers: HintBarrier[]}} options */
function spreadHints(seats, hints, { barriers }) {
  const band =
    parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue("--focus-ring-w"),
    ) || 0;
  const faces = hints.map((hint) => {
    const { chip, box: start } = seats.measure(hint.seat, hint.at);
    return {
      start,
      chip,
      target: hint.target,
      ...(hint.placement === undefined ? {} : { placement: hint.placement }),
      hint,
    };
  });
  const browsed = faces.find(({ hint }) => hint.browsed);
  const seated = seatHints(faces, {
    barriers,
    band,
    viewport: layoutWindow(),
    browsed,
  });
  return seated.map(({ face, box }) => {
    if (box) face.chip.style.removeProperty("visibility");
    else face.chip.style.visibility = "hidden";
    return {
      seat: face.hint.seat,
      target: face.hint.element,
      at: face.hint.at,
      start: face.start,
      box: box ?? face.start,
      held: Boolean(box?.held || face.target.clippedTop),
      withheld: !box,
    };
  });
}

// Whether `outer` encloses `inner` and is larger across or down: an equal box is the same
// place rather than a box around it.
/** @param {import("../rect.js").Box} outer @param {import("../rect.js").Box} inner */
const encloses = (outer, inner) =>
  outer.left <= inner.left &&
  outer.top <= inner.top &&
  outer.right >= inner.right &&
  outer.bottom >= inner.bottom &&
  (outer.right - outer.left > inner.right - inner.left ||
    outer.bottom - outer.top > inner.bottom - inner.top);

// How far out of its target each before seat stands, beyond its own width and the gap.
// Chips before nested targets that share a left edge would stand in one flush column,
// leaving nothing to say which names the group and which each member, so a before seat
// steps out once for each level of nesting it has below the deepest before seat in its
// own tree, the targets its outermost enclosing target holds: every chip stands right of
// the chips of the targets around it, the deepest stand where they would alone, none
// crosses into its own target, and a target in no nest keeps its chip beside it. The
// step narrows to fit the outermost chips in the room the window leaves, down to a floor
// below which the levels would not read as distinct; past it the window clamps them. A
// chip the window clamps already has no room, so it does not narrow everyone else's.
const NEST_STEP = 10;
const NEST_FLOOR = 4;
/** @template {HintFace} T
 * @typedef {{face: T, ancestors: HintNest<T>[], root: () => HintNest<T>, deepest: number}} HintNest */
/** @template {HintFace} T @param {readonly T[]} faces @param {(face: T) => number} room */
function nestOutsets(faces, room) {
  const records = faces.map(
    /** @returns {HintNest<T>} */ (face) => ({
      face,
      ancestors: [],
      deepest: 0,
      root() {
        return this.ancestors.find((parent) => !parent.ancestors.length) ?? this;
      },
    }),
  );
  const before = records.filter(({ face }) => face.placement === "before");
  for (const record of before)
    record.ancestors = before.filter(
      (other) => other !== record && encloses(other.face.target, record.face.target),
    );
  for (const record of before) {
    const root = record.root();
    root.deepest = Math.max(root.deepest, record.ancestors.length);
  }
  const levels = records.map((record) => ({
    face: record.face,
    level:
      record.face.placement === "before"
        ? record.root().deepest - record.ancestors.length
        : 0,
  }));
  const fits = levels.flatMap(({ face, level }) => {
    const fit = level ? room(face) / level : 0;
    return fit > 0 ? [fit] : [];
  });
  const step = Math.floor(clamp(Math.min(NEST_STEP, ...fits), NEST_FLOOR, NEST_STEP));
  return levels.map(({ face, level }) => ({ face, outset: level * step }));
}

// Where each face stands, folded from rectangles `spreadHints` has already read. Each
// face is `{ start, target, placement }`, `start` the box it was drawn at; the answer
// is one box per face, in order, each clear of the barriers and every face seated
// before it, or null for a face withheld because no such seat reads as its target's.
// A box is `held` where what decided its seat stands still as the page scrolls, the
// window's edge or a fixed barrier, rather than its target or a face riding with its
// own, so the window holds it where a scroll carries the rest. `browsed` is the face a
// walk is on, if any.
/** @template {HintFace} T @param {readonly T[]} faces @param {{barriers?: HintBarrier[], band: number, viewport: import("../rect.js").Box, browsed?: T | undefined}} options */
export function seatHints(
  faces,
  { barriers: fixedBarriers = [], band, viewport, browsed },
) {
  const gap = 2;
  const targets = faces.map(({ target }) => target);
  // The browsed hint wears the layer's band (--focus-shadow, styles/tokens.css), which a face's
  // own rectangle does not report. Any chip can become the browsed one as the user
  // types, so the pass seats every face as though it were, keeping the one layout. A
  // window edge takes the whole band, because a band drawn past it is clipped away. A
  // barrier — another face, or the chrome — takes the wider of the gap and the band,
  // because a band may stand in the gap it keeps but not past it; only the browsed chip
  // paints one, so it has that space to itself. Seated to the gap alone both cleared by
  // coincidence, the gap and the band both being 2px.
  const clear = Math.max(gap, band);
  // Side by side, two chips stand `apart`, well clear of the 1px between one code's own
  // keycaps (`.lf-binding-sequence`, chrome.css), so a row of two-letter chips reads as
  // codes: touching, `na` and `ng` read as `n a n g`. Stacked chips keep only `clear`,
  // since a code reads across. Until 14 November 2026 chips could touch side by side.
  const apart = 6;
  /** @param {HintBox} box @returns {HintBox} */
  const widened = (box) => ({
    ...box,
    left: box.left - apart,
    right: box.right + apart,
  });
  const edgeLeft = viewport.left + band;
  const edgeTop = viewport.top + band;
  const edgeRight = viewport.right - band;
  const edgeBottom = viewport.bottom - band;
  /** @param {HintFace} face */
  const beforeLeft = ({ start, target }) => target.left - start.width - clear;
  // Whether a chip at `seat` reads as its own target's, the one test every seat a chip
  // takes passes. Off its own target, a chip reads as any other target that stands
  // between its middle and its own target, its middle included, as a seat before a
  // button does on the button to its left, or one stepped out of a column does on a
  // target beside the column. And it reads as the target whose rows are nearest its
  // middle among those in its column or its own target's, as in a list or a stack of
  // controls; ties stand, as where a corner chip straddles two rows or two targets share
  // an edge. A target around its own competes with neither, since its chip stands
  // a step out (`nestOutsets`). So a chip in the gutter between two cards, level with its
  // own target's first line, reads as its own though the other card's edge is nearer its
  // middle. Nor may it stand further above or below its target than one more chip would
  // fill, as a chip pushed past two others stacked over its target would.
  /** @param {HintBox} seat @param {HintFace} face */
  const readsAs = (seat, face) => {
    const own = face.target;
    if (Math.max(own.top - seat.bottom, seat.top - own.bottom) > seat.height + clear)
      return false;
    const x = (seat.left + seat.right) / 2;
    const y = (seat.top + seat.bottom) / 2;
    /** @param {import("../rect.js").Box} rows */
    const off = (rows) => Math.max(rows.top - y, y - rows.bottom, 0);
    // The stretch from the chip's middle to the nearest point of its own target.
    const near = { x: clamp(x, own.left, own.right), y: clamp(y, own.top, own.bottom) };
    /** @param {import("../rect.js").Box} box */
    const between = (box) =>
      box.left < Math.max(x, near.x) &&
      box.right > Math.min(x, near.x) &&
      box.top < Math.max(y, near.y) &&
      box.bottom > Math.min(y, near.y);
    const onOwn = near.x === x && near.y === y;
    return targets.every(
      (target) =>
        sameBox(target, own) ||
        encloses(target, own) ||
        ((onOwn || !between(target)) &&
          (!(overlapsAcross(target, own) || overlapsAcross(target, seat)) ||
            off(target) >= off(own))),
    );
  };
  // A before seat stands level with its target's first line, so in a list of short rows
  // each chip reads as its own row's rather than the boundary with the row above.
  /** @param {HintFace} face */
  const level = ({ start, target }) =>
    target.top + (Math.min(target.height, 2 * start.height) - start.height) / 2;
  // A corner chip hangs half above its target, which reads as the target's while the
  // target runs on below it. In a list of rows shorter than a chip, it covers the row
  // above as much as its own, so wherever two rows' corner chips would collide, each
  // stands level with its own row instead (`level`). Rows sharing a column and no line
  // are neighbours; a target beside another shares neither and keeps its corner.
  /** @param {HintFace} face */
  const corner = (face) => (face.placement ?? "corner") === "corner";
  // A target narrower than a key, with another as narrow beside it on its line less than
  // a key away, as a film's slots in a narrow window or adjacent footnote markers are,
  // gets no chip: no seat beside it says which of the run it names, and chips for a whole
  // run bury it. A narrow target beside a wide one, as an icon beside a field, keeps its
  // chip. Its member stays in the map, so its code still takes it and a walk onto it
  // shows its chip. A key is a chip's height, one keycap. Rows stacked one under another,
  // as in a contents list, share no line and keep their chips. Until 14 November 2026
  // such a run's chips stacked or scattered around it.
  /** @param {HintFace} face */
  const bunched = ({ start, target }) =>
    target.width < start.height &&
    targets.some(
      (other) =>
        other !== target &&
        other.width < start.height &&
        !sameBox(other, target) &&
        !encloses(other, target) &&
        !encloses(target, other) &&
        other.top < target.bottom &&
        target.top < other.bottom &&
        Math.max(other.left - target.right, target.left - other.right) < start.height,
    );
  /** @param {import("../rect.js").Box} one @param {import("../rect.js").Box} other */
  const rowNeighbours = (one, other) =>
    overlapsAcross(one, other) && (one.bottom <= other.top || other.bottom <= one.top);
  const crowded = new Set(
    faces.filter(
      (face) =>
        corner(face) &&
        targets.some(
          (target) =>
            target !== face.target &&
            rowNeighbours(face.target, target) &&
            Math.abs(target.left - face.target.left) < face.start.width &&
            Math.abs(target.top - face.target.top) < face.start.height,
        ),
    ),
  );
  // A crowded column's chips stand in columns as wide as its widest chip, each at its
  // column's left edge, so where codes grow from one letter to two, neither column's
  // edge moves.
  /** @param {T} face */
  const columnWidth = (face) =>
    Math.max(
      ...faces
        .filter(
          (other) =>
            crowded.has(other) &&
            Math.abs(other.target.left - face.target.left) < face.start.width,
        )
        .map(({ start }) => start.width),
    );
  // Each face stands in the first seat its placement offers that reads as its own
  // target's where the window lets it stand. An owner's chip stands before its target,
  // and above it where the seat before reads as a neighbour's, as in a row of cards; a
  // control's stands above, and before it where the seat above is a neighbour's. Both
  // seats stand outside the target, so one the window pushes onto its own target is
  // neither. Where neither reads as its own, as in a grid of buttons, the chip stands on
  // its target's corner, as every Go-to chip does.
  const measured = nestOutsets(faces, (face) => beforeLeft(face) - edgeLeft).map(
    ({ face, outset }) => {
      const { start, target } = face;
      /** @param {{left: number, top: number}} at */
      const inWindow = ({ left, top }) =>
        movedTo(
          start,
          clamp(left, edgeLeft, Math.max(edgeLeft, edgeRight - start.width)),
          clamp(top, edgeTop, Math.max(edgeTop, edgeBottom - start.height)),
        );
      const before = { left: beforeLeft(face) - outset, top: level(face) };
      const above = { left: target.left, top: target.top - start.height - clear };
      const outside = {
        before: [before, above],
        above: [above, before],
        corner: [],
      }[face.placement ?? "corner"].find((at) => {
        const seat = inWindow(at);
        return !overlaps(seat, target) && readsAs(seat, face);
      });
      const column = crowded.has(face) ? columnWidth(face) : start.width;
      const at = outside ?? {
        left: start.left + (start.width - column) / 2,
        top: crowded.has(face) ? level(face) : start.top,
      };
      const seated = inWindow(at);
      return {
        face,
        seated,
        ownTarget: outside ? target : null,
        clamped: seated.left !== at.left || seated.top !== at.top,
        column,
      };
    },
  );
  // Faces are seated in turn, each clear of those before it, so the order decides which
  // of two crowded chips steps out or is withheld.
  /** @param {typeof measured} order */
  const seatInTurn = (order) => {
    /** @type {Map<T, HintBox | null>} */
    const placed = new Map();
    for (const face of order) placed.set(face.face, seatOne(face, placed));
    return placed;
  };
  /** @param {typeof measured[number]} measuredFace @param {Map<T, HintBox | null>} placed */
  const seatOne = ({ face, seated, ownTarget, clamped, column }, placed) => {
    if (face !== browsed && bunched(face)) return null;
    /** @param {HintBox} seat */
    const barriersAcross = (seat) => [
      ...fixedBarriers.filter((other) => overlapsAcross(other, seat)),
      ...[...placed.values()].flatMap((box) =>
        box && overlapsAcross(widened(box), seat) ? [widened(box)] : [],
      ),
    ];
    const barriers = barriersAcross(seated);
    /** @param {HintBarrier[]} around */
    const openTop = (around) =>
      nearestOpenTop(seated, seated.top, around, edgeTop, edgeBottom, clear, (top) =>
        readsAs(movedTo(seated, seated.left, top), face),
      );
    // An outside seat keeps off its own target where the column leaves it room, and
    // stands on it where the target fills the room, as a block at the window's left
    // edge does: on its own target, a chip names nothing else.
    /** @returns {HintBox | null} */
    const moved = () => {
      const open =
        (ownTarget && overlapsAcross(ownTarget, seated)
          ? openTop([...barriers, ownTarget])
          : null) ?? openTop(barriers);
      if (!open) return null;
      const box = movedTo(seated, seated.left, open.at);
      // Below a face the window holds, the window holds this one too.
      const by = open.by;
      box.held =
        clamped ||
        by === "edge" ||
        fixedBarriers.some((barrier) => barrier === by) ||
        (typeof by === "object" && Boolean(by?.held));
      return box;
    };
    // A crowded row's chip that finds its own seat taken steps out to the left, a column
    // at a time, still level with its row, so every other row's chip stands a column
    // out. Where the window leaves no column, it is withheld rather than moved up or
    // down, which would leave it between its row and the next, whose own chip is then
    // further off.
    /** @returns {HintBox | null} */
    const levelled = () => {
      for (const step of [0, 1, 2]) {
        const left = seated.left - step * (column + apart);
        if (left < edgeLeft) break;
        const seat = movedTo(seated, left, seated.top);
        if (
          !barriersAcross(seat).some((barrier) => overlaps(seat, barrier)) &&
          readsAs(seat, face)
        )
          return Object.assign(seat, { held: clamped });
      }
      return null;
    };
    return crowded.has(face) ? levelled() : moved();
  };
  // The chip a walk is browsing wears its band where the user is, so where page order
  // would withhold it, the map is seated again with it first. Only then: seated first
  // everywhere, it would move a crowded column's chips to other columns on every Tab.
  let boxes = seatInTurn(measured);
  if (browsed && !boxes.get(browsed))
    boxes = seatInTurn([
      ...measured.filter(({ face }) => face === browsed),
      ...measured.filter(({ face }) => face !== browsed),
    ]);
  return faces.map((face) => ({ face, box: boxes.get(face) ?? null }));
}

/* One armed map over a caller's scene.

   Membership and seating are separate readings, and the difference is how often each is
   taken. `read` answers which members the map holds and what codes name them, each
   member already carrying its `code` because the codes are the caller's, so `kept` and a
   typed letter narrow the map without recoding it; that answer is held until something
   invalidates it. `layout`
   answers where those members are, from one `scene` reading for every member a paint
   seats, because a chip's place among its neighbours and its own box are the same
   measurement: derived from different readings they put the chip where neither reading
   said. `identity` names the element a walk and a re-read recognize a member by.
   `kept` narrows the map to the members a caller's filter keeps, as a typed letter
   narrows it to the codes that begin with it.

   Seats belong to the whole map. A paint that seats chips seats every member's, and
   narrowing the map, by a letter or by `kept`, hides the chips it rules out and moves
   none, so the chips the user is reading stay where they stood. A walk holds the seats
   too, except where it reaches a withheld chip, which seats the map again with that chip
   first (`seatHints`, `browsed`). The map is seated again on a new reading, once a
   scroll settles, on a resize, and when the caller invalidates it.

   `chrome.barriers` reads the fixed furniture the placement pass must keep clear.
   A map stands through a scroll once it has stood still long enough to be read: its
   chips ride with the things they name (chip-seats.js), so the codes the user is
   reading stay where they were read and stay pressable, while membership and seats
   wait for the scene to settle. A map armed into a page already in flight has stood
   still for nobody, and shows nothing until it settles rather than putting codes on a
   scene that is leaving. */
/** @template {{code: string}} C
 * @template R
 * @template {{key: unknown, className: string}} M
 * @typedef {{layer: HTMLElement, walk: string, read: () => C[], identity: (candidate: C) => Element,
 * kept?: (candidate: C) => boolean,
 * scene: () => R, layout: (candidates: C[], options: {current: C | undefined, reading: R}) => {candidate: C, model: M, left: number, top: number, target: HintBox, placement: HintPlacement}[],
 * template: (model: M) => unknown, take: (candidate: C) => unknown,
 * words: {describe: (candidate: C) => string, take: string, all: string}, chrome: {barriers: () => HintBarrier[]}}} HintSessionOptions
 */
/** @template {{code: string}} C @template R @template {{key: unknown, className: string}} M
 * @param {HintSessionOptions<C, R, M>} options */
export function createHintSession({
  layer,
  walk: walkKey,
  read,
  identity,
  kept = () => true,
  scene,
  layout,
  template,
  take: takeCandidate,
  words,
  chrome,
}) {
  let armed = false;
  let prefix = "";
  /** @type {C[]} */
  let candidates = [];
  // Where the audible walk stands in `hinted()`, or -1 when no hint has been heard.
  let at = -1;
  let stale = false;
  // The members `kept` keeps, taken when the map is read or `kept` changes.
  /** @type {C[]} */
  let mapped = [];
  // What the seats were measured against, until a new reading or a settled scroll: each
  // seated member's target and the chrome's barriers, and the members withheld.
  /** @type {{targets: Map<unknown, HintBox>, barriers: HintBarrier[], withheld: Set<C>} | null} */
  let seating = null;
  const seats = chipSeats(layer);

  const members = () => mapped;
  const hinted = () => mapped.filter(({ code }) => code.startsWith(prefix));
  /** @param {C} candidate */
  const enabled = (candidate) => [...candidate.code].every(bindingEnabled);
  /** @param {{candidate: C}} plan */
  const shown = (plan) => enabled(plan.candidate) || plan.candidate === hinted()[at];
  const nativeTake = keySequenceModel([
    { text: spell("Enter"), keys: [spell("Enter")], state: "neutral", spoken: "Enter" },
  ]);
  /** @param {{candidate: C, model: M}} plan */
  const face = (plan) =>
    plan.candidate && !enabled(plan.candidate)
      ? html`<span
          class=${`lf-key-hint lf-current${plan.model.className.includes(" lf-in") ? " lf-in" : ""}`}
          data-lf-hint-native="Enter"
          >${keySequenceTemplate(nativeTake)}</span
        >`
      : template(plan.model);

  // Every way the map is replaced whole puts the user back at its head, with no letters
  // typed and nothing heard. Whether the page is moving is a fact about the page rather
  // than about the map (arrivals.js, `scrolling`).
  /** @param {C[]} found */
  function hold(found) {
    prefix = "";
    at = -1;
    stale = false;
    seating = null;
    candidates = found;
    mapped = found.filter(kept);
    return found;
  }

  function arm() {
    armed = true;
    return hold(read());
  }

  function disarm() {
    armed = false;
    hold([]);
    seats.clear();
  }

  // What the caller's `kept` keeps has changed, as a filter comes or goes: the map keeps
  // its reading and its seats, and shows the members `kept` keeps with no letters typed.
  // It answers them, for a caller that speaks their number in this press.
  function narrow() {
    prefix = "";
    at = -1;
    mapped = candidates.filter(kept);
    repaint();
    return mapped;
  }

  // The scene the caller reads has changed meaning, as the character routes it may
  // show have: the frame that paints reads it again.
  function invalidate() {
    prefix = "";
    at = -1;
    stale = true;
    seating = null;
    repaint();
  }

  /** @param {C | undefined} candidate */
  function take(candidate) {
    const current = read();
    const found =
      candidate && current.find((one) => identity(one) === identity(candidate));
    if (found) return takeCandidate(found);
    hold(current);
    announce("That target is no longer visible. The hints are reset.");
    repaint();
  }

  /** @param {string} key */
  function type(key) {
    const next = prefix + key;
    if (!members().some(({ code }) => code.startsWith(next))) {
      announce(`No hint ${next}. The current hints are unchanged.`);
      return;
    }
    prefix = next;
    at = -1;
    const complete = hinted().find(({ code }) => code === prefix);
    if (complete) return take(complete);
    announce(`${hinted().length} targets remain.`);
    repaint();
  }

  /** @param {import("./bindings.js").Step} direction */
  function walk(direction) {
    const targets = hinted();
    if (!hasRows(targets)) return;
    // Nothing heard yet, the walk starts at whichever end it walks from.
    const target = cycledRow(targets, targets[at], direction);
    at = targets.indexOf(target);
    beginWalk(walkKey, "Target", () =>
      listWalkPosition(hinted(), hinted()[at], { identity }),
    );
    const said = words.describe(target);
    const stop = /[.!?]$/.test(said) ? "" : ".";
    announce(
      `${enabled(target) ? `Hint ${target.code}: ` : ""}${said}${stop} Press Enter to ${words.take}.`,
    );
    repaint();
  }

  // One letter back, or nothing to give back. The caller's Escape rung continues to its
  // own next step on false.
  function backOneLetter() {
    if (!prefix) return false;
    prefix = prefix.slice(0, -1);
    at = -1;
    announce(prefix ? `Hint ${prefix}.` : words.all);
    repaint();
    return true;
  }

  // The walk's own rows, so both vocabularies offer Tab, Shift+Tab and Enter as one
  // declaration: each caller names them under `id`, says what taking a member does in
  // `choose`, and decides `when` the walk is offered.
  /** @param {{id: string, when?: () => boolean, choose: {description?: string, title: string}}} options @returns {import("./bindings.js").Command[]} */
  function walkRows({ id, when = () => members().length > 0, choose }) {
    return [
      {
        id: `${id}.walk`,
        touch: false,
        keys: ["Tab", "Shift+Tab"],
        routes: [
          { id: `${id}.next`, binding: "Tab", title: "Hear the next visible target" },
          {
            id: `${id}.previous`,
            binding: "Shift+Tab",
            title: "Hear the previous visible target",
          },
        ],
        title: "browse hints",
        repeat: true,
        when,
        runKey: /** @param {string} binding */ (binding) =>
          walk(binding === "Tab" ? 1 : -1),
      },
      {
        id: `${id}.choose`,
        touch: false,
        keys: ["Enter"],
        description: choose.description,
        title: choose.title,
        travels: true,
        when: () => at >= 0,
        run: () => take(hinted()[at]),
      },
    ];
  }

  // Seats every member's chip, whatever narrowing or character routes leave showing,
  // and stands the seats of the chips that show where the seating puts them. Widening
  // the map onto a chip with no seat seats the whole map anew.
  /** @param {ReturnType<typeof layout>} plans */
  function draw(plans) {
    const browsed = hinted()[at];
    const drawn = plans.map((plan) => {
      const seat = seats.seat(plan.model.key);
      render(face(plan), seat);
      return {
        seat,
        element: plan.candidate ? identity(plan.candidate) : null,
        at: { left: plan.left, top: plan.top },
        target: plan.target,
        placement: plan.placement,
        browsed: plan.candidate === browsed,
      };
    });
    // The coded map is spread around the fixed chrome.
    const barriers = chrome.barriers();
    const placed = plans.length ? spreadHints(seats, drawn, { barriers }) : [];
    const showing = new Set(showable(plans));
    seats.place(
      placed.filter((_, index) => {
        const plan = plans[index];
        return plan !== undefined && showing.has(plan);
      }),
    );
    seating = {
      targets: new Map(plans.map(({ model, target }) => [model.key, target])),
      barriers,
      withheld: new Set(
        plans.flatMap(({ candidate }, index) =>
          placed[index]?.withheld ? [candidate] : [],
        ),
      ),
    };
  }

  // The plans whose chips show: those the narrowing keeps, as far as the character
  // routes show them.
  /** @param {ReturnType<typeof layout>} plans */
  function showable(plans) {
    const narrowed = new Set(hinted());
    return plans.filter((plan) => narrowed.has(plan.candidate) && shown(plan));
  }

  // Whether the seats still stand for the whole map's `plans`: every target and the
  // chrome's barriers stand where the seats were measured against them, every chip that
  // shows has a seat, and the walk is not on a withheld chip, which seats the map again
  // with that chip first (`seatHints`, `browsed`).
  /** @param {ReturnType<typeof layout>} plans */
  function standing(plans) {
    if (!seating) return false;
    const { targets, barriers, withheld } = seating;
    const heard = hinted()[at];
    return (
      !(heard && withheld.has(heard)) &&
      plans.every(({ model, target }) => {
        const was = targets.get(model.key);
        return was !== undefined && sameBox(was, target);
      }) &&
      showable(plans).every(({ model }) => seats.seated(model.key)) &&
      sameBoxes(chrome.barriers(), barriers)
    );
  }

  // Shows the chips of `plans` in the seats they stand in, and hides every other.
  /** @param {ReturnType<typeof layout>} plans */
  function show(plans) {
    for (const plan of plans) {
      const seat = seats.seated(plan.model.key);
      if (seat) render(face(plan), seat);
    }
    seats.keepOnly(new Set(plans.map(({ model }) => model.key)));
  }

  function paint() {
    if (!armed) {
      seats.clear();
      return;
    }
    const moving = scrolling();
    const wasWalking = at >= 0;
    const heard = hinted()[at];
    const emptyBefore = mapped.length === 0;
    const detached = candidates.some((candidate) => !identity(candidate)?.isConnected);
    // Only at rest and with no letters typed: a partly typed code freezes the map until
    // the user completes or backs out of that prefix.
    if (!moving && !prefix && (stale || detached || !candidates.length)) {
      hold(read());
      at = heard
        ? hinted().findIndex(
            (candidate) =>
              identity(candidate) === identity(heard) && candidate.code === heard.code,
          )
        : -1;
    }
    const plans = layout(candidates, { current: hinted()[at], reading: scene() });
    // A scroll holds the seats, and so does every paint while they stand, the map the
    // user has read keeping its faces up to date in them as they type or walk it.
    if (!moving && !standing(plans)) draw(plans);
    const kept = showable(plans);
    show(kept);
    if (moving) return;
    const current = hinted()[at];
    if (wasWalking && current && !kept.some(({ candidate }) => candidate === current))
      at = -1;
    // The keys were painted before geometry retired the browsed hint, and a map
    // that has just emptied or filled, after `kept`, changes which of the caller's
    // rows stand.
    if ((wasWalking && at < 0) || emptyBefore !== (mapped.length === 0)) repaint();
  }

  // A page that moves under an armed map makes opaque labels temporarily untrustworthy,
  // so the map is read again once the scroll settles. Only while armed: what the
  // page's own repaint door says holds at every scroll position, no list's membership
  // moving with the page.
  function mount() {
    document.addEventListener("lf-keyboard-preference", invalidate);
    watchScrollEnds(() => {
      if (!armed) return;
      stale = true;
      seating = null;
      repaint();
    });
    addEventListener("resize", () => {
      if (!armed) return;
      stale = true;
      seating = null;
      repaint();
    });
  }

  return {
    arm,
    armed: () => armed,
    backOneLetter,
    candidates: members,
    disarm,
    invalidate,
    mount,
    narrow,
    paint,
    prefix: () => prefix,
    type,
    walkRows,
  };
}
