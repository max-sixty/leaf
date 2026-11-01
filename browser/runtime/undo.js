/* Undo: the `z` walk and the one door every withdrawal goes through.

   The server's view of the shown revision lists, newest first, the user's gestures this
   document can take back (`served_state/document.py`); nothing here judges a candidate
   again. `z` takes the head of that list only when the server marks it `newest`, the
   user's newest gesture, so a reply sent since ends the walk, unless the press before
   armed another gesture (below), which it then takes; a widget's Undo, a
   reaction chip, and a reaction strip each name an exact entry, and a notice's Undo
   takes the gesture it reports by `z`'s rules (`offerUndo`). All of them withdraw
   through `withdraw`.

   `z` says what it takes and how long ago that was made, in the command reference, the
   floating panel's menu row and the notice its undo leaves ("Undo: resolved “Rollout
   safety” · 3d ago", then "Undid: resolved “Rollout safety” · 3d ago"), in
   every tab and after a reload. A thread goes by its name as it stands now, a to-do by
   its title and a reaction by where it stands, all of
   which the page already holds. An action's ids are words only in the document it was
   made in, so the server serves what the head did in that document's words
   (`gesture`, `GestureWords.gesture`), and the widget goes by its name on this page.
   An exact control's older entry carries no such reading, so its undo names only the
   widget. The age is the gesture's own `ts`, worded by the page's one clock (`ago`).

   `z` leaves the user at what it takes back, the gesture's place: the thread a
   settlement or reaction is in, the message holding a widget an agent sent, or the
   element changed. A to-do's Done changes only the leaf's own rows, which stand in
   front of the user, so it has none. A press reaches the place one of three ways:

   - Where the user sees it, the press takes the gesture there.
   - Where the place is out of view, or the agent has picked the gesture up
     (`picked_up`, served from the opened pickups), the press shows it and takes
     nothing, so `z` never takes back what the user cannot see. It shows the place the
     way an `lf-activity` row's link does, a thread opening and an element travelled
     to as its fragment, and arms, saying "Press again to undo: …". The second press
     takes it back. Any key between, a press on the page, or a scroll taking what the
     press showed out of view clears the arm, and the next press shows again; a press
     in Leaf's chrome keeps it, since the menu's Undo, the touch route, is reached
     through the leaf.
   - Where the gesture's own landing has just carried the user from its place, as a
     thread settlement's does (thread/folding.js, `landedAway`), the user's last look
     at it was the gesture itself, so the press takes it at once and then, once the
     page presents the withdrawal, shows the place under the press's intent. The
     gesture arms the press as a showing press does, and the same inputs clear it;
     after one, the rules above apply.

   Showing is a navigation step, so Back returns to where the user pressed. The rule is
   the same for every gesture; only a place's kind decides how it is shown. An exact
   control, such as a widget's Undo or a reaction chip, is pressed where its gesture is
   drawn, so its withdrawal moves nobody.

   A widget's gesture leaves, by its attempt, the words the widget named it by
   (`retainGesture`, `says`, pending/dispatch.js), and while this page holds them its
   undo is said in them, the name its own announcement used: "Chose “Fast”",
   then "Undid: Chose “Fast” · just now". Those words and a landing's arm live
   with the page that made the gesture, so after a reload or from another tab a
   gesture out of view is shown before it is taken. */
import { notice } from "./notifications.js";
import {
  applicationState,
  readApplication,
  whenDocumentPresented,
} from "./semantic-state.js";
import { runtime } from "./context.js";
import { pageCommand } from "./keyboard/register.js";
import { savedReadingSettled } from "./keyboard/bindings.js";
import { reactionPlace } from "./reactions.js";
import { PENDING } from "./thread/identity.js";
import { threadIdNamed, threadNamed } from "./thread/state.js";
import { addressableLabel, addressableWord } from "./addressable-names.js";
import { elementById, inChrome } from "./passages.js";
import { focusDestination, inputCount, onUserInput } from "./focus.js";
import { placeBox, placeHolder, seenRect, whenNone } from "./geometry.js";
import { messageHolding, threadName } from "./thread/messages.js";
import { surfaceFocusTarget } from "./thread/surfaces.js";
import { drawnThreadId, THREAD } from "./thread/selectors.js";
import { ago } from "./presence.js";
import { quotedWords as quoted } from "./words.js";
import { retainUserIntent } from "./user-intent.js";
import { raiseError } from "./errors.js";

