/* Each Thread panel owns its scaffold and controls. A caller mounts an instance and
 * supplies its elements to the controllers that read them; creating a second panel
 * never aliases the first panel's DOM or reading region. */
import { focused } from "../keyboard/scopes.js";
import { registerReadingRegion } from "../reading-regions.js";
import { closeControl, el } from "../widget-elements.js";
import { createThreadListView } from "./thread-list-view.js";
import { createThreadNarrowingView } from "./narrowing-view.js";
import { under } from "../shadow.js";
import { declareOccluder } from "../geometry.js";
import { textField } from "../composing/text-field.js";

let nextPanelId = 0;

export function createThreadPanelElements({
  id = `lf-thread-panel-${++nextPanelId}`,
} = {}) {
  const panel = el("dialog", "lf-ui lf-thread-panel");
  panel.id = id;
  const panelHead = el("div", "lf-thread-panel-head");
  const closeBtn = closeControl({
    name: "Close threads",
    title: "Close threads (Esc)",
  });
  const panelTitle = el("span", "lf-auxiliary-title", "Threads");
  const firstUnreadBtn = el("button", "lf-btn lf-first-unread", "Next unread");
  firstUnreadBtn.type = "button";
  firstUnreadBtn.hidden = true;
  firstUnreadBtn.title = "Go to first unread message";
  panelHead.append(panelTitle, firstUnreadBtn, closeBtn);

  const narrowingView = createThreadNarrowingView();
  const findInput = narrowingView.searchInput;

  const threadsBox = createThreadListView();
  threadsBox.className = "lf-threads";
  threadsBox.tabIndex = -1;
  threadsBox.setAttribute("role", "group");
  threadsBox.setAttribute("aria-label", "Threads");
  const threadsFrame = el("div", "lf-threads-frame");
  threadsFrame.append(threadsBox);
  const generalRow = el("div", "lf-general");
  const generalInput = textField();
  generalInput.name = "comment";
  const generalSend = el("button", "lf-btn", "Send");
  generalRow.append(generalInput, generalSend);
  const panelFoot = el("div", "lf-thread-panel-foot");
  panelFoot.append(generalRow);
  panel.append(panelHead, narrowingView, threadsFrame, panelFoot);
  let stopOccluding = null;
  const mountOverlay = () => {
    stopOccluding ??= declareOccluder(panel);
    return () => {
      stopOccluding?.();
      stopOccluding = null;
    };
  };
  let stopReadingRegion = null;
  const mountReadingRegion = () => {
    stopReadingRegion ??= registerReadingRegion({ id, host: panel, body: threadsBox });
    return () => {
      stopReadingRegion?.();
      stopReadingRegion = null;
    };
  };

  return {
    panel,
    closeBtn,
    firstUnreadBtn,
    narrowingView,
    findInput,
    threadsBox,
    generalInput,
    generalSend,
    panelFoot,
    inPanel: (panelIsOpen) => panelIsOpen() && under(focused(), panel),
    mountOverlay,
    mountReadingRegion,
    dispose: () => {
      stopReadingRegion?.();
      stopReadingRegion = null;
      stopOccluding?.();
      stopOccluding = null;
    },
  };
}
