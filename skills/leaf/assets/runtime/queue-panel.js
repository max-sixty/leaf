/* The Queue panel: everything waiting on the user, everything waiting on the agent, and
   what is done, in one drawer on the left edge.

   EXPERIMENTAL. This is a first cut at the panel that replaced the Asks drawer, chosen
   to see how it does in use; expect its groups, rows, wording and routes to change a
   lot, and change them freely.

   The panel decides no membership. Its two queues are the application's one reading,
   `queues.onYou` and `queues.onAgent` (`queues.js`, the browser's side of
   `agent_state.queues`), the same lists the `a` walk steps through and the banner
   counts; what is done is `done`, selected beside them from the readings that already
   exist: the answered Asks and the tasks a `task_end` ended. So a reply the user sends
   leaves "On you" and joins the agent's queue in the turn it is sent, as it leaves the
   banner's count.

   Each row says what kind of item it is, the item's title or opening words, and where it
   is: the passage or section it stands at, and its age, stage or outcome. A press or
   Enter on a row arrives exactly as `a` does (`queue-walk.js`, `arriveAtItem`), so the
   panel and the walk cannot disagree about where an item is. An Ask's row, and the row
   of a page widget move the user must send again, stands at that element
   (`declareSide`), so a walk or a comment from a focused row starts there.

   The banner's queue counts open it, as do the Queue control in More (a finger's
   route) and `g Shift+Q`.

   Rows join, leave and change only while the panel is open, and the list holds its
   focus across them (`RowFocus`); a closed panel holds no rows. The panel is offered
   while any list has an item, or while it stands so its control can still close it. */
import {
  addressableLabel,
  addressableName,
  addressableWord,
} from "./anchor-resolution.js";
import {
  queueBtn,
  queueList,
  queueOffered,
  queuePanel,
  drawerIsOpen,
} from "./drawers.js";
import { showNews } from "./banner-toolbar.js";
import { paintKeys } from "./keyboard/scopes.js";
import { clocked, shortAgo } from "./presence.js";
import { elementById, inChrome } from "./passages.js";
import { PRESENTATION } from "./presentation.js";
import { standsAt } from "./queue-list.js";
import { repaint } from "./repaint.js";
import { keeps } from "./keeps.js";
import {
  agentName,
  applicationPresenter,
  failSoftAfterRetention,
  PRESENTATION_ORDER,
  PresentationRetentionError,
  readApplication,
  watchSemantic,
} from "./semantic-state.js";
import { under } from "./shadow.js";
import { askAnswers } from "./asks/answer.js";
import { allAsks } from "./asks/model.js";
import { askHolding, declareSide } from "./standing-target.js";
import { anchorLabel } from "./thread/messages.js";
import { threadSummary } from "./thread/model.js";
import { workflowLabel } from "./thread/workflow.js";
import { walkPositionLabel } from "./walk-position.js";

// The kind of item, in the row's apparatus voice. An Ask says what kind of thing is
// asking, in its widget's own word ("Deletion", "Options"), and "Ask" where its
// element is not built.
const WORDS = Object.freeze({
  ask: "Ask",
  question: "Question",
  recovery: "Resend",
  answer: "Reply",
  work: "Working",
  task: "Task",
});
const OUTCOMES = Object.freeze({ done: "Done", failed: "Failed", dropped: "Dropped" });
const HEADINGS = "h1, h2, h3, h4, h5, h6";
const capital = (words) => words.charAt(0).toUpperCase() + words.slice(1);

function askWord(item) {
  const word = addressableWord(elementById(item.id));
  return word ? capital(word) : WORDS.ask;
}

