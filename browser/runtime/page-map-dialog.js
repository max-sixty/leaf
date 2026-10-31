/* The complete searchable Page Map dialog.

   The neutral annotation inventory supplies current target entries and live activation.
   One keyed Lit projection renders its groups and contributed records, filters
   them, and returns focus through the route that opened it. Retained nodes keep a state
   refresh from cancelling a held pointer or moving focus.
   Compact clusters use this same complete dialog for overflow.

   A native dialog delivers `close` after it has hidden the dialog, a task later. A close
   overtaken by a reopen therefore leaves the new opening's target and focus route intact.
   Every way out declares its landing as it closes the dialog:
   cancellation by Escape or Close hands the user back to the opening focus, or
   their reading position when there was none. Record actions navigate separately.
   The `close` event places nothing.

   The dialog is a list with a search above it. Up and Down walk its rows, Down or Enter
   in the search enters the list at the first match, and a row's Enter is its own press.
   A finger opens the map on its first row rather than in the search, since focusing the
   search raises a soft keyboard over the list the finger came to tap.
   A disclosure's deferred child arrival yields to newer input while its revealed
   choices stay available.

   Boot supplies the inventory and current annotation focus capabilities. Its
   mount attaches the dialog and binds controls; importing the module does not
   install application callbacks or activate the map. */

import { showNativeLayer, closeNativeLayer } from "./keyboard/layer-stack.js";
import { scrollIntoView } from "./landing-scroll.js";
import { nextRender } from "./rendering.js";
import { blockAt, says } from "./passages.js";
import {
  closeLayer,
  focusDestination,
  focused,
  handBack,
  holdFocus,
  openLayer,
  openerOf,
} from "./focus.js";
import { html, nothing, render, repeat } from "/runtime/framework.js";
import { iconTemplate } from "./icons.js";
import { keys, paintKeys, paintKeysWithin } from "./keyboard/scopes.js";
import { coarsePointer, pressIsKeyboardActivation } from "./pointer.js";
import { rowWalk } from "./walk-position.js";
import { closeControl, el, offeredAction, searchField } from "./widget-elements.js";
import { keepsHidden, keepsText } from "./keeps.js";
import { placeKeeper } from "./user-place.js";
import { retainUserIntent } from "./user-intent.js";
import {
  PAGE_CONTROL_RANK,
  pageControlsChanged,
  registerPageControl,
} from "./page-controls.js";
import {
  clearContributionControls,
  contributionHost,
  contributionReceipts,
} from "./contribution-controls.js";
import { contributionSource } from "./contributions.js";
import { railStands } from "./content-layout.js";
import { commandSteps } from "./keyboard/control-keys.js";

import { contributionItemKey, KINDS } from "./contribution-model.js";
import { marginMapGroups } from "./margin-map-model.js";
import { threadHeading } from "./thread/messages.js";
import { voiced, wordsText } from "./voice.js";

const dialog = document.createElement("dialog");
dialog.className = "lf-ui lf-page-map-dialog";
dialog.setAttribute("aria-label", "Page Map");
dialog.setAttribute("aria-modal", "true");
const dialogHead = el("div", "lf-dialog-head");
dialogHead.append(el("strong", "lf-dialog-title", "Page Map"));
const dialogClose = closeControl({
  name: "Close Page Map",
  title: "Close Page Map (Esc)",
});
dialogHead.append(dialogClose);
const dialogSearch = searchField("lf-page-map-search", {
  name: "page-map-search",
  label: "Find an action, status, or location in Page Map",
  placeholder: "Find an action, status, or location",
});
const dialogList = el("div", "lf-page-map-list scroll");
// A state update or a search re-renders the open sheet; the row the user was on holds
// their place in it (user-place.js), under the map key each row is rendered with.
const place = placeKeeper(dialogList, {
  items: ".lf-page-map-action",
  identity: (row) => row.dataset.lfMapKey,
  active: () => dialog.open,
});
const dialogEmpty = el(
  "p",
  "lf-rows-empty",
  "No matching actions, statuses, or locations.",
);
dialogEmpty.hidden = true;
dialogEmpty.setAttribute("role", "status");
dialog.append(dialogHead, dialogSearch, dialogList, dialogEmpty);

