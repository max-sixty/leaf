/** Derive structural TypeScript records from the two schemas a page's protocol holds:
 * the kernel's admission schema for each event record (`$events.kinds` in
 * skills/leaf/assets/registry.json), and the state the server serves the page's
 * runtime (skills/leaf/scripts/leaf/served_state/state.schema.json); and the values of
 * each page-wide declaration an author writes (`$authored`). Value constraints
 * (patterns, ranges, and conditional clauses) stay with the schemas' readers. Widget
 * detail stays open: the page's registry, rather than the kernel, owns it.
 *
 * The served state refers to an event record as `leaf:event` (any kind) or
 * `leaf:event/<kind>`, optionally with a pointer to one of its properties, to an x-state
 * verb as `leaf:verb`, which becomes `ServedVerb` from the layer schema's
 * `VERB_SCHEMA`, and to its own definitions as `#/$defs/<Name>`, each of which becomes
 * `Served<Name>`. An object
 * closed with `unevaluatedProperties` reads as closed, as one with
 * `additionalProperties: false` does.
 *
 * `protocolSchemas` reads those schemas, with each `state.Record`'s, as one value: the
 * types are generated from it, and `protocol.mjs` compares it with the baseline.
 */
import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const ANNOTATIONS = new Set(["description", "title", "$schema", "$id", "$comment"]);

/** What a served-state reference names: one of its own definitions (`own`), the
 * x-state verb (`verb`), or an event record (`event`, its kind or null for any kind,
 * with `field`, one property of it, or null). */
