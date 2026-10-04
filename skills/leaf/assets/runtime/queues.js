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
   selections must agree on. */
import { awaitsUser } from "./thread/model.js";

const atWork = (workflow) => ["working", "replying"].includes(workflow.stage);

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
  for (const workflow of workflows) {
    const item = {
      id: workflow.id,
      subject: workflow.subject,
      thread: workflow.thread,
    };
    // A move handed back in a thread is that thread's item above.
    if (workflow.next_actor === "user") {
      if (workflow.thread === null) onYou.push({ kind: "recovery", ...item });
    } else if (workflow.answer !== null)
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
