/* News a thread surface holds back while it would move what the reader reads.

   The rule: what the user sees moves only in answer to a gesture of theirs
   (`skills/leaf/assets/AGENTS.md`, "Layout and motion"). News is not one, so where
   drawing it would move something on screen it waits, and the first gesture that takes
   the user to it shows it, since the motion is then that gesture's. Everything here
   follows from that.

   A seat draws its threads in the page's flow (inline.js: a widget's seat, or a widget's
   outlet such as a diff line's), so whatever the agent adds grows the page there: a turn
   at the foot of its thread, a turn that reopens a resolved thread unfolding it, a thread
   the agent starts at the foot of the seat. A turn of the user's that this page did not
   just send, such as one from another tab, grows it the same way. Where that growth
   starts above the screen, the browser's scroll anchoring takes it into what the user
   has scrolled past; where it starts below, it moves nothing they see. Where it starts
   on screen, everything after it would move under the reader, so the seat draws what it
   drew before and says what is waiting in a row it already draws at a fixed size. A
   thread resolved or reopened elsewhere changes shape the same way:

   - a thread's own news (its new turns, a reaction put on a reply or taken off it, and
     its resolving or reopening, which draws or folds its reply box and reaction strips)
     in the thread's control row: the head row beside Resolve while it is drawn open,
     the foot row in Reopen's place while it is drawn resolved, and a folded outlet's
     summary;
   - a new thread in the control row of the thread it would follow, or, where the seat
     draws no thread, in place of its first-message row, at that row's height, unless the
     user stands in that box, which `holdBox` (reply-landing.js) keeps still instead;
   - a new thread at a widget's datum that has no seat yet, such as a diff line with no
     thread, behind the margin marker it gets. Its seat would be a new outlet the widget
     opens in the flow, with no row in it to say what waits, so the widget is not handed
     the thread to place (surfaces.js), and the margin draws it as it draws any thread
     no widget places, out of the flow.

   A panel card uses the same hold for its own news, and a closed card holds nothing,
   since its title row draws at one size whatever it says. A reply pinned to its
   scrollport can instead absorb news above it by scrolling. A held change leaves the
   controls it touches drawn as they were, and a press on one means what it drew
   (actions.js, `toggleReaction` and `settle`) and shows what the thread holds.

   `HeldNews` is that one owner for a seat, and `HeldArrivals` for the seats a widget has
   not opened. Each reads every reading against the one it drew last, the only baseline:
   news is whatever the seat would draw differently, the notice says exactly that
   difference, and a reading back to what is drawn holds nothing. The gestures that show
   what a thread holds are the ones that take the user to it:

   - pressing its notice, or its margin marker where a widget holds it out of the flow;
   - opening the thread: a folded outlet, or a panel card the list opens;
   - arriving at it: a t/T walk, going to one of its Asks, or any other route that takes
     them to the thread (`showHeld`), whether or not it already stood open. Putting
     back a reply box a surface stopped drawing is no arrival, since no gesture asked
     for it (destination.js, `carried`);
   - acting in it (`gesturedOn`): a reply, a reaction on one of its messages, settling
     it, a move on a widget one of them holds, or a thread they start in the seat, which
     answers what came before it and so follows it;
   - changing the panel's view, which moves its cards anyway.

   Held news also shows once none of the seat shows in the window, where its growth moves
   nothing anyone sees. A gesture that asks for something else in the thread, such as
   pressing into its reply box, shows nothing: the news is not its result, and drawing it
   would move the box under the press. Anything held in a seat is not drawn, so it stays
   unread until it shows.

   `HeldReading` is the same rule for a widget's region whose rows only the log or the
   clock decides, such as a command's lists of stopped goals and live workers: a reading
   that would change its size waits, the region standing as it was, while its growth
   would be seen, and a control of fixed size the widget already draws says so and
   shows it. */
import { shownBand, whenOffScreen } from "../geometry.js";
import { scrollersOf } from "../reading-regions.js";
import { offer } from "../widget-elements.js";
import { keepsText, layoutPx } from "../keeps.js";
import { keys, focused } from "../keyboard/scopes.js";
import { PRESS } from "../keyboard/bindings.js";
import { focusThread } from "./focus.js";
import { threadKey, threadNames } from "./model.js";
import { allThreads } from "./state.js";
import { THREAD } from "./selectors.js";
import { closestAcross } from "../passages.js";
import { readApplication } from "../semantic-state.js";
import { replyPinned } from "./reply-landing.js";

