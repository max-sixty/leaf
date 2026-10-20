/** Which schema changes break a page vendored at the current protocol, or a Leaf
 * sharing a record's format (`layer-registry.md`, "Page protocol").
 *
 * `protocol-baseline.json` holds each schema as it last stood (`protocolSchemas`), and
 * `build.mjs` moves it forward after each build `protocolBreaks` finds nothing in.
 * `protocolBreaks` walks the baseline and the current schemas side by side and names
 * each place where the side that must accept the other's values would no longer:
 *
 * - what a vendored page sends or holds, its browser commands and log events: the
 *   current schema accepts everything the baseline did, at the same protocol;
 * - what Leaf serves the page, the served state and the view answer: the baseline
 *   accepts everything the current schema allows, at the same protocol;
 * - a `state.Record`: both, at the same `since`, since every Leaf writing that format
 *   reads what the others wrote.
 *
 * A field the old schema declares at any depth, in any branch, and the new one doesn't
 * breaks either way, since the side still using it loses its meaning. An object that
 * declares fields holds only those, so a field only the new schema declares breaks
 * only where the new side requires it; an object that declares none, or a map, may hold
 * any, so a field newly declared there must take what the map took. Of the consumers,
 * only the browser door validates what it takes, so only there does a newly closed
 * object refuse fields, and only there does a changed `oneOf` break, since comparing
 * its branches one by one can't show that no value now meets two.
 *
 * The walk understands the keywords these schemas use and throws on any other. A union's
 * shared keywords, a reference's siblings and a command's record join each branch,
 * target and browser contract as an intersection. It compares `pattern`, `format` and
 * the conjunctive keywords (`allOf`, `not`, `if`/`then`/`else`, `dependentSchemas`) only
 * for equality, so changing one on the accepting side breaks even where it loosens, and
 * it refuses to compare a conjunct that holds a reference, whose text the two sides may
 * resolve differently.
 */
import { isDeepStrictEqual } from "node:util";
import { schemaReference } from "./contract-types.mjs";

const ANNOTATIONS = "description title $schema $id $comment $defs".split(" ");
// Lower bounds, which the accepting side may lower but not raise, and upper bounds.
const LOWER = "minLength minItems minProperties minimum exclusiveMinimum".split(" ");
const UPPER = "maxLength maxItems maxProperties maximum exclusiveMaximum".split(" ");
const CONJUNCTS = ["not", "if", "then", "else"];
const KEYWORDS = new Set([
  ...ANNOTATIONS,
  ...LOWER,
  ...UPPER,
  ...CONJUNCTS,
  ..."$ref type const enum pattern format uniqueItems items prefixItems".split(" "),
  ..."properties required additionalProperties unevaluatedProperties".split(" "),
  ..."dependentRequired dependentSchemas anyOf oneOf allOf".split(" "),
]);

// A reference resolved within one side's schemas (`schemaReference`), where any event
// record is the union of every kind's.
function resolver({ served, events, verb }) {
  return (ref) => {
    const named = schemaReference(ref);
    if (named.own) return served.$defs[named.own];
    if (named.verb) return verb;
    if (!named.event)
      return { anyOf: Object.values(events.kinds).map(({ record }) => record) };
    const record = events.kinds[named.event]?.record;
    const target = named.field ? record?.properties?.[named.field] : record;
    if (!target) throw new Error(`Unresolved schema reference: ${ref}`);
    return target;
  };
}

function checked(schema) {
  if (typeof schema === "boolean") return schema;
  for (const key of Object.keys(schema))
    if (!KEYWORDS.has(key)) throw new Error(`The protocol check can't read "${key}"`);
  if (schema.anyOf && schema.oneOf)
    throw new Error(`The protocol check can't read "anyOf" beside "oneOf"`);
  return schema;
}

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

function valuesOf(schema) {
  if ("const" in schema) return [schema.const];
  return schema.enum ?? null;
}

function types(schema) {
  if (schema.type) return new Set([schema.type].flat());
  const values = valuesOf(schema);
  return values && new Set(values.map(typeOf));
}

/** The schema of the values that meet both `a` and `b`: a union's branch with its
 * shared keywords, a reference's target with its siblings, a command's record with its
 * browser contract. A keyword they hold differently and that has no exact meet, such
 * as two patterns, stands as a clause of `allOf`. */
