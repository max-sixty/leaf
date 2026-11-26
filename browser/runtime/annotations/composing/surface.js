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
   until the draft has words (annotations/composing/selection.js). An explicit addressable target
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

   `showFab` places the bar; `openComposer` (annotations/composing/selection.js) binds its field to
   the durable draft and takes the focus decision. Every explicit item and visual route
   passes its resolved anchor to `commentOnTarget`, which focuses the field on the
   target's own draft; an earlier draft stays with its passage. Automatic passage selection opens that passage's own
   durable draft without moving focus. Submitted words still in flight remain owned by
   their original anchor, while a later target starts clean and keeps focus.

   Where `c` would open the box beside a target the user can see, the box already stands
   there, empty, with the key that opens it (`restFab`), so where `c` goes shows before
   the press, as it does for a selection. The user chose this, with
   the key in the panel's row and `c` leaving focus scrolled out of sight
   (`focusedPlace`), accepting a box in the
   margin at every stop of a walk, every Tab and every press that leaves focus on a
   control. With no room in the margin, the box waits for the press (floating-response.js).
   They passed over `c` following only a ringed control, which turned their
   presses inside a question into page comments, and writing about a target in the
   panel's field, which moved every box beside a target. The box at rest is the bar in
   its placement, in the frame the field will have, so the press moves nothing; only its
   face stands (`.lf-fab-rest`), with no anchor or composer behind it. So it holds no
   revision back, takes no Escape step, closes no thread card and builds no editor, and
   it goes with the focus that raised it. It goes in the frame a scroll takes that focus
   out of sight, though its placement would keep it on screen a little longer, carried
   up by the target's foot (comment-placement.js, `scroll-held-in`). From that frame `c`
   opens the panel's field, and a box still on screen would show a key that no longer
   opens it.

   Boot may supply an actual physical placement. The default floating presentation
   owns collision geometry and off-flow reveals in floating-response.js. This owner
   does not import or instantiate it; a page renderer can seat the native editor
   through the same cohort without loading that presentation.

   Boot supplies travel, delivery and mode commands to one surface owner, which builds
   the selection composer (annotations/composing/selection.js) from them and its own bar commands.
   Its constructor binds no document listeners; mount installs the selection gesture
   lifecycle and field-focus tracking after all capabilities have been composed. */
import {
  pageRange,
  programmaticSelection,
  selectEnds,
  selectionBackward,
} from "../../dom/native-selection.js";
import { html, render } from "/vendor/lit.js";
import { signal } from "/vendor/signals-core.js";
import { addressableWord } from "../../lib/element-word.js";
import { COMMENT_HINT } from "../../base/voice.js";
import {
  addressedFocus,
  anchoringIsReady,
  lightSeat,
  rangeHoldsWords,
  resolveAnchor,
  sectionOf,
  visualAt,
} from "../../readings/anchor-resolution.js";
import { sameAnchor } from "../../base/anchor-coordinate.js";
import { threadNamed } from "../../records/thread/state.js";
import { CARET_KEYS, selectsAll, WORKS } from "../../dom/control-selectors.js";
import { bringBackSurfaceOf } from "../../readings/off-flow.js";
import { covered, outOfWindow, placeBox, seenRect } from "../../dom/geometry.js";
import { scrollIntoView } from "../../readings/landing-scroll.js";
import { landGlides, stopGlide } from "../../dom/scrolling.js";
import { carriersOf } from "../../readings/scroll-containers.js";
import { cancelRender, nextRender } from "../../lib/frame-pass.js";
import {
  targetElement,
  targetPlace,
  targetSegments,
} from "../../readings/resolved-target.js";
import {
  composerOpen,
  createSelectionComposer,
  fabBar,
  fabInput,
  fabOptionsTrigger,
  fabRest,
  pendingAbout,
} from "./selection.js";

import { paintBarReactions, reactionAvailable } from "../reactions.js";
import { threadInput, currentLocationThread } from "../../records/thread/landing.js";
import { advertisesKeys } from "../../dom/keyboard/bindings.js";
import { commandBindingsNow, commandKeysNow } from "../../dom/keyboard/control-keys.js";
import { pageCommand, pageRung, pageScope } from "../../dom/keyboard/register.js";

import {
  elementById,
  pageWords,
  passageStart,
  rangeOf,
} from "../../readings/passages.js";
import {
  leftThePage,
  pageSelection,
  selectionAnchor,
  snapSelection,
} from "./capture.js";
import { coveredFrame, takesNoWords } from "./input.js";
import { repaint } from "../../dom/repaint.js";
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
} from "../../dom/focus.js";
import { commandScope, projectCommandScope } from "../../dom/keyboard/scopes.js";
import { under, upFrom, closestAcross } from "../../lib/shadow-tree.js";
import { nativeLayers } from "../../dom/keyboard/layer-stack.js";
import { heldObligation } from "../../records/current-target.js";
import { focusPlace } from "../../readings/user-place.js";

import {
  coarsePointer,
  eventSource,
  pointerAt,
  pressIsKeyboardActivation,
} from "../../base/pointer.js";
import { anchorLabel, draftLine, draftWords } from "../../records/thread/messages.js";
import { draftsReading } from "../../records/drafts.js";
import { seatOf } from "../../state/thread/model.js";

import { livePoint } from "../../readings/pointed-place.js";
import { keeps } from "../../lib/keeps.js";
import { move } from "../../dom/dom-move.js";
import { retainUserIntent, restrictUserIntent } from "../../dom/user-intent.js";
import { inChrome } from "../../base/ui-marks.js";

/** @typedef {{intent: ReturnType<typeof retainUserIntent>}} FabFocusHandoff */

/** The placement owner's live reading of the composition surface.
 * @typedef {Object} ResponseState
 * @property {NonNullable<import("../../../types/contract.js").EventMap["comment"]["anchor"]> | null} anchor
 * @property {boolean} open
 * @property {boolean} rests
 * @property {boolean} floating
 * @property {Element | null} target
 * @property {ReturnType<typeof resolveAnchor>} resolved
 * @property {boolean} captured
 * @property {(target: Element | null) => Element | null} pointIn
 * @property {() => {field: HTMLElement, frame: HTMLElement}} composition
 */

