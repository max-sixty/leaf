/* The page-side projection of activity attached to exact document targets.

   This module combines registered contributions with core readings such as Threads,
   Asks, version changes, delivery receipts, and work claims. It reconciles one cluster
   and the inline thread card per target, then supplies the complete target projection to
   `page-map-dialog.js`. `margin-entries.js` owns the public control grammar and contribution
   registry; `margin-cluster-view.js` owns retained control materialization and Lit child
   order; `margin-layout.js` owns where each row stands: its lane, its posture in the rail
   or as a pin, and the packing that keeps rows clear of one another.

   `margin-model.js` derives the immutable inventory and cluster selection; its public
   records carry target coordinates, captured contribution readings, and generated facts.
   This adapter keeps target nodes and generated-reading callbacks. The contribution
   registry keeps registrations and command scopes.
   `margin-map-model.js` derives the complete searchable Page Map from the same inventory.
   A model never reads back identity from a control or carries a native control.

   Keyboard and pointer expansion share one state. Focus arrival through Tab unfolds a
   compact cluster, Left and Right walk it, and Escape folds only the layer that gesture
   opened. Page Map and Go-to arrivals activate the exact visible control;
   they do not choose another action for the user.

   The thread card stands by its owning cluster, or, where the rail has no room for that
   cluster, by the page target the cluster is about. `thread-card-geometry.js` states
   where it stands: in the rail beside the cluster when the room there takes the card's
   minimum measure, otherwise under or over the cluster with its right edge on the
   visible edge, so it crosses the column by no more than the rail's shortfall. The card
   keeps its height in every case; one too tall for its spot slides across its cluster
   rather than shrinking. This module supplies the visible boundary — the reading region
   or the viewport under the banner and over the bottom chrome — measures the card, and
   closes it once what it stands by has left that boundary. The card contains the
   complete inline thread view; the Threads panel remains the complete index and
   takes over when already open. A right-rail card aligns its top to the cluster while
   reading. While its reply has focus or draft text, its foot stays at the same
   distance from the cluster as the editor grows; the boundary still has the last
   word. Leaving an empty reply, closing the card, or selecting another thread
   restores the reading alignment.

   The card is margin chrome, not a native layer: it shows the threads of the target the
   user stands at, from the target, its cluster, or the card itself, so standing on an
   element and reading its thread are one place rather than two layers contending
   for focus and presses. Keyboard arrival at a commented element puts the card up
   beside it; standing elsewhere on the page, letting go (`declareRelease`), or pressing
   outside the card, its target, and its cluster takes it down (`followStanding`). Escape from inside the
   card lands on its target. With Threads open the list's one expanded thread plays the
   card's part: the same arrival expands the target's thread there (`accompanyThread`).
   The rest of the runtime reads both directions from here: `threadHere` gives the thread
   a user standing on the page is at, and the side this owner declares to
   standing-target.js gives the page target a card, cluster, or panel thread stands for.

   Placing the card changes its geometry and nothing inside it. The user's place in
   its transcript is the list's own scroll, held through reflow. A landing, send, or
   step moves it; a new or growing agent turn follows while the reader is at the tail.
   Other state reads leave the transcript where the user put it.

   Each frozen cluster model names controls by contribution and entry identity. The Lit view
   retains their native nodes, so a state refresh cannot cancel a held pointer or move focus.
   A print-media render is deferred until screen media returns because print removes the
   injected controls and cannot supply their geometry.

   One constructed owner holds margin layout, retained controls, and preview state.
   Boot supplies version, map, travel, and semantic thread-render capabilities.
   mount hands the layer to the layout and binds the lifecycle after those owners exist; every
   later render reads the same bound capabilities, including event-driven repaints. */
import { cancelRender, nextRender, sizeObserver } from "./rendering.js";
import { labelWords, spokenSubject } from "./margin-entry-model.js";
import {
  mountMarginLayer,
  registerMarginRow,
  scheduleMarginEntryLabels,
  scheduleMarginLayout,
  unregisterMarginRow,
} from "./margin-layout.js";
import {
  marginContributionEntries,
  marginContributionSource,
  marginEntry,
  marginEntryRecord,
  marginEntrySource,
  presentMarginEntry,
  syncMarginAgentWorkflow,
  syncMarginEntrySelection,
  syncMarginTurn,
  syncMarginUnread,
  watchMarginContributions,
} from "./margin-entries.js";
import {
  KINDS,
  entryEngaged,
  choosePrimary,
  readingKey,
  readingChoices,
  primaryReading,
  threadReading,
  entryHasMarginHost,
  contributionItem,
  optionsOffered,
  markerFace,
  readingFace,
  readingState,
  readingBehavior,
  awaitingUser,
  unreadIn,
  readingContext,
  clusterProjection,
  marginInventory,
} from "./margin-model.js";
import { compareMarginContributions } from "./margin-entry-model.js";
import { mapButton } from "./page-map-dialog.js";
import { watchProjection } from "./projection-watch.js";
import {
  TEXT_BOX,
  TEXT_FIELD,
  declareRelease,
  focusDestination,
  letGo,
} from "./focus.js";
import { el, keeps, keepsHidden, offer } from "./widget-elements.js";
import { clampedRow, PRESS } from "./keyboard/bindings.js";
import { beginWalk, listWalkPosition } from "./walk-position.js";
import { ago, clocked } from "./presence.js";
import { runtime } from "./context.js";
import {
  containingReadingRegionFor,
  readingRegionFor,
  registerReadingRegion,
  shownRegionBounds,
} from "./reading-regions.js";

import { focused, keys, paintKeys } from "./keyboard/scopes.js";
import { pageCommand, pageRung, pageScope } from "./keyboard/register.js";
import {
  annotationsHidden,
  setAnnotationsHidden,
  watchAnnotations,
} from "./annotation-layer.js";
import { repaint } from "./repaint.js";
import { chromeRoot } from "./chrome.js";
import { versionBtn } from "./version-chooser.js";
import { motion, scrollBehavior } from "./motion.js";
import { panel } from "./thread/panel-elements.js";
import { accompaniedThread, accompanyThread } from "./thread/landing.js";
import { declareSide } from "./standing-target.js";
import { closestAcross, elementById, inChrome } from "./passages.js";
import { addressableSays, addressableWord, visualAt } from "./anchor-resolution.js";
import { paintTrace } from "./target-paint.js";
import { updateSequence } from "./updates.js";
import { threadList } from "./thread/state.js";
import { threadKey, turns } from "./thread/model.js";

import { projectionOrigins } from "./projection/model.js";
import { authoredStates } from "./projection/authored.js";
import { currentProjection } from "./projection/state.js";
import { notice } from "./notifications.js";
import { iconElement } from "./icons.js";
import { claimed, focusSurface } from "./thread/surfaces.js";
import { anchorLabel } from "./thread/messages.js";
import { createMarginClusterViews } from "./margin-cluster-view.js";

import { outlineSubjectFor, pageOutline } from "./thread/placement.js";
import { bannerControlDoor } from "./banner-shelf.js";
import { threadCardGeometry } from "./thread-card-geometry.js";
import { placeKeeper } from "./user-place.js";
import {
  isLiveWorkflow,
  isPageWidgetWorkflow,
  isWorkflowProgress,
  strongestWorkflow,
  threadAttention,
  workflowLabel,
} from "./thread/workflow.js";
import { renderedParent, under } from "./shadow.js";
import { retainUserIntent } from "./user-intent.js";

// A margin card's reply box.
const REPLY_BOX = `.lf-say ${TEXT_FIELD}`;

