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
   it would have; an object holding its value in an internal slot, such as a Date, is
   compared whole, so a node among its own properties is written out in full. A message
   function is still handed the values as given. Not covered: a node only a getter
   reaches, and `t.assert` from node:test. */
import strict from "node:assert/strict";
import { types } from "node:util";

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

// An object whose value lives in an internal slot (a Date's time, an Error's kind) is no
// container to copy: Node compares it whole.
const SLOTTED = [
  types.isDate,
  types.isRegExp,
  types.isNativeError,
  types.isBoxedPrimitive,
  types.isArrayBufferView,
  types.isAnyArrayBuffer,
  types.isPromise,
  types.isWeakMap,
  types.isWeakSet,
];
const container = (value) =>
  value !== null && typeof value === "object" && !SLOTTED.some((is) => is(value));

// The own values a comparison reads of a container: its data properties, and a Map's or
// Set's members. No getter runs, so a node a getter alone reaches is not seen.
function* members(value) {
  for (const key of Reflect.ownKeys(value)) {
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if ("value" in descriptor) yield descriptor.value;
  }
  if (value instanceof Map) for (const entry of value) yield* entry;
  if (value instanceof Set) yield* value;
}
// Whether a node lies under the value, through containers. `holding` keeps each
// container's answer for one comparison. Every container the value reaches is found
// before any is answered, and a node then marks each container that reaches it, so a
// container in a cycle holds a node wherever on the cycle that node hangs.
function holdsNode(value, holding) {
  if (isNode(value)) return true;
  if (!container(value)) return false;
  if (holding.has(value)) return holding.get(value);
  const holders = new Map([[value, []]]);
  const marked = [];
  for (const pending = [value]; pending.length;) {
    const at = pending.pop();
    for (const member of members(at)) {
      const node = isNode(member);
      if (node || holding.get(member)) marked.push(at);
      if (node || !container(member) || holding.has(member)) continue;
      if (!holders.has(member)) {
        holders.set(member, []);
        pending.push(member);
      }
      holders.get(member).push(at);
    }
  }
  for (const at of holders.keys()) holding.set(at, false);
  while (marked.length) {
    const at = marked.pop();
    if (holding.get(at)) continue;
    holding.set(at, true);
    marked.push(...holders.get(at));
  }
  return holding.get(value);
}

// The value with each node it holds replaced by its reference. One reading per
// comparison, so a value both sides share stays one value.
function written(value, seen, holding) {
  if (isNode(value)) return referenceTo(value);
  if (!holdsNode(value, holding)) return value;
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
  const write = (item) => written(item, seen, holding);
  if (value instanceof Map)
    for (const [key, item] of value) copy.set(write(key), write(item));
  if (value instanceof Set) for (const item of value) copy.add(write(item));
  for (const key of Reflect.ownKeys(value)) {
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if ("value" in descriptor) descriptor.value = write(descriptor.value);
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
    const holding = new Map();
    if (!holdsNode(actual, holding) && !holdsNode(expected, holding))
      return strict[name](actual, expected, ...rest);
    // A reference comparison is answered on the values as given, since a copy of an
    // object is never the object; only its failure is written with references.
    if (REFERENCE.has(name) && Object.is(actual, expected) !== name.startsWith("not"))
      return;
    const message =
      typeof rest[0] === "function" ? [() => rest[0](actual, expected)] : rest;
    const seen = new Map();
    try {
      strict[name](
        written(actual, seen, holding),
        written(expected, seen, holding),
        ...message,
      );
    } catch (error) {
      if (error instanceof strict.AssertionError)
        Error.captureStackTrace(error, compare);
      throw error;
    }
  };
}
assert.strict = assert;
export default assert;
