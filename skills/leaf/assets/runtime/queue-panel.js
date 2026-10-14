/* The On panel: everything waiting on the user, On me (`queues.on_user`), or
   everything waiting on the agent, On <agent> (`queues.on_agent`), each with its own
   Done, on the right edge, where the Threads panel stands. Only one of the two is open
   at a time, so they are two views of one side panel, and their banner doors stand side
   by side (banner.js).

   The panel has no name of its own. Its head is two tabs, one per list, and the open
   one reads as its title; the list in view is that tab's open items, then, folded, its
   Done: what left that list (`served_state.queues`, by `owner`). Each door opens it on
   its own list, the agent's count beside the status on On <agent>, and every other way
   in, `g Shift+M` included, opens On me, the list `m` walks; a door pressed while the
   panel shows the other list turns it to the door's (drawers.js, `views`). Which tab is
   open is the panel's own view state, which the log never holds.

   On me holds asks, to-dos on the user and resends; On <agent> holds answers the agent
   owes, its work in hand and its to-dos. Each ask carries its source and answer; only a
   to-do on the user offers Done. This view renders the publisher's selections and
   never recreates asks from to-do rows.

   EXPERIMENTAL. Expect its groups, rows, wording and routes to change as the panel
   is used, and change them freely.

   The panel decides no membership. Its two lists are the application's one reading,
   `queues.on_user` and `queues.on_agent` (the server's `served_state.queues`, with this
   tab's sends placed against it), the same lists the `m` walk steps through and the
   banner counts; what is done is `done`, served beside them from ended to-dos,
   answered or withdrawn asks and the agent's sent replies. So a reply the user sends
   joins On <agent> in the turn it is sent, and leaves On me when the server's reading
   of it arrives, as the banner's counts do.

   Each row says what kind of item it is, the item's title or opening words, and where it
   is: the passage or section it stands at, and its age, stage or outcome. A press or
   Enter on a row arrives exactly as `m` does (`queue-walk.js`, `arriveAtItem`), so the
   panel and the walk cannot disagree about where an item is. An ask's row, and the row
   of a page widget action the user must send again, stands at that element
   (`declareSide`), so a walk or a comment from a focused row starts there. A row whose
   to-do the user ends with Done carries that Done (`queue-list.js`), the walk's own
   (`queue-api.js`, `done`).

   Its door in the banner says how many items wait on the user, and the agent's
   count beside the status sentence opens it too; `g Shift+M` is the key.

   Rows join, leave and change only while the panel is open, and the list holds its
   focus across them (focus.js, keyed `holdFocus`); a closed panel holds no rows. Its door
   stands on every page, as the Threads door does, so an item arriving or the last one
   leaving moves nothing on the banner: "On me: 0" opens a panel that says so. Before
   the log's first answer it says only "On me", since a count read from no log would
   be a claim. */
import {
  addressableLabel,
  addressableName,
  addressableWord,
} from "./addressable-names.js";
import {
  queueBtn,
  queueList,
  queueNextBtn,
  queueName,
  queuePanel,
  queueTabs,
  drawerIsOpen,
} from "./drawers.js";
import { markBannerControl } from "./banner-toolbar.js";
import { clocked, shortAgo } from "./presence.js";
import { elementById, inChrome } from "./passages.js";
import { PRESENTATION } from "./presentation.js";
import { standsAt } from "./queue-list.js";
import { itemNoun, itemOutcome } from "./queues.js";
import { registry } from "./registry.js";
import { repaint } from "./repaint.js";
import { keeps, keepsHidden, keepsText } from "./keeps.js";
import {
  agentName,
  applicationPresenter,
  failSoftAfterRetention,
  PRESENTATION_ORDER,
  PresentationRetentionError,
} from "./semantic-state.js";
import { renderedOrder, under } from "./shadow.js";
import { askEnding } from "./asks/answer.js";
import { readAsks } from "./asks/model.js";
import { askPlace } from "./asks/place.js";
import { readThreads } from "./thread/state.js";
import { readQueues, queueItemKey } from "./queue-api.js";
import { askHolding, declareSide } from "./standing-target.js";
import { anchorLabel } from "./thread/messages.js";
import { queueTitle } from "./queue-title.js";
import { threadSummary } from "./thread/model.js";
import { workflowLabel } from "./thread/workflow.js";
import { walkPositionLabel } from "./walk-position.js";

