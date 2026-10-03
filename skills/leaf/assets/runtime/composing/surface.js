/* The anchored response bar: where it stands, what raises it, and the room it keeps.

   Normal reading mode leaves a plain click on unadorned authored content to the
   browser. Visible native and Leaf controls keep their click actions; text selection
   targets words. Alt-click, `s`, and a visual's “Respond to…” proxy are explicit
   Comment gestures. They pass a stable target from `aimTargetAt` or the visual provider
   into this surface. A whole item or picture names its authored id, while a visual part
   adds its declared token. Comment opens the compact field; Tab or its ellipsis extends
   that field with the other response margin entries. Tab, Shift-Tab, and the arrow keys then
   wrap through the visible margin entries. Escape folds the extension; Escape from the field
   hides the draft.
   The same anchor resolves both states against the target's geometry.

   The bar a selection or keyboard-selected addressable raises is `.lf-fab-bar`: the
   durable, compact `.lf-fab-input` followed by one response ellipsis. An explicit
   addressable target
   opens and focuses that field. On desktop, selecting a passage leaves the field open
   but unfocused. On touch screens, selection offers Comment on selection in the banner;
   its press captures the passage, clears the native selection menu, and opens the field.
   Until that press the native handles and menu have the passage to themselves. The
   field grows in place and never transfers text into a second composer card. A
   one-line note uses the shared action corner. A longer one widens within the thread
   card’s measure and then wraps. A transparent envelope fits the first message and
   the card’s metadata and reply slots before typing; only the editor paints then.

   The editor has one native seat, whether a widget, page or selected presentation
   holds it. Seating and restoring move that same node while retaining its draft,
   caret and focus. Readiness resolves only when the actual seat or presentation
   commits it; creating a composer does not claim that it has a place.

   `showFab` places the bar; `openComposer` (composing/selection.js) binds its field to
   the durable draft and takes the focus decision. Every explicit item and visual route
   passes its resolved anchor to `commentOnTarget`, which focuses the field and carries an
   unsent draft to the new target. Automatic passage selection opens that passage's own
   durable draft without moving focus. Submitted words still in flight remain owned by
   their original anchor, while a later target starts clean and keeps focus.

   Boot may supply an actual physical placement. The default floating presentation
   owns collision geometry and off-flow reveals in floating-response.js. This owner
   does not import or instantiate it; a page renderer can seat the native editor
   through the same cohort without loading that presentation.

   Boot supplies composer, travel, and mode commands to one surface owner. Its
   constructor binds no document listeners; mount installs the selection gesture
   lifecycle and field-focus tracking after all capabilities have been composed. */
import {
  addressableWord,
  anchoringIsReady,
  resolveAnchor,
  visualAt,
} from "../anchor-resolution.js";
import { sameAnchor } from "../anchor-coordinate.js";
import { bringBackSurfaceOf } from "../off-flow.js";
import {
  BANNER_CONTROL_RANK,
  dismissBannerControls,
  registerBannerControl,
  showBannerControl,
} from "../banner-toolbar.js";
import { seenRect } from "../geometry.js";
import { cancelRender, nextRender } from "../rendering.js";
import { targetElement, targetPlace, targetSegments } from "../resolved-target.js";
import {
  composer,
  composerOpen,
  fab,
  fabBar,
  fabInput,
  fabOptions,
} from "./selection.js";

import {
  closeCommandReference,
  commandReferenceOpen,
} from "../keyboard/command-reference.js";

import { paintReactionStanding } from "../reaction-standing.js";
import { threadInput, standingThread } from "../thread/landing.js";
import { replyDraftContext } from "../thread/replies.js";
import { activeCommandLabel } from "../keyboard/dispatch.js";
import {
  coveringAuxiliarySurface,
  pageCommand,
  pageRung,
  pageScope,
} from "../keyboard/register.js";

import { elementById, inChrome, pageRange, pageText, pageWords } from "../passages.js";
import {
  leftThePage,
  pageSelection,
  selectionAnchor,
  snapSelection,
} from "./capture.js";
import { repaint } from "../repaint.js";
import { drawn, handBack, holdFocus, letGo, takesLetters } from "../focus.js";
import { focused } from "../keyboard/scopes.js";
import { shadowHost, under } from "../shadow.js";
import { heldAsk } from "../standing-target.js";

import { coarsePointer, pointerAt } from "../pointer.js";
import { anchorLabel } from "../thread/messages.js";

import { reactionsAt } from "../thread/model.js";
import { allThreads } from "../thread/state.js";

import { standingPoint } from "../pointed-place.js";
import { keeps } from "../keeps.js";
import { retainUserIntent, restrictUserIntent } from "../user-intent.js";

