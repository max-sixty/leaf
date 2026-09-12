/* Stable DOM scaffold and passive geometry readings shared by panel views and layout.
 * Panel visibility belongs to thread-panel; the class here only renders that state. */
import { iconElement } from "../icons.js";
import { focused } from "../keyboard/scopes.js";
import { containsAcross } from "../passages.js";
import { COVERING } from "../chrome-layout.js";
import { registerReadingArrangement } from "../reading-regions.js";
import { el } from "../widget-elements.js";

export const panel = el("dialog", "lf-ui lf-thread-panel");
panel.id = "lf-threads";
export const panelHead = el("div", "lf-thread-panel-head");
export const closeBtn = el("button", "lf-btn lf-icon-action lf-close-action");
closeBtn.append(iconElement("cross", "lf-action-icon"));
closeBtn.title = "Close threads (Esc)";
closeBtn.setAttribute("aria-label", "Close threads");
export const panelTitle = el("span", "lf-auxiliary-title", "Threads");
panelHead.append(panelTitle, closeBtn);

export const filterToggle = el("button", "lf-btn lf-thread-filter-toggle", "Filters");
filterToggle.type = "button";
filterToggle.setAttribute("aria-expanded", "false");
filterToggle.setAttribute("aria-controls", "lf-thread-filters");
export const viewSummary = el("span", "lf-thread-view-summary");
export const resetFilters = el("button", "lf-btn lf-thread-filter-reset", "Reset");
resetFilters.type = "button";
resetFilters.setAttribute("aria-label", "Reset thread filters");
export const viewRow = el("div", "lf-thread-view");
viewRow.hidden = true;
viewRow.append(viewSummary, resetFilters);

const findRow = el("div", "lf-find");
export const findInput = document.createElement("input");
findInput.type = "search";
findInput.name = "thread-search";
findInput.className = "lf-find-box";
findInput.placeholder = "Find in threads";
findInput.setAttribute("aria-label", "Find in threads");
findInput.title = "Find in threads";
findRow.append(findInput, filterToggle);

const filterButton = (kind, value, label, className = "") => {
  const button = el(
    "button",
    `lf-btn lf-thread-filter${className ? ` ${className}` : ""}`,
    label,
  );
  button.type = "button";
  button.dataset.filterKind = kind;
  button.dataset.filterValue = value;
  button.dataset.filterLabel = label;
  button.setAttribute("aria-pressed", "false");
  return button;
};
const filterGroup = (label, buttons) => {
  const group = el("div", "lf-thread-filter-group");
  group.setAttribute("role", "group");
  group.setAttribute("aria-label", label);
  group.append(...buttons);
  return group;
};

export const stateButtons = {
  open: filterButton("state", "open", "Open"),
  reader: filterButton("state", "reader", "On you", "lf-needs"),
  agent: filterButton("state", "agent", "On agent"),
  resolved: filterButton("state", "resolved", "Resolved"),
};
export const needsBtn = stateButtons.reader;
export const scopeButtons = {
  page: filterButton("scope", "page", "Page"),
  local: filterButton("scope", "local", "Anchored"),
};
export const subjectButtons = {
  content: filterButton("subject", "content", "Content"),
  layer: filterButton("subject", "layer", "Layer"),
};
export const goneBtn = filterButton("gone", "gone", "No longer here");
goneBtn.hidden = true;

export const filterControls = el("div", "lf-thread-filters");
filterControls.id = "lf-thread-filters";
filterControls.hidden = true;
filterControls.setAttribute("aria-label", "Filter threads");
const facetRow = el("div", "lf-thread-filter-facets");
facetRow.append(
  filterGroup("Thread scope", Object.values(scopeButtons)),
  filterGroup("Thread subject", Object.values(subjectButtons)),
  filterGroup("Thread placement", [goneBtn]),
);
filterControls.append(
  filterGroup("Thread state", Object.values(stateButtons)),
  facetRow,
);

export const threadsBox = el("div", "lf-threads");
threadsBox.tabIndex = -1;
threadsBox.setAttribute("role", "group");
threadsBox.setAttribute("aria-label", "Threads");
export const threadsFrame = el("div", "lf-threads-frame");
threadsFrame.append(threadsBox);
export const generalRow = el("div", "lf-general");
export const generalInput = document.createElement("textarea");
generalInput.name = "comment";
export const generalSend = el("button", "lf-btn primary", "Send");
generalRow.append(generalInput, generalSend);
export const panelFoot = el("div", "lf-thread-panel-foot");
panelFoot.append(generalRow);
panel.append(panelHead, findRow, viewRow, filterControls, threadsFrame, panelFoot);

export const inPanel = (panelIsOpen) =>
  panelIsOpen() && containsAcross(panel, focused());
const covering = matchMedia(COVERING);
export const panelWouldCover = () => covering.matches;

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
