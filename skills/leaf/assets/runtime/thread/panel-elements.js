/* Each Thread panel owns its scaffold and controls. A caller mounts an instance and
 * supplies its elements to the controllers that read them; creating a second panel
 * never aliases the first panel's DOM or reading region. */
import { focused } from "../focus.js";
import { compoundReadingRegionId, registerReadingRegion } from "../reading-regions.js";
import { closeControl, el } from "../widget-elements.js";
import { createThreadListView } from "./thread-list-view.js";
import { createThreadNarrowingView } from "./narrowing-view.js";
import { under } from "../shadow.js";
import { declareOccluder } from "../geometry.js";

let nextPanelId = 0;

export function createThreadPanelElements({
  id = `lf-thread-panel-${++nextPanelId}`,
} = {}) {
  const panel = el("section", "lf-ui lf-thread-panel");
  panel.id = id;
  const panelHead = el("div", "lf-thread-panel-head");
  const closeBtn = closeControl({
    name: "Close threads",
    title: "Close threads (Esc)",
  });
  const panelTitle = el("span", "lf-auxiliary-title", "Threads");
  // The shared native auxiliary dialog takes this retained panel's name.
  panelTitle.id = `${id}-title`;
  panel.setAttribute("aria-labelledby", panelTitle.id);
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
  const panelFoot = el("div", "lf-thread-panel-foot");
  // The body can scroll when its controls alone exhaust the window. The resize
  // grip belongs to the outer panel, so that fallback never clips its hit box.
  const panelBody = el("div", "lf-thread-panel-body");
  panelBody.append(panelHead, narrowingView, threadsFrame, panelFoot);
  panel.append(panelBody);
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
    if (!stopReadingRegion) {
      const stops = [
        registerReadingRegion({
          id: compoundReadingRegionId(panel, "body"),
          host: panel,
          body: panelBody,
        }),
        // Header and View keep selecting the list. Its outer region also owns the
        // scroll that brings the list into view when the panel body is exhausted.
        registerReadingRegion({ id, host: panelBody, body: threadsBox }),
      ];
      stopReadingRegion = () => {
        for (const stop of stops) stop();
      };
    }
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
