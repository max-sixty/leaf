/* Projected data: the third kind of page word, and the seat that holds it.

   The page has three kinds of visible words:

   - authored prose is in both `says` and `wrote`;
   - runtime apparatus is in neither reading;
   - projected external or derived data is in `says` and not in `wrote`.

   The last kind is a projection, not another source of truth. An id-bearing element in
   the version is its seat. `projectData(seat, records, keyOf, render, options)` owns
   that seat's children, labels each rendered element with the seat id
   (`data-lf-projection`) and its record's stable key (`data-lf-datum`), and marks it
   generated. With `{nested: true}` it labels descendants a renderer already placed
   without reconciling their layout. An optional `labelOf(record, index)` supplies the
   human coordinate thread chrome reads; core never interprets the opaque key. When
   records came from `watchData`, the `snapshot` option carries that delivery's source id
   and revision, including across asynchronous rendering. Leaf stamps the seat and each
   datum with that provenance. Records remain the caller's input; the DOM never becomes
   another record store.

   The watcher constructs `origin` from the accepted source binding. `projectData` reads
   it from the supplied snapshot; emitters override `originOf` only to add a source-value
   path where construction knows that coordinate. The helper writes `data-lf-origin`
   beside each datum and clears it when an origin or nested datum retires. The package
   reference owns the origin fields; no reading infers them from a datum key or rendered
   text.

   Keys identify facts, not renderings or display strings. They are non-empty strings,
   unique within one projection, and must remain with the same logical datum across
   refreshes. `render` receives the prior element for the key and may update it in place;
   returning a replacement is also valid. Reconciliation retains nodes already in their
   place and schedules the shared anchor pass after synchronous projection work.

   A selection wholly inside a derived datum captures `{section, datum, quote}`. A datum
   projected from `watchData` also captures `{source, data_revision}`. Within that source
   revision, resolution looks only for the key under its section. If the original words
   still stand, Leaf marks them. If their display changes, Leaf outlines the same datum
   and keeps the old quote in the thread. A current-source replacement makes the
   placement outdated: the thread keeps its section context and remains in the panel, but
   it does not mark or attach to a datum from the new revision. An authored snapshot
   remains exact. A missing or duplicate key detaches rather than guessing. Selections
   crossing datum boundaries remain ordinary quote anchors because they name a passage,
   not one fact.

   `data-lf-projection`, `data-lf-datum`, `data-lf-origin`, `data-lf-source`,
   `data-lf-source-revision`, and `data-lf-gen` are written by `projectData`, never
   authored in a version. A custom widget joins through the helper alone; no consumer
   names its tag. Export preserves the rendered elements and their labels as a snapshot,
   while dropping the scripts that could refresh them. Print preserves the same readable
   words. Neither medium claims that the snapshot remains live. */

import { registry } from "../registry.js";
import { reachScrollers } from "../reach.js";
import { renderPanel, setChildren } from "../conversation/reconcile.js";

// Runtime-supplied data is a third kind of page word: it is neither prose the author
// put in the version nor apparatus the runtime asks the reader to operate. It belongs
// in `says` because the reader can point at it, and not in `wrote` because no version
// contains it. `projectData` states both facts on each rendered datum: data-lf-gen keeps
// it out of the authored reading, while data-lf-projection + data-lf-datum give it a
// logical identity that survives a renderer replacing its nodes.
//
// The source is the authored seat's id and the key is local to that seat. Keeping the
// pair in the DOM, rather than in a map beside it, preserves the document + log as the
// whole state model: records remain the caller's input, and this function owns only their
// current rendering. A module supplies fresh records on every call. `render` receives the
// prior node for the same key so an ordinary update can preserve focus and selection, but
// returning a replacement is valid—the anchor follows the key, not node identity.
//
// A projection normally owns all children of its root. A renderer that already owns a
// nested layout may opt into nested labels; the returned elements remain in place, but
// the same key validation and anchor pass still apply. `labelOf` gives generic chrome a
// human name for a datum without making it interpret the stable key. Keys are required
// strings rather than coerced values: `1` and `"1"` becoming the same DOM attribute
// would silently merge two facts.
let dataPaintQueued = false;
const changedRoots = new Set();
function projectionChanged(root) {
  changedRoots.add(root);
  if (dataPaintQueued) return;
  dataPaintQueued = true;
  queueMicrotask(() => {
    dataPaintQueued = false;
    for (const changed of changedRoots)
      if (changed.isConnected) reachScrollers(changed);
    changedRoots.clear();
    renderPanel();
  });
}

const projectedDescendants = (root) => {
  const found = [];
  const visit = (scope) => {
    for (const element of scope.querySelectorAll("*")) {
      found.push(element);
      if (element.shadowRoot) visit(element.shadowRoot);
    }
  };
  visit(root);
  if (root.shadowRoot) visit(root.shadowRoot);
  return found.filter(
    (element) =>
      element.dataset.lfProjection === root.id && element.hasAttribute("data-lf-datum"),
  );
};

const containedBy = (root, node) => {
  for (let at = node; at; at = at.parentElement ?? at.getRootNode()?.host ?? null)
    if (at === root) return true;
  return false;
};

