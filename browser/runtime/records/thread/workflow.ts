/* Canonical browser reading of where work stands, in words.

   Python says where every obligation record and every update's delivery (its
   workflow) stands, in one vocabulary (`standing.py`): whose move it is (`next_actor`),
   `state` (waiting, running, blocked, done), the `reason` a state leaves out, and on an
   update whether a turn has taken it in (`seen`). It names the record that speaks for
   each thread (`attention`), the workflow each update's record stands by (`workflow`),
   which thread each workflow stands in (`thread`) and the workflows strongest first
   (`served_workflows`). The application publisher adds the unresolved local send after
   the served ones (`local`); only a thread the user opened takes its attention from
   it. Every message, compact thread row and margin entry reads these values; none
   decides again whose turn a thread is, whether work moves, or which workflow is
   stronger. `strongestWorkflow` only places this tab's own sends against the served
   order. A workflow's word is `workflowWord`, its last step's line `workflowStep`, and
   its face on a control `progressFace`, on every surface; a thread's word is
   `threadAttention`'s, which Threads states as its status and the margin and Page Map
   as its line (`features/margin-model.js`, `threadMarks`). Each word is said by the agent or by
   Leaf (base/voice.js), and each word function takes `agent`, what the page calls its agent
   (`semantic-state.agentName`), from its application-facing caller, so this model
   stays free of application state. */
import { agentSays, leafSays } from "../../base/voice.js";
import type { Workflow } from "../../../types/domain.js";
import type { Immutable } from "../../base/snapshot.js";
import type { readThreadRecords } from "../../state/thread/model.js";

export type ThreadRecord = Immutable<ReturnType<typeof readThreadRecords>[number]>;
const widgetWorkflow = (
  workflow: Workflow,
): workflow is Extract<Workflow, { subject: { kind: "widget" } }> =>
  workflow.subject.kind === "widget";

/** The workflow's explicit line and the source position it was said at. */
export const hasWorkflowLine = (
  workflow: Workflow,
): workflow is Extract<Workflow, { detail: string; detail_seq: number }> =>
  workflow.detail !== null;

// Each standing's word, said by whoever says it (glossary.md, "Reader-facing words";
// base/voice.js). Leaf speaks in the agent's voice where what the agent would say is
// reliable: it started the update, or a progress message of its own stands after it,
// such as a line fork's working line (On it), its reply is streaming in (Replying), or
// it answered. Everything else is
// what Leaf observed of the update's way to the agent, through the harness or the
// clock, so Leaf says it in its own voice: the update waiting for the agent whether or
// not the server has logged it yet, a turn taking it in, and every reason it is
// blocked. The user chose this over words in the agent's voice such as "Got it", which
// put Leaf's inference in the agent's mouth, and gave the agent the reply it is
// streaming; they chose Leaf's "Queued for Claude" over the agent's "Not seen yet",
// and gave a line fork's working line the agent's On it.
// On leaf.page a write to a page whose agent isn't running waits seconds while its
// container starts, a wait only that first write pays, so a send that launches it says
// so until the server has it. The user asked for these words.
// An update a harness queue holds for the agent's next turn reads Queued like any other
// no turn has taken in: "Up next" would word a difference between two queues that asks
// nothing different of the user.
const REASON_WORDS: Record<NonNullable<Workflow["reason"]>, string> = Object.freeze({
  stopped: "Stopped",
  interrupted: "Interrupted",
  quiet: "Gone quiet",
  undelivered: "Still queued",
  terminal: "Waiting in the terminal",
  failed: "Failed",
  replying: "Replying",
});

// A failed response's word, on its workflow and on the failure reply that reports it.
export const NOT_ANSWERED = leafSays("Not answered");
// A thread settled, wherever its state is said.
export const RESOLVED = leafSays("Resolved");

// A workflow's word, or null where it says none: an answer says nothing unless
// `answered` asks for its word, as a title does. An update still waiting past the
// pickup grace (`activity.PICKUP_GRACE`) says so, and one a harness gave up on says it
// wasn't answered, where a send this tab had refused only failed.
export const workflowWord = (
  workflow: Workflow | null | undefined,
  agent: string,
  { answered = false } = {},
) => {
  if (!workflow) return null;
  const { state, reason } = workflow;
  if (state === "blocked")
    return reason === "undelivered"
      ? leafSays(`${REASON_WORDS.undelivered} for ${agent}`)
      : reason === "failed" && !workflow.local
        ? NOT_ANSWERED
        : leafSays(REASON_WORDS[reason ?? "failed"]);
  if (state === "done") return answered ? agentSays("Answered") : null;
  if (state === "running")
    return agentSays(reason === "replying" ? REASON_WORDS.replying : "On it");
  return workflow.seen
    ? leafSays("Delivered")
    : leafSays(workflow.launching ? "Starting the agent" : `Queued for ${agent}`);
};

