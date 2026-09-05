/* The anchored response bar: where it stands, what raises it, and the room it keeps.

   Normal reading mode leaves a plain click on unadorned authored content to the
   browser. Visible native and Leaf controls keep their click actions; text selection
   targets words. Alt-click, `s`, and a visual's “Respond to…” proxy are explicit
   Comment gestures. They pass the target from `aimTargetAt` or the visual provider to
   `commentOnTarget`, which opens the compact field and focuses its cursor in the same
   transaction. A whole item or picture names its authored id, while a visual part adds
   its declared token. Tab exchanges that field for choices in the same bar and focuses
   Comment first. Tab, Shift-Tab, and the arrow keys then wrap through every choice.
   Comment and Escape restore the field; Escape from the field hides the draft. The
   same anchor resolves both states against the target's geometry.

   The bar a selection or keyboard-selected item raises is `.lf-fab-bar`: the durable,
   compact `.lf-fab-input` followed by one response ellipsis. An explicit item target
   opens and focuses that field immediately. Selecting a passage opens the field
   without taking focus or collapsing the browser selection; the reader can still copy
   the selection or use its native context menu, then enter the field with Comment. The
   field grows in place and never transfers text into a second composer card. A
   one-line note is a pill. A longer one widens up to a readable 80ch and then wraps,
   and grows into the available clear band before it scrolls; its corner stays the
   pill's 16px rather than growing with the box, so the corner never reaches over the
   first or last line. Placement states a float's room as `--lf-float-w` and
   `--lf-float-h`; the bar is capped by it and the field's `--lf-response-room`
   excludes its neighboring controls. The field's scroll extent supplies its desired
   height without temporarily resizing it and losing the reader's scroll position.
   When the target fills the viewport, the viewport still caps the field. When a
   covering panel leaves no usable band for the response bar, placement withdraws it
   without discarding its draft. If the disappearing bar held focus, the visible
   Threads list takes it; an unrelated focused control keeps it. A partially exposed
   page remains interactive whenever the bar fits its actual remaining room. Enter
   inserts a newline; `Mod+Enter` sends. Tab changes the same bar into Comment, Suggest
   when the anchor is a quote, and the layer's reaction tokens.

   `showFab` places the bar; `openComposer` (composing/selection.js) binds its field to
   the durable draft and takes the focus decision. Every explicit item and visual route
   passes its resolved anchor to `commentOnTarget`, which focuses the same field and
   carries an unsent draft to the new target. Automatic passage selection opens that
   passage's own durable draft without moving focus. Submitted words still in flight
   remain owned by their original anchor, while a later target starts clean and keeps
   focus.

   `placeClear` fits the response bar into a free band bounded by the viewport, its
   target, and controls carrying `data-lf-offer`. A quoted passage keeps its whole
   paragraph clear. Placement prioritizes proximity to the target, then visible writing
   space; geometry supplies CSS room constraints, while CSS owns the field's content
   sizing. */
import {
  anchoringIsReady,
  markAt,
  NOTE,
  paintAnchors,
  resolveAnchor,
  sameAnchor,
  visualActionAnchor,
  visualAt,
} from "../anchors.js";
import { documentPoint, shownParts, shownRect } from "../geometry.js";
import { targetElement, targetParts, targetSegments } from "../resolved-target.js";
import {
  composerOpen,
  fab,
  fabBar,
  fabInput,
  hideComposer,
  openComposer,
} from "./selection.js";
import { designOn, designTarget, openOnDesign } from "../design.js";
import { referenceOpen, showReference } from "../keyboard/reference.js";
import {
  isReactArmed,
  paintReactionStanding,
  reactionContextContains,
  reactionTokens,
  setReact,
} from "../reactions.js";
import { panelCovers } from "../chrome-layout.js";
import { panel, threadsBox } from "../conversation/panel.js";
import { banner } from "../banner.js";
import { keylineEl, less } from "../keyboard/keyline.js";
import { blockAt, inChrome, pageRange, pageText, pageWords } from "../passages.js";
import { pageSelection, selectionAnchor, snapSelection } from "./capture.js";
import { paintHere } from "../keyboard/scopes.js";
import { letGo, takesLetters } from "../keyboard/page.js";
import { closeVersionMenu, versionMenuIsOpen } from "../version.js";
import { pointerAt } from "../pointer.js";
import { anchorLabel } from "../conversation/messages.js";
import { showThread } from "../conversation/landing.js";
import { reactionsOn } from "../conversation/model.js";

