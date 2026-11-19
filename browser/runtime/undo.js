/* Undo: the ⌘Z walk and the one door every withdrawal goes through.

   The server's view of the shown revision lists, newest first, the user's gestures this
   document can take back (`served_state/document.py`); nothing here judges an entry
   of it again. ⌘Z (Ctrl+Z off a Mac) takes the head of that list only when the server
   marks it `newest`, the user's newest gesture, so a gesture the list doesn't hold,
   such as a move a later revision's markup places, ends the walk. The one gesture ⌘Z takes from outside the
   list is an action still in this page's ledger (below). A widget's Undo, a reaction chip, and a
   reaction strip each name an exact entry, and a notice's Undo takes the gesture it
   reports by ⌘Z's rules (`offerUndo`). All of them withdraw
   through `withdraw`.

   ⌘Z says what it takes and how long ago that was made, in the command reference, the
   floating panel's menu row and the notice its undo leaves ("Undo: resolved “Rollout
   safety” 3d ago", then "Undone: resolved “Rollout safety” 3d ago"), in
   every tab and after a reload. The age follows the words with no separator, so it
   reads as when the gesture was made, not when the undo was; the notice says
   "Undone", Leaf's past participle, never "Undid" with its "I" left out (glossary.md,
   "Reader-facing words"). A thread goes by its name as it stands now, a rewrite
   by the words it replaced, a message by the words it was sent with and a reaction by
   where it stands, all of which the page already holds. An action's ids are words only
   in the document it was made in, so the server serves what the head did in that
   document's words (`gesture`, `GestureWords.gesture`), and the widget goes by its name
   on this page.
   An exact control's older entry carries no such reading, so its undo names only the
   widget. The age is the gesture's own `ts`, worded by the page's one clock (`ago`).

   ⌘Z takes the gesture back in the press, as an editor's undo does, and then leaves
   the user at its place: the thread a settlement or reaction is in, the message a
   rewrite changed or a reply the user sent, the message holding a widget an agent sent,
   the element changed, or the passage a comment was on, since taking a comment back
   may remove its thread. Where the place was out of view when the user pressed, the page
   shows it once it presents the withdrawal, the way an `lf-activity` row's link does,
   a thread opening and an element travelled to as its fragment, so Back returns to
   where the user pressed. Its notice says what was taken and how long ago. Visibility
   decides only whether the press travels, never whether it takes, so a reading of it
   that misses costs a scroll and never a press. It is read where each cover and each
   scroll Leaf runs comes to rest, so a press as a panel closes reads the page the
   closing leaves, and a press during the scroll a walk starts reads the page that
   scroll leaves. An exact control, such as a widget's Undo or a reaction chip, is
   pressed where its gesture is drawn, so its withdrawal moves nobody.

   Taking at once is the user's decision. Rejected: showing an out-of-view gesture with
   the first press and taking it with a second, so that a press never took what the user
   couldn't see. Its arm had to be cleared by every input, scroll and surface it met,
   and each reading of visibility that missed cost a press that took nothing, as when
   the press followed the Escape closing a panel. The notice and the travel tell the user
   what a press took instead.

   What ⌘Z, or a notice's Undo, took back takes a tint once the page shows the
   withdrawal, after the page has gone there if it was out of view (`tint`). It is the
   tint a message arriving and a revision's changed block take (motion.js,
   `backgroundFlash`), so the page marks every change it shows the same way. It tints
   the widget, message, thread or passage the undo changed, and a message the undo took
   away tints the thread that held it. The undo's notice stands until the user's next
   input rather than for its time (notifications.js, `holds`). Under reduced motion
   there is no tint, and the held notice says it alone. An exact control's withdrawal
   tints nothing, since the user pressed it where the gesture is drawn. The tint and the
   hold are the user's decision, over keeping a notice that leaves after 4 s, holding it
   in ink, darkening the panel's field, and an outline at twice the focus band's width.
   The user found the tint better to look at, and the band belongs to the marks of
   where the user is and what a gesture addresses (tokens.css). The tint stands where the
   user is already looking, or where the undo took them, and shows what changed rather
   than only naming it. It fades within about a second, since a tint held would lie
   over what the user reads, so the notice is what holds. A dark field is as loud, but
   at the window's foot, away from the change, and gives one notice a face no other
   control wears.

   A choice the user has just made may still be on its way to the log when they press,
   which is when a misclick is caught. The press takes it by its attempt, as the
   widget's own Undo does, and travels to it as to any other gesture: the ledger sends
   the undo once the log has the action (`travelling`). A message or a settlement still
   being sent can't be named before the log answers, so ⌘Z waits for it, as it waits
   for a reading being applied, for an older action still being presented, and for a
   held drag.

   A settlement takes the user's view of its thread away, so it leaves with this page
   the reader the user had the thread in, the page or the panel (`retainGesture`,
   `settled`, thread/folding.js), and taking it back returns the user there once the
   page presents the withdrawal, so undoing a settlement gives back the view it took,
   even where its landing carried them from the thread.

   A widget's gesture leaves, by its attempt, the words the widget named it by
   (`retainGesture`, `says`, pending/dispatch.js), and while this page holds them its
   undo is said in them, the name its own announcement used: "Chose “Fast”",
   then "Undone: Chose “Fast” just now". Those words and a settlement's reader live
   with the page that made the gesture, so after a reload or from another tab a thread
   opens where a route to it opens it. */
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
import { focusDestination } from "./focus.js";
import { placeBox, placeHolder } from "./geometry.js";
import { seenLanded } from "./scroll-containers.js";
import { messageHolding, threadName } from "./thread/messages.js";
import { surfaceFocusTarget } from "./thread/surfaces.js";
import { drawnThreadId, THREAD } from "./thread/selectors.js";
import { ago } from "./presence.js";
import { quotedWords as quoted } from "./words.js";
import { retainUserIntent } from "./user-intent.js";
import { raiseError } from "./errors.js";
import { dragHeld } from "./widget-elements.js";
import { backgroundFlash, flashDuration } from "./motion.js";

