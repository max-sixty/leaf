// Compiled from current-target.ts by build/typescript.mjs; edit that file.
/* The semantic target a comment or reaction at current browser focus acts on.

   Pointer and focus share aimTargetAt, which reads the deepest focus: a datum is in the
   shadow tree, while its host is only the enclosing addressable element. Focus on a
   visual that holds focus on a part of its own, as a chart on the point its keys
   reached, names that part (`focusTargetAt`). Chrome owners
   translate their controls through placeOf. A focused thread belongs to its own reply
   route, and chrome with no page target leaves only a general page comment.

   An obligation's controls target the obligation they work. Other focus keeps the
   exact datum or visual part, or the addressable element it is on, before falling back
   to the innermost addressable element, which in an obligation's answer widget is the
   part the user can name, as an option a focused link sits in.

   A question's group, the context the author declares round its answer widgets, asks
   nothing itself and holds what the question is about, so focus there names the group:
   a press on a control in it, such as a shot's slider, is the user reading the
   question rather than choosing the shot. That holds answered or not and however many
   widgets the group holds, since it is a fact about the markup, not about which
   obligation is open. */
import { focused } from "../../dom/focus.js";
import { aimTargetAt, focusTargetAt } from "../../readings/anchor-resolution.js";
import { placeOf } from "../../records/current-target.js";
import { heldThread } from "../../records/thread/focus.js";
import { under } from "../../lib/shadow-tree.js";
import { obligationPlace, readObligations } from "../../records/obligations/place.js";
import { OBLIGATION_CONTROL } from "../../records/obligations/view-elements.js";
import { inChrome } from "../../base/ui-marks.js";

// The innermost question group holding `node` (`obligationPlace`'s context), or null
// where none does or `node` is in one of that group's answer widgets.
function groupHolding(node) {
  const grouped = readObligations()
    .all.map((item) => obligationPlace(item))
    .filter(
      ({ source, context }) =>
        source && context && context !== source && under(node, context),
    );
  const group = grouped.reduce(
    (inner, { context }) => (inner && under(inner, context) ? inner : context),
    null,
  );
  const answering = grouped.some(
    ({ source, context }) => context === group && under(node, source),
  );
  return answering ? null : group;
}

export function createCurrentTarget({ currentLocationIn }) {
  return function currentTarget() {
    const held = focused();
    if (!held || held === document.body) return null;
    if (inChrome(held) && heldThread()) return null;
    const place = placeOf(held);
    if (!place || inChrome(place)) return null;
    if (place !== held) return aimTargetAt(place);
    const working = held.matches(OBLIGATION_CONTROL) ? currentLocationIn() : null;
    if (working) return aimTargetAt(working);
    const aim = focusTargetAt(held);
    if (!aim || aim.anchor.datum || aim.anchor.visual || aim.element === held)
      return aim;
    const group = groupHolding(held);
    return group ? aimTargetAt(group) : aim;
  };
}
