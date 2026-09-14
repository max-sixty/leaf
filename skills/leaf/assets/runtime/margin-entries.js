/* The immutable public grammar and registry for controls contributed to a page target's
   margin.

   Contributors publish one complete frozen reading. Margin and Page Map independently
   render that reading; neither inspects, moves, or activates contributor-owned DOM. A
   registration owns the sole activation capability for its entries, so package commands
   and both projections invoke the same current action. Updating replaces the whole
   reading and stable identity is the registration plus entry key.

   Behavior, tone, rank, and interaction state are independent contributor axes. Reader
   selection and agent workflow are independent presentation fields. Ordering follows
   interaction state, then rank, contribution key, and entry key. Registration and DOM
   order never decide which unrelated action becomes primary. */

import { html, render } from "../vendor/browser-runtime.js";
import { layoutMarginRows } from "./margin-layout.js";
import { iconElement } from "./icons.js";
import { keeps, offer } from "./widget-elements.js";
import { agentWorkflowStage } from "./updates.js";
import { PRESS } from "./keyboard/bindings.js";
import { commandScope, keys, projectCommandScope } from "./keyboard/scopes.js";

const contributions = new Set();
const listeners = new Set();
const presented = new WeakMap();
const records = new WeakMap();
const controlContributions = new WeakMap();
const iconNodes = new WeakMap();
const contributorClasses = new WeakMap();
const entryRecords = new WeakSet();

export const MARGIN_ENTRY_SCHEMA = Object.freeze({
  tones: Object.freeze(["neutral", "positive", "negative"]),
  behaviors: Object.freeze(["action", "disclosure", "status"]),
  states: Object.freeze(["idle", "engaged", "busy", "failed"]),
  ranks: Object.freeze([
    "complete",
    "escape",
    "primary",
    "secondary",
    "reading",
    "overflow",
  ]),
});

const TONES = new Set(MARGIN_ENTRY_SCHEMA.tones);
const BEHAVIORS = new Set(MARGIN_ENTRY_SCHEMA.behaviors);
const STATES = new Set(MARGIN_ENTRY_SCHEMA.states);
const RANKS = new Set(MARGIN_ENTRY_SCHEMA.ranks);
const STATE_PRIORITY = new Map([
  ["failed", 0],
  ["busy", 1],
  ["engaged", 2],
  ["idle", 3],
]);
const RANK_PRIORITY = new Map([
  ["complete", 0],
  ["escape", 1],
  ["primary", 2],
  ["secondary", 3],
  ["reading", 4],
  ["overflow", 5],
]);

const ENTRY_OPTIONS = new Set([
  "key",
  "glyph",
  "icon",
  "label",
  "accessibleLabel",
  "staticLabel",
  "context",
  "description",
  "behavior",
  "tone",
  "rank",
  "state",
  "visible",
  "disabled",
  "count",
  "selected",
  "pressed",
  "workflowReceipt",
  "relation",
  "activation",
  "title",
  "className",
  "scope",
]);
const READING_OPTIONS = new Set([
  "subject",
  "state",
  "side",
  "claim",
  "reserve",
  "notice",
  "entries",
  "readings",
]);

const changed = () => {
  for (const listener of listeners) listener();
};

const text = (value) => String(value ?? "").trim();
const unknownOptions = (offered, allowed, kind) => {
  const unknown = Object.keys(offered).filter((key) => !allowed.has(key));
  if (unknown.length)
    throw new TypeError(`Unknown margin ${kind} option: ${unknown.sort().join(", ")}`);
};
const freezeRelation = (relation) => {
  if (relation == null) return null;
  if (typeof relation !== "object")
    throw new TypeError("A margin entry relation must be an object");
  if (relation.kind === "entries") {
    const keys = relation.keys?.map(text).filter(Boolean) ?? [];
    if (!keys.length)
      throw new TypeError("A margin entry relation needs at least one entry key");
    return Object.freeze({
      kind: "entries",
      keys: Object.freeze(keys),
      expanded: Boolean(relation.expanded),
    });
  }
  if (relation.kind === "element") {
    const id = text(relation.id);
    if (!id) throw new TypeError("A margin element relation needs an id");
    return Object.freeze({
      kind: "element",
      id,
      expanded: Boolean(relation.expanded),
      popup: relation.popup == null ? null : text(relation.popup),
    });
  }
  throw new TypeError(`Unknown margin entry relation: ${String(relation.kind)}`);
};

