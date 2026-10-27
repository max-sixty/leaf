/* Putting the user on an element: the focus, and the caret inside it, what the
   keyboard can focus, where a closing layer hands the user back, how a change
   that moves or replaces the node they are on keeps them there, and who moved them
   each time where they are changes (`onCurrentLocation`).

   This module is the one reader of where the user is. Every other reader of it,
   or of what moved them there, reads `onCurrentLocation`, whose causes are `return`,
   `press`, `step`, `move` and `drop`. A `focusin` listener on a node hears nothing of a
   move between two nodes of one shadow tree beneath it, which reaches it as no event,
   and each reader guessing for itself which moves were the runtime's own returns or
   the keyboard's arrivals answered the same question several ways. A layer waiting
   one frame for its return target releases a hidden focused control immediately;
   a newer input owns the page and cancels that pending return. The lint
   (`architecture/current-location-listeners`) refuses `focusin` and `focusout` elsewhere, and
   `focus` and `blur` on the document or captured anywhere, except in the few files it
   names: those that ask about one element or its own subtree, and the interaction
   log, which records events and reads no current location. Rejected: keeping each reader's
   listener and having stages re-dispatch their moves to the document, which leaves
   every reader's own reading of the cause.

   It is also the one place that moves them. Every focus the runtime and the packages
   place goes through `focusDestination(node, cause)`, which says whether it is a route
   or a return; the lint (`architecture/placements`) refuses a plain `focus()` elsewhere.
   Each owner once marked its own returns with a flag its own listener read, and a plain
   `focus()` that was a return published as the user's move to every other reader.
   Rejected: keeping wrappers around a placement (`returningFocus`, `placeChrome`) that a
   caller could forget, which is how those returns reached the readers as moves.

   And it exposes the document's input count and text-entry predicates, begun by
   prepaint.js before any module can load, so startup and runtime share their reading.
   Delayed work uses the count to know whether the user moved on since it began.
   A hold asks a different question, so the two counts stay distinct:

   - A hold (`holdFocus`, `holdCurrentLocation`, `handBack`'s retry) reads `placements`: has
     focus been put anywhere since, by the user or by an owner, other than by a hold's
     own restore or a closing layer's hand-back. Its question is whether the place it
     holds is still the user's, and the user typing, pressing or scrolling in that place
     is them working there: a hold that inputs voided would drop the user from the box
     they are typing in whenever a render replaced it.
   - Delayed work (`retainUserIntent`, user-intent.js) reads `inputCount`: has the user
     pressed, typed, scrolled, touched or left the window since the gesture that started
     it. Its question is whether that gesture is still their latest word, and any input
     is a newer one, wherever focus is; a move that only counted placements would
     pull the user back to its destination after they had gone on typing elsewhere.

   It also keeps the one reading of the press in progress (`pressing`, `onPress`), and
   the press on a label that leaves the user on the control they had focused until
   it lands (`focused`). Rejected: merging the two counts into one, which would void a
   hold on every keystroke; and each owner keeping its own press tracker, which is how
   holds came to read the in-between node a label press goes through.

   And it owns the widget primitives built on these: closing a layer and handing the user
   on as one act (`closeLayer`), holding a place in a keyed list (`holdFocus` with `key`),
   and a group's one Tab stop (`rove`).

   The selector vocabulary lives in control-selectors.js, which imports nothing.
   In a framed document, a sample's or any other, only the document already holding
   input may place focus: one the user has not entered would take them from the page
   around it. A top-level document always may, since placing focus in a background tab
   takes it from nobody. A trusted pointer or keyboard entry gives the frame that
   ownership before Leaf handles the gesture (bootstrap.js); arrival, the embedding
   page's navigation, remote commands and delayed work cannot borrow it from the
   parent. This is a rule for Leaf placements, not a restriction on authored browser
   scripts.

   Its dependencies are structural vocabulary, rendering and writes; importing a
   gesture owner would cycle through its focus dependency. */
import { afterScript, nextRender } from "./rendering.js";
import { signal } from "/vendor/signals-core.js";
import { keeps } from "./keeps.js";
import { MODIFIER_KEYS, TEXT_BOX, TAB_STOP } from "./control-selectors.js";
import {
  excludedByInert,
  isNativeLayer,
  renderedParent,
  renderedUnder,
  shadowHost,
} from "./shadow-tree.js";

// The elements under `node` in the tree as rendered: a host's shadow tree in place of
// its children, and a slot's assigned elements, or its fallback, in its place. A host
// its author took out of the order (a negative `tabindex`) takes its whole tree out
// with it, so Tab skips what it renders.
function* renderedElements(node) {
  const children =
    node.localName === "slot"
      ? node.assignedElements({ flatten: true })
      : (node.shadowRoot ?? node).children;
  for (const child of children) {
    yield child;
    if (child.shadowRoot && parseInt(child.getAttribute("tabindex")) < 0) continue;
    yield* renderedElements(child);
  }
}
const SEQUENTIAL = `${TAB_STOP}, iframe, audio[controls], video[controls]`;
// The controls inside `root` that take a Tab stop right now, through open shadow trees as
// rendered: the candidates above and the embedded documents and players Tab enters, in
// the order, enabled, and drawn. A host that delegates its focus is no stop of its own,
// since Tab enters its tree. Which of them Tab visits, and in what order, is the
// browser's; nothing here predicts its walk.
export const tabStops = (root) =>
  [...renderedElements(root)].filter(
    (node) =>
      node.matches(SEQUENTIAL) &&
      node.tabIndex >= 0 &&
      !node.shadowRoot?.delegatesFocus &&
      !node.matches(":disabled") &&
      !node.inert &&
      node.checkVisibility({ visibilityProperty: true }),
  );

