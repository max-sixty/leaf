/* The Questions panel: everything waiting on the user, the Questions, then everything
   waiting on the agent, its Tasks, and what is done, on the right edge, where the
   Threads panel stands. Only one of the two is open at a time, so they are two views of
   one side panel, and their banner doors stand side by side (banner.js).

   Its queues combine canonical Questions, explicit tasks and delivery recovery.
   Each Question carries its source and answer; only an explicit user task offers
   Done. This view renders the publisher's selections and never recreates Questions
   from task rows.

   EXPERIMENTAL. Expect its groups, rows, wording and routes to change as the panel
   is used, and change them freely.

   The panel decides no membership. Its two queues are the application's one reading,
   `queues.onYou` and `queues.onAgent` (`queues.js`, the browser's side of
   `agent_state.queues`), the same lists the `q` walk steps through and the banner
   counts; what is done is `done`, selected beside them from ended tasks and answered
   or withdrawn Questions. So a reply the user sends
   leaves "On you" and joins the agent's queue in the turn it is sent, as it leaves the
   banner's count.

   Each row says what kind of item it is, the item's title or opening words, and where it
   is: the passage or section it stands at, and its age, stage or outcome. A press or
   Enter on a row arrives exactly as `q` does (`queue-walk.js`, `arriveAtItem`), so the
   panel and the walk cannot disagree about where an item is. A Question's row, and the row
   of a page widget move the user must send again, stands at that element
   (`declareSide`), so a walk or a comment from a focused row starts there. A row whose
   task the user ends with Done carries that Done (`queue-list.js`), the walk's own
   (`queue-api.js`, `done`).

   Its door in the banner says how many Questions wait on the user, and the agent's
   count beside the status sentence opens it too; `g Shift+Q` is the key.

   Rows join, leave and change only while the panel is open, and the list holds its
   focus across them (focus.js, keyed `holdFocus`); a closed panel holds no rows. Its door
   stands on every page, as the Threads door does, so a question arriving or the last one
   leaving moves nothing on the banner: "Questions: 0" opens a panel that says so. Before
   the log's first answer it says only "Questions", since a count read from no log would
   be a claim. */
import {
  addressableLabel,
  addressableName,
  addressableWord,
} from "./anchor-resolution.js";
import {
  queueBtn,
  queueList,
  queueNextBtn,
  queuePanel,
  drawerIsOpen,
} from "./drawers.js";
import { markBannerControl } from "./banner-toolbar.js";
import { clocked, shortAgo } from "./presence.js";
import { elementById, inChrome } from "./passages.js";
import { PRESENTATION } from "./presentation.js";
import { standsAt } from "./queue-list.js";
import { taskNoun } from "./queues.js";
import { registry } from "./registry.js";
import { repaint } from "./repaint.js";
import { keeps, keepsHidden, keepsText } from "./keeps.js";
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
import { questionWords } from "./questions/answer.js";
import { readQuestions } from "./questions/model.js";
import { questionPlace } from "./questions/place.js";
import { readThreads } from "./thread/state.js";
import { readQueues, queueItemKey } from "./queue-api.js";
import { questionHolding, declareSide } from "./standing-target.js";
import { anchorLabel } from "./thread/messages.js";
import { threadSummary } from "./thread/model.js";
import { workflowLabel } from "./thread/workflow.js";
import { walkPositionLabel } from "./walk-position.js";

// Widget requests say Question, prose requests say Thread, and explicit user tasks
// say To do. Response obligations keep their own Reply or Answer wording.
const WORDS = Object.freeze({
  question: "Question",
  recovery: "Resend",
  answer: "Answer",
  reply: "Reply",
  work: "Work started",
  task: "Task",
});
const wordOf = (item, noun) =>
  noun === "task" && item.owner === "user" ? "To do" : WORDS[noun];
const OUTCOMES = Object.freeze({ done: "Done", failed: "Failed", dropped: "Dropped" });
const HEADINGS = "h1, h2, h3, h4, h5, h6";

function questionWord(item) {
  const question = item.question;
  if (question.source.kind === "reply") return "Thread";
  const word = registry[question.source.tag]?.["x-word"] &&
    addressableWord(questionPlace(question).source);
  return word ? word.charAt(0).toUpperCase() + word.slice(1) : "Question";
}

// The section a page element stands in: the last heading before it whose parent also
// holds it, so a heading inside an earlier Question, or one closing an earlier section, is
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

