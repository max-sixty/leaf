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
const browser = (schemas) => schemas.events.kinds.note.browser;

test("an event record, which a page sends and is served, may change neither way", () => {
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
    changed((s) => (note(s).slug.maxLength = 60)),
    ["event note.slug: maxLength 40 → 60"],
  );
  assert.deepEqual(
    changed((s) => (note(s).tone.enum = ["plain"])),
    ['event note.tone: values ["plain","loud"] → ["plain"]'],
  );
  assert.deepEqual(
    changed((s) => (note(s).extra = { type: "string" })),
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
  assert.deepEqual(
    changed((s) => (s.events.kinds.other = s.events.kinds.note)),
    ["event other: a page is served a kind it doesn't know"],
  );
});

test("what the browser sends may loosen but not tighten", () => {
  assert.deepEqual(
    changed((s) => (browser(s).required = [])),
    [],
  );
  assert.deepEqual(
    changed((s) => (browser(s).properties = { tone: { const: "plain" } })),
    ['event note.tone: values "none" → ["plain"]'],
  );
  // A field the contract newly names narrows its record's, whatever else it names.
  const named = structuredClone(baseline);
  browser(named).properties = { slug: { maxLength: 30 } };
  assert.deepEqual(
    changed((s) => (browser(s).properties.tone = { const: "plain" }), named),
    ['event note.tone: values "none" → ["plain"]'],
  );
  assert.deepEqual(
    changed((s) => delete browser(s).properties.slug, named),
    [],
  );
  // A field new to the record was never sent, so the contract may bound it at once.
  assert.deepEqual(
    changed((s) => {
      note(s).extra = { type: "string" };
      browser(s).properties = { extra: { maxLength: 9 } };
    }),
    [],
  );
  assert.deepEqual(
    changed((s) => (browser(s).additionalProperties = false)),
    ["event note.*: a closed object refuses fields it took"],
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
  const cwd = (s) => (s.records.claim.schema.properties.cwd = { type: "string" });
  assert.deepEqual(changed(cwd), []);
  assert.deepEqual(
    changed((s) => cwd(s) && s.records.claim.schema.required.push("cwd")),
    ["record claim.cwd: the field is now required"],
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

test("a keyword the comparison can't read fails loudly", () => {
  assert.throws(
    () => changed((s) => (note(s).slug.contentEncoding = "base64")),
    /can't read "contentEncoding"/,
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
    ["event note.pick.x: the field is gone"],
  );
  // Closing an open object at the browser door refuses the fields it didn't name, even
  // beside `unevaluatedProperties: false` where a map took them.
  assert.deepEqual(
    changed((s) => (note(s).box.additionalProperties = false), tagged),
    ["event note.box.*: a closed object refuses fields it took"],
  );
  const sealed = structuredClone(tagged);
  Object.assign(note(sealed).box, {
    additionalProperties: { type: "string" },
    unevaluatedProperties: false,
  });
  assert.deepEqual(
    changed((s) => (note(s).box.additionalProperties = false), sealed),
    ["event note.box.*: a closed object refuses fields it took"],
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
    [
      'event note.tone: "oneOf" changed',
      'event note.tone: values ["plain"] → ["plain","loud"]',
    ],
  );
  // A bound beside a union holds in every branch.
  const branched = structuredClone(baseline);
  note(branched).slug = { type: "string", anyOf: [{ maxLength: 100 }] };
  assert.deepEqual(
    changed((s) => (note(s).slug.maxLength = 5), branched),
    ['event note.slug: maxLength "none" → 5'],
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
    [
      'served state.pick: type ["object"] → ["null"]',
      "served state.pick.x: the field is gone",
    ],
  );
  // A served branch dropped takes the fields no other branch names, at any depth.
  const payloads = structuredClone(baseline);
  const payload = (field) => ({
    type: "object",
    properties: { payload: { type: "object", properties: { [field]: {} } } },
  });
  payloads.served.properties.pick = { anyOf: [payload("y"), payload("x")] };
  assert.deepEqual(
    changed((s) => s.served.properties.pick.anyOf.pop(), payloads),
    ["served state.pick.payload.x: the field is gone"],
  );
  const listed = structuredClone(payloads);
  const listing = (field) => ({ type: "array", prefixItems: [payload(field)] });
  listed.served.properties.pick = { anyOf: [listing("y"), listing("x")] };
  assert.deepEqual(
    changed((s) => s.served.properties.pick.anyOf.pop(), listed),
    ["served state.pick[0].payload.x: the field is gone"],
  );
  // A field at one position is gone though another position names it, and kept where
  // the remaining branch's `items` names it at every position.
  const shifted = structuredClone(listed);
  shifted.served.properties.pick.anyOf[0].prefixItems = [{}, payload("x")];
  assert.deepEqual(
    changed((s) => s.served.properties.pick.anyOf.pop(), shifted),
    [
      "served state.pick[0].payload: the field is gone",
      "served state.pick[0].payload.x: the field is gone",
    ],
  );
  const covered = structuredClone(listed);
  covered.served.properties.pick.anyOf[0] = { type: "array", items: payload("x") };
  assert.deepEqual(
    changed((s) => s.served.properties.pick.anyOf.pop(), covered),
    [],
  );
  const shared = structuredClone(payloads);
  shared.served.properties.pick.properties = payload("x").properties;
  assert.deepEqual(
    changed((s) => s.served.properties.pick.anyOf.pop(), shared),
    [],
  );
  // A reference compares by its text, and its target where it is declared.
  const nested = structuredClone(baseline);
  nested.served.$defs.Tree = {
    type: "object",
    properties: { child: { $ref: "#/$defs/Tree" } },
  };
  nested.served.properties.tree = { $ref: "#/$defs/Tree" };
  const inline = { type: "object", properties: { child: { type: "string" } } };
  assert.deepEqual(
    changed((s) => (s.served.properties.tree = inline), nested),
    ['served state.tree: $ref "#/$defs/Tree" → "none"'],
  );
  assert.deepEqual(
    changed((s) => (s.served.$defs.Tree.properties.child = { type: "string" }), nested),
    ['served Tree.child: $ref "#/$defs/Tree" → "none"'],
  );
  // A position `prefixItems` stops naming holds what `items` allows.
  const tuple = structuredClone(baseline);
  tuple.served.properties.pair = {
    type: "array",
    prefixItems: [{ type: "string" }],
    items: { type: "number" },
  };
  assert.deepEqual(
    changed((s) => (s.served.properties.pair.prefixItems = []), tuple),
    ['served state.pair[0]: type ["string"] → ["number"]'],
  );
  // A map's newly named field must take what the map took.
  const mapped = structuredClone(baseline);
  note(mapped).counts = { type: "object", additionalProperties: { type: "number" } };
  assert.deepEqual(
    changed((s) => (note(s).counts.properties = { x: { type: "string" } }), mapped),
    ['event note.counts.x: type ["number"] → ["string"]'],
  );
});
