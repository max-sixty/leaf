/** Which schema changes move the page protocol, or a record's `since`
 * (`layer-registry.md`, "Page protocol").
 *
 * `protocol-baseline.json` holds each schema as it last stood, and each record's
 * earlier shapes from its `kept_since` on (`baselineSchemas`), and `build.mjs` moves
 * it forward after each build `protocolBreaks` finds nothing in. At the same
 * protocol, every event record and `$events.ownership` stays as it was, apart from its
 * annotations, and every kind stays; a new kind may join only where it declares
 * `skippable`, since a Leaf that skips it still reads the rest of the log rightly. A
 * `state.Record` changes its schema, apart from its annotations, only by setting its
 * `since` to the current protocol. A reader reads through a kind's kept keys
 * (`state.Record.kept`) the records of every shape from its `kept_since` on, and those
 * of an earlier shape as none. So a key once kept stays kept, and along each kept
 * path every shape in that window holds what a reader of the others relied on
 * (`projection`): each step keeps its types, its key and whether that key is
 * required, so a key a shape lacked is optional, and the kept key keeps its schema,
 * which says what every reader accepts. The baseline keeps every shape the build
 * verified from `kept_since` on, and `kept_since` names one of them, so a window never
 * reaches a shape no check saw, nor leaves out the last shape, whose records are on
 * disk; a new kind's is its own `since` (`layer-registry.md`, "Page protocol").
 *
 * Equality, rather than a field-by-field comparison of what each side accepts, costs
 * a bump or a `since` move for an added optional field; Leaf spends no code on
 * compatibility with earlier runtimes, so that cost is the one taken. The number
 * stays a hand-moved integer rather than a digest of these schemas, since Leaf orders
 * protocols: it refuses a newer Leaf's page and renews an older one.
 *
 * What a page sends, the `verbs` its layer declares and the served state are
 * not among them: the Leaf serving a page also supplies its runtime and composes its
 * layer (`runtime_selection.py`), so no older reader or sender meets them.
 */
import { isDeepStrictEqual } from "node:util";
import { ANNOTATIONS } from "./contract-types.mjs";

// A schema without its annotations. A map keeps every name, since a field may be named
// like an annotation, and a value under `const` or `enum` is data.
const MAPS = new Set("properties dependentSchemas dependentRequired $defs".split(" "));
function bare(schema) {
  if (typeof schema !== "object" || schema === null) return schema;
  if (Array.isArray(schema)) return schema.map(bare);
  return Object.fromEntries(
    Object.entries(schema)
      .filter(([key]) => !ANNOTATIONS.has(key))
      .map(([key, value]) => [
        key,
        key === "const" || key === "enum"
          ? value
          : MAPS.has(key)
            ? Object.fromEntries(
                Object.entries(value).map(([name, field]) => [name, bare(field)]),
              )
            : bare(value),
      ]),
  );
}
const same = (a, b) => isDeepStrictEqual(bare(a), bare(b));

// What a reader of the kept path `path` (`a/*/b`, `*` for each item of a list or value
// of a map) relies on in a record's schema, as far as the schema holds the path: at
// each step, the types it leaves as a set, the key it takes (`items` where those types
// include a list, else `additionalProperties`, for a `*`) and whether that key is
// required; and the kept key's schema (`leaf`) where the schema holds the whole path.
// A path ending at a `*` has none, since `a/*` would keep what `a` keeps.
function projection(schema, path) {
  const steps = [];
  let node = schema;
  for (const step of path.split("/")) {
    const type = [node.type ?? []].flat().sort();
    const takes =
      step !== "*" ? step : type.includes("array") ? "items" : "additionalProperties";
    steps.push({ type, takes, required: !!node.required?.includes(step) });
    node = step === "*" ? node[takes] : node.properties?.[step];
    if (node === undefined) return { steps };
  }
  return { steps, leaf: path.split("/").at(-1) === "*" ? undefined : node };
}

// Whether a reader of the shape `now` reads a record of the shape `was` along one kept
// path as `was`'s reader did: every step `was` holds is the same in `now`, so a key
// `was` lacks is optional in `now`, and the kept key's schema, where `was` has it, is
// `was`'s.
const holds = (was, now) =>
  was.steps.every((step, at) => isDeepStrictEqual(step, now.steps[at])) &&
  (was.leaf === undefined || same(was.leaf, now.leaf));

