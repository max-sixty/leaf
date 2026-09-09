/* The complete searchable Page Map dialog.

   The living margin supplies its current target entries and activates core reading
   items. This owner retains the dialog's groups and action proxies, filters them,
   forwards contributed controls, and returns focus through the route that opened it.
   Retained nodes keep a state refresh from cancelling a held pointer or moving focus.
   Compact clusters use this same complete sheet for overflow. */

import { blockAt, says } from "./passages.js";
import { iconElement } from "./icons.js";
import { paintKeys } from "./keyboard/scopes.js";
import { el, keeps, keepsHidden } from "./widget-elements.js";
import {
  compareMarginControlRecords,
  marginElementRecord,
  marginElements,
  syncForwardedMarginElementState,
  visibleMarginElementLabel,
} from "./margin-elements.js";

export const mapButton = el("button", "lf-btn lf-page-map-toggle", "Map");
mapButton.type = "button";
mapButton.hidden = true;
mapButton.title = "Open the page map";

const sheet = document.createElement("dialog");
sheet.className = "lf-ui lf-page-map-sheet";
sheet.setAttribute("aria-label", "Page map");
sheet.setAttribute("aria-modal", "true");
const sheetHead = el("div", "lf-page-map-head");
sheetHead.append(el("strong", "", "Page map"));
const sheetClose = el("button", "lf-btn", "Close");
sheetClose.type = "button";
sheetClose.onclick = () => sheet.close();
sheetHead.append(sheetClose);
const sheetSearch = el("input", "lf-page-map-search");
sheetSearch.type = "search";
sheetSearch.name = "page-map-search";
sheetSearch.placeholder = "Find an action, status, or location";
sheetSearch.setAttribute(
  "aria-label",
  "Find an action, status, or location in Page map",
);
const sheetList = el("div", "lf-page-map-list");
const sheetEmpty = el(
  "p",
  "lf-page-map-empty",
  "No matching actions, statuses, or locations",
);
sheetEmpty.hidden = true;
sheetEmpty.setAttribute("role", "status");
sheet.append(sheetHead, sheetSearch, sheetList, sheetEmpty);

let entries = [];
let activeInMargin = () => false;
let activateItem;
let faceFor;
let focusFallback;
let closeOwnsFocus = false;
let from = null;
let target = null;

export function connectPageMap({ active, activate, face, focus }) {
  activeInMargin = active;
  activateItem = activate;
  faceFor = face;
  focusFallback = focus;
}

export function mountPageMap(root) {
  root.append(sheet);
}

export const pageMapIsActive = () => sheet.open || activeInMargin();

export function pageMapContextContains(candidate, node) {
  return sheet.open && target === candidate && sheet.contains(node);
}

const controlsOf = (offered) => marginElements(offered.controls);

function sheetControls(entry) {
  const records = entry.offers
    .flatMap((offered) =>
      controlsOf(offered)
        .filter((control) => entry.shownControls.has(control))
        .map((control) => ({ control, offered })),
    )
    .sort(compareMarginControlRecords);
  return [...new Set(records.map(({ control }) => control))];
}

const sheetItemKey = (entry, item) => `${entry.key}:item:${item.id}`;

function sheetControlKey(entry, control) {
  const record = marginElementRecord(control);
  return `${entry.key}:${record.owner}:${record.key}`;
}

function syncSheetFace(button, { icon, glyph, label, visibleLabel = label }) {
  let face = button.querySelector(":scope > .lf-margin-kind");
  if (icon) {
    if (!(face instanceof SVGSVGElement) || face.dataset.lfIcon !== icon)
      face = iconElement(icon, "lf-margin-kind");
  } else {
    if (!(face instanceof HTMLSpanElement)) face = document.createElement("span");
    if (face.className !== "lf-margin-kind") face.className = "lf-margin-kind";
    face.removeAttribute("data-lf-icon");
    if (face.textContent !== glyph) face.textContent = glyph;
  }
  let text = button.querySelector(":scope > .lf-page-map-action-label");
  if (!text) text = el("span", "lf-page-map-action-label");
  if (text.textContent !== visibleLabel) text.textContent = visibleLabel;
  if (
    button.childNodes.length !== 2 ||
    button.childNodes[0] !== face ||
    button.childNodes[1] !== text
  )
    button.replaceChildren(face, text);
  if (button.getAttribute("aria-label") !== label)
    button.setAttribute("aria-label", label);
}