const WAIT = "Wait for the current change to finish before undoing";

// A widget as the chrome names it on this page, else the word for its kind.
function widgetNamed(id) {
  const element = elementById(id);
  if (!element) return "a widget";
  const label = addressableLabel(element);
  return label ? quoted(label) : `the ${addressableWord(element)}`;
}

// What an action did, from the server's reading of it in its own document. The verbs
// are core's: a widget's own verb, such as `move` or `edit`, may read as a noun, so a
// verb with no record form core knows is quoted as what was recorded.
function actionWords(event, gesture) {
  const widget = widgetNamed(event.widget);
  switch (gesture?.form) {
    case "choice":
      return `chose ${gesture.chosen.map((words) => quoted(words)).join(", ") || "nothing"} in ${widget}`;
    case "move":
      return `moved ${quoted(gesture.unit)} to ${quoted(gesture.to)} in ${widget}`;
    case "edit":
      return `edited ${widget}`;
    case "add":
      return `added ${quoted(gesture.words)} to ${widget}`;
    case "verb":
      return `recorded “${gesture.verb}” on ${widget}`;
    default:
      return `updated ${widget}`;
  }
}

const TODO_ENDINGS = {
  done: (title) => `marked ${title} done`,
  failed: (title) => `marked ${title} failed`,
  dropped: (title) => `dropped ${title}`,
};

// What a gesture did, in the words the page holds for it now.
function gestureWords(event, gesture) {
  if (event.token) return `${event.token} reaction on ${reactionPlace(event)}`;
  switch (event.kind) {
    case "resolve":
    case "unresolve": {
      const thread = threadNamed(event.parent);
      const name = thread ? quoted(threadName(thread), 48) : "a thread";
      return `${event.kind === "resolve" ? "resolved" : "reopened"} ${name}`;
    }
    case "todo_end": {
      const todo = runtime.todos.find(({ id }) => id === event.todo);
      return TODO_ENDINGS[event.outcome](todo ? quoted(todo.title) : "a to-do");
    }
    default:
      return actionWords(event, gesture);
  }
}

// Where taking `event` back shows on the page: the thread it settled or reacted in, a
// widget an agent sent in a message (its message is its place), or the element it
// changed. A to-do's Done changes only the leaf's own rows, which stand
// in front of the user, so it has no place.
function placeOf(event) {
  // A reaction in a thread is a reply naming the message it reacts to.
  if (["resolve", "unresolve", "reply"].includes(event.kind))
    return { thread: threadIdNamed(event.parent), nodes: [] };
  const id = event.kind === "action" ? event.widget : event.anchor?.section;
  if (!id) return null;
  const held = messageHolding(id);
  if (held)
    return { thread: held.thread, message: held.message, nodes: [held.element] };
  return { fragment: id, nodes: [elementById(id)] };
}

// Whether the user sees any of a destination (an element or a Range), past whatever
// covers it.
const seen = (where) =>
  Boolean(where && seenRect(placeHolder(where), new Map(), placeBox(where)));

const KEYS_HELD = new Set(["Shift", "Control", "Alt", "Meta", "CapsLock", "Fn"]);
const UNDO_KEYS = ["z"];

