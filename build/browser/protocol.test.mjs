/** `protocolBreaks` refuses a schema change at the same protocol, or at a record's same
 * `since`, and passes one that moves the number or changes only annotations
 * (`protocol.mjs`). */
import assert from "node:assert/strict";
import { test } from "node:test";
import { protocolBreaks } from "./protocol.mjs";

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

test("a record keeps each kept key through every shape", () => {
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
        delete claim.kept;
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
    refused("record claim: kept page changed its schema"),
  );
  assert.deepEqual(
    changed(
      moved((claim) => (claim.schema.required = [])),
      kept,
    ),
    refused("record claim: kept page is no longer required"),
  );
  assert.deepEqual(
    changed((s) => (s.records.claim.kept = ["page", "batches/*/page"]), kept),
    refused("record claim: kept batches/*/page is not in its schema"),
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
