/* The complete searchable Page Map dialog.

   The margin projection supplies its current target entries and activates core reading
   items. This owner retains the dialog's groups and action proxies, filters them,
   forwards contributed controls, and returns focus through the route that opened it.
   Retained nodes keep a state refresh from cancelling a held pointer or moving focus.
   Compact clusters use this same complete dialog for overflow.

   A native dialog delivers `close` after it has hidden the dialog. A close overtaken by a
   reopen therefore leaves the new opening's target and focus route intact. The Page Map's
   own Close button returns focus to its invoker. Keyboard departure and forwarded actions
   place focus synchronously, set `closeOwnsFocus`, and prevent the later close event from
   overwriting that route.

   Boot supplies margin commands and readings to one constructed map owner. Its
   mount attaches the dialog and binds controls; importing the module does not
   install application callbacks or activate the map. */

import { blockAt, says } from "./passages.js";
import { iconElement } from "./icons.js";
import { paintKeys } from "./keyboard/scopes.js";
import { el, keeps, keepsHidden } from "./widget-elements.js";
import {
  compareMarginEntryRecords,
  marginEntryRecord,
  marginEntries,
  syncForwardedMarginEntryState,
  syncMarginAgentPhase,
  visibleMarginEntryLabel,
} from "./margin-entries.js";

export const mapButton = el("button", "lf-btn lf-page-map-toggle", "Map");
mapButton.type = "button";
mapButton.hidden = true;
mapButton.title = "Open Page Map";

const dialog = document.createElement("dialog");
dialog.className = "lf-ui lf-page-map-dialog";
dialog.setAttribute("aria-label", "Page Map");
dialog.setAttribute("aria-modal", "true");
const dialogHead = el("div", "lf-page-map-head");
dialogHead.append(el("strong", "", "Page Map"));
const dialogClose = el("button", "lf-btn", "Close");
dialogClose.type = "button";
dialogHead.append(dialogClose);
const dialogSearch = el("input", "lf-page-map-search");
dialogSearch.type = "search";
dialogSearch.name = "page-map-search";
dialogSearch.placeholder = "Find an action, status, or location";
dialogSearch.setAttribute(
  "aria-label",
  "Find an action, status, or location in Page Map",
);
const dialogList = el("div", "lf-page-map-list");
const dialogEmpty = el(
  "p",
  "lf-page-map-empty",
  "No matching actions, statuses, or locations",
);
dialogEmpty.hidden = true;
dialogEmpty.setAttribute("role", "status");
dialog.append(dialogHead, dialogSearch, dialogList, dialogEmpty);

