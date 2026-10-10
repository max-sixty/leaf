/** Derive structural TypeScript records from the kernel's admission schema.
 * Value constraints (patterns, ranges, and conditional clauses) stay with admission.
 * Widget detail stays open: the page's registry, rather than the kernel, owns it.
 */
import { readFile } from "node:fs/promises";

function typeOf(schema) {
  if (schema === false) return "never";
  if (schema === true || Object.keys(schema).length === 0) return "unknown";
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
      if (schema.additionalProperties !== false)
        fields.push(`[key: string]: ${typeOf(schema.additionalProperties ?? {})};`);
      return `{ ${fields.join(" ")} }`;
    }
    default:
      throw new Error(`Unsupported structural schema: ${JSON.stringify(schema)}`);
  }
}

export async function eventTypes(root) {
  const registry = JSON.parse(
    await readFile(new URL("skills/leaf/assets/registry.json", root)),
  );
  const kinds = Object.entries(registry.$events.kinds);
  const records = kinds.map(
    ([kind, { record }]) => `${JSON.stringify(kind)}: ${typeOf(record)};`,
  );
  const browser = kinds
    .filter(([, contract]) => contract.browser)
    .map(([kind, contract]) => {
      const record = contract.record;
      const owned = new Set(Object.values(registry.$events.ownership).flat());
      const properties = Object.fromEntries(
        Object.entries(record.properties).filter(([key]) => !owned.has(key)),
      );
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
  return `// Generated from registry.json by npm run build:browser.\nexport interface EventMap {\n${records.join("\n")}\n}\ntype Keys<T> = T extends unknown ? keyof T : never;\nexport type CompleteUnion<T, Whole = T> = T extends unknown ? T & Partial<Record<Exclude<Keys<Whole>, keyof T>, never>> : never;\nexport type Event = CompleteUnion<EventMap[keyof EventMap]>;\nexport interface BrowserCommandMap {\n${browser.join("\n")}\n}\nexport type BrowserCommand = CompleteUnion<BrowserCommandMap[keyof BrowserCommandMap]>;\n`;
}
