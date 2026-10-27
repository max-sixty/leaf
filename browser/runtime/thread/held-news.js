/* News a thread surface holds back while it would move what the reader reads.

   These holds protect existing reading and active composition
   (`skills/leaf/references/interface-principles.md`). Each surface's rule below
   determines which surrounding content may move as messages arrive. A held change
   shows when a gesture takes the user to it. A hidden tab ends that reading. Returning reveals its held
   news and its first refreshed reading through the shared reading-continuity owner;
   keyboard blur alone leaves the reading protected. The ordinary message arrival
   tint and retirement fold explain the changed layout without withholding its words.

   A seat draws its threads in the page's flow (inline.js: a widget's seat, or a widget's
   outlet such as a diff line's), so whatever the agent adds grows the page there: a turn
   at the foot of its thread, a turn that reopens a resolved thread taking it out of the
   seat's Resolved disclosure, a thread the agent starts at the foot of the seat. A turn of the user's that this page did not
   just send, such as one from another tab, grows it the same way. Where that growth
   starts above the screen, the browser's scroll anchoring takes it into what the user
   has scrolled past; where it starts below, it moves nothing they see (geometry.js,
   `motionBand`, says where that is). Where it starts on screen, everything after it
   would move under the reader, so the seat draws what it drew before and says what is
   waiting in a row it already draws at a fixed size. A
   thread resolved or reopened elsewhere changes shape the same way:

   - a thread's own news (its new turns, a reaction put on a reply or taken off it, a
     summary the agent folds turns into or one that goes, and its resolving or reopening,
     which draws or folds its reply box and reaction strips) in the thread's control
     row: the head row beside Resolve or Reopen, Reopen's place in a resolved panel
     card's title, and, for its reopening alone, the summary of a seat's closed Resolved
     disclosure folding it, where nothing else it changes shows;
   - a new thread in the control row of the thread it would follow, or, where the seat
     draws no thread, in place of its first-message row, at that row's height, unless the
     user is in that box, which `holdBox` (reply-landing.js) keeps still instead;
   - a new thread at a widget's datum that has no seat yet, such as a diff line with no
     thread, behind the margin marker it gets. Its seat would be a new outlet the widget
     opens in the flow, with no row in it to say what waits, so the widget is not handed
     the thread to place (surfaces.js), and the margin draws it as it draws any thread
     no widget places, out of the flow.

   An open panel card shows appended messages immediately when no composition is
   active: its idle reply row and later cards may move, while existing messages keep
   their place. The margin's floating card is a seat whose growth moves one of its own
   edges (thread-preview.js). News at the thread's end shows at once where the card
   holds its top, beside or below what it is about with the user not writing in it, its
   reply row moving; everything else waits, but a settlement, which keeps the editor it
   interrupts (thread-card.js, `newsMoves`). A reply the agent is still streaming at the thread's end is such an
   appended message, its words joining it as they come and its answer completing it
   in place, so it streams into an idle open card and a held one counts it once as a
   new reply. So is an answer hiding the progress before it
   where that progress is the run at the thread's end, as the agent's acknowledgement
   is, unless the user is on a message the fold puts away, by focus or by a
   selection reaching into it (`currentLocationTouches`, focus.js). Hiding progress above a user's
   later message changes earlier content and uses the ordinary reading hold.
   The progress itself is no reply: until that answer it joins its run's face, the
   thread's working message while the work runs, not its replies (transcript.js), and
   its messages stand behind that face. A run the work leaves keeps its face where it
   stands, so only the newest run's face changes. The
   working message's arrival, its departure, and a new step whose words wrap to
   another height change the thread's height, so a seat holds any change of its words
   when that growth would move the reader. Its notice doesn't say that change (the
   user's choice, 2026-10-26): progress never counts as unread, and the receipt on the
   user's message, such as "On it", already says the agent is working, so a red
   "1 new message" over a draft announced news the user owes nothing. Held alone, it
   shows by any route below but the notice. Rejected: counting each held step as
   "1 new message" (2026-10-14 to 2026-10-26), and "Work in progress" or "Work
   changed" where the working message changed alone, which repeated that receipt.
   Completed progress disappears when the answer shows. Changes to other existing
   messages, reactions, folds and settlement use the same hold as a seat in page flow,
   and a notice calls a changed message an edit.
   A closed card holds nothing, since its title row draws at one size whatever it says.
   A reply pinned to its scrollport lets a turn joining the thread's end grow up into
   the room scrolled past, though nothing that changes above that end. A held change leaves the controls it touches drawn as they
   were, and a press on one means what it drew (actions.js, `setReaction` and
   `settle`) and shows what the thread holds.

   `HeldNews` is that one owner for a seat, and `HeldArrivals` for the seats a widget has
   not opened. Each reads every reading against the one it drew last, the only baseline:
   news is whatever the seat would draw differently, the notice says exactly that
   difference, and a reading back to what is drawn holds nothing. The gestures that show
   what a thread holds are the ones that take the user to it:

   - pressing its notice, or its margin marker where a widget holds it out of the flow;
   - opening the thread: a seat's Resolved disclosure folding it, or a panel card the
     list opens;
   - arriving at it: coming to stand in it from outside it, by a move of theirs, a t/T
     walk, an obligation, a link, Tab, whatever route took them (focus.js, `onCurrentLocation`), or by
     a press on its title, which stands for the whole thread, whether or not it already
     stood open. Coming back to the thread they were in is a stay, whatever puts them
     there, as when the runtime puts back a reply box a surface stopped drawing, and so
     is a move within it, such as Escape out of its reply box onto its title or going to
     an obligation it already shows;
   - acting in it (`gesturedOn`): a reply, a reaction on one of its messages, settling
     it, an action on a widget one of them holds or one that closes it, as accepting
     the suggestion it asked for does, or a thread they start in the seat, which
     answers what came before it and so follows it;
   - changing the panel's view, which moves its cards anyway.

   Held news also shows once growth anywhere in the seat would move nothing the user
   sees: none of it stands where a change of size moves what is seen (geometry.js,
   `growthIsSeen`), as when it is scrolled under the chrome. A press into the thread,
   such as into its reply box, shows
   nothing: it asks for what it lands on, and drawing the news would move that under the
   press. Where the destination is itself held, a message or an obligation in a held turn, or a
   thread a seat holds whole, the route shows it first (`showHeld`), since nothing
   undrawn can take focus. Anything held in a seat is not drawn, so it stays unread until
   it shows.

   Decisions. An idle open panel card shows appended messages (the user's decision,
   2026-10-08, relaxing #1694's blanket hold), and a streaming reply's words as they
   come (2026-10-09: holding them as an edit left the agent's opening an empty bubble
   behind "1 new reply" until the user pressed it), and an answer folding the progress
   run at the thread's end (2026-10-09: since #1926 the agent's first move is a progress
   acknowledgement, so holding the fold held nearly every answer). Everything above that
   run, the message the user is on and an active editor remain protected. Rejected: filling the list (#1480), which makes the
   open card as tall as the panel and leaves later cards below the fold; and letting a
   list that cannot scroll push its contents down, which needs the shift watch to stop
   checking such lists. Arrival is read from where the user is (the user's decision,
   2026-10-06, reversing #1780's record). Rejected: a `showHeld` call in each route that
   takes the user to a thread, which every new route had to remember and a route putting
   them back had to opt out of. The margin's floating card holds news while the user
   writes in it and keeps the width it first stood at (the user's decision,
   2026-10-13): before, it took every change at once, widening up to 232px and carrying
   Resolve, Close and Send sideways, and rising under a draft. Rejected: keeping only
   its width, which doubled the rise; keeping its box and scrolling the transcript,
   which scrolls Resolve away; and holding all news while it is open, which stops
   progress showing live where the user watches it. A presentation that makes room for
   the agent's answer to the user's last turn itself shows that answer at once, as the
   floating panel's thread view does (the user's decision, 2026-10-14, floating-panel.js):
   held, the reply the user waited for stood unseen behind a small notice in their own
   message's head row.

   `HeldReading` is the same rule for a widget's region whose rows only the log or the
   clock decides, such as a command's lists of stopped goals and live workers. The first
   ready reading draws whole. After that, a reading that would change the region's size
   waits, the region staying as it was, while its growth would be seen, and a control
   of fixed size the widget already draws says so and shows it.

   No first paint can size such a region, so a widget keeps its rows closed until the
   reader opens them through that control, as the Atlas plan's Stopped work disclosure
   does (`examples/command-hub.page/widgets/lf-atlas-plan.js`). The conversation
   workspace (`examples/corpus.page/widgets/lf-conversation-workspace.js`) is a known
   exception: it draws its lists at first paint, with "Lists current" as the control.
   A fixed-height box that scrolls the rows is no answer: a scroller shows no edge until
   it is scrolled, so nothing tells the reader a row is cut off. */
