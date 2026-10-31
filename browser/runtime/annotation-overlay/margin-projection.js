/* Overlay annotation clusters and contextual Thread cards.

   The application supplies the neutral annotation inventory and its live target/action
   directory. This renderer selects clusters and controls from those readings; it does
   not gather Threads, the On lists, workflows or contributed actions. Shared contribution
   controls retain native entries across page and frozen-Thread seats. This renderer's
   Lit view owns direct/disclosed child order; margin-layout.js owns rail/pin posture,
   lanes and packing. Page Map consumes the inventory independently of this renderer.

   Keyboard and pointer expansion share one state. Focus arrival through Tab unfolds a
   compact cluster, Left and Right walk it, and Escape folds only the layer that gesture
   opened. A pin the layout found no room for stands folded to its toggle
   (`standsFolded`, margin-model.js's `canFold`), and the same state opens it. Page Map
   and Go-to arrivals activate the exact visible control; they do not choose another
   action for the user.

   thread-preview.js owns the contextual card and its selected conversation's
   lifetime. The margin supplies its anchor control and manages cluster disclosure.
   A card accompanies the page target the user arrives at (current-target.js,
   `arrivalOf`), an obligation included: `m` lands
   on an obligation and its discussion opens beside it, clear of its options. Keeping the card
   shut while the user works an obligation was tried and rejected, since the user walks to an
   obligation to read its discussion with it. followCurrentLocation and the
   shared keyboard ladder decide when that relationship ends. It is margin chrome:
   target, cluster and card are one place. Being elsewhere on the page, releasing the target,
   or pressing outside that place dismisses it. Escape inside closes it beside the target;
   Send keeps focus on its thread. The card shows
   the threads of the innermost target holding the user's place that has any (its own,
   else an enclosing one's), never those of a target inside it: a thread on an obligation's
   options shows from the options, not from the obligation (`threadEntryAt`).

   Each frozen cluster model names controls by contribution and entry identity. The Lit view
   retains their native nodes, so a state refresh cannot cancel a held pointer or move focus.
   A print-media render is deferred until screen media returns because print removes the
   injected controls and cannot supply their geometry.

   This owner holds margin geometry and disclosure. The application's annotation
   pass owns refresh, clocks, contribution updates and print deferral; local geometry
   gestures request that same pass. Mount binds the overlay's mechanical lifecycle. */

import { createThreadPreview } from "./thread-preview.js";

import { afterScript, cancelRender, nextRender } from "../rendering.js";
import { spokenSubject } from "../contribution-model.js";
import {
  layoutMarginRows,
  marginColumn,
  mountMarginLayer,
  paintedBox,
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
  presentContributionReceipts,
  syncContributionSelection,
  syncContributionUnread,
} from "../contribution-controls.js";
import {
  entryEngaged,
  focusedOfferOf,
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
  spokenContext,
  clusterProjection,
} from "../margin-model.js";

import { move } from "../dom-move.js";

import {
  declareRelease,
  focusDestination,
  handBack,
  holdFocus,
  layerLanding,
  letGo,
  onPressAway,
  onCurrentLocation,
  pressLed,
  focused,
  closeLayer,
  rove,
  currentLocationIn,
} from "../focus.js";

import { el, generatedElement, offer } from "../widget-elements.js";
import { keeps, keepsHidden } from "../keeps.js";

import { PRESS, cycledRow, rowArrows } from "../keyboard/bindings.js";
import { beginWalk, listWalkPosition, rowWalk } from "../walk-position.js";

import { readingRegionFor } from "../reading-regions.js";

import { keys, paintKeys } from "../keyboard/scopes.js";
import { pageRung, pageScope } from "../keyboard/register.js";
import { nativeLayerHolding } from "../shadow-tree.js";

import { annotationsHidden, watchAnnotations } from "./annotation-layer.js";
import { repaint } from "../repaint.js";
import { chromeRoot, chromeForeground } from "../chrome.js";
import { arrivalOf, declareSide } from "../current-target.js";
import { closestAcross, inChrome } from "../passages.js";
import { visualAt } from "../anchor-resolution.js";
import { paintTrace } from "../target-paint.js";

import { threadNamed } from "../thread/state.js";
import { carryingThreadPlace, currentLocationThreadId } from "../thread/focus.js";

import { claimed, revealHeld } from "../thread/surfaces.js";

import { createMarginClusterViews } from "./margin-cluster-view.js";

import { seenRect, shownWindow, watchRoom } from "../geometry.js";
import { skipped } from "../shown-box.js";

import { hostIn, renderedUnder, under } from "../shadow.js";
import { retainUserIntent } from "../user-intent.js";

