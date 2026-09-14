/* The complete searchable Page Map dialog.

   The margin projection supplies its current target entries and activates core reading
   items. This owner retains the dialog's groups and its own projections of contributed
   records, filters them, and returns focus through the route that opened it.
   Retained nodes keep a state refresh from cancelling a held pointer or moving focus.
   Compact clusters use this same complete dialog for overflow.

   A native dialog delivers `close` after it has hidden the dialog. A close overtaken by a
   reopen therefore leaves the new opening's target and focus route intact. The Page Map's
   own Close button returns focus to its invoker. Keyboard departure and record actions
   place focus synchronously, set `closeOwnsFocus`, and prevent the later close event from
   overwriting that route.

   Boot supplies margin commands and readings to one constructed map owner. Its
   mount attaches the dialog and binds controls; importing the module does not
   install application callbacks or activate the map. */

import { blockAt, says } from "./passages.js";
import { html, render } from "../vendor/browser-runtime.js";
import { iconElement } from "./icons.js";
import { paintKeys } from "./keyboard/scopes.js";
import { projectCommandScope } from "./keyboard/scopes.js";
import { el, keeps, keepsHidden } from "./widget-elements.js";
import {
  clearMarginEntryControls,
  compareMarginEntryRecords,
  syncMarginAgentWorkflow,
  trackMarginEntryControl,
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
  const faceNodes = new WeakMap();

  const pageMapIsActive = () => dialog.open || activeInMargin();

  function pageMapDialogContains(candidate, node) {
    return dialog.open && target === candidate && dialog.contains(node);
  }

  function dialogControls(entry) {
    const records = entry.offers
      .flatMap((offered) =>
        offered.reading.entries
          .filter((record) => record.visible)
          .map((record) => ({ record, offered })),
      )
      .sort(compareMarginEntryRecords);
    return records;
  }

  const dialogItemKey = (entry, item) => `${entry.key}:item:${item.id}`;

  function dialogControlKey(entry, offered, record) {
    return `${entry.key}:${record.owner}:${record.key}`;
  }

  function syncDialogFace(
    button,
    { icon, glyph, label, visibleLabel = label, context = null },
  ) {
    let face = faceNodes.get(button);
    if (icon) {
      if (!(face instanceof SVGSVGElement) || face.dataset.lfIcon !== icon)
        face = iconElement(icon, "lf-margin-kind");
    } else {
      face = html`<span class="lf-margin-kind">${glyph}</span>`;
    }
    faceNodes.set(button, face);
    render(
      html`${face}<span class="lf-page-map-action-label"
          ><span class="lf-page-map-action-label-word">${visibleLabel}</span>${
            context
              ? html`<span class="lf-page-map-action-context">${context}</span>`
              : null
          }</span
        >`,
      button,
    );
    const accessibleLabel = [label, context].filter(Boolean).join(", ");
    if (button.getAttribute("aria-label") !== accessibleLabel)
      button.setAttribute("aria-label", accessibleLabel);
  }

  function syncSheetItem(button, entry, item) {
    button.lfMapEntry = entry;
    button.lfMapItem = item;
    delete button.lfMapOffer;
    delete button.lfMapRecord;
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
    syncMarginAgentWorkflow(button, item.workflowReceipt);
    button.disabled = false;
  }

  function syncSheetControl(button, entry, offered, record) {
    button.lfMapEntry = entry;
    button.lfMapOffer = offered;
    button.lfMapRecord = record;
    delete button.lfMapItem;
    delete button.dataset.lfMapItem;
    button.dataset.lfMapMarginEntry = dialogControlKey(entry, offered, record);
    button.dataset.lfBehavior = record.behavior;
    button.dataset.lfTone = record.tone;
    button.dataset.lfRank = record.rank;
    button.dataset.lfState = record.state;
    button.dataset.lfMarginEntryKey = record.key;
    button.dataset.lfMarginEntryOwner = record.owner;
    button.toggleAttribute("data-lf-target-selected", record.selected);
    if (record.pressed == null) button.removeAttribute("aria-pressed");
    else keeps(button, "aria-pressed", record.pressed);
    if (record.state === "busy") {
      button.setAttribute("aria-busy", "true");
    } else {
      button.removeAttribute("aria-busy");
    }
    button.disabled = record.disabled || record.behavior === "status";
    if (record.behavior === "disclosure")
      keeps(button, "aria-expanded", record.relation?.expanded ?? false);
    else button.removeAttribute("aria-expanded");
    if (record.relation?.kind === "element")
      keeps(button, "aria-controls", record.relation.id);
    else button.removeAttribute("aria-controls");
    if (record.relation?.popup) keeps(button, "aria-haspopup", record.relation.popup);
    else button.removeAttribute("aria-haspopup");
    if (record.description) keeps(button, "aria-description", record.description);
    else button.removeAttribute("aria-description");
    if (record.title) keeps(button, "title", record.title);
    else button.removeAttribute("title");
    const workflow = entry.workflowCarrier;
    const receipt =
      workflow?.key === record.key && workflow.owner === record.owner
        ? workflow.receipt
        : record.workflowReceipt;
    syncMarginAgentWorkflow(button, receipt);
    projectCommandScope(button, record.scope);
    syncDialogFace(button, {
      ...(record.icon ? { icon: record.icon } : { glyph: record.glyph }),
      label: record.accessibleLabel,
      visibleLabel: visibleMarginEntryLabel(record),
      context: record.context,
    });
    trackMarginEntryControl(offered, "map", record.key, button);
  }

  function makeSheetAction(key) {
    const button = el("button", "lf-page-map-action");
    button.type = "button";
    button.dataset.lfMapKey = key;
    button.onclick = (event) => {
      if (button.lfMapItem) {
        activateItem(button.lfMapItem, button.lfMapEntry);
        return;
      }
      const offered = button.lfMapOffer;
      const record = button.lfMapRecord;
      if (!offered || !record) return;
      const relation = record.relation;
      // A disclosure that owns another contributed control unfolds within the map.
      // The first press can then reveal the exact second action without closing the
      // only surface where a spilled contribution is reachable.
      if (relation?.kind === "entries") {
        const entry = button.lfMapEntry;
        offered.registration.activate(record.key, {
          origin: button,
          surface: "map",
          input: event.detail === 0 ? "keyboard" : "pointer",
        });
        requestAnimationFrame(() => {
          const revealed = relation.keys
            .map((key) =>
              dialogList.querySelector(
                `[data-lf-map-key="${CSS.escape(`control:${entry.key}:${offered.key}:${key}`)}"]`,
              ),
            )
            .find((candidate) => candidate?.checkVisibility());
          (revealed ?? button).focus({ preventScroll: true });
        });
        return;
      }
      const returnTo = from;
      closeOwnsFocus = true;
      dialog.close();
      if (returnTo?.isConnected && returnTo.checkVisibility())
        returnTo.focus({ preventScroll: true });
      offered.registration.activate(record.key, {
        origin: button,
        surface: "map",
        input: event.detail === 0 ? "keyboard" : "pointer",
      });
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
      const controlOwners = new Set(controls.map(({ record }) => record.owner));
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
      for (const { offered, record } of controls) {
        const key = `control:${dialogControlKey(entry, offered, record)}`;
        const button = existing.get(key) ?? makeSheetAction(key);
        syncSheetControl(button, entry, offered, record);
        wantedActions.push(button);
      }
      for (const button of wantedActions) {
        const relation = button.lfMapRecord?.relation;
        if (relation?.kind !== "entries") continue;
        const related = relation.keys
          .map((relatedKey) =>
            wantedActions.find(
              (candidate) =>
                candidate.lfMapOffer === button.lfMapOffer &&
                candidate.lfMapRecord?.key === relatedKey,
            ),
          )
          .filter(Boolean);
        related.forEach((candidate) => {
          if (!candidate.id)
            candidate.id = `lf-page-map-entry-${candidate.dataset.lfMapMarginEntry.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
        });
        if (related.length)
          keeps(
            button,
            "aria-controls",
            related.map((candidate) => candidate.id).join(" "),
          );
        else button.removeAttribute("aria-controls");
      }
      for (const offered of entry.offers)
        clearMarginEntryControls(
          offered,
          "map",
          new Set(
            controls
              .filter((candidate) => candidate.offered === offered)
              .map(({ record }) => record.key),
          ),
        );
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
    const destination = focusSpill
      ? [...(group?.querySelectorAll(".lf-page-map-action") ?? [])].find(
          (button) =>
            (button.lfMapRecord &&
              button.lfMapRecord.key === spilled?.dataset.lfMarginEntryKey &&
              button.lfMapRecord.owner === spilled?.dataset.lfMarginEntryOwner) ||
            spilled?.lfChoice?.items.some((item) => button.lfMapItem?.id === item.id),
        )
      : group?.querySelector(".lf-page-map-action");
    (destination ?? dialogSearch).focus({ preventScroll: true });
    paintKeys();
  }

  const enterPageMap = () => openPageMap();

  // Focus belongs to the visible control in this native layer. A contributor closing
  // its disclosure can use the registration's surface reading to return here.
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
