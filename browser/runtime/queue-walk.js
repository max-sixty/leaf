/* The On me walk: `m` and Shift+`m` page through everything waiting on the user,
   in the order the floating panel's On me view lists it (`onMeGroups`). The view opens
   with `g M`, as Threads opens with `g T` and `t` walks the threads.

   On me groups its items one of three ways, which the user picks at the view's foot
   and the browser keeps for every page (storage.js, `userChoice`): By place, under what
   names the part of the page each stands in (thread/placement.js, `partOver`); By kind,
   under the walk's word for each (`queueStop`); and By <agent>, under the goals of the
   agent's plan whose steps name them, those no goal names last. Until the user picks, a
   plan that gives the user a step groups By <agent>, else By place. The walk steps
   through the groups' items in the list's one order (`onMeGroups`), so successive
   presses reach successive rows. The user chose these groupings (2026-10-21) over Leaf
   ordering by what the plan waits on, an agent's note with picks, and a priority on
   every obligation, each needing a new contract or a guess. A step from where the user
   reads goes to the first item in that order after their place (`stepFrom`), which
   under By kind or By <agent> may not be the nearest one below.

   What waits on the user is the application's one reading, `queues.on_user`
   (the server's `served_state.queues`, with this tab's sends placed against it): each open
   obligation or to-do on the user, each thread holding a resend, and each page widget action
   handed back to them. The walk does not decide membership; it stops once at each place
   an obligation is arrived at, so a thread holding an open obligation is reached as that obligation. `t` still walks every open thread
   (navigation.js).

   Arrival belongs to the item's owner, so the walk adds no arrival of its own beside
   theirs: an obligation arrives through the obligation view's `arriveAtRecord`, a to-do
   on an element or the page included, at the place obligations/place.js gives it; a
   thread through the t/T walk's own (navigation.js, `arriveAtThread`), so it lands
   wherever that walk lands. Only what is no obligation the page places has no owner
   that arrives at it, a page widget action handed back to the user or an On <agent>
   card's to-do, so travel's `arrive` puts the user where its subject stands
   (`subjectPlace`). An On me card's Show arrives through the same
   function (`arriveAtItem`), for an item on either list or one that is done, and
   offers itself where that arrival goes anywhere (`arrivesAt`).

   A walk starts from the user's place, and steps off a stop only where the user is on
   it, by the rule every walk shares (current-target.js, `walkOrigin` and `stepFrom`).
   The chrome is a binding badge, not a page position, so its controls do not become
   the walk's origin. The user is on an obligation when their current location is in
   its place (`obligationHolding`, current-target.js), a to-do's included, on a thread
   stop when they are in its thread (`threadIn`), and on an action handed back when
   they are in its widget. Being on a to-do Done ends, `x` is that Done, as are the Done at
   the end of the floating panel's row and the Done on its On me card (`queue-api.js`,
   `done`): the user's `todo_end`, which leaves On me in the turn it is pressed. The
   to-do is a stance (keyboard/touch-controls.js): while the user stands on it the
   panel's empty field names it, "To-do · <title>", and its row's end offers its Done,
   a finger's route to Done wherever Show leaves them.

   The walk opens what answers each item it reaches: a thread opens, a widget's
   controls stand at its place, and a to-do, whose place holds nothing that answers
   it, opens On me (`showOnMe`), whose card holds its whole title and its Done, with
   the user left on its place, where `x` still ends it and the field still names it.
   The user chose that on 2026-10-31, after `m` left a to-do's long title cut to half
   a line in the field.

   Page order is each obligation's place in the page as rendered: an obligation's own
   element, the element a to-do is on or the page's head for one on the whole page
   (obligations/place.js), or its thread's passage for an obligation seated in a
   thread; a thread's passage; the widget an action was made on. An item with no place
   on the page, a general thread or one whose passage is gone, comes after every placed one in the list's own order, as the t/T walk reaches
   such threads from its list's ends. A step past either end comes round to the other.
   Each grouping orders its items within a group by page order (`inWalkOrder`), but a
   goal's by its steps' order.

   The walk can also step within one region of the page (`obligationActions.next`, as an
   `lf-tally`'s Next on me presses it): its stops are then the obligations waiting on the user
   that the region holds (`obligationsIn`, obligations/place.js), stepped by the same current location and
   page order, and its position counts them alone. A press from outside the region, such as
   one on the tally's own control above it, counts from the obligation the user last went to, if
   it is in the region: Tab and Shift+Tab pass over what they cross on the way to the
   control, so they keep it, while any other move the user makes ends it. Without one it
   counts from the first of the region's obligations they see, as a place they are at without
   being on it, and with none in sight it enters at the region's edge, Next at the
   first and Previous at the last. That obligation, kept by identity
   so a revision replacing its node keeps it, is the one place this walk keeps, and only
   this case reads it: anywhere else the user's own place decides.

   Experimental: the lists and the walk over them are new, and their shape is
   expected to change a lot. Change them freely.
*/
import { cycledRow, savedReadingSettled } from "./keyboard/bindings.js";
import { pageCommand, pageScope } from "./keyboard/register.js";
import { paintKeys } from "./keyboard/scopes.js";
import { onCurrentLocation } from "./focus.js";
import {
  obligationHolding,
  placeOf,
  currentLocationOrigin,
  stepFrom,
  walkOrigin,
} from "./current-target.js";
import { seenRect } from "./geometry.js";
import { inChrome } from "./passages.js";
import { byRenderedOrder, under } from "./shadow.js";
import { obligationWord } from "./obligations/answer.js";
import { answeredInWords, readObligations } from "./obligations/model.js";
import { obligationsIn, obligationPlace, subjectPlace } from "./obligations/place.js";
import { readPlan, readQueues, queueItemKey } from "./queue-api.js";
import { carriesObligation, itemNoun } from "./queues.js";
import { threadIn } from "./thread/focus.js";
import { drawnThreadId } from "./thread/selectors.js";
import { partOver } from "./thread/placement.js";
import { addressableLabel } from "./addressable-names.js";
import { userChoice } from "./storage.js";
import { agentName } from "./semantic-state.js";
import { effect, untracked } from "/runtime/framework.js";
import { retainUserIntent } from "./user-intent.js";
import { beginWalk, listWalkPosition, walkPositionLabel } from "./walk-position.js";

