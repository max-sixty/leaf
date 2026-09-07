/* The interaction gallery frames page-global Leaf chrome inside a second document.
 * This adapter exposes the production controls and state transitions to the parent
 * gallery without posting their gestures. Content widgets stay in the parent page;
 * only chrome that is singleton by design needs this document boundary. */

import { toggleBtn } from "./banner.js";
import { panelIsOpen, setPanel } from "./chrome-layout.js";
import { detachComposer, fabInput, openComposer } from "./composing/selection.js";
import {
  closePreview,
  openInlineThread,
  threadTransitionOrigin,
} from "./living-margin.js";
import { currentTray, showTray } from "./trays.js";

const presented = new Promise((resolve) => {
  if (document.body.hasAttribute("data-lf-presented")) {
    resolve();
    return;
  }
  const observer = new MutationObserver(() => {
    if (!document.body.hasAttribute("data-lf-presented")) return;
    observer.disconnect();
    resolve();
  });
  observer.observe(document.body, { attributes: true });
});

function neutralChrome() {
  detachComposer();
  closePreview();
  setPanel(false, { remember: false })?.finish();
  if (currentTray()) showTray(null, { remember: false });
}

window.leafInteractionGalleryFrame = {
  ready: presented.then(neutralChrome),
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