/** @template E
 * @typedef {E extends unknown ? Pick<E, Extract<keyof E, "id" | "kind" | "attempt" | "token" | "anchor" | "parent" | "message" | "text" | "widget" | "ts">> : never} GestureFields
 */
/** The fields a withdrawal reads, shared by an admitted event and a locally drawn gesture.
 * @typedef {import("../types/contract.js").CompleteUnion<GestureFields<ReturnType<typeof import("./thread/state.js").allThreads>[number]["root"] | import("./pending/dispatch.js").UndoCandidate | import("./framework/snapshot.js").Immutable<import("../types/domain.js").Event | import("../types/domain.js").Message>>>} UndoEvent
 * @typedef {typeof runtime.undo[number]} UndoEntry
 * @typedef {import("../types/contract.js").ServedGesture} Gesture
 * @typedef {ReturnType<typeof retainUserIntent>} UserIntent
 * @typedef {NonNullable<Parameters<OpenThread>[1]>["reader"]} Reader
 * @typedef {ReturnType<typeof import("./thread/destination.js").createThreadDestinations>["openPageThread"]} OpenThread
 * @typedef {{thread: string | null, message?: string, nodes: (Element | null)[], fragment?: never}
 * | {fragment: string, nodes: (Element | null)[], thread?: never, message?: never}} UndoPlace
 */

const WAIT = "Wait for the current change to finish before undoing";

// A widget as the chrome names it on this page, else the word for its kind.
/** @param {string | null | undefined} id */
function widgetNamed(id) {
  const element = elementById(id);
  if (!element) return "a widget";
  const label = addressableLabel(element);
  return label ? quoted(label) : `the ${addressableWord(element)}`;
}

// What an action did, from the server's reading of it in its own document. The verbs
// are core's: a widget's own verb, such as `move` or `edit`, may read as a noun, so a
// verb with no record form core knows is quoted as what was recorded.
/** @param {{widget?: string | undefined}} event @param {Gesture | undefined} gesture */
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

// What a gesture did, in the words the page holds for it now.
/** @param {UndoEvent} event @param {Gesture | undefined} gesture */
function gestureWords(event, gesture) {
  if (event.token) return `${event.token} reaction on ${reactionPlace(event)}`;
  switch (event.kind) {
    case "resolve":
    case "unresolve": {
      const thread = threadNamed(event.parent);
      const name = thread ? quoted(threadName(thread), 48) : "a thread";
      return `${event.kind === "resolve" ? "resolved" : "reopened"} ${name}`;
    }
    case "edit": {
      // By the words taking it back gives the message again, which the user wrote.
      const message = threadNamed(event.message)?.msgs.find(
        ({ id }) => id === event.message,
      );
      const was = message?.edited?.id === event.id ? message.edited.was : null;
      return `${event.text ? "edited" : "deleted"} ${was ? quoted(was, 48) : "a message"}`;
    }
    case "comment":
    case "reply":
      return `${event.kind === "comment" ? "commented" : "replied"} ${event.text ? quoted(event.text, 48) : "with a drawing"}`;
    default:
      return actionWords(event, gesture);
  }
}

