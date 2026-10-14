import {
  dismissBannerControls,
  scrollIntoView
} from "./bundle-chrome.js";
import {
  agentArrivalDuration,
  reducedMotion
} from "./bundle-motion.js";
import {
  excerptWords
} from "./bundle-passage-facts.js";
import {
  closeNativeLayer,
  commandAvailable,
  commandBinding,
  commandRoutes,
  controlAvailabilityOutput,
  el,
  elementDirective,
  iconElement,
  isCommandScope,
  offer,
  pressIsKeyboardActivation,
  projectCommandScope,
  watchCommandAvailability
} from "./bundle-page-paint.js";
import {
  afterScript,
  canPlaceFocus,
  focusDestination,
  focused,
  inputCount,
  isNativeLayer,
  keeps
} from "./bundle-sample-visibility.js";
import {
  html,
  nothing,
  render,
  repeat
} from "./bundle-queued-work.js";

// runtime/contribution-model.js
var entryRecords = /* @__PURE__ */ new WeakSet();
var isContributionEntry = (entry) => entryRecords.has(entry);
var CONTRIBUTION_ENTRY_SCHEMA = Object.freeze({
  tones: Object.freeze(["neutral", "positive", "negative"]),
  behaviors: Object.freeze(["action", "disclosure", "status"]),
  states: Object.freeze(["idle", "engaged", "busy", "failed"]),
  ranks: Object.freeze([
    "complete",
    "escape",
    "primary",
    "secondary",
    "reading",
    "overflow"
  ])
});
var TONES = new Set(CONTRIBUTION_ENTRY_SCHEMA.tones);
var BEHAVIORS = new Set(CONTRIBUTION_ENTRY_SCHEMA.behaviors);
var STATES = new Set(CONTRIBUTION_ENTRY_SCHEMA.states);
var RANKS = new Set(CONTRIBUTION_ENTRY_SCHEMA.ranks);
var STATE_PRIORITY = /* @__PURE__ */ new Map([
  ["failed", 0],
  ["busy", 1],
  ["engaged", 2],
  ["idle", 3]
]);
var RANK_PRIORITY = /* @__PURE__ */ new Map([
  ["complete", 0],
  ["escape", 1],
  ["primary", 2],
  ["secondary", 3],
  ["reading", 4],
  ["overflow", 5]
]);
var ENTRY_OPTIONS = /* @__PURE__ */ new Set([
  "key",
  "glyph",
  "icon",
  "label",
  "accessibleLabel",
  "context",
  "description",
  "behavior",
  "tone",
  "rank",
  "state",
  "visible",
  "disabled",
  "count",
  "pressed",
  "workflowReceipt",
  "relation",
  "activation",
  "title",
  "className",
  "scope"
]);
var KINDS = Object.freeze(
  Object.fromEntries(
    Object.entries({
      action: { label: "Action", icon: "dot", priority: -1 },
      change: { label: "Change", icon: "change", priority: 0 },
      restated: {
        label: "Rewritten",
        icon: "change",
        priority: 0,
        indication: true
      },
      comment: { label: "Thread", icon: "comment", priority: 1 },
      ask: { label: "Ask", icon: "question", priority: 2 },
      sent: {
        label: "Sent",
        icon: "sent",
        priority: 3,
        indication: true
      },
      queued: {
        label: "Queued",
        icon: "pickup",
        priority: 3,
        indication: true
      },
      pickup: {
        label: "Picked up",
        icon: "pickup",
        priority: 3,
        indication: true
      },
      // Every receipt whose progress stopped short: one past the pickup grace, one
      // whose turn ended or went quiet, one the harness failed. A single receipt reads
      // under its own label; this names a group of them.
      waiting: {
        label: "Stalled update",
        icon: "waiting",
        priority: 3,
        indication: true
      },
      user: {
        label: "My change",
        icon: "change",
        priority: 4,
        indication: true
      },
      reported: {
        label: "Reported state",
        icon: "activity",
        priority: 4,
        indication: true
      },
      activity: { label: "Working", icon: "activity", priority: 4 }
    }).map(([kind, face]) => [kind, Object.freeze(face)])
  )
);
var READING_OPTIONS = /* @__PURE__ */ new Set([
  "kind",
  "subject",
  "state",
  "side",
  "notice",
  "entries",
  "readings"
]);
var text = (value) => String(value ?? "").trim();
var unknownOptions = (offered, allowed, kind) => {
  const unknown = Object.keys(offered).filter((key) => !allowed.has(key));
  if (unknown.length)
    throw new TypeError(
      `Unknown contribution ${kind} option: ${unknown.sort().join(", ")}`
    );
};
var freezeRelation = (relation) => {
  if (relation == null) return null;
  if (relation.kind === "entries") {
    const keys = relation.keys?.map(text).filter(Boolean) ?? [];
    if (!keys.length)
      throw new TypeError("A contribution entry relation needs at least one entry key");
    return Object.freeze({
      kind: "entries",
      keys: Object.freeze(keys),
      expanded: Boolean(relation.expanded)
    });
  }
  if (relation.kind === "element") {
    const id = text(relation.id);
    if (!id) throw new TypeError("A margin element relation needs an id");
    return Object.freeze({
      kind: "element",
      id,
      expanded: Boolean(relation.expanded),
      popup: relation.popup == null ? null : text(relation.popup)
    });
  }
  throw new TypeError(`Unknown contribution entry relation: ${String(relation.kind)}`);
};
function contributionEntry(offered) {
  unknownOptions(offered, ENTRY_OPTIONS, "entry");
  const {
    key,
    glyph = null,
    icon = null,
    label,
    accessibleLabel = null,
    context = null,
    description = null,
    behavior = "action",
    tone = "neutral",
    rank = "primary",
    state = "idle",
    visible = true,
    disabled = false,
    count = 1,
    pressed = null,
    workflowReceipt = void 0,
    relation = null,
    activation = key,
    title = null,
    className = null,
    scope = null
  } = offered;
  if (!text(key)) throw new TypeError("A contribution entry needs a key");
  if (Boolean(text(glyph)) === Boolean(icon))
    throw new TypeError("A contribution entry needs exactly one glyph or icon");
  if (!text(label)) throw new TypeError("A contribution entry needs a label");
  if (!TONES.has(tone)) throw new TypeError(`Unknown contribution entry tone: ${tone}`);
  if (!BEHAVIORS.has(behavior))
    throw new TypeError(`Unknown contribution entry behavior: ${behavior}`);
  if (!RANKS.has(rank)) throw new TypeError(`Unknown contribution entry rank: ${rank}`);
  if (!STATES.has(state))
    throw new TypeError(`Unknown contribution entry state: ${state}`);
  if (!Number.isSafeInteger(count) || count < 0)
    throw new TypeError("A contribution entry count must be a non-negative integer");
  if (behavior !== "status" && !text(activation))
    throw new TypeError("An actionable contribution entry needs an activation");
  if (behavior === "status" && scope != null)
    throw new TypeError("A status contribution entry cannot have a command scope");
  const record = Object.freeze({
    key: text(key),
    glyph: glyph == null ? null : String(glyph),
    icon,
    label: text(label),
    accessibleLabel: text(accessibleLabel) || text(label),
    context: text(context) || null,
    description: text(description) || null,
    behavior,
    tone,
    rank,
    state,
    visible: Boolean(visible),
    disabled: Boolean(disabled),
    count,
    pressed: pressed == null ? null : Boolean(pressed),
    workflowReceipt,
    relation: freezeRelation(relation),
    activation: behavior === "status" ? null : text(activation),
    title: text(title) || null,
    className: text(className) || null
  });
  entryRecords.add(record);
  return record;
}
function normalizeContributionReading(reading, owner) {
  unknownOptions(reading, READING_OPTIONS, "contribution");
  const {
    kind = null,
    subject = null,
    state = "idle",
    side = "before",
    notice = null,
    entries = [],
    readings = []
  } = reading;
  if (!STATES.has(state)) throw new TypeError(`Unknown contribution state: ${state}`);
  if (kind != null && !Object.hasOwn(KINDS, kind))
    throw new TypeError(
      `Unknown contribution kind "${kind}" in contribution "${owner}"`
    );
  if (side !== "before" && side !== "after")
    throw new TypeError(`Unknown contribution side: ${side}`);
  const keys = /* @__PURE__ */ new Set();
  const normalizedEntries = entries.map((entry) => {
    const normalized = entryRecords.has(entry) ? entry : contributionEntry(entry);
    if (keys.has(normalized.key))
      throw new TypeError(
        `Duplicate contribution entry key "${normalized.key}" in contribution "${owner}"`
      );
    keys.add(normalized.key);
    const owned = Object.freeze({ ...normalized, owner });
    entryRecords.add(owned);
    return owned;
  });
  const ids = /* @__PURE__ */ new Set();
  for (const item of readings) {
    if (typeof item.id !== "string" || !item.id.trim() || ids.has(item.id))
      throw new TypeError(
        `Contribution reading IDs must be nonempty and unique in contribution "${owner}"`
      );
    ids.add(item.id);
  }
  const normalizedNotice = notice == null ? null : Object.freeze({
    text: text(notice.text),
    tone: text(notice.tone) || "negative"
  });
  return Object.freeze({
    kind: text(kind) || null,
    subject: text(subject) || null,
    state,
    side,
    notice: normalizedNotice,
    entries: Object.freeze(normalizedEntries),
    readings: Object.freeze(
      readings.map(({ activate, ...item }) => Object.freeze(item))
    )
  });
}
var contributionEntryStateRank = (state) => STATE_PRIORITY.get(state);
var contributionState = (offered) => offered.reading.state;
function compareContributions(left, right) {
  const state = STATE_PRIORITY.get(left.reading.state) - STATE_PRIORITY.get(right.reading.state);
  return state || left.key.localeCompare(right.key);
}
function compareContributionEntryRecords(left, right) {
  const state = STATE_PRIORITY.get(left.offered.reading.state) - STATE_PRIORITY.get(right.offered.reading.state);
  if (state) return state;
  const rank = RANK_PRIORITY.get(left.record.rank) - RANK_PRIORITY.get(right.record.rank);
  if (rank) return rank;
  const contribution = left.offered.key.localeCompare(right.offered.key);
  return contribution || left.record.key.localeCompare(right.record.key);
}
var visibleContributionEntryLabel = ({ behavior, label }) => behavior !== "disclosure" || /[…?]$/.test(label) ? label : `${label}\u2026`;
var contributionItemKey = (item) => JSON.stringify([item.owner ?? null, item.id]);
var SPOKEN_SUBJECT_CAP = 120;
var spokenSubject = (value) => excerptWords(value, SPOKEN_SUBJECT_CAP);

