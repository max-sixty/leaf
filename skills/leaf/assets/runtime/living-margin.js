import {
  layoutMarginRows,
  registerMarginRow,
  scheduleMarginLayout,
  unregisterMarginRow,
  updateMarginRow,
} from "./margin-layout.js";
import { shownBox, shownParts } from "./geometry.js";

const KINDS = {
  action: { label: "Action", symbol: "·", priority: -1 },
  change: { label: "Change", symbol: "Δ", priority: 0 },
  comment: { label: "Comment", symbol: "¶", priority: 1 },
  decision: { label: "Decision", symbol: "?", priority: 2 },
  outcome: { label: "Outcome", symbol: "✓", priority: 3 },
  activity: { label: "Agent activity", symbol: "↻", priority: 4 },
};

// Content modules contribute what their target offers; this projection decides where
// those controls stand and joins them to every other reading of the same target. The
// store is module-level because widgets upgrade after the margin is composed and may
// reconnect while a live version replaces the authored document.
const offeredItems = new Set();
const offerListeners = new Set();
const ACTION_COLLAPSE = new Set(["auto", "always"]);
const ACTION_TONES = new Set(["neutral", "positive", "negative", "primary"]);

const changedOffers = () => {
  for (const listener of offerListeners) listener();
};

// One control grammar for every gesture in a target's RHS item. Contributors keep
// their verbs and events; the margin owns the anatomy that makes those controls one
// family and the collapse policy the shared layout can apply when horizontal room
// runs out. The visible word remains in the DOM when it is collapsed, so the same
// control can expand again without being rebuilt and its accessible name never changes.
export function marginAction(
  control,
  { glyph, label, collapse = "auto", tone = "neutral" },
) {
  if (!(control instanceof Element))
    throw new TypeError("A margin action needs an Element control");
  if (!String(glyph ?? "").trim()) throw new TypeError("A margin action needs a glyph");
  if (!String(label ?? "").trim()) throw new TypeError("A margin action needs a label");
  if (!ACTION_COLLAPSE.has(collapse))
    throw new TypeError(`Unknown margin-action collapse: ${collapse}`);
  if (!ACTION_TONES.has(tone))
    throw new TypeError(`Unknown margin-action tone: ${tone}`);

  control.classList.add("lf-margin-action");
  control.dataset.lfCollapse = collapse;
  control.dataset.lfTone = tone;
  let glyphNode = control.querySelector(":scope > .lf-margin-action-glyph");
  let spaceNode = control.querySelector(":scope > .lf-margin-action-space");
  let labelNode = control.querySelector(":scope > .lf-margin-action-label");
  if (!glyphNode) glyphNode = document.createElement("span");
  if (!spaceNode) spaceNode = document.createElement("span");
  if (!labelNode) labelNode = document.createElement("span");
  glyphNode.className = "lf-margin-action-glyph";
  glyphNode.setAttribute("aria-hidden", "true");
  glyphNode.textContent = glyph;
  spaceNode.className = "lf-margin-action-space";
  spaceNode.setAttribute("aria-hidden", "true");
  spaceNode.textContent = " ";
  labelNode.className = "lf-margin-action-label";
  labelNode.textContent = label;
  control.replaceChildren(glyphNode, spaceNode, labelNode);
  if (!control.hasAttribute("aria-label")) control.setAttribute("aria-label", label);
  return control;
}

