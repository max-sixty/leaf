/* The anchored response bar: where it stands, what raises it, and the room it keeps.

   Normal reading mode leaves a plain click on unadorned authored content to the
   browser. Visible native and Leaf controls keep their click actions; text selection
   targets words. Alt-click, `s`, and a visual's “Respond to…” proxy are explicit
   Comment gestures. They pass a stable target from `aimTargetAt` or the visual provider
   into this surface. A whole item or picture names its authored id, while a visual part
   adds its declared token. Comment opens the compact field; Other responses opens an
   anchored picker, reached by the ⋯ in the empty field's corner, Tab from the field,
   or `e` while the field stands unfocused. Escape closes the picker; Escape from the
   field hides the draft. The same anchor resolves both states against the target's
   geometry.
   An active quoted draft whose words change stays beside its containing subject; this is
   placement only and never changes the quote recorded by its eventual send.

   The bar a selection or keyboard-selected addressable raises is `.lf-fab-bar`: the
   durable, compact `.lf-fab-input`, whose corner holds its Other responses control
   until the draft has words (composing/selection.js). An explicit addressable target
   opens and focuses that field. On desktop, selecting a passage leaves the field open
   but unfocused. Selection observed outside a completed page gesture, and selection on
   touch screens, is offered in the floating panel's page field instead, whose
   placeholder quotes it; a press on that field comments on the passage, which clears
   the native selection menu and opens this field (`offerSelection`). Until that press
   the native handles and menu have the passage to themselves. The field grows in place
   and never transfers text into a second composer card. A one-line note uses the shared action corner. A longer one widens
   within the thread card’s measure and then wraps. A transparent envelope fits the
   first message and the card’s metadata and reply slots before typing; only the
   editor paints then.

   The editor has one native seat, whether a widget, page or selected presentation
   holds it. Seating and restoring move that same node while retaining its draft,
   caret and focus. Readiness resolves only when the actual seat or presentation
   commits it; creating a composer does not claim that it has a place. An explicit
   opening reveals an inline seat after it has landed and taken focus; a floating
   presentation owns its own placement and reveal.

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

   Boot supplies travel, delivery and mode commands to one surface owner, which builds
   the selection composer (composing/selection.js) from them and its own bar commands.
   Its constructor binds no document listeners; mount installs the selection gesture
   lifecycle and field-focus tracking after all capabilities have been composed. */
import { signal } from "/runtime/framework.js";
import { addressableWord } from "../addressable-names.js";
import {
  anchoringIsReady,
  lightSeat,
  resolveAnchor,
  visualAt,
} from "../anchor-resolution.js";
import { sameAnchor } from "../anchor-coordinate.js";
import { CARET_KEYS, selectsAll, WORKS } from "../control-selectors.js";
import { bringBackSurfaceOf } from "../off-flow.js";
import { seenRect, underOccluder } from "../geometry.js";
import { scrollIntoView } from "../landing-scroll.js";
import { cancelRender, nextRender } from "../rendering.js";
import {
  targetElement,
  targetPlace,
  targetSegments,
  targetRange,
} from "../resolved-target.js";
import {
  composerOpen,
  createSelectionComposer,
  fabBar,
  fabInput,
  fabOptionsTrigger,
  pendingAbout,
} from "./selection.js";

import { paintBarReactions, reactionAvailable } from "../reactions.js";
import { threadInput, currentLocationThread } from "../thread/landing.js";
import { replyDraftContext } from "../thread/replies.js";
import { activeCommandLabel } from "../keyboard/dispatch.js";
import { pageCommand, pageRung, pageScope } from "../keyboard/register.js";

import {
  elementById,
  closestAcross,
  inChrome,
  pageRange,
  pageWords,
  programmaticSelection,
  selectEnds,
  selectionBackward,
} from "../passages.js";
import {
  leftThePage,
  pageSelection,
  selectionAnchor,
  snapSelection,
} from "./capture.js";
import { repaint } from "../repaint.js";
import {
  drawn,
  handBack,
  holdFocus,
  layerLanding,
  letGo,
  takesLetters,
  focusDestination,
  focused,
  closeLayer,
  onPress,
  onPressAway,
  pressRecords,
} from "../focus.js";
import { commandScope, projectCommandScope } from "../keyboard/scopes.js";
import { under, upFrom } from "../shadow.js";
import { nativeLayers } from "../keyboard/layer-stack.js";
import { heldObligation } from "../current-target.js";

import { coarsePointer, pointerAt, pressIsKeyboardActivation } from "../pointer.js";
import { anchorLabel } from "../thread/messages.js";

import { livePoint } from "../pointed-place.js";
import { keeps } from "../keeps.js";
import { move } from "../dom-move.js";
import { retainUserIntent, restrictUserIntent } from "../user-intent.js";

