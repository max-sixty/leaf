/* Reading regions are stable semantic places whose current scroll container may change.

   `registerReadingRegion` binds one stable id to a host and body. The host makes focus
   in a pane's header or footer select that pane, while the body is the scroller only in
   bounded posture. `registerArrangement` groups regions under one allocation owner;
   nested and compound owners inherit posture through DOM containment and read their
   assigned content box on demand. CSS still owns how that box is divided.

   A posture transition notifies watchers before mutation, when old geometry is intact,
   and after the next animation frame, when new geometry can be read. Superseded after
   notifications are dropped. Continuity owners subscribe here; this module stores no
   landmarks or scroll offsets. Hidden connected regions remain registered and return
   null bounds. Cleanup removes live DOM bindings, so a replacement can reclaim an id. */
import { shownBox, shownRect } from "./geometry.js";
import { containsAcross } from "./passages.js";
import { pageScroller } from "./scrolling.js";
import { layoutChanged } from "./widget-elements.js";
import { reachReadingScroller } from "./reach.js";

const regions = new Map();
const arrangements = new Set();
const transitionWatchers = new Set();

const depthOf = (node) => {
  let depth = 0;
  for (
    let current = node;
    current;
    current = current.parentElement ?? current.getRootNode()?.host ?? null
  )
    depth += 1;
  return depth;
};

const live = (region) => region?.host?.isConnected && region.body?.isConnected;

const hidden = (region) =>
  !live(region) ||
  region.host.hidden ||
  region.host.closest?.("[hidden], [aria-hidden='true']") !== null ||
  shownRect(region.host, new Map()) === null;

const arrangementFor = (node) =>
  [...arrangements]
    .filter(
      (arrangement) =>
        arrangement.owner.isConnected && containsAcross(arrangement.owner, node),
    )
    .sort((a, b) => depthOf(b.owner) - depthOf(a.owner))[0];

const parentArrangement = (arrangement) =>
  [...arrangements]
    .filter(
      (candidate) =>
        candidate !== arrangement &&
        candidate.owner.isConnected &&
        containsAcross(candidate.content, arrangement.owner),
    )
    .sort((a, b) => depthOf(b.owner) - depthOf(a.owner))[0];

const postureOf = (arrangement) => {
  if (!arrangement) return "flow";
  return arrangement.posture ?? postureOf(parentArrangement(arrangement));
};

const regionRecord = (region) => ({
  id: region.id,
  host: region.host,
  body: region.body,
});

export function compoundReadingRegionId(owner, localName) {
  if (!owner?.id || !/^[a-z][a-z0-9-]*$/.test(localName ?? ""))
    throw new Error("leaf: a compound reading region needs an owner id and local name");
  return `lf-region:${owner.id}:${localName}`;
}

const validateRegion = ({ id, host, body }) => {
  if (typeof id !== "string" || !id || !host || !body)
    throw new Error("leaf: a reading region needs id, host, and body");
};

const admitRegions = (declared) => {
  const ids = new Set();
  for (const declaration of declared) {
    validateRegion(declaration);
    if (ids.has(declaration.id) || live(regions.get(declaration.id)))
      throw new Error(`leaf: reading region ${declaration.id} is already live`);
    ids.add(declaration.id);
  }
  return declared.map((declaration) => {
    const { id, host, body } = declaration;
    const region = { id, host, body };
    const stopReaching = reachReadingScroller(body);
    regions.set(id, region);
    return () => {
      if (regions.get(id) === region) regions.delete(id);
      stopReaching();
    };
  });
};

export function registerReadingRegion(declaration) {
  const [cleanup] = admitRegions([declaration]);
  return cleanup;
}

export const readingRegion = (id) => {
  const region = regions.get(id);
  return live(region) ? regionRecord(region) : undefined;
};

export const readingRegions = () =>
  [...regions.values()].filter(live).map(regionRecord);

