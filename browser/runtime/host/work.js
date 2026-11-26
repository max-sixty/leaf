/* Work projections read declared roles against one application publication.
 * Leaf owns the roles; a package maps its tags onto them in $work.widgets, which
 * composition holds to each tag's declaration (`registry.validation.validate_work_roles`),
 * so this reader takes the entries as given. It owns progress, assignments, report age
 * and stopped-work meaning independently of how a dashboard composes those facts. */
import { declarationFor, layerFact, registry } from "../state/registry.js";
import { readPart } from "../state/semantic-state.js";
import { hasObligationSource } from "../state/obligations/source.js";
import { obligationsByRegion } from "../records/obligations/place.js";
import { authoredScope, elementById } from "../readings/passages.js";
import { quietSince } from "../state/presence.js";
import { quoted } from "../records/widget-descriptors.js";
import { saidAt, reportSequence } from "./reports.js";
import { widgetController } from "./widget-controller.js";
import { addressableName } from "../readings/addressable-names.js";

/** @typedef {{role: "scope" | "evidence"}} ContainerRole
 * @typedef {{role: "goal", state: string, done: readonly string[], stopped: readonly string[], stoppedAt?: string}} GoalRole
 * @typedef {{role: "worker", state: string, running: readonly string[], retired: readonly string[], on?: string}} WorkerRole
 * @typedef {ContainerRole | GoalRole | WorkerRole} WorkRole
 * @typedef {WorkRole["role"]} Role
 * @typedef {ReturnType<ReturnType<typeof widgetController>["read"]>} WidgetReading
 * @typedef {(element: Element) => WidgetReading} ReadWidget
 * @typedef {Extract<import("../state/semantic-application.js").ObligationRecord, {source: {kind: "widget"}}>} WidgetObligation
 * @typedef {{tree: WorkTree, held: Map<Node, import("../state/semantic-application.js").ObligationRecord[]>, asking: Set<string>, stopped: Map<Element, boolean>}} Open
 *   One reading's scope (`workTree`) and its open widget obligations: those each goal holds, placed
 *   once for every goal of the scope (`obligationsByRegion`); the ids of the widgets that
 *   own one; and each goal's `stopped`, which a parent's reads again.
 */
/** @returns {Record<string, WorkRole>} */
const widgets = () => layerFact("$work")?.widgets ?? {};

/** @overload @param {Element | null | undefined} element @param {"goal"} role @returns {GoalRole | null} */
/** @overload @param {Element | null | undefined} element @param {"worker"} role @returns {WorkerRole | null} */
/** @overload @param {Element | null | undefined} element @param {Role | null} [role] @returns {WorkRole | null} */
/** @param {Element | null | undefined} element @param {Role | null} [role] */
function workRole(element, role = null) {
  const spec = element ? widgets()[element.localName] : undefined;
  return spec && (!role || spec.role === role) ? spec : null;
}

/** @template {Role} R @typedef {{element: Element, role: Extract<WorkRole, {role: R}>}} WorkEntry */
/** @typedef {{
 *   goals: WorkEntry<"goal">[],
 *   workers: WorkEntry<"worker">[],
 *   childGoals: Map<Element, WorkEntry<"goal">[]>,
 *   childWorkers: Map<Element, Element[]>,
 *   leaves: (goal: Element) => WorkEntry<"goal">[],
 * }} WorkTree
 *   A scope's goals and workers in document order, read in one walk. A goal's or worker's
 *   children are those whose nearest work ancestor of any role is it; a goal's leaves are
 *   the goals inside it, through any role but a nested scope, that have no child goal.
 */
/** @template K, V @param {Map<K, V[]>} map @param {K} key @param {V} item */
const append = (map, key, item) => {
  const list = map.get(key);
  if (list) list.push(item);
  else map.set(key, [item]);
};
// One walk of the scope, so a reading costs the scope's size rather than its size for
// each goal (root AGENTS.md, "Responsiveness"). A nested scope's work is its own, so the
// walk doesn't enter it. `root` is the scope, or the page or message where `scope` is
// null.
/** @param {Element} root @param {Element | null} scope @returns {WorkTree} */
function workTree(root, scope) {
  const roles = widgets();
  /** @type {WorkTree["goals"]} */
  const goals = [];
  /** @type {WorkTree["workers"]} */
  const workers = [];
  /** @type {WorkTree["childGoals"]} */
  const childGoals = new Map();
  /** @type {WorkTree["childWorkers"]} */
  const childWorkers = new Map();
  /** @type {Map<Element | null, WorkEntry<"goal">[]>} goals by their nearest goal ancestor */
  const innerGoals = new Map();
  /** @param {Element} parent @param {Element | null} work @param {Element | null} goal */
  const visit = (parent, work, goal) => {
    for (const element of parent.children) {
      const role = roles[element.localName];
      if (role?.role === "scope") continue;
      if (role?.role === "goal") {
        const entry = { element, role };
        goals.push(entry);
        if (work) append(childGoals, work, entry);
        append(innerGoals, goal, entry);
      } else if (role?.role === "worker") {
        workers.push({ element, role });
        if (work) append(childWorkers, work, element);
      }
      visit(element, role ? element : work, role?.role === "goal" ? element : goal);
    }
  };
  visit(root, scope, null);
  /** @type {Map<Element, WorkEntry<"goal">[]>} */
  const leafCache = new Map();
  /** @param {Element} goal @returns {WorkEntry<"goal">[]} */
  const leaves = (goal) => {
    let found = leafCache.get(goal);
    if (!found) {
      found = (innerGoals.get(goal) ?? []).flatMap((inner) => [
        ...(childGoals.has(inner.element) ? [] : [inner]),
        ...leaves(inner.element),
      ]);
      leafCache.set(goal, found);
    }
    return found;
  };
  return { goals, workers, childGoals, childWorkers, leaves };
}

