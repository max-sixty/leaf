/* Holding the user's place in a scroll container while its contents change.

   A surface that re-renders a list the user may be scrolled into takes a place hold
   around the change: `placeKeeper(scroller, {items, identity})` names the nodes that
   can mark a place and the identity each is rendered under, and its `take` / `finish`
   pair brackets one mutation. The same helper can bracket a widget's synchronous
   mutation in the platform page scroller when native anchoring does not retain its
   focused control. `around` compensates the browser's anchoring once and claims no
   asynchronous scroll owner.

   The place is one reference node and its offset in the scroller's content. The
   reference is chosen by what the user last named: an item under the pointer or
   holding focus, whichever input came last, then the other, then the items in the
   scroller's visible band (less the sticky headers stuck over each item, `headerInset`,
   so an item wholly under a stuck heading is not where anyone is reading) from the top
   down.
   Only an item whose top stands in the band can be named or lead by default.
   A surface may supply a visible `preferred` item
   whose interior is the active reading, even with its top clipped; it follows named
   items and precedes the default visible rows. Otherwise, holding a top the user
   cannot see keeps nothing they see still: the item's growth pushes everything after
   it, where holding the next item grows it up into the room scrolled past. Without a
   preferred reading, the item the band's top cuts holds the place only where no item
   begins in view. Every candidate is recorded, so when the
   first leaves, hides, or is renamed out of `items`, the next one still present holds
   the place without recovering an old position. A candidate the render replaced is
   handed across to the node now rendered under its identity; that is how a keyed
   re-render keeps the place it was holding (repository AGENTS.md: whatever replaces a
   node hands its state across itself).

   The correction follows only reflow: adding `scrollTop` to a node's viewport top gives
   its content offset, which a user's scroll does not change, so a wheel, a key, or a
   deliberate landing during the hold is never fought. A scroll-limit clamp the browser
   applied because content shrank is identified by the falling limit and the scroller
   standing exactly on it, and is not paid for twice. A correction keeps the reader's
   place rather than choosing one (scrolling.js, `placeKept`).

   A mutation that spans tasks takes its hold with `take` and ends it with `finish`, which
   corrects once, then follows frame by frame while `following()` says the mutation is
   still running. Such a hold is the sole anchoring authority for its mutation:
   `overflow-anchor: none` stands on the scroller for the hold's life and leaves at the
   rendering pass after its release, so the browser and the hold never compensate the
   same reflow, and a user's scroll between frames stays theirs. It leaves at that pass
   rather than at the release because renders run back to back: one finishing and the
   next taking its hold in the same script would take the property away and put it back,
   a write that changes nothing. A second spanning hold on the same scroller yields to
   the first. A synchronous nested hold can correct a temporary clamp and hands the
   reflow it paid for to the outer hold, so the outer hold does not pay it again.

   One synchronous mutation takes its hold with `around(mutate)`, or with
   `take({spans: false})` / `finish` across separate paint steps. It claims nothing,
   including any anchoring property another keeper already owns.
   Nothing but reflow moves a scroller inside one task: the browser's own anchoring, which
   a forced layout applies, or a clamp. So its correction pays for every movement since
   the reading and lands the reference where it stood, whatever the browser did first,
   and the scroller's style is never written and taken back in the one task. So `mutate`
   moves no scroller itself: a `focus()` without `preventScroll` or a `scrollIntoView`
   inside it would be read as reflow and undone.

   The module also owns when focus marks the user's place at all (`focusedInView`), for
   the readers outside a hold that take focus as that place. */
import { inlineStyle } from "./keeps.js";
import { cancelRender, nextFrame, nextRender } from "./rendering.js";
import {
  headerInset,
  inWindowChrome,
  seenRect,
  stuckBox,
  visibleBand,
} from "./geometry.js";
import { aimedTop, moveScrollerBy, placeKept, scrollLimit } from "./scrolling.js";
import { pointerAt } from "./pointer.js";
import { recentPlaceInput, focused } from "./focus.js";