// Put the user on an element, saying what moved them there. Every focus the runtime and
// the packages place goes through here (the lint `architecture/placements` refuses a
// plain `focus()` elsewhere), because the call is the only place that knows whether it
// is the user going somewhere or the runtime handing them back, and every reader of
// where they are (`onCurrentLocation`) needs that word: a return that published as a move
// released held news, opened a cluster's options and chose a card the user never went
// to. The cause is one of:
//
// - `move`: a route taking the user somewhere, whether a key or a press began it;
// - `step`: standing in for Tab or Shift+Tab;
// - `return`: putting the user back where they came from or handing them across, a
//   closing layer's hand-back, a re-render carrying them to the node that replaced the
//   one they were on, a chrome placement moving the box they are in;
// - `press`: landing on a control to press it on the user's behalf, as a go-to that
//   presses a control does: the readers take it as the platform's focus for a press,
//   which asks for what it lands on and opens nothing on arrival.
//
// A focus that runs inside another placement, as a component's own focus handler
// forwarding to its selected child does, is part of that placement and takes its cause.
// A reader of where the user is that moves them answers a reading, not the
// placement that caused it, so its own placement names its own cause.
//
// The element may not be a tab stop: where it will not take focus, lend it the tab stop
// a control has for exactly as long as it holds it —
// the lend leaves when focus leaves it within the document, so a paragraph the Go-to
// sequence landed on is a paragraph again once the user moves off it, and `tabindex`
// never becomes a thing the runtime leaves behind on an author's element. An element
// that already declares a stop keeps its own. What wants this is an arrival at an
// element nobody owns — a go-to hint completing on a fold, a heading or a link's
// fragment; the reference handing a user back to the block they were reading; the skip
// link landing on the floating panel when none of its controls will take them. Each is "the
// user is now here", and each needs the browser's sequential focus navigation starting
// point to move with them, which is what `focus()` does and what nothing else does.
//
// A caret is where the user is inside the element they are on, so it arrives with them.
// An arrival that is a return — a bar moved between two parents, a seat re-rendered, a
// thread reconciled, a replaced document handing back the place the user was in —
// reads the caret with `readCaret` before its element goes away and passes it here, so
// that the focus and the place inside it land in one act rather than in two. Passing no
// caret leaves the platform's, which is what a first arrival wants.
//
// Placements never ask the browser to reveal their target: native focus scrolling
// crosses browsing contexts. A caller needing reveal uses document-local scrolling.
export const canPlaceFocus = () => window === window.top || document.hasFocus();
const CAUSES = new Set(["move", "step", "return", "press"]);
export function focusDestination(
  destination,
  cause,
  { caret = null, ...unknown } = {},
) {
  if (!CAUSES.has(cause)) throw new TypeError(`focusDestination: no cause ${cause}`);
  const unexpected = Object.keys(unknown);
  if (unexpected.length)
    throw new TypeError(`focusDestination: unknown options ${unexpected.join(", ")}`);
  if (!canPlaceFocus()) return;
  // Firefox otherwise inherits a pointer arrival's invisible focus through a
  // keyboard route, including a composer return. Ask the platform to show that
  // destination; pointer routes keep its own visibility heuristic.
  const options = {
    preventScroll: true,
    focusVisible: pressLed() ? undefined : true,
  };
  placed(cause, () => {
    destination.focus(options);
    if (!landedOn(destination) && lendable(destination)) lendStop(destination, options);
  });
  if (caret && holdsCaret(destination)) destination.setSelectionRange(...caret);
}
// The cause of the placement running now, null outside one. The outermost placement
// names it, since whatever focus runs inside it is part of the same act.
let placing = null;
const placed = (cause, move) => {
  const was = placing;
  placing ??= cause;
  try {
    return move();
  } finally {
    placing = was;
  }
};

// Whether focus is on `node`, or inside a shadow tree it hosts, as it does inside a
// text field's editor: the field is where the user is. A light child of it is somewhere
// else, so a container a placement lands on is landed on itself. The body is its
// document's active element whenever nothing is focused, so only `:focus` says it holds
// focus.
const landedOn = (node) =>
  node === document.body
    ? node.matches(":focus")
    : node.getRootNode().activeElement === node ||
      Boolean(node.shadowRoot?.activeElement);

// A stop is lent only to a drawn element that is no control of its own: a control that
// would not take focus is disabled, inert or hidden, and a stop would not change that.
const lendable = (node) => drawn(node) && !node.matches(TAB_STOP);

// The elements wearing a stop lent here, which is no part of what their author wrote.
const lent = new WeakSet();
export const wearsLentStop = (element) => lent.has(element);

// Run `leave` once, when the user moves off `element` within the document. A window
// losing system focus blurs the element too, but leaves it the document's focused
// area, and the platform hands focus back to it when the window returns; any other app
// taking key focus for a moment does it, such as macOS's dialog verifying a newly
// installed binary. That blur is not the user moving off, and what is held for as long
// as they are on the element is held through it. During every other blur, the element
// is no longer its root's activeElement: `el.blur()`, and focus moving to another
// element in light or shadow DOM, in Chromium, Firefox and WebKit.
export function whenLeft(element, leave) {
  const blur = () => {
    if (element.getRootNode().activeElement === element) return;
    element.removeEventListener("blur", blur);
    leave();
  };
  element.addEventListener("blur", blur);
}

function lendStop(destination, options) {
  if (destination.hasAttribute("tabindex")) return;
  // Only the `-1` lent here is taken back: a box that came to scroll meanwhile wears
  // the reach pass's stop (reach.js), which is that pass's to take. Taking it back
  // while the element is still focused makes it unfocusable under the user, and the
  // browser drops them to the body.
  const giveBack = () => {
    lent.delete(destination);
    if (destination.getAttribute("tabindex") === "-1")
      destination.removeAttribute("tabindex");
  };
  lent.add(destination);
  destination.tabIndex = -1;
  destination.focus(options);
  if (!landedOn(destination)) {
    giveBack();
    return;
  }
  whenLeft(destination, giveBack);
}

// The input types whose selection the platform will answer for. Reading `selectionStart`
// on any other throws rather than returning null.
const CARETED = new Set(["text", "search", "url", "tel", "password"]);
const holdsCaret = (node) =>
  node.matches(TEXT_BOX) || (node.tagName === "INPUT" && CARETED.has(node.type));

// Where the user is inside an element, or null where the element holds no caret. The
// reading is a plain triple so that it can be stored and read back in another document.
export function readCaret(node) {
  if (!node || !holdsCaret(node) || node.selectionStart === null) return null;
  return [node.selectionStart, node.selectionEnd, node.selectionDirection];
}

// The element holding focus, followed down through every open shadow tree containing it
// from `at`. A closed tree answers with its host, which is the text field's case: the
// field is the box the user is in.
export const deepFocus = (at = document.activeElement) => {
  while (at?.shadowRoot?.activeElement) at = at.shadowRoot.activeElement;
  return at;
};

// A press on a label can blur the element the user was on to the body, or let a
// containing thread take focus, before the platform focuses the label's control at its
// click. Those in-between nodes are no new current location: until the press lands, the user
// remains on the previously focused element, for every reader of where they are, every hold
// and every key. The press leaves DOM focus alone and keeps the platform's default, so a
// drag still selects a label's words. The current location's focus paint stays on that held
// element and its composed ancestry until the press lands.
//
// It lands at the label's click, whose default focuses the control, which a tap delivers
// after its release, or at a release off the label, which no click on it follows, or at
// a native menu, which swallows the release. A cancel, the window losing focus, a key
// (which puts the user back on the held element) and a runtime placement each end it
// too. A second contact meanwhile is no part of it.
let labelPress = null;
const heldByLabel = () => (labelPress?.held.isConnected ? labelPress.held : null);
function finishLabelPress() {
  const press = labelPress;
  if (!press) return null;
  labelPress = null;
  return press;
}
// Current location is read once more a task after the press lands, when the control's focus at
// the click has been read: a press that left the user on a node no reading told, or
// nowhere, as a label whose control takes no focus does, is the user's own move.
function landLabelPress() {
  if (!finishLabelPress()) return;
  setTimeout(() => {
    if (labelPress) return;
    const at = deepFocus();
    if (at && at !== document.body) return reconcile(null, pressedPath);
    if (!drawn(published?.deref())) return;
    placements += 1;
    lastLocation = null;
    publish(null, cause(null));
  });
}

// Where the user is: the element holding focus, inside any open shadow tree, or the
// element a press on a label holds them on. Asked in `tree`, a document or shadow root,
// it is the node standing for that place there, as `tree.activeElement` retargets focus:
// the host of the shadow tree the user is in, for a reader comparing or containing
// nodes of that tree. Every reading of focus outside this module asks here, so none
// misses a label press or a shadow tree (eslint's `architecture/current-location-reads`).
// Keyboard reflection follows this revision explicitly. Mechanical focus queries made
// while rendering stay untracked, so restoring focus cannot subscribe a render to itself.
const currentLocation = signal(0);
export const focusRevision = () => currentLocation.value;
export const focused = (tree = null) => {
  let at = heldByLabel() ?? deepFocus();
  if (tree) while (at && at.getRootNode() !== tree) at = shadowHost(at.getRootNode());
  return at;
};

