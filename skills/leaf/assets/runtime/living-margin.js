import {
  layoutMarginRows,
  registerMarginRow,
  scheduleMarginLayout,
  unregisterMarginRow,
  updateMarginRow,
} from "./margin-layout.js";
import { documentPoint, shownBox, shownParts } from "./geometry.js";
import { clampedRow } from "./keyboard/bindings.js";

// `indication` marks a reading that reports rather than offers: a receipt for a move
// already made, or the outcome that answered it. The reader has nothing to press there,
// so the Button showing it wears the flat `receipt` promise below.
const KINDS = {
  action: { label: "Action", symbol: "·", priority: -1 },
  change: { label: "Change", symbol: "Δ", priority: 0 },
  comment: { label: "Thread", symbol: "💬", priority: 1 },
  decision: { label: "Ask", symbol: "?", priority: 2 },
  outcome: { label: "Outcome", symbol: "✓", priority: 3, indication: true },
  sent: { label: "Sent", symbol: "✓", priority: 3, indication: true },
  pickup: { label: "Picked up", symbol: "✓", priority: 3, indication: true },
  waiting: {
    label: "Waiting for pickup",
    symbol: "○",
    priority: 3,
    indication: true,
  },
  activity: { label: "Active", symbol: "●", priority: 4 },
};

// Content modules contribute what their target offers; this projection decides where
// those controls stand and joins them to every other reading of the same target. The
// store is module-level because widgets upgrade after the margin is composed and may
// reconnect while a live version replaces the authored document.
const offeredItems = new Set();
const offerListeners = new Set();
const ACTION_TONES = new Set(["neutral", "positive", "negative"]);
const ACTION_BEHAVIORS = new Set(["action", "disclosure", "options", "receipt"]);

const changedOffers = () => {
  for (const listener of offerListeners) listener();
};

// One Button grammar for every gesture in a target's RHS cluster. Contributors keep
// their verbs and events; the margin owns the behavior and anatomy that make the
// controls one family. The visible word remains in the DOM as a transient label, so
// every Button keeps one circular fitting and one stable accessible name. Native
// `title` bubbles would repeat that label on a different timer and with a different
// face, so this anatomy owns the only visual tooltip too.
//
// `receipt` is the one promise that is not a press. It keeps its glyph and its place in
// the cluster and gives up everything that offers a gesture: the raised circle in the
// stylesheet, the tab stop, and the button role. `role="status"` stands in for that role
// and the phase is the accessible name, so a reader walking the page map still lands
// here and hears what the Button reports.
export function marginAction(
  control,
  { glyph, label, behavior = "action", tone = "neutral" },
) {
  if (!(control instanceof Element))
    throw new TypeError("A margin action needs an Element control");
  if (!String(glyph ?? "").trim()) throw new TypeError("A margin action needs a glyph");
  if (!String(label ?? "").trim()) throw new TypeError("A margin action needs a label");
  if (!ACTION_TONES.has(tone))
    throw new TypeError(`Unknown margin-action tone: ${tone}`);
  if (!ACTION_BEHAVIORS.has(behavior))
    throw new TypeError(`Unknown margin-action behavior: ${behavior}`);
  const labelText = String(label);

  control.classList.add("lf-margin-action");
  control.removeAttribute("title");
  control.dataset.lfBehavior = behavior;
  control.dataset.lfTone = tone;
  const opens = behavior === "disclosure" || behavior === "options";
  if (opens && !control.hasAttribute("aria-expanded"))
    control.setAttribute("aria-expanded", "false");
  if (!opens) control.removeAttribute("aria-expanded");
  if (behavior === "receipt") {
    control.setAttribute("role", "status");
    control.tabIndex = -1;
  } else if (control.getAttribute("role") === "status") {
    control.removeAttribute("role");
    control.removeAttribute("tabindex");
  }
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
  // The ellipsis says a press opens something. Only the two behaviors that do wear it.
  labelNode.textContent =
    opens && !labelText.endsWith("…") ? `${labelText}…` : labelText;
  control.replaceChildren(glyphNode, spaceNode, labelNode);
  if (!control.hasAttribute("aria-label"))
    control.setAttribute("aria-label", labelText);
  return control;
}

