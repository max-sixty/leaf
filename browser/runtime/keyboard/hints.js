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
   placement pass keeps every generated route visible. Unlike an ordinal address, an
   opaque hint has no meaning once its face is hidden, so collisions are spread rather
   than removed. Geometry belongs to each caller and is passed in so this module
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
 * @typedef {"corner" | "below" | "before" | "above"} HintPlacement
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

// The open top nearest `preferred`, and what decided it: the window's edge, a barrier
// the seat stands clear of, or nothing where the preferred top is open.
/** @param {HintBox} box @param {number} preferred @param {HintBarrier[]} barriers @param {number} top @param {number} bottom @param {number} gap */
function nearestOpenTop(box, preferred, barriers, top, bottom, gap) {
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
        !barriers.some((barrier) => overlaps(movedTo(box, box.left, at), barrier)),
    )
    .sort(
      (left, right) => Math.abs(left.at - preferred) - Math.abs(right.at - preferred),
    )[0];
}

// Read every face before seating one, keeping the pass to one layout. Callers put every
// chip in its seat first and provide the visible rectangle each chip names and the
// place `at` its seat is drawn from; each face is read there, and the answer is where
// each seat stands (chip-seats.js), its `box` a barrier for a following pass.
// `placement` chooses the corner, below, before, or above the target;
// outside seats keep the target clear.
/** @param {ReturnType<typeof chipSeats>} seats
 * @param {{seat: HTMLElement, at: {left: number, top: number}, target: HintBox, placement?: HintPlacement, element: Element | null}[]} hints
 * @param {{barriers?: HintBarrier[]}} [options] */
function spreadHints(seats, hints, { barriers = [] } = {}) {
  const band =
    parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue("--focus-ring-w"),
    ) || 0;
  const faces = hints.map((hint) => ({
    start: seats.measure(hint.seat, hint.at).box,
    target: hint.target,
    ...(hint.placement === undefined ? {} : { placement: hint.placement }),
    hint,
  }));
  return seatHints(faces, { barriers, band, viewport: layoutWindow() }).map(
    ({ face, box }) => ({
      seat: face.hint.seat,
      target: face.hint.element,
      at: face.hint.at,
      start: face.start,
      box,
      held: box.held || Boolean(face.target.clippedTop),
    }),
  );
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
// before it. A box is `held` where what decided its seat stands still as the page
// scrolls, the window's edge or a fixed barrier, rather than its target or a face
// riding with its own, so the window holds it where a scroll carries the rest.
/** @template {HintFace} T @param {readonly T[]} faces @param {{barriers?: HintBarrier[], band: number, viewport: import("../rect.js").Box}} options */
export function seatHints(faces, { barriers: fixedBarriers = [], band, viewport }) {
  const gap = 2;
  // The browsed hint wears the layer's band (--focus-shadow, base.css), which a face's
  // own rectangle does not report. Any chip can become the browsed one as the user
  // types, so the pass seats every face as though it were, keeping the one layout. A
  // window edge takes the whole band, because a band drawn past it is clipped away. A
  // barrier — another face, or the chrome — takes the wider of the gap and the band,
  // because a band may stand in the gap it keeps but not past it; only the browsed chip
  // paints one, so it has that space to itself. Seated to the gap alone both cleared by
  // coincidence, the gap and the band both being 2px.
  const clear = Math.max(gap, band);
  const edgeLeft = viewport.left + band;
  const edgeTop = viewport.top + band;
  const edgeRight = viewport.right - band;
  const edgeBottom = viewport.bottom - band;
  /** @param {HintFace} face */
  const beforeLeft = ({ start, target }) => target.left - start.width - clear;
  const measured = nestOutsets(faces, (face) => beforeLeft(face) - edgeLeft).map(
    ({ face, outset }) => {
      const { start, target, placement = "corner" } = face;
      const preferredLeft =
        placement === "below"
          ? target.left + (target.width - start.width) / 2
          : placement === "before"
            ? beforeLeft({ start, target }) - outset
            : placement === "above"
              ? target.left
              : start.left;
      const preferredTop =
        placement === "below"
          ? target.bottom + clear
          : placement === "above"
            ? target.top - start.height - clear
            : start.top;
      const first = movedTo(
        start,
        clamp(preferredLeft, edgeLeft, Math.max(edgeLeft, edgeRight - start.width)),
        clamp(preferredTop, edgeTop, Math.max(edgeTop, edgeBottom - start.height)),
      );
      const held = first.left !== preferredLeft || first.top !== preferredTop;
      return {
        face,
        seated: first,
        ownTarget: placement !== "corner" ? target : null,
        clamped: held,
      };
    },
  );
  /** @type {{face: T, box: HintBox}[]} */
  const placed = [];
  for (const { face, seated, ownTarget, clamped } of measured) {
    const fixed = fixedBarriers.filter((other) => overlapsAcross(other, seated));
    const barriers = [
      ...fixed,
      ...placed.filter(({ box }) => overlapsAcross(box, seated)).map(({ box }) => box),
    ];
    if (ownTarget && overlapsAcross(ownTarget, seated)) barriers.push(ownTarget);
    const open = nearestOpenTop(
      seated,
      seated.top,
      barriers,
      edgeTop,
      edgeBottom,
      clear,
    );
    // A viewport can be physically too small for every face. Keep the preferred clamped
    // seat in that impossible case; ordinary scenes always have an open interval, and
    // the invariant tests exercise collisions at every viewport edge.
    const box = movedTo(seated, seated.left, open?.at ?? seated.top);
    // Below a face the window holds, the window holds this one too.
    const by = open?.by;
    box.held =
      clamped ||
      by === "edge" ||
      fixed.some((barrier) => barrier === by) ||
      (typeof by === "object" && Boolean(by?.held));
    placed.push({ face, box });
  }
  return placed;
}