/** @typedef {import("./selection.js").Anchor} Anchor
 * @typedef {import("./selection.js").ComposerOptions} ComposerOptions
 * @typedef {ReturnType<typeof import("../../records/thread/destination.js").createThreadDestinations>} ThreadDestinations
 * @typedef {Pick<ComposerOptions, "reactionEmoji" | "setReact" | "designModeActive" | "openPageThread" | "createComment" | "landSent" | "refreshThread" | "wireInput" | "drawingEdits"> & {
 * rememberSelection: ReturnType<typeof import("./capture.js").createPassageSelection>["remember"],
 * landIn: typeof import("../../records/thread/landing.js").landIn,
 * threadHere: ThreadDestinations["threadHere"], threadAtCurrentLocation: ThreadDestinations["threadAtCurrentLocation"], threadTarget: ThreadDestinations["threadTarget"],
 * currentTarget: ReturnType<typeof import("./current-target.js").createCurrentTarget>,
 * markAt?: ((x: number, y: number) => string | null) | undefined,
 * scrollToElement: ReturnType<typeof import("../../features/anchor-travel.js").createAnchorTravel>["scrollToElement"],
 * scrollToPassage: ReturnType<typeof import("../../features/anchor-travel.js").createAnchorTravel>["scrollToPassage"],
 * scrollToRange: ReturnType<typeof import("../../features/anchor-travel.js").createAnchorTravel>["scrollToRange"],
 * visualActionAnchor: ReturnType<typeof import("../anchor-controls.js").createAnchorControls>["visualActionAnchor"],
 * designTarget: ReturnType<typeof import("../design.js").createDesignMode>["target"], openOnDesign: ReturnType<typeof import("../design.js").createDesignMode>["open"],
 * isReactArmed: () => boolean, reactionContextContains: (element: Element | null) => boolean,
 * drawModeActive: () => boolean, captureActive: () => boolean,
 * dismissThreadView: () => unknown, pageComment: {box: HTMLElement, open: () => unknown, offer: (passage: {quote: string, comment: () => unknown} | null) => unknown},
 * responseHome: HTMLElement, revealResponseHome?: (() => unknown) | null,
 * createPlacement?: typeof import("../annotation-overlay/composing/floating-response.js").createFloatingResponsePlacement | null | undefined
 * }} ResponseOptions
 */
