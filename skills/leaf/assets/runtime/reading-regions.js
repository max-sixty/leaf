/* Reading regions are stable semantic places whose current scroll container may change.

   `registerReadingRegion` binds one stable id to a host and body. The host makes focus
   in a pane's header or footer select that pane; the body is the region's scroller
   whenever the stylesheet makes it scroll, which is the only reading of posture there
   is: a bounded region's body scrolls, and a flowing one's is carried by the region
   containing it or by the page. CSS decides that from the space a workspace has
   (layouts.css, the workspace Layout), so nothing here chooses a posture.

   Every box Leaf makes scroll vertically is a region, so every question that names the
   box scrolling a node (`scrollerFor`, and `scrollersOf` for the boxes around it) gets
   that box rather than the page: a pane's body, the Threads list, a compound widget's
   parts, and a block bounded with x-bound or data-bound, which `bounds.js` registers. A
   box page CSS makes scroll is none of these. It stays unsupported: `version check`
   advises bounding the block instead, and nothing here searches the DOM for scrollers.

   A region's scroller can change without any gesture: a window crossing the workspace
   threshold, a tab showing, a panel opening. Each region's host is watched for size, and
   a region whose scroller is no longer the one last seen is announced to watchers as a
   `shift`, after the new geometry exists. Continuity owners record the user's place
   continuously and restore it on a shift; this module stores no landmarks or scroll
   offsets. `preserveReadingRegions` brackets a composition change with the same
   watchers, as `before` and `after`, retaining only scrollers inside that composition
   when regions become hidden or visible. Hidden connected regions remain registered and
   return null bounds. Cleanup removes live DOM bindings, so a replacement can reclaim an
   id. */
import { sizeObserver } from "./rendering.js";
import { shownRect } from "./geometry.js";
import { pageScroller } from "./scrolling.js";
import { reachReadingScroller } from "./reach.js";
import { under, upFrom } from "./shadow.js";
import { deepFocus } from "./focus.js";

const regions = new Map();
const transitionWatchers = new Set();

const depthOf = (node) => {
  let depth = 0;
  for (let current = node; current; current = upFrom(current)) depth += 1;
  return depth;
};

const live = (region) => region?.host?.isConnected && region.body?.isConnected;

const hidden = (region) =>
  !live(region) ||
  region.host.hidden ||
  region.host.closest?.("[hidden], [aria-hidden='true']") !== null ||
  shownRect(region.host, new Map()) === null;

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

export function registerReadingRegion({ id, host, body }) {
  if (typeof id !== "string" || !id || !host || !body)
    throw new Error("leaf: a reading region needs id, host, and body");
  if (live(regions.get(id)))
    throw new Error(`leaf: reading region ${id} is already live`);
  const region = { id, host, body, scroller: null };
  const stopReaching = reachReadingScroller(body);
  regions.set(id, region);
  sizes.observe(host);
  return () => {
    if (regions.get(id) === region) regions.delete(id);
    sizes.unobserve(host);
    stopReaching();
  };
}

// The box a page's Layout makes scroll, which no widget owns: the workspace's body,
// which scrolls as a whole where a pane in it does not bound itself (layouts.css). The
// stylesheet marks it (`--lf-reading-region: layout`) and it is registered like any
// other region, so a flowing pane inside it is carried by it rather than by the page.
// Chrome layout asks on every pass, since a revision can replace `main`'s children.
let layoutRegion = null;
export function syncLayoutRegion() {
  const main = document.querySelector("main");
  const body = main
    ? [...main.children].find(
        (child) =>
          child.checkVisibility() &&
          getComputedStyle(child).getPropertyValue("--lf-reading-region").trim() ===
            "layout",
      )
    : undefined;
  if (body === layoutRegion?.body) return;
  layoutRegion?.stop();
  layoutRegion = body
    ? {
        body,
        stop: registerReadingRegion({ id: "lf-region:layout", host: body, body }),
      }
    : null;
}

export const readingRegion = (id) => {
  const region = regions.get(id);
  return live(region) ? regionRecord(region) : undefined;
};

export const readingRegions = () =>
  [...regions.values()].filter(live).map(regionRecord);

export const readingRegionFor = (node) => {
  const region = [...regions.values()]
    .filter((candidate) => live(candidate) && under(node, candidate.host))
    .sort((a, b) => depthOf(b.host) - depthOf(a.host))[0];
  return region && regionRecord(region);
};

// The region the user is reading in, which the reading keys scroll and continuity
// restores first. Focus answers where it stands on the page or in a region; otherwise
// the user's last press, wheel, touch or arrival does, which is the platform's own rule
// for Space and PageDown: with nothing focused, Chrome scrolls from the node last
// pressed. A click on a pane's words focuses nothing, so without this a pane the user had
// just clicked into was no answer at all, and `d` scrolled a page a held workspace keeps
// still. Anything on the page outside every region names the page, which is `undefined`
// here as it is for `readingRegionFor`, and so does the body, where a let-go
// (`releaseFocus`) or a press on nothing puts the user. Anything in the chrome names
// nothing new, so opening a menu leaves the pane the user was reading as the answer.
// A key press is not among them: its target is where focus already stands, which
// arrived by `focusin`, or the body, which is where a click on words leaves it.
let recentRegionId = null;
const pageRoot = () => document.querySelector("body > main");
const actedIn = (event) => {
  const at = event.composedPath()[0];
  const region = readingRegionFor(at);
  if (region) recentRegionId = region.id;
  else if (at === document.body || under(at, pageRoot())) recentRegionId = null;
};
for (const type of ["pointerdown", "wheel", "touchstart", "focusin"])
  addEventListener(type, actedIn, { capture: true, passive: true });
