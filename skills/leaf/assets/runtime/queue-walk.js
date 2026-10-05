/* The queue walk: `a` and Shift+`a` page through everything waiting on the user, in
   page order.

   What waits on the user is the application's one reading, `queues.onYou`
   (`runtime/queues.js`, the browser's selection of `agent_state.queues`): each open
   task on the user, an Ask's or a thread question's among them, each thread holding a
   move to send again, and each page widget move handed back to them. The walk does not
   decide membership; it stops once at each place an item is arrived at, so a thread
   holding an open Ask is reached as that Ask. `t` still walks every open thread
   (navigation.js).

   Arrival belongs to the item's owner, so the walk adds no arrival of its own beside
   theirs: an Ask arrives through the Ask view's `arriveAtAsk`; a thread through the
   t/T walk's own (navigation.js, `arriveAtThread`), so it lands wherever that walk
   lands; a page widget move, or a task on an element or the page, by travel's `arrive`,
   onto the widget the move was made on, the element, or the page's head.
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
   (`threadHere`), or in its widget or element, and the press steps off it. Standing on
   a task Done ends, `x` is that Done, a step on the banner's row under a finger
   (`endTask`): the user's `task_end`, which leaves the queue in the turn it is pressed.

   Page order is each item's place in the document: an Ask's own element, or its
   thread's passage for an Ask seated in a thread; a thread's passage; the widget a move
   was made on or the element a task is on; the page's head for a task on the whole
   page. An item with no place on the page, a general thread or one whose passage is
   gone, comes after every placed one in the queue's own order, as the t/T walk reaches
   such threads from its list's ends. The walk is clamped, not wrapped.

   Experimental: the queues and the walk over them are new, and their shape is
   expected to change a lot (notes/what-needs-you/). Change them freely.
*/
import { pageCommand, pageScope } from "./keyboard/register.js";
import { paintKeys } from "./keyboard/scopes.js";
import { askHolding, placeOf, walkOrigin } from "./standing-target.js";
import { elementById, inChrome } from "./passages.js";
import { hostIn, under } from "./shadow.js";
import { allAsks } from "./asks/model.js";
import { endsByDone, taskNoun } from "./queues.js";
import { readApplication, watchSemantic } from "./semantic-state.js";
import { retainUserIntent } from "./user-intent.js";
import { beginWalk, listWalkPosition, walkPositionLabel } from "./walk-position.js";

const QUALIFIER = "waiting on you";
const NOUNS = Object.freeze({
  ask: "Ask",
  thread: "Thread",
  widget: "Move",
  page: "Task",
});
// What a stop is called: by where it is arrived at, but a task on an element is a Task
// rather than the Move a widget's stop otherwise is.
const nounOf = (item, stop) =>
  stop.kind === "widget" && taskNoun(item) === "task" ? "Task" : NOUNS[stop.kind];

// Where an item of either queue, or one that is done, is arrived at: an Ask's task by
// the Ask's own id, anything else by the thread it stands in, a task on the page as a
// whole at the page's head, or else the element it stands on, as a move is arrived at
// on the widget it was made on.
const stopOf = (item) =>
  item.ends === "widget"
    ? { kind: "ask", id: item.id, thread: item.thread }
    : item.thread !== null
      ? { kind: "thread", id: item.thread, thread: item.thread }
      : item.subject.kind === "page"
        ? { kind: "page", id: "page", thread: null }
        : { kind: "widget", id: item.subject.id, thread: null };
const sameStop = (a, b) => a.kind === b.kind && a.id === b.id;

// The page's head, where a task on the page as a whole is arrived at: its first
// top-level heading, or its first element.
const pageHead = () =>
  [...document.querySelectorAll("h1")].find((heading) => !inChrome(heading)) ??
  document.querySelector("main") ??
  document.body.firstElementChild;

