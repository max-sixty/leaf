/* Work projections read declared roles against one application publication.
 * Leaf owns the roles; a package maps its tags onto them in $work.widgets, which
 * composition holds to each tag's declaration (`registry.validation.validate_work_roles`),
 * so this reader takes the entries as given. It owns progress, assignments, report age
 * and stopped-work meaning independently of how a dashboard composes those facts. */
import { declarationFor, registry } from "../state/registry.js";
import { readPart } from "../state/semantic-state.js";
import { hasObligationSource } from "../state/obligations/source.js";
import { obligationsByRegion } from "../records/obligations/place.js";
import { authoredScope, elementById } from "../readings/passages.js";
import { quietSince } from "../state/presence.js";
import { quoted } from "../records/widget-descriptors.js";
import { saidAt, reportSequence } from "./reports.js";
import { controllerOf } from "./widget-controller.js";
import { addressableName } from "../readings/addressable-names.js";
import type { WidgetReading } from "./widget-controller.js";
import type { ObligationRecord } from "../state/semantic-application.js";

type ContainerRole = { role: "scope" | "evidence" };
type GoalRole = {
  role: "goal";
  state: string;
  done: readonly string[];
  stopped: readonly string[];
  stoppedAt?: string;
};
type WorkerRole = {
  role: "worker";
  state: string;
  running: readonly string[];
  retired: readonly string[];
  on?: string;
};
type WorkRole = ContainerRole | GoalRole | WorkerRole;
type Role = WorkRole["role"];
type ReadWidget = (element: Element) => WidgetReading;
/** One reading's scope (`workTree`) and its open widget obligations: those each goal holds, placed
 * once for every goal of the scope (`obligationsByRegion`); the ids of the widgets that
 * own one; and each goal's `stopped`, which a parent's reads again. */
type Open = {
  tree: WorkTree;
  held: Map<Node, ObligationRecord[]>;
  asking: Set<string>;
  stopped: Map<Element, boolean>;
};
const widgets = (): Record<string, WorkRole> => registry.$work?.widgets ?? {};

function workRole(element: Element | null | undefined, role: "goal"): GoalRole | null;
function workRole(
  element: Element | null | undefined,
  role: "worker",
): WorkerRole | null;
function workRole(
  element: Element | null | undefined,
  role?: Role | null,
): WorkRole | null;
function workRole(element: Element | null | undefined, role: Role | null = null) {
  const spec = element ? widgets()[element.localName] : undefined;
  return spec && (!role || spec.role === role) ? spec : null;
}

type WorkEntry<R extends Role> = {
  element: Element;
  role: Extract<WorkRole, { role: R }>;
};
/** A scope's goals and workers in document order, read in one walk. A goal's or worker's
 * children are those whose nearest work ancestor of any role is it; a goal's leaves are
 * the goals inside it, through any role but a nested scope, that have no child goal. */
type WorkTree = {
  goals: WorkEntry<"goal">[];
  workers: WorkEntry<"worker">[];
  childGoals: Map<Element, WorkEntry<"goal">[]>;
  childWorkers: Map<Element, Element[]>;
  leaves: (goal: Element) => WorkEntry<"goal">[];
};
const append = <K, V>(map: Map<K, V[]>, key: K, item: V) => {
  const list = map.get(key);
  if (list) list.push(item);
  else map.set(key, [item]);
};
// One walk of the scope, so a reading costs the scope's size rather than its size for
// each goal (root AGENTS.md, "Responsiveness"). A nested scope's work is its own, so the
// walk doesn't enter it. `root` is the scope, or the page or message where `scope` is
// null.
function workTree(root: Element, scope: Element | null): WorkTree {
  const roles = widgets();
  const goals: WorkTree["goals"] = [];
  const workers: WorkTree["workers"] = [];
  const childGoals: WorkTree["childGoals"] = new Map();
  const childWorkers: WorkTree["childWorkers"] = new Map();
  // Goals by their nearest goal ancestor.
  const innerGoals = new Map<Element | null, WorkEntry<"goal">[]>();
  const visit = (parent: Element, work: Element | null, goal: Element | null) => {
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
  const leafCache = new Map<Element, WorkEntry<"goal">[]>();
  const leaves = (goal: Element): WorkEntry<"goal">[] => {
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

function workAncestor(element: Element | null | undefined, role?: Role | null) {
  for (let at = element; at; at = at.parentElement) if (workRole(at, role)) return at;
  return null;
}

// The role's state verb: the one widget value record on its state attribute, which
// composition requires. It is also the role's report verb when the agent writes it.
const stateVerb = (element: Element, role: GoalRole | WorkerRole) =>
  Object.entries(declarationFor(element)?.verbs ?? {}).find(
    ([, spec]) =>
      spec.unit === "widget" &&
      spec.record?.kind === "value" &&
      spec.record.attr === role.state,
  )?.[0] as string;
function stateReport(element: Element, role: GoalRole | WorkerRole) {
  const verb = stateVerb(element, role);
  return registry.$states[element.localName]?.[verb]?.writer === "agent" ? verb : null;
}
const roleState = (element: Element, role: GoalRole | WorkerRole, read: ReadWidget) => {
  const state = read(element).state[stateVerb(element, role)];
  return state && "value" in state ? state.value : null;
};

const actionReports = (element: Element, action: string) =>
  reportSequence(element).filter((report) => report.action === action);

function workerView({ element: worker, role }: WorkEntry<"worker">, read: ReadWidget) {
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

const done = ({ element: goal, role }: WorkEntry<"goal">, read: ReadWidget) => {
  return role.done.some((value) => value === roleState(goal, role, read));
};

// The elements of the obligations waiting on the user that `goal` holds (`obligationsByRegion`)
// and owns itself: in its scope, under no nearer goal, and not a goal.
function interventions(goal: Element, open: Open) {
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

function stopped(entry: WorkEntry<"goal">, open: Open, read: ReadWidget): boolean {
  const { element: goal } = entry;
  let result = open.stopped.get(goal);
  if (result === undefined) {
    result = stoppedNow(entry, open, read);
    open.stopped.set(goal, result);
  }
  return result;
}
function stoppedNow(entry: WorkEntry<"goal">, open: Open, read: ReadWidget): boolean {
  const { element: goal, role } = entry;
  if (read(goal).thread.heldBy) return true;
  if (interventions(goal, open).length) return true;
  if (!role.stopped.some((value) => value === roleState(goal, role, read)))
    return false;
  if (open.asking.has(goal.id)) return true;
  const children = open.tree.childGoals.get(goal) ?? [];
  return children.length ? children.some((child) => stopped(child, open, read)) : true;
}

function goalView(
  entry: WorkEntry<"goal">,
  open: Open,
  workers: Map<Element, ReturnType<typeof workerView>>,
  read: ReadWidget,
) {
  const { element: goal, role } = entry;
  const leaves = open.tree.leaves(goal);
  const progressLeaves = leaves.length ? leaves : [entry];
  const liveWorkers = (open.tree.childWorkers.get(goal) ?? [])
    .map((worker) => workers.get(worker) as ReturnType<typeof workerView>)
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
export function readWork(element: Element) {
  const scope = workAncestor(element, "scope");
  const readings = new Map<Element, WidgetReading>();
  const read = (element: Element) => {
    let reading = readings.get(element);
    if (!reading) {
      reading = controllerOf(element).read();
      readings.set(element, reading);
    }
    return reading;
  };
  const obligations = openWidgetObligations();
  const tree = workTree(scope ?? authoredScope(element), scope);
  const open: Open = {
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
