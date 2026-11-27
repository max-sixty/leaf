/* News a thread surface holds back while it would move what the reader reads.

   These holds protect existing reading and active composition
   (`browser/AGENTS.md`, "Leaf's interface"). Each surface's rule below
   determines which surrounding content may move as messages arrive. A held change
   shows when a gesture takes the user to it. A hidden tab ends that reading. Returning reveals its held
   news and its first refreshed reading through the shared reading-continuity owner;
   keyboard blur alone leaves the reading protected. The ordinary message arrival
   tint and retirement fold explain the changed layout without withholding its words.

   A seat draws its threads in the page's flow (inline.js: a widget's seat, or a widget's
   outlet such as a diff line's), so whatever the agent adds to a thread grows the page
   there. A turn of the user's that this page did not just send, such as one from
   another tab, grows it the same way. Where that growth starts above the screen, the
   browser's scroll anchoring takes it into what the user has scrolled past; where it
   starts below, it moves nothing they see (dom/geometry.js, `motionBand`, says where that
   is). Where it starts on screen:

   - the thread the user is in, by focus or by a gesture of theirs still in flight
     (`gesturedOn`), draws what its news adds at once, as a chat does, and the seat
     keeps the control they are on still by scrolling what stands above it up by the
     growth (readings/user-place.js, `holdUserPlace`). That control is where the user
     is: a message they stand on stays and the reply box below it moves down by the
     turn; on the thread itself, as a send leaves them, its reply box stays. Where the
     page can't scroll by all of the growth, as when it is shorter than its window, the
     control moves by the rest. Its resolving or reopening waits as in the next case,
     with whatever arrives with it, since a settlement moves the thread between the
     seat's open threads and its Resolved disclosure, out from under the user;
   - any other thread drawn there keeps drawing what it drew, and says that news waits
     in its control row, the head row beside Resolve or Reopen, at a fixed size: its new
     turns, a reaction put on a reply or taken off it, a summary that comes or goes, and
     its resolving or reopening;
   - a thread not drawn yet draws at once, moving what follows it: one the agent starts
     in a seat or at a widget's datum, and one reopened out of a seat's closed Resolved
     disclosure. The user chose that over notices for these to wait
     behind: in the row the thread would follow, in place of the seat's first-message
     row, in the Resolved summary, and at the margin marker of a datum with no seat,
     which take a second hold for widgets out of what they are handed (surfaces.js).

   An open panel card shows appended messages immediately when no composition is
   active: its idle reply row and later cards may move, while existing messages keep
   their place. The margin's floating card is a seat whose growth moves the edge it
   does not hold, so news at the thread's end shows at once where that edge keeps still
   what the user is on, and waits otherwise (thread-preview.js, `endNewsMoves`);
   everything else waits, but a settlement, which keeps the editor it interrupts
   (thread-card.js, `newsMoves`). A reply the agent is still streaming at the thread's
   end is such an appended message, its words joining it as they come and its answer
   completing it in place, so it streams into an idle open card and a held one counts
   it once as a new reply. So is an answer ending the step before it where that
   step's face stands at the thread's end, as the agent's acknowledgement does. Ending
   a step above a user's later message changes earlier content and uses the ordinary
   reading hold. A step itself is no reply: it is the thread's working message while
   the work runs, not one of its replies (transcript.js). The
   working message's arrival, its departure, and a new step whose words wrap to
   another height change the thread's height, so a seat holds any change of its words
   when that growth would move the reader. Its notice doesn't say that change (the
   user's choice): progress never counts as unread, and the receipt on the
   user's message, such as "On it", already says the agent is working, so a red
   "1 new message" over a draft announces news the user owes nothing. Held alone, it
   shows by any route below but the notice. Rejected: counting each held step as
   "1 new message", and "Work in progress" or "Work
   changed" where the working message changes alone, which repeat that receipt.
   A step goes when the message that ended it shows. Changes to other existing
   messages, reactions, folds and settlement use the same hold as a seat in page flow,
   and a notice calls a changed message an edit.
   A closed card holds nothing, since its title row draws at one size whatever it says.
   A reply pinned to its scrollport lets a turn joining the thread's end grow up into
   the room scrolled past, though nothing that changes above that end. A held change leaves the controls it touches drawn as they
   were, and a press on one means what it drew (actions.js, `setReaction` and
   `settle`) and shows what the thread holds.

   `HeldNews` is that one owner for a seat. It reads every reading against the one it
   drew last, the only baseline: news is whatever the seat would draw differently, the
   notice says exactly that difference, and a reading back to what is drawn holds
   nothing. The gestures that show what a thread holds are the ones that take the user
   to it:

   - pressing its notice;
   - opening the thread: a panel card the list opens;
   - arriving at it: coming to stand in it from outside it, by a move of theirs, a t/T
     walk, an obligation, a link, Tab, whatever route took them (focus.js,
     `onCurrentLocation`). A press into it, such as into its reply box, puts the user in
     it, so what its news adds draws as in any thread they are in, the pressed control
     held still, though the margin's card keeps its own rule for that (inline.js), and a
     settlement still waits for its notice. Coming back
     to the thread they were in is a stay, whatever puts them there, as when the runtime
     puts back a reply box a surface stopped drawing, and so is a move within it;
   - acting in it (`gesturedOn`): a reply, a reaction on one of its messages, settling
     it, an action on a widget one of them holds or one that closes it, as accepting
     the suggestion it asked for does;
   - changing the panel's view, which moves its cards anyway.

   Held news also shows once growth anywhere in the seat would move nothing the user
   sees: none of it stands where a change of size moves what is seen (dom/geometry.js,
   `growthIsSeen`), as when it is scrolled under the chrome. Where a route's destination
   is itself held, a message or an obligation in a held turn, the route shows it first
   (`showHeld`), since nothing undrawn can take focus. Anything held in a seat is not
   drawn, so it stays unread until it shows.

   Decisions. An idle open panel card shows appended messages (the user's decision,
   over a blanket hold), and a streaming reply's words as they
   come (holding them as an edit leaves the agent's opening an empty bubble
   behind "1 new reply" until the user presses it), and an answer ending the step at
   the thread's end (the agent's first move is a progress acknowledgement, so holding
   that end holds nearly every answer). Everything above that step, the message the user
   is on and an active editor remain protected. Rejected: filling the list, which makes the
   open card as tall as the panel and leaves later cards below the fold; and letting a
   list that cannot scroll push its contents down, which needs the shift watch to stop
   checking such lists. Arrival is read from where the user is (the user's decision).
   Rejected: a `showHeld` call in each route that
   takes the user to a thread, which every new route had to remember and a route putting
   them back had to opt out of. The margin's floating card holds news that would move
   the reply the user writes (the user's decision), and its width never
   follows its words (comment-placement.js, `size-width`). Rejected: taking every change
   at once, which can widen it, carrying Resolve, Close and Send sideways, and raise it
   under a draft; keeping only its width, which can double the rise; keeping its
   box and scrolling the transcript, which scrolls Resolve away; and holding all news while it is open, which stops
   progress showing live where the user watches it. A presentation that makes room for
   the agent's answer to the user's last turn itself shows that answer at once, as the
   floating panel's thread view does (the user's decision, panel/floating-panel.js):
   held, the reply the user waits for stands unseen behind a small notice in their own
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
import { counted } from "../../lib/words.js";
import { growthIsSeen, whenNone } from "../../dom/geometry.js";
import { offerAction } from "../../lib/controls.js";
import { keeps, keepsText } from "../../lib/keeps.js";
import { keys } from "../../dom/keyboard/scopes.js";
import { focusThread } from "./focus.js";
import { isReaction, messageKey, turns } from "../../state/thread/model.js";
import { threadIdNamed, threadNamed, threadState } from "./state.js";
import { drawnThreadId, THREAD } from "./selectors.js";
import { runtime } from "../../state/context.js";
import { onCurrentLocation, focused } from "../../dom/focus.js";
import {
  onReadingInterrupted,
  readingIsContinuous,
} from "../../base/reading-continuity.js";
import { pagePresented } from "../../base/page-paint.js";
import { watchOwner } from "../../dom/arrivals.js";
import { holdUserPlace } from "../../readings/user-place.js";
import { closestAcross } from "../../lib/shadow-tree.js";
import { PRESS } from "../../lib/keys.js";
import type { ThreadReading, ThreadRecord } from "./thread-card.js";
import type { messageReading } from "./messages.js";

type MessageReading = ReturnType<typeof messageReading>;

// Whether this page's ledger holds a gesture of the user's on `thread`, of any kind, the
// refusal that takes one back included until the reading it restores is drawn: the
// application publisher says which thread each stands in (`thread.gestured`). Their
// words from another tab, or a turn a seat first draws after the log answered it, arrive
// like the agent's.
export const gesturedOn = (thread: { id: string }) =>
  threadState().gestured.includes(thread.id);

// Whether the user acts in the thread a seat draws under `key` (`gesturedOn`).
const gestured = (key: string | undefined) => {
  const thread = key === undefined ? null : threadNamed(key);
  return thread !== null && gesturedOn(thread);
};

// The reactions in force a strip draws, by emoji, since a reaction keeps its emoji but
// not its id when the log answers it.
const inForceEmoji = (reactions: NonNullable<MessageReading["reactions"]>) =>
  new Set(reactions.choices.filter(({ inForce }) => inForce).map(({ emoji }) => emoji));

// A summary as a card draws it: the messages of `drawn`, the ids of the turns the card
// draws, that it folds. A reaction reply it covers draws as a strip.
const fold = (
  summary: ThreadReading["summaries"][number],
  drawn: ReadonlySet<string>,
) => JSON.stringify([summary.id, summary.covers.filter((id) => drawn.has(id))]);

// The edit a message's words were last rewritten by, or null for words as first said.
const rewritten = (message: Pick<MessageReading, "base" | "id">) =>
  message.base === message.id ? null : message.base;

// How the seat would draw `message` differently in its words from `prior`, the same
// message as it drew it, or null where they stand as drawn:
// - "joined": a turn new to the thread, the agent's reply or a message of the user's
//   such as one from another tab, or words joining the reply still streaming, which a
//   provisional message stands for at the thread's end and which grows there as an
//   appended turn does;
// - "rewritten": words a new revision changed, an edit;
// - "grew": words that changed under the same revision, still that message arriving.
function messageChange(prior: MessageReading | undefined, message: MessageReading) {
  if (!prior) return "joined";
  const reworded = JSON.stringify(prior.body) !== JSON.stringify(message.body);
  if (prior.provisional) return reworded ? "joined" : null;
  if (!reworded) return null;
  return rewritten(prior) === rewritten(message) ? "grew" : "rewritten";
}

type ChangeReading = Pick<
  ThreadReading,
  "messages" | "resolved" | "working" | "summaries" | "source"
>;

// What of `now` the seat would draw differently from `was`, the thread as it drew it:
// each message's words (`messageChange`), each reaction put on a reply or taken off it,
// each summary that comes or goes, and the thread's settlement.
// `changed` the keys of the messages the news changes in place, every one where the
// settlement changes, which moves the thread's controls into or out of its head row and
// draws or folds its reaction strips; `folds` the keys of the messages a summary that
// comes or goes covers, and the ids of those that go, whose checkpoints a summary's
// change redraws from their tops. A step a new message ends, as the agent's answer
// ends the step before it, is that message's news, so the notice does not count it;
// one its turn ended is a change the notice says nothing of, as the working message's
// is. Where the step stood at the thread's foot (`footFold`) its end changes only that
// foot, as the answer's arrival does. `answers`
// names the user's turn and the first reply answering it (null while only work
// has arrived), when the user had the last turn as drawn: all of
// it, the reply, the work under way on it and that work's fold, lies after that turn,
// which a presentation may show at once (primary-reader.js, `answersAtOnce`). A message the log
// took back is no news: it goes. Null where nothing differs.
export function threadChange(was: ChangeReading, now: ChangeReading) {
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
    summaries: 0,
    appended: false,
  };
  const changed = new Set<string>();
  const arrived = new Set<string>();
  for (const message of now.messages) {
    const prior = drawn.get(message.key);
    const change = messageChange(prior, message);
    if (!prior || prior.provisional) arrived.add(message.id);
    // A step joins the thread as its working message, not as a reply, so it is the
    // working message's news (`news.working`), which the notice doesn't say.
    if (change === "joined" && message.progress) continue;
    if (change === "joined") {
      if (message.author === "agent") news.replies += 1;
      else news.messages += 1;
      news.appended = true;
    } else if (change === "grew" || change === "rewritten") {
      news[change === "grew" ? "replies" : "edits"] += 1;
      changed.add(message.key);
    } else if (settled) changed.add(message.key);
    else if (message.reactions && prior?.reactions) {
      const turned = inForceEmoji(prior.reactions).symmetricDifference(
        inForceEmoji(message.reactions),
      );
      news.reactions += turned.size;
      if (turned.size) changed.add(message.key);
    }
  }
  const summaries = (reading: ChangeReading) => {
    const ids = new Set(reading.messages.map(({ id }) => id));
    return new Map(reading.summaries.map((summary) => [fold(summary, ids), summary]));
  };
  const before = summaries(was);
  const after = summaries(now);
  const added = [...after].filter(([at]) => !before.has(at)).map(([, each]) => each);
  const gone = [...before].filter(([at]) => !after.has(at)).map(([, each]) => each);
  news.summaries = added.length || gone.length;
  // An ended step leaves the presentation, but stays in the source reading. The
  // message that ended it is the news, and a step its turn ended (`null`) goes as one
  // a message ended does; taking back a message by Undo remains no news.
  const visible = new Set(now.messages.map(({ id }) => id));
  const retired = new Set(
    now.source.msgs
      .filter(
        ({ completed_by }) =>
          completed_by === null ||
          (typeof completed_by === "string" && visible.has(completed_by)),
      )
      .map(({ key }) => key),
  );
  const removed = was.messages.filter(({ key }) => retired.has(key));
  const keys = new Map(
    [...was.messages, ...now.messages].map(({ id, key }) => [id, key]),
  );
  // Ending only the step at the foot changes the same foot as an arriving answer. A
  // step before a user's interjection also goes, so its old position participates in
  // the ordinary reading hold.
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
        covers.flatMap((id) => keys.get(id) ?? []),
      ),
    ],
    summaries: gone.map(({ id }) => id),
  };
  const counts: (keyof typeof news)[] = [
    "working",
    "replies",
    "messages",
    "edits",
    "reactions",
    "summaries",
  ];
  if (!settled && !removed.length && counts.every((count) => !news[count])) return null;
  const appendedAtEnd =
    news.appended &&
    was.messages
      .filter(({ key }) => !retired.has(key))
      .every((message, index) => now.messages[index]?.key === message.key);
  const turn = was.messages.findLastIndex(
    (message) => message.author === "user" && !message.progress,
  );
  const previousTurn = was.messages[turn];
  const asked = new Set(was.messages.slice(0, turn + 1).map(({ key }) => key));
  const currentTurn = now.messages.findIndex(
    (message) => message.key === was.messages[turn]?.key,
  );
  const answering =
    previousTurn !== undefined &&
    currentTurn >= 0 &&
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
  const answers = answering
    ? Object.freeze({
        turn: previousTurn.key,
        reply:
          now.messages.slice(currentTurn + 1).find((message) => !message.progress)
            ?.key ?? null,
      })
    : null;
  return { news, changed, folds, appendedAtEnd, footFold, answers };
}

// The thread `now` with what `was`, the thread as the seat drew it, did not show held
// back: what the log's news changed, as drawn. That is its settlement; its messages, the
// new ones left out, a reaction taken off or a streaming reply gone still present, and
// each one's words or mark as drawn, which only an edit, an undo of a reaction or a
// stream changes; and its summaries as drawn. A held thread is read from this as from
// any other, so what the reading derives from those, such as its title, its reaction
// strips or its controls, agrees with what it draws. A message with words the user took
// back in another tab is no news: it reads Deleted, or goes, at once.
// Whose turn it is and each message's delivery read as they stand, as the server
// derives them: they change the title's status and a message's head row in place, as
// in a thread that holds nothing, so a resolution held from the card already takes its
// turn off the title.
function withheld(was: ThreadRecord, now: ThreadRecord) {
  const current = new Map(now.msgs.map((message) => [messageKey(message), message]));
  // How the drawn reading ended each message held from it, by the held message.
  const drawnEnd = new Map<object, string | null | undefined>();
  const msgs = was.msgs.flatMap((prior) => {
    const message = current.get(messageKey(prior));
    if (!message) return isReaction(prior) || prior.provisional ? [prior] : [];
    // A reaction taken back while something stands on it is still the mark drawn.
    if (isReaction(prior) && !isReaction(message)) return [prior];
    // A streaming reply held as drawn is still the reply arriving, whatever completed it.
    // Its content version is the one its drawn words are, so the words a rewrite holds
    // back are neither marked read nor taken for the rewrite.
    const { text, body, edited, content_version, provisional, reactions } = prior;
    const held = {
      ...message,
      text,
      body,
      edited,
      content_version,
      provisional,
      reactions,
    };
    drawnEnd.set(held, prior.completed_by);
    return [held];
  });
  // A step stands as drawn: one the drawn reading ended, by its turn or by a message
  // this one shows, stays ended, as a stream held after its failure receipt replaced
  // it still ends the step before it, and one its turn ended since stands until the
  // news shows. A step a message held here ends stands too, as that message waits.
  const shown = new Set(msgs.map(({ id }) => id));
  const held = msgs.map((message) => {
    const ended = drawnEnd.get(message);
    return Object.freeze(
      ended === null ||
        (ended !== undefined && shown.has(ended)) ||
        (drawnEnd.has(message) && message.completed_by === null)
        ? { ...message, completed_by: ended }
        : message,
    );
  });
  const root =
    held.find((message) => messageKey(message) === messageKey(now.root)) ?? now.root;
  return Object.freeze({
    ...now,
    root,
    resolved: was.resolved,
    msgs: Object.freeze(held),
    turns: Object.freeze(turns({ msgs: held, root })),
    summaries: was.summaries,
  });
}

const newsParts = ({
  settled,
  replies,
  messages,
  edits,
  reactions,
  summaries,
}: ThreadChange["news"]) =>
  [
    settled,
    replies && counted(replies, "new reply", "new replies"),
    messages && counted(messages, "new message"),
    edits && counted(edits, "message edited", "messages edited"),
    reactions && counted(reactions, "reaction changed", "reactions changed"),
    summaries && counted(summaries, "summary changed", "summaries changed"),
  ].flatMap((part) => (typeof part === "string" && part.length > 0 ? [part] : []));

// How a notice says that things wait: one count of them all ("2 new"), a settling
// counting as one, on every surface that says news is held, Threads' notice of
// joining rows included.
export const newsCount = (total: number) => `${total} new`;

// The room a card holds for its notice's count: the widest count it says, in two
// figures of one width (`button.lf-thread-news`, surfaces.css), so a count past 99
// is cut.
export const NEWS_ROOM = newsCount(99);

// What a notice says: the count (`text`), and each fact of the news, most telling
// first, as the line its title, and so its accessible description, reads (`label`).
// Null where only the working message changed, which waits with no notice (the header).
const said = (news: ThreadChange["news"]) => {
  const { settled, replies, messages, edits, reactions, summaries } = news;
  const total = (settled ? 1 : 0) + replies + messages + edits + reactions + summaries;
  return total ? { text: newsCount(total), label: newsParts(news).join(" · ") } : null;
};

export type NewsNotice = { text: string; label: string; open: () => Element | null };

/** The control that says what a row holds and shows it. `set(news)` gives it the
 *  reading's `news` ({text, label, open}); `open` returns the thread to land a
 *  keyboard on, since the notice goes with what it held. It is an inline press that
 *  announces news waiting (`data-lf-news`, controls.css), in the accent the unread dot
 *  wears. It says one count of all
 *  that waits, "2 new", in every placement, which is its accessible name too, so a
 *  voice user saying the words they see reaches it; its preview says each fact, "1 new
 *  reply · 1 new message", and a screen reader hears that as its description while it
 *  stands on focus (annotations/preview.js). A name of the facts
 *  alone matches nothing the user sees. The user chose this over a line
 *  of facts that drops those past its room and counts them at its end ("1 new reply
 *  +1"), and says "2 new" only where even the first fact doesn't fit, so one piece of
 *  news reads three ways, in the danger ink an error wears. The words have a span of
 *  their own, so a card that holds the notice's room (`data-lf-room`, controls.css)
 *  keeps it at the width of the widest count it says (`NEWS_ROOM`). */