import { html, render } from "/runtime/framework.js";
import { growthAfterIsSeen, growthIsSeen, whenNone } from "../geometry.js";
import { offer } from "../widget-elements.js";
import { keeps, layoutPx } from "../keeps.js";
import { sizeObserver } from "../rendering.js";
import { keys } from "../keyboard/scopes.js";
import { PRESS } from "../keyboard/bindings.js";
import { focusThread } from "./focus.js";
import { isReaction, messageKey, threadKey } from "./model.js";
import { allThreads, threadIdNamed, threadState } from "./state.js";
import { drawnThreadId, THREAD } from "./selectors.js";
import { closestAcross } from "../passages.js";
import { runtime } from "../context.js";
import { onCurrentLocation, focused, currentLocationNodes } from "../focus.js";
import { onReadingInterrupted, readingIsContinuous } from "../reading-continuity.js";
import { pagePresented } from "../page-paint.js";
import { watchOwner } from "../arrivals.js";

// Whether this page's ledger holds a gesture of the user's on `thread`, of any kind, the
// refusal that takes one back included until the reading it restores is drawn: the
// application publisher says which thread each stands in (`thread.gestured`). Their
// words from another tab, or a turn a seat first draws after the log answered it, arrive
// like the agent's.
export const gesturedOn = (thread) => threadState().gestured.includes(thread.id);