export function createMarginProjection({
  inventory,
  refreshInventory,
  renderAnnotations,
  openPageThread,
  designModeActive,
  pointerModeActive,
  leavePageMap,
  openPageMap,
  pageMapDialogContains,
  scrollThreadIntoView,
  renderMarginThread,
  placedAt,
  marksFor,
  scrollToElement,
  openInPanel,
}) {
  const {
    targetFor,
    entryPoint,
    entryPlace,
    entryPassage,
    sourceItem,
    workflowReceipt,
    threadIdsAt,
    threadItem: marginThreadItem,
  } = inventory;
  const nav = el("nav", "lf-ui lf-margin-projection");
  // Every live page can gain an anchored comment, including one made entirely of prose.

  generatedElement(nav, { says: false });
  nav.setAttribute("aria-label", "Page Map");
  const toolbar = el("div", "lf-margin-toolbar");
  toolbar.setAttribute("role", "toolbar");
  toolbar.setAttribute(
    "aria-label",
    "Changes, threads, items on me, delivery status, and activity",
  );
  nav.append(toolbar);

  const card = createThreadPreview({
    inventory,
    renderMarginThread,
    placedAt,
    scrollThreadIntoView,
    scrollToElement,
    openInPanel,
    onClose: closedPreview,
  });
  const preview = card.element;
  const previewOpen = card.isOpen;
  let selectedReadingCarriers = new Set();
  const readingMarginEntries = new Map();
  const hosts = new Map();
  function* markerRows() {
    for (const host of hosts.values()) yield host.marker;
  }
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
      const marker = hosts.get(entry.key)?.marker;
      const name = markerName(entry, index, walked.length, position);
      paintMarker(marker, entry, hosts.get(entry.key).primary, {
        suppressed: Boolean(
          focusedOfferOf(entry, expandedOptionsKey, expandedOptionsOwner),
        ),
        accessibleLabel: name,
      });
    });
  }
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
  let transferThreadFocus = false;
  const forcedInlineOptionsKey = () => {
    const selected = card.selection();
    return selected?.disclosed ? selected.entry.key : null;
  };
  let expandedOptionsKey = null;
  // Whether an entry's pin stands folded is the layout's answer (`standsFolded`); the
  // gesture that opens any options opens a folded one.
  const folded = (entry) => standsFolded(hosts.get(entry.key));
  let refoldQueued = false;
  // An explicit mode can focus one contribution inside the target's existing cluster.
  // The rail then shows that owner's complete control set without spending margin entries on
  // readings in force or unrelated actions; Page Map still reads the whole entry.
  let expandedOptionsOwner = null;
  let hoveredHost = null;
  let highlighted = null;
  let highlightFrame = 0;
  let rovingFrame = 0;
  // A native layer over the page (a modal, or a popover) or a contextual thread surface
  // temporarily owns focus without ending the document interaction beneath it. Preserve
  // that context so its commands remain true and its owning margin entry can receive
  // focus when the surface closes.
  const inRetainedContext = (node) =>
    node instanceof Element &&
    (Boolean(nativeLayerHolding(node)) || under(node, preview));
  function readingMarginEntry(entry, kind) {
    const marker = hosts.get(entry.key)?.marker;
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
          title: "open / close",
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
  // whether it is open. Two shapes reach it. A thread margin entry opens the local card.
  // Any other reading is
  // asked what it discloses, and a single item
  // that answers has named the node and said which way it stands — the Change reading's
  // inline text diff. An item answering nothing promises nothing, which is what leaves a
  // Change margin entry over a block the comparison cannot align for the plain travel it
  // always was.
  function syncReadingRelation(control, choice) {
    if (choice?.kind === "comment") {
      keeps(control, "aria-controls", preview.id);
      keeps(control, "aria-expanded", card.selection()?.control === control);
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
  function scheduleWidthRender() {
    if (widthFrame) return;
    widthFrame = nextRender(() => {
      widthFrame = 0;
      renderAnnotations.refresh();
    });
  }

  // A viewport posture change can replace the focused full thread with its
  // compact action. Reconcile after resize delivery so the browser can finish its
  // own focus and popover bookkeeping before that node changes shape. Panel
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
      passage: () => entryPassage(row.lfEntry),
      order,
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
        // Whether the pin, while folded, shows its options beside the toggle. The
        // row's own `data-lf-options-open` describes the face it stands in now, and an
        // unfolded face shows its peers inline, so a row this pass folds reads it open.
        open: () =>
          clusterProjection(row.lfEntry, {
            expandedKey: expandedOptionsKey,
            expandedOwner: expandedOptionsOwner,
            folded: true,
          }).optionsOpen,
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
    const userContext = spokenContext(choice);
    const subject =
      count === 1 && choice.items[0].workflowFace ? choice.text : entry.title;
    // A lone item's own words, such as a to-do's title, which its subject does not say.
    const own = count === 1 ? choice.items[0].label : null;
    const said = own && !subject?.includes(own) ? `, ${own}` : "";
    const reading = `${face.label}${count > 1 ? `s (${count})` : ""}${said}${userContext ? `, ${userContext}` : ""}`;
    return `${reading}, ${index + 1} of ${anchored}${position == null ? "" : `, ${Math.max(0, Math.min(100, position))} percent down`}, ${spokenSubject(subject)}`;
  }

  // A row hidden with the annotation layer is not one the keyboard can land on either.
  function availableRows() {
    return [...markerRows()].filter(
      (row) =>
        !row.hidden &&
        !row.closest(".lf-withheld") &&
        row.checkVisibility({ visibilityProperty: true }),
    );
  }

  // Where a row's marker is painted (margin-layout.js, `paintedBox`).
  const markerBox = (row) =>
    paintedBox(row, closestAcross(row, "[data-lf-margin-for]"));

  // The rows in front of the user (`seenRect`): one under the floating panel,
  // or scrolled out of a pane, is no row the walk or the rail's way in may land on.
  function visibleRows() {
    const clips = new Map();
    return availableRows().filter((row) => seenRect(row, clips, markerBox(row)));
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
    const direction = binding === rowArrows(active)[1] ? 1 : -1;
    focusDestination(cycledRow(buttons, active, direction), "move");
    beginWalk("margin-entry", "Action", () => {
      const currentLocation = focused();
      const currentLocationHost = closestAcross(
        currentLocation,
        "[data-lf-margin-for]",
      );
      return listWalkPosition(
        clusterMarginEntries(currentLocationHost),
        currentLocation,
      );
    });
  }

  // Folding a cluster the user was in hands them back to its toggle.
  const landOnToggle = (entry) =>
    layerLanding(() => handBack(hosts.get(entry.key)?.more));
  function setOptionsOpen(
    entry,
    open,
    { land = null, focusOption = null, owner = null, preservePreview = false } = {},
  ) {
    const previousKey = expandedOptionsKey;
    const previousOwner = expandedOptionsOwner;
    const nextKey = open ? (entry?.key ?? null) : null;
    const nextOwner = open ? owner : null;
    if (previousKey === nextKey && expandedOptionsOwner === nextOwner) return;
    if (card.selection()?.entry && !preservePreview) closePreview();
    expandedOptionsKey = nextKey;
    expandedOptionsOwner = nextOwner;
    const paint = () => {
      // Folding is closing a layer (focus.js, `closeLayer`): the refresh moves no one, and
      // a closer that names a landing, as the fold's own Escape does, puts the user there.
      if (!open) {
        closeLayer(() => renderAnnotations.refresh(), land);
        return;
      }
      renderAnnotations.refresh();
      if (focusOption && nextKey) {
        const choices = clusterMarginEntries(hosts.get(nextKey)?.options);
        const fallback = clusterMarginEntries(hosts.get(nextKey));
        const next =
          (focusOption === "last" ? choices.at(-1) : choices[0]) ??
          (focusOption === "last" ? fallback.at(-1) : fallback[0]);
        // The arrival unfolding the cluster carries on to the action it lands on.
        if (next) focusDestination(next, "return");
      }
    };
    // Opening needs controls before the caller reads availability. Closing paints
    // the end of the gesture, where a submitted action replaces its contribution. Its
    // return is a `return`, which opens nothing (`arriveAtCluster`).
    if (open) paint();
    else afterScript(paint);
    if (previousOwner === "responses")
      document.dispatchEvent(new CustomEvent("lf-margin-entry-options-closed"));
  }

  // A placement on a margin control, revealing its row first where annotations are
  // hidden: `focusDestination`'s call, with its cause.
  function focusForNavigation(control, cause, options) {
    reveal(control);
    focusDestination(control, cause, options);
  }

  // Obligation decisions name a semantic entry through whichever retained projection control
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
    if (!entry || !entryHasMarginHost(entry)) return null;
    // A preview can own this entry's disclosure. Closing it may retire that fold,
    // so read the state to restore only after the preview has let it go.
    if (card.selection()?.entry) closePreview();
    const alreadyOpen = expandedOptionsKey === entry.key;
    const previousOwner = alreadyOpen ? expandedOptionsOwner : null;
    setOptionsOpen(entry, true, { owner });
    // The caller borrows this disclosure. Its release restores a fold already open
    // on this entry, or closes the fold it opened. A later gesture can take ownership
    // or move to another entry; releasing this borrow must leave that gesture alone.
    return () => {
      if (expandedOptionsKey !== entry.key || expandedOptionsOwner !== owner) return;
      setOptionsOpen(alreadyOpen ? entry : null, alreadyOpen, {
        owner: previousOwner,
      });
    };
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
    return control === hosts.get(entry.key)?.marker
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
    focusForNavigation(control, "press");
    control.click();
    return true;
  }

  // Where the Map hands the user back, for `handBack`: the entry's own marker, then a
  // row in view.
  function mapControlPlaces(entry = null) {
    const visible = visibleRows();
    return [
      entry ? hosts.get(entry.key)?.marker : null,
      visible.find((row) => row.tabIndex === 0) ?? visible[0],
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
    rove(markerRows(), stop);
  }

  function syncRoving() {
    const available = availableRows();
    const visible = visibleRows();
    if (!available.length) {
      holdTabStop(null);
      return;
    }
    const currentLocation = available.find((row) => row === focused());
    const candidates = visible.length ? visible : available;
    // The stop is the highest row in view, or with none in view the row nearest the
    // window, whatever held it before, so the way in follows from the page as it
    // stands rather than from the widths and scrolls it passed through. A stop kept
    // where it stood while in view moved for good once a narrower width had shown
    // another row first.
    const room = shownWindow();
    const place = (row) => {
      const box = markerBox(row);
      const away =
        box.bottom < room.top
          ? room.top - box.bottom
          : box.top > room.bottom
            ? box.top - room.bottom
            : 0;
      return [away, box.top, box.left];
    };
    const before = (a, b) => a[0] - b[0] || a[1] - b[1] || a[2] - b[2];
    const nearest = () =>
      candidates
        .map((row) => ({ row, at: place(row) }))
        .reduce((best, next) => (before(next.at, best.at) < 0 ? next : best)).row;
    const next = currentLocation ?? nearest();
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
  // that the user could be in: the card closes through its ordinary close, an
  // unfolded cluster folds, and focus held by a pin goes to the pin's target, since the
  // browser would otherwise put it on body. An explicit request still shows what it asks
  // for without bringing the layer back: `t`, a Threads row and a Page Map pick open the
  // card at their target, and an arrival that walks to a target or to one of its row's
  // controls (`m`, `focusForNavigation`) shows that one row, so what decides the target
  // is in reach, until the user is somewhere else. Tabbing or pressing onto a target
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
  function currentLocationHost(node) {
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
  const reveal = (node) =>
    revealHost(annotationsHidden() ? currentLocationHost(node) : null);
  onCurrentLocation((node) => {
    if (
      node &&
      revealed &&
      !revealed.contains(node) &&
      !(revealed.lfTarget && under(node, revealed.lfTarget))
    )
      revealHost(null);
  });
  // A cluster the user enters. Any arrival there outranks a pointer parked on
  // the previous target, which real pointer movement can take back without a press. The
  // keyboard arriving on one of its controls, a step or a route a key began, also opens
  // what it offers; a press opens it at its click, and a return opens nothing. A folded
  // cluster's toggle is its only control and stands after the actions it unfolds, so
  // Tab arriving on it lands on the first of them, and Shift+Tab on the last.
  function arriveAtCluster(host, node, cause, left) {
    hoveredHost = null;
    refreshHighlight();
    const control = node.closest?.(".lf-margin-entry");
    if (
      !(cause === "step" || (cause === "move" && !pressLed())) ||
      !control ||
      !host.contains(control)
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
    if (!current || !(standsFoldedNow || optionsOffered(current, primary))) return;
    if (expandedOptionsKey === current.key && expandedOptionsOwner) return;
    if (entryEngaged(current)) return;
    const from = left && hostIn(left, host.getRootNode());
    const back = Boolean(
      from && host.compareDocumentPosition(from) & Node.DOCUMENT_POSITION_FOLLOWING,
    );
    setOptionsOpen(current, true, {
      focusOption:
        control === host.more ? (standsFoldedNow && !back ? "first" : "last") : null,
    });
  }
  onCurrentLocation((node, cause, left) => {
    if (!node) return;
    for (const host of hosts.values())
      if (host.contains(node)) return arriveAtCluster(host, node, cause, left);
  });
  // Leaving a cluster folds what it unfolded, unless the user went into a surface that
  // keeps its context (`inRetainedContext`). A node hidden under the user leaves it too,
  // as its blur did. A node removed from under them is in no cluster any more, and the
  // render that removed it hands them on to its replacement, often a frame later, so it
  // folds nothing. A window losing focus moves no one.
  onCurrentLocation((node, cause, left) => {
    if (!left) return;
    for (const host of hosts.values()) {
      if (!under(left, host) || (node && under(node, host))) continue;
      nextRender(refreshHighlight);
      const current = host.lfEntry;
      if (current && expandedOptionsKey === current.key && !inRetainedContext(node))
        setOptionsOpen(current, false);
    }
  });
  // The keyboard arrival waiting for its margin row to show (`accompany`).
  let awaitingRow = null;
  watchAnnotations((hidden) => {
    if (hidden) {
      const holding = closestAcross(focused(), ".lf-margin-cluster");
      if (holding?.dataset.lfPlace === "pin" && holding.lfTarget?.isConnected)
        focusDestination(holding.lfTarget, "return");
      if (previewOpen()) closePreview();
      awaitingRow = null;
      expandedOptionsKey = null;
      expandedOptionsOwner = null;
    }
    revealHost(null);
    renderAnnotations.refresh();
    repaint();
  });

  let marginKeysAvailable = false;
  const marginKeys = [
    {
      id: "margin.controls",
      keys: ["ArrowLeft", "ArrowRight"],
      title: "move through margin entries",
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
    // Tab from the entry a card hangs from enters the card (thread-preview.js).
    ...card.openerKeys,
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

  // Markers and disclosed readings share one state presentation; their seats keep
  // their own names, visibility, keyboard position, and activation.
  function presentReading(
    node,
    entry,
    choice,
    { accessibleLabel = null, writesSeat = true } = {},
  ) {
    const items = choice?.items ?? [];
    const face = readingFace(choice);
    const behavior = readingBehavior(face);
    const line = readingContext(choice);
    node.lfEntry = entry;
    presentContributionEntry(
      node,
      contributionEntry({
        key: `reading:${choice?.key ?? "none"}`,
        icon: face.icon,
        label: readingLabel(choice),
        // A lone receipt's label is its workflow's word, said by whoever says it; a
        // group's is its kind's name.
        voice: face.voice ?? null,
        context: line,
        behavior,
        rank: "reading",
        state: readingState(choice),
        count: items.length,
        accessibleLabel,
      }),
      { writesRelation: false, writesSeat },
    );
    presentContributionReceipts(node, workflowReceipt(items), awaitingUser(items));
    syncReadingRelation(node, choice);
    syncContributionUnread(node, unreadIn(items));
    return behavior;
  }

  function paintMarker(
    row,
    entry,
    primary,
    { suppressed = false, accessibleLabel = null } = {},
  ) {
    const { kinds: markerKinds } = markerFace(entry);
    const choice = primaryReading(entry);
    keepsHidden(row, suppressed || markerKinds.length === 0 || Boolean(primary));
    keeps(row, "data-lf-kinds", markerKinds.map(({ kind }) => kind).join(" "));
    const behavior = presentReading(row, entry, choice, {
      accessibleLabel,
      writesSeat: false,
    });
    row.onclick = behavior === "status" ? null : pressMarker;
    if (row.lfTakeFocus) {
      delete row.lfTakeFocus;
      if (!row.hidden) focusDestination(row, "return");
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
    const count = choice.items.length;
    const kind = count > 1 ? `${face.label}s` : face.label;
    const userContext = spokenContext(choice);
    const behavior = presentReading(node, entry, choice, {
      accessibleLabel: `${kind} for ${spokenSubject(entry.title)}${count > 1 ? `, ${count} items` : ""}${userContext ? `, ${userContext}` : ""}`,
    });
    node.lfChoice = choice;
    keeps(node, "data-lf-kinds", choice.kind);
    node.onclick =
      behavior === "status"
        ? null
        : () => {
            if (node.lfChoice.kind !== "comment") {
              setOptionsOpen(node.lfEntry, false, { land: landOnToggle(node.lfEntry) });
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
      reveal,
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

  function presentCluster(host, marker, more, entry, projection, focus) {
    // Retiring a focused projection drops focus to the body, which reaches no reader
    // while the transfer below puts the user back in the same script, and a drop where
    // none does (focus.js, `onCurrentLocation`).
    const primary = host.present(projection);
    const options = host.options;
    const lostOptionFocus = focus.focusedOption && !currentLocationIn(options);
    const lostPrimaryFocus = focus.focusedPrimary && !currentLocationIn(host);
    if (!projection.hasOptions && (focused() === more || lostOptionFocus)) {
      const destination = primary ?? (primaryReading(entry) ? marker : null);
      if (destination === marker && marker.hidden) marker.lfTakeFocus = true;
      else if (destination) focusDestination(destination, "return");
    } else if (focus.focusedToggle && more.hidden) {
      // An unfolded face shows its options inline and hides the toggle that opened
      // them, as a folded pin does when `e` stands reactions in it: the user goes on to
      // the first of them, as a press on the toggle would land them.
      focus.restore?.(
        clusterMarginEntries(options)[0],
        primary,
        clusterMarginEntries(host)[0],
      );
    } else if (lostOptionFocus || lostPrimaryFocus) {
      // A changed contribution can replace either the focused primary or an option.
      // Return to the corresponding control in the new projection.
      focus.restore?.(
        primary,
        clusterMarginEntries(options)[0],
        clusterMarginEntries(host)[0],
      );
    }
  }

  function unfoldOpenThreadOwner(entry) {
    const previousOwner = expandedOptionsOwner;
    expandedOptionsKey = entry.key;
    expandedOptionsOwner = null;
    renderAnnotations.refresh();
    if (previousOwner === "responses")
      document.dispatchEvent(new CustomEvent("lf-margin-entry-options-closed"));
  }

  function renderNow(inventory) {
    const selected = card.selection();
    const forcedKey = selected?.forced ? selected.entry.key : null;
    const threadOwnerHeld = transferThreadFocus || focused() === selected?.control;
    transferThreadFocus = false;
    if (!nav.isConnected) move(chromeRoot, nav, chromeForeground);
    pageInventory = inventory;
    // A thread gone from the margin takes the reply being written in it out of the card,
    // open or closed, to where the thread now stands (thread/replies.js): the card can
    // draw it no more. Before the card closes, so a user writing there goes on in it.
    card.releaseLeft(
      new Set(pageInventory.flatMap((entry) => entry.items.map((item) => item.id))),
    );
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
    for (const [key, host] of hosts)
      if (!liveHosts.has(key)) {
        unregisterMarginRow(host);
        host.clear();
        host.remove();
        hosts.delete(key);
      }
    pageInventory.forEach((entry, order) => {
      if (!entryHasMarginHost(entry)) return;
      let host = hosts.get(entry.key);
      let marker = host?.marker;
      let more = host?.more;
      if (host) host.lfEntry = entry;
      if (!host) {
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
        hosts.set(entry.key, host);
      }
      registerMarginRow(host, markerOptions(host, order));
      // Insert in inventory order; the theme keeps the row unpainted and measurable
      // until the layout pass assigns its anchored posture.
      if (!host.isConnected)
        move(
          toolbar,
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
        focusedPrimary: Boolean(host.primary && currentLocationIn(host.primary)),
        focusedOption: Boolean(host.options && currentLocationIn(host.options)),
        focusedToggle: focused() === more,
        // The entry the user is on, by its contribution's key, across the projection
        // that may replace its control (focus.js, keyed `holdFocus`).
        restore: holdFocus(host, { key: "data-lf-margin-entry-identity" }),
      };
      const projection = clusterProjection(entry, {
        expandedKey: expandedOptionsKey,
        expandedOwner: expandedOptionsOwner,
        forcedInlineKey: forcedKey,
        folded: folded(entry),
      });
      if (!projection.hasOptions && expandedOptionsKey === entry.key) {
        expandedOptionsKey = null;
        expandedOptionsOwner = null;
      }
      presentCluster(host, marker, more, entry, projection, focus);
    });
    nameMarkers(readSpokenPositions(pageInventory));
    keepsHidden(nav, pageInventory.length === 0);
    keeps(nav, "aria-label", `Page Map, ${pageInventory.length} locations`);
    if (selected) {
      const fresh = pageInventory.find((entry) => entry.key === selected.entry.key);
      if (!fresh || !fresh.items.some((item) => item.kind === "comment"))
        closePreview();
      else {
        const owner = threadMarginEntry(fresh);
        if (
          owner &&
          !owner.checkVisibility() &&
          forcedKey !== fresh.key &&
          expandedOptionsKey !== fresh.key &&
          !hosts.get(fresh.key)?.more?.hidden
        ) {
          transferThreadFocus = threadOwnerHeld;
          unfoldOpenThreadOwner(fresh);
          return;
        }
        if (!owner || (!owner.checkVisibility() && forcedKey !== fresh.key))
          closePreview();
        else {
          card.refresh(fresh, owner, threadOwnerHeld);
          for (const row of markerRows())
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
    if (marginKeysAvailable !== pageInventory.length > 0) {
      marginKeysAvailable = pageInventory.length > 0;
      paintKeys();
    }
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
    // A user on the card's target itself already has its ring there; the
    // trace would paint over the one mark that says where they are.
    const onTarget =
      previewOpen() && active && active === targetFor(card.selection()?.entry);
    const marker = pointerHost ?? focusedHost;
    const source =
      marker ??
      ((renderedUnder(active, preview) || previewOpen()) && !onTarget
        ? hosts.get(card.selection()?.entry?.key)
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
    // So does the thread the user is in, where anchor paint marks it: its words lit,
    // or its element's contour (anchor-paint.js, `paintCurrentLocation`). A card whose thread
    // the user is in draws no box round its block. One the user stepped out of while
    // it stays open, into the floating panel or with a press on the block, keeps the
    // trace as its only mark, as does one on a thread anchor paint leaves unmarked, such
    // as a resolved thread whose reply is still being written. A marker under the
    // pointer or the keyboard still traces its block.
    const currentLocation = currentLocationThreadId();
    const currentLocationShown =
      !marker &&
      entry &&
      marksFor(currentLocation).length > 0 &&
      threadReading(entry)?.items.some(
        (item) => sourceItem(item).thread.id === currentLocation,
      );
    highlight(drawingOnly || currentLocationShown ? null : (targetFor(entry) ?? null));
  }

  function previewChanged() {
    refreshHighlight();
    for (const row of markerRows())
      syncReadingRelation(row, primaryReading(row.lfEntry));
    for (const button of readingMarginEntries.values())
      syncReadingRelation(button, button.lfChoice);
    paintKeys();
  }

  function showPreview(
    entry,
    control,
    threadItem = null,
    { origin = null, accompanies = false, forced = false } = {},
  ) {
    if (designModeActive()) return null;
    const previous = card.selection();
    const disclosed =
      (previous?.disclosed && previous.entry.key === entry.key) ||
      (forced && !control?.checkVisibility() && expandedOptionsKey !== entry.key);
    const positioned = card.show({
      entry,
      control,
      threadItem,
      origin,
      accompanies,
      forced,
      disclosed,
      prepare: () => {
        retirePreviewDisclosure(previous, entry);
        if (disclosed && expandedOptionsKey !== entry.key)
          setOptionsOpen(entry, true, { preservePreview: true });
        else if (forced && !control?.checkVisibility()) renderAnnotations.refresh();
        return accompanies ? control : threadMarginEntry(entry);
      },
    });
    previewChanged();
    return positioned;
  }

  function togglePinned(entry, button) {
    const selected = card.selection();
    if (selected?.entry.key === entry.key && selected.control === button) {
      closePreview();
      return;
    }
    card.focusThread(showPreview(entry, button));
  }

  // Closing the card hands a user who was in it on (focus.js, `closeLayer`). A close
  // aimed at the card itself, its Close or its Escape, hands them back to the margin
  // entry it hangs from (`landOnEntry`); any other, a mode or a rerender, lets them go.
  // A user the thread pass is carrying with its thread to where it now stands is that
  // pass's to land (thread/focus.js, `carryingThreadPlace`), so the close places no one.
  const landOnEntry = layerLanding((button) =>
    handBack(button, ...(button?.lfEntry ? mapControlPlaces(button.lfEntry) : [])),
  );
  /** @param {(control?: HTMLElement) => unknown} [land] */
  function closePreview(land = () => letGo()) {
    const button = card.selection()?.control;
    const at = focused();
    const heldInside = currentLocationIn(preview) && !carryingThreadPlace(at);
    closeLayer(() => card.close(), heldInside && (() => land(button)));
    paintKeys();
  }
  function retirePreviewDisclosure(previous, next = null) {
    if (
      previous?.disclosed &&
      previous.entry.key !== next?.key &&
      expandedOptionsKey === previous.entry.key
    )
      setOptionsOpen(null, false, { preservePreview: true });
  }
  function closedPreview(selection) {
    retirePreviewDisclosure(selection);
    previewChanged();
  }

  // The thread view, for the owners that open and close it from outside. What
  // takes it off again is the Page Map's own Escape step, read off the card that is open
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
  // The card is one step, from inside it as from the entry it hangs from or the target
  // it accompanies: the press takes it down and leaves the user beside its target. Tab
  // goes on from there, so into a target's own controls, such as an ask's options,
  // with the card coming back beside them, and a walk resumes from that thread.
  // One press is on trial from 2026-10-29, while the user tries it in use. It replaced
  // a middle step out onto the target with the card still up, which only the focus
  // ring told apart from the card: after a click its first press left the card up and
  // only drew a ring on the target. What that step reached is a Tab away, and the keys
  // a target forwards, such as an option's number, answer from inside the card. If
  // the trial fails, `git log -S '"back to element"'` finds the step to restore.
  // A cluster the user unfolded themselves and opened the card from is a level of
  // their own under the card, and the card hands back to it instead (below).
  const unfoldedUnder = () => {
    const entry = card.selection()?.control?.lfEntry;
    return Boolean(
      entry &&
      expandedOptionsKey === entry.key &&
      expandedOptionsKey !== forcedInlineOptionsKey() &&
      optionsRung(),
    );
  };
  // The target a close from inside the card lands beside, where it is still drawn.
  const besideTarget = () => {
    const target = targetFor(card.selection()?.entry);
    return currentLocationIn(preview) && target?.isConnected && target.checkVisibility()
      ? target
      : undefined;
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
        !renderedUnder(active, preview) &&
        !(card.selection()?.control && host?.contains(card.selection()?.control)))
    )
      return null;
    return {
      root: preview,
      title: "dismiss thread",
      // Where it lands turns on whether a level of the user's own stands under it. A
      // cluster they unfolded themselves is that level, and it folds the moment focus
      // leaves the margin, so the close hands them back to the entry the card hangs
      // from and the fold is the next press. With no such cluster — the walk's own
      // reveal folds with the card, and a bare marker has none — the entry is a control
      // they may never have focused, a `t` from the page having put the card up
      // without going near the margin, so the landing is the page it is anchored to.
      //
      // Under it means on the entry this card would land on. A cluster left unfolded on
      // another entry stands beside the card, not beneath it — the card retains the
      // margin's focus while it is up, so a `t` walk carries the card away from the
      // cluster and leaves it open — and landing on this entry would hand the next
      // press a fold that teleports focus somewhere third. So the question goes to
      // `optionsRung`, the step that would actually answer next, which also declines
      // for a host that has gone or an entry whose own state holds its actions open.
      // The step lands the user wherever they were, the page their press displaced
      // included, so its landing is the close's own rather than one for a user inside.
      out: () => {
        const currentLocation = unfoldedUnder();
        const button = card.selection()?.control;
        const target = besideTarget();
        closeLayer(
          () => closePreview(),
          currentLocation ? () => landOnEntry(button) : () => letGo(target),
        );
      },
    };
  }

  // The cluster the user unfolded is page-side state rather than a layer of the card,
  // so it answers from the ladder wherever they are — the card they opened from
  // it lands them out on the page, and the fold would otherwise be reachable only by
  // Tabbing back into the margin. It comes off after anything standing over the page and
  // before the page itself, beside the selection, and lands on the entry it hangs from,
  // which is the container it is part of.
  //
  // Once a contribution is engaged, its complete and escape controls are open because of
  // semantic state rather than because the user disclosed the secondary drawer. That
  // state consumes the earlier disclosure step: Escape leaves the action the user is
  // being on instead of first pretending to close controls that remain open by
  // contract.
  function optionsRung() {
    const host = hosts.get(expandedOptionsKey);
    if (!host?.lfEntry || host.lfEntry.key !== expandedOptionsKey) return null;
    if (entryEngaged(host.lfEntry)) return null;
    // A cluster the walk unfolded to hang the card from is the card's, and folds with it.
    if (expandedOptionsKey === forcedInlineOptionsKey()) return null;
    return {
      root: host,
      title: "close options",
      out: () =>
        setOptionsOpen(host.lfEntry, false, { land: landOnToggle(host.lfEntry) }),
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
        touch: false,
        keys: ["Escape"],
        description: () => pageMapRung(false)?.description,
        title: () => pageMapRung(false)?.title,
        commandReferenceWhen: () => Boolean(pageMapRung(false)),
        when: () => Boolean(pageMapRung()),
        run: () => pageMapRung()?.out(),
      },
    ],
  });

  function activate(item, entry, { focusMap = true } = {}) {
    if (expandedOptionsKey && expandedOptionsKey !== entry.key)
      setOptionsOpen(entry, false);
    const landsOnTarget = focusMap && !entryHasMarginHost(entry);
    // A Page Map-only location has no margin entry to receive the handoff. Reveal its
    // target first, then lend that authored element a programmatic tab stop so keyboard
    // focus and the visible arrival name the same place.
    closeLayer(
      () => {
        closePreview();
        leavePageMap();
      },
      focusMap &&
        (() => {
          if (!landsOnTarget) return handBack(...mapControlPlaces(entry));
          sourceItem(item).activate();
          if (targetFor(entry)?.isConnected) focusDestination(targetFor(entry), "move");
        }),
    );
    if (!landsOnTarget) sourceItem(item).activate();
  }

  function openThreadChoice(entry, button) {
    const choice = threadReading(entry);
    if (!choice) return;
    if (expandedOptionsKey && expandedOptionsKey !== entry.key)
      setOptionsOpen(entry, false);
    // A thread a widget holds out of its flow, so as to move nothing the user reads,
    // has this marker for its notice: pressing it shows the thread where the widget
    // draws it, and lands the user there (thread/held-news.js).
    const intent = retainUserIntent();
    const held = revealHeld(choice.items.map((item) => sourceItem(item).thread.id));
    if (held) {
      intent.handoff(closePreview);
      void held.presented.then(() =>
        openPageThread(held.id, {
          part: "thread",
          travel: false,
          intent,
        }),
      );
      return;
    }
    togglePinned(entry, button);
  }

  // `unfold: false` is a card that accompanies where the user is rather than one
  // they asked for: it hangs from the cluster's visible marker instead of unfolding the
  // cluster to reach the thread's own entry. Where the cluster shows but holds neither
  // on its face, as a suggestion's shows its Accept, the card unfolds it and folds it
  // again on closing; a cluster the page withholds shows no card.
  function openInlineThread(id, { origin = null, unfold = true } = {}) {
    const itemId = marginThreadItem(threadNamed(id));
    const entry = pageInventory.find((candidate) =>
      candidate.items.some((item) => item.id === itemId),
    );
    if (!entry || designModeActive()) return null;
    const choice = threadReading(entry);
    if (!choice) return null;
    const shown = (control) => (control?.checkVisibility() ? control : null);
    const host = hosts.get(entry.key);
    const marker = unfold
      ? null
      : (shown(threadMarginEntry(entry)) ?? shown(host?.marker));
    if (!unfold && !marker && !shown(host)) return null;
    const button = marker ?? threadMarginEntry(entry);
    const positioned = showPreview(entry, button, itemId, {
      origin,
      accompanies: !unfold,
      forced: true,
    });
    const thread = card.thread();
    return thread && positioned && { thread, presented: positioned };
  }

  // The row's acknowledgment face is read out of the published state projection rather
  // than the receipt paint. A repaint driven from the paint instead ran inside the
  // panel render the application performs *before* reconciliation, which is early enough
  // to read a candidate the same read is about to reject — and it ran inside a dispatch,
  // where the fault that candidate throws is reported as an uncaught page error rather
  // than rejecting the read.

  // The margin packs its rows a frame after anything moves them — a row registering,
  // the column resizing under a diagram that finished or a disclosure that opened — and
  // margin-layout.js says when it has moved the rows, and the card follows in that
  // same frame. comment-placement.js clears the renewed row only where the full
  // preferred message width fits beyond it; otherwise the message may cover it.

  // The selection belongs to the reading, not to focus or a particular feature's
  // control. Resolve it through the same inventory that decides which reading is the
  // visible marker and which is an unfolded option, then paint one shared state on the
  // compact projection. An open disclosure continues to use aria-expanded instead.
  function paintSelectedMarginEntries(selections) {
    // The trace reads current location as drawn too (`refreshHighlight`), which a press's end
    // moves with no focus change to say so.
    refreshHighlight();
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

  // ---------- the card goes where the user is ----------
  // A thread belongs to the target it is about, so a user is at that target from
  // any side of it: the target or anything inside it, its margin cluster, or the card
  // showing its threads. The card shows the threads of the target the user is at,
  // which is what lets both be up at once, and goes when they move anywhere else on the
  // page, let go, or press outside all three. Keyboard focus passing through the chrome
  // at large — the floating panel, its views — is working on the page rather than a place on it,
  // and leaves the card; a press anywhere else is the user's attention moving, and
  // takes it, as a press on another page place does.
  //
  // Arrival through the keyboard shows the card, as arrival through Tab unfolds a
  // cluster; a pointer that lands on a control in a commented block asked for that
  // control, and the mark and the marker are its way to the thread.
  const threadIdOf = (entry) => sourceItem(threadReading(entry).items[0]).thread.id;
  // The thread a margin entry stands for, the one its card shows first, or null.
  const entryThread = (node) => {
    if (under(node, preview) && previewOpen()) {
      const selected = card.selection();
      const item =
        selected &&
        threadReading(selected.entry)?.items.find(
          (candidate) => candidate.id === selected.threadItem,
        );
      if (item) return sourceItem(item).thread.id;
    }
    const entry = closestAcross(node, ".lf-margin-entry")?.lfEntry;
    return entry && threadReading(entry) ? threadIdOf(entry) : null;
  };
  // The thread whose margin entry the pointer is on, the one its card shows first, or null.
  const pointedThread = () => {
    const entry = hoveredHost?.isConnected ? hoveredHost.lfEntry : null;
    return entry && threadReading(entry) ? threadIdOf(entry) : null;
  };
  const threadIdsOf = (entry) =>
    threadReading(entry).items.map((item) => sourceItem(item).thread.id);
  // Only a page-owned seat or an exact widget-local placement takes the thread's
  // page position. The same card DOM drawn in the margin or by a primary reader leaves
  // that position and its margin preview available.
  const seatedOnPage = (id) =>
    claimed(id) ||
    [
      ...document.querySelectorAll(`.lf-page-thread[data-thread="${CSS.escape(id)}"]`),
    ].some((seat) => closestAcross(seat, ".lf-thread-seat[data-lf-thread-seat]"));
  // The innermost target holding the node whose threads the card would show. A thread is
  // about exactly its anchor's target (header), reached from anywhere
  // inside it and never from outside: after `m` the user is on the obligation element, so
  // the card shows a thread on the obligation but not one on its options or a phrase in its
  // heading. Treating an obligation as one target for its threads is a possible refinement. It
  // belongs where a thread's target is decided (anchor-placement), so every
  // reader keeps one definition, not in this or any other single reader.
  // Read the page target represented by the node (current-target.js), so chrome that shows a page
  // target, such as a comment note, arrives at that target as its own content does.
  // A target with pointed threads or quoted passages (groupFor) has a row for each:
  // being inside a pointed row takes that thread, and being elsewhere on the
  // target takes the row the card already shows for it, else its own row, or a pointed
  // or quoting one where it has none. A passage cannot receive focus, so the card's
  // row is what keeps returning to the target from switching which passage it shows.
  // Subject identity comes from the inventory even where a widget owns its seat.
  const threadEntryAt = (node) => {
    const ids = threadIdsAt(node);
    const here = (entry) =>
      threadReading(entry) &&
      threadIdsOf(entry).some((id) => ids.includes(id)) &&
      !seatedOnPage(threadIdOf(entry));
    const shown = previewOpen() && card.selection()?.entry?.key;
    return (
      pageInventory.find((entry) => entry.key === shown && here(entry)) ??
      pageInventory.find(here) ??
      null
    );
  };
  // A folded cluster opens while the keyboard arrives at its target, as it does when
  // the keyboard arrives on its toggle: what the user is at offers its actions, and
  // an obligation's digits name them. It folds again when they move anywhere else but in the
  // cluster itself, where focus keeps it open (the fold beside `arriveAtCluster`).
  let currentLocationUnfolded = null;
  // The arrivals below are the keyboard's: the user's latest input was a key, not a
  // press (focus.js, `pressLed`), since a press asks only for what it lands on. A Tab is
  // one, and so is any route a key began, or the runtime putting them back after one.
  const byKeyboard = () => !pressLed();
  function unfoldCurrentLocation(active) {
    const host = active && closestAcross(active, "[data-lf-margin-for]");
    if (host?.lfEntry?.key === currentLocationUnfolded) {
      currentLocationUnfolded = null;
      return;
    }
    const state = {
      expandedKey: expandedOptionsKey,
      expandedOwner: expandedOptionsOwner,
    };
    const place = active && !host && byKeyboard() && arrivalOf(active);
    const entry = place
      ? pageInventory.find(
          (candidate) =>
            folded(candidate) &&
            canFold(candidate, state) &&
            under(place, targetFor(candidate)),
        )
      : null;
    if (entry?.key === currentLocationUnfolded) return;
    if (currentLocationUnfolded && expandedOptionsKey === currentLocationUnfolded)
      setOptionsOpen(null, false, { preservePreview: true });
    currentLocationUnfolded = null;
    if (!entry || expandedOptionsKey === entry.key) return;
    setOptionsOpen(entry, true, { preservePreview: true });
    currentLocationUnfolded = entry.key;
  }
  // A keyboard arrival whose row the page still withholds, as one in a pane the arrival
  // is scrolling to, has nothing to hang its card from yet, so the card it replaces
  // goes now and its own waits for the margin's next layout to show the row. Standing
  // anywhere else, hiding the annotations, or a pointer mode ends the wait.
  function accompany(node, entry) {
    awaitingRow = null;
    if (openInlineThread(threadIdOf(entry), { unfold: false })) return;
    if (previewOpen() && card.selection()?.entry?.key !== entry.key) closePreview();
    awaitingRow = node;
  }
  function accompanyShownRow() {
    const node = awaitingRow;
    awaitingRow = null;
    if (
      !node ||
      focused() !== node ||
      previewOpen() ||
      annotationsHidden() ||
      designModeActive()
    )
      return;
    const entry = arrivalOf(node) && threadEntryAt(node);
    if (entry) accompany(node, entry);
  }
  function followCurrentLocation() {
    awaitingRow = null;
    refreshHighlight();
    const active = focused();
    unfoldCurrentLocation(active);
    if (
      !active ||
      active === document.body ||
      renderedUnder(active, preview) ||
      designModeActive()
    )
      return;
    const host = closestAcross(active, "[data-lf-margin-for]");
    if (host) {
      if (previewOpen() && host.lfEntry?.key !== card.selection()?.entry?.key)
        closePreview();
      return;
    }
    const entry = arrivalOf(active) && threadEntryAt(active);
    if (!entry) {
      if (previewOpen() && !inChrome(active)) closePreview();
      return;
    }
    if (previewOpen() && card.selection()?.entry?.key === entry.key) return;
    if (byKeyboard()) accompany(active, entry);
    else if (previewOpen()) closePreview();
  }
  // Letting go of where the user is leaves them nowhere, which takes the
  // card with it (`declareRelease`). A landing on the page that is not a let-go — `g p`,
  // a surface closing — leaves the card beside the target it is about.
  declareRelease(() => {
    if (previewOpen()) closePreview();
  });
  // A press away from the card puts it away (focus.js, `onPressAway`).
  const pressedAway = (path) => {
    if (!previewOpen()) return false;
    // A pointer mode reinterprets a press on the page as a stroke or an interface
    // comment, so only a press inside the card retains its current location.
    const currentTargets = pointerModeActive()
      ? [preview]
      : [
          preview,
          hosts.get(card.selection()?.entry?.key),
          targetFor(card.selection()?.entry),
        ];
    if (currentTargets.some((node) => node && path.includes(node))) return false;
    return !path.some(inRetainedContext);
  };

  const marginEntryChoices = (target) => clusterMarginEntries(marginEntryHost(target));
  // The conversation accompanying a page target while no Thread holds focus.
  // Core reads held identity first, including inside widget shadow roots.
  const accompaniedThreadHere = () => card.accompanied();
  // The page target this owner's chrome shows (current-target.js): a margin cluster
  // control's and the card's — its threads and its own controls.
  declareSide((node) => {
    const projected = marginTargetAt(node);
    if (projected) return projected;
    if (under(node, preview)) return targetFor(card.selection()?.entry);
    return null;
  });
  // A live revision may replace the browser document, and DOM identity cannot carry a
  // user in margin chrome across that. Carry the target and margin-entry keys
  // instead; this owner alone can revalidate those keys against the new projection. An
  // open card's thread opens again where any thread opens (thread/destination.js),
  // which takes the card only while the arriving revision draws its passage. A card
  // that accompanied the target the user was on, with the user outside the card,
  // comes back only beside that target's marker (`openInlineThread`, `unfold: false`).
  // A reply being written in the card carries its thread back itself (version.js,
  // `restoreEditingContinuity`), so the card is left to it.
  function captureCurrentLocation() {
    const active = focused();
    const host = closestAcross(active, "[data-lf-margin-for]");
    const control = active?.closest?.(".lf-margin-entry");
    const selected = card.selection();
    const entry = selected?.entry ?? host?.lfEntry;
    if (!entry) return null;
    const currentLocation = {
      entry: entry.key,
      preview:
        previewOpen() && !card.replying()
          ? { thread: selected.threadItem, accompanies: selected.accompanies }
          : null,
      focus: card.closeFocused()
        ? { kind: "preview-close" }
        : under(active, preview)
          ? { kind: "preview" }
          : control && host?.contains(control)
            ? {
                kind: "entry",
                key: contributionEntryRecord(control)?.key,
                owner: contributionEntryRecord(control)?.owner ?? null,
              }
            : null,
    };
    return currentLocation.preview || currentLocation.focus?.kind === "entry"
      ? currentLocation
      : null;
  }

  function restoreCurrentLocation(currentLocation) {
    if (!currentLocation || typeof currentLocation.entry !== "string") return false;
    const entry = pageInventory.find(
      (candidate) => candidate.key === currentLocation.entry,
    );
    if (!entry) return false;
    const shown = currentLocation.preview ? restoreCard(entry, currentLocation) : false;
    return currentLocation.focus?.kind === "entry"
      ? restoreEntryFocus(entry, currentLocation)
      : shown;
  }

  function restoreCard(entry, { preview: { thread, accompanies }, focus }) {
    const items = entry.items.filter((item) => item.kind === "comment");
    const item = items.find((candidate) => candidate.id === thread) ?? items[0];
    if (!item) return false;
    const id = sourceItem(item).thread.id;
    // A revision installed in place keeps the card, and its reading, where it still has
    // somewhere to stand.
    const selected = card.selection();
    const kept = selected?.entry.key === entry.key && selected.threadItem === item.id;
    if (kept && card.hasPlacement()) return true;
    if (kept) closePreview();
    const inCard = focus?.kind === "preview" || focus?.kind === "preview-close";
    if (accompanies && !inCard) return Boolean(openInlineThread(id, { unfold: false }));
    // Where the revision closed a tab or disclosure over the passage, or hid it, the
    // floating panel shows the thread: a reveal would move the page under a reader who
    // asked for nothing, and a card with no passage to stand beside never places. A user
    // who was in the card remains in the thread wherever it opens.
    const intent = retainUserIntent();
    const opened = openPageThread(id, {
      part: "thread",
      focus: inCard,
      travel: false,
      scroll: false,
      intent,
    });
    if (focus?.kind === "preview-close")
      void opened.then((destination) => {
        if (destination && under(destination, preview) && intent())
          card.focusThread(Promise.resolve(true), {
            closeControl: true,
            cause: "return",
          });
      });
    return true;
  }

  function restoreEntryFocus(entry, currentLocation) {
    const host = hosts.get(entry.key);
    const control = clusterMarginEntries(host).find(
      (candidate) =>
        contributionEntryRecord(candidate)?.key === currentLocation.focus.key &&
        (contributionEntryRecord(candidate)?.owner ?? null) ===
          currentLocation.focus.owner,
    );
    if (!control) return false;
    if (focused() === control) return true;
    // Roving tabindex is painted in the margin's next layout frame. The semantic
    // destination is already known here, so lend it a stop if that frame has not run.
    focusDestination(control, "return");
    return true;
  }

  // The margin's parts into the chrome, once it is mounted (leaf.js): the map button beside
  // the version picker, then its own parts in the root.

  function mount() {
    mountMarginLayer(toolbar);
    card.mount(() => closePreview(landOnEntry));
    document.addEventListener("lf-margin-layout", ({ detail: { column, height } }) => {
      accompanyShownRow();
      card.place();
      scheduleMarginEntryLabels();
      // A new width or height moves where targets stand down the page, and so what their
      // markers' names say; whatever else moves a target renders the margin, which names
      // them anew. Measured against the column this pass read.
      if (column.width === spokenBasis?.width && height === spokenBasis?.height) return;
      const moved = readSpokenPositions(pageInventory, column, height);
      if (moved.some((position, index) => position !== spokenPositions[index]))
        nameMarkers(moved);
    });
    document.addEventListener("pointerover", scheduleMarginEntryLabels, {
      capture: true,
    });
    document.addEventListener("pointerout", scheduleMarginEntryLabels, {
      capture: true,
    });
    // A drop is the change's own to put right: the margin follows where the user is.
    onCurrentLocation((node, cause) => {
      if (cause === "drop") return;
      scheduleMarginEntryLabels();
      queueMicrotask(followCurrentLocation);
    });
    // Ahead of the document, where a mode claims its presses before anyone else hears
    // them: whatever a press becomes, it is still the user's attention moving. A press
    // away from the card, or from the cluster whose options stand unfolded, puts it away.
    onPressAway(pressedAway, () => closePreview());
    const unfolded = () => hosts.get(expandedOptionsKey) ?? null;
    onPressAway(
      (path) => {
        const host = unfolded();
        return Boolean(host) && !path.includes(host) && !path.some(inRetainedContext);
      },
      () => setOptionsOpen(unfolded().lfEntry, false),
    );
    watchRoom(() => scheduleRoving());
    window.addEventListener("resize", () => scheduleWidthRender());
    renderAnnotations();
    // Before the foreground, whose chips anchor to the margin's rows (chrome.js). The
    // card needs no place of its own: floating.js positions it, and its Tab route
    // follows its entry wherever it stands (thread-preview.js).
    move(chromeRoot, nav, chromeForeground);
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
        ? (hosts.get(entry.key)?.marker ?? null)
        : (visible.find((row) => row.tabIndex === 0) ?? visible[0] ?? null);
    },
    targetFor,
    paint: renderNow,
    flushLayout: layoutMarginRows,
    scheduleThreadPreviewPosition: card.schedulePosition,
    marginTargetAt,
    marginEntryContextContains,
    focusForNavigation,
    presentedControl,
    openMarginEntryOptions,
    visibleMarginEntries,
    marginEntryKind,
    activateMarginEntry,
    closePreview,
    entryThread,
    pointedThread,
    inlineThreadView,
    keyboardRung,
    optionsRung,
    openInlineThread,
    threadPreview: {
      open: openInlineThread,
      focusTarget: card.focusTarget,
      accompanied: accompaniedThreadHere,
      close: closePreview,
    },
    paintSelectedMarginEntries,
    marginEntryChoices,
    captureCurrentLocation,
    restoreCurrentLocation,
    mount,
  };
}
