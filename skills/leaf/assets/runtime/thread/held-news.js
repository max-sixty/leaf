/* News a seat in the page's flow holds back while it would move what the reader reads.

   A seat draws its threads in the page's flow (inline.js: a widget's seat, or a widget's
   outlet such as a diff line's), so whatever the agent adds grows the page there: a turn
   at the foot of its thread, a turn that reopens a resolved thread unfolding it, a thread
   the agent starts at the foot of the seat. A turn of the user's that this page did not
   just send, such as one from another tab, grows it the same way. Where that growth
   starts above the screen, the browser's scroll anchoring takes it into what the user
   has scrolled past; where it starts below, it moves nothing they see. Where it starts
   on screen, everything after it would move under the reader, so the seat draws what it
   drew before and says what is waiting in a row it already draws at a fixed size:

   - a thread's own news (its new turns, and the reopening they bring) in the thread's
     control row: the head row beside Resolve while it is open, the foot row beside
     Reopen once resolved, and a folded outlet's summary;
   - a new thread in the control row of the thread it would follow, or, where the seat
     draws no thread, in place of its first-message row, at that row's height, unless the
     user stands in that box, which `holdBox` (reply-landing.js) keeps still instead;
   - a new thread at a widget's datum that has no seat yet, such as a diff line with no
     thread, behind the margin marker it gets. Its seat would be a new outlet the widget
     opens in the flow, with no row in it to say what waits, so the widget is not handed
     the thread to place (surfaces.js), and the margin draws it as it draws any thread
     no widget places, out of the flow.

   `HeldNews` is that one owner for a seat, and `HeldArrivals` for the seats a widget has
   not opened. Each reads every reading against the one it drew last and holds what is
   news. What it holds shows when the user opens the notice, when they add a turn of
   their own here (a reply in the thread, or a thread they start in the seat, which
   answers what came before it and so follows it), or when none of the seat shows in the
   window, where the growth moves nothing they see. Anything held in a seat is not
   drawn, so it stays unread until it shows.

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
import { turns } from "./model.js";
import { THREAD } from "./selectors.js";
import { closestAcross } from "../passages.js";
import { readApplication } from "../semantic-state.js";

// Whether a turn is the user's gesture: one this page's ledger still holds the attempt
// of, as it does in the turn they send it. Their words from another tab, or a turn a
// seat first draws after the log answered it, as a package mirror whose render waited
// on work of its own does, arrive like the agent's.
function ownTurn() {
  const ledger = new Set(
    readApplication().unresolved.map(({ event }) => event.attempt),
  );
  return ({ author, attempt }) => author === "user" && ledger.has(attempt);
}

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
const newsLabel = ({ reopened, replies, threads }) =>
  [
    reopened && "Reopened",
    counted(replies, "new reply", "new replies"),
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
      does: "Show what is waiting",
      line: "show it",
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

export class HeldNews {
  #seat;
  #view;
  #changed;
  // The reading last drawn; every thread and turn the seat has taken in, drawn or held,
  // so a reading after a release finds nothing new in what it shows; and what is held
  // back: each thread's held turns, the threads drawn resolved though a held turn reopened
  // them, and the threads not drawn.
  #shown = null;
  #known = new Map();
  #turns = new Map();
  #reopened = new Set();
  #threads = new Set();
  #stopWatching = null;

  // `view(key)` is the seat's ThreadView for a thread; `changed()` draws the seat again
  // from the reading it holds.
  constructor(seat, view, changed) {
    this.#seat = seat;
    this.#view = view;
    this.#changed = changed;
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
    for (const key of this.#turns.keys()) if (!keys.has(key)) this.#turns.delete(key);
    for (const key of this.#reopened) if (!keys.has(key)) this.#reopened.delete(key);
    for (const key of this.#threads) if (!keys.has(key)) this.#threads.delete(key);
    if (prior) this.#take(prior, reading, row);
    this.#known = new Map(
      reading.threads.map(({ key, messages }) => [
        key,
        new Set(messages.map((message) => message.key)),
      ]),
    );
    const shown = this.#draw(prior, reading);
    this.#shown = read ? shown : null;
    // Waiting for all of the seat to go keeps news held a little longer than it needs,
    // never shorter.
    if (this.#holding()) this.#stopWatching ??= whenOffScreen([this.#seat], this.#all);
    else this.#stop();
    return shown;
  }

  #take(prior, reading, row) {
    const own = ownTurn();
    const arrived = reading.threads.filter(({ key }) => !this.#known.has(key));
    // A thread the user starts is their gesture, and the threads before it show with it.
    if (arrived.some(({ messages }) => messages[0] && own(messages[0])))
      this.#threads.clear();
    else if (arrived.length) {
      const last = prior.threads.at(-1)?.key;
      const seen = growthAfterIsSeen(last ? this.#view(last)?.node : this.#seat);
      if (seen && (last || row)) for (const { key } of arrived) this.#threads.add(key);
      else this.#threads.clear();
    }
    const drawn = new Map(prior.threads.map((thread) => [thread.key, thread]));
    for (const thread of reading.threads) {
      const was = drawn.get(thread.key);
      if (!was) continue;
      const known = this.#known.get(thread.key);
      const added = thread.messages.filter(({ key }) => !known.has(key));
      // A thread settled again stands as drawn.
      if (thread.resolved) this.#reopened.delete(thread.key);
      if (!added.length) continue;
      if (added.some(own) || !growthAfterIsSeen(this.#view(thread.key)?.foot)) {
        this.#turns.delete(thread.key);
        this.#reopened.delete(thread.key);
        continue;
      }
      const held = this.#turns.get(thread.key) ?? new Set();
      for (const { key } of added) held.add(key);
      this.#turns.set(thread.key, held);
      if (was.resolved && !thread.resolved) this.#reopened.add(thread.key);
    }
  }

  #draw(prior, reading) {
    const drawn = new Map(prior?.threads.map((thread) => [thread.key, thread]));
    const threads = reading.threads
      .filter(({ key }) => !this.#threads.has(key))
      .map((thread) => {
        const held = this.#turns.get(thread.key);
        if (!held) return { ...thread, news: null };
        const reopened = this.#reopened.has(thread.key);
        const was = drawn.get(thread.key);
        return {
          ...thread,
          messages: thread.messages.filter(({ key }) => !held.has(key)),
          // The reopening waits too: the thread stands as drawn, resolved, and its notice
          // stands where Reopen did, since opening it is what reopening would show.
          ...(reopened && {
            resolved: true,
            resolvedBy: was.resolvedBy,
            settlement: null,
            reply: false,
          }),
          news: { reopened, replies: held.size },
        };
      });
    const waiting = this.#threads.size;
    const host = threads.at(-1);
    if (waiting && host) host.news = { ...host.news, threads: waiting };
    for (const thread of threads)
      if (thread.news)
        thread.news = {
          label: newsLabel(thread.news),
          reopened: Boolean(thread.news.reopened),
          open: () => this.#open(thread.key, thread === host && waiting),
        };
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

  // Shows what one notice holds: a thread's news, and the seat's new threads where that
  // notice also says them. Returns the thread a keyboard on the notice lands on.
  #open(key, threads) {
    const first = threads && [...this.#threads][0];
    if (key) {
      this.#turns.delete(key);
      this.#reopened.delete(key);
    }
    if (threads) this.#threads.clear();
    this.#changed();
    return this.#view(key ?? first)?.node ?? null;
  }

  #all = () => {
    if (!this.#holding()) return;
    this.#forget();
    this.#changed();
  };

  #forget() {
    this.#turns.clear();
    this.#reopened.clear();
    this.#threads.clear();
  }

  #holding() {
    return Boolean(this.#turns.size || this.#threads.size);
  }

  #stop() {
    this.#stopWatching?.();
    this.#stopWatching = null;
  }

  dispose() {
    this.#stop();
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
    const own = ownTurn();
    const keys = new Set(threads.map(({ thread }) => thread.key));
    this.#release(({ key }) => !keys.has(key));
    // Settling a thread or reopening it is the user's gesture in it, as a turn is. A
    // thread the agent moves follows its datum, and one moved to a datum with a thread
    // drawn joins that seat, whose HeldNews holds what arrives in it.
    for (const { thread, datum } of threads) {
      const held = this.#held.get(thread.key);
      if (!held) continue;
      held.datum = datum;
      if (thread.settling || turns(thread).some(own)) this.#held.delete(thread.key);
      else if (drawn.has(datum)) this.#lapse((each) => each === held);
    }
    const arrived = threads.filter(({ thread }) => !this.#known.has(thread.key));
    // A thread the user starts at a datum is their gesture, and the threads held there
    // show before it.
    const started = new Set(
      arrived.filter(({ thread }) => own(thread.root)).map(({ datum }) => datum),
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
