/* The page-side projection of activity attached to exact document targets.

   This module combines registered contributions with core readings such as Threads,
   Asks, version changes, delivery receipts, and work claims. It reconciles one cluster
   and the inline thread card per target, then supplies the complete target projection to
   `page-map-dialog.js`. `margin-entries.js` owns the public control grammar and contribution
   registry; `margin-layout.js` owns row measurement, rail claims, responsive docking,
   packing, and collision bands.

   A resting cluster has two seats: its primary and one peer, or its primary and More
   when at least two peers remain. An expanded cluster has six seats, with the final seat
   opening Page Map at the first omitted action. That limit also applies when the cluster
   docks. Page Map retains the complete inventory.

   An engaged contribution exposes its completion and escape controls first and never
   hides them behind More. Engagement is semantic state, not DOM focus, so an editor stays
   expanded when focus moves within its work. Explicit owner focus temporarily derives
   the cluster from that contribution alone; closing it restores the ordinary cluster.

   Controls are ordered by lifecycle state, rank, contribution key, and
   control key. Generated readings follow contributed controls. One target's Threads
   share one reading and one card. Page Map also includes readings that deliberately
   have no target control, such as durable state provenance.

   Keyboard and pointer expansion share one state. Focus arrival through Tab unfolds a
   compact cluster, Left and Right walk it, and Escape folds only the layer that gesture
   opened. Page-map and generated-address arrivals activate the exact visible control;
   they do not choose another action for the reader.

   The thread card stays attached to its owning cluster, chooses a readable side margin
   before overlaying the document, and closes after that cluster leaves the visible
   region. It contains the complete inline conversation view; the Threads panel remains
   the complete index and takes over when already open.

   Cluster reconciliation preserves each surviving control, proxy, and count badge so a
   state refresh cannot cancel a held pointer or move focus. A print-media render is
   deferred until screen media returns because print removes the injected controls and
   cannot supply their geometry.

   One constructed owner holds margin layout, retained controls, and preview state.
   Boot supplies version, map, travel, and semantic thread-render capabilities.
   mount reserves the rail and binds the lifecycle after those owners exist; every
   later render reads the same bound capabilities, including event-driven repaints. */
import {
  registerMarginRow,
  reserveRail,
  scheduleMarginEntryLabels,
  scheduleMarginLayout,
  unregisterMarginRow,
  updateMarginRow,
} from "./margin-layout.js";
import {
  compareMarginContributions,
  compareMarginEntryRecords,
  marginContributionEntries,
  marginContributionState,
  marginEntry,
  marginEntryRecord,
  marginEntries,
  marginEntryStateRank,
  syncForwardedMarginEntryState,
  syncMarginEntryCount,
  watchMarginContributions,
} from "./margin-entries.js";
import { mapButton } from "./page-map-dialog.js";
import { documentPoint, shownBox, shownParts } from "./geometry.js";
import { focusDestination } from "./focus.js";
import { el, keeps, keepsHidden, offer } from "./widget-elements.js";
import { clampedRow, PRESS } from "./keyboard/bindings.js";
import { beginWalk, listWalkPosition } from "./walk-position.js";
import { ago, clocked } from "./presence.js";
import { runtime } from "./context.js";
import { readingRegionFor, shownRegionBounds } from "./reading-regions.js";
import { panelWouldCover } from "./conversation/panel-elements.js";
import { COVERING } from "./chrome-layout.js";

import { focused, keys, paintKeys } from "./keyboard/scopes.js";
import { repaint } from "./repaint.js";
import { chromeRoot } from "./chrome.js";
import { versionBtn } from "./version.js";
import { foldShelf } from "./banner-shelf.js";
import { motion, scrollBehavior } from "./motion.js";
import { panel } from "./conversation/panel-elements.js";
import { blockAt, closestAcross, elementById, inChrome, says } from "./passages.js";
import { itemSays, itemWord, visualAt } from "./anchor-resolution.js";
import { paintTrace } from "./target-paint.js";
import { updateSequence, workClaimState } from "./updates.js";
import { threadList } from "./conversation/state.js";
import { threadKey } from "./conversation/model.js";

import { projectionOrigins } from "./projection/model.js";
import { authoredStates } from "./projection/authored.js";
import { currentProjection } from "./projection/state.js";
import { notice } from "./notifications.js";
import { iconElement } from "./icons.js";
import { claimed, focusSurface } from "./conversation/surfaces.js";
import { anchorLabel } from "./conversation/messages.js";

import { outlineSubjectFor, pageOutline } from "./conversation/placement.js";

