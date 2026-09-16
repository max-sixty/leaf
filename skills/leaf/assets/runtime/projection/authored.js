/* This module owns typed authored initial values and anchor parentage. It decodes the
 * authored initial condition once from validated source markup, before content modules
 * upgrade or render it. Those values are inputs to the complete widget projection; no
 * cloned DOM, inverse action, or restoration statement is retained. */
import { recordedWidgetSelector, stateSpecs } from "../registry.js";
import { COLLAPSE, quoteFrom, textNodesUnder } from "../passages.js";
import { readApplication } from "../semantic-state.js";

/* The authored initial condition, read once from validated source before upgrade.
   These typed values are inputs to the complete widget projection; no cloned DOM,
   inverse action, or restoration statement is retained.

   `rememberAuthoredParents` records parent identities before imports for anchor
   ownership. `stageAuthoredFacets` decodes source elements while their validated
   attributes, member order, and data bodies are intact. The complete staged document
   enters the application publisher before its content modules render. Page revisions
   and frozen thread markup use the same boundary, so presentation never becomes a
   semantic input.

   `authoredStates` holds the one typed initial condition per owner. Comparison readings
   come from those same values, collapsing body whitespace and omitting position indexes
   only where origin/diff checks require those comparisons.

   The complete initial value, by record kind:

   - `attribute`: sorted owned ids carrying the declared attribute;
   - `value`: the attribute string, or `null` when absent;
   - `position`: ordered id lists per container; an individual widget also names its
     containing id and index;
   - `body`: the data body's exact words, with source-layout indentation removed;
   - no record: `null` for a widget facet, an empty unit map otherwise.

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

export function domFacet(el, record) {
  if (record.kind === "attribute")
    return ownedRecordMembers(el, `[${record.attr}]`)
      .map((o) => o.id)
      .filter(Boolean)
      .sort()
      .join(" ");
  if (record.kind === "value") return el.getAttribute(record.attr);
  if (record.kind === "position") return el.closest(record.within)?.id ?? null;
  return quoteFrom(textNodesUnder(el));
}

// `parent` states where a root that is not yet in the document will stand, so the
// readings that ask about its place are right before insertion; a root already in the
// document answers for itself.
export function rememberAuthoredParents(root = document, parent = root.parentElement) {
  if (root.nodeType === Node.ELEMENT_NODE && !authoredParents.has(root))
    authoredParents.set(root, parent);
  for (const element of root.querySelectorAll("*"))
    if (!authoredParents.has(element))
      authoredParents.set(element, element.parentElement);
}

// A body record is licensed only for x-content: data, whose validated source is one
// direct <pre>. Keep the source's words while removing the layout its surrounding HTML
// needed: one opening newline, trailing whitespace, and the common indentation of its
// nonblank lines.
function decodeBodyRecord(widget) {
  const raw = widget
    .querySelector(":scope > pre")
    .textContent.replace(/^\n/, "")
    .replace(/\s+$/, "");
  const lines = raw.split("\n");
  const indents = lines
    .filter((line) => line.trim())
    .map((line) => line.match(/^[ \t]*/)[0].length);
  const cut = indents.length ? Math.min(...indents) : 0;
  return lines.map((line) => line.slice(cut)).join("\n");
}

function initialFacet(widget, spec) {
  const record = spec.record;
  if (spec.unit !== "widget") {
    const value = {};
    if (record?.kind === "position" && spec.unit !== "widget")
      for (const container of widget.querySelectorAll(record.within))
        if (container.id && recordedOwner(container) === widget)
          value[container.id] = [...container.children]
            .filter((part) => part.id)
            .map((part) => part.id);
    return { value, units: {} };
  }
  let value = null;
  if (record?.kind === "attribute")
    value = ownedRecordMembers(widget, `[${record.attr}]`)
      .map((member) => member.id)
      .filter(Boolean)
      .sort();
  else if (record?.kind === "value") value = widget.getAttribute(record.attr);
  else if (record?.kind === "position") {
    const container = widget.closest(record.within);
    value = container?.id ?? null;
    return {
      action: null,
      value,
      detail: {
        [record.value]: value,
        [record.order]: container
          ? [...container.children].filter((part) => part.id).indexOf(widget)
          : 0,
      },
    };
  } else if (record?.kind === "body") value = decodeBodyRecord(widget);
  return { action: null, value, detail: record ? { [record.value]: value } : {} };
}

export function stageAuthoredFacets(root = document, existing = authoredStates()) {
  const captured = new Map();
  const byTag = new Map();
  for (const { tag, spec } of stateSpecs()) {
    const facets = byTag.get(tag) ?? new Map();
    facets.set(spec.facet, spec);
    byTag.set(tag, facets);
  }
  const positions = {};
  for (const [tag, specs] of byTag) {
    const widgets = [...root.querySelectorAll(tag)];
    if (root.nodeType === Node.ELEMENT_NODE && root.matches(tag)) widgets.unshift(root);
    for (const widget of widgets) {
      if (!widget.id || existing.has(widget.id)) continue;
      for (const spec of specs.values())
        if (spec.unit === "widget" && spec.record?.kind === "position")
          for (const container of [
            ...root.querySelectorAll(spec.record.within),
            widget.closest(spec.record.within),
          ].filter(Boolean))
            if (container.id && !positions[container.id])
              positions[container.id] = [...container.children]
                .filter((part) => part.id)
                .map((part) => part.id);
      captured.set(widget.id, {
        tag,
        specs,
        positions,
        state: Object.fromEntries(
          [...specs].map(([facet, spec]) => [facet, initialFacet(widget, spec)]),
        ),
      });
    }
  }
  return captured;
}

// Comparison is deliberately lossy (body whitespace and position indexes), while
// rendering always receives the complete initial value above.
export function authoredFacet(coordinate) {
  const [owner, unit, facet] = JSON.parse(coordinate);
  const authored = authoredStates().get(owner);
  if (!authored) return undefined;
  const spec = authored.specs.get(facet);
  const record = spec.record;
  const value = authored.state[facet].value;
  if (record?.kind === "attribute") return value.join(" ");
  if (record?.kind === "body") return value.replace(COLLAPSE, " ").trim();
  if (record?.kind === "position" && spec.unit !== "widget")
    return (
      Object.keys(value).find((container) => value[container].includes(unit)) ?? null
    );
  return value;
}

export const stateCoordinate = (owner, unit, spec) =>
  JSON.stringify([owner, unit, spec.facet]);