// The selection the user drew in the tree containing `node`, where the browser keeps it.
const selectionOf = (node) => {
  const root = node.getRootNode();
  // Only Chromium's shadow roots answer their own selection; Firefox and WebKit
  // keep it on the document.
  const own = /** @type {{getSelection?: () => Selection}} */ (root);
  return (root instanceof ShadowRoot && own.getSelection?.()) || getSelection();
};

// Where the user is, nearest first: the focused node, unless focus rests on the
// body, then the ends of a selection they drew, its focus before its anchor, a caret a
// click left included, since a selection names where a reader is as surely as focus
// does. Each reader takes these by its own rule: the first that is a place on the page
// (`currentLocationOrigin`, current-target.js), or any that lies in a node (`currentLocationTouches`).
export function currentLocationNodes() {
  const at = focused();
  const selection = getSelection();
  return [
    at && at !== document.body ? at : null,
    selection?.focusNode ?? null,
    selection?.anchorNode ?? null,
  ].filter(Boolean);
}

// Whether the user is on `node` or on something in it: where they are
// (`currentLocationNodes`) is inside it, or a selection they drew reaches into it. A change
// that puts `node` away would take that place from them.
export function currentLocationTouches(node) {
  if (!node) return false;
  if (currentLocationNodes().some((at) => at === node || node.contains(at)))
    return true;
  const selection = selectionOf(node);
  return Boolean(selection?.rangeCount && selection.getRangeAt(0).intersectsNode(node));
}

