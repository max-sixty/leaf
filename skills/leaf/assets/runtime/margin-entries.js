/* The public grammar and registry for controls contributed to a page target's margin.

   Contributors own their verbs, events, and semantic engagement state. This module owns
   the shared control anatomy, validates stable identities within each contribution, and
   retains registrations while live documents and widgets reconnect. The margin projection
   consumes that registry to choose and place controls; contributors never place RHS rows.

   Behavior, tone, rank, and interaction state are independent axes. An action performs an
   immediate effect, a disclosure reveals context, and a status reports a move already
   made without offering a press. Tone changes the icon color without changing the ring
   or surface. Busy dims an in-flight press after the shared delay; engaged and failed
   controls stand beside words that already state their condition. Interaction state
   otherwise orders controls and keeps an active contribution open rather than becoming a
   product-facing visual taxonomy.
   A disclosure's visible label ends in an ellipsis because it opens context; action and
   status labels do not. Every axis has a default, so an option outside this grammar is
   refused rather than ignored: a caller stating a rank under a name this module does not
   know would otherwise get the default and no word about it.

   Ordering follows interaction state, then rank, contribution key, and control key. Failed,
   busy, and engaged contributions precede idle ones; completion and escape controls
   precede primary, secondary, reading, and overflow controls. Registration and DOM order
   never decide which unrelated action becomes primary.

   A disclosure owns `aria-expanded` by default, and every element owns its tab seat by
   default. `writesRelation: false` or `writesSeat: false` declares another sole writer.
   Two relation writers add and remove the same attribute each heartbeat; the disclosure
   watch reads that as news and repaints an untouched page's keys. Two seat writers make
   the element's `tabindex` alternate after each roving-seat pass. The retained record
   carries relation ownership into proxies, which forward transient native state while
   activation remains with the contributor's original control.

   A failed mutation leaves Failed, Retry, and Cancel at its target. Retry follows only a
   definitive refusal; an ambiguous transport result remains busy while delivery retries
   the same attempt. Reversible actions act immediately and may offer Undo. Confirmation
   is reserved for irreversible effects. */

import { layoutMarginRows } from "./margin-layout.js";
import { iconElement } from "./icons.js";
import { keeps } from "./widget-elements.js";
import { agentWorkPhase } from "./updates.js";

const contributions = new Set();
const listeners = new Set();

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
const MARGIN_ENTRY_OPTIONS = new Set([
  "behavior",
  "context",
  "glyph",
  "icon",
  "key",
  "label",
  "rank",
  "state",
  "tone",
  "writesRelation",
  "writesSeat",
]);
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

const RECORD = Symbol("Leaf margin entry record");
const FORWARDED_ATTRIBUTES = [
  "aria-busy",
  "aria-controls",
  "aria-disabled",
  "aria-expanded",
  "aria-haspopup",
  "aria-pressed",
  "data-lf-agent-phase",
];

const changed = () => {
  for (const listener of listeners) listener();
};

export const marginContributionEntries = () => contributions.values();

export const marginEntryStateRank = (state) => STATE_PRIORITY.get(state);

export function marginContributionState(offered) {
  const state = typeof offered.state === "function" ? offered.state() : offered.state;
  if (!STATES.has(state))
    throw new TypeError(`Unknown margin contribution state: ${state}`);
  return state;
}

export function compareMarginContributions(left, right) {
  const state =
    STATE_PRIORITY.get(marginContributionState(left)) -
    STATE_PRIORITY.get(marginContributionState(right));
  return state || left.key.localeCompare(right.key);
}

export function compareMarginEntryRecords(left, right) {
  const state =
    STATE_PRIORITY.get(marginContributionState(left.offered)) -
    STATE_PRIORITY.get(marginContributionState(right.offered));
  if (state) return state;
  const rank =
    RANK_PRIORITY.get(marginEntryRecord(left.control).rank) -
    RANK_PRIORITY.get(marginEntryRecord(right.control).rank);
  if (rank) return rank;
  const contribution = left.offered.key.localeCompare(right.offered.key);
  return (
    contribution ||
    marginEntryRecord(left.control).key.localeCompare(
      marginEntryRecord(right.control).key,
    )
  );
}