const hideReference = () => showReference(false, false);
const hasOtherResponses = (anchor) =>
  reactionTokens().length > 0 || Boolean(anchor?.quote && !designOn);

// ---------- selection → comment ----------
// Floating UI stays inside the document layout shell. Body already ends at a standing
// right panel's edge through its margin, while the root scrollport owns the browser's
// gutter. A covering sheet is the one strip body does not yield, so its width comes off
// here.
const rightEdge = () =>
  (panelCovers()
    ? innerWidth - panel.offsetWidth
    : Math.min(innerWidth, document.body.getBoundingClientRect().right)) - 8;
const fabFits = () =>
  rightEdge() > 8 && fabBar.scrollWidth <= Math.ceil(rightEdge() - 8);
// The floats live in the document — they scroll with the passage they stand beside —
// while every caller reasons in viewport terms: rects, the pointer, the banner's own
// band. The fixed floor covers the ordinary one-line banner; its live box takes over
// when compact chrome wraps to a second line.
export const BANNER_CLEAR = 48;
const topEdge = () => Math.max(BANNER_CLEAR, banner.getBoundingClientRect().bottom + 6);
const leftEdge = (node, left) =>
  Math.max(8, Math.min(left, rightEdge() - node.offsetWidth));
const bottomEdge = (left, width) => {
  const keyline = keylineEl.getBoundingClientRect();
  return keyline.height && left < keyline.right && left + width > keyline.left
    ? keyline.top - 8
    : innerHeight - 8;
};
// So the one writer of their position is where the coordinates change space: clamp in
// the viewport and above any key line it would cross, then store in the document.
// The chosen band also caps the float's height. Width is stated before band selection,
// because wrapping determines how much height the contents need.
function place(node, left, top, height) {
  node.style.setProperty("--lf-float-h", `${height}px`);
  const x = leftEdge(node, left);
  const bottom = bottomEdge(x, node.offsetWidth);
  const at = documentPoint(
    x,
    Math.max(topEdge(), Math.min(top, bottom - node.offsetHeight)),
  );
  node.style.left = at.left + "px";
  node.style.top = at.top + "px";
}
// Controls the page is standing on its own account, as against the ones in the runtime's
// layer: a reply's widget is markup frozen in the log, and the layer's own buttons are
// what floating chrome is allowed to sit beside. `data-lf-offer` is what makes a thing
// pressable (`offer`), so this asks after any widget's controls without naming one.
//
// Two controls out here still belong to the layer. The line saying how many comments a
// block holds and the visual's keyboard proxies wear the marker because a screen reader
// reaches them by Tab. Both are clipped to a pixel where they stand and take a box only
// on focus, fixed under the banner — so a float stepping down past either would step
// around nothing anyone can see, exactly the movement this walk exists to prevent.
const pageControls = () =>
  [...document.querySelectorAll(`[data-lf-offer]:not(.${NOTE})`)].filter(
    (control) =>
      !inChrome(control) && !control.matches(".lf-visual-actions, .lf-visual-action"),
  );

