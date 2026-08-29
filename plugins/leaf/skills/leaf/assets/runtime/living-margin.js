import {
  registerMarginRow,
  scheduleMarginLayout,
  unregisterMarginRow,
  updateMarginRow,
} from "./margin-layout.js";

const KINDS = {
  change: { label: "Change", symbol: "Δ", priority: 0 },
  comment: { label: "Comment", symbol: "¶", priority: 1 },
  ask: { label: "Ask", symbol: "?", priority: 2 },
  decision: { label: "Decision", symbol: "✓", priority: 3 },
  activity: { label: "Agent activity", symbol: "↻", priority: 4 },
};

const trimmed = (value, limit = 110) => {
  const text = String(value ?? "")
    .replace(/\s+/g, " ")
    .trim();
  return text.length > limit ? text.slice(0, limit - 1) + "…" : text;
};

const humanized = (value) =>
  String(value ?? "")
    .replace(/[-_]+/g, " ")
    .trim();

function targetPath(target) {
  if (target.id) return `id:${target.id}`;
  const steps = [];
  for (let node = target; node?.parentElement; node = node.parentElement) {
    const siblings = [...node.parentElement.children].filter(
      (candidate) =>
        !candidate.classList.contains("lf-ui") &&
        !candidate.hasAttribute("data-lf-gen"),
    );
    steps.push(`${node.localName}:${siblings.indexOf(node)}`);
    if (node.localName === "main") break;
  }
  return `path:${steps.reverse().join("/")}`;
}

function comesBefore(left, right) {
  if (left === right) return 0;
  if (!left) return 1;
  if (!right) return -1;
  return left.compareDocumentPosition(right) & Node.DOCUMENT_POSITION_FOLLOWING
    ? -1
    : 1;
}

