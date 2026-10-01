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
     user stands in that box, which `holdBox` (reply-landing.js) keeps still instead.

   `HeldNews` is that one owner for a seat. It reads each reading the seat is handed
   against the one it drew last, holds what is news, and returns the reading to draw,
   each thread carrying `news` where something waits behind it. What it holds shows when
   the user opens the notice, when they add a turn of their own here (a reply in the
   thread, or a thread they start in the seat, which answers what came before it and so
   follows it), or when none of the seat shows in the window, where the growth moves
   nothing they see. Anything held is not drawn, so it stays unread until it shows. */
import { shownBand } from "../geometry.js";
import { scrollersOf } from "../reading-regions.js";
import { offer } from "../widget-elements.js";
import { keepsText, layoutPx } from "../keeps.js";
import { keys, focused } from "../keyboard/scopes.js";
import { PRESS } from "../keyboard/bindings.js";
import { focusThread } from "./focus.js";
import { readApplication } from "../semantic-state.js";

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

// Calls `leave` once none of `node` shows in the window, and returns the step that stops
// watching. Waiting for all of the seat to go keeps news held a little longer than it
// needs, never shorter.
function whenOffScreen(node, leave) {
  const observer = new IntersectionObserver((entries) => {
    if (!entries.at(-1).isIntersecting) leave();
  });
  observer.observe(node);
  return () => observer.disconnect();
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
    if (this.#holding()) this.#stopWatching ??= whenOffScreen(this.#seat, this.#all);
    else this.#stop();
    return shown;
  }

  #take(prior, reading, row) {
    // A turn is the user's gesture while this page's ledger still holds its attempt, as
    // it does in the turn they send it. Their words from another tab, or a turn a seat
    // first draws after the log answered it, as a package mirror whose render waited
    // on work of its own does, arrive like the agent's.
    const ledger = new Set(
      readApplication().unresolved.map(({ event }) => event.attempt),
    );
    const own = ({ author, attempt }) => author === "user" && ledger.has(attempt);
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