function intersect(a, b) {
  if (a === false || b === false) return false;
  if (a === true) return b;
  if (b === true) return a;
  const both = { ...a };
  for (const [key, value] of Object.entries(b)) {
    const mine = both[key];
    if (!(key in both) || isDeepStrictEqual(mine, value)) both[key] = value;
    else if (ANNOTATIONS.includes(key)) continue;
    else if (key === "properties") {
      both.properties = { ...mine };
      for (const [name, field] of Object.entries(value))
        both.properties[name] = name in mine ? intersect(mine[name], field) : field;
    } else if (key === "required") both.required = [...new Set([...mine, ...value])];
    else if (key === "allOf") both.allOf = [...mine, ...value];
    else if (LOWER.includes(key)) both[key] = Math.max(mine, value);
    else if (UPPER.includes(key)) both[key] = Math.min(mine, value);
    else if (key === "type") {
      const [ours, theirs] = [new Set([mine].flat()), new Set([value].flat())];
      const met = [...new Set([...ours].filter((type) => accepts(theirs, type)))];
      for (const type of theirs) if (accepts(ours, type)) met.push(type);
      if (!met.length) return false;
      both.type = [...new Set(met)];
    } else if (["items", "additionalProperties", "unevaluatedProperties"].includes(key))
      both[key] = intersect(mine, value);
    else both.allOf = [...(both.allOf ?? []), { [key]: value }];
  }
  // `additionalProperties` speaks only for its own object's fields, so a field one side
  // names meets the other side's; `unevaluatedProperties` sees both sides' fields.
  for (const [named, other] of [
    [a, b],
    [b, a],
  ])
    if ("additionalProperties" in other)
      for (const name of Object.keys(named.properties ?? {}))
        if (!(name in (other.properties ?? {})))
          both.properties = {
            ...both.properties,
            [name]: intersect(both.properties[name], other.additionalProperties),
          };
  const [ours, theirs] = [valuesOf(a), valuesOf(b)];
  if (ours && theirs) {
    delete both.const;
    both.enum = ours.filter((one) =>
      theirs.some((other) => isDeepStrictEqual(one, other)),
    );
    if (!both.enum.length) return false;
  }
  return both;
}

// Whether a conjunct holds a reference, which each side resolves against its own schemas.
const mentionsReference = (value) =>
  typeof value === "object" &&
  value !== null &&
  ("$ref" in value || Object.values(value).some(mentionsReference));

function sameClause(consumer, producer) {
  if (mentionsReference(consumer))
    throw new Error("The protocol check can't compare a conjunct that holds a $ref");
  return isDeepStrictEqual(consumer, producer);
}

const show = (value) => JSON.stringify(value);

const closed = (schema) =>
  schema.additionalProperties === false || schema.unevaluatedProperties === false;

/** Each place the consumer's schema refuses a value the producer's allows, as
 * `[path, message]`. `oldConsumes` says which of the two is the old schema, and
 * `validates` whether the consumer is the browser door, which refuses what its schema
 * doesn't take. Each side resolves references within its own schemas. */
class Walk {
  constructor({ oldConsumes, validates, consumerSchemas, producerSchemas }) {
    this.oldConsumes = oldConsumes;
    this.validates = validates;
    this.resolveConsumer = resolver(consumerSchemas);
    this.resolveProducer = resolver(producerSchemas);
    this.active = new Set();
    this.ids = Object.assign(new WeakMap(), { count: 0 });
  }

  // A reference by its text, since a union's branches copy it into new objects; any
  // other schema by identity.
  key(schema) {
    if (typeof schema !== "object") return String(schema);
    if (schema.$ref) return JSON.stringify(schema);
    if (!this.ids.has(schema)) this.ids.set(schema, `#${this.ids.count++}`);
    return this.ids.get(schema);
  }

  // `keyword` going from the old schema's value to the new one's.
  change(keyword, consumer, producer) {
    const [before, after] = this.oldConsumes
      ? [consumer, producer]
      : [producer, consumer];
    return `${keyword} ${show(before ?? "none")} → ${show(after ?? "none")}`;
  }

  resolve(schema, resolveReference) {
    let current = checked(schema);
    while (current?.$ref) {
      const { $ref, ...siblings } = current;
      current = intersect(checked(resolveReference($ref)), siblings);
    }
    return current;
  }