// The focused control while it marks where the user is: while any of it is in front of
// them (geometry.js, `seenRect`), and it is not riding in a stuck sticky box
// (`stuckBox`) or the window's chrome (`inWindowChrome`). A user who scrolled away from
// the control they stand on is reading something else, though the control keeps focus,
// and a stuck tab strip, title or reply row, like the floating panel's row, stays in view over whatever they scroll to, so it names no place in what it holds.
// A reflow then holds, and a landing returns them to, what they see instead. A render
// holding the box they type in (reply-landing.js, `holdBox`), a reading place
// (reading-place.js, `capturePlace`), and revision continuity (version.js), for the
// region the user is working and whether a replaced reply box is scrolled back into
// view, ask this. Two readers ask a question of their own
// instead: a place hold here, whether the item focus names begins in the scroller's
// band, as it asks of the pointer's item, and the Threads list's resize landing
// (thread/landing.js), whether the focused title stands wholly where a landing puts it.
export function focusedInView() {
  const node = focused();
  return node && !inWindowChrome(node) && seenRect(node, new Map()) && !stuckBox(node)
    ? node
    : null;
}

// The candidates in the order they may hold the place, each once: an inherited
// reference, named items in input order, the surface's preferred reading, then the
// visible ones from the lead downward and wrapping to those above it.
/** @template {Element | string} T
 * @param {{inherited?: T | null | undefined, named: readonly T[], preferred?: T | null | undefined, visible: readonly T[]}} candidates
 * @returns {T[]} */
export function placeCandidates({ inherited, named, preferred, visible }) {
  const lead = inherited || named[0] || preferred || visible[0];
  const at = lead ? visible.indexOf(lead) : -1;
  const rest =
    at < 0 ? visible : [...visible.slice(at + 1), ...visible.slice(0, at + 1)];
  return [
    ...new Set(
      [inherited, ...named, preferred, lead, ...rest].filter(
        /** @returns {candidate is T} */ (candidate) => Boolean(candidate),
      ),
    ),
  ];
}

// How far to scroll so a reference whose content offset moved from `was` to `now` stands
// where it stood. `scrollTop`/`limit` are the scroller now and `held` the reading the
// hold last corrected at. Across tasks a clamp is removed only where the limit fell below
// the held scroll and the scroller stands exactly on it, since any other movement may be
// the user's; `withinTask`, every movement since the reading is reflow's.
/** @typedef {{scrollTop: number, limit: number}} ScrollReading */
/** @param {{was: number, now: number, scrollTop: number, limit: number, held: ScrollReading, withinTask?: boolean}} movement */
export function placeCorrection({
  was,
  now,
  scrollTop,
  limit,
  held,
  withinTask = false,
}) {
  const reflowed =
    withinTask || (limit < held.limit && held.scrollTop > limit && scrollTop === limit)
      ? scrollTop - held.scrollTop
      : 0;
  return now - was - reflowed;
}

// A synchronous hold inside another hold can correct a transient clamp before the
// enclosing presentation finishes. Credit the outer hold for the scroll the inner
// hold applied, so its own reference can still correct any different movement.
/** @typedef {{node: Element, key: string | null | undefined, contentTop: number}} PlaceReference */
/** @typedef {{named: Element | null, references: PlaceReference[], at: ScrollReading,
 * spans: boolean, borrowed?: {lease: PlaceLease, reading: LeaseReading}}} PlaceHold */
/** @typedef {{hold: PlaceHold | null, references: PlaceReference[]}} LeaseReading */
/** @typedef {{owner: object, snapshot: () => LeaseReading, sync: (reading: LeaseReading, paid: number) => void}} PlaceLease */
/** @type {WeakMap<Element, PlaceLease>} */
const heldScrollers = new WeakMap();
/** @param {number} moved @param {number} paid */
const sharedMovement = (moved, paid) =>
  Math.sign(moved) === Math.sign(paid)
    ? Math.sign(paid) * Math.min(Math.abs(moved), Math.abs(paid))
    : 0;

/** @param {Element} scroller
 * @param {{items: string, identity: (node: Element) => string | null | undefined, active?: () => boolean, preferred?: () => Element | null | undefined}} options */