export function createLivingMargin(dependencies) {
  const {
    anchorLabel,
    announce,
    approveBtn,
    banner,
    chromeRoot,
    claimState,
    comparisonBase,
    comparisonChanges,
    compact,
    el,
    elementById,
    goToAsk,
    inChrome,
    itemSays,
    itemWord,
    keys,
    offer,
    openAsks,
    pageScroller,
    paintKeys,
    placedAt,
    renderMarginThread,
    scrollBehavior,
    scrollToElement,
    showThread,
    stateProjection,
    threads,
    toggleBtn,
    updateSequence,
    versionBtn,
  } = dependencies;

  const nav = el("nav", "lf-ui lf-living-margin");
  nav.dataset.lfGen = "1";
  nav.setAttribute("aria-label", "Page map");
  const toolbar = el("div", "lf-margin-toolbar");
  toolbar.setAttribute("role", "toolbar");
  toolbar.setAttribute(
    "aria-label",
    "Changes, comments, asks, decisions, and activity",
  );
  nav.append(toolbar);
  chromeRoot.append(nav);

  function placeMargin(
    columnRect = document.querySelector("main")?.getBoundingClientRect(),
  ) {
    const main = document.querySelector("main");
    if (!main || !columnRect) return;
    nav.style.left = `${columnRect.left + pageScroller.scrollLeft}px`;
    nav.style.top = `${columnRect.top + pageScroller.scrollTop}px`;
    nav.style.width = `${columnRect.width}px`;
    nav.style.height = `${main.scrollHeight}px`;
  }

  const mapButton = el("button", "lf-btn lf-page-map-toggle", "Map");
  mapButton.type = "button";
  mapButton.hidden = true;
  mapButton.title = "Open the page map";
  function placeMapButton() {
    if (compact.matches)
      (approveBtn.isConnected ? approveBtn : toggleBtn).after(mapButton);
    else versionBtn.before(mapButton);
  }
  function changePosture() {
    const marginHeld =
      toolbar.contains(document.activeElement) ||
      preview.contains(document.activeElement);
    const sheetHeld = sheet.contains(document.activeElement);
    placeMapButton();
    if (compact.matches && !preview.hidden) closePreview(false);
    if (compact.matches && marginHeld) requestAnimationFrame(() => focusMapControl());
    if (!compact.matches && sheet.open) {
      sheetActivation = true;
      sheet.close();
      if (sheetHeld) requestAnimationFrame(() => focusMapControl());
    }
  }
  placeMapButton();
  compact.addEventListener("change", changePosture);

  const preview = el("aside", "lf-ui lf-margin-preview");
  preview.id = "lf-margin-preview";
  preview.hidden = true;
  const previewHead = el("div", "lf-margin-preview-head");
  const previewTitle = el("strong", "lf-margin-preview-title");
  const previewClose = el("button", "lf-btn lf-margin-preview-close", "×");
  previewClose.type = "button";
  previewClose.setAttribute("aria-label", "Close page-map preview");
  previewHead.append(previewTitle, previewClose);
  const previewKinds = el("div", "lf-margin-preview-kinds");
  const previewList = el("div", "lf-margin-preview-list");
  preview.append(previewHead, previewKinds, previewList);
  chromeRoot.append(preview);

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
  const sheetList = el("div", "lf-page-map-list");
  sheet.append(sheetHead, sheetList);
  chromeRoot.append(sheet);

  const rows = new Map();
  let currentEntries = [];
  let previewEntry = null;
  let previewButton = null;
  let pinnedKey = null;
  let suppressedKey = null;
  let cardHovered = false;
  let highlighted = null;
  let previewFrame = 0;
  let rovingFrame = 0;
  let sheetActivation = false;

  function add(groups, target, item) {
    if (target && (!target.isConnected || inChrome(target))) target = null;
    const key = target ? targetPath(target) : `detached:${item.kind}:${item.id}`;
    let group = groups.get(key);
    if (!group) {
      const word = target ? itemWord(target) : "Detached item";
      const said = target ? itemSays(target) : "No longer placed in this version";
      group = {
        key,
        target,
        title: trimmed([word, said].filter(Boolean).join(" · "), 72),
        items: [],
      };
      groups.set(key, group);
    }
    group.items.push(item);
  }

  function collectEntries() {
    const groups = new Map();
    for (const thread of threads()) {
      if (thread.resolved || !thread.root.anchor) continue;
      const id = thread.root.id;
      add(groups, placedAt(id), {
        kind: "comment",
        id: `comment:${id}`,
        text: trimmed(
          thread.root.text || anchorLabel(thread.root.anchor, thread.root.about),
        ),
        thread,
        activate: () => showThread(id),
      });
    }

    const asks = openAsks();
    for (const ask of asks) {
      const id = ask.id;
      add(groups, ask, {
        kind: "ask",
        id: `ask:${id}`,
        text: trimmed(`${itemWord(ask)} · ${itemSays(ask) || id}`),
        activate: () => {
          const standing = openAsks();
          const next = standing.find((candidate) => candidate.id === id);
          if (next) goToAsk(next, standing);
        },
      });
    }

    const projection = stateProjection();
    for (const [coordinate, entry] of projection.desired) {
      if (entry.e.kind !== "action") continue;
      const target = elementById(entry.unit) ?? elementById(entry.e.widget);
      if (!target) continue;
      const account = [itemWord(target), humanized(entry.e.action), itemSays(target)]
        .filter(Boolean)
        .join(" · ");
      add(groups, target, {
        kind: "decision",
        id: `decision:${coordinate}`,
        text: trimmed(account),
        activate: () => revealTarget(target, `Decision: ${account}`),
      });
    }

    const base = comparisonBase();
    comparisonChanges().forEach((target, index) => {
      const account = `${itemWord(target)} changed${base == null ? "" : ` since v${base}`}`;
      add(groups, target, {
        kind: "change",
        id: `change:${targetPath(target)}:${index}`,
        text: trimmed(`${account} · ${itemSays(target)}`),
        activate: () => revealTarget(target, account),
      });
    });

    if (claimState().claimsHeld)
      for (const update of updateSequence()) {
        if (update.source !== "claim" || update.disposition !== "effective") continue;
        const target =
          update.target.kind === "thread"
            ? placedAt(update.target.id)
            : elementById(update.target.id);
        const account = `${update.agent || "Agent"} · ${update.text || humanized(update.action)}`;
        add(groups, target, {
          kind: "activity",
          id: `activity:${update.id}`,
          text: trimmed(account),
          activate: () => revealTarget(target, account),
        });
      }

    return [...groups.values()]
      .map((group) => ({
        ...group,
        items: group.items.sort(
          (left, right) => KINDS[left.kind].priority - KINDS[right.kind].priority,
        ),
      }))
      .sort((left, right) => comesBefore(left.target, right.target));
  }

  function revealTarget(target, account) {
    if (!target?.isConnected) return;
    scrollToElement(target, scrollBehavior(), "nearest");
    announce(account);
  }

  function markerOptions(row) {
    return {
      anchor: () => row.lfEntry?.target,
      fallback: "hide",
      priority: 10,
      place: (marker, column) => {
        const target = marker.lfEntry?.target;
        if (!target) return;
        placeMargin(column);
        marker.style.top = `${Math.max(0, target.getBoundingClientRect().top - column.top)}px`;
      },
    };
  }

  function kindsIn(entry) {
    const counts = new Map();
    for (const item of entry.items)
      counts.set(item.kind, (counts.get(item.kind) ?? 0) + 1);
    return [...counts].map(([kind, count]) => ({ kind, count, ...KINDS[kind] }));
  }

  function markerName(entry, index, anchored) {
    const kinds = kindsIn(entry)
      .map(({ label, count }) => `${label}${count > 1 ? `s (${count})` : ""}`)
      .join(", ");
    const main = document.querySelector("main");
    const position =
      entry.target && main?.scrollHeight
        ? Math.round(
            ((entry.target.getBoundingClientRect().top -
              main.getBoundingClientRect().top) /
              main.scrollHeight) *
              100,
          )
        : null;
    return `${kinds}, ${index + 1} of ${anchored}, ${entry.title}${position == null ? "" : `, ${Math.max(0, Math.min(100, position))} percent down`}`;
  }

  function availableRows() {
    return [...toolbar.querySelectorAll(".lf-margin-marker:not(.lf-waiting)")].filter(
      (row) => row.checkVisibility(),
    );
  }

  function visibleRows() {
    return availableRows().filter((row) => {
      const box = row.getBoundingClientRect();
      return box.bottom > 0 && box.top < innerHeight;
    });
  }

  function focusMapControl(entry = null) {
    const marker = entry ? rows.get(entry.key) : null;
    if (marker?.isConnected && marker.checkVisibility()) {
      marker.focus({ preventScroll: true });
      return;
    }
    if (mapButton.isConnected && mapButton.checkVisibility()) {
      mapButton.focus({ preventScroll: true });
      return;
    }
    const visible = visibleRows();
    (visible.find((row) => row.tabIndex === 0) ?? visible[0] ?? versionBtn).focus({
      preventScroll: true,
    });
  }

  function syncRoving() {
    const available = availableRows();
    const visible = visibleRows();
    if (!available.length) {
      for (const row of rows.values()) row.tabIndex = -1;
      return;
    }
    const focused = available.find((row) => row === document.activeElement);
    const candidates = visible.length ? visible : available;
    const held = candidates.find(
      (row) => row === document.activeElement || row.tabIndex === 0,
    );
    const next =
      focused ??
      held ??
      candidates.reduce((best, row) => {
        const distance = (candidate) => {
          const box = candidate.getBoundingClientRect();
          if (box.bottom < 0) return -box.bottom;
          if (box.top > innerHeight) return box.top - innerHeight;
          return 0;
        };
        return distance(row) < distance(best) ? row : best;
      });
    for (const row of rows.values()) row.tabIndex = row === next ? 0 : -1;
  }

  function scheduleRoving() {
    cancelAnimationFrame(rovingFrame);
    rovingFrame = requestAnimationFrame(() => {
      rovingFrame = 0;
      syncRoving();
    });
  }

  function walkMarkers(direction, edge = null) {
    const visible = visibleRows();
    if (!visible.length) return;
    const current = visible.indexOf(document.activeElement);
    const index =
      edge === "first"
        ? 0
        : edge === "last"
          ? visible.length - 1
          : current < 0
            ? direction > 0
              ? 0
              : visible.length - 1
            : (current + direction + visible.length) % visible.length;
    const next = visible[index];
    for (const row of rows.values()) row.tabIndex = row === next ? 0 : -1;
    next.focus({ preventScroll: true });
  }

  keys(
    toolbar,
    "In the page map",
    [
      {
        id: "margin.walk",
        keys: ["ArrowUp", "ArrowDown"],
        does: "Walk the visible page-map markers",
        line: "walk the page map",
        repeat: true,
        run: (binding) => walkMarkers(binding === "ArrowDown" ? 1 : -1),
      },
      {
        id: "margin.first",
        keys: ["Home"],
        does: "First visible page-map marker",
        line: "first marker",
        run: () => walkMarkers(0, "first"),
      },
      {
        id: "margin.last",
        keys: ["End"],
        does: "Last visible page-map marker",
        line: "last marker",
        run: () => walkMarkers(0, "last"),
      },
      {
        id: "margin.preview-close",
        keys: ["Escape"],
        does: "Close the page-map preview",
        line: "close preview",
        when: () => !preview.hidden,
        run: () => closePreview(true),
      },
    ],
    () => visibleRows().length > 0,
  );
  keys(
    preview,
    "In a page-map preview",
    [
      {
        id: "margin.card-close",
        keys: ["Escape"],
        does: "Close the page-map preview",
        line: "close preview",
        run: () => closePreview(true),
      },
    ],
    () => !preview.hidden,
  );
  keys(
    sheet,
    "In the page map",
    [
      {
        id: "margin.sheet-close",
        keys: ["Escape"],
        does: "Close the page map",
        line: "close page map",
        run: () => sheet.close(),
      },
    ],
    () => sheet.open,
  );

  function paintMarker(row, entry, index, anchored) {
    row.lfEntry = entry;
    row.dataset.lfKinds = kindsIn(entry)
      .map(({ kind }) => kind)
      .join(" ");
    row.setAttribute("aria-label", markerName(entry, index, anchored));
    row.title = kindsIn(entry)
      .map(({ label, count }) => `${label}${count > 1 ? `s (${count})` : ""}`)
      .join(" · ");
    row.setAttribute("aria-controls", preview.id);
    row.setAttribute("aria-expanded", String(previewEntry?.key === entry.key));
    row.setAttribute("aria-pressed", String(pinnedKey === entry.key));
    const wanted = kindsIn(entry).map(({ kind, symbol, label, count }) => {
      let facet = row.querySelector(`:scope > [data-lf-kind="${kind}"]`);
      if (!facet) {
        facet = el("span", `lf-margin-facet lf-margin-${kind}`);
        facet.dataset.lfKind = kind;
        facet.setAttribute("aria-hidden", "true");
      }
      facet.textContent = symbol;
      facet.title = count > 1 ? `${count} ${label.toLowerCase()}s` : label;
      return facet;
    });
    if (entry.items.length > 1) {
      let count = row.querySelector(":scope > .lf-margin-count");
      if (!count) {
        count = el("span", "lf-margin-count");
        count.setAttribute("aria-hidden", "true");
      }
      count.textContent = entry.items.length;
      wanted.push(count);
    }
    for (const child of [...row.children]) if (!wanted.includes(child)) child.remove();
    wanted.forEach((child, position) => {
      if (row.children[position] !== child)
        row.insertBefore(child, row.children[position] ?? null);
    });
  }

  function render() {
    const main = document.querySelector("main");
    if (!nav.isConnected) chromeRoot.append(nav);
    placeMargin(main?.getBoundingClientRect());
    currentEntries = collectEntries();
    const anchoredEntries = currentEntries.filter((entry) => entry.target);
    const live = new Set(anchoredEntries.map((entry) => entry.key));
    for (const [key, row] of rows)
      if (!live.has(key)) {
        unregisterMarginRow(row);
        row.remove();
        rows.delete(key);
      }
    anchoredEntries.forEach((entry, index) => {
      let row = rows.get(entry.key);
      if (!row) {
        row = offer("button", "lf-margin-marker");
        row.onclick = (event) => {
          togglePinned(row.lfEntry, row);
          if (event.detail === 0 && pinnedKey === row.lfEntry.key)
            previewList
              .querySelector("textarea, button")
              ?.focus({ preventScroll: true });
        };
        row.addEventListener("pointerenter", () => {
          suppressedKey = null;
          showPreview(row.lfEntry, row);
        });
        row.addEventListener("pointerleave", deferPreviewClose);
        row.addEventListener("focus", () => {
          if (suppressedKey !== row.lfEntry.key) showPreview(row.lfEntry, row);
        });
        row.addEventListener("blur", deferPreviewClose);
        toolbar.append(row);
        rows.set(entry.key, row);
        registerMarginRow(row, markerOptions(row));
      } else updateMarginRow(row, markerOptions(row));
      paintMarker(row, entry, index, anchoredEntries.length);
    });
    anchoredEntries.forEach((entry, index) => {
      const row = rows.get(entry.key);
      if (toolbar.children[index] !== row)
        toolbar.insertBefore(row, toolbar.children[index] ?? null);
    });
    mapButton.hidden = currentEntries.length === 0;
    mapButton.textContent = `Map (${currentEntries.length})`;
    nav.hidden = anchoredEntries.length === 0;
    nav.setAttribute("aria-label", `Page map, ${anchoredEntries.length} locations`);
    if (sheet.open) renderSheet();
    if (previewEntry) {
      const fresh = currentEntries.find((entry) => entry.key === previewEntry.key);
      if (!fresh) closePreview(false);
      else {
        previewEntry = fresh;
        previewButton = rows.get(fresh.key) ?? previewButton;
        buildPreview(fresh);
        highlight(fresh.target);
        placePreview();
      }
    }
    scheduleMarginLayout();
    scheduleRoving();
    paintKeys();
  }

  function buildPreview(entry) {
    const focusedItem = preview.contains(document.activeElement)
      ? document.activeElement.closest?.("[data-lf-margin-item]")?.dataset.lfMarginItem
      : null;
    previewTitle.textContent = entry.title;
    previewKinds.replaceChildren(
      ...kindsIn(entry).map(({ kind, label, symbol, count }) => {
        const chip = el("span", `lf-margin-kind lf-margin-${kind}`);
        chip.append(
          el("span", "lf-margin-kind-symbol", symbol),
          document.createTextNode(`${label}${count > 1 ? ` ${count}` : ""}`),
        );
        return chip;
      }),
    );
    const nodes = entry.items.map((item) => previewItemNode(entry, item));
    const keep = new Set(nodes);
    for (const child of [...previewList.children]) if (!keep.has(child)) child.remove();
    let cursor = previewList.firstChild;
    for (const node of nodes) {
      if (node === cursor) cursor = cursor.nextSibling;
      else previewList.insertBefore(node, cursor);
    }
    if (focusedItem) {
      const replacement = [
        ...previewList.querySelectorAll("[data-lf-margin-item]"),
      ].find((candidate) => candidate.dataset.lfMarginItem === focusedItem);
      (replacement ?? previewClose).focus({ preventScroll: true });
    }
  }

  function previewItemNode(entry, item) {
    let node = [...previewList.children].find(
      (candidate) => candidate.dataset.lfMarginItem === item.id,
    );
    if (item.kind === "comment") {
      if (!node?.classList.contains("lf-margin-thread")) {
        node?.remove();
        node = el("section", "lf-margin-thread");
        const body = el("div", "lf-margin-thread-body");
        const open = el("button", "lf-btn lf-margin-thread-open", "Open in Comments");
        open.type = "button";
        node.append(body, open);
      }
      renderMarginThread(
        node.querySelector(":scope > .lf-margin-thread-body"),
        item.thread,
      );
      node.querySelector(":scope > .lf-margin-thread-open").onclick = () =>
        activate(item, entry);
    } else {
      if (!node?.classList.contains("lf-margin-preview-action")) {
        node?.remove();
        node = el("button", "lf-margin-preview-action");
        node.type = "button";
        node.append(el("span"), el("span", "lf-margin-action-text"));
      }
      const kind = node.firstElementChild;
      kind.className = `lf-margin-action-kind lf-margin-${item.kind}`;
      kind.textContent = KINDS[item.kind].label;
      node.lastElementChild.textContent = item.text || entry.title;
      node.setAttribute(
        "aria-label",
        `Open ${KINDS[item.kind].label.toLowerCase()}: ${item.text || entry.title}`,
      );
      node.onclick = () => activate(item, entry);
    }
    node.dataset.lfMarginItem = item.id;
    return node;
  }

  function highlight(target) {
    if (highlighted === target) return;
    highlighted?.classList.remove("lf-margin-target");
    highlighted = target;
    highlighted?.classList.add("lf-margin-target");
  }

  function showPreview(entry, button) {
    if (!entry || suppressedKey === entry.key) return;
    if (previewEntry?.key !== entry.key) buildPreview(entry);
    previewEntry = entry;
    previewButton = button;
    preview.hidden = false;
    highlight(entry.target);
    for (const [key, row] of rows) {
      row.setAttribute("aria-expanded", String(key === entry.key));
      row.setAttribute("aria-pressed", String(key === pinnedKey));
    }
    placePreview();
    paintKeys();
  }

  function togglePinned(entry, button) {
    if (pinnedKey === entry.key) {
      pinnedKey = null;
      suppressedKey = entry.key;
      closePreview(false);
      return;
    }
    pinnedKey = entry.key;
    suppressedKey = null;
    showPreview(entry, button);
  }

  function closePreview(returnFocus) {
    const button = previewButton;
    if (returnFocus && button?.lfEntry) suppressedKey = button.lfEntry.key;
    pinnedKey = null;
    previewEntry = null;
    previewButton = null;
    preview.hidden = true;
    highlight(null);
    for (const row of rows.values()) {
      row.setAttribute("aria-expanded", "false");
      row.setAttribute("aria-pressed", "false");
    }
    if (returnFocus && button?.isConnected) button.focus({ preventScroll: true });
    paintKeys();
  }

  function deferPreviewClose() {
    setTimeout(() => {
      const focusHeld =
        previewButton === document.activeElement ||
        preview.contains(document.activeElement);
      const pointerHeld = previewButton?.matches(":hover") || cardHovered;
      if (!focusHeld && !pointerHeld && pinnedKey !== previewEntry?.key)
        closePreview(false);
      if (!focusHeld && !pointerHeld) suppressedKey = null;
    }, 70);
  }

  function placePreview() {
    cancelAnimationFrame(previewFrame);
    previewFrame = requestAnimationFrame(() => {
      previewFrame = 0;
      if (preview.hidden || !previewButton?.isConnected) return;
      const marker = previewButton.getBoundingClientRect();
      const card = preview.getBoundingClientRect();
      const bannerBottom = banner.getBoundingClientRect().bottom;
      const minTop = Math.max(12, bannerBottom + 8);
      const maxTop = Math.max(minTop, innerHeight - card.height - 12);
      const top = Math.max(minTop, Math.min(maxTop, marker.top));
      const rightRoom = innerWidth - marker.right - 12;
      const left =
        rightRoom >= card.width + 8
          ? marker.right + 8
          : Math.max(12, marker.left - card.width - 8);
      preview.style.left = `${Math.min(left, innerWidth - card.width - 12)}px`;
      preview.style.top = `${top}px`;
    });
  }

  function activate(item, entry) {
    suppressedKey = entry.key;
    closePreview(false);
    if (sheet.open) {
      sheetActivation = true;
      sheet.close();
    }
    focusMapControl(entry);
    item.activate();
  }

  function renderSheet() {
    const focusedItem = sheet.contains(document.activeElement)
      ? document.activeElement.dataset.lfMapItem
      : null;
    const heldScroll = sheetList.scrollTop;
    sheetList.replaceChildren(
      ...currentEntries.map((entry) => {
        const group = el("section", "lf-page-map-group");
        group.append(el("h3", "", entry.title));
        const actions = el("div", "lf-page-map-actions");
        for (const item of entry.items) {
          const button = el("button", "lf-page-map-action");
          button.type = "button";
          button.append(
            el(
              "span",
              `lf-margin-kind lf-margin-${item.kind}`,
              KINDS[item.kind].symbol,
            ),
            el("span", "", item.text || entry.title),
          );
          button.setAttribute(
            "aria-label",
            `Open ${KINDS[item.kind].label.toLowerCase()}: ${item.text || entry.title}`,
          );
          button.dataset.lfMapItem = item.id;
          button.onclick = () => activate(item, entry);
          actions.append(button);
        }
        group.append(actions);
        return group;
      }),
    );
    sheetList.scrollTop = heldScroll;
    if (focusedItem) {
      const replacement = [...sheetList.querySelectorAll("[data-lf-map-item]")].find(
        (candidate) => candidate.dataset.lfMapItem === focusedItem,
      );
      (replacement ?? sheetClose).focus({ preventScroll: true });
    }
  }

  mapButton.onclick = () => {
    renderSheet();
    sheet.showModal();
    sheetClose.focus({ preventScroll: true });
    paintKeys();
  };
  sheet.addEventListener("close", () => {
    paintKeys();
    if (sheetActivation) {
      sheetActivation = false;
      return;
    }
    focusMapControl();
  });
  previewClose.onclick = () => closePreview(true);
  preview.addEventListener("pointerenter", () => (cardHovered = true));
  preview.addEventListener("pointerleave", () => {
    cardHovered = false;
    deferPreviewClose();
  });
  document.addEventListener("click", (event) => {
    if (
      pinnedKey &&
      !preview.contains(event.target) &&
      !event.target.closest?.(".lf-margin-marker")
    )
      closePreview(false);
  });
  document.addEventListener("lf-actions", render);
  document.addEventListener("lf-answered", render);
  document.addEventListener("lf-comparison", render);
  document.addEventListener("lf-margin-layout", placePreview);
  document.addEventListener(
    "scroll",
    () => {
      placePreview();
      scheduleRoving();
    },
    { capture: true, passive: true },
  );
  window.addEventListener("resize", () => {
    scheduleMarginLayout();
    placePreview();
    scheduleRoving();
  });
  render();

  return { render };
}
