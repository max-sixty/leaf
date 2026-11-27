/* Undo: the ⌘Z walk and the one door every withdrawal goes through.

   The server's view of the shown revision lists, newest first, the user's gestures this
   document can take back (`served_state/document.py`); nothing here judges an entry
   of it again. ⌘Z (Ctrl+Z off a Mac) takes the head of that list only when the server
   marks it `newest`, the user's newest gesture, so a gesture the list doesn't hold,
   such as a move a later revision's markup places, ends the walk. Outside the list, ⌘Z
   takes only a gesture this page holds and the list doesn't: an action still in this
   page's ledger, or the edit it last discarded (below). A widget's Undo, a reaction
   chip, and a reaction strip each name an exact entry, and a notice's Undo is ⌘Z's own
   press, offered while ⌘Z would take the gesture the notice reports (`offerUndo`).
   Every withdrawal from the log goes through `withdraw`.

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

   ⌘Z takes the gesture back in the press, as an editor's undo does, and then leaves the
   user at its place: the thread a settlement or reaction is in, the message a rewrite
   changed or a reply the user sent, the message holding a widget an agent sent, the
   element changed, or the passage a comment was on, since taking a comment back may
   remove its thread. Where the place was out of view when the user pressed, the page
   shows it once it presents the withdrawal. A thread opens where every route opens it.
   An element is revealed where it stands, opening what hides it, such as the deck card
   an answer moved on from, and the user is put on it; the page scrolls it to its start
   only where it isn't shown there already, as a widget's datum is landed
   (features/anchor-travel.js, `navigateToDatum`). Neither adds a Back step. Rejected:
   travelling to the element as a link to its fragment does, with a Back step. That
   landing puts the element's start at the window's top even where it already shows, so
   undoing an answer in a deck scrolled the card coming back where it stood up by most
   of a window. ⌘Z's notice says what was taken and how long ago. Visibility decides
   only whether the press travels, never whether it takes, so a reading of it that
   misses costs a scroll and never a press. It is read where each cover and each scroll
   Leaf runs comes to rest, so a press as a panel closes reads the page the closing
   leaves, and a press during the scroll a walk starts reads the page that scroll
   leaves. An exact control, such as a widget's Undo or a reaction chip, is pressed
   where its gesture is drawn, so its withdrawal moves nobody. Should this reading of
   visibility keep needing fixes, a simpler design is open: ⌘Z returns the user to where
   they stood when they made the gesture in this tab (records/history.js, `readPlace`),
   and otherwise moves nobody. That drops travel to a gesture made far from where the
   user stands, which the notice still names.

   Taking at once is the user's decision. Rejected: showing an out-of-view gesture with
   the first press and taking it with a second, so that a press never took what the user
   couldn't see. Its arm had to be cleared by every input, scroll and surface it met,
   and each reading of visibility that missed cost a press that took nothing, as when
   the press followed the Escape closing a panel. The notice and the travel tell the user
   what a press took instead.

   What ⌘Z, or a notice's Undo, took back takes a tint once the page shows the
   withdrawal, after the page has gone there if it was out of view (`tint`). It is the
   tint a message arriving and a revision's changed block take (dom/motion.js,
   `backgroundFlash`), so the page marks every change it shows the same way. It tints
   the widget, message, thread or passage the undo changed, and a message the undo took
   away tints the thread that held it. The undo's notice stands its time and then until
   the user's next input (transport/notifications.js, `showNotice`). Under reduced motion
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

   A settlement takes the user's view of its thread away, so this page notes that it
   made one (`retainGesture`, `settled`, records/thread/folding.js), and taking it back returns
   the user to the thread once the page presents the withdrawal, even where its landing
   carried them from the thread. The thread opens where every route opens it
   (records/thread/destination.js), by the user's choice of where threads open. Rejected:
   keeping with the gesture the reader the settlement was made in, a second record of
   where the thread opens beside the user's choice.

   A widget's gesture leaves, by its attempt, the words the widget named it by
   (`retainGesture`, `says`, records/pending/dispatch.js), and while this page holds them its
   undo is said in them, the name its own announcement used: "Chose “Fast”",
   then "Undone: Chose “Fast” just now". Those words and a settlement's mark live
   with the page that made the gesture, so after a reload or from another tab a thread
   opens where a route to it opens it.

   Taking back what the user wrote puts it to draft rather than discarding it, since no
   redo brings it back (`writtenIn`; records/drafts.js, `giveBackWords`): a comment's words, and
   its drawing, go back to its passage's draft or the page's, a reply's to its thread's
   reply box, and a rewrite's to the message's rewrite, and Resume writing goes to them.
   A comment whose thread goes with it brings the words of that thread's reply box
   along, after its own, so nothing the user wrote is left in a box that no longer
   stands. The log's answer decides the undo, so the words come back with it, in the box
   the press leaves the user at. Rejected: leaving the words only in the log, which no
   reading shows once nothing stands on the message (the user's decision); and holding
   the reply unseen with the comment's draft until it is sent again, as a refused
   comment does (`keepRefusedWords`), which carried it under whatever was sent from
   that box next.

   A box's Discard or Escape throws its changed words away (records/drafts.js, `discardDraft`),
   a gesture of the user's that never reaches the log, so this page keeps it, the
   latest only, until the document reloads (`keepDiscard`). ⌘Z takes it back while it
   is the user's newest gesture: while every other gesture the page can take back was
   logged by the reading the page held when it was made, or was on its way from this
   page then. So a newer gesture, in this tab or another, takes ⌘Z from it until that
   gesture is taken back, a list that arrives after it, as one does between versions,
   is ordered the same way, and no clock decides.
   Taking it back gives its words back to their draft, as taking a message back does,
   and puts the user in its box where Resume writing opens it, which is tinted
   (`takeDiscard`). Its notice, "Edit discarded", offers ⌘Z's press by the rule above
   (`offerUndo`), and under a finger the menu's Undo row takes it. Those are the one
   way back: after a newer gesture, the user takes that one back first (the user's
   decision). Rejected, by the user: Restore discarded edit (`g D`), which took the
   discard back past any newer gesture, a second route to one result with a row of its
   own under a phone's Navigate; and, while only a rewrite's Escape discarded, a timed
   Undo chip after the discard, a target the user cannot learn (transport/notifications.js). */
