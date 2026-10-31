/* Canonical browser reading of one exact message workflow.

   Python binds accepted delivery, turn, response, activity and condition evidence to
   an input, names the obligation record each serves (`obligation`), and derives each
   thread's attention from the records open in it. It also serves which thread each
   workflow stands in (`thread`) and the workflows strongest first (`served_workflows`).
   The application publisher adds the unresolved local send after the served ones; only
   a thread the user opened takes its attention from it. Every message, compact thread row and margin entry reads
   these values; none reclassifies receipts, streams, turn ownership, whose turn a
   thread is, or which workflow is stronger. `strongestWorkflow` only places this tab's
   own sends against the served order. A workflow's word is `workflowWord`, its last
   step's line `workflowStep`, and its face on a control `progressFace`, on every
   surface; a thread's word is `threadAttention`'s, which Threads states as its status
   and the margin and Page Map as its line (`margin-model.js`, `threadMarks`). Each
   word is said by the agent or by Leaf (voice.js), and each word function takes
   `agent`, what the page calls its agent (`semantic-state.agentName`), from its
   application-facing caller, so this model stays free of application state. */
import { agentSays, leafSays } from "../voice.js";

// Each stage's word, said by whoever says it (glossary.md, "Reader-facing words";
// voice.js). Leaf speaks in the agent's voice where what the agent would say is
// reliable: it started the update (On it), its reply is streaming in (Replying), or it
// answered. Everything else is what Leaf observed of the update's way to the agent,
// through the harness or the clock, so Leaf says it in its own voice: the update
// waiting for the agent whether or not the server has logged it yet, the harness
// queuing or delivering it, and every condition. The user chose this on 30 October
// 2026, over stage words in the agent's voice such as "Got it", which put Leaf's
// inference in the agent's mouth, and the same day gave the agent the reply it is
// streaming; on 27 October they chose Leaf's "Queued for Claude" over the agent's "Not
// seen yet".
const queuedFor = (agent) => leafSays(`Queued for ${agent}`);
const STAGES = Object.freeze({
  sending: queuedFor,
  sent: queuedFor,
  queued: () => leafSays("Up next"),
  picked_up: () => leafSays("Delivered"),
  working: () => agentSays("On it"),
  replying: () => agentSays("Replying"),
  answered: () => agentSays("Answered"),
});

const CONDITION_WORDS = Object.freeze({
  ended: "Stopped",
  interrupted: "Interrupted",
  stale: "Gone quiet",
  failed: "Failed",
});

// A failed response's word, on its workflow and on the failure reply that reports it.
export const NOT_ANSWERED = leafSays("Not answered");
// A thread settled, wherever its state is said.
export const RESOLVED = leafSays("Resolved");

// A workflow's word, or null where it says none: an answer says nothing unless
// `answered` asks for its word, as a title does. An update still waiting past the
// pickup grace (`activity.PICKUP_GRACE`) says so.
export const workflowWord = (workflow, agent, { answered = false } = {}) => {
  if (!workflow) return null;
  const { condition } = workflow;
  if (condition)
    return condition.kind === "stale" && condition.operation === "delivery"
      ? leafSays(`Still queued for ${agent}`)
      : condition.kind === "failed" && condition.operation === "response"
        ? NOT_ANSWERED
        : leafSays(CONDITION_WORDS[condition.kind] ?? "Failed");
  if (workflow.stage === "answered" && !answered) return null;
  return STAGES[workflow.stage]?.(agent) ?? null;
};

export const workflowTitle = (workflow, agent) =>
  [workflowWord(workflow, agent, { answered: true })?.text, workflow?.detail]
    .filter(Boolean)
    .join(" · ");

// The face a control paints for the agent's progress on a workflow: delivered, or at
// work, which a reply still streaming is too. Its word stays the workflow's own
// (`workflowWord`), so a reply streaming reads Replying under the working face.
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
export const workflowStep = (workflow, agent) =>
  progressFace(workflow) === "working" && workflow.detail
    ? agentSays(workflow.detail)
    : workflowWord(workflow, agent);

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

// An open to-do's word, wherever it stands, in the agent's voice since it opened the
// to-do: On it while a start runs on it, else what it means for the user's request,
// which the user chose over "To-do open" (2026-10-27).
export const todoWord = (running) => agentSays(running ? "On it" : "Still to do");

// A thread's state while it isn't resolved, and its `word`.
export function threadAttention(thread, agent) {
  if (thread.resolved) return null;
  const workflow = thread.attention?.workflow
    ? (thread.workflows.find(
        (candidate) => candidate.id === thread.attention.workflow,
      ) ?? null)
    : null;
  // The agent hands the turn over with a question, its own act; an update that never
  // reached it is Leaf's to hand back, asking the user to send it again.
  if (thread.attention?.kind === "needs_user")
    return Object.freeze({
      kind: "needs_user",
      word:
        thread.attention.reason === "obligation"
          ? agentSays("Your turn")
          : leafSays(
              workflow?.subject.kind === "thread" ? "Send it again" : "Try it again",
            ),
      workflow,
    });
  // A to-do the agent opened on the thread holds it after the update it answered has
  // settled: the agent's own commitment, in its voice.
  if (thread.attention?.kind === "waiting" && thread.attention.reason === "todo")
    return Object.freeze({
      kind: "waiting",
      word: todoWord(thread.todos[0].running),
      workflow: null,
    });
  if (thread.attention?.kind === "waiting")
    return Object.freeze({
      kind: "waiting",
      word:
        workflowWord(workflow, agent) ??
        leafSays(thread.attention.reason === "uncertain" ? "Uncertain" : "Waiting"),
      workflow,
    });
  return null;
}