// Holding the user's place across a change to the tree they are in. Moving a node
// blurs whatever it holds to the body in the same call, and hiding one does the same a
// frame later, on no frame an owner can count; the node keeps its value and selection,
// but the user's current location on it is gone. Focus lives as long as its node, so whatever
// moves, hides or replaces nodes under the user hands their place across itself:
// `holdFocus(scope)` reads where the user is inside `scope` before the change, with
// the caret there, and the function it returns puts them back.
//
// The held node comes first. Where the change removed or hid it, the caller names its
// stand-ins, most particular first: the replacement keyed on the identity the held node
// had, then the widget's own fallback. The user lands on the first that is drawn and
// takes focus, and the caret goes with them, since a stand-in is the same place under a
// new node. A stand-in may be a function, called only if the ones before it fail, since
// finding it may itself put something up, such as the card a thread moved to. Returning
// an element makes it the same place under a new node, and the caret goes there too. A
// stand-in that is somewhere else, such as the reply of the thread a seat's box gave way
// to, is the caller's own landing: it puts the user there its own way, takes no caret,
// and returns `true` where it did. Restoring answers whether the user is now on one
// of them.
// An asynchronous stand-in returns its actual landed element. Only that still-focused
// destination can receive the held caret; its owner retains permission across the wait.
//
// Nothing is owed while the user is still on the held node and it is drawn, and
// nothing once focus has been placed anywhere since the hold began: a user who moved on
// during a wait, or an owner inside the change that landed them itself, said the newer
// word, as with `handBack`. A restore putting the user back in the place it held is not
// a newer word, so holds nest; a function stand-in is the owner's own act, and wherever
// it moves focus is a placement to every other hold.
//
// A change can also run before the owner that hands the user on: a widget rebuilding
// its tree drops the box a later pass draws again elsewhere, and focus is on the body
// before any hold is read. So a hold read while the user has no current location holds the node
// that change dropped them from, while it is not drawn and they have neither been placed
// nor acted since.
//
// `null` where the user is not, and was not dropped from, inside `scope`, which
// may be a shadow root or a node already taken out of the document. The platform's
// retargeting answers that: a user inside a widget's shadow tree is inside the scope
// holding the widget.
//
// A hold is a reading and nothing more, so one its caller never restores, such as a
// batch's that commits, costs nothing: the one listener below counts placements for
// every hold, and a hold compares the count it began at.
//
// Which placements are a newer word: every one but a hold's own restore and a closing
// layer's own hand-back. A hold putting the user back in the place it held is not, so
// holds nest. A layer handing focus back to its opener as it closes, as an auto popover
// does when a re-render takes its strip away, is the layer's and not the user going
// anywhere, so the hold still waiting on that re-render keeps its place. A closer that
// names where the user goes (`handBack`, or any `return` placed here) has decided, and a
// hold waiting gives way to it.
let restoring = false;
let placements = 0;
// The user’s last location. A change that removes or hides the node they are on puts
// focus on the body and fires no `focusin`, so this still names that node afterwards.
// A move between two nodes of one shadow tree reaches the document as neither event, so
// each entered root reads its own `focusin` (`watchCurrentLocationIn`), and the node focus leaves for
// nowhere is read off the path of the `focusout` that says so. Every later placement
// writes it again, so it names a place nothing has placed the user away from.
//
// The user acting while they have no current location, a key, a press, a wheel, a touch, is them
// going on from there, so the dropped place is forgotten: a later owner putting them
// back in it would take them from whatever they went on to. While they still have a current location, the same inputs are them working there, and change nothing.
// A removed place remains available to its replacement, but owns no node lifetime.
let lastLocation = null;
// Every change to where the user is goes to each reader `onCurrentLocation` names, as
// `read(node, cause, left)`: the node they are now on, null where they are nowhere;
// what moved them there; and the node the readers last heard they were on, null where
// that was nowhere or the removed node has been collected. The causes:
//
// - `return`: the runtime putting them back or handing them across: a placement that
//   says so (`focusDestination`), a hold restoring its place (`holdFocus`,
//   `holdCurrentLocation`), a closer handing them back (`handBack`), or the platform handing
//   focus back from a layer it closed, as a dialog closed with Escape does;
// - `press`: focus landing on the node the user's last press was on, or on a control
//   holding it, before a key follows: the platform's own focus for the press, which asks
//   for what it lands on; or a placement landing on a control to press it on the user's
//   behalf (`focusDestination`), which asks the same;
// - `step`: sequential navigation, Tab or Shift+Tab, whether the browser moves them or
//   a placement stands in for it;
// - `move`: a placement taking them somewhere, or anything else, whether a key or a
//   press began it (`pressLed` says which);
// - `drop`: a change hid or removed the node they had focused, and focus fell to the body,
//   read as `null`. The dropped place is still where they are for every hold, and the
//   one to put them back is the owner of the change, so a reader of where they are
//   lets it pass; what it tells is that the node holding focus is gone from the screen,
//   which a reader painting focus answers.
// The reading is synchronous, inside the `focus()` that moved
// them and ahead of every listener below the document or the stage, so a reader that
// redraws on it does so before the route that moved them measures its landing. A
// reader that moves them itself starts a newer reading, and the older one goes to no
// reader after it, so none hears the two out of order.
//
// Focus that leaves a node for another and comes back to it is a new arrival there,
// though the readers never heard it leave: the Threads list given focus hands it on to
// the title the user was already on, inside the list's own `focus`, before the
// list's `focusin`. A focus that leaves for nowhere and returns, as a window losing
// and regaining focus does, is none.
const readers = new Set();
export const onCurrentLocation = (read) => {
  readers.add(read);
  return () => readers.delete(read);
};
let published = null;
let departed = false;
let readings = 0;
// Paint follows the same current location as keyboard routing. Native :focus also matches
// retargeting shadow hosts and the intermediate node of a held label press, neither
// of which receives that input. Dedicated attributes leave component classes with
// their owners. Public shadow parts expose both marks too, so vendor-part rules
// can choose a carrier on the actual focus ancestry rather than its whole host.
// Current location is synchronous, but its paint uses the gesture's final destination:
// a layer can return focus in one microtask and move it again in another during one
// gesture. Painting those intermediate arrivals would restore unchanged marks.
let paintDestination = null;
let paintedFocus = null;
let paintedWithin = new Set();
let paintedVisible = null;
let paintedVisibleWithin = new Set();
// Modality can change the cue without moving the destination. Paint readers need
// that change too; navigation readers must not hear it as another focus move.
const visibilityReaders = new Set();
export const onFocusVisibility = (read) => {
  visibilityReaders.add(read);
  return () => visibilityReaders.delete(read);
};
function markFocus(node, name, present) {
  keeps(node, `data-lf-${name}`, present ? "" : null);
  // Removing an absent token still rewrites the attribute.
  if (!present) {
    if (node.part?.contains(`lf-${name}`)) node.part.remove(`lf-${name}`);
  } else if (
    node.getRootNode().nodeType === Node.DOCUMENT_FRAGMENT_NODE &&
    node.hasAttribute("part")
  )
    node.part.add(`lf-${name}`);
}
// The keyboard cue's destination, read before or after its attributes are painted.
// Current location and its visibility are separate: a click keeps a control as the
// keyboard destination without advertising a keyboard cue. The browser owns
// focus-visible (including text entry and modality changes on the same node).
// Closed text-field roots expose their host, not the focused editor; text
// entry always needs a cue, as it does for native editors. A frame never matches
// :focus-visible on its host, so it takes the platform's rule from the inputs: visible
// unless a press put the user there (`inputInFrame`).
export function visibleFocus(node = focused()) {
  return node &&
    node !== document.body &&
    node !== document.documentElement &&
    (node.matches(":focus-visible") ||
      node.matches(TEXT_BOX) ||
      (node.localName === "iframe" && !pressLed()))
    ? node
    : null;
}
function paintFocus(node) {
  const next =
    node === document.body || node === document.documentElement ? null : node;
  if (next !== paintedFocus) {
    if (paintedFocus) markFocus(paintedFocus, "focus", false);
    if (next) markFocus(next, "focus", true);
    paintedFocus = next;
  }
  const within = new Set();
  // The document roots are in every element's ancestry, but no control draws
  // their marks. Leaving them out also avoids withdrawing and restoring the
  // same root marks when focus passes through a native drop in one gesture.
  for (
    let owner = next;
    owner && owner !== document.body && owner !== document.documentElement;
    owner = renderedParent(owner)
  )
    within.add(owner);
  for (const owner of paintedWithin) {
    if (!within.has(owner)) markFocus(owner, "focus-within", false);
  }
  for (const owner of within) {
    if (!paintedWithin.has(owner)) markFocus(owner, "focus-within", true);
  }
  paintedWithin = within;
  const visible = visibleFocus(next);
  if (visible !== paintedVisible) {
    if (paintedVisible) markFocus(paintedVisible, "focus-visible", false);
    if (visible) markFocus(visible, "focus-visible", true);
    paintedVisible = visible;
    for (const read of visibilityReaders) read();
  }
  const visibleWithin = visible ? within : new Set();
  for (const owner of paintedVisibleWithin) {
    if (!visibleWithin.has(owner)) markFocus(owner, "focus-visible-within", false);
  }
  for (const owner of visibleWithin) {
    if (!paintedVisibleWithin.has(owner))
      markFocus(owner, "focus-visible-within", true);
  }
  paintedVisibleWithin = visibleWithin;
}
// Retained moves preserve native focus without emitting a focus event. Recompute
// only its derived ancestry when the rendered tree changes, including slot moves.
// Attribute paint is outside this observation, so it cannot schedule itself.
//
// A destination still drawn into the tree but no longer holding focus, and not held
// by a label press, has had focus leave it for nowhere, and the `focusout` reading
// that decides whether that was a drop or a move has yet to run. Its ancestry is no
// current location until then, so the paint keeps what it drew and that reading repaints:
// painting the node where a change has just moved it would draw marks the reading
// takes straight back off.
const refreshFocusPaint = () => {
  const node = paintDestination?.deref();
  if (node?.isConnected && node !== deepFocus() && node !== heldByLabel()) return;
  if (node?.isConnected) watchCurrentLocationAround(node);
  paintFocus(node?.isConnected ? node : null);
};
let returnPaintPending = false;
const paintAfterScript = () => {
  if (!returnPaintPending) refreshFocusPaint();
};
const queueFocusPaint = () => afterScript(paintAfterScript);
const queueReturnFocusPaint = () => {
  if (returnPaintPending) return;
  returnPaintPending = true;
  nextRender(() => {
    if (!returnPaintPending) return;
    returnPaintPending = false;
    refreshFocusPaint();
  });
};
const paintRoots = new WeakSet();
function watchFocusPaintIn(root) {
  if (paintRoots.has(root)) return;
  paintRoots.add(root);
  new MutationObserver(queueFocusPaint).observe(root, {
    childList: true,
    subtree: true,
  });
  root.addEventListener("slotchange", queueFocusPaint);
}
function publish(node, cause) {
  watchCurrentLocationAround(node);
  paintDestination = node && new WeakRef(node);
  // A command-reference return may precede the command's own focus move in this
  // gesture. Its ring waits for the frame; a forward move supersedes that return
  // and still paints after the current script, before the next frame is shown.
  if (cause === "return") queueReturnFocusPaint();
  else {
    returnPaintPending = false;
    queueFocusPaint();
  }
  if (node === (published?.deref() ?? null) && !departed) return;
  departed = false;
  const left = published?.deref() ?? null;
  const reading = ++readings;
  currentLocation.value = reading;
  // A drop leaves the place where readers last heard the user was, so the next
  // reading, the owner putting them back there included, is told against it.
  if (cause === "drop") departed = true;
  else published = node && new WeakRef(node);
  if (node) placeInput = "focus";
  // What a reader places is its own act: it names its own cause, and it is a newer word
  // to a hold even inside a hold's restore.
  const was = [placing, restoring];
  [placing, restoring] = [null, false];
  try {
    for (const read of readers) {
      // Each reader answers alone: one that throws is reported and the rest still hear.
      try {
        read(node, cause, left);
      } catch (error) {
        reportError(error);
      }
      if (readings !== reading) return;
    }
  } finally {
    [placing, restoring] = was;
  }
}
// The press the user last made, as weak readings of the nodes under it, until a
// key follows it. Remembering the input modality does not own the old markup.
let pressedPath = null;
// Whether a node is what that press asked for: a node under it, or the control of a
// label under it, which the platform focuses at the press's click.
const pressedOn = (node) =>
  Boolean(pressedPath) &&
  pressedPath.some((ref) => {
    const at = ref.deref();
    return at === node || (at?.localName === "label" && at.control === node);
  });
// Whether the user's latest input was a press rather than a key, so that a `move` is a
// route a press began: what the platform's `:focus-visible` guesses from, read here
// from the inputs themselves. No input yet reads as no press.
export const pressLed = () => pressedPath !== null;
// The Tab the user is pressing, from its keydown until the task that moves them ends.
let stepping = null;
// Focus coming out of a dialog or popover that no longer stands is that layer handing it
// back as it closes, whether the platform or the layer's owner moves it. A nonmodal
// dialog closing hands focus back too, so a dialog stands while it is `open`, modal or
// not, and a popover while it is a native layer.
const leftClosedLayer = (left) => {
  const layer = left?.closest?.("dialog, [popover]");
  return Boolean(layer) && !(layer.open === true || isNativeLayer(layer));
};
const cause = (node, left = null) =>
  placing ??
  (leftClosedLayer(left)
    ? "return"
    : pressedOn(node)
      ? "press"
      : stepping
        ? "step"
        : "move");
