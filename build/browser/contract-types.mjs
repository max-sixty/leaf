/** Derive structural TypeScript records from the kernel's admission schema for each
 * event record (`$events.kinds` in browser/runtime/kernel-registry.json), which the page
 * protocol holds, and the state the server serves the runtime
 * (src/leaf/served_state/state.schema.json), which it doesn't; and the values of
 * each page-wide declaration an author writes (`$authored`). Value constraints
 * (patterns, ranges, and conditional clauses) stay with the schemas' readers. Widget
 * detail stays open: the page's registry, rather than the kernel, owns it.
 *
 * The served state refers to its own definitions as `#/$defs/<Name>`, each of which
 * becomes `Served<Name>`, to its whole answer as `#`, which becomes `ServedState`
 * (an event answer carries one), and to the schemas `registry.schema.leaf_resources` names
 * by `leaf:` reference: `leaf:event/<kind>` becomes that kind's `EventMap` entry,
 * `leaf:event` an `Event`, and `leaf:verb` `ServedVerb`, generated from the schema
 * Python composes. A reference may point to one property, as
 * `leaf:event/comment#/properties/anchor` does. An object closed with
 * `unevaluatedProperties` reads as closed, as one with `additionalProperties: false`
 * does.
 *
 * `protocolSchemas` reads those schemas, with each `state.Record`'s, as one value: the
 * types are generated from it, and `protocol.mjs` compares all but the served state
 * with the baseline.
 */
import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const ANNOTATIONS = new Set(["description", "title", "$schema", "$id", "$comment"]);

function reference(ref) {
  const [uri, pointer = ""] = ref.split("#");
  if (!uri) return pointer ? `Served${pointer.replace("/$defs/", "")}` : "ServedState";
  const named =
    uri === "leaf:verb"
      ? "ServedVerb"
      : uri === "leaf:event"
        ? "Event"
        : `EventMap[${JSON.stringify(uri.replace("leaf:event/", ""))}]`;
  const field = pointer.replace("/properties/", "");
  return field ? `Exclude<${named}[${JSON.stringify(field)}], undefined>` : named;
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
  // The kinds each `$events.kinds` classification names (`runtime/kernel-facts.js`
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
function authoredTypes({ $authored: { allocations } }) {
  const table = (declared) =>
    `{ ${Object.entries(declared)
      .map(
        ([name, values]) =>
          `${JSON.stringify(name)}: ${values.map((value) => JSON.stringify(value)).join(" | ")};`,
      )
      .join(" ")} }`;
  return `export type AuthoredAllocations = ${table(allocations)};\n`;
}

function servedTypes(schema, verb) {
  const { $defs, ...state } = schema;
  const definitions = Object.entries({ ...$defs, Verb: verb }).map(
    ([name, definition]) => `export type Served${name} = ${typeOf(definition)};`,
  );
  return `${definitions.join("\n")}\nexport type ServedState = ${typeOf(state)};\n`;
}

// The schemas whose home is Python: those `leaf:` references name
// (`registry.schema.leaf_resources`), and each `state.Record`'s
// (`leaf_dev.declared_records`).
function pythonSchemas(root) {
  const program = `
import json
from leaf.registry.schema import leaf_resources
from leaf_dev import declared_records
records = {
    kind: {"since": record.since, "schema": record.schema}
    for kind, record in declared_records().items()
}
print(json.dumps({"references": leaf_resources(), "records": records}))
`;
  return JSON.parse(
    execFileSync("uv", ["run", "--quiet", "python", "-c", program], {
      cwd: fileURLToPath(root),
      encoding: "utf8",
    }),
  );
}

/** Every schema the generated types and the page protocol read (`protocol.mjs`): the
 * kernel event records and browser commands (`$events`), the served state, the x-state
 * verb, and each `state.Record` with the number of its shape (`since`). */
export async function protocolSchemas(root) {
  const read = async (file) => JSON.parse(await readFile(new URL(file, root), "utf8"));
  const { $events } = await read("browser/runtime/kernel-registry.json");
  const { references, records } = pythonSchemas(root);
  return {
    protocol: $events.protocol,
    events: { ownership: $events.ownership, kinds: $events.kinds },
    served: await read("src/leaf/served_state/state.schema.json"),
    verb: references["leaf:verb"],
    // The composer's draft (`$events.draft`) beside the `state.Record`s.
    records: {
      ...records,
      draft: {
        since: $events.draft.since,
        schema: written($events.draft.schema, references),
      },
    },
  };
}

// `schema` with each `leaf:` reference written in, any properties beside it added to
// the target's, so the baseline holds the parts of a draft, such as its drawing, that
// the draft takes from the comment record at the draft's own format.
function written(schema, references) {
  if (typeof schema !== "object" || schema === null) return schema;
  if (Array.isArray(schema)) return schema.map((item) => written(item, references));
  const { $ref, ...rest } = Object.fromEntries(
    Object.entries(schema).map(([key, value]) => [key, written(value, references)]),
  );
  if (!$ref) return rest;
  const [uri, pointer] = $ref.split("#");
  const { $id, ...target } = pointer
    .split("/")
    .slice(1)
    .reduce((value, key) => value[key], references[uri]);
  return {
    ...target,
    ...rest,
    properties: { ...target.properties, ...rest.properties },
  };
}

export async function contractTypes(root, { events, served, verb }) {
  const registry = JSON.parse(
    await readFile(new URL("browser/runtime/kernel-registry.json", root), "utf8"),
  );
  return `/* @noformat Generated from kernel-registry.json, state.schema.json and schema.VERB_SCHEMA by build/browser/contract-types.mjs. */\n${eventTypes({ $events: events })}${authoredTypes(registry)}${servedTypes(served, verb)}`;
}
