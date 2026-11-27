// @ts-check
/* This module owns typed authored initial values and anchor parentage. It decodes the
 * authored initial condition once from validated source markup, before content modules
 * upgrade or render it. Those values are inputs to the complete widget projection; no
 * cloned DOM, inverse action, or restoration statement is retained. */
import { recordedWidgetSelector, stateSpecs } from "../../state/registry.js";
import { NATIVE_MEMBERS } from "../../state/kernel-facts.js";
import { elementReading } from "../../readings/passages.js";
import { readPart } from "../../state/semantic-state.js";
import { dataBody } from "../../lib/data-body.js";
import { authoredRank } from "../../lib/rank.js";

/** @typedef {import("../../../types/domain.js").ActionSpec} ActionSpec */
/** @typedef {import("../../../types/domain.js").AuthoredWidget} AuthoredWidget */
/** @typedef {import("../../../types/domain.js").StateRecord} StateRecord */

/* `rememberAuthoredParents` records parent identities before imports for anchor
   ownership. `stageAuthoredStates` decodes source elements while their validated
   attributes, member order, and data bodies are intact. The complete staged document
   enters the application publisher before its content modules render. Page revisions
   and thread markup use the same boundary, so presentation never becomes a
   semantic input.

   `authoredStates` holds the one typed initial condition per owner. Provenance
   origins compare those same typed values through `state/projection/model.js`; a body's
   Markdown source is never reconstructed from its rendered words.

   The complete initial value, by record kind:

   - `attribute`: the sorted ids of the members carrying the declared attribute
     (`setMembers`);
   - `value`: the attribute string, or `null` when absent;
   - `position`: ordered id lists for each container the widget orders, itself
     included where `within` names its own tag, and each listed unit's authored
     rank (lib/rank.js);
   - `body`: the parsed data body's exact text, including indentation and trailing whitespace;
   - no record: `null` for a widget verb, an empty unit map otherwise.

   Ownership of record members stops at the nearest ancestor recording the same
   physical slot: an attribute set's attribute, or a position. A position's
   container belongs to the nearest element at or above it recording positions, so a
   container and its members have one owner (Python's `projection.container_owner`).
   Other attributes and record kinds coexist, including scalar state on a member or
   container. */
export const authoredStates = readPart((root) => root.document.authored);
export const authoredParents = new WeakMap();

/** @param {Element} member @param {StateRecord} record */
const recordedOwner = (member, record) => {
  const selector = recordedWidgetSelector(record);
  return selector ? (member.parentElement?.closest(selector) ?? null) : null;
};
/** The members of the set `record` keeps on `widget`, in document order, or with
 * `marked` those the markup marks as in it: each element with an id whose nearest
 * ancestor recording the same attribute is `widget`, as the server's index reads them
 * (`projection.record_members`). A Leaf element is a member, and so is a native
 * element HTML marks with the record's attribute, as `checked` marks a checkbox
 * (`$native-members`). Any other native element is the author's own control: an
 * `<option selected>` inside an option's card is no pick.
 * @param {Element} widget
 * @param {Extract<StateRecord, {kind: "attribute"}>} record
 * @param {boolean} [marked] */
export const setMembers = (widget, record, marked = false) => {
  const native = NATIVE_MEMBERS[record.attr];
  return [...widget.querySelectorAll(marked ? `[${record.attr}]` : "[id]")].filter(
    (member) =>
      member.id &&
      (member.localName.startsWith("lf-") ||
        (member.localName === native?.tag &&
          native.type.includes((member.getAttribute("type") ?? "").toLowerCase()))) &&
      recordedOwner(member, record) === widget,
  );
};
/** @param {Element} widget @param {Extract<StateRecord, {kind: "attribute"}>} record */
const markedIds = (widget, record) =>
  setMembers(widget, record, true)
    .map((member) => member.id)
    .sort();

/** @param {Element} el @param {StateRecord} record */
export function domValue(el, record) {
  if (record.kind === "attribute") return markedIds(el, record);
  if (record.kind === "value") return el.getAttribute(record.attr);
  if (record.kind === "position") return el.closest(record.within)?.id ?? null;
  return elementReading(el);
}

// `parent` states where a root that is not yet in the document will stand, so the
// readings that ask about its place are right before insertion; a root already in the
// document answers for itself.
/** @param {Document | Element | DocumentFragment} [root] @param {Element | null} [parent]
 * @param {(node: Element) => Element} [original] */
export function rememberAuthoredParents(
  root = document,
  parent = root.parentElement,
  original = (node) => node,
) {
  /** @param {Element} element */
  const remember = (element) => {
    const live = original(element);
    if (authoredParents.has(live)) return;
    authoredParents.set(
      live,
      element.parentElement
        ? original(element.parentElement)
        : (parent ?? live.parentElement),
    );
  };
  if (root.nodeType === Node.ELEMENT_NODE) remember(/** @type {Element} */ (root));
  for (const element of root.querySelectorAll("*")) remember(element);
}

/** @param {Element} widget @param {ActionSpec} spec @returns {AuthoredWidget["state"][string]} */
function initialState(widget, spec) {
  const record = spec.record;
  if (spec.unit !== "widget") {
    /** @type {Record<string, string[]>} */
    const value = {};
    if (record?.kind !== "position") return { value, units: {} };
    /** @type {Record<string, string>} */
    const ranks = {};
    const containers = [...widget.querySelectorAll(record.within)];
    if (widget.matches(record.within)) containers.unshift(widget);
    for (const container of containers)
      if (
        container.id &&
        container.closest(recordedWidgetSelector(record)) === widget
      ) {
        const ids = [...container.children]
          .filter((part) => part.id)
          .map((part) => part.id);
        value[container.id] = ids;
        ids.forEach((id, index) => (ranks[id] = authoredRank(index)));
      }
    return { value, ranks, units: {} };
  }
  let value = null;
  if (record?.kind === "attribute") value = markedIds(widget, record);
  else if (record?.kind === "value") value = widget.getAttribute(record.attr);
  else if (record?.kind === "body") value = dataBody(widget);
  return { action: null, value, detail: record ? { value } : {} };
}

/** @param {Document | Element | DocumentFragment} root @returns {Map<string, AuthoredWidget>} */
export function stageAuthoredStates(root) {
  /** @type {Map<string, AuthoredWidget>} */
  const captured = new Map();
  /** @type {Map<string, Map<string, ActionSpec>>} */
  const byTag = new Map();
  for (const { tag, verb, spec } of stateSpecs()) {
    const specs = byTag.get(tag) ?? new Map();
    specs.set(verb, spec);
    byTag.set(tag, specs);
  }
  for (const [tag, specs] of byTag) {
    const widgets = [...root.querySelectorAll(tag)];
    if (root instanceof Element && root.matches(tag)) widgets.unshift(root);
    for (const widget of widgets) {
      if (!widget.id) continue;
      captured.set(widget.id, {
        tag,
        specs,
        state: Object.fromEntries(
          [...specs].map(([verb, spec]) => [verb, initialState(widget, spec)]),
        ),
      });
    }
  }
  return captured;
}