// One move fires once at the document and again at each stage it crosses into.
const read = new WeakSet();
function readFocusEvent(event) {
  if (read.has(event)) return;
  read.add(event);
  // A closing layer’s temporary focus is not a new current location (`closeLayer`).
  if (closing) return;
  // A node briefly focused during a label press is not a new current location; a
  // runtime placement during the press ends it.
  if (heldByLabel()) {
    if (placing === null) return;
    finishLabelPress();
  }
  if (!restoring && !(placing === null && leftClosedLayer(event.relatedTarget)))
    placements += 1;
  const at = deepFocus();
  lastLocation = at && new WeakRef(at);
  publish(at, cause(at, event.relatedTarget));
}
// Entering a component subscribes this owner to its subsequent internal moves.
// Those moves do not reach the document; guessing them at the next input would
// make their cause depend on the old node's later ancestry and lifetime.
function watchCurrentLocationAround(node) {
  for (let at = node; at; at = renderedParent(at))
    watchCurrentLocationIn(at.getRootNode());
}
// A shadow root reads the moves inside it, which reach the document as no event.
// Subscribe on captured focus, before a component's handler forwards first entry
// within its root and suppresses the original focusin. Stages can subscribe earlier;
// retained moves without an event subscribe through the paint ancestry reading.
function enter(event) {
  if (read.has(event)) return;
  read.add(event);
  watchCurrentLocationAround(deepFocus());
}
export function watchCurrentLocationIn(root) {
  root.addEventListener("focus", enter, true);
  root.addEventListener("focusin", readFocusEvent, true);
  watchFocusPaintIn(root);
}
watchCurrentLocationIn(document);
watchCurrentLocationAround(deepFocus());
// Leaving for nowhere from a node still drawn is the user's own move, and so a
// placement: body holds no stop, so a press on the page's words takes focus off the
// control and puts it nowhere with no `focusin` to count, and a hold still waiting
// would pull the user back from the words they chose. It is not a drop either, so the
// node is forgotten as where they were: a later change removing it drops nobody. A node
// a change hid or replaced is not drawn once it blurs, which leaves it the dropped place
// above rather than a move, and a window losing focus leaves the document's focus where
// it was.
document.addEventListener(
  "focusout",
  (event) => {
    if (event.relatedTarget !== null) {
      departed = true;
      return;
    }
    const left = event.composedPath()[0];
    lastLocation = new WeakRef(left);
    if (restoring) return;
    queueMicrotask(() => {
      const at = document.activeElement;
      if (at !== null && at !== document.body) return;
      if (heldByLabel()) return;
      if (!drawn(left)) return publish(null, "drop");
      // A borrowed body stop leaving for nowhere is the release itself, not
      // another placement after the caller began waiting for its return.
      if (left !== document.body) placements += 1;
      if (lastLocation?.deref() === left) lastLocation = null;
      publish(null, cause(null));
    });
  },
  true,
);
// A Tab moves the user as its keydown's default action, in the same task, and a handler
// standing in for the browser moves them inside the keydown itself, so the step ends
// with the task; holding Tab down repeats the keydown and so the step.
const sequential = (event) =>
  event.key === "Tab" && !event.altKey && !event.ctrlKey && !event.metaKey;
// Where the user is, read again once a key's or a press's task ends, and once a
// click's does, since a tap focuses at the click that follows it rather than at its
// press. A component's roots join current location observation when focus first enters them;
// the final input reading also covers a label's held intermediate move. Leaving for
// nowhere is the `focusout` reading's, except from a frame, which focus leaves with no
// event here when a press on this document takes it back.
function reconcile(step, pressed) {
  if (heldByLabel()) return;
  const deep = deepFocus();
  const at = deep === document.body ? null : deep;
  const was = published?.deref() ?? null;
  if (at === was || (!at && was?.localName !== "iframe")) return;
  placements += 1;
  lastLocation = at && new WeakRef(at);
  const input = [stepping, pressedPath];
  [stepping, pressedPath] = [step, pressed];
  try {
    publish(at, cause(at));
  } finally {
    [stepping, pressedPath] = input;
  }
}
// A press inside a frame goes to the frame's document, and focus follows it there with
// no event here: Firefox fires none at all, and Chromium only the window's `blur`. The
// frame's owner hears of each input from the frame's document, by its event `type`, and
// reports it here. A key or a press there is the user's latest input, which decides
// whether the frame wears its ring, and one that left focus in a frame the user was not
// yet on, which only a press does without an event here, puts them on the frame as a
// Tab into it would have.
export function inputInFrame(frame, type) {
  if (deepFocus() !== frame) return;
  if (type === "keydown") pressedPath = null;
  else if (type === "pointerdown" || type === "touchstart")
    pressedPath = [new WeakRef(frame)];
  if (published?.deref() === frame) queueFocusPaint();
  else reconcile(null, pressedPath);
}
addEventListener(
  "click",
  () => {
    const pressed = pressedPath;
    setTimeout(() => {
      reconcile(null, pressed);
      queueFocusPaint();
    });
  },
  { capture: true, passive: true },
);
// The user's inputs, counted: a key, a press, a wheel, a touch, text entered, or the
// window losing focus, as find-in-page takes it. Delayed work compares the count it
// began at (user-intent.js), as a hand-back waiting a frame for its target does. A scroll is none of these: the runtime's own landings fire
// it, and each of the user's ways of scrolling begins with one that is.
const inputs = document.documentElement.lfInputs;
export const inputCount = () => inputs.count;
// Mechanical owners may stop motion at the input edge, before a command or drawing
// handler consumes it. Observation adds no binding and never claims the event.
export const onUserInput = (read) => inputs.observe(read);

// Where the caret was, as a key went down, in each box the key went down in, before
// the box's own handling moved it. A command whose meaning hangs on the caret's place,
// as ↑ from the start of a box walks out of it, reads this rather than the caret the
// field has already moved by the time the command's row is asked. It holds until the
// task after the key's, so a row read outside a key falls back to the live caret.
let keyCarets = null;
onUserInput((event) => {
  if (event.type !== "keydown") return;
  const carets = new Map();
  for (const node of event.composedPath()) {
    const caret = node instanceof Element && readCaret(node);
    if (caret) carets.set(node, caret);
  }
  keyCarets = carets;
  setTimeout(() => {
    if (keyCarets === carets) keyCarets = null;
  });
});
export const caretAtKey = (node) => keyCarets?.get(node) ?? null;
onUserInput((event) => {
  if (event.type !== "blur") return;
  landLabelPress();
  endPress(event, false);
});

// Which input last named a place to keep in a reflow: a pointer moving, pressing or
// wheeling over an item, or the keyboard, whose arrivals name the item focus is on.
// It chooses which visible item holds a reflow, and supersedes no delayed move.
let placeInput = "focus";
for (const type of ["pointermove", "pointerdown", "wheel"])
  addEventListener(type, () => (placeInput = "pointer"), {
    capture: true,
    passive: true,
  });
