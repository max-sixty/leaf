/* Projected data: the third kind of page word, and the seat that holds it.

   The page has three kinds of visible words:

   - authored prose is in both `says` and `wrote`;
   - runtime apparatus is in neither reading;
   - projected external or derived data is in `says` and not in `wrote`.

   `projectData(seat, datums, {snapshot})` labels the renderer's already placed
   descendants. Each datum is `{node, key, label?, identity?, origin?}`. The renderer
   alone owns node identity, creation and placement; this owner never changes layout
   or recovers rendering records from the DOM. It validates coordinates and marks
   readable data rather than authored prose, removing retired labels even when a
   renderer retains their nodes as ordinary furniture.

   Keys are non-empty strings unique within the seat. `identity` names a durable
   subject across source replacements, independently of its rendering key. Without
   it a source-backed datum belongs to the observed revision. `label` supplies the
   human coordinate thread chrome reads; core never interprets the opaque key.

   A seat whose declared source attribute is absent may project its inline authored
   value without a snapshot. The watcher constructs `snapshot.origin` from an
   accepted source binding. Passing that snapshot stamps the seat and every datum
   with the source id and revision, including across asynchronous rendering. A
   datum's `origin` may add the exact source-value path its producer knows, or
   explicitly be null for no provenance.
   No reader infers a source path from a key or displayed words.
   The renderer commits visible words and their snapshot labels synchronously
   together, before awaiting any later resource settlement. Accepted data alone
   does not change the provenance of words still showing an earlier snapshot.

   This identity contract is experimental and open to change as more producers establish
   what persists through a replacement.

   A selection wholly inside a derived datum captures `{section, datum, quote}`. A datum
   projected from `watchData` also captures `{source, source_revision}`. A datum whose
   emitter supplies an identity follows that subject across value replacements, even if
   its rendering key changes. Other keys may name locations within one value, so their
   placements remain pinned to the captured revision. If the original words
   still stand, Leaf marks them. If their display changes, Leaf outlines the same datum
   and keeps the old quote in the thread. A different source makes the placement
   outdated; a duplicate key detaches rather than guessing. Selections crossing datum
   boundaries remain ordinary quote anchors because they name a passage, not one fact.

   `data-lf-projection`, `data-lf-datum`, `data-lf-identity`, `data-lf-origin`,
   `data-lf-source`, `data-lf-source-revision`, and `data-lf-gen` are written by
   `projectData`, never authored in a version. A custom widget joins through the helper
   alone; no consumer names its tag. Export preserves the rendered elements and their
   labels as a snapshot,
   while dropping the scripts that could refresh them. Print preserves the same readable
   words. Neither medium claims that the snapshot remains live.

   The application constructs this owner with its semantic invalidation command.
   Each instance batches changed roots until the next microtask; the renderer never
   imports application coordination to discover how a changed datum is presented. */

import { registry } from "../registry.js";
import { reachScrollers } from "../reach.js";
import { under } from "../shadow.js";
import { keeps } from "../keeps.js";

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

export function createDataProjection({ invalidateDom }) {
  let dataPaintQueued = false;
  const changedRoots = new Set();
  function applyProjection(root) {
    changedRoots.add(root);
    if (dataPaintQueued) return;
    dataPaintQueued = true;
    queueMicrotask(() => {
      dataPaintQueued = false;
      for (const changed of changedRoots)
        if (changed.isConnected) reachScrollers(changed);
      changedRoots.clear();
      invalidateDom();
    });
  }

  function projectData(root, datums, { snapshot } = {}) {
    if (!(root instanceof Element))
      throw new TypeError("projectData root must be an element");
    if (!root.id)
      throw new TypeError("projectData root needs an id to name its projection");
    if (!datums?.[Symbol.iterator])
      throw new TypeError("projectData datums must be iterable");
    const declaredInputs = registry[root.localName]?.["x-data"] ?? {};
    if (
      snapshot === undefined &&
      Object.values(declaredInputs).some(({ source }) => root.hasAttribute(source))
    )
      throw new Error(
        `projectData(${root.id}) must receive the snapshot that supplied its records`,
      );
    if (
      snapshot != null &&
      (typeof snapshot.source !== "string" ||
        !snapshot.source ||
        typeof snapshot.revision !== "string" ||
        !snapshot.revision)
    )
      throw new TypeError("projectData snapshot needs a source and revision");

    const stampBasis = (node) => {
      keeps(node, "data-lf-source", snapshot?.source ?? null);
      keeps(node, "data-lf-source-revision", snapshot?.revision ?? null);
    };
    stampBasis(root);
    const projected = projectedDescendants(root);
    const keys = new Set();
    const identities = new Set();
    const nodes = new Set();
    let index = 0;
    for (const {
      node,
      key,
      label,
      identity,
      origin = snapshot?.origin ?? null,
    } of datums) {
      if (typeof key !== "string" || !key)
        throw new TypeError(
          `projectData(${root.id}) key ${index} must be a non-empty string`,
        );
      if (keys.has(key))
        throw new Error(`projectData(${root.id}) received duplicate key ${key}`);
      keys.add(key);
      if (identity !== undefined) {
        if (typeof identity !== "string" || !identity)
          throw new TypeError(
            `projectData(${root.id}) identity ${index} must be a non-empty string`,
          );
        if (identities.has(identity))
          throw new Error(
            `projectData(${root.id}) received duplicate identity ${identity}`,
          );
        identities.add(identity);
      }
      if (!(node instanceof Element))
        throw new TypeError(`projectData(${root.id}) datum ${key} needs an element`);
      if (node === root || nodes.has(node))
        throw new Error(`projectData(${root.id}) reused the node for key ${key}`);
      if (!under(node, root))
        throw new Error(`projectData(${root.id}) datum ${key} is outside its root`);
      nodes.add(node);
      const priorLabel = node.dataset.lfDatumLabel;
      if (label !== undefined) {
        if (typeof label !== "string" || !label.trim())
          throw new TypeError(
            `projectData(${root.id}) label ${index} must be a non-empty string`,
          );
        keeps(node, "data-lf-datum-label", label);
        if (
          !node.hasAttribute("aria-label") &&
          (!node.hasAttribute("aria-description") ||
            node.getAttribute("aria-description") === priorLabel)
        )
          keeps(node, "aria-description", label);
      } else if (priorLabel !== undefined) {
        if (node.getAttribute("aria-description") === priorLabel)
          node.removeAttribute("aria-description");
        delete node.dataset.lfDatumLabel;
      }
      keeps(node, "data-lf-gen", "1");
      keeps(node, "data-lf-projection", root.id);
      keeps(node, "data-lf-datum", key);
      stampBasis(node);
      keeps(node, "data-lf-identity", identity ?? null);
      // The emitter knows which input it transformed. Keep that construction fact,
      // never recover a source path by interpreting its opaque key or displayed words.
      if (origin !== null && (typeof origin !== "object" || Array.isArray(origin)))
        throw new TypeError(
          `projectData(${root.id}) origin ${index} must be an object`,
        );
      keeps(node, "data-lf-origin", origin === null ? null : JSON.stringify(origin));
      index++;
    }

    for (const node of projected)
      if (!nodes.has(node)) {
        delete node.dataset.lfGen;
        delete node.dataset.lfProjection;
        delete node.dataset.lfDatum;
        delete node.dataset.lfIdentity;
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
    applyProjection(root);
  }

  return { projectData };
}