const QUALIFIER = "waiting on me";
const WITHIN = "waiting on me here";
const NOUNS = Object.freeze({
  thread: "Thread",
  subject: "Update",
});
// What a stop is called: an obligation by its widget's own word, else by where it is arrived
// at, but the agent's to-do is a To-do rather than the Update a subject's stop otherwise
// is.
const nounOf = (item, stop) =>
  carriesObligation(item)
    ? obligationWord(item.obligation)
    : stop.kind === "subject" && itemNoun(item) === "todo"
      ? "To-do"
      : NOUNS[stop.kind];

// Where an item of either list, or one that is done, is arrived at: an obligation by its
// own id, but in a thread only a widget's answered by its controls, since a question
// asked in words or a to-do on a thread is arrived at, like anything else there, by the
// thread it stands in; or else where its subject stands (`subjectPlace`), as an action
// handed back is arrived at on the widget it was made on and the agent's to-do at its
// element or the page's head.
const stopOf = (item) =>
  carriesObligation(item) && (item.thread === null || item.kind === "widget")
    ? {
        kind: "obligation",
        id: item.id,
        thread: item.thread,
        obligation: item.obligation,
      }
    : item.thread !== null
      ? {
          kind: "thread",
          id: item.thread,
          thread: item.thread,
          message: answeredInWords(item.obligation) ? item.obligation.message : null,
        }
      : {
          kind: "subject",
          id: item.subject.id ?? item.subject.kind,
          subject: item.subject,
          thread: null,
        };
const sameStop = (a, b) => a.kind === b.kind && a.id === b.id;

// An item as the walk reads it: where it is arrived at, the key the walk's position
// names that stop by, and what the walk calls it. An On me card reads the same, so it
// knows when the walk stands on it, and By kind groups by what the walk calls it.
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