export function marginEntry(offered) {
  if (!offered || typeof offered !== "object")
    throw new TypeError("A margin entry needs an options object");
  unknownOptions(offered, ENTRY_OPTIONS, "entry");
  const {
    key,
    glyph = null,
    icon = null,
    label,
    accessibleLabel = null,
    staticLabel = null,
    context = null,
    description = null,
    behavior = "action",
    tone = "neutral",
    rank = "primary",
    state = "idle",
    visible = true,
    disabled = false,
    count = 1,
    selected = false,
    pressed = null,
    workflowReceipt = undefined,
    relation = null,
    activation = key,
    title = null,
    className = null,
    scope = null,
  } = offered;
  if (!text(key)) throw new TypeError("A margin entry needs a key");
  if (Boolean(text(glyph)) === Boolean(icon))
    throw new TypeError("A margin entry needs exactly one glyph or icon");
  if (!text(label)) throw new TypeError("A margin entry needs a label");
  if (!TONES.has(tone)) throw new TypeError(`Unknown margin entry tone: ${tone}`);
  if (!BEHAVIORS.has(behavior))
    throw new TypeError(`Unknown margin entry behavior: ${behavior}`);
  if (!RANKS.has(rank)) throw new TypeError(`Unknown margin entry rank: ${rank}`);
  if (!STATES.has(state)) throw new TypeError(`Unknown margin entry state: ${state}`);
  if (!Number.isSafeInteger(count) || count < 0)
    throw new TypeError("A margin entry count must be a non-negative integer");
  if (behavior !== "status" && !text(activation))
    throw new TypeError("An actionable margin entry needs an activation");
  const record = Object.freeze({
    key: text(key),
    glyph: glyph == null ? null : String(glyph),
    icon,
    label: text(label),
    accessibleLabel: text(accessibleLabel) || text(label),
    staticLabel: text(staticLabel) || null,
    context: text(context) || null,
    description: text(description) || null,
    behavior,
    tone,
    rank,
    state,
    visible: Boolean(visible),
    disabled: Boolean(disabled),
    count,
    selected: Boolean(selected),
    pressed: pressed == null ? null : Boolean(pressed),
    workflowReceipt,
    relation: freezeRelation(relation),
    activation: behavior === "status" ? null : text(activation),
    title: text(title) || null,
    className: text(className) || null,
    scope,
  });
  entryRecords.add(record);
  return record;
}

function normalizeReading(reading, owner) {
  if (!reading || typeof reading !== "object")
    throw new TypeError("A margin contribution must read an object");
  unknownOptions(reading, READING_OPTIONS, "contribution");
  const {
    subject = null,
    state = "idle",
    side = "before",
    claim = true,
    reserve = 0,
    notice = null,
    entries = [],
    readings = [],
  } = reading;
  if (!STATES.has(state))
    throw new TypeError(`Unknown margin contribution state: ${state}`);
  if (side !== "before" && side !== "after")
    throw new TypeError(`Unknown margin contribution side: ${side}`);
  if (!Number.isFinite(reserve) || reserve < 0)
    throw new TypeError("A margin contribution reserve must be non-negative");
  if (!Array.isArray(entries))
    throw new TypeError("A margin contribution's entries must be an array");
  if (!Array.isArray(readings))
    throw new TypeError("A margin contribution's readings must be an array");
  const keys = new Set();
  const normalizedEntries = entries.map((entry) => {
    const normalized = entryRecords.has(entry) ? entry : marginEntry(entry);
    if (keys.has(normalized.key))
      throw new TypeError(
        `Duplicate margin entry key "${normalized.key}" in margin contribution "${owner}"`,
      );
    keys.add(normalized.key);
    const owned = Object.freeze({ ...normalized, owner });
    entryRecords.add(owned);
    return owned;
  });
  const normalizedNotice =
    notice == null
      ? null
      : Object.freeze({
          text: text(notice.text),
          tone: text(notice.tone) || "negative",
        });
  return Object.freeze({
    subject: text(subject) || null,
    state,
    side,
    claim: Boolean(claim),
    reserve,
    notice: normalizedNotice,
    entries: Object.freeze(normalizedEntries),
    readings: Object.freeze(readings.map((item) => Object.freeze({ ...item }))),
  });
}

export const marginContributionEntries = () => contributions.values();
export const marginEntryStateRank = (state) => STATE_PRIORITY.get(state);
export const marginContributionState = (offered) => offered.reading.state;

export function compareMarginContributions(left, right) {
  const state =
    STATE_PRIORITY.get(left.reading.state) - STATE_PRIORITY.get(right.reading.state);
  return state || left.key.localeCompare(right.key);
}

