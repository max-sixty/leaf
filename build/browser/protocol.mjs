/** Which schema changes break a page vendored at the current protocol, or a Leaf
 * sharing a record's format (`layer-registry.md`, "Page protocol").
 *
 * `protocol-baseline.json` holds each schema as it last stood (`protocolSchemas`), and
 * `build.mjs` moves it forward after each build `protocolBreaks` finds nothing in.
 * `protocolBreaks` lays each baseline schema beside its current form, keyword by
 * keyword, and names each change the side that must accept the other's values would
 * refuse:
 *
 * - what a vendored page sends (browser commands): the current schema accepts what the
 *   baseline did, and the browser door, which validates, refuses a newly closed object;
 * - what Leaf serves the page (the served state, its definitions and the x-state verb):
 *   the baseline accepts what the current schema allows;
 * - an event record, which a page sends or holds and is served: both;
 * - a `state.Record`: both, at the same `since`, since every Leaf writing that format
 *   reads what the others wrote.
 *
 * The comparison is by position, so it reads no reference and merges no union: a
 * reference compares by its text, and its target where it is declared; union, `allOf`
 * and `prefixItems` entries compare by index. A field either side drops is gone,
 * whatever the direction, and so is each field of a union branch the new schema drops
 * that nothing left names. A field only the new schema names is one older writers
 * never wrote, unless its object named none or holds a map, whose values it must take.
 * `pattern`, `format`, `not`, `if`/`then`/`else`, and at the browser door `oneOf`,
 * whose exclusivity a branch-by-branch comparison can't show, compare only for
 * equality. The comparison throws on any keyword it doesn't read, and on a field inside
 * `prefixItems`, so a field's path names no position.
 */
import { isDeepStrictEqual } from "node:util";

const ANNOTATIONS = new Set("description title $schema $id $comment $defs".split(" "));
// Lower bounds, which the accepting side may lower but not raise, and upper bounds.
const LOWER = "minLength minItems minProperties minimum exclusiveMinimum".split(" ");
const UPPER = "maxLength maxItems maxProperties maximum exclusiveMaximum".split(" ");
const EQUAL = ["pattern", "format", "not", "if", "then", "else"];
const KEYWORDS = new Set([
  ...ANNOTATIONS,
  ...LOWER,
  ...UPPER,
  ...EQUAL,
  ..."$ref type const enum uniqueItems items prefixItems properties required".split(
    " ",
  ),
  ..."additionalProperties unevaluatedProperties dependentRequired".split(" "),
  ..."dependentSchemas anyOf oneOf allOf".split(" "),
]);

const typeOf = (value) =>
  value === null
    ? "null"
    : Array.isArray(value)
      ? "array"
      : Number.isInteger(value)
        ? "integer"
        : typeof value;
const accepts = (wider, type) =>
  wider.has(type) || (type === "integer" && wider.has("number"));
const valuesOf = (schema) => ("const" in schema ? [schema.const] : schema.enum);
function types(schema) {
  if (schema.type) return new Set([schema.type].flat());
  return valuesOf(schema) && new Set(valuesOf(schema).map(typeOf));
}
const closed = (schema) =>
  schema.additionalProperties === false ||
  (!("additionalProperties" in schema) && schema.unevaluatedProperties === false);
// The schema of the fields an object doesn't name: none where it names some, under
// the rule that older writers never wrote one, and any where it names none.
const others = (schema) =>
  schema.additionalProperties ?? schema.unevaluatedProperties ?? !schema.properties;
const show = (value) => JSON.stringify(value ?? "none");

// The path of each field `schema` names, at any depth and in any branch.
function fields(schema, path = "", found = new Set()) {
  if (typeof schema !== "object") return found;
  for (const [name, field] of Object.entries(schema.properties ?? {}))
    fields(field, `${path}.${name}`, found.add(`${path}.${name}`));
  for (const branch of [
    schema.anyOf,
    schema.oneOf,
    schema.allOf,
    schema.if,
    schema.then,
    schema.else,
    Object.values(schema.dependentSchemas ?? {}),
  ].flat())
    fields(branch, path, found);
  fields(schema.items, `${path}[]`, found);
  fields(schema.additionalProperties, `${path}.*`, found);
  fields(schema.unevaluatedProperties, `${path}.*`, found);
  return found;
}

/** Each change from `old` to `now` the consuming side refuses, as `[path, message]`.
 * `side.newConsumes` says whether the new schema takes the old one's values or the
 * reverse, `side.validates` whether the consumer is the browser door, and
 * `side.overlay` whether the schemas only narrow fields declared elsewhere, as a
 * browser contract narrows its record, so a field newly named there is newly bounded. */
