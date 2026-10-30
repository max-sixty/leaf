/* Reading regions are stable semantic places whose current scroll container may change.

   `registerReadingRegion` binds one stable id to a host and body. The host makes focus
   in a pane's header or footer select that pane; the body is the region's scroller
   whenever the stylesheet makes it scroll, which is the only reading of scroll behavior there
   is: a bounded region's body scrolls, and a flowing one's is carried by the region
   containing it or by the page. CSS decides that from the space a workspace has
   (layouts.css, the workspace Layout), so nothing here chooses a scroll behavior.

   Every box Leaf makes scroll vertically is a region, so every question that names the
   box scrolling a node (`scrollerFor`, and `scrollersOf` for the boxes around it) gets
   that box rather than the page: a pane's body, the Threads list, a compound widget's
   parts, and a block bounded with x-bound or data-bound, which `bounds.js` registers. A
   box page CSS makes scroll is none of these. It stays unsupported: `page check`
   advises bounding the block instead, and nothing here searches the DOM for scrollers.
   Containment follows the rendered tree, including assigned slots: a native message
   laid out by a package's shadow reader belongs to that reader's region.

   A region's scroller can change without any gesture: a window crossing the workspace
   threshold, a tab showing, a panel opening. A region whose width changes keeps its
   scroller but rewraps, which moves its words under the reader just the same. Each
   region's host is watched for size, and a region whose scroller is no longer the one
   last seen, or whose width is not, is announced to watchers as a `shift`, after the new
   geometry exists. A viewport height change shifts every shown region, including
   flowing bodies whose own size stays the same while their visible band shrinks. The
   page is watched the same way and shifts with no region: its width, and the top of its
   landing band, which the chrome moves when the window's width gives it another row.
   Continuity owners record the user's place continuously and restore it on a shift;
   this module stores no landmarks or scroll offsets. `preserveReadingRegions` brackets
   a composition change with the same
   watchers, as `before` and `after`, retaining only scrollers inside that composition
   when regions become hidden or visible. Hidden connected regions remain registered and
   return null bounds. A region whose body is a closed `<details>` is concealed though
   its summary shows: none of what it holds does, so there is no place in it to read.
   Cleanup removes live DOM bindings, so a replacement can reclaim an id.

   The reach pass paints continuation at the body's scroll edges. An owner whose
   chrome covers the upper edge can supply `paintContinuation(above)` to paint that
   cue at its actual edge, on the same scroll and size observations. It receives
   false when no words remain above or the region is released.

   A region can show one subject of several in turn, as a trace's saved tree shows one
   checkpoint's elements at a time. Its owner replaces the body's contents through
   `showReadingSubject(id, subject, render)`, which tells watchers the subject is
   `leaving` and then `showing`, so a continuity owner keeps the reader's place in each
   subject and returns them to it.

   `onReadingInput` tells a reader where the user explicitly clicked or stepped by Tab.
   It includes unfocusable words, which update the reading region without a focus
   arrival. Mechanical returns, programmatic arrivals and scrolling are not choices
   of another passage. Each consumer interprets that target in its own domain. */
import { nextRender, sizeObserver } from "./rendering.js";
import { landingBand, shownRect, userScrollport } from "./geometry.js";
import { skipped } from "./shown-box.js";
import { pageScroller } from "./scrolling.js";
import { reachReadingScroller } from "./reach.js";
import { under, renderedUnder, renderedParent } from "./shadow.js";
import { layoutBox, pageDocument } from "./passages.js";
import { deepFocus, onCurrentLocation, pressing } from "./focus.js";

const regions = new Map();
const transitionWatchers = new Set();

const depthOf = (node) => {
  let depth = 0;
  for (let current = node; current; current = renderedParent(current)) depth += 1;
  return depth;
};

const live = (region) => region?.host?.isConnected && region.body?.isConnected;

// Three questions about a region's visibility, each asked where its cost and answer fit:
// `concealed` reads the page's own attributes alone, so the inventory decides what to
// sample without asking any geometry; `shown` (below) asks whether the browser draws
// the host at all, which a region scrolled out of the window still is; `hidden` asks
// whether the region has bounds to give now, concealed or clipped away entirely.
const concealed = (region) =>
  region.host.hidden ||
  region.host.closest?.("[hidden], [aria-hidden='true']") !== null ||
  region.body.matches("details:not([open])");

const hidden = (region) =>
  !live(region) || concealed(region) || shownRect(region.host, new Map()) === null;

const regionRecord = (region) => ({
  id: region.id,
  host: region.host,
  body: region.body,
  subject: region.subject,
});

export function compoundReadingRegionId(owner, localName) {
  if (!owner?.id || !/^[a-z][a-z0-9-]*$/.test(localName ?? ""))
    throw new Error("leaf: a compound reading region needs an owner id and local name");
  return `lf-region:${owner.id}:${localName}`;
}

