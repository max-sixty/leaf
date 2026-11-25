/** `protocolBreaks` refuses a schema change at the same protocol, or at a record's same
 * `since`, and passes one that moves the number or changes only annotations
 * (`protocol.mjs`). */
import assert from "node:assert/strict";
import { test } from "node:test";
import { baselineSchemas, protocolBreaks } from "./protocol.mjs";

// One event kind and one record.
const baseline = {
  protocol: 4,
  events: {
    ownership: { derived: [], browser_discard: ["id"] },
    kinds: {
      note: {
        record: {
          type: "object",
          properties: {
            kind: { const: "note" },
            id: { type: "string" },
            tone: { enum: ["plain", "loud"] },
            slug: { type: "string", pattern: "^[a-z]+$", maxLength: 40 },
          },
          required: ["kind", "id"],
          additionalProperties: false,
        },
      },
    },
  },
  records: {
    claim: {
      since: 3,
      schema: {
        type: "object",
        properties: { page: { type: "string" }, pid: { type: "integer" } },
        required: ["page"],
      },
      kept: [],
      kept_since: 3,
    },
  },
};

function changed(edit, before = baseline) {
  const current = structuredClone(before);
  edit(current);
  return protocolBreaks(before, current);
}
const none = [];
const refused = (...lines) => lines;

const note = (schemas) => schemas.events.kinds.note.record.properties;

test("at one protocol, every event record keeps its schema", () => {
  assert.deepEqual(
    changed(() => {}),
    none,
  );
  assert.deepEqual(
    changed((s) => (note(s).slug.maxLength = 60)),
    refused("event note: the record changed"),
  );
  assert.deepEqual(
    changed((s) => (note(s).extra = { type: "string" })),
    refused("event note: the record changed"),
  );
  assert.deepEqual(
    changed((s) => delete s.events.kinds.note),
    refused("event note: the kind is gone"),
  );
  assert.deepEqual(
    changed((s) => (s.events.kinds.other = s.events.kinds.note)),
    refused(
      "event other: an older Leaf skips a kind it doesn't know: declare it skippable if no reading that Leaf computes needs it, or bump",
    ),
  );
  assert.deepEqual(
    changed(
      (s) => (s.events.kinds.other = { ...s.events.kinds.note, skippable: true }),
    ),
    none,
  );
  assert.deepEqual(
    changed((s) => s.events.ownership.derived.push("at")),
    refused("$events.ownership: changed"),
  );
});

test("a new protocol starts the comparison again", () => {
  assert.deepEqual(
    changed((s) => {
      s.protocol = 5;
      note(s).slug.maxLength = 20;
    }),
    none,
  );
});

test("a record changes shape only with its since", () => {
  const pid = (s) => s.records.claim.schema.properties.pid;
  assert.deepEqual(
    changed((s) => (s.records.claim.schema.properties.cwd = { type: "string" })),
    refused("record claim: the schema changed at since 3"),
  );
  assert.deepEqual(
    changed((s) => {
      pid(s).type = "string";
      s.records.claim.since = 4;
    }),
    none,
  );
  assert.deepEqual(
    changed((s) => (s.records.claim.since = 2)),
    refused(
      "record claim: since 2 names neither its last shape's protocol nor this one, 4",
    ),
  );
  assert.deepEqual(
    changed((s) => (s.records.claim.since = 5)),
    refused("record claim: since 5 is past protocol 4"),
  );
});