// A repeated click can choose the focused destination without moving focus.
addEventListener(
  "click",
  (event) => {
    if (event.isTrusted && event.button === 0)
      placeInput = focused()?.contains(event.composedPath()[0]) ? "focus" : "pointer";
  },
  { capture: true, passive: true },
);
export const recentPlaceInput = () => placeInput;

// The primary pointer's press, from its `pointerdown` until it ends: its pointer and the
// nodes under its start, read after the event has gone, when the platform no longer
// reports its path. `onPress(start, path)` hears each press begin and returns what
// hears it end, as `end(event, completed)`. A release completes it. Every other end does
// not: a cancel, which the browser sends when it took the press for something else,
// commonly a touch scroll; a native menu the press opened, which swallows the release;
// and the window losing it altogether. So a gesture judged where it starts and acted on
// where it ends reads both from one press.
let press = null;
export const pressing = () => press;
const pressReaders = new Set();
// Returns what stops hearing presses, for an owner torn down before the page is.
export const onPress = (read) => {
  pressReaders.add(read);
  return () => pressReaders.delete(read);
};
// A press away from a surface puts it away: a primary press that begins outside it and
// completes outside it, `away(path)` reading each end's composed path. That is how the
// platform judges its own light dismissal (a popover's, a dialog's `closedby`), so a
// drag that starts outside and ends inside, or inside and ends outside, leaves the
// surface open, a touch scroll the browser cancels puts nothing away, and a finger and
// a mouse are one route. A secondary press, which opens a context menu on one platform
// before its release and after it on another, puts nothing away. The surface goes as
// the press completes, after the press's own handlers have read the scene it began in,
// and before its click, which may open what replaces it; `dismiss(path, from)` hears
// both ends' paths. Every surface that goes on a press elsewhere goes by this, rather
// than by a listener of its own on `pointerdown`, `mousedown` or `click`, each of which
// judged a different press. A surface decides for itself whether a press a pointer
// mode claims, a stroke or a capture, is one away from it.
export const onPressAway = (away, dismiss) =>
  onPress((start, from) =>
    start.button === 0 && away(from)
      ? (end, completed) => {
          const path = end.composedPath();
          if (completed && away(path)) dismiss(path, from);
        }
      : null,
  );
addEventListener(
  "pointerdown",
  (event) => {
    if (!event.isPrimary) return;
    const path = event.composedPath();
    const ends = [];
    press = { pointerId: event.pointerId, path, ends };
    for (const read of pressReaders) {
      const end = read(event, path);
      if (end) ends.push(end);
    }
    if (event.button !== 0 || labelPress) return;
    const label = /** @type {(EventTarget & Partial<HTMLLabelElement>)[]} */ (
      path
    ).find((node) => node?.localName === "label" && node.control);
    const held = label && deepFocus();
    if (!held || held === document.body) return;
    labelPress = { held, pointerId: event.pointerId, label };
  },
  { capture: true, passive: true },
);
function endPress(event, completed) {
  if (!press) return;
  const { ends } = press;
  press = null;
  for (const end of ends) end(event, completed);
}
for (const type of /** @type {const} */ (["pointerup", "pointercancel"]))
  addEventListener(
    type,
    (event) => {
      if (
        event.pointerId === labelPress?.pointerId &&
        (type === "pointercancel" || !event.composedPath().includes(labelPress.label))
      )
        landLabelPress();
      if (event.pointerId === press?.pointerId) endPress(event, type === "pointerup");
    },
    { capture: true, passive: true },
  );
addEventListener(
  "contextmenu",
  (event) => {
    landLabelPress();
    endPress(event, false);
  },
  { capture: true, passive: true },
);
addEventListener("click", landLabelPress, { capture: true, passive: true });

// A key ends a label press, since it changes the input the user works with: they go back
// on the element the press held them on, before the key's dispatch and default run,
// and the key's own route reads that element as its target (`recoveredLabelFocus`).
const recoveredLabelKeys = new WeakMap();
export const recoveredLabelFocus = (event) => recoveredLabelKeys.get(event);
addEventListener(
  "keydown",
  (event) => {
    placeInput = "focus";
    if (!labelPress || event.isComposing || MODIFIER_KEYS.includes(event.key)) return;
    const active = deepFocus();
    const { held } = finishLabelPress();
    if (active === held || !held.isConnected) return;
    focusDestination(held, "return");
    if (deepFocus() === held) recoveredLabelKeys.set(event, held);
  },
  true,
);

for (const type of ["keydown", "pointerdown", "wheel", "touchstart"])
  addEventListener(
    type,
    (event) => {
      if (type === "pointerdown")
        pressedPath = event.composedPath().map((node) => new WeakRef(node));
      else if (type === "keydown") pressedPath = null;
      stepping = null;
      if (type === "keydown" || type === "pointerdown") {
        const step = type === "keydown" && sequential(event) ? event : null;
        const pressed = pressedPath;
        stepping = step;
        setTimeout(() => {
          if (step && stepping === step) stepping = null;
          reconcile(step, pressed);
          queueFocusPaint();
        });
      }
      const at = deepFocus();
      if ((at && at !== document.body) || heldByLabel()) return;
      lastLocation = null;
      publish(null, cause(null));
    },
    { capture: true, passive: true },
  );
// The box that wears the focus ring for `node`. A rule that rings a control's face
// rather than the control declares it there, `--lf-wears-ring: 1` (theme.css), as a
// playground's choice rings its radio and words together; the nearest such box around
// the control is the one. Anything else wears its own. Those rules ring the face of the
// control the focus paint marks, so only that control has one. A landing in the
// focus task reads the carrier from native focus before Leaf paints. Reading the
// ring must not paint an intermediate focus destination: a return in the same
// task would otherwise remove and restore the previous focus marks.
export function ringBox(node) {
  if (!node?.matches?.(":focus, [data-lf-focus]")) return node;
  for (
    let box = renderedParent(node);
    box instanceof Element;
    box = renderedParent(box)
  )
    if (getComputedStyle(box).getPropertyValue("--lf-wears-ring") === "1") return box;
  return node;
}
// A focus place excludes inert content, even while its closing animation paints it.
// Drawn counts `visibility: hidden` as hidden: a node under it keeps focus for a frame
// and then the browser blurs it to the body, as it does a node under `display: none`.
export const drawn = (node) =>
  node?.isConnected &&
  !excludedByInert(node) &&
  node.checkVisibility({ visibilityProperty: true });