// The response bar carries the anchor its field will submit on, so targeting and typing
// cannot come to different conclusions about what the reader picked. Visibility is
// derived from that anchor and never read back off the stylesheet.
// The viewport, the target and the page's controls define one set of free bands.
// Walking down past controls and then clamping to the viewport could put a growing
// editor back on its target. Choose a band first; CSS can then size the field to it.
function placeClear(node, left, top, target, wantedHeight) {
  const x = leftEdge(node, left);
  const bottom = bottomEdge(x, node.offsetWidth);
  const sharing = [...pageControls().map((c) => c.getBoundingClientRect()), target]
    .filter((r) => r.width && r.left < x + node.offsetWidth + 6 && x < r.right + 6)
    .sort((a, b) => a.top - b.top);
  const bands = [];
  let start = topEdge();
  for (const r of sharing) {
    const end = Math.min(bottom, r.top - 6);
    if (end > start) bands.push({ top: start, bottom: end });
    start = Math.max(start, r.bottom + 6);
  }
  if (start < bottom) bands.push({ top: start, bottom });
  const minimum = composerOpen
    ? parseFloat(getComputedStyle(fabInput).minHeight)
    : node.offsetHeight;
  const candidates = bands
    .filter((band) => band.bottom - band.top >= minimum)
    .map((band) => {
      const height = Math.min(wantedHeight, band.bottom - band.top);
      const y = Math.max(band.top, Math.min(top, band.bottom - height));
      const distance = Math.max(target.top - y - height, y - target.bottom, 0);
      return { left: x, top: y, height, room: band.bottom - y, distance };
    });
  // Stay associated with the target, then keep as much writing visible as that band
  // allows. A distant gap is not a better seat just because it is taller. A target
  // filling the entire viewport leaves no free band, so the ordinary viewport clamp
  // remains the last resort.
  return (
    candidates.sort(
      (a, b) =>
        a.distance - b.distance ||
        b.height - a.height ||
        Math.abs(a.top - top) - Math.abs(b.top - top),
    )[0] ?? { left: x, top, room: bottom - topEdge() }
  );
}
let fabAnchor = null;
let fabOrigin = null;
let fabFloating = true;
const union = (rects) => {
  if (!rects.length) return null;
  const left = Math.min(...rects.map((rect) => rect.left));
  const top = Math.min(...rects.map((rect) => rect.top));
  const right = Math.max(...rects.map((rect) => rect.right));
  const bottom = Math.max(...rects.map((rect) => rect.bottom));
  return { left, top, right, bottom, width: right - left, height: bottom - top };
};
// A visual's durable anchor is also the geometry authority. Resolve it again after a
// reflow instead of remembering where inside the target the pointer happened to land.
function anchorBox(anchor) {
  let found;
  if (anchor?.quote) {
    const selection = pageSelection();
    const current = selection ? selectionAnchor(selection) : null;
    if (current && sameAnchor(anchor, current))
      return pageRange(selection).getBoundingClientRect();
    // Entering the compact field deliberately collapses the browser selection after
    // its durable passage has been captured. Resolve that passage again so layout can
    // keep the field beside it; an ordinary selection collapse still returns null and
    // lets updateFab dismiss the response surface.
    // The reactions palette temporarily owns focus and may itself be re-seated during
    // a responsive layout change. The open composer is the durable proof that this
    // captured passage still belongs to the response transaction; native selection is
    // no longer available once the textarea took focus.
    if (!composerOpen && !fabHoldsCapturedPassage()) return null;
    found = resolveAnchor(anchor, pageText());
    const segments = targetSegments(found);
    if (segments.length) {
      const range = document.createRange();
      range.setStart(segments[0].node, segments[0].start);
      range.setEnd(segments.at(-1).node, segments.at(-1).end);
      return range.getBoundingClientRect();
    }
    // Replacing source data must not close a draft about its prior revision. The
    // contextual placement keeps the field reachable beside its original section.
    if (found?.status !== "outdated") return null;
  } else found = anchor ? resolveAnchor(anchor, pageText()) : null;
  if (!targetElement(found)) return null;
  const clips = new Map();
  return union(
    targetParts(found)
      .map((part) => shownRect(part, clips))
      .filter(Boolean),
  );
}
// The passage remains the exact anchor, but its containing paragraph is not spare
// space: a short selection cannot lend the words after it to the response field.
// Keep the bar beside that whole block, or above/below it when the rail is too narrow.
function placeFab(target = anchorBox(fabAnchor)) {
  if (!fabAnchor || !target) return false;
  const room = rightEdge() - 8;
  // A covering workspace may leave no page band, or less than the controls can
  // shrink into. Report failed placement instead of assigning negative CSS sizes
  // and leaving a focused textarea behind that workspace.
  if (room <= 0) return false;
  const block = fabAnchor.quote && fabTargetAt();
  const clips = new Map();
  const keepClear =
    (block &&
      union(
        shownParts(block)
          .map((part) => shownRect(part, clips))
          .filter(Boolean),
      )) ||
    target;
  fabBar.style.setProperty("--lf-float-w", `${room}px`);
  if (composerOpen) {
    // CSS owns content sizing. Geometry contributes only the real room the field
    // can use, including the bar's other controls, before deciding where it stands.
    const controls = fabBar.offsetWidth - fabInput.offsetWidth;
    const besideRoom = rightEdge() - keepClear.right - 6 - controls;
    const minimum = parseFloat(
      getComputedStyle(fabInput).getPropertyValue("--lf-response-min-width"),
    );
    fabBar.style.setProperty(
      "--lf-response-room",
      `${Math.max(0, besideRoom >= minimum ? besideRoom : room - controls)}px`,
    );
  }
  if (!fabFits()) return false;
  const left =
    keepClear.right + 6 + fabBar.offsetWidth <= rightEdge()
      ? keepClear.right + 6
      : keepClear.right - fabBar.offsetWidth;
  // Read the field's scroll extent at its real width, without temporarily enlarging
  // it in either axis. A temporary enlargement reduces the scroll extent and clamps
  // scrollTop, so the captured scroll listener would make the last lines unreachable.
  const wantedHeight = composerOpen
    ? Math.max(
        fabBar.offsetHeight,
        fabInput.scrollHeight + fabInput.offsetHeight - fabInput.clientHeight,
      )
    : fabBar.offsetHeight;
  const at = placeClear(fabBar, left, target.top - 6, keepClear, wantedHeight);
  place(fabBar, at.left, at.top, at.room);
  return true;
}
export function showFab(
  anchor,
  target = null,
  { returnFocus = "target", origin = null, place = true } = {},
) {
  const previous = fabAnchor;
  const previousOrigin = fabOrigin;
  const leavingBar = !anchor && fabBar.contains(document.activeElement);
  const returnToPanel = leavingBar && panelCovers() && !fabFits();
  const returnTarget =
    leavingBar && previous && !previous.quote
      ? previousOrigin?.isConnected
        ? previousOrigin
        : previousOrigin
          ? visualActionAnchor(previous)
          : null
      : null;
  if (!anchor && composerOpen) hideComposer();
  fabAnchor = anchor;
  fabFloating = !fabAnchor || place;
  fabOrigin = fabAnchor && origin?.isConnected ? origin : null;
  fabBar.style.display = fabAnchor ? "inline-flex" : "none";
  fabInput.style.display = fabAnchor && composerOpen ? "block" : "none";
  const responses = fabBar.querySelector(":scope > .lf-react-trigger");
  if (responses) responses.hidden = !fabAnchor || !hasOtherResponses(fabAnchor);
  // Comment returns from the bar's choice state to this same field. At rest the input
  // itself is the comment affordance.
  fab.style.display = fabAnchor ? "" : "none";
  if (fabAnchor) {
    const label = anchorLabel(fabAnchor).replace(/^§\s*/, "");
    fabBar.setAttribute("aria-label", label ? `Respond to ${label}` : "Respond");
    fabInput.setAttribute("aria-label", label ? `Comment on ${label}` : "Comment");
    // The tokens already standing on this very anchor read pressed, and a press on one
    // takes it back (reactHere): the bar is the strip's shape on the page.
    paintReactionStanding(fabBar, reactionsOn(fabAnchor));
    // A docked margin control can name an item whose rendered box is currently off
    // screen. `r` still needs the durable anchor so it can extend that existing item;
    // in that route the floating bar is never painted and placement is deliberately
    // skipped. Every route that actually shows the bar keeps the geometry gate.
    if (place && !placeFab(target ?? anchorBox(fabAnchor))) {
      fabAnchor = null;
      fabOrigin = null;
      if (composerOpen) hideComposer();
      fabBar.style.display = "none";
      fabInput.style.display = "none";
      fab.style.display = "none";
    }
  }
  if (!sameAnchor(previous, fabAnchor)) paintAnchors();
  paintHere(); // the c row names this anchor, so the line is one more rendering of it
  if (!fabAnchor && returnFocus !== "none") {
    if (returnToPanel) threadsBox.focus({ preventScroll: true });
    else if (leavingBar && returnFocus === "target" && returnTarget?.isConnected)
      returnTarget.focus({ preventScroll: true });
    else if (
      leavingBar ||
      (returnFocus === "page" && document.activeElement === previousOrigin)
    )
      letGo();
  }
}
let dismissedSelectionKeyup = false;
export function dismissFab() {
  dismissedSelectionKeyup = Boolean(pageSelection() || fabAnchor?.quote);
  pageSelection()?.removeAllRanges();
  if (composerOpen) hideComposer();
  showFab(null);
}
export function refreshFab() {
  // A target row holds its anchor without floating the bar; layout cannot reject that
  // semantic place merely because the target's rendered box has scrolled away.
  if (!fabAnchor || !fabFloating) return;
  if (fabAnchor.quote && (composerOpen || fabHoldsCapturedPassage())) {
    if (!placeFab()) showFab(null, null, { returnFocus: "page" });
  } else if (fabAnchor.quote) updateFab();
  else if (!placeFab()) showFab(null, null, { returnFocus: "page" });
}
// The durable anchor names the authored coordinate an event can replay, while the
// margin needs the rendered block the gesture is visibly on. Those are deliberately
// different for selected words inside a paragraph without an ID: the event names its
// enclosing section, but both the temporary picker and the standing receipt sit at
// the paragraph. Match seatReactions' shadow-boundary rule so live and replay agree.
export const fabTargetAt = () => {
  if (!fabAnchor) return null;
  const found = resolveAnchor(fabAnchor, pageText());
  if (!found) return null;
  if (!fabAnchor.quote) return targetElement(found);
  const block = blockAt(targetSegments(found)[0]?.node);
  if (!block) return targetElement(found);
  const root = block.getRootNode();
  return root instanceof ShadowRoot ? root.host : block;
};
export const fabReturnTo = () =>
  fabAnchor && !fabAnchor.quote
    ? fabOrigin?.isConnected
      ? fabOrigin
      : visualActionAnchor(fabAnchor)
    : null;
