/* Pure semantic definitions of registry-declared widget commands.
   These match registry.contract's admission snapshots. Presentation and schema
   annotations are outside an operation's identity. */

function semanticSchema(schema) {
  if (!schema || typeof schema !== "object" || Array.isArray(schema)) return schema;
  const annotations = new Set([
    "title",
    "description",
    "$comment",
    "default",
    "examples",
    "deprecated",
    "readOnly",
    "writeOnly",
  ]);
  const maps = new Set([
    "properties",
    "patternProperties",
    "$defs",
    "definitions",
    "dependentSchemas",
  ]);
  const single = new Set([
    "additionalProperties",
    "unevaluatedProperties",
    "propertyNames",
    "items",
    "additionalItems",
    "unevaluatedItems",
    "contains",
    "not",
    "if",
    "then",
    "else",
    "contentSchema",
  ]);
  const sequences = new Set(["allOf", "anyOf", "oneOf", "prefixItems"]);
  return Object.fromEntries(
    Object.entries(schema)
      .filter(([key]) => !annotations.has(key))
      .map(([key, value]) => [
        key,
        key === "enum" || key === "const"
          ? value
          : maps.has(key)
            ? Object.fromEntries(
                Object.entries(value).map(([name, child]) => [
                  name,
                  semanticSchema(child),
                ]),
              )
            : sequences.has(key)
              ? value.map(semanticSchema)
              : single.has(key)
                ? semanticSchema(value)
                : value,
      ]),
  );
}

export function detailSchema(entry, spec) {
  const record = spec.record;
  if (!record) return spec.detail;
  const value =
    record.kind === "value"
      ? entry.properties[record.attr]
      : record.kind === "attribute"
        ? { type: "array", items: { type: "string" }, uniqueItems: true }
        : { type: "string" };
  const properties = { value };
  if (record.kind === "position")
    Object.assign(properties, { unit: { type: "string" }, rank: { type: "string" } });
  if (spec.update) properties.text = { type: "string", minLength: 1 };
  return {
    type: "object",
    properties,
    required: Object.keys(properties),
    additionalProperties: false,
  };
}

export function stateDefinition(origin, entry, spec) {
  return {
    origin,
    unit: spec.unit,
    record: spec.record ?? null,
    creates: spec.creates ?? null,
    update: spec.update ?? false,
    detail: semanticSchema(detailSchema(entry, spec)),
  };
}

export function sameStateDefinition(recorded, current) {
  if (recorded === current) return true;
  if (
    !recorded ||
    !current ||
    typeof recorded !== "object" ||
    typeof current !== "object" ||
    Array.isArray(recorded) !== Array.isArray(current)
  )
    return false;
  const keys = Object.keys(recorded);
  return (
    keys.length === Object.keys(current).length &&
    keys.every(
      (key) =>
        Object.hasOwn(current, key) &&
        (typeof recorded[key] === "object"
          ? sameStateDefinition(recorded[key], current[key])
          : recorded[key] === current[key]),
    )
  );
}

export function sameStateOperation(recorded, current) {
  if (!recorded || !current) return false;
  const { detail: _recordedDetail, ...recordedOperation } = recorded;
  const { detail: _currentDetail, ...currentOperation } = current;
  return sameStateDefinition(recordedOperation, currentOperation);
}

export function eventSpec(entry, event) {
  const spec = entry["x-state"]?.[event.action];
  const writer = { action: "user", report: "agent" }[event.kind];
  return spec && (spec.writer ?? "user") === writer ? spec : null;
}
