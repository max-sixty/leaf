/** `protocolBreaks` fails a schema change a page vendored at the same protocol, or a
 * Leaf at the same record format, would break on, and passes one it takes in stride
 * (`protocol.mjs`). */
import assert from "node:assert/strict";
import { test } from "node:test";
import { protocolBreaks } from "./protocol.mjs";

// One event kind the browser sends, the served state, and one record.
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
        browser: { required: ["kind"] },
      },
    },
  },
  served: {
    $defs: { ViewAnswer: { type: "object", properties: { ok: { type: "boolean" } } } },
    type: "object",
    properties: { title: { type: "string", maxLength: 80 } },
    required: ["title"],
  },
  verb: {},
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

const note = (schemas) => schemas.events.kinds.note.record.properties;

test("what a vendored page sends or holds may loosen but not tighten", () => {
  assert.deepEqual(
    changed(() => {}),
    [],
  );
  assert.deepEqual(
    changed((s) => (note(s).slug.pattern = "^[a-z-]+$")),
    ['event note.slug: pattern "^[a-z]+$" → "^[a-z-]+$"'],
  );
  assert.deepEqual(
    changed((s) => (note(s).slug.maxLength = 20)),
    ["event note.slug: maxLength 40 → 20"],
  );
  assert.deepEqual(
    changed((s) => (note(s).tone.enum = ["plain"])),
    ['event note.tone: values ["plain","loud"] → ["plain"]'],
  );
  assert.deepEqual(
    changed((s) => {
      delete note(s).slug.pattern;
      note(s).extra = { type: "string" };
    }),
    [],
  );
  assert.deepEqual(
    changed((s) => s.events.kinds.note.record.required.push("tone")),
    ["event note.tone: the field is now required"],
  );
  assert.deepEqual(
    changed((s) => delete s.events.kinds.note),
    ["event note: the kind is gone"],
  );
});

test("what Leaf serves may tighten but not loosen", () => {
  assert.deepEqual(
    changed((s) => (s.served.properties.title.maxLength = 120)),
    ["served state.title: maxLength 80 → 120"],
  );
  assert.deepEqual(
    changed((s) => (s.served.properties.title.maxLength = 60)),
    [],
  );
  assert.deepEqual(
    changed((s) => (s.served.properties.title.type = ["string", "null"])),
    ['served state.title: type ["string"] → ["string","null"]'],
  );
  assert.deepEqual(
    changed((s) => delete s.served.properties.title),
    ["served state.title: the field is gone"],
  );
});

test("an event the page is also served holds both ways", () => {
  const serving = structuredClone(baseline);
  serving.served.properties.notes = {
    type: "array",
    items: { $ref: "leaf:event/note" },
  };
  assert.deepEqual(
    changed((s) => (note(s).slug.maxLength = 60), serving),
    ["served state.notes[].slug: maxLength 40 → 60"],
  );
});

test("a new protocol starts the comparison again", () => {
  assert.deepEqual(
    changed((s) => {
      s.protocol = 5;
      note(s).slug.maxLength = 20;
    }),
    [],
  );
});

test("a record changes shape only with its since", () => {
  const pid = (s) => s.records.claim.schema.properties.pid;
  assert.deepEqual(
    changed((s) => (pid(s).type = "string")),
    ['record claim.pid: type ["integer"] → ["string"]'],
  );
  assert.deepEqual(
    changed((s) => (s.records.claim.schema.properties.cwd = { type: "string" })),
    [],
  );
  assert.deepEqual(
    changed((s) => {
      pid(s).type = "string";
      s.records.claim.since = 4;
    }),
    [],
  );
  assert.deepEqual(
    changed((s) => (s.records.claim.since = 2)),
    ["record claim: since 2 names neither its last shape's protocol nor this one, 4"],
  );
  assert.deepEqual(
    changed((s) => (s.records.claim.since = 5)),
    ["record claim: since 5 is past protocol 4"],
  );
});

test("a keyword the walk can't read fails loudly", () => {
  assert.throws(
    () => changed((s) => (note(s).slug.contentEncoding = "base64")),
    /can't read "contentEncoding"/,
  );
});

test("the walk sees through browser contracts, unions, references and maps", () => {
  // The browser contract narrows a field the record declares.
  assert.deepEqual(
    changed(
      (s) => (s.events.kinds.note.browser.properties = { tone: { const: "plain" } }),
    ),
    ['event note.tone: values ["plain","loud"] → ["plain"]'],
  );
  // A closed browser contract refuses the record's fields it doesn't name.
  assert.deepEqual(
    changed((s) => (s.events.kinds.note.browser.additionalProperties = false)),
    [
      "event note.kind: no value is taken where one was",
      "event note.id: no value is taken where one was",
      "event note.tone: no value is taken where one was",
      "event note.slug: no value is taken where one was",
    ],
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
    ['event note.tone: "oneOf" changed'],
  );
  assert.deepEqual(
    changed(() => {}, exclusive),
    [],
  );
  // A bound beside a union holds in every branch.
  const branched = structuredClone(baseline);
  note(branched).slug = { type: "string", anyOf: [{ maxLength: 100 }] };
  assert.deepEqual(
    changed((s) => (note(s).slug.maxLength = 5), branched),
    ["event note.slug: maxLength 100 → 5"],
  );
  // A served variant dropped takes its fields with it.
  const variants = structuredClone(baseline);
  variants.served.properties.pick = {
    anyOf: [
      { type: "object", properties: { x: { type: "string" } } },
      { type: "null" },
    ],
  };
  assert.deepEqual(
    changed((s) => (s.served.properties.pick = { type: "null" }), variants),
    ["served state.pick.x: the field is gone"],
  );
  // A definition that holds itself, against an inline one that doesn't.
  const nested = structuredClone(baseline);
  nested.served.$defs.Tree = {
    type: "object",
    properties: { child: { $ref: "#/$defs/Tree" } },
  };
  nested.served.properties.tree = { $ref: "#/$defs/Tree" };
  const inline = { type: "object", properties: { child: { type: "string" } } };
  assert.deepEqual(
    changed((s) => (s.served.properties.tree = inline), nested),
    ['served state.tree.child: type ["object"] → ["string"]'],
  );
  // A map's newly named field must take what the map took, and the browser door
  // closing an object that declared no fields refuses the fields it held.
  const mapped = structuredClone(baseline);
  note(mapped).counts = { type: "object", additionalProperties: { type: "number" } };
  note(mapped).meta = { type: "object" };
  assert.deepEqual(
    changed((s) => (note(s).counts.properties = { x: { type: "string" } }), mapped),
    ['event note.counts.x: type ["number"] → ["string"]'],
  );
  assert.deepEqual(
    changed((s) => (note(s).meta.additionalProperties = false), mapped),
    ["event note.meta.*: a closed object refuses fields it took"],
  );
});
