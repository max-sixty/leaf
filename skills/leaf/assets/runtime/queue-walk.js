/* The queue walk: `a` and Shift+`a` page through everything waiting on the user, in
   page order.

   What waits on the user is the application's one reading, `queues.onYou`
   (`runtime/queues.js`, the browser's selection of `agent_state.queues`): each open
   Ask, each other thread whose attention is the user's, and each page widget move
   handed back to them. The walk does not decide membership; it stops once at each
   item, so a thread holding an open Ask is reached as that Ask. `t` still walks every
   open thread (navigation.js).

   Arrival belongs to the item's owner, so the walk adds no arrival of its own beside
   theirs: an Ask arrives through the Ask view's `arriveAtAsk`; a thread through the
   t/T walk's own (navigation.js, `arriveAtThread`), so it lands wherever that walk
   lands; a page widget move by travel's `arrive`, onto the widget the move was made on.
   A Queue panel row arrives through the same function (`arriveAtItem`), for an item on
   either queue or one that is done.

   A walk starts from the user's place, in this order:

   1. current focus;
   2. selection or caret;
   3. the current visible reading block.

   `walkOrigin` reads that place from the browser on each press, for this walk and the
   thread walk alike. There is no remembered destination underneath those readings, and
   the chrome is a binding badge, not a page position, so its controls do not become the
   walk's origin. The user stands on an item when they stand in its Ask, in its thread
   (`threadHere`), or in its widget, and the press steps off it.

   Page order is each item's place in the document: an Ask's own element, or its
   thread's passage for an Ask seated in a thread; a thread's passage; the widget a move
   was made on. An item with no place on the page, a general thread or one whose passage
   is gone, comes after every placed one in the queue's own order, as the t/T walk
   reaches such threads from its list's ends. The walk is clamped, not wrapped.

   Experimental: the queues and the walk over them are new, and their shape is
   expected to change a lot (notes/what-needs-you/). Change them freely.
*/
import { pageCommand } from "./keyboard/register.js";
import { paintKeys } from "./keyboard/scopes.js";
import { askHolding, placeOf, walkOrigin } from "./standing-target.js";
import { elementById, inChrome } from "./passages.js";
import { hostIn, under } from "./shadow.js";
import { allAsks } from "./asks/model.js";
import { readApplication, watchSemantic } from "./semantic-state.js";
import { retainUserIntent } from "./user-intent.js";
import { beginWalk, listWalkPosition, walkPositionLabel } from "./walk-position.js";

const QUALIFIER = "waiting on you";
const NOUNS = Object.freeze({ ask: "Ask", thread: "Thread", widget: "Move" });

// Where an item of either queue, or one that is done, is arrived at: an Ask by its own
// id, anything else by the thread it stands in, or else the widget its move was made
// on.
const stopOf = (item) =>
  item.kind === "ask"
    ? { kind: "ask", id: item.id, thread: item.thread }
    : item.thread !== null
      ? { kind: "thread", id: item.thread, thread: item.thread }
      : { kind: "widget", id: item.subject.id, thread: null };

