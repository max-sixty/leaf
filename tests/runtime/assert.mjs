/* `node:assert/strict` as a runtime test imports it: dom.mjs routes that import here.

   Node writes a failed comparison's message by inspecting both values whole, and ignores
   their own inspection when it does. A happy-dom node reaches its document, its window
   and every other node through symbol-keyed internals, so one failed
   `assert.equal(node, other)` composed a diff of two whole documents: seconds for two bare
   elements, and in a fuller document long enough, and big enough, that the file was
   killed before it reported anything.

   So a comparison whose values hold no node goes to Node unchanged. One that does is
   compared, and reported, with each node replaced by a reference of its own: one per
   node, so two nodes are equal only when they are the same node, as the tests mean them,
   and a failure writes the node as its opening tag and a number. Every container on the
   way to a node is copied with its prototype and every own property, so it compares as
   it would have. A message function is still handed the values as given. `t.assert`,
   from node:test, does not come through here. */
import strict from "node:assert/strict";

class NodeReference {
  constructor(node, number) {
    const element = node.nodeType === Node.ELEMENT_NODE;
    const attributes = element
      ? [...node.attributes].map(({ name, value }) => ` ${name}="${value}"`).join("")
      : "";
    this.node = element
      ? `<${node.localName}${attributes}> #${number}`
      : `${node.nodeName ?? "window"} #${number}`;
  }
}
const references = new WeakMap();
let counted = 0;
const isNode = (value) => value instanceof Node || value === window;
const referenceTo = (node) => {
  if (!references.has(node))
    references.set(node, Object.freeze(new NodeReference(node, ++counted)));
  return references.get(node);
};

// The own values a comparison reads of an object: its data properties, and a Map's or
// Set's members. No getter runs.
function* members(value) {
  for (const key of Reflect.ownKeys(value)) {
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if ("value" in descriptor) yield descriptor.value;
  }
  if (value instanceof Map) for (const entry of value) yield* entry;
  if (value instanceof Set) yield* value;
}
function holdsNode(value, seen = new Set()) {
  if (isNode(value)) return true;
  if (value === null || typeof value !== "object" || seen.has(value)) return false;
  seen.add(value);
  for (const member of members(value)) if (holdsNode(member, seen)) return true;
  return false;
}

// The value with each node it holds replaced by its reference. One reading per
// comparison, so a value both sides share stays one value.
function written(value, seen) {
  if (isNode(value)) return referenceTo(value);
  if (value === null || typeof value !== "object" || !holdsNode(value)) return value;
  if (seen.has(value)) return seen.get(value);
  const copy = Array.isArray(value)
    ? []
    : value instanceof Map
      ? new Map()
      : value instanceof Set
        ? new Set()
        : {};
  Object.setPrototypeOf(copy, Object.getPrototypeOf(value));
  seen.set(value, copy);
  if (value instanceof Map)
    for (const [key, item] of value) copy.set(written(key, seen), written(item, seen));
  if (value instanceof Set) for (const item of value) copy.add(written(item, seen));
  for (const key of Reflect.ownKeys(value)) {
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if ("value" in descriptor) descriptor.value = written(descriptor.value, seen);
    Object.defineProperty(copy, key, descriptor);
  }
  return copy;
}

const REFERENCE = new Set(["equal", "notEqual", "strictEqual", "notStrictEqual"]);
const DEEP = new Set([
  "deepEqual",
  "notDeepEqual",
  "deepStrictEqual",
  "notDeepStrictEqual",
  "partialDeepStrictEqual",
]);

// Bound rather than wrapped, so a bare `assert(value)` still quotes the test's own line.
const assert = strict.bind(null);
Object.assign(assert, strict);
for (const name of [...REFERENCE, ...DEEP]) {
  if (!strict[name]) continue;
  assert[name] = function compare(actual, expected, ...rest) {
    if (!holdsNode(actual) && !holdsNode(expected))
      return strict[name](actual, expected, ...rest);
    // A reference comparison is answered on the values as given, since a copy of an
    // object is never the object; only its failure is written with references.
    if (REFERENCE.has(name) && Object.is(actual, expected) !== name.startsWith("not"))
      return;
    const message =
      typeof rest[0] === "function" ? [() => rest[0](actual, expected)] : rest;
    const seen = new Map();
    try {
      strict[name](written(actual, seen), written(expected, seen), ...message);
    } catch (error) {
      if (error instanceof strict.AssertionError)
        Error.captureStackTrace(error, compare);
      throw error;
    }
  };
}
assert.strict = assert;
export default assert;