export const readingRegionFor = (node) => {
  const region = [...regions.values()]
    .filter((candidate) => live(candidate) && containsAcross(candidate.host, node))
    .sort((a, b) => depthOf(b.host) - depthOf(a.host))[0];
  return region && regionRecord(region);
};

const asRegion = (regionOrNode) =>
  typeof regionOrNode === "string"
    ? regions.get(regionOrNode)
    : (regions.get(regionOrNode?.id) ??
      regions.get(readingRegionFor(regionOrNode)?.id));

export const readingPosture = (regionOrNode) =>
  postureOf(arrangementFor(asRegion(regionOrNode)?.host ?? regionOrNode));

export function effectiveScroller(regionOrNode) {
  const region = asRegion(regionOrNode);
  if (!region) return pageScroller;
  if (readingPosture(region) === "bounded") return region.body;
  const containing = [...regions.values()]
    .filter(
      (candidate) =>
        candidate !== region &&
        live(candidate) &&
        containsAcross(candidate.body, region.host),
    )
    .sort((a, b) => depthOf(b.host) - depthOf(a.host))[0];
  return containing ? effectiveScroller(containing) : pageScroller;
}

// Which box scrolls a given element, for anything that has to name its scroller rather
// than search for one. The document's for everything the document holds — and the
// panel's own list for a widget an agent put in a reply, which is scrolled by that and
// by nothing else. A drag naming the wrong one sits at the edge waiting for a scroll
// that never comes.
export const scrollerFor = (el) => {
  let region = readingRegionFor(el);
  while (region) {
    if (containsAcross(region.body, el)) return effectiveScroller(region);
    region = readingRegionFor(region.host.parentElement);
  }
  return pageScroller;
};

export function shownRegionBounds(regionOrNode) {
  const region = asRegion(regionOrNode);
  if (!region || hidden(region)) return null;
  return shownRect(region.body, new Map());
}

export function readingAllocation(node) {
  const arrangement = arrangementFor(asRegion(node)?.host ?? node);
  if (!arrangement?.content?.isConnected) return null;
  const box = shownBox(arrangement.content);
  return { width: box.width, height: box.height };
}

export function watchReadingRegionTransitions(listener) {
  transitionWatchers.add(listener);
  return () => transitionWatchers.delete(listener);
}

const notify = (detail) => {
  for (const listener of transitionWatchers) listener(detail);
};

export function registerArrangement({ owner, content, regions: declared = [] }) {
  if (!owner || !content)
    throw new Error("leaf: an arrangement needs owner and content elements");
  if ([...arrangements].some((arrangement) => arrangement.owner === owner))
    throw new Error("leaf: arrangement owner is already live");
  if ([...arrangements].some((arrangement) => arrangement.content === content))
    throw new Error("leaf: arrangement content is already live");
  const cleanups = admitRegions(declared);
  const arrangement = { owner, content, posture: null, generation: 0 };
  arrangements.add(arrangement);

  const affectedRegions = () =>
    [...regions.values()]
      .filter((region) => live(region) && containsAcross(owner, region.host))
      .map(regionRecord);

  return {
    async setPosture(posture) {
      if (!["bounded", "flow"].includes(posture))
        throw new Error(`leaf: unknown reading posture ${String(posture)}`);
      const from = postureOf(arrangement);
      if (from === posture && arrangement.posture === posture) return;
      const generation = ++arrangement.generation;
      const affected = affectedRegions();
      notify({ phase: "before", owner, from, to: posture, regions: affected });
      arrangement.posture = posture;
      owner.dataset.lfPosture = posture;
      content.dataset.lfPosture = posture;
      layoutChanged(owner);
      await new Promise((resolve) => requestAnimationFrame(resolve));
      if (generation !== arrangement.generation) return;
      notify({ phase: "after", owner, from, to: posture, regions: affected });
    },
    cleanup() {
      arrangement.generation += 1;
      arrangements.delete(arrangement);
      for (const cleanup of cleanups) cleanup();
      owner.removeAttribute("data-lf-posture");
      content.removeAttribute("data-lf-posture");
    },
  };
}