import { notice } from "../transport/notifications.js";
import {
  applicationState,
  readApplication,
  whenDocumentPresented,
} from "../state/semantic-state.js";
import { runtime } from "../state/context.js";
import { pageCommand } from "../dom/keyboard/register.js";
import { savedReadingSettled } from "../dom/keyboard/bindings.js";
import { PENDING } from "../state/thread/identity.js";
import { threadIdNamed, threadNamed } from "./thread/state.js";
import { addressableLabel } from "../readings/addressable-names.js";
import { addressableWord } from "../lib/element-word.js";
import { elementById } from "../readings/passages.js";
import { placeBox, placeHolder } from "../dom/geometry.js";
import { seenLanded } from "../readings/scroll-containers.js";
import { alreadyShown } from "../readings/landing-scroll.js";
import {
  anchorLabel,
  messageHolding,
  messageWords,
  threadName,
} from "./thread/messages.js";
import { surfaceFocusTarget } from "./thread/surfaces.js";
import { drawnThreadId, THREAD } from "./thread/selectors.js";
import { ago, saidNow } from "../state/presence.js";
import { quotedWords as quoted } from "../lib/words.js";
import { retainUserIntent } from "../dom/user-intent.js";
import { raiseError } from "../transport/errors.js";
import { dragHeld } from "../dom/widget-elements.js";
import { backgroundFlash } from "../dom/motion.js";
import {
  commentDraft,
  giveBackWords,
  keepDiscardsWith,
  PAGE_DRAFT,
  replyContext,
  rewriteContext,
  threadDraft,
} from "./drafts.js";
import { aimTargetAt } from "../readings/anchor-resolution.js";
import { threadKey } from "../state/thread/model.js";
import { inChrome } from "../base/ui-marks.js";
import { randomId } from "../base/ids.js";
import { focused } from "../dom/focus.js";
import { signal } from "/vendor/signals-core.js";
import type { CompleteUnion, EventMap, ServedGesture } from "../../types/contract.js";
import type { Discarded, DraftRoute } from "./drafts.js";
import type { createThreadDestinations } from "./thread/destination.js";
import type { Anchor, Event, Message } from "../../types/domain.js";
import type { createCommandDispatch, UndoCandidate } from "./pending/dispatch.js";
import type { Arrive } from "../dom/arrival-plan.js";
import type { NoticePress } from "../transport/notifications.js";
import type { threadList } from "./thread/state.js";
import type { Immutable } from "../base/snapshot.js";

