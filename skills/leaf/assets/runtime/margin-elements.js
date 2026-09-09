/* The public grammar and registry for controls contributed to a page target's margin.

   Contributors own their verbs, events, and semantic engagement state. This module owns
   the shared control anatomy, validates stable identities within each contribution, and
   retains registrations while live documents and widgets reconnect. The living margin
   consumes that registry to choose and place controls; contributors never place RHS rows.

   A margin element has independent behavior, tone, role, and lifecycle axes. A
   disclosure owns `aria-expanded` by default, and every element owns its tab seat by
   default. Callers opt out only when another named surface is the sole writer. Proxies
   read the retained record and forward transient native state while activation remains
   with the contributor's original control. */

import { layoutMarginRows } from "./margin-layout.js";
import { iconElement } from "./icons.js";
import { keeps } from "./widget-elements.js";

const contributions = new Set();
const listeners = new Set();

export const MARGIN_ELEMENT_SCHEMA = Object.freeze({
  tones: Object.freeze(["neutral", "positive", "negative"]),
  behaviors: Object.freeze(["action", "disclosure", "status"]),
  states: Object.freeze(["idle", "engaged", "busy", "failed"]),
  roles: Object.freeze([
    "complete",
    "escape",
    "primary",
    "secondary",
    "reading",
    "overflow",
  ]),
});

const TONES = new Set(MARGIN_ELEMENT_SCHEMA.tones);
const BEHAVIORS = new Set(MARGIN_ELEMENT_SCHEMA.behaviors);
const STATES = new Set(MARGIN_ELEMENT_SCHEMA.states);
const ROLES = new Set(MARGIN_ELEMENT_SCHEMA.roles);
const STATE_PRIORITY = new Map([
  ["failed", 0],
  ["busy", 1],
  ["engaged", 2],
  ["idle", 3],
]);
const ROLE_PRIORITY = new Map([
  ["complete", 0],
  ["escape", 1],
  ["primary", 2],
  ["secondary", 3],
  ["reading", 4],
  ["overflow", 5],
]);

const RECORD = Symbol("Leaf margin element record");
const FORWARDED_ATTRIBUTES = [
  "aria-busy",
  "aria-controls",
  "aria-disabled",
  "aria-expanded",
  "aria-haspopup",
  "aria-pressed",
];

const changed = () => {
  for (const listener of listeners) listener();
};

export const marginContributionEntries = () => contributions.values();

export const marginElementStateRank = (state) => STATE_PRIORITY.get(state);

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

export function compareMarginControlRecords(left, right) {
  const state =
    STATE_PRIORITY.get(marginContributionState(left.offered)) -
    STATE_PRIORITY.get(marginContributionState(right.offered));
  if (state) return state;
  const role =
    ROLE_PRIORITY.get(marginElementRecord(left.control).role) -
    ROLE_PRIORITY.get(marginElementRecord(right.control).role);
  if (role) return role;
  const contribution = left.offered.key.localeCompare(right.offered.key);
  return (
    contribution ||
    marginElementRecord(left.control).key.localeCompare(
      marginElementRecord(right.control).key,
    )
  );
}