// A widget ask says its widget's word, or Ask; a prose ask says Thread; a to-do on
// either side says To-do. Response obligations keep their own Reply or Answer wording.
const WORDS = Object.freeze({
  ask: "Ask",
  resend: "Resend",
  answer: "Answer",
  reply: "Reply",
  work: "Work started",
  todo: "To-do",
});
const wordOf = (item, noun) => WORDS[noun];
const HEADINGS = "h1, h2, h3, h4, h5, h6";

function askWord(item) {
  const ask = item.ask;
  if (ask.source.kind === "reply") return "Thread";
  if (ask.source.kind === "approval") return "Approval";
  const word =
    registry[ask.source.tag]?.["x-word"] && addressableWord(askPlace(ask).source);
  return word ? word.charAt(0).toUpperCase() + word.slice(1) : "Ask";
}

// The section a page element stands in: the last heading before it whose parent also
// holds it, so a heading inside an earlier ask, or one closing an earlier section, is
// not this element's.
function sectionWords(element) {
  if (!element || inChrome(element)) return "";
  const heading = [...document.querySelectorAll(HEADINGS)].findLast(
    (candidate) =>
      !inChrome(candidate) &&
      candidate.parentElement &&
      under(element, candidate.parentElement) &&
      !under(candidate, element) &&
      renderedOrder(candidate, element) < 0,
  );
  const words = heading ? addressableLabel(heading) : "";
  return words ? `§ ${words}` : "";
}

