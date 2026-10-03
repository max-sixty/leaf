/* Overlay annotation clusters and contextual Thread cards.

   The application supplies the neutral annotation inventory and its live target/action
   directory. This renderer selects clusters and controls from those readings; it does
   not gather Threads, Asks, workflows or contributed actions. Shared contribution
   controls retain native entries across page and frozen-Thread seats. This renderer's
   Lit view owns direct/disclosed child order; margin-layout.js owns rail/pin posture,
   lanes and packing. Page Map consumes the inventory independently of this renderer.

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
   down a line per wrap; its foot, with the reply row on it, for the turn that joins the
   transcript while the user drafts or sends, and where the card stands over what it is
   about and is read. Opening it on another thread lets it choose its spot afresh. A scroll
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
   Core Thread destinations read this target accompaniment. The side this owner
   declares to standing-target.js gives the page target a card or cluster stands for.
   The panel declares its own target association.

   Placing the card changes its geometry and nothing inside it. The user's place in
   its transcript is the messages' own scroll, held through reflow. The metadata and
   reply row stand outside that scroll. A landing, send, or
   step moves it; a new or growing agent turn follows while the reader is at the tail.
   Other state reads leave the transcript where the user put it.

   Each frozen cluster model names controls by contribution and entry identity. The Lit view
   retains their native nodes, so a state refresh cannot cancel a held pointer or move focus.
   A print-media render is deferred until screen media returns because print removes the
   injected controls and cannot supply their geometry.

   This owner holds overlay geometry and preview state. The application's annotation
   pass owns refresh, clocks, contribution updates and print deferral; local geometry
   gestures request that same pass. Mount binds the overlay's mechanical lifecycle. */

import { atScrollEnd, scrollToEnd } from "./scrolling.js";
import { afterScript, cancelRender, nextRender } from "./rendering.js";
import { labelWords, spokenSubject } from "./contribution-model.js";
import {
  THREAD_CARD,
  layoutMarginRows,
  mountMarginLayer,
  marginSpot,
  registerMarginRow,
  scheduleMarginEntryLabels,
  scheduleMarginLayout,
  standsFolded,
  unregisterMarginRow,
} from "./margin-layout.js";

import {
  contributionEntry,
  contributionEntryRecord,
  contributionEntrySource,
  presentContributionEntry,
  activateContributionControl as activateSharedContribution,
  syncContributionAgentWorkflow,
  syncContributionSelection,
  syncContributionTurn,
  syncContributionUnread,
} from "./contribution-controls.js";
import {
  entryEngaged,
  choosePrimary,
  readingKey,
  readingChoices,
  primaryReading,
  threadReading,
  entryHasMarginHost,
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
} from "./margin-model.js";

import { mapButton } from "./page-map-dialog.js";

import { pointBand } from "./pointed-place.js";
import {
  declareRelease,
  focusDestination,
  handBack,
  holdFocus,
  letGo,
  placeChrome,
} from "./focus.js";
import { TEXT_FIELD } from "./control-selectors.js";
import { closeControl, el, offer } from "./widget-elements.js";
import { keeps, keepsHidden, keepsText, layoutPx } from "./keeps.js";
import { setChildren } from "./dom-children.js";
import { PRESS } from "./keyboard/bindings.js";
import { beginWalk, listWalkPosition, rowWalk } from "./walk-position.js";

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
import { closestAcross, inChrome } from "./passages.js";
import { visualAt } from "./anchor-resolution.js";
import { paintTrace } from "./target-paint.js";

import { allThreads } from "./thread/state.js";
import { threadNames, turns } from "./thread/model.js";
import { whenDocumentPresented } from "./semantic-state.js";

import { notice } from "./notifications.js";
import { iconElement } from "./icons.js";
import { claimed, showHeld } from "./thread/surfaces.js";
import { anchorLabel } from "./thread/messages.js";
import { createMarginClusterViews } from "./margin-cluster-view.js";

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
import { passageGeometry } from "./resolved-target.js";
import { floatingPlacement, floatingUi, heldByWindow } from "./floating.js";
import { placeKeeper } from "./user-place.js";

import { under } from "./shadow.js";
import { retainUserIntent } from "./user-intent.js";
import { threadFocusDestination } from "./thread/focus.js";

// A margin card's reply box.
const REPLY_BOX = `.lf-thread-reply ${TEXT_FIELD}`;