// The rows a walk or the search's Enter can land on: every pressable entry the search
// has not hidden. A status is words beside the rows, not a stop among them.
const mapRows = () =>
  [...dialogList.querySelectorAll("button.lf-page-map-action")].filter((row) =>
    row.checkVisibility(),
  );

export function createPageMapDialog({
  inventory,
  activeInAnnotations,
  releaseAnnotations,
  annotationFocus,
}) {
  const { targetFor } = inventory;
  let entries = [];
  let groups = [];
  let target = null;
  let trackedOffers = new Set();
  // The Map is a row of the page's controls while it has entries, which a keyboard
  // reaches by `g P` (keyboard/go-to-sequence.js). Beside the rail, whose markers show
  // the page's annotations where they stand, it is a keyboard's convenience; where the
  // window has no room for the rail, the markers are pins over the content, and the
  // map is where a reader surveys them, so Navigate offers it to a mouse too.
  registerPageControl({
    key: "map",
    rank: PAGE_CONTROL_RANK.map,
    label: "Page Map",
    value: () => String(entries.length),
    shortcut: () => commandSteps("navigation.page-map"),
    offered: () => entries.length > 0,
    group: () => (railStands() ? "keys" : "navigate"),
    press: () => openPageMap(),
  });

  const pageMapIsActive = () => dialog.open || Boolean(activeInAnnotations?.());

  function activateItem(item, entry) {
    releaseAnnotations?.(entry);
    const destination = annotationFocus?.(entry);
    // A location without a presented annotation lands on its exact authored target.
    // Commands that open a Thread or obligation retain their own navigation capability.
    closeLayer(leavePageMap, () =>
      !destination && targetFor(entry)?.isConnected
        ? focusDestination(targetFor(entry), "move")
        : handBack(destination, openerOf(dialog)),
    );
    inventory.activate(item);
  }

  function pageMapDialogContains(candidate, node) {
    return dialog.open && target === candidate && dialog.contains(node);
  }

  // A thread's row names it as Threads does (`threadHeading`).
  const sheetName = (item, visibleWords) => {
    const thread = item && inventory.sourceItem(item)?.thread;
    return thread ? threadHeading(thread) : visibleWords;
  };
  // A row's kind leads it, its name follows, and what it says of its state, such as
  // whose turn a thread is, ends it, where Threads says the same.
  const sheetFace = ({ icon, glyph, item, visibleLabel, visibleWords, context }) =>
    html`<span class="lf-row-lead"
        >${
          icon
            ? iconTemplate(icon, "lf-margin-kind")
            : html`<span class="lf-margin-kind">${glyph}</span>`
        }</span
      ><span class="lf-page-map-action-label-word lf-row-main"
        >${voiced(sheetName(item, visibleWords ?? visibleLabel))}</span
      >${
        context
          ? html`<span class="lf-page-map-action-context lf-row-end"
              >${voiced(context)}</span
            >`
          : nothing
      }`;

  function activateSheetControl(event, action) {
    const { offered, record } = action;
    if (record.behavior === "status" || record.disabled) return;
    const control = event.currentTarget;
    const relation = record.relation;
    // A disclosure that owns another contributed control unfolds within the map.
    // The first press can then reveal the exact second action without closing the
    // only surface where a spilled contribution is reachable.
    if (relation?.kind === "entries") {
      const currentIntent = retainUserIntent({ available: () => dialog.open });
      contributionSource(offered).registration.activate(record.key, {
        origin: control,
        surface: "map",
        input: pressIsKeyboardActivation(event) ? "keyboard" : "pointer",
      });
      nextRender(() => {
        if (!currentIntent()) return;
        const revealed = relation.keys
          .map((key) =>
            contributionSource(offered).registration.control(key, "map", true),
          )
          .find((candidate) => candidate?.checkVisibility());
        focusDestination(revealed ?? control, "move");
      });
      return;
    }
    const returnTo = openerOf(dialog);
    closeLayer(
      () => closeNativeLayer(dialog),
      () => handBack(returnTo),
    );
    contributionSource(offered).registration.activate(record.key, {
      origin: control,
      surface: "map",
      input: pressIsKeyboardActivation(event) ? "keyboard" : "pointer",
    });
  }

  const sheetHost = (action, actions) =>
    contributionHost(contributionSource(action.offered), "map", action.record, {
      accessibleLabel: [
        action.record.accessibleLabel,
        wordsText(action.record.context ?? ""),
      ]
        .filter(Boolean)
        .join(", "),
      relatedControlIds: relatedControlIds(action, actions),
    });

  const sheetItemTemplate = (action) => html`
    <button
      type="button"
      ${offeredAction("row", "lf-page-map-action")}
      data-lf-map-key=${action.key}
      data-lf-map-item=${action.item.id}
      aria-label=${[action.label, wordsText(action.context ?? "")].filter(Boolean).join(", ")}
      ${contributionReceipts(action.receipt, action.awaitsUser)}
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

  const sheetControlTemplate = (action, actions) => {
    const body = sheetFace(action);
    if (action.record.behavior === "status")
      return html`<span
        id=${action.id}
        class="lf-page-map-action lf-row-plain"
        data-lf-map-key=${action.key}
        data-lf-map-margin-entry=${action.key}
        ${sheetHost(action, actions)}
        ${contributionReceipts(action.receipt, action.awaitsUser)}
        >${body}</span
      >`;
    return html`<button
      id=${action.id}
      type="button"
      ${offeredAction("row", "lf-page-map-action")}
      data-lf-map-key=${action.key}
      data-lf-map-margin-entry=${action.key}
      ${sheetHost(action, actions)}
      ${contributionReceipts(action.receipt, action.awaitsUser)}
      @click=${(event) => activateSheetControl(event, action)}
    >
      ${body}
    </button>`;
  };

  const sheetGroupTemplate = (group, query) => html`
    <section
      class="lf-page-map-group lf-rows-group"
      data-lf-map-group=${group.key}
      ?hidden=${Boolean(query) && !group.search.includes(query)}
    >
      <h3 class="lf-rows-head">${group.entry.title}</h3>
      <div class="lf-page-map-actions lf-rows">
        ${repeat(
          group.actions,
          ({ key }) => key,
          (action) =>
            action.kind === "item"
              ? sheetItemTemplate(action)
              : sheetControlTemplate(action, group.actions),
        )}
      </div>
    </section>
  `;

  function renderSheet() {
    const restoreFocus = holdFocus(dialog);
    place.around(() => presentSheet());
    // A control the filter hid or the render removed hands the user to the search.
    restoreFocus?.(dialogSearch);
    // Search bindings read the rendered rows, including those the query hid.
    paintKeysWithin(dialog);
  }

  function presentSheet() {
    const query = dialogSearch.value.trim().toLocaleLowerCase();
    const searchTextByKey = new Map(
      entries.map((entry) => {
        const passage = blockAt(targetFor(entry));
        return [entry.key, passage ? says(passage) : ""];
      }),
    );
    groups = marginMapGroups(entries, (item) => KINDS[item.kind], searchTextByKey);
    render(
      html`${repeat(
        groups,
        ({ key }) => key,
        (group) => sheetGroupTemplate(group, query),
      )}`,
      dialogList,
    );
    const liveOffers = new Set(
      groups.flatMap(({ entry }) => entry.offers.map(contributionSource)),
    );
    for (const offered of trackedOffers)
      if (!liveOffers.has(offered))
        clearContributionControls(offered, "map", new Set());
    for (const group of groups) {
      for (const offered of group.entry.offers)
        clearContributionControls(
          contributionSource(offered),
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
    keepsText(
      dialogEmpty,
      query
        ? "No matching actions, statuses, or locations."
        : "No margin controls, status indicators, or locations yet.",
    );
    keepsHidden(dialogEmpty, shown !== 0);
  }

  function renderPageMapDialog(nextEntries) {
    if (nextEntries.length !== entries.length) pageControlsChanged();
    entries = nextEntries;
    if (dialog.open) renderSheet();
  }

  function openPageMap(entry = null, { invoker = null, focusSpill = false } = {}) {
    const openedFrom = invoker ?? focused();
    target = entry ? targetFor(entry) : null;
    if (!dialog.open) {
      openLayer(dialog, openedFrom);
      dialogSearch.value = "";
    }
    renderSheet();
    if (!dialog.open) showNativeLayer(dialog);
    const index = entry
      ? entries.findIndex((candidate) => candidate.key === entry.key)
      : -1;
    const group = index < 0 ? null : dialogList.children[index];
    if (group) scrollIntoView(group, { block: "nearest", within: dialogList });
    const spilled = focusSpill ? openedFrom?.lfFirstSpilledOption : null;
    const spilledAction = focusSpill
      ? groups[index]?.actions.find(
          (action) =>
            (action.kind === "control" &&
              action.record.key === spilled?.record?.key &&
              action.record.owner === spilled?.record?.owner) ||
            (action.kind === "item" &&
              spilled?.choice?.items.some(
                (item) =>
                  contributionItemKey(action.item) === contributionItemKey(item),
              )),
        )
      : null;
    const destination = focusSpill
      ? spilledAction &&
        group?.querySelector(`[data-lf-map-key="${CSS.escape(spilledAction.key)}"]`)
      : group?.querySelector(".lf-page-map-action");
    focusDestination(
      destination ??
        (coarsePointer.matches ? (mapRows()[0] ?? dialogClose) : dialogSearch),
      "move",
    );
    paintKeys();
  }

  // Focus belongs to the visible control in this native layer. A contributor closing
  // its disclosure can use the registration's surface reading to return here.
  function leavePageMap() {
    if (!dialog.open) return;
    closeLayer(() => closeNativeLayer(dialog));
  }

  function cancelPageMap() {
    const returnTo = openerOf(dialog);
    closeLayer(leavePageMap, () => handBack(returnTo));
  }

  // The page has the map's keys while the map has entries, open or not, so the command
  // reference can say what the dialog's keys do before the user opens it; they answer
  // only from inside it, where focus puts the user.
  const mapHasEntries = () => entries.length > 0;

  function mount(root) {
    dialogSearch.addEventListener("input", renderSheet);
    keys(
      dialog,
      "In the Page Map",
      rowWalk({ id: "map", noun: "Entry", plural: "entries", rows: mapRows }),
      mapHasEntries,
    );
    // Escape and Close return to the opening focus or the prior reading position.
    // Leaf performs the whole step instead of landing the user from the `close` event:
    // that event arrives a task later, and a user whose next
    // press is `g` would arm the sequence before the focus moved and disarm it on
    // arrival.
    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      cancelPageMap();
    });
    dialog.addEventListener("close", () => {
      if (dialog.open) return;
      target = null;
      paintKeys();
    });
    dialogClose.onclick = cancelPageMap;
    root.append(dialog);
    dialogSearch.updateComplete.then(declareSearchKeys);
  }

  // The search box's own keys, declared on the exact input so they stand before its
  // typing, which keeps Down and Enter as caret and form keys that do nothing in a
  // one-line box. Escape stays the dialog's.
  function declareSearchKeys() {
    const hasRows = () => mapRows().length > 0;
    keys(
      dialogSearch.input,
      "In the Page Map's search",
      [
        {
          id: "map.search.enter",
          keys: ["ArrowDown"],
          title: "to the entries",
          when: hasRows,
          run: () => {
            const row = mapRows()[0];
            focusDestination(row, "move");
            scrollIntoView(row, { block: "nearest" });
          },
        },
        {
          id: "map.search.open",
          keys: ["Enter"],
          title: "open first",
          when: hasRows,
          run: () => mapRows()[0].click(),
        },
      ],
      mapHasEntries,
    );
  }
  return {
    pageMapIsActive,
    pageMapDialogContains,
    renderPageMapDialog,
    openPageMap,
    leavePageMap,
    mount,
  };
}
