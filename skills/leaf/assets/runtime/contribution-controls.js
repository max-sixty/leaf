/* Shared contribution controls. Records carry no browser capabilities; this owner
   retains their command scopes and presented controls, independently of the renderer
   that seats them. Every projection uses this directory for control, focus and
   containment, so a producer updates one registration whichever surface shows it. */
import { html, render } from "../vendor/browser-runtime.js";
import { iconElement } from "./icons.js";
import { offer } from "./widget-elements.js";
import { keeps } from "./keeps.js";
import { reducedMotion } from "./motion.js";
import { isCommandScope, projectCommandScope } from "./keyboard/scopes.js";
import {
  isContributionEntry,
  contributionEntry as normalizeContributionEntry,
  normalizeContributionReading,
  visibleContributionEntryLabel,
} from "./contribution-model.js";
// Scopes belong to the browser declaration, not the immutable model record.
const commandScopes = new WeakMap();
// The key this module projects an entry's scope onto its control under.
const CONTRIBUTION_ENTRY = Symbol("contribution entry");
function bindScope(record, declared) {
  const scope = commandScopes.get(declared) ?? declared.scope;
  if (scope != null) {
    if (!isCommandScope(scope))
      throw new TypeError("A margin entry scope needs a commandScope capability");
    commandScopes.set(record, scope);
  }
  return record;
}

export function contributionEntry(offered) {
  return bindScope(normalizeContributionEntry(offered), offered);
}

export function normalizeReading(reading, owner) {
  const normalized = normalizeContributionReading(reading, owner);
  normalized.entries.forEach((entry, index) =>
    bindScope(entry, reading.entries[index]),
  );
  return normalized;
}

const presented = new WeakMap();
const records = new WeakMap();
const controlContributions = new WeakMap();
const iconNodes = new WeakMap();
const contributorClasses = new WeakMap();

/** Create the native host for one generated margin entry reading. */
export function createContributionControl(record, className = "") {
  return offer(record.behavior === "status" ? "span" : "button", className);
}

export const contributionControlMatches = (control, record) =>
  record.behavior === "status"
    ? control instanceof HTMLSpanElement
    : control instanceof HTMLButtonElement;

export function contributionEntryRecord(control) {
  const record = records.get(control);
  if (!record)
    throw new TypeError("A presented margin control needs a margin entry record");
  return record;
}

export function contributionEntrySource(control) {
  const offered = controlContributions.get(control);
  if (!offered) return null;
  return typeof offered.source === "function" ? offered.source() : offered.source;
}

// Agent workflow is projection state. One claim gets one shared arrival window so the
// independently rendered Margin and Page Map carriers join rather than replay its pulse.
const agentWorkflowDescriptions = new WeakMap();
const claimArrivals = new Map();
const controlArrivals = new WeakMap();
function agentWorkflowDescription(control) {
  let reading = agentWorkflowDescriptions.get(control);
  if (!reading) {
    reading = {
      description: control.getAttribute("aria-description"),
      title: control.getAttribute("title"),
      stage: null,
      detail: null,
    };
    agentWorkflowDescriptions.set(control, reading);
  }
  return reading;
}

function syncAgentArrival(control, claim, stage) {
  if (stage !== "working") {
    control.removeAttribute("data-lf-agent-arrival");
    return;
  }
  if (!claimArrivals.has(claim)) claimArrivals.set(claim, performance.now());
  const elapsed = performance.now() - claimArrivals.get(claim);
  if (controlArrivals.get(control) === claim) return;
  controlArrivals.set(control, claim);
  if (elapsed >= 520 || reducedMotion()) return;
  control.style.setProperty("--lf-agent-arrival-delay", `${-elapsed}ms`);
  keeps(control, "data-lf-agent-arrival", "1");
  control.addEventListener(
    "animationend",
    () => control.removeAttribute("data-lf-agent-arrival"),
    { once: true },
  );
}