function syncSheetItem(button, entry, item) {
  button.lfMapEntry = entry;
  button.lfMapItem = item;
  delete button.lfMapControl;
  button.dataset.lfMapItem = item.id;
  delete button.dataset.lfMapMarginElement;
  const label = item.text || entry.title;
  syncSheetFace(button, {
    icon: faceFor(item).icon,
    label: `Open ${faceFor(item).label.toLowerCase()}: ${label}`,
    visibleLabel: label,
  });
  button.disabled = false;
}

function syncSheetControl(button, entry, control) {
  button.lfMapEntry = entry;
  button.lfMapControl = control;
  delete button.lfMapItem;
  delete button.dataset.lfMapItem;
  button.dataset.lfMapMarginElement = sheetControlKey(entry, control);
  const record = marginElementRecord(control);
  button.dataset.lfBehavior = record.behavior;
  button.dataset.lfTone = record.tone;
  button.dataset.lfRole = record.role;
  button.dataset.lfState = record.state;
  syncSheetFace(button, {
    ...(record.icon ? { icon: record.icon } : { glyph: record.glyph }),
    label: record.label,
    visibleLabel: visibleMarginElementLabel(record),
  });
  syncForwardedMarginElementState(button, control);
}

function makeSheetAction(key) {
  const button = el("button", "lf-page-map-action");
  button.type = "button";
  button.dataset.lfMapKey = key;
  button.onclick = () => {
    if (button.lfMapItem) {
      activateItem(button.lfMapItem, button.lfMapEntry);
      return;
    }
    const control = button.lfMapControl;
    if (!control) return;
    const returnTo = from;
    closeOwnsFocus = true;
    sheet.close();
    if (returnTo?.isConnected && returnTo.checkVisibility())
      returnTo.focus({ preventScroll: true });
    control.click();
  };
  return button;
}

function filterSheet() {
  const query = sheetSearch.value.trim().toLocaleLowerCase();
  let shown = 0;
  for (const group of sheetList.children) {
    const matches = !query || group.lfMapSearch.includes(query);
    group.hidden = !matches;
    if (matches) shown += 1;
  }
  sheetEmpty.textContent = query
    ? "No matching actions, statuses, or locations"
    : "No margin controls, status indicators, or locations yet";
  sheetEmpty.hidden = shown !== 0;
}

