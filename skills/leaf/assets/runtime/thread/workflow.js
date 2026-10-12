/* Canonical browser reading of one exact message workflow.

   Python binds accepted delivery, turn, response, activity and condition evidence to
   an input, and derives each thread's attention from them. It also serves which thread
   each workflow stands in (`thread`), whether it holds that thread the agent's turn
   (`holds_thread`), and the workflows strongest first (`served_workflows`). The
   application publisher adds the unresolved local send, with the attention it implies,
   after the served ones. Every message, compact thread row and margin entry reads
   these values; none reclassifies receipts, streams, turn ownership, whose turn a
   thread is, or which workflow is stronger. `strongestWorkflow` only places this tab's
   own sends against the served order. A workflow's word is `workflowLabel` and its face
   on a control `progressFace`, on every surface; a thread's word is `threadAttention`'s
   label, which Threads states as its status and the margin and Page Map as its line
   (`margin-model.js`, `threadMarks`). */

const STAGE_LABELS = Object.freeze({
  sending: "Sending",
  sent: "Sent",
  queued: "Queued",
  picked_up: "Picked up",
  working: "Working",
  replying: "Replying",
  answered: "Answered",
});

const CONDITION_LABELS = Object.freeze({
  ended: "Turn ended",
  interrupted: "Interrupted",
  stale: "Update stale",
  failed: "Failed",
});

const WAITING_FOR_PICKUP = "Waiting for pickup";
const NOT_ANSWERED = "Not answered";

export const workflowLabel = (workflow, { answered = false } = {}) => {
  if (!workflow) return "";
  if (workflow.condition)
    return workflow.condition.kind === "stale" &&
      workflow.condition.operation === "delivery"
      ? WAITING_FOR_PICKUP
      : workflow.condition.kind === "failed" &&
          workflow.condition.operation === "response"
        ? NOT_ANSWERED
        : (CONDITION_LABELS[workflow.condition.kind] ?? "Failed");
  if (workflow.stage === "answered" && !answered) return "";
  return STAGE_LABELS[workflow.stage] ?? "";
};

export const workflowTitle = (workflow) => {
  if (!workflow) return "";
  const label = workflowLabel(workflow, { answered: true });
  return [label, workflow.detail].filter(Boolean).join(" · ");
};

// The face a control paints for the agent's progress on a workflow: picked up, or at
// work, which a reply still streaming is too. Its word stays the workflow's own
// (`workflowLabel`), so a reply streaming reads Replying under the working face.
export const progressFace = (workflow) =>
  !workflow || workflow.condition
    ? null
    : workflow.stage === "picked_up"
      ? "picked_up"
      : ["working", "replying"].includes(workflow.stage)
        ? "working"
        : null;

export const isWorkflowProgress = (workflow) => progressFace(workflow) !== null;

export const isPageWidgetWorkflow = (workflow, revision) =>
  workflow.subject.kind === "widget" &&
  workflow.thread === null &&
  workflow.revision <= revision;

// A send this tab has not delivered is the only workflow at `sending`. It ranks below
// every served workflow with the same next actor, and an update that is the user's to
// make still ranks above every one that is the agent's.
const tier = (workflow) =>
  (workflow.next_actor === "user" ? 0 : 2) + Number(workflow.stage === "sending");

// The first of the strongest tier. `workflows` keeps the published order, served
// strongest first and this tab's sends after, so a caller selects by filtering it.
export function strongestWorkflow(workflows) {
  let strongest = null;
  for (const candidate of workflows)
    if (strongest === null || tier(candidate) < tier(strongest)) strongest = candidate;
  return strongest;
}

// An open to-do's word, wherever it stands: Working while a start runs on it.
export const todoLabel = (running) => (running ? "Working" : "To-do open");

export function threadAttention(thread) {
  if (thread.resolved) return null;
  const workflow = thread.attention?.workflow
    ? (thread.workflows.find(
        (candidate) => candidate.id === thread.attention.workflow,
      ) ?? null)
    : null;
  if (thread.attention?.kind === "needs_user") {
    const answering = thread.attention.reason === "ask";
    const nextMove = answering
      ? "answer"
      : workflow?.subject.kind === "thread"
        ? "resend"
        : "retry";
    const secondary = strongestWorkflow(
      thread.workflows.filter(
        (candidate) =>
          candidate.next_actor === "agent" &&
          candidate.holds_thread &&
          candidate.id !== workflow?.id,
      ),
    );
    return Object.freeze({
      kind: "needs_user",
      label: `On you to ${nextMove}`,
      workflow,
      secondary: [answering ? "" : workflowLabel(workflow), workflowLabel(secondary)]
        .filter(Boolean)
        .join(" · "),
    });
  }
  // A to-do the agent opened on the thread holds it after the update it answered has
  // settled; its title says what the agent still owes, and while a start runs on it,
  // that start's line says what the agent is doing about it.
  if (thread.attention?.kind === "waiting" && thread.attention.reason === "todo") {
    const { title, line } = thread.attention.todo;
    return Object.freeze({
      kind: "waiting",
      label: todoLabel(line),
      workflow: null,
      secondary: line ?? title,
    });
  }
  if (thread.attention?.kind === "waiting")
    return Object.freeze({
      kind: "waiting",
      label:
        workflowLabel(workflow) ||
        (thread.attention.reason === "uncertain" ? "Uncertain" : "Waiting"),
      workflow,
      secondary: "",
    });
  return null;
}