/* One armed map over a caller's scene.

   Membership and seating are separate readings, and the difference is how often each is
   taken. `read` answers which members the map holds and what codes name them, each
   member already carrying its `code` because a scene can be a subset of a wider reading
   whose codes it keeps; that answer is held until something invalidates it. `layout`
   answers where those members are, and runs every paint over the whole current set from
   one `scene` reading, because a chip's place among its neighbours and its own box are
   the same measurement: derived from different readings they put the chip where neither
   reading said. `identity` names the element a walk and a re-read recognize a member by.

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
  const seats = chipSeats(layer);

  const hinted = () => candidates.filter(({ code }) => code.startsWith(prefix));
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
    return (candidates = found);
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

  // The scene the caller reads has changed meaning — a filter came or went. `refresh`
  // rebuilds the map now, for a caller that must speak its new size in this press;
  // `invalidate` leaves the reading to the frame that paints it, which is the whole of
  // what a caller needs when it has nothing to say about the result.
  const refresh = () => hold(read());

  function invalidate() {
    prefix = "";
    at = -1;
    stale = true;
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
    if (!candidates.some(({ code }) => code.startsWith(next))) {
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
  function walkRows({ id, when = () => candidates.length > 0, choose }) {
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

  /** @param {ReturnType<typeof layout>} codedPlans */
  function draw(codedPlans) {
    const plans = codedPlans.filter(shown);
    const drawn = plans.map((plan) => {
      const seat = seats.seat(plan.model.key);
      render(face(plan), seat);
      return {
        seat,
        element: plan.candidate ? identity(plan.candidate) : null,
        at: { left: plan.left, top: plan.top },
        target: plan.target,
        placement: plan.placement,
      };
    });
    // The coded map is spread around the fixed chrome.
    seats.place(
      plans.length ? spreadHints(seats, drawn, { barriers: chrome.barriers() }) : [],
    );
  }

  function paint() {
    if (!armed) {
      seats.clear();
      return;
    }
    // A scroll holds the seats, and the map the user has read keeps its faces up to date
    // in them as they type or walk it.
    if (scrolling()) {
      const plans = layout(hinted(), {
        current: hinted()[at],
        reading: scene(),
      }).filter(shown);
      for (const plan of plans) {
        const seat = seats.seated(plan.model.key);
        if (seat) render(face(plan), seat);
      }
      seats.keepOnly(new Set(plans.map(({ model }) => model.key)));
      return;
    }
    const wasWalking = at >= 0;
    const heard = hinted()[at];
    const emptyBefore = candidates.length === 0;
    const detached = candidates.some((candidate) => !identity(candidate)?.isConnected);
    // Only with the map whole: a partly typed code freezes it until the user
    // completes or backs out of that prefix, so `hinted()` and `candidates` agree here.
    if (!prefix && (stale || detached || !candidates.length)) {
      candidates = read();
      stale = false;
      at = heard
        ? candidates.findIndex(
            (candidate) =>
              identity(candidate) === identity(heard) && candidate.code === heard.code,
          )
        : -1;
    }
    const current = hinted()[at];
    const plans = layout(hinted(), { current, reading: scene() });
    const drawn = new Set(plans.map((chip) => chip.candidate));
    if (wasWalking && current && !drawn.has(current)) at = -1;
    draw(plans);
    // The keys were painted before geometry retired the browsed hint, and a map
    // that has just emptied or filled changes which of the caller's rows stand.
    if ((wasWalking && at < 0) || emptyBefore !== (candidates.length === 0)) repaint();
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
      repaint();
    });
    addEventListener("resize", () => {
      if (!armed) return;
      stale = true;
      repaint();
    });
  }

  return {
    arm,
    armed: () => armed,
    backOneLetter,
    candidates: () => candidates,
    disarm,
    invalidate,
    mount,
    paint,
    prefix: () => prefix,
    refresh,
    type,
    walkRows,
  };
}
