/* The vocabulary's query doors, which is how the layer stays open.

   `elementDeclarations` and `tagsDeclaring` are the general iteration doors. `stateSpecs` is
   the one traversal of every tag's `verbs`, whichever side writes each verb. New code
   that loops over tag names or repeats that traversal is a closed list in another form. CSS selectors
   follow the same rule: a list of framed widget tags is still a closed consumer. */

import { installLanguagePaths } from "../base/language-paths.js";
import { runtime } from "./context.js";
import { isElementName } from "./registry-contract.js";
import { kept, version } from "./kept.js";
import type { WidgetDeclaration } from "../../types/contract.js";
import type { ActionSpec, StateRecord } from "../../types/domain.js";

// The vocabulary, composed per page: which tags a module upgrades, and which of their
// attributes are words the page says. Empty only during the real fetch interval, when
// the already-wired chrome can legitimately be used; a failed fetch still rejects
// startup rather than becoming an empty vocabulary.
/** A deciding verb and the member tags each outcome retires, stamped by registry.contract.stamp_decisions. */
export type Decision = { verb: string; retires: Record<string, readonly string[]> };
export const registry = runtime.registry;

// Which vocabulary stands: moved when a reader finds the layer's generation changed,
// as the vocabulary is adopted (`adoptRegistry`), and on every reading before one is,
// so nothing read of a vocabulary still being written is kept.
let readGeneration: string | undefined;
const vocabulary = version(() => {
  const generation = registry.$layer?.generation;
  if (generation && generation === readGeneration) return;
  readGeneration = generation;
  vocabulary.move();
});

// A reading of the vocabulary, kept until its generation says the vocabulary changed
// (kept.js), since a reader that asks for each command a page declares redoes it many
// times for one input.
export const perVocabulary = <T>(read: () => T): (() => T) =>
  kept(() => {
    vocabulary.read();
    return read();
  });

// Ordinary keys are the authoring vocabulary: exact custom-element names and CSS
// selectors. Only exact names are widget declarations; `lf-options.selected` is
// an idiom selector, by the `$names.widget` grammar Python reads too. Every widget
// traversal goes through this owner rather than treating all vocabulary as widgets.
export const elementDeclarations: () => readonly [string, WidgetDeclaration][] =
  perVocabulary(() => Object.entries(registry).filter(([tag]) => isElementName(tag)));

// Take in the fetched vocabulary. A verb's writer is read from `$states`
// (`registry-contract.js`), where composition stamped it.
// The layer-wide `$` declarations are frozen as they arrive, so every reader shares the
// registry's own value and none can write it.
export function adoptRegistry(declarations: typeof registry) {
  for (const [name, value] of Object.entries(declarations))
    if (name.startsWith("$")) freeze(value);
  Object.assign(registry, declarations);
  if (declarations.$languages) installLanguagePaths(declarations.$languages.paths);
}

function freeze(value: unknown) {
  if (value === null || typeof value !== "object" || Object.isFrozen(value)) return;
  for (const child of Object.values(value)) freeze(child);
  Object.freeze(value);
}

const recordSlot = (record: StateRecord) =>
  JSON.stringify([record.kind, "attr" in record ? record.attr : null]);
// Every tag's verbs, and the tags each recorded slot selects, read once for each
// vocabulary.
const indexedState = perVocabulary(() => {
  const generation = registry.$layer?.generation;
  if (typeof generation !== "string" || !generation)
    throw new Error("leaf: state vocabulary requested before registry loaded");

  const specs: { tag: string; verb: string; spec: ActionSpec }[] = [];
  for (const [tag, entry] of elementDeclarations())
    for (const [verb, spec] of Object.entries(entry.verbs ?? {}))
      specs.push({ tag, verb, spec });
  const recordTags: Map<string, Set<string>> = new Map();
  for (const { tag, spec } of specs) {
    if (!spec.record) continue;
    const slot = recordSlot(spec.record);
    const tags = recordTags.get(slot) ?? new Set();
    tags.add(tag);
    recordTags.set(slot, tags);
  }
  const recordSelectors = new Map(
    [...recordTags].map(([slot, tags]) => [slot, [...tags].join(",")]),
  );
  return { recordSelectors, specs };
});

// Whether two verbs' records read their state from markup the same way. A value or
// attribute record's `property` and `event` say how the page's elements keep the
// state (host/element-integration.js, "Recorded properties"), so two records that
// differ only there are one, as Python's `registry.contract.recorded` reads them.
const markupRecord = (record: StateRecord | undefined) =>
  record?.kind === "value" || record?.kind === "attribute"
    ? { kind: record.kind, attr: record.attr }
    : (record ?? null);
export const sameRecord = (
  one: StateRecord | undefined,
  other: StateRecord | undefined,
) => JSON.stringify(markupRecord(one)) === JSON.stringify(markupRecord(other));