export function createMarginProjection({
  panelIsOpen,
  openAsks,
  designModeActive,
  pointerModeActive,
  comparisonBase,
  comparisonChanges,
  inlineComparison,
  toggleInlineComparison,
  leavePageMap,
  openPageMap,
  pageMapDialogContains,
  renderPageMapDialog,
  scrollThreadIntoView,
  renderMarginThread,
  bottomChromeBoxes,
  placedAt,
  showThread,
  goToAsk,
  scrollToElement,
  scrollToThread,
}) {
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
        node = renderedParent(node);
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

  // Targets and generated-reading callbacks stay outside the model. Registered
  // contributions already publish their own immutable model readings.
  const targets = new Map();
  const itemSources = new WeakMap();
  const targetFor = (entry) => (entry ? (targets.get(entry.key) ?? null) : null);
  const sourceItem = (item) => itemSources.get(item);
  function captureItem(item) {
    const { activate, discloses, thread, ...data } = item;
    const snapshot = Object.freeze({
      ...data,
      carriesWorkflow: Boolean(workflowReceipt([item])),
    });
    itemSources.set(snapshot, { activate, discloses, thread });
    return snapshot;
  }

  const workflows = () => runtime.workflows;
  const renderMargin = clocked(document.body, renderNow);
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

  // The card is the margin's, as the cluster it hangs from is, rather than a layer over
  // the page: a top-layer popover made every press on the page a light dismissal and
  // tiered the keyboard over it, so standing on the passage it discusses took it down.
  // It shows while the user stands at its target (`followStanding`).
  const preview = el("aside", "lf-ui lf-margin-preview");
  preview.id = "lf-margin-preview";
  preview.hidden = true;
  preview.setAttribute("role", "dialog");
  const previewOpen = () => !preview.hidden;
  const previewClose = el(
    "button",
    "lf-btn lf-icon-action lf-close-action lf-margin-preview-close",
  );
  previewClose.append(iconElement("cross", "lf-action-icon"));
  previewClose.type = "button";
  previewClose.setAttribute("aria-label", "Dismiss thread view");
  previewClose.title = "Dismiss thread view (Esc)";
  const previewNav = el("span", "lf-margin-preview-nav");
  const previewPosition = el("span", "lf-margin-preview-position");
  const previewPrevious = offer(
    "button",
    "lf-btn lf-icon-action lf-margin-preview-step",
  );
  previewPrevious.append(iconElement("previous", "lf-action-icon"));
  previewPrevious.setAttribute("aria-label", "Previous thread");
  previewPrevious.title = "Previous thread";
  const previewNext = offer("button", "lf-btn lf-icon-action lf-margin-preview-step");
  previewNext.append(iconElement("next", "lf-action-icon"));
  previewNext.setAttribute("aria-label", "Next thread");
  previewNext.title = "Next thread";
  previewNav.append(previewPrevious, previewPosition, previewNext);
  const previewList = el("div", "lf-margin-preview-list");
  preview.append(previewList);
  let previewRegionMounted = false;
  // The card's transcript is re-rendered on every reading of its thread; a message holds
  // the user's place in it under the event id it is rendered with (user-place.js).
  const previewPlace = placeKeeper(previewList, {
    items: ".lf-page-thread-msg[data-event]",
    identity: (message) => message.dataset.event,
  });
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
    // Margin packing finishes on the next frame, so the card is placed again from its
    // cluster's settled position before the carried shell reads where to aim.
    return new Promise((resolve) => {
      nextRender(() => {
        if (
          epoch !== threadTransitionEpoch ||
          previewEntry?.key !== entry.key ||
          !previewOpen()
        ) {
          resolve(false);
          return;
        }
        resetThreadPreviewPosition();
        resolve(placedThreadPreview());
      });
    }).then((positioned) => {
      if (
        !positioned ||
        epoch !== threadTransitionEpoch ||
        previewEntry?.key !== entry.key
      )
        return false;
      transitionThread(origin);
      return true;
    });
  }

  let workflowCarriers = new Set();
  let selectedReadingCarriers = new Set();
  const workflowReceipt = (items) =>
    strongestWorkflow(
      items
        .map((item) => item.workflowReceipt)
        .filter((workflow) => workflow && isWorkflowProgress(workflow)),
    );
  const rows = new Map();
  const moreMarginEntries = new Map();
  const readingMarginEntries = new Map();
  const hosts = new Map();
  const inlineHosts = new Map();
  let optionsOrdinal = 0;
  let pageInventory = [];
  let previewEntry = null;
  let previewThreadItem = null;
  let previewLatest = null;
  let previewMarginEntry = null;
  let transferThreadFocus = false;
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
  // A modal or contextual thread surface temporarily owns focus without ending the
  // document interaction beneath it. Preserve that context so its commands remain
  // true and its owning margin entry can receive focus when the surface closes.
  const inRetainedContext = (node) =>
    node instanceof Element &&
    (Boolean(node.closest("dialog[open]")) ||
      preview.contains(node) ||
      (panelIsOpen() && panel.contains(node)));
  function readingMarginEntry(entry, kind) {
    const marker = rows.get(entry.key);
    if (marker && !marker.hidden && primaryReading(entry)?.kind === kind) return marker;
    const choice = readingChoices(entry).find((candidate) => candidate.kind === kind);
    return choice
      ? (readingMarginEntries.get(readingKey(entry, choice)) ?? null)
      : null;
  }
  const threadMarginEntry = (entry) => readingMarginEntry(entry, "comment");
  // A core reading can change between a disclosure and a status while retaining the
  // user's place. Its stable span owns the native-like press it needs while actionable;
  // ordinary contributed commands remain native buttons.
  const readingControl = (className) => {
    const control = offer("span", className);
    keys(
      control,
      "On a margin entry",
      [
        {
          id: "margin.press",
          keys: PRESS,
          does: "Open or close what the focused margin entry holds",
          line: "open / close",
          run: () => control.click(),
        },
      ],
      {
        when: () => {
          const record = marginEntryRecord(control);
          return record.behavior === "disclosure" && !record.disabled;
        },
      },
    );
    return control;
  };

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
    const disclosed =
      choice?.items.length === 1 ? sourceItem(choice.items[0]).discloses?.() : null;
    if (!disclosed) {
      control.removeAttribute("aria-controls");
      control.removeAttribute("aria-expanded");
      return;
    }
    keeps(control, "aria-controls", disclosed.id);
    keeps(control, "aria-expanded", disclosed.open);
  }
  let widthFrame = 0;
  let previewPositionFrame = 0;
  let previewPositionDismissDetached = false;
  let previewReferenceSeen = false;
  let previewPositionWaiters = [];
  let previewFocusPending = null;
  let rightFootOffset = null;
  function answerThreadPreviewPosition(positioned) {
    const waiters = previewPositionWaiters;
    previewPositionWaiters = [];
    for (const resolve of waiters) resolve(positioned);
  }
  const threadPreviewPositioned = () =>
    new Promise((resolve) => previewPositionWaiters.push(resolve));
  // Placement is synchronous, so a card that can be placed is placed now. One that
  // cannot yet — its owner not connected, no
  // room — is answered by the placement a later frame lands, or by the close that
  // abandons it.
  const placedThreadPreview = () =>
    placeThreadPreview() ? Promise.resolve(true) : threadPreviewPositioned();
  function resetThreadPreviewPosition() {
    cancelRender(previewPositionFrame);
    previewPositionFrame = 0;
    previewPositionDismissDetached = false;
    previewReferenceSeen = false;
    rightFootOffset = null;
    delete preview.dataset.lfThreadPlacement;
    preview.style.opacity = "0";
    preview.style.pointerEvents = "none";
  }
  function scheduleWidthRender() {
    if (widthFrame) return;
    widthFrame = nextRender(() => {
      widthFrame = 0;
      renderMargin.refresh();
    });
  }
  function deferThreadPreviewFocus(positioned, focus) {
    const pending = { key: previewEntry?.key, holding: document.activeElement };
    previewFocusPending = pending;
    void positioned?.then((placed) => {
      if (previewFocusPending !== pending || pending.key !== previewEntry?.key) return;
      previewFocusPending = null;
      const holdingGone =
        document.activeElement === document.body &&
        (!pending.holding?.isConnected || !pending.holding?.checkVisibility());
      if (placed && (document.activeElement === pending.holding || holdingGone))
        focus();
    });
  }

  const CARD_GAP = 8;
  // The room a card may stand in: its target's reading region, else the viewport, less
  // the banner over it and the bottom chrome under it. The chrome's boxes stand in one
  // row at the foot, so the tallest of them bounds the whole width.
  function threadCardBoundary(target) {
    const region = containingReadingRegionFor(target);
    const bounds = region ? shownRegionBounds(region) : null;
    const bannerBottom =
      document.querySelector(".lf-banner")?.getBoundingClientRect().bottom ?? 0;
    const left = (bounds?.left ?? 0) + CARD_GAP;
    const right = (bounds?.right ?? document.documentElement.clientWidth) - CARD_GAP;
    const top = Math.max(bounds?.top ?? 0, bannerBottom) + CARD_GAP;
    const bottom =
      Math.min(
        bounds?.bottom ?? innerHeight,
        ...bottomChromeBoxes().map((box) => box.top),
      ) - CARD_GAP;
    return new DOMRect(left, top, Math.max(0, right - left), Math.max(0, bottom - top));
  }
  function measureThreadCard(width) {
    preview.style.setProperty("--lf-thread-width", `${width}px`);
    fitThreadCardEditors();
    return preview.getBoundingClientRect().height;
  }
  // Keep room for the last turn above the pinned reply, while letting the editor
  // scroll internally once it fills its share of the transcript.
  function fitThreadCardEditors() {
    const maxListHeight =
      parseFloat(preview.style.getPropertyValue("--lf-thread-max-height")) -
      (preview.offsetHeight - previewList.clientHeight);
    for (const input of previewList.querySelectorAll(REPLY_BOX)) {
      const row = input.closest(".lf-say");
      const thread = row.closest(".lf-page-thread");
      const style = getComputedStyle(thread);
      const furniture = row.offsetHeight - input.offsetHeight;
      const inset = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
      const room = Math.max(
        40,
        Math.min(maxListHeight * 0.35, maxListHeight - furniture - inset),
      );
      input.style.setProperty("--lf-thread-editor-room", `${room}px`);
    }
  }

  function threadCardCluster() {
    // A row the rail has no room for is withheld and has no box. A card placed against
    // that empty box stood in the boundary's corner over the words the user pressed,
    // and read as detached before it had stood anywhere, so no scroll could dismiss it.
    // It stands by the row's target instead. A row whose target is not shown is withheld
    // too, and that target has no box to stand by either.
    const row =
      previewMarginEntry.closest("[data-lf-margin-for]") ?? previewMarginEntry;
    return (
      row.checkVisibility() ? row : (targetFor(previewEntry) ?? row)
    ).getBoundingClientRect();
  }
  function placeThreadPreview({ dismissDetached = false } = {}) {
    if (!previewOpen() || !previewMarginEntry?.isConnected) return false;
    const replyEditor = previewList.querySelector(REPLY_BOX);
    const drafting =
      replyEditor?.checkVisibility() &&
      (replyEditor === document.activeElement || replyEditor.value !== "");
    if (!drafting) rightFootOffset = null;
    const cluster = threadCardCluster();
    const boundary = threadCardBoundary(targetFor(previewEntry));
    if (!boundary.width || !boundary.height) return false;
    const style = getComputedStyle(preview);
    // The boundary alone caps the card's height; the geometry measures it under that
    // cap at the width it chose, which the card is then wearing.
    preview.style.setProperty("--lf-thread-max-height", `${boundary.height}px`);
    const geometry = threadCardGeometry({
      cluster,
      target: targetFor(previewEntry)?.getBoundingClientRect() ?? null,
      boundary,
      gap: CARD_GAP,
      minWidth: parseFloat(style.getPropertyValue("--thread-card-min")),
      preferredWidth: parseFloat(style.getPropertyValue("--thread-card")),
      heightAt: measureThreadCard,
      rightFootOffset,
    });
    if (geometry.placement === "right" && rightFootOffset === null && drafting)
      rightFootOffset = geometry.y + geometry.height - cluster.top;
    if (geometry.detached) {
      if (previewReferenceSeen && dismissDetached) {
        closePreview();
        return false;
      }
    } else previewReferenceSeen = true;
    preview.style.left = `${geometry.x}px`;
    preview.style.top = `${geometry.y + (geometry.placement === "right" ? geometry.height : 0)}px`;
    preview.dataset.lfThreadPlacement = geometry.placement;
    preview.style.removeProperty("opacity");
    preview.style.removeProperty("pointer-events");
    answerThreadPreviewPosition(true);
    return true;
  }
  function scheduleThreadPreviewPosition(dismissDetached = false) {
    previewPositionDismissDetached ||= dismissDetached;
    if (previewPositionFrame) return;
    previewPositionFrame = nextRender(() => {
      previewPositionFrame = 0;
      const dismiss = previewPositionDismissDetached;
      previewPositionDismissDetached = false;
      placeThreadPreview({ dismissDetached: dismiss });
    });
  }
  // A viewport posture change can replace the focused full thread with its
  // compact action. Reconcile after resize delivery so the browser can finish its
  // own focus and popover bookkeeping before that node changes shape. Panel and tray
  // changes notify this runtime directly through their owners.

  // A margin cluster is hoisted away from the page target it belongs to, so ancestry
  // cannot answer what a press on one of its controls is about. Keep that relationship
  // behind the owner that performs the hoist. Design mode uses it to turn the press into
  // a comment on the target and the named control instead of letting the action fire.
  function marginTargetAt(node) {
    const at = node?.nodeType === 1 ? node : node?.parentElement;
    const control = closestAcross(at, ".lf-margin-entry");
    const source = control && marginEntrySource(control);
    if (source) return source;
    return closestAcross(at, "[data-lf-margin-for]")?.lfTarget ?? null;
  }

  function groupFor(groups, target) {
    let group = groups.get(target);
    if (!group) {
      const key = targetPath(target);
      const word = addressableWord(target);
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

  function visibleWidgetWorkflows() {
    return workflows().filter((workflow) =>
      isPageWidgetWorkflow(workflow, runtime.currentRevision),
    );
  }

  function agentWorkflowFace(receipt) {
    if (!receipt) return null;
    const label = workflowLabel(receipt);
    if (!label) return null;
    return {
      kind:
        receipt.next_actor === "user" || receipt.condition
          ? "waiting"
          : ["working", "replying"].includes(receipt.stage)
            ? "activity"
            : receipt.stage === "picked_up"
              ? "pickup"
              : "sent",
      text: label,
      context: [receipt.ts ? ago(receipt.ts) : "", receipt.detail]
        .filter(Boolean)
        .join(" · "),
    };
  }

  const marginThreadItem = (thread) => (thread ? `comment:${threadKey(thread)}` : null);

  function collectEntries() {
    const groups = new Map();
    const receiptByCoordinate = new Map();
    for (const receipt of visibleWidgetWorkflows()) {
      const coordinate =
        typeof receipt.coordinate === "string"
          ? receipt.coordinate
          : JSON.stringify(receipt.coordinate);
      receiptByCoordinate.set(coordinate, receipt);
    }
    const representedThreads = new Set();
    for (const thread of threadList()) {
      if (thread.resolved || !thread.anchor || claimed(thread.root.id)) continue;
      const id = thread.root.id;
      const target = placedAt(id)?.element;
      if (target?.isConnected && !inChrome(target)) representedThreads.add(id);
      const attention = threadAttention(thread);
      const onUser = attention?.kind === "needs_user";
      const unread = thread.unread.length;
      add(groups, target, {
        kind: "comment",
        // One row for one thread, across the log answering for it. A thread the
        // user just opened is known by its attempt until the log names it, and a row
        // whose identity changed there would be rebuilt — taking with it the reply box
        // the send had just put them in.
        id: marginThreadItem(thread),
        text: labelWords(
          thread.root.text || anchorLabel(thread.anchor, thread.root.about),
        ),
        thread,
        // The Thread record already combines server attention with the local workflow
        // overlay. Margin and Page Map carry that reading rather than deriving another
        // answer from raw turn or workflow fields.
        userAttention: onUser
          ? {
              label: attention.label,
              reason: thread.attention?.reason ?? "workflow",
            }
          : null,
        unread,
        // Page Map lists each thread on its own row, so the word goes on the row
        // rather than on an aggregate.
        ...(onUser
          ? { mapContext: attention.label }
          : unread
            ? { mapContext: `${unread} unread` }
            : {}),
        // Work decorates the thread control; it never replaces the control's
        // comment face or its disclosure action.
        workflowReceipt: onUser ? null : attention?.workflow,
        activate: () => showThread(id),
      });
    }

    const asks = openAsks();
    for (const ask of asks) {
      const id = ask.id;
      const target = elementById(id);
      if (!target) continue;
      add(groups, target, {
        kind: "ask",
        id: `ask:${id}`,
        text: labelWords(
          `${addressableWord(target)} · ${addressableSays(target) || id}`,
        ),
        activate: () => {
          const standing = openAsks();
          const next = standing.find((candidate) => candidate.id === id);
          if (next) goToAsk(next, standing);
        },
      });
    }

    const projection = currentProjection();
    for (const origin of projectionOrigins(authoredStates(), projection)) {
      const target = elementById(origin.unit);
      if (!target) continue;
      const face = KINDS[origin.origin];
      add(groups, target, {
        kind: origin.origin,
        id: `state-origin:${origin.origin}:${origin.unit}`,
        // Durable provenance belongs in Page Map rather than another target margin entry:
        // it remains explicit without changing the page's action density or geometry.
        marker: false,
        text: labelWords(
          [face.label, addressableWord(target), addressableSays(target)]
            .filter(Boolean)
            .join(" · "),
        ),
        activate: () =>
          revealTarget(
            target,
            `${face.label}: ${addressableSays(target)}`,
            scrollToElement,
          ),
      });
    }
    const claimActivity = new Map(
      workflows()
        .filter(isLiveWorkflow)
        .map((item) => [`${item.subject.kind}:${item.subject.id}`, item]),
    );
    const activityAlreadyShown = new Set();
    for (const [coordinate, entry] of projection.desired) {
      if (entry.e.kind !== "action") continue;
      const target = elementById(entry.unit) ?? elementById(entry.e.widget);
      if (!target) continue;
      const receipt = receiptByCoordinate.get(coordinate);
      if (!receipt) continue;
      const account = [
        addressableWord(target),
        humanized(entry.e.action),
        addressableSays(target),
      ]
        .filter(Boolean)
        .join(" · ");
      const face = agentWorkflowFace(receipt);
      if (!face) continue;
      if (face.kind === "activity")
        activityAlreadyShown.add(`widget:${receipt.subject.id}`);
      add(groups, target, {
        kind: face.kind,
        id: `acknowledgment:${receipt.id}`,
        text: labelWords(`${face.text} · ${account}`),
        workflowFace: KINDS[face.kind],
        workflowReceipt: receipt,
        ...(face.context ? { context: face.context } : {}),
        activate: () =>
          revealTarget(target, `${face.text}: ${account}`, scrollToElement),
      });
    }

    const base = comparisonBase();
    comparisonChanges().forEach((target, index) => {
      const account = `${addressableWord(target)} changed${base == null ? "" : ` since v${base}`}`;
      const inline = inlineComparison(target);
      const mapAccount = inline ? `${addressableWord(target)} changed` : account;
      add(groups, target, {
        kind: "change",
        id: `change:${targetPath(target)}:${index}`,
        text: labelWords(`${mapAccount} · ${addressableSays(target)}`),
        // A disclosure has to say what it holds, or its one word reports a fact and
        // promises nothing. The margin entry's quieter line carries it, and a block the
        // comparison holds nothing for has none, so no margin entry offers a press it has
        // not got.
        ...(inline ? { context: inline.offer, mapContext: inline.offer } : {}),
        // What a Change reading holds, where the comparison kept the base version's
        // words for this block: pressing it splices dropped text into the current
        // passage and paints additions there, so the user learns what changed without
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

    if (runtime.activity?.held)
      for (const update of updateSequence()) {
        if (update.source !== "claim" || update.disposition !== "effective") continue;
        if (update.revision > runtime.currentRevision) continue;
        if (update.target.kind === "thread" && representedThreads.has(update.target.id))
          continue;
        if (activityAlreadyShown.has(`${update.target.kind}:${update.target.id}`))
          continue;
        const target =
          update.target.kind === "thread"
            ? placedAt(update.target.id)?.element
            : elementById(update.target.id);
        const quiet =
          claimActivity.get(`${update.target.kind}:${update.target.id}`)?.quiet ??
          false;
        const age = ago(update.ts);
        const account = [
          update.agent || "Agent",
          update.text || humanized(update.action),
          quiet ? `Was working ${age}` : null,
        ]
          .filter(Boolean)
          .join(" · ");
        add(groups, target, {
          kind: "activity",
          id: `activity:${update.id}`,
          text: labelWords(account),
          workflowFace: KINDS.activity,
          workflowReceipt: claimActivity.get(
            `${update.target.kind}:${update.target.id}`,
          ),
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
      const subject = offered.reading.subject;
      if (String(subject ?? "").trim()) {
        if (group.subject && group.subject !== String(subject).trim())
          throw new TypeError(
            `Conflicting margin contribution subjects for ${target.id || targetPath(target)}`,
          );
        group.subject = String(subject).trim();
      }
      for (const item of offered.reading.readings) {
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
    targets.clear();
    return marginInventory(
      collected
        .sort((left, right) => comesBefore(left.target, right.target))
        .map((group) => {
          const subject = outlineSubjectFor(group.target, subjects, outline);
          targets.set(group.key, group.target);
          return Object.freeze({
            key: group.key,
            targetId: group.target.id,
            title: labelWords(
              [
                group.subject ? null : subject.context,
                group.word,
                group.subject ?? addressableSays(group.target),
              ]
                .filter(Boolean)
                .join(" · "),
            ),
            offers: Object.freeze(group.offers.map((offered) => offered.model)),
            items: Object.freeze(group.items.map(captureItem)),
            workflowReceipt: workflowReceipt(group.items),
          });
        }),
    );
  }

  function revealTarget(target, account, scrollToElement) {
    if (!target?.isConnected) return;
    scrollToElement(target, scrollBehavior(), "nearest");
    // The account goes to the bottom notice rather than to the live region alone:
    // a Change margin entry's target is usually already on screen, so the scroll moves nothing
    // and a press that only announced was, to a sighted user, a press that did nothing.
    notice(account);
  }

  // Every row lives in the chrome's margin layer, whatever it holds, and the layout owns
  // where: which lane, in which posture, at what offset (margin-layout.js). The row states
  // its target and its place among the others.
  function markerOptions(row, order) {
    return {
      anchor: () => targetFor(row.lfEntry),
      order,
      priority: 10,
      move: (into) => moveHost(row, into),
    };
  }

  function markerName(entry, index, anchored, position) {
    const choice = primaryReading(entry);
    const face = markerFace(entry).face;
    const count = choice?.items.length ?? 0;
    const items = choice?.items ?? [];
    const userContext =
      awaitingUser(items) || unreadIn(items) ? readingContext(choice) : null;
    const reading = `${face.label}${count > 1 ? `s (${count})` : ""}${userContext ? `, ${userContext}` : ""}`;
    const subject =
      count === 1 && choice.items[0].workflowFace ? choice.text : entry.title;
    return `${reading}, ${index + 1} of ${anchored}${position == null ? "" : `, ${Math.max(0, Math.min(100, position))} percent down`}, ${spokenSubject(subject)}`;
  }

  // A row hidden with the annotation layer is not one the keyboard can land on either.
  function availableRows() {
    return [...rows.values()].filter(
      (row) =>
        !row.hidden &&
        !row.closest(".lf-withheld") &&
        row.checkVisibility({ visibilityProperty: true }),
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
    const previousOwner = expandedOptionsOwner;
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
        const choices = clusterMarginEntries(hosts.get(nextKey)?.options);
        const fallback = clusterMarginEntries(hosts.get(nextKey));
        const next =
          (focusOption === "last" ? choices.at(-1) : choices[0]) ??
          (focusOption === "last" ? fallback.at(-1) : fallback[0]);
        next?.focus({ preventScroll: true });
      }
    } finally {
      settlingOptionsFocus = false;
    }
    if (previousOwner === "responses")
      document.dispatchEvent(new CustomEvent("lf-margin-entry-options-closed"));
  }

  function focusForNavigation(control) {
    reveal(control);
    const wasSuppressingOptionsArrival = suppressingOptionsArrival;
    suppressingOptionsArrival = true;
    try {
      control.focus({ preventScroll: true });
    } finally {
      suppressingOptionsArrival = wasSuppressingOptionsArrival;
    }
  }

  // Ask decisions name a semantic entry through whichever retained projection control
  // the registration currently exposes. Return the visible margin instance without
  // consulting contributor DOM.
  function presentedControl(control) {
    if (control?.checkVisibility()) return control;
    if (!control?.matches(".lf-margin-entry")) return null;
    const { key, owner } = marginEntryRecord(control);
    if (!key || !owner) return null;
    return (
      visibleMarginEntries().find(
        (candidate) =>
          marginEntryRecord(candidate)?.key === key &&
          marginEntryRecord(candidate)?.owner === owner &&
          candidate.checkVisibility(),
      ) ?? null
    );
  }

  function openMarginEntryOptions(target, { owner = null } = {}) {
    renderMargin.refresh();
    const entry = pageInventory.find((candidate) => targetFor(candidate) === target);
    const more = entry && moreMarginEntries.get(entry.key);
    const focusedOffer =
      owner && entry?.offers.find((offered) => offered.key === owner);
    if (!entry || !more || (owner && !focusedOffer)) return false;
    if (expandedOptionsKey === entry.key && expandedOptionsOwner === owner) {
      const options = hosts.get(entry.key)?.options;
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
    if (!targetFor(entry) || !control) return false;
    scrollToElement(targetFor(entry), undefined, "nearest");
    // Arrive before activation, then use the exact visible margin entry's own press. A generated
    // route never chooses among the cluster's actions on the user's behalf.
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
    // The Map is a shelf control, so at a width that folds it the button itself is
    // behind a shut door and cannot take focus. Ask the shelf for the way in.
    const door = bannerControlDoor(mapButton);
    if (door) {
      door.focus({ preventScroll: true });
      return;
    }
    const visible = visibleRows();
    const last =
      visible.find((row) => row.tabIndex === 0) ??
      visible[0] ??
      bannerControlDoor(versionBtn);
    last?.focus({ preventScroll: true });
  }

  // The rail holds one tab stop: the way in from the page, not the reading position,
  // which the walk, generated go-to hints, and the pointer all reach without it. A
  // status reports a move already made, so the stop passes to the nearest marker that
  // still offers a press.
  function holdTabStop(next) {
    const available = availableRows();
    const acts = (row) => marginEntryRecord(row)?.behavior !== "status";
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
    cancelRender(rovingFrame);
    rovingFrame = nextRender(() => {
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

  // `o`: the annotation layer (annotation-layer.js). Hiding it takes off what it hides
  // that the user could be standing in: the card closes through its ordinary close, an
  // unfolded cluster folds, and focus held by a pin goes to the pin's target, since the
  // browser would otherwise put it on body. An explicit request still shows what it asks
  // for without bringing the layer back: `t`, a Threads row and a Page Map pick open the
  // card at their target, and an arrival that walks to a target or to one of its row's
  // controls (`a`, `focusForNavigation`) shows that one row, so what decides the target
  // is in reach, until the user stands somewhere else. Tabbing or pressing onto a target
  // reveals nothing: the layer stays as the user left it.
  let revealed = null;
  function revealHost(host) {
    const shows = annotationsHidden() && host?.dataset.lfPlace === "pin" ? host : null;
    if (shows === revealed) return;
    revealed?.removeAttribute("data-lf-revealed");
    revealed = shows;
    revealed?.setAttribute("data-lf-revealed", "");
  }
  // The row a node stands in, or the row of the innermost target holding it.
  function standingHost(node) {
    const own = closestAcross(node, ".lf-margin-cluster");
    if (own) return own;
    let found = null;
    for (const host of hosts.values())
      if (
        host.lfTarget &&
        under(node, host.lfTarget) &&
        (!found || under(host.lfTarget, found.lfTarget))
      )
        found = host;
    return found;
  }
  const reveal = (node) => revealHost(annotationsHidden() ? standingHost(node) : null);
  document.addEventListener(
    "focusin",
    (event) => {
      if (
        revealed &&
        !revealed.contains(event.target) &&
        !(revealed.lfTarget && under(event.target, revealed.lfTarget))
      )
        revealHost(null);
    },
    { capture: true },
  );
  watchAnnotations((hidden) => {
    if (hidden) {
      const holding = closestAcross(document.activeElement, ".lf-margin-cluster");
      if (holding?.dataset.lfPlace === "pin" && holding.lfTarget?.isConnected)
        focusDestination(holding.lfTarget);
      if (previewOpen()) closePreview();
      expandedOptionsKey = null;
      expandedOptionsOwner = null;
    }
    revealHost(null);
    renderMargin.refresh();
    repaint();
  });
  pageCommand({
    id: "annotations.toggle",
    keys: ["o"],
    does: "Hide or show the annotations drawn over the page",
    line: () => (annotationsHidden() ? "show annotations" : "hide annotations"),
    run: () => {
      setAnnotationsHidden(!annotationsHidden());
      notice(
        annotationsHidden() ? "Annotations hidden. o shows them" : "Annotations shown",
      );
    },
  });

  let marginKeysAvailable = false;
  const marginKeys = [
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

  function paintMarker(
    row,
    entry,
    primary,
    { suppressed = false, accessibleLabel = null } = {},
  ) {
    const { kinds: markerKinds, face, label, count: markerCount } = markerFace(entry);
    const choice = primaryReading(entry);
    const behavior = readingBehavior(face);
    row.lfEntry = entry;
    keepsHidden(row, suppressed || markerKinds.length === 0 || Boolean(primary));
    keeps(row, "data-lf-kinds", markerKinds.map(({ kind }) => kind).join(" "));
    presentMarginEntry(
      row,
      marginEntry({
        key: `reading:${choice?.key ?? "none"}`,
        icon: face.icon,
        label,
        accessibleLabel: accessibleLabel ?? label,
        context: readingContext(choice),
        behavior,
        rank: "reading",
        state: readingState(choice),
        count: markerCount,
      }),
      { writesRelation: false, writesSeat: false },
    );
    row.onclick = behavior === "status" ? null : pressMarker;
    row.removeAttribute("aria-pressed");
    syncReadingRelation(row, choice);
    syncMarginAgentWorkflow(row, workflowReceipt(choice?.items ?? []));
    syncMarginTurn(row, awaitingUser(choice?.items ?? []));
    syncMarginUnread(row, unreadIn(choice?.items ?? []));
    if (row.lfTakeFocus) {
      delete row.lfTakeFocus;
      (row.hidden ? document.body : row).focus({ preventScroll: true });
    }
  }

  function materializeReadingItem({ entry, choice }) {
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
    const userContext =
      awaitingUser(choice.items) || unreadIn(choice.items)
        ? readingContext(choice)
        : null;
    presentMarginEntry(
      node,
      marginEntry({
        key: `reading:${choice.key}`,
        icon: face.icon,
        label,
        accessibleLabel: `${label} for ${spokenSubject(entry.title)}${count > 1 ? `, ${count} items` : ""}${userContext ? `, ${userContext}` : ""}`,
        context: readingContext(choice),
        behavior,
        rank: "reading",
        state: readingState(choice),
        count,
      }),
      { writesRelation: false },
    );
    node.lfEntry = entry;
    node.lfChoice = choice;
    keeps(node, "data-lf-kinds", choice.kind);
    syncReadingRelation(node, choice);
    syncMarginAgentWorkflow(node, workflowReceipt(choice.items));
    syncMarginTurn(node, awaitingUser(choice.items));
    syncMarginUnread(node, unreadIn(choice.items));
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

  function activateContributionControl({ offered, entry, control, surface, event }) {
    const consumesFocusedOwner =
      expandedOptionsKey && expandedOptionsOwner === offered.key;
    const activated = marginContributionSource(offered).registration.activate(
      entry.key,
      {
        origin: control,
        surface,
        input: event.detail === 0 ? "keyboard" : "pointer",
        // A contributor can replace the activated entry and ask to retain focus. That is
        // one semantic destination, not a fresh keyboard arrival that should disclose the
        // whole cluster again.
        focus: (key) => {
          const destination = marginContributionSource(offered).registration.control(
            key,
            surface,
            true,
          );
          if (!destination) return false;
          focusForNavigation(destination);
          return true;
        },
      },
    );
    // A disclosed contributor is a route to an action, not a mode that survives that
    // action. Its next immutable reading decides whether the resulting controls remain
    // open.
    if (activated && consumesFocusedOwner) {
      expandedOptionsKey = null;
      expandedOptionsOwner = null;
      renderMargin.refresh();
    }
  }

  const clusterViews = createMarginClusterViews({
    activateContribution: activateContributionControl,
    materializeReading: materializeReadingItem,
    openSpill: (entry, spill) =>
      openPageMap(entry, { invoker: spill, focusSpill: true }),
  });

  function focusedOwnerOffer(entry) {
    if (expandedOptionsKey !== entry.key || !expandedOptionsOwner) return null;
    return entry.offers.find((offered) => offered.key === expandedOptionsOwner) ?? null;
  }

  function presentCluster(host, marker, more, entry, projection, focus) {
    let options = host.options;
    // Retiring a focused projection fires focusout synchronously. The render already owns
    // the resulting cluster state and transfers focus below, so do not let that event
    // start a nested render against the same child list.
    const wasSettlingOptionsFocus = settlingOptionsFocus;
    settlingOptionsFocus = true;
    let primary;
    try {
      primary = host.present(projection);
    } finally {
      settlingOptionsFocus = wasSettlingOptionsFocus;
    }
    options = host.options;
    const lostOptionFocus =
      focus.focusedOption && !options.contains(document.activeElement);
    if (
      !projection.hasOptions &&
      (document.activeElement === more || lostOptionFocus)
    ) {
      const destination = primary ?? (primaryReading(entry) ? marker : null);
      if (destination === marker && marker.hidden) marker.lfTakeFocus = true;
      else (destination ?? document.body).focus({ preventScroll: true });
    } else if (lostOptionFocus) {
      // A secondary projection can become the primary when its press settles. Keep
      // focus on that same semantic control instead of jumping to the first status
      // reading merely because the cluster stayed engaged and replaced its peers.
      const next =
        (focus.focusedRecord
          ? clusterMarginEntries(host).find(
              (candidate) =>
                marginEntryRecord(candidate)?.key === focus.focusedRecord.key &&
                marginEntryRecord(candidate)?.owner === focus.focusedRecord.owner,
            )
          : null) ??
        primary ??
        clusterMarginEntries(options)[0] ??
        clusterMarginEntries(host)[0];
      (next ?? document.body).focus({ preventScroll: true });
    }
    return primary;
  }

  // A widget frozen into a thread belongs to that thread's document,
  // not to the page margin behind it. Keep its contributed controls in the local
  // flow, grouped by the same exact target identity, without registering a page rail
  // claim or a second placement model in the widget module.
  function syncInlineOffers() {
    const grouped = new Map();
    for (const offered of marginContributionEntries()) {
      const target =
        typeof offered.target === "function" ? offered.target() : offered.target;
      if (
        !target?.isConnected ||
        !inChrome(target) ||
        !offered.reading.entries.some((entry) => entry.visible)
      )
        continue;
      const offers = grouped.get(target) ?? [];
      offers.push(offered.model);
      grouped.set(target, offers);
    }

    // A dynamic target can move one retained contribution between thread seats.
    // Retire the old owner before the new one tracks that same native control.
    for (const [target, host] of inlineHosts)
      if (!grouped.has(target)) {
        host.clear();
        host.remove();
        inlineHosts.delete(target);
      }

    for (const [target, offers] of grouped) {
      let host = inlineHosts.get(target);
      if (!host) {
        host = clusterViews.createInline();
        inlineHosts.set(target, host);
      }
      host.lfTarget = target;
      const items = (side) =>
        offers
          .filter((offered) => offered.reading.side === side)
          .sort(compareMarginContributions)
          .flatMap((offered) =>
            offered.reading.entries
              .filter((record) => record.visible)
              .map((record) => contributionItem(offered, record, "inline")),
          );
      host.present(
        Object.freeze({
          entry: null,
          items: Object.freeze([...items("before"), ...items("after")]),
          kind: "inline",
          label: `Actions for ${spokenSubject(addressableWord(target))}`,
          offers: Object.freeze([...offers]),
          target: target.id || targetPath(target),
        }),
      );
      if (target.nextSibling !== host) moveHost(host, () => target.after(host));
    }
  }

  function moveHost(host, move) {
    const held = host.contains(document.activeElement) ? document.activeElement : null;
    // Moving a focused expanded cluster between lanes, when its target's scroller
    // changes, synchronously emits focusout. That is a placement transition, not the user
    // leaving the cluster, so keep the options state machine from treating it as an
    // instruction to fold the controls it just exposed — and say the same thing to every
    // other reader of where the user stands, which is what `placingChrome` is for.
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
    // The one case where the placement did move the user: the control they were
    // standing on did not survive it, so focus is wherever the removal left it and the
    // standing paint is owed the news the guard above withheld.
    if (held && document.activeElement !== held) repaint();
  }

  function unfoldOpenThreadOwner(entry) {
    const previousOwner = expandedOptionsOwner;
    expandedOptionsKey = entry.key;
    expandedOptionsOwner = null;
    renderMargin.refresh();
    if (previousOwner === "responses")
      document.dispatchEvent(new CustomEvent("lf-margin-entry-options-closed"));
  }

  function transferThreadCard(
    button,
    { returnFocus = document.activeElement === previewMarginEntry } = {},
  ) {
    if (previewMarginEntry === button) return;
    resetThreadPreviewPosition();
    previewMarginEntry = button;
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
    syncInlineOffers();
    pageInventory = collectEntries();
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
    for (const key of rows.keys())
      if (!liveHosts.has(key)) {
        const host = hosts.get(key);
        unregisterMarginRow(host);
        host?.clear();
        host?.remove();
        rows.delete(key);
        moreMarginEntries.delete(key);
        hosts.delete(key);
      }
    const nextWorkflowCarriers = new Set();
    pageInventory.forEach((entry, order) => {
      if (!entryHasMarginHost(entry)) return;
      let marker = rows.get(entry.key);
      let more = moreMarginEntries.get(entry.key);
      let host = hosts.get(entry.key);
      if (host) host.lfEntry = entry;
      if (!marker) {
        marker = presentMarginEntry(
          readingControl("lf-margin-marker"),
          marginEntry({
            key: "reading",
            icon: "dot",
            label: "Open page details",
            behavior: "disclosure",
            rank: "reading",
          }),
          { writesRelation: false, writesSeat: false },
        );
        rows.set(entry.key, marker);
        more = presentMarginEntry(
          offer("button", "lf-margin-more"),
          marginEntry({
            key: "options",
            icon: "more",
            label: "More options",
            behavior: "disclosure",
            rank: "overflow",
          }),
        );
        const optionsId = `lf-margin-options-${++optionsOrdinal}`;
        host = clusterViews.createPage(marker, more, optionsId);
        keys(host, "In the Page Map", marginKeys, () => marginKeysAvailable);
        host.lfEntry = entry;
        more.setAttribute("aria-controls", optionsId);
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
        host.addEventListener("focusout", () => nextRender(refreshHighlight));
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
        // A direct primary belongs to its contribution rather than the reading marker.
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
        hosts.set(entry.key, host);
      }
      registerMarginRow(host, markerOptions(host, order));
      // Parked in the root lane, in the inventory's order and off screen until the layout
      // pass anchors it, so the controls it renders are in the document, and in the tab
      // order where they belong, from their first render.
      if (!host.isConnected)
        toolbar.insertBefore(
          host,
          pageInventory
            .slice(order + 1)
            .map((later) => hosts.get(later.key))
            .find((later) => later?.parentElement === toolbar) ?? null,
        );
      host.lfEntry = entry;
      host.lfTarget = targetFor(entry);
      marker.lfEntry = entry;
      const focus = {
        focusedOption: Boolean(host.options?.contains(document.activeElement)),
        focusedRecord: document.activeElement?.matches(".lf-margin-entry")
          ? marginEntryRecord(document.activeElement)
          : null,
      };
      const projection = clusterProjection(entry, {
        expandedKey: expandedOptionsKey,
        expandedOwner: expandedOptionsOwner,
        forcedInlineKey,
      });
      if (!projection.hasOptions && expandedOptionsKey === entry.key) {
        expandedOptionsKey = null;
        expandedOptionsOwner = null;
      }
      const primary = presentCluster(host, marker, more, entry, projection, focus);
      if (primary && entry.workflowCarrier) {
        syncMarginAgentWorkflow(primary, entry.workflowReceipt);
        nextWorkflowCarriers.add(primary);
      }
    });
    for (const control of workflowCarriers)
      if (!nextWorkflowCarriers.has(control)) syncMarginAgentWorkflow(control, null);
    workflowCarriers = nextWorkflowCarriers;
    // Geometry is one read-only batch after every row has reconciled. Reading a target
    // between two marker writes forced one full document layout per Page Map entry —
    // including on the two-second heartbeat. The spoken positions use the main rect
    // already read above and one final scroll height, then write every name together.
    const mainHeight = main?.scrollHeight ?? 0;
    const positions = pageInventory.map((entry) =>
      targetFor(entry) && !readingRegionFor(targetFor(entry)) && mainRect && mainHeight
        ? Math.round(
            ((targetFor(entry).getBoundingClientRect().top - mainRect.top) /
              mainHeight) *
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
      paintMarker(marker, entry, hosts.get(entry.key).primary, {
        suppressed: Boolean(focusedOwnerOffer(entry)),
        accessibleLabel: name,
      });
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
    // Every Page Map host contributes the same keyboard section. Its capability is the
    // map's existence; each row already asks the narrower question of whether its press
    // works from the current focus. Repeating live geometry in every scope's `when`
    // forced a layout per location when paintKeys reflected them.
    marginKeysAvailable = pageInventory.length > 0;
    paintKeys();
  }

  function buildThreadCard(entry, requestedItem = null) {
    const focusedControl = [previewPrevious, previewNext, previewClose].find(
      (control) => control === document.activeElement,
    );
    const focusedNode = preview.contains(document.activeElement)
      ? document.activeElement.closest?.("[data-lf-margin-entry]")
      : null;
    const focusedItem = focusedNode?.lfMarginItem ?? null;
    const threadItems = entry.items.filter((item) => item.kind === "comment");
    const wanted = requestedItem ?? previewThreadItem ?? focusedItem;
    const selected = threadItems.find((item) => item.id === wanted) ?? threadItems[0];
    // Another thread starts at its top; an update to this one holds the reader's place.
    const arriving = previewThreadItem !== (selected?.id ?? null);
    if (arriving) rightFootOffset = null;
    const latest = selected ? turns(sourceItem(selected).thread).at(-1) : null;
    const messageSelector =
      ":scope > .lf-margin-thread > .lf-margin-thread-body > " +
      ".lf-page-thread > .lf-page-thread-msg";
    const replySelector =
      ":scope > .lf-margin-thread > .lf-margin-thread-body > " +
      ".lf-page-thread > .lf-say";
    const lastShown = [...previewList.querySelectorAll(messageSelector)].at(-1);
    const lastBox = lastShown?.getBoundingClientRect();
    const listBox = previewList.getBoundingClientRect();
    const replyBox = previewList.querySelector(replySelector)?.getBoundingClientRect();
    const follow =
      !arriving &&
      previewLatest?.thread === selected?.id &&
      latest?.author === "agent" &&
      (latest.id !== previewLatest.id || latest.text !== previewLatest.text) &&
      lastBox &&
      lastBox.bottom >= listBox.top &&
      lastBox.bottom <= (replyBox?.top ?? listBox.bottom) + 80 &&
      previewList.scrollHeight - previewList.clientHeight - previewList.scrollTop <= 2;
    const hold = arriving ? null : previewPlace.take();
    if (arriving) previewList.scrollTop = 0;
    previewThreadItem = selected?.id ?? null;
    const targetHeading =
      targetFor(entry)?.querySelector(":scope > strong")?.textContent;
    // A target with a heading is named by it. One without — an aside, a paragraph —
    // is headed by the passage the selected thread quotes, as the panel heads it: a card
    // headed "aside · The fallback cookie is read-only…" over a comment on the aside's
    // last sentence was a third name for one thread, and the least exact.
    const quoted = sourceItem(selected)?.thread?.anchor
      ? anchorLabel(
          sourceItem(selected).thread.anchor,
          sourceItem(selected).thread.root.about,
        )
      : null;
    const title = labelWords(targetHeading || quoted || entry.title);
    keeps(preview, "aria-label", `Thread for ${spokenSubject(title)}`);
    previewNav.hidden = threadItems.length < 2;
    const selectedIndex = Math.max(0, threadItems.indexOf(selected));
    previewPosition.textContent = `${selectedIndex + 1}/${threadItems.length}`;
    previewPrevious.disabled = selectedIndex === 0;
    previewNext.disabled = selectedIndex === threadItems.length - 1;
    const nodes = selected ? [previewItemNode(selected)] : [];
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
      ].find((candidate) => candidate.lfMarginItem === focusedItem);
      const destination = replacement?.matches(
        `button, :is(${TEXT_BOX}):not([disabled])`,
      )
        ? replacement
        : (replacement?.querySelector(".lf-page-thread") ??
          previewList.querySelector(".lf-page-thread") ??
          previewClose);
      destination.focus({ preventScroll: true });
    }
    if (focusedControl && document.activeElement !== focusedControl)
      (previewNav.hidden ? previewClose : focusedControl).focus({
        preventScroll: true,
      });
    placeThreadPreview();
    previewPlace.finish(hold);
    previewLatest = latest && { thread: selected.id, id: latest.id, text: latest.text };
    if (follow) previewList.scrollTop = previewList.scrollHeight;
  }

  function stepPreviewThread(step) {
    if (!previewEntry) return;
    const threadItems = previewEntry.items.filter((item) => item.kind === "comment");
    const current = threadItems.findIndex((item) => item.id === previewThreadItem);
    const next = Math.max(0, Math.min(threadItems.length - 1, current + step));
    if (next === current || !threadItems[next]) return;
    buildThreadCard(previewEntry, threadItems[next].id);
    const thread = previewList.querySelector(".lf-page-thread");
    if (thread) {
      thread.focus({ preventScroll: true });
      scrollThreadIntoView(thread, thread);
    }
  }

  function previewItemNode(item) {
    let node = [...previewList.children].find(
      (candidate) => candidate.lfMarginItem === item.id,
    );
    if (!node?.classList.contains("lf-margin-thread")) {
      node?.remove();
      node = el("section", "lf-margin-thread");
      const body = el("div", "lf-margin-thread-body");
      node.append(body);
    }
    renderMarginThread(
      node.querySelector(":scope > .lf-margin-thread-body"),
      sourceItem(item).thread,
      {
        nav: previewNav.hidden ? null : previewNav,
        close: previewClose,
        prepareLanding: () => {
          const target = targetFor(previewEntry);
          const mayLand = retainUserIntent({
            source: focused(),
            available: () => target?.isConnected,
            fallback: bannerControlDoor(mapButton),
          });
          return {
            optimistic: () => {
              if (previewOpen()) return false;
              return mayLand.handoff(() => focusDestination(target));
            },
          };
        },
      },
    );
    node.dataset.lfMarginEntry = item.id;
    node.lfMarginItem = item.id;
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
    // A user standing on the card's target itself already has its ring there; the
    // trace would paint over the one mark that says where they stand.
    const onTarget = previewOpen() && active && active === targetFor(previewEntry);
    const source =
      pointerHost ??
      focusedHost ??
      ((preview.contains(active) || previewOpen()) && !onTarget
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
        (item) =>
          item.kind === "comment" && Boolean(sourceItem(item).thread?.root.drawing),
      );
    highlight(drawingOnly ? null : (targetFor(entry) ?? null));
  }

  function showPreview(entry, button, threadItem = null) {
    if (!entry || designModeActive()) return;
    if (forcedInlineKey && forcedInlineKey !== entry.key) forcedInlineKey = null;
    if (previewEntry && previewEntry.key !== entry.key) clearThreadTransition();
    previewEntry = entry;
    transferThreadCard(button);
    buildThreadCard(entry, threadItem);
    preview.hidden = false;
    const positioned = placedThreadPreview();
    refreshHighlight();
    for (const row of rows.values())
      syncReadingRelation(row, primaryReading(row.lfEntry));
    for (const button of readingMarginEntries.values())
      syncReadingRelation(button, button.lfChoice);
    paintKeys();
    return positioned;
  }

  function togglePinned(entry, button) {
    if (pinnedKey === entry.key && previewMarginEntry === button) {
      pinnedKey = null;
      closePreview();
      return;
    }
    const open = () => {
      pinnedKey = entry.key;
      const positioned = showPreview(entry, button);
      if (previewList.querySelector(".lf-page-thread"))
        deferThreadPreviewFocus(positioned, () => {
          if (previewEntry?.key !== entry.key) return;
          const thread = previewList.querySelector(".lf-page-thread");
          if (!thread) return;
          thread.focus({ preventScroll: true });
          scrollThreadIntoView(thread, thread);
        });
    };
    open();
  }

  function closePreview(returnFocus = false) {
    clearThreadTransition();
    const button = previewMarginEntry;
    // Hiding the card takes focus inside it to the body, so a close the user did not
    // aim at the card itself — a scroll, a mode, a rerender — lands them instead.
    const heldInside = preview.contains(focused());
    // A cluster the walk unfolded to hang the view from folds with the view; one the
    // user unfolded stays, and is its own rung.
    const forcedOptionsKey = forcedInlineOptionsKey;
    pinnedKey = null;
    forcedInlineKey = null;
    forcedInlineOptionsKey = null;
    previewEntry = null;
    previewThreadItem = null;
    previewLatest = null;
    previewMarginEntry = null;
    previewFocusPending = null;
    answerThreadPreviewPosition(false);
    resetThreadPreviewPosition();
    if (previewOpen()) {
      for (const reply of previewList.querySelectorAll(TEXT_FIELD))
        reply.lfCollapseReply?.();
      preview.hidden = true;
    }
    if (forcedOptionsKey && expandedOptionsKey === forcedOptionsKey)
      setOptionsOpen(null, false);
    refreshHighlight();
    for (const row of rows.values())
      syncReadingRelation(row, primaryReading(row.lfEntry));
    for (const reading of readingMarginEntries.values())
      syncReadingRelation(reading, reading.lfChoice);
    if (returnFocus) {
      if (button?.isConnected && button.checkVisibility())
        button.focus({ preventScroll: true });
      else if (button?.lfEntry) focusMapControl(button.lfEntry);
    } else if (heldInside) letGo();
    paintKeys();
  }

  // The thread view, for the owners that open and close it from outside. What
  // takes it off again is the Page Map's own Escape step, read off the card standing
  // rather than off whatever put it up. The view's own close control, pressed by
  // pointer, hands focus to the margin entry the view hangs from, since that is where
  // the pointer is.
  const inlineThreadView = {
    showing: () => previewOpen(),
    dismiss: () => closePreview(),
  };

  // The card, which the user is either inside or standing at the entry of. It is
  // hoisted into the chrome while anchored to a target, so it counts as chrome for which
  // surface holds focus and as page-anchored for where the user lands.
  //
  // Inside it, the thread's parent is the target it is about: the press steps out onto
  // that target and the card stays up beside it, since the user still stands there,
  // and letting go of the target is the next press. From the entry it hangs from, the
  // press takes the card down.
  // A cluster the user unfolded themselves and opened the card from is a level of
  // their own under the card, and the card hands back to it instead (below).
  const unfoldedUnder = () => {
    const entry = previewMarginEntry?.lfEntry;
    return Boolean(
      entry &&
      expandedOptionsKey === entry.key &&
      expandedOptionsKey !== forcedInlineOptionsKey &&
      optionsRung(),
    );
  };
  const stepsOut = () => {
    const target = targetFor(previewEntry);
    return preview.contains(focused()) &&
      !unfoldedUnder() &&
      target?.isConnected &&
      target.checkVisibility()
      ? target
      : null;
  };
  function keyboardRung({ atFocus = true } = {}) {
    const active = focused();
    const host = closestAcross(active, "[data-lf-margin-for]");
    // A press on the target leaves the card up and the user holding nothing, which
    // is still standing at the card's target: the card is theirs to take down.
    const nowhere = !active || active === document.body;
    if (
      !previewOpen() ||
      (atFocus &&
        !nowhere &&
        !preview.contains(active) &&
        !(previewMarginEntry && host?.contains(previewMarginEntry)))
    )
      return null;
    if (stepsOut())
      return {
        root: preview,
        does: "Return to the page element this thread is about",
        says: "back to page",
        out: () => focusDestination(stepsOut()),
      };
    return {
      root: preview,
      does: "Dismiss the thread view",
      says: "dismiss thread",
      // Where it lands turns on whether a level of the user's own stands under it. A
      // cluster they unfolded themselves is that level, and it folds the moment focus
      // leaves the margin, so the close hands them back to the entry the card hangs
      // from and the fold is the next press. With no such cluster — the walk's own
      // reveal folds with the card, and a bare marker has none — the entry is a control
      // they may never have stood on, a `t` from the page having put the card up
      // without going near the margin, so the landing is the page it is anchored to.
      //
      // Under it means on the entry this card would land on. A cluster left unfolded on
      // another entry stands beside the card, not beneath it — the card retains the
      // margin's focus while it is up, so a `t` walk carries the card away from the
      // cluster and leaves it open — and landing on this entry would hand the next
      // press a fold that teleports focus somewhere third. So the question goes to
      // `optionsRung`, the step that would actually answer next, which also declines
      // for a host that has gone or an entry whose own state holds its actions open.
      out: () => {
        const standing = unfoldedUnder();
        closePreview(standing);
        if (!standing) letGo();
      },
    };
  }

  // The cluster the user unfolded is page-side state rather than a layer of the card,
  // so it answers from the ladder wherever they are standing — the card they opened from
  // it lands them out on the page, and the fold would otherwise be reachable only by
  // Tabbing back into the margin. It comes off after anything standing over the page and
  // before the page itself, beside the selection, and lands on the entry it hangs from,
  // which is the container it is part of.
  //
  // Once a contribution is engaged, its complete and escape controls are open because of
  // semantic state rather than because the user disclosed the secondary tray. That
  // state consumes the earlier disclosure step: Escape leaves the action the user is
  // standing on instead of first pretending to close controls that remain open by
  // contract.
  function optionsRung() {
    const host = hosts.get(expandedOptionsKey);
    if (!host?.lfEntry || host.lfEntry.key !== expandedOptionsKey) return null;
    if (entryEngaged(host.lfEntry)) return null;
    // A cluster the walk unfolded to hang the card from is the card's, and folds with it.
    if (expandedOptionsKey === forcedInlineOptionsKey) return null;
    return {
      root: host,
      does: "Fold the secondary page actions",
      says: "close options",
      out: () => setOptionsOpen(host.lfEntry, false, { returnFocus: true }),
    };
  }
  pageRung("margin options", optionsRung);

  // The card's way out stands ahead of the reaction and navigation modes, as the
  // surface's old local listener did, without another keydown listener of its own.
  const pageMapRung = (atFocus = true) => keyboardRung({ atFocus }) ?? null;
  pageScope("page map", {
    title: "In the Page Map",
    root: () => pageMapRung()?.root ?? document,
    when: () => Boolean(pageMapRung(false)),
    at: () => Boolean(pageMapRung()),
    rows: [
      {
        id: "margin.back",
        keys: ["Escape"],
        does: () => pageMapRung(false)?.does,
        line: () => pageMapRung()?.says,
        commandReferenceWhen: () => Boolean(pageMapRung(false)),
        when: () => Boolean(pageMapRung()),
        run: () => pageMapRung()?.out(),
      },
    ],
  });

  function activate(item, entry, { focusMap = true } = {}) {
    if (expandedOptionsKey && expandedOptionsKey !== entry.key)
      setOptionsOpen(entry, false);
    closePreview();
    leavePageMap();
    const landsOnTarget = focusMap && !entryHasMarginHost(entry);
    if (focusMap && !landsOnTarget) focusMapControl(entry);
    sourceItem(item).activate();
    // A Page Map-only location has no margin entry to receive the handoff. Reveal its
    // target first, then lend that authored element a programmatic tab stop so keyboard
    // focus and the visible arrival name the same place.
    if (landsOnTarget && targetFor(entry)?.isConnected)
      focusDestination(targetFor(entry));
  }

  function openThreadChoice(entry, button) {
    const choice = threadReading(entry);
    if (!choice) return;
    // With Threads open the marker lands its thread there, a press into the panel like a
    // note's, so it goes through the same door.
    if (panelIsOpen()) {
      if (expandedOptionsKey && expandedOptionsKey !== entry.key)
        setOptionsOpen(entry, false);
      closePreview();
      leavePageMap();
      openPageThread(sourceItem(choice.items[0]).thread.root.id);
      return;
    }
    if (expandedOptionsKey && expandedOptionsKey !== entry.key)
      setOptionsOpen(entry, false);
    togglePinned(entry, button);
  }

  // `unfold: false` is a card that accompanies where the user stands rather than one
  // they asked for: it hangs from the cluster's visible marker instead of unfolding the
  // cluster to reach the thread's own entry, so arriving somewhere changes no margin.
  function openInlineThread(
    id,
    { transition = null, onPositioned = null, unfold = true } = {},
  ) {
    const itemId = marginThreadItem(threadList().find((t) => t.root.id === id));
    const entry = pageInventory.find((candidate) =>
      candidate.items.some((item) => item.id === itemId),
    );
    if (!entry || designModeActive() || panelIsOpen()) return null;
    const choice = threadReading(entry);
    if (!choice) return null;
    const shown = (control) => (control?.checkVisibility() ? control : null);
    const marker = unfold
      ? null
      : (shown(threadMarginEntry(entry)) ?? shown(rows.get(entry.key)));
    if (!unfold && !marker) return null;
    const previousForcedOptionsKey = forcedInlineOptionsKey;
    const transfersPreview = previewOpen();
    forcedInlineKey = entry.key;
    forcedInlineOptionsKey = null;
    // Reuse an open card as the thread walk changes targets, so folding the cluster the
    // last step unfolded does not take down the card the walk is carrying.
    if (transfersPreview) {
      previewEntry = entry;
      pinnedKey = entry.key;
    }
    if (previousForcedOptionsKey && expandedOptionsKey === previousForcedOptionsKey)
      setOptionsOpen(null, false, { preservePreview: transfersPreview });
    let button = marker ?? threadMarginEntry(entry);
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
    const initiallyPositioned = showPreview(entry, button, itemId);
    const item = [...previewList.children].find(
      (candidate) => candidate.lfMarginItem === itemId,
    );
    item?.scrollIntoView({ behavior: scrollBehavior(), block: "nearest" });
    const thread = item?.querySelector(".lf-page-thread") ?? null;
    const positioned = transition
      ? scheduleThreadTransition(transition, entry)
      : initiallyPositioned;
    if (thread && onPositioned)
      deferThreadPreviewFocus(positioned, () => {
        const current = [...previewList.children]
          .find((candidate) => candidate.lfMarginItem === itemId)
          ?.querySelector(".lf-page-thread");
        if (current) onPositioned(current);
      });
    return thread;
  }

  // A route that starts on the page stays on the page while that thread has an inline
  // destination. Widget-local surfaces are already rendered, while a margin-projection thread is
  // opened on demand. Threads remains the complete fallback for a detached or otherwise
  // unaddressable thread. Callers choose only the landing within the thread;
  // this function owns the surface choice so a mark, its accessibility note, and t/T
  // cannot drift into different policies. The margin card always lands on the thread
  // itself.
  //
  // A press on marked words passes `travel: false`: the words are already under the
  // user's hand, and centring them moves everything the user was looking at. The
  // card needs no trip, since placeThreadPreview keeps it inside the viewport.
  function openPageThread(id, { focus = "reply", travel = true } = {}) {
    if (!panelIsOpen()) {
      // The trip starts before the surface takes focus, which scrolls it into view: the
      // trip records the place the user leaves, so it has to find them still there.
      if (travel && claimed(id)) scrollToThread(id);
      const local = focusSurface(id, { focus });
      if (local) {
        closePreview();
        return local;
      }
      const thread = openInlineThread(id, {
        onPositioned: (positionedThread) => {
          positionedThread.focus({ preventScroll: true });
          positionedThread.scrollIntoView({
            behavior: scrollBehavior(),
            block: "nearest",
          });
          if (travel) scrollToThread(id);
        },
      });
      if (thread) return thread;
    }
    return showThread(id, { focus });
  }

  // The row's acknowledgment face is read out of the published state projection rather
  // than the receipt paint. A repaint driven from the paint instead ran inside the
  // panel render the application performs *before* reconciliation, which is early enough
  // to read a candidate the same read is about to reject — and it ran inside a dispatch,
  // where the fault that candidate throws is reported as an uncaught page error rather
  // than rejecting the read.

  // The margin packs its rows a frame after anything moves them — a row registering,
  // the column resizing under a diagram that finished or a disclosure that opened — and
  // the card was placed from its cluster when it opened. margin-layout.js says when it has
  // moved the rows, and the card follows in that same frame, so a user never sees it
  // standing above or below where its controls used to be.

  // Standing selection belongs to the reading, not to focus or a particular feature's
  // control. Resolve it through the same inventory that decides which reading is the
  // visible marker and which is an unfolded option, then paint one shared state on the
  // compact projection. An open disclosure continues to use aria-expanded instead.
  function paintSelectedMarginEntries(selections) {
    const selected = new Set();
    for (const selection of selections) {
      const entry = pageInventory.find(
        (candidate) => targetFor(candidate) === selection.target,
      );
      const control = entry && readingMarginEntry(entry, selection.kind);
      if (control?.isConnected) selected.add(control);
    }
    for (const control of selectedReadingCarriers)
      if (!selected.has(control)) syncMarginEntrySelection(control, false);
    for (const control of selected) syncMarginEntrySelection(control, true);
    selectedReadingCarriers = selected;
  }

  // ---------- the card goes where the user stands ----------
  // A thread belongs to the target it is about, so a user stands at that target from
  // any side of it: the target or anything inside it, its margin cluster, or the card
  // showing its threads. The card shows the threads of the target the user stands at,
  // which is what lets both be up at once, and goes when they stand anywhere else on the
  // page, let go, or press outside all three. Keyboard focus passing through the chrome
  // at large — the banner, a tray — is working on the page rather than a place on it,
  // and leaves the card; a press anywhere else is the user's attention moving, and
  // takes it, as a press on another page place does.
  //
  // Arrival through the keyboard shows the card, as arrival through Tab unfolds a
  // cluster; a pointer that lands on a control in a commented block asked for that
  // control, and the mark and the marker are its way to the thread.
  const threadIdOf = (entry) =>
    sourceItem(threadReading(entry).items[0]).thread.root.id;
  const threadIdsOf = (entry) =>
    threadReading(entry).items.map((item) => sourceItem(item).thread.root.id);
  // A thread seat already shows the thread where it stands on the page; a card
  // beside it would be the same thread twice.
  const seatedOnPage = (id) =>
    [
      ...document.querySelectorAll(`.lf-page-thread[data-thread="${CSS.escape(id)}"]`),
    ].some((seat) => !preview.contains(seat) && !panel.contains(seat));
  // The innermost target holding the node whose threads the card would show.
  const threadEntryAt = (node) => {
    let standing = null;
    for (const entry of pageInventory) {
      const target = targetFor(entry);
      if (!target || !threadReading(entry) || !under(node, target)) continue;
      if (seatedOnPage(threadIdOf(entry))) continue;
      if (!standing || under(target, targetFor(standing))) standing = entry;
    }
    return standing;
  };
  function followStanding() {
    refreshHighlight();
    const active = focused();
    if (
      !active ||
      active === document.body ||
      preview.contains(active) ||
      panel.contains(active) ||
      designModeActive()
    )
      return;
    const host = closestAcross(active, "[data-lf-margin-for]");
    // With Threads open the panel is where a target's threads show, and its one expanded
    // thread is the card: arriving at a target by the keyboard expands its thread there.
    // Nothing closes, since the list stays whole wherever the user stands.
    if (panelIsOpen()) {
      const entry = host ? host.lfEntry : threadEntryAt(active);
      if (entry && threadReading(entry) && active.matches(":focus-visible"))
        accompanyThread(threadIdsOf(entry));
      return;
    }
    if (host) {
      if (previewOpen() && host.lfEntry?.key !== previewEntry?.key) closePreview();
      return;
    }
    const entry = threadEntryAt(active);
    if (!entry) {
      if (previewOpen() && !inChrome(active)) closePreview();
      return;
    }
    if (previewOpen() && previewEntry?.key === entry.key) return;
    if (active.matches(":focus-visible"))
      openInlineThread(threadIdOf(entry), { unfold: false });
    else if (previewOpen()) closePreview();
  }
  // Letting go of where the user stands leaves them standing nowhere, which takes the
  // card with it (`declareRelease`). A landing on the page that is not a let-go — `g p`,
  // a surface closing — leaves the card beside the target it is about.
  declareRelease(() => {
    if (previewOpen()) closePreview();
  });
  // A press away is judged where it starts and acted on where it ends, both outside,
  // as the platform's light dismissal is: the press's own handlers read the scene
  // first, so Threads pressed with the card up still carries its thread into the panel.
  const pressedAway = (event) => {
    if (!previewOpen()) return false;
    const path = event.composedPath();
    // A pointer mode reinterprets a press on the page as a stroke or an interface
    // comment, so there a press stands nowhere but in the card itself.
    const stands = pointerModeActive()
      ? [preview]
      : [preview, hosts.get(previewEntry?.key), targetFor(previewEntry)];
    if (stands.some((node) => node && path.includes(node))) return false;
    return !path.some(inRetainedContext);
  };
  let pressStartedAway = false;
  function pressAway(event) {
    pressStartedAway = pressedAway(event);
  }
  function pressEnded(event) {
    const away = pressStartedAway && pressedAway(event);
    pressStartedAway = false;
    if (away) closePreview();
  }

  const marginEntryChoices = (target) => clusterMarginEntries(marginEntryHost(target));
  const unfoldedMarginEntries = () =>
    expandedOptionsKey ? (hosts.get(expandedOptionsKey) ?? null) : null;
  const foldMarginEntryOptions = () => setOptionsOpen(null, false);
  // The thread the user is at: the one holding focus, else the one the card shows. The
  // card is up only while the user stands somewhere it belongs (`followStanding`,
  // `declareRelease`, `pressAway`), so its being up is the answer rather than a second
  // reading of where they stand beside it. With Threads open the list's thread expanded
  // for the target the user stands on plays the card's part. `c` answers in that
  // thread's reply box, `t` walks on from it, and Threads opens at it. A thread inside
  // the card or on the page is `.lf-page-thread`; one in the list is `.lf-thread`.
  const threadHere = () => {
    const active = focused();
    if (panelIsOpen()) {
      const entry = active && !panel.contains(active) && threadEntryAt(active);
      return entry ? accompaniedThread(threadIdsOf(entry)) : null;
    }
    const direct = active?.closest?.(".lf-page-thread[data-thread]");
    if (direct) return direct;
    if (!pinnedKey || previewEntry?.key !== pinnedKey || !previewOpen()) return null;
    const threads = previewList.querySelectorAll(".lf-margin-thread .lf-page-thread");
    return threads.length === 1 ? threads[0] : null;
  };
  // The page element a thread is about, resolved or not: where its anchor is placed, the
  // element its inventory entry is grouped under. A general or detached thread has none.
  const threadTarget = (id) => placedAt(id)?.element ?? null;
  // The page target this owner's chrome shows (standing-target.js): a margin cluster
  // control's, the card's — its threads and its own controls — and a thread's in the
  // Threads panel. `threadHere` is the same relation read the other way.
  declareSide((node) => {
    const projected = marginTargetAt(node);
    if (projected) return projected;
    if (preview.contains(node)) return targetFor(previewEntry);
    const listed = panel.contains(node)
      ? closestAcross(node, ".lf-thread[data-id]")
      : null;
    return listed ? threadTarget(listed.dataset.id) : null;
  });
  // A live revision replaces the browser document, so DOM identity cannot carry a
  // user standing in retained margin chrome. Carry the target and margin-entry keys
  // instead; this owner alone can revalidate those keys against the new projection and
  // reopen the transient preview that supplied the focused control.
  function captureStanding() {
    const active = focused();
    const host = closestAcross(active, "[data-lf-margin-for]");
    const control = active?.closest?.(".lf-margin-entry");
    const entry = previewEntry ?? host?.lfEntry;
    if (!entry) return null;
    const standing = {
      entry: entry.key,
      preview: previewOpen() ? { thread: previewThreadItem } : null,
      focus:
        active === previewClose
          ? { kind: "preview-close" }
          : control && host?.contains(control)
            ? {
                kind: "entry",
                key: marginEntryRecord(control)?.key,
                owner: marginEntryRecord(control)?.owner ?? null,
              }
            : null,
    };
    return standing.preview || standing.focus ? standing : null;
  }

  function restoreStanding(standing) {
    if (!standing || typeof standing.entry !== "string") return false;
    const entry = pageInventory.find((candidate) => candidate.key === standing.entry);
    if (!entry) return false;
    if (standing.preview) {
      const button = threadMarginEntry(entry);
      if (!button?.isConnected) return false;
      pinnedKey = entry.key;
      const positioned = showPreview(entry, button, standing.preview.thread);
      if (standing.focus?.kind === "preview-close")
        deferThreadPreviewFocus(positioned, () => {
          if (previewEntry?.key === entry.key)
            previewClose.focus({ preventScroll: true });
        });
      return true;
    }
    if (standing.focus?.kind !== "entry") return false;
    const host = hosts.get(entry.key);
    const control = clusterMarginEntries(host).find(
      (candidate) =>
        marginEntryRecord(candidate)?.key === standing.focus.key &&
        (marginEntryRecord(candidate)?.owner ?? null) === standing.focus.owner,
    );
    if (!control) return false;
    // Roving tabindex is painted in the margin's next layout frame. The semantic
    // destination is already known here, so lend it a stop if that frame has not run.
    focusDestination(control);
    return true;
  }

  // The margin's parts into the chrome, once it is mounted (leaf.js): the map button beside
  // the version chooser, then its own parts in the root.

  function mount() {
    mountMarginLayer(toolbar);
    onPaper.addEventListener("change", () => {
      if (!onPaper.matches) renderMargin.refresh();
    });
    previewClose.onclick = () => closePreview(true);
    preview.addEventListener("focusin", (event) => {
      if (!event.target.matches(REPLY_BOX) || rightFootOffset !== null) return;
      if (previewMarginEntry && preview.dataset.lfThreadPlacement === "right")
        rightFootOffset =
          preview.getBoundingClientRect().bottom - threadCardCluster().top;
    });
    preview.addEventListener("focusout", (event) => {
      if (event.target.matches(REPLY_BOX) && !event.target.value)
        scheduleThreadPreviewPosition();
    });
    sizeObserver(() => scheduleThreadPreviewPosition()).observe(preview);
    previewPrevious.onclick = () => stepPreviewThread(-1);
    previewNext.onclick = () => stepPreviewThread(1);
    watchProjection(document.body, renderMargin);
    document.addEventListener("lf-comparison", renderMargin);
    document.addEventListener("lf-margin-layout", () => {
      placeThreadPreview();
      scheduleMarginEntryLabels();
    });
    for (const event of ["pointerover", "focusin"])
      document.addEventListener(event, scheduleMarginEntryLabels, { capture: true });
    document.addEventListener("focusin", () => queueMicrotask(followStanding), {
      capture: true,
    });
    // Ahead of the document, where a mode claims its presses before anyone else hears
    // them: whatever a press becomes, it is still the user's attention moving.
    addEventListener("pointerdown", pressAway, { capture: true });
    addEventListener("pointerup", pressEnded, { capture: true });
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
        if (!preview.contains(event.target)) scheduleThreadPreviewPosition(true);
      },
      { capture: true, passive: true },
    );
    window.addEventListener("resize", () => {
      scheduleThreadPreviewPosition();
      scheduleWidthRender();
    });
    renderMargin();
    chromeRoot.append(nav, preview);
    if (!previewRegionMounted) {
      previewRegionMounted = true;
      registerReadingRegion({
        id: "lf-margin-preview",
        host: preview,
        body: previewList,
      });
    }
  }
  return {
    pageMapActive: () => availableRows().includes(focused()),
    activateMapItem: activate,
    faceForMap: (item) => KINDS[item.kind],
    targetFor,
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
    inlineThreadView,
    keyboardRung,
    optionsRung,
    openInlineThread,
    openPageThread,
    paintSelectedMarginEntries,
    marginEntryChoices,
    unfoldedMarginEntries,
    foldMarginEntryOptions,
    threadHere,
    threadTarget,
    captureStanding,
    restoreStanding,
    mount,
  };
}
