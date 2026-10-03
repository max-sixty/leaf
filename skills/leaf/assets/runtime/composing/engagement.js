/* User gestures and drafts that a document replacement would discard. */
import { TEXT_BOX } from "../control-selectors.js";
import { runtime } from "../context.js";
import { dragHeld } from "../widget-elements.js";
import { focused } from "../keyboard/scopes.js";
import { replyBoxHasDraft } from "../thread/replies.js";
import { draftOf } from "./input.js";
import { composerOpen } from "./selection.js";

export function createEngagement({
  hasPending,
  fabAnchorAt,
  targetPickerOpen,
  pageComposerDrawing,
}) {
  function unaccountedGesture() {
    return runtime.undoing || hasPending() || dragHeld();
  }

  function midComposition() {
    const active = focused();
    const replyDraft = replyBoxHasDraft(active);
    return (
      composerOpen ||
      Boolean(pageComposerDrawing()) ||
      targetPickerOpen() ||
      Boolean(fabAnchorAt()) ||
      unaccountedGesture() ||
      (active?.matches(TEXT_BOX) &&
        (draftOf(active) !== "" ||
          replyDraft === true ||
          (replyDraft === null && active.hasAttribute("data-lf-offer"))))
    );
  }

  return { unaccountedGesture, midComposition };
}
