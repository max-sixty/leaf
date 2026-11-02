/* Projected data: the third kind of page word, and the seat that holds it.

   The page has three kinds of visible words:

   - authored prose is in both `says` and `wrote`;
   - runtime apparatus is in neither reading;
   - projected external or derived data is in `says` and not in `wrote`.

   A widget whose tag declares `x-data` names the items it drew from its bound value
   with plain attributes, and Leaf stamps them (`projectMarked`) once the widget
   reports the value it drew (element-data.js, "Bound values"):

   - `data-lf-datum`, the key: a non-empty string unique within the seat, which core
     never interprets;
   - `data-lf-identity`, optional: a durable subject across source replacements,
     independently of its key. Without it a source-backed datum belongs to the
     observed revision;
   - `data-lf-datum-label`, optional: the human coordinate thread chrome reads;
   - `data-lf-origin-path`, optional: a JSON array naming the exact place in the value
     the datum shows, such as `["files", 0, "patch"]`, which only its producer knows.
     No reader infers a source path from a key or displayed words.

   The marks do nothing on a page without Leaf, so a widget drawn there needs no other
   code. A mark belongs to the nearest element up the composed tree whose tag declares
   bound data, so a widget drawn inside another marks only its own. The widget alone
   owns its nodes and their marks, removing a mark from a node it keeps that no longer
   shows data; this owner never changes layout. It validates the marks, and writes the
   stamp that makes them readable data rather than authored prose: the seat's and each
   datum's source and revision, and the datum's origin, the snapshot's origin with the
   mark's path. A stamp without a snapshot, for words no bound value supplied, carries
   neither. The widget commits visible words and their marks synchronously together,
   before awaiting any later resource settlement. Accepted data alone does not change
   the provenance of words still showing an earlier snapshot.

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
import { composedParentNode, shadowRootsIn } from "../shadow.js";
import { keeps } from "../keeps.js";

// The nodes a projection stamped under its root, in the trees that hold the page's
// words: the ones anchor resolution can find (`pageQueryAll`), so what a replacement
// clears and what a thread resolves to are one set. A marking widget may already have
// dropped the key from a node it retired, so this reads Leaf's own stamp.
/** @param {Element} root */
const projectedDescendants = (root) =>
  [root, ...shadowRootsIn(root)]
    .flatMap((scope) => [...scope.querySelectorAll("[data-lf-projection]")])
    .filter((element) => element.getAttribute("data-lf-projection") === root.id);

/** @param {Element} node */
const markOwner = (node) => {
  for (let at = composedParentNode(node); at; at = composedParentNode(at))
    if (at instanceof Element && registry[at.localName]?.["x-data"]) return at;
  return null;
};

// The items a widget marked under `root`. An attribute is always a string, so the
// stamp's refusals reduce to emptiness, duplicates and a malformed path.
/** @param {Element} root */
const markedDatums = (root) =>
  [root, ...shadowRootsIn(root)]
    .flatMap((scope) => [...scope.querySelectorAll("[data-lf-datum]")])
    .filter((node) => markOwner(node) === root)
    .map((node) => ({
      node,
      key: node.getAttribute("data-lf-datum") ?? undefined,
      label: node.getAttribute("data-lf-datum-label") ?? undefined,
      identity: node.getAttribute("data-lf-identity") ?? undefined,
      path: node.getAttribute("data-lf-origin-path") ?? undefined,
    }));

// A mark's origin path, a JSON array of field names and indices.
/** @param {string} who @param {string} key @param {string} text */
const originPath = (who, key, text) => {
  /** @type {unknown} */
  let path;
  try {
    path = JSON.parse(text);
  } catch {
    path = null;
  }
  if (
    !Array.isArray(path) ||
    !path.every(
      /** @param {unknown} step @returns {step is string | number} */
      (step) =>
        typeof step === "string" ||
        (typeof step === "number" && Number.isInteger(step) && step >= 0),
    )
  )
    throw new TypeError(
      `${who} datum ${key} data-lf-origin-path must be a JSON array of field names and indices`,
    );
  return path;
};