export function newsNotice() {
  const node = offerAction("inline", "lf-thread-news");
  keeps(node, "data-lf-news", "");
  const words = document.createElement("span");
  // The news is Leaf's, so the words wear Leaf's voice, as the panel's field does a
  // reading all Leaf says (base/voice.js).
  words.dataset.lfVoice = "leaf";
  node.append(words);
  let open: () => Element | null = () => null;
  // Its whole label, under the count it shows, is what the preview reads (annotations/preview.js).
  let label = "";
  node.lfPreview = () => (label ? { detail: [label] } : null);
  // A key on the notice, which stands the user on it, lands them on the thread, since
  // the notice goes with what it held. A pointer's press takes no focus itself, and
  // its owner's `open` decides where the press lands: a thread's leaves the user where
  // they stand, so a reply being written keeps its caret rather than the press taking
  // it out of the box.
  node.addEventListener("mousedown", (event) => event.preventDefault());
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
    set(news: NewsNotice) {
      keepsText(words, news.text);
      label = news.label;
      open = news.open;
    },
  };
}

// Every live seat's HeldNews, so an arrival can show what any of them holds of its
// thread.
const holders = new Set<HeldNews>();

/** Shows what every seat holds of the thread `id` names, a message's id naming its
 *  thread: an arrival at it, or a route whose destination it holds. Each seat draws
 *  what it released before this returns. Returns whether any seat held anything of it. */
