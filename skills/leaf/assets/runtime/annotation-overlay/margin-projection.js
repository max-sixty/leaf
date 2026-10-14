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
   A card accompanies the page target the user stands at, an ask included: `m` lands
   on an ask and its discussion opens beside it, clear of its options. Keeping the card
   shut while the user works an ask was tried and rejected, since the user walks to an
   ask to read its discussion with it. followStanding and the
   shared keyboard ladder decide when that relationship ends. It is margin chrome:
   target, cluster and card are one place. Standing elsewhere, releasing the target,
   or pressing outside that place dismisses it. Escape inside lands on the target;
   Send keeps focus on its thread. With Threads open, the list's expanded thread
   supplies the accompaniment and declares its own target association. The card shows
   the threads of the innermost target holding the user's place that has any (its own,
   else an enclosing one's), never those of a target inside it: a thread on an ask's
   options shows from the options, not from the ask (`threadEntryAt`).

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
  clusterProjection,
} from "../margin-model.js";

import { mapButton } from "../page-map-dialog.js";
import { move } from "../dom-move.js";

import {
  declareRelease,
  focusDestination,
  handBack,
  holdFocus,
  layerLanding,
  letGo,
  onPress,
  onStanding,
  pressLed,
  focused,
  closeLayer,
  rove,
  standingIn,
} from "../focus.js";

import { el, offer } from "../widget-elements.js";
import { keeps, keepsHidden } from "../keeps.js";

import { PRESS, rowArrows } from "../keyboard/bindings.js";
import { beginWalk, listWalkPosition, rowWalk } from "../walk-position.js";

import { readingRegionFor } from "../reading-regions.js";

import { keys, paintKeys } from "../keyboard/scopes.js";
import { pageRung, pageScope } from "../keyboard/register.js";
import { nativeLayerHolding } from "../shadow-tree.js";

import { annotationsHidden, watchAnnotations } from "./annotation-layer.js";
import { repaint } from "../repaint.js";
import { chromeRoot, chromeForeground } from "../chrome.js";
import { versionBtn } from "../version-picker.js";
import { declareSide, placeOf } from "../standing-target.js";
import { closestAcross, inChrome } from "../passages.js";
import { visualAt } from "../anchor-resolution.js";
import { paintTrace } from "../target-paint.js";

import { allThreads } from "../thread/state.js";
import { threadNames } from "../thread/model.js";
import { carryingReply } from "../thread/focus.js";

import { claimed, revealHeld } from "../thread/surfaces.js";

import { createMarginClusterViews } from "./margin-cluster-view.js";

import { bannerControlDoor } from "../banner-toolbar.js";

import { seenRect, shownWindow, skipped, watchRoom } from "../geometry.js";