function paintAgentDescription(control) {
  const reading = agentWorkflowDescriptions.get(control);
  if (!reading) {
    control.removeAttribute("aria-description");
    control.removeAttribute("title");
    return;
  }
  if (!reading.stage) {
    for (const [attribute, value] of [
      ["aria-description", reading.description],
      ["title", reading.title],
    ]) {
      keeps(control, attribute, value);
    }
    return;
  }
  const work = [reading.stage === "working" ? "Working" : "Picked up", reading.detail]
    .filter(Boolean)
    .join(" · ");
  const record = records.get(control);
  keeps(
    control,
    "aria-description",
    [reading.description, work].filter(Boolean).join(" · "),
  );
  keeps(
    control,
    "title",
    [
      record?.title ?? record?.label,
      reading.title !== (record?.title ?? record?.label) && reading.title,
      work,
    ]
      .filter(Boolean)
      .join(" · "),
  );
}

function syncAgentDescriptionBase(control, description, title) {
  Object.assign(agentWorkflowDescription(control), { description, title });
  paintAgentDescription(control);
}

export function syncContributionAgentWorkflow(control, receipt) {
  const workflowStage = receipt?.stage ?? null;
  const stage = workflowStage === "replying" ? "working" : workflowStage;
  const paintedStage =
    !receipt?.condition && ["picked_up", "working"].includes(stage) ? stage : null;
  syncAgentArrival(
    control,
    receipt && JSON.stringify([receipt.subject.kind, receipt.subject.id, receipt.id]),
    paintedStage,
  );
  const reading = agentWorkflowDescription(control);
  keeps(control, "data-lf-agent-workflow", paintedStage || null);
  Object.assign(
    reading,
    paintedStage
      ? { stage: paintedStage, detail: receipt.detail }
      : { stage: null, detail: null },
  );
  paintAgentDescription(control);
}

export function syncContributionSelection(control, selected) {
  control.toggleAttribute("data-lf-target-selected", Boolean(selected));
}

// Whose word a reading is waiting on. Projection state like agent workflow, and written
// the same way: the projection decides it, both surfaces paint the same attribute, and a
// carrier that stops waiting loses it rather than keeping a stale colour. Only the
// user's turn is named, because that is the one a page has to point at; a thread with
// the agent already says so through pickup and work.
export function syncContributionTurn(control, awaitsUser) {
  keeps(control, "data-lf-turn", awaitsUser ? "user" : null);
}

// Whether a reading carries agent content the user has not taken in: the same
// Thread `unread` the panel and banner paint, as one attribute both surfaces share.
export function syncContributionUnread(control, count) {
  control.toggleAttribute("data-lf-unread", Boolean(count));
}

function iconFor(control, icon) {
  if (!icon) return null;
  let node = iconNodes.get(control);
  if (!node || node.dataset.lfIcon !== icon) {
    node = iconElement(icon);
    iconNodes.set(control, node);
  }
  return node;
}

export function presentContributionHost(
  control,
  offered,
  {
    accessibleLabel = null,
    relatedControlIds = [],
    writesRelation = true,
    writesSeat = true,
  } = {},
) {
  if (!(control instanceof Element))
    throw new TypeError("A margin presentation needs an Element control");
  const record = isContributionEntry(offered) ? offered : contributionEntry(offered);
  if (control instanceof HTMLButtonElement && record.behavior === "status")
    throw new TypeError("A status margin entry needs a stable span host");
  records.set(control, record);
  keeps(control, "data-lf-margin-entry-key", record.key);
  keeps(control, "data-lf-margin-entry-owner", record.owner || null);
  keeps(control, "data-lf-behavior", record.behavior);
  keeps(control, "data-lf-tone", record.tone);
  keeps(control, "data-lf-rank", record.rank);
  keeps(control, "data-lf-state", record.state);
  keeps(control, "data-lf-offer", record.behavior === "status" ? "" : "button");
  keeps(control, "aria-pressed", record.pressed);
  keeps(control, "aria-busy", record.state === "busy" ? "true" : null);
  const relation = record.relation;
  if (writesRelation) {
    keeps(
      control,
      "aria-expanded",
      record.behavior === "disclosure" ? (relation?.expanded ?? false) : null,
    );
    keeps(
      control,
      "aria-controls",
      relation?.kind === "element"
        ? relation.id
        : relation?.kind === "entries" && relatedControlIds.length
          ? relatedControlIds.join(" ")
          : null,
    );
    keeps(control, "aria-haspopup", relation?.popup || null);
  }
  if (control instanceof HTMLButtonElement) {
    const wasStatus = control.getAttribute("role") === "status";
    control.removeAttribute("role");
    if (writesSeat && wasStatus) control.removeAttribute("tabindex");
    if (control.type !== "button") control.type = "button";
    // A pending action can be the user's retained place even while it refuses a
    // second activation. Native disabled buttons cannot hold that place; the immutable
    // record and registration enforce refusal while aria exposes it to the user.
    if (control.disabled) control.disabled = false;
    keeps(control, "aria-disabled", record.disabled);
  } else if (record.behavior === "status") {
    keeps(control, "role", "status");
    control.removeAttribute("aria-disabled");
    if (writesSeat) keeps(control, "tabindex", -1);
  } else {
    keeps(control, "role", "button");
    keeps(control, "aria-disabled", record.disabled);
    if (writesSeat && control.tabIndex < 0) control.tabIndex = 0;
  }
  keeps(control, "aria-label", accessibleLabel ?? record.accessibleLabel);
  syncAgentDescriptionBase(control, record.description || null, record.title || null);
  projectCommandScope(control, CONTRIBUTION_ENTRY, commandScopes.get(record));
  return record;
}

