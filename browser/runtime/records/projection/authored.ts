/* This module owns typed authored initial values and anchor parentage. It decodes the
 * authored initial condition once from validated source markup, before content modules
 * upgrade or render it. Those values are inputs to the complete widget projection; no
 * cloned DOM, inverse action, or restoration statement is retained. */
import { exhibits, recordedWidgetSelector, stateSpecs } from "../../state/registry.js";
import { runtime } from "../../state/context.js";
import { NATIVE_MEMBERS } from "../../state/kernel-facts.js";
import { readPart } from "../../state/semantic-state.js";
import { dataBody } from "../../lib/data-body.js";
import { authoredRank } from "../../lib/rank.js";
import type { ActionSpec, AuthoredWidget, StateRecord } from "../../../types/domain.js";

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
     (`markedMembers`), one radio of each radio group among them;
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
const authoredParents = new WeakMap();

const recordedOwner = (member: Element, record: StateRecord) => {
  const selector = recordedWidgetSelector(record);
  return selector ? (member.parentElement?.closest(selector) ?? null) : null;
};
// An element's parent in the authored document, which layout may since have moved.
export const authoredParent = (element: Element): Element | null =>
  authoredParents.has(element) ? authoredParents.get(element) : element.parentElement;

// Whether an element stands strictly inside an `exhibit` widget in the authored
// document, so what it holds is quoted material rather than controls. The exhibit
// itself is no mention, as the server reads it (`structure.quoted_in`);
// `tests/exhibit_cases.json` holds both runtimes to one set of cases.
export const quotedBy = (element: Element) => {
  for (let node = authoredParent(element); node; node = authoredParent(node))
    if (exhibits(node, runtime.registry[node.localName])) return true;
  return false;
};

// The elements with an id that may be native members (`nativeMarks`).
export const NATIVE_CANDIDATES = [
  ...new Set(Object.values(NATIVE_MEMBERS).map(({ tag }) => `${tag}[id]`)),
].join(",");

/** The attributes a native element is a member under (`$native-members`), as HTML
 * marks it, as `checked` marks a checkbox: none for any other element, and none
 * inside an SVG, which the server's reading keeps whole (`structure.SourceDocument`). */
export const nativeMarks = (element: Element) =>
  element.namespaceURI === "http://www.w3.org/1999/xhtml" && !element.closest("svg")
    ? Object.entries(NATIVE_MEMBERS)
        .filter(
          ([, { tag, type }]) =>
            element.localName === tag &&
            type.includes((element.getAttribute("type") ?? "").toLowerCase()),
        )
        .map(([attr]) => attr)
    : [];

/** The members of the set `record` keeps on `widget` that its markup marks as in it,
 * as the server's index reads them (`projection.attribute_marks`): each element with
 * an id and the attribute whose nearest ancestor recording that attribute is
 * `widget`, with no exhibit between. A Leaf element is a member, and so is a native
 * element HTML marks with the attribute (`nativeMarks`). Any other native element is
 * the author's own control: an `<option selected>` inside an option's card is no
 * pick. Of the radios of one group, HTML checks the last its markup marks. */
const markedMembers = (
  widget: Element,
  record: Extract<StateRecord, { kind: "attribute" }>,
) => {
  const quoted = quotedBy(widget);
  const members = [...widget.querySelectorAll(`[id][${record.attr}]`)].filter(
    (member) =>
      (member.localName.startsWith("lf-") ||
        nativeMarks(member).includes(record.attr)) &&
      recordedOwner(member, record) === widget &&
      quotedBy(member) === quoted,
  );
  // A radio group is the radios of one name in one form, or in one tree where they
  // have none, as the arrival reads it (base/document-inputs.js).
  const last = new Map<Node, Map<string, Element>>();
  for (const member of members)
    if (radio(member)) {
      const scope = member.form ?? member.getRootNode();
      last.set(scope, (last.get(scope) ?? new Map()).set(member.name, member));
    }
  const shown = new Set([...last.values()].flatMap((names) => [...names.values()]));
  return members.filter((member) => !radio(member) || shown.has(member));
};
const radio = (element: Element): element is HTMLInputElement =>
  element instanceof HTMLInputElement && element.type === "radio" && !!element.name;

// `parent` states where a root that is not yet in the document will stand, so the
// readings that ask about its place are right before insertion; a root already in the
// document answers for itself.
export function rememberAuthoredParents(
  root: Document | Element | DocumentFragment = document,
  parent: Element | null = root.parentElement,
  original: (node: Element) => Element = (node) => node,
) {
  const remember = (element: Element) => {
    const live = original(element);
    if (authoredParents.has(live)) return;
    authoredParents.set(
      live,
      element.parentElement
        ? original(element.parentElement)
        : (parent ?? live.parentElement),
    );
  };
  if (root.nodeType === Node.ELEMENT_NODE) remember(root as Element);
  for (const element of root.querySelectorAll("*")) remember(element);
}

function initialState(
  widget: Element,
  spec: ActionSpec,
): AuthoredWidget["state"][string] {
  const record = spec.record;
  if (spec.unit !== "widget") {
    const value: Record<string, string[]> = {};
    if (record?.kind !== "position") return { value, units: {} };
    const ranks: Record<string, string> = {};
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
  if (record?.kind === "attribute")
    value = markedMembers(widget, record)
      .map((member) => member.id)
      .sort();
  else if (record?.kind === "value") value = widget.getAttribute(record.attr);
  else if (record?.kind === "body") value = dataBody(widget);
  return { action: null, value, detail: record ? { value } : {} };
}

export function stageAuthoredStates(
  root: Document | Element | DocumentFragment,
): Map<string, AuthoredWidget> {
  const captured = new Map<string, AuthoredWidget>();
  const byTag = new Map<string, Map<string, ActionSpec>>();
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