export function projectData(
  root,
  records,
  keyOf,
  render,
  { nested = false, labelOf = null, snapshot, originOf = null } = {},
) {
  if (!(root instanceof Element))
    throw new TypeError("projectData root must be an element");
  if (!root.id)
    throw new TypeError("projectData root needs an id to name its projection");
  if (!records?.[Symbol.iterator])
    throw new TypeError("projectData records must be iterable");
  if (typeof keyOf !== "function" || typeof render !== "function")
    throw new TypeError("projectData needs key and render functions");

  if (typeof nested !== "boolean")
    throw new TypeError("projectData nested must be a boolean");
  if (labelOf !== null && typeof labelOf !== "function")
    throw new TypeError("projectData labelOf must be a function or null");
  const declaredInputs = registry[root.localName]?.["x-data"] ?? {};
  if (snapshot === undefined && Object.keys(declaredInputs).length)
    throw new Error(
      `projectData(${root.id}) must receive the snapshot that supplied its records`,
    );
  if (
    snapshot != null &&
    (typeof snapshot.source !== "string" ||
      !snapshot.source ||
      !Number.isInteger(snapshot.revision) ||
      snapshot.revision < 1)
  )
    throw new TypeError("projectData snapshot needs a source and positive revision");

  const stampBasis = (node) => {
    if (snapshot) node.dataset.lfSource = snapshot.source;
    else delete node.dataset.lfSource;
    if (snapshot) node.dataset.lfSourceRevision = String(snapshot.revision);
    else delete node.dataset.lfSourceRevision;
  };
  stampBasis(root);
  if (originOf !== null && typeof originOf !== "function")
    throw new TypeError("projectData originOf must be a function or null");

  const prior = new Map();
  const projected = nested ? projectedDescendants(root) : [...root.children];
  for (const child of projected) {
    if (child.dataset.lfProjection !== root.id || !child.hasAttribute("data-lf-datum"))
      continue;
    const key = child.dataset.lfDatum;
    if (prior.has(key))
      throw new Error(`projectData(${root.id}) already renders duplicate key ${key}`);
    prior.set(key, child);
  }

  const keys = new Set();
  const nodes = new Set();
  const wanted = [];
  let index = 0;
  for (const record of records) {
    const key = keyOf(record, index);
    if (typeof key !== "string" || !key)
      throw new TypeError(
        `projectData(${root.id}) key ${index} must be a non-empty string`,
      );
    if (keys.has(key))
      throw new Error(`projectData(${root.id}) received duplicate key ${key}`);
    keys.add(key);
    const node = render(record, prior.get(key) ?? null, index);
    if (!(node instanceof Element))
      throw new TypeError(`projectData(${root.id}) render(${key}) returned no element`);
    if (node === root || nodes.has(node))
      throw new Error(`projectData(${root.id}) render reused the node for key ${key}`);
    if (nested && !containedBy(root, node))
      throw new Error(
        `projectData(${root.id}) render(${key}) returned an element outside its root`,
      );
    nodes.add(node);
    const priorLabel = node.dataset.lfDatumLabel;
    if (labelOf) {
      const label = labelOf(record, index);
      if (typeof label !== "string" || !label.trim())
        throw new TypeError(
          `projectData(${root.id}) label ${index} must be a non-empty string`,
        );
      node.dataset.lfDatumLabel = label;
      if (
        !node.hasAttribute("aria-label") &&
        (!node.hasAttribute("aria-description") ||
          node.getAttribute("aria-description") === priorLabel)
      )
        node.setAttribute("aria-description", label);
    } else if (priorLabel !== undefined) {
      if (node.getAttribute("aria-description") === priorLabel)
        node.removeAttribute("aria-description");
      delete node.dataset.lfDatumLabel;
    }
    node.dataset.lfGen = "1";
    node.dataset.lfProjection = root.id;
    node.dataset.lfDatum = key;
    stampBasis(node);
    // The emitter knows which input it transformed. Keep that construction fact,
    // never recover a source path by interpreting its opaque key or displayed words.
    const origin = (originOf ? originOf(record, index) : snapshot?.origin) ?? null;
    if (origin !== null) {
      if (typeof origin !== "object" || Array.isArray(origin))
        throw new TypeError(
          `projectData(${root.id}) origin ${index} must be an object`,
        );
      node.dataset.lfOrigin = JSON.stringify(origin);
    } else delete node.dataset.lfOrigin;
    wanted.push(node);
    index++;
  }

  if (nested) {
    for (const node of projected)
      if (!nodes.has(node)) {
        delete node.dataset.lfGen;
        delete node.dataset.lfProjection;
        delete node.dataset.lfDatum;
        delete node.dataset.lfSource;
        delete node.dataset.lfSourceRevision;
        delete node.dataset.lfOrigin;
        const label = node.dataset.lfDatumLabel;
        if (label !== undefined) {
          if (node.getAttribute("aria-description") === label)
            node.removeAttribute("aria-description");
          delete node.dataset.lfDatumLabel;
        }
      }
  } else {
    // A projection's children are its rendering. Remove source whitespace or an old
    // non-element rendering first, then use the runtime's stable-child reconciler so a
    // node already in the right place is not detached and reinserted.
    for (const child of [...root.childNodes])
      if (child.nodeType !== Node.ELEMENT_NODE) child.remove();
    setChildren(root, wanted);
  }
  projectionChanged(root);
  return wanted;
}
