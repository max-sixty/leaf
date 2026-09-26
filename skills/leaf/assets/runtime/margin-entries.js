/* The immutable public grammar and registry for controls contributed to a page target's
   margin.

   Contributors publish one complete frozen reading. Margin and Page Map independently
   render that reading; neither inspects, moves, or activates contributor-owned DOM. A
   registration owns the sole activation capability for its entries, so package commands
   and both projections invoke the same current action. Updating replaces the whole
   reading and stable identity is the registration plus entry key.

   Behavior, tone, rank, and interaction state are independent contributor axes. User
   selection, agent workflow, and whose turn a reading waits on are independent
   presentation fields, written by the projection rather than declared. Ordering follows
   interaction state, then rank, contribution key, and entry key. Registration and DOM
   order never decide which unrelated action becomes primary. */

import { html, render } from "../vendor/browser-runtime.js";
import { layoutMarginRows } from "./margin-layout.js";
import { iconElement } from "./icons.js";
import { keeps, offer } from "./widget-elements.js";
import { focused, isCommandScope, projectCommandScope } from "./keyboard/scopes.js";

import {
  isMarginEntry,
  marginEntry as normalizeMarginEntry,
  normalizeMarginReading,
  visibleMarginEntryLabel,
} from "./margin-entry-model.js";
export {
  MARGIN_ENTRY_SCHEMA,
  compareMarginContributions,
  compareMarginEntryRecords,
  marginContributionState,
  marginEntryStateRank,
  visibleMarginEntryLabel,
} from "./margin-entry-model.js";

const text = (value) => String(value ?? "").trim();
// Scopes belong to the browser declaration, not the immutable model record.
const commandScopes = new WeakMap();
// The key this module projects an entry's scope onto its control under.
const MARGIN_ENTRY = Symbol("margin entry");
function bindScope(record, declared) {
  const scope = commandScopes.get(declared) ?? declared.scope;
  if (scope != null) {
    if (!isCommandScope(scope))
      throw new TypeError("A margin entry scope needs a commandScope capability");
    commandScopes.set(record, scope);
  }
  return record;
}

export function marginEntry(offered) {
  return bindScope(normalizeMarginEntry(offered), offered);
}

function normalizeReading(reading, owner) {
  const normalized = normalizeMarginReading(reading, owner);
  normalized.entries.forEach((entry, index) =>
    bindScope(entry, reading.entries[index]),
  );
  return normalized;
}

// A registration publishes its data once per update. Both projections use those
// same records; only this registry resolves their live activation capability.
const contributionSources = new WeakMap();
export const marginContributionSource = (model) => contributionSources.get(model);
function publishReading(offered) {
  offered.reading = normalizeReading(offered.read(), offered.key);
  const { readings, ...reading } = offered.reading;
  offered.model = Object.freeze({
    key: offered.key,
    reading: Object.freeze({ ...reading, hasReadings: readings.length > 0 }),
  });
  contributionSources.set(offered.model, offered);
}

const contributions = new Set();
const listeners = new Set();
const presented = new WeakMap();
const records = new WeakMap();
const controlContributions = new WeakMap();
const iconNodes = new WeakMap();
const contributorClasses = new WeakMap();

const changed = () => {
  for (const listener of listeners) listener();
};

