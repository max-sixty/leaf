/* The complete searchable Page Map dialog.

   The margin projection supplies its current target entries and activates core reading
   items. One keyed Lit projection renders its groups and contributed records, filters
   them, and returns focus through the route that opened it. Retained nodes keep a state
   refresh from cancelling a held pointer or moving focus.
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
import { html, nothing, render, repeat } from "../vendor/browser-runtime.js";
import { iconTemplate } from "./icons.js";
import { focused, paintKeys } from "./keyboard/scopes.js";
import { el, keeps } from "./widget-elements.js";
import {
  BANNER_CONTROL_RANK,
  registerBannerControl,
  showBannerControl,
} from "./banner-shelf.js";
import {
  clearMarginEntryControls,
  compareMarginEntryRecords,
  presentMarginEntryHost,
  syncMarginAgentWorkflow,
  trackMarginEntryControl,
  visibleMarginEntryLabel,
} from "./margin-entries.js";

export const mapButton = el("button", "lf-btn lf-page-map-toggle", "Map");
mapButton.type = "button";
mapButton.title = "Open Page Map";
registerBannerControl({
  key: "map",
  control: mapButton,
  rank: BANNER_CONTROL_RANK.map,
  present: false,
});

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
  let trackedOffers = new Set();

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

  const dialogItemKey = (entry, item) => JSON.stringify(["item", entry.key, item.id]);

  function dialogControlKey(entry, offered, record) {
    return JSON.stringify(["control", entry.key, offered.key, record.key]);
  }

  const dialogControlId = (entry, offered, record) =>
    `lf-page-map-entry-${encodeURIComponent(dialogControlKey(entry, offered, record))}`;

  const sheetFace = ({ icon, glyph, visibleLabel, context }) =>
    html`${
        icon
          ? iconTemplate(icon, "lf-margin-kind")
          : html`<span class="lf-margin-kind">${glyph}</span>`
      }<span class="lf-page-map-action-label"
        ><span class="lf-page-map-action-label-word">${visibleLabel}</span>${
          context
            ? html`<span class="lf-page-map-action-context">${context}</span>`
            : nothing
        }</span
      >`;

  function sheetGroups() {
    return entries.map((entry) => {
      const controls = dialogControls(entry);
      const controlOwners = new Set(controls.map(({ record }) => record.owner));
      const items = entry.items.filter(
        (item) => !item.owner || !controlOwners.has(item.owner),
      );
      const actions = [
        ...items.map((item) => {
          const face = faceFor(item);
          const visibleLabel = item.text || entry.title;
          return {
            kind: "item",
            key: dialogItemKey(entry, item),
            entry,
            item,
            icon: face.icon,
            label: `Open ${face.label.toLowerCase()}: ${visibleLabel}`,
            visibleLabel,
            // Map rows stay one line unless their producer explicitly owes a second.
            // Version comparisons do: their pair is provenance rather than part of the
            // account.
            context: item.mapContext,
          };
        }),
        ...controls.map(({ offered, record }) => ({
          kind: "control",
          key: dialogControlKey(entry, offered, record),
          id: dialogControlId(entry, offered, record),
          entry,
          offered,
          record,
          icon: record.icon,
          glyph: record.glyph,
          label: record.accessibleLabel,
          visibleLabel: visibleMarginEntryLabel(record),
          context: record.context,
        })),
      ];
      const passage = blockAt(entry.target);
      const search = [
        entry.title,
        ...actions.flatMap(({ visibleLabel, context }) => [visibleLabel, context]),
        passage ? says(passage) : "",
      ]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase();
      return { key: entry.key, entry, controls, actions, search };
    });
  }

  function activateSheetControl(event, action) {
    const { offered, record } = action;
    if (record.behavior === "status" || record.disabled) return;
    const control = event.currentTarget;
    const relation = record.relation;
    // A disclosure that owns another contributed control unfolds within the map.
    // The first press can then reveal the exact second action without closing the
    // only surface where a spilled contribution is reachable.
    if (relation?.kind === "entries") {
      offered.registration.activate(record.key, {
        origin: control,
        surface: "map",
        input: event.detail === 0 ? "keyboard" : "pointer",
      });
      requestAnimationFrame(() => {
        const revealed = relation.keys
          .map((key) => offered.registration.control(key, "map", true))
          .find((candidate) => candidate?.checkVisibility());
        (revealed ?? control).focus({ preventScroll: true });
      });
      return;
    }
    const returnTo = from;
    closeOwnsFocus = true;
    dialog.close();
    if (returnTo?.isConnected && returnTo.checkVisibility())
      returnTo.focus({ preventScroll: true });
    offered.registration.activate(record.key, {
      origin: control,
      surface: "map",
      input: event.detail === 0 ? "keyboard" : "pointer",
    });
  }

  function presentSheetControl(control, action, actions) {
    if (!control) return;
    const { entry, offered, record } = action;
    presentMarginEntryHost(control, record, {
      accessibleLabel: [record.accessibleLabel, record.context]
        .filter(Boolean)
        .join(", "),
      relatedControlIds: relatedControlIds(action, actions),
    });
    const workflow = entry.workflowCarrier;
    const receipt =
      workflow?.key === record.key && workflow.owner === record.owner
        ? workflow.receipt
        : record.workflowReceipt;
    syncMarginAgentWorkflow(control, receipt);
    trackMarginEntryControl(offered, "map", record.key, control);
  }

  const sheetItemTemplate = (action) => html`
    <button
      type="button"
      class="lf-page-map-action"
      data-lf-map-key=${action.key}
      data-lf-map-item=${action.item.id}
      aria-label=${[action.label, action.context].filter(Boolean).join(", ")}
      .lfMapEntry=${action.entry}
      .lfMapItem=${action.item}
      @click=${() => activateItem(action.item, action.entry)}
    >
      ${sheetFace(action)}
    </button>
  `;

  function relatedControlIds(action, actions) {
    if (action.record.relation?.kind !== "entries") return [];
    const related = new Set(action.record.relation.keys);
    const ids = actions
      .filter(
        (candidate) =>
          candidate.kind === "control" &&
          candidate.offered === action.offered &&
          related.has(candidate.record.key),
      )
      .map(({ id }) => id);
    return ids;
  }

  const sheetControlTemplate = (action) => {
    const body = sheetFace(action);
    if (action.record.behavior === "status")
      return html`<span
        id=${action.id}
        class="lf-page-map-action"
        data-lf-map-key=${action.key}
        data-lf-map-margin-entry=${action.key}
        .lfMapEntry=${action.entry}
        .lfMapOffer=${action.offered}
        .lfMapRecord=${action.record}
        >${body}</span
      >`;
    return html`<button
      id=${action.id}
      type="button"
      class="lf-page-map-action"
      data-lf-map-key=${action.key}
      data-lf-map-margin-entry=${action.key}
      .lfMapEntry=${action.entry}
      .lfMapOffer=${action.offered}
      .lfMapRecord=${action.record}
      @click=${(event) => activateSheetControl(event, action)}
    >
      ${body}
    </button>`;
  };

  const sheetGroupTemplate = (group, query) => html`
    <section
      class="lf-page-map-group"
      data-lf-map-group=${group.key}
      ?hidden=${Boolean(query) && !group.search.includes(query)}
    >
      <h3>${group.entry.title}</h3>
      <div class="lf-page-map-actions">
        ${repeat(
          group.actions,
          ({ key }) => key,
          (action) =>
            action.kind === "item"
              ? sheetItemTemplate(action)
              : sheetControlTemplate(action),
        )}
      </div>
    </section>
  `;

  function renderSheet() {
    const standing = focused();
    const active = dialog.contains(standing) ? standing : null;
    const heldScroll = dialogList.scrollTop;
    const query = dialogSearch.value.trim().toLocaleLowerCase();
    const groups = sheetGroups();
    render(
      html`${repeat(
        groups,
        ({ key }) => key,
        (group) => sheetGroupTemplate(group, query),
      )}`,
      dialogList,
    );
    const liveOffers = new Set(groups.flatMap(({ entry }) => entry.offers));
    for (const offered of trackedOffers)
      if (!liveOffers.has(offered)) clearMarginEntryControls(offered, "map", new Set());
    for (const group of groups) {
      const actions = new Map(group.actions.map((action) => [action.key, action]));
      for (const control of dialogList.querySelectorAll(
        `[data-lf-map-group="${CSS.escape(group.key)}"] .lf-page-map-action`,
      )) {
        const action = actions.get(control.dataset.lfMapKey);
        if (!action) continue;
        if (action.kind === "item")
          syncMarginAgentWorkflow(control, action.item.workflowReceipt);
        else presentSheetControl(control, action, group.actions);
      }
      for (const offered of group.entry.offers)
        clearMarginEntryControls(
          offered,
          "map",
          new Set(
            group.controls
              .filter((candidate) => candidate.offered === offered)
              .map(({ record }) => record.key),
          ),
        );
    }
    trackedOffers = liveOffers;
    const shown = groups.filter(
      (group) => !query || group.search.includes(query),
    ).length;
    dialogEmpty.textContent = query
      ? "No matching actions, statuses, or locations"
      : "No margin controls, status indicators, or locations yet";
    dialogEmpty.hidden = shown !== 0;
    dialogList.scrollTop = heldScroll;
    if (active) {
      if (!active.isConnected || !active.checkVisibility())
        dialogSearch.focus({ preventScroll: true });
      else if (focused() !== active) active.focus({ preventScroll: true });
    }
  }

  function pageMapInvoker() {
    const shelf = mapButton.closest(".lf-banner-menu");
    if (shelf?.lfInvoker?.checkVisibility()) return shelf.lfInvoker;
    return mapButton;
  }

  function renderPageMapDialog(nextEntries) {
    entries = nextEntries;
    const label = `Map (${entries.length})`;
    showBannerControl(mapButton, entries.length > 0);
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
    dialogSearch.addEventListener("input", renderSheet);
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