// Every explicit target gesture ends here. The gesture has already resolved its stable
// authored anchor; this command owns the one transition from that target into Comment.
// Focusing the field drops any older browser selection, and an unsent draft follows the
// deliberate move. A visual proxy supplies its origin so Escape can return to it.
export function commentOnTarget({ anchor }, { origin = null } = {}) {
  clearTimeout(selectionUpdate);
  selectionUpdate = null;
  targetActivation = true;
  const selection = getSelection();
  if (selection?.rangeCount) selection.removeAllRanges();
  openComment(anchor, "", { carry: true });
  if (origin) showFab(anchor, null, { origin });
  setTimeout(() => {
    targetActivation = false;
  });
}
// Focusing text entry collapses a native page selection. Hold that browser-authored
// selectionchange out of updateFab: the durable anchor is already captured, and letting
// the collapse re-read it as no selection dismisses the field the reader just entered.
export function focusFabComment() {
  if (!fabAnchor) return;
  clearTimeout(selectionUpdate);
  selectionUpdate = null;
  fabInputTakingFocus = true;
  if (composerOpen) fabInput.focus({ preventScroll: true });
  else openComment(structuredClone(fabAnchor), "");
}
export const fabOptionsAvailable = () =>
  Boolean(fabBar.querySelector(":scope > .lf-react-trigger:not([hidden])"));
