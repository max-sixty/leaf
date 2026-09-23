/* Holding the reader's place in a scroll container while its contents change.

   A surface that re-renders a list the reader may be scrolled into takes a place hold
   around the change: `placeKeeper(scroller, {items, identity})` names the nodes that
   can mark a place and the identity each is rendered under, and its `take` / `finish`
   pair brackets one mutation. The document itself needs none of this: its scroller is
   the platform's, and native scroll anchoring holds it (theme.css, at the body strip).

   The place is one reference node and its offset in the scroller's content. The
   reference is chosen by what the reader last named: the item under the pointer while
   the pointer is over the scroller, then the item holding focus, then the items in the
   scroller's visible band (`visibleBand`, so an item wholly under a stuck heading is not
   where anyone is reading) from the top down. Every candidate is recorded, so when the
   first leaves, hides, or is renamed out of `items`, the next one still standing holds
   the place without recovering an old position. A candidate the render replaced is
   handed across to the node now rendered under its identity; that is how a keyed
   re-render keeps the place it was holding (repository AGENTS.md: whatever replaces a
   node hands its state across itself).

   The correction follows only reflow: adding `scrollTop` to a node's viewport top gives
   its content offset, which a reader's scroll does not change, so a wheel, a key, or a
   deliberate landing during the hold is never fought. A scroll-limit clamp the browser
   applied because content shrank is identified by the falling limit and the scroller
   standing exactly on it, and is not paid for twice.

   A hold is the sole anchoring authority for its mutation: `overflow-anchor: none` is set
   on the scroller for the hold's life and removed on release, so the browser and the hold
   never compensate the same reflow. A hold taken while another stands on the same
   scroller inherits its reference, because a mutation in flight (a fold) has already
   moved whatever the pointer would now name. `finish` corrects once, then follows frame
   by frame while `following()` says the mutation is still running. */
import { visibleBand } from "./geometry.js";
import { focused } from "./keyboard/scopes.js";
import { pointerAt } from "./pointer.js";

// The candidates in the order they may hold the place, each once: an inherited
// reference, the pointer's, focus's, then the visible ones from the lead downward and
// wrapping to those above it.
export function placeCandidates({ inherited, pointer, focus, visible }) {
  const lead = inherited || pointer || focus || visible[0];
  const at = visible.indexOf(lead);
  const rest =
    at < 0 ? visible : [...visible.slice(at + 1), ...visible.slice(0, at + 1)];
  return [...new Set([inherited, pointer, focus, lead, ...rest].filter(Boolean))];
}

// How far to scroll so a reference whose content offset moved from `was` to `now` stands
// where it stood. `scrollTop`/`limit` are the scroller now and `held` the reading the
// hold last corrected at; a clamp is removed only where the limit fell below the held
// scroll and the scroller stands exactly on it.
export function placeCorrection({ was, now, scrollTop, limit, held }) {
  const clamp =
    limit < held.limit && held.scrollTop > limit && scrollTop === limit
      ? scrollTop - held.scrollTop
      : 0;
  return now - was - clamp;
}

export function placeKeeper(scroller, { items, identity, active = () => true }) {
  let standing = null;
  const limit = () => Math.max(0, scroller.scrollHeight - scroller.clientHeight);
  // The box a node can hold the place by, or null where it holds nothing.
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
  const rendered = (key) =>
    !key
      ? null
      : [...scroller.querySelectorAll(items)].find(
          (node) => identity(node) === key && heldBox(node),
        );
  // The reference's live node: itself, or the node the render put under its identity.
  const live = (reference) => {
    if (heldBox(reference.node)) return reference.node;
    const replacement = rendered(reference.key);
    if (replacement) reference.node = replacement;
    return replacement ?? null;
  };

  function release(hold) {
    if (standing !== hold) return;
    standing = null;
    scroller.style.removeProperty("overflow-anchor");
  }

  function correct(hold) {
    if (standing !== hold || !active()) return false;
    const reference = hold.references.find(live);
    if (!reference) return false;
    const now = heldBox(reference.node).top + scroller.scrollTop;
    const delta = placeCorrection({
      was: reference.contentTop,
      now,
      scrollTop: scroller.scrollTop,
      limit: limit(),
      held: hold.at,
    });
    if (delta) scroller.scrollTop += delta;
    // Every candidate observed this reflow too; refresh their baselines after the
    // correction, or a later hand-off pays again for movement the first one absorbed.
    for (const candidate of hold.references) {
      const node = live(candidate);
      if (node) candidate.contentTop = heldBox(node).top + scroller.scrollTop;
    }
    hold.at = { scrollTop: scroller.scrollTop, limit: limit() };
    return true;
  }

  function take() {
    const prior = standing;
    if (prior) correct(prior);
    standing = null;
    scroller.style.removeProperty("overflow-anchor");
    if (!active()) return null;
    const band = visibleBand(scroller);
    if (!band) return null;
    const nodes = [...scroller.querySelectorAll(items)];
    const boxes = new Map(nodes.map((node) => [node, node.getBoundingClientRect()]));
    const { x, y } = pointerAt();
    const over = x >= band.left && x <= band.right && y >= band.top && y <= band.bottom;
    const references = placeCandidates({
      inherited: prior?.references.find(live)?.node,
      pointer: over ? document.elementFromPoint(x, y)?.closest?.(items) : null,
      focus: focused()?.closest?.(items),
      visible: nodes
        .filter((node) => {
          const box = boxes.get(node);
          return (
            node.checkVisibility() &&
            box.width &&
            box.height &&
            box.bottom > band.top &&
            box.top < band.bottom
          );
        })
        .sort((a, b) => boxes.get(a).top - boxes.get(b).top),
    })
      .filter((node) => scroller.contains(node))
      .map((node) => ({
        node,
        key: identity(node),
        contentTop: node.getBoundingClientRect().top + scroller.scrollTop,
      }));
    if (!references.length) return null;
    standing = {
      references,
      at: { scrollTop: scroller.scrollTop, limit: limit() },
    };
    scroller.style.setProperty("overflow-anchor", "none");
    return standing;
  }

  function follow(hold, following) {
    if (!correct(hold) || !following()) release(hold);
    else requestAnimationFrame(() => follow(hold, following));
  }

  function finish(hold, following = () => false) {
    if (!hold) return;
    correct(hold);
    if (following()) requestAnimationFrame(() => follow(hold, following));
    else release(hold);
  }

  // One synchronous mutation under a hold.
  function around(mutate) {
    const hold = take();
    try {
      return mutate();
    } finally {
      finish(hold);
    }
  }

  return { take, finish, around };
}
