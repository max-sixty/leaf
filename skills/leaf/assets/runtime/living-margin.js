import {
  layoutMarginRows,
  registerMarginRow,
  reserveRail,
  scheduleMarginLayout,
  unregisterMarginRow,
  updateMarginRow,
} from "./margin-layout.js";
import { documentPoint, shownBox, shownParts } from "./geometry.js";
import { clampedRow } from "./keyboard/bindings.js";
import { landInConversation } from "./conversation/landing.js";

const KINDS = {
  action: { label: "Action", icon: "dot", priority: -1 },
  change: { label: "Change", icon: "change", priority: 0 },
  comment: { label: "Thread", icon: "comment", priority: 1 },
  decision: { label: "Ask", icon: "question", priority: 2 },
  outcome: { label: "Outcome", icon: "check", priority: 3 },
  sent: { label: "Sent", icon: "sent", priority: 3 },
  pickup: { label: "Picked up", icon: "pickup", priority: 3 },
  waiting: { label: "Waiting for pickup", icon: "waiting", priority: 3 },
  activity: { label: "Active", icon: "activity", priority: 4 },
};

// Content modules contribute what their target offers; this projection decides where
// those controls stand and joins them to every other reading of the same target. The
// store is module-level because widgets upgrade after the margin is composed and may
// reconnect while a live version replaces the authored document.
const offeredItems = new Set();
const offerListeners = new Set();
const ACTION_TONES = new Set(["neutral", "positive", "negative"]);
const ACTION_BEHAVIORS = new Set(["action", "disclosure", "options"]);
const ACTION_STATES = new Set(["idle", "engaged", "busy", "failed", "settled"]);
const ACTION_ROLES = new Set([
  "complete",
  "escape",
  "primary",
  "secondary",
  "reading",
  "overflow",
]);
const ACTIVE_STATES = new Set(["engaged", "busy", "failed"]);
const STATE_PRIORITY = new Map([
  ["failed", 0],
  ["busy", 1],
  ["engaged", 2],
  ["settled", 3],
  ["idle", 3],
]);
const ROLE_PRIORITY = new Map([
  ["complete", 0],
  ["escape", 1],
  ["primary", 2],
  ["secondary", 3],
  ["reading", 4],
  ["overflow", 5],
]);
const RESTING_BUTTON_BUDGET = 2;
const EXPANDED_BUTTON_BUDGET = 6;

// Built-in Button faces use one stroked, currentColor icon vocabulary. Reaction tokens
// are authored content and may still supply a glyph; platform emoji never supplies a
// structural Leaf face, so line weight and baseline stay the same across systems.
const ICONS = {
  activity: '<circle cx="8" cy="8" r="3" fill="currentColor" stroke="none"/>',
  change:
    '<path d="M3 5.25h8.5M9.25 3l2.25 2.25L9.25 7.5M13 10.75H4.5M6.75 8.5 4.5 10.75 6.75 13"/>',
  check: '<path d="m3 8.25 3.15 3.15L13 4.75"/>',
  comment: '<path d="M3 3.25h10v7H7.25L4 12.75v-2H3z"/>',
  "compare-before":
    '<circle cx="8" cy="8" r="5.5"/><path d="M8 2.5a5.5 5.5 0 0 0 0 11Z" fill="currentColor" stroke="none"/>',
  "compare-after":
    '<circle cx="8" cy="8" r="5.5"/><path d="M8 2.5a5.5 5.5 0 0 1 0 11Z" fill="currentColor" stroke="none"/>',
  cross: '<path d="m4 4 8 8M12 4l-8 8"/>',
  dot: '<circle cx="8" cy="8" r="1.5" fill="currentColor" stroke="none"/>',
  edit: '<path d="m3.25 10.75-.5 2.5 2.5-.5 6.9-6.9-2-2zM9.25 4.75l2 2"/>',
  more: '<circle cx="3.5" cy="8" r="1" fill="currentColor" stroke="none"/><circle cx="8" cy="8" r="1" fill="currentColor" stroke="none"/><circle cx="12.5" cy="8" r="1" fill="currentColor" stroke="none"/>',
  all: '<path d="M3 4h6M3 8h6M3 12h6M12 8v4M10 10h4"/>',
  pickup: '<path d="M8 2.75v6.5M5.5 6.75 8 9.25l2.5-2.5M3 10.5v2h10v-2"/>',
  question:
    '<path d="M5.6 6.1a2.5 2.5 0 1 1 3.1 2.45c-.7.2-.7.8-.7 1.2"/><circle cx="8" cy="12.35" r=".7" fill="currentColor" stroke="none"/>',
  retry: '<path d="M12.5 5.25V2.75M12.5 2.75H10M12.35 3.1A5 5 0 1 0 13 9"/>',
  sent: '<path d="M2.75 3.25 13.25 8 2.75 12.75l1.2-4L9 8 3.95 7.25z"/>',
  undo: '<path d="M5.25 4.25 2.75 6.5 5.25 8.75M3 6.5h5.5a4 4 0 0 1 4 4v1"/>',
  waiting: '<circle cx="8" cy="8" r="5"/><path d="M8 5v3.25l2 1.25"/>',
};

export function iconElement(icon, className = "lf-margin-action-icon") {
  if (!ICONS[icon]) throw new TypeError(`Unknown Leaf icon: ${icon}`);
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 16 16");
  svg.setAttribute("focusable", "false");
  svg.setAttribute("aria-hidden", "true");
  svg.classList.add(className);
  svg.dataset.lfIcon = icon;
  svg.innerHTML = ICONS[icon];
  return svg;
}

