/* Stable DOM scaffold and passive geometry readings shared by panel views and layout.
 * Panel visibility belongs to thread-panel; the class here only renders that state. */
import { iconElement } from "../icons.js";
import { focused } from "../keyboard/scopes.js";
import { registerReadingArrangement } from "../reading-regions.js";
import { el } from "../widget-elements.js";
import { createThreadListView } from "./thread-list-view.js";
import { createThreadNarrowingView } from "./narrowing-view.js";
import { under } from "../shadow.js";

export const panel = el("dialog", "lf-ui lf-thread-panel");
panel.id = "lf-threads";
export const panelHead = el("div", "lf-thread-panel-head");
export const closeBtn = el("button", "lf-btn lf-icon-action lf-close-action");
closeBtn.append(iconElement("cross", "lf-action-icon"));
closeBtn.title = "Close threads (Esc)";
closeBtn.setAttribute("aria-label", "Close threads");
export const panelTitle = el("span", "lf-auxiliary-title", "Threads");
export const firstUnreadBtn = el("button", "lf-btn lf-first-unread", "Unread");
firstUnreadBtn.type = "button";
firstUnreadBtn.hidden = true;
firstUnreadBtn.title = "Go to first unread message";
panelHead.append(panelTitle, firstUnreadBtn, closeBtn);

export const narrowingView = createThreadNarrowingView();
export const findInput = narrowingView.searchInput;

export const threadsBox = createThreadListView();
threadsBox.className = "lf-threads";
threadsBox.tabIndex = -1;
threadsBox.setAttribute("role", "group");
threadsBox.setAttribute("aria-label", "Threads");
export const threadsFrame = el("div", "lf-threads-frame");
threadsFrame.append(threadsBox);
export const generalRow = el("div", "lf-general");
export const generalInput = document.createElement("textarea");
generalInput.name = "comment";
export const generalSend = el("button", "lf-btn", "Send");
generalRow.append(generalInput, generalSend);
export const panelFoot = el("div", "lf-thread-panel-foot");
panelFoot.append(generalRow);
panel.append(panelHead, narrowingView, threadsFrame, panelFoot);

export const inPanel = (panelIsOpen) => panelIsOpen() && under(focused(), panel);
// Whether the open panel stands over most of a box on the page — more than half its
// width. The panel stands over the right of the page without covering it, so a box the
// width of the column keeps most of itself clear at a desktop window and is read where it
// stands, while words at the right end of a line, or a box in the right margin, are under
// it. One reading for everything that asks whether the panel hides a page box: travel
// making way for its destination (chrome-layout.js) and exposure counting a message read
// (read.js). A box inside the panel is the panel's own and never under it.
export function panelStandsOver(node, rect = node.getBoundingClientRect()) {
  if (!panel.open || under(node, panel)) return false;
  const edge = panel.getBoundingClientRect().left;
  return rect.right - Math.max(rect.left, edge) > rect.width / 2;
}

let readingArrangement = null;
export function mountPanelReadingRegion() {
  if (readingArrangement) return;
  readingArrangement = registerReadingArrangement({
    owner: panel,
    content: panel,
    regions: [{ id: "lf-threads", host: panel, body: threadsBox }],
  });
  void readingArrangement.setReadingPosture("bounded");
}