export const workflowTitle = (workflow: Workflow | null | undefined, agent: string) =>
  [workflowWord(workflow, agent, { answered: true })?.text, workflow?.detail]
    .filter(Boolean)
    .join(" · ");

// Whether the agent has a record or a workflow in hand: at work on it, or held from it
// only by a dialog in its own window, which the user's answer there frees.
export const inHand = ({
  state,
  reason,
}: {
  readonly state: Workflow["state"];
  readonly reason: Workflow["reason"];
}) => state === "running" || reason === "terminal";

// The face a control paints for the agent's progress on a workflow: taken in by a
// turn, or at work, which a reply still streaming is too. Its word stays the
// workflow's own (`workflowWord`), so a reply streaming reads Replying under the
// working face.
export const progressFace = (workflow: Workflow | null | undefined) =>
  !workflow
    ? null
    : workflow.state === "running"
      ? "working"
      : workflow.state === "waiting" && workflow.seen
        ? "delivered"
        : null;

export const isWorkflowProgress = (workflow: Workflow | null | undefined) =>
  progressFace(workflow) !== null;

// What the agent's last step on a workflow says while it is at work on it: the line of
// the start or progress reply that holds it (`detail`), which the page's status says of
// the newest it holds. Before it says one, and once the work stalls, none.
export const workflowStep = (workflow: Workflow | null | undefined) =>
  progressFace(workflow) === "working" && workflow?.detail
    ? agentSays(workflow.detail)
    : null;

export const isPageWidgetWorkflow = (workflow: Workflow, revision: number | null) =>
  widgetWorkflow(workflow) &&
  workflow.thread === null &&
  workflow.revision <= Number(revision);

// Whether a workflow's update is back with the user to send again: a served one the
// harness gave up on, or this tab's refused send.
const handedBack = (workflow: Workflow) =>
  workflow.state === "blocked" && workflow.reason === "failed";

// A send this tab has not delivered is the only `local` workflow. It ranks below
// every served workflow with the same next actor, and an update that is the user's to
// make still ranks above every one that is the agent's.
const tier = (workflow: Workflow) =>
  (handedBack(workflow) ? 0 : 2) + Number(Boolean(workflow.local));

// The first of the strongest tier. `workflows` keeps the published order, served
// strongest first and this tab's sends after, so a caller selects by filtering it.
export function strongestWorkflow(workflows: readonly Workflow[]) {
  let strongest = null;
  for (const candidate of workflows)
    if (strongest === null || tier(candidate) < tier(strongest)) strongest = candidate;
  return strongest;
}

// An open to-do's word, wherever it stands, in the agent's voice since it opened the
// to-do: On it while a start runs on it, else what it means for the user's request,
// which the user chose over "To-do open": Waiting on what the agent named its work
// waiting on (`waiting_on`), or Still to do. One whose start stopped or went quiet
// says so in Leaf's voice, as an update's does.
export const todoWord = (todo: {
  readonly state: Workflow["state"];
  readonly reason: Workflow["reason"];
  readonly waiting_on?: string | null;
}) =>
  todo.state === "blocked"
    ? leafSays(REASON_WORDS[todo.reason ?? "quiet"])
    : agentSays(
        todo.state === "running"
          ? "On it"
          : todo.waiting_on
            ? `Waiting on ${todo.waiting_on}`
            : "Still to do",
      );

// Whose turn a thread is while it isn't resolved, where it stands and its `word`: the
// reading of the record that speaks for it (`attention`). `workflow` is the one an
// update's record stands by.
export function threadAttention(thread: ThreadRecord, agent: string) {
  const record = thread.resolved ? null : thread.attention;
  if (!record) return null;
  const workflow =
    record.source.kind === "update"
      ? (thread.workflows.find((candidate) => candidate.id === record.workflow) ?? null)
      : null;
  // The agent hands the turn over with a question, its own act; an update that never
  // reached it is Leaf's to hand back, asking the user to send it again.
  if (record.next_actor === "user")
    return Object.freeze({
      turn: "user" as const,
      state: record.state,
      word:
        record.source.kind === "update"
          ? leafSays(
              workflow?.subject.kind === "thread" ? "Send it again" : "Try it again",
            )
          : agentSays("Your turn"),
      workflow,
    });
  return Object.freeze({
    turn: "agent" as const,
    state: record.state,
    // A to-do the agent opened on the thread holds it after the update it answered
    // has settled: the agent's own commitment, in its voice.
    word:
      record.source.kind === "todo"
        ? todoWord(record)
        : (workflowWord(workflow, agent) ??
          leafSays(record.state === "blocked" ? "Uncertain" : "Waiting")),
    workflow,
  });
}