// Where taking `event` back shows on the page: the thread it settled or reacted in, the
// message a rewrite changed or a reply the user sent, a widget an agent sent in a
// message (its message is its place), or the element it changed or a comment was on.
// A rewrite changes only its message's words, so the thread's passage or marker in view
// doesn't show it. Taking a comment back removes its thread unless an answer stands on
// it, which only the server's reading says, so its place is its passage, never the
// thread.
/** @param {UndoEvent} event @returns {UndoPlace | null} */
function placeOf(event) {
  const message =
    event.kind === "edit"
      ? event.message
      : event.kind === "reply" && !event.token
        ? event.id
        : null;
  if (message)
    return {
      thread: null,
      message,
      nodes: [
        ...document.querySelectorAll(`.lf-msg[data-lf-event="${CSS.escape(message)}"]`),
      ],
    };
  // A reaction in a thread is a reply naming the message it reacts to.
  if (event.kind === "resolve" || event.kind === "unresolve" || event.kind === "reply")
    return { thread: event.parent ? threadIdNamed(event.parent) : null, nodes: [] };
  const id = event.kind === "action" ? event.widget : event.anchor?.section;
  if (!id) return null;
  const held = messageHolding(id);
  if (held)
    return { thread: held.thread, message: held.message, nodes: [held.element] };
  return { fragment: id, nodes: [elementById(id)] };
}

// Whether the user sees any of a destination (an element or a Range) where the glides
// under way leave it, past whatever covers it where it comes to rest.
/** @param {Element | Range | null | undefined} where */
const seen = (where) => {
  const holder = where && placeHolder(where);
  return Boolean(where && holder && seenLanded(holder, placeBox(where), true));
};

const UNDO_KEYS = ["Mod+z"];