export function showHeld(id: string) {
  const thread = threadIdNamed(id);
  let shown = false;
  for (const held of holders) shown = held.show(thread) || shown;
  return shown;
}

// The thread the user is in, and their arrivals at another. A move or a step there shows
// what it holds. A press there puts the user in it, so each seat holding it draws again
// and the seat's rule for a user in it decides (inline.js). No reading brings either
// draw, so an arrival on a control in the thread, as a press into its reply box or a Tab
// into its reply row, takes the hold a reading takes, which keeps that control where it
// stood (readings/user-place.js, `holdUserPlace`). An arrival on the thread itself, by a walk or
// a press on one of its messages, takes none: the hold would keep its reply box still,
// as it does for a user standing on the thread when news comes, and so move what they
// arrived on up by the news, where the growth below the thread's head leaves it put.
let currentLocation: string | null = null;
onCurrentLocation((node: Node | null, cause: string) => {
  // A drop leaves them in the thread, for its owner to put them back in.
  if (cause === "drop") return;
  const thread = node && closestAcross(node, THREAD);
  const id = drawnThreadId(thread);
  const arrived = id !== null && id !== currentLocation;
  currentLocation = id;
  if (!arrived || cause === "return") return;
  const keep = node === thread ? () => {} : holdUserPlace();
  if (cause === "press") for (const held of holders) held.redraw(id);
  else showHeld(id);
  keep();
});

