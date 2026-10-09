/* Reading regions are stable semantic places whose current scroll container may change.

   `registerReadingRegion` binds one stable id to a host and body. The host makes focus
   in a pane's header or footer select that pane; the body is the region's scroller
   whenever the stylesheet makes it scroll, which is the only reading of posture there
   is: a bounded region's body scrolls, and a flowing one's is carried by the region
   containing it or by the page. CSS decides that from the space a workspace has
   (layouts.css, the workspace Layout), so nothing here chooses a posture.

   A separately scrolling piece of a region's apparatus declares `apparatusFor`, the
   owning region's id. It stays in the physical scroll inventory, while focus and
   gestures there select its owner for reading. Containment still names the apparatus's
   own box, so bringing its controls into view never mistakes the owner's reading body
   for the box that actually carries them.

   Every box Leaf makes scroll vertically is a region, so every question that names the
   box scrolling a node (`scrollerFor`, and `scrollersOf` for the boxes around it) gets
   that box rather than the page: a pane's body, the Threads list, a compound widget's
   parts, and a block bounded with x-bound or data-bound, which `bounds.js` registers. A
   box page CSS makes scroll is none of these. It stays unsupported: `page check`
   advises bounding the block instead, and nothing here searches the DOM for scrollers.

   A region's scroller can change without any gesture: a window crossing the workspace
   threshold, a tab showing, a panel opening. A region whose width changes keeps its
   scroller but rewraps, which moves its words under the reader just the same. Each
   region's host is watched for size, and a region whose scroller is no longer the one
   last seen, or whose width is not, is announced to watchers as a `shift`, after the new
   geometry exists. The page is watched the same way and shifts with no region: its
   width, and the top of its landing band, which the banner moves when the window's width
   gives it another row. Continuity owners record the user's place continuously and
   restore it on a shift; this module stores no landmarks or scroll offsets. `preserveReadingRegions` brackets a composition change with the same
   watchers, as `before` and `after`, retaining only scrollers inside that composition
   when regions become hidden or visible. Hidden connected regions remain registered and
   return null bounds. Cleanup removes live DOM bindings, so a replacement can reclaim an
   id.

   `onReadingInput` tells a reader where the user explicitly clicked or stepped by Tab.
   It includes unfocusable words, which update the reading region without a focus
   arrival. Mechanical returns, programmatic arrivals and scrolling are not choices
   of another passage. Each consumer interprets that target in its own domain. */
import { sizeObserver } from "./rendering.js";
import { landingBand, shownRect, skipped } from "./geometry.js";
import { pageScroller } from "./scrolling.js";
import { reachReadingScroller } from "./reach.js";
import { under, upFrom } from "./shadow.js";
import { deepFocus, onStanding, pressing } from "./focus.js";

const regions = new Map();
const transitionWatchers = new Set();

const depthOf = (node) => {
  let depth = 0;
  for (let current = node; current; current = upFrom(current)) depth += 1;
  return depth;
};

const live = (region) => region?.host?.isConnected && region.body?.isConnected;

const concealed = (region) =>
  region.host.hidden ||
  region.host.closest?.("[hidden], [aria-hidden='true']") !== null;

const hidden = (region) =>
  !live(region) || concealed(region) || shownRect(region.host, new Map()) === null;

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