export function showFabOptions() {
  fabBar.querySelector(":scope > .lf-react-trigger")?.click();
}
// The response field follows the selection. What counts as one is measured on the quote it would
// store, not on the selection's own toString(): those are different strings, and gating on
// the one the reader sees while storing the one the document holds lets a two-character
// quote through behind a rendered three-character selection — a quote short enough to match
// almost anywhere.
const MIN_QUOTE = 3;

export function updateFab() {
  if (!anchoringIsReady()) {
    showFab(null);
    return;
  }
  const sel = pageSelection();
  const anchor = sel ? selectionAnchor(sel) : null;
  if (anchor?.quote.length >= MIN_QUOTE) {
    // A fast keyboard action can capture this completed native selection before the
    // pointer gesture's queued update arrives. That later update is the same target,
    // not a request to reopen its Comment composer: reopening calls closeReactions
    // and used to collapse choices immediately after `r` exposed them.
    if (sameAnchor(anchor, fabAnchor)) {
      placeFab();
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
// the capture reads the one the reader is looking at — and only for the primary
// button, because a right button's release precedes its context menu, and growing the
// selection there rewrites what Copy was aimed at.
//
// A queued step belongs to the gesture that queued it, and the next press may begin
// before it runs. Then the selection it would act on is not the one it was queued
// for: it is the drag under way, and `snapSelection` rewrites that drag mid-gesture.
// Chromium does not resume extending a selection it has been handed through
// `setBaseAndExtent`, so the pointer's remaining travel is lost and a sweep from
// "paragraph" to "carrying" ends up captured as "paragraph" — the reader's own hand
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
  clearTimeout(selectionUpdate);
  selectionUpdate = setTimeout(() => {
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
function openComment(anchor, text, options = {}) {
  // Chromium may collapse the native page Selection before dispatching the textarea's
  // focus event. Mark the handoff first so that intermediate selectionchange cannot
  // dismiss the durable anchor the composer is opening on.
  fabInputTakingFocus = options.focus !== false;
  return openComposer(anchor, text, options);
}
function fabHoldsCapturedPassage() {
  return fabInputTakingFocus || fabBar.contains(document.activeElement);
}
// Wired once the chrome is mounted (chrome.js): the box is selection.js's, an owner that
// imports this module back.
export function wireFabInput() {
  fabInput.addEventListener("focus", () => {
    clearTimeout(selectionUpdate);
    selectionUpdate = null;
    fabInputTakingFocus = true;
  });
  fabInput.addEventListener("blur", () => {
    fabInputTakingFocus = false;
  });
}
let primaryPointerPressed = false;
// Whether the page's own words stood selected when the key line was last painted for
// this press. The bar waits for the release; the Escape rung cannot, because from the
// first glyph a drag takes, Escape clears the selection rather than letting go of the
// control the reader is standing on, and until now nothing repainted the line inside a
// press — the word only became true when the frame the press itself scheduled happened
// to land after the drag had moved, and stayed a lie for a whole heartbeat when it
// landed before. Only the crossing is painted: a drag growing a selection that already
// stands says the same word, and repainting the chrome on every move of a drag would
// put a whole `paintHere` inside every frame of one.
let selectionStood = false;
const rememberPointerSelection = () => {
  const selection = pageSelection();
  const anchor = selection ? selectionAnchor(selection) : null;
  if (anchor?.quote?.length >= MIN_QUOTE)
    selectionRangeDuringPress = pageRange(selection).cloneRange();
};
document.addEventListener(
  "pointerdown",
  (ev) => {
    primaryPointerPressed = ev.isPrimary && ev.button === 0;
    if (primaryPointerPressed) pressesBegun++;
    pointerSelecting = primaryPointerPressed && pageWords(ev.target);
    selectionDragged = false;
    selectionRangeDuringPress = null;
    selectionGestureClaimed = false;
    selectionPressPoint = pointerSelecting ? { x: ev.clientX, y: ev.clientY } : null;
    // Read here, ahead of the browser's own collapse, so the first crossing this press
    // makes is measured against what the line already says rather than against nothing.
    selectionStood = Boolean(pageSelection());
    const selection = pointerSelecting ? pageSelection() : null;
    if (selection && pageRange(selection).intersectsNode(ev.target))
      rememberPointerSelection();
    actionPress = Boolean(ev.target.closest?.(".lf-react-surface, .lf-composer"));
  },
  true,
);
document.addEventListener("pointermove", (ev) => {
  if (!pointerSelecting || !selectionPressPoint) return;
  if (ev.defaultPrevented) {
    selectionGestureClaimed = true;
    return;
  }
  selectionDragged ||=
    Math.hypot(ev.clientX - selectionPressPoint.x, ev.clientY - selectionPressPoint.y) >
    3;
});
const finishPointerSelection = (ev) => {
  // A mouse pointer is followed by the compatibility mouseup below, which performs the
  // sentence snap before opening the field. Opening from pointerup first would focus the
  // textarea and collapse the still-unsnapped Selection before mouseup can finish it.
  // Touch/pen and cancellation owe us no compatibility mouse event, so they keep this
  // direct route.
  if (primaryPointerPressed && ev.type === "pointerup" && ev.pointerType === "mouse") {
    // Keep selectionchange in the in-progress branch until compatibility mouseup.
    setTimeout(() => {
      actionPress = false;
    });
    return;
  }
  if (primaryPointerPressed) scheduleSelectionUpdate();
  primaryPointerPressed = false;
  pointerSelecting = false;
  selectionGestureClaimed = false;
  setTimeout(() => {
    actionPress = false;
  });
};
document.addEventListener("pointerup", finishPointerSelection);
document.addEventListener("pointercancel", finishPointerSelection);
// Touch handles and browser selection commands do not owe the page a mouseup or keyup.
// During a pointer drag, the completed gesture below remains the one that snaps and
// places the passage; presses on the action surface must not retract their own target.
document.addEventListener("selectionchange", () => {
  if (primaryPointerPressed) {
    rememberPointerSelection();
    const stands = Boolean(pageSelection());
    if (stands !== selectionStood) {
      selectionStood = stands;
      paintHere();
    }
    return;
  }
  if (
    actionPress ||
    targetActivation ||
    fabHoldsCapturedPassage() ||
    takesLetters(document.activeElement)
  )
    return;
  scheduleSelectionUpdate();
});
document.addEventListener("mouseup", (ev) => {
  primaryPointerPressed = false;
  pointerSelecting = false;
  const gestureClaimed = selectionGestureClaimed;
  selectionGestureClaimed = false;
  if (gestureClaimed) {
    selectionRangeDuringPress = null;
    scheduleSelectionUpdate();
    return;
  }
  if (actionPress) return;
  if (!pageWords(ev.target) && !pageSelection()) return;
  const selection = pageSelection();
  const selected = selection ? selectionAnchor(selection) : null;
  const completed =
    selectionDragged && !(selected?.quote?.length >= MIN_QUOTE)
      ? selectionRangeDuringPress
      : null;
  deferSelectionUpdate(() => {
    if (completed) {
      const restored = getSelection();
      restored.removeAllRanges();
      restored.addRange(completed);
    }
    if (ev.button === 0) snapSelection();
    updateFab();
  });
});
// Selections made from the keyboard (shift-arrows, ⌘A) deserve the same response bar. Typing in
// a box never does, whatever is selected elsewhere.
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
// Floating chrome getting out of the way of a press somewhere else, which is a fact about
// the press rather than about who receives it: the aim takes a press away from the page
// (see claimPress) and must not take this with it, or the keyboard reference stays up over
// the composer that press just opened. Hence one function, called from both.
// The two side panels are absent from it on purpose. A float answers the press in front
// of it and stands down behind it; the thread panel and the leaves tray are
// workspaces the reader stood up, kept through a reload (PANEL_KEY, TRAY_KEY) and so
// through a click all the more — a tray any press removes cannot be watched while
// working, which is the tray's point. Each closes by its own button, its key, or Esc.
export function standDown(target) {
  const visual = visualAt(target);
  const sameVisual =
    visual &&
    !fabAnchor?.quote &&
    fabAnchor?.section === visual.id &&
    fabAnchor?.visual === visual.part?.id;
  if (
    !sameVisual &&
    !target.closest?.(".lf-react-surface, .lf-composer") &&
    !reactionContextContains(target)
  ) {
    if (composerOpen) hideComposer();
    showFab(null, null, { returnFocus: "page" });
    // The armed react press goes with the bar it was armed on.
    setReact(false);
  }
  if (referenceOpen() && !target.closest?.(".lf-help")) hideReference();
  if (!target.closest?.(".lf-help, .lf-keyline")) less();
  // The press on the button itself is its own toggle, so it is not an outside click;
  // without that the open and this close would both run and the menu could never open.
  if (versionMenuIsOpen() && !target.closest?.(".lf-version-menu, .lf-version"))
    closeVersionMenu();
}
// Document listeners see a shadow-tree press retargeted to its host. Read the
// composed origin so core controls seated in a widget surface remain inside their
// own composer/reaction layer instead of being dismissed before `click` can fire.
document.addEventListener("mousedown", (ev) => standDown(ev.composedPath()[0]));

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
document.addEventListener("click", (ev) => {
  if (!pageWords(ev.target)) return;
  // A press design mode did not take at the press is a press on prose: a drag that
  // selected words has the 💬 (updateFab, on the mouseup) and is not a click on the
  // block; a plain click comments on the block it landed in.
  if (designOn) {
    if (pageSelection()) return;
    const target = designTarget(ev.target);
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
  const threadId = markAt(point.x, point.y);
  if (threadId) return showThread(threadId);
});

export const fabAnchorAt = () => fabAnchor;