export function registerMarginItem({
  target,
  controls,
  items = () => [],
  side = "before",
  claim = true,
}) {
  if (!new Set(["before", "after"]).has(side))
    throw new TypeError(`Unknown margin-item side: ${side}`);
  if (controls instanceof Element) controls.classList.add("lf-margin-contribution");
  const offered = { target, controls, items, side, claim };
  offeredItems.add(offered);
  changedOffers();
  return {
    update({ immediate = false } = {}) {
      changedOffers();
      if (immediate) layoutMarginRows();
    },
    unregister() {
      if (!offeredItems.delete(offered)) return;
      controls?.remove();
      changedOffers();
    },
  };
}

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
  const root = target.getRootNode();
  // IDs and sibling paths are scoped to a shadow root. Prefix them with the host's
  // own stable path so two instances of the same shadow template stay distinct,
  // while a live-version replacement at the same authored coordinate can still
  // retain its marker and preview focus.
  const prefix = root instanceof ShadowRoot ? `${targetPath(root.host)}/shadow/` : "";
  if (target.id) return `${prefix}id:${target.id}`;
  const steps = [];
  for (let node = target; node;) {
    const parent =
      node.parentElement ??
      (node.parentNode instanceof ShadowRoot ? node.parentNode : null);
    if (!parent) break;
    const siblings = [...parent.children].filter(
      (candidate) =>
        !candidate.classList.contains("lf-ui") &&
        !candidate.hasAttribute("data-lf-gen"),
    );
    steps.push(`${node.localName}:${siblings.indexOf(node)}`);
    if (node.localName === "main" || parent instanceof ShadowRoot) break;
    node = parent;
  }
  return `${prefix}path:${steps.reverse().join("/")}`;
}

function comesBefore(left, right) {
  if (left === right) return 0;
  if (!left) return 1;
  if (!right) return -1;
  // compareDocumentPosition calls nodes in separate shadow trees disconnected and
  // leaves their order implementation-specific. Build each composed ancestry instead:
  // the first divergent nodes share a document or shadow root and therefore have a
  // stable order. Keeping every inner step also distinguishes a target in an outer
  // tree from a later target inside one of its nested shadow hosts.
  const ancestry = (target) => {
    const chain = [];
    for (let node = target; node;) {
      chain.push(node);
      node =
        node.assignedSlot ?? node.parentElement ?? node.getRootNode()?.host ?? null;
    }
    return chain.reverse();
  };
  const leftChain = ancestry(left);
  const rightChain = ancestry(right);
  let index = 0;
  while (
    index < leftChain.length &&
    index < rightChain.length &&
    leftChain[index] === rightChain[index]
  )
    index += 1;
  if (index === leftChain.length || index === rightChain.length)
    return leftChain.length - rightChain.length;
  return leftChain[index].compareDocumentPosition(rightChain[index]) &
    Node.DOCUMENT_POSITION_FOLLOWING
    ? -1
    : 1;
}