const changedOffers = () => {
  for (const listener of offerListeners) listener();
};

// One Button grammar for every gesture in a target's RHS cluster. Contributors keep
// their verbs and events; the margin owns the behavior and anatomy that make the
// controls one family. The visible word remains in the DOM as a transient label, so
// every Button keeps one circular fitting and one stable accessible name. Native
// `title` bubbles would repeat that label on a different timer and with a different
// face, so this anatomy owns the only visual tooltip too.
export function marginAction(
  control,
  {
    glyph = null,
    icon = null,
    key,
    label,
    behavior = "action",
    tone = "neutral",
    role = "primary",
    state = "idle",
  },
) {
  if (!(control instanceof Element))
    throw new TypeError("A margin action needs an Element control");
  if (!String(key ?? "").trim()) throw new TypeError("A margin action needs a key");
  if (Boolean(String(glyph ?? "").trim()) === Boolean(icon))
    throw new TypeError("A margin action needs exactly one glyph or icon");
  if (!String(label ?? "").trim()) throw new TypeError("A margin action needs a label");
  if (!ACTION_TONES.has(tone))
    throw new TypeError(`Unknown margin-action tone: ${tone}`);
  if (!ACTION_BEHAVIORS.has(behavior))
    throw new TypeError(`Unknown margin-action behavior: ${behavior}`);
  if (!ACTION_ROLES.has(role))
    throw new TypeError(`Unknown margin-action role: ${role}`);
  const labelText = String(label);

  control.classList.add("lf-margin-action");
  control.removeAttribute("title");
  control.dataset.lfButtonKey = String(key);
  control.dataset.lfBehavior = behavior;
  control.dataset.lfTone = tone;
  control.dataset.lfRole = role;
  marginActionState(control, state);
  if (behavior !== "action" && !control.hasAttribute("aria-expanded"))
    control.setAttribute("aria-expanded", "false");
  if (behavior === "action") control.removeAttribute("aria-expanded");
  let glyphNode = control.querySelector(
    ":scope > :is(.lf-margin-action-glyph, .lf-margin-action-icon)",
  );
  let spaceNode = control.querySelector(":scope > .lf-margin-action-space");
  let labelNode = control.querySelector(":scope > .lf-margin-action-label");
  if (icon) {
    glyphNode = iconElement(icon);
  } else {
    if (!(glyphNode instanceof HTMLSpanElement))
      glyphNode = document.createElement("span");
    glyphNode.className = "lf-margin-action-glyph";
    glyphNode.removeAttribute("data-lf-icon");
    glyphNode.textContent = glyph;
  }
  if (!spaceNode) spaceNode = document.createElement("span");
  if (!labelNode) labelNode = document.createElement("span");
  glyphNode.setAttribute("aria-hidden", "true");
  spaceNode.className = "lf-margin-action-space";
  spaceNode.setAttribute("aria-hidden", "true");
  spaceNode.textContent = " ";
  labelNode.className = "lf-margin-action-label";
  labelNode.textContent =
    behavior === "action" || labelText.endsWith("…") ? labelText : `${labelText}…`;
  control.replaceChildren(glyphNode, spaceNode, labelNode);
  if (!control.hasAttribute("aria-label"))
    control.setAttribute("aria-label", labelText);
  return control;
}

export function marginActionState(control, state) {
  if (!(control instanceof Element) || !control.classList.contains("lf-margin-action"))
    throw new TypeError("A margin-action state needs a margin action");
  if (!ACTION_STATES.has(state))
    throw new TypeError(`Unknown margin-action state: ${state}`);
  control.dataset.lfState = state;
  if (state === "busy") control.setAttribute("aria-busy", "true");
  else control.removeAttribute("aria-busy");
  return control;
}