test("a key once kept stays kept, with its schema", () => {
  const kept = structuredClone(baseline);
  kept.records.claim.kept = ["page"];
  const moved = (edit) => (s) => {
    s.records.claim.since = 4;
    edit(s.records.claim);
  };
  assert.deepEqual(
    changed(
      moved((claim) => (claim.schema.properties.pid.type = "string")),
      kept,
    ),
    none,
  );
  assert.deepEqual(
    changed(
      moved((claim) => {
        delete claim.schema.properties.page;
        claim.schema.required = [];
        claim.kept = [];
      }),
      kept,
    ),
    refused("record claim: page is kept, so every shape keeps it"),
  );
  assert.deepEqual(
    changed(
      moved((claim) => (claim.schema.properties.page = { type: "integer" })),
      kept,
    ),
    refused("record claim: kept page changed its schema from its shape at since 3"),
  );
  assert.deepEqual(
    changed(
      moved((claim) => (claim.schema.required = [])),
      kept,
    ),
    refused("record claim: kept page changed its schema from its shape at since 3"),
  );
  assert.deepEqual(
    changed((s) => (s.records.claim.kept = ["page", "batches/*/page"]), kept),
    refused("record claim: kept batches/*/page is not in its schema"),
  );
});

test("along a kept path, a shape holds each step its last shape holds", () => {
  const entry = () => ({
    type: "object",
    properties: { page: { type: "string" }, note: { type: "string" } },
    required: ["page"],
  });
  const schema = (at) => ({
    type: "object",
    properties: {
      batches: { type: "array", items: entry() },
      drafts: { type: "object", additionalProperties: entry() },
      listed: { type: "array", items: entry() },
      nullable: { type: ["array", "null"], items: entry() },
      opened: { type: "object", properties: { at } },
    },
    required: ["batches", "drafts", "listed", "nullable"],
  });
  // Its shape at since 3, and an earlier one in which `opened/at` was a string.
  const walked = structuredClone(baseline);
  Object.assign(walked.records.claim, {
    schema: schema({ type: "number" }),
    kept: ["batches/*/page", "drafts/*/page"],
    kept_since: 2,
    earlier: [{ since: 2, schema: schema({ type: "string" }) }],
  });
  // Each case moves the shape on and keeps `adds` beside what it kept.
  const moved =
    (edit, ...adds) =>
    (s) => {
      s.records.claim.since = 4;
      edit(s.records.claim.schema.properties, s.records.claim.schema);
      s.records.claim.kept.push(...adds);
    };
  const changedSchema = (path, since = 3) =>
    refused(
      `record claim: kept ${path} changed its schema from its shape at since ${since}`,
    );
  // What no kept path reaches may change.
  assert.deepEqual(
    changed(
      moved((fields) => delete fields.drafts.additionalProperties.properties.note),
      walked,
    ),
    none,
  );
  assert.deepEqual(
    changed(
      moved(
        (fields) =>
          (fields.drafts.additionalProperties.properties.page.type = "integer"),
      ),
      walked,
    ),
    changedSchema("drafts/*/page"),
  );
  // A `*` keeps taking a list's items, or a map's values, whether the path is kept
  // already or newly.
  assert.deepEqual(
    changed(
      moved(
        (fields) =>
          (fields.batches = { type: "object", additionalProperties: entry() }),
      ),
      walked,
    ),
    changedSchema("batches/*/page"),
  );
  assert.deepEqual(
    changed(
      moved(
        (fields) => (fields.listed = { type: "object", additionalProperties: entry() }),
        "listed/*/page",
      ),
      walked,
    ),
    changedSchema("listed/*/page"),
  );
  // A path names a key: `batches/*` would keep what `batches` keeps.
  assert.deepEqual(
    changed(
      moved(() => {}, "batches/*"),
      walked,
    ),
    refused("record claim: kept batches/* is not in its schema"),
  );
  // A key the last shape lacked may be kept where it is optional, at any depth, under
  // whatever the last shape required, and its own keys may be required.
  const created = (required) => (fields) => {
    const value = fields.drafts.additionalProperties;
    value.properties.created = { type: "number" };
    if (required) value.required.push("created");
  };
  assert.deepEqual(changed(moved(created(false), "drafts/*/created"), walked), none);
  assert.deepEqual(
    changed(moved(created(true), "drafts/*/created"), walked),
    changedSchema("drafts/*/created"),
  );
  const meta = (required) => (fields, schema) => {
    fields.meta = {
      type: "object",
      properties: { created: { type: "number" } },
      required: ["created"],
    };
    if (required) schema.required.push("meta");
  };
  assert.deepEqual(changed(moved(meta(false), "meta/created"), walked), none);
  assert.deepEqual(
    changed(moved(meta(true), "meta/created"), walked),
    changedSchema("meta/created"),
  );
  // A type list reads as a set: a `*` takes the items of a list a shape allows to be
  // null, whose null reads as stored, in whatever order its types are listed.
  assert.deepEqual(
    changed(
      moved((fields) => (fields.nullable.type = ["null", "array"]), "nullable/*/page"),
      walked,
    ),
    none,
  );
  // Every shape from `kept_since` on holds the path, not only the last one: a key
  // whose type changed in an earlier shape, before any shape kept it, can be kept
  // only once `kept_since` leaves that shape out.
  assert.deepEqual(
    changed(
      moved(() => {}, "opened/at"),
      walked,
    ),
    refused(
      "record claim: kept opened/at changed its schema from its shape at since 2; kept_since 3 would leave that shape out",
    ),
  );
  assert.deepEqual(
    changed((s) => {
      Object.assign(s.records.claim, { since: 4, kept_since: 3 });
      s.records.claim.kept.push("opened/at");
    }, walked),
    none,
  );
});

