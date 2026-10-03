/* The interaction gallery runs each demonstration inside a second Leaf document. This
 * adapter exposes production controls and state transitions to the parent gallery
 * without posting their gestures.
 *
 * Passive sample startup loads this module. The shared host owns readiness;
 * this adapter choreographs production transitions without recording gestures. */

import { retainUserIntent } from "./user-intent.js";

let commands;

function neutralChrome() {
  commands.detachComposer();
  commands.closePreview?.();
  commands.setPanel(false, { remember: false });
  if (commands.currentDrawer()) commands.setOpenDrawer(null, { remember: false });
}

export function mountReplay(capabilities) {
  commands = capabilities;
  window.leafInteractionGalleryFrame = {
    resetComment(section, text) {
      neutralChrome();
      commands.openComposer({ section }, text, { focus: false });
    },
    commentInput() {
      return commands.fabInput;
    },
    submitComment(threadId) {
      const intent = retainUserIntent();
      const transition = commands.threadTransitionOrigin?.(
        commands.fabInput,
        commands.fabFrameAt(),
      );
      commands.detachComposer();
      return () => commands.openThread(threadId, { travel: false, intent, transition });
    },
    resetThreads() {
      neutralChrome();
    },
    threadsButton() {
      return commands.toggleBtn;
    },
    threadsOpen() {
      return commands.panelIsOpen();
    },
    setThreads(open) {
      commands.setPanel(open, { remember: false });
    },
  };
}