/** @type {{projectMarked: (root: Element, snapshot: import("../data.js").DataSnapshot | null) => void} | null} */
let constructed = null;
/** Stamp the items a widget marked under `root` (`createDataProjection`).
 * @param {Element} root @param {import("../data.js").DataSnapshot | null} snapshot */
export function projectMarked(root, snapshot) {
  if (!constructed) throw new Error("Leaf's data projection has not been constructed");
  constructed.projectMarked(root, snapshot);
}

/** @param {{invalidateDom: () => void}} options */
export function createDataProjection({ invalidateDom }) {
  let dataPaintQueued = false;
  /** @type {Set<Element>} */
  const changedRoots = new Set();
  // The label Leaf last mirrored into each datum's aria-description, so a new label
  // replaces only what Leaf wrote, whoever wrote `data-lf-datum-label`.
  /** @type {WeakMap<Element, string>} */
  const mirrored = new WeakMap();
  /** @param {Element} root */
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

  /** Stamp the items a widget marked under `root` with the snapshot that supplied the
   *  value it drew, or null for words no bound value supplied; element-data.js has
   *  matched the value to the snapshot.
   *  @param {Element} root @param {import("../data.js").DataSnapshot | null} snapshot */
  function projectMarked(root, snapshot) {
    if (!root.id)
      throw new TypeError(`<${root.localName}> needs an id to name its drawn data`);
    const who = `<${root.localName} id=${root.id}>`;
    /** @param {Element} node */
    const stampBasis = (node) => {
      keeps(node, "data-lf-source", snapshot?.source ?? null);
      keeps(node, "data-lf-source-revision", snapshot?.revision ?? null);
    };
    stampBasis(root);
    const projected = projectedDescendants(root);
    const keys = new Set();
    const identities = new Set();
    const nodes = new Set();
    for (const { node, key, label, identity, path } of markedDatums(root)) {
      // A key and an identity become a comment's anchor, so a duplicate would let a
      // comment follow an unrelated datum.
      if (!key) throw new TypeError(`${who} keys must be non-empty strings`);
      if (keys.has(key)) throw new Error(`${who} received duplicate key ${key}`);
      keys.add(key);
      if (identity !== undefined) {
        if (!identity)
          throw new TypeError(`${who} identity for ${key} must be a non-empty string`);
        if (identities.has(identity))
          throw new Error(`${who} received duplicate identity ${identity}`);
        identities.add(identity);
      }
      nodes.add(node);
      if (label !== undefined) {
        const prior = mirrored.get(node);
        if (
          !node.hasAttribute("aria-label") &&
          (!node.hasAttribute("aria-description") ||
            node.getAttribute("aria-description") === prior)
        ) {
          keeps(node, "aria-description", label);
          mirrored.set(node, label);
        }
      } else unmirror(node);
      keeps(node, "data-lf-gen", "1");
      keeps(node, "data-lf-projection", root.id);
      stampBasis(node);
      // The emitter knows which part of the value it drew. Keep that construction
      // fact, never recover a source path by interpreting its opaque key or words.
      const origin = snapshot?.origin
        ? {
            ...snapshot.origin,
            ...(path === undefined ? {} : { path: originPath(who, key, path) }),
          }
        : null;
      keeps(node, "data-lf-origin", origin === null ? null : JSON.stringify(origin));
    }

    for (const node of projected)
      if (!nodes.has(node)) {
        node.removeAttribute("data-lf-gen");
        node.removeAttribute("data-lf-projection");
        node.removeAttribute("data-lf-source");
        node.removeAttribute("data-lf-source-revision");
        node.removeAttribute("data-lf-origin");
        unmirror(node);
      }
    applyProjection(root);
  }

  /** @param {Element} node */
  function unmirror(node) {
    const label = mirrored.get(node);
    if (label === undefined) return;
    if (node.getAttribute("aria-description") === label)
      node.removeAttribute("aria-description");
    mirrored.delete(node);
  }

  constructed = { projectMarked };
  return constructed;
}