export type ThreadChange = NonNullable<ReturnType<typeof threadChange>>;
type DrawableThread = ThreadReading & { visible?: boolean; folding?: boolean };
export type HeldThread = Omit<DrawableThread, "settlement"> & {
  settlement: ThreadReading["settlement"] | null;
  news: NewsNotice | null;
};
type HeldCollection = { threads: readonly HeldThread[] };
type NewsView = { node: Element; newsMoves: (change: ThreadChange) => boolean };

export class HeldNews {
  #seat;
  #view;
  #changed;
  // The reading last drawn, the one each reading is read against; the threads it draws
  // holding news; the threads whose news the user asked to see, which the next reading
  // draws as they stand; and each thread's key by its id.
  #shown: HeldCollection | null = null;
  #holds: Set<string> = new Set();
  #released: Map<string, symbol> = new Map();
  #keys: Map<string, string> = new Map();
  #stopWatching: (() => void) | null = null;

  // `view(key)` is the seat's ThreadView for a thread; `changed()` draws the seat again
  // from the reading it holds.
  constructor(
    seat: Element,
    view: (key: string) => NewsView | null,
    changed: () => void,
  ) {
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
  // either.
  hold<R extends { threads: readonly DrawableThread[] }>(reading: R) {
    const candidate = this.prepare(reading);
    candidate.commit();
    return candidate.reading;
  }

  // Required presenters prepare before yielding to package layout. Only the
  // candidate actually painted becomes the baseline for the next comparison.
  prepare<R extends { threads: readonly DrawableThread[] }>(reading: R) {
    const read = runtime.statePhase === "ready";
    if (!read || !readingIsContinuous()) this.#forget();
    const prior = read ? this.#shown : null;
    this.#keys = new Map(reading.threads.map(({ id, key }) => [id, key]));
    const shown = this.#draw(prior, reading);
    const released = new Map(this.#released);
    // Waiting for all of the seat to go keeps news held a little longer than it needs,
    // never shorter.
    if (this.#holds.size)
      this.#stopWatching ??= whenNone([this.#seat], growthIsSeen, this.#all);
    else this.#stop();
    return {
      reading: shown,
      commit: () => {
        // A release issued while this candidate awaited paint belongs to the next
        // reading. Consume only the intents this candidate actually drew.
        for (const [key, token] of released)
          if (this.#released.get(key) === token) this.#released.delete(key);
        this.#shown = read ? shown : null;
      },
    };
  }

  // Each thread as it stands, except one whose news would move what the reader reads,
  // which stands as it was drawn, its notice saying what waits, if anything but the
  // working message does.
  #draw<R extends { threads: readonly DrawableThread[] }>(
    prior: HeldCollection | null,
    reading: R,
  ): Omit<R, "threads"> & HeldCollection {
    this.#holds.clear();
    const drawn = new Map(prior?.threads.map((thread) => [thread.key, thread]));
    const threads = reading.threads.map((thread): HeldThread => {
      const was = drawn.get(thread.key);
      // A card the reading takes off the screen, or one already leaving it, shows
      // nothing for news to move.
      const shown = thread.visible !== false && !thread.folding;
      if (!was || !shown || this.#released.has(thread.key))
        return { ...thread, news: null };
      const view = this.#view(thread.key);
      const held = threadChange(was, thread);
      if (!held || gestured(thread.key) || !view?.newsMoves(held))
        return { ...thread, news: null };
      this.#holds.add(thread.key);
      const notice = said(held.news);
      // What the news changes stands as drawn.
      return {
        ...thread.reread(withheld(was.source, thread.source)),
        // Workflows and to-dos update in place, but the working message itself
        // keeps its drawn presence while its arrival or departure is held.
        working: held.news.working ? was.working : thread.working,
        news: notice
          ? {
              ...notice,
              open: () => {
                showHeld(thread.id);
                return this.#view(thread.key)?.node ?? null;
              },
            }
          : null,
      };
    });
    return Object.freeze({ ...reading, threads: Object.freeze(threads) });
  }

  // Shows what the seat holds of the thread `id`.
  show(id: string) {
    const key = this.#keys.get(id);
    if (key === undefined || !this.#holds.has(key)) return false;
    if (this.#released.has(key)) return true;
    this.#released.set(key, Symbol("release"));
    // A thread held while the user acts in it has a newer reading on its way, which
    // draws it as it stands; drawing the one held now would show a state that reading
    // replaces in the same task.
    if (!gestured(key)) this.#changed();
    return true;
  }

  // Draws the seat again where it holds the thread `id`, so the thread's rule for a
  // user now in it decides.
  redraw(id: string) {
    const key = this.#keys.get(id);
    if (key !== undefined && this.#holds.has(key)) this.#changed();
  }

  // The next reading draws every thread as it stands, as when the user changes what
  // the surface shows, which moves its threads anyway.
  release() {
    this.#forget();
  }

  #all = () => {
    if (!this.#holds.size) return;
    this.#forget();
    this.#changed();
  };

  // Every thread the seat holds shows on the next reading.
  #forget() {
    for (const thread of this.#shown?.threads ?? [])
      this.#released.set(thread.key, Symbol("release"));
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

// Each owner's held readings, for `showHeldReadings`.
const heldBy = new WeakMap<Element, Set<HeldReading<unknown>>>();

/** Show what every reading `owner` holds: the reader asked to see the change, as
 *  `show` does for one reading. */
export function showHeldReadings(owner: Element) {
  for (const reading of heldBy.get(owner) ?? []) reading.show();
}

/** One region's reading, held while drawing it would move what the reader sees.
 *  `owner` is the widget, `region()` gives the nodes the reading draws, and `changed()`
 *  draws the widget again.
 *  A reading is a value equal to the one drawn last exactly when it draws at the same
 *  size, such as the keys of its rows. `hold(reading)` returns the reading to draw:
 *  `reading` where it is the first, where it equals the one drawn last, or where growth
 *  anywhere in the region would move nothing the user sees (dom/geometry.js,
 *  `growthIsSeen`), since a row may change anywhere in it; otherwise the reading drawn
 *  last. What it holds shows when the user opens it (`release` or `show`), or once
 *  that growth would move nothing seen. The wait lasts while `owner` stands: a departure
 *  ends it and a return takes it up again, since a return draws nothing again. Current
 *  activation availability is not a retained presentation: callers refresh it
 *  from its current owner even while the reading holds. */
export class HeldReading<T> {
  #region;
  #changed;
  #shown: T | null = null;
  #released = false;
  #watch: { nodes: readonly Element[]; stop: (() => void) | null } | null = null;

  constructor(owner: Element, region: () => readonly Element[], changed: () => void) {
    this.#region = region;
    this.#changed = changed;
    let held = heldBy.get(owner);
    if (!held) heldBy.set(owner, (held = new Set()));
    held.add(this);
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

  hold(reading: T): T {
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
 *  anywhere in `node` is unseen (dom/geometry.js, `growthIsSeen`). Otherwise `node` stands
 *  as drawn and the change waits until that growth would move nothing seen, or until
 *  the reading breaks, as a hidden tab breaks it. Returns a step that drops a waiting
 *  change. A gesture of the reader's into the box is theirs to move it: the owner,
 *  which knows what counts as one, drops the wait and applies the change itself, as a
 *  live sample's host does on a click or key inside its child (host/sample.js). */
export function heldGrowth(node: Element, change: () => void) {
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
