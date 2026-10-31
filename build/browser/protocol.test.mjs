/** `protocolBreaks` refuses a schema change a page's log at the same protocol, or a
 * Leaf at the same record format, would break on, and passes one every side takes in
 * stride (`protocol.mjs`). */
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

test("an event record, which a page sends and every Leaf reads, may change neither way", () => {
  assert.deepEqual(
    changed(() => {}),
    none,
  );
  assert.deepEqual(
    changed((s) => (note(s).slug.pattern = "^[a-z-]+$")),
    refused('event note.slug: pattern "^[a-z]+$" → "^[a-z-]+$"'),
  );
  assert.deepEqual(
    changed((s) => (note(s).slug.maxLength = 20)),
    refused("event note.slug: maxLength 40 → 20"),
  );
  assert.deepEqual(
    changed((s) => (note(s).slug.maxLength = 60)),
    refused("event note.slug: maxLength 40 → 60"),
  );
  assert.deepEqual(
    changed((s) => (note(s).tone.enum = ["plain"])),
    refused('event note.tone: values ["plain","loud"] → ["plain"]'),
  );
  assert.deepEqual(
    changed((s) => (note(s).extra = { type: "string" })),
    none,
  );
  assert.deepEqual(
    changed((s) => s.events.kinds.note.record.required.push("tone")),
    refused("event note.tone: the field is now required"),
  );
  assert.deepEqual(
    changed((s) => delete s.events.kinds.note),
    refused("event note: the kind is gone"),
  );
  assert.deepEqual(
    changed((s) => (s.events.kinds.other = s.events.kinds.note)),
    refused("event other: an older Leaf or page reads a kind it doesn't know"),
  );
  assert.deepEqual(
    changed(
      (s) => (s.events.kinds.other = { ...s.events.kinds.note, skippable: true }),
    ),
    none,
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
    changed((s) => (pid(s).type = "string")),
    refused('record claim.pid: type ["integer"] → ["string"]'),
  );
  const cwd = (s) => (s.records.claim.schema.properties.cwd = { type: "string" });
  assert.deepEqual(changed(cwd), none);
  assert.deepEqual(
    changed((s) => cwd(s) && s.records.claim.schema.required.push("cwd")),
    refused("record claim.cwd: the field is now required"),
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

test("a keyword the comparison can't read fails loudly", () => {
  assert.throws(
    () => changed((s) => (note(s).slug.contentEncoding = "base64")),
    /can't read "contentEncoding"/,
  );
  const pair = (field) => ({ prefixItems: [{ properties: { [field]: {} } }] });
  assert.throws(
    () => changed((s) => (note(s).pair = pair("x"))),
    /can't read fields inside `prefixItems`/,
  );
});

test("the comparison sees through unions, references and maps", () => {
  // A field one variant drops is gone, though another variant keeps it.
  const variant = (tag) => ({
    type: "object",
    properties: { tag: { const: tag }, x: { type: "string" } },
    additionalProperties: false,
  });
  const tagged = structuredClone(baseline);
  note(tagged).pick = { anyOf: [variant("a"), variant("b")] };
  note(tagged).box = { type: "object", properties: { label: { type: "string" } } };
  assert.deepEqual(
    changed((s) => delete note(s).pick.anyOf[0].properties.x, tagged),
    refused("event note.pick.x: the field is gone"),
  );
  // Closing an open object at the browser door refuses the fields it didn't name, even
  // beside `unevaluatedProperties: false` where a map took them.
  assert.deepEqual(
    changed((s) => (note(s).box.additionalProperties = false), tagged),
    refused("event note.box.*: a closed object refuses fields it took"),
  );
  const sealed = structuredClone(tagged);
  Object.assign(note(sealed).box, {
    additionalProperties: { type: "string" },
    unevaluatedProperties: false,
  });
  assert.deepEqual(
    changed((s) => (note(s).box.additionalProperties = false), sealed),
    refused("event note.box.*: a closed object refuses fields it took"),
  );
  // The browser door refuses a value two branches of a `oneOf` take, so a changed
  // `oneOf` there breaks even where each branch loosens.
  const exclusive = structuredClone(baseline);
  note(exclusive).tone = {
    anyOf: [{ oneOf: [{ const: "plain" }, { const: "loud" }] }],
  };
  const first = (s) => note(s).tone.anyOf[0].oneOf;
  assert.deepEqual(
    changed((s) => (first(s)[0] = { enum: ["plain", "loud"] }), exclusive),
    refused(
      'event note.tone: "oneOf" changed',
      'event note.tone: values ["plain"] → ["plain","loud"]',
    ),
  );
  // A bound beside a union holds in every branch.
  const branched = structuredClone(baseline);
  note(branched).slug = { type: "string", anyOf: [{ maxLength: 100 }] };
  assert.deepEqual(
    changed((s) => (note(s).slug.maxLength = 5), branched),
    refused('event note.slug: maxLength "none" → 5'),
  );
  // A record's variant dropped takes its fields with it.
  const claim = (s) => s.records.claim.schema.properties;
  const variants = structuredClone(baseline);
  claim(variants).pick = {
    anyOf: [
      { type: "object", properties: { x: { type: "string" } } },
      { type: "null" },
    ],
  };
  assert.deepEqual(
    changed((s) => (claim(s).pick = { type: "null" }), variants),
    refused(
      'record claim.pick: type ["object"] → ["null"]',
      "record claim.pick.x: the field is gone",
      // Read by position, a reader taking the old branches meets one it lacks.
      'record claim.pick: {"type":"null"} → false',
    ),
  );
  // A branch dropped takes the fields no other branch names, at any depth.
  const payloads = structuredClone(baseline);
  const payload = (field) => ({
    type: "object",
    properties: { payload: { type: "object", properties: { [field]: {} } } },
  });
  claim(payloads).pick = { anyOf: [payload("y"), payload("x")] };
  const gone = (lines) => lines.filter((line) => line.endsWith("the field is gone"));
  assert.deepEqual(
    gone(changed((s) => claim(s).pick.anyOf.pop(), payloads)),
    refused("record claim.pick.payload.x: the field is gone"),
  );
  const shared = structuredClone(payloads);
  claim(shared).pick.properties = payload("x").properties;
  assert.deepEqual(gone(changed((s) => claim(s).pick.anyOf.pop(), shared)), none);
  // A reference compares by its text.
  const nested = structuredClone(baseline);
  claim(nested).tree = { $ref: "#/$defs/Tree" };
  const inline = { type: "object", properties: { child: { type: "string" } } };
  assert.deepEqual(
    changed((s) => (claim(s).tree = inline), nested),
    refused(
      'record claim.tree: type "none" → ["object"]',
      'record claim.tree.child: type "none" → ["string"]',
      'record claim.tree: $ref "#/$defs/Tree" → "none"',
    ),
  );
  // A position `prefixItems` stops naming holds what `items` allows.
  const tuple = structuredClone(baseline);
  claim(tuple).pair = {
    type: "array",
    prefixItems: [{ type: "string" }],
    items: { type: "number" },
  };
  assert.deepEqual(
    changed((s) => (claim(s).pair.prefixItems = []), tuple),
    refused('record claim.pair[0]: type ["string"] → ["number"]'),
  );
  // A map's newly named field must take what the map took.
  const mapped = structuredClone(baseline);
  note(mapped).counts = { type: "object", additionalProperties: { type: "number" } };
  assert.deepEqual(
    changed((s) => (note(s).counts.properties = { x: { type: "string" } }), mapped),
    refused('event note.counts.x: type ["number"] → ["string"]'),
  );
});

test("an annotation changes nothing, inside a conditional too", () => {
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
  // A map keeps every name, and `$defs` is compared, since a reference reads it.
  assert.deepEqual(
    changed(
      (s) => (s.records.claim.schema.then.dependentRequired = { description: ["pid"] }),
      conditional,
    ).length,
    1,
  );
  const defs = structuredClone(conditional);
  defs.records.claim.schema.then.$defs = { rule: { type: "string" } };
  assert.deepEqual(
    changed((s) => (s.records.claim.schema.then.$defs.rule.type = "integer"), defs)
      .length,
    1,
  );
  // A field named like an annotation is still a field.
  assert.deepEqual(
    changed((s) => (then(s).description.type = "integer"), conditional),
    refused(
      'record claim: then {"properties":{"pid":{"type":"integer"},"description":{"type":"string"}}} → {"properties":{"pid":{"type":"integer"},"description":{"type":"integer"}}}',
    ),
  );
});
