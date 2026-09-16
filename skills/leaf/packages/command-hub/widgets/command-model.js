/* Shared projection for the optional orchestration family. Leaf's kernel supplies the
 * document, log, Asks, and report folds; this package owns the meaning of Command's tags.
 * Later packages may replace or add role entries under `$command.widgets`. */
import {
  declarationFor,
  elementsDeclaring,
  layerFact,
  openAsks,
  quietSince,
  quoted,
  saidAt,
  updateSequence,
  widgetController,
} from "/runtime/widget-api.js";

const widgets = layerFact("$command")?.widgets ?? {};

function specs(role) {
  return Object.entries(widgets).filter(([, spec]) => spec?.role === role);
}

function assertModel() {
  for (const role of ["command", "goal", "worker"])
    if (!specs(role).length)
      throw new Error(`leaf: $command.widgets declares no ${role} role`);
}
assertModel();

export function commandRole(element, role = null) {
  const spec = widgets[element?.localName];
  return spec && (!role || spec.role === role) ? spec : null;
}

export function elementsWithCommandRole(root, role, { direct = false } = {}) {
  const tags = new Set(specs(role).map(([tag]) => tag));
  const candidates = direct ? [...root.children] : [...root.querySelectorAll("*")];
  const boundary = closestCommandRole(root, "command");
  return candidates.filter(
    (element) =>
      tags.has(element.localName) &&
      closestCommandRole(element, "command") === boundary,
  );
}

export const directCommandRole = (root, role) =>
  elementsWithCommandRole(root, role, { direct: true });

export function closestCommandRole(element, role) {
  for (let at = element; at; at = at.parentElement)
    if (commandRole(at, role)) return at;
  return null;
}

function stateReport(element, role) {
  const spec = commandRole(element, role);
  const report = declarationFor(element, "x-report")?.[spec?.report];
  return report ? [spec.report, report] : [null, null];
}

function stateFacet(element, role) {
  const attribute = commandRole(element, role)?.state;
  const matches = ["x-state", "x-report"].flatMap((channel) =>
    Object.values(declarationFor(element, channel) ?? {}).filter(
      (spec) =>
        spec.unit === "widget" &&
        spec.record?.kind === "value" &&
        spec.record.attr === attribute,
    ),
  );
  if (matches.length !== 1)
    throw new Error(
      `leaf: $command ${role} <${element.localName}> state ${attribute} needs one recorded widget facet`,
    );
  return matches[0].facet;
}

const roleState = (element, role, read) =>
  read(element).state[stateFacet(element, role)]?.value ?? null;

const reportUpdates = (element, action) =>
  updateSequence(element).filter(
    (update) => update.source === "report" && update.action === action,
  );

function workerView(worker, read) {
  const role = commandRole(worker, "worker");
  const state = roleState(worker, "worker", read);
  const focus = role.on && worker.getAttribute(role.on);
  const [reportVerb] = stateReport(worker, "worker");
  const reports = reportVerb ? reportUpdates(worker, reportVerb) : [];
  const heard = reports.at(-1)?.ts ?? saidAt(worker);
  const running = role.running.includes(state);
  const command = closestCommandRole(worker, "command");
  const goal = closestCommandRole(worker.parentElement, "goal");
  const remit =
    goal && closestCommandRole(goal, "command") === command ? goal : command;
  const candidate = focus ? document.getElementById(focus) : null;
  const assignment =
    candidate &&
    commandRole(candidate, "goal") &&
    closestCommandRole(candidate, "command") === command &&
    (remit === command || remit.contains(candidate))
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
  const role = commandRole(goal, "goal");
  return role.done.includes(roleState(goal, "goal", read));
};

function interventions(goal, open) {
  const command = closestCommandRole(goal, "command");
  return elementsDeclaring(goal, "x-awaits").filter(
    (item) =>
      item !== goal &&
      !commandRole(item, "goal") &&
      closestCommandRole(item, "command") === command &&
      closestCommandRole(item.parentElement, "goal") === goal &&
      !quoted(item) &&
      open.has(item.id),
  );
}

function stopped(goal, open, nested, read) {
  const role = commandRole(goal, "goal");
  if (read(goal).conversation.heldBy) return true;
  if (nested.length) return true;
  if (!role.stopped.includes(roleState(goal, "goal", read))) return false;
  if (open.has(goal.id)) return true;
  const children = directCommandRole(goal, "goal");
  return children.length
    ? children.some((child) => stopped(child, open, interventions(child, open), read))
    : true;
}

function goalView(goal, open, read) {
  const descendants = elementsWithCommandRole(goal, "goal");
  const leaves = descendants.filter((item) => !directCommandRole(item, "goal").length);
  const progressLeaves = leaves.length ? leaves : [goal];
  const liveWorkers = directCommandRole(goal, "worker")
    .map((worker) => workerView(worker, read))
    .filter((worker) => !worker.retired);
  const role = commandRole(goal, "goal");
  const state = roleState(goal, "goal", read);
  const [reportVerb, reportSpec] = stateReport(goal, "goal");
  const reports = reportVerb ? reportUpdates(goal, reportVerb) : [];
  const latestReport = reports.at(-1);
  const reportedStoppedAt =
    latestReport?.disposition === "effective" &&
    role.stopped.includes(latestReport.detail[reportSpec.record.value])
      ? latestReport.ts
      : null;
  const nested = interventions(goal, open);
  const held = Boolean(read(goal).conversation.heldBy);
  return {
    element: goal,
    role,
    state,
    title: goal.querySelector(":scope > strong")?.textContent.trim() || goal.id,
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

export function commandSnapshot(plan) {
  const readings = new Map();
  const read = (element) => {
    if (!readings.has(element)) readings.set(element, widgetController(element).read());
    return readings.get(element);
  };
  const open = new Set(openAsks().map((ask) => ask.sourceId));
  const goals = elementsWithCommandRole(plan, "goal").map((goal) =>
    goalView(goal, open, read),
  );
  const byElement = new Map(goals.map((goal) => [goal.element, goal]));
  const workers = elementsWithCommandRole(plan, "worker").map((worker) =>
    workerView(worker, read),
  );
  const liveWorkers = workers.filter((worker) => !worker.retired);
  const leaves = goals.filter(
    (goal) => !directCommandRole(goal.element, "goal").length,
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
    plan,
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