export function createQueuePanel({ actions, next, announce }) {
  const reading = readQueues;
  const threadOf = (id) =>
    id === null
      ? null
      : (readThreads().threads.find((thread) => thread.id === id) ?? null);
  const agent = agentName;
  // The panel's door beside Threads, in the Threads door's face: its name and how many
  // Questions wait on the user, as that one says how many threads are open (banner.js).
  // Until the log has answered, the door claims no count, as the Threads door claims none.
  function nameDoor() {
    const count = reading().phase === "ready" ? reading().onYou.length : null;
    keepsText(queueBtn, count === null ? "Questions" : `Questions: ${count}`);
    keeps(
      queueBtn,
      "aria-label",
      count === null ? "Questions" : `Questions: ${count} waiting on you`,
    );
    keeps(
      queueBtn,
      "data-lf-key-title",
      `Show or hide your questions and ${agent()}'s tasks`,
    );
  }

  // Where an item is: the section its thread's passage or its own element stands in, or
  // the element the thread is about where that names itself, as a section does by its
  // heading. A thread about no element is about the whole page.
  function place(item, thread) {
    if (item.subject.kind === "page") return "Whole page";
    // A task on an element that names itself, as a section does by its heading, is
    // there.
    const itself =
      !thread && taskNoun(item) === "task"
        ? addressableName(elementById(item.subject.id))
        : "";
    if (itself) return `§ ${itself}`;
    if (!thread) {
      // A widget answering a Question is where that Question is.
      const own = elementById(item.subject.id);
      const question = own && questionHolding(readQuestions().all, own);
      return sectionWords(question ? questionPlace(question).context : own);
    }
    if (!thread.anchor?.section) return "Whole page";
    const about = elementById(thread.anchor.section);
    const named = addressableName(about);
    return named ? `§ ${named}` : sectionWords(about) || anchorLabel(thread.anchor);
  }
  // A widget is named by the Question it answers, where it answers one, as that Question's own
  // row names it.
  function title(item, thread) {
    const own = elementById(item.subject.id);
    const topic = thread ? threadSummary(thread).topic : "";
    if (item.title) return item.title;
    if (item.kind === "work" && item.detail) return item.detail;
    if (item.subject.kind === "widget") {
      const question = own && questionHolding(readQuestions().all, own);
      return (
        (question && addressableLabel(questionPlace(question).context)) ||
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
    if (taskNoun(item) === "question")
      return thread && shortAgo(threadSummary(thread).latest);
    if (item.kind === "answer") return workflowLabel(item.workflow);
    if (item.kind === "work")
      return [workflowLabel(item.workflow), shortAgo(item.workflow?.ts)]
        .filter(Boolean)
        .join(" · ");
    // A task the agent has in hand says the line its start gave, as a move in hand does.
    if (item.kind === "task" && item.running)
      return [item.running.text, shortAgo(item.running.ts)].filter(Boolean).join(" · ");
    return "";
  }
  // A Question names its canonical answer or withdrawal; an explicit task names its
  // outcome.
  function ended(item) {
    if (item.kind === "question") {
      if (item.question.status === "withdrawn") return "Withdrawn";
      const answer = questionWords(item.question);
      return answer ? `Answered ${answer}` : "Answered";
    }
    return [OUTCOMES[item.state] ?? item.state, shortAgo(item.ended)]
      .filter(Boolean)
      .join(" ");
  }
  function row(item, list) {
    const thread = threadOf(item.thread);
    const noun = taskNoun(item);
    const word = noun === "question" ? questionWord(item) : wordOf(item, noun);
    const where = (
      list === "done"
        ? [ended(item), place(item, thread)]
        : [place(item, thread), when(item, thread)]
    )
      .filter(Boolean)
      .join(" · ");
    const words = title(item, thread);
    // The element a row stands at: a Question, or a page widget whose move the user must send
    // again. A reply the agent owes a move stands nowhere, so a Question's own row is the one
    // row standing at it.
    const at =
      noun === "question" ||
      (item.kind === "recovery" &&
        item.subject.kind === "widget" &&
        item.thread === null)
        ? item.kind === "question" ? item.question.id : item.subject.id
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
      live: item.kind === "work" || Boolean(item.running),
      // A task on the user that no widget answers ends at their Done, which its row
      // carries.
      done: item.offers.done,
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
    const { onYou, onAgent, done } = reading();
    // Before the log's first answer the panel, like its door, counts nothing, and says
    // so as the Threads panel does.
    const known = Boolean(reading().phase === "ready");
    const you = onYou.map((item) => row(item, "you"));
    const them = onAgent.map((item) => row(item, "agent"));
    const finished = done.map((item) => row(item, "done"));
    rows = new Map([...you, ...them, ...finished].map((entry) => [entry.key, entry]));
    return Object.freeze({
      open,
      queues: Object.freeze([
        Object.freeze({
          id: "you",
          label: known ? `Questions · ${you.length}` : "Questions",
          rows: Object.freeze(you),
          empty: known ? "No questions for you." : "Loading current questions…",
        }),
        Object.freeze({
          id: "agent",
          label: known ? `Tasks · ${them.length}` : "Tasks",
          rows: Object.freeze(them),
          empty: known ? `${agent()} has no tasks.` : "Loading current tasks…",
        }),
      ]),
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
    nameDoor();
    const waiting = reading().onYou.length > 0;
    keepsHidden(queueNextBtn, !waiting);
    // On a phone the door waits in More, which says a question is there as it says an
    // approval is open.
    markBannerControl(queueBtn, waiting ? "questions waiting" : null);
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
          "Questions panel presentation and retention failed",
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
    const ready = actions.open(queueItemKey(entry.item)).then((arrived) => {
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
  // A Done on a row: the canonical Done command on that task (queue-api.js, `done`).
  function finish(key) {
    const entry = rows.get(key);
    if (entry?.done) actions.done(queueItemKey(entry.item));
  }
  queueList.configure({ activate: goTo, finish, fallback: queuePanel });
  queueNextBtn.onclick = () => next();

  // A row stands at the element it names rather than in the panel.
  declareSide((node) => {
    const at = standsAt(node);
    const question = readQuestions().all.find((question) => question.id === at);
    return question ? questionPlace(question).node : at ? elementById(at) : null;
  });

  function mount() {
    if (mounted) return;
    mounted = true;
    watchSemantic(present);
    document.addEventListener(PRESENTATION, present);
  }

  return { mount, present };
}
