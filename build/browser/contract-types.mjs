/** Derive structural TypeScript records from the two schemas a page's protocol holds:
 * the kernel's admission schema for each event record (`$events.kinds` in
 * skills/leaf/assets/registry.json), and the state the server serves the page's
 * runtime (skills/leaf/scripts/leaf/served_state/state.schema.json). Value constraints
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
 */
import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const ANNOTATIONS = new Set(["description", "title", "$schema", "$id", "$comment"]);

function reference(ref) {
  const own = /^#\/\$defs\/([A-Za-z]+)$/.exec(ref);
  if (own) return `Served${own[1]}`;
  if (ref === "leaf:verb") return "ServedVerb";
  const event = /^leaf:event(?:\/([a-z_]+))?(?:#\/properties\/([a-z_]+))?$/.exec(ref);
  if (!event) throw new Error(`Unsupported schema reference: ${ref}`);
  const [, kind, field] = event;
  if (!kind) return "Event";
  const record = `EventMap[${JSON.stringify(kind)}]`;
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
  return `export interface EventMap {\n${records.join("\n")}\n}\ntype Keys<T> = T extends unknown ? keyof T : never;\nexport type CompleteUnion<T, Whole = T> = T extends unknown ? T & Partial<Record<Exclude<Keys<Whole>, keyof T>, never>> : never;\nexport type Event = CompleteUnion<EventMap[keyof EventMap]>;\nexport interface BrowserCommandMap {\n${browser.join("\n")}\n}\nexport type BrowserCommand = CompleteUnion<BrowserCommandMap[keyof BrowserCommandMap]>;\n`;
}

function servedTypes(schema, verb) {
  const { $defs, ...state } = schema;
  const definitions = Object.entries({ ...$defs, Verb: verb }).map(
    ([name, definition]) => `export type Served${name} = ${typeOf(definition)};`,
  );
  return `${definitions.join("\n")}\nexport type ServedState = ${typeOf(state)};\n`;
}

// The x-state verb's schema, whose home is Python's layer schema (`schema.VERB_SCHEMA`),
// built there from the name patterns the rest of the layer schema shares.
function verbSchema(root) {
  return JSON.parse(
    execFileSync(
      "uv",
      [
        "run",
        "--quiet",
        "python",
        "-c",
        "import json; from leaf.schema import VERB_SCHEMA; print(json.dumps(VERB_SCHEMA))",
      ],
      { cwd: fileURLToPath(root), encoding: "utf8" },
    ),
  );
}

export async function contractTypes(root) {
  const read = async (file) => JSON.parse(await readFile(new URL(file, root)));
  const registry = await read("skills/leaf/assets/registry.json");
  const served = await read("skills/leaf/scripts/leaf/served_state/state.schema.json");
  return `/* @noformat Generated from registry.json, state.schema.json and schema.VERB_SCHEMA by build/browser/contract-types.mjs. */\n${eventTypes(registry)}${servedTypes(served, verbSchema(root))}`;
}