/** @param {{post: ReturnType<typeof import("./pending/dispatch.js").createCommandDispatch>["post"],
 * stateApplying: () => boolean, unaccountedGesture: () => boolean,
 * openThread: ReturnType<typeof import("./thread/destination.js").createThreadDestinations>["openPageThread"],
 * threadPlace: (id: string) => Element | Range | null}} dependencies */
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
  /** @typedef {{says?: string, settled?: {reader: Reader}}} GestureFacts */
  /** @type {Map<string, GestureFacts>} */
  const gestures = new Map();
  /** @param {string} attempt @param {GestureFacts} facts */
  function retainGesture(attempt, facts) {
    const live = takeable();
    if (live)
      for (const kept of gestures.keys()) if (!live.has(kept)) gestures.delete(kept);
    gestures.set(attempt, { ...gestures.get(attempt), ...facts });
  }
  // What taking `event` back takes: by the name its gesture was acknowledged by where
  // this page made it, else in the words the page holds for it now.
  /** @param {UndoEvent} event */
  const said = (event) => {
    // By attempt as well, since an action still in the ledger goes by its pending id.
    const gesture = runtime.undo.find(
      (entry) =>
        entry.event.id === event.id ||
        (event.attempt !== undefined && entry.event.attempt === event.attempt),
    )?.gesture;
    return (
      (event.attempt ? gestures.get(event.attempt)?.says : undefined) ??
      gestureWords(event, gesture)
    );
  };
  // ...and how long ago it was made, as one clause (the header).
  /** @param {UndoEvent} event */
  const takes = (event) => [said(event), ago(event.ts)].filter(Boolean).join(" ");

  // The gesture ⌘Z would take on the list the page holds now.
  const head = () => {
    const [first] = runtime.undo;
    return first?.newest ? first.event : null;
  };
  function undoable() {
    return stateApplying() ? null : head();
  }
  // The user's newest gesture while it is an action still in the ledger, which the list
  // doesn't hold yet. It goes by its pending id, the name the page draws it under until
  // a reading logs it and the ledger renames once the log answers
  // (pending/model.js, `nameAdmitted`), as the widget's own Undo names it. None while
  // a drag is held, since the widget draws nothing until the drag ends.
  const travelling = () => {
    if (dragHeld()) return null;
    const entry = readApplication().unresolved.findLast(
      ({ state }) => state !== "refused",
    );
    return entry?.event.kind === "action"
      ? { ...entry.event, id: entry.localId, ts: entry.timestamp }
      : null;
  };
  // The gesture the next press takes.
  const next = () => travelling() ?? head();
  // Whether taking back this exact gesture now takes back what the user sees. The
  // ordered ledger sends the undo behind everything already queued, the target's own
  // unanswered send included, and the server remains final admission. Two things it
  // cannot order: another action awaiting presentation may change which gestures
  // the page can honestly offer, whether or not its own POST has answered, and only
  // an action's withdrawal can name its target before the log does, so a message
  // the log has not taken waits for its answer.
  /** @param {UndoEvent} event */
  function withdrawable(event) {
    if (event.kind !== "action" && String(event.id).startsWith(PENDING)) return false;
    return !applicationState
      .unpresented()
      .some(
        (entry) =>
          entry.event.kind === "action" &&
          entry.localId !== event.id &&
          entry.admitted?.id !== event.id,
      );
  }

  // The one withdrawal door. Returns null when the page refuses the withdrawal now,
  // otherwise the delivery, which yields the admitted undo or null.
  /** @param {UndoEvent} event */
  function withdraw(event) {
    if (!withdrawable(event)) {
      raiseError(WAIT);
      return null;
    }
    const taken = takes(event);
    return post({ kind: "undo", undoes: event.id }).then((accepted) => {
      if (accepted) {
        notice(`Undone: ${taken}`, { holds: true });
        if (event.attempt) gestures.delete(event.attempt);
      }
      return accepted;
    });
  }

  // The page's own drawings of a thread: in the panel, on a seat or beside its passage.
  /** @param {string} id */
  const drawingsOf = (id) => [
    ...[...document.querySelectorAll(THREAD)].filter(
      (node) => drawnThreadId(node) === id,
    ),
    surfaceFocusTarget(id, { part: "thread" }),
  ];
  /** @param {UndoPlace} place */
  const inView = (place) =>
    [
      ...(place.thread ? [threadPlace(place.thread), ...drawingsOf(place.thread)] : []),
      ...place.nodes,
    ].some(seen);

  // Whether `event`'s place stands out of view, so taking it back travels there.
  /** @param {UndoEvent} event */
  function outOfView(event) {
    const place = placeOf(event);
    return place !== null && !inView(place);
  }

  // Put the user on a thread, under the intent of the gesture that asked for it: in the
  // reader a settlement named (thread/folding.js), else where they see it drawn on the
  // page, which needs no travel, else where a route to it opens it.
  /** @param {string} id @param {UserIntent} intent @param {Reader} [reader] */
  async function returnToThread(id, intent, reader = null) {
    if (reader) return openThread(id, { part: "thread", intent, reader });
    const seated = drawingsOf(id).find((node) => node && !inChrome(node) && seen(node));
    if (!seated) return openThread(id, { part: "thread", intent });
    intent.handoff(() => focusDestination(seated, "move"));
    return seated;
  }

  // A settlement this page made, with the reader it was made in.
  /** @param {UndoEvent} event */
  const settledHere = (event) =>
    event.attempt ? gestures.get(event.attempt)?.settled : undefined;

  // Go to what the gesture changed, under the intent of the press that asked for it: a
  // thread in the `reader` its settlement was made in, where it was made here.
  /** @param {UndoEvent} event @param {UserIntent} intent @param {Reader} [reader] */
  function show(event, intent, reader) {
    const place = placeOf(event);
    if (place?.message) return openThread(place.message, { part: "message", intent });
    if (place?.thread) return returnToThread(place.thread, intent, reader);
    if (place?.fragment === undefined || !intent()) return;
    // A fragment link's own navigation step (anchor-travel.js, `followFragment`), so
    // Back returns to where the user was reading.
    const url = new URL(window.location.href);
    url.hash = place.fragment;
    if (window.navigation)
      return window.navigation.navigate(url.href).finished.catch(() => {});
    window.location.assign(url);
  }

  // Tint what taking `event` back changed, as the page draws it now (the header): the
  // nodes at its place still drawn, else the thread a message it took away was in.
  /** @param {UndoEvent} event */
  function tint(event) {
    const place = placeOf(event);
    if (!place) return;
    const drawn = place.nodes.filter((node) => node?.isConnected);
    const thread =
      place.thread ??
      (event.kind === "reply" && event.parent ? threadIdNamed(event.parent) : null);
    for (const node of new Set(drawn.length ? drawn : thread ? drawingsOf(thread) : []))
      if (node) backgroundFlash(node, flashDuration());
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
  // Take back `event`, then leave the user at its place: for a settlement this page
  // made, its thread in the reader it was made in, else the place where it stood out of
  // view when they pressed. Both are read before the withdrawal, which takes the
  // settlement's reader with it. What it changed is tinted once the user is there.
  /** @param {UndoEvent} event */
  function walkTo(event) {
    const settled = settledHere(event);
    const travels = Boolean(settled) || outOfView(event);
    const intent = retainUserIntent();
    const answer = withdraw(event);
    if (!answer) return null;
    void whenDocumentPresented()
      .then(async () => {
        if (travels) await show(event, intent, settled?.reader);
        tint(event);
      })
      .catch(() => {});
    return answer;
  }
  function undoLast() {
    const action = travelling();
    if (action) return walkTo(action);
    if (!settled()) return null;
    const event = head();
    return event ? walkTo(event) : null;
  }

  // The press a notice of the gesture made under `attempt` offers (notifications.js,
  // `press`), as a Reopen's notice, or a Resolve's that leaves no thread open, offers
  // Undo (thread/folding.js, `nextStep`). It takes
  // back that gesture as ⌘Z takes the list's head, never what ⌘Z would take by then,
  // and stands while the page can still take the gesture back, so the log refusing it,
  // or its withdrawal by any route, takes the notice away.
  /** @param {string} attempt @returns {import("./notifications.js").NoticePress} */
  const offerUndo = (attempt) => ({
    action: "undo",
    command: "history.undo",
    run() {
      if (!settled()) return null;
      const entry = runtime.undo.find(({ event }) => event.attempt === attempt);
      return entry ? walkTo(entry.event) : null;
    },
    stands: () => takeable()?.has(attempt) ?? true,
  });

  // The last thing the user did to this page, put back, on the platform's undo chord
  // rather than a letter, the user's decision: an undo can change what is out of view,
  // so a word typed onto the page by someone who thought they were in a box must not
  // reach it. A box keeps every letter, with any modifier, for its words
  // (keyboard/text-entry.js), so ⌘Z undoes typing inside a box and a gesture outside
  // one, as Draw mode's takes back a stroke. Rejected: `z`, which `zazu` typed onto the
  // page presses twice; ⇧Z, which a capitalised word presses; and `g Z`, two presses
  // for every undo. Resolve keeps `r`, also the user's choice, since what it changes is
  // the thread in front of them. A chord is no printed key, so one pressed before the
  // page's history arrives isn't held for it (bootstrap.js) and does nothing. The word is
  // "undo" and never the verb it is about to state — `move` is one widget's word, and a
  // line that said it would be naming a member where the mechanism is what holds.
  pageCommand({
    id: "history.undo",
    ready: savedReadingSettled,
    keys: UNDO_KEYS,
    // Said from the gesture the next press takes (`next`) rather than `undoable`, so a
    // reading being applied leaves the words standing while it holds the press back.
    // The menu's row cuts long words, so it says the age at its end rather than after
    // them.
    description: () => {
      const event = next();
      return event ? `Undo: ${takes(event)}` : "Undo the latest update";
    },
    title: "undo",
    touch: () => {
      const event = next();
      return event ? `Undo: ${said(event)}` : "Undo";
    },
    touchValue: () => {
      const event = next();
      return event ? ago(event.ts) : "";
    },
    menu: "page",
    // Dead while the page holds a gesture no log read accounts for, other than an
    // action it can take by its attempt now, this one's own send included. The line
    // drops the chip for as long as that is true rather than promising a press that
    // would undo the wrong thing or only say to wait.
    when: () => {
      const action = travelling();
      return action
        ? withdrawable(action)
        : !unaccountedGesture() && Boolean(undoable());
    },
    run: (/** @type {Parameters<typeof undoLast>} */ ...args) => undoLast(...args),
  });

  return {
    offerUndo,
    returnToThread,
    retainGesture,
    undoable,
    undoLast,
    withdraw,
  };
}
