/* The semantic target a comment or reaction at current browser focus acts on.

   Pointer and focus share aimTargetAt, which reads the deepest focus: a datum is in the
   shadow tree, while its host is only the enclosing addressable element. Chrome owners
   translate their controls through placeOf. A focused thread belongs to its own reply
   route, and chrome with no page target leaves only a general page comment.

   An obligation's controls target the obligation they work. Other focus keeps the
   exact datum or visual part, or the addressable element it is on, before falling back
   to the innermost addressable element, which in an obligation's answer widget is the
   part the user can name, as an option a focused link sits in.

   A question's frame, the context around its answer widgets, asks nothing itself and
   holds what the question is about, so focus there names the frame: a press on a
   control in it, such as a shot's slider, is the user reading the question rather than
   choosing the shot. That holds answered or not and however many widgets the frame
   holds, since it is a fact about the markup, not about which obligation is open. */
import { focused } from "../focus.js";
import { inChrome } from "../passages.js";
import { aimTargetAt } from "../anchor-resolution.js";
import { placeOf } from "../current-target.js";
import { heldThread } from "../thread/focus.js";
import { under } from "../shadow.js";
import { readObligations } from "../obligations/model.js";
import { obligationPlace } from "../obligations/place.js";
import { OBLIGATION_CONTROL } from "../obligations/view-elements.js";

// The innermost question frame holding `node`, or null where none does or `node` is in
// one of that frame's answer widgets.
/** @param {Element} node */
function frameHolding(node) {
  const framed = readObligations()
    .all.map((item) => obligationPlace(item))
    .filter(
      ({ source, context }) =>
        source && context && context !== source && under(node, context),
    );
  const frame = framed.reduce(
    /** @param {Element | null} inner */
    (inner, { context }) => (inner && under(inner, context) ? inner : context),
    null,
  );
  const answering = framed.some(
    ({ source, context }) => context === frame && under(node, source),
  );
  return answering ? null : frame;
}

/** @param {{currentLocationIn: () => Element | null}} options */
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
    const aim = aimTargetAt(held);
    if (!aim || aim.anchor.datum || aim.anchor.visual || aim.element === held)
      return aim;
    const frame = frameHolding(held);
    return frame ? aimTargetAt(frame) : aim;
  };
}
