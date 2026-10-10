/* Queues select the canonical Questions, explicit Tasks and response workflows.
 * A Question is never synthesized as a Task. Its source owns its answer; only an
 * explicit user Task offers Done. Pending thread sends change attention through
 * the application publisher, while widget completion waits for admission. */
import { awaitsUser } from "./thread/model.js";
import { atWork } from "./thread/workflow.js";

export const endsByDone = (item) => item.ends === "done";
export const queueOffers = (item, ready, onYou) => ({
  open: ready,
  done: ready && onYou && item.kind === "task" && endsByDone(item),
});

export const taskNoun = (item) =>
  item.kind === "answer" && item.answer?.kind === "reply" ? "reply" : item.kind;

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
  ends: task.ends,
});

export const questionItem = (question) => ({
  kind: "question",
  id: question.id,
  owner: "user",
  subject: question.source.kind === "widget"
    ? { kind: "widget", id: question.source.id }
    : { kind: "thread", id: question.thread },
  thread: question.thread,
  title: question.prompt.text,
  running: null,
  agent: null,
  session: null,
  ends: question.source.kind === "widget" ? "widget" : "reply",
  question,
});

export function selectQueues({ threads, workflows, tasks, questions }) {
  const onYou = [
    ...(questions?.user ?? []).map(questionItem),
    ...tasks.filter((task) => task.owner === "user").map(taskItem),
  ];
  for (const thread of threads)
    if (awaitsUser(thread) && thread.attention.reason === "recovery")
      onYou.push({
        kind: "recovery",
        id: thread.id,
        subject: { kind: "thread", id: thread.id },
        thread: thread.id,
      });
  const onAgent = [];
  // A pending thread send replaces the served response obligation for that thread.
  const sending = (workflow) =>
    workflow.stage === "sending" && workflow.subject.kind === "thread";
  const resent = new Set(workflows.filter(sending).map(({ thread }) => thread));
  for (const workflow of workflows) {
    const item = { id: workflow.id, subject: workflow.subject, thread: workflow.thread };
    if (workflow.next_actor === "user") {
      if (workflow.thread === null) onYou.push({ kind: "recovery", ...item });
    } else if (
      sending(workflow) || (workflow.answer !== null && !resent.has(workflow.thread))
    )
      onAgent.push({ kind: "answer", ...item, answer: workflow.answer, stage: workflow.stage });
    else if (atWork(workflow))
      onAgent.push({ kind: "work", ...item, detail: workflow.detail });
  }
  onAgent.push(...tasks.filter((task) => task.owner === "agent").map(taskItem));
  return { onYou, onAgent };
}

export function selectDone({ tasks, questions }) {
  return [
    ...(questions?.all ?? []).filter((question) => question.status !== "open")
      .map((question) => ({
        ...questionItem(question),
        state: question.status === "answered" ? "done" : "dropped",
        ended: question.answer?.event?.ts ?? null,
        detail: null,
      })),
    ...tasks.map((task) => ({
      ...taskItem(task),
      state: task.state,
      ended: task.outcome?.ts ?? null,
      detail: task.outcome?.detail ?? null,
    })),
  ];
}