export const recentReadingRegion = () => readingRegion(recentRegionId);
export const userReadingRegion = () => {
  const at = deepFocus();
  const region = readingRegionFor(at);
  if (region || under(at, pageRoot())) return region;
  return recentReadingRegion();
};

// The deepest region whose body actually contains this node. A region's host includes
// its frame furniture so focus there can still select the region for reading commands;
// geometry that must contain the node itself instead walks outward to the body it lives
// in. Keep that containment walk shared with scrollerFor so placement and travel cannot
// disagree about which reading box holds a control.
export const containingReadingRegionFor = (node) => {
  let region = readingRegionFor(node);
  while (region) {
    if (under(node, region.body)) return region;
    region = readingRegionFor(region.host.parentElement);
  }
  return undefined;
};

const asRegion = (regionOrNode) =>
  typeof regionOrNode === "string"
    ? regions.get(regionOrNode)
    : (regions.get(regionOrNode?.id) ??
      regions.get(readingRegionFor(regionOrNode)?.id));

const scrolls = (box) => /auto|scroll/.test(getComputedStyle(box).overflowY);

// "bounded" when the region's own body scrolls, "flow" when something outside it does.
export const readingPosture = (regionOrNode) => {
  const region = asRegion(regionOrNode);
  return region && live(region) && scrolls(region.body) ? "bounded" : "flow";
};

export function effectiveScroller(regionOrNode) {
  const region = asRegion(regionOrNode);
  if (!region) return pageScroller;
  if (readingPosture(region) === "bounded") return region.body;
  const containing = [...regions.values()]
    .filter(
      (candidate) =>
        candidate !== region && live(candidate) && under(region.host, candidate.body),
    )
    .sort((a, b) => depthOf(b.host) - depthOf(a.host))[0];
  return containing ? effectiveScroller(containing) : pageScroller;
}

// Which box scrolls a given element, for anything that has to name its scroller rather
// than search for one. The document's for everything the document holds — and the
// panel's own list for a widget an agent put in a reply, which is scrolled by that and
// by nothing else. A drag naming the wrong one sits at the edge waiting for a scroll
// that never comes. The list answers here as any region does: the panel registers it as
// its bounded reading region (`mountPanelReadingRegion`).
export const scrollerFor = (el) => {
  const region = containingReadingRegionFor(el);
  return region ? effectiveScroller(region) : pageScroller;
};

// Every box whose scroll moves a node, innermost first: its region's scroller, then the
// box scrolling that one, out to the page. A move the inner box cannot take whole is
// the next one's to finish: a bounded block not yet full grows in the page rather than
// scrolling, and a region scrolled to its end moves no further. A fixed box between a
// node and a scroller stands still while that scroller moves, so the walk ends there.
export function* scrollersOf(node) {
  for (let box = scrollerFor(node); ; box = scrollerFor(upFrom(box))) {
    for (let at = node; at !== box; at = upFrom(at))
      if (!at || getComputedStyle(at).position === "fixed") return;
    yield box;
    if (box === pageScroller) return;
    node = box;
  }
}

export function shownRegionBounds(regionOrNode) {
  const region = asRegion(regionOrNode);
  if (!region || hidden(region)) return null;
  return shownRect(region.body, new Map());
}

export function watchReadingRegionTransitions(listener) {
  transitionWatchers.add(listener);
  return () => transitionWatchers.delete(listener);
}

const notify = (detail) => {
  for (const listener of transitionWatchers) listener(detail);
};

const compositionTransitions = new Map();

export async function preserveReadingRegions(owner, change) {
  const transition = {
    owner,
    regions: readingRegions().filter((region) => under(region.host, owner)),
  };
  // A second choice can supersede an unfinished layout. Its intermediate geometry
  // must not overwrite the reading captured before the first choice.
  notify({
    ...transition,
    phase: "before",
    retained: compositionTransitions.has(owner),
  });
  compositionTransitions.set(owner, transition);
  let completed = false;
  try {
    await change();
    completed = true;
  } finally {
    if (compositionTransitions.get(owner) === transition) {
      compositionTransitions.delete(owner);
      notify({
        ...transition,
        phase: "after",
        cancelled: !completed || !owner.isConnected,
      });
    }
  }
}

// Whether every region is still scrolled by the box last seen for it. A layout that has
// handed a region to another scroller, before the observer below has announced it, is
// not a place to record the user's position in: the old scroller has already let go
// of it (a flow page clamps as its content leaves).
export const scrollersSettled = () =>
  [...regions.values()].every(
    (region) =>
      !live(region) ||
      !region.scroller ||
      effectiveScroller(region) === region.scroller,
  );

// Every region's scroller as last seen, so a size change that hands a region to a
// different scroller is announced once, after layout has produced it. Read on the
// observer's delivery, which follows layout; nothing here writes a box it observes.
const sizes = sizeObserver(() => {
  const shifted = [];
  for (const region of regions.values()) {
    if (!live(region)) continue;
    const scroller = effectiveScroller(region);
    if (region.scroller && region.scroller !== scroller)
      shifted.push({
        region: regionRecord(region),
        from: region.scroller,
        to: scroller,
      });
    region.scroller = scroller;
  }
  if (shifted.length) notify({ phase: "shift", shifted });
});