function schemaReference(ref) {
  const own = /^#\/\$defs\/([A-Za-z]+)$/.exec(ref);
  if (own) return { own: own[1] };
  if (ref === "leaf:verb") return { verb: true };
  const event = /^leaf:event(?:\/([a-z_]+))?(?:#\/properties\/([a-z_]+))?$/.exec(ref);
  if (!event) throw new Error(`Unsupported schema reference: ${ref}`);
  return { event: event[1] ?? null, field: event[2] ?? null };
}

function reference(ref) {
  const { own, verb, event, field } = schemaReference(ref);
  if (own) return `Served${own}`;
  if (verb) return "ServedVerb";
  if (!event) return "Event";
  const record = `EventMap[${JSON.stringify(event)}]`;
  return field ? `Exclude<${record}[${JSON.stringify(field)}], undefined>` : record;
}

function typeOf(input) {
  if (input === false) return "never";
  if (input === true) return "unknown";
  const schema = Object.fromEntries(
    Object.entries(input).filter(([key]) => !ANNOTATIONS.has(key)),
  );
  if (Object.keys(schema).length === 0) return "unknown";
  if ("const" in schema) return JSON.stringify(schema.const);
  if (schema.enum) return schema.enum.map(JSON.stringify).join(" | ");
  if (schema.anyOf || schema.oneOf) {
    const { anyOf, oneOf, ...base } = schema;
    return (anyOf ?? oneOf)
      .map((branch) =>
        typeOf({
          ...base,
          ...branch,
          properties: { ...base.properties, ...branch.properties },
          required: [...(base.required ?? []), ...(branch.required ?? [])],
        }),
      )
      .join(" | ");
  }
  if (schema.$ref) {
    const { $ref, ...rest } = schema;
    const named = reference($ref);
    return Object.keys(rest.properties ?? {}).length
      ? `${named} & ${typeOf({ type: "object", unevaluatedProperties: false, ...rest })}`
      : named;
  }
  if (Array.isArray(schema.type))
    return schema.type.map((type) => typeOf({ ...schema, type })).join(" | ");
  switch (schema.type) {
    case "string":
      return "string";
    case "integer":
    case "number":
      return "number";
    case "boolean":
      return "boolean";
    case "null":
      return "null";
    case "array":
      if (schema.prefixItems) {
        const tuple = schema.prefixItems.map(typeOf);
        if (schema.items !== false) tuple.push(`...(${typeOf(schema.items ?? {})})[]`);
        return `readonly [${tuple.join(", ")}]`;
      }
      return `ReadonlyArray<${typeOf(schema.items ?? {})}>`;
    case "object": {
      const fields = Object.entries(schema.properties ?? {}).map(
        ([name, value]) =>
          `${JSON.stringify(name)}${schema.required?.includes(name) ? "" : "?"}: ${typeOf(value)};`,
      );
      // An object naming its fields reads as those fields: one left open for a
      // reference to extend, or for fields another Leaf writes, still has no others
      // this reader knows.
      if (
        schema.additionalProperties === undefined
          ? !schema.properties && schema.unevaluatedProperties !== false
          : schema.additionalProperties !== false
      )
        fields.push(`[key: string]: ${typeOf(schema.additionalProperties ?? {})};`);
      return `{ ${fields.join(" ")} }`;
    }
    default:
      throw new Error(`Unsupported structural schema: ${JSON.stringify(schema)}`);
  }
}

function eventTypes(registry) {
  const kinds = Object.entries(registry.$events.kinds);
  const records = kinds.map(
    ([kind, { record }]) => `${JSON.stringify(kind)}: ${typeOf(record)};`,
  );
  const browser = kinds
    .filter(([, contract]) => contract.browser)
    .map(([kind, contract]) => {
      const owned = new Set(Object.values(registry.$events.ownership).flat());
      // Server-owned fields leave every branch of the record, not only its top level:
      // a branch naming one (an edit's `author`) would otherwise put it back.
      const unowned = (schema) => ({
        ...schema,
        ...(schema.properties && {
          properties: Object.fromEntries(
            Object.entries(schema.properties).filter(([key]) => !owned.has(key)),
          ),
        }),
        ...(schema.required && {
          required: schema.required.filter((key) => !owned.has(key)),
        }),
        ...Object.fromEntries(
          ["anyOf", "oneOf"]
            .filter((key) => schema[key])
            .map((key) => [key, schema[key].map(unowned)]),
        ),
      });
      const record = unowned(contract.record);
      const properties = { ...record.properties };
      // The browser contract may forbid fields the agent is allowed to write.
      const forbidden = contract.browser.not;
      for (const branch of forbidden?.anyOf ?? (forbidden ? [forbidden] : []))
        if (Object.keys(branch).length === 1 && branch.required?.length === 1)
          properties[branch.required[0]] = false;
      for (const [key, value] of Object.entries(contract.browser.properties ?? {}))
        properties[key] = { ...properties[key], ...value };
      const required = [
        ...new Set([...record.required, ...contract.browser.required]),
      ].filter((key) => !owned.has(key));
      return `${JSON.stringify(kind)}: ${typeOf({ ...record, properties, required })};`;
    });
  // The kinds each `$events.kinds` classification names (`runtime/event-kinds.js`
  // carries the same classifications as values).
  const classified = Object.entries({
    MessageKind: "message",
    UndoableKind: "undoable",
    WidgetKind: "verb_writer",
  }).map(
    ([type, flag]) =>
      `export type ${type} = ${kinds
        .filter(([, contract]) => contract[flag])
        .map(([kind]) => JSON.stringify(kind))
        .join(" | ")};\n`,
  );
  return `${classified.join("")}export interface EventMap {\n${records.join("\n")}\n}\ntype Keys<T> = T extends unknown ? keyof T : never;\nexport type CompleteUnion<T, Whole = T> = T extends unknown ? T & Partial<Record<Exclude<Keys<Whole>, keyof T>, never>> : never;\nexport type Event = CompleteUnion<EventMap[keyof EventMap]>;\nexport interface BrowserCommandMap {\n${browser.join("\n")}\n}\nexport type BrowserCommand = CompleteUnion<BrowserCommandMap[keyof BrowserCommandMap]>;\n`;
}

// Each page-wide declaration an author writes (`$authored`), with the values the
// runtime may read from it, so a reader comparing against another value fails to
// type-check.
function authoredTypes({ $authored: { allocations, meta } }) {
  const table = (declared) =>
    `{ ${Object.entries(declared)
      .map(
        ([name, values]) =>
          `${JSON.stringify(name)}: ${values.map((value) => JSON.stringify(value)).join(" | ")};`,
      )
      .join(" ")} }`;
  return `export type AuthoredAllocations = ${table(allocations)};\nexport type AuthoredMeta = ${table(meta)};\n`;
}

function servedTypes(schema, verb) {
  const { $defs, ...state } = schema;
  const definitions = Object.entries({ ...$defs, Verb: verb }).map(
    ([name, definition]) => `export type Served${name} = ${typeOf(definition)};`,
  );
  return `${definitions.join("\n")}\nexport type ServedState = ${typeOf(state)};\n`;
}

// The schemas whose home is Python: the x-state verb's (`schema.VERB_SCHEMA`), built
// there from the name patterns the rest of the layer schema shares, and each
// `state.Record`'s, read once every module declaring one is imported.
function pythonSchemas(root) {
  const program = `
import importlib, json, pkgutil
import leaf, leaf_website
from leaf.schema import VERB_SCHEMA
from leaf.state import RECORDS
for package in (leaf, leaf_website):
    for module in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        if not module.name.endswith(".__main__"):
            importlib.import_module(module.name)
records = {
    kind: {"since": record.since, "schema": record.schema}
    for kind, record in sorted(RECORDS.items())
}
print(json.dumps({"verb": VERB_SCHEMA, "records": records}))
`;
  return JSON.parse(
    execFileSync("uv", ["run", "--quiet", "python", "-c", program], {
      cwd: fileURLToPath(root),
      encoding: "utf8",
    }),
  );
}

/** Every schema the page protocol holds and every record's (`protocol.mjs`): the kernel
 * event records and browser commands (`$events`), the served state and the x-state
 * verb it carries, and each `state.Record` with the protocol its shape was set at. */
export async function protocolSchemas(root) {
  const read = async (file) => JSON.parse(await readFile(new URL(file, root)));
  const { $events } = await read("skills/leaf/assets/registry.json");
  const { verb, records } = pythonSchemas(root);
  return {
    protocol: $events.protocol,
    events: { ownership: $events.ownership, kinds: $events.kinds },
    served: await read("skills/leaf/scripts/leaf/served_state/state.schema.json"),
    verb,
    // The composer's draft beside the `state.Record`s: its format guards its drawing.
    records: {
      ...records,
      draft: { since: $events.draft_since, schema: draftSchema($events) },
    },
  };
}

// What a draft's format guards: its drawing, the comment record's with the placement in
// its section, `at`, that `captured` (runtime/composing/drawing.js) adds while it is a
// draft.
function draftSchema({ kinds }) {
  const drawing = kinds.comment.record.properties.drawing;
  const at = { type: "array", minItems: 6, maxItems: 6, items: { type: "number" } };
  return {
    type: "object",
    properties: { drawing: { ...drawing, properties: { ...drawing.properties, at } } },
  };
}

export async function contractTypes(root, { events, served, verb }) {
  const registry = JSON.parse(
    await readFile(new URL("skills/leaf/assets/registry.json", root)),
  );
  return `/* @noformat Generated from registry.json, state.schema.json and schema.VERB_SCHEMA by build/browser/contract-types.mjs. */\n${eventTypes({ $events: events })}${authoredTypes(registry)}${servedTypes(served, verb)}`;
}
