/* The interaction gallery frames page-global Leaf chrome inside a second document.
 * This adapter exposes the production controls and state transitions to the parent
 * gallery without posting their gestures. Content widgets stay in the parent page;
 * only chrome that is singleton by design needs this document boundary.
 *
 * The parent loads this adapter into a complete document before it loads Leaf. The
 * adapter can therefore hear Leaf's startup outcome without racing it, while Leaf does
 * not measure the frame until its stylesheet has loaded. Readiness is Leaf's
 * presentation fact rather than a timer: a slow state read may delay the frame, while
 * a failed startup rejects it immediately. */

let commands;
let mountCommands;
const mounted = new Promise((resolve) => {
  mountCommands = resolve;
});

function presented() {
  return new Promise((resolve, reject) => {
    const observer = new MutationObserver(() => {
      if (!document.body.hasAttribute("data-lf-presented")) return;
      cleanup();
      resolve();
    });
    const failed = () => {
      cleanup();
      reject(new Error("the contained Leaf page did not finish presenting"));
    };
    const cleanup = () => {
      observer.disconnect();
      window.removeEventListener("lf-startup-failed", failed);
    };
    if (document.body.hasAttribute("data-lf-presented")) {
      resolve();
      return;
    }
    observer.observe(document.body, { attributes: true });
    window.addEventListener("lf-startup-failed", failed, { once: true });
  });
}

function neutralChrome() {
  commands.detachComposer();
  commands.closePreview();
  commands.setPanel(false, { remember: false })?.finish();
  if (commands.currentTray()) commands.setOpenTray(null, { remember: false });
}

async function prepare() {
  await Promise.all([presented(), mounted]);
  neutralChrome();
}

window.leafInteractionGalleryFrame = {
  mount(capabilities) {
    if (commands) throw new Error("the interaction gallery adapter mounted twice");
    commands = capabilities;
    mountCommands();
  },
  ready: prepare(),
  resetComment(text) {
    neutralChrome();
    commands.openComposer({ section: "bg-thread-text" }, text, { focus: false });
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
    return commands.openInlineThread(threadId, transition);
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
    return commands.setPanel(open, { remember: false });
  },
};
