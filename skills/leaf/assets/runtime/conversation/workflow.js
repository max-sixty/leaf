/* Canonical browser reading of one exact message workflow.

   Python binds accepted delivery, turn, response, activity and condition evidence to
   an input, and derives each thread's attention from them. The application publisher
   adds the unresolved local send and the attention it implies. Every message, compact
   thread row and margin entry reads these values; none reclassifies receipts, streams,
   turn ownership, or whose turn a thread is. `strongestWorkflow` only chooses which of
   one surface's workflows it shows. */

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

export const workflowLabel = (workflow, { answered = false } = {}) => {
  if (!workflow) return "";
  if (workflow.condition)
    return workflow.condition.kind === "stale" &&
      workflow.condition.operation === "delivery"
      ? "Waiting for pickup"
      : workflow.condition.kind === "failed" &&
          workflow.condition.operation === "response"
        ? "Not answered"
        : (CONDITION_LABELS[workflow.condition.kind] ?? "Failed");
  if (workflow.stage === "answered" && !answered) return "";
  return STAGE_LABELS[workflow.stage] ?? "";
};

export const workflowTitle = (workflow) => {
  if (!workflow) return "";
  const label = workflowLabel(workflow, { answered: true });
  return [label, workflow.detail].filter(Boolean).join(" · ");
};

const stageRank = Object.freeze({
  answered: -1,
  sending: 0,
  sent: 1,
  queued: 2,
  picked_up: 3,
  working: 5,
  replying: 6,
});

export const isLiveWorkflow = (workflow) =>
  !workflow.condition && ["working", "replying"].includes(workflow.stage);

export const isWorkflowProgress = (workflow) =>
  !workflow.condition && ["picked_up", "working", "replying"].includes(workflow.stage);

export const isPageWidgetWorkflow = (workflow, revision) =>
  workflow.subject.kind === "widget" &&
  Boolean(workflow.coordinate) &&
  workflow.revision <= revision;

function compareWorkflows(left, right) {
  const nextActor =
    Number(right.next_actor === "user") - Number(left.next_actor === "user");
  if (nextActor) return nextActor;
  const liveDifference = Number(isLiveWorkflow(right)) - Number(isLiveWorkflow(left));
  if (liveDifference) return liveDifference;
  const condition = Number(Boolean(right.condition)) - Number(Boolean(left.condition));
  if (condition) return condition;
  const stage = (stageRank[right.stage] ?? -2) - (stageRank[left.stage] ?? -2);
  if (stage) return stage;
  const sequence = (right.seq ?? -1) - (left.seq ?? -1);
  if (sequence) return sequence;
  return String(right.id).localeCompare(String(left.id));
}

export function strongestWorkflow(workflows) {
  return workflows.reduce(
    (strongest, candidate) =>
      strongest === null || compareWorkflows(candidate, strongest) < 0
        ? candidate
        : strongest,
    null,
  );
}

export function threadAttention(thread) {
  if (thread.resolved) return null;
  const workflow = thread.attention?.workflow
    ? (thread.workflows.find(
        (candidate) => candidate.id === thread.attention.workflow,
      ) ?? null)
    : null;
  if (thread.attention?.kind === "needs_user") {
    const secondary = strongestWorkflow(
      thread.workflows.filter(
        (candidate) =>
          candidate.next_actor === "agent" && candidate.id !== workflow?.id,
      ),
    );
    return Object.freeze({
      kind: "needs_user",
      label:
        thread.attention.reason === "ask"
          ? "On you"
          : workflowLabel(workflow) || "Needs you",
      workflow,
      secondary: workflowLabel(secondary),
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
