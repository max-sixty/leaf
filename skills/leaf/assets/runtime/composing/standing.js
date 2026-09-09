/* The semantic item a comment or reaction at the current focus addresses. */
import { documentFocused } from "../keyboard/scopes.js";
import { inChrome } from "../passages.js";
import { itemAt } from "../anchor-resolution.js";

// The item the reader is standing in, which is what a press means when they have pointed
// at nothing. The ⌥ aim reaches an item through the pointer and focus used to reach none
// at all: tabbing to a link in an option left `c` offering the page.
//
// The unanswered Ask where the reader is standing on a control that works it, and the innermost
// item everywhere else. The control the walk stands them on is one part of the question
// (standOn), so a press made
// from a pick, a ✓ or a mark means the question those answer. Standing *in* an Ask is not
// the same fact: a reader who tabbed to a hyperlink has said
// something more particular than the question containing it, and answering the question
// there both overrides what they named and made the same markup answer differently
// according to whether its question was still open — a link in a settled group gave the
// option, the identical link in an open one gave the whole group.
//
// So the ring `markHere` paints and this are two questions, and the earlier version had
// them confused. The ring says which Ask the reader is in, for the walk and the answering
// keys; this says what a remark made here is about. They agree wherever the reader is
// working the Ask, which is every arrival the Ask walk makes.
//
// Below that, the innermost item — the aim's own reading — through `askPlace`, so a
// control a widget hoisted into the margin speaks for the Ask it points back at rather
// than for the block it hangs beside.
//
// Focus in the chrome is not a place in the page. The banner, the panel and the trays are
// where a reader works on the page rather than where they stand in it, so a press made
// from one means the page whole. A box that takes letters never arrives here at all: the
// typing scope claims the letter before the page is asked.
//
// `documentFocused()` rather than `focused()`: a control
// staged in a shadow tree retargets to its host, and the host is the place in the document
// both the chrome guard and the item walk want. standingConversation below wants the inner
// reading, and says so.
export function createStandingItem({ isAskControl, askPlace, standingIn }) {
  return function standingItem() {
    const held = documentFocused();
    if (!held || held === document.body || inChrome(held)) return null;
    const working = isAskControl(held) ? standingIn() : null;
    return working ?? itemAt(askPlace(held));
  };
}