export function watchMarginContributions(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export const visibleMarginEntryLabel = ({ behavior, label }) =>
  behavior !== "disclosure" || label.endsWith("…") ? label : `${label}…`;

export function marginEntryRecord(control) {
  const record = control?.[RECORD];
  if (!record) throw new TypeError("A contributed margin entry must use marginEntry");
  return record;
}

export function marginEntries(controls) {
  if (!(controls instanceof Element)) return [];
  if (controls.matches(".lf-margin-entry")) return [controls];
  return [...controls.querySelectorAll(".lf-margin-entry")];
}

function validateMarginEntries(offered) {
  const keys = new Set();
  for (const control of marginEntries(offered.controls)) {
    const record = marginEntryRecord(control);
    if (keys.has(record.key))
      throw new TypeError(
        `Duplicate margin entry key "${record.key}" in margin contribution "${offered.key}"`,
      );
    if (record.owner && record.owner !== offered.key)
      throw new TypeError(
        `margin entry "${record.key}" already belongs to margin contribution "${record.owner}"`,
      );
    keys.add(record.key);
    record.owner = offered.key;
    control.dataset.lfMarginEntryOwner = offered.key;
  }
}

// Ownership is independent of a control's action and delivery state. A semantic
// carrier keeps its glyph and press while the canonical receipt supplies its color.
const agentDescriptions = new WeakMap();
const forwardedSources = new WeakMap();
// Every claim gets one arrival window shared by its margin and Page Map carriers.
// A new carrier can join the remaining pulse, but repainting cannot begin it again.
const claimArrivals = new Map();
const controlArrivals = new WeakMap();
function syncAgentArrival(control, claim, phase) {
  if (phase !== "active") {
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
    () => {
      control.removeAttribute("data-lf-agent-arrival");
    },
    { once: true },
  );
}

// Both entry reconciliation and activity updates ask this one writer to compose
// text. Rebuilding a control must not clear a tooltip whose ownership is unchanged.
function paintAgentDescription(control) {
  const source = forwardedSources.get(control);
  if (source) {
    for (const attribute of ["aria-description", "title"]) {
      const value = source.getAttribute(attribute);
      if (value === null) control.removeAttribute(attribute);
      else keeps(control, attribute, value);
    }
    return;
  }
  const reading = agentDescriptions.get(control);
  if (!reading) {
    control.removeAttribute("title");
    return;
  }
  if (!reading.phase) {
    for (const [attribute, value] of [
      ["aria-description", reading.description],
      ["title", reading.title],
    ]) {
      if (value === null) control.removeAttribute(attribute);
      else keeps(control, attribute, value);
    }
    return;
  }
  const work = [reading.phase === "active" ? "Working" : "Picked up", reading.detail]
    .filter(Boolean)
    .join(" · ");
  const action = control[RECORD]?.label || control.getAttribute("aria-label");
  keeps(
    control,
    "aria-description",
    [reading.description, work].filter(Boolean).join(" · "),
  );
  keeps(
    control,
    "title",
    [action, reading.title !== action && reading.title, work]
      .filter(Boolean)
      .join(" · "),
  );
}

export function syncMarginAgentPhase(control, receipt) {
  const phase = agentWorkPhase(receipt);
  syncAgentArrival(
    control,
    receipt && JSON.stringify([receipt.target.kind, receipt.target.id, receipt.id]),
    phase,
  );
  if (phase) {
    if (!agentDescriptions.has(control))
      agentDescriptions.set(control, {
        description: control.getAttribute("aria-description"),
        title: control.getAttribute("title"),
      });
    Object.assign(agentDescriptions.get(control), { phase, detail: receipt.detail });
    keeps(control, "data-lf-agent-phase", phase);
    paintAgentDescription(control);
  } else {
    control.removeAttribute("data-lf-agent-phase");
    if (agentDescriptions.has(control)) {
      agentDescriptions.get(control).phase = null;
      paintAgentDescription(control);
      agentDescriptions.delete(control);
    }
  }
}

export function syncForwardedMarginEntryState(projection, source) {
  forwardedSources.set(projection, source);
  paintAgentDescription(projection);
  syncAgentArrival(
    projection,
    controlArrivals.get(source),
    source.dataset.lfAgentPhase,
  );
  const label = source.getAttribute("aria-label");
  if (label == null) projection.removeAttribute("aria-label");
  else keeps(projection, "aria-label", label);
  const disabled = source.disabled || source.getAttribute("aria-disabled") === "true";
  if (projection.disabled !== disabled) projection.disabled = disabled;
  for (const attribute of FORWARDED_ATTRIBUTES) {
    const value = source.getAttribute(attribute);
    if (value == null) projection.removeAttribute(attribute);
    else keeps(projection, attribute, value);
  }
}

export function marginEntry(control, options) {
  const {
    glyph = null,
    icon = null,
    key,
    label,
    context = null,
    behavior = "action",
    tone = "neutral",
    rank = "primary",
    state = "idle",
    writesRelation = true,
    writesSeat = true,
  } = options;
  // Every axis has a default, so an option this grammar does not know is silently
  // nothing: the control keeps the default for the axis the caller meant to state.
  // That is how a rename of this vocabulary reaches a call site — the old name goes
  // on being accepted and the stated rank stops arriving. Name it here instead.
  const unknown = Object.keys(options).filter(
    (option) => !MARGIN_ENTRY_OPTIONS.has(option),
  );
  if (unknown.length)
    throw new TypeError(`Unknown margin entry option: ${unknown.sort().join(", ")}`);
  if (!(control instanceof Element))
    throw new TypeError("A margin entry needs an Element control");
  if (!String(key ?? "").trim()) throw new TypeError("A margin entry needs a key");
  if (Boolean(String(glyph ?? "").trim()) === Boolean(icon))
    throw new TypeError("A margin entry needs exactly one glyph or icon");
  if (!String(label ?? "").trim()) throw new TypeError("A margin entry needs a label");
  if (!TONES.has(tone)) throw new TypeError(`Unknown margin entry tone: ${tone}`);
  if (!BEHAVIORS.has(behavior))
    throw new TypeError(`Unknown margin entry behavior: ${behavior}`);
  if (!RANKS.has(rank)) throw new TypeError(`Unknown margin entry rank: ${rank}`);
  const record = control[RECORD] ?? {};
  Object.assign(record, {
    key: String(key),
    glyph: glyph == null ? null : String(glyph),
    icon,
    label: String(label),
    context: String(context ?? "").trim() || null,
    behavior,
    tone,
    rank,
    state,
    writesRelation,
  });
  control[RECORD] = record;

  if (!control.classList.contains("lf-margin-entry"))
    control.classList.add("lf-margin-entry");
  paintAgentDescription(control);
  keeps(control, "data-lf-margin-entry-key", record.key);
  keeps(control, "data-lf-behavior", record.behavior);
  keeps(control, "data-lf-tone", record.tone);
  keeps(control, "data-lf-rank", record.rank);
  keeps(control, "data-lf-offer", behavior === "status" ? "" : "button");
  setMarginEntryState(control, state);
  const opens = behavior === "disclosure";
  if (opens && writesRelation && !control.hasAttribute("aria-expanded"))
    control.setAttribute("aria-expanded", "false");
  if (!opens) control.removeAttribute("aria-expanded");
  if (behavior === "status") {
    keeps(control, "role", "status");
    if (writesSeat) keeps(control, "tabindex", -1);
  } else if (!(control instanceof HTMLButtonElement)) {
    keeps(control, "role", "button");
    if (writesSeat && control.tabIndex < 0) control.tabIndex = 0;
  } else if (control.getAttribute("role") === "status") {
    control.removeAttribute("role");
    if (writesSeat) control.removeAttribute("tabindex");
  }

  let glyphNode = control.querySelector(
    ":scope > :is(.lf-margin-entry-glyph, .lf-margin-entry-icon)",
  );
  let spaceNode = control.querySelector(":scope > .lf-margin-entry-space");
  let labelNode = control.querySelector(":scope > .lf-margin-entry-label");
  if (icon) {
    if (!(glyphNode instanceof SVGSVGElement) || glyphNode.dataset.lfIcon !== icon)
      glyphNode = iconElement(icon);
  } else {
    if (!(glyphNode instanceof HTMLSpanElement))
      glyphNode = document.createElement("span");
    if (glyphNode.className !== "lf-margin-entry-glyph")
      glyphNode.className = "lf-margin-entry-glyph";
    glyphNode.removeAttribute("data-lf-icon");
    if (glyphNode.textContent !== glyph) glyphNode.textContent = glyph;
  }
  if (!spaceNode) spaceNode = document.createElement("span");
  if (!labelNode) labelNode = document.createElement("span");
  if (glyphNode.getAttribute("aria-hidden") !== "true")
    glyphNode.setAttribute("aria-hidden", "true");
  if (spaceNode.className !== "lf-margin-entry-space")
    spaceNode.className = "lf-margin-entry-space";
  if (spaceNode.getAttribute("aria-hidden") !== "true")
    spaceNode.setAttribute("aria-hidden", "true");
  if (spaceNode.textContent !== " ") spaceNode.textContent = " ";
  if (labelNode.className !== "lf-margin-entry-label")
    labelNode.className = "lf-margin-entry-label";
  if (labelNode.getAttribute("aria-hidden") !== "true")
    labelNode.setAttribute("aria-hidden", "true");

  const visibleLabel = visibleMarginEntryLabel(record);
  let labelWord = labelNode.querySelector(":scope > .lf-margin-entry-label-word");
  let contextNode = labelNode.querySelector(":scope > .lf-margin-entry-context");
  if (!labelWord) labelWord = document.createElement("span");
  if (labelWord.className !== "lf-margin-entry-label-word")
    labelWord.className = "lf-margin-entry-label-word";
  if (labelWord.textContent !== visibleLabel) labelWord.textContent = visibleLabel;
  if (record.context && !contextNode) contextNode = document.createElement("span");
  if (!record.context) {
    contextNode?.remove();
    contextNode = null;
  }
  if (contextNode) {
    if (contextNode.className !== "lf-margin-entry-context")
      contextNode.className = "lf-margin-entry-context";
    if (contextNode.textContent !== record.context)
      contextNode.textContent = record.context;
  }
  const labelParts = [labelWord, ...(contextNode ? [contextNode] : [])];
  if (
    labelNode.childNodes.length !== labelParts.length ||
    labelParts.some((node, index) => labelNode.childNodes[index] !== node)
  )
    labelNode.replaceChildren(...labelParts);

  const countNode = control.querySelector(":scope > .lf-margin-count");
  const anatomy = [glyphNode, spaceNode, labelNode, ...(countNode ? [countNode] : [])];
  if (
    control.childNodes.length !== anatomy.length ||
    anatomy.some((node, index) => control.childNodes[index] !== node)
  )
    control.replaceChildren(...anatomy);
  if (!control.hasAttribute("aria-label"))
    control.setAttribute("aria-label", record.label);
  return control;
}

export function syncMarginEntryCount(control, count) {
  let badge = control.querySelector(":scope > .lf-margin-count");
  if (count <= 1) {
    badge?.remove();
    return;
  }
  if (!badge) badge = document.createElement("span");
  if (badge.className !== "lf-margin-count") badge.className = "lf-margin-count";
  if (badge.getAttribute("aria-hidden") !== "true")
    badge.setAttribute("aria-hidden", "true");
  if (badge.textContent !== String(count)) badge.textContent = count;
  if (control.lastChild !== badge) control.append(badge);
}

export function setMarginEntryState(control, state) {
  if (!(control instanceof Element) || !control.classList.contains("lf-margin-entry"))
    throw new TypeError("A margin entry state needs a margin entry");
  if (!STATES.has(state)) throw new TypeError(`Unknown margin entry state: ${state}`);
  marginEntryRecord(control).state = state;
  keeps(control, "data-lf-state", state);
  if (state === "busy") keeps(control, "aria-busy", "true");
  else control.removeAttribute("aria-busy");
  return control;
}

export function registerMarginContribution({
  key,
  target,
  controls,
  items = () => [],
  subject = null,
  state = "idle",
  side = "before",
  claim = true,
  reserve = 0,
}) {
  if (!String(key ?? "").trim())
    throw new TypeError("A margin contribution needs a key");
  if (side !== "before" && side !== "after")
    throw new TypeError(`Unknown margin contribution side: ${side}`);
  if (typeof state !== "string" && typeof state !== "function")
    throw new TypeError("A margin contribution's state must be a string or function");
  if (subject != null && typeof subject !== "string" && typeof subject !== "function")
    throw new TypeError("A margin contribution's subject must be a string or function");
  if (typeof state === "string" && !STATES.has(state))
    throw new TypeError(`Unknown margin contribution state: ${state}`);
  if (controls instanceof Element) controls.classList.add("lf-margin-contribution");
  const offered = {
    key: String(key),
    target,
    controls,
    items,
    subject,
    state,
    side,
    claim,
    reserve,
  };
  validateMarginEntries(offered);
  contributions.add(offered);
  changed();
  return {
    update({ immediate = false } = {}) {
      validateMarginEntries(offered);
      changed();
      if (immediate) layoutMarginRows();
    },
    unregister() {
      if (!contributions.delete(offered)) return;
      changed();
      for (const control of marginEntries(controls)) {
        const record = marginEntryRecord(control);
        if (record.owner === offered.key) delete record.owner;
        control.removeAttribute("data-lf-margin-entry-owner");
      }
      controls?.remove();
    },
  };
}