/** @param {Element | null | undefined} element @param {Role | null} [role] */
function workAncestor(element, role) {
  for (let at = element; at; at = at.parentElement) if (workRole(at, role)) return at;
  return null;
}

// The role's state verb: the one widget value record on its state attribute, which
// composition requires. It is also the role's report verb when the agent writes it.
/** @param {Element} element @param {GoalRole | WorkerRole} role */
const stateVerb = (element, role) =>
  /** @type {string} */ (
    Object.entries(declarationFor(element)?.verbs ?? {}).find(
      ([, spec]) =>
        spec.unit === "widget" &&
        spec.record?.kind === "value" &&
        spec.record.attr === role.state,
    )?.[0]
  );
/** @param {Element} element @param {GoalRole | WorkerRole} role */
function stateReport(element, role) {
  const verb = stateVerb(element, role);
  return registry.$states[element.localName]?.[verb]?.writer === "agent" ? verb : null;
}
/** @param {Element} element @param {GoalRole | WorkerRole} role @param {ReadWidget} read */
const roleState = (element, role, read) => {
  const state = read(element).state[stateVerb(element, role)];
  return state && "value" in state ? state.value : null;
};

/** @param {Element} element @param {string} action */
const actionReports = (element, action) =>
  reportSequence(element).filter((report) => report.action === action);

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

// The elements of the obligations waiting on the user that `goal` holds (`obligationsByRegion`)
// and owns itself: in its scope, under no nearer goal, and not a goal.
/** @param {Element} goal @param {Open} open */
function interventions(goal, open) {
  const scope = workAncestor(goal, "scope");
  return (
    (open.held.get(goal) ?? [])
      // `open.held` holds widgets' obligations, which each name their widget.
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

/** @param {WorkEntry<"goal">} entry @param {Open} open @param {ReadWidget} read @returns {boolean} */
function stopped(entry, open, read) {
  const { element: goal } = entry;
  let result = open.stopped.get(goal);
  if (result === undefined) {
    result = stoppedNow(entry, open, read);
    open.stopped.set(goal, result);
  }
  return result;
}
/** @param {WorkEntry<"goal">} entry @param {Open} open @param {ReadWidget} read @returns {boolean} */
function stoppedNow(entry, open, read) {
  const { element: goal, role } = entry;
  if (read(goal).thread.heldBy) return true;
  if (interventions(goal, open).length) return true;
  if (!role.stopped.some((value) => value === roleState(goal, role, read)))
    return false;
  if (open.asking.has(goal.id)) return true;
  const children = open.tree.childGoals.get(goal) ?? [];
  return children.length ? children.some((child) => stopped(child, open, read)) : true;
}

/** @param {WorkEntry<"goal">} entry @param {Open} open @param {Map<Element, ReturnType<typeof workerView>>} workers @param {ReadWidget} read */
function goalView(entry, open, workers, read) {
  const { element: goal, role } = entry;
  const leaves = open.tree.leaves(goal);
  const progressLeaves = leaves.length ? leaves : [entry];
  const liveWorkers = (open.tree.childWorkers.get(goal) ?? [])
    .map((worker) => /** @type {ReturnType<typeof workerView>} */ (workers.get(worker)))
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
  const held = Boolean(read(goal).thread.heldBy);
  return {
    element: goal,
    role,
    state,
    title: addressableName(goal) || goal.id,
    done: done(entry, read),
    stopped: stopped(entry, open, read),
    held,
    leaves: progressLeaves.map(({ element }) => element),
    finished: progressLeaves.filter((leaf) => done(leaf, read)).length,
    liveWorkers,
    stoppedAt:
      reportedStoppedAt ?? (role.stoppedAt ? goal.getAttribute(role.stoppedAt) : null),
  };
}

// The obligations that stop work: a widget's, while it waits on the user; one they left
// with the agent does not (records/obligations/place.js). Selected as one part, so a paint
// that reads work repaints only when one of these moves, not on every change to the
// inventory, which a comment makes.
const openWidgetObligations = readPart((root) =>
  root.effective.obligations.user.filter((item) => hasObligationSource(item, "widget")),
);

// The work of the scope `element` is or stands in. Outside every scope it is the work
// in no scope of the page or message holding it (`authoredScope`), and the reading's
// `scope` is null, as a worker's `remit` outside any goal is.
/** @param {Element} element */
export function readWork(element) {
  const scope = workAncestor(element, "scope");
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
  const obligations = openWidgetObligations();
  const tree = workTree(scope ?? authoredScope(element), scope);
  /** @type {Open} */
  const open = {
    tree,
    held: obligationsByRegion(
      tree.goals.map(({ element }) => element),
      obligations,
    ),
    asking: new Set(obligations.map((item) => item.source.id)),
    stopped: new Map(),
  };
  const workers = tree.workers.map((worker) => workerView(worker, read));
  const workerViews = new Map(workers.map((worker) => [worker.element, worker]));
  const goals = tree.goals.map((goal) => goalView(goal, open, workerViews, read));
  const byElement = new Map(goals.map((goal) => [goal.element, goal]));
  const liveWorkers = workers.filter((worker) => !worker.retired);
  const leaves = goals.filter((goal) => !tree.childGoals.has(goal.element));
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