export function registerMarginItem({
  target,
  controls,
  items = () => [],
  side = "before",
  claim = true,
  reserve = 0,
}) {
  if (!new Set(["before", "after"]).has(side))
    throw new TypeError(`Unknown margin-item side: ${side}`);
  if (controls instanceof Element) controls.classList.add("lf-margin-contribution");
  const offered = { target, controls, items, side, claim, reserve };
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
    acknowledgments,
    announce,
    approveBtn,
    blockAt,
    chromeRoot,
    claimState,
    comparisonBase,
    comparisonChanges,
    compact,
    closestAcross,
    currentRevision,
    designIsOn,
    droppedAt,
    el,
    elementById,
    focused,
    goToDecision,
    inChrome,
    itemSays,
    itemWord,
    keys,
    offer,
    openDecisions,
    panelIsOpen,
    paintKeys,
    placedAt,
    quietSince,
    renderMarginThread,
    scrollBehavior,
    scrollToElement,
    setPanel,
    showThread,
    stateProjection,
    threadPanel,
    threads,
    toggleBtn,
    updateSequence,
    versionBtn,
    waitingForPickupSince,
  } = dependencies;

  const nav = el("nav", "lf-ui lf-living-margin");
  nav.dataset.lfGen = "1";
  nav.setAttribute("aria-label", "Page map");
  const toolbar = el("div", "lf-margin-toolbar");
  toolbar.setAttribute("role", "toolbar");
  toolbar.setAttribute("aria-label", "Changes, threads, asks, outcomes, and activity");
  nav.append(toolbar);
  chromeRoot.append(nav);

  function placeMargin(
    columnRect = document.querySelector("main")?.getBoundingClientRect(),
  ) {
    const main = document.querySelector("main");
    if (!main || !columnRect) return;
    const at = documentPoint(columnRect.left, columnRect.top);
    nav.style.left = `${at.left}px`;
    nav.style.top = `${at.top}px`;
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
    if (compact.matches && preview.matches(":popover-open")) closePreview(false);
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
  preview.setAttribute("popover", "auto");
  preview.setAttribute("role", "dialog");
  const previewHead = el("div", "lf-margin-preview-head");
  const previewTitle = el("strong", "lf-margin-preview-title");
  const previewClose = el("button", "lf-btn lf-margin-preview-close", "×");
  previewClose.type = "button";
  previewClose.setAttribute("aria-label", "Close thread");
  previewHead.append(previewTitle, previewClose);
  const previewList = el("div", "lf-margin-preview-list");
  preview.append(previewHead, previewList);
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
  const moreButtons = new Map();
  const optionGroups = new Map();
  const controlProxies = new WeakMap();
  const readingButtons = new Map();
  const hosts = new Map();
  const inlineHosts = new Map();
  let optionsOrdinal = 0;
  let pageMapEntries = [];
  let previewEntry = null;
  let previewButton = null;
  let transferThreadFocus = false;
  let previewShowing = false;
  let pinnedKey = null;
  let forcedInlineKey = null;
  let expandedOptionsKey = null;
  let highlighted = null;
  let rovingFrame = 0;
  let sheetActivation = false;
  let previewRequest = 0;
  // The cascade owns available room: panels and trays change the body's named
  // container, while an authored sidebar claims the page's left strip. Read the
  // posture it resolved instead of asking the viewport a different question.
  const threadBeside = () =>
    getComputedStyle(document.querySelector("main"))
      .getPropertyValue("--lf-thread-beside")
      .trim() === "1";
  const markerNeedsPreview = (entry) => primaryReading(entry)?.kind === "comment";
  const controlsOf = (offered) => {
    const controls = offered.controls;
    if (!(controls instanceof Element)) return [];
    if (controls.matches(".lf-margin-action")) return [controls];
    return [...controls.querySelectorAll(":scope > .lf-margin-action")];
  };
  const offerReadings = (offered) => {
    const items = typeof offered.items === "function" ? offered.items() : offered.items;
    return items ?? [];
  };
  const standingAfterOffers = (entry) =>
    entry.offers.filter(
      (offered) => offered.side === "after" && offerReadings(offered).length > 0,
    );
  const directOffers = (entry) => [
    ...entry.offers.filter((offered) => offered.side === "before"),
    ...standingAfterOffers(entry),
  ];
  const directControls = (entry) => directOffers(entry).flatMap(controlsOf);
  const controlsShownByOwner = (controls) => {
    // The margin hides non-primary controls with `display: none`, so ask how this
    // batch paints while exempt from that rule. Write every exemption before the first
    // style read: alternating an attribute write and getComputedStyle would recalculate
    // the whole page once per Button. Contributor-owned `display` and `visibility`
    // still apply — including the retired half of a settled pair.
    const wasPrimary = controls.map((control) =>
      control.hasAttribute("data-lf-button-primary"),
    );
    for (const control of controls) control.setAttribute("data-lf-button-primary", "");
    let shown;
    try {
      shown = controls.filter((control) => {
        const style = getComputedStyle(control);
        return (
          !control.hidden && style.display !== "none" && style.visibility !== "hidden"
        );
      });
    } finally {
      controls.forEach((control, index) =>
        control.toggleAttribute("data-lf-button-primary", wasPrimary[index]),
      );
    }
    return shown;
  };
  function choosePrimary(entry) {
    const controls = controlsShownByOwner(directControls(entry));
    return controls[0] ?? null;
  }
  function syncControlRoles(entry) {
    const primary = choosePrimary(entry);
    for (const control of directControls(entry))
      control.toggleAttribute("data-lf-button-primary", control === primary);
    return primary;
  }
  const markerItems = (entry) => entry.items.filter((item) => item.marker !== false);
  const readingKey = (entry, choice) => `${entry.key}:${choice.key}`;
  const readingChoices = (entry) => {
    const threads = [];
    const choices = [];
    for (const item of markerItems(entry)) {
      if (item.kind === "comment") threads.push(item);
      else
        choices.push({
          key: item.id,
          kind: item.kind,
          items: [item],
          text: item.text,
        });
    }
    if (threads.length)
      choices.push({
        // One target owns one Thread Button. Membership changes repaint its badge and
        // card without replacing the control that owns an open conversation.
        key: "threads",
        kind: "comment",
        items: threads,
        text: threads[0].text,
      });
    return choices.sort(
      (left, right) => KINDS[left.kind].priority - KINDS[right.kind].priority,
    );
  };
  const primaryReading = (entry) => readingChoices(entry)[0] ?? null;
  const threadReading = (entry) =>
    readingChoices(entry).find((choice) => choice.kind === "comment") ?? null;
  const secondaryReadings = (entry, primaryControl) =>
    readingChoices(entry).slice(primaryControl ? 0 : 1);

  function threadButton(entry) {
    const marker = rows.get(entry.key);
    if (marker && !marker.hidden && primaryReading(entry)?.kind === "comment")
      return marker;
    const choice = threadReading(entry);
    return choice ? (readingButtons.get(readingKey(entry, choice)) ?? null) : null;
  }
  const secondaryControls = (entry, primary) =>
    controlsShownByOwner(directControls(entry)).filter(
      (control) => control !== primary,
    );
  const afterOffers = (entry, { claimedOnly = false } = {}) =>
    entry.offers.filter(
      (offered) =>
        offered.side === "after" &&
        offerReadings(offered).length === 0 &&
        offered.controls &&
        (!claimedOnly || offered.claim),
    );
  const optionsOffered = (entry, primary, { claimedOnly = false } = {}) => {
    // Generated readings are stable parts of the page map and claim their own `…`.
    // Temporary choices still borrow room unless their contributing owner claims it.
    if (secondaryReadings(entry, primary).length > 0) return true;
    return (
      (!claimedOnly || entry.offers.some((offered) => offered.claim)) &&
      (secondaryControls(entry, primary).length > 0 ||
        afterOffers(entry, { claimedOnly }).length > 0)
    );
  };

  function markerFace(entry) {
    const kinds = kindsIn(entry, { markerOnly: true });
    const choice = primaryReading(entry);
    const face =
      (choice?.items.length === 1 && choice.items[0].acknowledgmentFace) ||
      KINDS[choice?.kind] ||
      KINDS.action;
    const faceCount = choice?.items.length ?? 0;
    return {
      kinds,
      face,
      label: faceCount > 1 ? `${face.label}s` : face.label,
      // The badge describes this Button's result. Other readings live behind `…`
      // and must not make a Thread Button appear to open more threads than it does.
      count: faceCount,
    };
  }

  function syncThreadRelation(control, isThread) {
    if (!isThread) {
      control.removeAttribute("aria-controls");
      control.removeAttribute("aria-expanded");
      return;
    }
    const opensBeside = threadBeside() || forcedInlineKey === control.lfEntry?.key;
    control.setAttribute("aria-controls", opensBeside ? preview.id : threadPanel.id);
    if (opensBeside)
      control.setAttribute("aria-expanded", String(previewButton === control));
    else control.removeAttribute("aria-expanded");
  }
  let postureFrame = 0;
  let previewPositionFrame = 0;
  function schedulePostureRender() {
    if (postureFrame) return;
    postureFrame = requestAnimationFrame(() => {
      postureFrame = 0;
      render();
    });
  }
  function placeThreadPreview() {
    if (
      !preview.matches(":popover-open") ||
      !preview.hasAttribute("data-lf-thread") ||
      !previewButton?.isConnected
    )
      return;
    const marker = previewButton.getBoundingClientRect();
    // The stylesheet gives the card the room left to the right of this edge, so a marker
    // standing near the window's own edge would leave a conversation too narrow to read
    // or answer in. --thread-card-floor is where that room stops being a margin: past it
    // the card comes off its marker and covers the page instead, which is the posture a
    // bounded thread card is already allowed. An accepted comment opens its thread at
    // every width, so this is the only place the width can be refused.
    const floor = parseFloat(
      getComputedStyle(preview).getPropertyValue("--thread-card-floor"),
    );
    const besideLeft = Math.max(8, Math.min(marker.right + 8, innerWidth - 8 - floor));
    preview.style.setProperty("--lf-thread-left", `${besideLeft}px`);
    const card = preview.getBoundingClientRect();
    const bannerBottom =
      document.querySelector(".lf-banner")?.getBoundingClientRect().bottom ?? 0;
    const firstTop = bannerBottom + 8;
    const lastTop = innerHeight - card.height - 8;
    const besideTop = (marker.top + marker.bottom - card.height) / 2;
    preview.style.setProperty(
      "--lf-thread-top",
      `${Math.max(firstTop, Math.min(besideTop, lastTop))}px`,
    );
  }
  function scheduleThreadPreviewPosition() {
    if (previewPositionFrame) return;
    previewPositionFrame = requestAnimationFrame(() => {
      previewPositionFrame = 0;
      placeThreadPreview();
    });
  }
  // A viewport posture change can replace the focused full conversation with its
  // compact action. Reconcile after resize delivery so the browser can finish its
  // own focus and popover bookkeeping before that node changes shape. Panel and tray
  // changes notify this runtime directly through their owners.

  // A margin item is hoisted away from the page target it belongs to, so ancestry
  // cannot answer what a press on one of its controls is about. Keep that relationship
  // behind the owner that performs the hoist. Design mode uses it to turn the press into
  // a comment on the target and the named control instead of letting the action fire.
  function marginTargetAt(node) {
    const at = node?.nodeType === 1 ? node : node?.parentElement;
    return closestAcross(at, "[data-lf-margin-for]")?.lfTarget ?? null;
  }

  function groupFor(groups, target) {
    let group = groups.get(target);
    if (!group) {
      const key = targetPath(target);
      const kindWord = itemWord(target);
      const word = kindWord === "decision" ? "ask" : kindWord;
      group = {
        key,
        target,
        title: trimmed([word, itemSays(target)].filter(Boolean).join(" · "), 72),
        items: [],
        offers: [],
      };
      groups.set(target, group);
    }
    return group;
  }

  function add(groups, target, item) {
    if (!target?.isConnected || inChrome(target)) return;
    const group = groupFor(groups, target);
    group.items.push(item);
  }

  function visibleAcknowledgments() {
    const visible = [];
    for (const projected of acknowledgments()) {
      if (projected.revision > currentRevision()) continue;
      if (projected.phase !== "active" || claimState().claimsHeld) {
        visible.push(projected);
        continue;
      }
      if (!projected.event) continue;
      visible.push({
        ...projected,
        phase: projected.fallback_phase,
        ts: projected.fallback_ts,
        detail: null,
      });
    }
    return visible;
  }

  function acknowledgmentFace(receipt) {
    if (receipt.phase === "active") {
      const turnClosed =
        receipt.session && receipt.session === claimState().claimingSession
          ? claimState().agentTurnClosed
          : null;
      const quiet = quietSince(receipt.ts) || droppedAt(receipt.ts, turnClosed);
      return {
        kind: "activity",
        text: ["Active", receipt.detail, quiet ? "quiet" : null]
          .filter(Boolean)
          .join(" · "),
      };
    }
    if (receipt.phase === "picked_up") return { kind: "pickup", text: "Picked up" };
    if (waitingForPickupSince(receipt.ts))
      return { kind: "waiting", text: "Waiting for pickup" };
    return { kind: "sent", text: "Sent" };
  }

  function collectEntries() {
    const groups = new Map();
    const receiptByCoordinate = new Map();
    for (const receipt of visibleAcknowledgments()) {
      receiptByCoordinate.set(JSON.stringify(receipt.coordinate), receipt);
    }
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
    const activityAlreadyShown = new Set();
    for (const [coordinate, entry] of projection.desired) {
      if (entry.e.kind !== "action") continue;
      const target = elementById(entry.unit) ?? elementById(entry.e.widget);
      if (!target) continue;
      const account = [itemWord(target), humanized(entry.e.action), itemSays(target)]
        .filter(Boolean)
        .join(" · ");
      const receipt = receiptByCoordinate.get(coordinate);
      const face = receipt ? acknowledgmentFace(receipt) : null;
      if (face?.kind === "activity")
        activityAlreadyShown.add(`widget:${receipt.target.id}`);
      add(groups, target, {
        kind: "outcome",
        id: receipt ? `acknowledgment:${receipt.id}` : `outcome:${coordinate}`,
        text: trimmed(face ? `${face.text} · ${account}` : account),
        ...(face ? { acknowledgmentFace: KINDS[face.kind] } : {}),
        activate: () => revealTarget(target, `${face?.text ?? "Outcome"}: ${account}`),
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
        if (update.revision > currentRevision()) continue;
        if (activityAlreadyShown.has(`${update.target.kind}:${update.target.id}`))
          continue;
        const target =
          update.target.kind === "thread"
            ? placedAt(update.target.id)
            : elementById(update.target.id);
        const turnClosed =
          update.session && update.session === claimState().claimingSession
            ? claimState().agentTurnClosed
            : null;
        const quiet = quietSince(update.ts) || droppedAt(update.ts, turnClosed);
        const account = [
          update.agent || "Agent",
          update.text || humanized(update.action),
          quiet ? "quiet" : null,
        ]
          .filter(Boolean)
          .join(" · ");
        add(groups, target, {
          kind: "activity",
          id: `activity:${update.id}`,
          text: trimmed(account),
          acknowledgmentFace: KINDS.activity,
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
        const primary = choosePrimary(entry);
        const stable = [];
        if (primary && entry.offers.some((offered) => offered.claim))
          stable.push(primary);
        const marker = rows.get(entry.key);
        if (!primary && marker && !marker.hidden) stable.push(marker);
        const more = moreButtons.get(entry.key);
        if (more && optionsOffered(entry, primary, { claimedOnly: true }))
          stable.push(more);
        const widths = stable
          .map((part) => part.getBoundingClientRect().width)
          .filter(Boolean);
        const reserved = Math.max(
          0,
          ...entry.offers.map((offered) =>
            typeof offered.reserve === "function"
              ? offered.reserve()
              : offered.reserve || 0,
          ),
        );
        if (!widths.length && !reserved) return 0;
        const style = getComputedStyle(row);
        const gap = parseFloat(style.columnGap || style.gap) || 0;
        const current =
          widths.reduce((total, width) => total + width, 0) +
          gap * Math.max(0, widths.length - 1);
        return (
          Math.max(current, reserved) +
          (parseFloat(style.paddingLeft) || 0) +
          (parseFloat(style.paddingRight) || 0)
        );
      },
      shown: (target) =>
        Boolean(target && shownParts(target).some((part) => part.checkVisibility())),
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
    const choice = primaryReading(entry);
    const face = markerFace(entry).face;
    const count = choice?.items.length ?? 0;
    const reading = `${face.label}${count > 1 ? `s (${count})` : ""}`;
    const subject =
      count === 1 && choice.items[0].acknowledgmentFace ? choice.text : entry.title;
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
    return `${reading}, ${index + 1} of ${anchored}, ${subject}${position == null ? "" : `, ${Math.max(0, Math.min(100, position))} percent down`}`;
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

  function pageMapItems() {
    return pageMapEntries.map((entry) => hosts.get(entry.key)).filter(Boolean);
  }

  function openPageMapItem(item) {
    const entry = item?.lfEntry;
    if (!entry?.target) return;
    scrollToElement(entry.target, undefined, "nearest");
    const marker = rows.get(entry.key);
    if (marker && !marker.hidden) {
      if (compact.matches) openSheet(entry);
      else {
        // A pointer focuses the marker before its click. Reproduce that arrival, then let
        // the control's own click remain the one semantic path into its preview.
        marker.focus({ preventScroll: true });
        marker.click();
      }
      return;
    }
    const action = [...item.querySelectorAll(".lf-margin-action")].find(
      (control) =>
        control !== marker &&
        !control.disabled &&
        !control.hidden &&
        control.checkVisibility(),
    );
    action?.focus({ preventScroll: true });
  }

  function setOptionsOpen(entry, open, { returnFocus = false } = {}) {
    const previousKey = expandedOptionsKey;
    const previousGroup = previousKey ? optionGroups.get(previousKey) : null;
    const nextKey = open ? (entry?.key ?? null) : null;
    if (previousKey === nextKey) return;
    if (previewEntry) closePreview(false);
    expandedOptionsKey = nextKey;
    render();
    if (previousGroup?.querySelector(".lf-margin-reactions"))
      document.dispatchEvent(new CustomEvent("lf-button-options-closed"));
    if (returnFocus && previousKey) {
      const more = moreButtons.get(previousKey);
      if (more?.isConnected && !more.hidden) more.focus({ preventScroll: true });
    }
  }

  function openButtonOptions(target) {
    render();
    const entry = pageMapEntries.find((candidate) => candidate.target === target);
    const more = entry && moreButtons.get(entry.key);
    if (!entry || !more || more.hidden) return false;
    setOptionsOpen(entry, true);
    return true;
  }

  // Enter the rail without opening one addressed item. The roving marker is already the
  // Page map's reading position; prefer its visible member so the Arrow/Home/End scope is
  // live on arrival, and repair the tab stop when an earlier layout has not painted one.
  function focusPageMap() {
    const available = availableRows();
    if (!available.length) return false;
    const visible = visibleRows();
    const candidates = visible.length ? visible : available;
    const next = candidates.find((row) => row.tabIndex === 0) ?? candidates[0];
    if (!visible.length && next.lfEntry?.target)
      scrollToElement(next.lfEntry.target, "instant", "nearest");
    holdTabStop(next);
    next.focus({ preventScroll: true });
    return true;
  }

  // The Page map has one capability and two responsive surfaces. The margin rail is the
  // direct reading position where it has a member; the sheet is the complete map where
  // the rail has deliberately left the layout or the map is empty.
  function enterPageMap() {
    if (!focusPageMap()) openSheet();
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

  // The rail holds one tab stop. That stop is the way in from the page, not the reading
  // position: the walk, the numbered addresses, and the pointer all reach a marker
  // without it. A receipt is an indication rather than a press, so it never takes the
  // stop, and the stop passes to the nearest marker that acts. A rail with nothing but
  // receipts leaves the tab order altogether, and `M` and `m` are the way in.
  function holdTabStop(next) {
    const acts = (row) => row.dataset.lfBehavior !== "receipt";
    const stop = next && !acts(next) ? availableRows().find(acts) : next;
    for (const row of rows.values()) row.tabIndex = row === stop ? 0 : -1;
  }

  function syncRoving() {
    const available = availableRows();
    const visible = visibleRows();
    if (!available.length) {
      holdTabStop(null);
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
    holdTabStop(next);
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
    const next =
      edge === "first"
        ? visible[0]
        : edge === "last"
          ? visible.at(-1)
          : clampedRow(visible, document.activeElement, direction);
    holdTabStop(next);
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
  ];

  function paintMarker(row, entry, index, anchored, primary) {
    const { kinds: markerKinds, face, label, count: markerCount } = markerFace(entry);
    const choice = primaryReading(entry);
    row.lfEntry = entry;
    row.hidden = markerKinds.length === 0 || Boolean(primary);
    row.dataset.lfKinds = markerKinds.map(({ kind }) => kind).join(" ");
    marginAction(row, {
      glyph: face.symbol,
      label,
      behavior: face.indication ? "receipt" : "disclosure",
    });
    // Where this marker stands in the walk places it for a reader listening, and reads
    // as progress if it were painted. The name carries it; the visible word does not.
    row.setAttribute("aria-label", markerName(entry, index, anchored));
    syncThreadRelation(row, markerNeedsPreview(entry));
    row.removeAttribute("aria-pressed");
    if (markerCount > 1) {
      const count = el("span", "lf-margin-count");
      count.setAttribute("aria-hidden", "true");
      count.textContent = markerCount;
      row.append(count);
    }
    if (row.lfTakeFocus) {
      delete row.lfTakeFocus;
      (row.hidden ? document.body : row).focus({ preventScroll: true });
    }
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

  function optionControlNode(control, entry) {
    let node = controlProxies.get(control);
    if (!node) {
      node = offer("button", "lf-margin-option-proxy");
      node.type = "button";
      controlProxies.set(control, node);
    }
    const glyph =
      control.querySelector(":scope > .lf-margin-action-glyph")?.textContent || "·";
    const label =
      control.querySelector(":scope > .lf-margin-action-label")?.textContent ||
      control.textContent.trim() ||
      "Action";
    marginAction(node, {
      glyph,
      label,
      behavior: control.dataset.lfBehavior || "action",
      tone: control.dataset.lfTone || "neutral",
    });
    node.setAttribute("aria-label", control.getAttribute("aria-label") || label);
    node.disabled =
      control.disabled || control.getAttribute("aria-disabled") === "true";
    for (const attribute of [
      "aria-busy",
      "aria-controls",
      "aria-disabled",
      "aria-expanded",
      "aria-haspopup",
      "aria-pressed",
    ]) {
      const value = control.getAttribute(attribute);
      if (value == null) node.removeAttribute(attribute);
      else node.setAttribute(attribute, value);
    }
    node.onclick = () => {
      setOptionsOpen(entry, false, { returnFocus: true });
      control.click();
    };
    return node;
  }

  function readingOptionNode(entry, choice) {
    const key = readingKey(entry, choice);
    let node = readingButtons.get(key);
    if (!node) {
      node = offer("button", "lf-margin-reading-option");
      node.type = "button";
      readingButtons.set(key, node);
    }
    const face = KINDS[choice.kind];
    const count = choice.items.length;
    const label = count > 1 ? `${face.label}s` : face.label;
    marginAction(node, {
      glyph: face.symbol,
      label,
      behavior: "disclosure",
    });
    node.lfEntry = entry;
    node.lfChoice = choice;
    syncThreadRelation(node, choice.kind === "comment");
    node.dataset.lfKinds = choice.kind;
    node.setAttribute(
      "aria-label",
      `${label} for ${entry.title}${count > 1 ? `, ${count} items` : ""}`,
    );
    if (count > 1) {
      const badge = el("span", "lf-margin-count");
      badge.setAttribute("aria-hidden", "true");
      badge.textContent = count;
      node.append(badge);
    }
    node.onclick = () => {
      if (node.lfChoice.kind !== "comment") {
        setOptionsOpen(node.lfEntry, false, { returnFocus: true });
        activate(node.lfChoice.items[0], node.lfEntry, { focusMap: false });
        return;
      }
      openThreadChoice(node.lfEntry, node);
    };
    return node;
  }

  function syncOptionGroup(group, entry, primary) {
    const nodes = [
      ...secondaryControls(entry, primary).map((control) =>
        optionControlNode(control, entry),
      ),
      ...secondaryReadings(entry, primary).map((choice) =>
        readingOptionNode(entry, choice),
      ),
      ...afterOffers(entry)
        .map((offered) => offered.controls)
        .filter(Boolean),
    ];
    const wanted = [...new Set(nodes)];
    for (const child of [...group.children])
      if (!wanted.includes(child)) child.remove();
    wanted.forEach((child, position) => {
      if (group.children[position] !== child)
        group.insertBefore(child, group.children[position] ?? null);
    });
    group.lfEntry = entry;
    group.setAttribute("aria-label", `More options for ${entry.title}`);
    group.hidden = expandedOptionsKey !== entry.key || wanted.length === 0;
  }

  function syncControls(host, marker, more, options, entry) {
    const focusedOption = options.contains(document.activeElement);
    const primary = syncControlRoles(entry);
    const controls = directOffers(entry)
      .filter((offered) => offered.controls)
      .map((offered) => offered.controls);
    const wanted = [...controls, marker, more, options];
    for (const child of [...host.children]) if (!wanted.includes(child)) child.remove();
    wanted.forEach((child, position) => {
      if (host.children[position] !== child)
        host.insertBefore(child, host.children[position] ?? null);
    });
    more.hidden = !optionsOffered(entry, primary);
    if (more.hidden && expandedOptionsKey === entry.key) expandedOptionsKey = null;
    more.lfEntry = entry;
    more.setAttribute("aria-label", `More options for ${entry.title}`);
    more.setAttribute("aria-expanded", String(expandedOptionsKey === entry.key));
    host.toggleAttribute("data-lf-options-open", expandedOptionsKey === entry.key);
    syncOptionGroup(options, entry, primary);
    const lostOptionFocus = focusedOption && !options.contains(document.activeElement);
    if (more.hidden && (document.activeElement === more || lostOptionFocus)) {
      const destination = primary ?? (primaryReading(entry) ? marker : null);
      if (destination === marker && marker.hidden) marker.lfTakeFocus = true;
      else (destination ?? document.body).focus({ preventScroll: true });
    } else if (lostOptionFocus) {
      const next = [...options.querySelectorAll("button:not([disabled])")].find(
        (button) => button.checkVisibility(),
      );
      (next ?? more).focus({ preventScroll: true });
    }
    return primary;
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
      host.lfTarget = target;
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

  function unfoldOpenThreadOwner(entry) {
    const previousKey = expandedOptionsKey;
    const previousGroup = previousKey ? optionGroups.get(previousKey) : null;
    expandedOptionsKey = entry.key;
    render();
    if (previousGroup?.querySelector(".lf-margin-reactions"))
      document.dispatchEvent(new CustomEvent("lf-button-options-closed"));
  }

  function transferThreadCard(
    button,
    { returnFocus = document.activeElement === previewButton } = {},
  ) {
    if (previewButton === button) return;
    const previous = previewButton;
    previous?.style.removeProperty("anchor-name");
    previewButton = button;
    button.style.setProperty("anchor-name", "--lf-margin-preview");
    if (returnFocus) button.focus({ preventScroll: true });
  }

  function render() {
    const threadOwnerHeld =
      transferThreadFocus || document.activeElement === previewButton;
    transferThreadFocus = false;
    const main = document.querySelector("main");
    if (!nav.isConnected) chromeRoot.append(nav);
    placeMargin(main?.getBoundingClientRect());
    syncInlineOffers();
    pageMapEntries = collectEntries().filter((entry) => entry.target);
    const live = new Set(pageMapEntries.map((entry) => entry.key));
    const liveReadingKeys = new Set(
      pageMapEntries.flatMap((entry) =>
        readingChoices(entry).map((choice) => readingKey(entry, choice)),
      ),
    );
    for (const key of readingButtons.keys())
      if (!liveReadingKeys.has(key)) readingButtons.delete(key);
    if (expandedOptionsKey && !live.has(expandedOptionsKey)) expandedOptionsKey = null;
    for (const [key, marker] of rows)
      if (!live.has(key)) {
        const host = hosts.get(key);
        unregisterMarginRow(host);
        host?.remove();
        rows.delete(key);
        moreButtons.delete(key);
        optionGroups.delete(key);
        hosts.delete(key);
      }
    const externalDocks = new Map();
    let corePosition = 0;
    pageMapEntries.forEach((entry, index) => {
      let marker = rows.get(entry.key);
      let more = moreButtons.get(entry.key);
      let options = optionGroups.get(entry.key);
      let host = hosts.get(entry.key);
      if (host) host.lfEntry = entry;
      if (!marker) {
        host = el("div", "lf-ui lf-margin-item");
        host.dataset.lfGen = "1";
        host.setAttribute("role", "group");
        marker = marginAction(offer("button", "lf-margin-marker"), {
          glyph: "·",
          label: "Open page details",
          behavior: "disclosure",
        });
        marker.onclick = () => {
          const choice = primaryReading(marker.lfEntry);
          if (!choice) return;
          if (choice.kind !== "comment") {
            activate(choice.items[0], marker.lfEntry);
            return;
          }
          openThreadChoice(marker.lfEntry, marker);
        };
        keys(
          host,
          "In the page map",
          marginKeys,
          () => document.activeElement === marker && visibleRows().length > 0,
        );
        host.lfEntry = entry;
        rows.set(entry.key, marker);
        more = marginAction(offer("button", "lf-margin-more"), {
          glyph: "…",
          label: "More options",
          behavior: "options",
        });
        options = el("div", "lf-margin-options");
        options.id = `lf-margin-options-${++optionsOrdinal}`;
        options.hidden = true;
        options.setAttribute("role", "group");
        more.setAttribute("aria-controls", options.id);
        more.onclick = () => {
          setOptionsOpen(more.lfEntry, expandedOptionsKey !== more.lfEntry.key);
        };
        // Contributed primaries remain the owner's real control, so they do not pass
        // through the generated marker/proxy activation paths below. Close any unfolded
        // choices at the cluster boundary before that owner handles its press.
        host.addEventListener(
          "click",
          (event) => {
            if (!expandedOptionsKey) return;
            const primary = event.target.closest?.("[data-lf-button-primary]");
            if (primary && host.contains(primary)) setOptionsOpen(host.lfEntry, false);
          },
          { capture: true },
        );
        moreButtons.set(entry.key, more);
        optionGroups.set(entry.key, options);
        hosts.set(entry.key, host);
        registerMarginRow(host, markerOptions(host));
      } else updateMarginRow(host, markerOptions(host));
      host.lfEntry = entry;
      host.lfTarget = entry.target;
      host.dataset.lfMarginFor = entry.target.id || entry.key;
      host.setAttribute("aria-label", `Page actions for ${entry.title}`);
      marker.lfEntry = entry;
      const primary = syncControls(host, marker, more, options, entry);
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
      paintMarker(marker, entry, index, pageMapEntries.length, primary);
    });
    mapButton.hidden = pageMapEntries.length === 0;
    mapButton.textContent = `Map (${pageMapEntries.length})`;
    nav.hidden = pageMapEntries.length === 0;
    nav.setAttribute("aria-label", `Page map, ${pageMapEntries.length} locations`);
    if (sheet.open) renderSheet();
    if (previewEntry) {
      const fresh = pageMapEntries.find((entry) => entry.key === previewEntry.key);
      if (!fresh || !fresh.items.some((item) => item.kind === "comment"))
        closePreview(false);
      else if (forcedInlineKey !== fresh.key && !threadBeside()) {
        const threads = fresh.items.filter((item) => item.kind === "comment");
        closePreview(false);
        openThreads(threads, fresh);
      } else {
        previewEntry = fresh;
        const owner = threadButton(fresh);
        if (
          owner &&
          !owner.checkVisibility() &&
          forcedInlineKey !== fresh.key &&
          expandedOptionsKey !== fresh.key &&
          !moreButtons.get(fresh.key)?.hidden
        ) {
          transferThreadFocus = threadOwnerHeld;
          unfoldOpenThreadOwner(fresh);
          return;
        }
        if (!owner || (!owner.checkVisibility() && forcedInlineKey !== fresh.key))
          closePreview(false);
        else {
          transferThreadCard(owner, { returnFocus: threadOwnerHeld });
          buildThreadCard(fresh);
          highlight(fresh.target);
          for (const row of rows.values())
            syncThreadRelation(row, markerNeedsPreview(row.lfEntry));
          for (const reading of readingButtons.values())
            syncThreadRelation(reading, reading.lfChoice?.kind === "comment");
        }
      }
    }
    scheduleMarginLayout();
    scheduleRoving();
    paintKeys();
  }

  function buildThreadCard(entry) {
    const focusedNode = preview.contains(document.activeElement)
      ? document.activeElement.closest?.("[data-lf-margin-item]")
      : null;
    const focusedItem = focusedNode?.dataset.lfMarginItem ?? null;
    const threadItems = entry.items.filter((item) => item.kind === "comment");
    const targetHeading = entry.target?.querySelector(":scope > strong")?.textContent;
    const title = trimmed(targetHeading || entry.title, 72);
    preview.setAttribute("data-lf-thread", "");
    preview.setAttribute("aria-label", `Thread for ${title}`);
    previewTitle.textContent = title;
    const nodes = threadItems.map(previewItemNode);
    const keep = new Set(nodes);
    for (const child of [...previewList.children]) if (!keep.has(child)) child.remove();
    let cursor = previewList.firstChild;
    for (const node of nodes) {
      if (node === cursor) cursor = cursor.nextSibling;
      else previewList.insertBefore(node, cursor);
    }
    if (focusedItem && !focusedNode?.isConnected) {
      const replacement = [
        ...previewList.querySelectorAll("[data-lf-margin-item]"),
      ].find((candidate) => candidate.dataset.lfMarginItem === focusedItem);
      const destination = replacement?.matches("button, textarea:not([disabled])")
        ? replacement
        : (replacement?.querySelector("textarea:not([disabled])") ??
          replacement?.querySelector("button") ??
          previewClose);
      destination.focus({ preventScroll: true });
    }
    placeThreadPreview();
  }

  function previewItemNode(item) {
    let node = [...previewList.children].find(
      (candidate) => candidate.dataset.lfMarginItem === item.id,
    );
    if (!node?.classList.contains("lf-margin-thread")) {
      node?.remove();
      node = el("section", "lf-margin-thread");
      const body = el("div", "lf-margin-thread-body");
      node.append(body);
    }
    renderMarginThread(
      node.querySelector(":scope > .lf-margin-thread-body"),
      item.thread,
    );
    node.dataset.lfMarginItem = item.id;
    return node;
  }

  function highlight(target) {
    if (highlighted === target) return;
    highlighted?.classList.remove("lf-margin-target");
    highlighted = target;
    highlighted?.classList.add("lf-margin-target");
  }

  function showPreview(entry, button, retry = true) {
    if (!entry || designIsOn()) return;
    if (forcedInlineKey && forcedInlineKey !== entry.key) forcedInlineKey = null;
    previewEntry = entry;
    transferThreadCard(button);
    buildThreadCard(entry);
    // The open pseudo-class is not observable until the browser's show operation
    // completes, and another auto popover may still be closing in this rendering turn.
    if (!preview.matches(":popover-open") && !previewShowing) {
      previewShowing = true;
      try {
        // The pressed Thread Button owns the card's position through the anchor name
        // above. The card remains an ordinary popover rather than an implicit invoker
        // target so its close control and conversation keep their established order in
        // the shared chrome layer.
        preview.showPopover();
      } catch (error) {
        // Chromium also refuses a second popover operation in the same rendering turn,
        // even when it belongs to another surface. Keep the requested marker current and
        // try the show once that turn has settled; a focus move meanwhile cancels it, and
        // focus remains a usable Page-map arrival if the browser still refuses the preview.
        if (!(error instanceof DOMException) || error.name !== "InvalidStateError")
          throw error;
        if (retry)
          requestAnimationFrame(() => {
            if (previewButton === button && button.isConnected)
              showPreview(entry, button, false);
          });
      } finally {
        previewShowing = false;
      }
    }
    placeThreadPreview();
    highlight(entry.target);
    for (const row of rows.values())
      syncThreadRelation(row, markerNeedsPreview(row.lfEntry));
    for (const button of readingButtons.values())
      syncThreadRelation(button, button.lfChoice?.kind === "comment");
    paintKeys();
  }

  function togglePinned(entry, button) {
    if (pinnedKey === entry.key && previewButton === button) {
      pinnedKey = null;
      closePreview(false);
      return;
    }
    pinnedKey = entry.key;
    showPreview(entry, button);
  }

  function closePreview(returnFocus) {
    const button = previewButton;
    pinnedKey = null;
    forcedInlineKey = null;
    previewEntry = null;
    previewButton = null;
    button?.style.removeProperty("anchor-name");
    if (preview.matches(":popover-open")) preview.hidePopover();
    highlight(null);
    for (const row of rows.values())
      syncThreadRelation(row, markerNeedsPreview(row.lfEntry));
    for (const reading of readingButtons.values())
      syncThreadRelation(reading, reading.lfChoice?.kind === "comment");
    if (returnFocus) {
      if (button?.isConnected && button.checkVisibility())
        button.focus({ preventScroll: true });
      else if (button?.lfEntry) focusMapControl(button.lfEntry);
    }
    paintKeys();
  }

  // The card and its owning Button cluster are one page-map stack even though the card
  // is hoisted into the chrome. Expose the current rung to the one keyboard register so
  // it can stand ahead of reaction and navigation modes, preserving the local surface's
  // old order without another keydown listener. One press closes only the deepest rung.
  function keyboardRung({ atFocus = true } = {}) {
    const active = focused();
    const host = closestAcross(active, "[data-lf-margin-for]");
    if (
      preview.matches(":popover-open") &&
      (!atFocus ||
        preview.contains(active) ||
        (previewButton && host?.contains(previewButton)))
    )
      return {
        does: "Close the thread card",
        says: "close thread",
        out: () => closePreview(true),
      };
    const optionsHost = atFocus ? host : hosts.get(expandedOptionsKey);
    if (optionsHost?.lfEntry?.key === expandedOptionsKey)
      return {
        does: "Fold the secondary page actions",
        says: "close options",
        out: () => setOptionsOpen(optionsHost.lfEntry, false, { returnFocus: true }),
      };
    return null;
  }

  function activate(item, entry, { focusMap = true } = {}) {
    if (expandedOptionsKey && expandedOptionsKey !== entry.key)
      setOptionsOpen(entry, false);
    closePreview(false);
    if (sheet.open) {
      sheetActivation = true;
      sheet.close();
    }
    if (focusMap) focusMapControl(entry);
    item.activate();
  }

  function openThreadChoice(entry, button) {
    const open = () => {
      if (expandedOptionsKey && expandedOptionsKey !== entry.key)
        setOptionsOpen(entry, false);
      const choice = threadReading(entry);
      if (!choice) return;
      if (!threadBeside()) {
        setOptionsOpen(entry, false);
        openThreads(choice.items, entry);
        return;
      }
      togglePinned(entry, button);
    };
    if (panelIsOpen()) {
      const request = ++previewRequest;
      setPanel(false);
      const movements = document.body.getAnimations();
      Promise.allSettled(movements.map((movement) => movement.finished)).then(() => {
        if (request === previewRequest && button.isConnected) open();
      });
      return;
    }
    previewRequest += 1;
    open();
  }

  function openThreads(threadItems, entry) {
    if (threadItems.length === 1) {
      activate(threadItems[0], entry);
      return;
    }
    closePreview(false);
    focusMapControl(entry);
    setPanel(true);
  }

  function openInlineThread(id) {
    const itemId = `comment:${id}`;
    const entry = pageMapEntries.find((candidate) =>
      candidate.items.some((item) => item.id === itemId),
    );
    if (!entry || designIsOn()) return null;
    const choice = threadReading(entry);
    if (!choice) return null;
    if (panelIsOpen()) setPanel(false);
    let button = threadButton(entry);
    if (!button?.checkVisibility()) {
      setOptionsOpen(entry, true);
      button = threadButton(entry);
    }
    if (!button) return null;
    pinnedKey = entry.key;
    forcedInlineKey = entry.key;
    buildThreadCard(entry);
    showPreview(entry, button);
    const item = [...previewList.children].find(
      (candidate) => candidate.dataset.lfMarginItem === itemId,
    );
    item?.scrollIntoView({ behavior: scrollBehavior(), block: "nearest" });
    return item?.querySelector("textarea") ?? null;
  }

  function renderSheet() {
    const focusedItem = sheet.contains(document.activeElement)
      ? document.activeElement.dataset.lfMapItem
      : null;
    const heldScroll = sheetList.scrollTop;
    sheetList.replaceChildren(
      ...pageMapEntries.map((entry) => {
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

  function openSheet(entry = null) {
    renderSheet();
    if (!sheet.open) sheet.showModal();
    const index = entry
      ? pageMapEntries.findIndex((candidate) => candidate.key === entry.key)
      : -1;
    const group = index < 0 ? null : sheetList.children[index];
    if (group) {
      const listBox = sheetList.getBoundingClientRect();
      const groupBox = group.getBoundingClientRect();
      if (groupBox.top < listBox.top) sheetList.scrollTop -= listBox.top - groupBox.top;
      else if (groupBox.bottom > listBox.bottom)
        sheetList.scrollTop += groupBox.bottom - listBox.bottom;
    }
    (group?.querySelector(".lf-page-map-action") ?? sheetClose).focus({
      preventScroll: true,
    });
    paintKeys();
  }
  mapButton.onclick = () => openSheet();
  sheet.addEventListener("close", () => {
    paintKeys();
    if (sheetActivation) {
      sheetActivation = false;
      return;
    }
    focusMapControl();
  });
  previewClose.onclick = () => closePreview(true);
  preview.addEventListener("toggle", (event) => {
    if (event.newState !== "closed") return;
    if (!previewEntry) return;
    const button = previewButton;
    pinnedKey = null;
    forcedInlineKey = null;
    previewEntry = null;
    previewButton = null;
    button?.style.removeProperty("anchor-name");
    highlight(null);
    for (const row of rows.values())
      syncThreadRelation(row, markerNeedsPreview(row.lfEntry));
    for (const reading of readingButtons.values())
      syncThreadRelation(reading, reading.lfChoice?.kind === "comment");
    paintKeys();
  });
  // The row's acknowledgment face is read out of the state projection, so it follows the
  // applied log on `lf-actions` rather than the receipt paint: every path that reconciles
  // a complete state dispatches that once it has reconciled, and both of the paths that
  // paint receipts sit inside one. A repaint driven from the paint instead ran inside the
  // panel render the application performs *before* reconciliation, which is early enough
  // to read a candidate the same read is about to reject — and it ran inside a dispatch,
  // where the fault that candidate throws is reported as an uncaught page error rather
  // than rejecting the read.
  document.addEventListener("lf-actions", render);
  document.addEventListener("lf-answered", render);
  document.addEventListener("lf-comparison", render);
  offerListeners.add(render);
  document.addEventListener(
    "scroll",
    () => {
      scheduleRoving();
      scheduleThreadPreviewPosition();
    },
    { capture: true, passive: true },
  );
  window.addEventListener("resize", () => {
    placeThreadPreview();
    schedulePostureRender();
  });
  render();

  return {
    // The unfolded cluster, for a gesture that needs to know whether the fold standing
    // open is one it opened itself. The cluster and not a flag, because a fold open
    // somewhere is not the fold this gesture put on: the caller asks whose target it
    // belongs to (`lfTarget`) rather than whether any fold is open. The Page-map scope's
    // own rung reads the reader's position directly (`keyboardRung`) and needs neither.
    unfoldedButtons: () =>
      expandedOptionsKey ? (hosts.get(expandedOptionsKey) ?? null) : null,
    // Folding on the reader's behalf — a disarm putting back a fold its own raise opened
    // — happens wherever the reader is standing rather than inside the cluster, so it
    // takes no focus with it: the reader may have left that cluster, and a press already
    // on its way would land on a Button they were not standing on.
    foldButtonOptions: () => setOptionsOpen(null, false),
    activeInlineThread: () => {
      if (
        !pinnedKey ||
        previewEntry?.key !== pinnedKey ||
        document.activeElement !== previewButton ||
        !preview.matches(":popover-open") ||
        !preview.hasAttribute("data-lf-thread")
      )
        return null;
      const conversations = previewList.querySelectorAll(
        ".lf-margin-thread .lf-conversation-thread",
      );
      return conversations.length === 1 ? conversations[0] : null;
    },
    closePreview: () => closePreview(false),
    enterPageMap,
    keyboardRung,
    marginTargetAt,
    openButtonOptions,
    openInlineThread,
    openPageMapItem,
    pageMapItems,
    render,
  };
}
