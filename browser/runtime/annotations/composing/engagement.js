// Compiled from engagement.ts by build/typescript.mjs; edit that file.
/* User gestures and drafts that a document replacement would discard. */
import { TEXT_BOX } from "../../dom/control-selectors.js";
import { dragHeld } from "../../dom/widget-elements.js";
import { focused } from "../../dom/focus.js";
import {
  replyCompositionHasDraft,
  replyDraftsHold,
} from "../../records/thread/replies.js";
import { pageSelection, selectionAnchor } from "./capture.js";
import { draftOf } from "./input.js";
import { elementById } from "../../readings/passages.js";
import { composerOpen } from "./selection.js";

export function createEngagement({ hasPending, fabAnchorAt, targetPickerOpen }) {
  function unaccountedGesture() {
    return hasPending() || dragHeld();
  }

  // Admission supplies the install's native-node retention proof. A selected passage
  // or anchored comment also needs its complete authored anchor scope kept, since
  // preserving a paragraph alone can still leave its durable quote ambiguous.
  function midComposition(retains = () => false) {
    const active = focused();
    const replyDraft = replyCompositionHasDraft(active);
    const selection = pageSelection();
    const anchors = [fabAnchorAt(), selection && selectionAnchor(selection)].filter(
      (anchor) => anchor !== null,
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