// Whether this page's ledger holds a gesture of the user's on `thread`: one of its
// messages, a reply or a settlement naming one, a reaction or its withdrawal, a move on a
// widget one of them holds, or the refusal that takes one back, which stays in the ledger
// until the reading it restores is drawn. Their words from another tab, or a turn a seat
// first draws after the log answered it, as a package mirror whose render waited on work
// of its own does, arrive like the agent's.
export function gesturedOn(thread) {
  const { unresolved, document, authoritative } = readApplication();
  // A reaction the user withdraws leaves the thread the page draws in the turn they take
  // it back, while the log's reading of the thread still holds it.
  const logged = authoritative?.browser.thread.threads.find(
    ({ id }) => id === thread.id,
  );
  const messages = new Set(
    [...thread.msgs, ...(logged?.msgs ?? [])].map(({ id }) => id),
  );
  const attempts = new Set(thread.msgs.map(({ attempt }) => attempt));
  return unresolved.some(
    ({ event }) =>
      attempts.has(event.attempt) ||
      messages.has(event.parent) ||
      messages.has(event.undoes) ||
      (event.widget &&
        messages.has(document.descriptors.get(event.widget)?.document.message)),
  );
}

// The standing reactions a strip draws, by token, since a reaction keeps its token but
// not its id when the log answers it.
const tokens = (reactions) =>
  new Set(reactions.choices.filter(({ standing }) => standing).map(({ name }) => name));

// The tokens standing in one of two strips and not the other.
const symmetric = (a, b) => [...a, ...b].filter((name) => !a.has(name) || !b.has(name));

// What of `now` the seat would draw differently from `was`, the thread as it drew it:
// each message that is new or whose words changed, each reaction put on a reply or taken
// off it, and the thread's settlement. `messages` is `now`'s messages with each of those
// drawn as `was` drew it and the new ones left out; `changed` the keys of the ones drawn
// as they were, every one where the settlement changes, which moves the thread's
// controls into or out of its head row and draws or folds its reaction strips. A message
// the log took back is no news: it goes. Null where nothing differs.
function difference(was, now) {
  const drawn = new Map(was.messages.map((message) => [message.key, message]));
  const settled =
    Boolean(was.resolved) === Boolean(now.resolved)
      ? null
      : now.resolved
        ? "Resolved"
        : "Reopened";
  const news = { settled, replies: 0, reactions: 0, appended: false };
  const changed = new Set();
  const messages = now.messages.flatMap((message) => {
    const prior = drawn.get(message.key);
    if (!prior) {
      news.replies += 1;
      news.appended = true;
      return [];
    }
    if (JSON.stringify(prior.body) !== JSON.stringify(message.body)) {
      news.replies += 1;
      changed.add(message.key);
      return [prior];
    }
    const turned =
      !settled && message.reactions && prior.reactions
        ? symmetric(tokens(prior.reactions), tokens(message.reactions)).length
        : 0;
    news.reactions += turned;
    if (!settled && !turned) return [message];
    changed.add(message.key);
    return [{ ...message, reactions: prior.reactions }];
  });
  return settled || news.replies || news.reactions ? { news, messages, changed } : null;
}

// What a thread's settlement draws, which a held settlement draws as it was.
const settledFace = ({ resolved, resolvedBy, settlement, reply }) => ({
  resolved,
  resolvedBy,
  settlement,
  reply,
});

// Whether growth after `node` would move what the user sees: the node's foot stands
// inside every box that scrolls it. A node not drawn has no foot to grow from.
function growthAfterIsSeen(node) {
  const { bottom, height } = node?.getBoundingClientRect() ?? {};
  if (!height) return false;
  for (const box of scrollersOf(node)) {
    const band = shownBand(box);
    if (!band || bottom <= band.top || bottom >= band.bottom) return false;
  }
  return true;
}