import { hostIn, renderedUnder, under } from "../shadow.js";
import { retainUserIntent } from "../user-intent.js";

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
    threadIdsAt,
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

  const card = createThreadPreview({
    inventory,
    renderMarginThread,
    placedAt,
    openPageThread,
    panelIsOpen,
    scrollThreadIntoView,
    scrollToElement,
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
  // focus when the surface closes. A side surface standing beside the page, such as
  // the On panel, is somewhere else the user went.
  const inRetainedContext = (node) =>
    node instanceof Element &&
    (Boolean(nativeLayerHolding(node)) ||
      under(node, preview) ||
      (panelIsOpen() && under(node, panel)));
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
          description: "Open or close what the focused margin entry holds",
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
        opensInline ? card.selection()?.control === control : null,
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
  function scheduleWidthRender() {
    if (widthFrame) return;
    widthFrame = nextRender(() => {
      widthFrame = 0;
      renderAnnotations.refresh();
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
    return [...markerRows()].filter(
      (row) =>
        !row.hidden &&
        !row.closest(".lf-withheld") &&
        row.checkVisibility({ visibilityProperty: true }),
    );
  }

  // The rows in front of the user (`seenRect`): one under the banner or the bottom bar,
  // or scrolled out of a pane, is no row the walk or the rail's way in may land on.
  function visibleRows() {
    const clips = new Map();
    return availableRows().filter((row) => seenRect(row, clips));
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
    focusDestination(
      buttons[(at + direction + buttons.length) % buttons.length],
      "move",
    );
    beginWalk("margin-entry", "Action", () => {
      const standing = focused();
      const standingHost = closestAcross(standing, "[data-lf-margin-for]");
      return listWalkPosition(clusterMarginEntries(standingHost), standing);
    });
  }

  // Folding a cluster the user stood in hands them back to its toggle.
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

  // Where the Map hands the user back, for `handBack`: the entry's own marker, then the
  // way into the Map, then a row in view, then the version control. The Map is a toolbar
  // control, so at a width that folds it the button itself is behind a shut door and
  // cannot take focus; the toolbar is asked for the way in.
  function mapControlPlaces(entry = null) {
    const visible = visibleRows();
    return [
      entry ? hosts.get(entry.key)?.marker : null,
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
    rove(markerRows(), stop);
  }

  function syncRoving() {
    const available = availableRows();
    const visible = visibleRows();
    if (!available.length) {
      holdTabStop(null);
      return;
    }
    const standing = available.find((row) => row === focused());
    const candidates = visible.length ? visible : available;
    // A stop in view stays where it is. With none in view the stop is the row nearest
    // the window, whatever held it before, so the way in follows from the page as it
    // stands rather than from the widths and scrolls it passed through.
    const held = visible.find((row) => row.tabIndex === 0);
    const room = shownWindow();
    const distance = (row) => {
      const box = row.getBoundingClientRect();
      if (box.bottom < room.top) return room.top - box.bottom;
      if (box.top > room.bottom) return box.top - room.bottom;
      return 0;
    };
    const next =
      standing ??
      held ??
      candidates.reduce((best, row) => (distance(row) < distance(best) ? row : best));
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
  // controls (`m`, `focusForNavigation`) shows that one row, so what decides the target
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
  onStanding((node) => {
    if (
      node &&
      revealed &&
      !revealed.contains(node) &&
      !(revealed.lfTarget && under(node, revealed.lfTarget))
    )
      revealHost(null);
  });
  // A cluster the user comes to stand in. Any arrival there outranks a pointer parked on
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
  onStanding((node, cause, left) => {
    if (!node) return;
    for (const host of hosts.values())
      if (host.contains(node)) return arriveAtCluster(host, node, cause, left);
  });
  // Leaving a cluster folds what it unfolded, unless the user went into a surface that
  // keeps its context (`inRetainedContext`). A node hidden under the user leaves it too,
  // as its blur did. A node removed from under them is in no cluster any more, and the
  // render that removed it hands them on to its replacement, often a frame later, so it
  // folds nothing. A window losing focus moves no one.
  onStanding((node, cause, left) => {
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
      description: "Move through the margin entries on this target",
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
    node.lfEntry = entry;
    presentContributionEntry(
      node,
      contributionEntry({
        key: `reading:${choice?.key ?? "none"}`,
        icon: face.icon,
        label: readingLabel(choice),
        context: readingContext(choice),
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
    const userContext =
      awaitingUser(choice.items) || unreadIn(choice.items)
        ? readingContext(choice)
        : null;
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
    // none does (focus.js, `onStanding`).
    const primary = host.present(projection);
    const options = host.options;
    const lostOptionFocus = focus.focusedOption && !standingIn(options);
    const lostPrimaryFocus = focus.focusedPrimary && !standingIn(host);
    if (!projection.hasOptions && (focused() === more || lostOptionFocus)) {
      const destination = primary ?? (primaryReading(entry) ? marker : null);
      if (destination === marker && marker.hidden) marker.lfTakeFocus = true;
      else if (destination) focusDestination(destination, "return");
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
    // Before the card, which anchors to its rows (`mount`).
    if (!nav.isConnected)
      move(
        chromeRoot,
        nav,
        preview.parentNode === chromeRoot ? preview : chromeForeground,
      );
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
        focusedPrimary: Boolean(host.primary && standingIn(host.primary)),
        focusedOption: Boolean(host.options && standingIn(host.options)),
        // The entry the user stands on, by its contribution's key, across the projection
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
        closePreview(landOnEntry);
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
    // A user standing on the card's target itself already has its ring there; the
    // trace would paint over the one mark that says where they stand.
    const onTarget =
      previewOpen() && active && active === targetFor(card.selection()?.entry);
    const source =
      pointerHost ??
      focusedHost ??
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
    highlight(drawingOnly ? null : (targetFor(entry) ?? null));
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

  // Closing the card hands a user who stood in it on (focus.js, `closeLayer`). A close
  // aimed at the card itself, its Close or its Escape, hands them back to the margin
  // entry it hangs from (`landOnEntry`); any other, a mode or a rerender, lets them go.
  // A reply the thread pass is carrying to where its thread now stands is that pass's to
  // land (thread/focus.js, `carryingReply`), so the close places no one.
  const landOnEntry = layerLanding((button) =>
    handBack(button, ...(button?.lfEntry ? mapControlPlaces(button.lfEntry) : [])),
  );
  /** @param {(control?: HTMLElement) => unknown} [land] */
  function closePreview(land = letGo) {
    const button = card.selection()?.control;
    const at = focused();
    const heldInside = standingIn(preview) && !carryingReply(at);
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
  // Inside it, the thread's parent is the target it is about: the press steps out onto
  // that target and the card stays up beside it, since the user still stands there,
  // and letting go of the target is the next press. From the entry it hangs from, the
  // press takes the card down.
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
  const stepsOut = (from = focused()) => {
    const target = targetFor(card.selection()?.entry);
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
        !renderedUnder(active, preview) &&
        !(card.selection()?.control && host?.contains(card.selection()?.control)))
    )
      return null;
    if (stepsOut())
      return {
        root: preview,
        description: "Return to the page element this thread is about",
        title: "back to element",
        out: () => focusDestination(stepsOut(), "return"),
      };
    return {
      root: preview,
      description: "Dismiss the thread view",
      title: "dismiss thread",
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
      // The step lands the user wherever they stood, the page their press displaced
      // included, so its landing is the close's own rather than one for a user inside.
      out: () => {
        const standing = unfoldedUnder();
        const button = card.selection()?.control;
        closeLayer(() => closePreview(), standing ? () => landOnEntry(button) : letGo);
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
    if (expandedOptionsKey === forcedInlineOptionsKey()) return null;
    return {
      root: host,
      description: "Fold the secondary page actions",
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

  // `unfold: false` is a card that accompanies where the user stands rather than one
  // they asked for: it hangs from the cluster's visible marker instead of unfolding the
  // cluster to reach the thread's own entry. Where the cluster shows but holds neither
  // on its face, as a suggestion's shows its Accept, the card unfolds it and folds it
  // again on closing; a cluster the page withholds shows no card.
  function openInlineThread(id, { transition = null, unfold = true } = {}) {
    const itemId = marginThreadItem(threadNames(allThreads()).get(id));
    const entry = pageInventory.find((candidate) =>
      candidate.items.some((item) => item.id === itemId),
    );
    if (!entry || designModeActive() || panelIsOpen()) return null;
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
      origin: transition,
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
  // about exactly its anchor's target (header), reached from anywhere
  // inside it and never from outside: after `m` the user stands on the ask element, so
  // the card shows a thread on the ask but not one on its options or a phrase in its
  // heading. Treating an ask as one target for its threads is a possible refinement. It
  // belongs where a thread's target is decided (anchor-placement), so every
  // reader keeps one definition, not in this or any other single reader.
  // Read from where the node stands (standing-target.js), so chrome that shows a page
  // target, such as a comment note, arrives at that target as its own content does.
  // A target with pointed threads (groupFor) has a row for each: standing inside a
  // pointed row takes that thread, and standing elsewhere on the target takes its own
  // row, or a pointed one where it has none.
  // Subject identity comes from the inventory even where a widget owns its seat.
  const threadEntryAt = (node) => {
    const ids = threadIdsAt(node);
    return (
      pageInventory.find(
        (entry) =>
          threadReading(entry) &&
          threadIdsOf(entry).some((id) => ids.includes(id)) &&
          !seatedOnPage(threadIdOf(entry)),
      ) ?? null
    );
  };
  // A folded cluster opens while the keyboard stands at its target, as it does when
  // the keyboard arrives on its toggle: what the user stands at offers its actions, and
  // an ask's digits name them. It folds again when they stand anywhere else but in the
  // cluster itself, where standing keeps it open (the fold beside `arriveAtCluster`).
  let standingUnfolded = null;
  // The arrivals below are the keyboard's: the user's latest input was a key, not a
  // press (focus.js, `pressLed`), since a press asks only for what it lands on. A Tab is
  // one, and so is any route a key began, or the runtime putting them back after one.
  const byKeyboard = () => !pressLed();
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
    const place = active && !host && byKeyboard() && placeOf(active);
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
    const entry = threadEntryAt(node);
    if (entry) accompany(node, entry);
  }
  function followStanding() {
    awaitingRow = null;
    refreshHighlight();
    const active = focused();
    unfoldStanding(active);
    if (
      !active ||
      active === document.body ||
      renderedUnder(active, preview) ||
      renderedUnder(active, panel) ||
      designModeActive()
    )
      return;
    const host = closestAcross(active, "[data-lf-margin-for]");
    // With Threads open the panel is where a target's threads show, and its one expanded
    // thread is the card: arriving at a target by the keyboard expands its thread there.
    // Nothing closes, since the list stays whole wherever the user stands.
    if (panelIsOpen()) {
      const entry = host ? host.lfEntry : threadEntryAt(active);
      if (entry && threadReading(entry) && byKeyboard())
        accompanyThread(threadIdsOf(entry));
      return;
    }
    if (host) {
      if (previewOpen() && host.lfEntry?.key !== card.selection()?.entry?.key)
        closePreview();
      return;
    }
    const entry = threadEntryAt(active);
    if (!entry) {
      if (previewOpen() && !inChrome(active)) closePreview();
      return;
    }
    if (previewOpen() && card.selection()?.entry?.key === entry.key) return;
    if (byKeyboard()) accompany(active, entry);
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
  const pressedAway = (path) => {
    if (!previewOpen()) return false;
    // A pointer mode reinterprets a press on the page as a stroke or an interface
    // comment, so there a press stands nowhere but in the card itself.
    const stands = pointerModeActive()
      ? [preview]
      : [
          preview,
          hosts.get(card.selection()?.entry?.key),
          targetFor(card.selection()?.entry),
        ];
    if (stands.some((node) => node && path.includes(node))) return false;
    return !path.some(inRetainedContext);
  };
  const pressAway = (start, path) =>
    pressedAway(path)
      ? (end, completed) => {
          if (completed && pressedAway(end.composedPath())) closePreview();
        }
      : null;

  const marginEntryChoices = (target) => clusterMarginEntries(marginEntryHost(target));
  // The conversation accompanying a page target while no Thread holds focus.
  // Core reads held identity first, including inside widget shadow roots.
  const accompaniedThreadHere = () => {
    const active = focused();
    if (panelIsOpen()) {
      const entry = active && !renderedUnder(active, panel) && threadEntryAt(active);
      return entry ? accompaniedThread(threadIdsOf(entry)) : null;
    }
    return card.accompanied();
  };
  // The page target this owner's chrome shows (standing-target.js): a margin cluster
  // control's and the card's — its threads and its own controls.
  declareSide((node) => {
    const projected = marginTargetAt(node);
    if (projected) return projected;
    if (under(node, preview)) return targetFor(card.selection()?.entry);
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
    const entry = card.selection()?.entry ?? host?.lfEntry;
    if (!entry) return null;
    const standing = {
      entry: entry.key,
      preview: previewOpen() ? { thread: card.selection()?.threadItem } : null,
      focus: card.closeFocused()
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
      const positioned = showPreview(entry, button, standing.preview.thread);
      if (!positioned) return false;
      if (standing.focus?.kind === "preview-close")
        card.focusThread(positioned, { closeControl: true, cause: "return" });
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
    // A drop is the change's own to put right: the margin follows where the user stands.
    onStanding((node, cause) => {
      if (cause === "drop") return;
      scheduleMarginEntryLabels();
      queueMicrotask(followStanding);
    });
    // Ahead of the document, where a mode claims its presses before anyone else hears
    // them: whatever a press becomes, it is still the user's attention moving.
    onPress(pressAway);
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
    watchRoom(() => scheduleRoving());
    window.addEventListener("resize", () => scheduleWidthRender());
    renderAnnotations();
    // The card anchors to its row (floating.js), which an anchor may do only to a box
    // laid out before it: the margin comes first.
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
    threadTransitionOrigin: card.threadTransitionOrigin,
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
    captureStanding,
    restoreStanding,
    mount,
  };
}
