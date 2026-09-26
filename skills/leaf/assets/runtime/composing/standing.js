/* The addressable element a comment or reaction at the current focus acts on. */
import { documentFocused } from "../keyboard/scopes.js";
import { inChrome } from "../passages.js";
import { addressableAt } from "../anchor-resolution.js";
import { placeOf } from "../standing-target.js";
import { heldThread } from "../thread/focus.js";

// The addressable element the user is standing in, which is what a press means when they
// have pointed at nothing. The ⌥ aim reaches an element through the pointer and focus used to reach none
// at all: tabbing to a link in an option left `c` offering the page.
//
// The unanswered Ask where the user is standing on a control that works it, and the innermost
// addressable element everywhere else. The control the walk stands them on is one part of the question
// (standOn), so a press made
// from a pick, a ✓ or a mark means the question those answer. Standing *in* an Ask is not
// the same fact: a user who tabbed to a hyperlink has said
// something more particular than the question containing it, and answering the question
// there both overrides what they named and made the same markup answer differently
// according to whether its question was still open — a link in a settled group gave the
// option, the identical link in an open one gave the whole group.
//
// So the ring `markHere` paints and this are two questions, and the earlier version had
// them confused. The ring says which Ask the user is in, for the walk and the answering
// keys; this says what a remark made here is about. They agree wherever the user is
// working the Ask, which is every arrival the Ask walk makes.
//
// Below that, the innermost addressable element — the aim's own reading.
//
// Chrome that shows one page target stands at it (standing-target.js), so a remark made
// from a margin control or the Asks tray is about that target. The rest of the chrome
// stands nowhere: it is where a user works on the page rather than where they stand in it,
// so a press made from it means the page whole. A thread drawn in the chrome is the other
// exception: a remark made in it is about the thread, which `c` answers in its box and `e`
// on its reply's strip, so the element the thread is about is no answer there. A box that
// takes letters never arrives here at all: the typing scope claims the letter before the
// page is asked.
//
// `documentFocused()` rather than `focused()`: a control staged in a shadow tree
// retargets to its host, and the host is the place in the document both the chrome guard
// and the element walk want.
export function createStandingElement({ isAskControl, standingIn }) {
  return function standingElement() {
    const held = documentFocused();
    if (!held || held === document.body) return null;
    if (inChrome(held) && heldThread()) return null;
    const place = placeOf(held);
    if (!place || inChrome(place)) return null;
    if (place !== held) return addressableAt(place);
    const working = isAskControl(held) ? standingIn() : null;
    return working ?? addressableAt(held);
  };
}