export function compareMarginEntryRecords(left, right) {
  const state =
    STATE_PRIORITY.get(left.offered.reading.state) -
    STATE_PRIORITY.get(right.offered.reading.state);
  if (state) return state;
  const rank =
    RANK_PRIORITY.get(left.record.rank) - RANK_PRIORITY.get(right.record.rank);
  if (rank) return rank;
  const contribution = left.offered.key.localeCompare(right.offered.key);
  return contribution || left.record.key.localeCompare(right.record.key);
}

export function watchMarginContributions(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export const visibleMarginEntryLabel = ({ behavior, label }) =>
  behavior !== "disclosure" || label.endsWith("…") ? label : `${label}…`;

const marginEntryCommands = (control) =>
  commandScope(
    "On a margin entry",
    [
      {
        id: "margin.press",
        keys: PRESS,
        does: () =>
          records.get(control)?.behavior === "disclosure"
            ? "Open or close what the focused margin entry holds"
            : "Press the focused margin entry",
        line: () =>
          records.get(control)?.behavior === "disclosure" ? "open / close" : "press",
        run: () => control.click(),
      },
    ],
    {
      when: () => {
        const record = records.get(control);
        return Boolean(record && record.behavior !== "status" && !record.disabled);
      },
    },
  );

/** Create the stable semantic host for a generated margin entry.
 *
 * A contribution key plus entry key names one reader place even when its current
 * reading changes between an action and a status. A native button cannot shed its
 * button semantics, so projections retain this span and the shared presenter changes
 * its ARIA role, tab seat, and command capability in place.
 */
export function createMarginEntryControl(className = "") {
  const control = offer("span", className);
  keys(control, marginEntryCommands(control));
  return control;
}

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

export function syncMarginAgentWorkflow(control, receipt) {
  const workflowStage = agentWorkflowStage(receipt);
  const stage = ["picked_up", "working"].includes(workflowStage) ? workflowStage : null;
  syncAgentArrival(
    control,
    receipt && JSON.stringify([receipt.target.kind, receipt.target.id, receipt.id]),
    stage,
  );
  if (stage) {
    if (!agentWorkflowDescriptions.has(control))
      agentWorkflowDescriptions.set(control, {
        description: control.getAttribute("aria-description"),
        title: control.getAttribute("title"),
      });
    Object.assign(agentWorkflowDescriptions.get(control), {
      stage,
      detail: receipt.detail,
    });
    keeps(control, "data-lf-agent-workflow", stage);
    paintAgentDescription(control);
  } else {
    control.removeAttribute("data-lf-agent-workflow");
    if (agentWorkflowDescriptions.has(control)) {
      agentWorkflowDescriptions.get(control).stage = null;
      paintAgentDescription(control);
      agentWorkflowDescriptions.delete(control);
    }
  }
}

export function syncMarginEntrySelection(control, selected) {
  control.toggleAttribute("data-lf-target-selected", Boolean(selected));
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
  { writesRelation = true, writesSeat = true } = {},
) {
  if (!(control instanceof Element))
    throw new TypeError("A margin presentation needs an Element control");
  const record = entryRecords.has(offered) ? offered : marginEntry(offered);
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
  control.toggleAttribute("data-lf-target-selected", record.selected);
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
    else if (!relation) control.removeAttribute("aria-controls");
    if (relation?.popup) keeps(control, "aria-haspopup", relation.popup);
    else control.removeAttribute("aria-haspopup");
  }
  if (control instanceof HTMLButtonElement) {
    const wasStatus = control.getAttribute("role") === "status";
    control.removeAttribute("role");
    if (writesSeat && wasStatus) control.removeAttribute("tabindex");
    if (control.type !== "button") control.type = "button";
    // A pending action can be the reader's retained place even while it refuses a
    // second activation. Native disabled buttons cannot hold that place; the immutable
    // record and registration enforce refusal while aria exposes it to the reader.
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
  keeps(control, "aria-label", record.accessibleLabel);
  if (record.staticLabel) keeps(control, "data-lf-static-label", record.staticLabel);
  else control.removeAttribute("data-lf-static-label");
  if (record.description) keeps(control, "aria-description", record.description);
  else if (!agentWorkflowDescriptions.has(control))
    control.removeAttribute("aria-description");
  if (record.title) keeps(control, "title", record.title);
  else if (!agentWorkflowDescriptions.has(control)) control.removeAttribute("title");
  projectCommandScope(control, record.scope);
  return record;
}

export function presentMarginEntry(control, offered, options = {}) {
  const record = presentMarginEntryHost(control, offered, options);
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
  offered.reading = normalizeReading(read(), owner);
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
      offered.activate(current.activation, {
        ...context,
        entry: current,
        focus:
          context.focus ??
          ((key) =>
            control(key, context.surface ?? null, true)?.focus({
              preventScroll: true,
            })),
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
      offered.reading = normalizeReading(read(), owner);
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