  compare(consumerRaw, producerRaw, path) {
    // A schema that holds itself, such as a plan step's steps, is compared once per
    // pair of references: a pair met again inside its own walk holds by assumption.
    const key =
      consumerRaw?.$ref || producerRaw?.$ref
        ? `${this.key(consumerRaw)}:${this.key(producerRaw)}`
        : null;
    if (key && this.active.has(key)) return [];
    if (key) this.active.add(key);
    try {
      return this.compareResolved(
        this.resolve(consumerRaw, this.resolveConsumer),
        this.resolve(producerRaw, this.resolveProducer),
        path,
      );
    } finally {
      if (key) this.active.delete(key);
    }
  }

  compareResolved(consumer, producer, path) {
    if (producer === false) return [];
    if (consumer === false) return [[path, "no value is taken where one was"]];
    if (consumer === true) consumer = {};
    if (producer === true) producer = {};
    const producerBranches = producer.anyOf ?? producer.oneOf;
    if (producerBranches) {
      const { anyOf, oneOf, ...base } = producer;
      return producerBranches.flatMap((one, index) =>
        this.compare(consumer, intersect(base, checked(one)), `${path}|${index}`),
      );
    }
    const consumerBranches = consumer.anyOf ?? consumer.oneOf;
    if (consumerBranches) {
      const { anyOf, oneOf, ...base } = consumer;
      // Where no branch takes the value, report the branch it came closest to: the
      // one whose shallowest refusal lies deepest, so a branch that agrees on the
      // value's type and kind wins over one that refuses it outright, and then the
      // one with fewest refusals.
      let closest = null;
      for (const one of consumerBranches) {
        const refused = this.compare(intersect(base, checked(one)), producer, path);
        if (!refused.length) return [];
        const depth = Math.min(
          ...refused.map(([where]) => where.split(/[.[|]/).length),
        );
        if (
          !closest ||
          depth > closest.depth ||
          (depth === closest.depth && refused.length < closest.refused.length)
        )
          closest = { refused, depth };
      }
      return closest.refused;
    }
    return [
      ...this.values(consumer, producer, path),
      ...this.objects(consumer, producer, path),
      ...this.arrays(consumer, producer, path),
      ...this.conjuncts(consumer, producer, path),
    ];
  }

  values(consumer, producer, path) {
    const breaks = [];
    const taken = types(consumer);
    const given = types(producer);
    if (taken && (!given || [...given].some((type) => !accepts(taken, type))))
      breaks.push([path, this.change("type", [...taken], given && [...given])]);
    const allowed = valuesOf(consumer);
    const offered = valuesOf(producer);
    if (
      allowed &&
      (!offered ||
        offered.some((value) => !allowed.some((one) => isDeepStrictEqual(one, value))))
    )
      breaks.push([path, this.change("values", allowed, offered)]);
    if (
      "pattern" in consumer &&
      consumer.pattern !== producer.pattern &&
      !offered?.every((value) => new RegExp(consumer.pattern, "u").test(value))
    )
      breaks.push([path, this.change("pattern", consumer.pattern, producer.pattern)]);
    if ("format" in consumer && consumer.format !== producer.format)
      breaks.push([path, this.change("format", consumer.format, producer.format)]);
    for (const keyword of LOWER)
      if (keyword in consumer && !(consumer[keyword] <= producer[keyword]))
        breaks.push([path, this.change(keyword, consumer[keyword], producer[keyword])]);
    for (const keyword of UPPER)
      if (keyword in consumer && !(consumer[keyword] >= producer[keyword]))
        breaks.push([path, this.change(keyword, consumer[keyword], producer[keyword])]);
    if (consumer.uniqueItems && !producer.uniqueItems)
      breaks.push([path, this.change("uniqueItems", true, producer.uniqueItems)]);
    return breaks;
  }

  objects(consumer, producer, path) {
    const kinds = types(producer);
    if (kinds && !kinds.has("object")) return [];
    const breaks = [];
    const taken = consumer.properties ?? {};
    const given = producer.properties ?? {};
    const map = [consumer.additionalProperties, consumer.unevaluatedProperties].find(
      (schema) => typeof schema === "object",
    );
    const refuses = this.validates && closed(consumer);
    for (const [name, schema] of Object.entries(given))
      if (name in taken)
        breaks.push(...this.compare(taken[name], schema, `${path}.${name}`));
      else if (map) breaks.push(...this.compare(map, schema, `${path}.${name}`));
      else if (refuses)
        breaks.push([`${path}.${name}`, "a closed object refuses the field"]);
    // The values of fields the producer doesn't name: none where it names some, and any
    // where it names none.
    const extra =
      producer.additionalProperties ??
      producer.unevaluatedProperties ??
      (producer.properties ? undefined : true);
    if (extra !== undefined && extra !== false) {
      for (const [name, schema] of Object.entries(taken))
        if (!(name in given))
          breaks.push(...this.compare(schema, extra, `${path}.${name}`));
      if (map && !refuses) breaks.push(...this.compare(map, extra, `${path}.*`));
    }
    // An open object the browser door admitted may have held fields it didn't name.
    if (refuses && !closed(producer))
      breaks.push([`${path}.*`, "a closed object refuses fields it took"]);
    for (const name of consumer.required ?? [])
      if (!producer.required?.includes(name))
        breaks.push([
          `${path}.${name}`,
          this.oldConsumes
            ? "the old side requires the field, which the new may leave out"
            : "the field is now required",
        ]);
    for (const [name, needs] of Object.entries(consumer.dependentRequired ?? {})) {
      const held = new Set([
        ...(producer.dependentRequired?.[name] ?? []),
        ...(producer.required ?? []),
      ]);
      for (const need of needs)
        if (!held.has(need))
          breaks.push([
            `${path}.${name}`,
            `the field now needs ${show(need)} beside it`,
          ]);
    }
    return breaks;
  }

  arrays(consumer, producer, path) {
    const listed = (schema) => "items" in schema || "prefixItems" in schema;
    if (!listed(consumer) && !listed(producer)) return [];
    const at = (schema, index) => schema.prefixItems?.[index] ?? schema.items ?? true;
    const prefix = Math.max(
      consumer.prefixItems?.length ?? 0,
      producer.prefixItems?.length ?? 0,
    );
    // Positions past the producer's `maxItems` hold nothing to compare.
    const reach = producer.maxItems ?? Infinity;
    const breaks = [];
    for (let index = 0; index < Math.min(prefix, reach); index++)
      breaks.push(
        ...this.compare(at(consumer, index), at(producer, index), `${path}[${index}]`),
      );
    if (reach > prefix)
      breaks.push(
        ...this.compare(consumer.items ?? true, producer.items ?? true, `${path}[]`),
      );
    return breaks;
  }

  conjuncts(consumer, producer, path) {
    const breaks = [];
    for (const keyword of CONJUNCTS)
      if (keyword in consumer && !sameClause(consumer[keyword], producer[keyword]))
        breaks.push([path, `"${keyword}" changed`]);
    for (const clause of consumer.allOf ?? [])
      if (!producer.allOf?.some((given) => sameClause(clause, given)))
        breaks.push([path, `an "allOf" clause changed: ${show(clause)}`]);
    for (const [name, schema] of Object.entries(consumer.dependentSchemas ?? {}))
      if (!sameClause(schema, producer.dependentSchemas?.[name]))
        breaks.push([`${path}.${name}`, `"dependentSchemas" changed`]);
    return breaks;
  }
}

/** What `schema` declares, at any depth and in any branch: the path of each field, and
 * the branches of each `oneOf` by its path. */
function declared(schema, resolve, path = "", found = undefined, seen = new Set()) {
  found ??= { fields: new Set(), oneOfs: new Map() };
  if (typeof checked(schema) !== "object") return found;
  if (schema.$ref) {
    if (seen.has(schema.$ref)) return found;
    seen = new Set(seen).add(schema.$ref);
    declared(resolve(schema.$ref), resolve, path, found, seen);
  }
  if (schema.oneOf)
    found.oneOfs.set(path, [...(found.oneOfs.get(path) ?? []), ...schema.oneOf]);
  for (const branch of [schema.anyOf, schema.oneOf, schema.allOf].flat())
    if (branch) declared(branch, resolve, path, found, seen);
  for (const [name, field] of Object.entries(schema.properties ?? {})) {
    found.fields.add(`${path}.${name}`);
    declared(field, resolve, `${path}.${name}`, found, seen);
  }
  for (const map of [schema.additionalProperties, schema.unevaluatedProperties])
    if (typeof map === "object") declared(map, resolve, `${path}.*`, found, seen);
  // An array that holds nothing declares nothing in its items.
  if (schema.maxItems !== 0)
    for (const item of [...(schema.prefixItems ?? []), schema.items])
      if (item !== undefined) declared(item, resolve, `${path}[]`, found, seen);
  return found;
}

/** Where the side that must accept `oldSchema`'s or `newSchema`'s values no longer
 * would, under `rule`: `sent` (the new side takes what the old sent), `served` (the
 * old side reads what the new serves), or `record` (both); and each field the old
 * schema declares that the new one lost. */
function breaks(rule, where, [oldSchemas, oldSchema], [newSchemas, newSchema]) {
  const before = declared(oldSchema, resolver(oldSchemas));
  const after = declared(newSchema, resolver(newSchemas));
  const found = [...before.fields]
    .filter((field) => !after.fields.has(field))
    .map((field) => [`${where}${field}`, "the field is gone"]);
  // `oneOf` refuses a value two branches take, which comparing branches one by one
  // can't see, so at the browser door its branches compare only for equality.
  if (rule === "sent")
    for (const [path, branches] of after.oneOfs)
      if (
        !branches.every((one) =>
          before.oneOfs.get(path)?.some((old) => sameClause(one, old)),
        )
      )
        found.push([`${where}${path}`, `"oneOf" changed`]);
  const directions = { sent: [false], served: [true], record: [false, true] }[rule];
  for (const oldConsumes of directions) {
    const walk = new Walk({
      oldConsumes,
      validates: rule === "sent",
      consumerSchemas: oldConsumes ? oldSchemas : newSchemas,
      producerSchemas: oldConsumes ? newSchemas : oldSchemas,
    });
    const [consumer, producer] = oldConsumes
      ? [oldSchema, newSchema]
      : [newSchema, oldSchema];
    found.push(...walk.compare(consumer, producer, where));
  }
  return found;
}

// What the browser door validates a command against (`event_contracts`,
// `browser_command_error`): the kind's record less the fields admission derives, and
// its browser contract.
function command({ record, browser }, { derived }) {
  const own = (name) => !derived.includes(name);
  return intersect(
    {
      ...record,
      properties: Object.fromEntries(
        Object.entries(record.properties).filter(([name]) => own(name)),
      ),
      required: record.required.filter(own),
    },
    browser,
  );
}

/** Each change from `baseline` to `current` that breaks what the baseline promised,
 * as a line naming where and what; empty where nothing does. Both are
 * `protocolSchemas` readings. */
export function protocolBreaks(baseline, current) {
  const found = [];
  if (baseline.protocol === current.protocol) {
    for (const [kind, contract] of Object.entries(baseline.events.kinds)) {
      const now = current.events.kinds[kind];
      if (!now) {
        found.push([`event ${kind}`, "the kind is gone"]);
        continue;
      }
      found.push(
        ...breaks(
          "sent",
          `event ${kind}`,
          [baseline, contract.record],
          [current, now.record],
        ),
      );
      if (!contract.browser) continue;
      if (!now.browser) found.push([`event ${kind}`, "the browser no longer sends it"]);
      else
        found.push(
          ...breaks(
            "sent",
            `event ${kind}`,
            [baseline, command(contract, baseline.events.ownership)],
            [current, command(now, current.events.ownership)],
          ),
        );
    }
    if (!isDeepStrictEqual(baseline.events.ownership, current.events.ownership))
      found.push(["$events.ownership", "changed"]);
    found.push(
      ...breaks(
        "served",
        "served state",
        [baseline, baseline.served],
        [current, current.served],
      ),
      ...breaks(
        "served",
        "view answer",
        [baseline, { $ref: "#/$defs/ViewAnswer" }],
        [current, { $ref: "#/$defs/ViewAnswer" }],
      ),
    );
  }
  for (const [kind, { since, schema }] of Object.entries(current.records)) {
    const where = `record ${kind}`;
    const before = baseline.records[kind];
    if (since > current.protocol)
      found.push([where, `since ${since} is past protocol ${current.protocol}`]);
    else if (before?.since === since)
      found.push(...breaks("record", where, [{}, before.schema], [{}, schema]));
    else if (since !== current.protocol)
      found.push([
        where,
        `since ${since} names neither its last shape's protocol nor this one, ${current.protocol}`,
      ]);
  }
  // The same change shows once, though each branch of a union and each direction of a
  // record meets it.
  return [
    ...new Set(found.map(([where, what]) => `${where.replace(/\|\d+/g, "")}: ${what}`)),
  ];
}
