/* The On me walk: `m` and Shift+`m` page through everything waiting on the user,
   in the order the floating panel's On me view lists it (`onMeGroups`). The view opens
   with `g M`, as Threads opens with `g T` and `t` walks the threads.

   On me groups its items one of three ways, which the user picks at the view's foot
   and the browser keeps for every page (storage.js, `userChoice`): By place, under the
   heading or named region of the part of the page each stands in (thread/placement.js,
   `partOver`);
   By kind, under the walk's word for each (`queueStop`); and By <agent>, under the
   goals of the agent's plan whose steps name them, with those no goal names last.
   Until the user picks, a plan that gives the user a step groups By <agent>, else By
   place. Groups stand in the order their first item comes in page order, a plan's
   goals in the plan's order and a goal's items in its steps' order, and the walk steps
   through the groups' items in that one order, so successive presses reach successive
   rows of the list (`onMeGroups` says how answered items keep that order still). The user chose groupings to choose from, the agent's plan among
   them, on 21 October 2026, over Leaf ordering by what the plan waits on, an agent's
   note with picks, and a priority on every obligation, each of which needed a new
   contract or a guess. A step from no item on the list, from where the user reads,
   still goes to the first item in that order that stands after their place
   (`stepFrom`), so under By kind or By <agent> it may not be the nearest one below.

   What waits on the user is the application's one reading, `queues.on_user`
   (the server's `served_state.queues`, with this tab's sends placed against it): each open
   obligation or to-do on the user, each thread holding a resend, and each page widget action
   handed back to them. The walk does not decide membership; it stops once at each place
   an obligation is arrived at, so a thread holding an open obligation is reached as that obligation. `t` still walks every open thread
   (navigation.js).

   Arrival belongs to the item's owner, so the walk adds no arrival of its own beside
   theirs: an obligation arrives through the obligation view's `arriveAtRecord`; a thread through the
   t/T walk's own (navigation.js, `arriveAtThread`), so it lands wherever that walk
   lands; a page widget action, or a to-do on an element or the page, by travel's `arrive`,
   onto the widget the action was made on, the element, or the page's head; the
   version's approval by the floating panel's own arrival (page-status.js,
   `registerApprovalPresentation`). An On me card's Show arrives through the same
   function (`arriveAtItem`), for an item on either list or one that is done, and
   offers itself where that arrival goes anywhere (`arrivesAt`); the card names its
   item as the walk does (`queueStop`).

   A walk starts from the user's place, in this order:

   1. current focus;
   2. selection or caret;
   3. the current visible reading block.

   `walkOrigin` reads that place from the browser on each press, for this walk and the
   thread walk alike. There is no remembered destination underneath those readings, and
   the chrome is a binding badge, not a page position, so its controls do not become the
   walk's origin. The user stands on an obligation when they stand in its widget, in its thread
   (`threadHere`), or in its widget or element, and the press steps off it. Standing on
   a to-do Done ends, `x` is that Done, as is the Done on its On me row
   (`queue-api.js`, `done`): the user's `todo_end`, which leaves On me in the turn it is
   pressed.

   Page order is each obligation's place in the page as rendered: an obligation's own element, or its
   thread's passage for an obligation seated in a thread; a thread's passage; the widget an action
   was made on or the element a to-do is on; the page's head for a to-do on the whole
   page. An item with no place on the page, a general thread or one whose passage is
   gone, comes after every placed one in the list's own order, as the t/T walk reaches
   such threads from its list's ends. A step past either end comes round to the other.
   Each grouping orders its items within a group by page order (`inWalkOrder`), but a
   goal's by its steps' order.

   The walk can also step within one region of the page (`obligationActions.next`, as an
   `lf-tally`'s Next on me presses it): its stops are then the obligations waiting on the user
   that the region holds (`obligationsIn`, obligations/place.js), stepped by the same standing and
   page order, and its position counts them alone. A press from outside the region, such as
   one on the tally's own control above it, counts from the obligation the user last went to, if
   it is in the region: Tab and Shift+Tab pass over what they cross on the way to the
   control, so they keep it, while any other move the user makes ends it. Without one it
   counts from the first of the region's obligations they see, as a place they are at without
   standing on it, and with none in sight it enters at the region's edge, Next at the
   first and Previous at the last. That obligation, kept by identity
   so a revision replacing its node keeps it, is the one place the walk keeps, and only
   this case reads it: anywhere else the user's own place decides.

   Experimental: the lists and the walk over them are new, and their shape is
   expected to change a lot. Change them freely.
*/
import { cycledRow, savedReadingSettled } from "./keyboard/bindings.js";
import { pageCommand, pageScope } from "./keyboard/register.js";
import { paintKeys } from "./keyboard/scopes.js";
import { focused, onStanding } from "./focus.js";
import {
  obligationHolding,
  placeOf,
  standingOrigin,
  stepFrom,
  walkOrigin,
} from "./standing-target.js";
import { seenRect } from "./geometry.js";
import { elementById, inChrome, pageDocument } from "./passages.js";
import { byRenderedOrder, under } from "./shadow.js";
import { obligationWord } from "./obligations/answer.js";
import { answeredInWords, readObligations } from "./obligations/model.js";
import { obligationsIn, obligationPlace } from "./obligations/place.js";
import { readPlan, readQueues, queueItemKey } from "./queue-api.js";
import { carriesObligation, itemNoun } from "./queues.js";
import { drawnThreadId } from "./thread/selectors.js";
import { partOver } from "./thread/placement.js";
import { addressableLabel } from "./addressable-names.js";
import { userChoice } from "./storage.js";
import { agentName } from "./semantic-state.js";
import { watchProjection } from "./projection-watch.js";
import { retainUserIntent } from "./user-intent.js";
import { beginWalk, listWalkPosition, walkPositionLabel } from "./walk-position.js";
import { approvalTarget, presentedApproval } from "./page-status.js";

