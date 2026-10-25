/* Projected data: the third kind of page word, and the seat that holds it.

   The page has three kinds of visible words:

   - authored prose is in both `says` and `wrote`;
   - runtime apparatus is in neither reading;
   - projected external or derived data is in `says` and not in `wrote`.

   A renderer names its datums one of two ways, and both reach one stamp:

   - It marks the items it drew with plain attributes, `data-lf-datum` (the key) and
     optionally `data-lf-identity` and `data-lf-datum-label`, then dispatches `drawn`
     with the value it drew (leaf-element.js, "Bound values"). Leaf finds the snapshot
     that supplied that value and calls `projectMarked(seat, snapshot)`. The marks do
     nothing on a page without Leaf, so a widget drawn there needs no other code.
   - Prototype only, until its callers move: `projectData(seat, datums, {snapshot})`
     with each datum `{node, key, label?, identity?, origin?}`.

   The renderer alone owns node identity, creation and placement; this owner never
   changes layout. It validates coordinates and marks readable data rather than
   authored prose, removing retired labels even when a renderer retains their nodes as
   ordinary furniture. A mark belongs to the nearest element up the composed tree whose
   tag declares bound data, so a widget drawn inside another marks only its own.

   Keys are non-empty strings unique within the seat. `identity` names a durable
   subject across source replacements, independently of its rendering key. Without
   it a source-backed datum belongs to the observed revision. `label` supplies the
   human coordinate thread chrome reads; core never interprets the opaque key.

   A seat whose declared source attribute is absent may project its inline authored
   value without a snapshot. The watcher constructs `snapshot.origin` from an
   accepted source binding. Passing that snapshot stamps the seat and every datum
   with the source id and revision, including across asynchronous rendering. A
   datum's `origin` may add the exact source-value path its producer knows, or
   explicitly be null for no provenance; marks carry no origin path yet.
   No reader infers a source path from a key or displayed words.
   The renderer commits visible words and their snapshot labels synchronously
   together, before awaiting any later resource settlement. Accepted data alone
   does not change the provenance of words still showing an earlier snapshot.

   This identity contract is experimental and open to change as more producers establish
   what persists through a replacement.

   A selection wholly inside a derived datum captures `{section, datum, quote}`. A datum
   projected from a bound input also captures `{source, source_revision}`. A datum whose
   emitter supplies an identity follows that subject across value replacements, even if
   its rendering key changes. Other keys may name locations within one value, so their
   placements remain pinned to the captured revision. If the original words
   still stand, Leaf marks them. If their display changes, Leaf outlines the same datum
   and keeps the old quote in the thread. A different source makes the placement
   outdated; a duplicate key detaches rather than guessing. Selections crossing datum
   boundaries remain ordinary quote anchors because they name a passage, not one fact.

   `data-lf-projection`, `data-lf-origin`, `data-lf-source`, `data-lf-source-revision`
   and `data-lf-gen` are written here alone, never authored in a version, and a datum is
   a node carrying both `data-lf-projection` and `data-lf-datum` (`DATUM`, passages.js).
   No consumer names a widget's tag. Export preserves the rendered elements and their
   labels as a snapshot, while dropping the scripts that could refresh them. Print
   preserves the same readable words. Neither medium claims that the snapshot remains
   live.

   The application constructs this owner with its semantic invalidation command.
   Each instance batches changed roots until the next microtask; the renderer never
   imports application coordination to discover how a changed datum is presented.
   `LeafElement`, which may not import the application, stamps a widget's marks
   through the module's `projectMarked`, which reaches the owner the application
   constructed. */

import { registry } from "../registry.js";
import { reachScrollers } from "../reach.js";
import { composedParentNode, shadowRootsIn, under } from "../shadow.js";
import { keeps } from "../keeps.js";

// The nodes a projection stamped under its root, in the trees that hold the page's
// words: the ones anchor resolution can find (`pageQueryAll`), so what a replacement
// clears and what a thread resolves to are one set. A marking widget may already have
// dropped the key from a node it retired, so this reads Leaf's own stamp.
const projectedDescendants = (root) =>
  [root, ...shadowRootsIn(root)]
    .flatMap((scope) => [...scope.querySelectorAll("[data-lf-projection]")])
    .filter((element) => element.dataset.lfProjection === root.id);

const markOwner = (node) => {
  for (let at = composedParentNode(node); at; at = composedParentNode(at))
    if (at.nodeType === Node.ELEMENT_NODE && registry[at.localName]?.["x-data"])
      return at;
  return null;
};

// The items a widget marked, read as the datums `stamp` takes. An attribute is always
// a string, so the stamp's refusals reduce to emptiness and duplicates.
const markedDatums = (root) =>
  [root, ...shadowRootsIn(root)]
    .flatMap((scope) => [...scope.querySelectorAll("[data-lf-datum]")])
    .filter((node) => markOwner(node) === root)
    .map((node) => ({
      node,
      key: node.dataset.lfDatum,
      label: node.dataset.lfDatumLabel,
      identity: node.dataset.lfIdentity,
    }));