test("a record's window of shapes starts at its kept_since and takes each shape since moves past", () => {
  const held = structuredClone(baseline);
  Object.assign(held.records.claim, {
    kept_since: 2,
    earlier: [{ since: 2, schema: { type: "object" } }],
  });
  const schemas = (since, kept_since) => ({
    ...structuredClone(held),
    records: {
      claim: { ...structuredClone(baseline.records.claim), since, kept_since },
    },
    served: {},
    verb: {},
    widget: {},
  });
  const earlier = (since, kept_since) =>
    baselineSchemas(schemas(since, kept_since), held).records.claim.earlier;
  assert.deepEqual(earlier(3, 2), held.records.claim.earlier);
  assert.deepEqual(earlier(4, 2), [
    ...held.records.claim.earlier,
    { since: 3, schema: baseline.records.claim.schema },
  ]);
  assert.deepEqual(earlier(4, 3), [
    { since: 3, schema: baseline.records.claim.schema },
  ]);
  // `kept_since` names a shape the history holds, so it never reaches back past the
  // verified shapes nor leaves out the last, whose records are on disk; a new kind's
  // is its own since.
  const window = (kind, since, kept_since) =>
    changed((s) => (s.records[kind] = { ...s.records.claim, since, kept_since }), held);
  assert.deepEqual(
    window("claim", 4, 1),
    refused(
      "record claim: kept_since 1 names none of the shapes its history holds, 2, 3",
    ),
  );
  assert.deepEqual(
    window("claim", 4, 4),
    refused(
      "record claim: kept_since 4 names none of the shapes its history holds, 2, 3",
    ),
  );
  assert.deepEqual(
    window("other", 4, 3),
    refused("record other: kept_since 3 names none of the shapes its history holds, 4"),
  );
});

test("an annotation changes nothing, at any depth", () => {
  const conditional = structuredClone(baseline);
  Object.assign(conditional.records.claim.schema, {
    if: { properties: { page: { const: "x" } } },
    then: { properties: { pid: { type: "integer" }, description: { type: "string" } } },
  });
  const then = (s) => s.records.claim.schema.then.properties;
  assert.deepEqual(
    changed((s) => (then(s).pid.description = "The server's process"), conditional),
    none,
  );
  // A field named like an annotation is still a field.
  assert.deepEqual(
    changed((s) => (then(s).description.type = "integer"), conditional),
    refused("record claim: the schema changed at since 3"),
  );
});