export function createResponseSurface({
  rememberSelection,
  landIn,
  threadHere,
  threadAtCurrentLocation,
  replyThreadAtCurrentLocation,
  threadTarget,
  currentTarget,
  markAt,
  scrollToElement,
  scrollToRange,
  visualActionAnchor,
  designModeActive,
  designTarget,
  openOnDesign,
  isReactArmed,
  reactionContextContains,
  reactionTokens,
  setReact,
  openPageThread,
  drawModeActive,
  captureActive,
  refreshThread,
  dismissThreadView,
  pageComment,
  responseHome,
  revealResponseHome = null,
  createComment,
  landSent,
  wireInput,
  drawingEdits,
  createPlacement = null,
}) {
  const hasOtherResponses = (anchor) =>
    reactionTokens().length > 0 || Boolean(anchor?.quote && !designModeActive());

  // ---------- selection → comment ----------
  // What the comment box's bar answers, a signal since its rows' availability reads it
  // (keyboard/scopes.js).
  const fabAnchor = signal(null);
  // The row inside the target the gesture that opened this bar pointed at, which the bar
  // stands level with (pointed-place.js).
  let fabPoint = null;
  let usesPlacement = false;
  let fabInlineOutlet = null;
  let fabPositionWaiters = [];
  const fabFocused = () => focused(fabInlineOutlet ? null : document);

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
    !fabAnchor.value
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
  // so the user's place in it, caret and composition included, crosses light and shadow
  // DOM moves with it (`move`).
  function moveFab(parent) {
    if (fabBar.parentElement !== parent) move(parent, fabBar, null);
  }

  // Whether the bar stands inline in an outlet or floats, said as the one attribute the
  // stylesheets read. Floating, the selected presentation decides whether it shows
  // (`data-lf-placement`, `data-lf-withheld`); core writes no visibility of its own.
  const presentFab = () =>
    keeps(fabBar, "data-lf-presentation", fabInlineOutlet ? "inline" : null);

  function seatFab(outlet) {
    if (!(outlet instanceof Element) || !fabAnchor.value || !composerOpen) return false;
    // A seat a panel stands over cannot take the user even where it paints: the panels
    // dominate what focus reaches, so the editor stays at its home instead. The seat is
    // judged, not the editor moved into it, which measures no width until the outlet
    // renders it; a boxless outlet is judged by the box that lays out what it holds.
    let seat = outlet;
    while (seat && !(seat.getBoundingClientRect().width > 0)) seat = upFrom(seat);
    if (seat && underOccluder(seat)) return false;
    // Admit the actual editor after its native move: an empty or display:contents
    // outlet has no visibility of its own. A rejected nomination leaves the previous
    // seat, geometry and held typing place intact so the cohort can try its fallback.
    const previousParent = fabBar.parentNode;
    const previousOutlet = fabInlineOutlet;
    const restoreFocus = holdFocus(fabBar);
    if (fabBar.parentNode !== outlet) move(outlet, fabBar, null);
    fabInlineOutlet = outlet;
    presentFab();
    if (!fabDrawn()) {
      if (previousParent && fabBar.parentNode !== previousParent)
        move(previousParent, fabBar, null);
      else if (!previousParent) fabBar.remove();
      fabInlineOutlet = previousOutlet;
      presentFab();
      restoreFocus?.();
      return false;
    }
    if (usesPlacement) stopFabPositioning({ reset: true, repositioning: true });
    usesPlacement = false;
    answerFabPosition(true);
    placement?.stoodAgain();
    restoreFocus?.();
    return true;
  }

  function restoreFab({ place = true } = {}) {
    if (
      (placement || !place || !fabAnchor.value || !composerOpen) &&
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
    presentFab();
    // Retiring an outlet must return the native editor even when its home is hidden.
    // The home owns its lifetime; actual editor visibility alone answers readiness.
    moveFab(responseHome);
    if (!placement && place && fabAnchor.value && responseHome.isConnected) {
      answerFabPosition(true);
      restoreFocus?.();
    } else if (place && fabAnchor.value && standFab() && restoreFocus)
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
  const responseTarget = (anchor) => {
    if (!anchor) return null;
    const found = resolveAnchor(anchor);
    if (standsIn(anchor, found)) return found;
    // Reading saved edits or a later revision can replace the words under a live
    // draft. Its original anchor remains the event's meaning; its containing
    // subject supplies only a place to keep the editor visible and editable. An
    // explicitly detached quote never named that subject as its resolved location.
    return composerOpen &&
      anchor.quote &&
      !anchor.detached &&
      sameAnchor(anchor, fabAnchor.value)
      ? (found ?? resolveAnchor({ section: anchor.section }))
      : null;
  };
  const anchorStands = (anchor) => Boolean(responseTarget(anchor));
  const fabPointIn = (target) =>
    fabAnchor.value?.quote ? null : livePoint(target, fabPoint);
  const placement =
    createPlacement?.({
      bar: fabBar,
      input: fabInput,
      response: {
        get anchor() {
          return fabAnchor.value;
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
        get resolved() {
          return responseTarget(fabAnchor.value);
        },
        get captured() {
          return fabHoldsCapturedPassage();
        },
        pointIn: fabPointIn,
      },
      positioned: answerFabPosition,
      dismiss: () => letGoOfFab(),
      scrollToElement,
      scrollToRange,
    }) ?? null;
  // An element response exits to its subject, or the declared proxy representing it
  // where the subject cannot take focus. Resolve that structural parent from the current
  // anchor, so c from an obligation and an aimed press on the same obligation unwind alike.
  // There is no saved pre-command focus: being on an option comments on its obligation,
  // and closing returns to the obligation itself. A drawing's proxy is the fallback, not
  // the parent, even for a user who pressed it: focused, its face stands at the
  // window's head, away from the drawing it is about (chrome.css). A quoted selection clears to
  // the page; a removed subject has no parent to land on.
  const returnPlaces = (anchor) =>
    anchor && !anchor.quote ? [anchorTargetAt(anchor), visualActionAnchor(anchor)] : [];
  // Putting the bar away is closing a layer (focus.js, `closeLayer`): `showFab(null)`
  // moves no focus, and the closer names where a user who was in the bar lands, read
  // before it goes. `putAwayFab` hands them back to the bar's subject; `letGoOfFab` lets
  // them go onto the page, from the bar or from that subject.
  function landingFromBar(toPage) {
    const leavingBar = fabBar.contains(fabFocused());
    const places = leavingBar || toPage ? returnPlaces(fabAnchor.value) : [];
    return layerLanding(() => {
      // The shared return tests each place in turn: a subject that cannot take focus
      // yields to its proxy. If neither remains, it lands on the page.
      if (leavingBar && !toPage) handBack(...places);
      else if (leavingBar || (toPage && places.includes(focused(document)))) letGo();
    });
  }
  function putAwayFab() {
    const land = landingFromBar(false);
    closeLayer(() => showFab(null), land);
  }
  function letGoOfFab() {
    const land = landingFromBar(true);
    closeLayer(() => showFab(null), land);
  }
  // The bar's whole paint for the anchor it stands on, or for none: whether it shows,
  // whether only its target is chosen, which responses it offers, and what it is called.
  // Comment returns from the bar's choice state to this same field. With only a target
  // chosen, the button is the affordance; once Comment is open, the input replaces it.
  function paintFab() {
    fabBar.toggleAttribute(
      "data-lf-target-only",
      Boolean(fabAnchor.value && !composerOpen),
    );
    composer.syncResponseOptions(fabAnchor.value);
    if (!fabAnchor.value) return;
    const label = anchorLabel(fabAnchor.value, pendingAbout).replace(/^§\s*/, "");
    keeps(fabBar, "aria-label", label ? `Respond to ${label}` : "Respond");
    keeps(fabInput, "aria-label", label ? `Comment on ${label}` : "Comment");
    paintBarReactions(fabAnchor.value);
  }
  // The bar taken down: no anchor, no placement, no open responses or composer. Both
  // ways it goes, put away and refused room on opening, end here.
  function clearFab() {
    fabInputTakingFocus = false;
    composer.resetResponseOptions();
    placement?.release();
    if (composerOpen) composer.hideComposer();
    fabPoint = null;
    stopFabPositioning({ reset: true });
    fabAnchor.value = null;
    usesPlacement = Boolean(placement);
    paintFab();
  }
  function showFab(anchor, { place = true, point = undefined, reveal = false } = {}) {
    const previous = fabAnchor.value;
    if (!anchor) {
      restoreFab({ place: false });
      clearFab();
    } else {
      const previousFloating = usesPlacement;
      const same = sameAnchor(previous, anchor);
      const keptInline = Boolean(fabInlineOutlet?.isConnected && previous && same);
      if (fabInlineOutlet && !keptInline) restoreFab({ place: false });
      if (!same) {
        if (previous) composer.resetResponseOptions();
        placement?.release();
      }
      // A gesture opening the bar says where in its target the bar stands, `null` for
      // nowhere; re-placing the bar on the same anchor keeps where the last one said, and
      // any other anchor starts at its target's top.
      const stands = point !== undefined ? point : same ? fabPoint : null;
      const pointMoved = stands !== fabPoint;
      fabPoint = stands;
      if (!same || !place || pointMoved || (!previousFloating && !keptInline))
        stopFabPositioning({ reset: true });
      fabAnchor.value = anchor;
      usesPlacement = Boolean(placement) && place && !keptInline;
      paintFab();
      // A margin control can name an item whose rendered box is currently off
      // screen. `e` still needs the durable anchor so it can extend that existing item;
      // in that route the floating bar is never painted and placement is deliberately
      // skipped. Every route that actually shows the bar keeps the geometry gate. The gate
      // is for opening: the bar already being on this anchor, placed again, is
      // withheld rather than put away (standFab).
      if (usesPlacement && !placement.place({ reveal })) {
        if (same && placement.stands()) placement.withhold();
        else clearFab();
      }
    }
    // A bar raised on a new target takes the thread card down: the card stands above
    // page-level chrome and may cover the bar, and the user has moved on from its thread
    // to a new response, as opening a margin entry's options closes it.
    if (fabAnchor.value && usesPlacement && !sameAnchor(previous, fabAnchor.value))
      dismissThreadView();
    if (!sameAnchor(previous, fabAnchor.value)) refreshThread();
    repaint(); // the c row names this anchor, so the line is one more rendering of it
  }
  let dismissedSelectionKeyup = false;
  function dismissFab() {
    dismissedSelectionKeyup = Boolean(pageSelection() || fabAnchor.value?.quote);
    pageSelection()?.removeAllRanges();
    putAwayFab();
  }
  function refreshFab() {
    if (!fabAnchor.value || !usesPlacement) return;
    // A bare selection's bar is the selection's, and goes with it.
    if (fabAnchor.value.quote && !composerOpen && !fabHoldsCapturedPassage())
      updateFab();
    else standFab();
  }
  // Stands the bar the user already has again. Geometry says where it stands, never
  // whether: the bar goes when a gesture puts it away or when its subject leaves the
  // document, and never because a scroll, a resize, a panel or a closed disclosure left
  // it no attachment. The default floating editor follows its passage out of view;
  // Resume writing reveals that same field. A bar with no usable room is withheld,
  // draft, anchor and all, and the next
  // placement that finds room stands it again.
  function standFab() {
    if (!(placement?.stands() ?? anchorStands(fabAnchor.value))) {
      letGoOfFab();
      return false;
    }
    if (!placement || placement.place()) return true;
    placement?.withhold();
    return false;
  }
  // The durable anchor names the authored coordinate an event can replay, while the
  // margin needs the rendered seat the gesture is visibly on. Those are deliberately
  // different for selected words inside a paragraph without an ID: the event names its
  // enclosing section, but the bar, margin row, note and reaction receipt all stand at
  // the resolved `place`, lifted out of a shadow root by `lightSeat`.
  //
  // Asked of any anchor rather than only of the current one: a draft the composer put
  // away carries its own anchor and nothing else in the runtime can say which block that
  // draft is about, which is what the route back to it has to travel to.
  const anchorTargetAt = (anchor) => {
    if (!anchor) return null;
    const found = responseTarget(anchor);
    if (!found) return null;
    if (!anchor.quote) return targetElement(found);
    return lightSeat(targetPlace(found));
  };
  const anchorTravelAt = (anchor) =>
    (anchor?.quote && targetRange(resolveAnchor(anchor))) || anchorTargetAt(anchor);
  const fabTargetAt = () => anchorTargetAt(fabAnchor.value);
  const fabReturnPlaces = () => returnPlaces(fabAnchor.value);

  // Opening Comment is an overlay gesture. Any visible part of its subject is
  // enough to open it: the physical presenter owns its attachment and measure, so
  // this asks only whether any of it is seen, not whether a landing would show more
  // (landing-scroll.js, `alreadyShown`, which a short subject cut by an edge is not).
  // Only a stale current location or a resumed draft whose subject is wholly out of view needs
  // travel (including revealing a closed ancestor), before placement measures it.
  function bringForward(addressable) {
    if (addressable && !seenRect(addressable, new Map()))
      scrollToElement(addressable, "instant");
  }

  // Every explicit target gesture ends here. The gesture has already resolved its stable
  // authored anchor; this command owns the one transition from that target into Comment.
  // Focusing the field drops any older browser selection, and an unsent draft follows the
  // deliberate move. Escape resolves the same structural parent for every entry route.
  function commentOnTarget({ anchor, element = null, point = null }) {
    cancelRender(selectionUpdate);
    selectionUpdate = null;
    bringForward(element);
    targetActivation = true;
    const selection = getSelection();
    if (selection?.rangeCount) selection.removeAllRanges();
    openComment(anchor, "", { carry: true, point });
    setTimeout(() => {
      targetActivation = false;
      // A browser command or touch handle can replace the visual target while its
      // selectionchange is held out above. Re-read once the explicit activation is
      // complete so that real later selection is not discarded with the focus collapse.
      selectionChanged();
    });
  }
  // Focusing text entry collapses a native page selection. Hold that browser-authored
  // selectionchange out of updateFab: the durable anchor is already captured, and letting
  // the collapse re-read it as no selection dismisses the field the user just entered.
  function focusFabComment() {
    if (!fabAnchor.value) return;
    cancelRender(selectionUpdate);
    selectionUpdate = null;
    const handoff = beginFabFocus();
    if (!composerOpen) {
      openComment(structuredClone(fabAnchor.value), "");
      return;
    }
    const anchor = structuredClone(fabAnchor.value);
    bringBackSurfaceOf(fabBar);
    showFab(anchor, { reveal: true });
    landFabFocus(handoff, anchor, () => sameAnchor(anchor, fabAnchor.value));
  }
  const fabOptionsAvailable = () =>
    Boolean(
      fabAnchor.value &&
      hasOtherResponses(fabAnchor.value) &&
      composer.responseOptionsAvailable(),
    );
  const showFabOptions = ({ reaction = false } = {}) =>
    composer.setResponseOptions(true, { focus: reaction ? "reaction" : "first" });
  // The response field follows any selection that stores page words. Even a one-character
  // quote carries its section and exact surrounding context, so the resolver can identify
  // its occurrence without guessing from quote length.
  const hasQuote = (anchor) => Boolean(anchor?.quote?.trim());
  const hasPageSelectionTarget = () => {
    const selection = pageSelection();
    const anchor = selection ? selectionAnchor(selection) : null;
    return hasQuote(anchor);
  };

  // Observed selection belongs to the browser until Comment is pressed. Native handles
  // and browser commands owe the page no pointer/key completion, and selectionchange
  // carries the same trusted notification for a script's endpoint write. It can offer
  // the current passage, but cannot authorize replacing a composer or its draft.
  // That menu can stand on either side of the words; never compete with it by raising
  // a second adjacent surface. The floating panel's page field offers the current
  // selection instead (floating-panel.js, `selectedWords`): its placeholder quotes the
  // words, and a press there comments on them. The press reads the selection again
  // where it still stands, as a source refresh that kept its native endpoints leaves
  // it, and otherwise takes the anchor read when it last settled, since a field taking
  // focus, or a tap on iOS, can drop the page's selection before the press ends.
  let offeredSelection = null;
  const offerSelection = (anchor) => {
    if (anchor === offeredSelection) return;
    offeredSelection = anchor;
    pageComment.offer(
      anchor
        ? { quote: anchor.quote, comment: () => commentOnOfferedSelection(anchor) }
        : null,
    );
  };
  function commentOnOfferedSelection(settled = offeredSelection) {
    const selection = anchoringIsReady() ? pageSelection() : null;
    const currentLocation = selection ? selectionAnchor(selection) : null;
    commentOnSelection(hasQuote(currentLocation) ? currentLocation : settled);
  }
  const commentOnSelection = (anchor) => {
    offerSelection(null);
    if (!hasQuote(anchor)) return;
    cancelRender(selectionUpdate);
    selectionUpdate = null;
    openComment(anchor, "");
  };

  function observeSelection() {
    const selection = anchoringIsReady() ? pageSelection() : null;
    const anchor = selection ? selectionAnchor(selection) : null;
    offerSelection(
      hasQuote(anchor) && !sameAnchor(anchor, fabAnchor.value) ? anchor : null,
    );
  }

  function updateFab() {
    if (!anchoringIsReady()) {
      offerSelection(null);
      putAwayFab();
      return;
    }
    const sel = pageSelection();
    const anchor = sel ? selectionAnchor(sel) : null;
    if (
      (coarsePointer.matches || !placement) &&
      hasQuote(anchor) &&
      (!fabHoldsCapturedPassage() || !sameAnchor(anchor, fabAnchor.value))
    ) {
      offerSelection(anchor);
      return;
    }
    offerSelection(null);
    if (hasQuote(anchor)) {
      // A fast keyboard action can capture this completed native selection before the
      // pointer gesture's queued update arrives. That later update is the same target,
      // not a request to reopen its Comment composer: reopening calls closeReactions
      // and used to collapse choices immediately after `e` exposed them.
      if (sameAnchor(anchor, fabAnchor.value)) {
        placement?.place();
        return;
      }
      // Selecting words is still the browser's gesture. Open Leaf's response field beside
      // them without moving focus into it, so the live Selection remains available to Copy
      // and the native context menu. An explicit Comment press uses the same field and
      // focuses it through focusFabComment below.
      openComment(anchor, "", { focus: false });
    } else if (fabAnchor.value?.quote && !fabHoldsCapturedPassage()) putAwayFab();
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
  // The shared retained intent asks whether a newer gesture has begun, including
  // Escape before the queued frame, which no press records, and the step outlives the
  // press that queued it.
  let selectionUpdate = null;
  let selectionIntent = null;
  const deferSelectionUpdate = (update) => {
    const mayUpdate = retainUserIntent();
    selectionIntent = mayUpdate;
    cancelRender(selectionUpdate);
    selectionUpdate = nextRender(() => {
      selectionUpdate = null;
      selectionIntent = null;
      if (!mayUpdate()) return;
      update();
    });
  };
  const scheduleSelectionUpdate = () => {
    // Keep this gesture's pending snap, but replace work a newer gesture retired.
    if (selectionUpdate && selectionIntent()) return;
    deferSelectionUpdate(updateFab);
  };
  // What the press under way began with and has done, kept against the press (focus.js,
  // `pressRecords`), so none of it outlasts the press: a release a widget stopped, or one
  // let go off the window, leaves nothing for the next selectionchange to read.
  //
  // - `selecting`: a primary-button press begun in page words owns their selection
  //   until it finishes it, at a finger's or pen's release or a mouse's compatibility
  //   mouseup. It is the press's retained intent (user-intent.js), since the press
  //   belongs to the content it began on and a newer input supersedes it: a bounded
  //   reading region can take native focus after pointerdown, and the previous focus is
  //   not its owner.
  // - `point`, `dragged`: where it began, and whether it has since moved off it.
  // - `range`, `backward`: what the drag has held inside the document
  //   (`rememberPointerSelection`).
  // - `claimed`: a widget turned the press into a different gesture after pointerdown.
  //   `preventDefault` on its bubbling pointermove is the shared claim boundary: the
  //   selection surface must not restore the range it captured before that claim.
  // - `words`: the page's own words the press began with (the click door below).
  // - `action`: a press on the response surface's own controls, or on chrome while a
  //   passage is offered, which holds selectionchange out until the press is over.
  /**
   * @typedef {{
   *   selecting: (() => boolean) | null,
   *   point: { x: number, y: number },
   *   dragged: boolean,
   *   range: Range | null,
   *   backward: boolean,
   *   claimed: boolean,
   *   words: string,
   *   action: boolean,
   * }} PagePress
   */
  /** @type {{ keep: (event: PointerEvent, value: PagePress) => PagePress, kept: () => PagePress | null }} */
  const pagePresses = pressRecords();
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
  const endFabFocus = (handoff = null) => {
    if (handoff && handoff !== fabFocusHandoff) return;
    fabInputTakingFocus = false;
    fabFocusHandoff = null;
  };
  // Every handoff lands here. It is marked at once and lands a frame or more later, and
  // the user owns the page for the whole of that gap: a passage selected when it lands
  // that this composer did not open on is theirs, taken since, and focusing the field
  // would collapse it before anything could read it. Standing down releases the mark with
  // it, so the collapse the mark holds out cannot outlive the focus it was holding it for.
  function landFabFocus(handoff, anchor, stands) {
    handoff.intent = restrictUserIntent(
      handoff.intent,
      () => composerOpen && stands() && sameAnchor(anchor, fabAnchor.value),
    );
    void fabPositioned().then((positioned) => {
      if (handoff !== fabFocusHandoff) return;
      const taken = pageSelection();
      const words = taken ? selectionAnchor(taken) : null;
      const landed =
        positioned &&
        (!hasQuote(words) || sameAnchor(words, anchor)) &&
        handoff.intent.handoff(() => {
          focusDestination(fabInput, "move");
          if (fabInlineOutlet) scrollIntoView(fabInput, { block: "nearest" });
        });
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
      !fabAnchor.value ||
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
    return composer.openComposer(anchor, text, options);
  }
  function fabHoldsCapturedPassage() {
    return (
      fabInputTakingFocus ||
      fabBar.contains(fabFocused()) ||
      reactionContextContains(fabFocused())
    );
  }
  // Wired once the chrome is mounted: the box is selection.js's.
  function wireFabInput() {
    fabInput.addEventListener("focus", () => {
      cancelRender(selectionUpdate);
      selectionUpdate = null;
      offerSelection(null);
      fabInputTakingFocus = true;
    });
    fabInput.addEventListener("blur", () => {
      fabInputTakingFocus = false;
    });
  }
  // Whether the page's own words stood selected when the keys were last painted.
  // Escape owns the selection from its first glyph. Paint only that crossing, including
  // a selection begun in a label whose pointer press is not a page-word gesture; growing
  // a selection that already stands needs no repaint on each drag frame.
  let selectionStood = false;
  const reflectSelection = () => {
    const stands = Boolean(pageSelection());
    if (stands === selectionStood) return;
    selectionStood = stands;
    repaint();
  };
  // What this drag has had inside the document, kept against a release that ends holding
  // something else. Only while both ends are still in it: `pageSelection` answers for the
  // end the press began at, which stays in the page for the whole of a drag that leaves it,
  // so without the far end this remembered the runaway range itself and had nothing to put
  // back.
  const rememberPointerSelection = (press) => {
    const selection = pageSelection();
    if (!selection || leftThePage(selection)) return;
    const anchor = selectionAnchor(selection);
    if (hasQuote(anchor)) {
      press.range = pageRange(selection).cloneRange();
      press.backward = selectionBackward(selection);
    }
  };

  const finishPointerSelection = (ev) => {
    if (drawModeActive()) return;
    const press = pagePresses.kept();
    if (!press?.selecting) return;
    // Opening or acting in chrome is a route away from the page, not a new selection
    // gesture. Keep the native touch passage verbatim while focus moves
    // through the floating panel, its popovers, and their controls.
    if (offeredSelection && inChrome(ev.composedPath()[0])) {
      press.selecting = null;
      return;
    }
    // A mouse pointer is followed by the compatibility mouseup below, which performs the
    // sentence snap before opening the field. Opening from pointerup first would focus the
    // field and collapse the still-unsnapped Selection before mouseup can finish it.
    // Touch/pen and cancellation owe us no compatibility mouse event, so they keep this
    // direct route.
    if (ev.type === "pointerup" && ev.pointerType === "mouse") return;
    const selected = press.selecting() && !press.claimed;
    press.selecting = null;
    if (!selected) return;
    rememberSelection();
    scheduleSelectionUpdate();
  };
  // A press on the response surface's controls holds selectionchange out until it is
  // over, after the compatibility events its release owes (focus.js, `pressing`), so the
  // focus collapse it causes is not read as the user's. Native selectionchange may have
  // coalesced that collapse and a later passage meanwhile, so the live selection is read
  // as the press goes, through the same guards as a native notification.
  const rereadAfterAction = () =>
    pagePresses.kept()?.action ? selectionChanged : null;

  // Touch handles and browser selection commands do not owe the page a mouseup or keyup.
  // During a pointer drag, the completed gesture below remains the one that snaps and
  // places the passage; presses on the action surface must not retract their own target.

  // Selections made from the keyboard (shift-arrows, ⌘A) deserve the same response bar. Typing in
  // a box never does, whatever is selected elsewhere.

  // The response surface getting out of the way of a press away from it (focus.js,
  // `onPressAway`), which is a fact about the press rather than about who receives it, so
  // a press the aim or a design mode claims from the page puts it away too. A press on
  // the visual the bar stands for keeps it, as does a stroke in a draw mode or a capture's
  // drag, which go on into the draft the composer holds. A native modal owns its press,
  // the command reference's included, which goes by its own light dismissal
  // (`closedby`), and the composer behind it stays inert.
  function pressedAway(path) {
    if (
      drawModeActive() ||
      captureActive() ||
      nativeLayers().some((layer) => layer.kind === "modal")
    )
      return false;
    // The node pressed, not the widget host a shadow tree retargets it to: core controls
    // seated in a widget surface stay inside their own composer or reaction layer.
    const [target] = path;
    // A release outside the document can begin its path at window, which has no
    // visual place to compare with the open composer.
    const visual = target?.nodeType === Node.ELEMENT_NODE ? visualAt(target) : null;
    const sameVisual =
      visual &&
      !fabAnchor.value?.quote &&
      fabAnchor.value?.section === visual.id &&
      fabAnchor.value?.visual === visual.part?.id;
    return (
      !sameVisual &&
      !target.closest?.(".lf-fab-bar, .lf-react-surface, .lf-composer") &&
      !reactionContextContains(target)
    );
  }
  // The press goes away as it completes, after its own focus change has placed the user
  // where it landed, so the bar lets go only of a user it still holds: one who pressed
  // its subject, or anything else that takes focus, stays there.
  function standDown() {
    if (composerOpen) composer.hideComposer();
    if (fabAnchor.value)
      closeLayer(() => showFab(null), fabBar.contains(fabFocused()) && letGo);
    // The armed react press goes with the bar it was armed on.
    setReact(false);
  }

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

  const fabAnchorAt = () => fabAnchor.value;
  const fabFrameAt = () => placement?.frame() ?? null;
  const fabPointAt = () => fabPointIn(fabTargetAt());

  // The composer this bar's field belongs to, built once every surface command it reads
  // exists and before the commands below that read it. The two answer each other at every
  // gesture, so one owner builds both and boot wires neither to the other.
  const composer = createSelectionComposer({
    setReact,
    reactionTokens,
    reactionAvailable,
    designModeActive,
    openPageThread,
    anchorTravelAt,
    bringForward,
    fabAnchorAt,
    fabPointAt,
    fabFrameAt,
    fabPositioned,
    beginFabFocus,
    endFabFocus,
    landFabFocus,
    showFab,
    letGoOfFab,
    createComment,
    landSent,
    refreshThread,
    wireInput,
    drawingEdits,
  });

  function selectionChanged() {
    const automatic = programmaticSelection(getSelection());
    const press = pagePresses.kept();
    if (press?.selecting?.()) {
      rememberPointerSelection(press);
      if (coarsePointer.matches && !press.claimed) rememberSelection();
      reflectSelection();
      return;
    }
    // Focus and action handoffs own the captured target while the browser collapses
    // its selection. Outside those handoffs, observe the browser's live passage;
    // only the completed page gesture above/below may replace the composer.
    if (takesLetters(focused())) {
      offerSelection(null);
      return;
    }
    if (press?.action || targetActivation) return;
    const selection = pageSelection();
    if (coarsePointer.matches && selection && !automatic) rememberSelection(selection);
    observeSelection();
    // A bare selected passage only stands while the browser still holds it.
    // Focusing Comment captures that passage, and a written draft keeps it even
    // after focus moves elsewhere; neither belongs to the native selection now.
    if (
      !selection &&
      fabAnchor.value?.quote &&
      !fabHoldsCapturedPassage() &&
      !composer.composerHolds()
    )
      putAwayFab();
    reflectSelection();
  }

  function mount() {
    composer.mount();
    placement?.mount();
    coarsePointer.addEventListener("change", observeSelection);
    document.addEventListener(
      "pointerdown",
      (ev) => {
        if (drawModeActive()) return;
        // Read here, ahead of the browser's own collapse, so the first crossing this press
        // makes is measured against what the line already says rather than against nothing,
        // and what the press took is told from what it merely landed in.
        const stood = pageSelection();
        selectionStood = Boolean(stood);
        // A second contact is no part of the press under way.
        if (!ev.isPrimary) return;
        // Admission reads the press's origin across widget shadow roots. The host
        // also contains runtime editors and controls, which are not page prose.
        const target = ev.composedPath()[0];
        const selecting = ev.button === 0 && pageWords(target);
        const press = pagePresses.keep(ev, {
          selecting: selecting ? retainUserIntent({ source: target }) : null,
          point: { x: ev.clientX, y: ev.clientY },
          dragged: false,
          range: null,
          backward: false,
          claimed: false,
          words: stood ? stood.toString() : "",
          action:
            (offeredSelection && inChrome(target)) ||
            Boolean(
              /** @type {Partial<Element>} */ (target).closest?.(
                ".lf-react-surface, .lf-composer",
              ),
            ),
        });
        if (selecting && stood && pageRange(stood).intersectsNode(target))
          rememberPointerSelection(press);
      },
      true,
    );
    onPress(() => rereadAfterAction);
    document.addEventListener("pointermove", (ev) => {
      if (drawModeActive()) return;
      const press = pagePresses.kept();
      if (!press?.selecting) return;
      if (ev.defaultPrevented) {
        press.claimed = true;
        return;
      }
      press.dragged ||=
        Math.hypot(ev.clientX - press.point.x, ev.clientY - press.point.y) > 3;
    });
    document.addEventListener("touchstart", (ev) => {
      // The native touch event follows pointerdown and is the same selecting press.
      // Capture its input generation at that producer, before handles can adjust it.
      const press = pagePresses.kept();
      if (press?.selecting)
        press.selecting = retainUserIntent({ source: ev.composedPath()[0] });
    });
    document.addEventListener("pointerup", finishPointerSelection);
    document.addEventListener("pointercancel", finishPointerSelection);
    document.addEventListener("selectionchange", selectionChanged);
    document.addEventListener("mouseup", (ev) => {
      if (drawModeActive()) return;
      const press = pagePresses.kept();
      // Only a gesture begun in page words owns their selection. A release from
      // chrome (such as resizing a panel) must not snap an existing passage.
      if (!press?.selecting) return;
      const selectedOnPage = press.selecting();
      press.selecting = null;
      if (press.claimed || press.action || !selectedOnPage) return;
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
      const escaped = press.dragged && leftThePage();
      const completed =
        press.dragged && (escaped || !hasQuote(selected)) ? press.range : null;
      const selectedByGesture =
        press.dragged || ev.detail > 1 || selection?.toString() !== press.words;
      // Keep the user's completed selection before its deferred snap. Escape or a
      // next gesture can legitimately arrive before that frame; it must still have
      // selected a passage. The completed snap below refines that same gesture.
      if (selectedByGesture && hasQuote(selected) && !escaped) rememberSelection();
      deferSelectionUpdate(() => {
        if (completed) {
          const head = [completed.startContainer, completed.startOffset];
          const tail = [completed.endContainer, completed.endOffset];
          selectEnds(...(press.backward ? [tail, head] : [head, tail]));
        } else if (escaped) {
          // A drag that crossed out before it covered anything has no passage to offer and
          // no words to put back. The browser's own selection stays where it is — the user
          // can still copy it — and the response surface says nothing about it.
          putAwayFab();
          return;
        }
        if (ev.button === 0) snapSelection();
        if (selectedByGesture) rememberSelection();
        updateFab();
      });
    });
    document.addEventListener("keyup", (ev) => {
      if (dismissedSelectionKeyup) {
        dismissedSelectionKeyup = false;
        if (ev.key === "Escape") return;
      }
      if (isReactArmed()) return;
      const target = ev.composedPath()[0];
      if (takesLetters(target) || inChrome(target)) return;
      if (!pageWords(target) && !pageSelection()) return;
      if ((ev.shiftKey && CARET_KEYS.includes(ev.key)) || selectsAll(ev)) {
        rememberSelection();
        scheduleSelectionUpdate();
      } else observeSelection();
    });
    onPressAway(pressedAway, standDown);
    document.addEventListener("click", (ev) => {
      if (drawModeActive()) return;
      const target = ev.composedPath()[0];
      if (!pageWords(target)) return;
      // A press that ends holding words it did not begin with took them, and is that
      // selection's mouseup rather than a click on whatever lies under it: the user was
      // reaching for the words, and the 💬 is already up on them (updateFab, on the same
      // mouseup). The same complaint `offer` answers for a press on a control
      // (reachedForWords), and it governs the whole of
      // what a click on prose means — the block design mode comments on, and the thread a
      // mark opens. Marked words are where it showed: a gesture inside one travelled to its
      // thread, and with Threads open the reply box it landed in collapsed the selection
      // the user had just made, so the words and the 💬 went with it.
      //
      // Asked of what this press changed rather than of the current selection those two
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
      const press = pagePresses.kept();
      if (words && words.toString() !== (press?.words ?? "")) return;
      // A plain click comments on the block it landed in. Read where it landed rather than
      // at a widget host, since a Leaf surface the widget seats in its shadow tree answers
      // for itself (design.js).
      if (designModeActive()) {
        const design = designTarget(target);
        if (design) openOnDesign(design);
        return;
      }
      // A painted owner may contain working controls or editing regions. Their
      // native click keeps its meaning even when an annotation covers the owner.
      if (closestAcross(target, WORKS)) return;
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
      const point = pressIsKeyboardActivation(ev)
        ? { x: ev.clientX, y: ev.clientY }
        : pointerAt();
      const threadId = markAt?.(point.x, point.y);
      if (threadId)
        return void openPageThread(threadId, { part: "thread", travel: false });
    });
    wireFabInput();
  }

  // ---------- where "comment" goes ----------
  // The thread the user is in, and the box it is written in. Three
  // containers hold one and the user can enter any of them: the panel's thread, a
  // thread seated on the page (x-thread-seat), and each thread inside that seat.
  // They are one question — a press meaning "say something about this" belongs to the box
  // of the thread the user is already in — so they get one reading rather than a
  // rule for the panel and a different one for the page.
  //
  // One of the three is in the chrome, which is not the exception it looks like: page scope
  // already crosses there. A page key that takes the user somewhere owes them an answer
  // once they are there.
  //
  // One live aim and then one climb, rather than four cases. A selection outranks
  // position; a captured target does too until the user is elsewhere. The draft
  // keeps its words independently of which target the next press names. Below the
  // aim, the answer walks
  // outward from where they are — the nearest thread's box, then the nearest
  // addressable element, then the page, which is what is left when they are
  // nowhere in it. An element anchor answers in its own word (a figure, a card), the way
  // the panel names one. Every destination is a box to write in and says so in the same
  // sentence; the word is what varies.
  const commenting = (word) => ({
    title: `comment on the ${word}`,
  });
  function commentDestination() {
    // The panel's field quotes the selected words, and a press there does what c does,
    // so the field carries c's badge.
    if (offeredSelection)
      return {
        ...commenting("selection"),
        box: pageComment.box,
        go: commentOnOfferedSelection,
      };
    const here = currentTarget();
    const anchor = fabAnchorAt();
    // The thread drawn with the user's place (`threadHere`), such as the card beside it,
    // is one place with it, so its reply box is where c writes, even where the thread is
    // about a block enclosing what they stand on: the box they see is the one c names,
    // rather than a new thread on the obligation the card stands beside, which closed the
    // card they were reading. That thread starts from `s`, which chooses an element.
    // An undrawn thread continues only where it is about what they stand on: its target
    // lies within the element they stand at — the obligation holding focus, answered or
    // not, else the element itself — as an obligation's options group does when the user
    // holds one of its marks. So with no card shown, an element inside a commented block
    // takes a thread of its own, and a selection still starts one on its words.

    const inline = threadHere();
    const threadId = threadAtCurrentLocation();
    const replyId = replyThreadAtCurrentLocation();
    const target = threadId && threadTarget(threadId);
    const inlineBox = inline && threadInput(inline);
    const said =
      currentLocationThread() ?? (inlineBox ? { held: inline, box: inlineBox } : null);
    const subject =
      threadId &&
      (!here || (target && under(target, heldObligation() ?? here.element)));
    const replySubject = subject && replyId;
    // A captured passage outranks the focus it preceded, but a kept draft is not a
    // current target. Read both page and thread location before choosing the aim.
    // After the user lands elsewhere, Comment names that new place;
    // commentOnTarget carries the old words without replacing a destination's
    // independent draft.
    if (
      anchor &&
      (pageSelection() ||
        fabHoldsCapturedPassage() ||
        (!said && !subject && (!here || here.element === fabTargetAt())))
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
          composer.carryComposerToReply(replyDraftContext(said.box));
          landIn(said);
        },
      };
    if (replySubject)
      return {
        ...commenting("thread"),
        box: null,
        go: async () => {
          const destination = await openPageThread(threadId, {
            part: "reply",
            travel: false,
          });
          if (!destination) return;
          composer.carryComposerToReply(replyDraftContext(destination));
          landIn({ box: destination });
        },
      };
    if (here)
      return {
        ...commenting(here.anchor.datum ? "item" : addressableWord(here.element)),
        box: fabInput,
        go: () => commentOnTarget(here),
      };
    // The page's own box is the floating panel's field.
    return { ...commenting("page"), box: pageComment.box, go: pageComment.open };
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
  // being in gets its own reply box, the item they are in gets the box
  // belonging to it, and otherwise the page's general box, the floating panel's field. c
  // names and focuses the box directly; g T independently names the list. Never the panel's collapse: c doubled as the toggle once, so with the panel
  // standing open the key that promised “comment” answered “close”. Backing out is
  // whatever the box is standing in.
  //
  // Current location outranks the page; a live selection or a newly captured target outranks
  // current location. The draft stored on an earlier target supplies words, not that priority.
  pageCommand({
    id: "comment.create",
    touch: false,
    keys: ["c"],
    // The surfaces name the destination in front of the user rather than the capability:
    // "Comment" covered all four and so promised none of them.
    title: () => commentDestination().title,
    // It goes to the destination it names, revealing a box off screen.
    travels: true,
    // A selection made before the anchor pass has run can't be quoted yet, and commenting
    // on the page instead is not what the user asked for — so the press waits, and the
    // row's own liveness is where that is said rather than a refusal inside run that no
    // surface can see.
    //
    when: () => anchoringIsReady() || !pageSelection(),
    run: () => {
      // Activation reads the current native selection directly. Painting its offer
      // first would displace the reading controls only to restore them in this press.
      const selection = pageSelection();
      const anchor = selection ? selectionAnchor(selection) : null;
      if (hasQuote(anchor)) {
        commentOnSelection(anchor);
        return;
      }
      updateFab();
      commentDestination().go();
    },
  });

  // Tab opens responses from the editor, while attachments keep native traversal.
  // Project this alongside the input owner's submit scope rather than replacing it.
  const composerOptions = commandScope("In the comment box", [
    {
      id: "comment.options",
      keys: () => (composer.responseOptionsAreOpen() ? [] : ["Tab"]),
      title: "other responses",
      control: fabOptionsTrigger,
      when: fabOptionsAvailable,
      run: () =>
        composer.setResponseOptions(!composer.responseOptionsAreOpen(), {
          focus: "first",
        }),
    },
  ]);
  projectCommandScope(fabInput, composerOptions, composerOptions);

  // The composer's own rung is its own scope rather than the box's, because the box may not
  // have focus — the user clicked away and the composer still stands, holding their draft.
  pageScope("composer", {
    title: "In the comment box",
    at: () => composerOpen && !placement?.withheld(),
    rows: [
      {
        id: "composer.close",
        touch: false,
        keys: ["Escape"],
        title: () => (composer.composerHolds() ? "close — draft kept" : "close"),
        when: () => !composer.responseOptionsAreOpen(),
        run: () => dismissFab(),
      },
    ],
  });

  // The first step of the page's Escape ladder: a selection or a captured target is the
  // innermost thing the user is holding, and letting it go is one press.
  pageRung("selection", () =>
    pageSelection() || (fabAnchorAt() && !placement?.withheld())
      ? {
          title: "unselect",
          out: dismissFab,
        }
      : null,
  );

  return {
    pendingComposer: composer.pendingComposer,
    openDraft: composer.openDraft,
    openComposer: composer.openComposer,
    openComposerWithMedia: composer.openComposerWithMedia,
    hideComposer: composer.hideComposer,
    syncResponseOptions: composer.syncResponseOptions,
    draftKey: composer.draftKey,
    draftDrawing: composer.draftDrawing,
    heldDrawings: composer.heldDrawings,
    watchHeldDrawings: composer.watchHeldDrawings,
    setDraftDrawing: composer.setDraftDrawing,
    commentHint,
    fabPositioned,
    showFab,
    refreshFab,
    fabTargetAt,
    fabReturnPlaces,
    commentOnTarget,
    showFabOptions,
    hasPageSelectionTarget,
    updateFab,
    fabAnchorAt,
    seatFab,
    restoreFab,
    finishPlacement,
    fabInlineOutlet: () => fabInlineOutlet,
    mount,
  };
}