let constructed = null;
/** Stamp the items a widget marked under `root` (`createDataProjection`). */
export function projectMarked(root, snapshot) {
  if (!constructed) throw new Error("Leaf's data projection has not been constructed");
  constructed.projectMarked(root, snapshot);
}

export function createDataProjection({ invalidateDom }) {
  let dataPaintQueued = false;
  const changedRoots = new Set();
  // The label Leaf last mirrored into each datum's aria-description, so a new label
  // replaces only what Leaf wrote, whoever wrote `data-lf-datum-label`.
  const mirrored = new WeakMap();
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

  /** @param {Element} root @param {any} datums @param {{snapshot?: any}} [options] */
  function projectData(root, datums, { snapshot } = {}) {
    if (!root.id)
      throw new TypeError("projectData root needs an id to name its projection");
    const declaredInputs = registry[root.localName]?.["x-data"] ?? {};
    if (
      snapshot === undefined &&
      Object.values(declaredInputs).some(
        ({ source, reference }) =>
          (source && root.hasAttribute(source)) ||
          (reference && root.hasAttribute(reference)),
      )
    )
      throw new Error(
        `projectData(${root.id}) must receive the snapshot that supplied its records`,
      );
    stamp(root, datums, snapshot, `projectData(${root.id})`);
  }

  /** Stamp the items a widget marked under `root` with the snapshot that supplied the
   *  value it drew; leaf-element.js has matched the value to the snapshot. */
  function stampMarked(root, snapshot) {
    if (!root.id)
      throw new TypeError(`<${root.localName}> needs an id to name its drawn data`);
    stamp(root, markedDatums(root), snapshot, `<${root.localName} id=${root.id}>`);
  }

  /** @param {Element} root @param {any[]} datums @param {any} snapshot @param {string} who */
  function stamp(root, datums, snapshot, who) {
    const stampBasis = (node) => {
      keeps(node, "data-lf-source", snapshot?.source ?? null);
      keeps(node, "data-lf-source-revision", snapshot?.revision ?? null);
    };
    stampBasis(root);
    const projected = projectedDescendants(root);
    const keys = new Set();
    const identities = new Set();
    const nodes = new Set();
    for (const {
      node,
      key,
      label,
      identity,
      origin = snapshot?.origin ?? null,
    } of datums) {
      // A key and an identity become a comment's anchor, and nothing past this point
      // reads them again, so one that is not a word (an object stringifies to the same
      // "[object Object]" as the next) would let a comment follow an unrelated datum.
      if (typeof key !== "string" || !key)
        throw new TypeError(`${who} keys must be non-empty strings`);
      if (keys.has(key)) throw new Error(`${who} received duplicate key ${key}`);
      keys.add(key);
      if (identity !== undefined) {
        if (typeof identity !== "string" || !identity)
          throw new TypeError(`${who} identity for ${key} must be a non-empty string`);
        if (identities.has(identity))
          throw new Error(`${who} received duplicate identity ${identity}`);
        identities.add(identity);
      }
      if (node === root || nodes.has(node))
        throw new Error(`${who} reused the node for key ${key}`);
      if (!under(node, root))
        throw new Error(`${who} datum ${key} is outside its root`);
      nodes.add(node);
      if (label !== undefined) {
        keeps(node, "data-lf-datum-label", label);
        const prior = mirrored.get(node);
        if (
          !node.hasAttribute("aria-label") &&
          (!node.hasAttribute("aria-description") ||
            node.getAttribute("aria-description") === prior)
        ) {
          keeps(node, "aria-description", label);
          mirrored.set(node, label);
        }
      } else {
        unmirror(node);
        delete node.dataset.lfDatumLabel;
      }
      keeps(node, "data-lf-gen", "1");
      keeps(node, "data-lf-projection", root.id);
      keeps(node, "data-lf-datum", key);
      stampBasis(node);
      keeps(node, "data-lf-identity", identity ?? null);
      // The emitter knows which input it transformed. Keep that construction fact,
      // never recover a source path by interpreting its opaque key or displayed words.
      keeps(node, "data-lf-origin", origin === null ? null : JSON.stringify(origin));
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
        unmirror(node);
        delete node.dataset.lfDatumLabel;
      }
    applyProjection(root);
  }

  function unmirror(node) {
    const label = mirrored.get(node);
    if (label === undefined) return;
    if (node.getAttribute("aria-description") === label)
      node.removeAttribute("aria-description");
    mirrored.delete(node);
  }

  constructed = { projectData, projectMarked: stampMarked };
  return constructed;
}