export function registerMarginItem({
  key,
  target,
  controls,
  items = () => [],
  state = "idle",
  side = "before",
  claim = true,
  reserve = 0,
}) {
  if (!String(key ?? "").trim()) throw new TypeError("A margin item needs a key");
  if (!new Set(["before", "after"]).has(side))
    throw new TypeError(`Unknown margin-item side: ${side}`);
  if (typeof state !== "string" && typeof state !== "function")
    throw new TypeError("A margin item's state must be a string or function");
  if (typeof state === "string" && !ACTION_STATES.has(state))
    throw new TypeError(`Unknown margin-item state: ${state}`);
  if (controls instanceof Element) controls.classList.add("lf-margin-contribution");
  const offered = {
    key: String(key),
    target,
    controls,
    items,
    state,
    side,
    claim,
    reserve,
  };
  offeredItems.add(offered);
  changedOffers();
  return {
    update({ immediate = false } = {}) {
      changedOffers();
      if (immediate) layoutMarginRows();
    },
    unregister() {
      if (!offeredItems.delete(offered)) return;
      // Let the projection detach a focused contribution while its focus-settling
      // guard is active. Removing it first can synchronously fire focusout, whose
      // fold render moves that same node before Element.remove completes.
      changedOffers();
      controls?.remove();
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
    foldShelf,
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
    updateSequence,
    versionBtn,
    waitingForPickupSince,
  } = dependencies;

  const nav = el("nav", "lf-ui lf-living-margin");
  // Every live page can gain an anchored comment, including one made entirely of prose.
  reserveRail();
  nav.dataset.lfGen = "1";
  nav.setAttribute("aria-label", "Page map");
  const toolbar = el("div", "lf-margin-toolbar");
  toolbar.setAttribute("role", "toolbar");
  toolbar.setAttribute("aria-label", "Changes, threads, asks, outcomes, and activity");
  nav.append(toolbar);
  chromeRoot.append(nav);

  function measureMargin(
    columnRect = document.querySelector("main")?.getBoundingClientRect(),
  ) {
    const main = document.querySelector("main");
    if (!main || !columnRect) return;
    const at = documentPoint(columnRect.left, columnRect.top);
    const height = main.scrollHeight;
    return () => {
      nav.style.left = `${at.left}px`;
      nav.style.top = `${at.top}px`;
      nav.style.width = `${columnRect.width}px`;
      nav.style.height = `${height}px`;
    };
  }

  const mapButton = el("button", "lf-btn lf-page-map-toggle", "Map");
  mapButton.type = "button";
  mapButton.hidden = true;
  mapButton.title = "Open the page map";
  function changePosture() {
    const marginHeld =
      toolbar.contains(document.activeElement) ||
      preview.contains(document.activeElement);
    const sheetHeld = sheet.contains(document.activeElement);
    if (compact.matches && preview.matches(":popover-open")) closePreview(false);
    if (compact.matches && marginHeld) requestAnimationFrame(() => focusMapControl());
    if (!compact.matches && sheet.open) {
      sheetActivation = true;
      sheet.close();
      if (sheetHeld) requestAnimationFrame(() => focusMapControl());
    }
    render();
  }
  // One seat in the banner's one order, taken once: the map stands with the page's other
  // destinations, just before the version chooser. It used to take the far side of
  // approval under the compact query and be re-placed on every crossing of it, which was
  // the same address at two different places on one row — and, because a blanket answer
  // that had arrived in between claims that same seat, the seat it landed in depended on
  // which way the reader had last crossed 900px. Placed at build, before any of them.
  versionBtn.before(mapButton);
  foldShelf();
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
  const spillButtons = new Map();
  const spilledOptions = new Map();
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
  let hoveredKey = null;
  let settlingOptionsFocus = false;
  let suppressingOptionsArrival = false;
  let highlighted = null;
  let rovingFrame = 0;
  let sheetActivation = false;
  let sheetFrom = null;
  let sheetTarget = null;
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
    return [...controls.querySelectorAll(".lf-margin-action")];
  };
  const offerReadings = (offered) => {
    const items = typeof offered.items === "function" ? offered.items() : offered.items;
    return items ?? [];
  };
  const offerState = (offered) => {
    const state = typeof offered.state === "function" ? offered.state() : offered.state;
    if (!ACTION_STATES.has(state))
      throw new TypeError(`Unknown margin-item state: ${state}`);
    return state;
  };
  // One target has one lifecycle reading. Failure outranks work in flight, which
  // outranks an open interaction; a settled receipt and the ordinary idle state never
  // force peers open. Generated acknowledgment readings join through the same state
  // axis rather than a second engagement flag.
  const entryState = (entry) => {
    const states = [
      ...entry.offers.map(offerState),
      ...entry.items.map(
        (item) => item.state ?? (item.acknowledgmentFace ? "busy" : "idle"),
      ),
    ];
    return (
      states.sort(
        (left, right) => STATE_PRIORITY.get(left) - STATE_PRIORITY.get(right),
      )[0] ?? "idle"
    );
  };
  const entryEngaged = (entry) => ACTIVE_STATES.has(entryState(entry));
  // A modal or contextual thread surface temporarily owns focus without ending the
  // document interaction beneath it. Preserve that context so its commands remain
  // true and its owning Button can receive focus when the surface closes.
  const inRetainedContext = (node) =>
    node instanceof Element &&
    (Boolean(node.closest("dialog[open]")) ||
      preview.contains(node) ||
      (panelIsOpen() && threadPanel.contains(node)));
  const compareOffers = (left, right) => {
    const state =
      STATE_PRIORITY.get(offerState(left)) - STATE_PRIORITY.get(offerState(right));
    if (state) return state;
    return left.key.localeCompare(right.key);
  };
  const standingAfterOffers = (entry) =>
    entry.offers
      .filter(
        (offered) => offered.side === "after" && offerReadings(offered).length > 0,
      )
      .sort(compareOffers);
  const directOffers = (entry) => [
    ...entry.offers.filter((offered) => offered.side === "before").sort(compareOffers),
    ...standingAfterOffers(entry),
  ];
  const compareControlRecords = (left, right) => {
    const state =
      STATE_PRIORITY.get(offerState(left.offered)) -
      STATE_PRIORITY.get(offerState(right.offered));
    if (state) return state;
    const role =
      ROLE_PRIORITY.get(left.control.dataset.lfRole) -
      ROLE_PRIORITY.get(right.control.dataset.lfRole);
    if (role) return role;
    const offer = left.offered.key.localeCompare(right.offered.key);
    if (offer) return offer;
    return left.control.dataset.lfButtonKey.localeCompare(
      right.control.dataset.lfButtonKey,
    );
  };
  const directControlRecords = (entry) =>
    directOffers(entry)
      .flatMap((offered) =>
        controlsOf(offered).map((control) => ({ control, offered })),
      )
      .sort(compareControlRecords);
  const directControls = (entry) =>
    directControlRecords(entry).map(({ control }) => control);
  const controlsShownByOwner = (controls) => {
    // The margin hides non-primary controls with `display: none`, so ask how this
    // batch paints while exempt from that rule. Write every exemption before the first
    // style read: alternating an attribute write and getComputedStyle would recalculate
    // the whole page once per Button. Contributor-owned `display` and `visibility`
    // still apply — including the retired half of a settled pair.
    const wasPrimary = controls.map((control) =>
      control.hasAttribute("data-lf-button-primary"),
    );
    const wasOverflow = controls.map((control) =>
      control.hasAttribute("data-lf-button-overflow"),
    );
    for (const control of controls) {
      control.setAttribute("data-lf-button-primary", "");
      control.removeAttribute("data-lf-button-overflow");
    }
    let shown;
    try {
      shown = controls.filter((control) => {
        const style = getComputedStyle(control);
        return (
          !control.hidden && style.display !== "none" && style.visibility !== "hidden"
        );
      });
    } finally {
      controls.forEach((control, index) => {
        control.toggleAttribute("data-lf-button-primary", wasPrimary[index]);
        control.toggleAttribute("data-lf-button-overflow", wasOverflow[index]);
      });
    }
    return shown;
  };
  function choosePrimary(entry) {
    return (
      directControlRecords(entry).find(({ control }) =>
        entry.shownControls.has(control),
      )?.control ?? null
    );
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
      (left, right) =>
        KINDS[left.kind].priority - KINDS[right.kind].priority ||
        left.key.localeCompare(right.key),
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
    directControls(entry).filter(
      (control) => control !== primary && entry.shownControls.has(control),
    );
  const afterOffers = (entry, { claimedOnly = false } = {}) =>
    entry.offers
      .filter(
        (offered) =>
          offered.side === "after" &&
          offerReadings(offered).length === 0 &&
          offered.controls &&
          (!claimedOnly || offered.claim),
      )
      .sort(compareOffers);
  const secondaryCount = (entry, primary, { claimedOnly = false } = {}) => {
    const generated = secondaryReadings(entry, primary).length;
    const contributed = secondaryControls(entry, primary).length;
    const after = afterOffers(entry, { claimedOnly }).reduce(
      (count, offered) =>
        count +
        controlsOf(offered).filter((control) => entry.shownControls.has(control))
          .length,
      0,
    );
    if (claimedOnly && !entry.offers.some((offered) => offered.claim)) return generated;
    return generated + contributed + after;
  };
  // One peer is not overflow. It costs the same second circle as `…`, but the peer says
  // what it does and is immediately usable. Ellipsis earns its place only from the third
  // Button onward.
  const optionsOffered = (entry, primary, options = {}) =>
    secondaryCount(entry, primary, options) > RESTING_BUTTON_BUDGET - 1;

  function markerFace(entry) {
    const kinds = kindsIn(entry, { markerOnly: true });
    const choice = primaryReading(entry);
    const face = readingFace(choice);
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

  function readingFace(choice) {
    return (
      (choice?.items.length === 1 && choice.items[0].acknowledgmentFace) ||
      KINDS[choice?.kind] ||
      KINDS.action
    );
  }

  function readingState(choice) {
    return (
      (choice?.items ?? [])
        .map((item) => item.state ?? (item.acknowledgmentFace ? "busy" : "idle"))
        .sort(
          (left, right) => STATE_PRIORITY.get(left) - STATE_PRIORITY.get(right),
        )[0] ?? "idle"
    );
  }

  function syncThreadRelation(control, isThread) {
    if (!isThread) {
      control.removeAttribute("aria-controls");
      control.removeAttribute("aria-expanded");
      return;
    }
    const opensBeside =
      !panelIsOpen() && (threadBeside() || forcedInlineKey === control.lfEntry?.key);
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
      if (group.offers.some((candidate) => candidate.key === offered.key))
        throw new TypeError(
          `Duplicate margin-item key for ${target.id || targetPath(target)}: ${offered.key}`,
        );
      group.offers.push(offered);
      for (const control of controlsOf(offered))
        control.dataset.lfButtonOwner = offered.key;
      const items =
        typeof offered.items === "function" ? offered.items() : offered.items;
      for (const item of items ?? []) {
        const kind = item.kind ?? "action";
        if (!KINDS[kind]) throw new TypeError(`Unknown margin-item kind: ${kind}`);
        group.items.push({ marker: false, ...item, kind });
      }
    }

    return [...groups.values()]
      .map((group) => {
        const represented = new Set(
          group.items
            .filter((item) => item.marker === false && item.represents)
            .map((item) => item.kind),
        );
        return {
          ...group,
          items: group.items
            .filter(
              (item) =>
                item.marker === false ||
                item.acknowledgmentFace ||
                !represented.has(item.kind),
            )
            .sort(
              (left, right) =>
                KINDS[left.kind].priority - KINDS[right.kind].priority ||
                // Threads at one target keep the conversation's log order, not
                // the arbitrary spelling of their event identities.
                (left.kind === "comment" ? 0 : left.id.localeCompare(right.id)),
            ),
        };
      })
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
        const options = optionGroups.get(entry.key);
        if (
          options &&
          !optionsOffered(entry, primary, { claimedOnly: true }) &&
          secondaryCount(entry, primary, { claimedOnly: true }) > 0
        )
          stable.push(...clusterButtons(options));
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
        const place = nav.contains(item) ? measureMargin(column) : null;
        const top = Math.max(0, shownBox(target).top - column.top);
        return () => {
          place?.();
          item.style.top = `${top}px`;
        };
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

  function clusterButtons(host) {
    if (!host) return [];
    return [...host.querySelectorAll(".lf-margin-action")].filter(
      (button) =>
        !button.disabled &&
        button.getAttribute("aria-disabled") !== "true" &&
        button.checkVisibility(),
    );
  }

  const buttonHost = (target) =>
    [...hosts.values()].find((host) => host.lfTarget === target) ?? null;

  function buttonContextContains(target, node) {
    return (
      Boolean(buttonHost(target)?.contains(node)) ||
      (sheet.open && sheetTarget === target && sheet.contains(node))
    );
  }

  function stepClusterButtons(binding) {
    const active = focused();
    const host = closestAcross(active, "[data-lf-margin-for]");
    const buttons = clusterButtons(host);
    const at = buttons.indexOf(active);
    if (at < 0 || buttons.length < 2) return;
    const direction = binding === "ArrowRight" ? 1 : -1;
    buttons[(at + direction + buttons.length) % buttons.length].focus({
      preventScroll: true,
    });
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
    if (action) focusForNavigation(action);
  }

  function setOptionsOpen(
    entry,
    open,
    { returnFocus = false, focusOption = null } = {},
  ) {
    const previousKey = expandedOptionsKey;
    const previousGroup = previousKey ? optionGroups.get(previousKey) : null;
    const nextKey = open ? (entry?.key ?? null) : null;
    if (previousKey === nextKey) return;
    if (previewEntry) closePreview(false);
    expandedOptionsKey = nextKey;
    settlingOptionsFocus = true;
    try {
      render();
      if (returnFocus && previousKey) {
        const more = moreButtons.get(previousKey);
        if (more?.isConnected && !more.hidden) more.focus({ preventScroll: true });
      } else if (focusOption && nextKey) {
        const choices = clusterButtons(optionGroups.get(nextKey));
        const fallback = clusterButtons(hosts.get(nextKey));
        const next =
          (focusOption === "last" ? choices.at(-1) : choices[0]) ??
          (focusOption === "last" ? fallback.at(-1) : fallback[0]);
        next?.focus({ preventScroll: true });
      }
    } finally {
      settlingOptionsFocus = false;
    }
    if (previousGroup?.querySelector(".lf-margin-reactions"))
      document.dispatchEvent(new CustomEvent("lf-button-options-closed"));
  }

  function focusForNavigation(control) {
    const wasSuppressingOptionsArrival = suppressingOptionsArrival;
    suppressingOptionsArrival = true;
    try {
      control.focus({ preventScroll: true });
    } finally {
      suppressingOptionsArrival = wasSuppressingOptionsArrival;
    }
  }

  function openButtonOptions(target) {
    render();
    const entry = pageMapEntries.find((candidate) => candidate.target === target);
    const more = entry && moreButtons.get(entry.key);
    if (!entry || !more) return false;
    if (expandedOptionsKey === entry.key) return true;
    if (more.hidden) return false;
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

  const pageMapIsActive = () => sheet.open || availableRows().includes(focused());
  function leavePageMap() {
    if (sheet.open) sheet.close();
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

  // The rail holds one tab stop: the way in from the page, not the reading position,
  // which the walk, the numbered addresses, and the pointer all reach without it.
  function holdTabStop(next) {
    for (const row of rows.values()) row.tabIndex = row === next ? 0 : -1;
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
      id: "margin.buttons",
      keys: ["ArrowLeft", "ArrowRight"],
      does: "Move through the Buttons on this target",
      line: "move through Buttons",
      repeat: true,
      when: () => {
        const active = focused();
        const host = closestAcross(active, "[data-lf-margin-for]");
        return (
          active?.matches?.(".lf-margin-action") && clusterButtons(host).length > 1
        );
      },
      run: stepClusterButtons,
    },
    {
      id: "margin.walk",
      keys: ["ArrowUp", "ArrowDown"],
      does: "Walk the visible page-map markers",
      line: "walk the page map",
      repeat: true,
      when: () => focused()?.matches?.(".lf-margin-marker") && visibleRows().length > 0,
      run: (binding) => walkMarkers(binding === "ArrowDown" ? 1 : -1),
    },
    {
      id: "margin.first",
      keys: ["Home"],
      does: "First visible page-map marker",
      line: "first marker",
      when: () => focused()?.matches?.(".lf-margin-marker") && visibleRows().length > 0,
      run: () => walkMarkers(0, "first"),
    },
    {
      id: "margin.last",
      keys: ["End"],
      does: "Last visible page-map marker",
      line: "last marker",
      when: () => focused()?.matches?.(".lf-margin-marker") && visibleRows().length > 0,
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
      key: `reading:${choice?.key ?? "none"}`,
      icon: face.icon,
      label,
      behavior: "disclosure",
      role: "reading",
      state: readingState(choice),
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
    const icon = control.querySelector(":scope > .lf-margin-action-icon")?.dataset
      .lfIcon;
    const glyph = control.querySelector(
      ":scope > .lf-margin-action-glyph",
    )?.textContent;
    const label =
      control.querySelector(":scope > .lf-margin-action-label")?.textContent ||
      control.textContent.trim() ||
      "Action";
    marginAction(node, {
      key: `${control.dataset.lfButtonKey}:proxy`,
      ...(icon ? { icon } : { glyph: glyph || "·" }),
      label,
      behavior: control.dataset.lfBehavior || "action",
      tone: control.dataset.lfTone || "neutral",
      role: control.dataset.lfRole || "secondary",
      state: control.dataset.lfState || "idle",
    });
    node.setAttribute("aria-label", control.getAttribute("aria-label") || label);
    node.lfForwardedControl = control;
    node.dataset.lfButtonOwner = control.dataset.lfButtonOwner;
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
    const face = readingFace(choice);
    const count = choice.items.length;
    const label = count > 1 ? `${face.label}s` : face.label;
    marginAction(node, {
      key: `reading:${choice.key}`,
      icon: face.icon,
      label,
      behavior: "disclosure",
      role: "reading",
      state: readingState(choice),
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

  function optionNodes(entry, primary) {
    return [
      ...secondaryControls(entry, primary).map((control) =>
        optionControlNode(control, entry),
      ),
      ...secondaryReadings(entry, primary).map((choice) =>
        readingOptionNode(entry, choice),
      ),
      ...afterOffers(entry).flatMap((offered) =>
        controlsOf(offered)
          .filter((control) => entry.shownControls.has(control))
          .map((control) => ({ control, offered }))
          .sort(compareControlRecords)
          .map(({ control }) => control),
      ),
    ];
  }

  function syncOptionGroup(group, entry, primary, optionsOpen) {
    const allNodes = optionNodes(entry, primary);
    const unique = [...new Set(allNodes)];
    const peerCapacity = Math.max(0, EXPANDED_BUTTON_BUDGET - 1);
    const needsSpill = unique.length > peerCapacity;
    // The spill route consumes the last visible fitting; it does not increase the
    // cluster beyond its budget. A fully expanded cluster is therefore either one
    // primary plus five peers, or one primary plus four peers plus the Page map route.
    const visibleCapacity = needsSpill ? peerCapacity - 1 : peerCapacity;
    const hidden = Math.max(0, unique.length - visibleCapacity);
    const visible = new Set(unique.slice(0, visibleCapacity));
    const after = afterOffers(entry);
    const afterControls = new Set(after.flatMap(controlsOf));
    const wanted = unique.filter(
      (node) => visible.has(node) && !afterControls.has(node),
    );
    // Keep contributor-owned groups intact: their keyboard scopes and event handlers
    // belong to the real controls. Overflow hides individual fittings, not the owner.
    for (const offered of after) {
      const controls = controlsOf(offered);
      for (const control of controls)
        control.toggleAttribute("data-lf-button-overflow", !visible.has(control));
      offered.controls.toggleAttribute(
        "data-lf-button-overflow",
        !controls.some((control) => visible.has(control)),
      );
      wanted.push(offered.controls);
    }
    spilledOptions.set(entry.key, unique.slice(visibleCapacity));
    let spill = spillButtons.get(entry.key);
    if (needsSpill) {
      if (!spill) {
        spill = offer("button", "lf-margin-spill");
        spill.type = "button";
        spillButtons.set(entry.key, spill);
      }
      marginAction(spill, {
        key: "all-options",
        icon: "all",
        label: `Show ${hidden} more in Page map`,
        behavior: "disclosure",
        role: "overflow",
        state: "idle",
      });
      spill.dataset.lfSpillCount = String(hidden);
      spill.setAttribute("aria-label", `Show ${hidden} more in Page map`);
      spill.onclick = () => openSheet(entry, { invoker: spill, focusSpill: true });
      wanted.push(spill);
    } else if (spill) {
      spill.remove();
      spillButtons.delete(entry.key);
    }
    for (const child of [...group.children])
      if (!wanted.includes(child)) child.remove();
    wanted.forEach((child, position) => {
      if (group.children[position] !== child)
        group.insertBefore(child, group.children[position] ?? null);
    });
    group.lfEntry = entry;
    group.setAttribute(
      "aria-label",
      `${entryEngaged(entry) ? "Actions" : "More options"} for ${entry.title}`,
    );
    group.hidden = !optionsOpen || wanted.length === 0;
  }

  function syncControls(host, marker, more, options, entry) {
    const active = document.activeElement;
    const focusedOption = options.contains(active);
    const forwardedControl = active?.lfForwardedControl;
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
    const secondaries = secondaryCount(entry, primary);
    const hasOptions = optionsOffered(entry, primary);
    if (!hasOptions && expandedOptionsKey === entry.key) expandedOptionsKey = null;
    const optionsOpen =
      secondaries > 0 &&
      (!hasOptions || expandedOptionsKey === entry.key || entryEngaged(entry));
    more.hidden = !hasOptions || optionsOpen;
    more.lfEntry = entry;
    more.setAttribute("aria-label", `More options for ${entry.title}`);
    more.setAttribute("aria-expanded", String(optionsOpen));
    host.toggleAttribute("data-lf-options-open", optionsOpen);
    host.dataset.lfState = entryState(entry);
    // Replacing a focused proxy fires focusout synchronously. The render already owns
    // the resulting cluster state and transfers focus below, so do not let that event
    // start a nested render against the same child list.
    const wasSettlingOptionsFocus = settlingOptionsFocus;
    settlingOptionsFocus = true;
    try {
      syncOptionGroup(options, entry, primary, optionsOpen);
    } finally {
      settlingOptionsFocus = wasSettlingOptionsFocus;
    }
    const lostOptionFocus = focusedOption && !options.contains(document.activeElement);
    if (!hasOptions && (document.activeElement === more || lostOptionFocus)) {
      const destination = primary ?? (primaryReading(entry) ? marker : null);
      if (destination === marker && marker.hidden) marker.lfTakeFocus = true;
      else (destination ?? document.body).focus({ preventScroll: true });
    } else if (lostOptionFocus) {
      // A secondary proxy can become the real primary when its press settles. Keep
      // focus on that same semantic control instead of jumping to the first status
      // reading merely because the cluster stayed engaged and replaced its peers.
      const next =
        (forwardedControl?.checkVisibility() ? forwardedControl : null) ??
        primary ??
        clusterButtons(options)[0] ??
        clusterButtons(host)[0];
      (next ?? document.body).focus({ preventScroll: true });
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
          .sort(compareOffers)
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
    measureMargin(main?.getBoundingClientRect())?.();
    syncInlineOffers();
    pageMapEntries = collectEntries().filter((entry) => entry.target);
    // Read contributor visibility once for the whole render, before folding any
    // controls. Placement and option counts share this reading; probing again
    // temporarily unfolds controls and forces style/layout work for every row.
    const shownControls = new Set(
      controlsShownByOwner([
        ...new Set(pageMapEntries.flatMap((entry) => entry.offers.flatMap(controlsOf))),
      ]),
    );
    for (const entry of pageMapEntries) entry.shownControls = shownControls;
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
        spillButtons.delete(key);
        spilledOptions.delete(key);
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
          key: "reading",
          icon: "dot",
          label: "Open page details",
          behavior: "disclosure",
          role: "reading",
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
          () => visibleRows().length > 0 || clusterButtons(host).length > 1,
        );
        host.lfEntry = entry;
        rows.set(entry.key, marker);
        more = marginAction(offer("button", "lf-margin-more"), {
          key: "options",
          icon: "more",
          label: "More options",
          behavior: "options",
          role: "overflow",
        });
        options = el("div", "lf-margin-options");
        options.id = `lf-margin-options-${++optionsOrdinal}`;
        options.hidden = true;
        options.setAttribute("role", "group");
        more.setAttribute("aria-controls", options.id);
        more.onclick = () => {
          const open = expandedOptionsKey !== more.lfEntry.key;
          setOptionsOpen(more.lfEntry, open, {
            focusOption: open ? "first" : null,
          });
        };
        host.addEventListener("focusin", (event) => {
          const control = event.target.closest?.(".lf-margin-action");
          if (
            settlingOptionsFocus ||
            suppressingOptionsArrival ||
            !control ||
            !host.contains(control) ||
            !control.matches(":focus-visible")
          )
            return;
          const current = host.lfEntry;
          const primary = current && choosePrimary(current);
          if (!current || !optionsOffered(current, primary)) return;
          if (entryEngaged(current)) return;
          setOptionsOpen(current, true, {
            focusOption: control === more ? "last" : null,
          });
        });
        host.addEventListener("focusin", () => {
          // A new keyboard destination outranks a pointer parked on the previous
          // target. Real pointer movement can take ownership back without a press.
          hoveredKey = null;
          refreshHighlight();
        });
        host.addEventListener("focusout", () =>
          requestAnimationFrame(refreshHighlight),
        );
        const hover = () => {
          hoveredKey = host.lfEntry?.key ?? null;
          refreshHighlight();
        };
        host.addEventListener("pointerenter", hover);
        host.addEventListener("pointermove", hover);
        host.addEventListener("pointerleave", () => {
          if (hoveredKey === host.lfEntry?.key) hoveredKey = null;
          refreshHighlight();
        });
        host.addEventListener("focusout", (event) => {
          const current = host.lfEntry;
          if (
            settlingOptionsFocus ||
            !current ||
            expandedOptionsKey !== current.key ||
            inRetainedContext(event.relatedTarget) ||
            host.contains(event.relatedTarget)
          )
            return;
          setOptionsOpen(current, false);
        });
        // A direct primary belongs to its owner rather than the generated proxy path.
        // Fold only a temporary expansion before that action; an engaged owner keeps
        // its completion actions exposed until its own state actually ends.
        host.addEventListener(
          "click",
          (event) => {
            if (!expandedOptionsKey || entryEngaged(host.lfEntry)) return;
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
        closePreview(preview.contains(document.activeElement));
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
          for (const row of rows.values())
            syncThreadRelation(row, markerNeedsPreview(row.lfEntry));
          for (const reading of readingButtons.values())
            syncThreadRelation(reading, reading.lfChoice?.kind === "comment");
        }
      }
    }
    refreshHighlight();
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

  function refreshHighlight() {
    const active = focused();
    const focusedHost = closestAcross(active, "[data-lf-margin-for]");
    const key =
      hoveredKey ??
      focusedHost?.lfEntry?.key ??
      (preview.contains(active) || preview.matches(":popover-open")
        ? previewEntry?.key
        : null);
    highlight(pageMapEntries.find((entry) => entry.key === key)?.target ?? null);
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
    refreshHighlight();
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
    const reply = previewList.querySelector("textarea");
    if (reply) landInConversation(reply);
  }

  function closePreview(returnFocus) {
    const button = previewButton;
    pinnedKey = null;
    forcedInlineKey = null;
    previewEntry = null;
    previewButton = null;
    button?.style.removeProperty("anchor-name");
    if (preview.matches(":popover-open")) preview.hidePopover();
    refreshHighlight();
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
    const choice = threadReading(entry);
    if (!choice) return;
    if (panelIsOpen()) {
      activate(choice.items[0], entry, { focusMap: false });
      return;
    }
    if (expandedOptionsKey && expandedOptionsKey !== entry.key)
      setOptionsOpen(entry, false);
    if (!threadBeside()) {
      setOptionsOpen(entry, false);
      openThreads(choice.items, entry);
      return;
    }
    togglePinned(entry, button);
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
    if (!entry || designIsOn() || panelIsOpen()) return null;
    const choice = threadReading(entry);
    if (!choice) return null;
    let button = threadButton(entry);
    if (!button?.checkVisibility()) {
      setOptionsOpen(entry, true);
      button = threadButton(entry);
    }
    if (!button) return null;
    pinnedKey = entry.key;
    forcedInlineKey = entry.key;
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
    const focusedButton = sheet.contains(document.activeElement)
      ? document.activeElement.dataset.lfMapButton
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
            iconElement(KINDS[item.kind].icon, "lf-margin-kind"),
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
        for (const option of spilledOptions.get(entry.key) ?? []) {
          const button = el("button", "lf-page-map-action");
          button.type = "button";
          const icon = option.querySelector(":scope > .lf-margin-action-icon")?.dataset
            .lfIcon;
          const glyph = option.querySelector(
            ":scope > .lf-margin-action-glyph",
          )?.textContent;
          const label =
            option.getAttribute("aria-label") ||
            option.querySelector(":scope > .lf-margin-action-label")?.textContent ||
            "Page action";
          button.append(
            icon
              ? iconElement(icon, "lf-margin-kind")
              : el("span", "lf-margin-kind", glyph || "·"),
            el("span", "", label),
          );
          button.setAttribute("aria-label", label);
          button.disabled =
            option.disabled || option.getAttribute("aria-disabled") === "true";
          button.dataset.lfMapButton = `${entry.key}:${option.dataset.lfButtonOwner ?? "reading"}:${option.dataset.lfButtonKey}`;
          button.onclick = () => {
            const from = sheetFrom;
            sheetActivation = true;
            sheet.close();
            requestAnimationFrame(() => {
              // Spilled Buttons have no on-page box to own a floating thread card.
              // The Page map already supplies the named route into the conversation.
              if (option.lfChoice?.kind === "comment")
                openThreads(option.lfChoice.items, entry);
              else {
                // Keep the source interaction alive until its own action consumes it.
                // Moving to the map marker first would discard temporary responses and
                // their anchor before this proxy could press the original Button.
                if (from?.isConnected && from.checkVisibility())
                  from.focus({ preventScroll: true });
                option.click();
              }
            });
          };
          actions.append(button);
        }
        group.append(actions);
        return group;
      }),
    );
    sheetList.scrollTop = heldScroll;
    if (focusedItem || focusedButton) {
      const replacement = [
        ...sheetList.querySelectorAll("[data-lf-map-item], [data-lf-map-button]"),
      ].find(
        (candidate) =>
          (focusedItem && candidate.dataset.lfMapItem === focusedItem) ||
          (focusedButton && candidate.dataset.lfMapButton === focusedButton),
      );
      (replacement ?? sheetClose).focus({ preventScroll: true });
    }
  }

  function openSheet(entry = null, { invoker = mapButton, focusSpill = false } = {}) {
    sheetTarget = entry?.target ?? null;
    // The command's door owns the return route, not incidental keyboard focus. Page
    // addresses and the map chord use the Map toggle; overflow names its exact Button.
    if (!sheet.open) sheetFrom = invoker;
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
    const destination = focusSpill
      ? group?.querySelector("[data-lf-map-button]")
      : group?.querySelector(".lf-page-map-action");
    (destination ?? sheetClose).focus({ preventScroll: true });
    paintKeys();
  }
  mapButton.onclick = () => openSheet();
  sheet.addEventListener("close", () => {
    const from = sheetFrom;
    sheetFrom = null;
    sheetTarget = null;
    paintKeys();
    if (sheetActivation) {
      sheetActivation = false;
      return;
    }
    if (from?.isConnected && from.checkVisibility())
      from.focus({ preventScroll: true });
    else focusMapControl();
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
    refreshHighlight();
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
  // The margin packs its rows a frame after anything moves them — a row registering,
  // the column resizing under a diagram that finished or a disclosure that opened — and
  // the card beside a marker was placed once, when it opened. margin-layout.js says when
  // it has moved the rows, and the card follows in that same frame, so a reader never
  // sees it standing beside where its marker used to be.
  document.addEventListener("lf-margin-layout", placeThreadPreview);
  document.addEventListener(
    "pointerdown",
    (event) => {
      if (!expandedOptionsKey) return;
      const host = hosts.get(expandedOptionsKey);
      if (
        !host ||
        event.composedPath().includes(host) ||
        event.composedPath().some(inRetainedContext)
      )
        return;
      setOptionsOpen(host.lfEntry, false);
    },
    { capture: true },
  );
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
    buttonChoices: (target) => clusterButtons(buttonHost(target)),
    buttonContextContains,
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
    leavePageMap,
    focusForNavigation,
    keyboardRung,
    marginTargetAt,
    openButtonOptions,
    openInlineThread,
    openPageMapItem,
    pageMapItems,
    pageMapIsActive,
    render,
  };
}