// runtime/contribution-controls.js
var commandScopes = /* @__PURE__ */ new WeakMap();
var commandEntries = /* @__PURE__ */ new WeakSet();
var contributionOwnsCommand = (record) => commandEntries.has(record);
var CONTRIBUTION_ENTRY = /* @__PURE__ */ Symbol("contribution entry");
function bindScope(record, declared) {
  const scope = commandScopes.get(declared) ?? declared.scope;
  if (scope != null) commandScopes.set(record, scope);
  if (contributionOwnsCommand(declared)) commandEntries.add(record);
  return record;
}
function contributionEntry2(offered) {
  const scope = commandScopes.get(offered) ?? offered.scope;
  if (scope != null && !isCommandScope(scope))
    throw new TypeError("A margin entry scope needs a commandScope capability");
  const command = entryCommand(scope, offered.activation);
  if (command) commandEntries.add(offered);
  return bindScope(
    contributionEntry(
      contributionOwnsCommand(offered) ? {
        ...offered,
        disabled: commandDisabled(scope, command)
      } : offered
    ),
    offered
  );
}
function contributionCommand(record) {
  if (!contributionOwnsCommand(record)) return null;
  const scope = commandScopes.get(record);
  return entryCommand(scope, record.activation);
}
function contributionCommandDisabled(record) {
  const scope = commandScopes.get(record);
  const command = contributionCommand(record);
  return contributionOwnsCommand(record) && commandDisabled(scope, command);
}
var commandDisabled = (scope, command) => Boolean(
  !command || scope.scope.when && !scope.scope.when() || !commandAvailable(command.row, command.route)
);
function entryCommand(scope, id) {
  for (const row of scope?.scope.rows ?? []) {
    if (!row.run) continue;
    const routes = commandRoutes(row);
    if (!routes.length && row.id === id)
      return { row, route: null, binding: commandBinding(row) };
    const route = routes.find((route2) => route2.id === id);
    if (route) return { row, route, binding: commandBinding(row, route) };
  }
  return null;
}
function normalizeReading(reading, owner, previous = null) {
  const priorEntries = new Map(
    (previous?.entries ?? []).map((entry) => [entry.key, entry])
  );
  const entries = (reading.entries ?? []).map((entry) => {
    const prior = priorEntries.get(entry.key);
    if (contributionOwnsCommand(prior) && entry.activation === prior.activation && (commandScopes.get(entry) ?? entry.scope) === commandScopes.get(prior))
      commandEntries.add(entry);
    if (!isContributionEntry(entry)) return contributionEntry2(entry);
    if (!contributionOwnsCommand(entry)) return entry;
    const { owner: _owner, ...fields } = entry;
    const declaration = { ...fields, scope: commandScopes.get(entry) };
    commandEntries.add(declaration);
    return contributionEntry2(declaration);
  });
  const normalized = normalizeContributionReading({ ...reading, entries }, owner);
  normalized.entries.forEach((entry, index) => bindScope(entry, entries[index]));
  return normalized;
}
var contributionControls = /* @__PURE__ */ new WeakMap();
var relationOrdinal = 0;
var presented = /* @__PURE__ */ new WeakMap();
var records = /* @__PURE__ */ new WeakMap();
var controlContributions = /* @__PURE__ */ new WeakMap();
var iconNodes = /* @__PURE__ */ new WeakMap();
var contributorClasses = /* @__PURE__ */ new WeakMap();
function createContributionControl(record, className = "") {
  return offer(record.behavior === "status" ? "span" : "button", className);
}
var contributionControlMatches = (control, record) => record.behavior === "status" ? control instanceof HTMLSpanElement : control instanceof HTMLButtonElement;
function contributionEntryRecord(control) {
  const record = records.get(control);
  if (!record)
    throw new TypeError("A presented margin control needs a margin entry record");
  return record;
}
function contributionControlKey(control) {
  const { owner, key } = contributionEntryRecord(control);
  return JSON.stringify([owner, key]);
}
function contributionEntrySource(control) {
  const offered = controlContributions.get(control);
  if (!offered) return null;
  return offered.source();
}
var agentWorkflowDescriptions = /* @__PURE__ */ new WeakMap();
var claimArrivals = /* @__PURE__ */ new Map();
var controlArrivals = /* @__PURE__ */ new WeakMap();
function agentWorkflowDescription(control) {
  let reading = agentWorkflowDescriptions.get(control);
  if (!reading) {
    reading = {
      description: control.getAttribute("aria-description"),
      title: control.getAttribute("title"),
      stage: null,
      detail: null
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
  if (elapsed >= agentArrivalDuration() || reducedMotion()) return;
  control.style.setProperty("--lf-agent-arrival-delay", `${-elapsed}ms`);
  keeps(control, "data-lf-agent-arrival", "1");
  control.addEventListener(
    "animationend",
    () => control.removeAttribute("data-lf-agent-arrival"),
    { once: true }
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
      ["title", reading.title]
    ]) {
      keeps(control, attribute, value);
    }
    return;
  }
  const work = [reading.stage === "working" ? "Working" : "Picked up", reading.detail].filter(Boolean).join(" \xB7 ");
  const record = records.get(control);
  keeps(
    control,
    "aria-description",
    [reading.description, work].filter(Boolean).join(" \xB7 ")
  );
  keeps(
    control,
    "title",
    [
      record?.title ?? record?.label,
      reading.title !== (record?.title ?? record?.label) && reading.title,
      work
    ].filter(Boolean).join(" \xB7 ")
  );
}
function syncAgentDescriptionBase(control, description, title) {
  Object.assign(agentWorkflowDescription(control), { description, title });
  paintAgentDescription(control);
}
function syncContributionAgentWorkflow(control, receipt) {
  const workflowStage = receipt?.stage ?? null;
  const stage = workflowStage === "replying" ? "working" : workflowStage;
  const paintedStage = !receipt?.condition && ["picked_up", "working"].includes(stage) ? stage : null;
  syncAgentArrival(
    control,
    receipt && JSON.stringify([receipt.subject.kind, receipt.subject.id, receipt.id]),
    paintedStage
  );
  const reading = agentWorkflowDescription(control);
  keeps(control, "data-lf-agent-workflow", paintedStage || null);
  Object.assign(
    reading,
    paintedStage ? { stage: paintedStage, detail: receipt.detail } : { stage: null, detail: null }
  );
  paintAgentDescription(control);
}
function syncContributionSelection(control, selected) {
  control.toggleAttribute("data-lf-target-selected", Boolean(selected));
}
function syncContributionTurn(control, awaitsUser) {
  keeps(control, "data-lf-turn", awaitsUser ? "user" : null);
}
function syncContributionUnread(control, count) {
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
function presentContributionHost(control, offered, {
  accessibleLabel = null,
  relatedControlIds = [],
  writesRelation = true,
  writesSeat = true
} = {}) {
  const record = isContributionEntry(offered) ? offered : contributionEntry2(offered);
  if (control instanceof HTMLButtonElement && record.behavior === "status")
    throw new TypeError("A status margin entry needs a stable span host");
  controlAvailabilityOutput(
    control,
    CONTRIBUTION_ENTRY,
    contributionOwnsCommand(record) ? { disabled: control instanceof HTMLButtonElement, ariaDisabled: true } : null
  );
  records.set(control, record);
  keeps(control, "data-lf-margin-entry-key", record.key);
  keeps(control, "data-lf-margin-entry-owner", record.owner || null);
  keeps(
    control,
    "data-lf-margin-entry-identity",
    JSON.stringify([record.owner, record.key])
  );
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
      record.behavior === "disclosure" ? relation?.expanded ?? false : null
    );
    keeps(
      control,
      "aria-controls",
      relation?.kind === "element" ? relation.id : relation?.kind === "entries" && relatedControlIds.length ? relatedControlIds.join(" ") : null
    );
    keeps(control, "aria-haspopup", relation?.popup || null);
  }
  if (control instanceof HTMLButtonElement) {
    const wasStatus = control.getAttribute("role") === "status";
    control.removeAttribute("role");
    if (writesSeat && wasStatus) control.removeAttribute("tabindex");
    if (control.type !== "button") control.type = "button";
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
var contributionHost = elementDirective(
  "contributionHost",
  (control, source, surface, record, options) => {
    presentContributionHost(control, record, options);
    trackContributionControl(source, surface, record.key, control);
  }
);
function presentContributionReceipts(control, receipt, awaitsUser) {
  syncContributionAgentWorkflow(control, receipt);
  syncContributionTurn(control, awaitsUser);
}
var contributionReceipts = elementDirective(
  "contributionReceipts",
  presentContributionReceipts
);
function presentContributionEntry(control, offered, options = {}) {
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
  const glyph = record.icon ? iconFor(control, record.icon) : html`<span class="lf-margin-entry-glyph" aria-hidden="true"
        >${record.glyph}</span
      >`;
  render(
    html`${glyph}<span class="lf-margin-entry-space" aria-hidden="true"> </span
      ><span class="lf-margin-entry-label" aria-hidden="true"
        ><span class="lf-margin-entry-label-word">${visibleLabel}</span>${record.context ? html`<span class="lf-margin-entry-context">${record.context}</span>` : null}</span
      >${record.count > 1 ? html`<span class="lf-margin-count" aria-hidden="true"
              >${record.count}</span
            >` : null}`,
    control
  );
  return control;
}
function trackContributionControl(offered, surface, key, control) {
  controlContributions.set(control, offered);
  let surfaces = presented.get(offered);
  if (!surfaces) {
    surfaces = /* @__PURE__ */ new Map();
    presented.set(offered, surfaces);
  }
  let controls = surfaces.get(surface);
  if (!controls) {
    controls = /* @__PURE__ */ new Map();
    surfaces.set(surface, controls);
  }
  controls.set(key, control);
}
function clearContributionControls(offered, surface, liveKeys) {
  const controls = presented.get(offered)?.get(surface);
  if (!controls) return;
  for (const [key, control] of controls) {
    if (liveKeys.has(key)) continue;
    controls.delete(key);
    const retained = [...presented.get(offered).values()].some(
      (seats) => [...seats.values()].includes(control)
    );
    if (!retained) releaseContributionControl(control);
  }
}
function contributionControl(offered, entryKey, surface = null, visible = false) {
  const surfaces = presented.get(offered);
  for (const name of surface ? [surface] : ["margin", "page", "map", "inline"]) {
    const control = surfaces?.get(name)?.get(entryKey);
    if (control?.isConnected && (!visible || control.checkVisibility())) return control;
  }
  return null;
}
function contributionContains(offered, node) {
  if (!(node instanceof Node)) return false;
  return [...presented.get(offered)?.values() ?? []].some(
    (controls) => [...controls.values()].some(
      (control) => control === node || control.contains(node)
    )
  );
}
function releaseContributionControl(control) {
  controlAvailabilityOutput(control, CONTRIBUTION_ENTRY);
  projectCommandScope(control, CONTRIBUTION_ENTRY, null);
  controlContributions.delete(control);
}
function forgetContributionControls(offered) {
  for (const controls of presented.get(offered)?.values() ?? [])
    for (const control of controls.values()) releaseContributionControl(control);
  presented.delete(offered);
}
function activateContributionControl({ offered, entry, control, surface, event }, reveal = null) {
  return offered.registration.activate(entry.key, {
    origin: control,
    surface,
    input: pressIsKeyboardActivation(event) ? "keyboard" : "pointer",
    focus: (key) => {
      const destination = offered.registration.control(key, surface, true);
      if (!destination) return false;
      reveal?.(destination);
      focusDestination(destination, "return");
      return true;
    }
  });
}
function materializeContributionControls(source, surface, activate) {
  let controls = contributionControls.get(source);
  if (!controls) {
    controls = /* @__PURE__ */ new Map();
    contributionControls.set(source, controls);
  }
  const entries = source.reading.entries.filter((entry) => entry.visible);
  const liveKeys = new Set(entries.map((entry) => entry.key));
  const changed2 = /* @__PURE__ */ new Set();
  for (const key of controls.keys()) if (!liveKeys.has(key)) controls.delete(key);
  for (const entry of entries) {
    let control = controls.get(entry.key);
    if (!control || !contributionControlMatches(control, entry)) {
      control = createContributionControl(entry);
      controls.set(entry.key, control);
      changed2.add(control);
    } else if (contributionEntryRecord(control) !== entry) changed2.add(control);
    control.onclick = (event) => activate({ offered: source, entry, control, surface, event });
    trackContributionControl(source, surface, entry.key, control);
  }
  clearContributionControls(source, surface, liveKeys);
  for (const entry of entries) {
    const control = controls.get(entry.key);
    const related = entry.relation?.kind === "entries" ? entry.relation.keys.map((key) => controls.get(key)).filter(Boolean) : [];
    related.forEach((node, index) => {
      if (!node.id) node.id = `lf-margin-related-${++relationOrdinal}-${index + 1}`;
    });
    if (changed2.has(control))
      presentContributionEntry(control, entry, {
        relatedControlIds: related.map((node) => node.id)
      });
  }
  return controls;
}

// runtime/contributions.js
var text2 = (value) => String(value ?? "").trim();
var contributionSources = /* @__PURE__ */ new WeakMap();
var publishing = 0;
var contributionSource = (model) => contributionSources.get(model);
function publishReading(offered) {
  publishing++;
  try {
    const declared = offered.read();
    const normalized = normalizeReading(declared, offered.key, offered.reading);
    if (!offered.activate && normalized.entries.some(
      (entry) => entry.behavior !== "status" && !contributionOwnsCommand(entry)
    ))
      throw new TypeError("An unscoped contribution action needs an activate function");
    offered.readingActions = new Map(
      (declared.readings ?? []).map(({ id, activate }) => [id, activate])
    );
    offered.reading = normalized;
    const { readings, ...reading } = offered.reading;
    offered.model = Object.freeze({
      key: offered.key,
      reading: Object.freeze({ ...reading, hasReadings: readings.length > 0 })
    });
    contributionSources.set(offered.model, offered);
  } finally {
    publishing--;
  }
}
var contributions = /* @__PURE__ */ new Set();
var listeners = /* @__PURE__ */ new Set();
var owed = false;
var changed = () => {
  owed = true;
  afterScript(settle);
};
function settle({ immediate = false } = {}) {
  if (!owed || publishing) return;
  owed = false;
  for (const listener of listeners) listener({ immediate });
}
var contributionEntries = () => contributions.values();
watchCommandAvailability(() => {
  for (const offered of contributions)
    if (offered.reading.entries.some(
      (entry) => contributionOwnsCommand(entry) && entry.disabled !== contributionCommandDisabled(entry)
    ))
      offered.registration.update({ immediate: true });
});
function presentingContributions() {
  owed = false;
}
function watchContributions(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
function registerContribution({ key, target, source = target, read, activate }) {
  const owner = text2(key);
  if (!owner) throw new TypeError("A contribution needs a key");
  const targetOf = typeof target === "function" ? target : () => target;
  const sourceOf = source === target ? targetOf : typeof source === "function" ? source : () => source;
  const offered = {
    key: owner,
    target: targetOf,
    source: sourceOf,
    read,
    activate,
    reading: null
  };
  publishReading(offered);
  contributions.add(offered);
  changed();
  const entry = (entryKey) => offered.reading.entries.find((candidate) => candidate.key === entryKey) ?? null;
  const control = (entryKey, surface = null, visible = false) => {
    settle();
    return contributionControl(offered, entryKey, surface, visible);
  };
  let owedFocus = null;
  const landFocus = () => {
    const key2 = owedFocus;
    owedFocus = null;
    offered.focusRequest = null;
    if (key2 != null) registration.focus(key2, "move");
  };
  const arrive = (entryKey, surface, move) => {
    const request = { key: text2(entryKey), surface };
    const previous = offered.focusRequest;
    offered.focusRequest = request;
    try {
      changed();
      settle({ immediate: true });
      const destination = control(request.key, surface, true);
      if (!destination) return false;
      return move(destination);
    } finally {
      if (offered.focusRequest === request) offered.focusRequest = previous;
    }
  };
  const registration = Object.freeze({
    entry(entryKey) {
      return entry(text2(entryKey));
    },
    control,
    contains(node) {
      return contributionContains(offered, node);
    },
    activate(entryKey, context = {}) {
      if (!contributions.has(offered)) return false;
      const current = entry(text2(entryKey));
      if (!current || !current.visible || (contributionOwnsCommand(current) ? contributionCommandDisabled(current) : current.disabled) || current.behavior === "status")
        return false;
      const originOwnsFocus = context.origin == null || context.origin === focused();
      const focusCurrentSurface = (key2) => arrive(key2, context.surface ?? null, (destination) => {
        if (context.focus) return context.focus(key2);
        focusDestination(destination, "return");
        return true;
      });
      const activationContext = {
        ...context,
        entry: current,
        focus: originOwnsFocus ? focusCurrentSurface : () => false
      };
      const command = contributionCommand(current);
      if (command) command.row.run(command.binding, activationContext);
      else offered.activate(current.activation, activationContext);
      return true;
    },
    activateReading(id) {
      const activate2 = offered.readingActions.get(id);
      if (!activate2) return false;
      activate2();
      return true;
    },
    // Puts the user on the entry's control, saying what moved them (focus.js,
    // `focusDestination`).
    focus(entryKey, cause, surface = null) {
      return arrive(entryKey, surface, (destination) => {
        focusDestination(destination, cause);
        return true;
      });
    },
    // A focus asked for with an update lands when the script's render does, on the
    // control that render leaves: two updates in one script (an undo shown pending, then
    // its publication) render once rather than painting the step between them.
    update({ immediate = false, focus = null } = {}) {
      publishReading(offered);
      if (focus != null) {
        owedFocus = text2(focus);
        offered.focusRequest = { key: owedFocus, surface: null };
        afterScript(landFocus);
      }
      changed();
      if (immediate) {
        settle({ immediate: true });
      }
    },
    unregister() {
      if (!contributions.delete(offered)) return;
      forgetContributionControls(offered);
      changed();
    }
  });
  offered.registration = registration;
  return registration;
}

// runtime/version-picker.js
var LATEST_FAILED = "Latest edit couldn't be shown";
var INITIAL_LATEST = "New page available \u2192 open v999";
var EMPTY = Object.freeze([]);
var INITIAL = Object.freeze({
  picker: Object.freeze({
    offered: false,
    token: "Showing Draft",
    compared: false,
    news: false,
    keyTitle: "Draft",
    ariaLabel: "Draft"
  }),
  latest: Object.freeze({
    disabled: false,
    keyTitle: "Open the current page",
    label: INITIAL_LATEST,
    shown: null
  }),
  rows: EMPTY,
  selection: Object.freeze({
    base: null,
    currentRevision: null,
    on: false,
    pendingBase: null,
    baseRevision: null
  })
});
var VersionPickerView = class {
  #activate = null;
  #compare = null;
  #displayedRows = EMPTY;
  #latest = null;
  #model = INITIAL;
  #toggle = null;
  #openingInput = null;
  constructor() {
    this.button = el("button", "lf-btn lf-version");
    this.menu = el("div", "lf-ui lf-version-menu");
    this.latestChip = el("button", "lf-ui lf-btn lf-latest-chip");
    this.menu.id = "lf-versions";
    this.menu.setAttribute("popover", "auto");
    this.menu.setAttribute("role", "menu");
    this.menu.setAttribute("aria-label", "Versions");
    this.button.setAttribute("popovertarget", this.menu.id);
    this.menu.addEventListener("beforetoggle", (event) => {
      if (event.newState === "open") {
        this.#openingInput = inputCount();
        dismissBannerControls();
      }
    });
    this.menu.addEventListener("toggle", (event) => {
      if (event.newState === "open") {
        const arrival = this.#selectedRow();
        if (arrival && canPlaceFocus() && inputCount() === this.#openingInput) {
          focusDestination(arrival, "move");
          scrollIntoView(arrival, { block: "nearest" });
        }
      } else {
        this.#openingInput = null;
        this.#displayedRows = this.#model.rows;
        this.#renderMenu();
      }
      this.#toggle?.();
    });
    this.latestChip.onclick = () => this.latest();
    this.present(INITIAL);
  }
  configure({ activate, compare, latest, toggle }) {
    this.#activate = activate;
    this.#compare = compare;
    this.#latest = latest;
    this.#toggle = toggle;
  }
  isOpen() {
    return isNativeLayer(this.menu);
  }
  close() {
    if (this.isOpen()) closeNativeLayer(this.menu);
  }
  rows() {
    return [...this.menu.querySelectorAll(".lf-version-row")];
  }
  stops() {
    return [...this.menu.querySelectorAll("button:not(:disabled)")].filter(
      (control) => control.getClientRects().length
    );
  }
  atBoundary(end) {
    return focused() === this.stops().at(end);
  }
  #selectedRow() {
    const { base, currentRevision } = this.#model.selection;
    return this.rows().find(
      (row) => base !== null ? row.dataset.lfVersion === String(base) : row.dataset.lfRevision === String(currentRevision)
    ) ?? this.rows()[0];
  }
  numberedRoutes() {
    return this.rows().map((control) => ({ control, version: +control.dataset.lfVersion })).filter(({ version }) => version >= 1 && version <= 9).sort((left, right) => left.version - right.version).map(({ control, version }) => ({
      id: `version.open-v${version}`,
      binding: String(version),
      title: `open v${version}`,
      control
    }));
  }
  // The picker's commands, and word of each reading it presents, for another
  // presentation of the same versions, the floating panel's Versions view, which draws
  // its own rows from `versionsReading` (version.js).
  #listeners = /* @__PURE__ */ new Set();
  watch(listener) {
    this.#listeners.add(listener);
    return () => this.#listeners.delete(listener);
  }
  activate(entry) {
    this.#activate?.(entry);
  }
  compare(version) {
    this.#compare?.(version);
  }
  latest() {
    this.#latest?.();
  }
  present(model) {
    this.#model = model;
    for (const listener of this.#listeners) listener(model);
    const { picker, latest } = model;
    if (!picker.offered) this.close();
    this.button.toggleAttribute("disabled", !picker.offered);
    keeps(this.button, "aria-haspopup", picker.offered ? "menu" : null);
    this.button.classList.toggle("on", picker.compared);
    this.button.toggleAttribute("data-lf-news", picker.news);
    keeps(this.button, "data-lf-key-title", picker.keyTitle);
    keeps(this.button, "aria-label", picker.ariaLabel);
    render(picker.token, this.button);
    this.latestChip.toggleAttribute("disabled", latest.disabled);
    keeps(this.latestChip, "data-lf-key-title", latest.keyTitle);
    render(latest.label, this.latestChip);
    if (!this.isOpen()) this.#displayedRows = model.rows;
    this.#renderMenu();
  }
  #renderMenu() {
    const { selection } = this.#model;
    render(
      html`${repeat(
        this.#displayedRows,
        // Draft and stamped destinations can share a revision and remain distinct.
        (entry) => `${entry.version === null ? "draft" : "version"}:${entry.revision}`,
        (entry) => {
          const compared = selection.on && selection.baseRevision !== null && entry.revision >= selection.baseRevision && entry.revision <= selection.currentRevision;
          const pending = entry.version === selection.pendingBase;
          return html`
            <button
              class=${`lf-version-row${compared ? " lf-compared" : ""}`}
              role="menuitem"
              data-lf-revision=${entry.revision}
              data-lf-version=${entry.version ?? nothing}
              aria-current=${entry.current ? "true" : nothing}
              @click=${() => {
            this.close();
            this.#activate?.(entry);
          }}
            >
              <span class="lf-version-num">${entry.name}</span>
              ${entry.note ? html`<span class="lf-version-note">${entry.note}</span>` : nothing}
            </button>
            ${entry.comparable ? html`<button
                    class="lf-version-diff"
                    role="menuitemcheckbox"
                    data-lf-version=${entry.version}
                    aria-label=${`Compare with v${entry.version}`}
                    title=${`Mark what changed since v${entry.version}`}
                    aria-checked=${String(
            pending || selection.on && entry.version === selection.base
          )}
                    aria-busy=${pending ? "true" : nothing}
                    @click=${() => {
            this.close();
            this.#compare?.(entry.version);
          }}
                  >
                    Compare
                  </button>` : nothing}
          `;
        }
      )}`,
      this.menu
    );
  }
};
var versionPicker = new VersionPickerView();
var versionBtn = versionPicker.button;
var versionMenu = versionPicker.menu;
var latestChip = versionPicker.latestChip;
var versionMenuIsOpen = () => versionPicker.isOpen();
var closeVersionMenu = () => versionPicker.close();
var latestVersionLabel = ({ failed = false, activeLabel = null } = {}) => failed ? LATEST_FAILED : activeLabel ? `New page available \u2192 open ${activeLabel}` : INITIAL_LATEST;

// runtime/margin-model.js
var RESTING_MARGIN_ENTRY_BUDGET = 2;
var TOGGLE = Object.freeze({ icon: "more", label: "More options" });
var FOLDED = Object.freeze(
  Object.fromEntries(
    Object.entries(KINDS).map(([kind, { icon, label }]) => [
      kind,
      Object.freeze({ icon, label })
    ])
  )
);
var EXPANDED_MARGIN_ENTRY_BUDGET = 6;
function annotationItems(entry) {
  const represented = new Set(
    entry.offers.flatMap(
      ({ reading }) => reading.entries.filter((record) => record.visible).map((record) => record.owner)
    )
  );
  return entry.items.filter((item) => !item.owner || !represented.has(item.owner));
}
var noticeItems = (entry) => entry.offers.flatMap((offered) => {
  const notice = offered.reading.notice;
  if (!notice) return [];
  return [Object.freeze({ kind: "notice", key: offered, notice, offered })];
});
var deriveEntryState = (entry) => {
  const states = [
    ...entry.offers.map(contributionState),
    ...entry.items.map((item) => item.state ?? item.workflowFace?.state ?? "idle")
  ];
  return states.sort(
    (left, right) => contributionEntryStateRank(left) - contributionEntryStateRank(right)
  )[0] ?? "idle";
};
var entryState = (entry) => entry.state;
var entryEngaged = (entry) => entry.state !== "idle";
var controlReceipt = (carrier, record) => carrier?.key === record.key && carrier.owner === record.owner ? carrier.receipt : record.workflowReceipt;
var contributionItem = (offered, record, carrier, cluster = null) => Object.freeze({
  cluster,
  kind: "contribution",
  offered,
  record,
  receipt: controlReceipt(carrier, record)
});
var visibleRecords = (offers) => offers.flatMap(
  (offered) => offered.reading.entries.filter((record) => record.visible).map((record) => ({ offered, record }))
);
var entryControls = (entry) => [...entry.controls, ...entry.afterControls].sort(compareContributionEntryRecords);
var choosePrimary = (entry) => entry.controls[0] ?? null;
var entryHasMarginHost = (entry) => entry.hasMarginHost;
var readingKey = (entry, choice) => JSON.stringify([entry.key, choice.key]);
var deriveReadingChoices = (items) => {
  const threadList = [];
  const choices = [];
  for (const item of items.filter((item2) => item2.marker !== false)) {
    if (item.kind === "comment") threadList.push(item);
    else
      choices.push({
        key: contributionItemKey(item),
        kind: item.kind,
        items: [item],
        text: item.text
      });
  }
  if (threadList.length)
    choices.push({
      // One target owns one thread margin entry. Membership changes repaint its badge and
      // card without replacing the control that owns an open thread.
      key: "threadList",
      kind: "comment",
      items: threadList,
      text: threadList[0].text
    });
  return Object.freeze(
    choices.map((choice) => Object.freeze({ ...choice, items: Object.freeze(choice.items) })).sort(
      (left, right) => KINDS[left.kind].priority - KINDS[right.kind].priority || left.items[0].id.localeCompare(right.items[0].id) || left.key.localeCompare(right.key)
    )
  );
};
var readingChoices = (entry) => entry.choices;
var primaryReading = (entry) => readingChoices(entry)[0] ?? null;
var threadReading = (entry) => readingChoices(entry).find((choice) => choice.kind === "comment") ?? null;
var secondaryReadings = (entry, primaryControl) => readingChoices(entry).slice(primaryControl ? 0 : 1);
var secondaryCount = (entry, primary) => secondaryReadings(entry, primary).length + entry.controls.length - Number(Boolean(primary)) + entry.afterControls.length;
var optionsOffered = (entry, primary) => secondaryCount(entry, primary) > RESTING_MARGIN_ENTRY_BUDGET - 1;
function readingLabel(choice) {
  const face = readingFace(choice);
  const items = choice?.items ?? [];
  if (items.length > 1) return `${face.label}s`;
  return items[0]?.label || face.label;
}
function markerFace(entry) {
  const kinds = kindsIn(entry, { markerOnly: true });
  const choice = primaryReading(entry);
  const face = readingFace(choice);
  const faceCount = choice?.items.length ?? 0;
  return {
    kinds,
    face,
    label: readingLabel(choice),
    // The badge describes this margin entry's result. Other readings live behind `…`
    // and must not make a thread margin entry appear to open more threadList than it does.
    count: faceCount
  };
}
function readingFace(choice) {
  return choice?.items.length === 1 && choice.items[0].workflowFace || KINDS[choice?.kind] || KINDS.action;
}
function readingState(choice) {
  return (choice?.items ?? []).map((item) => item.state ?? item.workflowFace?.state ?? "idle").sort(
    (left, right) => contributionEntryStateRank(left) - contributionEntryStateRank(right)
  )[0] ?? "idle";
}
var readingBehavior = (face) => face.indication ? "status" : "disclosure";
var userAttention = (items) => {
  let first = null;
  for (const item of items) {
    const attention = item.userAttention;
    if (!attention) continue;
    if (attention.reason === "ask") return attention;
    first ??= attention;
  }
  return first;
};
var awaitingUser = (items) => Boolean(userAttention(items));
var unreadIn = (items) => items.reduce((sum, item) => sum + (item.unread ?? 0), 0);
function readingContext(choice) {
  const attention = userAttention(choice?.items ?? []);
  if (attention) return attention.label;
  const unread = unreadIn(choice?.items ?? []);
  if (unread) return `${unread} unread`;
  if (choice?.items.length !== 1) return null;
  return choice.items[0].context ?? null;
}
function kindsIn(entry, { markerOnly = false } = {}) {
  const counts = /* @__PURE__ */ new Map();
  for (const item of entry.items) {
    if (!markerOnly || item.marker !== false)
      counts.set(item.kind, (counts.get(item.kind) ?? 0) + 1);
  }
  return [...counts].map(([kind, count]) => ({ kind, count, ...KINDS[kind] }));
}
var readingItem = (entry, choice) => Object.freeze({
  kind: "reading",
  key: `reading:${readingKey(entry, choice)}`,
  entry,
  choice
});
function optionItems(entry, primary, focusedOffer = null) {
  if (focusedOffer) {
    return focusedOffer.reading.entries.filter((record) => record.visible).map(
      (record) => contributionItem(focusedOffer, record, entry.workflowCarrier, entry)
    );
  }
  return [
    ...entry.controls.slice(primary ? 1 : 0).map((item) => Object.freeze({ ...item, cluster: entry })),
    ...secondaryReadings(entry, primary).map((choice) => readingItem(entry, choice)),
    ...entry.afterControls.map((item) => Object.freeze({ ...item, cluster: entry }))
  ];
}
function optionGroupProjection(entry, primary, optionsOpen, focusedOffer = null, forcedInlineKey = null, folded = false) {
  const items = optionItems(entry, primary, focusedOffer);
  const peerCapacity = Math.max(
    0,
    EXPANDED_MARGIN_ENTRY_BUDGET - (!focusedOffer && (primary || entry.choices.length) ? 1 : 0)
  );
  const needsSpill = items.length > peerCapacity;
  const visibleCapacity = needsSpill ? peerCapacity - 1 : peerCapacity;
  const hidden = Math.max(0, items.length - visibleCapacity);
  const direct = items.slice(0, visibleCapacity);
  const forcedThread = forcedInlineKey === entry.key ? items.find((item) => item.choice?.kind === "comment") : null;
  if (forcedThread && direct.length && !direct.includes(forcedThread))
    direct[direct.length - 1] = forcedThread;
  const firstSpilled = items.find((item) => !direct.includes(item));
  return Object.freeze({
    entry,
    entryKey: entry.key,
    label: `${entryEngaged(entry) || folded ? "Actions" : "More options"} for ${spokenSubject(entry.title)}`,
    hidden: !optionsOpen || direct.length === 0,
    items: Object.freeze(items),
    spill: needsSpill ? Object.freeze({
      count: hidden,
      first: firstSpilled,
      label: `Show ${hidden} more in Page Map`
    }) : null,
    visible: Object.freeze(direct)
  });
}
var focusedOfferOf = (entry, expandedKey, expandedOwner) => expandedKey === entry.key && expandedOwner ? entry.offers.find((offered) => offered.key === expandedOwner) ?? null : null;
function canFold(entry, { expandedKey = null, expandedOwner = null } = {}) {
  if (focusedOfferOf(entry, expandedKey, expandedOwner)) return false;
  const primary = choosePrimary(entry);
  return Boolean(primary) && secondaryCount(entry, primary) > 0 && entry.choices.length === 0 && noticeItems(entry).length === 0 && !entryEngaged(entry);
}
function clusterProjection(entry, {
  expandedKey = null,
  expandedOwner = null,
  forcedInlineKey = null,
  folded = false
} = {}) {
  const focusedOffer = focusedOfferOf(entry, expandedKey, expandedOwner);
  const primary = focusedOffer ? null : choosePrimary(entry);
  const folds = folded && canFold(entry, { expandedKey, expandedOwner });
  const shown = folds ? null : primary;
  const subject = spokenSubject(entry.title);
  const secondaries = focusedOffer ? focusedOffer.reading.entries.filter((record) => record.visible).length : secondaryCount(entry, primary);
  const hasOptions = folds || secondaries > (focusedOffer ? 0 : RESTING_MARGIN_ENTRY_BUDGET - 1);
  const optionsOpen = secondaries > 0 && (!hasOptions || expandedKey === entry.key || entryEngaged(entry));
  const kind = folds ? primary.offered.reading.kind ?? "action" : null;
  return Object.freeze({
    primary,
    hasOptions,
    optionsOpen,
    optionsExpanded: optionsOpen && expandedKey === entry.key,
    folded: folds,
    options: optionGroupProjection(
      entry,
      shown,
      optionsOpen,
      focusedOffer,
      forcedInlineKey,
      folds
    ),
    direct: Object.freeze([...shown ? [shown] : [], ...noticeItems(entry)]),
    entry,
    kind: "page",
    label: `Page actions for ${subject}`,
    toggle: kind ? FOLDED[kind] : TOGGLE,
    moreLabel: kind ? `${KINDS[kind].label}, ${subject}` : `More options for ${subject}`,
    offers: entry.offers,
    hasPrimary: Boolean(shown),
    state: entryState(entry),
    target: entry.targetId || entry.key
  });
}
function marginInventory(groups) {
  return Object.freeze(
    groups.map((group) => {
      const represented = new Set(
        group.items.filter((item) => item.marker === false && item.represents).map((item) => item.kind)
      );
      let items = group.items.filter(
        (item) => item.marker === false || item.workflowFace || !represented.has(item.kind)
      ).sort(
        (left, right) => KINDS[left.kind].priority - KINDS[right.kind].priority || (left.kind === "comment" ? 0 : left.id.localeCompare(right.id))
      );
      const direct = group.offers.filter(
        (offered) => offered.reading.side === "before" || offered.reading.hasReadings
      );
      const after = group.offers.filter(
        (offered) => offered.reading.side === "after" && !offered.reading.hasReadings
      ).sort(compareContributions);
      const directRecords = visibleRecords(direct).sort(
        compareContributionEntryRecords
      );
      const primary = directRecords[0];
      const receipt = group.workflowReceipt;
      const workflowCarrier = primary && receipt ? Object.freeze({
        key: primary.record.key,
        owner: primary.record.owner,
        receipt
      }) : null;
      const controlsFrom = (records2) => records2.map(
        ({ offered, record }) => contributionItem(offered, record, workflowCarrier)
      );
      const controls = Object.freeze(controlsFrom(directRecords));
      const afterControls = Object.freeze(
        after.flatMap(
          (offered) => controlsFrom(visibleRecords([offered]).sort(compareContributionEntryRecords))
        )
      );
      if (workflowCarrier)
        items = items.filter((item) => !(item.workflowFace && item.carriesWorkflow));
      return Object.freeze({
        ...group,
        items: Object.freeze(items),
        controls,
        afterControls,
        choices: deriveReadingChoices(items),
        state: deriveEntryState({ offers: group.offers, items }),
        hasMarginHost: controls.length > 0 || afterControls.length > 0 || items.some((item) => item.marker !== false),
        workflowCarrier
      });
    })
  );
}

export {
  CONTRIBUTION_ENTRY_SCHEMA,
  KINDS,
  compareContributions,
  visibleContributionEntryLabel,
  contributionItemKey,
  spokenSubject,
  contributionEntry2 as contributionEntry,
  contributionEntryRecord,
  contributionControlKey,
  contributionEntrySource,
  syncContributionSelection,
  syncContributionUnread,
  contributionHost,
  presentContributionReceipts,
  contributionReceipts,
  presentContributionEntry,
  clearContributionControls,
  activateContributionControl,
  materializeContributionControls,
  contributionSource,
  contributionEntries,
  presentingContributions,
  watchContributions,
  registerContribution,
  annotationItems,
  entryEngaged,
  entryControls,
  choosePrimary,
  entryHasMarginHost,
  readingKey,
  readingChoices,
  primaryReading,
  threadReading,
  optionsOffered,
  readingLabel,
  markerFace,
  readingFace,
  readingState,
  readingBehavior,
  awaitingUser,
  unreadIn,
  readingContext,
  focusedOfferOf,
  canFold,
  clusterProjection,
  marginInventory,
  versionPicker,
  versionBtn,
  versionMenu,
  latestChip,
  versionMenuIsOpen,
  closeVersionMenu,
  latestVersionLabel
};
