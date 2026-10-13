/* The Questions walk: `q` and Shift+`q` page through everything waiting on the user,
   in page order: the Questions the panel lists first (queue-panel.js). The panel opens with
   `g Q`, as the Threads panel opens with `g T` and `t` walks the threads.

   What waits on the user is the application's one reading, `queues.questions`
   (the server's `served_state.queues`, with this tab's sends placed against it): each open
   ask or to-do on the user, each thread holding a resend, and each page widget action
   handed back to them. The walk does not decide membership; it stops once at each place
   an item is arrived at, so a thread holding an open ask is reached as that ask. `t` still walks every open thread
   (navigation.js).

   Arrival belongs to the item's owner, so the walk adds no arrival of its own beside
   theirs: an ask arrives through the ask view's `arriveAtAsk`; a thread through the
   t/T walk's own (navigation.js, `arriveAtThread`), so it lands wherever that walk
   lands; a page widget action, or a to-do on an element or the page, by travel's `arrive`,
   onto the widget the action was made on, the element, or the page's head; the
   version's approval by the chrome showing it, travel onto the banner's control or
   the floating panel's own arrival (banner.js, `registerApprovalPresentation`).
   A Questions panel row arrives through the same function (`arriveAtItem`), for an item on
   either list or one that is done.

   A walk starts from the user's place, in this order:

   1. current focus;
   2. selection or caret;
   3. the current visible reading block.

   `walkOrigin` reads that place from the browser on each press, for this walk and the
   thread walk alike. There is no remembered destination underneath those readings, and
   the chrome is a binding badge, not a page position, so its controls do not become the
   walk's origin. The user stands on an item when they stand in its ask, in its thread
   (`threadHere`), or in its widget or element, and the press steps off it. Standing on
   a to-do Done ends, `x` is that Done, a step on the banner's row under a finger
   (`queue-api.js`, `done`): the user's `todo_end`, which leaves Questions in the turn it is pressed.

   Page order is each item's place in the page as rendered: an ask's own element, or its
   thread's passage for an ask seated in a thread; a thread's passage; the widget an action
   was made on or the element a to-do is on; the page's head for a to-do on the whole
   page. An item with no place on the page, a general thread or one whose passage is
   gone, comes after every placed one in the list's own order, as the t/T walk reaches
   such threads from its list's ends. A step past either end comes round to the other.

   The walk can also step within one region of the page (`askActions.next`, as an
   `lf-tally`'s Next question presses it): its stops are then the asks waiting on the user
   that the region holds (`asksIn`, asks/place.js), stepped by the same standing and
   page order, and its position counts them alone. A press from outside the region, such as
   one on the tally's own control above it, counts from the ask the user last went to, if
   it is in the region: Tab and Shift+Tab pass over what they cross on the way to the
   control, so they keep it, while any other move the user makes ends it. Without one it
   counts from the first of the region's asks they see, as a place they are at without
   standing on it, and with none in sight it enters at the region's edge, Next at the
   first and Previous at the last. That ask, kept by identity
   so a revision replacing its node keeps it, is the one place the walk keeps, and only
   this case reads it: anywhere else the user's own place decides.

   Experimental: the lists and the walk over them are new, and their shape is
   expected to change a lot (notes/what-needs-you/). Change them freely.
*/
import { cycledRow, savedReadingSettled } from "./keyboard/bindings.js";
import { pageCommand, pageScope } from "./keyboard/register.js";
import { paintKeys } from "./keyboard/scopes.js";
import { focused, onStanding } from "./focus.js";
import { coarsePointer } from "./pointer.js";
import { askHolding, placeOf, stepFrom, walkOrigin } from "./standing-target.js";
import { seenRect } from "./geometry.js";
import { elementById, inChrome, pageDocument } from "./passages.js";
import { byRenderedOrder, inUi, under } from "./shadow.js";
import { readAsks } from "./asks/model.js";
import { asksIn, askPlace } from "./asks/place.js";
import { readQueues, queueItemKey } from "./queue-api.js";
import { itemNoun } from "./queues.js";
import { watchSemantic } from "./semantic-state.js";
import { retainUserIntent } from "./user-intent.js";
import { beginWalk, listWalkPosition, walkPositionLabel } from "./walk-position.js";
import { approvalTarget, presentedApproval } from "./banner.js";