export const stateSpecs = () => indexedState().specs;
export const recordedWidgetSelector = (record: StateRecord) =>
  indexedState().recordSelectors.get(recordSlot(record)) ?? "";

// The declaration a widget's tag has: its attribute schema and the facts it declares,
// each under its own name (`$keys`). An idiom, which a selector keys, is no element's
// declaration.
export const declarationFor = (
  el: Element | null | undefined,
): WidgetDeclaration | undefined =>
  el && isElementName(el.localName) ? registry[el.localName] : undefined;

export type InputDeclaration = NonNullable<WidgetDeclaration["inputs"]>[string];

// The attributes that bind a declared input (`inputs`), which markup binds by setting
// one: the attribute `source` names holds a page source's id, and the one `reference`
// names the id of a widget whose output the input reads. Python's list of the two keys
// is `schema.INPUT_BINDINGS`, and the declaration's type is generated from its schema.
export const bindingAttributes = ({ source, reference }: InputDeclaration) =>
  [source, reference].flatMap((attribute) => attribute ?? []);

// How a tag is decided, or null where no verb decides it: `verb`, the verb (`verbs`)
// whose detail `outcome` is the decision, and `retires`, each outcome's member
// tags that leave the page under it (`retired-when`). Composition stamps it into
// the vocabulary as `$decisions` (Python's `registry.contract.stamp_decisions`), so
// nothing here re-derives it.
export const decisionFor = (tag: string): Decision | null =>
  registry.$decisions[tag] ?? null;

// The widgets at or under `root` whose declaration `holds` answers for, in document
// order. The browser matches their tags, so a root holding a long document of plain
// rows, as a tab set's panel can, costs a native match of each row rather than a
// script's look at it. The match costs more for each tag it names, so a question about
// some widgets names only theirs.
export const declaredElements = (
  root: Document | DocumentFragment | Element,
  holds: (entry: WidgetDeclaration) => unknown = () => true,
) => {
  const tags = tagsDeclaring(holds);
  if (!tags.length) return [];
  const selector = tags.join(",");
  const found = [...root.querySelectorAll(selector)];
  if (root instanceof Element && root.matches(selector)) found.unshift(root);
  return found;
};

// Which widgets answer a question the way the caller means it, read from what they
// declare. Nothing out here names a widget: a behaviour some widgets want is a fact
// they declare, so the twelfth widget is covered by its declaration alone — the
// alternative keeps working perfectly on the widget it was taught and silently does
// nothing for the next one.
export const tagsDeclaring = (
  holds: (entry: WidgetDeclaration, tag: string) => unknown,
) =>
  elementDeclarations()
    .filter(([tag, entry]) => holds(entry, tag))
    .map(([tag]) => tag);

// Whether a module upgrades a tag. Composition derives `$modules` from the files it
// composes (Python's `registry.contract.MODULES`): a module at `widgets/<tag>.js` is
// what makes a tag an upgraded widget, and no declaration says so.
export const upgrades = (tag: string): boolean =>
  Object.hasOwn(registry.$modules ?? {}, tag);

// The `content` values whose body is one `<pre>` holding text: in the notation the
// element's module reads (`data`), or in Markdown, which Leaf reads (`markdown`).
// Python asks `registry.contract.body_is_data`.
export const DATA_CONTENT: readonly WidgetDeclaration["content"][] = [
  "data",
  "markdown",
];
export const bodyIsData = (entry: WidgetDeclaration | undefined) =>
  DATA_CONTENT.includes(entry?.content);

// Every declared attribute holds one of the admitted values. A boolean asks whether a
// flag is present; other values compare with the attribute's text. The lint holds each
// value to the attribute's schema.
const matchesWhen = (
  el: Element,
  when: Record<string, readonly (string | boolean)[]> | null | undefined,
) =>
  Object.entries(when ?? {}).every(([attr, values]) =>
    values.some((value) =>
      typeof value === "boolean"
        ? el.hasAttribute(attr) === value
        : el.getAttribute(attr) === value,
    ),
  );

// A declared fact as it holds for one occurrence. A fact declared with
// `{when: {attribute: [values]}}` is `true` while the element's attributes match and
// `false` otherwise; any other declaration is returned as declared. A reader asking
// whether the tag declares the fact at all reads the declaration instead. The
// declaration schema says which facts may take that form; Python's is
// `registry.contract.holds_for`.
export const holdsFor = (el: Element, rule: unknown): unknown =>
  typeof rule === "object" &&
  rule !== null &&
  "when" in rule &&
  Object.keys(rule).length === 1
    ? matchesWhen(el, rule.when as Parameters<typeof matchesWhen>[1])
    : rule;

// An occurrence quotes its descendants only while its declared condition holds.
export const exhibits = (el: Element, entry: WidgetDeclaration | null | undefined) =>
  !!holdsFor(el, entry?.exhibit);