/** @param {ResponseOptions} options */
export function createResponseSurface({
  rememberSelection,
  landIn,
  threadHere,
  threadAtCurrentLocation,
  threadTarget,
  currentTarget,
  markAt,
  scrollToElement,
  scrollToPassage,
  scrollToRange,
  visualActionAnchor,
  designModeActive,
  designTarget,
  openOnDesign,
  isReactArmed,
  reactionContextContains,
  reactionEmoji,
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
  /** @param {Anchor | null} anchor */
  const hasOtherResponses = (anchor) =>
    reactionEmoji().length > 0 || Boolean(anchor?.quote && !designModeActive());

  // ---------- selection → comment ----------
  // What the comment box's bar answers, a signal since its rows' availability reads it
  // (dom/keyboard/scopes.js).
  /** @type {import("@preact/signals-core").Signal<Anchor | null>} */
  const fabAnchor = signal(null);
  // The target `c` would open the box beside, while the box rests there (`restFab`).
  /** @type {ReturnType<ResponseOptions["currentTarget"]>} */
  let resting = null;
  const standingAnchor = () => fabAnchor.value ?? resting?.anchor ?? null;
  // The row inside the target the gesture that opened this bar pointed at, which the bar
  // stands level with (readings/pointed-place.js).
  /** @type {Element | null} */
  let fabPoint = null;
  /** @type {ReturnType<NonNullable<ResponseOptions["createPlacement"]>> | null} */
  let activePlacement = null;
  /** @type {Element | null} */
  let fabInlineOutlet = null;
  /** @type {((ready: boolean) => void)[]} */
  let fabPositionWaiters = [];
  const fabFocused = () => focused(fabInlineOutlet ? null : document);

  const fabDrawn = () => drawn(composerOpen ? fabInput : fabBar);
  /** @param {boolean} positioned */
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
  /** @returns {Promise<boolean>} */
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
    placement?.stop({ reset });
    if (reset && !repositioning) answerFabPosition(false);
  };
  // Reparenting the canonical response bar is presentation, not a composer transition,
  // so the user's place in it, caret and composition included, crosses light and shadow
  // DOM moves with it (`move`).
  /** @param {Element} parent */
  function moveFab(parent) {
    if (fabBar.parentElement !== parent) move(parent, fabBar, null);
  }

  // Whether the bar stands inline in an outlet or floats, said as the one attribute the
  // stylesheets read. Floating, the selected presentation decides whether it shows
  // (`data-lf-placement`, `data-lf-withheld`); core writes no visibility of its own.
  // The label of the hold the outlet the bar stands in offers (its `lfHold`,
  // records/thread/surfaces.js), a signal since the field draws its second send from it. A
  // comment holds the widget it is about and nothing in it, so the hold is offered only
  // on the widget's own target.
  /** @type {import("@preact/signals-core").Signal<string | null>} */
  const fabHold = signal(null);
  const fabHoldAt = () =>
    seatOf({ anchor: fabAnchor.value, about: pendingAbout }) ? fabHold.value : null;
  const presentFab = () => {
    keeps(fabBar, "data-lf-presentation", fabInlineOutlet ? "inline" : null);
    fabHold.value = fabInlineOutlet?.lfHold ?? null;
  };

  // An outlet's geometry is judged only as the editor moves into it, as a floating
  // bar's room is judged only as it opens (`showFab`). A seat the chrome covers, as
  // under the room a panel takes, cannot take the user even where it paints, so the
  // editor stays at its home instead. The seat is judged, not the editor moved into it,
  // which measures no width until the outlet renders it; a boxless outlet is judged by
  // the box that lays out what it holds, by the same rule. So an outlet that shows only
  // while it holds something still lays out where its editor will stand.
  //
  // A seat merely scrolled out of the window can take an editor as it opens, as a
  // file's comment below a long hunk: the opening's landing brings it in
  // (`landFabFocus`), and it stays beside its subject. An editor the user already sees
  // stays where it is rather than move to such a seat. The move itself scrolls the page
  // to the editor, and a resize's restore of the reader's place (features/version.js,
  // `restoreShifted`) can then scroll back to the place read while the editor stood
  // outside the page, which leaves the editor and the draft in it below the window, as
  // when a window widened from a phone's width offers a widget's outlet as the seat of
  // the box floating beside its datum.
  //
  // The outlet the editor stands in keeps it wherever news, a scroll or a resize
  // carries the outlet, partly under the panel's row included. Sending the editor
  // home would move the field the user is typing in (browser/AGENTS.md, "The page
  // holds still under the user's aim"), and their next keystroke lands the field
  // clear of the row (annotations/editor-view.js). Judging that outlet again could also loop: the
  // outlet grows as it takes the editor, so a cover that crossed none of the empty
  // outlet can cross the outlet holding it. The editor would go home, and the emptied
  // outlet would take it back, at every commit. Only admission, below, refuses the
  // outlet the editor stands in, once that outlet no longer draws it.
  /** @param {Element} outlet */
  function seatFab(outlet) {
    if (!(outlet instanceof Element) || !fabAnchor.value || !composerOpen) return false;
    if (fabBar.parentNode !== outlet) {
      /** @type {Element | null} */
      let seat = outlet;
      while (seat && !(seat.getBoundingClientRect().width > 0)) seat = upFrom(seat);
      const box = seat && placeBox(seat);
      if (seat && box && covered(box, seat)) return false;
      if (box && !fabFocusHandoff && outOfWindow(box) && seenRect(fabInput, new Map()))
        return false;
    }
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
    if (activePlacement) stopFabPositioning({ reset: true, repositioning: true });
    activePlacement = null;
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
    activePlacement = placement;
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
  /** @param {Anchor} anchor @param {ReturnType<typeof resolveAnchor>} found */
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
  /** @param {Anchor | null} anchor */
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
      ? (found ?? (anchor.section ? resolveAnchor({ section: anchor.section }) : null))
      : null;
  };
  /** @param {Anchor | null} anchor */
  const anchorStands = (anchor) => Boolean(responseTarget(anchor));
  /** @param {Element | null} target */
  const fabPointIn = (target) =>
    fabAnchor.value?.quote ? null : livePoint(target, fabPoint);
  const placement =
    createPlacement?.({
      bar: fabBar,
      input: fabInput,
      response: {
        get anchor() {
          return standingAnchor();
        },
        get open() {
          return composerOpen;
        },
        get rests() {
          return Boolean(resting);
        },
        get floating() {
          return Boolean(activePlacement);
        },
        get target() {
          return anchorTargetAt(standingAnchor());
        },
        get resolved() {
          return responseTarget(standingAnchor());
        },
        get captured() {
          return fabHoldsCapturedPassage();
        },
        pointIn: fabPointIn,
        composition: () => composer.composition(),
      },
      positioned: answerFabPosition,
      dismiss: () => letGoOfFab(),
      scrollToElement,
      scrollToPassage,
      scrollToRange,
    }) ?? null;
  // An element response exits to its subject, or the declared proxy representing it
  // where the subject cannot take focus. Resolve that structural parent from the current
  // anchor, so c from an obligation and an aimed press on the same obligation unwind alike.
  // There is no saved pre-command focus: being on an option comments on its obligation,
  // and closing returns to the obligation itself. A drawing's proxy is the fallback, not
  // the parent, even for a user who pressed it: it is a hidden stand-in for the drawing
  // (control-faces.js, `proxy`), so the drawing, which the user sees, is where they
  // return. A part of a drawing is returned to as travel reaches it, where the drawing
  // names for it (`addressedFocus`), as a chart takes focus itself, settling on its point
  // only if the user lands there. A quoted selection clears to the page; a removed
  // subject has no parent to land on.
  /** @param {Anchor | null} anchor */
  const returnPlaces = (anchor) => {
    if (!anchor || anchor.quote) return [];
    const drawing = anchor.visual ? sectionOf(anchor) : null;
    const part =
      drawing && anchor.visual ? addressedFocus(drawing, anchor.visual) : null;
    return [part, anchorTargetAt(anchor), visualActionAnchor(anchor)];
  };
  // Putting the bar away is closing a layer (dom/focus.js, `closeLayer`): `showFab(null)`
  // moves no focus, and the closer names where a user who was in the bar lands, read
  // before it goes. `putAwayFab` hands them back to the bar's subject; `letGoOfFab` lets
  // them go onto the page, from the bar or from that subject.
  /** @param {boolean} toPage */
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
  // A send lands the user itself, on the conversation it opens (selection.js, `send`),
  // so the bar its settlement takes down lands no one. The call it returns lets go of
  // a user the send landed nowhere, while they still stand in the bar and no other
  // anchor has taken it.
  function takeDownFab() {
    closeLayer(() => showFab(null));
    return () => {
      if (!fabAnchor.value && fabBar.contains(fabFocused())) letGo();
    };
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
    activePlacement = placement;
    paintFab();
  }
  /** @param {Anchor | null} anchor @param {{place?: boolean, point?: Element | null | undefined, reveal?: boolean}} [options] */
  function showFab(anchor, { place = true, point = undefined, reveal = false } = {}) {
    letGoOfRest();
    const previous = fabAnchor.value;
    if (!anchor) {
      restoreFab({ place: false });
      clearFab();
    } else {
      const previousFloating = activePlacement;
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
      activePlacement = place && !keptInline ? placement : null;
      paintFab();
      // A margin control can name an item whose rendered box is currently off
      // screen. `e` still needs the durable anchor so it can extend that existing item;
      // in that route the floating bar is never painted and placement is deliberately
      // skipped. Every route that actually shows the bar keeps the geometry gate. The gate
      // is for opening: the bar already being on this anchor, placed again, is
      // withheld rather than put away (standFab).
      if (activePlacement && !activePlacement.place({ reveal })) {
        if (same && activePlacement.stands()) activePlacement.withhold();
        else clearFab();
      }
    }
    // A bar raised on a new target takes the thread card down: the card stands above
    // page-level chrome and may cover the bar, and the user has moved on from its thread
    // to a new response, as opening a margin entry's options closes it.
    if (fabAnchor.value && activePlacement && !sameAnchor(previous, fabAnchor.value))
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
    if (resting) placement?.place();
    if (!fabAnchor.value || !activePlacement) return;
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
    placement.withhold();
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
  /** @param {Anchor | null} anchor */
  const anchorTargetAt = (anchor) => {
    if (!anchor) return null;
    const found = responseTarget(anchor);
    if (!found) return null;
    if (!anchor.quote) return targetElement(found);
    return lightSeat(targetPlace(found));
  };
  /** @param {Anchor | null} anchor */
  const anchorTravelAt = (anchor) => {
    const start = anchor?.quote
      ? passageStart(targetSegments(resolveAnchor(anchor)))
      : [];
    return start.length ? rangeOf(start) : anchorTargetAt(anchor);
  };
  const fabTargetAt = () => anchorTargetAt(fabAnchor.value);
  const fabReturnPlaces = () => returnPlaces(fabAnchor.value);

  // Opening Comment is an overlay gesture. Any visible part of its subject is
  // enough to open it: the physical presenter owns its attachment and measure, so
  // this asks only whether any of it is seen, not whether a landing would show more
  // (readings/landing-scroll.js, `alreadyShown`, which a short subject cut by an edge is not).
  // Only a stale current location or a resumed draft whose subject is wholly out of view needs
  // travel (including revealing a closed ancestor), before placement measures it.
  /** @param {Element | null} addressable */
  function bringForward(addressable) {
    if (addressable && !seenRect(addressable, new Map()))
      scrollToElement(addressable, "instant");
  }

  // Every explicit target gesture ends here. The gesture has already resolved its stable
  // authored anchor; this command owns the one transition from that target into Comment.
  // Focusing the field drops any older browser selection, and the field opens on the
  // target's own draft, leaving an earlier one with its passage. Escape resolves the
  // same structural parent for every entry route.
  /** @param {{anchor: Anchor, element?: Element | null, point?: Element | null}} target */
  function commentOnTarget({ anchor, element = null, point = null }) {
    stopSelectionUpdate();
    bringForward(element);
    targetActivation = true;
    const selection = getSelection();
    if (selection?.rangeCount) selection.removeAllRanges();
    openComment(anchor, "", { point });
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
    stopSelectionUpdate();
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
  /** @param {Anchor | import("../../readings/anchor-resolution.js").CapturedAnchor | null} anchor @returns {anchor is Anchor & {quote: string}} */
  const hasQuote = (anchor) => Boolean(anchor?.quote?.trim());
  // Whether words stand selected on the page, which a comment on the selection would
  // quote. It reads none of the context a capture reads around them, so a repaint
  // asking where `c` goes, and each surface asking whether `c` is live, capture nothing.
  const hasPageSelectionTarget = () => {
    const selection = pageSelection();
    return selection !== null && rangeHoldsWords(pageRange(selection));
  };

  // Observed selection belongs to the browser until Comment is pressed. Native handles
  // and browser commands owe the page no pointer/key completion, and selectionchange
  // carries the same trusted notification for a script's endpoint write. It can offer
  // the current passage, but cannot authorize replacing a composer or its draft.
  // That menu can stand on either side of the words; never compete with it by raising
  // a second adjacent surface. The floating panel's page field offers the current
  // selection instead (panel/floating-panel.js, `selectedWords`): its placeholder quotes the
  // words, and a press there comments on them. The press reads the selection again
  // where it still stands, as a source refresh that kept its native endpoints leaves
  // it, and otherwise takes the anchor read when it last settled, since a field taking
  // focus, or a tap on iOS, can drop the page's selection before the press ends.
  /** @type {(Anchor & {quote: string}) | null} */
  let offeredSelection = null;
  /** @param {(Anchor & {quote: string}) | null} anchor */
  const offerSelection = (anchor) => {
    if (anchor === offeredSelection) return;
    offeredSelection = anchor;
    pageComment.offer(
      anchor
        ? {
            quote: anchor.quote,
            comment: () => commentOnSelection(selectedWords() ?? anchor),
          }
        : null,
    );
  };
  // The words selected on the page, as the passage a comment on them quotes, or null
  // while none are or anchoring can't quote them yet.
  const selectedWords = () => {
    const selection = anchoringIsReady() ? pageSelection() : null;
    const anchor = selection ? selectionAnchor(selection) : null;
    return hasQuote(anchor) ? anchor : null;
  };
  /** @param {Anchor | null} anchor */
  const commentOnSelection = (anchor) => {
    offerSelection(null);
    if (!hasQuote(anchor)) return;
    stopSelectionUpdate();
    openComment(anchor, "");
  };

  // Whether a press is still selecting words. They are the press's until it completes,
  // which offers or places whatever it selected (`updateFab`), so no box stands for them
  // meanwhile: the panel's field quotes none, whatever else asks, such as a key released
  // mid-press, and no box shows `c` for them (`commentDestination`).
  const pressSelecting = () => Boolean(pagePresses.kept()?.selecting?.());
  // The panel's field offers the selected words while no bar stands for them.
  function observeSelection() {
    const words = pressSelecting() ? null : selectedWords();
    offerSelection(words && !sameAnchor(words, fabAnchor.value) ? words : null);
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
      // and would collapse choices immediately after `e` exposed them.
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
  /** @type {{ticket: ReturnType<typeof nextRender>, intent: ReturnType<typeof retainUserIntent>} | null} */
  let selectionUpdate = null;
  function stopSelectionUpdate() {
    if (selectionUpdate) cancelRender(selectionUpdate.ticket);
    selectionUpdate = null;
  }
  /** @param {() => unknown} update */
  const deferSelectionUpdate = (update) => {
    const mayUpdate = retainUserIntent();
    stopSelectionUpdate();
    const ticket = nextRender(() => {
      selectionUpdate = null;
      if (!mayUpdate()) return;
      update();
    });
    selectionUpdate = { ticket, intent: mayUpdate };
  };
  const scheduleSelectionUpdate = () => {
    // Keep this gesture's pending snap, but replace work a newer gesture retired.
    if (selectionUpdate?.intent()) return;
    deferSelectionUpdate(updateFab);
  };
  // What the press under way began with and has done, kept against the press (dom/focus.js,
  // `pressRecords`), so none of it outlasts the press: a release a widget stopped, or one
  // let go off the window, leaves nothing for the next selectionchange to read.
  //
  // - `selecting`: a primary-button press begun in page words owns their selection
  //   until it finishes it, at a finger's or pen's release or a mouse's compatibility
  //   mouseup. It is the press's retained intent (dom/user-intent.js), since the press
  //   belongs to the content it began on and a newer input supersedes it: a bounded
  //   reading region can take native focus after pointerdown, and the previous focus is
  //   not its owner.
  // - `point`, `dragged`: where it began, and whether it has since moved off it.
  // - `range`, `backward`: what the drag has held inside the document
  //   (`rememberPointerSelection`).
  // - `away`: whether the hand last moved over something other than page words, such as
  //   the layer. The selection alone can't say: over the layer's own words the browser
  //   can leave its far end on the page's last words, inside the document while the
  //   range holds everything after the press.
  // - `claimed`: a widget turned the press into a different gesture after pointerdown.
  //   `preventDefault` on its bubbling pointermove is the shared claim boundary: the
  //   selection surface must not restore the range it captured before that claim.
  // - `words`: the page's own words the press began with (the click door below).
  // - `action`: a press on the response surface's own controls, or on chrome while a
  //   passage is offered, which holds selectionchange out until the press is over.
  /**
   * @typedef {{
   *   selecting: ReturnType<typeof retainUserIntent> | null,
   *   point: { x: number, y: number },
   *   dragged: boolean,
   *   range: Range | null,
   *   backward: boolean,
   *   away: boolean,
   *   claimed: boolean,
   *   words: string,
   *   action: boolean,
   * }} PagePress
   */
  /** @type {import("../../dom/focus.js").PressRecords<PagePress>} */
  const pagePresses = pressRecords();
  let targetActivation = false;
  let fabInputTakingFocus = false;
  // Which handoff the mark belongs to. The mark itself is one bit, so a landing that only
  // read the bit could not tell its own handoff's mark from a later one's, and releasing
  // on the way out would drop a mark still being held for a focus yet to land.
  /** @type {FabFocusHandoff | null} */
  let fabFocusHandoff = null;
  const beginFabFocus = () => {
    fabInputTakingFocus = true;
    /** @type {FabFocusHandoff} */
    const handoff = {
      intent: retainUserIntent({
        available: () => fabFocusHandoff === handoff,
      }),
    };
    fabFocusHandoff = handoff;
    return handoff;
  };
  /** @param {FabFocusHandoff | null} [handoff] */
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
  /** @param {FabFocusHandoff} handoff @param {Anchor | null} anchor @param {() => boolean} stands */
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
  /** @param {Anchor | null} anchor @param {string} text @param {Parameters<ReturnType<typeof createSelectionComposer>["openComposer"]>[2]} [options] */
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
      stopSelectionUpdate();
      offerSelection(null);
      fabInputTakingFocus = true;
    });
    fabInput.addEventListener("blur", () => {
      fabInputTakingFocus = false;
    });
    // A press on the box at rest leaves focus on its target, which is what raised it,
    // until the press opens the field.
    fabRest.addEventListener("mousedown", (ev) => ev.preventDefault());
    fabRest.addEventListener("click", () => {
      if (resting) commentOnTarget(resting);
    });
    // Kept words the box cuts short read whole under its name.
    fabRest.lfPreview = () => {
      const words = fabRest.querySelector(".lf-compose-placeholder-words");
      const kept = resting && keptDraft(resting.anchor);
      return kept && words && words.scrollWidth > words.clientWidth
        ? { detail: [draftLine(kept)] }
        : null;
    };
  }
  // What the page's selection held when the keys were last painted: nothing, only
  // spaces, or words; null once a press begins. Escape owns the selection from its first
  // glyph, and `c` comments on it from its first word (`commentDestination`). A press can
  // also change the words without either crossing, as a Shift-press extending them does,
  // and its first change takes `c` off the box standing for the words it began with.
  // Paint only those changes, including a selection begun in a label whose pointer press
  // is not a page-word gesture; growing a selection that already holds words needs no
  // repaint on each drag frame.
  /** @type {"nothing" | "spaces" | "words" | null} */
  let selectionStood = "nothing";
  const reflectSelection = () => {
    const stands = hasPageSelectionTarget()
      ? "words"
      : pageSelection()
        ? "spaces"
        : "nothing";
    if (stands === selectionStood) return;
    selectionStood = stands;
    repaint();
  };
  // What this drag has had inside the document, kept against a release that ends holding
  // something else. Only while both ends and the hand are still in it: `pageSelection`
  // answers for the end the press began at, which stays in the page for the whole of a
  // drag that leaves it, so without the far end and the hand (`away`) this would remember
  // the runaway range itself and have nothing to put back.
  /** @param {PagePress} press */
  const rememberPointerSelection = (press) => {
    const selection = pageSelection();
    if (!selection || press.away || leftThePage(selection)) return;
    const anchor = selectionAnchor(selection);
    if (hasQuote(anchor)) {
      press.range = pageRange(selection).cloneRange();
      press.backward = selectionBackward(selection);
    }
  };

  /** @param {PointerEvent} ev */
  const finishPointerSelection = (ev) => {
    if (drawModeActive()) return;
    const press = pagePresses.kept();
    if (!press?.selecting) return;
    // Opening or acting in chrome is a route away from the page, not a new selection
    // gesture. Keep the native touch passage verbatim while focus moves
    // through the floating panel, its popovers, and their controls.
    if (offeredSelection && inChrome(eventSource(ev))) {
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
  // over, after the compatibility events its release owes (dom/focus.js, `pressing`), so the
  // focus collapse it causes is not read as the user's. Native selectionchange may have
  // coalesced that collapse and a later passage meanwhile, so the live selection is read
  // as the press goes, through the same guards as a native notification.
  const rereadAfterAction = () =>
    pagePresses.kept()?.action ? selectionChanged : null;

  // The response surface getting out of the way of a press away from it (dom/focus.js,
  // `onPressAway`), which is a fact about the press rather than about who receives it, so
  // a press the aim or a design mode claims from the page puts it away too. A press on
  // the visual the bar stands for keeps it, as does a stroke in a draw mode or a capture's
  // drag, which go on into the draft the composer holds. A native modal owns its press,
  // the command reference's included, which goes by its own light dismissal
  // (`closedby`), and the composer behind it stays inert.
  /** @param {EventTarget[]} path */
  function pressedAway(path) {
    if (
      drawModeActive() ||
      captureActive() ||
      nativeLayers().some((layer) => layer.kind === "modal")
    )
      return false;
    // The node pressed, not the widget host a shadow tree retargets it to: core controls
    // seated in a widget surface stay inside their own composer or reaction layer.
    const [origin] = path;
    const target = origin instanceof Element ? origin : null;
    // A release outside the document can begin its path at window, which has no
    // visual place to compare with the open composer.
    const visual = target ? visualAt(target) : null;
    const sameVisual =
      visual &&
      !fabAnchor.value?.quote &&
      fabAnchor.value?.section === visual.id &&
      fabAnchor.value.visual === visual.part?.id;
    return (
      !sameVisual &&
      !target?.closest(".lf-fab-bar, .lf-react-surface, .lf-composer") &&
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

  const fabAnchorAt = () => fabAnchor.value;
  const fabFrameAt = () => placement?.frame() ?? null;
  const fabPointAt = () => fabPointIn(fabTargetAt());

  // The composer this bar's field belongs to, built once every surface command it reads
  // exists and before the commands below that read it. The two answer each other at every
  // gesture, so one owner builds both and boot wires neither to the other.
  const composer = createSelectionComposer({
    setReact,
    reactionEmoji,
    reactionAvailable,
    designModeActive,
    openPageThread,
    anchorTravelAt,
    fabAnchorAt,
    fabHoldAt,
    fabPointAt,
    fabFrameAt,
    fabPositioned,
    beginFabFocus,
    endFabFocus,
    landFabFocus,
    showFab,
    letGoOfFab,
    takeDownFab,
    createComment,
    landSent,
    refreshThread,
    wireInput,
    drawingEdits,
  });

  // Touch handles and browser selection commands do not owe the page a mouseup or keyup.
  // During a pointer drag, the completed gesture below remains the one that snaps and
  // places the passage; presses on the action surface must not retract their own target.
  function selectionChanged() {
    const automatic = programmaticSelection(getSelection());
    const press = pagePresses.kept();
    if (press?.selecting?.()) {
      rememberPointerSelection(press);
      if (coarsePointer.matches && !press.claimed) rememberSelection();
      observeSelection();
      reflectSelection();
      return;
    }
    // Words selected in a box are the box's, so a box holding focus offers no passage.
    if (takesLetters(focused())) {
      offerSelection(null);
      retireBarePassage();
      return;
    }
    // Focus and action handoffs own the captured target while the browser collapses
    // its selection. Outside those handoffs, observe the browser's live passage;
    // only the completed page gesture above/below may replace the composer.
    if (press?.action || targetActivation) return;
    const selection = pageSelection();
    if (coarsePointer.matches && selection && !automatic) rememberSelection(selection);
    observeSelection();
    retireBarePassage();
    reflectSelection();
  }
  // A bare passage is selected words the bar stands beside, which the user has neither
  // entered nor written in. Its bar is the browser selection's, and stands only while
  // the browser still holds those words. Focusing Comment captures the passage, and a
  // written draft keeps it even after focus moves elsewhere; neither belongs to the
  // native selection then.
  const barePassage = () => {
    const passage = fabAnchor.value;
    return passage?.quote && !fabHoldsCapturedPassage() && !composer.composerHolds()
      ? passage
      : null;
  };
  // Other words selected, or none, end a bare passage. A box that takes the selection,
  // as page search's does, ends it too, however soon focus leaves the box again. Only a
  // bare passage's bar reads the selection here, so a keystroke in a box reads nothing.
  // A press under way leaves the bar until the press completes (`selectionChanged`), and
  // meanwhile `c` reads the same rule (`commentDestination`).
  function retireBarePassage() {
    const passage = barePassage();
    if (!passage || (pageSelection() && !anchoringIsReady())) return;
    if (!sameAnchor(selectedWords(), passage)) putAwayFab();
  }

  function mount() {
    composer.mount();
    placement?.mount();
    coarsePointer.addEventListener("change", observeSelection);
    document.addEventListener(
      "pointerdown",
      (ev) => {
        if (drawModeActive()) return;
        // Read here, ahead of the browser's own collapse, so what the press took is told
        // from what it merely landed in. Its first change repaints (`reflectSelection`).
        const stood = pageSelection();
        selectionStood = null;
        // A second contact is no part of the press under way.
        if (!ev.isPrimary) return;
        // Admission reads the press's origin across widget shadow roots. The host
        // also contains runtime editors and controls, which are not page prose.
        const target = eventSource(ev);
        const selecting = ev.button === 0 && pageWords(target);
        const press = pagePresses.keep(ev, {
          selecting: selecting ? retainUserIntent({ source: target }) : null,
          point: { x: ev.clientX, y: ev.clientY },
          dragged: false,
          range: null,
          backward: false,
          away: false,
          claimed: false,
          words: stood ? stood.toString() : "",
          action:
            (offeredSelection && inChrome(target)) ||
            Boolean(
              target instanceof Element &&
              target.closest(".lf-react-surface, .lf-composer"),
            ),
        });
        if (selecting && stood && target && pageRange(stood).intersectsNode(target))
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
      press.away = !pageWords(eventSource(ev));
    });
    document.addEventListener("touchstart", (ev) => {
      // The native touch event follows pointerdown and is the same selecting press.
      // Capture its input generation at that producer, before handles can adjust it.
      const press = pagePresses.kept();
      if (press?.selecting)
        press.selecting = retainUserIntent({ source: eventSource(ev) });
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
      // and the range this press remembered is that. Without it, a hand a few words along a
      // paragraph overshooting the layer would capture and mark far more than it held, and
      // name the whole document in the field — because past the page's last words the
      // browser extends through everything between (leftThePage, annotations/composing/capture.js).
      // A release with the hand over the layer (`away`) has left it too, wherever the
      // browser put the selection's far end.
      //
      // Asked here and nowhere shared, because the gesture is what tells this from ⌘A: select
      // all means the document and lands its far end past the page by definition, and it
      // arrives through the keyboard's route, which never comes past this line.
      const escaped = press.dragged && (press.away || leftThePage());
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
          /** @type {import("../../dom/native-selection.js").SelectionEnd} */
          const head = [completed.startContainer, completed.startOffset];
          /** @type {import("../../dom/native-selection.js").SelectionEnd} */
          const tail = [completed.endContainer, completed.endOffset];
          selectEnds(press.backward ? tail : head, press.backward ? head : tail);
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
    // Selections made from the keyboard (shift-arrows, ⌘A) deserve the same response bar.
    // Typing in a box never does, whatever is selected elsewhere.
    document.addEventListener("keyup", (ev) => {
      if (dismissedSelectionKeyup) {
        dismissedSelectionKeyup = false;
        if (ev.key === "Escape") return;
      }
      if (isReactArmed()) return;
      const target = eventSource(ev);
      if (takesLetters(target) || inChrome(target)) return;
      if (!pageWords(target) && !pageSelection()) return;
      if ((ev.shiftKey && CARET_KEYS.includes(ev.key)) || selectsAll(ev)) {
        rememberSelection();
        scheduleSelectionUpdate();
      } else observeSelection();
    });
    onPressAway(pressedAway, standDown);
    // What a plain click on the page means, decided once. Design mode explicitly changes
    // the grammar, and a visible mark opens its thread. Unadorned authored content keeps
    // the browser's native meaning; Comment targeting belongs to Alt-click, `s`, and the
    // visual proxies instead.
    //
    // Once, because the hit-test reads layout and opening a thread rewrites it: a second
    // handler asking `markAt` after the first had opened the mark's thread would miss
    // that mark and raise the comment field over it, leaving an element anchor set, which
    // `midComposition` reads (engagement.js), so the page would stop following new
    // versions.
    document.addEventListener("click", (ev) => {
      if (drawModeActive()) return;
      const target = eventSource(ev);
      if (!pageWords(target)) return;
      // A press that ends holding words it did not begin with took them, and is that
      // selection's mouseup rather than a click on whatever lies under it: the user was
      // reaching for the words, and the 💬 is already up on them (updateFab, on the same
      // mouseup). The same complaint `offer` answers for a press on a control
      // (reachedForWords), and it governs the whole of
      // what a click on prose means — the block design mode comments on, and the thread a
      // mark opens. Marked words show it most: a gesture inside one would travel to its
      // thread, and with Threads open the reply box it lands in would collapse the
      // selection the user just made, taking the words and the 💬 with it.
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
      // for itself (annotations/design.js).
      if (designModeActive()) {
        const design = designTarget(target);
        if (design) openOnDesign(design);
        return;
      }
      // A painted owner may contain working controls or editing regions. Their
      // native click keeps its meaning even when an annotation covers the owner. So does
      // a click a widget took, which it says by preventing the click's default
      // (module-input.md, "Pointer presses"), as panel/page-keys/controller.js reads a key:
      // a press on an option card picks the option and opens no thread on its question.
      if (ev.defaultPrevented || closestAcross(target, WORKS)) return;
      // The record rather than this event's own coordinates, for the reason the record is
      // kept from a pointer event at all (base/pointer.js): `click` is a legacy mouse event and
      // carries the pointer's place rounded to a whole pixel, while markAt measures against
      // getClientRects, whose edges are floats. Asked at the rounded point, this can answer
      // a different thread than refreshHover just promised at the true one — a quote lit
      // up under the hand and a press on it opening nothing.
      //
      // A click with no press behind it carries 0,0 rather than a position — `offer` calls
      // click() to supply the keys a span doesn't come with — and the record would answer
      // for wherever the pointer is parked, so that one keeps reading the event.
      const point = pressIsKeyboardActivation(ev)
        ? { x: ev.clientX, y: ev.clientY }
        : pointerAt();
      const threadId = markAt?.(point.x, point.y);
      if (!threadId) return;
      // The press picked words where they stood, and the thread opens without travel,
      // so a glide under way that carries them stops there, as a spatial command stops
      // one (dom/scrolling.js, `stopGlide`): the card the thread opens moves no scroller of
      // its own (readings/scroll-containers.js, `scrollersOf`), so its landing would leave a
      // walk's glide carrying the clicked words out of the window.
      const clicked =
        target instanceof Element ? target : (target?.parentElement ?? null);
      for (const box of carriersOf(clicked)) stopGlide(box);
      void openPageThread(threadId, { travel: false });
    });
    wireFabInput();
  }

  // ---------- where "comment" goes ----------
  // The thread the user is in, and the box it is written in. Two
  // containers hold one and the user can enter either: the panel's thread, and a thread
  // drawn on the page, in a card or in a widget's outlet.
  // They are one question — a press meaning "say something about this" belongs to the box
  // of the thread the user is already in — so they get one reading rather than a
  // rule for the panel and a different one for the page.
  //
  // One of the two is in the chrome, which is not the exception it looks like: page scope
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
  /** @param {string} word */
  const commenting = (word) => ({
    title: `comment on the ${word}`,
  });
  // The element and threads where focus puts the user. Focus they have scrolled out of
  // sight puts them nowhere in the page, so `c` writes where they are reading rather than
  // taking them back to it: a walk's stop scrolled away from took the page back 1949 px
  // at the median, and they backed out of 4 presses in 7 (panel/page-keys/controller.js lets go
  // of it on any key).
  function focusedPlace() {
    const at = focused();
    if (at && at !== document.body && !focusPlace())
      return { here: null, threadId: null, said: null };
    const inline = threadHere();
    const inlineBox = inline && threadInput(inline);
    return {
      here: currentTarget(),
      threadId: threadAtCurrentLocation(),
      said:
        currentLocationThread() ??
        (inlineBox ? { held: inline, box: inlineBox } : null),
    };
  }
  // `onWords` marks a destination where c puts the caret in the words its box holds now.
  // The comment box moved to where the user stands is no such place: it opens on that
  // place's own draft, whatever words the box holds.
  /** @returns {{title: string, box: Element | null, onWords?: boolean, go: () => unknown, rest?: NonNullable<ReturnType<ResponseOptions["currentTarget"]>>}} */
  function commentDestination() {
    const anchor = fabAnchorAt();
    // Words selected on the page outrank where the user stands, and a comment on them
    // opens beside them. The box standing for those words carries c: the panel's field
    // while it quotes them, since a press there comments on them too, or the bar beside
    // them. A box standing for other words carries none, and words a press is still
    // selecting have no box, though the old words' box stands until the press completes.
    // Only the box needs to know which words are selected, so the title and `when`
    // capture none.
    if (anchoringIsReady() && hasPageSelectionTarget())
      return {
        ...commenting("selection"),
        get box() {
          if (pressSelecting()) return null;
          const words = selectedWords();
          if (sameAnchor(words, offeredSelection)) return pageComment.box;
          return sameAnchor(words, anchor) ? fabInput : null;
        },
        // Placed beside the words as they stand, like a target's box below.
        go: () => {
          landGlides();
          commentOnSelection(selectedWords());
        },
      };
    const { here, threadId, said } = focusedPlace();
    // The thread drawn with the user's place (`threadHere`), such as the card beside it,
    // is one place with it, so its reply box is where c writes, even where the thread is
    // about a block enclosing what they stand on: the box they see is the one c names,
    // rather than a new thread on the obligation the card stands beside, which would close
    // the card they are reading. That thread starts from `s`, which chooses an element.
    // An undrawn thread continues only where it is about what they stand on: its target
    // lies within the element they stand at — the obligation holding focus, answered or
    // not, else the element itself — as an obligation's options group does when the user
    // holds one of its marks, or it names the very target they stand on, as a thread on
    // the point a chart's keys stand on does, whose mark is not the element focus holds.
    // So with no card shown, an element inside a commented block takes a thread of its
    // own, and a selection still starts one on its words.

    const target = threadId && threadTarget(threadId);
    const subject =
      threadId &&
      (!here ||
        (target && under(target, heldObligation() ?? here.element)) ||
        sameAnchor(threadNamed(threadId)?.anchor, here.anchor));
    // A captured passage outranks the focus it preceded, but a kept draft is not a
    // current target. Read both page and thread location before choosing the aim.
    // After the user lands elsewhere, Comment names that new place and opens its own
    // draft, the old words staying with theirs. The element holding a passage is
    // elsewhere too: the user standing on it is about the whole element, not the words
    // the draft quotes. A bare passage's words are no longer selected here, so its bar
    // is no destination, even while a press under way still shows it.
    if (
      anchor &&
      !barePassage() &&
      (fabHoldsCapturedPassage() ||
        (!said && !subject && (!here || sameAnchor(here.anchor, anchor))))
    )
      return {
        ...commenting(
          anchor.quote
            ? "selection"
            : addressableWord(elementById(anchor.section)) || "element",
        ),
        box: fabInput,
        onWords: true,
        go: focusFabComment,
      };
    if (said)
      return {
        ...commenting("thread"),
        box: said.box,
        onWords: true,
        go: () => {
          composer.leaveForThread();
          landIn(said);
        },
      };
    if (subject)
      return {
        ...commenting("thread"),
        box: null,
        go: async () => {
          const destination = await openPageThread(threadId, {
            part: "reply",
            travel: false,
          });
          if (!destination) return;
          composer.leaveForThread();
          landIn({ box: destination });
        },
      };
    // The bar opens beside the target the user stands on. While the bar stands beside
    // another subject, its box is not where c writes, so it shows no c.
    if (here)
      return {
        ...commenting(here.anchor.datum ? "item" : addressableWord(here.element)),
        box: anchor ? null : fabInput,
        rest: here,
        // The box's placement measures its target where it stands, so the glides under
        // way land first (dom/scrolling.js, `landGlides`): `c` pressed as `m` sets off
        // opens the box beside the ask where `m` lands it, where a box placed mid-glide
        // took the side with room then and ended off screen with focus in it.
        go: () => {
          landGlides();
          commentOnTarget(here);
        },
      };
    // The page's own box is the floating panel's field.
    return {
      ...commenting("page"),
      box: pageComment.box,
      onWords: true,
      go: pageComment.open,
    };
  }

  // The destination's box is the identity chrome uses to place a contextual binding badge,
  // and the label is whichever Comment route dispatch would answer from here. Dispatch
  // still decides whether either row can be reached from the current scope. A repaint
  // asks for this hint and then rests the box (dom/repaint.js), so the walk answers both.
  let commentKey = "";
  const commentHint = () => {
    const { box } = commentDestination();
    commentKey = commandKeysNow("comment.create").join(" ");
    return { box, label: commentKey };
  };
  // The box c puts the caret in the words of, while those words cover the placeholder
  // that would name c, with that key: the key chips hang it on the box's corner
  // (input.js, `coveredFrame`; readings/key-badges/command-hints.js). Comment declares no
  // control to carry the chip, since a control it lacked would leave c dead everywhere
  // else (dom/keyboard/bindings.js, `commandAvailable`).
  const coveredEntry = () => {
    const { box, onWords } = commentDestination();
    const control = onWords ? coveredFrame(box) : null;
    const [binding] = control ? commandBindingsNow("comment.create") : [];
    return control && binding ? { control, binding } : null;
  };

  // The target the box rests beside: the one `c` would open it on, while the user can see
  // it. A finger is shown no keys, so it is shown no box waiting for one, and a frame
  // holding focus, as a live sample does, has the keys itself.
  const restingTarget = () => {
    if (
      fabAnchor.value ||
      !placement ||
      !advertisesKeys() ||
      focused()?.localName === "iframe" ||
      pageSelection()
    )
      return null;
    const { rest } = commentDestination();
    return rest && seenRect(rest.element, new Map()) ? rest : null;
  };
  // A move to another target places the box afresh and keeps whether it waits for room,
  // which the new placement answers; only the box going away lets go of that.
  function letGoOfRest() {
    if (!resting) return;
    resting = null;
    placement?.stop({ reset: true });
    placement?.release();
    keeps(fabBar, "data-lf-rest", null);
  }
  // The draft kept on a target, as the margin and Threads list it.
  /** @param {Anchor} anchor */
  const keptDraft = (anchor) => {
    const key = composer.draftKey(anchor);
    return draftsReading().find(({ context }) => context === key);
  };
  // Read in each repaint, since where `c` goes follows focus, whether a scroll has taken
  // it out of sight (readings/user-place.js), and the state.
  function restFab() {
    const next = restingTarget();
    const key = next && commentKey;
    const target = key ? next : null;
    if (!target) {
      letGoOfRest();
      return;
    }
    if (resting && !sameAnchor(target.anchor, resting.anchor)) {
      resting = null;
      placement?.stop({ reset: true });
    }
    keeps(fabBar, "data-lf-rest", "");
    // A draft kept on the target shows its words where the empty box says Comment…,
    // since `c` opens the box on them, as a box holding words shows them.
    const draft = keptDraft(target.anchor);
    const kept = draft ? draftWords(draft) : "";
    render(
      html`<span class="lf-compose-placeholder" ?data-lf-words=${Boolean(kept)}
        ><span class="lf-compose-placeholder-words">${kept || COMMENT_HINT}</span
        ><kbd class="lf-key-badge">${key}</kbd></span
      >`,
      fabRest,
    );
    const arrived = !resting;
    resting = target;
    if (!arrived) return;
    activePlacement = placement;
    const label = anchorLabel(target.anchor, null).replace(/^§\s*/, "");
    keeps(fabRest, "aria-label", label ? `Comment on ${label}` : "Comment");
    keeps(fabBar, "data-lf-paint-plane", "page");
    placement?.place();
  }

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
    // A box that takes no words now, as the panel's field while a stance stands
    // (panel/field-readings.js, `still`), is no place for c to write; words selected on the
    // page still are, since a comment on them opens a box of its own.
    when: () =>
      (anchoringIsReady() || !pageSelection()) &&
      (hasPageSelectionTarget() || !takesNoWords(commentDestination().box)),
    // The press goes where the badge and title it was read from said: one reading
    // decides all three.
    run: () => commentDestination().go(),
  });

  // Tab opens responses from the editor, outside a list item, where the editor takes
  // Tab to nest it; attachments keep native traversal, and so does a box offering a
  // second send (`fabHoldAt`), which Tab reaches past Send.
  // Project this alongside the input owner's submit scope rather than replacing it.
  const composerOptions = commandScope("In the comment box", [
    {
      id: "comment.options",
      keys: () => (composer.responseOptionsAreOpen() || fabHoldAt() ? [] : ["Tab"]),
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
    coveredEntry,
    restFab,
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
