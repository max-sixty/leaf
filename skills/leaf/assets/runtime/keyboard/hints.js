/* The transient keyboard hint session, and the code and placement policy under it.

   Two vocabularies stand on this one interaction: the Go-to sequence's map of visible
   page targets, and the target chooser's map of addressable elements. Arming reads a
   scene, gives each member an opaque prefix-free code, and paints a chip on it. Typed
   letters narrow the map, Tab walks it aloud, Enter takes the one just heard, and
   Escape gives a letter back. A letter that names nothing is reported and the standing
   map is left alone, because a mistyped route should not cost the reader the letters
   they had right. A scroll freezes membership and re-reads it once the scene settles,
   so a target arriving mid-scroll is named at rest rather than on the frame it appears.
   A candidate is revalidated against a fresh reading before it is taken, so a target
   that left the scene cannot be worked by a stale label.

   What the members are, what a chip says, what taking one does, and where chrome stands
   belong to the caller. Everything above is here once.

   A hint code is generated from a caller-owned alphabet. Replacing one leaf with all of
   its children keeps the result prefix-free while leaving most targets on one letter;
   only the tail branches when a scene contains more targets than the alphabet. The
   placement pass keeps every generated route visible. Unlike an ordinal address, an
   opaque hint has no meaning once its face is hidden, so collisions are spread rather
   than removed. Geometry belongs to each caller and is passed in so this module
   introduces no ownership cycle through the shortcut bar. */
import { html, nothing, render, repeat } from "../../vendor/browser-runtime.js";
import { overlaps } from "../geometry.js";
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
// while an unchanged owner retains its chip and keycaps across paint-only updates.
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

const clamp = (value, start, end) => Math.max(start, Math.min(value, end));

function nearestOpenTop(box, preferred, barriers, top, bottom, gap) {
  const last = Math.max(top, bottom - box.height);
  const seats = [preferred, top, last];
  for (const barrier of barriers)
    seats.push(barrier.bottom + gap, barrier.top - gap - box.height);
  return seats
    .map((seat) => clamp(seat, top, last))
    .filter(
      (seat) =>
        !barriers.some((barrier) => overlaps(movedTo(box, box.left, seat), barrier)),
    )
    .sort((left, right) => Math.abs(left - preferred) - Math.abs(right - preferred))[0];
}

// Read every face before moving one, keeping the pass to one layout. Callers append all
// chips first and provide the visible rectangle each chip names. `belowTarget` makes
// that edge the preferred seat and the target an obstacle. The returned boxes can be
// barriers for a following pass.
export function spreadHints(
  hints,
  {
    barriers: fixedBarriers = [],
    lineBox,
    viewportLeft = 0,
    viewportTop = 0,
    viewportRight = document.documentElement.clientWidth,
    viewportBottom = document.documentElement.clientHeight,
  } = {},
) {
  const gap = 2;
  // The browsed hint wears the layer's band (--here-shadow, theme.css), which a face's
  // own rectangle does not report. Any chip can become the browsed one as the reader
  // types, so the pass seats every face as though it were, keeping the one layout. A
  // window edge takes the whole band, because a band drawn past it is clipped away. A
  // barrier — another face, or the shortcut bar — takes the wider of the gap and the band,
  // because a band may stand in the gap it keeps but not past it; only the browsed chip
  // paints one, so it has that space to itself. Seated to the gap alone both cleared by
  // coincidence, the gap and the band both being 2px.
  const band =
    parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue("--here-ring-w"),
    ) || 0;
  const clear = Math.max(gap, band);
  const line = lineBox ?? { left: 0, top: viewportBottom, right: 0, height: 0 };
  const lineBand = {
    left: line.left,
    top: line.top,
    right: line.right,
    bottom: viewportBottom,
  };
  const edgeLeft = viewportLeft + band;
  const edgeTop = viewportTop + band;
  const edgeRight = viewportRight - band;
  const edgeBottom = viewportBottom - band;
  const measured = hints.map(({ chip, target, belowTarget = false }) => {
    const start = chip.getBoundingClientRect();
    const preferredLeft = belowTarget
      ? target.left + (target.width - start.width) / 2
      : start.left;
    const preferredTop = belowTarget ? target.bottom + clear : start.top;
    const first = movedTo(
      start,
      clamp(preferredLeft, edgeLeft, Math.max(edgeLeft, edgeRight - start.width)),
      clamp(preferredTop, edgeTop, Math.max(edgeTop, edgeBottom - start.height)),
    );
    const rightSeat = Math.max(target.left, line.right + clear);
    const canSitRight = rightSeat + start.width <= Math.min(target.right, edgeRight);
    const left =
      line.height && overlaps(first, lineBand) && canSitRight ? rightSeat : first.left;
    return [chip, movedTo(first, left, first.top), start, belowTarget ? target : null];
  });
  const placed = [];
  for (const [chip, seated, start, ownTarget] of measured) {
    const barriers = [...fixedBarriers, ...placed].filter(
      (other) => other.left < seated.right && seated.left < other.right,
    );
    if (ownTarget && ownTarget.left < seated.right && seated.left < ownTarget.right)
      barriers.push(ownTarget);
    if (
      lineBand.bottom > lineBand.top &&
      lineBand.left < seated.right &&
      seated.left < lineBand.right
    )
      barriers.push(lineBand);
    const top = nearestOpenTop(
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
    const box = movedTo(seated, seated.left, top ?? seated.top);
    const sideShift = box.left - start.left;
    const shift = box.top - start.top;
    if (sideShift) chip.style.left = `${parseFloat(chip.style.left) + sideShift}px`;
    if (shift) chip.style.top = `${parseFloat(chip.style.top) + shift}px`;
    placed.push(box);
  }
  return placed;
}

