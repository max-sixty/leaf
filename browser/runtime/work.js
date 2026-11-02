/* Work projections read declared roles against one application publication.
 * Pages own their task and worker vocabulary through $work.widgets; this reader
 * owns progress, assignments, report age and stopped-work meaning independently
 * of how a dashboard composes those facts. */
import { declarationFor, layerFact, registry } from "./registry.js";
import { readPart } from "./semantic-state.js";
import { hasObligationSource } from "./obligations/source.js";
import { obligationsIn } from "./obligations/place.js";
import { elementById } from "./passages.js";
import { quietSince } from "./presence.js";
import { quoted } from "./widget-descriptors.js";
import { saidAt, reportSequence } from "./reports.js";
import { widgetController } from "./widget-controller.js";
import { addressableName } from "./addressable-names.js";

/** @typedef {{role: "scope" | "evidence"}} ContainerRole
 * @typedef {{role: "goal", state: string, done: readonly string[], stopped: readonly string[], stoppedAt?: string}} GoalRole
 * @typedef {{role: "worker", state: string, running: readonly string[], retired: readonly string[], on?: string}} WorkerRole
 * @typedef {ContainerRole | GoalRole | WorkerRole} WorkRole
 * @typedef {WorkRole["role"]} Role
 * @typedef {ReturnType<ReturnType<typeof widgetController>["read"]>} WidgetReading
 * @typedef {(element: Element) => WidgetReading} ReadWidget
 * @typedef {Extract<import("./framework/application.js").ObligationRecord, {source: {kind: "widget"}}>} WidgetObligation
 */
/** @returns {Record<string, WorkRole>} */
const widgets = () => layerFact("$work")?.widgets ?? {};

/** @overload @param {Element | null | undefined} element @param {"goal"} role @returns {GoalRole | null} */
/** @overload @param {Element | null | undefined} element @param {"worker"} role @returns {WorkerRole | null} */
/** @overload @param {Element | null | undefined} element @param {Role | null} [role] @returns {WorkRole | null} */
/** @param {Element | null | undefined} element @param {Role | null} [role] */
export function workRole(element, role = null) {
  const spec = element ? widgets()[element.localName] : undefined;
  return spec && (!role || spec.role === role) ? spec : null;
}

/** @template {Role} R @typedef {{element: Element, role: Extract<WorkRole, {role: R}>}} WorkEntry */
/** @template {Role} R @param {[string, WorkRole]} entry @param {R} role
 * @returns {entry is [string, Extract<WorkRole, {role: R}>]} */
const hasRole = (entry, role) => entry[1].role === role;
/** @template {Role} R @param {Element} root @param {R} role @param {{direct?: boolean}} [options]
 * @returns {WorkEntry<R>[]} */
function workEntries(root, role, { direct = false } = {}) {
  const roles = new Map(
    Object.entries(widgets()).filter((entry) => hasRole(entry, role)),
  );
  const boundary = workAncestor(root, "scope");
  return [...root.querySelectorAll("*")].flatMap((element) => {
    const declared = roles.get(element.localName);
    return declared &&
      workAncestor(element, "scope") === boundary &&
      (!direct || workAncestor(element.parentElement) === root)
      ? [{ element, role: declared }]
      : [];
  });
}
/** @param {Element} root @param {Role} role @param {{direct?: boolean}} [options] */
export function workElements(root, role, options) {
  return workEntries(root, role, options).map(({ element }) => element);
}
/** @param {Element} root @param {Role} role */
export const directWorkElements = (root, role) =>
  workElements(root, role, { direct: true });

/** @param {Element | null | undefined} element @param {Role | null} [role] */
export function workAncestor(element, role) {
  for (let at = element; at; at = at.parentElement) if (workRole(at, role)) return at;
  return null;
}

// The role's state verb is also its report verb when the agent writes it.
/** @param {Element} element @param {GoalRole | WorkerRole} role */
function stateVerb(element, role) {
  const stamped = registry.$states[element.localName];
  const matches = Object.entries(declarationFor(element, "x-state") ?? {}).flatMap(
    ([verb, spec]) => {
      const state = stamped?.[verb];
      return spec.unit === "widget" &&
        spec.record?.kind === "value" &&
        spec.record.attr === role.state &&
        state
        ? [{ verb, state }]
        : [];
    },
  );
  const match = matches[0];
  if (!match || matches.length !== 1)
    throw new Error(
      `leaf: $work ${role.role} <${element.localName}> state ${role.state} needs one recorded widget verb`,
    );
  return match;
}
/** @param {Element} element @param {GoalRole | WorkerRole} role */
function stateReport(element, role) {
  const { verb, state } = stateVerb(element, role);
  return state.writer === "agent" ? verb : null;
}
/** @param {Element} element @param {GoalRole | WorkerRole} role @param {ReadWidget} read */
const roleState = (element, role, read) => {
  const state = read(element).state[stateVerb(element, role).verb];
  return state && "value" in state ? state.value : null;
};

/** @param {Element} element @param {string} action */
const actionReports = (element, action) =>
  reportSequence(element).filter(
    (report) => report.source === "report" && report.action === action,
  );