export function createQueuePanel({ actions, next, announce, agentDoor }) {
  const reading = readQueues;
  const threadOf = (id) =>
    id === null
      ? null
      : (readThreads().threads.find((thread) => thread.id === id) ?? null);
  const agent = agentName;
  // The panel's door beside Threads, in the Threads door's face: its name and how many
  // items wait on the user, as that one says how many threads are open (banner.js).
  // Until the log has answered, the door claims no count, as the Threads door claims none.
  function nameDoor() {
    const count = reading().phase === "ready" ? reading().on_user.length : null;
    keepsText(queueBtn, count === null ? "On me" : `On me: ${count}`);
    keeps(queueBtn, "aria-label", count === null ? "On me" : `On me: ${count}`);
    keeps(queueBtn, "data-lf-key-title", `Show or hide what's on me and on ${agent()}`);
  }

  // Where an item is: the section its thread's passage or its own element stands in, or
  // the element the thread is about where that names itself, as a section does by its
  // heading. A thread about no element is about the whole page.
  function place(item, thread) {
    if (item.subject.kind === "page") return "Whole page";
    // A to-do on an element that names itself, as a section does by its heading, is
    // there.
    const itself =
      !thread && itemNoun(item) === "todo"
        ? addressableName(elementById(item.subject.id))
        : "";
    if (itself) return `§ ${itself}`;
    if (!thread) {
      // A widget answering an ask is where that ask is.
      const own = elementById(item.subject.id);
      const ask = own && askHolding(readAsks().all, own);
      return sectionWords(ask ? askPlace(ask).context : own);
    }
    if (!thread.anchor?.section) return "Whole page";
    const about = elementById(thread.anchor.section);
    const named = addressableName(about);
    return named ? `§ ${named}` : sectionWords(about) || anchorLabel(thread.anchor);
  }
  // The rest of where: how long it has stood or how far a reply has got, after the
  // place; and before it, how a finished item ended, which is what a Done row is for.
  function when(item, thread) {
    if (itemNoun(item) === "ask")
      return thread && shortAgo(threadSummary(thread).latest);
    // An update in hand says the line the agent last gave for it, as its thread's
    // working message does.
    const state = [workflowLabel(item.workflow), item.workflow?.detail];
    if (item.kind === "answer") return state.filter(Boolean).join(" · ");
    if (item.kind === "work")
      return [...state, shortAgo(item.workflow?.ts)].filter(Boolean).join(" · ");
    // A to-do the agent has in hand says the line its start gave, as an update in hand does.
    if (item.kind === "todo" && item.running)
      return [item.running.text, shortAgo(item.running.ts)].filter(Boolean).join(" · ");
    return "";
  }
  // An ask names how it ended, a to-do its outcome, and a reply that it was sent.
  function ended(item) {
    if (item.kind === "ask") return askEnding(item.ask);
    return [itemOutcome(item), shortAgo(item.ended)].filter(Boolean).join(" ");
  }
  function row(item, list) {
    const thread = threadOf(item.thread);
    const noun = itemNoun(item);
    const word = noun === "ask" ? askWord(item) : wordOf(item, noun);
    const where = (
      list === "done"
        ? [ended(item), place(item, thread)]
        : [place(item, thread), when(item, thread)]
    )
      .filter(Boolean)
      .join(" · ");
    const words = queueTitle(item);
    // The element a row stands at: an ask, or a page widget whose action the user must send
    // again. A reply the agent owes an update stands nowhere, so an ask's own row is the one
    // row standing at it.
    const at =
      noun === "ask" ||
      (item.kind === "resend" && item.subject.kind === "widget" && item.thread === null)
        ? item.kind === "ask"
          ? item.ask.id
          : item.subject.id
        : null;
    return Object.freeze({
      key: `${list}:${noun}:${item.id}`,
      item,
      list,
      at,
      kind: noun,
      word,
      title: words,
      where,
      live: item.live,
      // A to-do on the user that no widget answers ends at their Done, which its row
      // carries.
      done: item.offers.done,
      account: [word, words, where, list === "done" ? item.detail : ""]
        .filter(Boolean)
        .join(" · "),
    });
  }

  // The list in view, and which of the served lists and Done owners it reads. It goes
  // back to On me as the panel closes, so a door or a key opens it fresh.
  let tab = "you";
  let wasOpen = false;
  const LISTS = Object.freeze({
    you: Object.freeze({ items: "on_user", owner: "user" }),
    agent: Object.freeze({ items: "on_agent", owner: "agent" }),
  });
  const tabName = (id) => (id === "you" ? "On me" : `On ${agent()}`);
  const turnTo = (id) => {
    if (id === tab) return false;
    tab = id;
    void present();
    return true;
  };
  for (const [id, control] of Object.entries(queueTabs))
    control.onclick = () => turnTo(id);
  // Each door's list, the one it counts, for the drawer's doors (drawers.js).
  const tabOf = (door) => (door === agentDoor ? "agent" : "you");
  const views = Object.freeze({
    shows: (door) => tabOf(door) === tab,
    turn: (door) => turnTo(tabOf(door)),
  });
  // Each tab names its list and, once the log has answered, how many items wait on it;
  // the open one is pressed, and names the panel.
  function nameTabs() {
    const known = reading().phase === "ready";
    for (const [id, control] of Object.entries(queueTabs)) {
      const count = reading()[LISTS[id].items].length;
      keepsText(control, known ? `${tabName(id)} · ${count}` : tabName(id));
      keeps(control, "aria-pressed", String(id === tab));
    }
    keepsText(queueName, tabName(tab));
  }

  let rows = new Map();
  function readModel() {
    const open = drawerIsOpen("queue");
    if (!open) {
      rows = new Map();
      return Object.freeze({
        open,
        queue: Object.freeze({ id: tab, rows: Object.freeze([]), empty: "" }),
        done: Object.freeze({ label: "", rows: Object.freeze([]) }),
      });
    }
    const served = reading();
    // Before the log's first answer the panel, like its door, counts nothing, and says
    // so as the Threads panel does.
    const known = served.phase === "ready";
    const shown = served[LISTS[tab].items].map((item) => row(item, tab));
    const finished = served.done
      .filter((item) => item.owner === LISTS[tab].owner)
      .map((item) => row(item, "done"));
    rows = new Map([...shown, ...finished].map((entry) => [entry.key, entry]));
    return Object.freeze({
      open,
      queue: Object.freeze({
        id: tab,
        rows: Object.freeze(shown),
        empty: known
          ? `Nothing waiting on ${tab === "you" ? "me" : agent()}.`
          : "Loading…",
      }),
      done: Object.freeze({
        label: `Done · ${finished.length}`,
        rows: Object.freeze(finished),
      }),
    });
  }

  // Clock changes claim the same presenter as publications. Its scheduled paint
  // captures the new row ages, and owns their commit and retention on failure.
  const model = clocked(queueList, readModel, () => present());

  async function paintQueue(current) {
    const open = drawerIsOpen("queue");
    if (wasOpen && !open) tab = "you";
    wasOpen = open;
    nameDoor();
    nameTabs();
    const waiting = reading().on_user.length > 0;
    keepsHidden(queueNextBtn, !waiting);
    // On a phone the door waits in More, which says something is on the user as it says
    // an approval is open.
    markBannerControl(queueBtn, waiting ? "items on me" : null);
    repaint();
    const next = model();
    try {
      const painted = await queueList.present(next);
      if (!current()) return [];
      queueList.commit();
      return [painted];
    } catch (error) {
      if (!current()) return [];
      try {
        await queueList.retainCommitted();
      } catch (retaining) {
        throw new PresentationRetentionError(
          [error, retaining],
          "On panel presentation and retention failed",
        );
      }
      throw error;
    }
  }

  let mounted = false;
  const presenter = applicationPresenter({
    region: "queue",
    renderer: queueList,
    order: PRESENTATION_ORDER.queue,
    // The panel draws the queues, places each row by its thread or Question, and names
    // the agent; a publication that leaves those unchanged claims nothing.
    reading: (root) =>
      mounted
        ? {
            queues: root.effective.queues,
            threads: root.effective.thread.collection.threads,
            questions: root.effective.asks.all,
            agent: root.authoritative?.agent ?? null,
          }
        : null,
    failSoft: failSoftAfterRetention(queueList),
    paint: (epoch, current) => paintQueue(current),
  });
  const present = () => presenter.present();

  // A press on a row: the walk's own arrival, then where the row stands in its list.
  function goTo(key) {
    const entry = rows.get(key);
    if (!entry) return;
    const list = [...rows.values()].filter((other) => other.list === entry.list);
    const ready = actions.open(queueItemKey(entry.item)).then((arrived) => {
      if (!arrived) return;
      const qualifier =
        entry.list === "done"
          ? "done"
          : entry.list === "you"
            ? "waiting on me"
            : `waiting on ${agent()}`;
      announce(
        walkPositionLabel(entry.word, list.indexOf(entry) + 1, list.length, qualifier),
      );
    });
    void ready.catch(() => {});
  }
  // A Done on a row: the canonical Done command on that to-do (queue-api.js, `done`).
  function finish(key) {
    const entry = rows.get(key);
    if (entry?.done) actions.done(queueItemKey(entry.item));
  }
  queueList.configure({ activate: goTo, finish, fallback: queuePanel });
  queueNextBtn.onclick = () => next();

  // A row stands at the element it names rather than in the panel.
  declareSide((node) => {
    const at = standsAt(node);
    const ask = readAsks().all.find((ask) => ask.id === at);
    return ask ? askPlace(ask).node : at ? elementById(at) : null;
  });

  function mount() {
    if (mounted) return;
    mounted = true;
    void present();
    document.addEventListener(PRESENTATION, present);
  }

  return { mount, present, views };
}