export function createQueueWalk({
  arriveAtAsk,
  arriveAtThread,
  threadHere,
  threadTarget,
  prepareTrip,
  arrive,
  readableDestination,
  announce,
}) {
  function stops() {
    const placed = [];
    const loose = [];
    for (const item of readApplication().effective.queues.onYou) {
      const stop = stopOf(item);
      const at =
        stop.kind === "ask" && stop.thread === null
          ? elementById(stop.id)
          : stop.thread !== null
            ? threadTarget(stop.thread)
            : elementById(stop.id);
      const place = at && !inChrome(at) ? hostIn(at, document) : null;
      (place ? placed : loose).push({ ...stop, key: `${stop.kind}:${stop.id}`, place });
    }
    placed.sort((a, b) =>
      a.place === b.place
        ? 0
        : a.place.compareDocumentPosition(b.place) & Node.DOCUMENT_POSITION_FOLLOWING
          ? -1
          : 1,
    );
    return [...placed, ...loose];
  }

  // The item the user stands on, if any: the thread holding them, the Ask holding their
  // place, or the widget that does. Standing in a thread that holds an open Ask is not
  // standing on that Ask, as it never was for the Ask walk this replaces.
  function standingStop(list) {
    const held = threadHere();
    const thread = held?.dataset.id ?? held?.dataset.thread;
    if (thread) {
      const stop = list.find(
        (candidate) => candidate.kind === "thread" && candidate.id === thread,
      );
      if (stop) return stop;
    }
    const here = walkOrigin();
    if (!here) return null;
    const ask = askHolding(
      list.filter((stop) => stop.kind === "ask"),
      placeOf(here),
    );
    if (ask) return ask;
    return (
      list.find((stop) => {
        if (stop.kind !== "widget") return false;
        const widget = elementById(stop.id);
        return widget && (widget === here || under(here, widget));
      }) ?? null
    );
  }

  // The stop `dir` steps to: off the one the user stands on, else the nearest on that
  // side of their place, clamped at either end. A stop whose place holds the user's,
  // such as a thread on the paragraph their caret is in, is the nearest either way,
  // since they are at it without standing on it. A stop with no place stands after
  // every placed one, so it is ahead of any place on the page.
  function step(list, dir) {
    const standing = standingStop(list);
    if (standing) {
      const at = list.indexOf(standing);
      return list[Math.max(0, Math.min(list.length - 1, at + dir))];
    }
    const here = walkOrigin();
    if (!here) return dir > 0 ? list[0] : list.at(-1);
    const side =
      dir > 0 ? Node.DOCUMENT_POSITION_FOLLOWING : Node.DOCUMENT_POSITION_PRECEDING;
    const reach = list.filter((stop) => {
      if (!stop.place) return dir > 0;
      if (stop.place === here || under(here, stop.place)) return true;
      const rel = here.compareDocumentPosition(stop.place);
      return !(rel & Node.DOCUMENT_POSITION_CONTAINS) && rel & side;
    });
    return dir > 0 ? (reach[0] ?? list.at(-1)) : (reach.at(-1) ?? list[0]);
  }

  // A page widget move handed back to the user has no owner that arrives at it, so travel
  // puts the user on the widget itself.
  function arriveAtWidget(id) {
    const intent = retainUserIntent({ available: () => Boolean(elementById(id)) });
    const where = elementById(id);
    if (!where) return Promise.resolve(false);
    const departure = prepareTrip({ landing: () => elementById(id), intent });
    departure.plan(where);
    return arrive(
      () => {
        const at = elementById(id);
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

  // An answered Ask is arrived at the same way, which is how the Queue panel's Done
  // rows return the user to one to review or revise it.
  function arriveAt(stop) {
    if (stop.kind === "ask") {
      const record = allAsks().find((ask) => ask.id === stop.id);
      return record ? arriveAtAsk(record) : Promise.resolve(false);
    }
    if (stop.kind === "thread") return arriveAtThread(stop.id);
    return arriveAtWidget(stop.id);
  }

  // Where the walk stands in the whole queue, and the kind of item it stands on: the
  // count is of every kind, so the kind follows it rather than naming the list.
  function position() {
    const list = stops();
    const here = standingStop(list);
    const at = listWalkPosition(list, here, { identity: (stop) => stop.key });
    return at && { ...at, qualifier: `${QUALIFIER} · ${NOUNS[here.kind]}` };
  }

  function walk(dir) {
    const list = stops();
    if (!list.length) return;
    const next = step(list, dir);
    // The walk reads the standing destination, so begin it once the arrival has moved
    // focus. A failed arrival has not arrived and must not register the prior item as
    // this walk's destination.
    const ready = arriveAt(next).then((arrived) => {
      if (!arrived) return;
      announce(
        beginWalk("queue", null, position) ??
          walkPositionLabel(
            null,
            list.indexOf(next) + 1,
            list.length,
            `${QUALIFIER} · ${NOUNS[next.kind]}`,
          ),
      );
    });
    void ready.catch(() => {});
    return ready;
  }

  const offered = () => readApplication().effective.queues.onYou.length > 0;
  let wasOffered = false;
  let stopWatching = null;
  // The a/A row stands on the queue, so the surfaces reading it are repainted where it
  // empties or fills.
  function mount() {
    stopWatching ??= watchSemantic(() => {
      if (offered() === wasOffered) return;
      wasOffered = offered();
      paintKeys();
    });
  }

  pageCommand({
    id: "queue.walk",
    touch: false,
    keys: ["a", "Shift+a"],
    routes: [
      {
        id: "queue.next",
        binding: "a",
        title: "Next waiting on you",
        description: "Next Ask, thread or move to resend waiting on you",
      },
      {
        id: "queue.previous",
        binding: "Shift+a",
        title: "Previous waiting on you",
        description: "Previous Ask, thread or move to resend waiting on you",
      },
    ],
    title: "Waiting on you",
    line: "on you",
    when: offered,
    repeat: true,
    // The same shape as the thread walk: it moves the user from item to item rather than
    // down a level, so the standing scope lets go of whichever one they end on. An item
    // reached through the panel leaves the panel a level of its own on the way out,
    // whether this walk opened it or the user already had it.
    run: (binding) => walk(binding === "a" ? 1 : -1),
  });

  // A Queue panel row arrives where the walk would (queue-panel.js), whichever list
  // its item is on.
  const arriveAtItem = (item) => arriveAt(stopOf(item));

  return { mount, arriveAtItem };
}
