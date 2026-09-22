/* The interaction gallery runs each demonstration inside a second Leaf document. This
 * adapter exposes production controls and state transitions to the parent gallery
 * without posting their gestures.
 *
 * Passive specimen startup loads this module. The shared host owns readiness;
 * this adapter choreographs production transitions without recording gestures. */

let commands;

function neutralChrome() {
  commands.detachComposer();
  commands.closePreview();
  commands.setPanel(false, { remember: false });
  if (commands.currentTray()) commands.setOpenTray(null, { remember: false });
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
      const transition = commands.threadTransitionOrigin(
        commands.fabInput,
        commands.fabInput.value,
      );
      commands.detachComposer();
      return () => commands.openInlineThread(threadId, { transition });
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