function renderSheet() {
  const active = sheet.contains(document.activeElement) ? document.activeElement : null;
  const heldScroll = sheetList.scrollTop;
  const groups = new Map(
    [...sheetList.children].map((group) => [group.dataset.lfMapGroup, group]),
  );
  const wantedGroups = [];
  for (const entry of entries) {
    let group = groups.get(entry.key);
    if (!group) {
      group = el("section", "lf-page-map-group");
      group.dataset.lfMapGroup = entry.key;
      group.append(el("h3"), el("div", "lf-page-map-actions"));
    }
    const heading = group.querySelector(":scope > h3");
    if (heading.textContent !== entry.title) heading.textContent = entry.title;
    const actions = group.querySelector(":scope > .lf-page-map-actions");
    const existing = new Map(
      [...actions.children].map((button) => [button.dataset.lfMapKey, button]),
    );
    const controls = sheetControls(entry);
    const controlOwners = new Set(
      controls.map((control) => marginElementRecord(control).owner),
    );
    const items = entry.items.filter(
      (item) => !item.owner || !controlOwners.has(item.owner),
    );
    const wantedActions = [];
    for (const item of items) {
      const key = sheetItemKey(entry, item);
      const button = existing.get(key) ?? makeSheetAction(key);
      syncSheetItem(button, entry, item);
      wantedActions.push(button);
    }
    for (const control of controls) {
      const key = `control:${sheetControlKey(entry, control)}`;
      const button = existing.get(key) ?? makeSheetAction(key);
      syncSheetControl(button, entry, control);
      wantedActions.push(button);
    }
    for (const child of [...actions.children])
      if (!wantedActions.includes(child)) child.remove();
    wantedActions.forEach((button, index) => {
      if (actions.children[index] !== button)
        actions.insertBefore(button, actions.children[index] ?? null);
    });
    const passage = blockAt(entry.target);
    group.lfMapSearch = [group.textContent, passage ? says(passage) : ""]
      .filter(Boolean)
      .join(" ")
      .toLocaleLowerCase();
    wantedGroups.push(group);
  }
  for (const child of [...sheetList.children])
    if (!wantedGroups.includes(child)) child.remove();
  wantedGroups.forEach((group, index) => {
    if (sheetList.children[index] !== group)
      sheetList.insertBefore(group, sheetList.children[index] ?? null);
  });
  filterSheet();
  sheetList.scrollTop = heldScroll;
  if (active && (!active.isConnected || !active.checkVisibility()))
    sheetSearch.focus({ preventScroll: true });
}

function pageMapInvoker() {
  const shelf = mapButton.closest(".lf-banner-menu");
  if (shelf?.lfInvoker?.checkVisibility()) return shelf.lfInvoker;
  return mapButton;
}

export function renderPageMap(nextEntries) {
  entries = nextEntries;
  const label = `Map (${entries.length})`;
  keepsHidden(mapButton, entries.length === 0);
  if (mapButton.textContent !== label) mapButton.textContent = label;
  if (sheet.open) renderSheet();
}

export function openPageMap(entry = null, { invoker = null, focusSpill = false } = {}) {
  const openedFrom = invoker ?? pageMapInvoker();
  target = entry?.target ?? null;
  if (!sheet.open) {
    from = openedFrom;
    sheetSearch.value = "";
  }
  renderSheet();
  if (!sheet.open) sheet.showModal();
  const index = entry
    ? entries.findIndex((candidate) => candidate.key === entry.key)
    : -1;
  const group = index < 0 ? null : sheetList.children[index];
  if (group) {
    const listBox = sheetList.getBoundingClientRect();
    const groupBox = group.getBoundingClientRect();
    if (groupBox.top < listBox.top) sheetList.scrollTop -= listBox.top - groupBox.top;
    else if (groupBox.bottom > listBox.bottom)
      sheetList.scrollTop += groupBox.bottom - listBox.bottom;
  }
  const spilled = focusSpill ? openedFrom.lfFirstSpilledOption : null;
  const forwarded = spilled?.lfForwardedControl ?? spilled;
  const destination = focusSpill
    ? [...(group?.querySelectorAll(".lf-page-map-action") ?? [])].find(
        (button) =>
          button.lfMapControl === forwarded ||
          spilled?.lfChoice?.items.some((item) => button.lfMapItem?.id === item.id),
      )
    : group?.querySelector(".lf-page-map-action");
  (destination ?? sheetSearch).focus({ preventScroll: true });
  paintKeys();
}

export const enterPageMap = () => openPageMap();

export function leavePageMap() {
  if (!sheet.open) return;
  closeOwnsFocus = true;
  sheet.close();
}

sheetSearch.addEventListener("input", filterSheet);
mapButton.onclick = enterPageMap;
sheet.addEventListener("close", () => {
  const returnTo = from;
  const focusOwned = closeOwnsFocus;
  closeOwnsFocus = false;
  if (sheet.open) return;
  from = null;
  target = null;
  paintKeys();
  if (focusOwned) return;
  if (returnTo?.isConnected && returnTo.checkVisibility())
    returnTo.focus({ preventScroll: true });
  else focusFallback();
});
