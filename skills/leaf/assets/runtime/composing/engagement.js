/* User gestures and drafts that a document replacement would discard. */
import { TEXT_BOX } from "../control-selectors.js";
import { runtime } from "../context.js";
import { dragHeld } from "../widget-elements.js";
import { focused } from "../keyboard/scopes.js";
import { replyCompositionHasDraft, hasReplyDraft } from "../thread/replies.js";
import { pageSelection } from "./capture.js";
import { draftOf } from "./input.js";
import { composerOpen } from "./selection.js";

export function createEngagement({ hasPending, fabAnchorAt, targetPickerOpen }) {
  function unaccountedGesture() {
    return runtime.undoing || hasPending() || dragHeld();
  }

  function midComposition() {
    const active = focused();
    const replyDraft = replyCompositionHasDraft(active);
    return (
      composerOpen ||
      targetPickerOpen() ||
      Boolean(fabAnchorAt()) ||
      Boolean(pageSelection()) ||
      unaccountedGesture() ||
      hasReplyDraft() ||
      replyDraft === true ||
      (active?.matches(TEXT_BOX) &&
        (draftOf(active) !== "" ||
          (replyDraft === null && active.hasAttribute("data-lf-offer"))))
    );
  }

  return { unaccountedGesture, midComposition };
}