// Whether the user acts in the thread a seat draws under `key` (`gesturedOn`).
const gestured = (key) => {
  const thread = allThreads().find((each) => threadKey(each) === key);
  return Boolean(thread) && gesturedOn(thread);
};

// The reactions in force a strip draws, by token, since a reaction keeps its token but
// not its id when the log answers it.
const tokens = (reactions) =>
  new Set(reactions.choices.filter(({ inForce }) => inForce).map(({ name }) => name));

// The tokens in force in one of two strips and not the other.
const symmetric = (a, b) => [...a, ...b].filter((name) => !a.has(name) || !b.has(name));

// A summary as a card draws it: the messages of `drawn`, the ids of the turns the card
// draws, that it folds, and whether one of them holds it open (`protected`, which the
// server derives from whose turn it is). A reaction reply it covers draws as a strip.
const fold = (summary, drawn) =>
  JSON.stringify([
    summary.id,
    summary.covers.filter((id) => drawn.has(id)),
    Boolean(summary.protected?.length),
  ]);

// The edit a message's words were last rewritten by, or null for words as first said.
const rewritten = (message) => (message.base === message.id ? null : message.base);

// How the seat would draw `message` differently in its words from `prior`, the same
// message as it drew it, or null where they stand as drawn:
// - "joined": a turn new to the thread, the agent's reply or a message of the user's
//   such as one from another tab, or words joining the reply still streaming, which a
//   provisional message stands for at the thread's end and which grows there as an
//   appended turn does;
// - "rewritten": words a new revision changed, an edit;
// - "grew": words that changed under the same revision, still that message arriving.
function messageChange(prior, message) {
  if (!prior) return "joined";
  const reworded = JSON.stringify(prior.body) !== JSON.stringify(message.body);
  if (prior.provisional) return reworded ? "joined" : null;
  if (!reworded) return null;
  return rewritten(prior) === rewritten(message) ? "grew" : "rewritten";
}