const QUALIFIER = "waiting on me";
const WITHIN = "waiting on me here";
const NOUNS = Object.freeze({
  thread: "Thread",
  widget: "Update",
  page: "To-do",
  approval: "Approval",
});
// What a stop is called: an obligation by its widget's own word, else by where it is arrived
// at, but a to-do on an element is a To-do rather than the Update a widget's stop
// otherwise is.
const nounOf = (item, stop) =>
  carriesObligation(item) && stop.kind !== "approval"
    ? obligationWord(item.obligation)
    : stop.kind === "widget" && itemNoun(item) === "todo"
      ? "To-do"
      : NOUNS[stop.kind];

// Where an item of either list, or one that is done, is arrived at: a widget obligation by
// the obligation's own id, a question asked in words in a thread, like anything else, by the
// thread it stands in, a to-do on the page as a whole at the page's head, or else the
// element it stands on, as an action is arrived at on the widget it was made on.
const stopOf = (item) =>
  item.kind === "approval"
    ? { kind: "approval", id: item.id, thread: null }
    : item.kind === "widget" &&
        !(item.thread !== null && answeredInWords(item.obligation))
      ? {
          kind: "obligation",
          id: item.id,
          thread: item.thread,
          obligation: item.obligation,
        }
      : item.thread !== null
        ? { kind: "thread", id: item.thread, thread: item.thread }
        : item.subject.kind === "page"
          ? { kind: "page", id: "page", thread: null }
          : { kind: "widget", id: item.subject.id, thread: null };
const sameStop = (a, b) => a.kind === b.kind && a.id === b.id;

// An item as the walk reads it: where it is arrived at, the key the walk's position
// names that stop by, and what the walk calls it. An On me card reads the same, so it
// names its kind as the field does after `m` and knows when the walk stands on it.
export function queueStop(item) {
  const stop = stopOf(item);
  return { ...stop, key: `${stop.kind}:${stop.id}`, noun: nounOf(item, stop) };
}

// On me's groupings, in the order its chooser offers them, and the one the user chose.
export const ON_ME_GROUPINGS = Object.freeze(["place", "kind", "plan"]);
const chosenGrouping = userChoice("lf-on-me-grouping", ON_ME_GROUPINGS);
export const groupingLabel = (grouping) =>
  grouping === "plan"
    ? `By ${agentName()}`
    : grouping === "kind"
      ? "By kind"
      : "By place";
// The ids of the items a plan step names, its own and its steps', in the plan's order;
// and whether a step, or one under it, is the user's.
const namedIn = (step) => [
  ...(step.item ? [step.item.id] : []),
  ...step.steps.flatMap(namedIn),
];
const givesUser = (step) => step.owner === "user" || step.steps.some(givesUser);