export function createMarginProjection({
  panelIsOpen,
  openAsks,
  designIsOn,
  comparisonBase,
  comparisonChanges,
  inlineComparison,
  toggleInlineComparison,
  leavePageMap,
  openPageMap,
  pageMapDialogContains,
  renderPageMapDialog,
  standsWith,
  revealConversation,
  renderMarginThread,
  bottomChromeBoxes,
  placedAt,
  showThread,
  goToAsk,
  scrollToElement,
  scrollToThread,
  landInConversation,
}) {
  const KINDS = {
    action: { label: "Action", icon: "dot", priority: -1 },
    change: { label: "Change", icon: "change", priority: 0 },
    restated: {
      label: "Rewritten",
      icon: "change",
      priority: 0,
      indication: true,
    },
    comment: { label: "Thread", icon: "comment", priority: 1 },
    ask: { label: "Ask", icon: "question", priority: 2 },
    sent: {
      label: "Sent",
      icon: "sent",
      priority: 3,
      indication: true,
      state: "busy",
    },
    pickup: {
      label: "Picked up",
      icon: "pickup",
      priority: 3,
      indication: true,
      state: "idle",
    },
    waiting: {
      label: "Waiting for pickup",
      icon: "waiting",
      priority: 3,
      indication: true,
      state: "busy",
    },
    reader: {
      label: "Your change",
      icon: "change",
      priority: 4,
      indication: true,
    },
    reported: {
      label: "Reported update",
      icon: "activity",
      priority: 4,
      indication: true,
    },
    activity: { label: "Active", icon: "activity", priority: 4, state: "busy" },
  };
  const RESTING_MARGIN_ENTRY_BUDGET = 2;
  const EXPANDED_MARGIN_ENTRY_BUDGET = 6;

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

  const acknowledgments = () => runtime.activity?.interactions ?? [];
  const renderMargin = clocked(document.body, renderNow);
  // The margin entry the reader is standing on, or null off one: the press row's words read it.
  const focusedMarginEntryBehavior = () => {
    const control = focused();
    return control?.matches?.(".lf-margin-entry")
      ? marginEntryRecord(control).behavior
      : null;
  };

  const nav = el("nav", "lf-ui lf-margin-projection");
  // Every live page can gain an anchored comment, including one made entirely of prose.

  nav.dataset.lfGen = "1";
  nav.setAttribute("aria-label", "Page Map");
  const toolbar = el("div", "lf-margin-toolbar");
  toolbar.setAttribute("role", "toolbar");
  toolbar.setAttribute(
    "aria-label",
    "Changes, threads, asks, delivery status, and activity",
  );
  nav.append(toolbar);

  function measureMargin(
    columnRect = document.querySelector("main")?.getBoundingClientRect(),
  ) {
    const main = document.querySelector("main");
    if (!main || !columnRect) return;
    const at = documentPoint(columnRect.left, columnRect.top);
    const height = main.scrollHeight;
    return () => {
      const dimensions = {
        left: `${at.left}px`,
        top: `${at.top}px`,
        width: `${columnRect.width}px`,
        height: `${height}px`,
      };
      for (const [property, value] of Object.entries(dimensions))
        if (nav.style[property] !== value) nav.style[property] = value;
    };
  }

  function changePosture() {
    const marginHeld =
      toolbar.contains(document.activeElement) ||
      preview.contains(document.activeElement);
    if (panelWouldCover() && preview.matches(":popover-open")) closePreview();
    if (panelWouldCover() && marginHeld) requestAnimationFrame(() => focusMapControl());
    renderMargin.refresh();
  }
  const preview = el("aside", "lf-ui lf-margin-preview");
  preview.id = "lf-margin-preview";
  preview.setAttribute("popover", "auto");
  preview.setAttribute("role", "dialog");
  const previewHead = el("div", "lf-margin-preview-head");
  const previewTitle = el("strong", "lf-margin-preview-title");
  const previewClose = el(
    "button",
    "lf-btn lf-icon-action lf-close-action lf-margin-preview-close",
  );
  previewClose.append(iconElement("cross", "lf-action-icon"));
  previewClose.type = "button";
  previewClose.setAttribute("aria-label", "Close thread");
  previewClose.title = "Close thread (Esc)";
  previewHead.append(previewTitle, previewClose);
  const previewList = el("div", "lf-margin-preview-list");
  preview.append(previewHead, previewList);
  let threadTransitionEpoch = 0;
  let threadTransitionMotions = [];

  // The submitted composer and a developer replay describe the same starting box; the
  // transition owns that geometry contract instead of making either caller duplicate it.
  function threadTransitionOrigin(element, text) {
    const box = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return {
      left: box.left,
      top: box.top,
      width: box.width,
      height: box.height,
      backgroundColor: style.backgroundColor,
      borderColor: style.borderColor,
      borderRadius: style.borderRadius,
      boxShadow: style.boxShadow,
      text,
    };
  }

  function clearThreadTransition() {
    threadTransitionEpoch += 1;
    for (const played of threadTransitionMotions) played.cancel();
    threadTransitionMotions = [];
    chromeRoot.querySelector(".lf-thread-transition")?.remove();
    preview.style.removeProperty("opacity");
  }

  // A comment written beside the page becomes this larger inline thread. Carry its
  // submitted field to the card rather than replacing one rectangle with another in a
  // frame; the real card fades through the carried shell, so its contents never stretch.
  function transitionThread(origin) {
    if (!origin?.width || !origin?.height) return;
    const target = preview.getBoundingClientRect();
    if (!target.width || !target.height) return;

    const ghost = el("div", "lf-ui lf-response-control lf-thread-transition");
    const ghostText = el("span", "lf-thread-transition-text", origin.text);
    ghost.append(ghostText);
    ghost.setAttribute("aria-hidden", "true");
    Object.assign(ghost.style, {
      left: `${origin.left}px`,
      top: `${origin.top}px`,
      width: `${origin.width}px`,
      height: `${origin.height}px`,
      backgroundColor: origin.backgroundColor,
      borderColor: origin.borderColor,
      borderRadius: origin.borderRadius,
      boxShadow: origin.boxShadow,
    });
    chromeRoot.append(ghost);

    const end = getComputedStyle(preview);
    const duration = 280;
    const carried = motion(
      ghost,
      [
        { opacity: 1 },
        { opacity: 1, offset: 0.42 },
        {
          left: `${target.left}px`,
          top: `${target.top}px`,
          width: `${target.width}px`,
          height: `${target.height}px`,
          borderRadius: end.borderRadius,
          backgroundColor: end.backgroundColor,
          borderColor: end.borderColor,
          boxShadow: end.boxShadow,
          opacity: 0,
        },
      ],
      duration,
    );
    const revealed = motion(
      preview,
      [
        { opacity: 0, transform: "translateY(2px)" },
        {
          opacity: 0,
          transform: "translateY(2px)",
          offset: 0.42,
        },
        { opacity: 1, transform: "none" },
      ],
      duration,
    );
    const words = motion(
      ghostText,
      [{ opacity: 1 }, { opacity: 0, offset: 0.42 }, { opacity: 0 }],
      duration,
    );
    threadTransitionMotions = [carried, revealed, words].filter(Boolean);
    if (carried)
      carried.finished.then(
        () => ghost.remove(),
        () => ghost.remove(),
      );
    else ghost.remove();
    // `motion` releases its filled frame after this reaction. The card's ordinary
    // styles already are the final frame, so no separate cleanup can flash it back.
    revealed?.finished.catch(() => {});
  }

  function scheduleThreadTransition(origin, entry) {
    clearThreadTransition();
    const epoch = threadTransitionEpoch;
    // Margin packing finishes on the next frame. Keep the real card transparent until
    // then, so the carried shell aims at the marker's settled position without flashing
    // the card at its provisional one.
    preview.style.opacity = "0";
    requestAnimationFrame(() => {
      if (epoch !== threadTransitionEpoch) return;
      preview.style.removeProperty("opacity");
      if (previewEntry?.key !== entry.key || !preview.matches(":popover-open")) return;
      placeThreadPreview();
      transitionThread(origin);
    });
  }

  const rows = new Map();
  const moreMarginEntries = new Map();
  const spillMarginEntries = new Map();
  const optionGroups = new Map();
  const controlProxies = new WeakMap();
  const readingMarginEntries = new Map();
  const hosts = new Map();
  const inlineHosts = new Map();
  let optionsOrdinal = 0;
  let pageInventory = [];
  let previewEntry = null;
  let previewMarginEntry = null;
  let transferThreadFocus = false;
  let previewShowing = false;
  let pinnedKey = null;
  let forcedInlineKey = null;
  let forcedInlineOptionsKey = null;
  let expandedOptionsKey = null;
  // An explicit mode can focus one contribution inside the target's existing cluster.
  // The rail then shows that owner's complete control set without spending margin entries on
  // standing readings or unrelated actions; Page Map still reads the whole entry.
  let expandedOptionsOwner = null;
  let hoveredHost = null;
  let settlingOptionsFocus = false;
  let suppressingOptionsArrival = false;
  let highlighted = null;
  let rovingFrame = 0;
  const controlsOf = (offered) => marginEntries(offered.controls);
  const offerReadings = (offered) => {
    const items = typeof offered.items === "function" ? offered.items() : offered.items;
    return items ?? [];
  };
  // One target has one lifecycle reading. Failure outranks work in flight, which
  // outranks an open interaction; the ordinary idle state never forces peers open.
  // Generated acknowledgment readings join through the same state axis rather than a
  // second engagement flag.
  const entryState = (entry) => {
    const states = [
      ...entry.offers.map(marginContributionState),
      ...entry.items.map(
        (item) => item.state ?? (item.acknowledgmentFace ? "busy" : "idle"),
      ),
    ];
    return (
      states.sort(
        (left, right) => marginEntryStateRank(left) - marginEntryStateRank(right),
      )[0] ?? "idle"
    );
  };
  // Every state but idle keeps the cluster open, so the reading is the absence of idle
  // rather than a second list of states beside the grammar's.
  const entryEngaged = (entry) => entryState(entry) !== "idle";
  // A modal or contextual thread surface temporarily owns focus without ending the
  // document interaction beneath it. Preserve that context so its commands remain
  // true and its owning margin entry can receive focus when the surface closes.
  const inRetainedContext = (node) =>
    node instanceof Element &&
    (Boolean(node.closest("dialog[open]")) ||
      preview.contains(node) ||
      (panelIsOpen() && panel.contains(node)));
  const standingAfterOffers = (entry) =>
    entry.offers
      .filter(
        (offered) => offered.side === "after" && offerReadings(offered).length > 0,
      )
      .sort(compareMarginContributions);
  const directOffers = (entry) => [
    ...entry.offers
      .filter((offered) => offered.side === "before")
      .sort(compareMarginContributions),
    ...standingAfterOffers(entry),
  ];
  const directControlRecords = (entry) =>
    directOffers(entry)
      .flatMap((offered) =>
        controlsOf(offered).map((control) => ({ control, offered })),
      )
      .sort(compareMarginEntryRecords);
  const directControls = (entry) =>
    directControlRecords(entry).map(({ control }) => control);
  const controlsShownByOwner = (controls) => {
    // The margin hides non-primary controls with `display: none`, so ask how this
    // batch paints while exempt from that rule. Write every exemption before the first
    // style read: alternating an attribute write and getComputedStyle would recalculate
    // the whole page once per margin entry. Contributor-owned `display` and `visibility`
    // still apply — including the retired half of a settled pair.
    const wasPrimary = controls.map((control) =>
      control.hasAttribute("data-lf-margin-entry-primary"),
    );
    const wasOverflow = controls.map((control) =>
      control.hasAttribute("data-lf-margin-entry-overflow"),
    );
    for (const control of controls) {
      control.toggleAttribute("data-lf-margin-entry-primary", true);
      control.removeAttribute("data-lf-margin-entry-overflow");
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
        control.toggleAttribute("data-lf-margin-entry-primary", wasPrimary[index]);
        control.toggleAttribute("data-lf-margin-entry-overflow", wasOverflow[index]);
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
      control.toggleAttribute("data-lf-margin-entry-primary", control === primary);
    return primary;
  }
  const markerItems = (entry) => entry.items.filter((item) => item.marker !== false);
  const entryHasMarginHost = (entry) =>
    entry.offers.length > 0 || markerItems(entry).length > 0;
  const readingKey = (entry, choice) => `${entry.key}:${choice.key}`;
  const readingChoices = (entry) => {
    const threadList = [];
    const choices = [];
    for (const item of markerItems(entry)) {
      if (item.kind === "comment") threadList.push(item);
      else
        choices.push({
          key: item.id,
          kind: item.kind,
          items: [item],
          text: item.text,
        });
    }
    if (threadList.length)
      choices.push({
        // One target owns one thread margin entry. Membership changes repaint its badge and
        // card without replacing the control that owns an open conversation.
        key: "threadList",
        kind: "comment",
        items: threadList,
        text: threadList[0].text,
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

  function threadMarginEntry(entry) {
    const marker = rows.get(entry.key);
    if (marker && !marker.hidden && primaryReading(entry)?.kind === "comment")
      return marker;
    const choice = threadReading(entry);
    return choice
      ? (readingMarginEntries.get(readingKey(entry, choice)) ?? null)
      : null;
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
      .sort(compareMarginContributions);
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
  // margin entry onward.
  const optionsOffered = (entry, primary, options = {}) =>
    secondaryCount(entry, primary, options) > RESTING_MARGIN_ENTRY_BUDGET - 1;

  function markerFace(entry) {
    const kinds = kindsIn(entry, { markerOnly: true });
    const choice = primaryReading(entry);
    const face = readingFace(choice);
    const faceCount = choice?.items.length ?? 0;
    return {
      kinds,
      face,
      label: faceCount > 1 ? `${face.label}s` : face.label,
      // The badge describes this margin entry's result. Other readings live behind `…`
      // and must not make a thread margin entry appear to open more threadList than it does.
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
        .map((item) => item.state ?? item.acknowledgmentFace?.state ?? "idle")
        .sort(
          (left, right) => marginEntryStateRank(left) - marginEntryStateRank(right),
        )[0] ?? "idle"
    );
  }

  const readingBehavior = (face) => (face.indication ? "status" : "disclosure");

  function readingContext(choice) {
    if (choice?.items.length !== 1) return null;
    return choice.items[0].context ?? null;
  }

  // A reading wears two promises over its life — a margin entry while there is something to
  // open, a status once the move is made — and only one element may carry both, or the
  // seat moves under a reader standing in it. A <button> cannot stop being one, so the
  // seat is a span and `marginEntry` writes whichever promise the reading now makes.
  // What the platform then does not supply is the press, which the margin's own scope
  // declares (margin.press) rather than a listener here: a key the register does not
  // hold is a key no surface can promise.
  const readingControl = (className) => offer("span", className);

  // The one writer over a reading's disclosure relation, settling `aria-controls` and
  // `aria-expanded` together because a control that says it opens something has to say
  // whether it is open. Two shapes reach it. A thread margin entry opens the local card while the
  // panel is closed and the matching panel card while it is open. Any other reading is
  // asked what it discloses, and a single item
  // that answers has named the node and said which way it stands — the Change reading's
  // inline text diff. An item answering nothing promises nothing, which is what leaves a
  // Change margin entry over a block the comparison cannot align for the plain travel it
  // always was.
  function syncReadingRelation(control, choice) {
    if (choice?.kind === "comment") {
      const opensInline = !panelIsOpen();
      keeps(control, "aria-controls", opensInline ? preview.id : panel.id);
      if (opensInline) keeps(control, "aria-expanded", previewMarginEntry === control);
      else control.removeAttribute("aria-expanded");
      return;
    }
    const disclosed = choice?.items.length === 1 ? choice.items[0].discloses?.() : null;
    if (!disclosed) {
      control.removeAttribute("aria-controls");
      control.removeAttribute("aria-expanded");
      return;
    }
    keeps(control, "aria-controls", disclosed.id);
    keeps(control, "aria-expanded", disclosed.open);
  }
  let postureFrame = 0;
  let previewPositionFrame = 0;
  let previewPositionRemeasure = false;
  let previewPositionDismissDetached = false;
  let previewPlacementMetrics = null;
  let previewReferenceSeen = false;
  function schedulePostureRender() {
    if (postureFrame) return;
    postureFrame = requestAnimationFrame(() => {
      postureFrame = 0;
      renderMargin.refresh();
    });
  }
  const clamp = (value, minimum, maximum) =>
    Math.max(minimum, Math.min(value, maximum));
  const overlaps = (one, other, gap = 0) =>
    one.left < other.right + gap &&
    other.left < one.right + gap &&
    one.top < other.bottom + gap &&
    other.top < one.bottom + gap;

  function keepThreadPreviewFocusVisible() {
    const active = document.activeElement;
    if (!(active instanceof HTMLElement) || !preview.contains(active)) return;
    const card = preview.getBoundingClientRect();
    const activeBox = active.getBoundingClientRect();
    const inset = 12;
    if (activeBox.bottom > card.bottom - inset)
      preview.scrollTop += activeBox.bottom - card.bottom + inset;
    else if (activeBox.top < card.top + inset)
      preview.scrollTop -= card.top + inset - activeBox.top;
  }

  function threadSidePlacement(left, width, height, target, firstTop, lastBottom) {
    const gap = 8;
    const totalHeight = lastBottom - firstTop;
    const cardHeight = Math.min(height, totalHeight);
    const lastTop = lastBottom - cardHeight;
    const desired = clamp(
      (target.top + target.bottom - cardHeight) / 2,
      firstTop,
      lastTop,
    );
    const candidate = {
      left,
      right: left + width,
      top: desired,
      bottom: desired + cardHeight,
    };
    if (!overlaps(candidate, target, gap))
      return { top: desired, maxHeight: totalHeight };

    const belowTop = Math.max(firstTop, Math.min(target.bottom + gap, lastBottom));
    const aboveBottom = Math.max(firstTop, Math.min(target.top - gap, lastBottom));
    const belowRoom = Math.max(0, lastBottom - belowTop);
    const aboveRoom = Math.max(0, aboveBottom - firstTop);
    const below = height <= belowRoom || (height > aboveRoom && belowRoom >= aboveRoom);
    const room = below ? belowRoom : aboveRoom;
    if (!room) return null;
    const placedHeight = Math.min(height, room);
    return {
      top: below ? belowTop : aboveBottom - placedHeight,
      maxHeight: room,
    };
  }

  function placeThreadPreview({ remeasure = true, dismissDetached = false } = {}) {
    if (
      !preview.matches(":popover-open") ||
      !preview.hasAttribute("data-lf-thread") ||
      !previewMarginEntry?.isConnected
    )
      return;
    const controls =
      previewMarginEntry.closest("[data-lf-margin-for]") ?? previewMarginEntry;
    const target = controls.getBoundingClientRect();
    const readingRegion = readingRegionFor(previewEntry?.target);
    const regionBounds = readingRegion && shownRegionBounds(readingRegion);
    const main = readingRegion
      ? null
      : document.querySelector("main")?.getBoundingClientRect();
    const bannerBottom =
      document.querySelector(".lf-banner")?.getBoundingClientRect().bottom ?? 0;
    const gap = 8;
    const firstLeft = regionBounds?.left ?? 0;
    const lastRight = regionBounds?.right ?? document.documentElement.clientWidth;
    const firstTop = Math.max(regionBounds?.top ?? 0, bannerBottom) + gap;
    const lastBottom = (regionBounds?.bottom ?? innerHeight) - gap;
    const totalHeight = Math.max(0, lastBottom - firstTop);
    const lastBottomFor = (left, right) =>
      bottomChromeBoxes()
        .filter((box) => left < box.right && box.left < right)
        .reduce((bottom, box) => Math.min(bottom, box.top - gap), lastBottom);
    const referenceVisible = target.bottom > firstTop && target.top < lastBottom;
    if (referenceVisible) {
      previewReferenceSeen = true;
    } else if (previewReferenceSeen && dismissDetached) {
      closePreview();
      return;
    }
    if (remeasure || !previewPlacementMetrics) {
      const style = getComputedStyle(preview);
      previewPlacementMetrics = {
        preferredWidth: Math.min(
          parseFloat(style.getPropertyValue("--thread-card")),
          lastRight - firstLeft - 2 * gap,
        ),
        minimumWidth: parseFloat(style.getPropertyValue("--thread-card-min")),
        borderHeight:
          parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth),
        heights: new Map(),
      };
    }
    const metrics = previewPlacementMetrics;
    const naturalHeight = (width, availableHeight = totalHeight) => {
      const key = `${width.toFixed(2)}:${availableHeight.toFixed(2)}`;
      if (!metrics.heights.has(key)) {
        preview.style.setProperty("--lf-thread-width", `${width}px`);
        preview.style.setProperty("--lf-thread-max-height", `${availableHeight}px`);
        metrics.heights.set(key, preview.scrollHeight + metrics.borderHeight);
      }
      return metrics.heights.get(key);
    };
    const sideCandidates = main
      ? [
          {
            name: "right",
            width: Math.min(metrics.preferredWidth, lastRight - main.right - 2 * gap),
            get left() {
              return lastRight - gap - this.width;
            },
          },
          {
            name: "left",
            left: gap,
            width: Math.min(metrics.preferredWidth, main.left - 2 * gap),
          },
        ]
      : [];
    for (const side of sideCandidates) {
      if (side.width < metrics.minimumWidth) continue;
      const sideTop = firstTop;
      const sideBottom = lastBottomFor(side.left, side.left + side.width);
      const sideHeight = Math.max(0, sideBottom - sideTop);
      const height = naturalHeight(side.width, sideHeight);
      const placement = threadSidePlacement(
        side.left,
        side.width,
        height,
        target,
        sideTop,
        sideBottom,
      );
      if (!placement) continue;
      preview.dataset.lfThreadPlacement = side.name;
      preview.style.setProperty("--lf-thread-width", `${side.width}px`);
      preview.style.setProperty("--lf-thread-max-height", `${placement.maxHeight}px`);
      preview.style.setProperty("--lf-thread-left", `${side.left}px`);
      preview.style.setProperty("--lf-thread-top", `${placement.top}px`);
      if (remeasure) keepThreadPreviewFocusVisible();
      return;
    }

    // Both margins are unavailable. Preserve the full reading measure over the document,
    // preferring the room below the selected cluster, then above, then the larger side as
    // a scrolling viewport. The cluster itself is never part of the area the card spends.
    const width = metrics.preferredWidth;
    const lastLeft = lastRight - width - gap;
    const left = clamp(target.right - width, firstLeft + gap, lastLeft);
    const overlayTop = firstTop;
    const overlayBottom = lastBottomFor(left, left + width);
    const overlayHeight = naturalHeight(width, Math.max(0, overlayBottom - overlayTop));
    const belowTop = Math.max(overlayTop, Math.min(target.bottom + gap, overlayBottom));
    const aboveBottom = Math.max(overlayTop, Math.min(target.top - gap, overlayBottom));
    const belowRoom = Math.max(0, overlayBottom - belowTop);
    const aboveRoom = Math.max(0, aboveBottom - overlayTop);
    const below =
      overlayHeight <= belowRoom ||
      (overlayHeight > aboveRoom && belowRoom >= aboveRoom);
    const room = below ? belowRoom : aboveRoom;
    const cardHeight = Math.min(overlayHeight, room);
    const top = below ? belowTop : aboveBottom - cardHeight;
    preview.dataset.lfThreadPlacement = below ? "below" : "above";
    preview.style.setProperty("--lf-thread-width", `${width}px`);
    preview.style.setProperty("--lf-thread-max-height", `${room}px`);
    preview.style.setProperty("--lf-thread-left", `${left}px`);
    preview.style.setProperty("--lf-thread-top", `${top}px`);
    if (remeasure) keepThreadPreviewFocusVisible();
  }
  function scheduleThreadPreviewPosition(remeasure = false, dismissDetached = false) {
    if (remeasure) {
      previewPositionRemeasure = true;
      previewPositionDismissDetached = false;
    } else previewPositionDismissDetached ||= dismissDetached;
    if (previewPositionFrame) return;
    previewPositionFrame = requestAnimationFrame(() => {
      previewPositionFrame = 0;
      const measure = previewPositionRemeasure;
      const dismiss = previewPositionDismissDetached;
      previewPositionRemeasure = false;
      previewPositionDismissDetached = false;
      placeThreadPreview({ remeasure: measure, dismissDetached: dismiss });
    });
  }
  // A viewport posture change can replace the focused full conversation with its
  // compact action. Reconcile after resize delivery so the browser can finish its
  // own focus and popover bookkeeping before that node changes shape. Panel and tray
  // changes notify this runtime directly through their owners.

  // A margin cluster is hoisted away from the page target it belongs to, so ancestry
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
      const word = itemWord(target);
      group = {
        key,
        target,
        word,
        subject: null,
        title: null,
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
    return acknowledgments().filter(
      (projected) => projected.revision <= runtime.currentRevision,
    );
  }

  function acknowledgmentFace(receipt) {
    const age = ago(receipt.ts);
    if (receipt.phase === "active") {
      return {
        kind: "activity",
        text: ["Active", receipt.detail, receipt.quiet ? "quiet" : null]
          .filter(Boolean)
          .join(" · "),
        context: [age && `Checked in ${age}`, receipt.detail]
          .filter(Boolean)
          .join(" · "),
      };
    }
    if (receipt.phase === "queued")
      return { kind: "pickup", text: "Queued", context: age };
    if (receipt.phase === "picked_up")
      return {
        kind: receipt.dropped ? "waiting" : "pickup",
        text: receipt.dropped ? "Picked up · turn ended" : "Picked up",
        context: age,
      };
    if (receipt.phase === "waiting")
      return {
        kind: "waiting",
        text: "Waiting for pickup",
        context: age && `Sent ${age}`,
      };
    return { kind: "sent", text: "Sent", context: age };
  }

  const marginThreadItem = (thread) => (thread ? `comment:${threadKey(thread)}` : null);

  function collectEntries() {
    const groups = new Map();
    const receiptByCoordinate = new Map();
    for (const receipt of visibleAcknowledgments()) {
      receiptByCoordinate.set(JSON.stringify(receipt.coordinate), receipt);
    }
    for (const thread of threadList()) {
      if (thread.resolved || !thread.anchor || claimed(thread.root.id)) continue;
      const id = thread.root.id;
      add(groups, placedAt(id)?.element, {
        kind: "comment",
        // One row for one conversation, across the log answering for it. A thread the
        // reader just opened is known by its attempt until the log names it, and a row
        // whose identity changed there would be rebuilt — taking with it the reply box
        // the send had just put them in.
        id: marginThreadItem(thread),
        text: trimmed(
          thread.root.text || anchorLabel(thread.anchor, thread.root.about),
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

    const projection = currentProjection();
    for (const origin of projectionOrigins(authoredStates, projection)) {
      const target = elementById(origin.unit);
      if (!target) continue;
      const face = KINDS[origin.origin];
      add(groups, target, {
        kind: origin.origin,
        id: `state-origin:${origin.origin}:${origin.unit}`,
        // Durable provenance belongs in Page Map rather than another target margin entry:
        // it remains explicit without changing the page's action density or geometry.
        marker: false,
        text: trimmed(
          [face.label, itemWord(target), itemSays(target)].filter(Boolean).join(" · "),
        ),
        activate: () =>
          revealTarget(target, `${face.label}: ${itemSays(target)}`, scrollToElement),
      });
    }
    const claimActivity = new Map(
      acknowledgments()
        .filter((item) => item.phase === "active")
        .map((item) => [`${item.target.kind}:${item.target.id}`, item]),
    );
    const activityAlreadyShown = new Set();
    for (const [coordinate, entry] of projection.desired) {
      if (entry.e.kind !== "action") continue;
      const target = elementById(entry.unit) ?? elementById(entry.e.widget);
      if (!target) continue;
      const receipt = receiptByCoordinate.get(coordinate);
      if (!receipt) continue;
      const account = [itemWord(target), humanized(entry.e.action), itemSays(target)]
        .filter(Boolean)
        .join(" · ");
      const face = acknowledgmentFace(receipt);
      if (face.kind === "activity")
        activityAlreadyShown.add(`widget:${receipt.target.id}`);
      add(groups, target, {
        kind: face.kind,
        id: `acknowledgment:${receipt.id}`,
        text: trimmed(`${face.text} · ${account}`),
        acknowledgmentFace: KINDS[face.kind],
        ...(face.context ? { context: face.context } : {}),
        activate: () =>
          revealTarget(target, `${face.text}: ${account}`, scrollToElement),
      });
    }

    const base = comparisonBase();
    comparisonChanges().forEach((target, index) => {
      const account = `${itemWord(target)} changed${base == null ? "" : ` since v${base}`}`;
      const inline = inlineComparison(target);
      const mapAccount = inline ? `${itemWord(target)} changed` : account;
      add(groups, target, {
        kind: "change",
        id: `change:${targetPath(target)}:${index}`,
        text: trimmed(`${mapAccount} · ${itemSays(target)}`),
        // A disclosure has to say what it holds, or its one word reports a fact and
        // promises nothing. The margin entry's quieter line carries it, and a block the
        // comparison holds nothing for has none, so no margin entry offers a press it has
        // not got.
        ...(inline ? { context: inline.offer, mapContext: inline.offer } : {}),
        // What a Change reading holds, where the comparison kept the base version's
        // words for this block: pressing it splices dropped text into the current
        // passage and paints additions there, so the reader learns what changed without
        // travelling to the other version and back. Where it kept none, the press is the
        // travel it always was, and `discloses` answering null is what says so — to the
        // margin entry's relation, to the shortcut bar's word for the press, and to the
        // reference.
        discloses: () => inlineComparison(target),
        activate: () => {
          const said = toggleInlineComparison(target);
          revealTarget(
            target,
            said ? `${account} · ${said}` : account,
            scrollToElement,
          );
        },
      });
    });

    if (workClaimState().claimsHeld)
      for (const update of updateSequence()) {
        if (update.source !== "claim" || update.disposition !== "effective") continue;
        if (update.revision > runtime.currentRevision) continue;
        if (activityAlreadyShown.has(`${update.target.kind}:${update.target.id}`))
          continue;
        const target =
          update.target.kind === "thread"
            ? placedAt(update.target.id)?.element
            : elementById(update.target.id);
        const quiet =
          claimActivity.get(`${update.target.kind}:${update.target.id}`)?.quiet ??
          false;
        const account = [
          update.agent || "Agent",
          update.text || humanized(update.action),
          quiet ? "quiet" : null,
        ]
          .filter(Boolean)
          .join(" · ");
        const age = ago(update.ts);
        add(groups, target, {
          kind: "activity",
          id: `activity:${update.id}`,
          text: trimmed(account),
          acknowledgmentFace: KINDS.activity,
          context: [age && `Checked in ${age}`, update.text]
            .filter(Boolean)
            .join(" · "),
          activate: () => revealTarget(target, account, scrollToElement),
        });
      }

    for (const offered of marginContributionEntries()) {
      const target =
        typeof offered.target === "function" ? offered.target() : offered.target;
      if (!target?.isConnected || inChrome(target)) continue;
      const group = groupFor(groups, target);
      if (group.offers.some((candidate) => candidate.key === offered.key))
        throw new TypeError(
          `Duplicate margin contribution key for ${target.id || targetPath(target)}: ${offered.key}`,
        );
      group.offers.push(offered);
      const subject =
        typeof offered.subject === "function" ? offered.subject() : offered.subject;
      if (String(subject ?? "").trim()) {
        if (group.subject && group.subject !== String(subject).trim())
          throw new TypeError(
            `Conflicting margin contribution subjects for ${target.id || targetPath(target)}`,
          );
        group.subject = String(subject).trim();
      }
      const items =
        typeof offered.items === "function" ? offered.items() : offered.items;
      for (const item of items ?? []) {
        const kind = item.kind ?? "action";
        if (!KINDS[kind]) throw new TypeError(`Unknown margin reading kind: ${kind}`);
        group.items.push({ marker: false, ...item, owner: offered.key, kind });
      }
    }

    const outline = pageOutline();
    const collected = [...groups.values()];
    const subjects = collected
      .filter((group) => !group.subject)
      .map((group) => group.target);
    return collected
      .map((group) => {
        const items = group.items;
        const represented = new Set(
          items
            .filter((item) => item.marker === false && item.represents)
            .map((item) => item.kind),
        );
        const subject = outlineSubjectFor(group.target, subjects, outline);
        return {
          ...group,
          title: trimmed(
            [
              group.subject ? null : subject.context,
              group.word,
              group.subject ?? itemSays(group.target),
            ]
              .filter(Boolean)
              .join(" · "),
            72,
          ),
          items: items
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

  function revealTarget(target, account, scrollToElement) {
    if (!target?.isConnected) return;
    scrollToElement(target, scrollBehavior(), "nearest");
    // The account goes to the bottom notice rather than to the live region alone:
    // a Change margin entry's target is usually already on screen, so the scroll moves nothing
    // and a press that only announced was, to a sighted reader, a press that did nothing.
    notice(account);
  }

  function markerOptions(row) {
    return {
      anchor: () => row.lfEntry?.target,
      ...(row.lfEntry?.offers.length || readingRegionFor(row.lfEntry?.target)
        ? {}
        : { fallback: "hide" }),
      priority: 10,
      claim: () => {
        const entry = row.lfEntry;
        if (!entry) return 0;
        if (readingRegionFor(entry.target)) return 0;
        const primary = choosePrimary(entry);
        const stable = [];
        if (primary && entry.offers.some((offered) => offered.claim))
          stable.push(primary);
        const marker = rows.get(entry.key);
        if (!primary && marker && !marker.hidden) stable.push(marker);
        const more = moreMarginEntries.get(entry.key);
        if (more && optionsOffered(entry, primary, { claimedOnly: true }))
          stable.push(more);
        const options = optionGroups.get(entry.key);
        if (
          options &&
          !optionsOffered(entry, primary, { claimedOnly: true }) &&
          secondaryCount(entry, primary, { claimedOnly: true }) > 0
        )
          stable.push(...clusterMarginEntries(options));
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
      hangs: () => !readingRegionFor(row.lfEntry?.target) && !panelWouldCover(),
      // A wide row is hoisted into main's positioning context. If its live width no
      // longer fits the rail, move the same node beside its target before static flow
      // takes over; restore the hoist before measuring whether it fits again.
      float: (item) => {
        if (item.lfEntry?.offers.length || readingRegionFor(item.lfEntry?.target))
          moveExternalHost(item, false);
      },
      dock: (item) => {
        if (item.lfEntry?.offers.length || readingRegionFor(item.lfEntry?.target))
          moveExternalHost(item, true);
      },
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

  function markerName(entry, index, anchored, position) {
    const choice = primaryReading(entry);
    const face = markerFace(entry).face;
    const count = choice?.items.length ?? 0;
    const reading = `${face.label}${count > 1 ? `s (${count})` : ""}`;
    const subject =
      count === 1 && choice.items[0].acknowledgmentFace ? choice.text : entry.title;
    return `${reading}, ${index + 1} of ${anchored}, ${subject}${position == null ? "" : `, ${Math.max(0, Math.min(100, position))} percent down`}`;
  }

  function availableRows() {
    return [...rows.values()].filter(
      (row) => !row.hidden && !row.closest(".lf-withheld") && row.checkVisibility(),
    );
  }

  function visibleRows() {
    return availableRows().filter((row) => {
      const box = row.getBoundingClientRect();
      return box.bottom > 0 && box.top < innerHeight;
    });
  }

  function clusterMarginEntries(host) {
    if (!host) return [];
    return [...host.querySelectorAll(".lf-margin-entry")].filter(
      (button) =>
        !button.disabled &&
        button.getAttribute("aria-disabled") !== "true" &&
        button.checkVisibility(),
    );
  }

  const marginEntryHost = (target) =>
    [...hosts.values()].find((host) => host.lfTarget === target) ?? null;

  function marginEntryContextContains(target, node) {
    return (
      Boolean(marginEntryHost(target)?.contains(node)) ||
      pageMapDialogContains(target, node)
    );
  }

  function stepClusterMarginEntries(binding) {
    const active = focused();
    const host = closestAcross(active, "[data-lf-margin-for]");
    const buttons = clusterMarginEntries(host);
    const at = buttons.indexOf(active);
    if (at < 0 || buttons.length < 2) return;
    const direction = binding === "ArrowRight" ? 1 : -1;
    buttons[(at + direction + buttons.length) % buttons.length].focus({
      preventScroll: true,
    });
    beginWalk("margin-entry", "Action", () => {
      const standing = focused();
      const standingHost = closestAcross(standing, "[data-lf-margin-for]");
      return listWalkPosition(clusterMarginEntries(standingHost), standing);
    });
  }

  function setOptionsOpen(
    entry,
    open,
    {
      returnFocus = false,
      focusOption = null,
      owner = null,
      preservePreview = false,
    } = {},
  ) {
    const previousKey = expandedOptionsKey;
    const previousGroup = previousKey ? optionGroups.get(previousKey) : null;
    const nextKey = open ? (entry?.key ?? null) : null;
    const nextOwner = open ? owner : null;
    if (previousKey === nextKey && expandedOptionsOwner === nextOwner) return;
    if (previewEntry && !preservePreview) closePreview();
    expandedOptionsKey = nextKey;
    expandedOptionsOwner = nextOwner;
    settlingOptionsFocus = true;
    try {
      renderMargin.refresh();
      if (returnFocus && previousKey) {
        const more = moreMarginEntries.get(previousKey);
        if (more?.isConnected && !more.hidden) more.focus({ preventScroll: true });
      } else if (focusOption && nextKey) {
        const choices = clusterMarginEntries(optionGroups.get(nextKey));
        const fallback = clusterMarginEntries(hosts.get(nextKey));
        const next =
          (focusOption === "last" ? choices.at(-1) : choices[0]) ??
          (focusOption === "last" ? fallback.at(-1) : fallback[0]);
        next?.focus({ preventScroll: true });
      }
    } finally {
      settlingOptionsFocus = false;
    }
    if (previousGroup?.querySelector(".lf-margin-reactions"))
      document.dispatchEvent(new CustomEvent("lf-margin-entry-options-closed"));
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

  // A contributed control remains the action's canonical target even when the margin
  // presents its secondary through a proxy in the unfolded cluster. Geometry belongs to
  // what the reader can see; dispatch still belongs to the original control.
  function presentedControl(control) {
    if (control.checkVisibility()) return control;
    const proxy = controlProxies.get(control);
    return proxy?.checkVisibility() ? proxy : control;
  }

  function openMarginEntryOptions(target, { owner = null } = {}) {
    renderMargin.refresh();
    const entry = pageInventory.find((candidate) => candidate.target === target);
    const more = entry && moreMarginEntries.get(entry.key);
    const focusedOffer =
      owner && entry?.offers.find((offered) => offered.key === owner);
    if (!entry || !more || (owner && !focusedOffer)) return false;
    if (expandedOptionsKey === entry.key && expandedOptionsOwner === owner) {
      const options = optionGroups.get(entry.key);
      if (options?.isConnected && !options.hidden) return true;
      expandedOptionsKey = null;
      expandedOptionsOwner = null;
      renderMargin.refresh();
    }
    if (expandedOptionsKey === entry.key && expandedOptionsOwner !== owner) {
      setOptionsOpen(entry, true, { owner });
      return true;
    }
    if (!owner && more.hidden) return false;
    setOptionsOpen(entry, true, { owner });
    return true;
  }

  function visibleMarginEntries() {
    return pageInventory.flatMap((entry) => clusterMarginEntries(hosts.get(entry.key)));
  }

  // A generated reading control has one exact meaning even when its target holds other
  // readings behind More. Contributed action controls have no core reading kind.
  function marginEntryKind(control) {
    const host = closestAcross(control, "[data-lf-margin-for]");
    const entry = host?.lfEntry;
    if (!entry) return null;
    if (control.lfChoice) return control.lfChoice.kind;
    return control === rows.get(entry.key)
      ? (primaryReading(entry)?.kind ?? null)
      : null;
  }

  function activateMarginEntry(control) {
    const item = closestAcross(control, "[data-lf-margin-for]");
    const entry = item?.lfEntry;
    if (!entry?.target || !control) return false;
    scrollToElement(entry.target, undefined, "nearest");
    // Arrive before activation, then use the exact visible margin entry's own press. A generated
    // route never chooses among the cluster's actions on the reader's behalf.
    focusForNavigation(control);
    control.click();
    return true;
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
  // which the walk, generated go-to hints, and the pointer all reach without it. A
  // status reports a move already made, so the stop passes to the nearest marker that
  // still offers a press.
  function holdTabStop(next) {
    const available = availableRows();
    const acts = (row) => row.dataset.lfBehavior !== "status";
    let stop = next;
    if (stop && !acts(stop)) {
      const at = available.indexOf(stop);
      stop = available.reduce((nearest, row, index) => {
        if (!acts(row)) return nearest;
        if (!nearest) return { row, distance: Math.abs(index - at) };
        const distance = Math.abs(index - at);
        return distance < nearest.distance ? { row, distance } : nearest;
      }, null)?.row;
    }
    for (const row of rows.values()) keeps(row, "tabindex", row === stop ? 0 : -1);
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
    beginWalk("page-map", "Marker", () =>
      listWalkPosition(visibleRows(), document.activeElement),
    );
  }

  let marginKeysAvailable = false;
  const marginKeys = [
    // The seat a reading holds is a span, so the platform's own activation is not under
    // it. Declared here rather than answered by a listener on the control: this is the
    // register's whole bargain — the line and the reference draw the key off the same row
    // the press is matched against, so neither can promise what the other does not do.
    // Only the span-shaped readings, because a native margin entry in this cluster answers its
    // own press and a second answer here would be two meanings for one key.
    {
      id: "margin.press",
      keys: PRESS,
      // Said for the margin entry under the reader, not for margin entries in general: "work this
      // margin entry" over a Change reading promised something, and Enter there scrolls to a
      // paragraph already on screen. A reading's press goes to what it points at; a
      // disclosure's opens or closes it; an action's does the verb on its face.
      // Read off the standing margin entry, and only where there is one: the reference
      // lists this row's sentence from anywhere on the page.
      does: () => {
        const behavior = focusedMarginEntryBehavior();
        if (behavior === "disclosure")
          return "Open or close what the focused margin entry holds";
        if (behavior === "action") return "Press the focused margin entry";
        if (behavior) return "Go to what the focused margin entry points at";
        return "Work the focused margin entry";
      },
      line: () => {
        const behavior = focusedMarginEntryBehavior();
        if (behavior === "disclosure") return "open / close";
        if (behavior === "action") return "press";
        if (behavior) return "go to it";
        return "work this margin entry";
      },
      when: () => focused()?.matches?.('.lf-margin-entry[role="button"]'),
      run: () => focused().click(),
    },
    {
      id: "margin.controls",
      keys: ["ArrowLeft", "ArrowRight"],
      does: "Move through the margin entries on this target",
      line: "move through margin entries",
      repeat: true,
      when: () => {
        const active = focused();
        const host = closestAcross(active, "[data-lf-margin-for]");
        return (
          active?.matches?.(".lf-margin-entry") && clusterMarginEntries(host).length > 1
        );
      },
      run: stepClusterMarginEntries,
    },
    {
      id: "margin.walk",
      keys: ["ArrowUp", "ArrowDown"],
      does: "Walk the visible page-map markers",
      line: "walk the Page Map",
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

  function pressMarker(event) {
    const marker = event.currentTarget;
    const choice = primaryReading(marker.lfEntry);
    if (!choice) return;
    if (choice.kind !== "comment") {
      activate(choice.items[0], marker.lfEntry);
      return;
    }
    openThreadChoice(marker.lfEntry, marker);
  }

  function paintMarker(row, entry, primary, { suppressed = false } = {}) {
    const { kinds: markerKinds, face, label, count: markerCount } = markerFace(entry);
    const choice = primaryReading(entry);
    const behavior = readingBehavior(face);
    row.lfEntry = entry;
    keepsHidden(row, suppressed || markerKinds.length === 0 || Boolean(primary));
    keeps(row, "data-lf-kinds", markerKinds.map(({ kind }) => kind).join(" "));
    marginEntry(row, {
      key: `reading:${choice?.key ?? "none"}`,
      icon: face.icon,
      label,
      context: readingContext(choice),
      behavior,
      rank: "reading",
      state: readingState(choice),
      writesRelation: false,
      writesSeat: false,
    });
    row.onclick = behavior === "status" ? null : pressMarker;
    syncReadingRelation(row, choice);
    row.removeAttribute("aria-pressed");
    syncMarginEntryCount(row, markerCount);
    if (row.lfTakeFocus) {
      delete row.lfTakeFocus;
      (row.hidden ? document.body : row).focus({ preventScroll: true });
    }
  }

  function externalPerch(target, main, flow = panelWouldCover()) {
    if (!main) return target;
    // A hanging item must be a child of main's own positioning context. In flow it
    // belongs immediately after the rendered block that owns its target. A declared
    // shadow tree still contributes through its host, where document CSS can reach the
    // controls.
    let perch = flow ? (blockAt(target) ?? target) : target;
    while (!main.contains(perch)) {
      const root = perch.getRootNode();
      if (!(root instanceof ShadowRoot)) return target;
      perch = root.host;
    }
    if (flow) return perch;
    while (perch.parentElement !== main && main.contains(perch.parentElement))
      perch = perch.parentElement;
    return perch;
  }

  function moveExternalHost(host, flow) {
    const main = document.querySelector("main");
    const target = host.lfEntry?.target;
    if (!main || !target || panelWouldCover()) return;
    const perch = externalPerch(target, main, flow);
    let after = perch;
    for (const entry of pageInventory) {
      const candidate = hosts.get(entry.key);
      if (candidate === host) break;
      if (
        candidate?.isConnected &&
        externalPerch(entry.target, main, flow) === perch &&
        candidate.parentNode === perch.parentNode
      )
        after = candidate;
    }
    if (after.nextSibling !== host) moveHost(host, () => after.after(host));
  }

  function optionControlNode(control, entry) {
    let node = controlProxies.get(control);
    if (!node) {
      node = offer("button", "lf-margin-option-proxy");
      node.type = "button";
      controlProxies.set(control, node);
    }
    const record = marginEntryRecord(control);
    marginEntry(node, {
      key: `${record.key}:proxy`,
      ...(record.icon ? { icon: record.icon } : { glyph: record.glyph }),
      label: record.label,
      context: record.context,
      behavior: record.behavior,
      tone: record.tone,
      rank: record.rank,
      state: record.state,
      writesRelation: record.writesRelation,
    });
    syncForwardedMarginEntryState(node, control);
    node.lfForwardedControl = control;
    // The proxy carries the control's press, so it carries where that control stands.
    standsWith(node, control);
    keeps(node, "data-lf-margin-entry-owner", record.owner);
    node.onclick = () => {
      control.click();
    };
    return node;
  }

  function readingOptionNode(entry, choice) {
    const key = readingKey(entry, choice);
    let node = readingMarginEntries.get(key);
    if (!node) {
      node = readingControl("lf-margin-reading-option");
      readingMarginEntries.set(key, node);
    }
    const face = readingFace(choice);
    const behavior = readingBehavior(face);
    const count = choice.items.length;
    const label = count > 1 ? `${face.label}s` : face.label;
    marginEntry(node, {
      key: `reading:${choice.key}`,
      icon: face.icon,
      label,
      context: readingContext(choice),
      behavior,
      rank: "reading",
      state: readingState(choice),
      writesRelation: false,
    });
    node.lfEntry = entry;
    node.lfChoice = choice;
    syncReadingRelation(node, choice);
    keeps(node, "data-lf-kinds", choice.kind);
    keeps(
      node,
      "aria-label",
      `${label} for ${entry.title}${count > 1 ? `, ${count} items` : ""}`,
    );
    syncMarginEntryCount(node, count);
    node.onclick =
      behavior === "status"
        ? null
        : () => {
            if (node.lfChoice.kind !== "comment") {
              setOptionsOpen(node.lfEntry, false, { returnFocus: true });
              activate(node.lfChoice.items[0], node.lfEntry, { focusMap: false });
              return;
            }
            openThreadChoice(node.lfEntry, node);
          };
    return node;
  }

  function focusedOwnerOffer(entry) {
    if (expandedOptionsKey !== entry.key || !expandedOptionsOwner) return null;
    return entry.offers.find((offered) => offered.key === expandedOptionsOwner) ?? null;
  }

  function optionNodes(entry, primary, focusedOffer = null) {
    if (focusedOffer) {
      const controls = controlsOf(focusedOffer).filter((control) =>
        entry.shownControls.has(control),
      );
      return focusedOffer.side === "after"
        ? controls
        : controls.map((control) => optionControlNode(control, entry));
    }
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
          .sort(compareMarginEntryRecords)
          .map(({ control }) => control),
      ),
    ];
  }

  function syncOptionGroup(group, entry, primary, optionsOpen, focusedOffer = null) {
    const allNodes = optionNodes(entry, primary, focusedOffer);
    const unique = [...new Set(allNodes)];
    // Peers may use the whole cluster budget only when no margin entry stands outside this
    // group. Reaction mode is the common case: it has neither a primary nor a reading
    // marker, so its six declared choices fit exactly. A reading-only target keeps its
    // marker visible, and that margin entry counts just as a contributed primary would.
    const peerCapacity = Math.max(
      0,
      EXPANDED_MARGIN_ENTRY_BUDGET -
        (!focusedOffer && (primary || markerFace(entry).kinds.length) ? 1 : 0),
    );
    const needsSpill = unique.length > peerCapacity;
    // The spill route consumes the last visible margin entry; it does not increase the
    // cluster beyond its budget. A fully expanded cluster is therefore either one
    // primary plus five peers, or one primary plus four peers plus the Page Map route.
    const visibleCapacity = needsSpill ? peerCapacity - 1 : peerCapacity;
    const hidden = Math.max(0, unique.length - visibleCapacity);
    const direct = unique.slice(0, visibleCapacity);
    const forcedThread =
      forcedInlineKey === entry.key
        ? unique.find((node) => node.lfChoice?.kind === "comment")
        : null;
    // An open thread card keeps its owning Thread control on the page edge. When the
    // ordinary order would put it beyond the six-control budget, spill the last unrelated
    // peer in its place; the Page Map still retains every action in canonical order.
    if (forcedThread && direct.length && !direct.includes(forcedThread))
      direct[direct.length - 1] = forcedThread;
    const visible = new Set(direct);
    const after = focusedOffer
      ? focusedOffer.side === "after"
        ? [focusedOffer]
        : []
      : afterOffers(entry);
    const afterControls = new Set(after.flatMap(controlsOf));
    const wanted = unique.filter(
      (node) => visible.has(node) && !afterControls.has(node),
    );
    // Keep contributor-owned groups intact: their keyboard scopes and event handlers
    // belong to the real controls. Overflow hides individual margin entries, not the owner.
    for (const offered of after) {
      const controls = controlsOf(offered);
      for (const control of controls)
        control.toggleAttribute("data-lf-margin-entry-overflow", !visible.has(control));
      offered.controls.toggleAttribute(
        "data-lf-margin-entry-overflow",
        !controls.some((control) => visible.has(control)),
      );
      wanted.push(offered.controls);
    }
    let spill = spillMarginEntries.get(entry.key);
    if (needsSpill) {
      if (!spill) {
        spill = offer("button", "lf-margin-spill");
        spill.type = "button";
        spillMarginEntries.set(entry.key, spill);
      }
      marginEntry(spill, {
        key: "all-options",
        icon: "all",
        label: `Show ${hidden} more in Page Map`,
        behavior: "disclosure",
        rank: "overflow",
        state: "idle",
      });
      keeps(spill, "data-lf-spill-count", hidden);
      spill.lfFirstSpilledOption = unique.find((node) => !visible.has(node));
      keeps(spill, "aria-label", `Show ${hidden} more in Page Map`);
      spill.onclick = () => openPageMap(entry, { invoker: spill, focusSpill: true });
      wanted.push(spill);
    } else if (spill) {
      spill.remove();
      spillMarginEntries.delete(entry.key);
    }
    for (const child of [...group.children])
      if (!wanted.includes(child)) child.remove();
    wanted.forEach((child, position) => {
      if (group.children[position] !== child)
        group.insertBefore(child, group.children[position] ?? null);
    });
    group.lfEntry = entry;
    keeps(
      group,
      "aria-label",
      `${entryEngaged(entry) ? "Actions" : "More options"} for ${entry.title}`,
    );
    keepsHidden(group, !optionsOpen || wanted.length === 0);
  }

  function syncControls(host, marker, more, options, entry) {
    const active = document.activeElement;
    const focusedOption = options.contains(active);
    const forwardedControl = active?.lfForwardedControl;
    const focusedOffer = focusedOwnerOffer(entry);
    const primary = focusedOffer ? null : syncControlRoles(entry);
    if (focusedOffer)
      for (const control of directControls(entry))
        control.removeAttribute("data-lf-margin-entry-primary");
    const controls = focusedOffer
      ? []
      : directOffers(entry)
          .filter((offered) => offered.controls)
          .map((offered) => offered.controls);
    const wanted = [...controls, marker, more, options];
    for (const child of [...host.children]) if (!wanted.includes(child)) child.remove();
    wanted.forEach((child, position) => {
      if (host.children[position] !== child)
        host.insertBefore(child, host.children[position] ?? null);
    });
    const secondaries = focusedOffer
      ? controlsOf(focusedOffer).filter((control) => entry.shownControls.has(control))
          .length
      : secondaryCount(entry, primary);
    const hasOptions = focusedOffer ? secondaries > 0 : optionsOffered(entry, primary);
    if (!hasOptions && expandedOptionsKey === entry.key) {
      expandedOptionsKey = null;
      expandedOptionsOwner = null;
    }
    const optionsOpen =
      secondaries > 0 &&
      (!hasOptions || expandedOptionsKey === entry.key || entryEngaged(entry));
    keepsHidden(more, !hasOptions || optionsOpen);
    more.lfEntry = entry;
    keeps(more, "aria-label", `More options for ${entry.title}`);
    keeps(more, "aria-expanded", optionsOpen);
    host.toggleAttribute("data-lf-options-open", optionsOpen);
    keeps(host, "data-lf-state", entryState(entry));
    // Replacing a focused proxy fires focusout synchronously. The render already owns
    // the resulting cluster state and transfers focus below, so do not let that event
    // start a nested render against the same child list.
    const wasSettlingOptionsFocus = settlingOptionsFocus;
    settlingOptionsFocus = true;
    try {
      syncOptionGroup(options, entry, primary, optionsOpen, focusedOffer);
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
        clusterMarginEntries(options)[0] ??
        clusterMarginEntries(host)[0];
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
    for (const offered of marginContributionEntries()) {
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
      keeps(host, "data-lf-margin-for", target.id || targetPath(target));
      host.lfTarget = target;
      keeps(host, "aria-label", `Actions for ${itemWord(target)}`);
      const controls = (side) =>
        offers
          .filter((offered) => offered.side === side)
          .sort(compareMarginContributions)
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
    // Moving a focused expanded cluster between the hanging rail and document flow
    // synchronously emits focusout. That is a placement transition, not the reader
    // leaving the cluster, so keep the options state machine from treating it as an
    // instruction to fold the controls it just exposed — and say the same thing to every
    // other reader of where the reader stands, which is what `placingChrome` is for.
    const wasSettlingOptionsFocus = settlingOptionsFocus;
    const wasPlacingChrome = runtime.placingChrome;
    settlingOptionsFocus = true;
    runtime.placingChrome = true;
    try {
      move();
      if (held?.isConnected) held.focus({ preventScroll: true });
    } finally {
      settlingOptionsFocus = wasSettlingOptionsFocus;
      runtime.placingChrome = wasPlacingChrome;
    }
    // The one case where the placement did move the reader: the control they were
    // standing on did not survive it, so focus is wherever the removal left it and the
    // standing paint is owed the news the guard above withheld.
    if (held && document.activeElement !== held) repaint();
  }

  function unfoldOpenThreadOwner(entry) {
    const previousKey = expandedOptionsKey;
    const previousGroup = previousKey ? optionGroups.get(previousKey) : null;
    expandedOptionsKey = entry.key;
    expandedOptionsOwner = null;
    renderMargin.refresh();
    if (previousGroup?.querySelector(".lf-margin-reactions"))
      document.dispatchEvent(new CustomEvent("lf-margin-entry-options-closed"));
  }

  function transferThreadCard(
    button,
    { returnFocus = document.activeElement === previewMarginEntry } = {},
  ) {
    if (previewMarginEntry === button) return;
    previewMarginEntry = button;
    previewReferenceSeen = false;
    if (returnFocus) button.focus({ preventScroll: true });
  }

  // Paper is not a posture this can be read in. Print hides every injected control
  // (`[data-lf-offer]` in the chrome stylesheet's print block) and the margin projection
  // with it, so the one contributor-visibility reading a render is built on comes back
  // empty: every cluster folds to nothing, and what has been written down is the medium
  // rather than the page. Nobody sees it on the dialog, where the margin does not print
  // at all, but the fold outlives the print preview and stands on screen until the next
  // render repairs it. It is the panel's head-room rule on the other surface that
  // measures: a reading taken where the box is `display: none` is not a measurement. So
  // a render asked for on paper is refused whole and taken once the screen is back.
  const onPaper = matchMedia("print");

  function renderNow() {
    if (onPaper.matches) return;
    const threadOwnerHeld =
      transferThreadFocus || document.activeElement === previewMarginEntry;
    transferThreadFocus = false;
    const main = document.querySelector("main");
    if (!nav.isConnected) chromeRoot.append(nav);
    const mainRect = main?.getBoundingClientRect();
    measureMargin(mainRect)?.();
    syncInlineOffers();
    pageInventory = collectEntries().filter((entry) => entry.target);
    // Read contributor visibility once for the whole render, before folding any
    // controls. Placement and option counts share this reading; probing again
    // temporarily unfolds controls and forces style/layout work for every row.
    const shownControls = new Set(
      controlsShownByOwner([
        ...new Set(pageInventory.flatMap((entry) => entry.offers.flatMap(controlsOf))),
      ]),
    );
    for (const entry of pageInventory) entry.shownControls = shownControls;
    const liveHosts = new Set(
      pageInventory.filter(entryHasMarginHost).map((entry) => entry.key),
    );
    const liveReadingKeys = new Set(
      pageInventory.flatMap((entry) =>
        readingChoices(entry).map((choice) => readingKey(entry, choice)),
      ),
    );
    for (const key of readingMarginEntries.keys())
      if (!liveReadingKeys.has(key)) readingMarginEntries.delete(key);
    if (expandedOptionsKey && !liveHosts.has(expandedOptionsKey)) {
      expandedOptionsKey = null;
      expandedOptionsOwner = null;
    }
    for (const [key, marker] of rows)
      if (!liveHosts.has(key)) {
        const host = hosts.get(key);
        unregisterMarginRow(host);
        host?.remove();
        rows.delete(key);
        moreMarginEntries.delete(key);
        spillMarginEntries.delete(key);
        optionGroups.delete(key);
        hosts.delete(key);
      }
    const externalDocks = new Map();
    let corePosition = 0;
    pageInventory.forEach((entry) => {
      if (!entryHasMarginHost(entry)) return;
      let marker = rows.get(entry.key);
      let more = moreMarginEntries.get(entry.key);
      let options = optionGroups.get(entry.key);
      let host = hosts.get(entry.key);
      if (host) host.lfEntry = entry;
      if (!marker) {
        host = el("div", "lf-ui lf-margin-cluster");
        host.dataset.lfGen = "1";
        host.setAttribute("role", "group");
        marker = marginEntry(readingControl("lf-margin-marker"), {
          key: "reading",
          icon: "dot",
          label: "Open page details",
          behavior: "disclosure",
          rank: "reading",
          writesRelation: false,
          writesSeat: false,
        });
        keys(host, "In the Page Map", marginKeys, () => marginKeysAvailable);
        host.lfEntry = entry;
        rows.set(entry.key, marker);
        more = marginEntry(offer("button", "lf-margin-more"), {
          key: "options",
          icon: "more",
          label: "More options",
          behavior: "disclosure",
          rank: "overflow",
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
          const control = event.target.closest?.(".lf-margin-entry");
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
          if (expandedOptionsKey === current.key && expandedOptionsOwner) return;
          if (entryEngaged(current)) return;
          setOptionsOpen(current, true, {
            focusOption: control === more ? "last" : null,
          });
        });
        host.addEventListener("focusin", () => {
          // A new keyboard destination outranks a pointer parked on the previous
          // target. Real pointer movement can take ownership back without a press.
          hoveredHost = null;
          refreshHighlight();
        });
        host.addEventListener("focusout", () =>
          requestAnimationFrame(refreshHighlight),
        );
        const takePointerOwnership = (event) => {
          const control = document
            .elementFromPoint(event.clientX, event.clientY)
            ?.closest?.(".lf-margin-entry");
          hoveredHost = control && host.contains(control) ? host : null;
          refreshHighlight();
        };
        host.addEventListener("pointermove", takePointerOwnership);
        host.addEventListener("pointerleave", () => {
          if (hoveredHost === host) {
            hoveredHost = null;
          }
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
            const primary = event.target.closest?.("[data-lf-margin-entry-primary]");
            if (primary && host.contains(primary)) setOptionsOpen(host.lfEntry, false);
          },
          { capture: true },
        );
        moreMarginEntries.set(entry.key, more);
        optionGroups.set(entry.key, options);
        hosts.set(entry.key, host);
        registerMarginRow(host, markerOptions(host));
      } else updateMarginRow(host, markerOptions(host));
      host.lfEntry = entry;
      host.lfTarget = entry.target;
      keeps(host, "data-lf-margin-for", entry.target.id || entry.key);
      keeps(host, "aria-label", `Page actions for ${entry.title}`);
      marker.lfEntry = entry;
      const primary = syncControls(host, marker, more, options, entry);
      if (entry.offers.length || readingRegionFor(entry.target)) {
        keeps(host, "data-lf-external", "1");
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
      paintMarker(marker, entry, primary, {
        suppressed: Boolean(focusedOwnerOffer(entry)),
      });
    });
    // Geometry is one read-only batch after every row has reconciled. Reading a target
    // between two marker writes forced one full document layout per Page-map entry —
    // including on the two-second heartbeat. The spoken positions use the main rect
    // already read above and one final scroll height, then write every name together.
    const mainHeight = main?.scrollHeight ?? 0;
    const positions = pageInventory.map((entry) =>
      entry.target && !readingRegionFor(entry.target) && mainRect && mainHeight
        ? Math.round(
            ((entry.target.getBoundingClientRect().top - mainRect.top) / mainHeight) *
              100,
          )
        : null,
    );
    const walked = pageInventory
      .map((entry, index) => ({ entry, position: positions[index] }))
      .filter(({ entry }) => entryHasMarginHost(entry));
    walked.forEach(({ entry, position }, index) => {
      const marker = rows.get(entry.key);
      const name = markerName(entry, index, walked.length, position);
      keeps(marker, "aria-label", name);
    });
    renderPageMapDialog(pageInventory);
    keepsHidden(nav, pageInventory.length === 0);
    keeps(nav, "aria-label", `Page Map, ${pageInventory.length} locations`);
    if (previewEntry) {
      const fresh = pageInventory.find((entry) => entry.key === previewEntry.key);
      if (!fresh || !fresh.items.some((item) => item.kind === "comment"))
        closePreview(preview.contains(document.activeElement));
      else {
        previewEntry = fresh;
        const owner = threadMarginEntry(fresh);
        if (
          owner &&
          !owner.checkVisibility() &&
          forcedInlineKey !== fresh.key &&
          expandedOptionsKey !== fresh.key &&
          !moreMarginEntries.get(fresh.key)?.hidden
        ) {
          transferThreadFocus = threadOwnerHeld;
          unfoldOpenThreadOwner(fresh);
          return;
        }
        if (!owner || (!owner.checkVisibility() && forcedInlineKey !== fresh.key))
          closePreview();
        else {
          transferThreadCard(owner, { returnFocus: threadOwnerHeld });
          buildThreadCard(fresh);
          for (const row of rows.values())
            syncReadingRelation(row, primaryReading(row.lfEntry));
          for (const reading of readingMarginEntries.values())
            syncReadingRelation(reading, reading.lfChoice);
        }
      }
    }
    refreshHighlight();
    scheduleMarginLayout();
    scheduleRoving();
    scheduleMarginEntryLabels();
    // Every Page-map host contributes the same keyboard section. Its capability is the
    // map's existence; each row already asks the narrower question of whether its press
    // works from the current focus. Repeating live geometry in every scope's `when`
    // forced a layout per location when paintKeys reflected them.
    marginKeysAvailable = pageInventory.length > 0;
    paintKeys();
  }

  function buildThreadCard(entry) {
    const focusedNode = preview.contains(document.activeElement)
      ? document.activeElement.closest?.("[data-lf-margin-entry]")
      : null;
    const focusedItem = focusedNode?.dataset.lfMarginEntry ?? null;
    const threadItems = entry.items.filter((item) => item.kind === "comment");
    const targetHeading = entry.target?.querySelector(":scope > strong")?.textContent;
    // A target with a heading is named by it. One without — an aside, a paragraph —
    // and holding one thread is headed by the passage that thread quotes, as the panel
    // heads it: a card headed "aside · The fallback cookie is read-only…" over a comment
    // on the aside's last sentence was a third name for one thread, and the least exact.
    const quoted =
      threadItems.length === 1 && threadItems[0].thread?.anchor
        ? anchorLabel(threadItems[0].thread.anchor, threadItems[0].thread.root.about)
        : null;
    const title = trimmed(targetHeading || quoted || entry.title, 72);
    keeps(preview, "data-lf-thread", "");
    keeps(preview, "aria-label", `Thread for ${title}`);
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
        ...previewList.querySelectorAll("[data-lf-margin-entry]"),
      ].find((candidate) => candidate.dataset.lfMarginEntry === focusedItem);
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
      (candidate) => candidate.dataset.lfMarginEntry === item.id,
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
    node.dataset.lfMarginEntry = item.id;
    return node;
  }

  function highlight(target) {
    if (highlighted === target) return;
    highlighted = target;
    const part = target ? visualAt(target, { unclaimed: false })?.part : null;
    paintTrace(target, part?.element === target ? part.surface : target);
  }

  function refreshHighlight() {
    const active = focused();
    const focusedHost = closestAcross(active, "[data-lf-margin-for]");
    const pointerHost = hoveredHost?.isConnected ? hoveredHost : null;
    const source =
      pointerHost ??
      focusedHost ??
      (preview.contains(active) || preview.matches(":popover-open")
        ? hosts.get(previewEntry?.key)
        : null);
    const entry = pageInventory.find(
      (candidate) => candidate.key === source?.lfEntry?.key,
    );
    // A drawing already marks this target on the page. When every item at the location
    // is a drawing comment, focusing its marker or thread needs no second target box.
    const drawingOnly =
      entry?.items.length &&
      entry.items.every(
        (item) => item.kind === "comment" && Boolean(item.thread?.root.drawing),
      );
    highlight(drawingOnly ? null : (entry?.target ?? null));
  }

  function showPreview(entry, button, retry = true) {
    if (!entry || designIsOn()) return;
    if (forcedInlineKey && forcedInlineKey !== entry.key) forcedInlineKey = null;
    if (previewEntry && previewEntry.key !== entry.key) clearThreadTransition();
    previewEntry = entry;
    transferThreadCard(button);
    buildThreadCard(entry);
    // The open pseudo-class is not observable until the browser's show operation
    // completes, and another auto popover may still be closing in this rendering turn.
    if (!preview.matches(":popover-open") && !previewShowing) {
      previewShowing = true;
      try {
        // The card remains an ordinary popover rather than an implicit invoker target so
        // its close control and conversation keep their established order in the shared
        // chrome layer.
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
            if (previewMarginEntry === button && button.isConnected)
              showPreview(entry, button, false);
          });
      } finally {
        previewShowing = false;
      }
    }
    placeThreadPreview();
    refreshHighlight();
    for (const row of rows.values())
      syncReadingRelation(row, primaryReading(row.lfEntry));
    for (const button of readingMarginEntries.values())
      syncReadingRelation(button, button.lfChoice);
    paintKeys();
  }

  function togglePinned(entry, button) {
    if (pinnedKey === entry.key && previewMarginEntry === button) {
      pinnedKey = null;
      closePreview();
      return;
    }
    pinnedKey = entry.key;
    showPreview(entry, button);
    const reply = previewList.querySelector("textarea");
    if (reply) {
      reply.focus({ preventScroll: true });
      revealConversation(reply.closest(".lf-conversation-thread"), reply);
    }
  }

  function closePreview(returnFocus = false) {
    clearThreadTransition();
    const button = previewMarginEntry;
    pinnedKey = null;
    forcedInlineKey = null;
    forcedInlineOptionsKey = null;
    previewEntry = null;
    previewMarginEntry = null;
    previewReferenceSeen = false;
    if (preview.matches(":popover-open")) preview.hidePopover();
    refreshHighlight();
    for (const row of rows.values())
      syncReadingRelation(row, primaryReading(row.lfEntry));
    for (const reading of readingMarginEntries.values())
      syncReadingRelation(reading, reading.lfChoice);
    if (returnFocus) {
      if (button?.isConnected && button.checkVisibility())
        button.focus({ preventScroll: true });
      else if (button?.lfEntry) focusMapControl(button.lfEntry);
    }
    paintKeys();
  }

  // The card and its owning margin entry cluster are one page-map stack even though the card
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
        (previewMarginEntry && host?.contains(previewMarginEntry)))
    )
      return {
        root: preview,
        does: "Close the thread card",
        says: "close thread",
        out: () => closePreview(true),
      };
    const optionsHost = atFocus ? host : hosts.get(expandedOptionsKey);
    if (optionsHost?.lfEntry?.key === expandedOptionsKey)
      return {
        root: optionsHost,
        does: "Fold the secondary page actions",
        says: "close options",
        out: () => setOptionsOpen(optionsHost.lfEntry, false, { returnFocus: true }),
      };
    return null;
  }

  function activate(item, entry, { focusMap = true } = {}) {
    if (expandedOptionsKey && expandedOptionsKey !== entry.key)
      setOptionsOpen(entry, false);
    closePreview();
    leavePageMap();
    const landsOnTarget = focusMap && !entryHasMarginHost(entry);
    if (focusMap && !landsOnTarget) focusMapControl(entry);
    item.activate();
    // A Page-map-only location has no margin control to receive the handoff. Reveal its
    // target first, then lend that authored element a programmatic tab stop so keyboard
    // focus and the visible arrival name the same place.
    if (landsOnTarget && entry.target?.isConnected) focusDestination(entry.target);
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
    togglePinned(entry, button);
  }

  function openInlineThread(id, transition = null) {
    const itemId = marginThreadItem(threadList().find((t) => t.root.id === id));
    const entry = pageInventory.find((candidate) =>
      candidate.items.some((item) => item.id === itemId),
    );
    if (!entry || designIsOn() || panelIsOpen()) return null;
    const choice = threadReading(entry);
    if (!choice) return null;
    const previousForcedOptionsKey = forcedInlineOptionsKey;
    const transfersPreview = preview.matches(":popover-open");
    forcedInlineKey = entry.key;
    forcedInlineOptionsKey = null;
    // Reuse an open card as the thread walk changes targets. Hiding and showing the same
    // popover in one keyboard turn leaves its delayed close event free to clear the new
    // owner's return route.
    if (transfersPreview) {
      previewEntry = entry;
      pinnedKey = entry.key;
    }
    if (previousForcedOptionsKey && expandedOptionsKey === previousForcedOptionsKey)
      setOptionsOpen(null, false, { preservePreview: transfersPreview });
    let button = threadMarginEntry(entry);
    if (!button?.checkVisibility()) {
      forcedInlineOptionsKey = expandedOptionsKey === entry.key ? null : entry.key;
      if (forcedInlineOptionsKey)
        setOptionsOpen(entry, true, { preservePreview: transfersPreview });
      else renderMargin.refresh();
      button = threadMarginEntry(entry);
    }
    if (!button?.isConnected) {
      const optionsKey = forcedInlineOptionsKey;
      forcedInlineKey = null;
      forcedInlineOptionsKey = null;
      if (previewEntry) closePreview();
      if (optionsKey && expandedOptionsKey === optionsKey) setOptionsOpen(null, false);
      return null;
    }
    pinnedKey = entry.key;
    showPreview(entry, button);
    const item = [...previewList.children].find(
      (candidate) => candidate.dataset.lfMarginEntry === itemId,
    );
    item?.scrollIntoView({ behavior: scrollBehavior(), block: "nearest" });
    if (transition) scheduleThreadTransition(transition, entry);
    return item?.querySelector(".lf-conversation-thread") ?? null;
  }

  // A route that starts on the page stays on the page while that thread has an inline
  // address. Widget-local surfaces are already rendered, while a margin-projection thread is
  // opened on demand. Threads remains the complete fallback for a detached or otherwise
  // unaddressable conversation. Callers choose only the landing within the conversation;
  // this function owns the surface choice so a mark, its accessibility note, and t/T
  // cannot drift into different policies.
  function openPageThread(id, { focus = "reply" } = {}) {
    if (!panelIsOpen()) {
      const local = focusSurface(id, { focus });
      if (local) {
        const optionsKey = forcedInlineOptionsKey;
        closePreview();
        if (optionsKey && expandedOptionsKey === optionsKey)
          setOptionsOpen(null, false);
        scrollToThread(id);
        return local;
      }
      const thread = openInlineThread(id);
      if (thread) {
        const destination =
          focus === "thread"
            ? thread
            : (thread.querySelector("textarea:not([disabled])") ?? thread);
        if (destination === thread) {
          thread.focus({ preventScroll: true });
          thread.scrollIntoView({ behavior: scrollBehavior(), block: "nearest" });
          scrollToThread(id);
        } else {
          landInConversation(destination);
        }
        return destination;
      }
    }
    showThread(id, { focus });
    return null;
  }

  // The row's acknowledgment face is read out of the state projection, so it follows the
  // applied log on `lf-actions` rather than the receipt paint: every path that reconciles
  // a complete state dispatches that once it has reconciled, and both of the paths that
  // paint receipts sit inside one. A repaint driven from the paint instead ran inside the
  // panel render the application performs *before* reconciliation, which is early enough
  // to read a candidate the same read is about to reject — and it ran inside a dispatch,
  // where the fault that candidate throws is reported as an uncaught page error rather
  // than rejecting the read.

  // The margin packs its rows a frame after anything moves them — a row registering,
  // the column resizing under a diagram that finished or a disclosure that opened — and
  // the card was placed from its cluster when it opened. margin-layout.js says when it has
  // moved the rows, and the card follows in that same frame, so a reader never sees it
  // standing above or below where its controls used to be.

  const marginEntryChoices = (target) => clusterMarginEntries(marginEntryHost(target));
  const unfoldedMarginEntries = () =>
    expandedOptionsKey ? (hosts.get(expandedOptionsKey) ?? null) : null;
  const foldMarginEntryOptions = () => setOptionsOpen(null, false);
  const activeInlineThread = () => {
    const active = focused();
    const direct = active?.closest?.(".lf-conversation-thread[data-thread]");
    if (direct && !panelIsOpen()) return direct;
    if (
      !pinnedKey ||
      previewEntry?.key !== pinnedKey ||
      !preview.matches(":popover-open") ||
      !preview.hasAttribute("data-lf-thread")
    )
      return null;
    const held = preview.contains(active)
      ? active.closest?.(".lf-conversation-thread")
      : null;
    if (held) return held;
    if (active !== previewMarginEntry) return null;
    const conversations = previewList.querySelectorAll(
      ".lf-margin-thread .lf-conversation-thread",
    );
    return conversations.length === 1 ? conversations[0] : null;
  };

  // The margin's parts into the chrome, once it is mounted (leaf.js): the map button beside
  // the version chooser, then its own parts in the root.

  function mount() {
    reserveRail();
    onPaper.addEventListener("change", () => {
      if (!onPaper.matches) renderMargin.refresh();
    });
    previewClose.onclick = () => closePreview(true);
    preview.addEventListener("focusin", keepThreadPreviewFocusVisible);
    preview.addEventListener("toggle", (event) => {
      if (event.newState !== "closed") return;
      clearThreadTransition();
      if (!previewEntry) return;
      const button = previewMarginEntry;
      pinnedKey = null;
      forcedInlineKey = null;
      forcedInlineOptionsKey = null;
      previewEntry = null;
      previewMarginEntry = null;
      previewReferenceSeen = false;
      refreshHighlight();
      for (const row of rows.values())
        syncReadingRelation(row, primaryReading(row.lfEntry));
      for (const reading of readingMarginEntries.values())
        syncReadingRelation(reading, reading.lfChoice);
      paintKeys();
    });
    document.addEventListener("lf-actions", renderMargin);
    document.addEventListener("lf-answered", renderMargin);
    document.addEventListener("lf-comparison", renderMargin);
    document.addEventListener("lf-margin-layout", () => {
      placeThreadPreview({ remeasure: true });
      scheduleMarginEntryLabels();
    });
    for (const event of ["pointerover", "focusin"])
      document.addEventListener(event, scheduleMarginEntryLabels, { capture: true });
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
    watchMarginContributions(renderMargin);
    document.addEventListener(
      "scroll",
      (event) => {
        scheduleRoving();
        if (!preview.contains(event.target)) scheduleThreadPreviewPosition(false, true);
      },
      { capture: true, passive: true },
    );
    window.addEventListener("resize", () => {
      scheduleThreadPreviewPosition(true);
      schedulePostureRender();
    });
    renderMargin();
    matchMedia(COVERING).addEventListener("change", changePosture);
    versionBtn.before(mapButton);
    foldShelf();
    chromeRoot.append(nav, preview);
  }
  return {
    pageMapActive: () => availableRows().includes(focused()),
    activateMapItem: activate,
    faceForMap: (item) => KINDS[item.kind],
    focusMapControl,
    renderMargin,
    threadTransitionOrigin,
    scheduleThreadPreviewPosition,
    marginTargetAt,
    marginEntryContextContains,
    focusForNavigation,
    presentedControl,
    openMarginEntryOptions,
    visibleMarginEntries,
    marginEntryKind,
    activateMarginEntry,
    closePreview,
    keyboardRung,
    openInlineThread,
    openPageThread,
    marginEntryChoices,
    unfoldedMarginEntries,
    foldMarginEntryOptions,
    activeInlineThread,
    mount,
  };
}