// The node hidden or removed by a change that left the user with no current location.
const dropped = () => {
  const at = deepFocus();
  if (at && at !== document.body) return null;
  const node = lastLocation?.deref();
  return node && !drawn(node) ? node : null;
};
// A list of keyed items names its place by `key`, the attribute each item carries. The
// hold then reads the item the user is in and the order of every item at the hold,
// and its restore, after the held node, tries the item now carrying the same key, then
// the nearest item that survived after it, then before it, before the caller's own
// stand-ins: the user is never left on the body because the row they were on left the
// list.
export function holdFocus(scope, { key = null } = {}) {
  const node = heldIn(scope);
  if (!node) return null;
  const restore = holdOn(node);
  if (!key) return restore;
  let item = node;
  while (item && !item.matches?.(`[${key}]`)) item = renderedParent(item);
  if (!item || item === scope || !renderedUnder(item, scope)) return restore;
  // The items are read in the tree the held one stands in, which is the scope's own or a
  // shadow tree inside it.
  const tree = item.getRootNode() === scope.getRootNode() ? scope : item.getRootNode();
  const items = () =>
    [...tree.querySelectorAll(`[${key}]`)].filter((item) => renderedUnder(item, scope));
  // A key marking several nodes of one place counts once, where it first stands.
  const keys = [...new Set(items().map((each) => each.getAttribute(key)))];
  const at = keys.indexOf(item.getAttribute(key));
  const order = [keys[at], ...keys.slice(at + 1), ...keys.slice(0, at).reverse()];
  // In an item, the control like the one the user was on, as Remove for Remove, read
  // in the item's own tree, or the item itself where it holds none.
  // Not shadow.js's `hostIn`, which answers null where the climb leaves the item's tree:
  // this keeps the outermost host it reached.
  let control = node;
  while (control.getRootNode() !== item.getRootNode()) {
    const host = shadowHost(control.getRootNode());
    if (!host) break; // Slotted document controls already name their native kind.
    control = host;
  }
  const like =
    control.localName +
    [...control.classList].map((name) => `.${CSS.escape(name)}`).join("");
  const [same, ...rest] = order;
  return (...standIns) => {
    // The items now present, by key, read once for the whole restore: a list whose keys
    // all changed tries every held key against it.
    let byKey = null;
    const keyed = (value) => {
      if (!byKey) {
        byKey = new Map();
        for (const each of items()) {
          const at = each.getAttribute(key);
          if (!byKey.has(at)) byKey.set(at, []);
          byKey.get(at).push(each);
        }
      }
      return byKey.get(value) ?? [];
    };
    // The drawn item keyed so, where a hidden copy of it stands too. One key may mark
    // several nodes of one place, as a diff line's text and its gutter's Comment: the one
    // like the control the user was on, or holding one, comes first.
    const matching = (root) => {
      if (root.matches(like) && drawn(root)) return root;
      const assigned =
        root.localName === "slot" ? root.assignedElements({ flatten: true }) : [];
      for (const child of assigned.length ? assigned : root.children) {
        const found = matching(child);
        if (found) return found;
      }
      return null;
    };
    const find = (value) => {
      const found = keyed(value).filter(drawn);
      return (
        (like && found.find((each) => each.matches(like))) ??
        (like && found.map(matching).find(Boolean)) ??
        found[0] ??
        null
      );
    };
    // The item keyed the same is the same place, so the caret goes with the user; a
    // neighbour is another place, which this hold lands on with no caret.
    const neighbour = (value) => () => {
      const place = find(value);
      if (!place || !drawn(place)) return null;
      focusDestination(place, "return");
      return landedOn(place);
    };
    return restore(() => find(same), ...rest.map(neighbour), ...standIns);
  };
}
const heldIn = (scope) => {
  const held = heldByLabel();
  if (held) return renderedUnder(held, scope) ? held : null;
  const currentLocation = deepFocus(
    scope.getRootNode().activeElement ?? scope.ownerDocument.activeElement,
  );
  if (
    currentLocation &&
    currentLocation !== document.body &&
    renderedUnder(currentLocation, scope)
  )
    return currentLocation;
  // Asked of every node `move` inserts, so the cheap containment reading comes first.
  const node = lastLocation?.deref();
  return node && renderedUnder(node, scope) ? dropped() : null;
};

// Whether the user is in `scope`, across every shadow tree between them.
export const currentLocationIn = (scope) => {
  const at = focused();
  return Boolean(at) && at !== document.body && renderedUnder(at, scope);
};

// The roving stop of a group: `stop` is the one item Tab reaches, and every other item
// is reached by the group's own arrows. Null leaves the group no stop.
export function rove(items, stop) {
  for (const item of items) keeps(item, "tabindex", item === stop ? 0 : -1);
}

// Where a layer hands the user back when it closes: the control they had focused as it
// opened, or the one its opener names, as a menu row's door. Recorded once at the opening
// (`openLayer`) and read by the close (`openerOf`), so no layer keeps its own record.
// The body is nowhere, so a layer opened from it hands back nothing and lets go.
const openers = new WeakMap();
export function openLayer(layer, opener = focused()) {
  openers.set(layer, opener && opener !== document.body ? opener : null);
}
export const openerOf = (layer) => openers.get(layer) ?? null;

// Closing a layer the user may be in and handing them on, as one act. `close` hides
// the layer and places nothing itself; whatever focus does while it runs, the platform's
// own hand-back as a dialog or popover closes included, reaches no reader of where the
// user is and is no placement. `land`, where the closer names one, then puts the
// user where the close takes them: `handBack(...)`, `letGo`, a route; that placement is
// heard and counted as any is. Where `land` names none and the close left the user on
// another node, as a platform hand-back does, readers hear it once as a `return`, which
// is the layer's own and no newer word to a hold. One the close hid them under and no
// landing put right is a drop, as any is.
//
// A close inside another, as a card closing while the page map that holds it closes,
// is part of that act: it lands nobody and tells nobody. The outer close's landing
// takes the user on, or where it names none, the first inner landing does.
let closing = 0;
let deferredLanding = null;
let landingLayer = false;
// A landing a closer builds away from its `closeLayer` call, as a surface's landing on
// an entry, which several closes share. It runs only as a close's landing: called at any
// other time it would be a layer return beside the close, which readers hear as a
// second move and holds read as a newer word, so it throws. Lint lets `handBack` stand
// only in a close's `land` argument or in a function this wraps (`layer-returns`).
export function layerLanding(land) {
  return (...args) => {
    if (!landingLayer)
      throw new Error("A layer's landing runs only as the layer closes");
    return land(...args);
  };
}
/** @param {() => unknown} close @param {(() => unknown) | false | null} [land] */
export function closeLayer(close, land = null) {
  closing += 1;
  let deferred = null;
  // A close inside a landing is no landing of its own while it hides.
  const landingAround = landingLayer;
  landingLayer = false;
  try {
    close();
  } finally {
    landingLayer = landingAround;
    closing -= 1;
    // The outermost close takes what an inner one deferred, whether or not it threw,
    // so no landing outlives the act it belonged to.
    if (!closing) [deferred, deferredLanding] = [deferredLanding, null];
  }
  if (closing) {
    if (land) deferredLanding ??= land;
    return;
  }
  const landing = land || deferred;
  if (landing) {
    const outer = landingLayer;
    landingLayer = true;
    try {
      landing();
    } finally {
      landingLayer = outer;
    }
  }
  const at = deepFocus();
  if (!at || at === document.body || at === published?.deref()) return;
  lastLocation = new WeakRef(at);
  publish(at, "return");
}

// The same reading with no scope, for an owner that learns which place it holds from
// the node: where the user is, or the node a change dropped them from. `null` where
// they have no current location, or on nothing a change took away.
export function holdCurrentLocation() {
  const at = focused();
  const node = at && at !== document.body ? at : dropped();
  return node ? { node, restore: holdOn(node) } : null;
}