export function createQueueWalk({
  arriveAtRecord,
  arriveAtThread,
  threadPlace,
  prepareNavigationStep,
  arrive,
  readableDestination,
  showOnMe,
  announce,
  actions,
}) {
  // The element a stop stands at on the page, if it has one.
  const stopElement = (stop) =>
    stop.kind === "obligation"
      ? stop.thread !== null
        ? threadPlace(stop.thread)
        : obligationPlace(stop.obligation).node
      : stop.thread !== null
        ? threadPlace(stop.thread)
        : subjectPlace(stop.subject);

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
  // `items` in On me's groups (`grouping`), each a `title` over its items, and `leads`,
  // the items that lead their walk stops: the list's one order, which the walk follows
  // too. The groups and their order are read from
  // everything On me has held (`heldOnMe`), not from which items remain, so the list,
  // which keeps an answered item in its seat, and the walk, which steps over it, stand
  // in one order: a plan's goals in the plan's order, else each group where the first
  // item it holds comes in page order. A group's items stand by their steps' order in
  // a goal, else in page order. Items arrived at in one place, such as a thread's
  // question and a to-do on that thread, are one stop of the walk, so they stand
  // together in the first of their groups. A list leaves out of that order what it
  // draws on another item's card (`carried`, record ids), so a question a decision's
  // card carries, standing on a row of its own once the decision is answered, moves no
  // group while the card holds it.
  function onMeGroups(items, by = grouping(), carried = new Set()) {
    const keyed = new Map(
      [...heldOnMe().filter((item) => !carried.has(item.id)), ...items].map((item) => [
        queueItemKey(item),
        item,
      ]),
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
    // The first item a group lists of each stop, which alone wears the walk's ring.
    const leads = new Set();
    for (const stop of stops.values()) {
      const listed = stop.items.filter((item) => shown.has(queueItemKey(item)));
      if (!listed.length) continue;
      leads.add(listed[0]);
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
        leads,
      }));
  }

  // The walk's stops among `items`, in their order: an item's stop, once, where its
  // first item stands.
  function stopsAmong(items) {
    const list = [];
    const listed = new Set();
    for (const item of items) {
      const stop = queueStop(item);
      // Two items arrived at in one place, such as two to-dos on one thread or on one
      // element, are one stop: the user standing there is on the first of them, which
      // `x` ends, and the next press goes on past the place.
      const at =
        (stop.kind === "obligation" && obligationPlace(stop.obligation).node) ||
        stop.key;
      if (listed.has(at)) continue;
      listed.add(at);
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

  // The item the user is on, if any: the thread holding them, else the innermost of the
  // list's obligations holding their place, as `obligationHolding` reads obligations, so
  // a to-do the user ended leaves them on the one its subject stands in, or the
  // innermost widget an action was handed back on, in page order the last that holds
  // them. A thread drawn beside their place, such as the card a thread about an
  // obligation opens, is not one they are in, so a thread stop of its own is the next
  // one along from the obligation, and from the thread's target the press arrives at
  // it. Being in a thread that holds an open obligation is not being on that
  // obligation. `origin` names the user's place unless a walk supplies its own starting
  // point; only a current location can be on a stop, so a place they let go of or a
  // reading in the viewport starts a walk but selects no task to finish or count.
  function currentLocationStop(list, origin = currentLocationOrigin()) {
    if (origin?.kind !== "current-location") return null;
    const thread = drawnThreadId(threadIn(origin.node));
    return (
      (thread &&
        list.find(
          (candidate) => candidate.kind === "thread" && candidate.id === thread,
        )) ||
      placeStop(list, origin)
    );
  }

  // The obligation or subject stop holding the user's place, if any.
  function placeStop(list, { place: here }) {
    const listed = list.filter((stop) => stop.kind === "obligation");
    const item = obligationHolding(
      listed.map((stop) => stop.obligation),
      placeOf(here),
      readObligations().all,
    );
    if (item) return listed.find((stop) => stop.id === item.id);
    return (
      list.findLast((stop) => {
        if (stop.kind !== "subject") return false;
        const at = stopElement(stop);
        return at && under(here, at);
      }) ?? null
    );
  }

  // The stop `dir` steps to: off the one
  // the user is on, else from their place by the page walks' rule (`stepFrom`,
  // current-target.js). Within a region, a place outside it enters at the end the step
  // faces. `enter` starts inside a selected tab's panel; `at` starts at a visible obligation
  // without stepping off it.
  function step(list, dir, region, origin) {
    // Outside the region nothing the user is on is one of its stops, even where the
    // press sits inside the lf-ask around an obligation.
    if (region && !under(origin.place, region)) return cycledRow(list, null, dir);
    const currentLocation = currentLocationStop(list, origin);
    if (currentLocation) return cycledRow(list, currentLocation, dir);
    return stepFrom(list, origin, dir, (stop) => stop.place);
  }

  // What no owner arrives at, such as a page widget action handed back to the user,
  // travel arrives at where its subject stands.
  function arriveAtElement(find) {
    const intent = retainUserIntent({ available: () => Boolean(find()) });
    const where = find();
    if (!where) return Promise.resolve(false);
    const departure = prepareNavigationStep({ landing: find, intent });
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
    if (stop.kind === "thread") return arriveAtThread(stop.id, stop.message);
    return arriveAtElement(() => stopElement(stop));
  }

  // Where the walk stands in the whole list, and the kind of item it stands on: the
  // count is of every kind, so the kind follows it rather than naming the list.
  function position(region) {
    const list = stopsOf(region);
    const here = currentLocationStop(list);
    const at = listWalkPosition(list, here, { identity: (stop) => stop.key });
    return at && { ...at, qualifier: `${region ? WITHIN : QUALIFIER} · ${here.noun}` };
  }

  // Resolves whether it arrived.
  function walk(dir, region = null, origin = walkOrigin()) {
    const list = stopsOf(region);
    if (!list.length) return Promise.resolve(false);
    const next = step(list, dir, region, origin);
    // The walk reads the current destination, so begin it once the arrival has moved
    // focus. A failed arrival has not arrived and must not register the prior item as
    // this walk's destination.
    const ready = arriveAt(next).then((arrived) => {
      if (!arrived) return false;
      announce(
        beginWalk("queue", null, () => position(region)) ??
          walkPositionLabel(
            null,
            list.indexOf(next) + 1,
            list.length,
            `${region ? WITHIN : QUALIFIER} · ${next.noun}`,
          ),
      );
      if (next.kind === "obligation" && next.obligation.source.kind === "todo")
        showOnMe();
      return true;
    });
    void ready.catch(() => {});
    return ready;
  }

  // The to-do Done ends where the user is on `stop`.
  const doneAt = (stop) =>
    stop
      ? (readQueues().on_user.find(
          (item) => item.offers.done && sameStop(stopOf(item), stop),
        ) ?? null)
      : null;

  // The to-do Done ends now: the one the user is on.
  const doneTodo = () => doneAt(currentLocationStop(stops()));

  // The user's Done on a to-do on them: their `todo_end`, through the one append door.
  // The to-do leaves On me in the turn they press it (`framework/application.js`).
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
    watching ??= effect(() => {
      if (offered() === wasOffered && doneable() === wasDoneable) return;
      wasOffered = offered();
      wasDoneable = doneable();
      untracked(paintKeys);
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
    travels: true,
    // The same shape as the thread walk: it moves the user from item to item rather than
    // down a level, so the current scope lets go of whichever one they end on. An item
    // reached through the panel leaves the panel a level of its own on the way out,
    // whether this walk opened it or the user already had it.
    run: (binding) => walk(binding === "m" ? 1 : -1),
  });

  // Standing on a to-do the user ends with Done, wherever Show, `m`, a click or Tab put
  // them, is a stance whose way out is that Done: `x`, and a finger's check at the end
  // of the panel's row, whose field names the to-do (touch-controls.js).
  pageScope("todo", {
    title: "On a to-do waiting on me",
    says: () => `To-do · ${doneTodo()?.obligation.prompt.text ?? ""}`,
    ready: savedReadingSettled,
    at: () => Boolean(doneTodo()),
    rows: [
      {
        id: "queue.todo.done",
        keys: ["x"],
        title: "done",
        exit: true,
        action: "done",
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
  // which the panel opens with the user on the widget. A question can also arrive at
  // its exact message, including in an unanchored thread.
  const arrivesAt = (item) => {
    const stop = stopOf(item);
    return (
      Boolean(pagePlace(stop)) ||
      Boolean(stop.message) ||
      (stop.kind === "obligation" && stop.thread !== null)
    );
  };

  // The id of the obligation the user last went to, for a walk within a region pressed from
  // outside it. Sequential navigation passes over what it crosses, so it keeps the obligation.
  let wentTo = null;
  onCurrentLocation((node, cause) => {
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
        node: obligationPlace(kept).source,
        place: obligationPlace(kept).source,
        kind: "current-location",
      });
    // What the user reads in the region: the first of its obligations any of which they see,
    // where they are without being on it, so a waiting one is the next and an
    // answered one leads to the next after it.
    const clips = new Map();
    const shown = items
      .map((item) => obligationPlace(item).node)
      .find((node) => node && seenRect(node, clips));
    return shown
      ? walk(toward, within, { node: shown, place: shown, kind: "at" })
      : walk(toward, within, here);
  }

  // On me's list as the panel draws it: its groups, the grouping they stand in and the
  // user's choice of it, the heading each item's row names as its place, and whether
  // one of its items is arrived at on `node`, as a walk standing there would be on it
  // (`currentLocationStop`), so On me's card shows what travel took the user to.
  const onMe = Object.freeze({
    groups: onMeGroups,
    grouping,
    choose: (value) => chosenGrouping.write(value),
    place: itemPlace,
    lists: (node) =>
      Boolean(
        node &&
        currentLocationStop(stops(), {
          kind: "current-location",
          node,
          place: node,
        }),
      ),
  });

  return { mount, arriveAtItem, arrivesAt, onMe, nextWithin };
}
