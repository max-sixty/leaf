/* The transient keyboard hint session, and the code and placement policy under it.

   Two vocabularies stand on this one interaction: the Go-to sequence's map of visible
   page targets, and the target picker's map of addressable elements. Arming reads a
   scene, gives each member an opaque prefix-free code, and paints a chip on it. Typed
   letters narrow the map, Tab walks it aloud, Enter takes the one just heard, and
   Escape gives a letter back. A letter that names nothing is reported and the standing
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
   introduces no ownership cycle through the shortcut bar. */
import { bindingEnabled, spell } from "./bindings.js";
import { html, render } from "../../vendor/browser-runtime.js";
import { keySequenceModel, keySequenceTemplate } from "./presentation.js";
import { clamp, overlaps, overlapsAcross } from "../rect.js";
import { chipSeats } from "./chip-seats.js";
import { scrolling, watchScrollEnds } from "../arrivals.js";
import { announce } from "../notifications.js";
import { repaint } from "../repaint.js";
import { beginWalk, listWalkPosition } from "../walk-position.js";

export const HINT_KEYS = [..."asdfghjklqwertyuiopzxcvbnm"];

export function hintCodes(count, keys = HINT_KEYS) {
  const codes = [...keys];
  while (codes.length < count) {
    const shortest = Math.min(...codes.map((code) => code.length));
    const at = codes.findLastIndex((code) => code.length === shortest);
    const parent = codes[at];
    codes.splice(at, 1, ...keys.map((key) => parent + key));
  }
  return codes.slice(0, count);
}

// Lit sees only an opaque primitive. The native row or target remains controller state,
// while an unchanged owner retains its seat, chip and keycaps across paint-only updates.
export function renderKeys() {
  const keys = new WeakMap();
  let next = 1;
  return (owner) => {
    if (!keys.has(owner)) keys.set(owner, next++);
    return keys.get(owner);
  };
}

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
function nearestOpenTop(box, preferred, barriers, top, bottom, gap) {
  const last = Math.max(top, bottom - box.height);
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
    .map(({ at, by }) => {
      const held = clamp(at, top, last);
      return { at: held, by: held === at ? by : "edge" };
    })
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
function spreadHints(
  seats,
  hints,
  {
    barriers = [],
    lineBox,
    viewportLeft = 0,
    viewportTop = 0,
    viewportRight = document.documentElement.clientWidth,
    viewportBottom = document.documentElement.clientHeight,
  } = {},
) {
  const band =
    parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue("--focus-ring-w"),
    ) || 0;
  const faces = hints.map(({ seat, at, target, placement = "corner" }) => ({
    start: seats.boxAt(seat, at),
    target,
    placement,
  }));
  const placed = seatHints(faces, {
    barriers,
    lineBox,
    band,
    viewport: {
      left: viewportLeft,
      top: viewportTop,
      right: viewportRight,
      bottom: viewportBottom,
    },
  });
  return hints.map(({ seat, at, target, element }, index) => ({
    seat,
    target: element,
    at,
    start: faces[index].start,
    box: placed[index],
    // A chip on a target whose top the room cuts stands at the room's edge.
    held: placed[index].held || Boolean(target?.clippedTop),
  }));
}

// Where each face stands, folded from rectangles `spreadHints` has already read. Each
// face is `{ start, target, placement }`, `start` the box it was drawn at; the answer
// is one box per face, in order, each clear of the barriers, the key line and every face
// seated before it. A box is `held` where what decided its seat stands still as the page
// scrolls, the window's edge, the key line or a fixed barrier, rather than its target or
// a face riding with its own, so the window holds it where a scroll carries the rest.
export function seatHints(
  faces,
  { barriers: fixedBarriers = [], lineBox, band, viewport },
) {
  const gap = 2;
  // The browsed hint wears the layer's band (--focus-shadow, theme.css), which a face's
  // own rectangle does not report. Any chip can become the browsed one as the user
  // types, so the pass seats every face as though it were, keeping the one layout. A
  // window edge takes the whole band, because a band drawn past it is clipped away. A
  // barrier — another face, or the shortcut bar — takes the wider of the gap and the band,
  // because a band may stand in the gap it keeps but not past it; only the browsed chip
  // paints one, so it has that space to itself. Seated to the gap alone both cleared by
  // coincidence, the gap and the band both being 2px.
  const clear = Math.max(gap, band);
  const line = lineBox ?? { left: 0, top: viewport.bottom, right: 0, height: 0 };
  const lineBand = {
    left: line.left,
    top: line.top,
    right: line.right,
    bottom: viewport.bottom,
  };
  const edgeLeft = viewport.left + band;
  const edgeTop = viewport.top + band;
  const edgeRight = viewport.right - band;
  const edgeBottom = viewport.bottom - band;
  const measured = faces.map(({ start, target, placement = "corner" }) => {
    const preferredLeft =
      placement === "below"
        ? target.left + (target.width - start.width) / 2
        : placement === "before"
          ? target.left - start.width - clear
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
    const rightSeat = Math.max(target.left, line.right + clear);
    const canSitRight = rightSeat + start.width <= Math.min(target.right, edgeRight);
    const beside = line.height && overlaps(first, lineBand) && canSitRight;
    const held = beside || first.left !== preferredLeft || first.top !== preferredTop;
    return [
      movedTo(first, beside ? rightSeat : first.left, first.top),
      placement !== "corner" ? target : null,
      held,
    ];
  });
  const placed = [];
  for (const [seated, ownTarget, clamped] of measured) {
    const fixed = fixedBarriers.filter((other) => overlapsAcross(other, seated));
    const barriers = [
      ...fixed,
      ...placed.filter((other) => overlapsAcross(other, seated)),
    ];
    if (ownTarget && overlapsAcross(ownTarget, seated)) barriers.push(ownTarget);
    if (lineBand.bottom > lineBand.top && overlapsAcross(lineBand, seated)) {
      fixed.push(lineBand);
      barriers.push(lineBand);
    }
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
    box.held =
      clamped || open?.by === "edge" || fixed.includes(open?.by) || !!open?.by?.held;
    placed.push(box);
  }
  return placed;
}

