/* The page-side projection of activity attached to exact document targets.

   This module combines registered contributions with core readings such as Threads,
   Asks, version changes, delivery receipts, and work claims. It reconciles one cluster
   and the inline thread card per target, then supplies the complete target projection to
   `page-map-dialog.js`. `margin-entries.js` owns the public control grammar and contribution
   registry; `margin-cluster-view.js` owns retained control materialization and Lit child
   order; `margin-layout.js` owns row measurement, rail claims, responsive docking, packing,
   and collision bands.

   `margin-model.js` derives the immutable inventory and cluster selection; its public
   records carry target coordinates, captured contribution readings, and generated facts.
   This adapter keeps target nodes and generated-reading callbacks. The contribution
   registry keeps registrations and command scopes.
   `margin-map-model.js` derives the complete searchable Page Map from the same inventory.
   A model never reads back identity from a control or carries a native control.

   Keyboard and pointer expansion share one state. Focus arrival through Tab unfolds a
   compact cluster, Left and Right walk it, and Escape folds only the layer that gesture
   opened. Page Map and Go-to arrivals activate the exact visible control;
   they do not choose another action for the reader.

   The thread card stands by its owning cluster, or, where the rail has no room for that
   cluster, by the page target the cluster is about. `thread-card-geometry.js` states
   where it stands: in the rail beside the cluster when the room there takes the card's
   minimum measure, otherwise under or over the cluster with its right edge on the
   visible edge, so it crosses the column by no more than the rail's shortfall. The card
   keeps its height in every case; one too tall for its spot slides across its cluster
   rather than shrinking. This module supplies the visible boundary — the reading region
   or the viewport under the banner and over the bottom chrome — measures the card, and
   closes it once what it stands by has left that boundary. The card contains the
   complete inline conversation view; the Threads panel remains the complete index and
   takes over when already open.

   Placing the card changes its geometry and nothing inside it. The reader's place in
   its transcript is the list's own scroll, which the browser holds through reflow; only
   a gesture moves it — a landing through `revealConversation`, a send revealing the
   reply, a step to another thread starting it at the top. Every state read places the
   card, so a scroll written there would move a reader partway up the transcript on each
   status the agent writes.

   Each frozen cluster model names controls by contribution and entry identity. The Lit view
   retains their native nodes, so a state refresh cannot cancel a held pointer or move focus.
   A print-media render is deferred until screen media returns because print removes the
   injected controls and cannot supply their geometry.

   One constructed owner holds margin layout, retained controls, and preview state.
   Boot supplies version, map, travel, and semantic thread-render capabilities.
   mount reserves the rail and binds the lifecycle after those owners exist; every
   later render reads the same bound capabilities, including event-driven repaints. */
import { labelWords, spokenSubject } from "./margin-entry-model.js";
import {
  registerMarginRow,
  reserveRail,
  scheduleMarginEntryLabels,
  scheduleMarginLayout,
  unregisterMarginRow,
  updateMarginRow,
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
  watchMarginContributions,
} from "./margin-entries.js";
import {
  KINDS,
  secondaryCount,
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
  awaitingReader,
  readingContext,
  clusterProjection,
  marginInventory,
} from "./margin-model.js";
import { compareMarginContributions } from "./margin-entry-model.js";
import { mapButton } from "./page-map-dialog.js";
import { watchProjection } from "./projection-watch.js";
import { documentPoint, shownBox, shownParts } from "./geometry.js";
import { focusDestination, letGo } from "./focus.js";
import { el, keeps, keepsHidden, offer } from "./widget-elements.js";
import { clampedRow, PRESS } from "./keyboard/bindings.js";
import { beginWalk, listWalkPosition } from "./walk-position.js";
import { ago, clocked } from "./presence.js";
import { runtime } from "./context.js";
import {
  containingReadingRegionFor,
  readingRegionFor,
  shownRegionBounds,
} from "./reading-regions.js";

