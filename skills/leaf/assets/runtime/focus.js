/* Putting the user on an element: the focus, and the caret inside it, what the
   keyboard can stand on, where a closing layer hands the user back, how a change
   that moves or replaces the node they stand on keeps them there, and who moved them
   each time where they stand changes (`onStanding`).

   This module is the one reader of where the user stands. Every other reader of it,
   or of what moved them there, reads `onStanding`, whose causes are `return`,
   `press`, `step`, `move` and `drop`. A `focusin` listener on a node hears nothing of a
   move between two nodes of one shadow tree beneath it, which reaches it as no event,
   and each reader guessing for itself which moves were the runtime's own returns or
   the keyboard's arrivals answered the same question several ways. The lint
   (`architecture/standing-listeners`) refuses `focusin` and `focusout` elsewhere, and
   `focus` and `blur` on the document or captured anywhere, except in the few files it
   names: those that ask about one element or its own subtree, and the interaction
   log, which records events and reads no standing. Rejected: keeping each reader's
   listener and having stages re-dispatch their moves to the document, which leaves
   every reader's own reading of the cause.

   It is also the one place that moves them. Every focus the runtime and the packages
   place goes through `focusDestination(node, cause)`, which says whether it is a route
   or a return; the lint (`architecture/placements`) refuses a plain `focus()` elsewhere.
   Each owner once marked its own returns with a flag its own listener read, and a plain
   `focus()` that was a return published as the user's move to every other reader.
   Rejected: keeping wrappers around a placement (`returningFocus`, `placeChrome`) that a
   caller could forget, which is how those returns reached the readers as moves.

   The selector vocabulary lives in control-selectors.js, which imports nothing.
   This module imports only that vocabulary and rendering.js: importing a gesture
   owner would cycle through its focus dependency. The hand-back and the hold therefore
   count placements off the events read here rather than from user-intent.js. */
import { nextRender } from "./rendering.js";
import { TEXT_BOX, TAB_STOP } from "./control-selectors.js";

// The stops Tab walks inside `root` right now, in document order: the candidates above
// that are in the order, enabled, and drawn. A modal's own Tab loop reads this.
export const tabStops = (root) =>
  [...root.querySelectorAll(TAB_STOP)].filter(
    (node) =>
      node.tabIndex >= 0 &&
      !node.matches(":disabled") &&
      !node.inert &&
      node.checkVisibility(),
  );