export const marginContributionEntries = () => contributions.values();
export function watchMarginContributions(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Create the native host for one generated margin entry reading. */
export function createMarginEntryControl(record, className = "") {
  return offer(record.behavior === "status" ? "span" : "button", className);
}

export const marginEntryControlMatches = (control, record) =>
  record.behavior === "status"
    ? control instanceof HTMLSpanElement
    : control instanceof HTMLButtonElement;

export function marginEntryRecord(control) {
  const record = records.get(control);
  if (!record)
    throw new TypeError("A presented margin control needs a margin entry record");
  return record;
}

export function marginEntrySource(control) {
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
  if (elapsed >= 520 || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
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
      if (value === null) control.removeAttribute(attribute);
      else keeps(control, attribute, value);
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

export function syncMarginAgentWorkflow(control, receipt) {
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
  if (paintedStage) {
    Object.assign(reading, { stage: paintedStage, detail: receipt.detail });
    keeps(control, "data-lf-agent-workflow", paintedStage);
  } else {
    control.removeAttribute("data-lf-agent-workflow");
    Object.assign(reading, { stage: null, detail: null });
  }
  paintAgentDescription(control);
}

export function syncMarginEntrySelection(control, selected) {
  control.toggleAttribute("data-lf-target-selected", Boolean(selected));
}

// Whose word a reading is waiting on. Projection state like agent workflow, and written
// the same way: the projection decides it, both surfaces paint the same attribute, and a
// carrier that stops waiting loses it rather than keeping a stale colour. Only the
// user's turn is named, because that is the one a page has to point at; a thread with
// the agent already says so through pickup and work.
export function syncMarginTurn(control, awaitsUser) {
  if (awaitsUser) keeps(control, "data-lf-turn", "user");
  else control.removeAttribute("data-lf-turn");
}

// Whether a reading carries agent content the user has not taken in: the same
// Thread `unread` the panel and banner paint, as one attribute both surfaces share.
export function syncMarginUnread(control, count) {
  if (count) keeps(control, "data-lf-unread", "");
  else control.removeAttribute("data-lf-unread");
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

export function presentMarginEntryHost(
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
  const record = isMarginEntry(offered) ? offered : marginEntry(offered);
  if (control instanceof HTMLButtonElement && record.behavior === "status")
    throw new TypeError("A status margin entry needs a stable span host");
  records.set(control, record);
  keeps(control, "data-lf-margin-entry-key", record.key);
  if (record.owner) keeps(control, "data-lf-margin-entry-owner", record.owner);
  else control.removeAttribute("data-lf-margin-entry-owner");
  keeps(control, "data-lf-behavior", record.behavior);
  keeps(control, "data-lf-tone", record.tone);
  keeps(control, "data-lf-rank", record.rank);
  keeps(control, "data-lf-state", record.state);
  keeps(control, "data-lf-offer", record.behavior === "status" ? "" : "button");
  if (record.pressed == null) control.removeAttribute("aria-pressed");
  else keeps(control, "aria-pressed", record.pressed);
  if (record.state === "busy") {
    keeps(control, "aria-busy", "true");
  } else {
    control.removeAttribute("aria-busy");
  }
  const relation = record.relation;
  if (writesRelation) {
    if (record.behavior === "disclosure")
      keeps(control, "aria-expanded", relation?.expanded ?? false);
    else control.removeAttribute("aria-expanded");
    if (relation?.kind === "element") keeps(control, "aria-controls", relation.id);
    else if (relation?.kind === "entries" && relatedControlIds.length)
      keeps(control, "aria-controls", relatedControlIds.join(" "));
    else control.removeAttribute("aria-controls");
    if (relation?.popup) keeps(control, "aria-haspopup", relation.popup);
    else control.removeAttribute("aria-haspopup");
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
  projectCommandScope(control, MARGIN_ENTRY, commandScopes.get(record));
  return record;
}

export function presentMarginEntry(control, offered, options = {}) {
  const record = presentMarginEntryHost(control, offered, options);
  if (Object.hasOwn(options, "selected"))
    syncMarginEntrySelection(control, options.selected);
  if (!control.classList.contains("lf-margin-entry"))
    control.classList.add("lf-margin-entry");
  const priorClasses = contributorClasses.get(control) ?? [];
  const nextClasses = record.className?.split(/\s+/).filter(Boolean) ?? [];
  if (
    priorClasses.length !== nextClasses.length ||
    priorClasses.some((name, index) => name !== nextClasses[index])
  ) {
    control.classList.remove(...priorClasses);
    if (nextClasses.length) control.classList.add(...nextClasses);
  }
  contributorClasses.set(control, nextClasses);
  const visibleLabel = visibleMarginEntryLabel(record);
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
    syncMarginAgentWorkflow(control, record.workflowReceipt);
  return control;
}

export function trackMarginEntryControl(offered, surface, key, control) {
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

export function clearMarginEntryControls(offered, surface, liveKeys) {
  const controls = presented.get(offered)?.get(surface);
  if (!controls) return;
  for (const key of controls.keys()) if (!liveKeys.has(key)) controls.delete(key);
}

export function registerMarginContribution({
  key,
  target,
  source = target,
  read,
  activate,
}) {
  const owner = text(key);
  if (!owner) throw new TypeError("A margin contribution needs a key");
  if (typeof read !== "function")
    throw new TypeError("A margin contribution needs a read function");
  if (typeof activate !== "function")
    throw new TypeError("A margin contribution needs an activate function");
  const offered = { key: owner, target, source, read, activate, reading: null };
  publishReading(offered);
  contributions.add(offered);
  changed();

  const entry = (entryKey) =>
    offered.reading.entries.find((candidate) => candidate.key === entryKey) ?? null;
  const control = (entryKey, surface = null, visible = false) => {
    const surfaces = presented.get(offered);
    const preferred = surface ? [surface] : ["margin", "map", "inline"];
    for (const name of preferred) {
      const candidate = surfaces?.get(name)?.get(entryKey);
      if (candidate?.isConnected && (!visible || candidate.checkVisibility()))
        return candidate;
    }
    return null;
  };
  const registration = Object.freeze({
    entry(entryKey) {
      return entry(text(entryKey));
    },
    control,
    contains(node) {
      if (!(node instanceof Node)) return false;
      const surfaces = presented.get(offered);
      return [...(surfaces?.values() ?? [])].some((controls) =>
        [...controls.values()].some(
          (candidate) => candidate === node || candidate.contains(node),
        ),
      );
    },
    activate(entryKey, context = {}) {
      const current = entry(text(entryKey));
      if (
        !current ||
        !current.visible ||
        current.disabled ||
        current.behavior === "status"
      )
        return false;
      const originOwnsFocus = context.origin == null || context.origin === focused();
      const focusCurrentSurface =
        context.focus ??
        ((key) => {
          const destination = control(key, context.surface ?? null, true);
          if (!destination) return false;
          destination.focus({ preventScroll: true });
          return true;
        });
      offered.activate(current.activation, {
        ...context,
        entry: current,
        focus: originOwnsFocus ? focusCurrentSurface : () => false,
      });
      return true;
    },
    focus(entryKey, surface = null) {
      const destination = control(text(entryKey), surface, true);
      if (!destination) return false;
      destination.focus({ preventScroll: true });
      return true;
    },
    update({ immediate = false, focus = null } = {}) {
      publishReading(offered);
      changed();
      if (immediate) layoutMarginRows();
      if (focus != null) registration.focus(focus);
    },
    unregister() {
      if (!contributions.delete(offered)) return;
      presented.delete(offered);
      changed();
    },
  });
  offered.registration = registration;
  return registration;
}