// What of `now` the seat would draw differently from `was`, the thread as it drew it:
// each message's words (`messageChange`), each reaction put on a reply or taken off it,
// each summary that comes or goes, and the thread's settlement.
// `changed` the keys of the messages the news changes in place, every one where the
// settlement changes, which moves the thread's controls into or out of its head row and
// draws or folds its reaction strips; `folds` the keys of the messages a summary that
// comes or goes covers, and the ids of those that go, whose checkpoints a summary's
// change redraws from their tops. A summary a new reply completes, as progress is
// folded when the agent's answer arrives, moves what it covers but is that reply's news,
// so the notice does not count it, and where it folds the run standing at the thread's
// foot (`footFold`) it changes only that foot, as the answer's arrival does. `answers`
// says the news is the agent answering the user, who had the last turn as drawn: all of
// it, the reply, the work under way on it and that work's fold, lies after that turn,
// which a presentation may show at once (primary-reader.js, `answersAtOnce`). A message the log
// took back is no news: it goes. `joined` names new messages and existing streamed
// messages whose words grew, including progress. Card placement uses those same
// arrivals when predicting motion and when they actually show. Null where nothing differs.
export function threadChange(was, now, { progressOpen = false } = {}) {
  const drawn = new Map(was.messages.map((message) => [message.key, message]));
  const settled =
    Boolean(was.resolved) === Boolean(now.resolved)
      ? null
      : now.resolved
        ? "Resolved"
        : "Reopened";
  const news = {
    settled,
    working: was.working?.words !== now.working?.words,
    replies: 0,
    messages: 0,
    edits: 0,
    reactions: 0,
    appended: false,
  };
  const changed = new Set();
  const joined = new Set();
  const arrived = new Set();
  for (const message of now.messages) {
    const prior = drawn.get(message.key);
    const change = messageChange(prior, message);
    if (change === "joined") joined.add(message.key);
    if (!prior || prior.provisional) arrived.add(message.id);
    // A progress message joins the thread's working message, not its replies, so it is
    // the working message's news (`news.working`), which the notice doesn't say. Where
    // the step shows, because the reader opened the progress (`progressOpen`,
    // thread-card.js) or the thread is resolved and keeps its progress as messages, it
    // is a reply's news.
    if (change === "joined" && message.progress && !progressOpen && !now.resolved)
      continue;
    if (change === "joined") {
      if (message.author === "agent") news.replies += 1;
      else news.messages += 1;
      news.appended = true;
    } else if (change === "grew" || change === "rewritten") {
      news[change === "grew" ? "replies" : "edits"] += 1;
      changed.add(message.key);
    } else if (settled) changed.add(message.key);
    else if (message.reactions && prior.reactions) {
      const turned = symmetric(tokens(prior.reactions), tokens(message.reactions));
      news.reactions += turned.length;
      if (turned.length) changed.add(message.key);
    }
  }
  const summaries = (reading) => {
    const ids = new Set(reading.messages.map(({ id }) => id));
    return new Map(reading.summaries.map((summary) => [fold(summary, ids), summary]));
  };
  const before = summaries(was);
  const after = summaries(now);
  const added = [...after].filter(([at]) => !before.has(at)).map(([, each]) => each);
  const gone = [...before].filter(([at]) => !after.has(at)).map(([, each]) => each);
  news.summaries = added.length || gone.length;
  // Completed progress leaves the presentation, but stays in the source reading.
  // Its answer is the news; taking back a message by Undo remains no news.
  const visible = new Set(now.messages.map(({ id }) => id));
  const retired = new Set(
    now.source.msgs
      .filter((message) => visible.has(message.completed_by))
      .map(({ key }) => key),
  );
  const removed = was.messages.filter(({ key }) => retired.has(key));
  const keys = new Map(
    [...was.messages, ...now.messages].map(({ id, key }) => [id, key]),
  );
  // Replacing only the final progress run changes the same foot as an arriving
  // answer. Earlier progress, including a run before a user interjection, also
  // disappears, so its old position participates in the ordinary reading hold.
  const arrivals = new Set(
    now.messages.filter(({ id }) => arrived.has(id)).map(({ key }) => key),
  );
  const tail = was.messages.map(({ key }) => key).filter((key) => !arrivals.has(key));
  const footFold =
    removed.length > 0 &&
    !added.length &&
    !gone.length &&
    tail.slice(-removed.length).every((key) => retired.has(key));
  const folds = {
    messages: [
      ...removed.map(({ key }) => key),
      ...[...added, ...gone].flatMap(({ covers }) =>
        covers.map((id) => keys.get(id)).filter(Boolean),
      ),
    ],
    summaries: gone.map(({ id }) => id),
  };
  const counts = ["working", "replies", "messages", "edits", "reactions", "summaries"];
  if (!settled && counts.every((count) => !news[count])) return null;
  const appendedAtEnd =
    news.appended &&
    was.messages
      .filter(({ key }) => !retired.has(key))
      .every((message, index) => now.messages[index]?.key === message.key);
  const turn = was.messages.findLastIndex(
    (message) => message.author === "user" && !message.progress,
  );
  const asked = new Set(was.messages.slice(0, turn + 1).map(({ key }) => key));
  const answers =
    turn >= 0 &&
    was.messages
      .slice(turn + 1)
      .every((message) => message.progress || message.provisional) &&
    !settled &&
    !news.messages &&
    !news.edits &&
    !news.reactions &&
    !news.summaries &&
    !folds.summaries.length &&
    (!news.appended || appendedAtEnd) &&
    ![...changed, ...folds.messages].some((key) => asked.has(key));
  return { news, changed, joined, folds, appendedAtEnd, footFold, answers };
}