function diff(old, now, path, side) {
  if (isDeepStrictEqual(old, now)) return [];
  if (old === true) old = {};
  if (now === true) now = {};
  const [consumer, producer] = side.newConsumes ? [now, old] : [old, now];
  if (producer === false) return [];
  if (consumer === false) return [[path, `${show(old)} → ${show(now)}`]];
  for (const key of [...Object.keys(old), ...Object.keys(now)])
    if (!KEYWORDS.has(key)) throw new Error(`The protocol check can't read "${key}"`);
  // A union on one side only is a union of one on the other.
  const union = (schema) => schema.anyOf ?? schema.oneOf;
  if (Boolean(union(old)) !== Boolean(union(now)))
    return union(old)
      ? diff(old, { anyOf: [now] }, path, side)
      : diff({ anyOf: [old] }, now, path, side);
  const found = [];
  const report = (what, before, after) =>
    found.push([path, `${what} ${show(before)} → ${show(after)}`]);
  // Whether `keyword` holds anything the consumer refuses, where `holds(c, p)` says the
  // consumer's value takes the producer's.
  const check = (keyword, holds, before = old[keyword], after = now[keyword]) => {
    if (consumer[keyword] !== undefined && !holds(consumer[keyword], producer[keyword]))
      report(keyword, before, after);
  };
  const nested = (where, before, after, how = side) =>
    found.push(...diff(before, after, `${path}${where}`, how));

  check("$ref", (taken, given) => taken === given);
  // A consumer's `const` or `enum` speaks for its types under "values" below.
  const taken = consumer.type && types(consumer);
  const given = types(producer);
  if (taken && (!given || [...given].some((type) => !accepts(taken, type))))
    report("type", types(old) && [...types(old)], types(now) && [...types(now)]);
  const offered = valuesOf(producer);
  if (
    valuesOf(consumer) &&
    !offered?.every((v) => valuesOf(consumer).some((w) => isDeepStrictEqual(v, w)))
  )
    report("values", valuesOf(old), valuesOf(now));
  for (const keyword of EQUAL) check(keyword, isDeepStrictEqual);
  for (const keyword of LOWER) check(keyword, (c, p) => c <= p);
  for (const keyword of UPPER) check(keyword, (c, p) => c >= p);
  check("uniqueItems", (c, p) => !c || p);
  for (const name of consumer.required ?? [])
    if (!producer.required?.includes(name))
      found.push([
        `${path}.${name}`,
        side.newConsumes
          ? "the field is now required"
          : "the old side requires the field, which the new may leave out",
      ]);
  for (const name of Object.keys(consumer.dependentRequired ?? {}))
    if (
      !consumer.dependentRequired[name].every((need) =>
        [
          ...(producer.dependentRequired?.[name] ?? []),
          ...(producer.required ?? []),
        ].includes(need),
      )
    )
      report(
        `dependentRequired ${name}`,
        old.dependentRequired?.[name],
        now.dependentRequired?.[name],
      );

  // The fields a side doesn't name: a reader that doesn't validate ignores them unless
  // it holds a map, and a writer writes those `others` allows.
  const unnamed = (schema) =>
    schema === consumer
      ? typeof others(schema) === "object"
        ? others(schema)
        : true
      : others(schema);
  for (const name of new Set([
    ...Object.keys(old.properties ?? {}),
    ...Object.keys(now.properties ?? {}),
  ])) {
    const [before, after] = [old.properties?.[name], now.properties?.[name]];
    // Beside a contract, `side.overlay` is the old record it narrows, which says what
    // the contract's writer could send where the old contract named nothing: what the
    // record allowed, and nothing where it named no such field.
    const record = side.overlay && (side.overlay.properties?.[name] ?? false);
    const how = side.overlay ? { ...side, overlay: record } : side;
    if (side.overlay) nested(`.${name}`, before ?? Boolean(record), after ?? true, how);
    else if (!after) found.push([`${path}.${name}`, "the field is gone"]);
    else nested(`.${name}`, before ?? unnamed(old), after);
  }
  if (side.validates && closed(consumer) && !closed(producer))
    found.push([`${path}.*`, "a closed object refuses fields it took"]);
  else if ([old, now].some((s) => typeof others(s) === "object"))
    nested(".*", unnamed(old), unnamed(now));

  // A position past `prefixItems` holds what `items` allows. A tuple's positions hold
  // values, not fields, which keeps a field's path free of positions.
  const at = (schema, index) => schema.prefixItems?.[index] ?? schema.items ?? true;
  for (const item of [...(old.prefixItems ?? []), ...(now.prefixItems ?? [])])
    if (fields(item).size)
      throw new Error("The protocol check can't read fields inside `prefixItems`");
  const positions = Math.max(
    old.prefixItems?.length ?? 0,
    now.prefixItems?.length ?? 0,
  );
  for (let index = 0; index < positions; index++)
    nested(`[${index}]`, at(old, index), at(now, index));
  if ("items" in old || "items" in now)
    nested("[]", old.items ?? true, now.items ?? true);
  for (const keyword of ["allOf", "anyOf", "oneOf"]) {
    const [before, after] = [old[keyword] ?? [], now[keyword] ?? []];
    // A missing conjunct takes anything; a missing branch, nothing, so a branch the new
    // schema drops takes with it each field no remaining branch names.
    const missing = keyword === "allOf";
    // What the new schema still names: its remaining branches and what they share.
    const { anyOf, oneOf, ...shared } = now;
    const kept = new Set([shared, ...after].flatMap((branch) => [...fields(branch)]));
    for (let index = 0; index < Math.max(before.length, after.length); index++) {
      nested(`|${index}`, before[index] ?? missing, after[index] ?? missing);
      if (!missing && !after[index])
        for (const field of fields(before[index]))
          if (!kept.has(field)) found.push([`${path}${field}`, "the field is gone"]);
    }
  }
  if (side.validates && !isDeepStrictEqual(old.oneOf, now.oneOf))
    found.push([path, `"oneOf" changed`]);
  for (const name of new Set([
    ...Object.keys(old.dependentSchemas ?? {}),
    ...Object.keys(now.dependentSchemas ?? {}),
  ]))
    nested(
      `.${name}`,
      old.dependentSchemas?.[name] ?? true,
      now.dependentSchemas?.[name] ?? true,
    );
  return found;
}