import { focused, keys, paintKeys } from "./keyboard/scopes.js";
import { pageRung, pageScope } from "./keyboard/register.js";
import { repaint } from "./repaint.js";
import { chromeRoot } from "./chrome.js";
import { versionBtn } from "./version-chooser.js";
import { motion, scrollBehavior } from "./motion.js";
import { panel } from "./conversation/panel-elements.js";
import { blockAt, closestAcross, elementById, inChrome } from "./passages.js";
import { addressableSays, addressableWord, visualAt } from "./anchor-resolution.js";
import { paintTrace } from "./target-paint.js";
import { updateSequence } from "./updates.js";
import { threadList } from "./conversation/state.js";
import { threadKey } from "./conversation/model.js";

import { projectionOrigins } from "./projection/model.js";
import { authoredStates } from "./projection/authored.js";
import { currentProjection } from "./projection/state.js";
import { notice } from "./notifications.js";
import { iconElement } from "./icons.js";
import { claimed, focusSurface } from "./conversation/surfaces.js";
import { anchorLabel } from "./conversation/messages.js";
import { createMarginClusterViews } from "./margin-cluster-view.js";

import { outlineSubjectFor, pageOutline } from "./conversation/placement.js";
import { bannerControlDoor } from "./banner-shelf.js";
import { threadCardGeometry } from "./thread-card-geometry.js";
import { placeKeeper } from "./reader-place.js";
import {
  isLiveWorkflow,
  isPageWidgetWorkflow,
  isWorkflowProgress,
  strongestWorkflow,
  threadAttention,
  workflowLabel,
} from "./conversation/workflow.js";

// Whether the margin's rail stands, as the stylesheet decided it: theme.css states the
// posture on `main` where it claims the rail, and this reads that answer rather than
// deriving one of its own from a width. It resolves a container query, so a read after a
// write forces layout, and the layout pass calls it from inside its write loops, once
// per row. So the answer is read once per task and reused: a pass is synchronous, and
// nothing it writes can change the reading, since the claim comes out of `main`'s room
// inside the shell while the container answers on the shell itself. The microtask that
// clears it runs before anything outside the pass can ask.
const readRailPosture = () => {
  const main = document.querySelector("main");
  return (
    Boolean(main) &&
    getComputedStyle(main).getPropertyValue("--lf-rail-posture").trim() === "margin"
  );
};
let railReading = null;
const railStands = () => {
  if (railReading === null) {
    railReading = readRailPosture();
    queueMicrotask(() => (railReading = null));
  }
  return railReading;
};