const QUALIFIER = "waiting on me";
const WITHIN = "waiting on me here";
const NOUNS = Object.freeze({
  ask: "Ask",
  thread: "Thread",
  widget: "Update",
  page: "To-do",
  approval: "Approval",
});
// What a stop is called: by where it is arrived at, but a to-do on an element is a To-do
// rather than the Update a widget's stop otherwise is.
const nounOf = (item, stop) =>
  stop.kind === "widget" && itemNoun(item) === "todo" ? "To-do" : NOUNS[stop.kind];

// Where an item of either list, or one that is done, is arrived at: a widget ask by
// the ask's own id, anything else by the thread it stands in, a to-do on the page as a
// whole at the page's head, or else the element it stands on, as an action is arrived at
// on the widget it was made on.
const stopOf = (item) =>
  item.kind === "ask" && item.ask.source.kind === "approval"
    ? { kind: "approval", id: item.id, thread: null }
    : item.kind === "ask" && item.ask.source.kind === "widget"
      ? { kind: "ask", id: item.id, thread: item.thread, ask: item.ask }
      : item.thread !== null
        ? { kind: "thread", id: item.thread, thread: item.thread }
        : item.subject.kind === "page"
          ? { kind: "page", id: "page", thread: null }
          : { kind: "widget", id: item.subject.id, thread: null };
const sameStop = (a, b) => a.kind === b.kind && a.id === b.id;

// The page's head, where a to-do on the page as a whole is arrived at: its first
// top-level heading, or its first element.
const pageHead = () =>
  [...document.querySelectorAll("h1")].find((heading) => !inChrome(heading)) ??
  pageDocument() ??
  document.body.firstElementChild;