// The section a page element stands in: the last heading before it whose parent also
// holds it, so a heading inside an earlier Ask, or one closing an earlier section, is
// not this element's.
function sectionWords(element) {
  if (!element || inChrome(element)) return "";
  const heading = [...document.querySelectorAll(HEADINGS)].findLast(
    (candidate) =>
      !inChrome(candidate) &&
      candidate.parentElement &&
      under(element, candidate.parentElement) &&
      !under(candidate, element) &&
      candidate.compareDocumentPosition(element) & Node.DOCUMENT_POSITION_FOLLOWING,
  );
  const words = heading ? addressableLabel(heading) : "";
  return words ? `§ ${words}` : "";
}

export function createQueuePanel({ arriveAtItem, announce }) {
  const reading = () => readApplication().effective;
  const threadOf = (id) =>
    id === null
      ? null
      : (reading().thread.all.find((thread) => thread.id === id) ?? null);
  const workflowOf = (id) =>
    reading().workflows.find((workflow) => workflow.id === id) ?? null;
  const agent = agentName;
  // The control in More names the panel's sides as the panel does.
  const nameControl = () =>
    keeps(
      queueBtn,
      "data-lf-key-title",
      `Show or hide what is waiting on you and on ${agent()}`,
    );
  nameControl();

  // Where an item is: the section its thread's passage or its own element stands in, or
  // the element the thread is about where that names itself, as a section does by its
  // heading. A thread about no element is about the whole page.
  function place(item, thread) {
    if (!thread) {
      // A widget answering an Ask is where that Ask is.
      const own = elementById(item.subject.id);
      const ask = own && askHolding(allAsks(), own);
      return sectionWords(ask ? elementById(ask.id) : own);
    }
    if (!thread.anchor?.section) return "Whole page";
    const about = elementById(thread.anchor.section);
    const named = addressableName(about);
    return named ? `§ ${named}` : sectionWords(about) || anchorLabel(thread.anchor);
  }
  // A widget is named by the Ask it answers, where it answers one, as that Ask's own
  // row names it.
  function title(item, thread) {
    const own = elementById(item.subject.id);
    const topic = thread ? threadSummary(thread).topic : "";
    if (item.kind === "task") return item.title;
    if (item.kind === "work" && item.detail) return item.detail;
    if (item.subject.kind === "widget") {
      const ask = own && askHolding(allAsks(), own);
      return (
        (ask && addressableLabel(elementById(ask.id))) ||
        addressableLabel(own) ||
        topic ||
        item.id
      );
    }
    return topic || item.id;
  }
  // The rest of where: how long it has stood or how far a reply has got, after the
  // place; and before it, how a finished item ended, which is what a Done row is for.
  function when(item, thread) {
    if (item.kind === "question")
      return thread && shortAgo(threadSummary(thread).latest);
    if (item.kind === "answer") return workflowLabel(workflowOf(item.id));
    if (item.kind === "work") return shortAgo(workflowOf(item.id)?.ts);
    // A task the agent has in hand says the line its start gave, as a move in hand does.
    if (item.kind === "task" && item.running)
      return [item.running.text, shortAgo(item.running.ts)].filter(Boolean).join(" · ");
    return "";
  }
  function ended(item) {
    if (item.kind === "task")
      return [OUTCOMES[item.state] ?? item.state, shortAgo(item.ended)]
        .filter(Boolean)
        .join(" ");
    const ask = allAsks().find((candidate) => candidate.id === item.id);
    const answer = ask ? askAnswers([ask])[0] : "";
    return answer ? `Answered ${answer}` : "Answered";
  }
  function row(item, list) {
    const thread = threadOf(item.thread);
    const word = item.kind === "ask" ? askWord(item) : WORDS[item.kind];
    const where = (
      list === "done"
        ? [ended(item), place(item, thread)]
        : [place(item, thread), when(item, thread)]
    )
      .filter(Boolean)
      .join(" · ");
    const words = title(item, thread);
    // The element a row stands at: an Ask, or a page widget whose move the user must send
    // again. A reply the agent owes a move stands nowhere, so an Ask's own row is the one
    // row standing at it.
    const at =
      item.kind === "ask" ||
      (item.kind === "recovery" &&
        item.subject.kind === "widget" &&
        item.thread === null)
        ? item.subject.id
        : null;
    return Object.freeze({
      key: `${list}:${item.kind}:${item.id}`,
      item,
      list,
      at,
      kind: item.kind,
      word,
      title: words,
      where,
      live: item.kind === "work" || Boolean(item.running),
      account: [word, words, where, list === "done" ? item.detail : ""]
        .filter(Boolean)
        .join(" · "),
    });
  }

  let rows = new Map();
  function readModel() {
    const open = drawerIsOpen("queue");
    if (!open) {
      rows = new Map();
      return Object.freeze({
        open,
        queues: Object.freeze([]),
        done: Object.freeze({ label: "", rows: Object.freeze([]) }),
      });
    }
    const { queues, done } = reading();
    const you = queues.onYou.map((item) => row(item, "you"));
    const them = queues.onAgent.map((item) => row(item, "agent"));
    const finished = done.map((item) => row(item, "done"));
    rows = new Map([...you, ...them, ...finished].map((entry) => [entry.key, entry]));
    return Object.freeze({
      open,
      queues: Object.freeze([
        Object.freeze({
          id: "you",
          label: `On you · ${you.length}`,
          rows: Object.freeze(you),
          empty: "Nothing is waiting on you.",
        }),
        Object.freeze({
          id: "agent",
          label: `On ${agent()} · ${them.length}`,
          rows: Object.freeze(them),
          empty: `Nothing is waiting on ${agent()}.`,
        }),
      ]),
      done: Object.freeze({
        label: `Done · ${finished.length}`,
        rows: Object.freeze(finished),
      }),
    });
  }

  // The ages a row says move on the clock as well as on the log. A tick repaints the list
  // directly; a publication paints through the presenter below, which reads the model
  // inside this same clocked function so the clock knows which readings it made.
  let presenting = false;
  const model = clocked(queueList, () => {
    const next = readModel();
    if (!presenting)
      void queueList.paint(next).then(
        () => queueList.commit(),
        (error) => console.error("leaf: Queue panel tick failed", error),
      );
    return next;
  });

  let shortcutsOffered = false;
  async function paintQueue(current) {
    const offered = queueOffered();
    showNews(queueBtn, offered);
    nameControl();
    // The panel's rows and its control stand on this reading, so the surfaces reading
    // them are repainted where it is offered or withdrawn.
    if (offered !== shortcutsOffered) {
      shortcutsOffered = offered;
      paintKeys();
    } else repaint();
    presenting = true;
    let next;
    try {
      next = model();
    } finally {
      presenting = false;
    }
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
          "Queue presentation and retention failed",
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
    current: () => (mounted ? readApplication().semanticEpoch : null),
    failSoft: failSoftAfterRetention(queueList),
    paint: (epoch, current) => paintQueue(current),
  });
  const present = () => presenter.present();

  // A press on a row: the walk's own arrival, then where the row stands in its list.
  function goTo(key) {
    const entry = rows.get(key);
    if (!entry) return;
    const list = [...rows.values()].filter((other) => other.list === entry.list);
    const ready = arriveAtItem(entry.item).then((arrived) => {
      if (!arrived) return;
      const qualifier =
        entry.list === "done"
          ? "done"
          : entry.list === "you"
            ? "waiting on you"
            : `waiting on ${agent()}`;
      announce(
        walkPositionLabel(entry.word, list.indexOf(entry) + 1, list.length, qualifier),
      );
    });
    void ready.catch(() => {});
  }
  queueList.configure({ activate: goTo, fallback: queuePanel });

  // A row stands at the element it names rather than in the panel.
  declareSide((node) => {
    const at = standsAt(node);
    return at ? elementById(at) : null;
  });

  function mount() {
    if (mounted) return;
    mounted = true;
    watchSemantic(present);
    document.addEventListener(PRESENTATION, present);
  }

  return { mount, present };
}
