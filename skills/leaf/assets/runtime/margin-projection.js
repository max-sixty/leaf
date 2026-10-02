/* The page-side projection of activity attached to exact document targets.

   This module combines registered contributions with core readings such as Threads,
   Asks, version changes, delivery receipts, and work claims. It reconciles one cluster
   and the inline thread card per target, and one more cluster for each thread a
   pointing gesture stood at a row inside its target (pointed-place.js), then supplies
   the complete target projection to `page-map-dialog.js`. `margin-entries.js` owns the
   public control grammar and contribution registry; `margin-cluster-view.js` owns
   retained control materialization and Lit child order; `margin-layout.js` owns where
   each row stands: its lane, its posture in the rail or as a pin, and the packing that
   keeps rows clear of one another.

   `margin-model.js` derives the immutable inventory and cluster selection; its public
   records carry target coordinates, captured contribution readings, and generated facts.
   This adapter keeps target nodes and generated-reading callbacks. The contribution
   registry keeps registrations and command scopes.
   `margin-map-model.js` derives the complete searchable Page Map from the same inventory.
   A model never reads back identity from a control or carries a native control.

   Keyboard and pointer expansion share one state. Focus arrival through Tab unfolds a
   compact cluster, Left and Right walk it, and Escape folds only the layer that gesture
   opened. A pin the layout found no room for stands folded to its toggle
   (`standsFolded`, margin-model.js's `canFold`), and the same state opens it. Page Map
   and Go-to arrivals activate the exact visible control; they do not choose another
   action for the user.

   The thread card stands where the comment box its thread began in stood, by the one
   rule `comment-placement.js` states for both: beside what it is about, level with the
   words it quotes or the row a pointing gesture named, where that room takes the card's
   minimum measure, and past its cluster where the room beyond takes that too;
   otherwise under or over what it is about. A thread with no target stands by its
   cluster. The card is as wide as its thread up to the room its side gives, and keeps
   its height in every case; one too tall for its spot slides inside the boundary
   rather than shrinking. This module supplies what the card stands by, the visible
   boundary — the reading region or the viewport under the banner and over the bottom
   chrome — and the card's size for the room; Floating UI (floating.js) places it and
   follows what moves its target. A card leaving with what it is about passes under the
   chrome, which stacks over it, and a reading region clips it at its edge. The card
   contains the complete inline thread view; the Threads panel remains the complete
   index and takes over when already open. Once placed, the card keeps its side and
   holds one edge at its distance from the line it stands level with (`previewHold`):
   its top, so a turn arriving or the reply gaining a line leaves the transcript and the
   reply's first lines where the user reads them, and the reply's foot and Send move
   down a line per wrap; its foot, with the reply row on it, where a turn joins the
   transcript while the user drafts, and where the card stands over what it is about
   and is read. Opening it on another thread lets it choose its spot afresh. A scroll
   never closes it: the card leaves with what it is about and comes back with it.

   The reply editor grows with its words, the card downward until its foot meets the
   boundary's and upward from there, until the card fills the boundary; then the
   transcript above it gives up its room to that growth down to a few lines of the turn
   being answered, and only then does the editor scroll.

   The card is margin chrome, not a native layer: it shows the threads of the target the
   user stands at, from the target, its cluster, or the card itself, so standing on an
   element and reading its thread are one place rather than two layers contending
   for focus and presses. Keyboard arrival at a commented element puts the card up
   beside it; standing elsewhere on the page, letting go (`declareRelease`), or pressing
   outside the card, its target, and its cluster takes it down (`followStanding`). Escape from inside the
   card lands on its target, and so does a send from it (`cardTarget`), with the card
   still up showing what was sent. With Threads open the list's one expanded thread plays the
   card's part: the same arrival expands the target's thread there (`accompanyThread`).
   The rest of the runtime reads both directions from here: `threadHere` gives the thread
   a user standing on the page is at, and the side this owner declares to
   standing-target.js gives the page target a card, cluster, or panel thread stands for.

   Placing the card changes its geometry and nothing inside it. The user's place in
   its transcript is the messages' own scroll, held through reflow. The metadata and
   reply row stand outside that scroll. A landing, send, or
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
import { replyHasWords } from "./thread/replies.js";
import { afterScript, cancelRender, nextRender } from "./rendering.js";
import {
  KINDS,
  excerptWords,
  labelWords,
  spokenSubject,
} from "./margin-entry-model.js";
import {
  THREAD_CARD,
  mountMarginLayer,
  marginSpot,
  registerMarginRow,
  scheduleMarginEntryLabels,
  scheduleMarginLayout,
  standsFolded,
  unregisterMarginRow,
} from "./margin-layout.js";
import {
  marginContributionEntries,
  presentingMarginContributions,
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
  entryEngaged,
  choosePrimary,
  readingKey,
  readingChoices,
  primaryReading,
  threadReading,
  entryHasMarginHost,
  contributionItem,
  optionsOffered,
  canFold,
  markerFace,
  readingFace,
  readingLabel,
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
import { pointBand, standingPoint } from "./pointed-place.js";
import {
  TEXT_FIELD,
  declareRelease,
  focusDestination,
  handBack,
  holdFocus,
  letGo,
  placeChrome,
} from "./focus.js";
import { closeControl, el, offer } from "./widget-elements.js";
import { keeps, keepsHidden, keepsText, layoutPx } from "./keeps.js";
import { setChildren } from "./dom-children.js";
import { PRESS } from "./keyboard/bindings.js";
import { beginWalk, listWalkPosition, rowWalk } from "./walk-position.js";
import { ago, clocked } from "./presence.js";
import { runtime } from "./context.js";
import {
  containingReadingRegionFor,
  effectiveScroller,
  readingRegionFor,
  registerReadingRegion,
  shownRegionBounds,
} from "./reading-regions.js";

import { focused, keys, paintKeys } from "./keyboard/scopes.js";
import { pageCommand, pageRung, pageScope } from "./keyboard/register.js";
import { declareOffFlowSurface } from "./off-flow.js";
import {
  annotationsHidden,
  setAnnotationsHidden,
  watchAnnotations,
} from "./annotation-layer.js";
import { repaint } from "./repaint.js";
import { chromeRoot } from "./chrome.js";
import { versionBtn } from "./version-picker.js";
import { motion, scrollBehavior } from "./motion.js";
import { declareSide, placeOf } from "./standing-target.js";
import { closestAcross, elementById, inChrome } from "./passages.js";
import { addressableLabel, addressableWord, visualAt } from "./anchor-resolution.js";
import { paintTrace } from "./target-paint.js";
import { updateSequence } from "./updates.js";
import { threadList } from "./thread/state.js";
import { threadKey, turns } from "./thread/model.js";
import { whenDocumentPresented } from "./semantic-state.js";

import { projectionOrigins } from "./projection/model.js";
import { authoredStates } from "./projection/authored.js";
import { currentProjection } from "./projection/state.js";
import { notice } from "./notifications.js";
import { iconElement } from "./icons.js";
import { claimed, focusSurface, surfaceFocusTarget } from "./thread/surfaces.js";
import { anchorLabel } from "./thread/messages.js";
import { createMarginClusterViews } from "./margin-cluster-view.js";

import { outlineSubjectFor, pageOutline } from "./thread/placement.js";
import { bannerControlDoor } from "./banner-toolbar.js";
import { coarsePointer } from "./pointer.js";
import {
  COMMENT_GAP,
  cardMeasure,
  cardMinimum,
  commentBoundary,
  commentPlacement,
  makeRoom,
} from "./comment-placement.js";
import { shownExtent, shownParts, shownRect, skipped } from "./geometry.js";
import { clamp, union } from "./rect.js";
import { passageBox } from "./resolved-target.js";
import { floatingPlacement, floatingUi, heldByWindow } from "./floating.js";
import { placeKeeper } from "./user-place.js";
import {
  isLiveWorkflow,
  isPageWidgetWorkflow,
  isWorkflowProgress,
  strongestWorkflow,
  threadAttention,
  workflowLabel,
} from "./thread/workflow.js";
import { renderedParent, shadowHost, under } from "./shadow.js";
import { retainUserIntent } from "./user-intent.js";

// A margin card's reply box.
const REPLY_BOX = `.lf-say ${TEXT_FIELD}`;

export function createMarginProjection({
  panel,
  accompaniedThread,
  accompanyThread,
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
    const host = shadowHost(target.getRootNode());
    // IDs and sibling paths are scoped to a shadow root. Prefix them with the host's
    // own stable path so two instances of the same shadow template stay distinct,
    // while a live-version replacement at the same authored coordinate can still
    // retain its marker and preview focus.
    const prefix = host ? `${targetPath(host)}/shadow/` : "";
    if (target.id) return `${prefix}id:${target.id}`;
    const steps = [];
    let from = "path:";
    for (let node = target; node;) {
      // A projected datum's node is generated, so it stands at no authored position
      // among its siblings; it is named by its projection and key, which also survive a
      // renderer replacing it (projection/data.js).
      if (node.dataset?.lfProjection && node.hasAttribute("data-lf-datum")) {
        from = `datum:${node.dataset.lfProjection}/${node.dataset.lfDatum}:`;
        break;
      }
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
    return `${prefix}${from}${steps.reverse().join("/")}`;
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
  // The row a pointed entry stands by (groupFor), as anchor paint last placed it, while
  // it still stands inside its target. Where the entry stands (`entryPlace`) is that
  // row, else the target: every reading of where an entry is on the page, as against
  // what it is about, asks this.
  const points = new Map();
  const entryPoint = (entry) =>
    entry ? standingPoint(targetFor(entry), points.get(entry.key)) : null;
  const entryPlace = (entry) => entryPoint(entry) ?? targetFor(entry);
  // A pointed row is named by its words as the page reads them, cells and blocks apart.
  const pointName = (words) => {
    const excerpt = words && excerptWords(words, 32);
    return excerpt ? `“${excerpt}”` : null;
  };
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
  preview.id = THREAD_CARD;
  preview.hidden = true;
  preview.setAttribute("role", "dialog");
  const previewOpen = () => !preview.hidden;
  const previewClose = closeControl({
    name: "Dismiss thread view",
    title: "Dismiss thread view (Esc)",
    className: "lf-margin-preview-close",
  });
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
  let previewTranscript = null;
  let previewPlace = null;
  let stopPreviewRegion = null;
  // The card's transcript is re-rendered on every reading of its thread; a message holds
  // the user's place in it under the event id it is rendered with (user-place.js).
  function syncPreviewTranscript() {
    const transcript = previewList.querySelector(".lf-thread-transcript");
    if (transcript === previewTranscript) return;
    stopPreviewRegion?.();
    stopPreviewRegion = null;
    previewTranscript = transcript;
    previewPlace = transcript
      ? placeKeeper(transcript, {
          items: ".lf-page-thread-msg[data-event]",
          identity: (message) => message.dataset.event,
        })
      : null;
    if (previewRegionMounted && transcript)
      stopPreviewRegion = registerReadingRegion({
        id: THREAD_CARD,
        host: preview,
        body: transcript,
      });
  }
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
        forgetThreadPreviewPlacement();
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
  // Selected from the published workflows rather than gathered from the items, whose
  // order is the margin's, so the strongest is the server's.
  const workflowReceipt = (items) => {
    const receipts = new Set(items.map((item) => item.workflowReceipt?.id));
    return strongestWorkflow(
      workflows().filter(
        (workflow) => receipts.has(workflow.id) && isWorkflowProgress(workflow),
      ),
    );
  };
  const rows = new Map();
  const moreMarginEntries = new Map();
  const readingMarginEntries = new Map();
  const hosts = new Map();
  const inlineHosts = new Map();
  let optionsOrdinal = 0;
  let pageInventory = [];
  // How far down the page each entry's target stands, in whole percent, as its marker's
  // name last said. A target in skipped content (a tab not chosen) stands nowhere down
  // the page, and asking would force that content's style and layout (`skipped`).
  let spokenPositions = [];
  // The column's size the positions were measured against.
  let spokenBasis = null;
  // Geometry is one read-only batch after every row has reconciled. Reading a target
  // between two marker writes forced one full document layout per Page Map entry —
  // including on the two-second heartbeat. Every name is then written together.
  function nameMarkers(positions) {
    spokenPositions = positions;
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
  }
  // Down the margin's column, which is `main` or, on a page without one, the body, as
  // the margin's layout reads it (margin-layout.js).
  const marginColumn = () => document.querySelector("main") || document.body;
  function readSpokenPositions(
    inventory,
    mainRect = marginColumn().getBoundingClientRect(),
    mainHeight = marginColumn().scrollHeight,
  ) {
    spokenBasis = mainRect && { width: mainRect.width, height: mainHeight };
    return inventory.map((entry) =>
      targetFor(entry) &&
      !skipped(targetFor(entry)) &&
      !readingRegionFor(targetFor(entry)) &&
      mainRect &&
      mainHeight
        ? Math.round(
            ((entryPlace(entry).getBoundingClientRect().top - mainRect.top) /
              mainHeight) *
              100,
          )
        : null,
    );
  }
  let previewEntry = null;
  let previewThreadItem = null;
  let previewLatest = null;
  let previewMarginEntry = null;
  let transferThreadFocus = false;
  let pinnedKey = null;
  let forcedInlineKey = null;
  let forcedInlineOptionsKey = null;
  let expandedOptionsKey = null;
  // Whether an entry's pin stands folded is the layout's answer (`standsFolded`); the
  // gesture that opens any options opens a folded one.
  const folded = (entry) => standsFolded(hosts.get(entry.key));
  let refoldQueued = false;
  // An explicit mode can focus one contribution inside the target's existing cluster.
  // The rail then shows that owner's complete control set without spending margin entries on
  // standing readings or unrelated actions; Page Map still reads the whole entry.
  let expandedOptionsOwner = null;
  let hoveredHost = null;
  let settlingOptionsFocus = false;
  let suppressingOptionsArrival = false;
  let highlighted = null;
  let highlightFrame = 0;
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
      keeps(
        control,
        "aria-expanded",
        opensInline ? previewMarginEntry === control : null,
      );
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
  let previewPositionWaiters = [];
  let previewFocusPending = null;
  // The side the card holds (comment-placement.js); the offsets of its top and foot from
  // the line it stands level with, and its transcript's height, when it last stood
  // (`placeThreadPreview`); and whether a scroll has carried it out of the window with
  // what it is about.
  const previewSide = commentPlacement();
  let previewHold = null;
  let previewAway = false;
  function answerThreadPreviewPosition(positioned) {
    const waiters = previewPositionWaiters;
    previewPositionWaiters = [];
    for (const resolve of waiters) resolve(positioned);
  }
  const threadPreviewPositioned = () =>
    new Promise((resolve) => previewPositionWaiters.push(resolve));
  // A placement lands in the microtasks after it starts, before the frame paints. One
  // that cannot land yet — its owner not connected, no room — is answered by a later
  // placement, or by the close that abandons it.
  const placedThreadPreview = () => {
    placeThreadPreview();
    return threadPreviewPositioned();
  };
  // Floating UI follows what moves the card's target: its scroll containers, the window
  // and visual viewport, and the target and card changing size or moving.
  const previewPlacement = floatingPlacement({
    floating: preview,
    update: () => scheduleThreadPreviewPosition(),
  });
  // A card that stays open keeps its spot while its next placement is worked out from
  // nothing it held: the edge it was held by, the frame queued, and any answer in flight
  // are dropped, and the placement rewrites only what moved. A card with no spot yet is
  // unplaced, and chrome.css keeps an unplaced card unseen and out of reach.
  function forgetThreadPreviewPlacement() {
    previewPlacement.supersede();
    cancelRender(previewPositionFrame);
    previewPositionFrame = 0;
    previewSide.forget();
    previewHold = null;
    previewAway = false;
  }
  function unplaceThreadPreview() {
    forgetThreadPreviewPlacement();
    previewPlacement.stop();
    delete preview.dataset.lfThreadPlacement;
    preview.style.removeProperty("clip-path");
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

  // The card stands in the comment box's boundary (comment-placement.js), within its
  // target's reading region when it has one. That is the visible viewport, so a reply
  // editor stays above a phone's software keyboard.
  const regionBounds = (target) => {
    const region = containingReadingRegionFor(target);
    return region ? shownRegionBounds(region) : null;
  };
  // A scroll moves the held edge and with it the room to the boundary, so the cap the
  // geometry asks for moves with every scroll, and every write during a scroll costs a
  // repaint (keeps.js) while the card's far edge, written from the
  // main thread, trails the scroll that carries the rest of it. So a scroll leaves the
  // cap the card wears: a card short of both caps renders the same under either, and a
  // card at its cap takes a new one only once its contents change, when a turn arrives
  // or a draft grows. If the complete thread now fits, the cap grows once to let the
  // transcript leave scrolling behind. A cap that would cut the card it stands on is
  // always taken. Both
  // are in the card's positioning space, as offsetHeight is.
  let wornContent = null;
  const threadCardContent = () =>
    [previewTranscript, ...previewList.querySelectorAll(REPLY_BOX)].reduce(
      (sum, box) => sum + (box ? box.scrollHeight - box.clientHeight : 0),
      previewList.scrollHeight,
    );
  function measureThreadCard(room, cap) {
    preview.style.setProperty("--lf-thread-width", `${room}px`);
    const worn = parseFloat(preview.style.getPropertyValue("--lf-thread-max-height"));
    const height = preview.offsetHeight;
    const content = threadCardContent();
    const atCap = height >= worn - 0.5;
    const overflow = previewTranscript
      ? previewTranscript.scrollHeight - previewTranscript.clientHeight
      : 0;
    const fitsUnscrolled = overflow > 0.5 && height + overflow <= cap;
    if (
      !(worn >= 0) ||
      cap < height - 0.5 ||
      (atCap && content !== wornContent) ||
      fitsUnscrolled
    ) {
      preview.style.setProperty("--lf-thread-max-height", `${cap}px`);
      wornContent = content;
    }
    fitThreadCardEditors();
    return preview.getBoundingClientRect().height;
  }
  // The thread's complete turns, without the reply row under them: what an arriving or a
  // sent turn changes and a new line of the reply does not. Unrounded, since the row's
  // height is fractional and a rounded difference moves with it.
  const boxHeight = (node) => node.getBoundingClientRect().height;
  function measureTranscript() {
    return [...previewList.querySelectorAll(".lf-margin-thread")].reduce(
      (sum, thread) =>
        [...thread.querySelectorAll(".lf-say")].reduce(
          (turns, row) => turns - boxHeight(row),
          sum +
            boxHeight(thread) +
            [...thread.querySelectorAll(".lf-thread-transcript")].reduce(
              (overflow, transcript) =>
                overflow + transcript.scrollHeight - transcript.clientHeight,
              0,
            ),
        ),
      0,
    );
  }
  // The reply takes the room below the transcript without carrying the words above
  // it. A transcript that cannot fit beside even one editor line scrolls itself;
  // typing then uses the remaining room and scrolls inside the editor.
  function fitThreadCardEditors() {
    const listRoom =
      parseFloat(preview.style.getPropertyValue("--lf-thread-max-height")) -
      (preview.offsetHeight - previewList.clientHeight);
    for (const input of previewList.querySelectorAll(REPLY_BOX)) {
      const row = input.closest(".lf-say");
      const thread = row.closest(".lf-page-thread");
      const style = getComputedStyle(thread);
      const box = getComputedStyle(input);
      const line = parseFloat(box.lineHeight);
      const furniture = row.offsetHeight - input.offsetHeight;
      const inset = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
      // Reserve the turns' own content, rather than the room the last-sized editor
      // left them. After a resize that editor can exceed the new card's height.
      const answered =
        (thread.querySelector(".lf-thread-root-meta")?.offsetHeight ?? 0) +
        thread.querySelector(".lf-thread-transcript").scrollHeight;
      const oneLine =
        input.offsetHeight -
        input.clientHeight +
        line +
        parseFloat(box.paddingTop) +
        parseFloat(box.paddingBottom);
      const room = Math.max(oneLine, listRoom - answered - furniture - inset);
      input.style.setProperty("--lf-thread-editor-room", `${room}px`);
    }
  }

  // The row the card hangs from where its thread has no target to stand by. A row the
  // rail has no room for is withheld and has no box; it stands by the row's target
  // instead, at the row inside it the cluster would stand level with (pointed-place.js).
  function threadCardCluster() {
    const row =
      previewMarginEntry.closest("[data-lf-margin-for]") ?? previewMarginEntry;
    if (row.checkVisibility()) return row;
    return entryPlace(previewEntry) ?? row;
  }
  // The thread the card shows, and the first line of the words it quotes, if it does.
  const threadCardThread = () => {
    const item = previewEntry?.items.find(
      (candidate) => candidate.id === previewThreadItem,
    );
    return item ? sourceItem(item)?.thread : null;
  };
  // What the card stands by, read as the comment box reads it (comment-placement.js):
  // its target's shown box, or the row a pointing gesture named in it, and the line it
  // stands level with, a quoted passage's first. A thread with no target stands by its
  // cluster.
  function threadCardPlace() {
    const target = targetFor(previewEntry);
    const point = entryPoint(previewEntry);
    if (!target) {
      const cluster = threadCardCluster();
      const box = cluster.getBoundingClientRect();
      return { element: cluster, clear: box, extent: box, row: box.top, margin: null };
    }
    const clips = new Map();
    const shown = union(
      shownParts(target)
        .map((part) => shownRect(part, clips))
        .filter(Boolean),
    );
    // A pointed row is small enough to stand by whole, so the card leaves with it; a
    // target stands by what shows of it, as the comment box does.
    const whole = shownExtent(target) ?? target.getBoundingClientRect();
    const extent = point ? pointBand(whole, point) : whole;
    const clear = point ? extent : (shown ?? whole);
    const thread = threadCardThread();
    const words =
      !point && thread?.anchor?.quote ? passageBox(placedAt(thread.id)) : null;
    return {
      element: point ?? target,
      clear,
      extent,
      row: (words ?? clear).top,
      margin: marginSpot(target, point),
    };
  }
  const THREAD_SIDES = { right: "right", left: "left", bottom: "below", top: "above" };
  // Where the card stands is comment-placement.js's rule, the one the comment box stands
  // by, so a sent comment's card opens where its box stood. Beyond it the card holds its
  // place as its thread changes: it keeps the top while the user reads or writes a new
  // line, and its foot, with the reply row on it, while a turn joins the transcript as
  // the user drafts, whether one arrives or they sent it, so the box they type in stays
  // put and the transcript rises by the turn. A card over its target grows up from its
  // foot. The boundary caps the card at the room from its held edge. Drafting grows the
  // editor into that room, then scrolls its words rather than carrying the card.
  function placeThreadPreview() {
    if (!previewOpen() || !previewMarginEntry?.isConnected) return false;
    const placement = previewPlacement.begin();
    const stillCurrent = () =>
      previewPlacement.current(placement) &&
      previewOpen() &&
      previewMarginEntry?.isConnected;
    const place = threadCardPlace();
    // Floating UI follows what moves what the card stands by, so a card with no room yet
    // is placed once something gives it some.
    const watch = (ui) =>
      previewPlacement.watch(
        place.element,
        {
          contextElement: place.element,
          getBoundingClientRect: () => threadCardPlace().clear,
        },
        ui.autoUpdate,
      );
    const boundary = commentBoundary({ region: regionBounds(targetFor(previewEntry)) });
    if (!boundary.width || !boundary.height) {
      void floatingUi().then((ui) => stillCurrent() && watch(ui));
      return false;
    }
    const replyEditor = previewList.querySelector(REPLY_BOX);
    // Drafting is standing anywhere in the reply's row, Send included, holding words in
    // it, or a send of the user's still on its way. The send takes the user out of the
    // box it empties (`landSent`), and the turn it adds must not move the reply row or
    // Send from under the press.
    const newest = [
      ...(replyEditor
        ?.closest(".lf-page-thread")
        ?.querySelectorAll(".lf-page-thread-msg") ?? []),
    ].at(-1);
    const drafting = Boolean(
      replyEditor?.checkVisibility() &&
      (replyEditor.closest(".lf-say").contains(document.activeElement) ||
        replyEditor.value !== "" ||
        newest?.matches('.user[aria-busy="true"]')),
    );
    const scroller = effectiveScroller(
      containingReadingRegionFor(place.element) ?? place.element,
    );
    const { side, fresh } = previewSide.choose({
      clear: place.clear,
      extent: place.extent,
      boundary,
      minimum: { width: cardMinimum() },
      scroller,
      coarse: coarsePointer.matches,
    });
    if (fresh) {
      previewHold = null;
      if (
        (side === "top" || side === "bottom") &&
        makeRoom(
          side,
          place.clear,
          place.extent,
          preview.getBoundingClientRect().height,
          boundary,
          scroller,
        )
      ) {
        previewSide.scrolled();
        return placeThreadPreview();
      }
    }
    const transcript = measureTranscript();
    const turned = previewHold && Math.abs(transcript - previewHold.transcript) > 0.5;
    const held = drafting ? (turned ? "foot" : "top") : side === "top" ? "foot" : "top";
    void floatingUi()
      .then((ui) => {
        if (!stillCurrent()) return null;
        const { reference, placement, middleware, heldIn } = previewSide.options(ui, {
          clear: place.clear,
          row: place.row,
          margin: place.margin,
          boundary,
          minimum: { width: cardMinimum() },
          fit({ width, scale }) {
            const room = Math.min(cardMeasure(), width);
            preview.style.setProperty(
              "--lf-thread-min-width",
              `${Math.min(cardMinimum(), room)}px`,
            );
            // Choosing its spot, the card is capped by the boundary alone, and slides
            // inside it rather than shrinking. Held, it has the room from its held edge
            // to the boundary's far edge, with that edge inside the boundary as far as
            // its last height puts it. This cap holds for reading and writing alike:
            // a growing editor uses the room below its top, then scrolls internally.
            const last = previewHold
              ? Math.min(previewHold.foot - previewHold.top, boundary.height)
              : 0;
            const edge =
              previewHold &&
              previewSide.line(place.clear, place.row) + previewHold[held];
            const cap = !previewHold
              ? boundary.height
              : held === "foot"
                ? clamp(edge, boundary.top + last, boundary.bottom) - boundary.top
                : boundary.bottom - clamp(edge, boundary.top, boundary.bottom - last);
            measureThreadCard(room, cap / scale.y);
          },
          hold: () => previewHold && { [held]: previewHold[held] },
        });
        watch(ui);
        return previewPlacement.position(
          ui.computePosition,
          { contextElement: place.element, getBoundingClientRect: () => reference },
          { placement, middleware },
          (answer) =>
            heldIn(answer) &&
            heldByWindow(
              answer.y,
              answer.y + answer.middlewareData.held.height,
              COMMENT_GAP,
            )
              ? "window"
              : "page",
          place.element,
        );
      })
      .then((position) => {
        if (!position || !stillCurrent()) return;
        // The spot the rule stood the card at before the boundary shifted it in, so a
        // card opened low in the window rises back to it once a scroll gives it room.
        const { scale, spot } = previewSide.landed(position);
        // The transcript this placement answered, so a turn that joined it while the
        // placement was worked out is one the next placement still sees join.
        previewHold = { ...spot, transcript };
        // An unchanged declaration is the browser's own no-op, and `keeps` is the rest's.
        previewPlacement.stand(position);
        const card = preview.getBoundingClientRect();
        previewAway = card.bottom <= boundary.top || card.top >= boundary.bottom;
        // Leaving with what it is about, the card passes under the chrome, which stacks
        // over it, and a reading region it stands in cuts it at the region's edge as it
        // cuts the words.
        const region = boundary.inRegion;
        if (region) {
          const inset = [
            (region.top - card.top) / scale.y,
            (card.right - region.right) / scale.x,
            (card.bottom - region.bottom) / scale.y,
            (region.left - card.left) / scale.x,
          ];
          preview.style.clipPath = `inset(${inset.map(layoutPx).join(" ")})`;
        } else preview.style.removeProperty("clip-path");
        keeps(preview, "data-lf-thread-placement", THREAD_SIDES[side]);
        answerThreadPreviewPosition(true);
      })
      .catch((error) => {
        // A card Floating UI cannot place would stand open and unseen, so it closes, as
        // the comment box withdraws, and the failure surfaces.
        if (stillCurrent()) closePreview();
        throw error;
      });
    return true;
  }
  function scheduleThreadPreviewPosition() {
    if (previewPositionFrame) return;
    previewPositionFrame = nextRender(() => {
      previewPositionFrame = 0;
      placeThreadPreview();
    });
  }
  // A viewport posture change can replace the focused full thread with its
  // compact action. Reconcile after resize delivery so the browser can finish its
  // own focus and popover bookkeeping before that node changes shape. Panel and drawer
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

  // One group per target, and one more for each row inside it that pointing gestures
  // stood threads at (pointed-place.js): those threads stand there together, and
  // everything else about the target (its other threads, an Ask's marker, a widget's
  // actions) keeps the target's own row. `pointed` is `{ key, element, words }`: the
  // row's key, which its first comment gave it and later ones share, the element it is,
  // and its words as the page reads them, which name it.
  function groupFor(groups, target, pointed = null) {
    const slot = pointed ? `point:${pointed.key}` : target;
    let group = groups.get(slot);
    if (!group) {
      const key = pointed ? `${targetPath(target)}@${pointed.key}` : targetPath(target);
      const word = addressableWord(target);
      group = {
        key,
        target,
        point: pointed?.element ?? null,
        pointWords: pointed?.words ?? null,
        word,
        subject: null,
        title: null,
        items: [],
        offers: [],
      };
      groups.set(slot, group);
    }
    return group;
  }

  function add(groups, target, item, pointed = null) {
    if (!target?.isConnected || inChrome(target)) return;
    const group = groupFor(groups, target, pointed);
    group.items.push(item);
  }

  function visibleWidgetWorkflows() {
    return workflows().filter((workflow) =>
      isPageWidgetWorkflow(workflow, runtime.currentRevision),
    );
  }

  // A receipt's face is its category's icon and rank under the receipt's own label,
  // so one reading of a receipt never names a different stage than its text does.
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
              : receipt.stage === "queued"
                ? "queued"
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
      receiptByCoordinate.set(JSON.stringify(receipt.coordinate), receipt);
    }
    const representedThreads = new Set();
    for (const thread of threadList()) {
      const drafting = replyHasWords(threadKey(thread));
      if ((thread.resolved && !drafting) || !thread.anchor || claimed(thread.id))
        continue;
      const id = thread.id;
      const target = placedAt(id)?.element;
      if (target?.isConnected && !inChrome(target)) representedThreads.add(id);
      const attention = threadAttention(thread);
      const onUser = attention?.kind === "needs_user";
      const unread = thread.unread.length;
      const placement = placedAt(id);
      const point = standingPoint(target, placement?.point);
      const pointed = point
        ? { key: placement.pointRow, element: point, words: placement.pointWords }
        : null;
      add(
        groups,
        target,
        {
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
        },
        pointed,
      );
    }

    const asks = openAsks();
    for (const ask of asks) {
      const id = ask.id;
      const target = elementById(id);
      if (!target) continue;
      add(groups, target, {
        kind: "ask",
        id: `ask:${id}`,
        // The group this row stands in already names the Ask; the row says why it is
        // there, since these are the Asks the user owes.
        text: "Waiting on you",
        // The marker's own label is the question, which says more than the kind its
        // glyph already shows.
        label: addressableLabel(target) || null,
        activate: () => {
          const standing = openAsks();
          const next = standing.find((candidate) => candidate.id === id);
          if (next) goToAsk(next, standing);
        },
      });
    }

    const projection = currentProjection();
    const claimActivity = new Map(
      workflows()
        .filter(isLiveWorkflow)
        .map((item) => [`${item.subject.kind}:${item.subject.id}`, item]),
    );
    const activityAlreadyShown = new Set();
    const acknowledged = new Set();
    for (const [coordinate, entry] of projection.desired) {
      if (entry.e.kind !== "action") continue;
      const target = elementById(entry.unit) ?? elementById(entry.e.widget);
      if (!target) continue;
      const receipt = receiptByCoordinate.get(coordinate);
      if (!receipt) continue;
      const account = [
        addressableWord(target),
        humanized(entry.e.action),
        addressableLabel(target),
      ]
        .filter(Boolean)
        .join(" · ");
      const face = agentWorkflowFace(receipt);
      if (!face) continue;
      if (face.kind === "activity")
        activityAlreadyShown.add(`widget:${receipt.subject.id}`);
      acknowledged.add(target);
      add(groups, target, {
        kind: face.kind,
        id: `acknowledgment:${receipt.id}`,
        text: labelWords(`${face.text} · ${account}`),
        workflowFace: Object.freeze({ ...KINDS[face.kind], label: face.text }),
        workflowReceipt: receipt,
        ...(face.context ? { context: face.context } : {}),
        activate: () =>
          revealTarget(target, `${face.text}: ${account}`, scrollToElement),
      });
    }

    for (const origin of projectionOrigins(authoredStates(), projection)) {
      const target = elementById(origin.unit);
      if (!target) continue;
      // A gesture the agent still owes an answer to stands under its workflow row, which
      // says the change is the user's and where it has got to; its provenance row would
      // say the first half again.
      if (origin.origin === "user" && acknowledged.has(target)) continue;
      const face = KINDS[origin.origin];
      add(groups, target, {
        kind: origin.origin,
        id: `state-origin:${origin.origin}:${origin.unit}`,
        // Durable provenance belongs in Page Map rather than another target margin entry:
        // it remains explicit without changing the page's action density or geometry.
        marker: false,
        text: labelWords(
          [face.label, addressableWord(target), addressableLabel(target)]
            .filter(Boolean)
            .join(" · "),
        ),
        activate: () =>
          revealTarget(
            target,
            `${face.label}: ${addressableLabel(target) || addressableWord(target)}`,
            scrollToElement,
          ),
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
        text: labelWords(
          [mapAccount, addressableLabel(target)].filter(Boolean).join(" · "),
        ),
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
        const age = ago(update.ts);
        const account = [update.agent, update.text || humanized(update.action)]
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
    points.clear();
    return marginInventory(
      collected
        .sort((left, right) =>
          comesBefore(left.point ?? left.target, right.point ?? right.target),
        )
        .map((group) => {
          const subject = outlineSubjectFor(group.target, subjects, outline);
          targets.set(group.key, group.target);
          if (group.point) points.set(group.key, group.point);
          return Object.freeze({
            key: group.key,
            targetId: group.target.id,
            title: labelWords(
              [
                group.subject ? null : subject.context,
                group.word,
                group.subject ?? addressableLabel(group.target),
                // A pointed row is named by the words it stands by, so it and the
                // target's own row do not read alike.
                pointName(group.pointWords),
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
      point: () => entryPoint(row.lfEntry),
      order,
      move: (into) => moveHost(row, into),
      fold: {
        able: () =>
          canFold(row.lfEntry, {
            expandedKey: expandedOptionsKey,
            expandedOwner: expandedOptionsOwner,
          }),
        // How many controls the pin shows opened: its options and the toggle.
        controls: () => {
          const { options } = clusterProjection(row.lfEntry, {
            expandedKey: row.lfEntry.key,
            folded: true,
          });
          return options.visible.length + (options.spill ? 1 : 0) + 1;
        },
        // Told from inside the layout pass, which has already seated the row at its new
        // size: the cluster is presented again once that pass has written, before the
        // frame paints, however many rows it folded.
        changed: () => {
          if (refoldQueued) return;
          refoldQueued = true;
          queueMicrotask(() => {
            refoldQueued = false;
            renderMargin.refresh();
          });
        },
      },
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
    const paint = () => {
      settlingOptionsFocus = true;
      try {
        renderMargin.refresh();
        if (returnFocus && previousKey) {
          handBack(moreMarginEntries.get(previousKey));
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
    };
    // Opening needs controls before the caller reads availability. Closing paints
    // the end of the gesture, where a submitted action replaces its contribution.
    // Paint and its focus return share the guard, so the return cannot reopen it.
    if (open) paint();
    else afterScript(paint);
    if (previousOwner === "responses")
      document.dispatchEvent(new CustomEvent("lf-margin-entry-options-closed"));
  }

  function focusForNavigation(control) {
    reveal(control);
    const wasSuppressingOptionsArrival = suppressingOptionsArrival;
    suppressingOptionsArrival = true;
    try {
      focusDestination(control);
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

  // Stand one contributor's options open at a target. Decided on the entries before
  // anything paints, so the cluster renders once, already open, rather than shut and
  // then opened in the same task.
  function openMarginEntryOptions(target, owner) {
    const entry = collectEntries().find(
      (candidate) =>
        targetFor(candidate) === target &&
        candidate.offers.some((offered) => offered.key === owner),
    );
    if (!entry || !entryHasMarginHost(entry)) return false;
    if (expandedOptionsKey === entry.key && expandedOptionsOwner === owner) {
      renderMargin.refresh();
      const options = hosts.get(entry.key)?.options;
      if (options?.isConnected && !options.hidden) return true;
      expandedOptionsKey = null;
      expandedOptionsOwner = null;
    }
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
    scrollToElement(entryPlace(entry), undefined, "nearest");
    // Arrive before activation, then use the exact visible margin entry's own press. A generated
    // route never chooses among the cluster's actions on the user's behalf.
    focusForNavigation(control);
    control.click();
    return true;
  }

  // Where the Map hands the user back, for `handBack`: the entry's own marker, then the
  // way into the Map, then a row in view, then the version control. The Map is a toolbar
  // control, so at a width that folds it the button itself is behind a shut door and
  // cannot take focus; the toolbar is asked for the way in.
  function mapControlPlaces(entry = null) {
    const visible = visibleRows();
    return [
      entry ? rows.get(entry.key) : null,
      bannerControlDoor(mapButton),
      visible.find((row) => row.tabIndex === 0) ?? visible[0],
      bannerControlDoor(versionBtn),
    ];
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
  function toggleAnnotations() {
    setAnnotationsHidden(!annotationsHidden());
    notice(
      !annotationsHidden()
        ? "Annotations shown"
        : coarsePointer.matches
          ? "Annotations hidden"
          : "Annotations hidden. o shows them",
    );
  }
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
    // A pin covers the corner of its block, and a finger has no `o` to clear it.
    touch: () => (annotationsHidden() ? "Show annotations" : "Hide annotations"),
    run: toggleAnnotations,
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
    // The walk answers from a marker, not from the entries beside it, which Left and
    // Right move between.
    ...rowWalk({
      id: "margin",
      noun: "Marker",
      plural: "visible markers",
      rows: visibleRows,
      landed: holdTabStop,
      scroll: false,
    }).map((row) => ({
      ...row,
      when: () => focused()?.matches?.(".lf-margin-marker") && visibleRows().length > 0,
    })),
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
    const kind = count > 1 ? `${face.label}s` : face.label;
    const userContext =
      awaitingUser(choice.items) || unreadIn(choice.items)
        ? readingContext(choice)
        : null;
    presentMarginEntry(
      node,
      marginEntry({
        key: `reading:${choice.key}`,
        icon: face.icon,
        label: readingLabel(choice),
        accessibleLabel: `${kind} for ${spokenSubject(entry.title)}${count > 1 ? `, ${count} items` : ""}${userContext ? `, ${userContext}` : ""}`,
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
    const restoreFocus = holdFocus(host);
    // Moving a focused expanded cluster between lanes, when its target's scroller
    // changes, synchronously emits focusout. That is a placement transition, not the user
    // leaving the cluster, so keep the options state machine from treating it as an
    // instruction to fold the controls it just exposed — and say the same thing to every
    // other reader of where the user stands, which is what `placeChrome` is for.
    const wasSettlingOptionsFocus = settlingOptionsFocus;
    settlingOptionsFocus = true;
    let kept = true;
    try {
      kept = placeChrome(() => {
        move();
        return restoreFocus?.() ?? true;
      });
    } finally {
      settlingOptionsFocus = wasSettlingOptionsFocus;
    }
    // The one case where the placement did move the user: the control they were
    // standing on did not survive it, so focus is wherever the removal left it and the
    // standing paint is owed the news the guard above withheld.
    if (!kept) repaint();
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
    forgetThreadPreviewPlacement();
    previewMarginEntry = button;
    if (returnFocus) button.focus({ preventScroll: true });
  }

  // Paper is not a posture this can be read in. Print hides every injected control
  // (`[data-lf-offer]` in the chrome stylesheet's print block) and the margin projection
  // with it, so the one contributor-visibility reading a render is built on comes back
  // empty: every cluster folds to nothing, and what has been written down is the medium
  // rather than the page. Nobody sees it on the dialog, where the margin does not print
  // at all, but the fold outlives the print preview and stands on screen until the next
  // render repairs it. A reading taken where the box is `display: none` is not a
  // measurement, so a render asked for on paper is refused whole and taken once the
  // screen is back.
  const onPaper = matchMedia("print");

  function renderNow() {
    if (onPaper.matches) return;
    const threadOwnerHeld =
      transferThreadFocus || document.activeElement === previewMarginEntry;
    transferThreadFocus = false;
    // Before the card, which anchors to its rows (`mount`).
    if (!nav.isConnected)
      chromeRoot.insertBefore(nav, preview.parentNode === chromeRoot ? preview : null);
    presentingMarginContributions();
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
        // Its face is the cluster's to paint (margin-cluster-view.js).
        more = offer("button", "lf-margin-more");
        const optionsId = `lf-margin-options-${++optionsOrdinal}`;
        host = clusterViews.createPage(marker, more, optionsId);
        keys(host, "In the margin", marginKeys, () => marginKeysAvailable);
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
          const standsFoldedNow =
            Boolean(current) &&
            folded(current) &&
            canFold(current, {
              expandedKey: expandedOptionsKey,
              expandedOwner: expandedOptionsOwner,
            });
          if (!current || !(standsFoldedNow || optionsOffered(current, primary)))
            return;
          if (expandedOptionsKey === current.key && expandedOptionsOwner) return;
          if (entryEngaged(current)) return;
          // A folded cluster's toggle is its only control and stands after the actions it
          // unfolds, so Tab arriving on it lands on the first of them, and Shift+Tab on
          // the last.
          const back =
            event.relatedTarget instanceof Node &&
            Boolean(
              host.compareDocumentPosition(event.relatedTarget) &
              Node.DOCUMENT_POSITION_FOLLOWING,
            );
          setOptionsOpen(current, true, {
            focusOption:
              control === more ? (standsFoldedNow && !back ? "first" : "last") : null,
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
      // Insert in inventory order; the theme keeps the row unpainted and measurable
      // until the layout pass assigns its anchored posture.
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
        folded: folded(entry),
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
    nameMarkers(readSpokenPositions(pageInventory));
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
    const restoreFocus = holdFocus(preview);
    const focusedItem = restoreFocus
      ? (document.activeElement.closest?.("[data-lf-margin-entry]")?.lfMarginItem ??
        null)
      : null;
    const threadItems = entry.items.filter((item) => item.kind === "comment");
    const wanted = requestedItem ?? previewThreadItem ?? focusedItem;
    const selected = threadItems.find((item) => item.id === wanted) ?? threadItems[0];
    // Another thread starts at its top; an update to this one holds the reader's place.
    const arriving = previewThreadItem !== (selected?.id ?? null);
    // Another thread is another card, which chooses its own spot.
    if (arriving) {
      previewSide.forget();
      previewHold = null;
    }
    const latest = selected ? turns(sourceItem(selected).thread).at(-1) : null;
    const messageSelector =
      ":scope > .lf-margin-thread > .lf-margin-thread-body > " +
      ".lf-page-thread > .lf-thread-transcript > .lf-page-thread-msg";
    const replySelector =
      ":scope > .lf-margin-thread > .lf-margin-thread-body > " +
      ".lf-page-thread > .lf-say";
    const lastShown = [...previewList.querySelectorAll(messageSelector)].at(-1);
    const lastBox = lastShown?.getBoundingClientRect();
    const listBox = previewTranscript?.getBoundingClientRect();
    const replyBox = previewList.querySelector(replySelector)?.getBoundingClientRect();
    const follow =
      !arriving &&
      previewLatest?.thread === selected?.id &&
      latest?.author === "agent" &&
      (latest.id !== previewLatest.id || latest.text !== previewLatest.text) &&
      lastBox &&
      listBox &&
      lastBox.bottom >= listBox.top &&
      lastBox.bottom <= (replyBox?.top ?? listBox.bottom) + 80 &&
      previewTranscript.scrollHeight -
        previewTranscript.clientHeight -
        previewTranscript.scrollTop <=
        2;
    const present = () => {
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
      keepsHidden(previewNav, threadItems.length < 2);
      const selectedIndex = Math.max(0, threadItems.indexOf(selected));
      keepsText(previewPosition, `${selectedIndex + 1}/${threadItems.length}`);
      previewPrevious.toggleAttribute("disabled", selectedIndex === 0);
      previewNext.toggleAttribute("disabled", selectedIndex === threadItems.length - 1);
      setChildren(previewList, selected ? [previewItemNode(selected)] : []);
      syncPreviewTranscript();
      // The list holds the one thread the card shows, so a user whose place in a thread
      // the rebuild took lands on that thread; a step button it hid hands them to Close.
      restoreFocus?.(
        focusedItem && previewList.querySelector(".lf-page-thread"),
        previewClose,
      );
      placeThreadPreview();
    };
    if (!arriving && previewPlace) previewPlace.around(present);
    else {
      present();
      if (previewTranscript) previewTranscript.scrollTop = 0;
    }
    previewLatest = latest && { thread: selected.id, id: latest.id, text: latest.text };
    if (follow) previewTranscript.scrollTop = previewTranscript.scrollHeight;
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
        // A resolved thread with no draft has no margin card, so resolving closes it and
        // hands the user to its target, and a resolve that no longer stands opens the
        // card on the thread again, while the margin is still where threads open.
        prepareLanding: () => {
          const target = targetFor(previewEntry);
          const thread = sourceItem(item).thread.id;
          const mayLand = retainUserIntent({
            source: focused(),
            available: () => Boolean(target?.isConnected) && !panelIsOpen(),
            fallback: bannerControlDoor(mapButton),
          });
          return {
            optimistic: () => {
              if (previewOpen()) return false;
              return mayLand.handoff(() => focusDestination(target));
            },
            reverse: async (may = mayLand) => {
              await whenDocumentPresented();
              return (
                may() &&
                mayLand.available() &&
                Boolean(openPageThread(thread, { focus: "thread" }))
              );
            },
          };
        },
      },
    );
    keeps(node, "data-lf-margin-entry", item.id);
    node.lfMarginItem = item.id;
    return node;
  }

  // One gesture can move the trace's source more than once: a close that clears it and
  // the focus it hands back that names the same target again. The trace paints what the
  // gesture ends on, once, in the frame that follows it.
  function highlight(target) {
    if (highlighted === target) return;
    highlighted = target;
    highlightFrame ||= nextRender(() => {
      highlightFrame = 0;
      const part = highlighted
        ? visualAt(highlighted, { unclaimed: false })?.part
        : null;
      paintTrace(
        highlighted,
        part?.element === highlighted ? part.surface : highlighted,
      );
    });
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
    keepsHidden(preview, false);
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
    // aim at the card itself — a mode, a rerender — lands them instead.
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
    unplaceThreadPreview();
    if (previewOpen()) preview.hidden = true;
    if (forcedOptionsKey && expandedOptionsKey === forcedOptionsKey)
      setOptionsOpen(null, false);
    refreshHighlight();
    for (const row of rows.values())
      syncReadingRelation(row, primaryReading(row.lfEntry));
    for (const reading of readingMarginEntries.values())
      syncReadingRelation(reading, reading.lfChoice);
    if (returnFocus)
      handBack(button, ...(button?.lfEntry ? mapControlPlaces(button.lfEntry) : []));
    else if (heldInside) letGo();
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
  const stepsOut = (from = focused()) => {
    const target = targetFor(previewEntry);
    return preview.contains(from) &&
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
  // semantic state rather than because the user disclosed the secondary drawer. That
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
    title: "In the margin",
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
    if (focusMap && !landsOnTarget) handBack(...mapControlPlaces(entry));
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
      openPageThread(sourceItem(choice.items[0]).thread.id);
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
    const itemId = marginThreadItem(threadList().find((t) => t.id === id));
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
    return thread && { thread, presented: positioned };
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
  // card needs no trip: it opens in the window even where its cluster is above it.
  function openPageThread(id, { focus = "reply", travel = true } = {}) {
    if (!panelIsOpen()) {
      // The trip starts before the surface takes focus, which scrolls it into view: the
      // trip records the place the user leaves, so it has to find them still there.
      const local = surfaceFocusTarget(id, { focus });
      if (local) {
        if (travel) scrollToThread(id, { focus });
        else focusSurface(id, { focus });
        closePreview();
        return local;
      }
      const opened = openInlineThread(id, {
        onPositioned: travel
          ? null
          : (thread) => {
              focusForNavigation(thread);
              thread.scrollIntoView({ behavior: scrollBehavior(), block: "nearest" });
            },
      });
      if (opened) {
        if (travel) scrollToThread(id, { focus, presented: opened.presented });
        return opened.thread;
      }
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
  // the card keeps its row clear, as it stood when it opened. margin-layout.js says when
  // it has moved the rows, and the card follows in that same frame, so a user never sees
  // it standing over where its controls moved to.

  // Standing selection belongs to the reading, not to focus or a particular feature's
  // control. Resolve it through the same inventory that decides which reading is the
  // visible marker and which is an unfolded option, then paint one shared state on the
  // compact projection. An open disclosure continues to use aria-expanded instead.
  function paintSelectedMarginEntries(selections) {
    const selected = new Set();
    // A target's own row and each pointed thread's row (groupFor) are all about it.
    for (const selection of selections)
      for (const entry of pageInventory) {
        if (targetFor(entry) !== selection.target) continue;
        const control = readingMarginEntry(entry, selection.kind);
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
  // at large — the banner, a drawer — is working on the page rather than a place on it,
  // and leaves the card; a press anywhere else is the user's attention moving, and
  // takes it, as a press on another page place does.
  //
  // Arrival through the keyboard shows the card, as arrival through Tab unfolds a
  // cluster; a pointer that lands on a control in a commented block asked for that
  // control, and the mark and the marker are its way to the thread.
  const threadIdOf = (entry) => sourceItem(threadReading(entry).items[0]).thread.id;
  const threadIdsOf = (entry) =>
    threadReading(entry).items.map((item) => sourceItem(item).thread.id);
  // Only a page-owned seat or an exact widget-local placement takes the thread's
  // page position. A package mirror uses the same card DOM but leaves that position
  // and its margin preview available.
  const seatedOnPage = (id) =>
    claimed(id) ||
    [
      ...document.querySelectorAll(`.lf-page-thread[data-thread="${CSS.escape(id)}"]`),
    ].some((seat) => closestAcross(seat, ".lf-thread-seat[data-lf-thread-seat]"));
  // The innermost target holding the node whose threads the card would show. A thread is
  // about exactly its anchor's target (glossary, Standing target), reached from anywhere
  // inside it and never from outside: after `a` the user stands on the Ask element, so
  // the card shows a thread on the Ask but not one on its options or a phrase in its
  // heading. Treating an Ask as one target for its threads is a possible refinement. It
  // belongs where a thread's target is decided (anchor-paint's placement), so every
  // reader keeps one definition, not in this or any other single reader.
  // Read from where the node stands (standing-target.js), so chrome that shows a page
  // target, such as a comment note, arrives at that target as its own content does.
  // A target with pointed threads (groupFor) has a row for each: standing inside a
  // pointed row takes that thread, and standing elsewhere on the target takes its own
  // row, or a pointed one where it has none.
  const pointRank = (entry, place) => {
    const point = entryPoint(entry);
    return !point ? 1 : under(place, point) ? 2 : 0;
  };
  const threadEntryAt = (node) => {
    const place = placeOf(node);
    let standing = null;
    for (const entry of pageInventory) {
      const target = targetFor(entry);
      if (!target || !threadReading(entry) || !under(place, target)) continue;
      if (seatedOnPage(threadIdOf(entry))) continue;
      const held = standing && targetFor(standing);
      if (
        !standing ||
        (target === held
          ? pointRank(entry, place) >= pointRank(standing, place)
          : under(target, held))
      )
        standing = entry;
    }
    return standing;
  };
  // A folded cluster opens while the keyboard stands at its target, as it does when
  // the keyboard arrives on its toggle: what the user stands at offers its actions, and
  // an Ask's digits name them. It folds again when they stand anywhere else but in the
  // cluster itself, whose own focus then keeps it open (the host's `focusout`).
  let standingUnfolded = null;
  function unfoldStanding(active) {
    const host = active && closestAcross(active, "[data-lf-margin-for]");
    if (host?.lfEntry?.key === standingUnfolded) {
      standingUnfolded = null;
      return;
    }
    const state = {
      expandedKey: expandedOptionsKey,
      expandedOwner: expandedOptionsOwner,
    };
    const place =
      active && !host && active.matches(":focus-visible") && placeOf(active);
    const entry = place
      ? pageInventory.find(
          (candidate) =>
            folded(candidate) &&
            canFold(candidate, state) &&
            under(place, targetFor(candidate)),
        )
      : null;
    if (entry?.key === standingUnfolded) return;
    if (standingUnfolded && expandedOptionsKey === standingUnfolded)
      setOptionsOpen(null, false, { preservePreview: true });
    standingUnfolded = null;
    if (!entry || expandedOptionsKey === entry.key) return;
    setOptionsOpen(entry, true, { preservePreview: true });
    standingUnfolded = entry.key;
  }
  function followStanding() {
    refreshHighlight();
    const active = focused();
    unfoldStanding(active);
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
    if (!pinnedKey || previewEntry?.key !== pinnedKey || !previewOpen() || previewAway)
      return null;
    const threads = previewList.querySelectorAll(".lf-margin-thread .lf-page-thread");
    return threads.length === 1 ? threads[0] : null;
  };
  // The page element a thread is about, resolved or not: where its anchor is placed, the
  // element its inventory entry is grouped under. A general or detached thread has none.
  const threadTarget = (id) => placedAt(id)?.element ?? null;
  const threadFocusTarget = (id, options) =>
    surfaceFocusTarget(id, options) ??
    [...previewList.querySelectorAll(".lf-page-thread")].find(
      (thread) => thread.dataset.thread === id,
    ) ??
    null;
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
  // the version picker, then its own parts in the root.

  function mount() {
    mountMarginLayer(toolbar);
    onPaper.addEventListener("change", () => {
      if (!onPaper.matches) renderMargin.refresh();
    });
    previewClose.onclick = () => closePreview(true);
    preview.addEventListener("focusout", (event) => {
      const row = event.target.closest?.(".lf-say");
      if (
        row &&
        !row.contains(event.relatedTarget) &&
        !row.querySelector(REPLY_BOX)?.value
      )
        scheduleThreadPreviewPosition();
    });
    // Carried away with what it is about, the card comes back with it.
    declareOffFlowSurface(preview, {
      bringBack: (behavior) =>
        scrollToElement(
          entryPlace(previewEntry) ?? previewMarginEntry,
          behavior,
          "nearest",
        ),
    });
    previewPrevious.onclick = () => stepPreviewThread(-1);
    previewNext.onclick = () => stepPreviewThread(1);
    watchProjection(document.body, renderMargin);
    document.addEventListener("lf-comparison", renderMargin);
    document.addEventListener("lf-margin-layout", ({ detail: { column, height } }) => {
      placeThreadPreview();
      scheduleMarginEntryLabels();
      // A new width or height moves where targets stand down the page, and so what their
      // markers' names say; whatever else moves a target renders the margin, which names
      // them anew. Measured against the column this pass read.
      if (column.width === spokenBasis?.width && height === spokenBasis?.height) return;
      const moved = readSpokenPositions(pageInventory, column, height);
      if (moved.some((position, index) => position !== spokenPositions[index]))
        nameMarkers(moved);
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
    document.addEventListener("scroll", () => scheduleRoving(), {
      capture: true,
      passive: true,
    });
    window.addEventListener("resize", () => scheduleWidthRender());
    renderMargin();
    // The card anchors to its row (floating.js), which an anchor may do only to a box
    // laid out before it: the margin comes first.
    chromeRoot.append(nav, preview);
    if (!previewRegionMounted) {
      previewRegionMounted = true;
      // The card may not yet hold a thread. Its region starts with the first transcript.
      if (previewTranscript) {
        stopPreviewRegion = registerReadingRegion({
          id: THREAD_CARD,
          host: preview,
          body: previewTranscript,
        });
      }
    }
  }
  return {
    pageMapActive: () => availableRows().includes(focused()),
    activateMapItem: activate,
    faceForMap: (item) => KINDS[item.kind],
    targetFor,
    mapControlPlaces,
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
    // The element a thread in the card is about, where a send from it leaves the user
    // with the card still up: the same step Escape takes out of the card.
    cardTarget: stepsOut,
    optionsRung,
    openInlineThread,
    openPageThread,
    paintSelectedMarginEntries,
    marginEntryChoices,
    unfoldedMarginEntries,
    foldMarginEntryOptions,
    threadHere,
    threadTarget,
    threadFocusTarget,
    captureStanding,
    restoreStanding,
    mount,
  };
}