// The node a hold carried the user to from the one it held, with the input count then:
// the same place under a new node, so work waiting on the held node follows it there
// while the user has done nothing since (user-intent.js).
const carried = new WeakMap();
export const carriedFrom = (node) => carried.get(node) ?? null;
function holdOn(held) {
  const caret = readCaret(held);
  const began = placements;
  return (...standIns) => {
    if (placements !== began) return false;
    for (const standIn of [held, ...standIns]) {
      // A reader of a restore before, or a function stand-in, that moved the user said
      // a newer word, and no later stand-in lands over it.
      if (placements !== began) return false;
      // A function runs as the owner's own act, so whatever it does with focus counts
      // as a placement to every other hold; only the move back to the held place does not.
      const place = typeof standIn === "function" ? standIn() : standIn;
      // An asynchronous owner lands under its original input intent before returning
      // the destination. Continue its caret only while that exact editor still holds
      // focus; a Promise is never permission to find or focus another stand-in.
      if (place?.then)
        return place.then((destination) => {
          if (
            !(destination instanceof Element) ||
            !drawn(destination) ||
            deepFocus() !== destination
          )
            return false;
          return land(() => {
            focusDestination(destination, "return", { caret });
            return landedOn(destination);
          });
        });
      if (place === true) return true;
      if (!(place instanceof Element) || !drawn(place)) continue;
      if (place === held && deepFocus() === held) return true;
      const landed = land(() => {
        focusDestination(place, "return", { caret });
        return landedOn(place);
      });
      if (landed) {
        // Two holds in a row with no input between carry the same place on, so the
        // record names the node the first one held.
        const before = carriedFrom(held);
        if (place !== held)
          carried.set(
            place,
            before?.inputs === inputCount()
              ? before
              : { from: held, inputs: inputCount() },
          );
        return true;
      }
    }
    return false;
  };
}
const land = (landing) => {
  const was = restoring;
  restoring = true;
  try {
    return landing();
  } finally {
    restoring = was;
  }
};

// Where a printed key becomes text in the box.
export const typesText = inputs.typesText;

// Select options retain typeahead when an open custom list moves focus into an option.
export const takesLetters = inputs.takesLetters;

// Radio and range controls own their arrow navigation before a containing widget.
// Custom controls expose the same role at their focused element as the native input.
export function controlNavigationKeys(node) {
  if (node?.matches('input[type="radio"], [role="radio"]'))
    return ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"];
  if (node?.matches('input[type="range"], [role="slider"]'))
    // A slider's value steps, not control-selectors.js's CARET_KEYS: the same keys today.
    return [
      "ArrowLeft",
      "ArrowRight",
      "ArrowUp",
      "ArrowDown",
      "Home",
      "End",
      "PageUp",
      "PageDown",
    ];
  return [];
}

// Landing the user in the document. One act at both ends of the ladder, and for every
// step that would otherwise leave them on Leaf's own apparatus, because being on an
// item out on the page and being on a panel button are the same state — the user
// holding something — reached from either side of the chrome. What those rungs do not
// share is the word, and neither word is the other's: leaving the chrome names where the
// user lands, since that is the whole of what the rung is for, and letting go of an obligation
// names the act, since they were on the page all along.
//
// Where they land is beside what they let go of, while they see it, since that is what
// they were reading; otherwise the block they are reading in the page region they last
// acted in (reading-regions.js, `pageReadingRegion`), which is a reading of that region's
// current scroll rather than a place remembered from before the press: a surface closing
// moves the page under them, and what they can see when it has gone is the answer. Only
// the region is remembered, so no revision, repaint or reflow can strand the block.
//
// Focus and then blur, which is the pair and not either half. The focus moves the
// browser's sequential focus navigation starting point to the block, so the user's next
// Tab carries on from what they are reading rather than from the top of the document,
// which is where `document.body.focus()` puts it. The blur hands Space, PageDown, arrows,
// Home and End back to the page's own scroll box, which a focused block would keep.
//
// `releaseFocus` is the other half of the pair and the top of the document is the point of
// it: a page that has just arrived is not a page anybody has read yet, so its first Tab
// belongs at its first control rather than part-way through the prose that happens to be on
// screen. It is also the fallback here, for a page whose view holds nothing to land on,
// such as a run of figures, where the honest answer is that the user has no reading
// position for the browser to continue from. A region in that state still has one: the
// declared reading lands on its body (reading-place.js, `landingPlace`).
/** @type {(from?: Element | null) => HTMLElement | null} */
let readingBlock = () => null;
export function declareReading(read) {
  readingBlock = read;
}
//
// It is the same pair on the body, which carries no tab stop of its own. A permanent
// `tabindex` on body was once how the let-go worked on a page too short to scroll, but it
// also made the body the focusable ancestor of every word: a click on a pane's text
// focused the body, and Chrome starts Space, PageDown and the arrows from the focused
// element before the node last pressed, so they scrolled the root, which a held
// workspace keeps still, and never the pane under the click. So the body borrows the stop
// for the focus that moves the starting point to the top, and gives it back on the blur.
export function releaseFocus() {
  focusDestination(document.body, "move");
  document.body.blur();
}

// Letting go of what the user is on, the current scope's Escape, is a landing that
// also closes what was shown beside that location: the thread card beside the target they held.
// Other landings reach the page without letting go of anything — `g p`, a surface
// closing — so the release is its own act rather than something read off focus leaving.
let released = () => {};
export function declareRelease(release) {
  released = release;
}
// Once: what the release ends may have let go already, as the thread card does when it
// closes with the focus inside it, and a second let-go would land the user again.
let letGoes = 0;
export function release() {
  const before = letGoes;
  released();
  if (letGoes === before) letGo();
}
// A landing on the page is the user going on to it, a `move`. It leaves them at nothing,
// beside what they let go of rather than anywhere else, and each reader `onLetGo` names
// hears that node once the landing is done (current-target.js, `walkOrigin`).
const letGoReaders = new Set();
export const onLetGo = (read) => {
  letGoReaders.add(read);
  return () => letGoReaders.delete(read);
};
export function letGo() {
  letGoes++;
  const from = focused();
  const block = readingBlock(from);
  if (!block?.isConnected) releaseFocus();
  else {
    focusDestination(block, "move");
    block.blur();
  }
  if (from && from !== document.body) for (const read of letGoReaders) read(from);
}

// Handing the user back when a layer closes with them inside it. The closer names where,
// most particular first — the control whose press opened the layer, the proxy the layer's
// subject has on the page, the door a folded toolbar shows in a control's place — and the
// user lands on the first that takes focus. The page's body is nowhere: an opener read
// while nothing held focus names no place to return to.
//
// A destination still in the document may not take focus yet: reconciliation can
// replace a control in the same task, and the paint the close asked for may still hold
// it hidden. So where none lands but one is still there, the list is read once more on
// the next frame. A destination then gone or hidden is gone for good — the layer it
// was in closed while this one was up — and the user lands where `letGo` puts them,
// which is also where a closer that names nothing sends them. Focus placed anywhere in
// that frame keeps its place: a user who moved on, or a caller that landed them itself,
// said the newer word. That is the placement count every hold reads, so a move between
// two nodes of one shadow tree counts as well.
export function handBack(...destinations) {
  const places = destinations.filter((node) => node && node !== document.body);
  // A reader of a landing that moved the user elsewhere said a newer word, and no
  // later destination lands over it.
  const landed = () => {
    const at = placements;
    return places.some((node) => {
      if (placements !== at) return true;
      if (!drawn(node)) return false;
      focusDestination(node, "return");
      return landedOn(node);
    });
  };
  if (landed()) return;
  if (!places.some((node) => node.isConnected)) {
    letGo();
    return;
  }
  // The close has already hidden its focused control. Give the next key the page
  // while a connected return target has one frame to become focusable again.
  const yielded = !drawn(deepFocus());
  if (yielded) releaseFocus();
  const began = placements;
  const pendingInput = inputCount();
  nextRender(() => {
    if (
      inputCount() !== pendingInput ||
      placements !== began ||
      (yielded && deepFocus() !== document.body) ||
      landed()
    )
      return;
    letGo();
  });
}