export function placeKeeper(
  scroller,
  { items, identity, active = () => true, preferred = () => null },
) {
  /** @type {PlaceHold | null} */
  let current = null;
  const owner = {};
  /** @type {PlaceLease} */
  const lease = {
    owner,
    snapshot: () => ({
      hold: current,
      references: current?.references.filter(live) ?? [],
    }),
    sync: ({ hold, references }, paid) => {
      if (current !== hold || !hold) return;
      for (const reference of references)
        if (live(reference)) reference.contentTop += paid;
      hold.at = { scrollTop: scroller.scrollTop, limit: limit() };
    },
  };
  const limit = () => scrollLimit(scroller);
  // The box a node can hold the place by, or null where it holds nothing.
  /** @param {Element | null | undefined} node */
  const heldBox = (node) => {
    if (
      !node?.isConnected ||
      !scroller.contains(node) ||
      !node.matches(items) ||
      !node.checkVisibility()
    )
      return null;
    const box = node.getBoundingClientRect();
    return box.width && box.height ? box : null;
  };
  // A node with no identity (undefined or empty) has no successor to hand across to; it
  // must not match every other node that lacks one.
  /** @param {string | null | undefined} key */
  const rendered = (key) => {
    if (!key) return null;
    for (const node of scroller.querySelectorAll(items)) {
      if (identity(node) !== key) continue;
      const box = heldBox(node);
      if (box) return { node, box };
    }
    return null;
  };
  // The reference's live node: itself, or the node the render put under its identity.
  /** @param {PlaceReference} reference */
  const live = (reference) => {
    const box = heldBox(reference.node);
    if (box) return { reference, node: reference.node, box };
    const replacement = rendered(reference.key);
    if (!replacement) return null;
    reference.node = replacement.node;
    return { reference, ...replacement };
  };

  // Native anchoring is off while a hold that spans tasks stands, and comes back at the
  // next rendering pass with none in place, before that frame lays anything out. A
  // same-value property set writes nothing.
  let returning = 0;
  function claim() {
    if (current?.spans) {
      cancelRender(returning);
      returning = 0;
      inlineStyle(scroller).setProperty("overflow-anchor", "none");
    } else if (!returning && inlineStyle(scroller).getPropertyValue("overflow-anchor"))
      returning = nextRender(() => {
        returning = 0;
        if (!heldScrollers.has(scroller))
          inlineStyle(scroller).removeProperty("overflow-anchor");
      });
  }

  /** @param {PlaceHold} hold */
  function release(hold) {
    if (current !== hold) return;
    current = null;
    if (heldScrollers.get(scroller)?.owner === owner) heldScrollers.delete(scroller);
    if (hold.spans) claim();
  }

  /** @param {PlaceHold} hold */
  function correct(hold) {
    if (current !== hold || !active()) return false;
    /** @type {ReturnType<typeof live>} */
    let reading = null;
    for (const reference of hold.references) {
      reading = live(reference);
      if (reading) break;
    }
    if (!reading) return false;
    const reference = reading.reference;
    const now = reading.box.top + scroller.scrollTop;
    const was = reference.contentTop;
    const scrollWas = scroller.scrollTop;
    const delta = placeCorrection({
      was,
      now,
      scrollTop: scroller.scrollTop,
      limit: limit(),
      held: hold.at,
      withinTask: !hold.spans,
    });
    // From where the last correction aimed rather than where its rounding left the
    // box: a fold corrects every frame, and each frame's rounding would add to the last
    // (scrolling.js, `moveScrollerBy`).
    if (delta) {
      moveScrollerBy(scroller, aimedTop(scroller) - scroller.scrollTop + delta);
      placeKept(scroller);
    }
    // Every candidate observed this reflow too; refresh their baselines after the
    // correction, or a later hand-off pays again for movement the first one absorbed.
    for (const candidate of hold.references) {
      const geometry = live(candidate);
      if (geometry) candidate.contentTop = geometry.box.top + scroller.scrollTop;
    }
    hold.at = { scrollTop: scroller.scrollTop, limit: limit() };
    if (hold.borrowed) {
      hold.borrowed.lease.sync(
        hold.borrowed.reading,
        sharedMovement(now - was, scroller.scrollTop - scrollWas),
      );
      hold.borrowed.reading = hold.borrowed.lease.snapshot();
    }
    return true;
  }

  function take({ spans = true } = {}) {
    const enclosing = heldScrollers.get(scroller);
    if (enclosing?.owner !== owner && enclosing && spans) return null;
    const prior = current;
    if (prior) correct(prior);
    current = heldPlace(prior, spans);
    if (current && enclosing?.owner !== owner && enclosing)
      current.borrowed = { lease: enclosing, reading: enclosing.snapshot() };
    else if (current) heldScrollers.set(scroller, lease);
    else if (enclosing?.owner === owner) heldScrollers.delete(scroller);
    if (spans || prior?.spans) claim();
    return current;
  }

  // The place as it stands now, carrying on from `prior` where one stood.
  /** @param {PlaceHold | null} prior @param {boolean} spans @returns {PlaceHold | null} */
  function heldPlace(prior, spans) {
    if (!active()) return null;
    const band = visibleBand(scroller);
    if (!band) return null;
    const nodes = [...scroller.querySelectorAll(items)].map((node) => ({
      node,
      box: node.getBoundingClientRect(),
    }));
    // Where each item's view starts: below the sticky headers stuck over it, if any.
    /** @type {Map<Element, number>} */
    const tops = new Map();
    /** @param {Element} node */
    const topFor = (node) => {
      const prior = tops.get(node);
      if (prior !== undefined) return prior;
      const top = band.top + headerInset(node, scroller);
      tops.set(node, top);
      return top;
    };
    const { x, y } = pointerAt();
    const over = x >= band.left && x <= band.right && y >= band.top && y <= band.bottom;
    const visible = nodes
      .filter(({ node, box }) => {
        return (
          node.checkVisibility() &&
          box.width &&
          box.height &&
          box.bottom > topFor(node) &&
          box.top < band.bottom
        );
      })
      .sort((a, b) => a.box.top - b.box.top);
    // A named row begins in view. The surface's active reading may begin above it.
    const beginning = visible
      .filter(({ node, box }) => box.top >= topFor(node))
      .map(({ node }) => node);
    const shown = new Set(visible.map(({ node }) => node));
    const pointer = over ? document.elementFromPoint(x, y)?.closest?.(items) : null;
    const focus = focused()?.closest?.(items);
    const named = (
      recentPlaceInput() === "pointer" ? [pointer, focus] : [focus, pointer]
    ).flatMap((candidate) => beginning.filter((node) => node === candidate));
    const reading = preferred();
    const candidates = placeCandidates({
      inherited: prior?.references.find(
        (candidate) => live(candidate) && shown.has(candidate.node),
      )?.node,
      named,
      preferred: visible.find(({ node }) => node === reading)?.node,
      visible: beginning,
    });
    const references = [...new Set([...candidates, ...visible.map(({ node }) => node)])]
      .filter((node) => scroller.contains(node))
      .map((node) => ({
        node,
        key: identity(node),
        contentTop: node.getBoundingClientRect().top + scroller.scrollTop,
      }));
    if (!references.length) return null;
    return {
      named: named[0] ?? null,
      references,
      at: { scrollTop: scroller.scrollTop, limit: limit() },
      spans,
    };
  }

  /** @param {PlaceHold} hold @param {() => boolean} following */
  function follow(hold, following) {
    if (!correct(hold) || !following()) release(hold);
    else nextFrame(() => follow(hold, following));
  }

  /** @param {PlaceHold | null | undefined} hold @param {() => boolean} [following] */
  function finish(hold, following = () => false) {
    if (!hold) return;
    correct(hold);
    if (following()) nextFrame(() => follow(hold, following));
    else release(hold);
  }

  // One synchronous mutation under a hold.
  /** @template T @param {() => T} mutate @returns {T} */
  function around(mutate) {
    const held = take({ spans: false });
    try {
      return mutate();
    } finally {
      finish(held);
    }
  }

  return { take, finish, around };
}
