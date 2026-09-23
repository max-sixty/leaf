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
import { letGo } from "./focus.js";
import { html, nothing, render, repeat } from "../vendor/browser-runtime.js";
import { iconTemplate } from "./icons.js";
import { focused, paintKeys } from "./keyboard/scopes.js";
import { el, offer } from "./widget-elements.js";
import { placeKeeper } from "./reader-place.js";
import {
  BANNER_CONTROL_RANK,
  bannerControlDoor,
  registerBannerControl,
  showBannerControl,
} from "./banner-shelf.js";
import {
  clearMarginEntryControls,
  marginContributionSource,
  presentMarginEntryHost,
  syncMarginAgentWorkflow,
  syncMarginTurn,
  trackMarginEntryControl,
} from "./margin-entries.js";

import { marginItemKey } from "./margin-entry-model.js";
import { marginMapGroups } from "./margin-map-model.js";

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
const dialogSearch = offer("wa-input", "lf-page-map-search lf-label-hidden");
dialogSearch.type = "search";
dialogSearch.name = "page-map-search";
dialogSearch.placeholder = "Find an action, status, or location";
dialogSearch.label = "Find an action, status, or location in Page Map";
dialogSearch.size = "s";
const dialogList = el("div", "lf-page-map-list");
// A state update or a search re-renders the open sheet; the row the reader was on holds
// their place in it (reader-place.js), under the id each row is rendered with.
const place = placeKeeper(dialogList, {
  items: ".lf-page-map-action",
  identity: (row) => row.id,
  active: () => dialog.open,
});
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
  targetFor,
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

  function activateSheetControl(event, action) {
    const { offered, record } = action;
    if (record.behavior === "status" || record.disabled) return;
    const control = event.currentTarget;
    const relation = record.relation;
    // A disclosure that owns another contributed control unfolds within the map.
    // The first press can then reveal the exact second action without closing the
    // only surface where a spilled contribution is reachable.
    if (relation?.kind === "entries") {
      marginContributionSource(offered).registration.activate(record.key, {
        origin: control,
        surface: "map",
        input: event.detail === 0 ? "keyboard" : "pointer",
      });
      requestAnimationFrame(() => {
        const revealed = relation.keys
          .map((key) =>
            marginContributionSource(offered).registration.control(key, "map", true),
          )
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
    marginContributionSource(offered).registration.activate(record.key, {
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
    trackMarginEntryControl(
      marginContributionSource(offered),
      "map",
      record.key,
      control,
    );
  }

  const sheetItemTemplate = (action) => html`
    <button
      type="button"
      class="lf-page-map-action"
      data-lf-map-key=${action.key}
      data-lf-map-item=${action.item.id}
      aria-label=${[action.label, action.context].filter(Boolean).join(", ")}
      .lfMapAction=${action}
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
        .lfMapAction=${action}
        >${body}</span
      >`;
    return html`<button
      id=${action.id}
      type="button"
      class="lf-page-map-action"
      data-lf-map-key=${action.key}
      data-lf-map-margin-entry=${action.key}
      .lfMapAction=${action}
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
    const hold = place.take();
    const query = dialogSearch.value.trim().toLocaleLowerCase();
    const searchTextByKey = new Map(
      entries.map((entry) => {
        const passage = blockAt(targetFor(entry));
        return [entry.key, passage ? says(passage) : ""];
      }),
    );
    const groups = marginMapGroups(entries, faceFor, searchTextByKey);
    render(
      html`${repeat(
        groups,
        ({ key }) => key,
        (group) => sheetGroupTemplate(group, query),
      )}`,
      dialogList,
    );
    const liveOffers = new Set(
      groups.flatMap(({ entry }) => entry.offers.map(marginContributionSource)),
    );
    for (const offered of trackedOffers)
      if (!liveOffers.has(offered)) clearMarginEntryControls(offered, "map", new Set());
    const groupsByKey = new Map(groups.map((group) => [group.key, group]));
    for (const control of dialogList.querySelectorAll(".lf-page-map-action")) {
      const action = control.lfMapAction;
      if (action.kind === "item") {
        syncMarginAgentWorkflow(control, action.item.workflowReceipt);
        syncMarginTurn(control, Boolean(action.item.readerAttention));
      } else
        presentSheetControl(control, action, groupsByKey.get(action.entry.key).actions);
    }
    for (const group of groups) {
      for (const offered of group.entry.offers)
        clearMarginEntryControls(
          marginContributionSource(offered),
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
    place.finish(hold);
    if (active) {
      if (!active.isConnected || !active.checkVisibility())
        dialogSearch.focus({ preventScroll: true });
      else if (focused() !== active) active.focus({ preventScroll: true });
    }
  }

  function pageMapInvoker() {
    return bannerControlDoor(mapButton) ?? mapButton;
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
    target = entry ? targetFor(entry) : null;
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
            (button.lfMapAction?.record &&
              button.lfMapAction.record.key === spilled?.record?.key &&
              button.lfMapAction.record.owner === spilled?.record?.owner) ||
            spilled?.choice?.items.some(
              (item) =>
                button.lfMapAction?.item &&
                marginItemKey(button.lfMapAction.item) === marginItemKey(item),
            ),
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
    // Escape is one step of the page's unwind, and a modal's parent is the page it
    // stands over, so this press lands the reader there. Leaf performs the whole step
    // rather than letting the platform close the dialog and this owner land the reader
    // from the `close` event: that event arrives a task later, and a reader whose next
    // press is `g` would arm the sequence before the focus moved and disarm it on
    // arrival. The Close button is the other way out and keeps the invoker, the pointer
    // being already on the control that reopens the dialog.
    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      leavePageMap();
      letGo();
    });
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