export function registerReadingRegion({
  id,
  host,
  body,
  paintContinuation = undefined,
}) {
  if (typeof id !== "string" || !id || !host || !body)
    throw new Error("leaf: a reading region needs id, host, and body");
  if (live(regions.get(id)))
    throw new Error(`leaf: reading region ${id} is already live`);
  const region = {
    id,
    host,
    body,
    subject: undefined,
    scroller: null,
    width: null,
    away: false,
  };
  const stopReaching = reachReadingScroller(body, paintContinuation);
  regions.set(id, region);
  sizes.observe(host);
  return () => {
    if (regions.get(id) === region) regions.delete(id);
    sizes.unobserve(host);
    stopReaching();
  };
}

// The boxes a page's Layout makes scroll, which no widget owns: the workspace's body,
// which scrolls as a whole where a pane in it does not bound itself, and a sidebar
// page's authored `layout-track`, which scrolls while it stands beside the body
// (layouts.css). The stylesheet marks each one
// (`--lf-reading-region: layout`): a child of `main`, or the only child of one that is
// not itself marked. Each is registered like any other region, so what it holds is
// carried by it rather than by the page, and its scroll behavior is read from whether it
// scrolls. Its id is the authored id of the box or, for an only child, of the child of
// `main` holding it, as a sidebar page's `aside` names that box, so a neighbour's
// arrival or removal never renames it; an unnamed one takes its place among the unnamed
// ones, in a namespace of its own. Document composition asks on every pass, since a
// revision can replace `main`'s children and a resize can change which of them the stylesheet marks.
const layoutRegions = new Map();
const marked = (box) =>
  box.checkVisibility() &&
  getComputedStyle(box).getPropertyValue("--lf-reading-region").trim() === "layout";
export function syncLayoutRegion() {
  const main = layoutBox();
  const bodies = main
    ? [...main.children].flatMap((child) => {
        if (marked(child)) return [[child, child.id]];
        const only = child.childElementCount === 1 ? child.firstElementChild : null;
        return only && marked(only) ? [[only, only.id || child.id]] : [];
      })
    : [];
  let unnamed = 0;
  const ids = new Map(
    bodies.map(([body, name]) => [
      body,
      name ? `lf-region:layout#${name}` : `lf-region:layout@${unnamed++}`,
    ]),
  );
  for (const [body, region] of layoutRegions)
    if (ids.get(body) !== region.id) {
      region.stop();
      layoutRegions.delete(body);
    }
  for (const [body, id] of ids)
    if (!layoutRegions.has(body))
      layoutRegions.set(body, {
        id,
        stop: registerReadingRegion({ id, host: body, body }),
      });
}

// Replace a region's contents with another subject's (see the header). A region not
// registered yet has no place to keep, so the render runs alone.
export function showReadingSubject(id, subject, render) {
  const region = regions.get(id);
  if (!live(region) || region.subject === subject) {
    if (region) region.subject = subject;
    return render();
  }
  notify({ phase: "leaving", region: regionRecord(region) });
  region.subject = subject;
  const rendered = render();
  notify({ phase: "showing", region: regionRecord(region) });
  return rendered;
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
    .filter((candidate) => live(candidate) && renderedUnder(node, candidate.host))
    .sort((a, b) => depthOf(b.host) - depthOf(a.host))[0];
  return region;
};

export const readingRegionFor = (node) => {
  const region = regionAt(node);
  return region && regionRecord(region);
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
// arrived as a change where the user is (focus.js, `onCurrentLocation`), or the body,
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
// That focus belongs to the same press while it is down (focus.js, `pressing`);
// pointerdown has already named its place.
const readingInputReaders = new Set();
export const onReadingInput = (read) => readingInputReaders.add(read);
const readingInput = (node) => {
  for (const read of readingInputReaders) read(node);
};
const actedAt = (at, arriving) => {
  const region = readingRegionFor(at);
  if (region) {
    recentRegionId = region.id;
    if (under(region.host, pageDocument())) pageRegionId = region.id;
  } else if (
    (at === document.body || under(at, pageDocument())) &&
    !(arriving && at === document.body && pressing()?.released === false)
  )
    recentRegionId = pageRegionId = null;
};
for (const type of ["pointerdown", "wheel", "touchstart", "click"])
  addEventListener(
    type,
    (event) => {
      const at = event.composedPath()[0];
      if (type !== "click") actedAt(at, false);
      else if (event.isTrusted && /** @type {MouseEvent} */ (event).button === 0)
        readingInput(at);
    },
    { capture: true, passive: true },
  );
// An arrival, by whatever route, a move inside a widget's shadow tree included.
onCurrentLocation((node, cause) => {
  if (node) actedAt(node, true);
  if (node && cause === "step") readingInput(node);
});
export const recentReadingRegion = () => readingRegion(recentRegionId);
// A region hidden from layout — a closed panel's list, a pane in a tab not shown — is not
// where the user reads. One scrolled out of the window still is.
const shown = (region) => (region?.host.checkVisibility() ? region : undefined);
export const pageReadingRegion = () => {
  const at = deepFocus();
  if (under(at, pageDocument())) return readingRegionFor(at);
  return shown(readingRegion(pageRegionId));
};
export const userReadingRegion = () => {
  const at = deepFocus();
  const region = readingRegionFor(at);
  if (region || under(at, pageDocument())) return region;
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
    if (renderedUnder(node, region.body)) return regionRecord(region);
    region = regionAt(renderedParent(region.host));
  }
  return undefined;
};