export function createMarginProjection({
  inventory,
  refreshInventory,
  renderAnnotations,
  openPageThread,
  panel,
  accompaniedThread,
  accompanyThread,
  panelIsOpen,
  designModeActive,
  pointerModeActive,
  leavePageMap,
  openPageMap,
  pageMapDialogContains,
  scrollThreadIntoView,
  renderMarginThread,
  placedAt,
  scrollToElement,
}) {
  const {
    targetFor,
    entryPoint,
    entryPlace,
    sourceItem,
    workflowReceipt,
    threadItem: marginThreadItem,
  } = inventory;
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
          items: ".lf-msg[data-event]",
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
  let threadTransitionMotion = null;

  // The submitted composer and a developer replay describe the same starting box; the
  // transition owns that geometry contract instead of making either caller duplicate it.
  function threadTransitionOrigin(element, frame) {
    if (!frame) return null;
    const box = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return {
      frame,
      left: box.left,
      top: box.top,
      width: box.width,
      height: box.height,
      messageWidth: parseFloat(style.width),
      messageHeight: parseFloat(style.height),
      scroll: element.scrollTop,
    };
  }

  let previewMessageViewport = null;
  function clearThreadTransition() {
    threadTransitionEpoch += 1;
    threadTransitionMotion?.cancel();
    threadTransitionMotion = null;
  }

  // The real message is legible from the first frame; only its surrounding frame
  // grows. No copied words, translation, scaling, or second placement at motion's end.
  function transitionThread(origin) {
    const target = preview.getBoundingClientRect();
    const style = getComputedStyle(preview);
    const scale = {
      x: target.width / parseFloat(style.width),
      y: target.height / parseFloat(style.height),
    };
    const inset = [
      (origin.top - target.top) / scale.y,
      (target.right - origin.left - origin.width) / scale.x,
      (target.bottom - origin.top - origin.height) / scale.y,
      (origin.left - target.left) / scale.x,
    ];
    threadTransitionMotion = motion(
      preview,
      [
        { clipPath: `inset(${inset.map(layoutPx).join(" ")} round 6px)` },
        { clipPath: preview.style.clipPath || "inset(0px round 10px)" },
      ],
      240,
    );
  }

  function revealThread(origin, entry, positioned) {
    clearThreadTransition();
    const epoch = threadTransitionEpoch;
    return positioned.then((placed) => {
      if (
        !placed ||
        epoch !== threadTransitionEpoch ||
        previewEntry?.key !== entry.key ||
        !previewOpen()
      )
        return false;
      transitionThread(origin);
      return true;
    });
  }

  function carryCommentFrame(origin) {
    previewMessageViewport?.stopRegion?.();
    previewMessageViewport = origin && {
      scroll: origin.scroll,
      body: null,
      stopRegion: null,
    };
    preview.toggleAttribute("data-lf-comment-frame", Boolean(previewMessageViewport));
    const properties = {
      "--lf-comment-width": previewMessageViewport && `${origin.frame.width}px`,
      "--lf-comment-message-width":
        previewMessageViewport && `${origin.messageWidth}px`,
      "--lf-comment-message-height":
        previewMessageViewport && `${origin.messageHeight}px`,
    };
    for (const [name, value] of Object.entries(properties))
      if (value) preview.style.setProperty(name, value);
      else preview.style.removeProperty(name);
  }

  let workflowCarriers = new Set();
  let selectedReadingCarriers = new Set();
  const rows = new Map();
  const moreMarginEntries = new Map();
  const readingMarginEntries = new Map();
  const hosts = new Map();
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
          const record = contributionEntryRecord(control);
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
  let previewPositionResult = null;
  let previewFocusPending = null;
  // The side the card holds (comment-placement.js); the offsets of its top and foot from
  // the line it stands level with; its transcript height and reply-line hold at the last
  // placement (`placeThreadPreview`); and whether a scroll has carried it out of the
  // window with what it is about.
  const previewSide = commentPlacement();
  let previewHold = null;
  let previewAway = false;
  function answerThreadPreviewPosition(positioned) {
    previewPositionResult?.resolve(positioned);
    previewPositionResult = null;
  }
  // A placement lands in the microtasks after it starts, before the frame paints. One
  // that cannot land yet — its owner not connected, no room — is answered by a later
  // placement, or by the close that abandons it.
  const placedThreadPreview = () => {
    previewPositionResult ??= Promise.withResolvers();
    cancelRender(previewPositionFrame);
    previewPositionFrame = 0;
    placeThreadPreview();
    return previewPositionResult.promise;
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
      renderAnnotations.refresh();
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
  function measureThreadCard(room, cap, reading) {
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
    if (reading?.end) scrollToEnd(previewTranscript);
    return preview.getBoundingClientRect().height;
  }
  // The thread's complete turns, without the reply row under them: what an arriving or a
  // sent turn changes and a new line of the reply does not. Unrounded, since the row's
  // height is fractional and a rounded difference moves with it.
  const boxHeight = (node) => node.getBoundingClientRect().height;
  function measureTranscript() {
    return [...previewList.querySelectorAll(".lf-margin-thread")].reduce(
      (sum, thread) =>
        [...thread.querySelectorAll(".lf-thread-reply")].reduce(
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
  // Draft lines take room before they scroll. A long transcript yields up to half
  // the card's body to the reply; a short one leaves the remaining room available.
  // Growing the editor moves their shared boundary, never the card's attachment.
  function fitThreadCardEditors() {
    const listRoom =
      parseFloat(preview.style.getPropertyValue("--lf-thread-max-height")) -
      (preview.offsetHeight - previewList.clientHeight);
    previewList.style.setProperty("--lf-thread-list-room", `${listRoom}px`);
    for (const input of previewList.querySelectorAll(REPLY_BOX)) {
      const row = input.closest(".lf-thread-reply");
      const thread = row.closest(".lf-page-thread");
      const style = getComputedStyle(thread);
      const box = getComputedStyle(input);
      const line = parseFloat(box.lineHeight);
      const furniture = row.offsetHeight - input.offsetHeight;
      const inset = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
      const available =
        listRoom -
        (thread.querySelector(".lf-thread-root-meta")?.offsetHeight ?? 0) -
        furniture -
        inset;
      const answered = Math.min(
        thread.querySelector(".lf-thread-transcript").scrollHeight,
        available / 2,
      );
      const oneLine =
        input.offsetHeight -
        input.clientHeight +
        line +
        parseFloat(box.paddingTop) +
        parseFloat(box.paddingBottom);
      const room = Math.max(oneLine, available - answered);
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
      !point && thread?.anchor?.quote ? passageGeometry(placedAt(thread.id)) : null;
    return {
      element: point ?? target,
      clear,
      extent,
      row: (words?.attachment ?? clear).top,
      column: words?.attachment?.left ?? null,
      margin: marginSpot(target, point),
    };
  }
  const THREAD_SIDES = { right: "right", left: "left", bottom: "below", top: "above" };
  // Where the card stands is comment-placement.js's rule, the one the comment box stands
  // by, so a sent comment's card opens where its box stood. Beyond it the card holds its
  // place as its thread changes: it keeps the top while the user reads or writes a new
  // line, and its foot, with the reply row on it, after a turn joins the transcript as
  // the user drafts, whether one arrives or they sent it, so the box they type in stays
  // put through subsequent sizing passes. A card over its target grows up from its
  // foot. The boundary caps the card at the room from its held edge. Drafting grows the
  // editor into that room, then scrolls its words rather than carrying the card.
  function placeThreadPreview() {
    if (!previewOpen() || !previewMarginEntry?.isConnected) return false;
    const placement = previewPlacement.begin();
    let reading = null;
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
      ...(replyEditor?.closest(".lf-page-thread")?.querySelectorAll(".lf-msg") ?? []),
    ].at(-1);
    const drafting = Boolean(
      replyEditor?.checkVisibility() &&
      (replyEditor.closest(".lf-thread-reply").contains(document.activeElement) ||
        replyEditor.value !== "" ||
        newest?.matches('.user[aria-busy="true"]')),
    );
    const scroller = effectiveScroller(
      containingReadingRegionFor(place.element) ?? place.element,
    );
    const { side, fresh, hold } = previewSide.choose({
      clear: place.clear,
      row: place.row,
      extent: place.extent,
      boundary,
      minimumWidth: cardMinimum(),
      scroller,
      coarse: coarsePointer.matches,
    });
    const transcript = measureTranscript();
    if (hold) previewHold = { ...hold, transcript };
    if (fresh) previewHold = null;
    const turned = previewHold && Math.abs(transcript - previewHold.transcript) > 0.5;
    // A turn changes the transcript on one pass, then the card's own size changes its
    // measurement on the next. Borrow the reply's line for that turn, keyed by the
    // projected message's stable key so admitting a Send keeps the same hold. A later
    // reading turn or a new edit releases it; an arriving turn while drafting borrows it
    // anew, and a Send borrows it through the handoff out of the reply row.
    const thread = threadCardThread();
    const latest = thread && turns(thread).at(-1);
    const newDraft = drafting && !previewHold?.drafting;
    const continuedDraft =
      drafting && replyEditor?.value && replyEditor.value !== previewHold?.draftText;
    const keepReplyLine = Boolean(
      latest &&
      !newDraft &&
      !continuedDraft &&
      ((previewHold?.replyTurn && previewHold.replyTurn === latest.key) ||
        (turned && (drafting || (previewHold?.drafting && latest.author === "user")))),
    );
    // Adoption holds the message's start: expanded composer choices may add a row
    // below it that the thread does not carry. Later placements use the card's own
    // top/foot reading, including the normal above-side and reply-line holds.
    const held =
      !hold && (keepReplyLine || (!drafting && side === "top")) ? "foot" : "top";
    void floatingUi()
      .then((ui) => {
        if (!stillCurrent()) return null;
        const { reference, placement, middleware, heldIn } = previewSide.options(ui, {
          clear: place.clear,
          row: place.row,
          column: place.column,
          margin: place.margin,
          boundary,
          minimumWidth: cardMinimum(),
          fit({ width, scale }) {
            if (!stillCurrent()) return;
            // Capture when fitting actually starts, after the module load and any
            // Send landing. Hold this reading through every middleware measurement:
            // an intermediate cap must not turn an earlier offset into end-following.
            reading ??= previewTranscript && {
              end: !fresh && atScrollEnd(previewTranscript),
            };
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
            const height = measureThreadCard(room, cap / scale.y, reading);
            // Fitting the width settles wrapping before opening the card spends
            // scroll travel. A scroll supersedes this answer's attachment geometry.
            if (
              fresh &&
              (side === "top" || side === "bottom") &&
              makeRoom(side, place.clear, place.extent, height, boundary, scroller)
            ) {
              previewSide.scrolled();
              placeThreadPreview();
            }
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
        if (previewMessageViewport) {
          const body = previewList.querySelector(".lf-msg > .lf-msg-body");
          if (body && body !== previewMessageViewport.body) {
            previewMessageViewport.stopRegion?.();
            body.scrollTop = previewMessageViewport.scroll;
            previewMessageViewport.body = body;
            // Adoption retains the editor's viewport inside the transcript. It is
            // a reading region of its own while that inner viewport stands.
            previewMessageViewport.stopRegion = registerReadingRegion({
              id: `${THREAD_CARD}:submitted`,
              host: body,
              body,
            });
          }
        }
        // The spot the rule stood the card at before the boundary shifted it in, so a
        // card opened low in the window rises back to it once a scroll gives it room.
        const { scale, spot } = previewSide.landed(position);
        // The transcript this placement answered, so a turn that joined it while the
        // placement was worked out is one the next placement still sees join.
        previewHold = {
          ...spot,
          transcript,
          drafting,
          replyTurn: keepReplyLine ? latest.key : null,
          draftText: replyEditor?.value,
        };
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
    const source = control && contributionEntrySource(control);
    if (source) return source;
    return closestAcross(at, "[data-lf-margin-for]")?.lfTarget ?? null;
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
            renderAnnotations.refresh();
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
        renderAnnotations.refresh();
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
    const { key, owner } = contributionEntryRecord(control);
    if (!key || !owner) return null;
    return (
      visibleMarginEntries().find(
        (candidate) =>
          contributionEntryRecord(candidate)?.key === key &&
          contributionEntryRecord(candidate)?.owner === owner &&
          candidate.checkVisibility(),
      ) ?? null
    );
  }

  // Stand one contributor's options open at a target. Decided on the entries before
  // anything paints, so the cluster renders once, already open, rather than shut and
  // then opened in the same task.
  function openMarginEntryOptions(target, owner) {
    const entry = refreshInventory().find(
      (candidate) =>
        targetFor(candidate) === target &&
        candidate.offers.some((offered) => offered.key === owner),
    );
    if (!entry || !entryHasMarginHost(entry)) return false;
    if (expandedOptionsKey === entry.key && expandedOptionsOwner === owner) {
      renderAnnotations.refresh();
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
    const acts = (row) => contributionEntryRecord(row)?.behavior !== "status";
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
    renderAnnotations.refresh();
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
    presentContributionEntry(
      row,
      contributionEntry({
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
    syncContributionAgentWorkflow(row, workflowReceipt(choice?.items ?? []));
    syncContributionTurn(row, awaitingUser(choice?.items ?? []));
    syncContributionUnread(row, unreadIn(choice?.items ?? []));
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
    presentContributionEntry(
      node,
      contributionEntry({
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
    syncContributionAgentWorkflow(node, workflowReceipt(choice.items));
    syncContributionTurn(node, awaitingUser(choice.items));
    syncContributionUnread(node, unreadIn(choice.items));
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
    const activated = activateSharedContribution(
      { offered, entry, control, surface, event },
      focusForNavigation,
    );
    // A disclosed contributor is a route to an action, not a mode that survives that
    // action. Its next immutable reading decides whether the resulting controls remain
    // open.
    if (activated && consumesFocusedOwner) {
      expandedOptionsKey = null;
      expandedOptionsOwner = null;
      renderAnnotations.refresh();
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
                contributionEntryRecord(candidate)?.key === focus.focusedRecord.key &&
                contributionEntryRecord(candidate)?.owner === focus.focusedRecord.owner,
            )
          : null) ??
        primary ??
        clusterMarginEntries(options)[0] ??
        clusterMarginEntries(host)[0];
      (next ?? document.body).focus({ preventScroll: true });
    }
    return primary;
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
    renderAnnotations.refresh();
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

  function renderNow(inventory) {
    const threadOwnerHeld =
      transferThreadFocus || document.activeElement === previewMarginEntry;
    transferThreadFocus = false;
    // Before the card, which anchors to its rows (`mount`).
    if (!nav.isConnected)
      chromeRoot.insertBefore(nav, preview.parentNode === chromeRoot ? preview : null);
    pageInventory = inventory;
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
        marker = presentContributionEntry(
          readingControl("lf-margin-marker"),
          contributionEntry({
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
          ? contributionEntryRecord(document.activeElement)
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
        syncContributionAgentWorkflow(primary, entry.workflowReceipt);
        nextWorkflowCarriers.add(primary);
      }
    });
    for (const control of workflowCarriers)
      if (!nextWorkflowCarriers.has(control))
        syncContributionAgentWorkflow(control, null);
    workflowCarriers = nextWorkflowCarriers;
    nameMarkers(readSpokenPositions(pageInventory));
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

  function buildThreadCard(entry, requestedItem = null, origin = null) {
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
      clearThreadTransition();
      carryCommentFrame(origin);
      if (origin) previewSide.adopt(origin.frame);
      else previewSide.forget();
      previewHold = null;
    }
    const latest = selected ? turns(sourceItem(selected).thread).at(-1) : null;
    const messageSelector =
      ":scope > .lf-margin-thread > .lf-margin-thread-body > " +
      ".lf-page-thread > .lf-thread-transcript > .lf-msg";
    const replySelector =
      ":scope > .lf-margin-thread > .lf-margin-thread-body > " +
      ".lf-page-thread > .lf-thread-reply";
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
      atScrollEnd(previewTranscript);
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
    };
    if (!arriving && previewPlace) previewPlace.around(present);
    else {
      present();
      if (previewTranscript) previewTranscript.scrollTop = 0;
    }
    previewLatest = latest && { thread: selected.id, id: latest.id, text: latest.text };
    if (follow) scrollToEnd(previewTranscript);
    // Fit the new content after restoring the reader but before paint; a deferred
    // pass exposes the previous height limit and makes a sent reply grow twice.
    placeThreadPreview();
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
                Boolean(await openPageThread(thread, { focus: "thread", intent: may }))
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

  function showPreview(entry, button, threadItem = null, origin = null) {
    if (!entry || designModeActive()) return;
    if (forcedInlineKey && forcedInlineKey !== entry.key) forcedInlineKey = null;
    if (previewEntry && previewEntry.key !== entry.key) clearThreadTransition();
    previewEntry = entry;
    transferThreadCard(button);
    buildThreadCard(entry, threadItem, origin);
    keepsHidden(preview, false);
    previewList.firstElementChild?.scrollIntoView({
      behavior: scrollBehavior(),
      block: "nearest",
    });
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
  }

  function closePreview(returnFocus = false) {
    carryCommentFrame(null);
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
      void openPageThread(sourceItem(choice.items[0]).thread.id);
      return;
    }
    if (expandedOptionsKey && expandedOptionsKey !== entry.key)
      setOptionsOpen(entry, false);
    // A thread a widget holds out of its flow, so as to move nothing the user reads,
    // has this marker for its notice: pressing it shows the thread where the widget
    // draws it, and lands the user there (thread/held-news.js).
    if (showHeld(choice.items.map((item) => sourceItem(item).thread.id))) {
      closePreview();
      return;
    }
    togglePinned(entry, button);
  }

  // `unfold: false` is a card that accompanies where the user stands rather than one
  // they asked for: it hangs from the cluster's visible marker instead of unfolding the
  // cluster to reach the thread's own entry, so arriving somewhere changes no margin.
  function openInlineThread(id, { transition = null, unfold = true } = {}) {
    const itemId = marginThreadItem(threadNames(allThreads()).get(id));
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
      else renderAnnotations.refresh();
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
    const initiallyPositioned = showPreview(entry, button, itemId, transition);
    const item = [...previewList.children].find(
      (candidate) => candidate.lfMarginItem === itemId,
    );
    const thread = item?.querySelector(".lf-page-thread") ?? null;
    const positioned = transition
      ? revealThread(transition, entry, initiallyPositioned)
      : initiallyPositioned;
    return thread && { thread, presented: positioned };
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
      if (!selected.has(control)) syncContributionSelection(control, false);
    for (const control of selected) syncContributionSelection(control, true);
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
  // belongs where a thread's target is decided (anchor-placement), so every
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
  // The conversation accompanying a page target while no Thread holds focus.
  // Core reads held identity first, including inside widget shadow roots.
  const accompaniedThreadHere = () => {
    const active = focused();
    if (panelIsOpen()) {
      const entry = active && !panel.contains(active) && threadEntryAt(active);
      return entry ? accompaniedThread(threadIdsOf(entry)) : null;
    }
    if (!pinnedKey || previewEntry?.key !== pinnedKey || !previewOpen() || previewAway)
      return null;
    const threads = previewList.querySelectorAll(".lf-margin-thread .lf-page-thread");
    return threads.length === 1 ? threads[0] : null;
  };
  const previewFocusTarget = (id, { focus = null } = {}) => {
    id = threadNames(allThreads()).get(id)?.id ?? id;
    const thread = [...previewList.querySelectorAll(".lf-page-thread")].find(
      (candidate) => candidate.dataset.thread === id,
    );
    return thread ? threadFocusDestination(thread, { focus: focus ?? "thread" }) : null;
  };
  // The page target this owner's chrome shows (standing-target.js): a margin cluster
  // control's and the card's — its threads and its own controls.
  declareSide((node) => {
    const projected = marginTargetAt(node);
    if (projected) return projected;
    if (preview.contains(node)) return targetFor(previewEntry);
    return null;
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
                key: contributionEntryRecord(control)?.key,
                owner: contributionEntryRecord(control)?.owner ?? null,
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
        contributionEntryRecord(candidate)?.key === standing.focus.key &&
        (contributionEntryRecord(candidate)?.owner ?? null) === standing.focus.owner,
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
    previewClose.onclick = () => closePreview(true);
    preview.addEventListener("focusout", (event) => {
      const row = event.target.closest?.(".lf-thread-reply");
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
    document.addEventListener("scroll", () => scheduleRoving(), {
      capture: true,
      passive: true,
    });
    window.addEventListener("resize", () => scheduleWidthRender());
    renderAnnotations();
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
    releaseForMap: (entry) => {
      if (expandedOptionsKey && expandedOptionsKey !== entry.key)
        setOptionsOpen(entry, false);
      closePreview();
    },
    mapFocusTarget: (entry) => {
      const visible = visibleRows();
      return entry
        ? (rows.get(entry.key) ?? null)
        : (visible.find((row) => row.tabIndex === 0) ?? visible[0] ?? null);
    },
    targetFor,
    paint: renderNow,
    flushLayout: layoutMarginRows,
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
    threadPreview: {
      open: openInlineThread,
      focusTarget: previewFocusTarget,
      accompanied: accompaniedThreadHere,
      close: closePreview,
    },
    paintSelectedMarginEntries,
    marginEntryChoices,
    unfoldedMarginEntries,
    foldMarginEntryOptions,
    captureStanding,
    restoreStanding,
    mount,
  };
}