export function presentContributionEntry(control, offered, options = {}) {
  const record = presentContributionHost(control, offered, options);
  if (Object.hasOwn(options, "selected"))
    syncContributionSelection(control, options.selected);
  control.classList.toggle("lf-margin-entry", true);
  const priorClasses = contributorClasses.get(control) ?? [];
  const nextClasses = record.className?.split(/\s+/).filter(Boolean) ?? [];
  for (const name of priorClasses)
    if (!nextClasses.includes(name)) control.classList.toggle(name, false);
  for (const name of nextClasses) control.classList.toggle(name, true);
  contributorClasses.set(control, nextClasses);
  const visibleLabel = visibleContributionEntryLabel(record);
  const glyph = record.icon
    ? iconFor(control, record.icon)
    : html`<span class="lf-margin-entry-glyph" aria-hidden="true"
        >${record.glyph}</span
      >`;
  render(
    html`${glyph}<span class="lf-margin-entry-space" aria-hidden="true"> </span
      ><span class="lf-margin-entry-label" aria-hidden="true"
        ><span class="lf-margin-entry-label-word">${visibleLabel}</span>${
          record.context
            ? html`<span class="lf-margin-entry-context">${record.context}</span>`
            : null
        }</span
      >${
        record.count > 1
          ? html`<span class="lf-margin-count" aria-hidden="true"
              >${record.count}</span
            >`
          : null
      }`,
    control,
  );
  if (record.workflowReceipt !== undefined)
    syncContributionAgentWorkflow(control, record.workflowReceipt);
  return control;
}

export function trackContributionControl(offered, surface, key, control) {
  controlContributions.set(control, offered);
  let surfaces = presented.get(offered);
  if (!surfaces) {
    surfaces = new Map();
    presented.set(offered, surfaces);
  }
  let controls = surfaces.get(surface);
  if (!controls) {
    controls = new Map();
    surfaces.set(surface, controls);
  }
  controls.set(key, control);
}

export function clearContributionControls(offered, surface, liveKeys) {
  const controls = presented.get(offered)?.get(surface);
  if (!controls) return;
  for (const key of controls.keys()) if (!liveKeys.has(key)) controls.delete(key);
}

export function contributionControl(
  offered,
  entryKey,
  surface = null,
  visible = false,
) {
  const surfaces = presented.get(offered);
  for (const name of surface ? [surface] : ["margin", "map", "inline"]) {
    const control = surfaces?.get(name)?.get(entryKey);
    if (control?.isConnected && (!visible || control.checkVisibility())) return control;
  }
  return null;
}

export function contributionContains(offered, node) {
  if (!(node instanceof Node)) return false;
  return [...(presented.get(offered)?.values() ?? [])].some((controls) =>
    [...controls.values()].some(
      (control) => control === node || control.contains(node),
    ),
  );
}

export function forgetContributionControls(offered) {
  presented.delete(offered);
}