// How long after the last scroll frame the scene is taken as settled when the browser
// sends no `scrollend`. A programmatic scroll written a frame at a time, and a scroll
// restoration that replaces the scene under an armed map, both end without one; the
// map would otherwise hold its frozen membership until the next resize.
const SETTLE_MS = 80;

/* One armed map over a caller's scene.

   `read` returns this scene's members, each already carrying the `code` that names it:
   the caller owns that assignment because a scene can be a subset of a wider reading
   whose codes it keeps. `identity` names the element a walk and a re-read recognize a
   member by. `plan` draws one member — the chip's immutable model and where its corner
   starts — or nothing where the member is no longer paintable. `extras` are chips the
   caller keeps outside the coded map, such as named destinations on fixed chrome; they
   are seated first and become barriers for the coded ones. `chrome` reads the standing
   furniture the placement pass must keep clear. `followsScroll` says whether the coded
   chips are redrawn while the page moves or withheld until it settles; either way their
   membership is frozen for the length of the scroll. */
export function createHintSession({
  layer,
  walk: walkKey,
  read,
  identity,
  scene = () => null,
  plan,
  template,
  take: takeCandidate,
  words,
  chrome,
  extras = () => [],
  followsScroll = false,
}) {
  let armed = false;
  let prefix = "";
  let candidates = [];
  // Where the audible walk stands in `hinted()`, or -1 when no hint has been heard.
  let at = -1;
  let scrolling = false;
  let stale = false;
  let settleTimer = 0;

  const hinted = () => candidates.filter(({ code }) => code.startsWith(prefix));

  // Every way the map is replaced whole puts the reader back at its head: no letters
  // typed, nothing heard, and nothing held over from a scroll that was under way.
  //
  // The reading it carries was taken outside a paint, so the caller can speak the map's
  // size in the same press that arms it — but that is a frame before the line explaining
  // the map has been laid out, and the room the reader has is measured net of that line.
  // The frame that paints the map therefore reads the scene again: a chip whose place
  // among its neighbours came from one reading and whose box came from another sits
  // where neither reading put it.
  function hold(found) {
    prefix = "";
    at = -1;
    scrolling = false;
    stale = true;
    clearTimeout(settleTimer);
    return (candidates = found);
  }

  function arm() {
    armed = true;
    return hold(read());
  }

  function disarm() {
    armed = false;
    hold([]);
    render(nothing, layer);
  }

  // The scene the caller reads has changed meaning — a filter came or went — so the map
  // is rebuilt now rather than at the next paint, and the caller can speak its size.
  const refresh = () => hold(read());

  function take(candidate) {
    const current = read();
    if (candidate && current.some((one) => identity(one) === identity(candidate)))
      return takeCandidate(candidate);
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
    announce(`Hint ${target.code}: ${said}${stop} Press Enter to ${words.take}.`);
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
    const plans = [...extraPlans, ...codedPlans];
    render(
      html`${repeat(
        plans,
        ({ model }) => model.key,
        ({ model }) => template(model),
      )}`,
      layer,
    );
    const chips = [...layer.children];
    const seated = plans.map((drawn, index) => {
      const chip = chips[index];
      chip.style.left = `${drawn.left}px`;
      chip.style.top = `${drawn.top}px`;
      return { chip, target: drawn.target, belowTarget: drawn.belowTarget };
    });
    // Fixed chips stay where the caller put them and reserve their own pixels; the
    // coded map is spread around them, the standing chrome, and the key line.
    const reserved = extraPlans.length
      ? spreadHints(seated.slice(0, extraPlans.length))
      : [];
    if (codedPlans.length)
      spreadHints(seated.slice(extraPlans.length), {
        barriers: [...reserved, ...chrome.barriers()],
        lineBox: chrome.lineBox(),
        viewportTop: chrome.viewportTop(),
      });
  }

  function paint() {
    if (!armed) {
      render(nothing, layer);
      return;
    }
    const extraPlans = extras();
    // A moving page target cannot carry a readable opaque route where the caller says
    // so; fixed chips stay put and remain visible throughout the scroll.
    if (scrolling && !followsScroll) return draw(extraPlans, []);
    const wasWalking = at >= 0;
    const heard = hinted()[at];
    const emptyBefore = candidates.length === 0;
    // A scroll keeps one map until it settles. Reconciliation is different: every old
    // candidate is detached at once, so holding that map would paint nothing
    // indefinitely if the replacement's scroll restoration produces no final scrollend.
    const detached = candidates.some((candidate) => !identity(candidate)?.isConnected);
    // Only with the map whole: a partly typed code freezes it until the reader
    // completes or backs out of that prefix, so `hinted()` and `candidates` agree here.
    const fresh = !prefix && !scrolling && (stale || detached || !candidates.length);
    if (fresh) {
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
    const reading = scene();
    const plans = [];
    const drawn = new Set();
    for (const candidate of hinted()) {
      const chip = plan(candidate, { current: candidate === current, fresh, reading });
      if (!chip) continue;
      plans.push(chip);
      drawn.add(candidate);
    }
    if (wasWalking && current && !drawn.has(current)) at = -1;
    draw(extraPlans, plans);
    // The shortcut bar was painted before geometry retired the browsed hint, and a map
    // that has just emptied or filled changes which of the caller's rows stand.
    if ((wasWalking && at < 0) || emptyBefore !== (candidates.length === 0)) repaint();
  }

  function settled() {
    clearTimeout(settleTimer);
    if (!scrolling) return;
    scrolling = false;
    repaint();
  }

  // A page that moves under an armed map makes opaque labels temporarily untrustworthy.
  // Capture, because a panel's list and a board's own overflow scroll in boxes of their
  // own and a scroll event does not bubble.
  //
  // Only while armed, which is why these are listeners of their own rather than lines in
  // the page's own repaint door (pageShifted): what that door says holds at every scroll
  // position, no list's membership moving with the page, so it would be repainting for
  // nobody. Armed, the paint is the whole shared repaint — the ring and line are cheap
  // beside the chips, and one door is what stops the chips having a repaint set of their
  // own to keep in step.
  function mount() {
    addEventListener(
      "scroll",
      () => {
        if (!armed) return;
        scrolling = true;
        stale = true;
        clearTimeout(settleTimer);
        settleTimer = setTimeout(settled, SETTLE_MS);
        repaint();
      },
      { capture: true, passive: true },
    );
    addEventListener(
      "scrollend",
      () => {
        if (armed) settled();
      },
      { capture: true, passive: true },
    );
    addEventListener("resize", () => {
      if (!armed) return;
      clearTimeout(settleTimer);
      scrolling = false;
      stale = true;
      repaint();
    });
  }

  return {
    arm,
    backOneLetter,
    candidates: () => candidates,
    choose: () => take(hinted()[at]),
    disarm,
    mount,
    paint,
    prefix: () => prefix,
    refresh,
    type,
    walk,
    walking: () => at >= 0,
  };
}