export function watchMarginContributions(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export const visibleMarginElementLabel = ({ behavior, label }) =>
  behavior !== "disclosure" || label.endsWith("…") ? label : `${label}…`;

export function marginElementRecord(control) {
  const record = control?.[RECORD];
  if (!record)
    throw new TypeError("A contributed margin element must use marginElement");
  return record;
}

export function marginElements(controls) {
  if (!(controls instanceof Element)) return [];
  if (controls.matches(".lf-margin-element")) return [controls];
  return [...controls.querySelectorAll(".lf-margin-element")];
}

function validateMarginElements(offered) {
  const keys = new Set();
  for (const control of marginElements(offered.controls)) {
    const record = marginElementRecord(control);
    if (keys.has(record.key))
      throw new TypeError(
        `Duplicate margin element key "${record.key}" in margin contribution "${offered.key}"`,
      );
    if (record.owner && record.owner !== offered.key)
      throw new TypeError(
        `margin element "${record.key}" already belongs to margin contribution "${record.owner}"`,
      );
    keys.add(record.key);
    record.owner = offered.key;
    control.dataset.lfMarginElementOwner = offered.key;
  }
}

export function syncForwardedMarginElementState(projection, source) {
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

export function marginElement(
  control,
  {
    glyph = null,
    icon = null,
    key,
    label,
    context = null,
    behavior = "action",
    tone = "neutral",
    role = "primary",
    state = "idle",
    writesRelation = true,
    writesSeat = true,
  },
) {
  if (!(control instanceof Element))
    throw new TypeError("A margin element needs an Element control");
  if (!String(key ?? "").trim()) throw new TypeError("A margin element needs a key");
  if (Boolean(String(glyph ?? "").trim()) === Boolean(icon))
    throw new TypeError("A margin element needs exactly one glyph or icon");
  if (!String(label ?? "").trim())
    throw new TypeError("A margin element needs a label");
  if (!TONES.has(tone)) throw new TypeError(`Unknown margin element tone: ${tone}`);
  if (!BEHAVIORS.has(behavior))
    throw new TypeError(`Unknown margin element behavior: ${behavior}`);
  if (!ROLES.has(role)) throw new TypeError(`Unknown margin element role: ${role}`);
  const record = control[RECORD] ?? {};
  Object.assign(record, {
    key: String(key),
    glyph: glyph == null ? null : String(glyph),
    icon,
    label: String(label),
    context: String(context ?? "").trim() || null,
    behavior,
    tone,
    role,
    state,
    writesRelation,
  });
  control[RECORD] = record;

  if (!control.classList.contains("lf-margin-element"))
    control.classList.add("lf-margin-element");
  control.removeAttribute("title");
  keeps(control, "data-lf-margin-element-key", record.key);
  keeps(control, "data-lf-behavior", record.behavior);
  keeps(control, "data-lf-tone", record.tone);
  keeps(control, "data-lf-role", record.role);
  keeps(control, "data-lf-offer", behavior === "status" ? "" : "button");
  marginElementState(control, state);
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
    ":scope > :is(.lf-margin-element-glyph, .lf-margin-element-icon)",
  );
  let spaceNode = control.querySelector(":scope > .lf-margin-element-space");
  let labelNode = control.querySelector(":scope > .lf-margin-element-label");
  if (icon) {
    if (!(glyphNode instanceof SVGSVGElement) || glyphNode.dataset.lfIcon !== icon)
      glyphNode = iconElement(icon);
  } else {
    if (!(glyphNode instanceof HTMLSpanElement))
      glyphNode = document.createElement("span");
    if (glyphNode.className !== "lf-margin-element-glyph")
      glyphNode.className = "lf-margin-element-glyph";
    glyphNode.removeAttribute("data-lf-icon");
    if (glyphNode.textContent !== glyph) glyphNode.textContent = glyph;
  }
  if (!spaceNode) spaceNode = document.createElement("span");
  if (!labelNode) labelNode = document.createElement("span");
  if (glyphNode.getAttribute("aria-hidden") !== "true")
    glyphNode.setAttribute("aria-hidden", "true");
  if (spaceNode.className !== "lf-margin-element-space")
    spaceNode.className = "lf-margin-element-space";
  if (spaceNode.getAttribute("aria-hidden") !== "true")
    spaceNode.setAttribute("aria-hidden", "true");
  if (spaceNode.textContent !== " ") spaceNode.textContent = " ";
  if (labelNode.className !== "lf-margin-element-label")
    labelNode.className = "lf-margin-element-label";
  if (labelNode.getAttribute("aria-hidden") !== "true")
    labelNode.setAttribute("aria-hidden", "true");

  const visibleLabel = visibleMarginElementLabel(record);
  let labelWord = labelNode.querySelector(":scope > .lf-margin-element-label-word");
  let contextNode = labelNode.querySelector(":scope > .lf-margin-element-context");
  if (!labelWord) labelWord = document.createElement("span");
  if (labelWord.className !== "lf-margin-element-label-word")
    labelWord.className = "lf-margin-element-label-word";
  if (labelWord.textContent !== visibleLabel) labelWord.textContent = visibleLabel;
  if (record.context && !contextNode) contextNode = document.createElement("span");
  if (!record.context) {
    contextNode?.remove();
    contextNode = null;
  }
  if (contextNode) {
    if (contextNode.className !== "lf-margin-element-context")
      contextNode.className = "lf-margin-element-context";
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

export function syncMarginElementCount(control, count) {
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

export function marginElementState(control, state) {
  if (!(control instanceof Element) || !control.classList.contains("lf-margin-element"))
    throw new TypeError("A margin element state needs a margin element");
  if (!STATES.has(state)) throw new TypeError(`Unknown margin element state: ${state}`);
  marginElementRecord(control).state = state;
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
  validateMarginElements(offered);
  contributions.add(offered);
  changed();
  return {
    update({ immediate = false } = {}) {
      validateMarginElements(offered);
      changed();
      if (immediate) layoutMarginRows();
    },
    unregister() {
      if (!contributions.delete(offered)) return;
      changed();
      for (const control of marginElements(controls)) {
        const record = marginElementRecord(control);
        if (record.owner === offered.key) delete record.owner;
        control.removeAttribute("data-lf-margin-element-owner");
      }
      controls?.remove();
    },
  };
}