type GestureFields<E> = E extends unknown
  ? Pick<
      E,
      Extract<
        keyof E,
        | "id"
        | "kind"
        | "attempt"
        | "emoji"
        | "anchor"
        | "parent"
        | "message"
        | "text"
        | "widget"
        | "ts"
        | "drawing"
        | "suggestion"
        | "about"
        | "revision"
        | "base"
      >
    >
  : never;
/** The fields a withdrawal reads, shared by an admitted event and a locally drawn gesture. */
type UndoEvent = CompleteUnion<
  GestureFields<
    | ReturnType<typeof threadList>[number]["root"]
    | UndoCandidate
    | Immutable<Event | Message>
  >
>;
type Discard = Omit<Discarded, "at"> & {
  kind: "discard";
  attempt: string;
  ts: string;
  before: { seq: number; attempts: ReadonlySet<string> };
  message: string | null;
  widget: string | null;
};
type Gesture = ServedGesture;
type UserIntent = ReturnType<typeof retainUserIntent>;
type UndoPlace =
  | {
      thread: string | null;
      message?: string;
      nodes: (Element | null)[];
      fragment?: never;
    }
  | { fragment: string; nodes: (Element | null)[]; thread?: never; message?: never };

const WAIT = "Wait for the current change to finish before undoing";

// A widget as the chrome names it on this page, else the word for its kind.
function widgetNamed(id: string | null | undefined) {
  const element = elementById(id);
  if (!element) return "a widget";
  const label = addressableLabel(element);
  return label ? quoted(label) : `the ${addressableWord(element)}`;
}