// The page's head, where a to-do on the page as a whole is arrived at: its first
// top-level heading, or its first element.
const pageHead = () =>
  [...document.querySelectorAll("h1")].find((heading) => !inChrome(heading)) ??
  pageDocument() ??
  document.body.firstElementChild;

export function createQueueWalk({
  arriveAtRecord,
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
      : stop.kind === "obligation"
        ? stop.thread !== null
          ? threadPlace(stop.thread)
          : obligationPlace(stop.obligation).node
        : stop.kind === "page"
          ? pageHead()
          : stop.thread !== null
            ? threadPlace(stop.thread)
            : elementById(stop.id);

  // Where a stop stands on the page, if anywhere.
  const pagePlace = (stop) => {
    const at = stopElement(stop);
    return at?.isConnected && !inChrome(at) ? at : null;
  };

  // Items of any list in the walk's order: by where each is arrived at on the page, and
  // those with no place there after, in the list's own order.
  const inWalkOrder = (items) =>
    byRenderedOrder(items, (item) => pagePlace(queueStop(item)));

  // How On me groups now: the user's choice, else By <agent> where the plan gives the
  // user a step, which stays so as the user answers it, else By place.
  const grouping = () =>
    chosenGrouping.read() ??
    ((readPlan()?.steps ?? []).some(givesUser) ? "plan" : "place");
  // The heading of the part of the page an item stands in, and what it says.
  const itemHeading = (item) => {
    const at = pagePlace(queueStop(item));
    return at ? partOver(at) : null;
  };
  const itemPlace = (item) => {
    const heading = itemHeading(item);
    return heading ? addressableLabel(heading) : "";
  };
  // Everything On me has held on this page: what waits on the user and what the user
  // finished. It only grows as they answer, so an order read from it holds still while
  // the list empties.
  const heldOnMe = () => {
    const reading = readQueues();
    return [
      ...reading.on_user,
      ...reading.done.filter((item) => item.owner === "user"),
    ];
  };
  // `items` in On me's groups (`grouping`), each a `title` over its items: the list's one
  // order, which the walk follows too. The groups and their order are read from
  // everything On me has held (`heldOnMe`), not from which items remain, so the list,
  // which keeps an answered item in its seat, and the walk, which steps over it, stand
  // in one order: a plan's goals in the plan's order, else each group where the first
  // item it holds comes in page order. A group's items stand by their steps' order in
  // a goal, else in page order. Items arrived at in one place, such as a thread's
  // question and a to-do on that thread, are one stop of the walk, so they stand
  // together in the first of their groups.
  function onMeGroups(items, by = grouping()) {
    const keyed = new Map(
      [...heldOnMe(), ...items].map((item) => [queueItemKey(item), item]),
    );
    const basis = inWalkOrder([...keyed.values()]);
    const goals = by === "plan" ? (readPlan()?.steps ?? []) : [];
    const named = goals.map(namedIn);
    const groupOf = (item) => {
      if (by === "kind") return queueStop(item).noun;
      if (by !== "plan") return itemHeading(item);
      const at = named.findIndex((ids) => ids.includes(item.id));
      return at < 0 ? goals.length : at;
    };
    // Group by group, the place it stands at: a goal by the plan, with those no goal
    // names after it, else where the first item it holds comes.
    const order = new Map();
    if (by === "plan") for (let at = 0; at <= goals.length; at += 1) order.set(at, at);
    for (const item of basis) {
      const group = groupOf(item);
      if (!order.has(group)) order.set(group, order.size);
    }
    const stops = new Map();
    basis.forEach((item, at) => {
      const key = queueStop(item).key;
      if (!stops.has(key)) stops.set(key, { at, items: [] });
      stops.get(key).items.push(item);
    });
    const shown = new Set(items.map(queueItemKey));
    const groups = new Map();
    for (const stop of stops.values()) {
      const listed = stop.items.filter((item) => shown.has(queueItemKey(item)));
      if (!listed.length) continue;
      const group = stop.items
        .map(groupOf)
        .reduce((first, next) => (order.get(next) < order.get(first) ? next : first));
      const rank =
        by === "plan" && group < goals.length
          ? Math.min(
              ...stop.items
                .map((item) => named[group].indexOf(item.id))
                .filter((at) => at >= 0),
            )
          : stop.at;
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group).push({ rank, items: listed });
    }
    return [...groups.entries()]
      .sort(([a], [b]) => order.get(a) - order.get(b))
      .map(([group, held]) => ({
        key:
          by === "plan"
            ? `goal:${group}`
            : by === "kind"
              ? `kind:${group}`
              : (group ?? "place"),
        title:
          by === "plan"
            ? group < goals.length
              ? (goals[group].title ?? `Goal ${group + 1}`)
              : "Not in the plan"
            : by === "kind"
              ? group
              : group
                ? addressableLabel(group)
                : "The whole page",
        items: held.sort((a, b) => a.rank - b.rank).flatMap((stop) => stop.items),
      }));
  }

  // The walk's stops among `items`, in their order: an item's stop, once, where its
  // first item stands.
  function stopsAmong(items) {
    const list = [];
    const listed = new Set();
    for (const item of items) {
      const stop = queueStop(item);
      if (listed.has(stop.key)) continue;
      listed.add(stop.key);
      list.push({ ...stop, place: pagePlace(stop) });
    }
    return list;
  }
  const stops = () =>
    stopsAmong(onMeGroups(readQueues().on_user).flatMap((group) => group.items));

  // The stops of a walk within `region`: the obligations waiting on the user it holds,
  // in page order whatever On me's grouping, as the region is read on the page.
  function stopsWithin(region) {
    const held = new Set(obligationsIn(region).map((item) => item.id));
    return stopsAmong(inWalkOrder(readQueues().on_user)).filter(
      (stop) => stop.kind === "obligation" && held.has(stop.id),
    );
  }
  const stopsOf = (region) => (region ? stopsWithin(region) : stops());

  // The item the user stands on, if any: the thread holding them, the obligation holding their
  // place, or the innermost element that does, in page order the last that holds them,
  // as `obligationHolding` reads obligations. The page's own stop is its head element alone, never
  // what that holds, since on a page without a heading the head is `main`. Standing in
  // a thread that holds an open obligation is not standing on that obligation. `origin` names
  // the user's place unless a walk supplies its own starting point. A reading
  // in the viewport can start a walk but does not select a task to finish or count.
  function standingStop(list, origin = standingOrigin()) {
    if (focused(document) === approvalTarget())
      return list.find((stop) => stop.kind === "approval") ?? null;
    const held = threadHere();
    const thread = drawnThreadId(held);
    if (thread) {
      const stop = list.find(
        (candidate) => candidate.kind === "thread" && candidate.id === thread,
      );
      if (stop) return stop;
    }
    if (origin?.kind !== "standing") return null;
    const { place: here } = origin;
    if (!here) return null;
    const item = obligationHolding(readObligations().all, placeOf(here));
    if (item) {
      const stop = list.find(
        (candidate) => candidate.kind === "obligation" && candidate.id === item.id,
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
  // faces. `enter` starts inside a selected tab's panel; `at` starts at a visible obligation
  // without stepping off it.
  function step(list, dir, region, origin) {
    // Outside the region nothing the user stands on is one of its stops, even where the
    // press sits inside the lf-ask around an obligation.
    if (region && !under(origin.place, region)) return cycledRow(list, null, dir);
    const standing = standingStop(list, origin);
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

  // An answered obligation is arrived at the same way, which is how On me's Done
  // rows return the user to one to review or revise it.
  function arriveAt(stop) {
    if (stop.kind === "obligation") {
      const record = readObligations().all.find((item) => item.id === stop.id);
      return record ? arriveAtRecord(record) : Promise.resolve(false);
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
  function walk(dir, region = null, origin = walkOrigin()) {
    const list = stopsOf(region);
    if (!list.length) return Promise.resolve(false);
    const { row: next, wrapped } = step(list, dir, region, origin);
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
      ? (readQueues().on_user.find(
          (item) => item.offers.done && sameStop(stopOf(item), stop),
        ) ?? null)
      : null;

  // The to-do Done ends now: the one the user stands on.
  const doneTodo = () => doneAt(standingStop(stops()));

  // The user's Done on a to-do on them: their `todo_end`, through the one append door.
  // The to-do leaves On me in the turn they press it (`application.ts`).
  function endTodo(id) {
    return actions.done(queueItemKey({ kind: "todo", id }));
  }

  const offered = () => readQueues().on_user.length > 0;
  const doneable = () =>
    readQueues()
      .on_user.filter((item) => item.offers.done)
      .map((item) => item.id)
      .join(" ");
  let wasOffered = false;
  let wasDoneable = "";
  let watching = null;
  // The m/M row stands on On me, and Done on the to-dos it holds, so the surfaces
  // reading them are repainted where the list empties or fills or those to-dos change.
  function mount() {
    watching ??= watchProjection(document.body, () => {
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
    keys: ["m", "Shift+m"],
    routes: [
      // The whole page's list, which a tally's Next on me, walking one region, is not.
      {
        id: "queue.next",
        binding: "m",
        title: "Next on me",
      },
      {
        id: "queue.previous",
        binding: "Shift+m",
        title: "Previous on me",
      },
    ],
    title: "On me",
    when: offered,
    repeat: true,
    // The same shape as the thread walk: it moves the user from item to item rather than
    // down a level, so the standing scope lets go of whichever one they end on. An item
    // reached through the panel leaves the panel a level of its own on the way out,
    // whether this walk opened it or the user already had it.
    run: (binding) => walk(binding === "m" ? 1 : -1),
  });

  // Where `m` lands on a to-do the user ends with Done, Done is a key. A finger presses
  // the same Done on the to-do's row in On me, so the panel's row offers no step for it.
  pageScope("todo", {
    title: "On a to-do waiting on me",
    ready: savedReadingSettled,
    at: () => Boolean(doneTodo()),
    rows: [
      {
        id: "queue.todo.done",
        keys: ["x"],
        title: "done",
        touch: false,
        when: () => Boolean(doneTodo()),
        run: () => {
          const todo = doneTodo();
          if (todo) endTodo(todo.id);
        },
      },
    ],
  });

  // An On me row arrives where the walk would, whichever list its obligation is on.
  const arriveAtItem = (item) => arriveAt(stopOf(item));
  // Whether the walk takes the user somewhere for an item that its card does not already
  // offer: its place on the page, or a widget in a thread the page draws no passage for,
  // which the panel opens with the user on the widget. A thread with no place opens in
  // the panel as the card's Discuss opens it, and the version's approval stands in On me
  // (`stopElement`), so neither goes anywhere further.
  const arrivesAt = (item) => {
    const stop = stopOf(item);
    return (
      Boolean(pagePlace(stop)) || (stop.kind === "obligation" && stop.thread !== null)
    );
  };

  // The id of the obligation the user last went to, for a walk within a region pressed from
  // outside it. Sequential navigation passes over what it crosses, so it keeps the obligation.
  let wentTo = null;
  onStanding((node, cause) => {
    if (cause === "step") return;
    const place = node && placeOf(node);
    wentTo = (place && obligationHolding(readObligations().all, place)?.id) ?? null;
  });

  // The public walk within a region (`obligationActions.next`).
  function nextWithin({ within, dir = 1 }) {
    if (!(within instanceof Element))
      throw new TypeError("leaf: obligationActions.next needs an element `within`");
    const here = walkOrigin();
    const items = obligationsIn(within);
    const kept = items.find((item) => item.id === wentTo);
    const toward = dir < 0 ? -1 : 1;
    if (under(here.place, within)) return walk(toward, within, here);
    if (kept)
      return walk(toward, within, {
        place: obligationPlace(kept).source,
        kind: "standing",
      });
    // What the user reads in the region: the first of its obligations any of which they see,
    // where they are without standing on it, so a waiting one is the next and an
    // answered one leads to the next after it.
    const clips = new Map();
    const shown = items
      .map((item) => obligationPlace(item).node)
      .find((node) => node && seenRect(node, clips));
    return shown
      ? walk(toward, within, { place: shown, kind: "at" })
      : walk(toward, within, here);
  }

  // On me's list as the panel draws it: its groups, the grouping they stand in and the
  // user's choice of it, and the heading each item's row names as its place.
  const onMe = Object.freeze({
    groups: onMeGroups,
    grouping,
    choose: (value) => chosenGrouping.write(value),
    place: itemPlace,
  });

  return { mount, arriveAtItem, arrivesAt, onMe, nextWithin };
}