const asRegion = (regionOrNode) =>
  typeof regionOrNode === "string"
    ? regions.get(regionOrNode)
    : (regions.get(regionOrNode?.id) ??
      regions.get(readingRegionFor(regionOrNode)?.id));

const scrolls = (box) => userScrollport(getComputedStyle(box).overflowY);

// "bounded" when the region's own body scrolls, "flow" when something outside it does.
export const regionScrollBehavior = (regionOrNode) => {
  const region = asRegion(regionOrNode);
  return region &&
    live(region) &&
    !concealed(region) &&
    !skipped(region.body) &&
    scrolls(region.body)
    ? "bounded"
    : "flow";
};

export function effectiveScroller(regionOrNode) {
  const region = asRegion(regionOrNode);
  if (!region) return pageScroller;
  if (regionScrollBehavior(region) === "bounded") return region.body;
  const containing = [...regions.values()]
    .filter(
      (candidate) =>
        candidate !== region &&
        live(candidate) &&
        renderedUnder(region.host, candidate.body),
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
  for (let box = scrollerFor(node); ; box = scrollerFor(renderedParent(box))) {
    for (let at = node; at !== box; at = renderedParent(at))
      if (!at || getComputedStyle(at).position === "fixed") return;
    yield box;
    if (box === pageScroller) return;
    node = box;
  }
}

// The boxes a scroll passes to once each inner one is spent, as native input chains it
// at a box whose overscroll-behavior lets it go: `scrollersOf`'s, then the page's. A
// fixed box ends `scrollersOf` because the page's scroll leaves it in place, but its
// scroll still chains to the page, the box its containing block, the viewport, scrolls.
export function* scrollChainOf(node) {
  let last = null;
  for (last of scrollersOf(node)) yield last;
  if (last !== pageScroller) yield pageScroller;
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
let viewportHeight = innerHeight;

// The page's width and the top of its landing band as last seen, or null before the
// first delivery. The page needs no registration: the root is always there, and its
// size changes only with the window's.
let pageSeen = null;
const pageGeometry = () => ({
  width: pageScroller.clientWidth,
  band: landingBand(pageScroller)?.top ?? 0,
});
// A band that moves with the window's width shifts the page. One that moves without
// it, as a page tab strip arriving does (`--lf-root-headers`, page-layout.js), comes with
// the content that moved it, whose owner keeps the reader's place across it, so it is
// taken as seen wherever it is read: no size need change with it, and left unseen it
// would read as unsettled, recording nothing, until the window next changed.
const pageMoved = (now = pageGeometry()) => {
  if (pageSeen === null) return false;
  if (now.width !== pageSeen.width) return true;
  pageSeen = now;
  return false;
};

// Whether the page and every region stand as last seen. A layout that has handed a
// region to another scroller or rewrapped it or the page, before the observer below has
// announced it, is not a place to record the user's position in: the words have already
// moved under the reader (a flow page clamps as its content leaves), and the restore the
// announcement brings would return them to that moved place. A region hidden from layout
// shows no words to move, and measuring one in skipped content would lay out what it
// skips.
export const regionsSettled = () =>
  viewportHeight === innerHeight &&
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
function measureRegions() {
  const viewportChanged = viewportHeight !== innerHeight;
  viewportHeight = innerHeight;
  const shifted = [];
  for (const region of regions.values()) {
    if (!live(region) || !shown(region)) continue;
    const scroller = effectiveScroller(region);
    const width = region.host.offsetWidth;
    // A region concealed when last measured, as a closed disclosure's, returns: its
    // words stood in no scroller meanwhile, though one carried its box.
    const away = concealed(region);
    if (region.scroller && (viewportChanged || !asSeen(region, scroller, width)))
      shifted.push({
        region: regionRecord(region),
        from: region.scroller,
        to: scroller,
        returned: Boolean(region.away) && !away,
      });
    region.scroller = scroller;
    region.width = width;
    region.away = away;
  }
  const now = pageGeometry();
  if (pageMoved(now)) shifted.push({ region: null, band: now.band - pageSeen.band });
  pageSeen = now;
  if (shifted.length) notify({ phase: "shift", shifted });
}
const sizes = sizeObserver(measureRegions);
sizes.observe(pageScroller);
// A flowing region need not resize when only the window's height changes.
// Share the observer's comparison so one reflow produces one shift reading.
addEventListener("resize", () => nextRender(measureRegions), { passive: true });