export function createLivingMargin(dependencies) {
  const {
    anchorLabel,
    announce,
    approveBtn,
    banner,
    blockAt,
    chromeRoot,
    claimState,
    comparisonBase,
    comparisonChanges,
    compact,
    el,
    elementById,
    goToDecision,
    inChrome,
    itemSays,
    itemWord,
    keys,
    offer,
    openDecisions,
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
    "Changes, comments, decisions, outcomes, and activity",
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
    render();
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
  const hosts = new Map();
  const inlineHosts = new Map();
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

  function groupFor(groups, target, item = null) {
    if (target && (!target.isConnected || inChrome(target))) target = null;
    const lookup =
      target ?? `detached:${item?.kind ?? "action"}:${item?.id ?? groups.size}`;
    let group = groups.get(lookup);
    if (!group) {
      const key = target ? targetPath(target) : lookup;
      const word = target ? itemWord(target) : "Detached item";
      const said = target ? itemSays(target) : "No longer placed in this version";
      group = {
        key,
        target,
        title: trimmed([word, said].filter(Boolean).join(" · "), 72),
        items: [],
        offers: [],
      };
      groups.set(lookup, group);
    }
    return group;
  }

  function add(groups, target, item) {
    const group = groupFor(groups, target, item);
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

    const decisions = openDecisions();
    for (const decision of decisions) {
      const id = decision.id;
      add(groups, decision, {
        kind: "decision",
        id: `decision:${id}`,
        text: trimmed(`${itemWord(decision)} · ${itemSays(decision) || id}`),
        activate: () => {
          const standing = openDecisions();
          const next = standing.find((candidate) => candidate.id === id);
          if (next) goToDecision(next, standing);
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
        kind: "outcome",
        id: `outcome:${coordinate}`,
        text: trimmed(account),
        activate: () => revealTarget(target, `Outcome: ${account}`),
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

    for (const offered of offeredItems) {
      const target =
        typeof offered.target === "function" ? offered.target() : offered.target;
      if (!target?.isConnected || inChrome(target)) continue;
      const group = groupFor(groups, target);
      group.offers.push(offered);
      const items =
        typeof offered.items === "function" ? offered.items() : offered.items;
      for (const item of items ?? []) {
        const kind = item.kind ?? "action";
        if (!KINDS[kind]) throw new TypeError(`Unknown margin-item kind: ${kind}`);
        group.items.push({ marker: false, ...item, kind });
      }
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
      ...(row.lfEntry?.offers.length ? {} : { fallback: "hide" }),
      priority: 10,
      claim: () => {
        const entry = row.lfEntry;
        if (!entry) return 0;
        const stable = entry.offers
          .filter((offered) => offered.claim && offered.controls)
          .map((offered) => offered.controls);
        const marker = rows.get(entry.key);
        if (marker && !marker.hidden) stable.push(marker);
        const widths = stable
          .map((part) => part.getBoundingClientRect().width)
          .filter(Boolean);
        if (!widths.length) return 0;
        const style = getComputedStyle(row);
        const gap = parseFloat(style.columnGap || style.gap) || 0;
        return (
          widths.reduce((total, width) => total + width, 0) +
          gap * (widths.length - 1) +
          (parseFloat(style.paddingLeft) || 0) +
          (parseFloat(style.paddingRight) || 0)
        );
      },
      shown: (target) =>
        Boolean(target && shownParts(target).some((part) => part.checkVisibility())),
      condense: (item, column, room) => {
        if (!item.querySelector('[data-lf-collapse="auto"]')) return false;
        const parts = [...item.children].filter((part) => part.checkVisibility());
        if (!parts.length) return false;
        const style = getComputedStyle(item);
        const gap = parseFloat(style.columnGap || style.gap) || 0;
        const natural =
          parts.reduce((total, part) => {
            const partStyle = getComputedStyle(part);
            return (
              total +
              part.getBoundingClientRect().width +
              (parseFloat(partStyle.marginLeft) || 0) +
              (parseFloat(partStyle.marginRight) || 0)
            );
          }, 0) +
          gap * (parts.length - 1) +
          (parseFloat(style.paddingLeft) || 0) +
          (parseFloat(style.paddingRight) || 0);
        const available = compact.matches
          ? column.width
          : Math.max(0, room - item.getBoundingClientRect().left);
        return natural > available + 0.5;
      },
      // Compact mode has no page rail. Dock every contributed item even when a
      // positioned widget happens to leave enough local room for the absolute
      // prototype; that accident must not give one nested target a desktop posture.
      hangs: () => !compact.matches,
      place: (item, column) => {
        const target = item.lfEntry?.target;
        if (!target) return;
        if (nav.contains(item)) placeMargin(column);
        item.style.top = `${Math.max(0, shownBox(target).top - column.top)}px`;
      },
    };
  }

  function kindsIn(entry, { markerOnly = false } = {}) {
    const counts = new Map();
    for (const item of entry.items) {
      if (!markerOnly || item.marker !== false)
        counts.set(item.kind, (counts.get(item.kind) ?? 0) + 1);
    }
    return [...counts].map(([kind, count]) => ({ kind, count, ...KINDS[kind] }));
  }

  function markerName(entry, index, anchored) {
    const kinds = kindsIn(entry, { markerOnly: true })
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
    return [...rows.values()].filter(
      (row) => !row.hidden && !row.closest(".lf-waiting") && row.checkVisibility(),
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

  const marginKeys = [
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
  ];
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
    const markerKinds = kindsIn(entry, { markerOnly: true });
    row.lfEntry = entry;
    row.hidden = markerKinds.length === 0;
    row.dataset.lfKinds = markerKinds.map(({ kind }) => kind).join(" ");
    row.setAttribute("aria-label", markerName(entry, index, anchored));
    row.title = markerKinds
      .map(({ label, count }) => `${label}${count > 1 ? `s (${count})` : ""}`)
      .join(" · ");
    row.setAttribute("aria-controls", preview.id);
    row.setAttribute("aria-expanded", String(previewEntry?.key === entry.key));
    row.setAttribute("aria-pressed", String(pinnedKey === entry.key));
    const wanted = markerKinds.map(({ kind, symbol, label, count }) => {
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
    const markerCount = entry.items.filter((item) => item.marker !== false).length;
    if (markerCount > 1) {
      let count = row.querySelector(":scope > .lf-margin-count");
      if (!count) {
        count = el("span", "lf-margin-count");
        count.setAttribute("aria-hidden", "true");
      }
      count.textContent = markerCount;
      wanted.push(count);
    }
    for (const child of [...row.children]) if (!wanted.includes(child)) child.remove();
    wanted.forEach((child, position) => {
      if (row.children[position] !== child)
        row.insertBefore(child, row.children[position] ?? null);
    });
  }

  function externalPerch(target, main) {
    if (!main) return target;
    // A wide item must be a child of main's own positioning context. In the
    // compact flow it belongs immediately after the rendered block that owns its
    // target: hoisting every item to a common section makes controls for its first
    // paragraph appear after the section's last one. A declared shadow tree still
    // contributes to that one document-owned layer: climb through its host before
    // placing the item, otherwise the document stylesheet cannot give a plug-in's
    // controls the common action shape.
    let perch = compact.matches ? (blockAt(target) ?? target) : target;
    while (!main.contains(perch)) {
      const root = perch.getRootNode();
      if (!(root instanceof ShadowRoot)) return target;
      perch = root.host;
    }
    if (compact.matches) return perch;
    while (perch.parentElement !== main && main.contains(perch.parentElement))
      perch = perch.parentElement;
    return perch;
  }

  function syncControls(host, marker, entry) {
    const controls = (side) =>
      entry.offers
        .filter((offered) => offered.side === side && offered.controls)
        .map((offered) => offered.controls);
    const wanted = [...controls("before"), marker, ...controls("after")];
    for (const child of [...host.children]) if (!wanted.includes(child)) child.remove();
    wanted.forEach((child, position) => {
      if (host.children[position] !== child)
        host.insertBefore(child, host.children[position] ?? null);
    });
  }

  // A widget frozen into a conversation belongs to that conversation's document,
  // not to the page margin behind it. Keep its contributed controls in the local
  // flow, grouped by the same exact target identity, without registering a page rail
  // claim or a second placement model in the widget module.
  function syncInlineOffers() {
    const grouped = new Map();
    for (const offered of offeredItems) {
      const target =
        typeof offered.target === "function" ? offered.target() : offered.target;
      if (!target?.isConnected || !inChrome(target) || !offered.controls) continue;
      const offers = grouped.get(target) ?? [];
      offers.push(offered);
      grouped.set(target, offers);
    }

    for (const [target, offers] of grouped) {
      let host = inlineHosts.get(target);
      if (!host) {
        host = el("div", "lf-ui");
        host.dataset.lfGen = "1";
        host.setAttribute("role", "group");
        inlineHosts.set(target, host);
      }
      host.dataset.lfMarginFor = target.id || targetPath(target);
      host.setAttribute("aria-label", `Actions for ${itemWord(target)}`);
      const controls = (side) =>
        offers
          .filter((offered) => offered.side === side)
          .map((offered) => offered.controls);
      const wanted = [...controls("before"), ...controls("after")];
      for (const child of [...host.children])
        if (!wanted.includes(child)) child.remove();
      wanted.forEach((child, position) => {
        if (host.children[position] !== child)
          host.insertBefore(child, host.children[position] ?? null);
      });
      if (target.nextSibling !== host) moveHost(host, () => target.after(host));
    }

    for (const [target, host] of inlineHosts)
      if (!grouped.has(target)) {
        host.remove();
        inlineHosts.delete(target);
      }
  }

  function moveHost(host, move) {
    const held = host.contains(document.activeElement) ? document.activeElement : null;
    move();
    if (held?.isConnected) held.focus({ preventScroll: true });
  }

  function render() {
    const main = document.querySelector("main");
    if (!nav.isConnected) chromeRoot.append(nav);
    placeMargin(main?.getBoundingClientRect());
    syncInlineOffers();
    currentEntries = collectEntries();
    const anchoredEntries = currentEntries.filter((entry) => entry.target);
    const live = new Set(anchoredEntries.map((entry) => entry.key));
    for (const [key, marker] of rows)
      if (!live.has(key)) {
        const host = hosts.get(key);
        unregisterMarginRow(host);
        host?.remove();
        rows.delete(key);
        hosts.delete(key);
      }
    const externalDocks = new Map();
    let corePosition = 0;
    anchoredEntries.forEach((entry, index) => {
      let marker = rows.get(entry.key);
      let host = hosts.get(entry.key);
      if (host) host.lfEntry = entry;
      if (!marker) {
        host = el("div", "lf-ui lf-margin-item");
        host.dataset.lfGen = "1";
        host.setAttribute("role", "group");
        marker = marginAction(offer("button", "lf-margin-marker"), {
          glyph: "·",
          label: "Open page details",
          collapse: "always",
        });
        marker.onclick = (event) => {
          togglePinned(marker.lfEntry, marker);
          if (event.detail === 0 && pinnedKey === marker.lfEntry.key)
            previewList
              .querySelector("textarea, button")
              ?.focus({ preventScroll: true });
        };
        marker.addEventListener("pointerenter", () => {
          suppressedKey = null;
          showPreview(marker.lfEntry, marker);
        });
        marker.addEventListener("pointerleave", deferPreviewClose);
        marker.addEventListener("focus", () => {
          if (suppressedKey !== marker.lfEntry.key) showPreview(marker.lfEntry, marker);
        });
        marker.addEventListener("blur", deferPreviewClose);
        keys(
          host,
          "In the page map",
          marginKeys,
          () => document.activeElement === marker && visibleRows().length > 0,
        );
        host.lfEntry = entry;
        rows.set(entry.key, marker);
        hosts.set(entry.key, host);
        registerMarginRow(host, markerOptions(host));
      } else updateMarginRow(host, markerOptions(host));
      host.lfEntry = entry;
      host.dataset.lfMarginFor = entry.target.id || entry.key;
      host.setAttribute("aria-label", `Page actions for ${entry.title}`);
      marker.lfEntry = entry;
      syncControls(host, marker, entry);
      host.toggleAttribute(
        "data-lf-claims-rail",
        entry.offers.some((offered) => offered.claim && offered.controls),
      );
      if (entry.offers.length) {
        host.dataset.lfExternal = "1";
        const perch = externalPerch(entry.target, main);
        const dock = externalDocks.get(perch) ?? perch;
        if (dock.nextSibling !== host) moveHost(host, () => dock.after(host));
        externalDocks.set(perch, host);
      } else {
        delete host.dataset.lfExternal;
        if (toolbar.children[corePosition] !== host)
          moveHost(host, () =>
            toolbar.insertBefore(host, toolbar.children[corePosition] ?? null),
          );
        corePosition += 1;
      }
      paintMarker(marker, entry, index, anchoredEntries.length);
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
        const open = el("button", "lf-btn lf-margin-thread-open", "Open in Threads");
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
      // The room is the page's own and not the window's, which is the side's version of
      // the banner line two above. An open panel takes its strip out of the body rather
      // than standing over it (chrome-style.js), so a card placed against the window
      // stands in the panel — and one the reader left open covers the narrowing box at
      // the top of it, where the ring of the box they are typing in goes under this
      // card's ×. The margin's card belongs in the column the margin is drawn in.
      const roomRight = document.body.getBoundingClientRect().right;
      const rightRoom = roomRight - marker.right - 12;
      const left =
        rightRoom >= card.width + 8
          ? marker.right + 8
          : Math.max(12, marker.left - card.width - 8);
      preview.style.left = `${Math.min(left, roomRight - card.width - 12)}px`;
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
  // Blur on a marker is delayed so focus can enter its preview. Once focus leaves the
  // preview too, that bridge is spent: a keyboard reader's next control must not sit
  // under an unpinned card that belongs to the previous stop.
  preview.addEventListener("focusout", (event) => {
    const next = event.relatedTarget;
    if (!pinnedKey && !preview.contains(next) && next !== previewButton)
      closePreview(false);
  });
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
  offerListeners.add(render);
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