export function createQueueWalk({
  arriveAtAsk,
  arriveAtThread,
  threadHere,
  threadPlace,
  prepareTrip,
  arrive,
  readableDestination,
  announce,
  actions,
}) {
  // The element a stop stands at on the page, if it has one.
  const stopElement = (stop) =>
    stop.kind === "approval"
      ? approvalTarget()
      : stop.kind === "ask"
        ? stop.thread !== null
          ? threadPlace(stop.thread)
          : askPlace(stop.ask).node
        : stop.kind === "page"
          ? pageHead()
          : stop.thread !== null
            ? threadPlace(stop.thread)
            : elementById(stop.id);

  function stops() {
    const list = [];
    const listed = new Set();
    for (const item of readQueues().questions) {
      const stop = stopOf(item);
      // Two items arrived at in one place, such as two to-dos on one thread, are one
      // stop.
      if (listed.has(`${stop.kind}:${stop.id}`)) continue;
      listed.add(`${stop.kind}:${stop.id}`);
      const at = stopElement(stop);
      list.push({
        ...stop,
        key: `${stop.kind}:${stop.id}`,
        noun: nounOf(item, stop),
        place: at?.isConnected && !inChrome(at) ? at : null,
      });
    }
    return byRenderedOrder(list, (stop) => stop.place);
  }

  // The stops of a walk within `region`: the asks waiting on the user it holds.
  function stopsWithin(region) {
    const held = new Set(asksIn(region).map((ask) => ask.id));
    return stops().filter((stop) => stop.kind === "ask" && held.has(stop.id));
  }
  const stopsOf = (region) => (region ? stopsWithin(region) : stops());

  // The item the user stands on, if any: the thread holding them, the ask holding their
  // place, or the innermost element that does, in page order the last that holds them,
  // as `askHolding` reads asks. The page's own stop is its head element alone, never
  // what that holds, since on a page without a heading the head is `main`. Standing in
  // a thread that holds an open ask is not standing on that ask. `here` is the place
  // the step counts from, the user's own unless a caller names another.
  function standingStop(list, here = walkOrigin()) {
    if (focused(document) === approvalTarget())
      return list.find((stop) => stop.kind === "approval") ?? null;
    const held = threadHere();
    const thread = held?.dataset.id ?? held?.dataset.thread;
    if (thread) {
      const stop = list.find(
        (candidate) => candidate.kind === "thread" && candidate.id === thread,
      );
      if (stop) return stop;
    }
    if (!here) return null;
    const ask = askHolding(readAsks().all, placeOf(here));
    if (ask) {
      const stop = list.find(
        (candidate) => candidate.kind === "ask" && candidate.id === ask.id,
      );
      if (stop) return stop;
    }
    return (
      list.findLast((stop) => {
        if (stop.kind === "page") return stopElement(stop) === here;
        if (stop.kind !== "widget") return false;
        const at = stopElement(stop);
        return at && (at === here || under(here, at));
      }) ?? null
    );
  }

  // The stop `dir` steps to, and whether it came round an end to reach it: off the one
  // the user stands on, else from their place by the page walks' rule (`stepFrom`,
  // standing-target.js). Within a region, a place outside it enters at the end the step
  // faces. `stands` false reads the origin as a place the user is at without standing on
  // it, as the first ask they see in a region is.
  function step(list, dir, region, origin = walkOrigin(), stands = true) {
    // Outside the region nothing the user stands on is one of its stops, even where the
    // press sits inside an ask's context.
    if (region && !under(origin, region)) return cycledRow(list, null, dir);
    const standing = stands ? standingStop(list, origin) : null;
    if (standing) return cycledRow(list, standing, dir);
    return stepFrom(list, origin, dir, (stop) => stop.place);
  }

  // A page widget action handed back to the user, or a to-do on an element or the page, has
  // no owner that arrives at it, so travel puts the user on the element itself.
  function arriveAtElement(find) {
    const intent = retainUserIntent({ available: () => Boolean(find()) });
    const where = find();
    if (!where) return Promise.resolve(false);
    const departure = prepareTrip({ landing: find, intent });
    departure.plan(where);
    return arrive(
      () => {
        const at = find();
        return (
          at && {
            where: at,
            focus: at,
            scroll: [{ at, when: () => !readableDestination(at) }],
          }
        );
      },
      { intent, departure },
    );
  }

  // An answered ask is arrived at the same way, which is how the Questions panel's Done
  // rows return the user to one to review or revise it.
  function arriveAt(stop) {
    if (stop.kind === "ask") {
      const record = readAsks().all.find((ask) => ask.id === stop.id);
      return record ? arriveAtAsk(record) : Promise.resolve(false);
    }
    if (stop.kind === "thread") return arriveAtThread(stop.id);
    // A chrome presenting the approval elsewhere brings the user to it itself.
    if (stop.kind === "approval" && presentedApproval())
      return presentedApproval().arrive();
    return arriveAtElement(() => stopElement(stop));
  }

  // Where the walk stands in the whole list, and the kind of item it stands on: the
  // count is of every kind, so the kind follows it rather than naming the list.
  function position(region) {
    const list = stopsOf(region);
    const here = standingStop(list);
    const at = listWalkPosition(list, here, { identity: (stop) => stop.key });
    return at && { ...at, qualifier: `${region ? WITHIN : QUALIFIER} · ${here.noun}` };
  }

  // Resolves whether it arrived.
  function walk(dir, region = null, origin = walkOrigin(), stands = true) {
    const list = stopsOf(region);
    if (!list.length) return Promise.resolve(false);
    const { row: next, wrapped } = step(list, dir, region, origin, stands);
    // The walk reads the standing destination, so begin it once the arrival has moved
    // focus. A failed arrival has not arrived and must not register the prior item as
    // this walk's destination.
    const ready = arriveAt(next).then((arrived) => {
      if (!arrived) return false;
      announce(
        beginWalk("queue", null, () => position(region), wrapped) ??
          walkPositionLabel(
            null,
            list.indexOf(next) + 1,
            list.length,
            `${region ? WITHIN : QUALIFIER} · ${next.noun}`,
          ),
      );
      return true;
    });
    void ready.catch(() => {});
    return ready;
  }

  // The to-do Done ends where the user stands on `stop`.
  const doneAt = (stop) =>
    stop
      ? (readQueues().questions.find(
          (item) => item.offers.done && sameStop(stopOf(item), stop),
        ) ?? null)
      : null;

  // The to-do Done ends now. Under a finger with a keyboard beside it, as on a tablet,
  // Tab onto the banner's Done step takes focus through Leaf's own controls and the
  // page's body, where the user stands on no item, so while focus is there and no
  // caret or selection stands on the page the step keeps the to-do it was shown for,
  // if it is still on the user; anywhere else, the to-do the user stands on.
  let shownFor = null;
  function doneTodo() {
    const stop = standingStop(stops());
    const focus = focused(document);
    if (
      stop ||
      !coarsePointer.matches ||
      (focus && focus !== document.body && !inUi(focus) && !inChrome(focus)) ||
      placeOf(getSelection()?.focusNode)
    ) {
      shownFor = doneAt(stop);
      return shownFor;
    }
    shownFor =
      readQueues().questions.find(
        (item) => item.id === shownFor?.id && item.offers.done,
      ) ?? null;
    return shownFor;
  }

  // The user's Done on a to-do on them: their `todo_end`, through the one append door.
  // The to-do leaves their Questions in the turn they press it (`application.ts`).
  function endTodo(id) {
    return actions.done(queueItemKey({ kind: "todo", id }));
  }

  const offered = () => readQueues().questions.length > 0;
  const doneable = () =>
    readQueues()
      .questions.filter((item) => item.offers.done)
      .map((item) => item.id)
      .join(" ");
  let wasOffered = false;
  let wasDoneable = "";
  let stopWatching = null;
  // The q/Q row stands on Questions, and Done on the to-dos it holds, so the surfaces
  // reading them are repainted where the list empties or fills or those to-dos change.
  function mount() {
    stopWatching ??= watchSemantic(() => {
      if (offered() === wasOffered && doneable() === wasDoneable) return;
      wasOffered = offered();
      wasDoneable = doneable();
      paintKeys();
    });
  }

  pageCommand({
    id: "queue.walk",
    ready: savedReadingSettled,
    touch: false,
    keys: ["q", "Shift+q"],
    routes: [
      {
        id: "queue.next",
        binding: "q",
        title: "Next question",
        description: "Next ask, thread, to-do or resend waiting on me",
      },
      {
        id: "queue.previous",
        binding: "Shift+q",
        title: "Previous question",
        description: "Previous ask, thread, to-do or resend waiting on me",
      },
    ],
    title: "Questions",
    line: "questions",
    when: offered,
    repeat: true,
    // The same shape as the thread walk: it moves the user from item to item rather than
    // down a level, so the standing scope lets go of whichever one they end on. An item
    // reached through the panel leaves the panel a level of its own on the way out,
    // whether this walk opened it or the user already had it.
    run: (binding) => walk(binding === "q" ? 1 : -1),
  });

  // Where `q` lands on a to-do the user ends with Done, Done is a key, and a step on the
  // banner's row under a finger. Its row in the Questions panel carries the same Done.
  pageScope("todo", {
    title: "On a to-do waiting on me",
    ready: savedReadingSettled,
    at: () => Boolean(doneTodo()),
    rows: [
      {
        id: "queue.todo.done",
        keys: ["x"],
        title: "done",
        description: "Mark this to-do done",
        touch: "Done",
        when: () => Boolean(doneTodo()),
        run: () => {
          const todo = doneTodo();
          if (todo) endTodo(todo.id);
        },
      },
    ],
  });

  // A Questions panel row arrives where the walk would (queue-panel.js), whichever list
  // its item is on.
  const arriveAtItem = (item) => arriveAt(stopOf(item));

  // The Questions panel's Next question, which is `q` pressed from wherever the user
  // stands (queue-panel.js).
  const next = () => walk(1);

  // The id of the ask the user last went to, for a walk within a region pressed from
  // outside it. Sequential navigation passes over what it crosses, so it keeps the ask.
  let wentTo = null;
  onStanding((node, cause) => {
    if (cause === "step") return;
    const place = node && placeOf(node);
    wentTo = (place && askHolding(readAsks().all, place)?.id) ?? null;
  });

  // The public walk within a region (`askActions.next`).
  function nextWithin({ within, dir = 1 }) {
    if (!(within instanceof Element))
      throw new TypeError("leaf: askActions.next needs an element `within`");
    const here = walkOrigin();
    const asks = asksIn(within);
    const kept = asks.find((ask) => ask.id === wentTo);
    const toward = dir < 0 ? -1 : 1;
    if (under(here, within)) return walk(toward, within, here);
    if (kept) return walk(toward, within, askPlace(kept).source);
    // What the user reads in the region: the first of its asks any of which they see,
    // where they are without standing on it, so a waiting one is the next and an
    // answered one leads to the next after it.
    const clips = new Map();
    const shown = asks
      .map((ask) => askPlace(ask).node)
      .find((node) => node && seenRect(node, clips));
    return shown ? walk(toward, within, shown, false) : walk(toward, within, here);
  }

  return { mount, arriveAtItem, next, nextWithin };
}
