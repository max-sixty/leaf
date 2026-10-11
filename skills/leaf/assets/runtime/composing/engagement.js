/* User gestures and drafts that a document replacement would discard. */
import { TEXT_BOX } from "../control-selectors.js";
import { runtime } from "../context.js";
import { dragHeld } from "../widget-elements.js";
import { focused } from "../focus.js";
import { replyCompositionHasDraft, replyDraftsHold } from "../thread/replies.js";
import { pageSelection, selectionAnchor } from "./capture.js";
import { draftOf } from "./input.js";
import { elementById } from "../passages.js";
import { composerOpen } from "./selection.js";

export function createEngagement({ hasPending, fabAnchorAt, targetPickerOpen }) {
  function unaccountedGesture() {
    return runtime.undoing || hasPending() || dragHeld();
  }

  // Admission supplies the install's native-node retention proof. A selected passage
  // or anchored comment also needs its complete authored anchor scope kept, since
  // preserving a paragraph alone can still leave its durable quote ambiguous.
  function midComposition(retains = () => false) {
    const active = focused();
    const replyDraft = replyCompositionHasDraft(active);
    const selection = pageSelection();
    const anchors = [fabAnchorAt(), selection && selectionAnchor(selection)].filter(
      Boolean,
    );
    const keptPassages =
      anchors.length > 0 &&
      anchors.every((anchor) => retains(elementById(anchor.section)));
    return (
      ((composerOpen || anchors.length > 0) && !keptPassages) ||
      targetPickerOpen() ||
      unaccountedGesture() ||
      replyDraftsHold(retains) ||
      (active?.matches(TEXT_BOX) &&
        !retains(active) &&
        (replyDraft === true ||
          draftOf(active) !== "" ||
          (replyDraft === null && active.hasAttribute("data-lf-offer"))))
    );
  }

  return { unaccountedGesture, midComposition };
}
