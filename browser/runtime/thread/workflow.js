/* Canonical browser reading of one exact message workflow.

   Python binds accepted delivery, turn, response, activity and condition evidence to
   an input, names the obligation record each serves (`obligation`), and derives each
   thread's attention from the records open in it. It also serves which thread each
   workflow stands in (`thread`) and the workflows strongest first (`served_workflows`).
   The application publisher adds the unresolved local send after the served ones; only
   a thread the user opened takes its attention from it. Every message, compact thread row and margin entry reads
   these values; none reclassifies receipts, streams, turn ownership, whose turn a
   thread is, or which workflow is stronger. `strongestWorkflow` only places this tab's
   own sends against the served order. A workflow's word is `workflowLabel`, its last
   step's line `workflowStep`, and its face on a control `progressFace`, on every
   surface; a thread's word is `threadAttention`'s label, which Threads states as its
   status and the margin and Page Map as its line (`margin-model.js`, `threadMarks`). */

// Each stage as the agent would say it (glossary.md, "Reader-facing words"). Until the
// agent has the update in a turn or its harness's queue, all it can say is that it
// hasn't seen it, whether or not the server has logged it yet: the message drawn in
// the thread already shows the user's own gesture, and the page's status says when a
// send isn't getting through.
const STAGE_LABELS = Object.freeze({
  sending: "Not seen yet",
  sent: "Not seen yet",
  queued: "Up next",
  picked_up: "Got it",
  working: "On it",
  replying: "Replying",
  answered: "Answered",
});

const CONDITION_LABELS = Object.freeze({
  ended: "Stopped",
  interrupted: "Interrupted",
  stale: "Gone quiet",
  failed: "Failed",
});

// An update still unseen past the pickup grace (`activity.PICKUP_GRACE`).
const WAITING_FOR_DELIVERY = "Still not seen";
// A failed response's word, on its workflow and on the failure reply that reports it.
export const NOT_ANSWERED = "Couldn't answer";

export const workflowLabel = (workflow, { answered = false } = {}) => {
  if (!workflow) return "";
  if (workflow.condition)
    return workflow.condition.kind === "stale" &&
      workflow.condition.operation === "delivery"
      ? WAITING_FOR_DELIVERY
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

// The face a control paints for the agent's progress on a workflow: delivered, or at
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

// What the agent's last step on a workflow says while it is at work on it: the line of
// the start or progress reply that holds it (`detail`), which the page's status says of
// the newest it holds. Before it says one, and once the work stalls, the workflow's word.
export const workflowStep = (workflow) =>
  (progressFace(workflow) === "working" && workflow.detail) || workflowLabel(workflow);

export const isPageWidgetWorkflow = (workflow, revision) =>
  workflow.subject.kind === "widget" &&
  workflow.thread === null &&
  workflow.revision <= revision;

// Whether a workflow's update is back with the user to send again: a served one the
// harness gave up on keeps its failed response at `answered`, the one stage only that
// reaches, and this tab's refused send failed its delivery.
const handedBack = (workflow) =>
  workflow.stage === "answered" ||
  (workflow.stage === "sending" && workflow.condition?.kind === "failed");

// A send this tab has not delivered is the only workflow at `sending`. It ranks below
// every served workflow with the same next actor, and an update that is the user's to
// make still ranks above every one that is the agent's.
const tier = (workflow) =>
  (handedBack(workflow) ? 0 : 2) + Number(workflow.stage === "sending");

// The first of the strongest tier. `workflows` keeps the published order, served
// strongest first and this tab's sends after, so a caller selects by filtering it.
export function strongestWorkflow(workflows) {
  let strongest = null;
  for (const candidate of workflows)
    if (strongest === null || tier(candidate) < tier(strongest)) strongest = candidate;
  return strongest;
}

// An open to-do's word, wherever it stands: Working while a start runs on it.
export const todoLabel = (running) => (running ? "On it" : "To-do open");

export function threadAttention(thread) {
  if (thread.resolved) return null;
  const workflow = thread.attention?.workflow
    ? (thread.workflows.find(
        (candidate) => candidate.id === thread.attention.workflow,
      ) ?? null)
    : null;
  if (thread.attention?.kind === "needs_user") {
    const answering = thread.attention.reason === "obligation";
    // The agent hands the turn over in its own voice; an update that never reached it
    // asks the user to send it again.
    const nextMove = answering
      ? "Your turn"
      : workflow?.subject.kind === "thread"
        ? "Send it again"
        : "Try it again";
    // The updates in the thread the agent still owes an answer.
    const owed = new Set(
      (thread.obligations ?? [])
        .filter((item) => item.source.kind === "update" && item.next_actor === "agent")
        .map((item) => item.id),
    );
    const secondary = strongestWorkflow(
      thread.workflows.filter(
        (candidate) => owed.has(candidate.obligation) && candidate.id !== workflow?.id,
      ),
    );
    return Object.freeze({
      kind: "needs_user",
      label: nextMove,
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
    const [{ title, running }] = thread.todos;
    return Object.freeze({
      kind: "waiting",
      label: todoLabel(running),
      workflow: null,
      secondary: running?.text ?? title,
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
