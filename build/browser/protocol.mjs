/** Which schema changes move the page protocol, or a record's `since`
 * (`layer-registry.md`, "Page protocol").
 *
 * `protocol-baseline.json` holds each schema as it last stood (`baselineSchemas`), and
 * `build.mjs` moves it forward after each build `protocolBreaks` finds nothing in. At
 * the same protocol, every event record and `$events.ownership` stays as it was, apart
 * from its annotations, and every kind stays; a new kind may join only where it
 * declares `skippable`, since a Leaf that skips it still reads the rest of the log
 * rightly. A `state.Record` changes its schema, apart from its annotations, only by
 * setting its `since` to the current protocol.
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
  for (const [kind, { since, schema }] of Object.entries(current.records)) {
    const before = baseline.records[kind];
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