export function createQueueWalk({
  arriveAtAsk,
  arriveAtThread,
  threadHere,
  threadTarget,
  prepareTrip,
  arrive,
  readableDestination,
  announce,
  post,
}) {
  // The element a stop stands at on the page, if it has one.
  const stopElement = (stop) =>
    stop.kind === "page"
      ? pageHead()
      : stop.thread !== null
        ? threadTarget(stop.thread)
        : elementById(stop.id);

  function stops() {
    const placed = [];
    const loose = [];
    const listed = new Set();
    for (const item of readApplication().effective.queues.onYou) {
      const stop = stopOf(item);
      // Two items arrived at in one place, such as two tasks on one thread, are one
      // stop.
      if (listed.has(`${stop.kind}:${stop.id}`)) continue;
      listed.add(`${stop.kind}:${stop.id}`);
      const at = stopElement(stop);
      const place = at && !inChrome(at) ? hostIn(at, document) : null;
      (place ? placed : loose).push({
        ...stop,
        key: `${stop.kind}:${stop.id}`,
        noun: nounOf(item, stop),
        place,
      });
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
  // place, or the element that does. Standing in a thread that holds an open Ask is not
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
        if (stop.kind !== "widget" && stop.kind !== "page") return false;
        const at = stopElement(stop);
        return at && (at === here || under(here, at));
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

  // A page widget move handed back to the user, or a task on an element or the page, has
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

  // An answered Ask is arrived at the same way, which is how the Queue panel's Done
  // rows return the user to one to review or revise it.
  function arriveAt(stop) {
    if (stop.kind === "ask") {
      const record = allAsks().find((ask) => ask.id === stop.id);
      return record ? arriveAtAsk(record) : Promise.resolve(false);
    }
    if (stop.kind === "thread") return arriveAtThread(stop.id);
    return arriveAtElement(() => stopElement(stop));
  }

  // Where the walk stands in the whole queue, and the kind of item it stands on: the
  // count is of every kind, so the kind follows it rather than naming the list.
  function position() {
    const list = stops();
    const here = standingStop(list);
    const at = listWalkPosition(list, here, { identity: (stop) => stop.key });
    return at && { ...at, qualifier: `${QUALIFIER} · ${here.noun}` };
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
            `${QUALIFIER} · ${next.noun}`,
          ),
      );
    });
    void ready.catch(() => {});
    return ready;
  }

  // The task the user stands on that their Done ends, if any: one on the thread, element
  // or page the user stands at.
  function standingTask() {
    const stop = standingStop(stops());
    return stop
      ? (readApplication().effective.queues.onYou.find(
          (item) => endsByDone(item) && sameStop(stopOf(item), stop),
        ) ?? null)
      : null;
  }

  // The user's Done on a task on them: their `task_end`, through the one append door.
  // The task leaves their queue in the turn they press it (`application.ts`).
  function endTask(id) {
    void post({ kind: "task_end", task: id, outcome: "done" });
    announce("Done");
  }

  const offered = () => readApplication().effective.queues.onYou.length > 0;
  const doneable = () =>
    readApplication()
      .effective.queues.onYou.filter(endsByDone)
      .map((item) => item.id)
      .join(" ");
  let wasOffered = false;
  let wasDoneable = "";
  let stopWatching = null;
  // The a/A row stands on the queue, and Done on the tasks it holds, so the surfaces
  // reading them are repainted where the queue empties or fills or those tasks change.
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
    touch: false,
    keys: ["a", "Shift+a"],
    routes: [
      {
        id: "queue.next",
        binding: "a",
        title: "Next waiting on you",
        description: "Next Ask, thread, task or move to resend waiting on you",
      },
      {
        id: "queue.previous",
        binding: "Shift+a",
        title: "Previous waiting on you",
        description: "Previous Ask, thread, task or move to resend waiting on you",
      },
    ],
    title: "Waiting on you",
    description: "Next / previous Ask, thread, task or move to resend waiting on you",
    line: "on you",
    when: offered,
    repeat: true,
    // The same shape as the thread walk: it moves the user from item to item rather than
    // down a level, so the standing scope lets go of whichever one they end on. An item
    // reached through the panel leaves the panel a level of its own on the way out,
    // whether this walk opened it or the user already had it.
    run: (binding) => walk(binding === "a" ? 1 : -1),
  });

  // Where `a` lands on a task the user ends with Done, Done is a key, and a step on the
  // banner's row under a finger. Its row in the Queue panel carries the same Done.
  pageScope("task", {
    title: "On a task waiting on you",
    at: () => Boolean(standingTask()),
    rows: [
      {
        id: "queue.task.done",
        keys: ["x"],
        title: "done",
        description: "Mark the task waiting on you done",
        touch: "Done",
        when: () => Boolean(standingTask()),
        run: () => {
          const task = standingTask();
          if (task) endTask(task.id);
        },
      },
    ],
  });

  // A Queue panel row arrives where the walk would (queue-panel.js), whichever list
  // its item is on.
  const arriveAtItem = (item) => arriveAt(stopOf(item));

  return { mount, arriveAtItem, endTask };
}