/** @param {WorkEntry<"worker">} entry @param {ReadWidget} read */
function workerView({ element: worker, role }, read) {
  const state = roleState(worker, role, read);
  const focus = role.on && worker.getAttribute(role.on);
  const reportVerb = stateReport(worker, role);
  const reports = reportVerb ? actionReports(worker, reportVerb) : [];
  const heard = reports.at(-1)?.ts ?? saidAt(worker);
  const running = role.running.some((value) => value === state);
  const scope = workAncestor(worker, "scope");
  const goal = workAncestor(worker.parentElement, "goal");
  const remit = goal && workAncestor(goal, "scope") === scope ? goal : scope;
  const candidate = focus ? document.getElementById(focus) : null;
  const assignment =
    candidate &&
    workRole(candidate, "goal") &&
    workAncestor(candidate, "scope") === scope &&
    (remit === scope || remit?.contains(candidate))
      ? candidate
      : null;
  return {
    element: worker,
    role,
    state,
    retired: role.retired.some((value) => value === state),
    running,
    quiet: running && quietSince(heard),
    heard,
    remit,
    assignment,
  };
}

/** @param {WorkEntry<"goal">} entry @param {ReadWidget} read */
const done = ({ element: goal, role }, read) => {
  return role.done.some((value) => value === roleState(goal, role, read));
};

// The elements of the obligations waiting on the user that `goal` holds (`obligationsIn`) and owns
// itself: in its scope, under no nearer goal, and not a goal.
/** @param {Element} goal @param {readonly WidgetObligation[]} open */
function interventions(goal, open) {
  const scope = workAncestor(goal, "scope");
  return (
    obligationsIn(goal, open)
      // `obligationsIn` holds widgets' obligations, which each name their widget.
      .map((item) =>
        item.source.kind === "widget" ? elementById(item.source.id) : null,
      )
      .filter((item) => item !== null)
      .filter(
        (item) =>
          item !== goal &&
          !workRole(item, "goal") &&
          workAncestor(item, "scope") === scope &&
          workAncestor(item.parentElement, "goal") === goal &&
          !quoted(item),
      )
  );
}

/** @param {WorkEntry<"goal">} entry @param {readonly WidgetObligation[]} open @param {Element[]} nested @param {ReadWidget} read @returns {boolean} */
function stopped(entry, open, nested, read) {
  const { element: goal, role } = entry;
  if (read(goal).thread.heldBy) return true;
  if (nested.length) return true;
  if (!role.stopped.some((value) => value === roleState(goal, role, read)))
    return false;
  if (open.some((item) => item.source.id === goal.id)) return true;
  const children = workEntries(goal, "goal", { direct: true });
  return children.length
    ? children.some((child) =>
        stopped(child, open, interventions(child.element, open), read),
      )
    : true;
}

/** @param {WorkEntry<"goal">} entry @param {readonly WidgetObligation[]} open @param {ReadWidget} read */
function goalView(entry, open, read) {
  const { element: goal, role } = entry;
  const descendants = workEntries(goal, "goal");
  const leaves = descendants.filter(
    (item) => !directWorkElements(item.element, "goal").length,
  );
  const progressLeaves = leaves.length ? leaves : [entry];
  const liveWorkers = workEntries(goal, "worker", { direct: true })
    .map((worker) => workerView(worker, read))
    .filter((worker) => !worker.retired);
  const state = roleState(goal, role, read);
  const reportVerb = stateReport(goal, role);
  const reports = reportVerb ? actionReports(goal, reportVerb) : [];
  const latestReport = reports.at(-1);
  const reportedStoppedAt =
    latestReport?.disposition === "effective" &&
    role.stopped.some((value) => value === latestReport.detail.value)
      ? latestReport.ts
      : null;
  const nested = interventions(goal, open);
  const held = Boolean(read(goal).thread.heldBy);
  return {
    element: goal,
    role,
    state,
    title: addressableName(goal) || goal.id,
    done: done(entry, read),
    stopped: stopped(entry, open, nested, read),
    held,
    leaves: progressLeaves.map(({ element }) => element),
    finished: progressLeaves.filter((leaf) => done(leaf, read)).length,
    liveWorkers,
    stoppedAt:
      reportedStoppedAt ?? (role.stoppedAt ? goal.getAttribute(role.stoppedAt) : null),
  };
}

// The obligations that stop work: a widget's, while it waits on the user; one they left
// with the agent does not (obligations/place.js). Selected as one part, so a paint
// that reads work repaints only when one of these moves, not on every change to the
// inventory, which a comment makes.
const openWidgetObligations = readPart((root) =>
  root.effective.obligations.user.filter((item) => hasObligationSource(item, "widget")),
);

/** @param {Element} scope */
export function readWork(scope) {
  /** @type {Map<Element, WidgetReading>} */
  const readings = new Map();
  /** @param {Element} element */
  const read = (element) => {
    let reading = readings.get(element);
    if (!reading) {
      reading = widgetController(element).read();
      readings.set(element, reading);
    }
    return reading;
  };
  const open = openWidgetObligations();
  const goals = workEntries(scope, "goal").map((goal) => goalView(goal, open, read));
  const byElement = new Map(goals.map((goal) => [goal.element, goal]));
  const workers = workEntries(scope, "worker").map((worker) =>
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