export function createPageMapDialog({
  activeInMargin,
  activateItem,
  faceFor,
  focusFallback,
}) {
  let entries = [];
  let closeOwnsFocus = false;
  let from = null;
  let target = null;

  const pageMapIsActive = () => dialog.open || activeInMargin();

  function pageMapDialogContains(candidate, node) {
    return dialog.open && target === candidate && dialog.contains(node);
  }

  const controlsOf = (offered) => marginEntries(offered.controls);

  function dialogControls(entry) {
    const records = entry.offers
      .flatMap((offered) =>
        controlsOf(offered)
          .filter((control) => entry.shownControls.has(control))
          .map((control) => ({ control, offered })),
      )
      .sort(compareMarginEntryRecords);
    return [...new Set(records.map(({ control }) => control))];
  }

  const dialogItemKey = (entry, item) => `${entry.key}:item:${item.id}`;

  function dialogControlKey(entry, control) {
    const record = marginEntryRecord(control);
    return `${entry.key}:${record.owner}:${record.key}`;
  }

  function syncDialogFace(
    button,
    { icon, glyph, label, visibleLabel = label, context = null },
  ) {
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
    let labelWord = text.querySelector(":scope > .lf-page-map-action-label-word");
    let contextNode = text.querySelector(":scope > .lf-page-map-action-context");
    if (!labelWord) labelWord = el("span", "lf-page-map-action-label-word");
    if (labelWord.textContent !== visibleLabel) labelWord.textContent = visibleLabel;
    if (context && !contextNode) contextNode = el("span", "lf-page-map-action-context");
    if (!context) {
      contextNode?.remove();
      contextNode = null;
    }
    if (contextNode && contextNode.textContent !== context)
      contextNode.textContent = context;
    const labelParts = [labelWord, ...(contextNode ? [contextNode] : [])];
    if (
      text.childNodes.length !== labelParts.length ||
      labelParts.some((node, index) => text.childNodes[index] !== node)
    )
      text.replaceChildren(...labelParts);
    if (
      button.childNodes.length !== 2 ||
      button.childNodes[0] !== face ||
      button.childNodes[1] !== text
    )
      button.replaceChildren(face, text);
    const accessibleLabel = [label, context].filter(Boolean).join(", ");
    if (button.getAttribute("aria-label") !== accessibleLabel)
      button.setAttribute("aria-label", accessibleLabel);
  }

  function syncSheetItem(button, entry, item) {
    button.lfMapEntry = entry;
    button.lfMapItem = item;
    delete button.lfMapControl;
    delete button.lfForwardedControl;
    button.dataset.lfMapItem = item.id;
    delete button.dataset.lfMapMarginEntry;
    const label = item.text || entry.title;
    syncDialogFace(button, {
      icon: faceFor(item).icon,
      label: `Open ${faceFor(item).label.toLowerCase()}: ${label}`,
      visibleLabel: label,
      // Map rows stay one line unless their producer explicitly owes a second. Version
      // comparisons do: their pair is provenance rather than part of the account.
      context: item.mapContext,
    });
    syncMarginAgentPhase(button, item.agentReceipt);
    button.disabled = false;
  }

  function syncSheetControl(button, entry, control) {
    button.lfMapEntry = entry;
    button.lfMapControl = control;
    button.lfForwardedControl = control;
    delete button.lfMapItem;
    delete button.dataset.lfMapItem;
    button.dataset.lfMapMarginEntry = dialogControlKey(entry, control);
    const record = marginEntryRecord(control);
    button.dataset.lfBehavior = record.behavior;
    button.dataset.lfTone = record.tone;
    button.dataset.lfRank = record.rank;
    button.dataset.lfState = record.state;
    syncDialogFace(button, {
      ...(record.icon ? { icon: record.icon } : { glyph: record.glyph }),
      label: record.label,
      visibleLabel: visibleMarginEntryLabel(record),
    });
    syncForwardedMarginEntryState(button, control);
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
      const controls = marginEntries(control.parentElement);
      const relation = control.getAttribute("aria-controls");
      const controlled = relation
        ? controls.find((candidate) => candidate.id === relation)
        : null;
      // A disclosure that owns another contributed control unfolds within the map.
      // The first press can then reveal the exact second action without closing the
      // only surface where a spilled contribution is reachable.
      if (controlled) {
        const entry = button.lfMapEntry;
        control.click();
        requestAnimationFrame(() => {
          const controlledKey = `control:${dialogControlKey(entry, controlled)}`;
          const revealed = dialogList.querySelector(
            `[data-lf-map-key="${CSS.escape(controlledKey)}"]`,
          );
          (revealed ?? button).focus({ preventScroll: true });
        });
        return;
      }
      const returnTo = from;
      closeOwnsFocus = true;
      dialog.close();
      if (returnTo?.isConnected && returnTo.checkVisibility())
        returnTo.focus({ preventScroll: true });
      control.click();
    };
    return button;
  }

  function filterSheet() {
    const query = dialogSearch.value.trim().toLocaleLowerCase();
    let shown = 0;
    for (const group of dialogList.children) {
      const matches = !query || group.lfMapSearch.includes(query);
      group.hidden = !matches;
      if (matches) shown += 1;
    }
    dialogEmpty.textContent = query
      ? "No matching actions, statuses, or locations"
      : "No margin controls, status indicators, or locations yet";
    dialogEmpty.hidden = shown !== 0;
  }

  function renderSheet() {
    const active = dialog.contains(document.activeElement)
      ? document.activeElement
      : null;
    const heldScroll = dialogList.scrollTop;
    const groups = new Map(
      [...dialogList.children].map((group) => [group.dataset.lfMapGroup, group]),
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
      const controls = dialogControls(entry);
      const controlOwners = new Set(
        controls.map((control) => marginEntryRecord(control).owner),
      );
      const items = entry.items.filter(
        (item) => !item.owner || !controlOwners.has(item.owner),
      );
      const wantedActions = [];
      for (const item of items) {
        const key = dialogItemKey(entry, item);
        const button = existing.get(key) ?? makeSheetAction(key);
        syncSheetItem(button, entry, item);
        wantedActions.push(button);
      }
      for (const control of controls) {
        const key = `control:${dialogControlKey(entry, control)}`;
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
    for (const child of [...dialogList.children])
      if (!wantedGroups.includes(child)) child.remove();
    wantedGroups.forEach((group, index) => {
      if (dialogList.children[index] !== group)
        dialogList.insertBefore(group, dialogList.children[index] ?? null);
    });
    filterSheet();
    dialogList.scrollTop = heldScroll;
    if (active && (!active.isConnected || !active.checkVisibility()))
      dialogSearch.focus({ preventScroll: true });
  }

  function pageMapInvoker() {
    const shelf = mapButton.closest(".lf-banner-menu");
    if (shelf?.lfInvoker?.checkVisibility()) return shelf.lfInvoker;
    return mapButton;
  }

  function renderPageMapDialog(nextEntries) {
    entries = nextEntries;
    const label = `Map (${entries.length})`;
    keepsHidden(mapButton, entries.length === 0);
    if (mapButton.textContent !== label) mapButton.textContent = label;
    if (dialog.open) renderSheet();
  }

  function openPageMap(entry = null, { invoker = null, focusSpill = false } = {}) {
    const openedFrom = invoker ?? pageMapInvoker();
    target = entry?.target ?? null;
    if (!dialog.open) {
      from = openedFrom;
      dialogSearch.value = "";
    }
    renderSheet();
    if (!dialog.open) dialog.showModal();
    const index = entry
      ? entries.findIndex((candidate) => candidate.key === entry.key)
      : -1;
    const group = index < 0 ? null : dialogList.children[index];
    if (group) {
      const listBox = dialogList.getBoundingClientRect();
      const groupBox = group.getBoundingClientRect();
      if (groupBox.top < listBox.top)
        dialogList.scrollTop -= listBox.top - groupBox.top;
      else if (groupBox.bottom > listBox.bottom)
        dialogList.scrollTop += groupBox.bottom - listBox.bottom;
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
    (destination ?? dialogSearch).focus({ preventScroll: true });
    paintKeys();
  }

  const enterPageMap = () => openPageMap();

  function leavePageMap() {
    if (!dialog.open) return;
    closeOwnsFocus = true;
    dialog.close();
  }

  function mount(root) {
    dialogSearch.addEventListener("input", filterSheet);
    mapButton.onclick = enterPageMap;
    dialog.addEventListener("close", () => {
      const returnTo = from;
      const focusOwned = closeOwnsFocus;
      closeOwnsFocus = false;
      if (dialog.open) return;
      from = null;
      target = null;
      paintKeys();
      if (focusOwned) return;
      if (returnTo?.isConnected && returnTo.checkVisibility())
        returnTo.focus({ preventScroll: true });
      else focusFallback();
    });
    dialogClose.onclick = () => dialog.close();
    root.append(dialog);
  }
  return {
    pageMapIsActive,
    pageMapDialogContains,
    renderPageMapDialog,
    openPageMap,
    enterPageMap,
    leavePageMap,
    mount,
  };
}