// Whether growth inside `nodes`, wherever in them it starts, would move what the user
// sees: some of them stands inside every box that scrolls it. Growth wholly above the
// screen goes into what scroll anchoring holds, and wholly below it moves nothing seen.
function growthInsideIsSeen(nodes) {
  return nodes.some((node) => {
    const { top, bottom, height } = node.getBoundingClientRect();
    if (!height) return false;
    return scrollersOf(node).every((box) => {
      const band = shownBand(box);
      return band && bottom > band.top && top < band.bottom;
    });
  });
}

const counted = (count, one, many) => count && `${count} ${count === 1 ? one : many}`;
const newsLabel = ({ settled, replies, reactions, threads }) =>
  [
    settled,
    counted(replies, "new reply", "new replies"),
    counted(reactions, "reaction changed", "reactions changed"),
    counted(threads, "new thread", "new threads"),
  ]
    .filter(Boolean)
    .join(" · ");

/** The control that says what a row holds and shows it. `set(news)` gives it the
 *  reading's `news` ({label, reopened, open}); `open` returns the thread to land a
 *  keyboard on, since the notice goes with what it held. A held reopening's notice stands
 *  where Reopen did, in Reopen's face, which sets its row's height, and is the thread's
 *  reopen control (`lf-reopen`), so the thread's Enter and `r` keep their meaning and
 *  press it to show the thread reopened. */
export function newsNotice() {
  const node = offer("button", "lf-outline-chip lf-thread-news");
  let open = () => null;
  node.onclick = () => {
    const standing = focused() === node;
    const landing = open();
    if (standing && landing) focusThread(landing, { preventScroll: true });
  };
  keys(node, "On news waiting in a thread", [
    {
      id: "thread.news",
      keys: PRESS,
      description: "Show what is waiting",
      title: "show it",
      run: () => node.click(),
    },
  ]);
  return {
    node,
    set(news) {
      keepsText(node, news.label);
      node.classList.toggle("lf-outline-chip", !news.reopened);
      for (const face of ["lf-btn", "lf-thread-action", "lf-reopen"])
        node.classList.toggle(face, news.reopened);
      open = news.open;
    },
  };
}

/** The row a seat that draws no thread shows in its first-message row's place while it
 *  holds a thread, at the height that row stood at. The first-message row has no room
 *  to spare: a notice beside its box moved the box's Send and the hold route beside it.
 *  The box comes back once the thread shows. */
export function seatNotice() {
  const notice = newsNotice();
  const node = offer("div", "lf-seat-news");
  node.append(notice.node);
  return {
    node,
    set(news, box) {
      notice.set(news);
      if (box?.isConnected)
        node.style.blockSize = layoutPx(box.getBoundingClientRect().height);
    },
  };
}

// Every live seat's HeldNews, so an arrival can show what any of them holds of its
// thread.
const holders = new Set();

/** Shows what every seat holds of the thread `id` names, a message's id naming its
 *  thread: the arrival a navigation makes at it. Each seat draws what it released
 *  before this returns. Returns whether any seat held anything of it. */
export function showHeld(id) {
  const thread = threadNames(allThreads()).get(id)?.id ?? id;
  let shown = false;
  for (const held of holders) shown = held.show(thread) || shown;
  return shown;
}

export class HeldNews {
  #seat;
  #view;
  #changed;
  // The reading last drawn, the one each reading is read against: every thread the seat
  // has taken in, by key, drawn or held; the threads it draws holding news; the threads
  // whose news the user asked to see, which the next reading draws as they stand; the
  // threads not drawn; and each thread's key by its id.
  #shown = null;
  #known = new Set();
  #holds = new Set();
  #released = new Set();
  #threads = new Set();
  #keys = new Map();
  #stopWatching = null;

  // `view(key)` is the seat's ThreadView for a thread; `changed()` draws the seat again
  // from the reading it holds.
  constructor(seat, view, changed) {
    this.#seat = seat;
    this.#view = view;
    this.#changed = changed;
    holders.add(this);
  }