// The thread `now` with what `was`, the thread as the seat drew it, did not show held
// back: what the log's news changed, as drawn. That is its settlement; its messages, the
// new ones left out, a reaction taken off or a streaming reply gone still present, and
// each one's words as drawn, which only an edit or a stream changes; and its summaries
// as drawn. A held thread is read from this as from any other, so what the reading
// derives from those, such as its title, its reaction strips or its controls, agrees
// with what it draws.
// Whose turn it is and each message's delivery read as they stand, as the server
// derives them: they change the title's status and a message's head row in place, as
// in a thread that holds nothing, so a resolution held from the card already takes its
// turn off the title.
function withheld(was, now) {
  const current = new Map(now.msgs.map((message) => [messageKey(message), message]));
  const msgs = was.msgs.flatMap((prior) => {
    const message = current.get(messageKey(prior));
    if (!message) return isReaction(prior) || prior.provisional ? [prior] : [];
    // A streaming reply held as drawn is still the reply arriving, whatever completed it.
    // Its content version is the one its drawn words are, so the words a rewrite holds
    // back are neither marked read nor taken for the rewrite.
    const { text, body, edited, content_version, provisional, reactions } = prior;
    return [
      Object.freeze({
        ...message,
        text,
        body,
        edited,
        content_version,
        provisional,
        reactions,
        // A failed stream can remain in this held reading after leaving the server's
        // current reading. Its progress stays hidden until that stream leaves too.
        completed_by: message.completed_by ?? prior.completed_by,
      }),
    ];
  });
  return Object.freeze({
    ...now,
    root:
      msgs.find((message) => messageKey(message) === messageKey(now.root)) ?? now.root,
    resolved: was.resolved,
    msgs: Object.freeze(msgs),
    summaries: was.summaries,
  });
}

const counted = (count, one, many) => count && `${count} ${count === 1 ? one : many}`;
/** @param {{
 *   settled?: string,
 *   replies?: number,
 *   messages?: number,
 *   edits?: number,
 *   reactions?: number,
 *   summaries?: number,
 *   threads?: number,
 * }} news */
const newsParts = ({
  settled,
  replies,
  messages,
  edits,
  reactions,
  summaries,
  threads,
}) =>
  [
    settled,
    counted(replies, "new reply", "new replies"),
    counted(messages, "new message", "new messages"),
    counted(edits, "message edited", "messages edited"),
    counted(reactions, "reaction changed", "reactions changed"),
    counted(summaries, "summary changed", "summaries changed"),
    counted(threads, "new thread", "new threads"),
  ].filter(Boolean);

// What a notice says: each fact of the news, most telling first and each after the
// first led by its separator, and the line they make.
const said = (news) => {
  const parts = newsParts(news).map((part, index) => (index ? ` · ${part}` : part));
  return { parts, label: parts.join("") };
};

/** The control that says what a row holds and shows it. `set(news)` gives it the
 *  reading's `news` ({parts, label, reopened, open}); `open` returns the thread to land a
 *  keyboard on, since the notice goes with what it held. A held reopening's notice stands
 *  where Reopen did, with the same compact face as other news, and is the thread's
 *  reopen control (`lf-reopen`), so the thread's Enter and `r` keep their meaning and
 *  press it to show the thread reopened. A `header` notice stands in a resolved panel
 *  card's title as a node of its own, since the notice in the card's rows may have
 *  stood elsewhere a moment before. The words have a span of their own, so a card that
 *  holds the notice's room (`data-room`, controls.css) keeps it at the width of the
 *  news it first said. Each fact of the news has a span in it, and a fact that would
 *  pass the notice's width drops whole rather than cutting the facts before it, so
 *  "1 new reply" with a message arriving after it still reads "1 new reply", where a cut
 *  read "1 new re…" (components/surfaces.css); the title and the accessible name keep
 *  every fact. While facts are dropped, the notice counts them at its end ("+1",
 *  `data-lf-more`), so a reader with no tooltip, as on a phone, knows more waits. The
 *  count reads the layout, so a size observer recounts whenever the words or a fact
 *  change size, a fact's first observation included. */