// What an action did, from the server's reading of it in its own document. The verbs
// are core's: a widget's own verb, such as `move` or `edit`, may read as a noun, so a
// verb with no record form core knows is quoted as what was recorded.
function actionWords(
  event: { widget?: string | undefined },
  gesture: Gesture | undefined,
) {
  const widget = widgetNamed(event.widget);
  switch (gesture?.form) {
    case "choice":
      return `chose ${gesture.chosen.map((words) => quoted(words)).join(", ") || "nothing"} in ${widget}`;
    case "move":
      return `moved ${quoted(gesture.unit)}${gesture.to ? ` to ${quoted(gesture.to)}` : ""} in ${widget}`;
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

// Where a reaction stands, as Threads names its anchor.
function reactionPlace(event: {
  kind: string;
  anchor?: Anchor | null | undefined;
  about?: EventMap["comment"]["about"];
}) {
  if (event.kind === "reply") return "the reply";
  if (!event.anchor) return "the page";
  return anchorLabel(event.anchor, event.about);
}

// What a gesture did, in the words the page holds for it now.
function gestureWords(event: UndoEvent, gesture: Gesture | undefined) {
  if (event.emoji) return `${event.emoji} reaction on ${reactionPlace(event)}`;
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
function placeOf(event: UndoEvent): UndoPlace | null {
  const message =
    event.kind === "edit"
      ? event.message
      : event.kind === "reply" && !event.emoji
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

// The draft a message the user wrote was written in, holding what taking it back gives
// back: a comment's words, and its drawing, to its passage's draft or the page's, with
// the reply box of the thread it opened (`under`); a reply's to its thread's reply box;
// a rewrite's to the message's rewrite, written over the words taking it back restores.
// A reaction that opened a thread writes no words, so it brings only that reply box's.
// Null for a deletion, whose words come back on the message, and every other gesture
// that wrote none.
function writtenIn(
  event: UndoEvent,
): { ctx: string; text: string; payload?: object; under?: string | null } | null {
  const text = event.text ?? "";
  switch (event.kind) {
    case "comment": {
      const { anchor } = event;
      const thread = threadNamed(event.id);
      const under = thread ? replyContext(threadKey(thread)) : null;
      if (anchor) return { ...commentDraft({ ...event, anchor }), text, under };
      return text ? { ctx: PAGE_DRAFT, text, under } : null;
    }
    case "reply": {
      const thread = event.parent ? threadNamed(event.parent) : null;
      return thread && text ? { ctx: replyContext(threadKey(thread)), text } : null;
    }
    case "edit":
      return text
        ? {
            ctx: rewriteContext(event.message),
            text,
            ...(typeof event.base === "string" && { payload: { over: event.base } }),
          }
        : null;
    default:
      return null;
  }
}

// Whether the user sees any of a destination (an element or a Range) where the glides
// under way leave it, past whatever covers it where it comes to rest.
const seen = (where: Element | Range | null | undefined) => {
  const holder = where && placeHolder(where);
  return Boolean(where && holder && seenLanded(holder, placeBox(where), true));
};

const UNDO_KEYS = ["Mod+z"];

export function createUndo({
  post,
  stateApplying,
  unaccountedGesture,
  openThread,
  threadPlace,
  arrive,
  resumeDraft,
}: {
  post: ReturnType<typeof createCommandDispatch>["post"];
  stateApplying: () => boolean;
  unaccountedGesture: () => boolean;
  openThread: ReturnType<typeof createThreadDestinations>["openPageThread"];
  threadPlace: (id: string) => Element | Range | null;
  arrive: Arrive;
  resumeDraft: (context: string, route?: DraftRoute) => Promise<void>;
}) {
  // The edit this page last discarded, while it can be taken back (`keepDiscard`).
  const discard = signal<Discard | null>(null);
  // The attempts of the gestures on their way to the log, less those it refused.
  const sending = () =>
    readApplication().unresolved.flatMap((entry) =>
      entry.state === "refused" ? [] : [entry.event.attempt],
    );
  // The attempts of the gestures the page can still take back: on their way to the
  // log, on the undo list, or the edit last discarded. One taken back is in none. Null
  // between versions, when the page holds no undo list.
  function takeable() {
    const { view } = readApplication().effective;
    if (!view) return null;
    const discarded = discard.value;
    return new Set([
      ...view.undo.map(({ event }) => event.attempt),
      ...sending(),
      ...(discarded ? [discarded.attempt] : []),
    ]);
  }
  // Kept while its gesture can still be taken back.
  type GestureFacts = { says?: string; settled?: boolean };
  const gestures = new Map<string, GestureFacts>();
  function retainGesture(attempt: string, facts: GestureFacts) {
    const live = takeable();
    if (live)
      for (const kept of gestures.keys()) if (!live.has(kept)) gestures.delete(kept);
    gestures.set(attempt, { ...gestures.get(attempt), ...facts });
  }
  // What a discard was an edit of: a rewrite's message by its words, as taking a
  // rewrite back says it, else the element its box stood in, as an action's undo names
  // its widget.
  const editOf = ({ message: id, widget }: Discard) => {
    if (id === null) return widgetNamed(widget);
    const message = threadNamed(id)?.msgs.find((one) => one.id === id);
    return message ? quoted(messageWords(message), 48) : "a message";
  };
  // What taking `event` back takes: by the name its gesture was acknowledged by where
  // this page made it, else in the words the page holds for it now; a discard by the
  // words taking it back gives back.
  const said = (event: UndoEvent | Discard) => {
    if (event.kind === "discard") return `discarded an edit of ${editOf(event)}`;
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
  const takes = (event: UndoEvent | Discard) =>
    [said(event), ago(event.ts)].filter(Boolean).join(" ");

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
  // (state/pending/model.js, `nameAdmitted`), as the widget's own Undo names it. None while
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
  // The discard while it is the user's newest gesture: each other gesture on the list
  // was logged by the reading the page held when it was made, or was on its way from
  // this page then (`keepDiscard`).
  const newestDiscard = () => {
    const held = discard.value;
    const { view } = readApplication().effective;
    if (!held || !view) return null;
    const { seq, attempts } = held.before;
    const newer = (attempt: string | undefined) =>
      attempt === undefined || !attempts.has(attempt);
    return view.undo.some(({ event }) => event.seq > seq && newer(event.attempt)) ||
      sending().some(newer)
      ? null
      : held;
  };
  // The user's newest gesture while this page holds it and the list doesn't: the edit
  // it last discarded, which never reaches the log, or an action still in the ledger.
  const local = () => newestDiscard() ?? travelling();
  // The gesture the next press takes.
  const next = () => local() ?? head();
  // Whether taking back this exact gesture now takes back what the user sees. The
  // ordered ledger sends the undo behind everything already queued, the target's own
  // unanswered send included, and the server remains final admission. Two things it
  // cannot order: another action awaiting presentation may change which gestures
  // the page can honestly offer, whether or not its own POST has answered, and only
  // an action's withdrawal can name its target before the log does, so a message
  // the log has not taken waits for its answer.
  function withdrawable(event: UndoEvent) {
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
  function withdraw(event: UndoEvent) {
    if (!withdrawable(event)) {
      raiseError(WAIT);
      return null;
    }
    const taken = takes(event);
    const written = writtenIn(event);
    return post({ kind: "undo", undoes: event.id }).then((accepted) => {
      if (accepted) {
        notice(`Undone: ${taken}`, { holds: true });
        // The answer brings the reading that holds the withdrawal, in which a
        // comment's thread is gone unless something stands on the comment.
        if (written)
          giveBackWords(
            written.ctx,
            written.text,
            written.payload,
            written.under && !threadNamed(event.id) ? written.under : null,
          );
        if (event.attempt) gestures.delete(event.attempt);
      }
      return accepted;
    });
  }

  // The page's own drawings of a thread: in the panel, on a seat or beside its passage.
  const drawingsOf = (id: string) => [
    ...[...document.querySelectorAll(THREAD)].filter(
      (node) => drawnThreadId(node) === id,
    ),
    surfaceFocusTarget(id, { part: "thread" }),
  ];
  const inView = (place: UndoPlace) =>
    [
      ...(place.thread ? [threadPlace(place.thread), ...drawingsOf(place.thread)] : []),
      ...place.nodes,
    ].some(seen);

  // Whether `event`'s place stands out of view, so taking it back travels there.
  function outOfView(event: UndoEvent) {
    const place = placeOf(event);
    return place !== null && !inView(place);
  }

  // Put the user on a thread, under the intent of the gesture that asked for it, where a
  // route to it opens it (records/thread/destination.js), which reads the user's choice of
  // where threads open. Where the user sees the thread drawn on the page, as in a
  // widget's seat, the route doesn't travel, and `travel` is the route's too. A return
  // adds no Back step (records/history.js), whether an undo or the log refusing a
  // settlement asked for it.
  function returnToThread(
    id: string,
    intent: UserIntent,
    { travel = true }: { travel?: boolean } = {},
  ) {
    const drawn = drawingsOf(id).some((node) => node && !inChrome(node) && seen(node));
    return openThread(id, {
      part: "thread",
      intent,
      travel: travel && !drawn,
      history: false,
    });
  }

  // Whether this page made the settlement `event` is.
  const settledHere = (event: UndoEvent) =>
    Boolean(event.attempt && gestures.get(event.attempt)?.settled);

  // Go to what the gesture changed, under the intent of the press that asked for it,
  // travelling there where `travel` says the place stood out of view. Neither route
  // adds a Back step, and an element is arrived at where it stands (the header).
  function show(event: UndoEvent, intent: UserIntent, travel: boolean = true) {
    const place = placeOf(event);
    if (place?.message)
      return openThread(place.message, {
        part: "message",
        intent,
        travel,
        history: false,
      });
    if (place?.thread) return returnToThread(place.thread, intent, { travel });
    const id = place?.fragment;
    if (id === undefined) return;
    return arrive(
      () => {
        const where = elementById(id);
        return (
          where && {
            where,
            focus: where,
            scroll: [
              {
                at: where,
                block: "start",
                when: () => !alreadyShown(where, { block: "start" }),
              },
            ],
          }
        );
      },
      { intent },
    );
  }

  // Tint what taking `event` back changed, as the page draws it now (the header): the
  // nodes at its place still drawn, else the thread a message it took away was in.
  function tint(event: UndoEvent) {
    const place = placeOf(event);
    if (!place) return;
    const drawn = place.nodes.filter((node) => node?.isConnected);
    const thread =
      place.thread ??
      (event.kind === "reply" && event.parent ? threadIdNamed(event.parent) : null);
    for (const node of new Set(drawn.length ? drawn : thread ? drawingsOf(thread) : []))
      if (node) backgroundFlash(node);
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
  // made, its thread, else the place where it stood out of view when they pressed. Both
  // are read before the withdrawal, which takes the settlement's mark with it. What it
  // changed is tinted once the user is there. Only a place out of view is travelled to;
  // a thread in view opens where the user stands.
  function walkTo(event: UndoEvent) {
    const settled = settledHere(event);
    const away = outOfView(event);
    const travels = settled || away;
    const intent = retainUserIntent();
    const answer = withdraw(event);
    if (!answer) return null;
    void whenDocumentPresented()
      .then(async () => {
        if (travels) await show(event, intent, away);
        tint(event);
      })
      .catch(() => {});
    return answer;
  }
  // Take a discard back: its words go back to their draft as a withdrawn message's do
  // (records/drafts.js, `giveBackWords`), and the user is put in their box where Resume writing
  // opens it, which is tinted once they stand in it. The box is the discard's place, so
  // the route travels where it stood out of view, as for any undo.
  async function takeDiscard(held: Discard) {
    const intent = retainUserIntent();
    const taken = takes(held);
    discard.value = null;
    giveBackWords(held.ctx, held.text, held.payload);
    notice(`Undone: ${taken}`, { holds: true });
    await resumeDraft(held.ctx, { intent });
    const box = focused();
    if (intent() && box) backgroundFlash(box);
  }
  function undoLast() {
    const held = local();
    if (held) return held.kind === "discard" ? takeDiscard(held) : walkTo(held);
    if (!settled()) return null;
    const event = head();
    return event ? walkTo(event) : null;
  }

  // The press a notice of the gesture made under `attempt` offers (transport/notifications.js,
  // `press`), as a Reopen's notice, or a Resolve's that leaves no thread open, offers
  // Undo (records/thread/folding.js, `nextStep`). It names ⌘Z's command only while ⌘Z would
  // take that gesture: once another gesture of the user's is the newest, it names no
  // command, and the notice keeps its words without a press. The notice stands
  // while the page can still take the gesture back (`stands`), so the log refusing it,
  // or its withdrawal by any route, takes the notice away. The user chose dropping the
  // press over keeping one that took back its own gesture while the ⌘Z it showed took
  // the newer one: a press showing ⌘Z does what ⌘Z does.
  const offerUndo = (attempt: string): NoticePress => ({
    action: "undo",
    get command() {
      return next()?.attempt === attempt ? "history.undo" : null;
    },
    stands: () => takeable()?.has(attempt) ?? true,
  });

  // A box's Discard or Escape is a gesture of the user's (the header), kept until
  // another takes its place or the document reloads.
  function keepDiscard({ at, ...discarded }: Discarded) {
    const attempt = randomId();
    // What it was an edit of, read while its box stands: a rewrite's message, else the
    // element a press on the box aims at.
    const rewrite = threadDraft(discarded.ctx);
    const message = rewrite?.part === "rewrite" ? rewrite.name : null;
    const widget =
      message === null && at ? (aimTargetAt(at)?.anchor.section ?? null) : null;
    // Both stand whether or not the page holds an undo list now, as between versions,
    // so a list that arrives later is ordered by them. A page that has read none of the
    // log has read through none of it.
    const before = {
      seq: runtime.lastEventSeq ?? 0,
      attempts: new Set(sending()),
    };
    discard.value = {
      ...discarded,
      kind: "discard",
      attempt,
      ts: saidNow(),
      before,
      message,
      widget,
    };
    notice("Edit discarded", { press: offerUndo(attempt) });
  }
  keepDiscardsWith(keepDiscard);

  // The last thing the user did to this page, put back, on the platform's undo chord
  // rather than a letter, the user's decision: an undo can change what is out of view,
  // so a word typed onto the page by someone who thought they were in a box must not
  // reach it. A box keeps every letter, with any modifier, for its words
  // (dom/keyboard/text-entry.js), so ⌘Z undoes typing inside a box and a gesture outside
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
      const held = local();
      return held
        ? held.kind === "discard" || withdrawable(held)
        : !unaccountedGesture() && Boolean(undoable());
    },
    run: (...args: Parameters<typeof undoLast>) => undoLast(...args),
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
