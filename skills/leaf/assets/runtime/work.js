/* Work projections read declared roles against one application publication.
 * Pages own their task and worker vocabulary through $work.widgets; this reader
 * owns progress, assignments, report age and stopped-work meaning independently
 * of how a dashboard composes those facts. */
import { declarationFor, elementsDeclaring, layerFact } from "./registry.js";
import { readQuestions } from "./questions/model.js";
import { quietSince } from "./presence.js";
import { quoted } from "./widget-elements.js";
import { saidAt, updateSequence } from "./updates.js";
import { widgetController } from "./widget-controller.js";
import { addressableName } from "./anchor-resolution.js";

const widgets = () => layerFact("$work")?.widgets ?? {};

function specs(role) {
  return Object.entries(widgets()).filter(([, spec]) => spec?.role === role);
}

export function workRole(element, role = null) {
  const spec = widgets()[element?.localName];
  return spec && (!role || spec.role === role) ? spec : null;
}

export function workElements(root, role, { direct = false } = {}) {
  const tags = new Set(specs(role).map(([tag]) => tag));
  const candidates = [...root.querySelectorAll("*")];
  const boundary = workAncestor(root, "scope");
  return candidates.filter(
    (element) =>
      tags.has(element.localName) &&
      workAncestor(element, "scope") === boundary &&
      (!direct || workAncestor(element.parentElement) === root),
  );
}

export const directWorkElements = (root, role) =>
  workElements(root, role, { direct: true });

export function workAncestor(element, role) {
  for (let at = element; at; at = at.parentElement) if (workRole(at, role)) return at;
  return null;
}

// The role's state verb is also its report verb when the agent writes it.
function stateReport(element, role) {
  const verb = stateVerb(element, role);
  const spec = declarationFor(element, "x-state")[verb];
  return spec.writer === "agent" ? [verb, spec] : [null, null];
}

function stateVerb(element, role) {
  const attribute = workRole(element, role)?.state;
  const matches = Object.entries(declarationFor(element, "x-state") ?? {})
    .filter(
      ([, spec]) =>
        spec.unit === "widget" &&
        spec.record?.kind === "value" &&
        spec.record.attr === attribute,
    )
    .map(([verb]) => verb);
  if (matches.length !== 1)
    throw new Error(
      `leaf: $work ${role} <${element.localName}> state ${attribute} needs one recorded widget verb`,
    );
  return matches[0];
}

const roleState = (element, role, read) =>
  read(element).state[stateVerb(element, role)]?.value ?? null;

const reportUpdates = (element, action) =>
  updateSequence(element).filter(
    (update) => update.source === "report" && update.action === action,
  );

function workerView(worker, read) {
  const role = workRole(worker, "worker");
  const state = roleState(worker, "worker", read);
  const focus = role.on && worker.getAttribute(role.on);
  const [reportVerb] = stateReport(worker, "worker");
  const reports = reportVerb ? reportUpdates(worker, reportVerb) : [];
  const heard = reports.at(-1)?.ts ?? saidAt(worker);
  const running = role.running.includes(state);
  const scope = workAncestor(worker, "scope");
  const goal = workAncestor(worker.parentElement, "goal");
  const remit = goal && workAncestor(goal, "scope") === scope ? goal : scope;
  const candidate = focus ? document.getElementById(focus) : null;
  const assignment =
    candidate &&
    workRole(candidate, "goal") &&
    workAncestor(candidate, "scope") === scope &&
    (remit === scope || remit.contains(candidate))
      ? candidate
      : null;
  return {
    element: worker,
    role,
    state,
    retired: role.retired.includes(state),
    running,
    quiet: running && quietSince(heard),
    heard,
    remit,
    assignment,
  };
}

const done = (goal, read) => {
  const role = workRole(goal, "goal");
  return role.done.includes(roleState(goal, "goal", read));
};

function interventions(goal, open) {
  const scope = workAncestor(goal, "scope");
  return elementsDeclaring(goal, "x-awaits").filter(
    (item) =>
      item !== goal &&
      !workRole(item, "goal") &&
      workAncestor(item, "scope") === scope &&
      workAncestor(item.parentElement, "goal") === goal &&
      !quoted(item) &&
      open.has(item.id),
  );
}

function stopped(goal, open, nested, read) {
  const role = workRole(goal, "goal");
  if (read(goal).thread.heldBy) return true;
  if (nested.length) return true;
  if (!role.stopped.includes(roleState(goal, "goal", read))) return false;
  if (open.has(goal.id)) return true;
  const children = directWorkElements(goal, "goal");
  return children.length
    ? children.some((child) => stopped(child, open, interventions(child, open), read))
    : true;
}

function goalView(goal, open, read) {
  const descendants = workElements(goal, "goal");
  const leaves = descendants.filter((item) => !directWorkElements(item, "goal").length);
  const progressLeaves = leaves.length ? leaves : [goal];
  const liveWorkers = directWorkElements(goal, "worker")
    .map((worker) => workerView(worker, read))
    .filter((worker) => !worker.retired);
  const role = workRole(goal, "goal");
  const state = roleState(goal, "goal", read);
  const [reportVerb] = stateReport(goal, "goal");
  const reports = reportVerb ? reportUpdates(goal, reportVerb) : [];
  const latestReport = reports.at(-1);
  const reportedStoppedAt =
    latestReport?.disposition === "effective" &&
    role.stopped.includes(latestReport.detail.value)
      ? latestReport.ts
      : null;
  const nested = interventions(goal, open);
  const held = Boolean(read(goal).thread.heldBy);
  return {
    element: goal,
    role,
    state,
    title: addressableName(goal) || goal.id,
    done: done(goal, read),
    stopped: stopped(goal, open, nested, read),
    held,
    leaves: progressLeaves,
    finished: progressLeaves.filter((leaf) => done(leaf, read)).length,
    liveWorkers,
    openInterventions: nested.filter((item) => open.has(item.id)),
    stoppedAt:
      reportedStoppedAt ?? (role.stoppedAt ? goal.getAttribute(role.stoppedAt) : null),
  };
}

export function readWork(scope) {
  const readings = new Map();
  const read = (element) => {
    if (!readings.has(element)) readings.set(element, widgetController(element).read());
    return readings.get(element);
  };
  const open = new Set(readQuestions().user.filter((question) => question.source.kind === "widget").map((question) => question.source.id));
  const goals = workElements(scope, "goal").map((goal) => goalView(goal, open, read));
  const byElement = new Map(goals.map((goal) => [goal.element, goal]));
  const workers = workElements(scope, "worker").map((worker) =>
    workerView(worker, read),
  );
  const liveWorkers = workers.filter((worker) => !worker.retired);
  const leaves = goals.filter(
    (goal) => !directWorkElements(goal.element, "goal").length,
  );
  const stoppedGoals = goals
    .filter((goal) => goal.stopped)
    .sort((a, b) => {
      const at = a.stoppedAt ? new Date(a.stoppedAt).getTime() : NaN;
      const bt = b.stoppedAt ? new Date(b.stoppedAt).getTime() : NaN;
      return (
        (Number.isFinite(at) ? at : Infinity) - (Number.isFinite(bt) ? bt : Infinity)
      );
    });
  return {
    scope,
    goals,
    byElement,
    leaves,
    done: leaves.filter((goal) => goal.done).length,
    workers,
    liveWorkers,
    running: liveWorkers.filter((worker) => worker.running && !worker.quiet),
    quiet: liveWorkers.filter((worker) => worker.quiet),
    stopped: stoppedGoals,
  };
}