export function newsNotice(header = false) {
  const node = offer(
    "button",
    header
      ? "lf-thread-notice lf-thread-notice-news lf-thread-header-action lf-thread-news"
      : "lf-thread-notice lf-thread-notice-news lf-thread-news",
  );
  const words = document.createElement("span");
  node.append(words);
  // A dropped fact wraps onto a line below the first (components/surfaces.css).
  const dropped = sizeObserver(() => {
    const [first, ...later] = /** @type {HTMLElement[]} */ ([...words.children]);
    const count = later.filter((fact) => fact.offsetTop !== first.offsetTop).length;
    keeps(words, "data-lf-more", count ? `+${count}` : null);
  });
  let open = () => null;
  const show = () => {
    const currentLocation = focused() === node;
    const landing = open();
    if (currentLocation && landing) focusThread(landing, "move");
  };
  keys(node, "On news waiting in a thread", [
    {
      id: "thread.news",
      keys: PRESS,
      title: "show what is waiting",
      control: node,
      run: show,
    },
  ]);
  return {
    node,
    set(news) {
      if (words.textContent !== news.label) {
        render(html`${news.parts.map((part) => html`<span>${part}</span>`)}`, words);
        dropped.disconnect();
        for (const box of [words, ...words.children]) dropped.observe(box);
      }
      keeps(node, "title", news.label);
      node.classList.toggle("lf-reopen", news.reopened);
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
 *  thread: an arrival at it, or a route whose destination it holds. Each seat draws
 *  what it released before this returns. Returns whether any seat held anything of it. */
export const showHeld = (id) => everySeat(id, (held, thread) => held.show(thread));

/** Shows the new threads a seat holds back where `id` names one of them, as their
 *  notice would, and nothing it holds of threads it draws: a destination with no node
 *  until its seat draws it. Returns whether any seat held it. */
export const showHeldThread = (id) =>
  everySeat(id, (held, thread) => held.showThreads(thread));

function everySeat(id, show) {
  const thread = threadIdNamed(id);
  let shown = false;
  for (const held of holders) shown = show(held, thread) || shown;
  return shown;
}

// The thread the user is in, and their arrivals at another, which show what it holds.
let currentLocation = null;
onCurrentLocation((node, cause) => {
  // A drop leaves them in the thread, for its owner to put them back in.
  if (cause === "drop") return;
  const thread = node && closestAcross(node, THREAD);
  const id = drawnThreadId(thread);
  const arrived =
    id !== null && id !== currentLocation && (cause === "move" || cause === "step");
  currentLocation = id;
  if (arrived) showHeld(id);
});

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
  #released = new Map();
  #threads = new Set();
  #keys = new Map();
  #stopWatching = null;

  // `view(key)` is the seat's ThreadView for a thread; `changed()` draws the seat again
  // from the reading it holds.
  constructor(seat, view, changed) {
    this.#seat = seat;
    this.#view = view;
    // A seat taken off the page, as the margin card's when it steps to another thread,
    // draws nothing again: its views would take back controls the live one now holds.
    this.#changed = () => {
      if (seat.isConnected) changed();
    };
    holders.add(this);
  }

  // The reading to draw from `reading`, the seat's whole reading of its threads. The first
  // reading drawn from the read log is what the seat shows on arrival, so none of it is
  // news; one drawn before the log is read, or while the server is away, is no baseline
  // either. `row` says whether the seat draws a first-message row the user is not in, in
  // whose place a new thread's notice can stand.
  hold(reading, { row }) {
    const candidate = this.prepare(reading, { row });
    candidate.commit();
    return candidate.reading;
  }

  // Required presenters prepare before yielding to package layout. Only the
  // candidate actually painted becomes the baseline for the next comparison.
  prepare(reading, { row }) {
    const read = runtime.statePhase === "ready";
    if (!read || !readingIsContinuous()) this.#forget();
    const prior = read ? this.#shown : null;
    const keys = new Set(reading.threads.map(({ key }) => key));
    for (const key of this.#threads) if (!keys.has(key)) this.#threads.delete(key);
    this.#keys = new Map(reading.threads.map(({ id, key }) => [id, key]));
    if (prior) this.#arrive(prior, reading, row);
    const shown = this.#draw(prior, reading);
    const released = new Map(this.#released);
    // Waiting for all of the seat to go keeps news held a little longer than it needs,
    // never shorter.
    if (this.#holding())
      this.#stopWatching ??= whenNone([this.#seat], growthIsSeen, this.#all);
    else this.#stop();
    return {
      reading: shown,
      commit: () => {
        // A release issued while this candidate awaited paint belongs to the next
        // reading. Consume only the intents this candidate actually drew.
        for (const [key, token] of released)
          if (this.#released.get(key) === token) this.#released.delete(key);
        this.#known = keys;
        this.#shown = read ? shown : null;
      },
    };
  }

  // Which of the threads new to the seat it holds back.
  #arrive(prior, reading, row) {
    const arrived = reading.threads.filter(({ key }) => !this.#known.has(key));
    // A thread the user starts is their gesture, and the threads before it show with it.
    if (arrived.some(({ key }) => gestured(key))) this.#threads.clear();
    else if (arrived.length) {
      const last = prior.threads.at(-1)?.key;
      const after = last ? this.#view(last)?.node : this.#seat;
      const seen = readingIsContinuous() && Boolean(after) && growthAfterIsSeen(after);
      if (seen && (last || row)) for (const { key } of arrived) this.#threads.add(key);
      else this.#threads.clear();
    }
  }

  // Each thread as it stands, except one whose news would move what the reader reads,
  // which stands as it was drawn, its notice saying what waits, if anything but the
  // working message does.
  #draw(prior, reading) {
    this.#holds.clear();
    const drawn = new Map(prior?.threads.map((thread) => [thread.key, thread]));
    const threads = reading.threads
      .filter(({ key }) => !this.#threads.has(key))
      .map((thread) => {
        const was = drawn.get(thread.key);
        // A card the reading takes off the screen, or one already leaving it, shows
        // nothing for news to move.
        const shown = thread.visible !== false && !thread.folding;
        const held =
          was && shown && !this.#released.has(thread.key)
            ? threadChange(was, thread, {
                progressOpen: this.#view(thread.key)?.progressOpen ?? false,
              })
            : null;
        if (!held || gestured(thread.key) || !this.#view(thread.key)?.newsMoves(held))
          return { ...thread, news: null };
        this.#holds.add(thread.key);
        // What the news changes stands as drawn. A held reopening's notice stands
        // where Reopen did, since opening it is what reopening would show.
        const { news } = held;
        return {
          ...thread.reread(withheld(was.source, thread.source)),
          // Workflows and to-dos update in place, but the working message itself
          // keeps its drawn presence while its arrival or departure is held.
          working: news.working ? was.working : thread.working,
          ...(news.settled === "Reopened" && { settlement: null }),
          news,
        };
      });
    const waiting = this.#threads.size;
    const host = threads.at(-1);
    if (waiting && host) host.news = { ...host.news, threads: waiting };
    for (const thread of threads) {
      const notice = thread.news && said(thread.news);
      // News of the working message alone waits with no notice (the header).
      if (!notice?.parts.length) thread.news = null;
      else
        thread.news = {
          ...notice,
          reopened: thread.news.settled === "Reopened",
          open: () => {
            const node = this.#view(thread.key)?.node ?? null;
            showHeld(thread.id);
            if (thread === host && waiting) this.#open(thread.key, true);
            return node;
          },
        };
    }
    // A thread arriving with no thread drawn is held only where the seat drew its
    // first-message row, so its notice stands in that row's place.
    const news =
      waiting && !host
        ? {
            ...said({ threads: waiting }),
            reopened: false,
            open: () => this.#open(null, true),
          }
        : null;
    return Object.freeze({ ...reading, threads: Object.freeze(threads), news });
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

  // Shows the new threads the seat holds, where it holds the thread `id` among them.
  showThreads(id) {
    if (!this.#threads.has(this.#keys.get(id))) return false;
    this.#open(null, true);
    return true;
  }

  // Shows what one notice holds: a thread's news, and the seat's new threads where that
  // notice also says them. Returns the thread a keyboard on the notice lands on.
  #open(key, threads) {
    const first = threads && [...this.#threads][0];
    let changed = false;
    if (key && this.#holds.has(key) && !this.#released.has(key)) {
      this.#released.set(key, Symbol("release"));
      // A thread held while the user acts in it has a newer reading on its way, which
      // draws it as it stands; drawing the one held now would show a state that reading
      // replaces in the same task.
      changed = !gestured(key);
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
    for (const thread of this.#shown?.threads ?? [])
      this.#released.set(thread.key, Symbol("release"));
    this.#threads.clear();
  }

  #holding() {
    return Boolean(this.#threads.size || this.#holds.size);
  }

  // Whether the seat holds no news and owes no release, so a reading it has drawn would
  // draw the same again.
  get settled() {
    return !this.#holding() && !this.#released.size;
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
 *  `owner` is the widget, `region()` gives the nodes the reading draws, and `changed()`
 *  draws the widget again.
 *  A reading is a value equal to the one drawn last exactly when it draws at the same
 *  size, such as the keys of its rows. `hold(reading)` returns the reading to draw:
 *  `reading` where it is the first, where it equals the one drawn last, or where growth
 *  anywhere in the region would move nothing the user sees (geometry.js,
 *  `growthIsSeen`), since a row may change anywhere in it; otherwise the reading drawn
 *  last. What it holds shows when the user opens it (`release` or `show`), or once
 *  that growth would move nothing seen. The wait lasts while `owner` stands: a departure
 *  ends it and a return takes it up again, since a return draws nothing again. Current
 *  activation availability is not a retained presentation: callers refresh it
 *  from its current owner even while the reading holds. */
export class HeldReading {
  #region;
  #changed;
  #shown = null;
  #released = false;
  #watch = null;

  constructor(owner, region, changed) {
    this.#region = region;
    this.#changed = changed;
    // A held watch keeps its nodes while the owner is away, with no stop to call.
    watchOwner(owner, {
      connect: () => {
        if (this.#watch && !this.#watch.stop)
          this.#watch.stop = whenNone(this.#watch.nodes, growthIsSeen, this.show);
      },
      disconnect: () => {
        this.#watch?.stop?.();
        if (this.#watch) this.#watch.stop = null;
      },
    });
  }

  hold(reading) {
    // Preparation can draw partial authored contributions before the complete log
    // arrives. That is no baseline for news: the first ready reading stands whole.
    if (runtime.statePhase !== "ready") {
      this.#shown = null;
      this.#stop();
      return reading;
    }
    const nodes = this.#region();
    if (
      this.#released ||
      this.#shown === null ||
      this.#shown === reading ||
      !readingIsContinuous() ||
      !nodes.some((node) => growthIsSeen(node))
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
      this.#watch = { nodes, stop: whenNone(nodes, growthIsSeen, this.show) };
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
    this.#watch?.stop?.();
    this.#watch = null;
  }
}

/** The same rule for one box whose size no gesture of the reader's changes, such as a
 *  live sample's frame taking its child's height as the child arrives: `change()`
 *  applies the new size now where it would move nothing the reader sees, which it does
 *  before the page presents, while their reading is interrupted, or while growth
 *  anywhere in `node` is unseen (geometry.js, `growthIsSeen`). Otherwise `node` stands
 *  as drawn and the change waits until that growth would move nothing seen, or until
 *  the reading breaks, as a hidden tab breaks it. Returns a step that drops a waiting
 *  change. A gesture of the reader's into the box is theirs to move it: the owner,
 *  which knows what counts as one, drops the wait and applies the change itself, as a
 *  live sample does on input inside its child (lf-sample.js). */
export function heldGrowth(node, change) {
  if (!pagePresented() || !readingIsContinuous() || !growthIsSeen(node)) {
    change();
    return () => {};
  }
  let waiting = true;
  const stop = () => {
    if (!waiting) return;
    waiting = false;
    unwatch();
    uninterrupt();
  };
  const show = () => {
    stop();
    change();
  };
  const unwatch = whenNone([node], growthIsSeen, show);
  const uninterrupt = onReadingInterrupted(show);
  return stop;
}

/** The threads one widget holds out of its flow: each thread the agent starts at a datum
 *  where the widget draws no thread, while growth at the datum's foot would be seen
 *  (geometry.js, `growthAfterIsSeen`). `hold` says
 *  which threads the widget is not handed to place. The margin draws each as it draws
 *  a thread no widget places, and pressing its marker is opening the notice, which
 *  `show` answers. The margin draws a held thread's marker though the agent settled it,
 *  since the marker is its notice. A thread also shows when the user adds a turn to it,
 *  settles or reopens it, or starts a thread at its datum, and once growth anywhere in
 *  the datum would move nothing seen. */
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
    const read = runtime.statePhase === "ready";
    if (!read) this.#held.clear();
    else if (this.#known) this.#take(threads, drawn);
    this.#known = read ? new Set(all.map(({ key }) => key)) : null;
    this.#watch(threads);
    return new Set(this.#held.keys());
  }

  #take(threads, drawn) {
    if (!readingIsContinuous()) {
      this.#lapse(() => true);
      return;
    }
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
  // thread the user is in (`currentLocationNodes`), by focus or by a selection of its
  // words, in the margin's card, stays there with them, since its
  // release would take the card, and the reply they may be writing, away; it shows
  // when they press its marker, or the next time its datum's growth goes unseen.
  #lapse(which) {
    const currentLocation = new Set(
      currentLocationNodes().map((node) => closestAcross(node, THREAD)?.dataset.thread),
    );
    return this.#release((held) => which(held) && !currentLocation.has(held.id));
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
      this.#watching.set(datum, { node, stop: whenNone([node], growthIsSeen, leave) });
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