/** The schemas the baseline holds: each a `protocolSchemas` reading carries but the
 * served state, the verb (`verbs`) and the widget declaration schema, which only the
 * generated types read; and of each record, beside its shape, its earlier shapes from
 * its `kept_since` on without their annotations (`earlier`), which take `baseline`'s
 * shape where `since` moved. */
export function baselineSchemas(
  { served: _s, verb: _v, widget: _w, ...held },
  baseline,
) {
  for (const [kind, record] of Object.entries(held.records)) {
    const earlier = shapes(baseline.records[kind])
      .filter((shape) => shape.since >= record.kept_since && shape.since < record.since)
      .map(({ since, schema }) => ({ since, schema: bare(schema) }));
    if (earlier.length) held.records[kind] = { ...record, earlier };
  }
  return held;
}

// Every shape a baseline record holds, oldest first.
const shapes = (record) =>
  record
    ? [...(record.earlier ?? []), { since: record.since, schema: record.schema }]
    : [];

/** Each change from `baseline` to `current` that needs the protocol or a record's
 * `since` to move, as lines naming what changed; none where nothing does. `baseline`
 * and `current` are `baselineSchemas` readings. */
export function protocolBreaks(baseline, current) {
  const refused = [];
  if (baseline.protocol === current.protocol) {
    const [kinds, now] = [baseline.events.kinds, current.events.kinds];
    for (const kind of new Set([...Object.keys(kinds), ...Object.keys(now)])) {
      if (!now[kind]) refused.push(`event ${kind}: the kind is gone`);
      else if (!kinds[kind]) {
        if (!now[kind].skippable)
          refused.push(
            `event ${kind}: an older Leaf skips a kind it doesn't know: declare it skippable if no reading that Leaf computes needs it, or bump`,
          );
      } else if (!same(kinds[kind].record, now[kind].record))
        refused.push(`event ${kind}: the record changed`);
    }
    if (!isDeepStrictEqual(baseline.events.ownership, current.events.ownership))
      refused.push("$events.ownership: changed");
  }
  for (const [kind, { since, schema, kept: keeps, kept_since: from }] of Object.entries(
    current.records,
  )) {
    const before = baseline.records[kind];
    // A kind's window starts at a shape its history holds, so it reaches back no further
    // than the shapes the build verified and keeps the last one, whose records are the
    // ones on disk; a new kind's starts at its own shape.
    const held = before ? shapes(before).map((shape) => shape.since) : [since];
    if (!held.includes(from))
      refused.push(
        `record ${kind}: kept_since ${from} names none of the shapes its history holds, ${held.join(", ")}`,
      );
    const window = shapes(before).filter((shape) => shape.since >= from);
    for (const path of keeps) {
      const now = projection(schema, path);
      if (now.leaf === undefined) {
        refused.push(`record ${kind}: kept ${path} is not in its schema`);
        continue;
      }
      const failing = window.filter(
        (shape) => !holds(projection(shape.schema, path), now),
      );
      const latest = failing.at(-1)?.since;
      const passing = window.find((shape) => shape.since > latest)?.since;
      if (failing.length)
        refused.push(
          `record ${kind}: kept ${path} changed its schema from its shape at since ${latest}` +
            (passing === undefined
              ? ""
              : `; kept_since ${passing} would leave that shape out`),
        );
    }
    for (const path of before?.kept ?? [])
      if (!keeps.includes(path))
        refused.push(`record ${kind}: ${path} is kept, so every shape keeps it`);
    if (since > current.protocol)
      refused.push(
        `record ${kind}: since ${since} is past protocol ${current.protocol}`,
      );
    else if (before?.since === since) {
      if (!same(before.schema, schema))
        refused.push(`record ${kind}: the schema changed at since ${since}`);
    } else if (since !== current.protocol)
      refused.push(
        `record ${kind}: since ${since} names neither its last shape's protocol nor this one, ${current.protocol}`,
      );
  }
  return refused;
}