/* One armed map over a caller's scene.

   Membership and seating are separate readings, and the difference is how often each is
   taken. `read` answers which members the map holds and what codes name them, each
   member already carrying its `code` because a scene can be a subset of a wider reading
   whose codes it keeps; that answer is held until something invalidates it. `layout`
   answers where those members are, and runs every paint over the whole standing set from
   one `scene` reading, because a chip's place among its neighbours and its own box are
   the same measurement: derived from different readings they put the chip where neither
   reading said. `identity` names the element a walk and a re-read recognize a member by.

   `extras` are chips the caller keeps outside the coded map, such as named destinations
   on fixed chrome; they are seated first and become barriers for the coded ones.
   `chrome` reads the standing furniture the placement pass must keep clear.
   A map stands through a scroll once it has stood still long enough to be read: its
   chips ride with the things they name (chip-seats.js), so the codes the user is
   reading stay where they were read and stay pressable, while membership and seats
   wait for the scene to settle. A map armed into a page already in flight has stood
   still for nobody, and shows nothing until it settles rather than putting codes on a
   scene that is leaving. */
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
  extras = () => [],
}) {
  let armed = false;
  let prefix = "";
  let candidates = [];
  // Where the audible walk stands in `hinted()`, or -1 when no hint has been heard.
  let at = -1;
  let stale = false;
  const seats = chipSeats(layer);

  const hinted = () => candidates.filter(({ code }) => code.startsWith(prefix));
  const enabled = (candidate) => [...candidate.code].every(bindingEnabled);
  const shown = (plan) => enabled(plan.candidate) || plan.candidate === hinted()[at];
  const nativeTake = keySequenceModel([spell("Enter")], undefined, ["Enter"]);
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

  function take(candidate) {
    const current = read();
    const found =
      candidate && current.find((one) => identity(one) === identity(candidate));
    if (found) return takeCandidate(found);
    hold(current);
    announce("That target is no longer visible. The hints are reset.");
    repaint();
  }

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

  function walk(direction) {
    const targets = hinted();
    if (!targets.length) return;
    at = (at + direction + targets.length) % targets.length;
    const target = targets[at];
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

  function draw(extraPlans, codedPlans) {
    codedPlans = codedPlans.filter(shown);
    const plans = [...extraPlans, ...codedPlans];
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
    // Fixed chips stay where the caller put them and reserve their own pixels; the
    // coded map is spread around them, the standing chrome, and the key line.
    const reserved = spreadHints(seats, drawn.slice(0, extraPlans.length));
    const coded = codedPlans.length
      ? spreadHints(seats, drawn.slice(extraPlans.length), {
          barriers: [...reserved.map(({ box }) => box), ...chrome.barriers()],
          lineBox: chrome.lineBox(),
          viewportTop: chrome.viewportTop(),
        })
      : [];
    seats.place([...reserved, ...coded]);
  }

  function paint() {
    if (!armed) {
      seats.clear();
      return;
    }
    // A scroll holds the seats, and the map the user has read keeps its faces up to date
    // in them as they type or walk it.
    if (scrolling()) {
      const plans = [
        ...extras(),
        ...layout(hinted(), { current: hinted()[at], reading: scene() }).filter(shown),
      ];
      for (const plan of plans) {
        const seat = seats.standing(plan.model.key);
        if (seat) render(face(plan), seat);
      }
      seats.keepOnly(new Set(plans.map(({ model }) => model.key)));
      return;
    }
    const extraPlans = extras();
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
    draw(extraPlans, plans);
    // The shortcut bar was painted before geometry retired the browsed hint, and a map
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
    choose: () => take(hinted()[at]),
    disarm,
    invalidate,
    mount,
    paint,
    prefix: () => prefix,
    refresh,
    type,
    walk,
    walking: () => at >= 0,
  };
}