export function createResponseSurface({
  panelElements: { generalInput, panel, threadsBox, inPanel },
  panelIsOpen,
  landIn,
  setPanel,
  threadHere,
  threadTarget,
  standingTarget,
  composerHolds,
  responseOptionsAreOpen,
  markAt,
  scrollToElement,
  visualActionAnchor,
  hideComposer,
  openComposer,
  carryComposerToReply,
  resetResponseOptions,
  responseOptionsAvailable,
  setResponseOptions,
  syncResponseOptions,
  designModeActive,
  designTarget,
  openOnDesign,
  isReactArmed,
  reactionContextContains,
  reactionTokens,
  setReact,
  collapseShortcutBar,
  closeVersionMenu,
  versionMenuIsOpen,
  openPageThread,
  drawModeActive,
  refreshThread,
  dismissThreadView,
  responseHome,
  revealResponseHome = null,
  createPlacement = null,
}) {
  const hideReference = () => closeCommandReference(false);
  const hasOtherResponses = (anchor) =>
    reactionTokens().length > 0 || Boolean(anchor?.quote && !designModeActive());

  // ---------- selection → comment ----------
  let fabAnchor = null;
  let fabOrigin = null;
  // The row inside the target the gesture that opened this bar pointed at, which the bar
  // stands level with (pointed-place.js).
  let fabPoint = null;
  let usesPlacement = false;
  let fabInlineOutlet = null;
  let fabPositionWaiters = [];
  const fabFocused = () => (fabInlineOutlet ? focused() : document.activeElement);

  const fabDrawn = () => drawn(composerOpen ? fabInput : fabBar);
  const answerFabPosition = (positioned) => {
    // Physical completion cannot certify an editor hidden by its current seat.
    // Keep its waiters until a current placement commits it, or cancellation declines.
    if (positioned && !fabDrawn()) return;
    const waiters = fabPositionWaiters;
    fabPositionWaiters = [];
    for (const resolve of waiters) resolve(positioned);
  };

  // Readiness belongs to the native bar, whether an inline seat or the selected
  // physical presentation commits it. A page presentation resolves this through seatFab.
  const fabPositioned = () =>
    !fabAnchor
      ? Promise.resolve(false)
      : !placement &&
          fabInlineOutlet === responseHome &&
          !fabDrawn() &&
          !fabFocusHandoff?.intent()
        ? Promise.resolve(false)
        : ((fabInlineOutlet?.isConnected && fabBar.parentElement === fabInlineOutlet) ||
              placement?.ready()) &&
            fabDrawn()
          ? Promise.resolve(true)
          : new Promise((resolve) => fabPositionWaiters.push(resolve));
  const stopFabPositioning = ({ reset = false, repositioning = false } = {}) => {
    placement?.stop({ reset, repositioning });
    if (reset && !repositioning) answerFabPosition(false);
  };
  // Reparenting the canonical response bar is presentation, not a composer transition,
  // so the user's place in it, caret included, crosses light and shadow DOM moves with it.
  function moveFab(parent) {
    if (fabBar.parentElement === parent) return;
    const restoreFocus = holdFocus(fabBar);
    parent.append(fabBar);
    restoreFocus?.();
  }

  function seatFab(outlet) {
    if (!(outlet instanceof Element) || !fabAnchor || !composerOpen) return false;
    // Admit the actual editor after its native move: an empty or display:contents
    // outlet has no visibility of its own. A rejected nomination leaves the previous
    // seat, geometry and held typing place intact so the cohort can try its fallback.
    const previousParent = fabBar.parentNode;
    const previousVisibility = fabBar.style.visibility;
    const restoreFocus = holdFocus(fabBar);
    if (fabBar.parentNode !== outlet) outlet.append(fabBar);
    fabBar.style.removeProperty("visibility");
    if (!fabDrawn()) {
      if (previousParent && fabBar.parentNode !== previousParent)
        previousParent.append(fabBar);
      else if (!previousParent) fabBar.remove();
      if (previousVisibility) fabBar.style.visibility = previousVisibility;
      else fabBar.style.removeProperty("visibility");
      restoreFocus?.();
      return false;
    }
    if (usesPlacement) stopFabPositioning({ reset: true, repositioning: true });
    fabInlineOutlet = outlet;
    usesPlacement = false;
    keeps(fabBar, "data-lf-presentation", "inline");
    fabBar.style.display = "inline-flex";
    fabBar.style.removeProperty("visibility");
    answerFabPosition(true);
    placement?.stoodAgain();
    restoreFocus?.();
    return true;
  }

  function restoreFab({ place = true } = {}) {
    if (
      (placement || !place || !fabAnchor || !composerOpen) &&
      fabBar.parentElement === responseHome &&
      (!fabInlineOutlet || fabInlineOutlet === responseHome)
    )
      return false;
    // Resetting the inline presentation hides the response before moving it back to the
    // viewport plane. Hold the user's place first: hiding a focused subtree makes Chromium
    // move focus to body before moveFab can observe what was held, and the bar takes
    // focus again only once it is placed.
    const restoreFocus = holdFocus(fabBar);
    stopFabPositioning({ reset: true, repositioning: place });
    fabInlineOutlet = placement ? null : responseHome;
    usesPlacement = Boolean(placement);
    keeps(fabBar, "data-lf-presentation", placement ? null : "inline");
    // Retiring an outlet must return the native editor even when its home is hidden.
    // The home owns its lifetime; actual editor visibility alone answers readiness.
    moveFab(responseHome);
    if (!placement && place && fabAnchor && responseHome.isConnected) {
      fabBar.style.removeProperty("visibility");
      answerFabPosition(true);
      restoreFocus?.();
    } else if (place && fabAnchor && standFab() && restoreFocus)
      void fabPositioned().then((positioned) => positioned && restoreFocus());
    return true;
  }

  // Whether a resolution is one this document can still put a box beside, which is not the
  // same question as whether it is on screen. Quoted words that resolve to segments stand
  // wherever they are. A source replacement must not close a draft about its prior
  // revision: an outdated finding falls back to its section, while an identified
  // subject keeps the draft beside its current datum even if the quoted words changed.
  // Everything else stands on its element.
  //
  // One rule, because two callers ask it: placement, below, and the route back to a kept
  // draft, which must not offer a passage this version no longer holds.
  const standsIn = (anchor, found) => {
    if (!found) return false;
    if (anchor.quote) {
      if (targetSegments(found).length) return true;
      if (found.status !== "outdated" && !(anchor.identity && found.datumElement))
        return false;
    }
    return Boolean(targetElement(found));
  };
  // Asked of a stored anchor from outside a live response transaction, where the composer
  // is down and there is no native selection to read the passage off.
  const anchorStands = (anchor) =>
    Boolean(anchor) && standsIn(anchor, resolveAnchor(anchor, pageText()));
  const fabPointIn = (target) =>
    fabAnchor?.quote ? null : standingPoint(target, fabPoint);
  const placement =
    createPlacement?.({
      nodes: { bar: fabBar, input: fabInput, composer, options: fabOptions },
      response: {
        get anchor() {
          return fabAnchor;
        },
        get open() {
          return composerOpen;
        },
        get floating() {
          return usesPlacement;
        },
        get target() {
          return fabTargetAt();
        },
        get captured() {
          return fabHoldsCapturedPassage();
        },
        pointIn: fabPointIn,
      },
      panel,
      panelIsOpen,
      threadsBox,
      positioned: answerFabPosition,
      dismiss: () => showFab(null, { returnFocus: "page" }),
      standsIn,
      scrollToElement,
    }) ?? null;
  // Where a bar on this anchor hands the user back: the control the gesture stood them
  // on, or the visual proxy for the same anchor where that control has gone, found
  // by identity so a repaint cannot strand it. A bar no gesture stood them on has nowhere
  // of its own and the user lands on the page — the element the bar is about is not a
  // landing merely for being named, an ⌥-aimed press having never stood them on it.
  const returnDestination = (anchor, origin) =>
    anchor && !anchor.quote && origin
      ? origin.isConnected
        ? origin
        : visualActionAnchor(anchor)
      : null;
  function showFab(
    anchor,
    { returnFocus = "target", origin = null, place = true, point = undefined } = {},
  ) {
    const previous = fabAnchor;
    const previousOrigin = fabOrigin;
    const previousFloating = usesPlacement;
    const leavingBar = !anchor && fabBar.contains(fabFocused());
    const returnToPanel = leavingBar && panelIsOpen() && !(placement?.fits() ?? true);
    const returnTarget = leavingBar
      ? returnDestination(previous, previousOrigin)
      : null;
    const keptInline = Boolean(
      fabInlineOutlet?.isConnected &&
      anchor &&
      previous &&
      sameAnchor(previous, anchor),
    );
    if (!anchor || (fabInlineOutlet && !keptInline)) restoreFab({ place: false });
    if (!anchor) fabInputTakingFocus = false;
    if (!anchor || (previous && !sameAnchor(previous, anchor))) resetResponseOptions();
    if (!anchor || !sameAnchor(previous, anchor)) {
      placement?.release();
    }
    if (!anchor && composerOpen) hideComposer();
    // A gesture opening the bar says where in its target the bar stands, `null` for
    // nowhere; re-placing the bar on the same anchor keeps where the last one said, and
    // any other anchor starts at its target's top.
    const stands =
      point !== undefined ? point : sameAnchor(previous, anchor) ? fabPoint : null;
    const pointMoved = stands !== fabPoint;
    fabPoint = stands;
    if (
      !anchor ||
      !previous ||
      !sameAnchor(previous, anchor) ||
      !place ||
      pointMoved ||
      (!previousFloating && !keptInline)
    )
      stopFabPositioning({ reset: true });
    fabAnchor = anchor;
    usesPlacement = Boolean(placement) && (!fabAnchor || (place && !keptInline));
    // A call that names the anchor already standing and supplies no control is the same
    // bar being re-placed — the other-responses toggle, leaving react mode, a scroll —
    // rather than a fresh gesture that stood the user nowhere. It keeps the control the
    // opening gesture stood them on; otherwise the way out of a bar the user opened
    // from a proxy would depend on what they did inside it.
    fabOrigin =
      fabAnchor && origin?.isConnected
        ? origin
        : fabAnchor && previous && sameAnchor(previous, fabAnchor)
          ? previousOrigin
          : null;
    fabBar.toggleAttribute("data-lf-target-only", Boolean(fabAnchor && !composerOpen));
    fabBar.style.display = fabAnchor ? "inline-flex" : "none";
    fabInput.style.display = fabAnchor && composerOpen ? "block" : "none";
    syncResponseOptions(fabAnchor);
    // Comment returns from the bar's choice state to this same field. With only a target
    // chosen, the button is the affordance; once Comment is open, the input replaces it.
    fab.style.display = fabAnchor ? "" : "none";
    if (fabAnchor) {
      const label = anchorLabel(fabAnchor).replace(/^§\s*/, "");
      keeps(fabBar, "aria-label", label ? `Respond to ${label}` : "Respond");
      keeps(fabInput, "aria-label", label ? `Comment on ${label}` : "Comment");
      // The tokens already standing on this very anchor read pressed, and a press on one
      // takes it back (reactHere): the bar is the strip's shape on the page.
      paintReactionStanding(fabBar, reactionsAt(allThreads(), fabAnchor));
      // A margin control can name an item whose rendered box is currently off
      // screen. `e` still needs the durable anchor so it can extend that existing item;
      // in that route the floating bar is never painted and placement is deliberately
      // skipped. Every route that actually shows the bar keeps the geometry gate. The gate
      // is for opening: the bar already standing on this anchor, placed again, is
      // withheld rather than put away (standFab).
      if (place && usesPlacement && placement && !placement.place()) {
        if (sameAnchor(previous, fabAnchor) && anchorStands(fabAnchor))
          placement?.withhold();
        else {
          fabAnchor = null;
          fabOrigin = null;
          placement?.release();
          stopFabPositioning({ reset: true });
          resetResponseOptions();
          fabBar.removeAttribute("data-lf-target-only");
          fabInputTakingFocus = false;
          if (composerOpen) hideComposer();
          fabBar.style.display = "none";
          fabInput.style.display = "none";
          fab.style.display = "none";
        }
      }
    }
    // A bar raised on a new target takes the thread card down: the card stands above
    // page-level chrome and may cover the bar, and the user has moved on from its thread
    // to a new response, as opening a margin entry's options closes it.
    if (fabAnchor && usesPlacement && !sameAnchor(previous, fabAnchor))
      dismissThreadView();
    if (!sameAnchor(previous, fabAnchor)) refreshThread();
    repaint(); // the c row names this anchor, so the line is one more rendering of it
    if (!fabAnchor && returnFocus !== "none") {
      if (returnToPanel) threadsBox.focus({ preventScroll: true });
      // The proxy may have gone hidden since the gesture opened the box — a fold that
      // closed under it, a row that re-rendered — and the page is the landing then, as it
      // is for a box that had no proxy to begin with.
      else if (leavingBar && returnFocus === "target") handBack(returnTarget);
      else if (
        leavingBar ||
        (returnFocus === "page" && document.activeElement === previousOrigin)
      )
        letGo();
    }
  }
  let dismissedSelectionKeyup = false;
  function dismissFab() {
    dismissedSelectionKeyup = Boolean(pageSelection() || fabAnchor?.quote);
    pageSelection()?.removeAllRanges();
    showFab(null);
  }
  function refreshFab() {
    if (!fabAnchor || !usesPlacement) return;
    // A bare selection's bar is the selection's, and goes with it.
    if (fabAnchor.quote && !composerOpen && !fabHoldsCapturedPassage()) updateFab();
    else standFab();
  }
  // Stands the bar the user already has again. Geometry says where it stands, never
  // whether: the bar goes when a gesture puts it away or when its subject leaves the
  // document, and never because a scroll, a resize, a panel or a closed disclosure left
  // it no attachment. An open editor uses the window while its subject is hidden;
  // a bar with no usable room is withheld, draft, anchor and all, and the next
  // placement that finds room stands it again.
  function standFab() {
    if (!anchorStands(fabAnchor)) {
      showFab(null, { returnFocus: "page" });
      return false;
    }
    if (!placement || placement.place()) return true;
    placement?.withhold();
    return false;
  }
  // The durable anchor names the authored coordinate an event can replay, while the
  // margin needs the rendered block the gesture is visibly on. Those are deliberately
  // different for selected words inside a paragraph without an ID: the event names its
  // enclosing section, but both the temporary picker and the standing receipt sit at
  // the paragraph. Match seatReactions' shadow-boundary rule so live and replay agree.
  //
  // Asked of any anchor rather than only of the standing one: a draft the composer put
  // away carries its own anchor and nothing else in the runtime can say which block that
  // draft is about, which is what the route back to it has to travel to.
  const anchorTargetAt = (anchor) => {
    if (!anchor) return null;
    const found = resolveAnchor(anchor, pageText());
    if (!found) return null;
    if (!anchor.quote) return targetElement(found);
    const place = targetPlace(found);
    if (!place) return null;
    return shadowHost(place.getRootNode()) ?? place;
  };
  const fabTargetAt = () => anchorTargetAt(fabAnchor);
  const fabReturnTo = () => returnDestination(fabAnchor, fabOrigin);

  // Opening Comment is an overlay gesture. Any visible part of its subject is
  // enough: placement clips the attachment and keeps the field in the usable window.
  // Only stale standing or a resumed draft whose subject is wholly out of view needs
  // travel (including revealing a closed ancestor), before placement measures it.
  function bringForward(addressable) {
    if (addressable && !seenRect(addressable, new Map()))
      scrollToElement(addressable, "instant");
  }

  // Every explicit target gesture ends here. The gesture has already resolved its stable
  // authored anchor; this command owns the one transition from that target into Comment.
  // Focusing the field drops any older browser selection, and an unsent draft follows the
  // deliberate move. A visual proxy supplies its origin so Escape can return to it.
  function commentOnTarget(
    { anchor, element = null, point = null },
    { origin = null } = {},
  ) {
    cancelRender(selectionUpdate);
    selectionUpdate = null;
    bringForward(element);
    targetActivation = true;
    const selection = getSelection();
    if (selection?.rangeCount) selection.removeAllRanges();
    openComment(anchor, "", { carry: true, point });
    if (origin) showFab(anchor, { origin });
    setTimeout(() => {
      targetActivation = false;
      // A browser command or touch handle can replace the visual target while its
      // selectionchange is held out above. Re-read once the explicit activation is
      // complete so that real later selection is not discarded with the focus collapse.
      scheduleSelectionUpdate();
    });
  }
  // Focusing text entry collapses a native page selection. Hold that browser-authored
  // selectionchange out of updateFab: the durable anchor is already captured, and letting
  // the collapse re-read it as no selection dismisses the field the user just entered.
  function focusFabComment() {
    if (!fabAnchor) return;
    cancelRender(selectionUpdate);
    selectionUpdate = null;
    const handoff = beginFabFocus();
    if (!composerOpen) {
      openComment(structuredClone(fabAnchor), "");
      return;
    }
    const anchor = structuredClone(fabAnchor);
    bringBackSurfaceOf(fabBar);
    landFabFocus(handoff, anchor, () => sameAnchor(anchor, fabAnchor));
  }
  const fabOptionsAvailable = () =>
    Boolean(fabAnchor && hasOtherResponses(fabAnchor) && responseOptionsAvailable());
  const showFabOptions = ({ reaction = false } = {}) =>
    setResponseOptions(true, { focus: reaction ? "reaction" : "first" });
  // The response field follows any selection that stores page words. Even a one-character
  // quote carries its section and exact surrounding context, so the resolver can identify
  // its occurrence without guessing from quote length.
  const hasQuote = (anchor) => Boolean(anchor?.quote?.trim());
  const hasPageSelectionTarget = () => {
    const selection = pageSelection();
    const anchor = selection ? selectionAnchor(selection) : null;
    return hasQuote(anchor);
  };

  // Touch selection belongs to the native handles and menu until Comment is pressed.
  // That menu can stand on either side of the words; never compete with it by raising
  // a second adjacent surface. Capture the passage for the banner's explicit action.
  let touchSelectionAnchor = null;
  const selectionComment = document.createElement("button");
  selectionComment.className = "lf-btn primary";
  selectionComment.type = "button";
  selectionComment.textContent = "Comment on selection";
  registerBannerControl({
    key: "comment-selection",
    control: selectionComment,
    rank: BANNER_CONTROL_RANK.commentSelection,
    seat: "gesture",
    present: false,
  });
  const offerTouchSelection = (anchor) => {
    touchSelectionAnchor = anchor;
    showBannerControl(selectionComment, Boolean(anchor));
  };
  const commentOnTouchSelection = () => {
    const anchor = touchSelectionAnchor;
    if (!anchor) return;
    dismissBannerControls();
    cancelRender(selectionUpdate);
    selectionUpdate = null;
    getSelection()?.removeAllRanges();
    offerTouchSelection(null);
    openComment(anchor, "");
  };

  function updateFab() {
    if (!anchoringIsReady()) {
      offerTouchSelection(null);
      showFab(null);
      return;
    }
    const sel = pageSelection();
    const anchor = sel ? selectionAnchor(sel) : null;
    if (
      (coarsePointer.matches || !placement) &&
      hasQuote(anchor) &&
      (!fabHoldsCapturedPassage() || !sameAnchor(anchor, fabAnchor))
    ) {
      showFab(null);
      offerTouchSelection(anchor);
      return;
    }
    offerTouchSelection(null);
    if (hasQuote(anchor)) {
      // A fast keyboard action can capture this completed native selection before the
      // pointer gesture's queued update arrives. That later update is the same target,
      // not a request to reopen its Comment composer: reopening calls closeReactions
      // and used to collapse choices immediately after `e` exposed them.
      if (sameAnchor(anchor, fabAnchor)) {
        placement?.place();
        return;
      }
      // Selecting words is still the browser's gesture. Open Leaf's response field beside
      // them without moving focus into it, so the live Selection remains available to Copy
      // and the native context menu. An explicit Comment press uses the same field and
      // focuses it through focusFabComment below.
      openComment(anchor, "", { focus: false });
    } else if (fabAnchor?.quote && !fabHoldsCapturedPassage()) showFab(null);
  }
  // Where the pointer stopped is not the question; where the selection is, is. The guard
  // exists so a mouseup inside the runtime's layer — a click in the panel, the composer —
  // can't re-decide the response surface out from under an open draft. A drag that ends on a widget's
  // control is the opposite case: the user was selecting that control's label, and a
  // tab's name runs to within a few pixels of the strip button's padding, so the mouseup
  // lands on chrome while the selection is the page's. The snap runs in the same queued
  // step that raises the field, so the bar lands beside the selection as snapped and
  // the capture reads the one the user is looking at — and only for the primary
  // button, because a right button's release precedes its context menu, and growing the
  // selection there rewrites what Copy was aimed at.
  //
  // Selection opening is counted work in the next rendering pass: the native
  // release finishes first, while the page cannot claim to be settled ahead of its field.
  // A queued step belongs to the gesture that queued it, and the next press may begin
  // before it runs. Then the selection it would act on is not the one it was queued
  // for: it is the drag under way, and `snapSelection` rewrites that drag mid-gesture.
  // Chromium does not resume extending a selection it has been handed through
  // `setBaseAndExtent`, so the pointer's remaining travel is lost and a sweep from
  // "paragraph" to "carrying" ends up captured as "paragraph" — the user's own hand
  // is slow enough that the step always ran first, and a loaded machine hands out that
  // ordering freely. The press under way owns the selection and queues its own step on
  // its own release, so standing down here drops no work.
  //
  // Which press is under way is asked as "has one begun since this was queued" rather
  // than as "is one down now". A press whose release never reaches the document — a
  // handler that stops it, a button let go off-window — leaves a pressed flag standing
  // for the rest of the page's life, and read here that would put every later selection
  // out too: the next drag would raise no field and read as a drag that selected
  // nothing. A count compared against the one this step was queued behind cannot get
  // stuck, because the step queued by the next release carries the count it finds.
  let selectionUpdate = null;
  let pressesBegun = 0;
  const deferSelectionUpdate = (update) => {
    const queuedBehind = pressesBegun;
    cancelRender(selectionUpdate);
    selectionUpdate = nextRender(() => {
      selectionUpdate = null;
      if (pressesBegun !== queuedBehind) return;
      update();
    });
  };
  const scheduleSelectionUpdate = () => {
    if (selectionUpdate) return;
    deferSelectionUpdate(updateFab);
  };
  let pointerSelecting = false;
  let selectionDragged = false;
  let selectionRangeDuringPress = null;
  let selectionPressPoint = null;
  // A widget may turn a press over page words into a different gesture after pointerdown.
  // `preventDefault` on its bubbling pointermove is the shared claim boundary: the
  // selection surface must not restore the range it captured before that claim.
  let selectionGestureClaimed = false;
  let actionPress = false;
  let targetActivation = false;
  let fabInputTakingFocus = false;
  // Which handoff the mark belongs to. The mark itself is one bit, so a landing that only
  // read the bit could not tell its own handoff's mark from a later one's, and releasing
  // on the way out would drop a mark still being held for a focus yet to land.
  let fabFocusHandoff = null;
  const beginFabFocus = () => {
    fabInputTakingFocus = true;
    const handoff = {};
    handoff.intent = retainUserIntent({
      available: () => fabFocusHandoff === handoff,
    });
    fabFocusHandoff = handoff;
    return handoff;
  };
  const endFabFocus = () => {
    fabInputTakingFocus = false;
    fabFocusHandoff = null;
  };
  // Every handoff lands here. It is marked at once and lands a frame or more later, and
  // the user owns the page for the whole of that gap: a passage standing when it lands
  // that this composer did not open on is theirs, taken since, and focusing the field
  // would collapse it before anything could read it. Standing down releases the mark with
  // it, so the collapse the mark holds out cannot outlive the focus it was holding it for.
  function landFabFocus(handoff, anchor, stands) {
    handoff.intent = restrictUserIntent(
      handoff.intent,
      () => composerOpen && stands() && sameAnchor(anchor, fabAnchor),
    );
    void fabPositioned().then((positioned) => {
      if (handoff !== fabFocusHandoff) return;
      const taken = pageSelection();
      const words = taken ? selectionAnchor(taken) : null;
      const landed =
        positioned &&
        (!hasQuote(words) || sameAnchor(words, anchor)) &&
        handoff.intent.handoff(() => fabInput.focus({ preventScroll: true }));
      if (!landed) endFabFocus();
    });
  }

  // Only a successful current Thread cohort may reveal the fallback home. Retirement
  // and rollback still move the native editor there without authorizing navigation.
  // An opening gesture keeps its original input generation through that preparation.
  function finishPlacement() {
    if (
      placement ||
      !revealResponseHome ||
      fabBar.parentElement !== responseHome ||
      !fabAnchor ||
      !composerOpen
    )
      return;
    if (!fabFocusHandoff?.intent.handoff(revealResponseHome)) {
      answerFabPosition(false);
      return;
    }
    answerFabPosition(true);
  }
  function openComment(anchor, text, options = {}) {
    return openComposer(anchor, text, options);
  }
  function fabHoldsCapturedPassage() {
    return (
      fabInputTakingFocus ||
      fabBar.contains(fabFocused()) ||
      reactionContextContains(fabFocused())
    );
  }
  // Wired once the chrome is mounted (leaf.js): the box is selection.js's, an owner that
  // imports this module back.
  function wireFabInput() {
    fabInput.addEventListener("focus", () => {
      cancelRender(selectionUpdate);
      selectionUpdate = null;
      fabInputTakingFocus = true;
    });
    fabInput.addEventListener("blur", () => {
      fabInputTakingFocus = false;
    });
  }
  let primaryPointerPressed = false;
  // Whether the page's own words stood selected when the shortcut bar was last painted for
  // this press. The bar waits for the release; the Escape rung cannot, because from the
  // first glyph a drag takes, Escape clears the selection rather than letting go of the
  // control the user is standing on, and until now nothing repainted the line inside a
  // press — the word only became true when the frame the press itself scheduled happened
  // to land after the drag had moved, and stayed a lie for a whole heartbeat when it
  // landed before. Only the crossing is painted: a drag growing a selection that already
  // stands says the same word, and repainting the chrome on every move of a drag would
  // put a whole shared repaint inside every frame of one.
  let selectionStood = false;
  // The page's own words this press began with, against the ones it ends holding: what
  // tells a gesture that took words from a press that merely landed in some (the click
  // door below). Read beside `selectionStood`, ahead of the browser's own collapse, for
  // the same reason.
  let wordsAtPress = "";
  // What this drag has had inside the document, kept against a release that ends holding
  // something else. Only while both ends are still in it: `pageSelection` answers for the
  // end the press began at, which stays in the page for the whole of a drag that leaves it,
  // so without the far end this remembered the runaway range itself and had nothing to put
  // back.
  const rememberPointerSelection = () => {
    const selection = pageSelection();
    if (!selection || leftThePage(selection)) return;
    const anchor = selectionAnchor(selection);
    if (hasQuote(anchor)) selectionRangeDuringPress = pageRange(selection).cloneRange();
  };

  const finishPointerSelection = (ev) => {
    if (drawModeActive()) return;
    // A mouse pointer is followed by the compatibility mouseup below, which performs the
    // sentence snap before opening the field. Opening from pointerup first would focus the
    // field and collapse the still-unsnapped Selection before mouseup can finish it.
    // Touch/pen and cancellation owe us no compatibility mouse event, so they keep this
    // direct route.
    // Released on the next task either way, which keeps selectionchange in the
    // in-progress branch until the compatibility mouseup has been and gone.
    const releasePress = () =>
      setTimeout(() => {
        actionPress = false;
      });
    // Opening or acting in chrome is a route away from the page, not a new selection
    // gesture. Keep the already-captured touch passage verbatim while focus moves
    // through the banner, its sibling popovers, and their controls.
    if (touchSelectionAnchor && inChrome(ev.target)) {
      primaryPointerPressed = false;
      pointerSelecting = false;
      selectionGestureClaimed = false;
      releasePress();
      return;
    }
    if (
      primaryPointerPressed &&
      ev.type === "pointerup" &&
      ev.pointerType === "mouse"
    ) {
      releasePress();
      return;
    }
    if (primaryPointerPressed) scheduleSelectionUpdate();
    primaryPointerPressed = false;
    pointerSelecting = false;
    selectionGestureClaimed = false;
    releasePress();
  };

  // Touch handles and browser selection commands do not owe the page a mouseup or keyup.
  // During a pointer drag, the completed gesture below remains the one that snaps and
  // places the passage; presses on the action surface must not retract their own target.

  // Selections made from the keyboard (shift-arrows, ⌘A) deserve the same response bar. Typing in
  // a box never does, whatever is selected elsewhere.

  // Floating chrome getting out of the way of a press somewhere else, which is a fact about
  // the press rather than about who receives it: the aim takes a press away from the page
  // (see claimPress) and must not take this with it, or the command reference stays up over
  // the composer that press just opened. Hence one function, called from both.
  // The two side panels are absent from it on purpose. A float answers the press in front
  // of it and stands down behind it; the thread panel and the leaves drawer are
  // auxiliary surfaces the user stood up, kept through a reload (AUXILIARY_SURFACE_KEY) and so
  // through a click all the more — a drawer any press removes cannot be watched while
  // working, which is the drawer's point. Each closes by its own button, its key, or Esc.
  function standDown(target) {
    const visual = visualAt(target);
    const sameVisual =
      visual &&
      !fabAnchor?.quote &&
      fabAnchor?.section === visual.id &&
      fabAnchor?.visual === visual.part?.id;
    if (
      !sameVisual &&
      !target.closest?.(".lf-fab-bar, .lf-react-surface, .lf-composer") &&
      !reactionContextContains(target)
    ) {
      if (composerOpen) hideComposer();
      showFab(null, { returnFocus: "page" });
      // The armed react press goes with the bar it was armed on.
      setReact(false);
    }
    if (commandReferenceOpen() && !target.closest?.(".lf-command-reference"))
      hideReference();
    if (!target.closest?.(".lf-command-reference, .lf-shortcut-bar"))
      collapseShortcutBar();
    // The press on the button itself is its own toggle, so it is not an outside click;
    // without that the open and this close would both run and the menu could never open.
    if (versionMenuIsOpen() && !target.closest?.(".lf-version-menu, .lf-version"))
      closeVersionMenu();
  }
  // Document listeners see a shadow-tree press retargeted to its host. Read the
  // composed origin so core controls seated in a widget surface remain inside their
  // own composer/reaction layer instead of being dismissed before `click` can fire.

  // What a plain click on the page means, decided once. Design mode explicitly changes the
  // grammar, and a visible mark opens its thread. Unadorned authored content keeps the
  // browser's native meaning; Comment targeting belongs to Alt-click, `s`, and the visual
  // proxies instead.
  //
  // Once, because the hit-test reads layout and opening the panel rewrites it. Two handlers
  // each asking `markAt` looked independent and were not: the first one's setPanel() reflowed
  // the document out from under the second, which then missed the very mark it had just
  // opened and raised the comment field on top of it — leaving an element anchor set, which
  // midComposition() reads, so the page quietly stopped following new versions. The rule this
  // file already carries covers it: a guard that reads state another function wrote is a sign
  // the two are one function.

  const fabAnchorAt = () => fabAnchor;
  const fabPointAt = () => fabPointIn(fabTargetAt());

  function mount() {
    placement?.mount();
    // Keep the native selection through the button's press; focusing the actual
    // comment field performs the handoff after the passage has been captured.
    selectionComment.addEventListener("mousedown", (event) => event.preventDefault());
    selectionComment.addEventListener("click", commentOnTouchSelection);
    coarsePointer.addEventListener("change", scheduleSelectionUpdate);
    document.addEventListener(
      "pointerdown",
      (ev) => {
        if (drawModeActive()) return;
        primaryPointerPressed = ev.isPrimary && ev.button === 0;
        if (primaryPointerPressed) pressesBegun++;
        pointerSelecting = primaryPointerPressed && pageWords(ev.target);
        selectionDragged = false;
        selectionRangeDuringPress = null;
        selectionGestureClaimed = false;
        selectionPressPoint = pointerSelecting
          ? { x: ev.clientX, y: ev.clientY }
          : null;
        // Read here, ahead of the browser's own collapse, so the first crossing this press
        // makes is measured against what the line already says rather than against nothing.
        const stood = pageSelection();
        selectionStood = Boolean(stood);
        wordsAtPress = stood ? stood.toString() : "";
        const selection = pointerSelecting ? stood : null;
        if (selection && pageRange(selection).intersectsNode(ev.target))
          rememberPointerSelection();
        actionPress =
          (touchSelectionAnchor && inChrome(ev.target)) ||
          ev.target === selectionComment ||
          Boolean(ev.target.closest?.(".lf-react-surface, .lf-composer"));
      },
      true,
    );
    document.addEventListener("pointermove", (ev) => {
      if (drawModeActive()) return;
      if (!pointerSelecting || !selectionPressPoint) return;
      if (ev.defaultPrevented) {
        selectionGestureClaimed = true;
        return;
      }
      selectionDragged ||=
        Math.hypot(
          ev.clientX - selectionPressPoint.x,
          ev.clientY - selectionPressPoint.y,
        ) > 3;
    });
    document.addEventListener("pointerup", finishPointerSelection);
    document.addEventListener("pointercancel", finishPointerSelection);
    document.addEventListener("selectionchange", () => {
      if (primaryPointerPressed) {
        rememberPointerSelection();
        const stands = Boolean(pageSelection());
        if (stands !== selectionStood) {
          selectionStood = stands;
          repaint();
        }
        return;
      }
      // The captured passage is not asked about here. What the handoff has to survive is
      // the collapse focusing the field causes, and `updateFab` holds that out at the one
      // branch that acts on an empty selection. Restated here it also swallowed the
      // opposite event: a passage the user went on to select, arriving while the bar
      // still held focus or while its focus was in flight, read as the collapse and was
      // dropped — and the handoff then landed on the field and collapsed the selection,
      // so nothing was left to re-read and the target never moved.
      if (actionPress || targetActivation || takesLetters(document.activeElement))
        return;
      scheduleSelectionUpdate();
    });
    document.addEventListener("mouseup", (ev) => {
      if (drawModeActive()) return;
      const selectedOnPage = pointerSelecting;
      primaryPointerPressed = false;
      pointerSelecting = false;
      const gestureClaimed = selectionGestureClaimed;
      selectionGestureClaimed = false;
      if (gestureClaimed) {
        selectionRangeDuringPress = null;
        scheduleSelectionUpdate();
        return;
      }
      // Only a gesture begun in page words owns their selection. A release from
      // chrome (such as resizing a panel) must not snap an existing passage.
      if (actionPress || !selectedOnPage) return;
      const selection = pageSelection();
      const selected = selection ? selectionAnchor(selection) : null;
      // A drag whose far end left the document is the same release as one that ended holding
      // nothing: what the user meant is what the drag had before the pointer crossed out,
      // and the range this press remembered is that. Without it, a hand five words along a
      // paragraph overshooting the layer by 40px captured 14,387 characters, marked 22,140,
      // and named the whole document in the field — because past the page's last words the
      // browser extends through everything between (leftThePage, composing/capture.js).
      //
      // Asked here and nowhere shared, because the gesture is what tells this from ⌘A: select
      // all means the document and lands its far end past the page by definition, and it
      // arrives through the keyboard's route, which never comes past this line.
      const escaped = selectionDragged && leftThePage();
      const completed =
        selectionDragged && (escaped || !hasQuote(selected))
          ? selectionRangeDuringPress
          : null;
      deferSelectionUpdate(() => {
        if (completed) {
          const restored = getSelection();
          restored.removeAllRanges();
          restored.addRange(completed);
        } else if (escaped) {
          // A drag that crossed out before it covered anything has no passage to offer and
          // no words to put back. The browser's own selection stays where it is — the user
          // can still copy it — and the response surface says nothing about it.
          showFab(null);
          return;
        }
        if (ev.button === 0) snapSelection();
        updateFab();
      });
    });
    document.addEventListener("keyup", (ev) => {
      if (dismissedSelectionKeyup) {
        dismissedSelectionKeyup = false;
        if (ev.key === "Escape") return;
      }
      if (isReactArmed()) return;
      if (takesLetters(ev.target) || inChrome(ev.target)) return;
      if (!pageWords(ev.target) && !pageSelection()) return;
      scheduleSelectionUpdate();
    });
    document.addEventListener("mousedown", (ev) => {
      if (!drawModeActive()) standDown(ev.composedPath()[0]);
    });
    document.addEventListener("click", (ev) => {
      if (drawModeActive()) return;
      if (!pageWords(ev.target)) return;
      // A press that ends holding words it did not begin with took them, and is that
      // selection's mouseup rather than a click on whatever lies under it: the user was
      // reaching for the words, and the 💬 is already up on them (updateFab, on the same
      // mouseup). The same complaint `offer` answers for a press on a control and the
      // thread list for a press on a card (reachedForWords), and it governs the whole of
      // what a click on prose means — the block design mode comments on, and the thread a
      // mark opens. Marked words are where it showed: a gesture inside one travelled to its
      // thread, and with Threads open the reply box it landed in collapsed the selection
      // the user had just made, so the words and the 💬 went with it.
      //
      // Asked of what this press changed rather than of the standing selection those two
      // have to read, because a mark is a painted range with no element to put the question
      // to — and because the state alone is too strict: a press landing inside words
      // already selected keeps them through its own mousedown, so it would refuse the press
      // that opens the very mark the user just picked out. That press is also the only
      // way the two readings can come out the same, since every other gesture moves the
      // selection before its click.
      //
      // Changed, and not "dragged": how far the pointer travelled covers one of the three
      // ways a user takes words, and a double-click's second press and a shift-click's
      // extension both arrive here having just taken some without moving it at all.
      const words = pageSelection();
      if (words && words.toString() !== wordsAtPress) return;
      // A plain click comments on the block it landed in. Read where it landed rather than
      // at a widget host, since a Leaf surface the widget seats in its shadow tree answers
      // for itself (design.js).
      if (designModeActive()) {
        const target = designTarget(ev.composedPath()[0]);
        if (target) openOnDesign(target);
        return;
      }
      // The record rather than this event's own coordinates, for the reason the record is
      // kept from a pointer event at all (pointer.js): `click` is a legacy mouse event and
      // carries the pointer's place rounded to a whole pixel, while markAt measures against
      // getClientRects, whose edges are floats. Asked at the rounded point this answered a
      // different thread than refreshHover had just promised at the true one — a quote lit
      // up under the hand and a press on it opening nothing.
      //
      // A click with no press behind it carries 0,0 rather than a position — `offer` calls
      // click() to supply the keys a span doesn't come with — and the record would answer
      // for wherever the pointer is parked, so that one keeps reading the event.
      const point = ev.detail ? pointerAt() : { x: ev.clientX, y: ev.clientY };
      const threadId = markAt?.(point.x, point.y);
      if (threadId)
        return void openPageThread(threadId, {
          focus: panel.classList.contains("open") ? "reply" : "thread",
          travel: false,
        });
    });
    wireFabInput();
  }

  // ---------- where "comment" goes ----------
  // The thread the user is standing in, and the box it is written in. Three
  // containers hold one and the user can stand in any of them: the panel's thread, a
  // thread seated on the page (x-thread-seat), and each thread inside that seat.
  // They are one question — a press meaning "say something about this" belongs to the box
  // of the thread the user is already in — so they get one reading rather than a
  // rule for the panel and a different one for the page.
  //
  // One of the three is in the chrome, which is not the exception it looks like: page scope
  // already crosses there. A page key that takes the user somewhere owes them an answer
  // once they are standing there.
  //
  // One live aim and then one climb, rather than four cases. A selection outranks
  // position; a captured target does too until the user stands elsewhere. The draft
  // keeps its words independently of which target the next press names. Below the
  // aim, the answer walks
  // outward from where they are standing — the nearest thread's box, then the nearest
  // addressable element, then the page, which is what is left when they are standing
  // nowhere in it. An element anchor answers in its own word (a figure, a card), the way
  // the panel names one. Every destination is a box to write in and says so in the same
  // sentence; the word is what varies.
  const commenting = (word) => ({
    title: `comment on the ${word}`,
  });
  function commentDestination() {
    if (touchSelectionAnchor)
      return {
        ...commenting("selection"),
        box: selectionComment,
        go: commentOnTouchSelection,
      };
    const here = standingTarget();
    const anchor = fabAnchorAt();
    // The thread the user is at continues where it is about what they stand on: they
    // are in it, or its target lies within the element they stand at — the Ask holding
    // focus, answered or not, else the element itself — as an Ask's options group does
    // when the user holds one of its marks. A card showing an enclosing block's thread is
    // about that block, so an element inside it, such as an Ask in a commented task,
    // takes a thread of its own, and a selection still starts one on its words.

    const inline = threadHere();
    const target = inline && threadTarget(inline);
    const inlineBox =
      inline &&
      (!here ||
        inline.contains(focused()) ||
        (target && under(target, heldAsk() ?? here.element))) &&
      threadInput(inline);
    const said =
      standingThread() ?? (inlineBox ? { held: inline, box: inlineBox } : null);
    // A captured passage outranks the focus it preceded, but a kept draft is not a
    // standing target. Read both page and thread standing before choosing the aim.
    // After the user lands elsewhere, Comment names that new place;
    // commentOnTarget carries the old words without replacing a destination's
    // independent draft.
    if (
      anchor &&
      (pageSelection() ||
        fabHoldsCapturedPassage() ||
        (!said && (!here || here.element === fabTargetAt())))
    )
      return {
        ...commenting(
          anchor.quote
            ? "selection"
            : addressableWord(elementById(anchor.section)) || "element",
        ),
        box: fabInput,
        go: focusFabComment,
      };
    if (said)
      return {
        ...commenting("thread"),
        box: said.box,
        go: () => {
          carryComposerToReply(replyDraftContext(said.box));
          landIn(said);
        },
      };
    if (here)
      return {
        ...commenting(here.anchor.datum ? "item" : addressableWord(here.element)),
        box: fabInput,
        go: () => commentOnTarget(here),
      };
    return {
      ...commenting("page"),
      box: generalInput,
      // Two steps down and two back: the box hands the user to the list it belongs
      // to, and the panel hands them to the page.
      go: () => {
        setPanel(true);
        generalInput.focus({ preventScroll: true });
      },
    };
  }

  // The destination's box is the identity chrome uses to place a contextual binding badge,
  // and the label is whichever Comment route dispatch would answer from here. Dispatch
  // still decides whether either row can be reached from the current scope.
  const commentHint = () => ({
    box: commentDestination().box,
    label: activeCommandLabel(["comment.create"]),
  });

  // c goes where commenting happens: a live selection gets the composer (what the floating
  // button does), an element click's pending 💬 gets that, an open thread the user is
  // standing in gets its own reply box, the item they are standing in gets the box
  // belonging to it, and otherwise the page's general box. That box lives in Threads, but c
  // names and focuses the box directly; g T independently names the list. Never the panel's
  // collapse: c doubled as the toggle once, so with the panel standing open the key that
  // promised “comment” answered “close”. Backing out is whatever the box is standing in.
  //
  // Standing outranks the page; a live selection or a newly captured target outranks
  // standing. The draft stored on an earlier target supplies words, not that priority.
  pageCommand({
    id: "comment.create",
    touch: false,
    keys: ["c"],
    // The surfaces name the destination in front of the user rather than the capability:
    // "Comment" covered all four and so promised none of them.
    description: () => commentDestination().description,
    title: () => commentDestination().title,
    // A selection made before the anchor pass has run can't be quoted yet, and commenting
    // on the page instead is not what the user asked for — so the press waits, and the
    // row's own liveness is where that is said rather than a refusal inside run that no
    // surface can see.
    //
    // One row answers from the page and from the Threads panel alike, whether the panel
    // stands beside the page or covers it: a covering surface drops every page row not
    // marked `covering`, and a copy of this one in the panel's scope knew only the page box.
    // Under any other covering surface there is nothing here to comment on.
    covering: true,
    when: () =>
      (anchoringIsReady() || !pageSelection()) &&
      (!coveringAuxiliarySurface() || inPanel(panelIsOpen)),
    run: () => {
      updateFab(); // the selection may be newer than the mouseup that last placed the bar
      commentDestination().go();
    },
  });

  // The composer's own rung is its own scope rather than the box's, because the box may not
  // have focus — the user clicked away and the composer still stands, holding their draft.
  pageScope("composer", {
    title: "In the composer",
    at: () => composerOpen && !placement?.withheld(),
    rows: [
      {
        id: "comment.options",
        keys: ["Tab"],
        description: "Show other responses",
        title: "other responses",
        when: () => fabOptionsAvailable() && !responseOptionsAreOpen(),
        run: () => showFabOptions(),
      },
      {
        id: "composer.close",
        keys: ["Escape"],
        description: () =>
          composerHolds()
            ? "Close the composer, keeping the draft"
            : "Close the composer",
        title: () => (composerHolds() ? "close — draft kept" : "close"),
        promoteEscape: false,
        when: () => !responseOptionsAreOpen(),
        run: () => dismissFab(),
      },
    ],
  });

  // The first step of the page's Escape ladder: a selection or a captured target is the
  // innermost thing the user is holding, and letting it go is one press. Clearing a
  // captured target is still available while c and r are the two actions on the thing the
  // user just chose, so it keeps its binding and its place in the reference while
  // yielding the short line's promoted slot to them.
  pageRung("selection", () =>
    pageSelection() || (fabAnchorAt() && !placement?.withheld())
      ? {
          title: "unselect",
          description: "Clear the selection",
          promoteEscape: !Boolean(fabAnchorAt()) || reactionTokens().length === 0,
          out: dismissFab,
        }
      : null,
  );

  return {
    commentHint,
    fabPositioned,
    beginFabFocus,
    endFabFocus,
    landFabFocus,
    anchorStands,
    showFab,
    dismissFab,
    refreshFab,
    anchorTargetAt,
    fabTargetAt,
    fabReturnTo,
    bringForward,
    commentOnTarget,
    focusFabComment,
    fabOptionsAvailable,
    showFabOptions,
    hasPageSelectionTarget,
    updateFab,
    standDown,
    fabAnchorAt,
    fabPointAt,
    fabFrameAt: () => placement?.frame() ?? null,
    seatFab,
    restoreFab,
    finishPlacement,
    fabInlineOutlet: () => fabInlineOutlet,
    mount,
  };
}
