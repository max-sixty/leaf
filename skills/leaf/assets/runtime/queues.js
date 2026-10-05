/* What is on the user and what is on the agent: the browser's selection of
   `agent_state.queues` from its own reading.

   The two lists are the same selection `leaf page state` prints, made from the same
   four readings: the open Asks, each thread's `attention`, the workflows, and the open
   tasks. Python derives each of those; the application publisher has already folded
   this tab's unresolved sends into the threads' attention and the workflows, so a
   reply the user just sent takes its thread off their queue in the turn it is sent,
   and a refused one puts it back. Nothing here decides whose turn a thread is: a
   thread is on the user exactly when its attention says so (`awaitsUser`).

   `onYou` holds each open Ask (`ask`); then each other thread whose attention is the
   user's, once, as a question left in prose (`question`) or a move to send again
   (`recovery`); then each page widget move handed back to the user (`recovery`).
   `onAgent` holds each move the agent owes an answer (`answer`), each subject it has
   claimed work on with nothing owed (`work`), and each open task (`task`). An item
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
   folds at its foot (`queue-panel.js`): each answered Ask (`ask`), the Ask reading's
   whole inventory less those still unanswered, and each task a `task_end` ended
   (`task`), with its outcome. Python serves the ended tasks beside the open ones
   (`served_state.browser`), so nothing here folds the log again.

   Experimental: the queues, the walk over them and the panel listing them are new, and
   their shape is expected to change a lot (notes/what-needs-you/). Change them freely.
*/
import { awaitsUser } from "./thread/model.js";
import { atWork } from "./thread/workflow.js";

export function selectQueues({ asks, threads, workflows, tasks }) {
  const asked = new Set(asks.map((ask) => ask.thread));
  const onYou = asks.map((ask) => ({
    kind: "ask",
    id: ask.id,
    subject: { kind: "widget", id: ask.id },
    thread: ask.thread,
  }));
  for (const thread of threads)
    if (awaitsUser(thread) && !asked.has(thread.id))
      onYou.push({
        kind: thread.attention.reason === "ask" ? "question" : "recovery",
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
  for (const task of tasks)
    onAgent.push({
      kind: "task",
      id: task.id,
      subject: task.subject,
      thread: task.thread,
      title: task.title,
      agent: task.agent,
      session: task.session,
    });
  return { onYou, onAgent };
}

export function selectDone({ asks, tasks }) {
  const unanswered = new Set(asks.unanswered.map((ask) => ask.id));
  return [
    ...asks.all
      .filter((ask) => !unanswered.has(ask.id))
      .map((ask) => ({
        kind: "ask",
        id: ask.id,
        subject: { kind: "widget", id: ask.id },
        thread: ask.thread,
      })),
    ...tasks.map((task) => ({
      kind: "task",
      id: task.id,
      subject: task.subject,
      thread: task.thread,
      title: task.title,
      state: task.state,
      ended: task.outcome?.ts ?? null,
      detail: task.outcome?.detail ?? null,
    })),
  ];
}