export function registerReadingRegion({ id, host, body, apparatusFor = null }) {
  if (typeof id !== "string" || !id || !host || !body)
    throw new Error("leaf: a reading region needs id, host, and body");
  if (live(regions.get(id)))
    throw new Error(`leaf: reading region ${id} is already live`);
  if (apparatusFor !== null && !live(regions.get(apparatusFor)))
    throw new Error("leaf: reading apparatus needs a live owning region");
  const region = { id, host, body, apparatusFor, scroller: null, width: null };
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

// Keep a region in the inventory while an authored disclosure or tab conceals it,
// but never ask its geometry merely to decide whether to sample it.
export const unconcealedReadingRegions = () =>
  [...regions.values()]
    .filter((region) => live(region) && !concealed(region) && !skipped(region.body))
    .map(regionRecord);

const regionAt = (node) => {
  const region = [...regions.values()]
    .filter((candidate) => live(candidate) && under(node, candidate.host))
    .sort((a, b) => depthOf(b.host) - depthOf(a.host))[0];
  return region;
};

export const readingRegionFor = (node) => {
  const region = regionAt(node);
  return region?.apparatusFor
    ? readingRegion(region.apparatusFor)
    : region && regionRecord(region);
};

// The region the user is reading in, which the reading keys scroll and continuity
// restores first. Focus answers where it stands on the page or in a region; otherwise
// the user's last press, wheel, touch or arrival does, which is the platform's own rule
// for Space and PageDown: with nothing focused, Chrome scrolls from the node last
// pressed. A click on a pane's words focuses nothing, so without this a pane the user had
// just clicked into was no answer at all, and `d` scrolled a page a full-height workspace keeps
// still. Anything on the page outside every region names the page, which is `undefined`
// here as it is for `readingRegionFor`, and so does the body, where a let-go
// (`releaseFocus`) or a press on nothing puts the user. Anything in the chrome names
// nothing new, so opening a menu leaves the pane the user was reading as the answer.
// A key press is not among them: its target is where focus already stands, which
// arrived as a change where the user stands (focus.js, `onStanding`), or the body,
// which is where a click on words leaves it.
//
// The page's own answer is kept apart from a surface's. A region in the chrome, such as
// the Threads list, answers while it shows; once it has closed, the user is back in the
// page region they acted in last (`pageReadingRegion`), which a surface opened on top of
// it never replaced. A landing in the document asks the page's answer alone, since a
// surface is no part of the document it lands in.
let recentRegionId = null;
let pageRegionId = null;
// Chrome can focus body between pointerdown on unfocusable words and pointerup.
// That focus belongs to the same press (focus.js, `pressing`); pointerdown has already
// named its place.
const readingInputReaders = new Set();
export const onReadingInput = (read) => readingInputReaders.add(read);
const readingInput = (node) => {
  for (const read of readingInputReaders) read(node);
};
const pageRoot = () => document.querySelector("body > main");
const actedAt = (at, arriving) => {
  const region = readingRegionFor(at);
  if (region) {
    recentRegionId = region.id;
    if (under(region.host, pageRoot())) pageRegionId = region.id;
  } else if (
    (at === document.body || under(at, pageRoot())) &&
    !(arriving && at === document.body && pressing())
  )
    recentRegionId = pageRegionId = null;
};
for (const type of ["pointerdown", "wheel", "touchstart", "click"])
  addEventListener(
    type,
    (event) => {
      const at = event.composedPath()[0];
      if (type !== "click") actedAt(at, false);
      else if (event.isTrusted && event.button === 0) readingInput(at);
    },
    { capture: true, passive: true },
  );
// An arrival, by whatever route, a move inside a widget's shadow tree included.
onStanding((node, cause) => {
  if (node) actedAt(node, true);
  if (node && cause === "step") readingInput(node);
});
export const recentReadingRegion = () => readingRegion(recentRegionId);
// A region hidden from layout — a closed panel's list, a pane in a tab not shown — is not
// where the user reads. One scrolled out of the window still is.
const shown = (region) => (region?.host.checkVisibility() ? region : undefined);
export const pageReadingRegion = () => {
  const at = deepFocus();
  if (under(at, pageRoot())) return readingRegionFor(at);
  return shown(readingRegion(pageRegionId));
};
export const userReadingRegion = () => {
  const at = deepFocus();
  const region = readingRegionFor(at);
  if (region || under(at, pageRoot())) return region;
  return shown(recentReadingRegion()) ?? pageReadingRegion();
};

// The deepest region whose body actually contains this node. A region's host includes
// its frame furniture so focus there can still select the region for reading commands;
// geometry that must contain the node itself instead walks outward to the body it lives
// in. Keep that containment walk shared with scrollerFor so placement and travel cannot
// disagree about which reading box holds a control.
export const containingReadingRegionFor = (node) => {
  let region = regionAt(node);
  while (region) {
    if (under(node, region.body)) return regionRecord(region);
    region = regionAt(region.host.parentElement);
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

// Whether a region is scrolled by the box last seen for it, at the width last seen.
const asSeen = (region, scroller, width) =>
  region.scroller === scroller && region.width === width;

// The page's width and the top of its landing band as last seen, or null before the
// first delivery. The page needs no registration: the root is always there, and its
// size changes only with the window's.
let pageSeen = null;
const pageGeometry = () => ({
  width: pageScroller.clientWidth,
  band: landingBand(pageScroller)?.top ?? 0,
});
const pageMoved = (now = pageGeometry()) =>
  pageSeen !== null && (now.width !== pageSeen.width || now.band !== pageSeen.band);

// Whether the page and every region stand as last seen. A layout that has handed a
// region to another scroller or rewrapped it or the page, before the observer below has
// announced it, is not a place to record the user's position in: the words have already
// moved under the reader (a flow page clamps as its content leaves), and the restore the
// announcement brings would return them to that moved place. A region hidden from layout
// shows no words to move, and measuring one in skipped content would lay out what it
// skips.
export const regionsSettled = () =>
  !pageMoved() &&
  [...regions.values()].every(
    (region) =>
      !live(region) ||
      !region.scroller ||
      !shown(region) ||
      asSeen(region, effectiveScroller(region), region.host.offsetWidth),
  );

// Every shown region's scroller and width as last seen, and the page's geometry, so a
// size change that hands a region to a different scroller, or rewraps it or the page, is
// announced once, after layout has produced it. A hidden region keeps what was last seen
// of it and is compared again once it shows. Read on the observer's delivery, which
// follows layout; nothing here writes a box it observes.
const sizes = sizeObserver(() => {
  const shifted = [];
  for (const region of regions.values()) {
    if (!live(region) || !shown(region)) continue;
    const scroller = effectiveScroller(region);
    const width = region.host.offsetWidth;
    if (region.scroller && !asSeen(region, scroller, width))
      shifted.push({
        region: regionRecord(region),
        from: region.scroller,
        to: scroller,
      });
    region.scroller = scroller;
    region.width = width;
  }
  const now = pageGeometry();
  if (pageMoved(now)) shifted.push({ region: null, band: now.band - pageSeen.band });
  pageSeen = now;
  if (shifted.length) notify({ phase: "shift", shifted });
});
sizes.observe(pageScroller);
// A band that moves with the window's width shifts the page (above). One that moves
// without it, as a page tab strip arriving does (`--lf-root-headers`, lf-tabs.js), comes
// with the content that moved it, which that content's owner keeps the reader's place
// across, so it is only seen: otherwise the page would read as unsettled, and record
// nothing, until the window next changed. The body changes size whenever that content
// arrives or leaves. Uncounted, since a page's body can grow for as long as it plays.
sizeObserver(
  () => {
    const now = pageGeometry();
    if (pageSeen && now.width === pageSeen.width) pageSeen = now;
  },
  { counted: false },
).observe(document.body);
