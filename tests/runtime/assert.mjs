/* `node:assert/strict` as a runtime test imports it: dom.mjs routes that import here.

   Node writes a failed comparison's message by inspecting both values whole, and ignores
   their own inspection when it does. A happy-dom node reaches its document, its window
   and every other node through symbol-keyed internals, so one failed
   `assert.equal(node, other)` composed a diff of two whole documents: seconds for two bare
   elements, and in a fuller document long enough, and big enough, that the file was
   killed before it reported anything. So each comparison runs on its values with every
   node written as its opening tag and a number of its own. Two nodes are the same value
   only when they are the same node, as the tests mean them, and a failure names them
   in a line. */
import strict from "node:assert/strict";

const numbers = new WeakMap();
let counted = 0;
const opening = (node) => {
  if (node.nodeType !== Node.ELEMENT_NODE) return node.nodeName;
  const attributes = [...node.attributes].map(
    ({ name, value }) => ` ${name}="${value}"`,
  );
  return `<${node.localName}${attributes.join("")}>`;
};
const named = (node) => {
  if (!numbers.has(node)) numbers.set(node, ++counted);
  return `${opening(node)} #${numbers.get(node)}`;
};

// The value with each node it holds written out, through the containers a comparison
// walks. One reading per comparison, so a value both sides share stays one value.
function written(value, seen) {
  if (value instanceof Node) return named(value);
  if (value === null || typeof value !== "object") return value;
  if (seen.has(value)) return seen.get(value);
  const prototype = Object.getPrototypeOf(value);
  let copy;
  if (Array.isArray(value)) {
    copy = [];
    seen.set(value, copy);
    for (const item of value) copy.push(written(item, seen));
  } else if (value instanceof Map) {
    copy = new Map();
    seen.set(value, copy);
    for (const [key, item] of value) copy.set(written(key, seen), written(item, seen));
  } else if (value instanceof Set) {
    copy = new Set();
    seen.set(value, copy);
    for (const item of value) copy.add(written(item, seen));
  } else if (prototype === Object.prototype || prototype === null) {
    copy = Object.create(prototype);
    seen.set(value, copy);
    for (const key of Reflect.ownKeys(value)) copy[key] = written(value[key], seen);
  } else return value;
  return copy;
}

const COMPARISONS = [
  "equal",
  "notEqual",
  "strictEqual",
  "notStrictEqual",
  "deepEqual",
  "notDeepEqual",
  "deepStrictEqual",
  "notDeepStrictEqual",
  "partialDeepStrictEqual",
];
// Bound rather than wrapped, so a bare `assert(value)` still quotes the test's own line.
const assert = strict.bind(null);
Object.assign(assert, strict);
for (const name of COMPARISONS) {
  if (!strict[name]) continue;
  assert[name] = function compare(actual, expected, ...message) {
    // A reference comparison that holds is answered on the values as given: a copy of
    // an object is never the object.
    if (/^(strictEqual|equal)$/.test(name) && Object.is(actual, expected)) return;
    if (/^not(Strict)?Equal$/.test(name) && !Object.is(actual, expected)) return;
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
