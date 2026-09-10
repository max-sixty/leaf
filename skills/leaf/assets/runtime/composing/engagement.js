/* Reader gestures and drafts that a document replacement would discard. */
import { runtime } from "../context.js";
import { focused } from "../keyboard/scopes.js";
import { replyBoxHasDraft } from "../conversation/replies.js";
import { draftOf } from "./input.js";
import { composerOpen } from "./selection.js";

export function createEngagement({
  hasPending,
  fabAnchorAt,
  targetChooserOpen,
  pageComposerDrawing,
}) {
  function unaccountedGesture() {
    return (
      runtime.undoing || hasPending() || Boolean(document.querySelector(".lf-dragging"))
    );
  }

  function midComposition() {
    const active = focused();
    const replyDraft = replyBoxHasDraft(active) ?? null;
    return (
      composerOpen ||
      Boolean(pageComposerDrawing()) ||
      targetChooserOpen() ||
      Boolean(fabAnchorAt()) ||
      unaccountedGesture() ||
      (active?.tagName === "TEXTAREA" &&
        (draftOf(active) !== "" ||
          replyDraft === true ||
          (replyDraft === null && active.hasAttribute("data-lf-offer"))))
    );
  }

  return { unaccountedGesture, midComposition };
}
