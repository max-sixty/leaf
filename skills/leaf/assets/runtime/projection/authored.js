/* This module owns typed authored initial values and anchor parentage: the authored
 * initial condition, read once after upgrade and before projection. Those values are
 * inputs to the complete widget projection; no cloned DOM, inverse action, or
 * restoration statement is retained. */
import { recordedWidgetSelector, stateSpecs } from "../registry.js";

export function createAuthoredProjection({ COLLAPSE, quoteFrom, textNodesUnder }) {
  const authoredStates = new Map();
  const authoredParents = new WeakMap();
  const recordedOwner = (member) => {
    const selector = recordedWidgetSelector();
    return selector ? member.closest(selector) : null;
  };
  const ownedRecordMembers = (widget, selector) =>
    [...widget.querySelectorAll(selector)].filter(
      (member) => recordedOwner(member) === widget,
    );

  function domFacet(el, record) {
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

  function rememberAuthoredParents(root = document) {
    const elements = root.nodeType === Node.ELEMENT_NODE ? [root] : [];
    elements.push(...root.querySelectorAll("*"));
    for (const element of elements)
      if (!authoredParents.has(element))
        authoredParents.set(element, element.parentElement);
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
    } else if (record?.kind === "body")
      value = textNodesUnder(widget)
        .map(({ node, start, end }) => node.data.slice(start, end))
        .join("");
    return { action: null, value, detail: record ? { [record.value]: value } : {} };
  }

  function captureAuthoredFacets(root = document) {
    const byTag = new Map();
    for (const { tag, spec } of stateSpecs()) {
      const facets = byTag.get(tag) ?? new Map();
      facets.set(spec.facet, spec);
      byTag.set(tag, facets);
    }
    const positions = {};
    for (const [tag, specs] of byTag) {
      const widgets = [...root.querySelectorAll(tag)];
      if (root.nodeType === Node.ELEMENT_NODE && root.matches(tag))
        widgets.unshift(root);
      for (const widget of widgets) {
        if (!widget.id || authoredStates.has(widget.id)) continue;
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
        authoredStates.set(widget.id, {
          specs,
          positions,
          state: Object.fromEntries(
            [...specs].map(([facet, spec]) => [facet, initialFacet(widget, spec)]),
          ),
        });
      }
    }
  }

  // Comparison is deliberately lossy (body whitespace and position indexes), while
  // rendering always receives the complete initial value above.
  function authoredFacet(coordinate) {
    const [owner, unit, facet] = JSON.parse(coordinate);
    const authored = authoredStates.get(owner);
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

  const unitOf = (e, spec) => (spec.unit === "widget" ? e.widget : e.detail[spec.unit]);
  const stateCoordinate = (owner, unit, spec) =>
    JSON.stringify([owner, unit, spec.facet]);
  return {
    authoredStates,
    authoredParents,
    authoredFacet,
    captureAuthoredFacets,
    domFacet,
    rememberAuthoredParents,
    stateCoordinate,
    unitOf,
  };
}