  // The reading to draw from `reading`, the seat's whole reading of its threads. The first
  // reading drawn from the read log is what the seat shows on arrival, so none of it is
  // news; one drawn before the log is read, or while the server is away, is no baseline
  // either. `row` says whether the seat draws a first-message row the user is not in, in
  // whose place a new thread's notice can stand.
  hold(reading, { row }) {
    const read = readApplication().phase === "ready";
    if (!read) this.#forget();
    const prior = read ? this.#shown : null;
    const keys = new Set(reading.threads.map(({ key }) => key));
    for (const key of this.#threads) if (!keys.has(key)) this.#threads.delete(key);
    this.#keys = new Map(reading.threads.map(({ id, key }) => [id, key]));
    const gestured = (key) => {
      const thread = allThreads().find((each) => threadKey(each) === key);
      return Boolean(thread) && gesturedOn(thread);
    };
    if (prior) this.#arrive(prior, reading, row, gestured);
    this.#known = keys;
    const shown = this.#draw(prior, reading, gestured);
    this.#released.clear();
    this.#shown = read ? shown : null;
    // Waiting for all of the seat to go keeps news held a little longer than it needs,
    // never shorter.
    if (this.#holding()) this.#stopWatching ??= whenOffScreen([this.#seat], this.#all);
    else this.#stop();
    return shown;
  }

  // Which of the threads new to the seat it holds back.
  #arrive(prior, reading, row, gestured) {
    const arrived = reading.threads.filter(({ key }) => !this.#known.has(key));
    // A thread the user starts is their gesture, and the threads before it show with it.
    if (arrived.some(({ key }) => gestured(key))) this.#threads.clear();
    else if (arrived.length) {
      const last = prior.threads.at(-1)?.key;
      const seen = growthAfterIsSeen(last ? this.#view(last)?.node : this.#seat);
      if (seen && (last || row)) for (const { key } of arrived) this.#threads.add(key);
      else this.#threads.clear();
    }
  }

  // Each thread as it stands, except one whose news would move what the reader reads,
  // which stands as it was drawn, its notice saying what waits.
  #draw(prior, reading, gestured) {
    this.#holds.clear();
    const drawn = new Map(prior?.threads.map((thread) => [thread.key, thread]));
    const threads = reading.threads
      .filter(({ key }) => !this.#threads.has(key))
      .map((thread) => {
        const was = drawn.get(thread.key);
        const held =
          was && !this.#released.has(thread.key) ? difference(was, thread) : null;
        if (!held || gestured(thread.key) || !this.#moves(thread.key, held))
          return { ...thread, news: null };
        this.#holds.add(thread.key);
        // What the news changes stands as drawn. A held reopening's notice stands
        // where Reopen did, since opening it is what reopening would show.
        const { news, messages } = held;
        return {
          ...thread,
          messages,
          ...(news.settled && settledFace(was)),
          ...(news.settled === "Reopened" && { settlement: null }),
          news,
        };
      });
    const waiting = this.#threads.size;
    const host = threads.at(-1);
    if (waiting && host) host.news = { ...host.news, threads: waiting };
    for (const thread of threads) {
      // Progress folds belong to the completing reply. If that reply is held,
      // the updates keep their existing presentation until it is shown too.
      const shown = new Set(thread.messages.map(({ id }) => id));
      thread.summaries = thread.summaries.filter(
        (summary) => !summary.trigger || shown.has(summary.trigger),
      );
      if (thread.news)
        thread.news = {
          label: newsLabel(thread.news),
          reopened: thread.news.settled === "Reopened",
          open: () => this.#open(thread.key, thread === host && waiting),
        };
    }
    // A thread arriving with no thread drawn is held only where the seat drew its
    // first-message row, so its notice stands in that row's place.
    const news =
      waiting && !host
        ? {
            label: newsLabel({ threads: waiting }),
            reopened: false,
            open: () => this.#open(null, true),
          }
        : null;
    return Object.freeze({ ...reading, threads: Object.freeze(threads), news });
  }

  // Whether drawing `held` would move what the reader reads: growth after a message it
  // changes, or after the thread's foot, where a message joins it or its settlement
  // changes what follows its messages, would be seen. A reply actually pinned to its
  // scrollport can absorb news above it, though not a settlement, which takes the reply
  // away or brings it. A short thread's sticky row still stands in flow and has no such
  // space to give.
  #moves(key, { news, changed }) {
    const view = this.#view(key);
    if (
      !view ||
      (!news.settled &&
        replyPinned(view.node.querySelector(":scope > .lf-thread-reply")))
    )
      return false;
    return [
      ...[...changed].map((message) => view.messageNode(message)),
      (news.appended || news.settled) && view.foot,
    ].some((node) => node && growthAfterIsSeen(node));
  }

  // Shows what the seat holds of the thread `id`: its news, or, where the seat holds the
  // thread itself, every thread it holds, as the notice saying them would.
  show(id) {
    const key = this.#keys.get(id);
    const thread = this.#threads.has(key);
    if (!this.#holds.has(key) && !thread) return false;
    this.#open(key, thread);
    return true;
  }

  // Shows what one notice holds: a thread's news, and the seat's new threads where that
  // notice also says them. Returns the thread a keyboard on the notice lands on.
  #open(key, threads) {
    const first = threads && [...this.#threads][0];
    let changed = false;
    if (key && this.#holds.has(key) && !this.#released.has(key)) {
      this.#released.add(key);
      changed = true;
    }
    if (threads && this.#threads.size) {
      this.#threads.clear();
      changed = true;
    }
    // Native disclosure can report the same opening after its owner released the
    // news. A no-op observation must not replace that operation's pending paint.
    if (changed) this.#changed();
    return this.#view(key ?? first)?.node ?? null;
  }

  // The next reading draws every thread as it stands, as when the user changes what
  // the surface shows, which moves its threads anyway.
  release() {
    this.#forget();
  }

  #all = () => {
    if (!this.#holding()) return;
    this.#forget();
    this.#changed();
  };

  // Every thread the seat holds shows on the next reading.
  #forget() {
    for (const thread of this.#shown?.threads ?? []) this.#released.add(thread.key);
    this.#threads.clear();
  }

  #holding() {
    return Boolean(this.#threads.size || this.#holds.size);
  }

  #stop() {
    this.#stopWatching?.();
    this.#stopWatching = null;
  }

  dispose() {
    this.#stop();
    holders.delete(this);
  }
}

/** One region's reading, held while drawing it would move what the reader sees.
 *  `region()` gives the nodes the reading draws, and `changed()` draws the widget again.
 *  A reading is a value equal to the one drawn last exactly when it draws at the same
 *  size, such as the keys of its rows. `hold(reading)` returns the reading to draw:
 *  `reading` where it is the first, where it equals the one drawn last, or where none
 *  of the region shows in the window, since a row may change anywhere in it; otherwise
 *  the reading drawn last. What it holds shows when the user opens it
 *  (`release` or `show`), or once none of the region shows in the window. */
export class HeldReading {
  #region;
  #changed;
  #shown = null;
  #released = false;
  #watch = null;

  constructor(region, changed) {
    this.#region = region;
    this.#changed = changed;
  }

  hold(reading) {
    // Preparation can draw partial authored contributions before the complete log
    // arrives. That is no baseline for news: the first ready reading stands whole.
    if (readApplication().phase !== "ready") {
      this.#shown = null;
      this.#stop();
      return reading;
    }
    const nodes = this.#region();
    if (
      this.#released ||
      this.#shown === null ||
      this.#shown === reading ||
      !growthInsideIsSeen(nodes)
    ) {
      this.#released = false;
      this.#shown = reading;
      this.#stop();
    } else if (
      !this.#watch ||
      this.#watch.nodes.length !== nodes.length ||
      this.#watch.nodes.some((node, at) => node !== nodes[at])
    ) {
      this.#stop();
      this.#watch = { nodes, stop: whenOffScreen(nodes, this.show) };
    }
    return this.#shown;
  }

  // The next reading draws whatever it moves: the user asked, or nobody can see.
  // `release` leaves the drawing to the caller, which may release several readings
  // for one paint; `show` draws now.
  release() {
    this.#released = true;
  }

  show = () => {
    this.release();
    this.#changed();
  };

  #stop() {
    this.#watch?.stop();
    this.#watch = null;
  }

  dispose() {
    this.#stop();
  }
}

/** The threads one widget holds out of its flow: each thread the agent starts at a datum
 *  where the widget draws no thread, while the datum's foot is on screen. `hold` says
 *  which threads the widget is not handed to place. The margin draws each as it draws
 *  a thread no widget places, and pressing its marker is opening the notice, which
 *  `show` answers. The margin draws a held thread's marker though the agent settled it,
 *  since the marker is its notice. A thread also shows when the user adds a turn to it,
 *  settles or reopens it, or starts a thread at its datum, and when none of the datum
 *  shows in the window. */
export class HeldArrivals {
  #changed;
  // The keys of the page's threads at the last reading, or null before a reading drawn
  // from the read log, which is what the page shows on arrival and so no baseline for
  // news; each held thread's id and datum, by key; and the watch on each holding datum's
  // node. A thread the widget is first handed because the user opened its datum, as a
  // collapsed file, is no news.
  #known = null;
  #held = new Map();
  #watching = new Map();

  // `changed()` hands the widget its threads again.
  constructor(changed) {
    this.#changed = changed;
  }

  // The keys to keep out of what the widget places. `threads` holds each thread record
  // the widget has an exact target for, with the `datum` it stands at and that datum's
  // `node`; `drawn` holds the datums where the widget drew a thread last, and `all` is
  // every thread record on the page.
  hold(threads, { drawn, all }) {
    const read = readApplication().phase === "ready";
    if (!read) this.#held.clear();
    else if (this.#known) this.#take(threads, drawn);
    this.#known = read ? new Set(all.map(({ key }) => key)) : null;
    this.#watch(threads);
    return new Set(this.#held.keys());
  }

  #take(threads, drawn) {
    const keys = new Set(threads.map(({ thread }) => thread.key));
    this.#release(({ key }) => !keys.has(key));
    // Settling a thread or reopening it is the user's gesture in it, as a turn is. A
    // thread the agent moves follows its datum, and one moved to a datum with a thread
    // drawn joins that seat, whose HeldNews holds what arrives in it.
    for (const { thread, datum } of threads) {
      const held = this.#held.get(thread.key);
      if (!held) continue;
      held.datum = datum;
      if (gesturedOn(thread)) this.#held.delete(thread.key);
      else if (drawn.has(datum)) this.#lapse((each) => each === held);
    }
    const arrived = threads.filter(({ thread }) => !this.#known.has(thread.key));
    // A thread the user starts at a datum is their gesture, and the threads held there
    // show before it.
    const started = new Set(
      arrived.filter(({ thread }) => gesturedOn(thread)).map(({ datum }) => datum),
    );
    for (const { thread, datum, node } of arrived) {
      // A datum with a thread drawn has a seat, and one whose growth would not be seen
      // draws its threads together.
      if (started.has(datum)) this.#release((held) => held.datum === datum);
      else if (drawn.has(datum) || !growthAfterIsSeen(node))
        this.#lapse((held) => held.datum === datum);
      else this.#held.set(thread.key, { key: thread.key, id: thread.id, datum });
    }
  }

  // Releases what `which` picks for a reason other than a gesture of the user's. A
  // thread the user stands in, in the margin's card, stays there with them, since its
  // release would take the card, and the reply they may be writing, away; it shows
  // when they press its marker, or the next time its datum leaves the window.
  #lapse(which) {
    const standing = closestAcross(focused(), THREAD)?.dataset.thread;
    return this.#release((held) => which(held) && held.id !== standing);
  }

  // One watch for each datum holding a thread, on the node it stands at now.
  #watch(threads) {
    const nodes = new Map(threads.map(({ datum, node }) => [datum, node]));
    const holding = new Set([...this.#held.values()].map(({ datum }) => datum));
    for (const [datum, watch] of this.#watching)
      if (!holding.has(datum) || watch.node !== nodes.get(datum)) {
        watch.stop();
        this.#watching.delete(datum);
      }
    for (const datum of holding) {
      if (this.#watching.has(datum)) continue;
      const node = nodes.get(datum);
      const leave = () => {
        if (this.#lapse((held) => held.datum === datum)) this.#changed();
      };
      this.#watching.set(datum, { node, stop: whenOffScreen([node], leave) });
    }
  }

  holds(id) {
    return [...this.#held.values()].some((held) => held.id === id);
  }

  // Shows the held threads `ids` names, and returns the ones it held, in `ids`' order.
  show(ids) {
    return ids.filter((id) => this.#release((held) => held.id === id));
  }

  #release(which) {
    const released = [...this.#held.values()].filter(which);
    for (const { key } of released) this.#held.delete(key);
    return released.length > 0;
  }

  dispose() {
    for (const watch of this.#watching.values()) watch.stop();
    this.#watching.clear();
  }
}
