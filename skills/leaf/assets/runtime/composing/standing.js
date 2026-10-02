/* The semantic target a comment or reaction at current browser focus acts on.
   Focus inside a widget keeps its exact datum or visual part; only ordered page walks
   retarget it to the document host. Pointer and focus share aimTargetAt. */
import { focused } from "../keyboard/scopes.js";
import { inChrome } from "../passages.js";
import { aimTargetAt } from "../anchor-resolution.js";
import { placeOf } from "../standing-target.js";
import { heldThread } from "../thread/focus.js";

// Ask controls target the question they work; other focus keeps the exact datum or
// visual part before falling back to the innermost addressable element. Chrome owners
// translate their controls through placeOf. A focused thread belongs to its own reply
// route, and chrome with no page target leaves only a general page comment.
//
// Read the deepest focus: a datum is in the shadow tree, while its host is only the
// enclosing addressable element. The pointer and keyboard resolve through the same
// aimTargetAt, including source provenance and visual-part identity.
export function createStandingTarget({ isAskControl, standingIn }) {
  return function standingTarget() {
    const held = focused();
    if (!held || held === document.body) return null;
    if (inChrome(held) && heldThread()) return null;
    const place = placeOf(held);
    if (!place || inChrome(place)) return null;
    if (place !== held) return aimTargetAt(place);
    const working = isAskControl(held) ? standingIn() : null;
    return aimTargetAt(working ?? held);
  };
}
