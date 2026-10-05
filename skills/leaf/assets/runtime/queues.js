/* What is on the user and what is on the agent: the browser's selection of
   `agent_state.queues` from its own reading.

   The two lists are the same selection `leaf page state` prints, made from the same
   three readings: each thread's `attention`, the workflows, and the open tasks, on
   either side (`tasks.page_tasks`). Python derives each of those; the application
   publisher has already folded this tab's unresolved sends into the threads' attention,
   the workflows and the tasks, so a reply the user just sent takes its thread off their
   queue in the turn it is sent, and a refused one puts it back. Nothing here decides
   whose turn a thread is: a thread is on the user exactly when its attention says so
   (`awaitsUser`).

   `onYou` holds each open task on the user (`task`, `owner: "user"`): each Ask, each
   question a thread leaves them, and each task the agent put on them. A task the user
   is ending with Done, still unanswered by the server, has already left the open
   tasks (`application.ts`). An Ask leaves the
   queue while a thread in its widget's seat holds it with the agent
   (`ask.held_by_seat`), and a task on a thread while the thread waits on the agent.
   Then come each thread whose attention is the user's to send a move again
   (`recovery`), once, and each page widget move handed back to the user (`recovery`).
   `onAgent` holds each move the agent owes an answer (`answer`), each move it has in
   hand that owes nothing (`work`), and each open task of the agent's (`task`). An item
   has the fields Python's has. `tests/served_records.py` folds a reading both
   selections must agree on.

   One item is the browser's alone: a message this tab is still sending, whose thread
   its attention already hands to the agent, is an `answer` the agent will owe, with
   no answer named yet and the stage `sending`. So the reply leaves the user's count
   and joins the agent's in the same turn. In a thread the agent already owes, it takes
   the place of the served answer, since the server owes a thread one answer, to its
   latest move. A widget move still sending is not: until
   the server reads it, it is not known to owe anything, and an Ask it answers still
   stands open.

   `selectDone` is a third list beside them, what is finished, which the Queue panel
   folds at its foot (`queue-panel.js`): each task that has ended, an answered Ask's
   among them, with its outcome. Python serves the ended tasks beside the open ones
   (`served_state.browser`), so nothing here folds the log again.

   `taskNoun` is what an item is called, derived from how it ends rather than recorded:
   an Ask where a widget answers it, a question where the user answers in its thread,
   otherwise its kind. `endsByDone` is whether the user ends it with Done, which a task
   on them about an element or the page does, having no other way to end
   (`queue-walk.js`, `endTask`).

   Experimental: the queues, the walk over them and the panel listing them are new, and
   their shape is expected to change a lot (notes/what-needs-you/). Change them freely.
*/
import { awaitsUser } from "./thread/model.js";
import { atWork } from "./thread/workflow.js";

// Whether the user ends this item with Done: a task on them about an element or the
// page. An Ask's task ends when its widget answers it, and a question in a thread at
// their reply or a settling reaction.
export const endsByDone = (item) =>
  item.kind === "task" &&
  item.owner === "user" &&
  !item.ask &&
  item.subject.kind !== "thread";

export function taskNoun(item) {
  if (item.kind !== "task") return item.kind;
  if (item.ask) return "ask";
  return item.owner === "user" && item.subject.kind === "thread" ? "question" : "task";
}

const taskItem = (task) => ({
  kind: "task",
  id: task.id,
  owner: task.owner,
  subject: task.subject,
  thread: task.thread,
  title: task.title,
  running: task.running,
  agent: task.agent,
  session: task.session,
  ask: task.ask,
});

export function selectQueues({ threads, workflows, tasks }) {
  const attention = new Map(threads.map((thread) => [thread.id, thread.attention]));
  const onUser = (task) => {
    if (task.ask) return !task.ask.held_by_seat;
    if (task.subject.kind === "thread")
      return attention.get(task.subject.id)?.kind !== "waiting";
    return true;
  };
  const onYou = tasks
    .filter((task) => task.owner === "user" && onUser(task))
    .map(taskItem);
  for (const thread of threads)
    if (awaitsUser(thread) && thread.attention.reason === "recovery")
      onYou.push({
        kind: "recovery",
        id: thread.id,
        subject: { kind: "thread", id: thread.id },
        thread: thread.id,
      });
  const onAgent = [];
  // The server owes a thread one answer, to its latest move, so a message still being
  // sent in a thread stands for that thread's answer in place of the one served.
  const sending = (workflow) =>
    workflow.stage === "sending" && workflow.subject.kind === "thread";
  const resent = new Set(workflows.filter(sending).map(({ thread }) => thread));
  for (const workflow of workflows) {
    const item = {
      id: workflow.id,
      subject: workflow.subject,
      thread: workflow.thread,
    };
    // A move handed back in a thread is that thread's item above.
    if (workflow.next_actor === "user") {
      if (workflow.thread === null) onYou.push({ kind: "recovery", ...item });
    } else if (
      sending(workflow) ||
      (workflow.answer !== null && !resent.has(workflow.thread))
    )
      onAgent.push({
        kind: "answer",
        ...item,
        answer: workflow.answer,
        stage: workflow.stage,
      });
    else if (atWork(workflow))
      onAgent.push({ kind: "work", ...item, detail: workflow.detail });
  }
  onAgent.push(...tasks.filter((task) => task.owner === "agent").map(taskItem));
  return { onYou, onAgent };
}

export function selectDone({ tasks }) {
  return tasks.map((task) => ({
    kind: "task",
    id: task.id,
    owner: task.owner,
    subject: task.subject,
    thread: task.thread,
    title: task.title,
    state: task.state,
    ended: task.outcome?.ts ?? null,
    detail: task.outcome?.detail ?? null,
    ask: task.ask,
  }));
}
