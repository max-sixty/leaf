/* This module owns typed authored initial values and anchor parentage. It decodes the
 * authored initial condition once from validated source markup, before content modules
 * upgrade or render it. Those values are inputs to the complete widget projection; no
 * cloned DOM, inverse action, or restoration statement is retained. */
import { recordedWidgetSelector, stateSpecs } from "../registry.js";
import { elementReading } from "../passages.js";
import { readApplication } from "../semantic-state.js";
import { dataBody } from "../widget-upgrade.js";
import { authoredRank } from "./model.js";
import { initialParent, initialSource } from "../initial-render.js";

/* The authored initial condition, read once from validated source before upgrade.
   These typed values are inputs to the complete widget projection; no cloned DOM,
   inverse action, or restoration statement is retained.

   `rememberAuthoredParents` records parent identities before imports for anchor
   ownership. `stageAuthoredStates` decodes source elements while their validated
   attributes, member order, and data bodies are intact. The complete staged document
   enters the application publisher before its content modules render. Page revisions
   and frozen thread markup use the same boundary, so presentation never becomes a
   semantic input.

   `authoredStates` holds the one typed initial condition per owner. Provenance
   origins compare those same typed values through `projection/model.js`; a body's
   Markdown source is never reconstructed from its rendered words.

   The complete initial value, by record kind:

   - `attribute`: sorted owned ids carrying the declared attribute;
   - `value`: the attribute string, or `null` when absent;
   - `position`: ordered id lists per container and each listed unit's authored rank
     (projection/model.js);
   - `body`: the parsed data body's exact text, including indentation and trailing whitespace;
   - no record: `null` for a widget verb, an empty unit map otherwise.

   Ownership of record members stops at `recordedOwner`, the nearest widget with a
   declared record. A custom outer container must not capture or restore a nested
   recorded widget's members. */
export const authoredStates = () => readApplication().document.authored;
export const authoredParents = new WeakMap();
const recordedOwner = (member) => {
  const selector = recordedWidgetSelector();
  return selector ? member.closest(selector) : null;
};
const ownedRecordMembers = (widget, selector) =>
  [...widget.querySelectorAll(selector)].filter(
    (member) => recordedOwner(member) === widget,
  );

export function domValue(el, record) {
  if (record.kind === "attribute")
    return ownedRecordMembers(el, `[${record.attr}]`)
      .map((o) => o.id)
      .filter(Boolean)
      .sort()
      .join(" ");
  if (record.kind === "value") return el.getAttribute(record.attr);
  if (record.kind === "position") return el.closest(record.within)?.id ?? null;
  return elementReading(el);
}

// `parent` states where a root that is not yet in the document will stand, so the
// readings that ask about its place are right before insertion; a root already in the
// document answers for itself.
export function rememberAuthoredParents(root = document, parent = root.parentElement) {
  if (root.nodeType === Node.ELEMENT_NODE && !authoredParents.has(root))
    authoredParents.set(root, root.parentElement ? initialParent(root) : parent);
  for (const element of root.querySelectorAll("*"))
    if (!authoredParents.has(element))
      authoredParents.set(element, initialParent(element));
}

function initialState(widget, spec) {
  const record = spec.record;
  if (spec.unit !== "widget") {
    const value = {};
    if (record?.kind !== "position") return { value, units: {} };
    const ranks = {};
    for (const container of widget.querySelectorAll(record.within))
      if (container.id && recordedOwner(container) === widget) {
        value[container.id] = [...container.children]
          .filter((part) => part.id)
          .map((part) => part.id);
        value[container.id].forEach((id, index) => (ranks[id] = authoredRank(index)));
      }
    return { value, ranks, units: {} };
  }
  let value = null;
  if (record?.kind === "attribute")
    value = ownedRecordMembers(widget, `[${record.attr}]`)
      .map((member) => member.id)
      .filter(Boolean)
      .sort();
  else if (record?.kind === "value") value = widget.getAttribute(record.attr);
  else if (record?.kind === "body") value = dataBody(widget);
  return { action: null, value, detail: record ? { value } : {} };
}

export function stageAuthoredStates(root = document, existing = authoredStates()) {
  root = initialSource(root);
  const captured = new Map();
  const byTag = new Map();
  for (const { tag, verb, spec } of stateSpecs()) {
    const specs = byTag.get(tag) ?? new Map();
    specs.set(verb, spec);
    byTag.set(tag, specs);
  }
  for (const [tag, specs] of byTag) {
    const widgets = [...root.querySelectorAll(tag)];
    if (root.nodeType === Node.ELEMENT_NODE && root.matches(tag)) widgets.unshift(root);
    for (const widget of widgets) {
      if (!widget.id || existing.has(widget.id)) continue;
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

export const stateCoordinate = (owner, unit, verb) =>
  JSON.stringify([owner, unit, verb]);
