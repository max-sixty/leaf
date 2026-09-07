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

let toggleBtn;
let panelIsOpen;
let setPanel;
let detachComposer;
let fabInput;
let openComposer;
let closePreview;
let openInlineThread;
let threadTransitionOrigin;
let currentTray;
let showTray;

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
  detachComposer();
  closePreview();
  setPanel(false, { remember: false })?.finish();
  if (currentTray()) showTray(null, { remember: false });
}

async function prepare() {
  await presented();
  const [banner, chromeLayout, selection, margin, trays] = await Promise.all([
    import("./banner.js"),
    import("./chrome-layout.js"),
    import("./composing/selection.js"),
    import("./living-margin.js"),
    import("./trays.js"),
  ]);
  ({ toggleBtn } = banner);
  ({ panelIsOpen, setPanel } = chromeLayout);
  ({ detachComposer, fabInput, openComposer } = selection);
  ({ closePreview, openInlineThread, threadTransitionOrigin } = margin);
  ({ currentTray, showTray } = trays);
  neutralChrome();
}

window.leafInteractionGalleryFrame = {
  ready: prepare(),
  resetComment(text) {
    neutralChrome();
    openComposer({ section: "bg-thread-text" }, text, { focus: false });
  },
  commentInput() {
    return fabInput;
  },
  submitComment(threadId) {
    const transition = threadTransitionOrigin(fabInput, fabInput.value);
    detachComposer();
    return openInlineThread(threadId, transition);
  },
  resetThreads() {
    neutralChrome();
  },
  threadsButton() {
    return toggleBtn;
  },
  threadsOpen() {
    return panelIsOpen();
  },
  setThreads(open) {
    return setPanel(open, { remember: false });
  },
};
