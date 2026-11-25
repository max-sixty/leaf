/** Which schema changes move the page protocol, or a record's `since`
 * (`layer-registry.md`, "Page protocol").
 *
 * `protocol-baseline.json` holds each schema as it last stood (`baselineSchemas`), and
 * `build.mjs` moves it forward after each build `protocolBreaks` finds nothing in. At
 * the same protocol, every event record and `$events.ownership` stays as it was, apart
 * from its annotations, and every kind stays; a new kind may join only where it
 * declares `skippable`, since a Leaf that skips it still reads the rest of the log
 * rightly. A `state.Record` changes its schema, apart from its annotations, only by
 * setting its `since` to the current protocol, and never drops a key it keeps
 * (`state.Record.kept`), loosens one from required, or changes its schema or
 * whether a `*` on its path walks a list or a map, since every Leaf reads a record's
 * kept keys whichever Leaf wrote it. A kept key's `anyOf` may gain variants, which
 * an older Leaf reads as it reads any value it doesn't know (`layer-registry.md`,
 * "Page protocol").
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

// Whether `now` is `was`, or `was` with variants added to its `anyOf`.
function widens(was, now) {
  if (!was.anyOf || !now.anyOf) return same(was, now);
  const { anyOf: before, ...rest } = was;
  const { anyOf: after, ...restNow } = now;
  return (
    same(rest, restNow) &&
    before.every((variant) => after.some((other) => same(variant, other)))
  );
}

// The schema at `path` (`a/*/b`, `*` for each item of a list or value of a map) in a
// record's schema, whether each key on the way is required, and what each `*` walks;
// none where the path leaves the schema, or ends at a `*`, since `a/*` would keep what
// `a` keeps.
function kept(schema, path) {
  let node = schema;
  const required = [];
  const walks = [];
  const steps = path.split("/");
  if (steps.at(-1) === "*") return undefined;
  for (const step of steps) {
    if (step === "*") {
      const walk = node?.type === "array" ? "items" : "additionalProperties";
      walks.push(walk);
      node = node?.[walk];
    } else {
      required.push(Boolean(node?.required?.includes(step)));
      node = node?.properties?.[step];
    }
    if (node === undefined) return undefined;
  }
  return { schema: node, required, walks };
}

/** The schemas the baseline holds: each a `protocolSchemas` reading carries but the
 * served state, the verb (`verbs`) and the widget declaration schema, which only the
 * generated types read. */
export const baselineSchemas = ({
  served: _served,
  verb: _verb,
  widget: _widget,
  ...held
}) => held;

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
  for (const [kind, { since, schema, kept: keeps }] of Object.entries(
    current.records,
  )) {
    const before = baseline.records[kind];
    for (const path of keeps)
      if (!kept(schema, path))
        refused.push(`record ${kind}: kept ${path} is not in its schema`);
    for (const path of before?.kept ?? []) {
      const [was, now] = [kept(before.schema, path), kept(schema, path)];
      if (!keeps.includes(path) || !now)
        refused.push(`record ${kind}: ${path} is kept, so every shape keeps it`);
      else if (
        !widens(was.schema, now.schema) ||
        !isDeepStrictEqual(was.walks, now.walks)
      )
        refused.push(`record ${kind}: kept ${path} changed its schema`);
      else if (was.required.some((required, step) => required && !now.required[step]))
        refused.push(`record ${kind}: kept ${path} is no longer required`);
    }
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