export function createMarginProjection({
  panelIsOpen,
  openAsks,
  designModeActive,
  comparisonBase,
  comparisonChanges,
  inlineComparison,
  toggleInlineComparison,
  leavePageMap,
  openPageMap,
  pageMapDialogContains,
  renderPageMapDialog,
  revealConversation,
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

  // Where focus was when it last moved, rather than where it is. The rail falling hides
  // the control holding it, and the browser takes focus off a hidden element itself,
  // onto body — sometimes before this owner hears that the shell moved and sometimes
  // after, since what decides it is whether the focus fixup lands before the resize
  // observation. Measured on the live reading alone, a held marker reached the Page Map
  // on four of five narrowings and body on the fifth. A blur to nothing writes nothing
  // here, so the remembered reading survives the hide.
  let marginHeld = false;
  const holdsMargin = () =>
    toolbar.contains(document.activeElement) ||
    preview.contains(document.activeElement);
  document.addEventListener(
    "focusin",
    () => {
      marginHeld = holdsMargin();
    },
    { capture: true },
  );

  function changePosture(stands) {
    if (!stands && preview.matches(":popover-open")) closePreview();
    // Both orderings answer: where the fixup has not landed the live reading holds, and
    // where it has, the remembered one does. Requiring body of the remembered reading
    // bounds the handoff to the hide — a reader who left the margin some other way,
    // with no `focusin` to land anywhere, keeps wherever they went.
    if (
      !stands &&
      (holdsMargin() || (marginHeld && document.activeElement === document.body))
    )
      requestAnimationFrame(() => focusMapControl());
    schedulePostureRender();
  }
  const preview = el("aside", "lf-ui lf-margin-preview");
  preview.id = "lf-margin-preview";
  preview.setAttribute("popover", "auto");
  preview.setAttribute("role", "dialog");
  const previewHead = el("div", "lf-margin-preview-head");
  const previewClose = el(
    "button",
    "lf-btn lf-icon-action lf-close-action lf-margin-preview-close",
  );
  previewClose.append(iconElement("cross", "lf-action-icon"));
  previewClose.type = "button";
  previewClose.setAttribute("aria-label", "Dismiss conversation view");
  previewClose.title = "Dismiss conversation view (Esc)";
  const previewNav = el("span", "lf-margin-preview-nav");
  const previewPosition = el("span", "lf-margin-preview-position");
  const previewPrevious = offer(
    "button",
    "lf-btn lf-icon-action lf-margin-preview-step",
  );
  previewPrevious.append(iconElement("previous", "lf-action-icon"));
  previewPrevious.setAttribute("aria-label", "Previous conversation");
  previewPrevious.title = "Previous conversation";
  const previewNext = offer("button", "lf-btn lf-icon-action lf-margin-preview-step");
  previewNext.append(iconElement("next", "lf-action-icon"));
  previewNext.setAttribute("aria-label", "Next conversation");
  previewNext.title = "Next conversation";
  previewNav.append(previewPrevious, previewPosition, previewNext);
  previewHead.append(previewNav, previewClose);
  const previewList = el("div", "lf-margin-preview-list");
  preview.append(previewHead, previewList);
  // The card's transcript is re-rendered on every reading of its thread; a message holds
  // the reader's place in it under the event id it is rendered with (reader-place.js).
  const previewPlace = placeKeeper(previewList, {
    items: ".lf-conversation-msg[data-event]",
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
      requestAnimationFrame(() => {
        if (
          epoch !== threadTransitionEpoch ||
          previewEntry?.key !== entry.key ||
          !preview.matches(":popover-open")
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
  const rowTops = new WeakMap();
  const moreMarginEntries = new Map();
  const readingMarginEntries = new Map();
  const hosts = new Map();
  const inlineHosts = new Map();
  let optionsOrdinal = 0;
  let pageInventory = [];
  let previewEntry = null;
  let previewThreadItem = null;
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
  // reader's place. Its stable span owns the native-like press it needs while actionable;
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
  let postureFrame = 0;
  let previewPositionFrame = 0;
  let previewPositionDismissDetached = false;
  let previewReferenceSeen = false;
  let previewPositionWaiters = [];
  let previewFocusPending = null;
  function answerThreadPreviewPosition(positioned) {
    const waiters = previewPositionWaiters;
    previewPositionWaiters = [];
    for (const resolve of waiters) resolve(positioned);
  }
  const threadPreviewPositioned = () =>
    new Promise((resolve) => previewPositionWaiters.push(resolve));
  // Placement is synchronous, so a card that can be placed is placed now. One that
  // cannot yet — its popover not open this rendering turn, its owner not connected, no
  // room — is answered by the placement a later frame lands, or by the close that
  // abandons it.
  const placedThreadPreview = () =>
    placeThreadPreview() ? Promise.resolve(true) : threadPreviewPositioned();
  function resetThreadPreviewPosition() {
    cancelAnimationFrame(previewPositionFrame);
    previewPositionFrame = 0;
    previewPositionDismissDetached = false;
    previewReferenceSeen = false;
    delete preview.dataset.lfThreadPlacement;
    preview.style.opacity = "0";
    preview.style.pointerEvents = "none";
  }
  function schedulePostureRender() {
    if (postureFrame) return;
    postureFrame = requestAnimationFrame(() => {
      postureFrame = 0;
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
    return preview.getBoundingClientRect().height;
  }
  // The reply scrolls internally once it fills the conversation's remaining room. A
  // viewport-only cap can put its first line and Send on opposite sides of the
  // transcript's clipping boundary.
  function fitThreadCardEditors() {
    for (const input of previewList.querySelectorAll(".lf-say textarea")) {
      const row = input.closest(".lf-say");
      const thread = row.closest(".lf-conversation-thread");
      const style = getComputedStyle(thread);
      const furniture = row.offsetHeight - input.offsetHeight;
      const inset = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
      input.style.setProperty(
        "--lf-thread-editor-room",
        `${Math.max(40, previewList.clientHeight - furniture - inset)}px`,
      );
    }
  }

  function placeThreadPreview({ dismissDetached = false } = {}) {
    if (
      !preview.matches(":popover-open") ||
      !preview.hasAttribute("data-lf-thread") ||
      !previewMarginEntry?.isConnected
    )
      return false;
    // A row the rail has no room for is withheld and has no box. A card placed against
    // that empty box stood in the boundary's corner over the words the reader pressed,
    // and read as detached before it had stood anywhere, so no scroll could dismiss it.
    // It stands by the row's target instead. A row whose target is not shown is withheld
    // too, and that target has no box to stand by either.
    const row =
      previewMarginEntry.closest("[data-lf-margin-for]") ?? previewMarginEntry;
    const cluster = (
      row.checkVisibility() ? row : (targetFor(previewEntry) ?? row)
    ).getBoundingClientRect();
    const boundary = threadCardBoundary(targetFor(previewEntry));
    if (!boundary.width || !boundary.height) return false;
    const style = getComputedStyle(preview);
    // The boundary alone caps the card's height; the geometry measures it under that
    // cap at the width it chose, which the card is then wearing.
    preview.style.setProperty("--lf-thread-max-height", `${boundary.height}px`);
    const geometry = threadCardGeometry({
      cluster,
      boundary,
      gap: CARD_GAP,
      minWidth: parseFloat(style.getPropertyValue("--thread-card-min")),
      preferredWidth: parseFloat(style.getPropertyValue("--thread-card")),
      heightAt: measureThreadCard,
    });
    if (geometry.detached) {
      if (previewReferenceSeen && dismissDetached) {
        closePreview();
        return false;
      }
    } else previewReferenceSeen = true;
    preview.style.left = `${geometry.x}px`;
    preview.style.top = `${geometry.y}px`;
    preview.dataset.lfThreadPlacement = geometry.placement;
    preview.style.removeProperty("opacity");
    preview.style.removeProperty("pointer-events");
    fitThreadCardEditors();
    answerThreadPreviewPosition(true);
    return true;
  }
  function scheduleThreadPreviewPosition(dismissDetached = false) {
    previewPositionDismissDetached ||= dismissDetached;
    if (previewPositionFrame) return;
    previewPositionFrame = requestAnimationFrame(() => {
      previewPositionFrame = 0;
      const dismiss = previewPositionDismissDetached;
      previewPositionDismissDetached = false;
      placeThreadPreview({ dismissDetached: dismiss });
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
        receipt.next_actor === "reader" || receipt.condition
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
      const onReader = attention?.kind === "needs_reader";
      add(groups, target, {
        kind: "comment",
        // One row for one conversation, across the log answering for it. A thread the
        // reader just opened is known by its attempt until the log names it, and a row
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
        readerAttention: onReader
          ? {
              label: attention.label,
              reason: thread.attention?.reason ?? "workflow",
            }
          : null,
        // Page Map lists each conversation on its own row, so the word goes on the row
        // rather than on an aggregate.
        ...(onReader ? { mapContext: attention.label } : {}),
        // Work decorates the conversation control; it never replaces the control's
        // comment face or its disclosure action.
        workflowReceipt: onReader ? null : attention?.workflow,
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
    // and a press that only announced was, to a sighted reader, a press that did nothing.
    notice(account);
  }

  function markerOptions(row) {
    return {
      anchor: () => targetFor(row.lfEntry),
      ...(row.lfEntry?.offers.length || readingRegionFor(targetFor(row.lfEntry))
        ? {}
        : { fallback: "hide" }),
      priority: 10,
      claim: () => {
        const entry = row.lfEntry;
        if (!entry) return 0;
        if (readingRegionFor(targetFor(entry))) return 0;
        const primaryItem = choosePrimary(entry);
        const primary = hosts.get(entry.key)?.primary ?? null;
        const stable = [];
        if (primary && entry.offers.some((offered) => offered.reading.claim))
          stable.push(primary);
        const marker = rows.get(entry.key);
        if (!primary && marker && !marker.hidden) stable.push(marker);
        const more = moreMarginEntries.get(entry.key);
        if (more && optionsOffered(entry, primaryItem, { claimedOnly: true }))
          stable.push(more);
        const options = hosts.get(entry.key)?.options;
        if (
          options &&
          !optionsOffered(entry, primaryItem, { claimedOnly: true }) &&
          secondaryCount(entry, primaryItem, { claimedOnly: true }) > 0
        )
          stable.push(...clusterMarginEntries(options));
        const widths = stable
          .map((part) => part.getBoundingClientRect().width)
          .filter(Boolean);
        const reserved = Math.max(
          0,
          ...entry.offers.map((offered) => offered.reading.reserve),
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
      // The compact margin projection has no page rail. Dock every contributed entry even when a
      // positioned widget happens to leave enough local room for the absolute
      // prototype; that accident must not give one nested target a desktop posture.
      hangs: () => !readingRegionFor(targetFor(row.lfEntry)) && railStands(),
      // A wide row is hoisted into main's positioning context. If its live width no
      // longer fits the rail, move the same node beside its target before static flow
      // takes over; restore the hoist before measuring whether it fits again.
      float: (item) => {
        if (item.lfEntry?.offers.length || readingRegionFor(targetFor(item.lfEntry)))
          moveExternalHost(item, false);
      },
      dock: (item) => {
        if (item.lfEntry?.offers.length || readingRegionFor(targetFor(item.lfEntry)))
          moveExternalHost(item, true);
      },
      place: (item, column) => {
        const target = targetFor(item.lfEntry);
        if (!target || item.classList.contains("lf-docked")) return;
        const place = nav.contains(item) ? measureMargin(column) : null;
        const top = Math.max(0, shownBox(target).top - column.top);
        return () => {
          place?.();
          // Compare measured coordinates before CSS serialization rounds them. A
          // repeated fractional value must not mutate the row on every heartbeat.
          if (rowTops.get(item) !== top) {
            item.style.top = `${top}px`;
            rowTops.set(item, top);
          }
        };
      },
    };
  }

  function markerName(entry, index, anchored, position) {
    const choice = primaryReading(entry);
    const face = markerFace(entry).face;
    const count = choice?.items.length ?? 0;
    const readerContext = awaitingReader(choice?.items ?? [])
      ? readingContext(choice)
      : null;
    const reading = `${face.label}${count > 1 ? `s (${count})` : ""}${readerContext ? `, ${readerContext}` : ""}`;
    const subject =
      count === 1 && choice.items[0].workflowFace ? choice.text : entry.title;
    return `${reading}, ${index + 1} of ${anchored}${position == null ? "" : `, ${Math.max(0, Math.min(100, position))} percent down`}, ${spokenSubject(subject)}`;
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
    syncMarginTurn(row, awaitingReader(choice?.items ?? []));
    if (row.lfTakeFocus) {
      delete row.lfTakeFocus;
      (row.hidden ? document.body : row).focus({ preventScroll: true });
    }
  }

  function externalPerch(target, main, flow) {
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
    const target = targetFor(host.lfEntry);
    if (!main || !target || !railStands()) return;
    const perch = externalPerch(target, main, flow);
    let after = perch;
    for (const entry of pageInventory) {
      const candidate = hosts.get(entry.key);
      if (candidate === host) break;
      if (
        candidate?.isConnected &&
        externalPerch(targetFor(entry), main, flow) === perch &&
        candidate.parentNode === perch.parentNode
      )
        after = candidate;
    }
    if (after.nextSibling !== host) moveHost(host, () => after.after(host));
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
    const readerContext = awaitingReader(choice.items) ? readingContext(choice) : null;
    presentMarginEntry(
      node,
      marginEntry({
        key: `reading:${choice.key}`,
        icon: face.icon,
        label,
        accessibleLabel: `${label} for ${spokenSubject(entry.title)}${count > 1 ? `, ${count} items` : ""}${readerContext ? `, ${readerContext}` : ""}`,
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
    syncMarginTurn(node, awaitingReader(choice.items));
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

  // A widget frozen into a conversation belongs to that conversation's document,
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

    // A dynamic target can move one retained contribution between conversation seats.
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
    const flow = !railStands();
    measureMargin(mainRect)?.();
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
    const externalDocks = new Map();
    const nextWorkflowCarriers = new Set();
    let corePosition = 0;
    pageInventory.forEach((entry) => {
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
        registerMarginRow(host, markerOptions(host));
      } else updateMarginRow(host, markerOptions(host));
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
      if (entry.offers.length || readingRegionFor(targetFor(entry))) {
        keeps(host, "data-lf-external", "1");
        const perch = externalPerch(targetFor(entry), main, flow);
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
    // Another thread starts at its top; the same one re-rendering keeps the reader's place.
    const arriving = previewThreadItem !== (selected?.id ?? null);
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
    keeps(preview, "data-lf-thread", "");
    keeps(preview, "aria-label", `Conversation for ${spokenSubject(title)}`);
    previewNav.hidden = threadItems.length < 2;
    previewHead.hidden = true;
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
      const destination = replacement?.matches("button, textarea:not([disabled])")
        ? replacement
        : (replacement?.querySelector(".lf-conversation-thread") ??
          previewList.querySelector(".lf-conversation-thread") ??
          previewClose);
      destination.focus({ preventScroll: true });
    }
    if (focusedControl && document.activeElement !== focusedControl)
      (previewNav.hidden ? previewClose : focusedControl).focus({
        preventScroll: true,
      });
    placeThreadPreview();
    previewPlace.finish(hold);
  }

  function stepPreviewThread(step) {
    if (!previewEntry) return;
    const threadItems = previewEntry.items.filter((item) => item.kind === "comment");
    const current = threadItems.findIndex((item) => item.id === previewThreadItem);
    const next = Math.max(0, Math.min(threadItems.length - 1, current + step));
    if (next === current || !threadItems[next]) return;
    buildThreadCard(previewEntry, threadItems[next].id);
    const thread = previewList.querySelector(".lf-conversation-thread");
    if (thread) {
      thread.focus({ preventScroll: true });
      revealConversation(thread, thread);
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
      { nav: previewNav.hidden ? null : previewNav, close: previewClose },
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
        (item) =>
          item.kind === "comment" && Boolean(sourceItem(item).thread?.root.drawing),
      );
    highlight(drawingOnly ? null : (targetFor(entry) ?? null));
  }

  function showPreview(entry, button, retry = true, threadItem = null) {
    if (!entry || designModeActive()) return;
    if (forcedInlineKey && forcedInlineKey !== entry.key) forcedInlineKey = null;
    if (previewEntry && previewEntry.key !== entry.key) clearThreadTransition();
    previewEntry = entry;
    transferThreadCard(button);
    buildThreadCard(entry, threadItem);
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
        // focus remains a usable Page Map arrival if the browser still refuses the preview.
        if (!(error instanceof DOMException) || error.name !== "InvalidStateError")
          throw error;
        if (retry)
          requestAnimationFrame(() => {
            if (previewMarginEntry === button && button.isConnected)
              showPreview(entry, button, false);
          });
        else answerThreadPreviewPosition(false);
      } finally {
        previewShowing = false;
      }
    }
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
      if (previewList.querySelector(".lf-conversation-thread"))
        deferThreadPreviewFocus(positioned, () => {
          if (previewEntry?.key !== entry.key) return;
          const thread = previewList.querySelector(".lf-conversation-thread");
          if (!thread) return;
          thread.focus({ preventScroll: true });
          revealConversation(thread, thread);
        });
    };
    open();
  }

  function closePreview(returnFocus = false) {
    clearThreadTransition();
    const button = previewMarginEntry;
    // A cluster the walk unfolded to hang the view from folds with the view; one the
    // reader unfolded stays, and is its own rung.
    const forcedOptionsKey = forcedInlineOptionsKey;
    pinnedKey = null;
    forcedInlineKey = null;
    forcedInlineOptionsKey = null;
    previewEntry = null;
    previewThreadItem = null;
    previewMarginEntry = null;
    previewFocusPending = null;
    answerThreadPreviewPosition(false);
    resetThreadPreviewPosition();
    if (preview.matches(":popover-open")) preview.hidePopover();
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
    }
    paintKeys();
  }

  // The conversation view, for the owners that open and close it from outside. What
  // takes it off again is the Page Map's own Escape step, read off the card standing
  // rather than off whatever put it up. The view's own close control, pressed by
  // pointer, hands focus to the margin entry the view hangs from, since that is where
  // the pointer is.
  const inlineThreadView = {
    showing: () =>
      preview.matches(":popover-open") && preview.hasAttribute("data-lf-thread"),
    dismiss: () => closePreview(),
  };

  // The card, which is a native layer the reader is either inside or standing at the
  // entry of. It is hoisted into the chrome while anchored to a passage, so it counts as
  // chrome for which surface holds focus and as page-anchored for where the reader
  // lands, and one press closes it.
  function keyboardRung({ atFocus = true } = {}) {
    const active = focused();
    const host = closestAcross(active, "[data-lf-margin-for]");
    if (
      !preview.matches(":popover-open") ||
      (atFocus &&
        !preview.contains(active) &&
        !(previewMarginEntry && host?.contains(previewMarginEntry)))
    )
      return null;
    return {
      root: preview,
      does: "Dismiss the conversation view",
      says: "dismiss conversation",
      // Where it lands turns on whether a level of the reader's own stands under it. A
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
      // Hiding the popover hands focus back to the control that opened it, which after
      // a walk is a control in the cluster the card has since left. That return is
      // transit rather than the reader arriving, and the landing below moves them on
      // from it in the same press, so the cluster is told not to read it as their
      // leaving — otherwise one press would take the card and the cluster together.
      out: () => {
        const entry = previewMarginEntry?.lfEntry;
        const standing = Boolean(
          entry &&
          expandedOptionsKey === entry.key &&
          expandedOptionsKey !== forcedInlineOptionsKey &&
          optionsRung(),
        );
        const wasSettlingOptionsFocus = settlingOptionsFocus;
        settlingOptionsFocus = true;
        try {
          closePreview(standing);
          if (!standing) letGo();
        } finally {
          settlingOptionsFocus = wasSettlingOptionsFocus;
        }
      },
    };
  }

  // The cluster the reader unfolded is page-side state rather than a layer of the card,
  // so it answers from the ladder wherever they are standing — the card they opened from
  // it lands them out on the page, and the fold would otherwise be reachable only by
  // Tabbing back into the margin. It comes off after anything standing over the page and
  // before the page itself, beside the selection, and lands on the entry it hangs from,
  // which is the container it is part of.
  //
  // Once a contribution is engaged, its complete and escape controls are open because of
  // semantic state rather than because the reader disclosed the secondary tray. That
  // state consumes the earlier disclosure step: Escape leaves the action the reader is
  // standing on instead of first pretending to close controls that remain open by
  // contract.
  function optionsRung() {
    const host = hosts.get(expandedOptionsKey);
    if (!host?.lfEntry || host.lfEntry.key !== expandedOptionsKey) return null;
    if (entryEngaged(host.lfEntry)) return null;
    return {
      root: host,
      does: "Fold the secondary page actions",
      says: "close options",
      out: () => setOptionsOpen(host.lfEntry, false, { returnFocus: true }),
    };
  }
  pageRung("margin options", optionsRung);

  // The card is a native layer over the page, so this scope stands ahead of the reaction
  // and navigation modes, as the surface's old local listener did, without another
  // keydown listener of its own.
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

  function openInlineThread(id, { transition = null, onPositioned = null } = {}) {
    const itemId = marginThreadItem(threadList().find((t) => t.root.id === id));
    const entry = pageInventory.find((candidate) =>
      candidate.items.some((item) => item.id === itemId),
    );
    if (!entry || designModeActive() || panelIsOpen()) return null;
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
    const initiallyPositioned = showPreview(entry, button, true, itemId);
    const item = [...previewList.children].find(
      (candidate) => candidate.lfMarginItem === itemId,
    );
    item?.scrollIntoView({ behavior: scrollBehavior(), block: "nearest" });
    const thread = item?.querySelector(".lf-conversation-thread") ?? null;
    const positioned = transition
      ? scheduleThreadTransition(transition, entry)
      : initiallyPositioned;
    if (thread && onPositioned)
      deferThreadPreviewFocus(positioned, () => {
        const current = [...previewList.children]
          .find((candidate) => candidate.lfMarginItem === itemId)
          ?.querySelector(".lf-conversation-thread");
        if (current) onPositioned(current);
      });
    return thread;
  }

  // A route that starts on the page stays on the page while that thread has an inline
  // destination. Widget-local surfaces are already rendered, while a margin-projection thread is
  // opened on demand. Threads remains the complete fallback for a detached or otherwise
  // unaddressable conversation. Callers choose only the landing within the conversation;
  // this function owns the surface choice so a mark, its accessibility note, and t/T
  // cannot drift into different policies. The margin card always lands on the thread
  // itself.
  //
  // A press on marked words passes `travel: false`: the words are already under the
  // reader's hand, and centring them moves everything the reader was looking at. The
  // card needs no trip, since placeThreadPreview keeps it inside the viewport.
  function openPageThread(id, { focus = "reply", travel = true } = {}) {
    if (!panelIsOpen()) {
      const local = focusSurface(id, { focus });
      if (local) {
        closePreview();
        if (travel) scrollToThread(id);
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
  // moved the rows, and the card follows in that same frame, so a reader never sees it
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
    const conversations = previewList.querySelectorAll(
      ".lf-margin-thread .lf-conversation-thread",
    );
    const pending = previewFocusPending?.key === previewEntry.key;
    if (!pending && active !== previewMarginEntry) return null;
    return conversations.length === 1 ? conversations[0] : null;
  };

  // A live revision replaces the browser document, so DOM identity cannot carry a
  // reader standing in retained margin chrome. Carry the target and margin-entry keys
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
      preview: preview.matches(":popover-open") ? { thread: previewThreadItem } : null,
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
      const positioned = showPreview(entry, button, true, standing.preview.thread);
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
    reserveRail();
    onPaper.addEventListener("change", () => {
      if (!onPaper.matches) renderMargin.refresh();
    });
    previewClose.onclick = () => closePreview(true);
    previewPrevious.onclick = () => stepPreviewThread(-1);
    previewNext.onclick = () => stepPreviewThread(1);
    preview.addEventListener("toggle", (event) => {
      if (event.newState !== "closed") return;
      for (const reply of previewList.querySelectorAll("textarea"))
        reply.lfCollapseReply?.();
      clearThreadTransition();
      if (!previewEntry) return;
      pinnedKey = null;
      forcedInlineKey = null;
      forcedInlineOptionsKey = null;
      previewEntry = null;
      previewThreadItem = null;
      previewMarginEntry = null;
      previewFocusPending = null;
      answerThreadPreviewPosition(false);
      resetThreadPreviewPosition();
      refreshHighlight();
      for (const row of rows.values())
        syncReadingRelation(row, primaryReading(row.lfEntry));
      for (const reading of readingMarginEntries.values())
        syncReadingRelation(reading, reading.lfChoice);
      paintKeys();
    });
    watchProjection(document.body, renderMargin);
    document.addEventListener("lf-comparison", renderMargin);
    document.addEventListener("lf-margin-layout", () => {
      placeThreadPreview();
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
        if (!preview.contains(event.target)) scheduleThreadPreviewPosition(true);
      },
      { capture: true, passive: true },
    );
    window.addEventListener("resize", () => {
      scheduleThreadPreviewPosition();
      schedulePostureRender();
    });
    renderMargin();
    // The rail stands or falls with the shell, which a resize and a strip taken or
    // given back both move. The repaint that follows a flip waits a frame, since this
    // observer must not move body itself.
    let railStood = railStands();
    new ResizeObserver(() => {
      const stands = railStands();
      if (stands === railStood) return;
      railStood = stands;
      changePosture(stands);
    }).observe(document.body);
    chromeRoot.append(nav, preview);
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
    activeInlineThread,
    captureStanding,
    restoreStanding,
    mount,
  };
}
