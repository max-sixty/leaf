/* Where a finding is, in words its author can find in the source.
 *
 * A finding is read by whoever wrote the page, usually an agent that cannot see it
 * drawn, so a bare `<code>` on a page holding forty of them names nothing. An element
 * with an id its author wrote (`ADDRESSABLE`, which leaves out the ids the runtime
 * lends) is named by it. One without is named with the nearest element that has one,
 * across any shadow root between them, since those ids are what `page state` addresses
 * content by.
 *
 * Written once, for the reason `open-roots.js` is: a probe that names elements its own
 * way reports the same box under two names. */
import { ADDRESSABLE } from "/runtime/check-api.js";

/** @param {Element} el */
const tag = (el) => `<${el.localName}${el.matches(ADDRESSABLE) ? " id=" + el.id : ""}>`;

/** @param {Node | null | undefined} el */
export const at = (el) => {
  if (!(el instanceof Element)) return "<?>";
  if (el.matches(ADDRESSABLE)) return tag(el);
  /** @type {Element | null} */
  let node = el;
  for (; node;) {
    const named = node.closest?.(ADDRESSABLE);
    if (named) return `${tag(el)} in ${tag(named)}`;
    const root = node.getRootNode();
    node = root instanceof ShadowRoot ? root.host : null;
  }
  return tag(el);
};

// A structured path under the nearest authored id, or the document when none exists.
// Child indices and explicit shadow steps keep two id-less boxes distinct. Consumers
// serialize it only when they need a map key; navigation never parses a display label.
/** @typedef {{id: string | null, steps: ({shadow: number} | {child: number})[]}} Place */
/** @param {Element} el @returns {Place} */
export const place = (el) => {
  /** @type {Place["steps"]} */
  const steps = [];
  /** @type {Element | null} */
  let node = el;
  for (; node;) {
    if (node.matches?.(ADDRESSABLE) && document.getElementById(node.id) === node)
      return { id: node.id, steps };
    /** @type {ParentNode | null} */
    const parent = node.parentNode;
    if (parent instanceof ShadowRoot) {
      steps.unshift({ shadow: [...parent.children].indexOf(node) });
      node = parent.host;
    } else if (parent instanceof Element || parent instanceof Document) {
      steps.unshift({ child: [...parent.children].indexOf(node) });
      node = parent instanceof Element ? parent : null;
    } else node = null;
  }
  return { id: null, steps };
};

/** @param {Place} location */
export function resolvePlace(location) {
  /** @type {Document | Element | null} */
  let node = location.id === null ? document : document.getElementById(location.id);
  for (const step of location.steps) {
    node =
      "shadow" in step
        ? node instanceof Element
          ? (node.shadowRoot?.children[step.shadow] ?? null)
          : null
        : (node?.children[step.child] ?? null);
  }
  return node instanceof Element ? node : null;
}

// Each record once, where a probe meets the same finding more than once.
/** @template T @param {T[]} records @returns {T[]} */
export const unique = (records) => {
  const seen = new Set();
  return records.filter((record) => {
    const key = JSON.stringify(record);
    return !seen.has(key) && seen.add(key);
  });
};