// Put the user on an element, saying what moved them there. Every focus the runtime and
// the packages place goes through here (the lint `architecture/placements` refuses a
// plain `focus()` elsewhere), because the call is the only place that knows whether it
// is the user going somewhere or the runtime handing them back, and every reader of
// where they stand (`onStanding`) needs that word: a return that published as a move
// released held news, opened a cluster's options and chose a card the user never went
// to. The cause is one of:
//
// - `move`: a route taking the user somewhere, whether a key or a press began it;
// - `step`: standing in for Tab or Shift+Tab, as a modal's own Tab loop does;
// - `return`: putting the user back where they came from or handing them across, a
//   closing layer's hand-back, a re-render carrying them to the node that replaced the
//   one they stood on, a chrome placement moving the box they stand in;
// - `press`: landing on a control to press it on the user's behalf, as a go-to that
//   presses a control does: the readers take it as the platform's focus for a press,
//   which asks for what it lands on and opens nothing on arrival.
//
// A focus that runs inside another placement, as a component's own focus handler
// forwarding to its selected child does, is part of that placement and takes its cause.
// A reader of where the user stands that moves them answers a reading, not the
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
// link landing on the banner when none of its controls will take them. Each is "the
// user is now here", and each needs the browser's sequential focus navigation starting
// point to move with them, which is what `focus()` does and what nothing else does.
//
// A caret is where the user is inside the element they are on, so it arrives with them.
// An arrival that is a return — a bar moved between two parents, a seat re-rendered, a
// thread reconciled, a replaced document handing back the place the user stood in —
// reads the caret with `readCaret` before its element goes away and passes it here, so
// that the focus and the place inside it land in one act rather than in two. Passing no
// caret leaves the platform's, which is what a first arrival wants.
//
// The placement keeps the page still unless `scroll` asks the browser to bring the
// element into view, as a list whose rows run past its box does for the row it lands on.
const CAUSES = new Set(["move", "step", "return", "press"]);
export function focusDestination(
  destination,
  cause,
  { caret = null, scroll = false } = {},
) {
  if (!CAUSES.has(cause)) throw new TypeError(`focusDestination: no cause ${cause}`);
  placed(cause, () => {
    destination.focus({ preventScroll: !scroll });
    if (!standsIn(destination) && lendable(destination)) lendStop(destination);
  });
  if (caret && holdsCaret(destination)) destination.setSelectionRange(...caret);
}
// A node handing on the focus it is gaining, from inside its own `focus` handler, to a
// node of its own, as the Threads list hands it to the title the user stood on: the
// arrival is the one that gave the node its focus, so the node it lands on takes that
// arrival's cause, whether a placement or the user's own Tab or press gave it.
export function forwardFocus(destination) {
  placed(placing ?? cause(destination), () =>
    destination.focus({ preventScroll: true }),
  );
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

// Whether focus stands on `node`, or inside a shadow tree it hosts, as it does inside a
// text field's editor: the field is where the user is. A light child of it is somewhere
// else, so a container a placement lands on is landed on itself.
const standsIn = (node) =>
  node.matches(":focus") || Boolean(node.shadowRoot?.activeElement);

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
// as they stand on the element is held through it. During every other blur, the element
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

function lendStop(destination) {
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
  destination.focus({ preventScroll: true });
  if (!standsIn(destination)) {
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

// The element holding focus, followed down through every open shadow tree it stands in
// from `at`. A closed tree answers with its host, which is the text field's case: the
// field is the box the user stands in.
export const deepFocus = (at = document.activeElement) => {
  while (at?.shadowRoot?.activeElement) at = at.shadowRoot.activeElement;
  return at;
};

// Holding the user's place across a change to the tree they stand in. Moving a node
// blurs whatever it holds to the body in the same call, and hiding one does the same a
// frame later, on no frame an owner can count; the node keeps its value and selection,
// but the user's standing on it is gone. Focus lives as long as its node, so whatever
// moves, hides or replaces nodes under the user hands their place across itself:
// `holdFocus(scope)` reads where the user stands inside `scope` before the change, with
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
// and returns `true` where it did. Restoring answers whether the user now stands on one
// of them.
// An asynchronous stand-in returns its actual landed element. Only that still-focused
// destination can receive the held caret; its owner retains permission across the wait.
//
// Nothing is owed while the user still stands on the held node and it is drawn, and
// nothing once focus has been placed anywhere since the hold began: a user who moved on
// during a wait, or an owner inside the change that landed them itself, said the newer
// word, as with `handBack`. A restore putting the user back in the place it held is not
// a newer word, so holds nest; a function stand-in is the owner's own act, and wherever
// it moves focus is a placement to every other hold.
//
// A change can also run before the owner that hands the user on: a widget rebuilding
// its tree drops the box a later pass draws again elsewhere, and focus is on the body
// before any hold is read. So a hold read while the user stands nowhere holds the node
// that change dropped them from, while it is not drawn and they have neither been placed
// nor acted since.
//
// `null` where the user does not stand, and was not dropped from, inside `scope`, which
// may be a shadow root or a node already taken out of the document. The platform's
// retargeting answers that: a user inside a widget's shadow tree stands inside the scope
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
// Where the user last stood. A change that removes or hides the node they stand on puts
// focus on the body and fires no `focusin`, so this still names that node afterwards.
// A move between two nodes of one shadow tree reaches the document as neither event, so
// every stage reads its own `focusin` (`watchStandingIn`), and the node focus leaves for
// nowhere is read off the path of the `focusout` that says so. Every later placement
// writes it again, so it names a place nothing has placed the user away from.
//
// The user acting while they stand nowhere, a key, a press, a wheel, a touch, is them
// going on from there, so the dropped place is forgotten: a later owner putting them
// back in it would take them from whatever they went on to. While they still stand
// somewhere, the same inputs are them working there, and change nothing.
let stood = null;
// Every change to where the user stands goes to each reader `onStanding` names, as
// `read(node, cause, left)`: the node they now stand on, null where they stand nowhere;
// what moved them there; and the node the readers last heard they stood on, null where
// that was nowhere. The causes:
//
// - `return`: the runtime putting them back or handing them across: a placement that
//   says so (`focusDestination`), a hold restoring its place (`holdFocus`,
//   `holdStanding`), a closer handing them back (`handBack`), or the platform handing
//   focus back from a layer it closed, as a dialog closed with Escape does;
// - `press`: focus landing on the node the user's last press was on, or on a control
//   holding it, before a key follows: the platform's own focus for the press, which asks
//   for what it lands on; or a placement landing on a control to press it on the user's
//   behalf (`focusDestination`), which asks the same;
// - `step`: sequential navigation, Tab or Shift+Tab, whether the browser moves them or
//   a placement stands in for it, as a modal's Tab loop does;
// - `move`: a placement taking them somewhere, or anything else, whether a key or a
//   press began it (`pressLed` says which);
// - `drop`: a change hid or removed the node they stood on, and focus fell to the body,
//   read as `null`. The dropped place is still where they stand for every hold, and the
//   one to put them back is the owner of the change, so a reader of where they stand
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
// the title the user already stood on, inside the list's own `focus`, before the
// list's `focusin`. A focus that leaves for nowhere and returns, as a window losing
// and regaining focus does, is none.
const readers = new Set();
export const onStanding = (read) => readers.add(read);
let published = null;
let departed = false;
let readings = 0;
function publish(node, cause) {
  if (node === published && !departed) return;
  departed = false;
  const left = published;
  const reading = ++readings;
  // A drop leaves the place where readers last heard the user stood, so the next
  // reading, the owner putting them back there included, is told against it.
  if (cause === "drop") departed = true;
  else published = node;
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
// The press the user last made, as the nodes under it, until a key follows it.
let pressedPath = null;
// Whether the user's latest input was a press rather than a key, so that a `move` is a
// route a press began: what the platform's `:focus-visible` guesses from, read here
// from the inputs themselves. No input yet reads as no press.
export const pressLed = () => pressedPath !== null;
// The Tab the user is pressing, from its keydown until the task that moves them ends.
let stepping = null;
// Focus coming out of a dialog or popover that no longer stands is that layer handing it
// back as it closes, whether the platform or the layer's owner moves it.
const leftClosedLayer = (left) => {
  const layer = left?.closest?.("dialog, [popover]");
  return Boolean(layer) && !layer.matches("dialog[open], :popover-open");
};
const cause = (node, left = null) =>
  placing ??
  (leftClosedLayer(left)
    ? "return"
    : pressedPath?.has(node)
      ? "press"
      : stepping
        ? "step"
        : "move");
// One move fires once at the document and again at each stage it crosses into.
const read = new WeakSet();
function stand(event) {
  if (read.has(event)) return;
  read.add(event);
  if (!restoring && !(placing === null && leftClosedLayer(event.relatedTarget)))
    placements += 1;
  stood = deepFocus();
  publish(stood, cause(stood, event.relatedTarget));
}
document.addEventListener("focusin", stand, true);
// A shadow stage reads the moves inside it, which reach the document as no event.
export function watchStandingIn(root) {
  root.addEventListener("focusin", stand, true);
}
// Leaving for nowhere from a node still drawn is the user's own move, and so a
// placement: body holds no stop, so a press on the page's words takes focus off the
// control and puts it nowhere with no `focusin` to count, and a hold still waiting
// would pull the user back from the words they chose. It is not a drop either, so the
// node is forgotten as where they stood: a later change removing it drops nobody. A node
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
    stood = left;
    if (restoring) return;
    queueMicrotask(() => {
      const at = document.activeElement;
      if (at !== null && at !== document.body) return;
      if (!drawn(left)) return publish(null, "drop");
      placements += 1;
      if (stood === left) stood = null;
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
// Where the user stands, read again once a key's or a press's task ends, and once a
// click's does, since a tap focuses at the click that follows it rather than at its
// press. A move between two nodes of a shadow tree no stage watches, as a component's
// own root makes, reaches no root this module listens on, so the reading the input left
// is told then, with the cause that input gave it, a Tab's step included, and a return
// where it came out of a layer that closed.
function reconcile(step, pressed) {
  const at = deepFocus();
  if (!at || at === document.body || at === published) return;
  placements += 1;
  stood = at;
  const was = [stepping, pressedPath];
  [stepping, pressedPath] = [step, pressed];
  try {
    publish(at, cause(at, published));
  } finally {
    [stepping, pressedPath] = was;
  }
}
addEventListener(
  "click",
  () => {
    const pressed = pressedPath;
    setTimeout(() => reconcile(null, pressed));
  },
  { capture: true, passive: true },
);
for (const type of ["keydown", "pointerdown", "wheel", "touchstart"])
  addEventListener(
    type,
    (event) => {
      if (type === "pointerdown") pressedPath = new Set(event.composedPath());
      else if (type === "keydown") pressedPath = null;
      stepping = null;
      if (type === "keydown" || type === "pointerdown") {
        const step = type === "keydown" && sequential(event) ? event : null;
        const pressed = pressedPath;
        stepping = step;
        setTimeout(() => {
          if (step && stepping === step) stepping = null;
          reconcile(step, pressed);
        });
      }
      const at = deepFocus();
      if (at && at !== document.body) return;
      stood = null;
      publish(null, cause(null));
    },
    { capture: true, passive: true },
  );
// Drawn counts `visibility: hidden` as hidden: a node under it keeps focus for a frame
// and then the browser blurs it to the body, as it does a node under `display: none`.
export const drawn = (node) =>
  node?.isConnected && node.checkVisibility({ visibilityProperty: true });
// The node a change took out from under a user who now stands nowhere: where they last
// stood, while it is no longer drawn.
const dropped = () => {
  const at = deepFocus();
  if (at && at !== document.body) return null;
  return stood && !drawn(stood) ? stood : null;
};
export function holdFocus(scope) {
  const standing = scope.getRootNode().activeElement;
  if (standing && standing !== document.body && scope.contains(standing))
    return holdOn(deepFocus(standing));
  const lost = dropped();
  return lost && scope.contains(lost) ? holdOn(lost) : null;
}

// The same reading with no scope, for an owner that learns which place it holds from
// the node: where the user stands, or the node a change dropped them from. `null` where
// they stand on nothing, or on nothing a change took away.
export function holdStanding() {
  const at = deepFocus();
  const node = at && at !== document.body ? at : dropped();
  return node ? { node, restore: holdOn(node) } : null;
}

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
            return standsIn(destination);
          });
        });
      if (place === true) return true;
      if (!(place instanceof Element) || !drawn(place)) continue;
      if (place === held && deepFocus() === held) return true;
      const landed = land(() => {
        focusDestination(place, "return", { caret });
        return standsIn(place);
      });
      if (landed) return true;
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
// A native layer's own opening and closing steps, as a dialog's `showModal` or a
// popover's `hidePopover`, which move focus the platform's way and not through
// `focusDestination`. Whatever they do with focus is the layer's return to every reader
// of standing, and no newer word to a hold waiting across them, so the owner re-seating
// its layers can put the user back where they stood.
export const nativeLayerSteps = (steps) => placed("return", () => land(steps));

const TYPED_TYPES = new Set([
  "text",
  "search",
  "url",
  "tel",
  "email",
  "password",
  "number",
  "date",
  "time",
  "datetime-local",
  "month",
  "week",
]);

// Where a printed key becomes text in the box.
export function typesText(node) {
  return (
    Boolean(node) &&
    (node.matches(TEXT_BOX) ||
      node.isContentEditable ||
      (node.tagName === "INPUT" && TYPED_TYPES.has(node.type)))
  );
}

// Select options retain typeahead when an open custom list moves focus into an option.
export function takesLetters(node) {
  return (
    typesText(node) ||
    (Boolean(node) &&
      (node.tagName === "SELECT" || node.getAttribute("role") === "option"))
  );
}

// Radio and range controls own their arrow navigation before a containing widget.
// Custom controls expose the same role at their focused element as the native input.
export function controlNavigationKeys(node) {
  if (node?.matches('input[type="radio"], [role="radio"]'))
    return ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"];
  if (node?.matches('input[type="range"], [role="slider"]'))
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
// step that would otherwise leave them on Leaf's own apparatus, because standing on an
// Ask out on the page and standing on a banner button are the same state — the user
// holding something — reached from either side of the chrome. What those rungs do not
// share is the word, and neither word is the other's: leaving the chrome names where the
// user lands, since that is the whole of what the rung is for, and letting go of an Ask
// names the act, since they were on the page all along.
//
// Where they land is the block they are reading in the page region they last acted in
// (reading-regions.js, `pageReadingRegion`), which is a reading of that region's current
// scroll rather than a place remembered from before the press: a surface closing moves
// the page under them, and what they can see when it has gone is the answer. Only the
// region is remembered, so no revision, repaint or reflow can strand the block.
//
// Focus and then blur, which is the pair and not either half. The focus moves the
// browser's sequential focus navigation starting point to the block, so the user's next
// Tab carries on from what they are reading rather than from the top of the document,
// which is where `document.body.focus()` puts it. The blur hands Space, PageDown, arrows,
// Home and End back to the page's own scroll box, which a focused block would keep.
//
// `releaseFocus` is the other half of the pair and the top of the document is the point of
// it: a page that has just arrived is not a page anybody has read yet, so its first Tab
// belongs at the skip link rather than part-way through the prose that happens to be on
// screen. It is also the fallback here, for a page whose view holds nothing to land on,
// such as a run of figures, where the honest answer is that the user has no reading
// position for the browser to continue from. A region in that state still has one: the
// declared reading lands on its body (reading-place.js, `landingPlace`).
//
// A surface covering the page makes it inert, so neither half of this reaches it: the
// page is not somewhere the user can be while it is covered, and the surface is the
// floor they are standing on. The closing layer often leaves focus inside that surface on
// its own — the platform hands a popover's focus back to whoever held it when the popover
// showed — but that is the platform's courtesy rather than a landing, and where it does
// not arrive focus falls to the body, which no let-go on an inert page can take back. So
// letting go asks the covering surface before the page.
//
// Two readings, not one. The surface is the whole of what covers, and answers whether the
// user is already somewhere inside it — a drawer's close button, the panel's find box —
// where nothing is owed them. The landing is the one place within it that takes a user
// who is nowhere. Both are the modality's, which is the thing that inerted the page: a
// layout predicate of its own would be a second answer, disagreeing with it across a
// width change until the next sync, and it would know only the surfaces it was written
// for rather than every one that covers.
let readingBlock = () => null;
export function declareReading(read) {
  readingBlock = read;
}
let coveringSurface = () => null;
let coveringLanding = () => null;
export function declareCovering({ surface, landing }) {
  coveringSurface = surface;
  coveringLanding = landing;
}
//
// It is the same pair on the body, which carries no tab stop of its own. A standing
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

// Letting go of what the user stands on, the standing scope's Escape, is a landing that
// also ends what stood there with them: the thread card beside the target they held.
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
// A landing on the page is the user going on to it, a `move`.
export function letGo() {
  letGoes++;
  const covering = coveringSurface();
  if (covering) {
    // `contains` stops at a shadow boundary and `document.activeElement` is the host of
    // the tree holding focus, so the two meet: a user standing inside a widget's shadow
    // tree reads as inside the surface holding that widget, which is what is being asked.
    if (!covering.contains(document.activeElement))
      focusDestination(coveringLanding(), "move");
    return;
  }
  const block = readingBlock();
  if (!block?.isConnected) {
    releaseFocus();
    return;
  }
  focusDestination(block, "move");
  block.blur();
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
// stood in closed while this one was up — and the user lands where `letGo` puts them,
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
      if (!node.isConnected || !node.checkVisibility()) return false;
      focusDestination(node, "return");
      return standsIn(node);
    });
  };
  if (landed()) return;
  if (!places.some((node) => node.isConnected)) {
    letGo();
    return;
  }
  const began = placements;
  nextRender(() => {
    if (placements !== began || landed()) return;
    letGo();
  });
}