const SENT = { newConsumes: true, validates: true };
const SERVED = { newConsumes: false, validates: false };
const READ = { newConsumes: true, validates: false };

/** Each change from `baseline` to `current` that breaks what the baseline promised,
 * as a line naming where and what; empty where nothing does. Both are
 * `protocolSchemas` readings. */
export function protocolBreaks(baseline, current) {
  const found = [];
  const compare = (where, old, now, ...sides) =>
    found.push(...sides.flatMap((side) => diff(old, now, where, side)));
  if (baseline.protocol === current.protocol) {
    const [kinds, now] = [baseline.events.kinds, current.events.kinds];
    for (const kind of new Set([...Object.keys(kinds), ...Object.keys(now)])) {
      const where = `event ${kind}`;
      if (!now[kind]) found.push([where, "the kind is gone"]);
      // The served state carries every kind, which a page's runtime reads.
      else if (!kinds[kind])
        found.push([where, "a page is served a kind it doesn't know"]);
      else {
        compare(where, kinds[kind].record, now[kind].record, SENT, SERVED);
        if (kinds[kind].browser && !now[kind].browser)
          found.push([where, "the browser no longer sends it"]);
        else if (kinds[kind].browser)
          compare(where, kinds[kind].browser, now[kind].browser, {
            ...SENT,
            overlay: kinds[kind].record,
          });
      }
    }
    if (!isDeepStrictEqual(baseline.events.ownership, current.events.ownership))
      found.push(["$events.ownership", "changed"]);
    const { $defs: before, ...state } = baseline.served;
    const { $defs: after, ...served } = current.served;
    compare("served state", state, served, SERVED);
    for (const name of Object.keys(before))
      if (after[name]) compare(`served ${name}`, before[name], after[name], SERVED);
    compare("x-state verb", baseline.verb, current.verb, SERVED);
  }
  for (const [kind, { since, schema }] of Object.entries(current.records)) {
    const where = `record ${kind}`;
    const before = baseline.records[kind];
    if (since > current.protocol)
      found.push([where, `since ${since} is past protocol ${current.protocol}`]);
    else if (before?.since === since)
      compare(where, before.schema, schema, READ, SERVED);
    else if (since !== current.protocol)
      found.push([
        where,
        `since ${since} names neither its last shape's protocol nor this one, ${current.protocol}`,
      ]);
  }
  // The same change shows once, though each direction meets it.
  return [
    ...new Set(found.map(([where, what]) => `${where.replace(/\|\d+/g, "")}: ${what}`)),
  ];
}