export function createUndo({
  post,
  stateApplying,
  unaccountedGesture,
  openThread,
  threadPlace,
}) {
  // The attempts of the gestures the page can still take back: on their way to the
  // log, or on the undo list. One the log refused, or one taken back, is in neither.
  // Null between versions, when the page holds no undo list.
  function takeable() {
    const { effective, unresolved } = readApplication();
    if (!effective.view) return null;
    return new Set([
      ...effective.view.undo.map(({ event }) => event.attempt),
      ...unresolved.flatMap((entry) =>
        entry.state === "refused" ? [] : [entry.event.attempt],
      ),
    ]);
  }
  // Kept while its gesture can still be taken back.
  /** @type {Map<string, {says?: string}>} */
  const gestures = new Map();
  function retainGesture(attempt, facts) {
    const live = takeable();
    if (live)
      for (const kept of gestures.keys()) if (!live.has(kept)) gestures.delete(kept);
    gestures.set(attempt, { ...gestures.get(attempt), ...facts });
  }
  // What taking `event` back takes: by the name its gesture was acknowledged by where
  // this page made it, else in the words the page holds for it now.
  const said = (event) => {
    const gesture = runtime.undo.find((entry) => entry.event.id === event.id)?.gesture;
    return gestures.get(event.attempt)?.says ?? gestureWords(event, gesture);
  };
  // ...and how long ago it was made.
  const takes = (event) => [said(event), ago(event.ts)].filter(Boolean).join(" · ");

  // The gesture `z` would take on the list the page holds now.
  const head = () => {
    const [first] = runtime.undo;
    return first?.newest ? first.event : null;
  };
  function undoable() {
    return stateApplying() ? null : head();
  }
  // Whether taking back this exact gesture now takes back what the user sees. The
  // ordered ledger sends the undo behind everything already queued, the target's own
  // unanswered send included, and the server remains final admission. Two things it
  // cannot order: another action awaiting presentation may change which gestures
  // the page can honestly offer, whether or not its own POST has answered, and only
  // an action's withdrawal can name its target before the log does, so a message
  // the log has not taken waits for its answer.
  function withdrawable(event) {
    if (event.kind !== "action" && String(event.id).startsWith(PENDING)) return false;
    return !applicationState
      .unpresented()
      .some(
        (entry) =>
          entry.event.kind === "action" &&
          (entry.admitted?.id ?? entry.localId) !== event.id,
      );
  }

  // The one withdrawal door. Returns null when the page refuses the withdrawal now,
  // otherwise the delivery, which yields the admitted undo or null.
  function withdraw(event) {
    if (!withdrawable(event)) {
      raiseError(WAIT);
      return null;
    }
    const taken = takes(event);
    return post({ kind: "undo", undoes: event.id }).then((accepted) => {
      if (accepted) {
        notice(`Undid: ${taken}`);
        gestures.delete(event.attempt);
      }
      return accepted;
    });
  }

  // The gesture the next press takes without showing it first: the one the last press
  // showed, or one whose landing has just carried the user from its place, which that
  // press returns them to (the header's three ways).
  /**
   * @type {{
   *   is: (event: {id: string, attempt?: string}) => boolean,
   *   stop: () => void,
   *   inputs: number[],
   *   shown: boolean,
   *   returns: boolean,
   * } | null}
   */
  let armed = null;
  function disarm() {
    armed?.stop();
    armed = null;
  }
  // Each input since the arm that could be something else, by its place in the
  // user's inputs (`inputCount`). A key may be the press that takes the gesture, so
  // the arm holds through one, and that press reads it as its own. The undo key itself
  // takes, shows or, while the page waits on a change, does nothing, so it is never
  // the user looking elsewhere.
  // A wheel clears a landing's arm, whose place nothing watches; a shown place clears
  // its own arm as it leaves the view.
  onUserInput((event) => {
    if (!armed || event.type === "blur") return;
    if (event.type === "wheel" && !armed.returns) return;
    if (
      event.type === "keydown" &&
      (event.repeat || KEYS_HELD.has(event.key) || UNDO_KEYS.includes(event.key))
    )
      return;
    if (
      (event.type === "pointerdown" || event.type === "touchstart") &&
      inChrome(/** @type {Node} */ (event.composedPath()[0]))
    )
      return;
    armed.inputs.push(inputCount());
    if (armed.inputs.length > 1) disarm();
  });
  // Whether this press takes the armed gesture: the press before it has finished
  // showing it, so a quick second press can't take what never reached the screen, and
  // nothing came between, or only the press itself.
  const armedFor = (event) =>
    Boolean(armed?.is(event)) &&
    armed.shown &&
    armed.inputs.every((input) => input === inputCount());
  // A thread settlement's landing has carried the user from the gesture's place
  // (thread/folding.js). Until they act, the user's last look at the gesture was the
  // gesture itself.
  function landedAway(attempt) {
    disarm();
    armed = {
      is: (event) => event.attempt === attempt,
      stop: () => {},
      inputs: [],
      shown: true,
      returns: true,
    };
  }

  // The page's own drawings of a thread: in the panel, on a seat or beside its passage.
  const drawingsOf = (id) => [
    ...[...document.querySelectorAll(THREAD)].filter(
      (node) => drawnThreadId(/** @type {HTMLElement} */ (node)) === id,
    ),
    surfaceFocusTarget(id, { part: "thread" }),
  ];
  const inView = (place) =>
    [
      ...(place.thread ? [threadPlace(place.thread), ...drawingsOf(place.thread)] : []),
      ...place.nodes,
    ].some(seen);

  // Whether `z` shows the gesture of the undo list's `entry` before taking it.
  function needsShowing(entry) {
    if (entry.picked_up) return true;
    const place = placeOf(entry.event);
    return Boolean(place) && !inView(place);
  }

  // Put the user on a thread, under the intent of the gesture that asked for it. A
  // thread the user sees drawn on the page is where they land; opening it could choose
  // another surface for it, as a margin card for a thread seated in a widget. A
  // settlement the log refuses returns the user here too (thread/folding.js).
  async function returnToThread(id, intent) {
    const seated = drawingsOf(id).find((node) => node && !inChrome(node) && seen(node));
    if (!seated) return openThread(id, { part: "thread", intent });
    intent.handoff(() => focusDestination(seated, "move"));
    return seated;
  }

  // Go to what the gesture changed, under the intent of the press that asked for it,
  // and resolve to the nodes that show it.
  async function show(event, intent = retainUserIntent()) {
    const place = placeOf(event);
    if (!place) return [];
    if (place.message) {
      const opened = await openThread(place.message, { part: "message", intent });
      return [opened, ...place.nodes].filter(Boolean);
    }
    if (place.thread)
      return [await returnToThread(place.thread, intent)].filter(Boolean);
    // A fragment link's own navigation step (anchor-travel.js, `followFragment`), so Back returns
    // to where the user was reading. The navigation step lands after this press returns, so the
    // show waits for it to finish where the Navigation API says when that is.
    const url = new URL(window.location.href);
    url.hash = place.fragment;
    if (window.navigation)
      await window.navigation.navigate(url.href).finished.catch(() => {});
    else window.location.assign(url);
    return place.nodes.filter(Boolean);
  }

  function arm(event) {
    disarm();
    let stop = () => {};
    const current = {
      is: (/** @type {{id: string}} */ other) => other.id === event.id,
      stop: () => stop(),
      inputs: [],
      shown: false,
      returns: false,
    };
    armed = current;
    notice(`Press again to undo: ${takes(event)}`);
    // What the press shows may still be on its way into view, so only leaving it after
    // it was seen clears the arm.
    void show(event).then((nodes) => {
      if (armed !== current) return;
      current.shown = true;
      if (!nodes.length) return;
      let landed = false;
      stop = whenNone(
        nodes,
        (node, clips) => {
          const shown = seenRect(node, clips);
          landed ||= Boolean(shown);
          return shown;
        },
        () => {
          if (landed && armed === current) disarm();
        },
      );
    });
  }

  // The walk needs the page settled, not only the gesture it takes back: an
  // unaccounted gesture is newer than the list's head, so the head would be the
  // gesture before the one the user just made, and a reading still being applied may
  // replace the list.
  function settled() {
    if (!stateApplying() && !unaccountedGesture()) return true;
    raiseError(WAIT);
    return false;
  }
  // Take back the undo list's `entry` by the header's three ways.
  function walkTo(entry) {
    const { event } = entry;
    // A landing's arm never stands in for showing what the agent has picked up.
    const taking = armedFor(event) && !(armed.returns && entry.picked_up);
    if (!taking && needsShowing(entry)) {
      arm(event);
      return null;
    }
    const returning = taking && armed.returns && retainUserIntent();
    const answer = withdraw(event);
    if (!answer) return null;
    disarm();
    if (returning)
      void whenDocumentPresented()
        .then(() => show(event, returning))
        .catch(() => {});
    return answer;
  }
  function undoLast() {
    if (!settled()) return null;
    // A press after one that showed a gesture, or after a settlement's landing, takes
    // that gesture, as its "Press again to undo" or its notice's Undo promised, even
    // where another tab's gesture has since become the newest.
    const promised = armed && runtime.undo.find(({ event }) => armed?.is(event));
    if (promised) return walkTo(promised);
    const [entry] = runtime.undo;
    return entry?.newest ? walkTo(entry) : null;
  }

  // The press a notice of the gesture made under `attempt` offers (notifications.js,
  // `press`), as a Resolve's "Resolved “…” · Undo" does (thread/folding.js). It takes
  // back that gesture as `z` takes the list's head, never what `z` would take by then,
  // and stands while the page can still take the gesture back, so the log refusing it,
  // or its withdrawal by any route, takes the notice away.
  const offerUndo = (attempt) => ({
    action: "undo",
    command: "history.undo",
    run() {
      if (!settled()) return null;
      const entry = runtime.undo.find(({ event }) => event.attempt === attempt);
      return entry ? walkTo(entry) : null;
    },
    stands: () => takeable()?.has(attempt) ?? true,
  });

  // The last thing the user did to this page, put back. Its own key rather than the
  // platform's ⌘Z, which belongs to the box a user is typing in and is taken by the
  // browser everywhere else: this is a page-level press like every other letter, and the
  // typing scope keeps it off a composer's words by claiming its letters. The word is
  // "undo" and never the verb it is about to state — `move` is one widget's word, and a
  // line that said it would be naming a member where the mechanism is what holds.
  pageCommand({
    id: "history.undo",
    ready: savedReadingSettled,
    keys: UNDO_KEYS,
    // Said from the list the page holds rather than `undoable`, so a reading being
    // applied leaves the words standing while it holds the press back. The menu's row
    // cuts long words, so it says the age at its end rather than after them. The words
    // stand whether the press will show or take: which it does turns on where the user
    // is reading when they press, which a scroll changes without a repaint.
    description: () => (head() ? `Undo: ${takes(head())}` : "Undo the latest update"),
    title: "undo",
    touch: () => (head() ? `Undo: ${said(head())}` : "Undo"),
    touchValue: () => (head() ? ago(head().ts) : ""),
    menu: "page",
    // Dead while the page holds a gesture no log read accounts for, this one's own send
    // included. The line drops the chip for as long as that is true rather than
    // promising a press that would undo the wrong thing.
    when: () => !unaccountedGesture() && Boolean(undoable()),
    run: (/** @type {Parameters<typeof undoLast>} */ ...args) => undoLast(...args),
  });

  return {
    landedAway,
    offerUndo,
    returnToThread,
    retainGesture,
    undoable,
    undoLast,
    withdraw,
  };
}
